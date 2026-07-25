---
title: Issue #616 — worktree write-fence scoping — fence by declared isolation, not spawn cwd
type: fix
status: active
date: 2026-07-22
---

# Issue #616 — worktree write-fence scoping — fence by declared isolation, not spawn cwd

## Summary

The fleet-lease write-fence pins every claimed agent to its spawn working directory, so any agent
that legitimately edits a different repository has all writes refused even with a valid read-write
lease (defect #616). The fence conflates "where the agent was spawned" with "where the agent may
write" — correct only for agents launched with `isolation: 'worktree'`. This plan makes isolation an
explicit, reservation-carried fact: the PreToolUse reservation stamps the parent's declared
isolation mode, and claim stamps `worktree_root` (the fence trigger) only where a worktree boundary
genuinely exists. Attested Workflow batch slots keep today's conservative cwd fence byte-for-byte.

## Problem Frame

Issue [#616](https://github.com/infiquetra/infiquetra-claude-plugins/issues/616) (defect; outcome
`governed-execution-integrity` leaf `leaf-governed-execution-integrity-sub-616`). Diff base
`origin/main` `ab84003b` (saga 0.110.0, fleet-core 0.19.0 — post-#615/PR #641). #617 is blocked by
this leaf because both edit `lease_broker.py`; this diff's shape sets #617's rebase surface.

**Mechanism, verified at `ab84003b`.** The fence is decided entirely at claim time:

- `claim_hook_agent` (`plugins/saga/scripts/lease_broker.py:338-353`) binds SubagentStart identity
  and passes `worktree_root=_canonical_cwd(payload)` **unconditionally** — the spawn cwd.
- Broker `claim()` (`plugins/fleet-core/scripts/fleet_commons/lease_broker.py:2580`) canonicalizes
  it (`:2598-2602`) and derives `resource_ref = {logical_unit_id, worktree_root}` (`:2653-2658`).
  `_AGENT_RESOURCE_KEYS` (`:176`) closes the set to exactly those two keys.
- `assert_write_target` (`:3044-3088`) fences a delegated mutation inside `worktree_root` with a
  symlink-safe containment check (`:3060-3088`) — but when the lease's `resource_ref` carries **no**
  `worktree_root`, it returns unfenced (`:3058-3059`). The fence trigger is the stamp, not a policy
  flag.

**The signal gap.** Nothing anywhere records whether the agent was actually launched with
`isolation: 'worktree'`. The SubagentStart payload carries no isolation field — the repo's own
payload-contract fixtures pin exactly `{hook_event_name, session_id, cwd, agent_id, agent_type}`
(`tests/test_saga_hooks.py:96-103`), and the adapter reads nothing beyond them. But the **PreToolUse** payload does: the
reservation path already reads `tool_input` (`_agent_type`,
`plugins/saga/scripts/lease_broker.py:80-90` falls back to `tool_input.subagent_type`), and the
Agent tool's `tool_input` carries `isolation` verbatim. The reservation is therefore the one
trusted, pre-spawn carrier for isolation truth — and broker `acquire_agent` (`:2246`) plus
`prepare_batch_call` (`:2711`, the slot-stamping path for Agent spawns while a Workflow batch is
live) are the two reserve surfaces it must ride.

**Impact (from the issue, still accurate).** The standard orchestration pattern — coordinator
session in a context repo, builder agents editing service repos — fails closed on every cross-repo
write. Found while diagnosing #615; independent second layer of the same diagnosis.

## Requirements

R1. **Non-isolated direct spawns write cross-repo.** An `Agent|Task` spawn whose `tool_input` does
not declare `isolation: 'worktree'` claims a lease with no `worktree_root`; a verified mutation
targeting a path outside its spawn cwd passes `assert_write_target` (admission, `read-write`
mutation mode, and hook verification still required — the fence is the only thing removed).

R2. **Worktree-isolated spawns stay fenced.** A spawn declaring `isolation: 'worktree'` claims with
`worktree_root` stamped from its actual child cwd; a write outside that root is still refused
through the existing symlink-safe containment check, which stays byte-identical.

R3. **Attested Workflow batch slots are byte-identical to today.** A batch slot that was never
PreToolUse-stamped (`tool_use_id is None` — Workflow-runtime children, #615) claims exactly as at
`ab84003b`: `worktree_root` stamped from child cwd. The #615 R9 scripted canary passes unchanged.

R4. **Stamped batch slots carry the same truth as non-batch spawns.** A direct Agent spawn during a
live batch (`prepare_batch_call` path) records the declared isolation on the slot, and claim honors
it identically to the non-batch path.

R5. **Registry rows from 0.19.0 load cleanly.** Pre-#616 registry files (no `isolation` key) load
via the established backfill-before-closed-mapping pattern; no migration machinery (schema-skew
hardening is #617's layer).

R6. **Strict additivity at the shared seams.** The mutation-gate order in `assert_write_target`
(`verify_agent` → mutation check → #615 batch renewal `:3050-3054` → fence) is unchanged; batch-slot
recycle (`_complete_foreground_lease`, `:3892`) resets `isolation` alongside `agent_id`/
`tool_use_id`; kill-switch semantics (`INFIQUETRA_FLEET_LEASE_ENFORCEMENT` exact-string `off`)
untouched.

R7. **Release surfaces complete in the same PR.** fleet-core 0.19.0→0.20.0 and saga 0.110.0→0.111.0
bumps, `marketplace.json`, both CHANGELOGs, drift-guard pins, DECISIONS entry, and
`check_release_surface_parity.py` clean; merge-time sibling-PR version-collision re-check.

R8. **Live acceptance canary (operator-gated, post-merge).** Under armed installed hooks after
plugin update **and** the `installed_plugins.json` pin check (#642 hazard: verify with
`FLEET_COMMONS_DEBUG=1` that the shim resolves fleet-core 0.20.0 before trusting any canary
result): (a) a non-isolated agent writes a target outside its spawn cwd successfully; (b) a
worktree-isolated agent's outside-write is refused; (c) the #615 R9 workflow-child canary re-run
passes.

## Key Technical Decisions

KTD1. **Isolation truth is reservation-carried, stamped at PreToolUse from
`tool_input.isolation`:** the PreToolUse payload is the only trusted pre-spawn surface that sees the
Agent tool call's declared isolation (SubagentStart carries no isolation field; cwd heuristics such
as "is the cwd a git worktree distinct from the primary checkout" have false positives — developer
worktrees, nested repos — and false negatives, and were rejected). This mirrors how the reservation
already carries `agent_type` from the same payload.

KTD2. **`isolation` becomes a first-class nullable `Lease` field, not a `resource_ref` key:**
`agent_type` set the precedent for promoting reservation-time facts to first-class fields
(`:158/:822/:926`). `_AGENT_RESOURCE_KEYS` stays closed at `{logical_unit_id, worktree_root}`, so
`canonical_resource_ref` validation (`:370-374`) is untouched and #626 (external-executor
settlement) extends a named field instead of colliding with a widened closed set. The adapter
normalizes: only the exact string `worktree` is stored; any other declared isolation (e.g.
`remote`) or absence stores `None` — the broker never learns speculative values.

KTD3. **Claim-time fence policy is a three-way branch on reservation state** (replacing the
unconditional cwd stamp):

| Reservation state at claim | Fence behavior | Why |
|---|---|---|
| `isolation == "worktree"` | Stamp `worktree_root` from child cwd | A dedicated worktree exists and is the correct write boundary |
| PreToolUse-stamped (`tool_use_id` present), no worktree isolation | No `worktree_root` — unfenced | Parent explicitly declared a non-isolated spawn; admission + mutation mode still bound it |
| Unstamped attested batch slot (`tool_use_id is None`) | Stamp `worktree_root` from child cwd (today's behavior) | No declared truth exists; conservative default, R9-proven |

The middle branch is the deliberate privilege change this defect demands — see D1.

KTD4. **No declared-write-roots surface ships in this change:** the Agent tool's `tool_input` has no
write-roots parameter, so a declared-roots design would require inventing a side channel
(environment variable or metadata file) that no caller populates today. Non-isolated-means-unfenced
is the issue's own proposed fallback; if a narrower grant is ever needed, #626 or a follow-up can
extend the first-class field shape from KTD2.

KTD5. **Registry compatibility uses the backfill-before-closed-mapping pattern:**
`Lease.from_dict` validates against a closed key set (`_closed_mapping`, `:846`);
`SettlementRecord.from_dict` already demonstrates the additive-field idiom — backfill the missing
optional key to `None` before validating (`:969-970`). Reuse it for `leases.*.isolation`; no
version-bump or migration machinery (deliberately left to #617's schema-skew layer).

KTD6. **The Workflow batch metadata schema (`workflow_lease_reservation.v1`, closed 16-key set) is
untouched:** batch-level isolation declaration for Workflow-runtime children is deferred — those
slots are interchangeable at claim (any child claims any slot), so per-slot isolation cannot be
matched to a specific child reliably, and the conservative cwd fence (KTD3 row 3) is the sound
default. Documented limitation: cross-repo builders dispatched *as Workflow-runtime children*
remain cwd-fenced; revisit alongside #626.

**D1 — operator pin required (P1, mirrors #615's D1).** KTD3's middle branch removes the write-fence
entirely for non-isolated spawns. The alternatives were: (i) unfenced (this plan's choice — the
issue's own proposal; admission, mutation mode, and hook verification remain); (ii) fence to a
declared write-root set (rejected as KTD4 scope creep — no carrier exists); (iii) keep the cwd
fence and require all cross-repo builders to be worktree-isolated (rejected: forces isolation
overhead onto every cross-repo spawn and contradicts the issue's intent). Jeff should pin (i)
explicitly before `/work` executes.

## Implementation Units

### U1. fleet-core broker — first-class `isolation` field and claim-time fence policy

**Goal:** carry declared isolation on the lease record and stamp `worktree_root` per KTD3.

**Files:** `plugins/fleet-core/scripts/fleet_commons/lease_broker.py` — `Lease` dataclass (`:812`),
`_LEASE_KEYS`/`from_dict` backfill/`to_dict` (`:845-930`), `acquire_agent` (`:2246`, new optional
`isolation` param), `prepare_batch_call` (`:2711`, same), `claim` (`:2580`, three-way branch
replacing the unconditional `derived["worktree_root"]` at `:2653-2658`), `_complete_foreground_lease`
batch-slot recycle (`:3892`, reset `isolation` to `None`).

**Boundaries:** `reserve_batch` (`:2477`) gains no isolation parameter (KTD6). `assert_write_target`
changes zero lines (the fence trigger stays "is `worktree_root` present"). #615's claim-ordering,
recycle dual-signal, and renewal seams are not reworked (R6).

**Test scenarios** (`tests/test_fleet_lease_broker.py`):

- claim of a stamped non-isolated reservation → `resource_ref` has `logical_unit_id` only;
  `assert_write_target` passes for a path outside the claim cwd (R1).
- claim of a stamped `isolation="worktree"` reservation → `worktree_root` == child cwd; outside
  write raises through the existing containment error (R2).
- claim of an attested unstamped batch slot → `worktree_root` stamped (byte-parity with a pinned
  pre-#616 expectation) (R3).
- `prepare_batch_call` records isolation on the slot; subsequent claim honors it (R4).
- registry round-trip: a 0.19.0-shaped lease dict (no `isolation` key) loads with `isolation=None`;
  a written registry re-loads (R5).
- batch-slot recycle after child-terminal resets `isolation` (a recycled slot re-claimed by a
  workflow child gets row-3 behavior, not the prior spawn's declaration) (R6).
- supersede path (`on_conflict="supersede"`): the replacing reservation's isolation wins.
- invalid isolation values rejected at the broker boundary (only `"worktree"`/`None` storable).

### U2. saga adapter — extract and forward declared isolation

**Goal:** `reserve_hook_agent` reads `tool_input.isolation` and forwards the normalized value on
both reserve paths; `claim_hook_agent` is unchanged (it still passes the actual child cwd — the
broker now decides whether to stamp it).

**Files:** `plugins/saga/scripts/lease_broker.py` — a `_declared_isolation(payload)` helper beside
`_agent_type` (`:80-90`), threaded into `acquire_agent` (`:317`) and `prepare_batch_call` (`:304`)
calls.

**Boundaries:** hooks (`lease_lifecycle_hook.py`, `lease_mutation_hook.py`) change zero lines —
the event routing and fail-closed postures are #615-audited surfaces.

**Test scenarios** (`tests/test_saga_hooks.py` — the hook payload-contract home, fixtures
`:96-103`; `tests/test_saga_workflow_emitter.py` for the batch interplay):

- payload with `tool_input.isolation == "worktree"` → reservation carries `worktree`; without it →
  `None`; with `"remote"` → `None` (KTD2 normalization).
- live-batch PreToolUse (`prepare_batch_call` route) forwards isolation identically (R4).
- SubagentStart claim payload contract unchanged (cwd still required and canonicalized).

### U3. Verification-only — frozen-seam nil-impact and R9 canary rehearsal

**Goal:** confirm the codex byte-frozen `outcome_compat` seam is untouched by the `Lease` field
addition (registry state is machine-local; the frozen seam consumes broker APIs, not registry
bytes), and rehearse the #615 R9 scripted canary hermetically (metadata JSON + `workflow_emitter.py
reserve/attest/release`) against the changed broker to prove R3 before merge. Recorded in the
work-session doc; no code changes.

**Test expectation:** none — verification-only unit; its evidence is the work-session record.

### U4. Release surfaces

**Goal:** fleet-core 0.20.0 + saga 0.111.0 in the same PR (R7).

**Files:** `plugins/fleet-core/.claude-plugin/plugin.json`, `plugins/saga/.claude-plugin/plugin.json`,
`.claude-plugin/marketplace.json`, both `CHANGELOG.md`s, drift pins (`tests/test_saga_plugin.py`,
`tests/test_liveness_events.py:698`, `tests/test_team_execution_liveness.py:179/:409` pattern from
#615), `docs/engineering-journal/DECISIONS.md` entry `{#worktree-fence-scoping-616}` (KTD1-KTD6 +
D1 pin), parity via `scripts/check_release_surface_parity.py`.

**Test scenarios:** existing drift-guard and parity tests updated to the new versions; merge-time
sibling-PR version-collision re-check (the known auto-merge silent-collision gotcha).

## Scope Boundaries

**Out of scope (true non-goals):** #617 registry schema-skew hardening (this plan deliberately uses
the minimal backfill idiom and leaves migration machinery alone); #642 `fleet_commons_shim`
stale-registry defect (operational hazard only — its pin check is folded into R8's canary
preamble); kill-switch semantics; the byte-frozen `outcome_compat` seam (codex#45 rides a later
re-freeze); TOCTOU `audit_store.py:194`; `assert_write_target`'s containment algorithm.

**Deferred to Follow-Up Work:** batch-level isolation declaration for Workflow-runtime children
(KTD6 — revisit alongside #626); declared-write-roots grants narrower than "unfenced" (KTD4 — needs
a real carrier surface first).

## Risk Analysis & Mitigation

- **Privilege widening (the D1 call).** Non-isolated spawns lose the cwd fence. Mitigation: the
  change is inert unless the parent's spawn was PreToolUse-stamped without worktree isolation —
  exactly the declared-intent case; admission caps, `read-write` mutation gating, and hook
  verification all remain; D1 requires an explicit operator pin.
- **Silent behavior drift for workflow children.** Mitigated structurally: KTD3 row 3 preserves
  byte-parity for unstamped slots, pinned by a dedicated test (R3) and the U3 canary rehearsal.
- **Registry forward/backward skew.** A 0.20.0 broker reads 0.19.0 state (R5 backfill); a 0.19.0
  broker reading 0.20.0 state would reject the unknown key — same-machine skew window only, and the
  #642 pin check in R8 is the operational guard. No cross-version co-existence is supported today
  (single-host state dir), matching the existing schema posture.
- **Adapter↔broker code-version skew (the #642 shape).** If the stale `installed_plugins.json`
  hazard recurs after this release, a saga 0.111.0 adapter passing the new `isolation` kwarg into a
  shim-resolved fleet-core 0.19.0 broker raises `TypeError` at PreToolUse — a loud, fail-closed
  halt on every Agent spawn, never a silent wrong-fence. Acceptable failure direction; the R8
  preamble's `FLEET_COMMONS_DEBUG=1` provenance check is the guard, #642 owns the durable fix.
- **Merge collision with #617.** #617 is dispatched-not-started and blocked by this leaf; keep this
  diff surgically scoped to the field + claim branch + recycle reset so #617 rebases onto a narrow,
  reviewed seam.

## Success Metrics

Gates green (`uv run pytest -q`, `ruff check` + `ruff format --check`, `mypy plugins/ scripts/
tests/ --ignore-missing-imports`, bandit no new findings); R1-R7 pinned by tests pre-merge; R8
canary passes post-merge under armed installed hooks with the shim provenance check clean.
