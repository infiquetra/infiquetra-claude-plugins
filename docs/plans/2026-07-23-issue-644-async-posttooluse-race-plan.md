---
title: Issue 644 — stop PostToolUse-at-launch from destroying unclaimed reservations
type: fix
status: active
date: 2026-07-23
origin: https://github.com/infiquetra/infiquetra-claude-plugins/issues/644
---

# Issue 644 — stop PostToolUse-at-launch from destroying unclaimed reservations

## Summary

With async Agent/Task spawns, the harness fires PostToolUse at launch-return (~100-156 ms after
PreToolUse), and `record_parent_completed` treats the still-unclaimed reservation as
"spawn never happened" — deleting the lease and popping the session admission before SubagentStart
can claim, a per-spawn coin-flip that makes direct spawns fail ~50% under armed hooks. The fix is a
single-branch change in the fleet-core broker: an unclaimed reservation receiving a parent-completed
signal is **stamped and kept claimable** instead of destroyed, with eager cleanup preserved only for
`PostToolUseFailure` (a spawn that genuinely never started), which the saga adapter now distinguishes
by `hook_event_name`.

## Problem Frame

Defect #644 (labels defect / needs-plan / hermes-task; requirements-ready). Diagnosed live 2026-07-23
during the #616 R8 rollout: 3/3 consecutive spawn failures ("expected exactly one fleet lease bound;
found 0"); a 100 ms registry watcher captured the reservation **and** the session admission wiped in
one locked write 101-156 ms after reservation — exactly at async launch-return
(`registry_timeline.log` / `registry_timeline2.log`, session scratchpad; durable record in
`docs/work-sessions/2026-07-22-issue-616-worktree-write-fence-scoping.md` post-merge section and
LEARNINGS `{#async-spawn-posttooluse-race-616-r8}` at commit `277f070d`). Same signature as the
3-of-8 verifier lease losses in the #616 code review and the prime suspect for the pass-4 whole-batch
disappearance. Until fixed, every armed-hooks session degrades: retry works, but each spawn is a race.

