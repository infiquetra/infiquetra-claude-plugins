---
title: Issue #615 — workflow-child lease binding — complete the driver-batch claim seam
type: fix
status: active
date: 2026-07-22
---

# Issue #615 — workflow-child lease binding — complete the driver-batch claim seam

## Summary

Workflow-dispatched subagents can never bind a fleet lease, so armed lease hooks fail-close every
governed Workflow run (defect #615). The #356 driver-side batch protocol already reserves, attests,
renews, and releases a prelaunch wave — but two seams contradict it: `claim` refuses the unstamped
slots that `attest` requires, and slot recycling waits on a parent-completion signal that never fires
for Workflow children. This plan completes those two seams in the fleet-core broker, adds in-lock
batch keep-alive, and adds a documented emergency kill-switch to the saga hooks. No exemption path:
children get real leases, fencing tokens, and mutation verification.

## Problem Frame

Issue [#615](https://github.com/infiquetra/infiquetra-claude-plugins/issues/615) (defect,
high-priority; outcome `governed-execution-integrity` leaf
`leaf-governed-execution-integrity-sub-615`). Diff base `origin/main` `ee8a2b1a` (saga 0.109.0,
fleet-core 0.18.0).

**Mechanism, verified at `ee8a2b1a`.** The lease protocol has two event classes with different
firing behavior for Workflow children:

- **Tool-call events never fire.** `PreToolUse`/`PostToolUse` on `Agent|Task` are events on the
  root's Agent tool call. The Workflow runtime spawns children internally, so
  `reserve_hook_agent`/`prepare_batch_call` (slot stamping,
  `plugins/saga/scripts/lease_broker.py:288-329`) and `record_hook_parent` (slot release + batch
  renewal, `plugins/saga/scripts/lease_broker.py:363-378`) never run for them.
- **Lifecycle events do fire.** `SubagentStart` reaches `claim_hook_agent`
  (`plugins/saga/scripts/lease_broker.py:338-353`) — the #615 evidence is precisely its
  `LeaseNotFoundError` — and `SubagentStop` reaches `record_hook_terminal`
  (`plugins/saga/scripts/lease_broker.py:356-360`).

The driver-side wave protocol (`plugins/saga/scripts/workflow_emitter.py`, #356) already handles
the root half: `reserve` calls `reserve_batch` with `agent_type="*"` and unstamped slots
(`workflow_emitter.py:118-130`), and `attest` **requires** every prelaunch slot to have
`tool_use_id: None` and `agent_id: None` (`workflow_emitter.py:162-172`). But the broker's `claim`
filter excludes exactly that state: a batch candidate must have `lease.tool_use_id is not None`
(`plugins/fleet-core/scripts/fleet_commons/lease_broker.py:2634`). The stamping step in between
(`prepare_batch_call`) belongs to the never-firing `PreToolUse` path. The attested prelaunch batch
is therefore unclaimable by construction — the contradiction is the defect.

Two design breadcrumbs show claim-time unstamped binding was the intent: the claimed lease's
`logical_unit_id` already has an unstamped fallback (`selected.tool_use_id or
f"{session}:{kind}:{child}"`, `lease_broker.py:2645` — dead code today), and
`_complete_foreground_lease` already recycles a batch slot back to pristine unclaimed state
(`agent_id=None, tool_use_id=None, agent_type="*"`, `lease_broker.py:3811-3827`) — reachable for
Workflow children only through the also-never-firing parent-completion signal
(`record_child_terminal` completes only when `parent_completed_at` is set,
`lease_broker.py:3748-3754`).

**Cost of the standing workaround.** The installed cache hooks are hand-neutralized per Workflow
launch and every plugin update silently re-arms them, deterministically fail-closing the next
governed run (LEARNINGS `{#installed-hook-skew-fail-close-637}`; halted the first #637 launch).
Success retires that ritual.

## Requirements

R1. A Workflow-dispatched child in a session with a live attested batch binds a real lease at
`SubagentStart` with no `PreToolUse` stamp, and its delegated `Bash`/`Edit`/`Write` mutations pass
`verify_hook_mutation` fencing.

R2. The non-batch claim path (`batch_id=None`) is byte-identical to today — direct `Agent`-tool
spawns outside a batch session keep current behavior, regression-pinned.

R3. In a batch session, claim selection is deterministic and prefers stamped slots (by fencing
sequence) before unstamped ones. Flow-matching a stamp to "its" child is impossible —
`SubagentStart` does not expose the parent tool-use id (#356 KTD4) — and cross-ordered same-type
claims remain the pre-existing, pinned behavior (`tests/test_saga_hooks.py:152`).

R4. An **unstamped** claimed batch slot recycles to pristine prelaunch state on child-terminal
alone; a **stamped** slot keeps the #356 dual-signal release contract (child terminal + parent
completed) unchanged.

R5. Live slots of a batch are renewed under the broker lock as the batch's children start and
finish, and additionally on every delegated-mutation verification when the mutating lease belongs
to a batch (keep-alive without a daemon; renewal frequency scales with actual child activity, so a
lone long-running child stays alive through its own writes). An expired slot is never resurrected
by keep-alive; non-batch leases keep today's mutation-verification behavior byte-identical (R2).
*(D1 resolution (i), operator-pinned 2026-07-22.)*

R6. Capacity truth is preserved: slots are charged through `_admit_agent` at `reserve_batch` time;
`claim` never creates uncounted capacity; a batch with all slots claimed fails the next child
closed (existing soft-warn + mutation halt), and TTL reaps leaked slots.

R7. An emergency kill-switch environment variable (`INFIQUETRA_FLEET_LEASE_ENFORCEMENT=off`)
neutralizes both saga lease hooks with a loud per-event notice; any other value or absence leaves
them armed. Documented as emergency-only.

R8. Release surfaces move in the same PR: fleet-core `0.18.0 → 0.19.0` and saga
`0.109.0 → 0.110.0` (`plugin.json` ×2, `marketplace.json`, both `CHANGELOG.md`s), drift pins
(`tests/test_saga_plugin.py`; fleet-core pins at `tests/test_liveness_events.py:698`,
`tests/test_team_execution_liveness.py:179` and `:409`), DECISIONS entry, and
`scripts/check_release_surface_parity.py` clean.

R9. **Live acceptance (operator-gated, post-merge — like #618's R9).** Runs against the installed
plugin cache, so it happens after the plugin update installs saga 0.110.0 + fleet-core 0.19.0 (a
canary against the pre-update cache would test the old, broken hooks). With ARMED installed hooks:
(a) a minimal one-agent canary workflow performs a `Write` successfully end-to-end through
reserve → attest → launch; (b) a direct `Agent`-tool spawn without the admission preflight is still
refused. Passing retires the hand-neutralization ritual.

## Key Technical Decisions

KTD1. **Complete the #356 batch protocol at the broker's claim/terminal seam — no exemption, no
adapter special-case.** The attested prelaunch state (unstamped `agent_type="*"` slots) becomes
claimable; everything else in the protocol already exists. Rationale: `attest` guarantees exactly
this state (`workflow_emitter.py:162-172`); `claim`'s unstamped `logical_unit_id` fallback
(`lease_broker.py:2645`) shows the intent; an `agent_type` exemption (issue direction 2) would
remove fencing for precisely the fleet class that mutates most, and the SubagentStart payload's
`agent_type` for Workflow children is unverified — batch presence is a root-authorized signal, an
agent-type string is not.

KTD2. **Stamped-first claim ordering, for strict additivity.** Candidate selection prefers
`tool_use_id`-stamped slots (ordered by fencing sequence), falling back to the oldest unstamped
slot. Rationale: today only stamped slots are claimable in a batch, so stamped-first preserves the
existing selection byte-for-byte whenever a stamp exists — unstamped binding activates only where
today's path raises `LeaseNotFoundError`, making the change a pure behavioral superset. `claim`
cannot flow-match a stamp to a specific child (no parent tool-use id at `SubagentStart`, #356
KTD4); cross-binding under mixed direct+workflow traffic is pre-existing, bounded, and pinned
(`tests/test_saga_hooks.py:152`). Selection stays deterministic (`(stamped-first,
fencing_sequence, lease_id)`).

KTD3. **Child-terminal-only recycle for unstamped slots.** #356 KTD4's dual-signal rationale
("`SubagentStart` does not expose its parent tool-use ID") protects leases that HAVE a parent tool
call; an unstamped batch slot provably has none, so `record_child_terminal` completes (recycles) it
on the child signal alone. Stamped slots are untouched. Failure direction stays safe: if
`SubagentStop` never fires, the slot leaks until TTL — fail-closed, never fail-open.

KTD4. **Keep-alive rides the existing lifecycle events AND the mutation-verification path,
in-lock.** `claim` and `record_child_terminal` renew the live sibling slots of the same batch
inside the lock they already hold, and the mutation-verification seam (`assert_write_target`,
`lease_broker.py:3000-3039` — already called by `verify_hook_mutation` on every delegated
mutation) opportunistically renews the mutating lease and its live batch siblings when — and only
when — that lease is a batch member. Rationale: lifecycle events cover wave transitions; mutations
cover long-running children — closing the D1 event-starvation gap under the emitted 30s/300s TTLs
(`execution_spec.py:3331-3332`): a lone child >300s renews itself with every write, and spares
stay alive while any sibling works. A wedged or silent child stops renewing and TTL reaps —
fail-closed is preserved. Renewal skips (never resurrects) expired slots; non-batch leases are
untouched on this path (R2); the driver-facing `renew_batch` contract (raises on any expired slot,
`lease_broker.py:3704-3735`) is unchanged. Cost: one registry write per delegated mutation.
*(Doc-review D1 resolution (i), operator-pinned 2026-07-22.)*

KTD5. **Kill-switch lives in the saga hook adapters, not the broker.**
`INFIQUETRA_FLEET_LEASE_ENFORCEMENT=off` short-circuits `dispatch()` in both
`plugins/saga/hooks/lease_lifecycle_hook.py` and `plugins/saga/hooks/lease_mutation_hook.py` with a
loud stderr notice per event. The broker's integrity invariants never learn a bypass; the exact
strings `"off"`/absent are the only recognized states (anything else = armed, fail-safe direction).

KTD6. **No protocol bump — `PROTOCOL_VERSION` stays 2.** The change is a behavioral superset on the
broker side; version-skewed pairings (old adapter + new broker, new adapter + old broker) degrade to
today's fail-closed behavior, never to unfenced execution. A bump would force a lockstep
saga/fleet-core upgrade for no safety gain.

## Implementation Units

### U1. Fleet-core broker — unstamped batch claim, terminal recycle, keep-alive

One unit because the three changes share the claim/terminal seam and their tests share fixtures.

**Files:** `plugins/fleet-core/scripts/fleet_commons/lease_broker.py` (claim candidate filter +
ordering at `:2626-2642`; `record_child_terminal` completion condition at `:3748-3754`; in-lock
sibling renewal in both, plus batch-member opportunistic renewal in `assert_write_target`
`:3000-3039` per KTD4/D1 resolution (i)).

**Test scenarios** (`tests/test_fleet_lease_broker.py`, beside the existing 55; end-to-end lifecycle
in `tests/test_saga_workflow_emitter.py` beside
`test_pretool_claim_collection_recycles_slot_and_renews_batch`):

- Batch claim with only unstamped slots binds the oldest one; `logical_unit_id` falls back to
  `{session}:{kind}:{child}` (the `:2645` branch goes live).
- Stamped-first: with one stamped and one older unstamped slot live, the next claim takes the
  stamped slot (deterministic ordering, R3); with only unstamped slots, the oldest is taken.
- KTD3 regression: `tests/test_saga_hooks.py:421`
  (`test_both_lifecycle_signals_are_required_in_either_order`) stays green — the dual-signal
  release contract for stamped and non-batch leases is untouched.
- Non-batch claim behavior byte-identical (R2 regression pin — no candidate-set change when
  `batch_id is None`).
- Exhausted batch (all slots claimed): next claim raises `LeaseNotFoundError` /
  `CapacityExhaustedError` unchanged (R6).
- `record_child_terminal` on an unstamped claimed slot recycles it to pristine (`agent_id=None`,
  `tool_use_id=None`, `agent_type="*"`, claim TTL); on a stamped slot without parent completion it
  does NOT complete (R4 both halves).
- Multi-phase simulation: width-1 batch, child A claims → terminal → recycled slot claimed by
  child B (the #615 "slots never recycle" attack, now passing).
- Keep-alive: a claim renews the live sibling slot's `renewed_at`; an expired sibling is skipped,
  not resurrected; driver `renew_batch` still raises on an expired slot (R5).
- Mutation-path renewal (D1 resolution i): `assert_write_target` on a batch-member lease renews
  that lease and its live siblings (a child whose execution TTL would lapse mid-unit survives by
  writing); on a non-batch lease it performs zero renewal — byte-identical to today (R2 pin); an
  expired batch lease still fails the mutation check (never resurrected).
- Same-`agent_id` re-claim returns the existing bound lease (idempotency at `:2607-2625` holds for
  unstamped claims).
- End-to-end (emitter test): `reserve` → `attest` → N `claim_hook_agent`-shaped claims with no
  `prepare_batch_call` → `verify_hook_mutation` passes for each child → terminals recycle → second
  wave claims recycled slots → `release` settles the batch.

### U2. Saga hooks — emergency kill-switch

**Files:** `plugins/saga/hooks/lease_lifecycle_hook.py`, `plugins/saga/hooks/lease_mutation_hook.py`
(guard at the top of `dispatch()`), kill-switch documented where the adapter's
`INFIQUETRA_FLEET_*` variables are described (locate the canonical env-var doc spot at execution
time; minimum: both CHANGELOGs + the DECISIONS entry).

**Test scenarios** (`tests/test_saga_hooks.py`):

- Env set to `off`: both hooks return without importing/raising, and emit the loud disabled notice
  (assert on stderr content) — a `PreToolUse` payload that would halt today passes through.
- Env absent, env `""`, env `On`/`false`/other: armed (halt behavior unchanged) — the fail-safe
  direction of R7.
- Mutation hook with the switch off never calls `verify_hook_mutation` (no broker state touched).

### U3. Cross-runtime and choreography notes — verification-only unit

No production edit expected; this unit verifies and documents two boundary claims so `/work` does
not discover them mid-flight.

**Verify:** (a) the codex frozen saga copy carries no lease hooks (confirmed 2026-07-22: its
`hooks/` holds only `hooks.json` + `session_context.py`; `scripts/lease_broker.py` is present) and
this PR does not touch `plugins/saga/scripts/lease_broker.py` — so the codex re-freeze impact is
nil and rides codex#45 unchanged; (b) the `/work` workflow-launch choreography
(`plugins/saga/skills/work/SKILL.md` + `plugins/saga/references/concurrency-spawn-sites.md`) needs
no edit for the fix path — the driver protocol (`reserve`/`attest`/`renew`/`release`) is unchanged.
Record both findings in the work-session doc.

**Test expectation:** none — verification and documentation only.

### U4. Release surfaces

**Files:** `plugins/fleet-core/.claude-plugin/plugin.json` (`0.19.0`),
`plugins/saga/.claude-plugin/plugin.json` (`0.110.0`), `.claude-plugin/marketplace.json`, both
`CHANGELOG.md`s, version pins in `tests/test_saga_plugin.py`, `tests/test_liveness_events.py:698`,
`tests/test_team_execution_liveness.py:179`/`:409`, DECISIONS entry `{#workflow-child-lease-binding-615}`
(KTD1–KTD6, rejected alternatives, revisit condition), `scripts/check_release_surface_parity.py`
clean.

**Test expectation:** existing drift-guard and parity suites cover this unit; no new scenarios.
Re-verify version uniqueness at merge time — sibling PRs bumping the same plugin version have
auto-merged into silent collisions before (repo LEARNINGS precedent; re-bump at merge if needed).

## Scope Boundaries

Out of scope (owned elsewhere):

- **#616** — worktree write-fence layer (blocks cross-repo builders even WITH a valid claim). #616
  and #617 are serialized because both edit lease code; this plan keeps its broker diff inside the
  claim/terminal seam and touches neither the write-fence (`assert_write_target` internals) nor the
  registry schema, so #616 rebases cleanly whichever lands first. Flag at PR time if #616's work has
  started.
- **#617** — lease registry schema-skew (blocked by #616).
- **#626** — external-executor settlement semantics (extends, must not collide — nothing here
  changes settlement facts or casualty classification).
- **codex#45** — byte-frozen `outcome_compat` seam; untouched (U3 verifies).
- **TOCTOU `audit_store.py:194`** — pre-existing, separate.
- **Workflow-runtime changes** — we adapt to its event surface; we do not modify it.
- **`/work` choreography** — unchanged (U3 verifies).

Deferred to follow-up work (planned, not now):

- Making the Workflow-runtime `agent_type` signal (if any) part of admission telemetry — only
  worthwhile once R9 shows what the payload actually carries.

## Risk Analysis & Pre-mortem

**Most likely failure (pre-mortem): session-identity propagation.** `claim_hook_agent` resolves the
batch via `active_batch_id` (`plugins/saga/scripts/lease_broker.py:262-285`) keyed on the payload's
`session_id`. If Workflow children's `SubagentStart` events carry a different `session_id` than the
root session that reserved the batch, claims miss the batch and fail exactly as today. This cannot
be proven from static code — it is the first thing the R9 canary verifies. Mitigation already in
the code: `INFIQUETRA_FLEET_BATCH_ID` env override takes precedence in `active_batch_id`; if the
canary exposes a session-id mismatch, the launch choreography exports the batch id at launch (a
choreography note, no code change).

**RESOLVED — doc-review finding D1 (P1): TTL event starvation → resolution (i), operator-pinned
2026-07-22.** The emitted lease metadata hard-codes `claim_ttl_seconds: 30` /
`execution_ttl_seconds: 300` (`plugins/saga/scripts/execution_spec.py:3331-3332`), and an
events-only keep-alive starves: a lone child running longer than 300 seconds with no sibling
events would see its own lease expire mid-unit, and spare unclaimed slots would expire after 30
idle seconds during low-width phases. Jeff pinned **resolution (i)** — extend KTD4 so the
mutation-verification path (`assert_write_target`, `lease_broker.py:3000-3039`) opportunistically
renews the mutating child's lease and its live batch siblings under the broker lock. Renewal
frequency scales with actual activity; a wedged/silent child still expires — fail-closed
preserved; cost: one registry write per delegated mutation; non-batch leases untouched (R2).
Rejected alternatives: (ii) driver-side renewal at task-notification seams (choreography change,
cadence-dependent); (iii) run-horizon TTLs (weakens TTL reaping for every consumer). R5, KTD4,
and U1 carry the pinned design.

Other enumerated risks:

- **Slot competition in mixed sessions** — a direct `Agent` spawn and Workflow children racing for
  width-limited slots: bounded by reservation width, deterministic via KTD2 ordering, and
  fail-closed on exhaustion. Accepted.
- **`SubagentStop` blocked by another hook** (the #356 KTD4 worry): the unstamped slot leaks until
  TTL; later phases may exhaust and halt — fail-closed, and keep-alive stops with the wedged run.
  Accepted.
- **Kill-switch normalization** — an operator setting `OFF`/`true` expecting disable gets armed
  hooks (fail-safe direction, loud notice explains the exact recognized value). Accepted by design.
- **Merge collision with #616** — both touch `lease_broker.py`; #616 is dispatched-not-started.
  Whoever lands second rebases; the diff here is deliberately narrow (claim/terminal seam only).

## Alternatives Considered

- **Issue direction 1 — claim-time auto-provisioning keyed on `agent_type=workflow-subagent`.**
  Rejected: creates capacity at claim time (violates #356 KTD3 "reservation precedes launch"),
  trusts an unverified runtime string, and duplicates a reservation mechanism that already exists.
- **Issue direction 2 — exempt Workflow children from enforcement.** Rejected: removes fencing for
  the highest-mutation fleet class; the Workflow runtime caps concurrency but provides no fencing
  tokens, so a stale child could write after supersession.
- **Adapter-side special-casing (saga `lease_broker.py`).** Rejected: the broker owns the schema
  (#356 KTD2); a saga-only fix would leave team-execution's adapter broken and touch the codex
  frozen adapter copy for no reason.
- **Protocol version bump to 3.** Rejected per KTD6 — no safety gain, forces lockstep upgrades.

## Success Metrics

- R9 canary passes with ARMED installed hooks; the per-launch neutralization ritual is retired
  (memory `workflow-lease-hooks-neutralized-615` gets updated to historical).
- Full battery, `ruff check` + `ruff format --check`, `mypy plugins/ scripts/ tests/`, bandit on
  touched scripts, and release-surface parity all green.
- Direct-spawn fencing regression pins green (R2, R9b).