Baseline: main `277f070d` (fleet-core 0.20.0 + saga 0.111.0, post-#616 merge `0b6bcbf5`). Standalone
defect thread (not a leaf of outcome #639; Objective grouping is the operator's call). Native work
saga: `issue-644`.

## Verified mechanism (all anchors at 277f070d)

The broker (`plugins/fleet-core/scripts/fleet_commons/lease_broker.py`) `record_parent_completed`
:3895-3929 matches leases by `(session_id, tool_use_id)` and hits the kill branch at :3913 —
`if updated.agent_id is None or updated.child_terminal_at is not None:` → `_complete_foreground_lease`
:3931-3961 (non-batch lease removed :3944-3946; batch slot recycled with `tool_use_id`/`isolation`
reset). The admission pop rides the same write at :3924-3927.

Four pre-existing invariants make the minimal fix compose correctly:

1. **The claimed-lease path is already async-safe.** A claimed, non-terminal lease just gets
   `parent_completed_at` stamped and survives (:3922-3923); release defers to
   `record_child_terminal` :3857-3893's dual-signal contract (:3873 releases when the parent signal
   is already present). Only the `agent_id is None` arm is wrong.
2. **The admission half fixes itself.** `_session_has_live_agents` :1952-1964 counts **any**
   unexpired agent-pool lease, claimed or not — if the reservation survives, the admission survives;
   no change needed at :3924-3927.
3. **The linger is already bounded.** `reserve_hook_agent` (saga adapter
   `plugins/saga/scripts/lease_broker.py` :313, :340) reserves foreground leases with
   `ttl_seconds = claim_ttl` (`DEFAULT_CLAIM_TTL_SECONDS = 30`, broker :38). A reservation whose
   child never arrives stops counting as live via `_expired_static` :1987-1991 after ≤30 s — no new
   grace-window clock is needed.
4. **Early stamping survives the claim.** `claim()` :2696-2706 binds via `replace(selected, …)` and
   never touches `parent_completed_at`; its candidate filter :2655-2664 does not exclude stamped
   leases. So a reservation stamped at launch-return is claimed intact, and `record_child_terminal`
   releases it at child terminal because the parent signal is already recorded. For stamped batch
   slots the same composition holds (:3872-3873 recycles a stamped slot only on the dual signal).

Event distinction is available adapter-side: `hooks/hooks.json` routes **both** `PostToolUse` and
`PostToolUseFailure` [Agent|Task] into `lease_lifecycle_hook.py` (dispatch :67-68), which passes the
full payload — including `hook_event_name` — to `record_hook_parent` :379-394, which today ignores it.

## Requirements

R1. `record_parent_completed` against an **unclaimed, unexpired** reservation (foreground or stamped
batch slot) no longer removes/recycles it: the lease survives with `parent_completed_at` stamped,
stays claimable, the session admission stays intact, and the return value for that lease is `()`.

R2. `claim()` after such a stamp binds the reservation with the stamp preserved; a subsequent
`record_child_terminal` releases it (foreground) or recycles it (batch slot) — the dual-signal
contract end-to-end for the async ordering reserve → parent-completed → claim → child-terminal.

R3. A spawn that genuinely never started still cleans up eagerly: `record_parent_completed(...,
spawn_failed=True)` keeps today's unclaimed-removal behavior, and the saga adapter passes
`spawn_failed=True` exactly when `hook_event_name == "PostToolUseFailure"`.

R4. Claimed-lease behavior is byte-compatible: existing dual-signal tests (e.g.
`test_normal_reservation_requires_two_release_signals`, batch settlement tests) pass unchanged; the
`record_parent_completed` return contract (tuple of removed lease ids) and the conformance truth-set
(`tests/test_concurrency_conformance.py` — `record_hook_parent` → `selected.record_parent_completed`)
are unchanged.

R5. Zero registry schema change (issue stop condition; keeps #617's rebase surface clean).
`parent_completed_at` is an existing `Lease` field — stamping an unclaimed lease writes no new key.

R6. An abandoned reservation (parent-completed stamped, child never arrives) stops occupying its
admission/session slot within the claim TTL: `_session_has_live_agents` returns False for it once
expired, and admission purge paths behave as today. For batch slots, `settle_batch` releases an
abandoned stamped slot (unclaimed with the parent signal recorded) so the registry drains to zero
leases at batch teardown — the drained-registry invariant the R8/R9 canaries assert.

R7. Repo gates green at the PR head: `uv run pytest -q`, `ruff check` + `ruff format --check`,
`mypy plugins/ scripts/ tests/ --ignore-missing-imports`, bandit delta zero vs base,
`python3 scripts/check_release_surface_parity.py`.

R8. **Live acceptance canary (post-merge + post-rollout, operator-gated):** 10 consecutive async
Agent spawns under armed installed hooks all bind and complete a delegated Write — zero occurrences
of "expected exactly one fleet lease bound; found 0". Preceded by the #642 provenance preamble
(`FLEET_COMMONS_DEBUG=1` shim check; hand-repair `installed_plugins.json` if stale — two-for-two
releases have needed it).

## Key Technical Decisions

KTD1 — **Fix locus: broker `record_parent_completed` unclaimed arm, stamp-and-survive**: change
:3913 so an unclaimed reservation is completed only when `spawn_failed` is set; otherwise it falls
into the existing stamp-and-keep else-branch (:3922-3923). Rationale: one branch, zero schema, the
admission half fixes itself (invariant 2), and the dual-signal contract already composes with early
stamping (invariant 4). Alternatives rejected: *payload launch-vs-completion sniffing* — depends on
an unverified harness payload contract and is unnecessary since early stamping is semantically
correct (the parent tool call **did** return); *age-based grace window* — introduces a time constant
with no natural value when the 30 s claim TTL already bounds the linger, and merely shrinks the race
instead of eliminating it; *unconditional no-cleanup* — discards the genuine failure signal we do
have (`PostToolUseFailure`) and leaves never-started spawns holding slots for the full TTL.

KTD2 — **Event-aware routing lands adapter-side as a keyword-only broker parameter**:
`record_parent_completed(session_id, tool_use_id, *, spawn_failed: bool = False)`;
`record_hook_parent` passes `spawn_failed = (payload hook_event_name == "PostToolUseFailure")`.
Rationale: the adapter is the only layer that sees the hook event; the default-False keyword keeps
every existing caller and the return contract byte-compatible; the conformance truth-set records
callable names only, so it stays frozen.

KTD3 — **Version-skew posture: no compatibility shim**: the new adapter passes `spawn_failed`
unconditionally; against an old broker this raises `TypeError` on an observational event
(PostToolUse posture is retained-for-retry, `lease_lifecycle_hook.py` :77-78), so the failure mode
is a lease released by its 30 s TTL instead of by signal — soft, bounded, and exactly the skew #642's
provenance check exists to catch. A try/except shim would mask skew silently; rejected.

KTD4 — **Batch stamped slots get the same deferral, plus one settlement arm**: the race applies to
workflow children (stamped slots carry `tool_use_id` from PreToolUse and are recycled by the same
:3913 branch — prime suspect for the #616 pass-4 batch disappearance). The one branch change covers
both shapes, and the stamped-slot recycle at child terminal (:3872-3873) is untouched, preserving
the #615 R9 contract. One companion change IS required (doc-review finding D1): `settle_batch`
:3803-3812 releases only *unclaimed-and-unstamped* or *claimed-and-dual-signal* slots — today the
eager recycle reset an abandoned stamped slot to unstamped, which is what made it drainable. The
new surviving state (stamped-unclaimed, `parent_completed_at` set) matches neither arm and would
leak an expired slot past settlement. Extend the release condition with one arm:
`lease.agent_id is None and lease.parent_completed_at is not None` — at settlement, an unclaimed
slot whose parent call already returned can owe no child. Mid-run wave settlements are unaffected
(a stamped slot awaiting its child has no parent signal yet).

DECISIONS.md entry `{#async-parent-signal-644}` ships with the release-surfaces unit (same-commit
journal rule), mirroring KTD1-KTD4.

## Implementation Units

Execution is serialized U1 → U2 → U3 (U2 consumes U1's signature; U3 records both versions).

### U1. Broker: defer unclaimed-reservation cleanup to `spawn_failed` or TTL

**Goal:** implement KTD1/KTD4 in `plugins/fleet-core/scripts/fleet_commons/lease_broker.py` —
`spawn_failed: bool = False` keyword-only parameter on `record_parent_completed`; the :3913 branch
completes an unclaimed lease only when `spawn_failed`; plus the KTD4 `settle_batch` drain arm
(:3803-3812 gains `agent_id is None and parent_completed_at is not None`). All other behavior
(claimed paths, admission guard, return contract, `_complete_foreground_lease`) untouched.

**Tier:** opus / high (judgment on a concurrency-critical seam).

**Tests:** `tests/test_fleet_lease_broker.py` —
(a) R1: unclaimed unexpired foreground reservation + default call → lease survives with
`parent_completed_at` stamped, admission intact, returns `()`;
(b) R2: full async ordering reserve → parent-completed → claim (stamp preserved) → child-terminal →
released; batch-slot variant: stamped slot survives parent-completed, child claims it, terminal
recycles it;
(c) R3: `spawn_failed=True` removes the unclaimed reservation (update
`test_unclaimed_failed_parent_releases_reservation` :528 to pass the flag — it is semantically the
spawn-failure case) and pops the admission when no other live agents exist;
(d) R4: existing claimed-path tests pass unchanged;
(e) session-scoping test :534 updated (`spawn_failed=True`, or re-asserted as survival scoping);
(f) R6: expired stamped-unclaimed reservation is not counted live and does not block a fresh
`acquire_agent`;
(g) R6/KTD4: `settle_batch` after a stamped slot's parent-completed with no claim releases the
slot (registry drains), while a mid-run stamped slot with no parent signal still survives
settlement (wave semantics unchanged).

### U2. Saga adapter: distinguish PostToolUseFailure from PostToolUse

**Goal:** implement KTD2/KTD3 in `plugins/saga/scripts/lease_broker.py` `record_hook_parent`
:379-394 — derive `spawn_failed` from the payload's `hook_event_name` and forward it. Zero changes to
`hooks/lease_lifecycle_hook.py` and `hooks/hooks.json` (they already deliver both events with the
full payload).

**Tier:** sonnet / high.

**Tests:** `tests/test_saga_hooks.py` — PostToolUse payload → broker called with
`spawn_failed=False`; PostToolUseFailure payload → `spawn_failed=True`; confirm
`tests/test_concurrency_conformance.py` truth-set for `record_hook_parent` stays green (call-name set
unchanged).

### U3. Release surfaces

**Goal:** fleet-core `plugin.json` → 0.21.0, saga `plugin.json` → 0.112.0 (adapter changed),
`.claude-plugin/marketplace.json` sync, both CHANGELOGs, drift-guard pins
(`tests/test_saga_plugin.py`, `tests/test_liveness_events.py` version pin, the
`tests/test_team_execution_liveness.py` pattern), DECISIONS.md `{#async-parent-signal-644}`,
`check_release_surface_parity.py` clean. Merge-time sibling-PR version-collision re-check
(evidence-integrity gotcha: same-version siblings auto-merge silently — re-bump at merge time).

**Tier:** sonnet / medium.

**Test expectation:** drift/parity suites above; no new feature tests (release-surface unit).

## Scope Boundaries

Out of scope (true non-goals): admission policy / lease-TTL redesign and `renew_batch`
all-or-nothing (#646); boot-id cohort split (#645); the pre-existing unfenced edge (#647);
`fleet_commons_shim` staleness (#642 — its provenance check is used operationally in R8 but not
modified); harness-side spawn-synchrony changes; workflow batch-slot recycle semantics beyond what
the race touches; registry schema/version-migration machinery (#617 territory — **stop condition:**
if the chosen design turns out to need a schema field, halt and surface to the operator; this plan
needs none).

Deferred to follow-up work: none identified beyond the already-filed #645-#648.

**Merge-collision note:** #617 rebases onto whatever #644 ships and owns broker schema territory —
this diff stays surgically narrow (the :3913 branch, one adapter function, tests, release surfaces).

## Execution hazards (for /work)

The defect under repair is live in the executing session: any verifier/review Agent spawn may
coin-flip fail with "expected exactly one fleet lease bound; found 0" — that is the defect, not the
spawn; retry once or twice before escalating. Armed hooks in the driving session currently run saga
0.111.0 + fleet-core 0.20.0 with provenance verified (rung 3). Post-merge rollout must re-run the
#642 preamble before the R8 canary.
