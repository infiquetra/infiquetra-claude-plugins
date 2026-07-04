---
title: capability: orphan runner containment — epoch fencing on evidence writes, lease quarantine, heartbeat reaper
repo: infiquetra-claude-plugins
type: capability
team: campps
project: operations
status: Idea
labels: capability, hermes-task, needs-plan
risk: medium
handoff_maturity: requirements-ready
tier: structural
wave: wave-1
objective: Govern fleet concurrency and reclaim leaked resources
---

# capability: orphan runner containment — epoch fencing on evidence writes, lease quarantine, heartbeat reaper

### Objective
Govern fleet concurrency and reclaim leaked resources

### Intent
Give every delegated/bridged runner in the fleet (agy delegation, saga outcome dispatch, and any
future teammate bridge) a single shared liveness-and-fencing discipline so a runner that has been
superseded, has expired, or has gone silent can never silently clobber or shadow the evidence its
successor writes. Today "did it actually run and persist" is not verifiable after the fact — a late
writer from a stale run can land its output after a retry has already written the current answer,
and there is no shared mechanism that reaps a runner that has simply gone quiet. This capability adds
three complementary defenses on top of the existing per-plugin lease/liveness primitives:

1. **Epoch fencing on evidence writes** — a monotonic fencing token checked on every evidence write so
   a write from a superseded lease is rejected (`ORPHAN_WRITE_BLOCKED`) while the current-lease write
   persists unharmed.
2. **Lease quarantine for expired writers** — when a lease has expired (rather than been superseded),
   its late write is quarantined aside — moved to a distinguishable location — rather than either
   landing silently or being dropped and lost. Expired-but-not-yet-superseded is a different failure
   shape than fenced-out-by-a-newer-epoch, and the two must be distinguishable in the evidence trail.
3. **Heartbeat reaper across bridges** — a shared runner-liveness heartbeat and reaper that flags
   stalled runners (aged heartbeat, empty artifact directories) and late-writers-after-close for
   reaping, so a runner that never crashes but simply stops emitting is not left to rot as invisible
   fleet-wide waste.

### Problem / motivation
This is theme 15 (delegation integrity) from the plugin-fleet grounding brief's recurring-pain
analysis: *"Silent no-ops in delegation & dead wiring (5+ learnings: agy silent Claude-fallback, dead-
wiring producer+consumer, test-shape-masks-dead-wiring, fake-adapter mismatch) — any bridge/delegation
idea needs 'did it actually run/persist' verification"* (`docs/plans/2026-07-03-plugin-fleet-grounding-
brief.md`, section 6, item 1). Orphan-runner liveness is exactly this pain applied to the write path:
the fleet already writes lease files, but nothing checks them at write time.

Two concrete lease primitives exist today and are both unfenced:

- `plugins/agy/scripts/agy_delegate.py:319` (and again at `:424`, `:483`, `:604`) writes a
  `run-lease.json` per delegation run recording `launch_state`, `started_at`, `ended_at`, and
  `shutdown` — but nothing on the read/evidence-write side checks whether that lease is still current
  before accepting a write from the runner that holds it. `plugins/agy/skills/agy-delegate/references/
  delegation-contract.md:110` documents `run-lease.json` as a required member of every evidence bundle,
  but the contract stops at "the file exists," not "the file's epoch was checked before the write it
  guards."
- `plugins/saga/scripts/outcome.py:1055` wires `outcome_liveness.harvest_liveness(...)` as the
  `production_liveness_processor`, reclaiming hung dispatched leaves that breach heartbeat/timeout
  budgets as `stalled` (R31). This reclaims the *spec-side* status but has no counterpart on the
  *evidence-write* side: nothing stops a runner that was already reclaimed as `stalled` from later
  writing evidence that a dependent or the operator then reads as live output.

No shared module unifies these two lease shapes, and neither enforces fencing at the point of write.
A late orphan write today either (a) silently lands and is indistinguishable from a legitimate write,
or (b) is dropped with no record it ever happened — both are the "silent no-op" failure class named in
the grounding brief.

### Out-of-scope / non-goals
- Rewriting or replacing `run-lease.json`'s existing schema or `agy_delegate.py`'s bundle-write
  sequencing — this capability adds a fencing/epoch check on top of the existing lease shape, not a
  new lease format.
- Rewriting `outcome_liveness.harvest_liveness` or the R31 stalled-terminal semantics — this
  capability adds the reaper/heartbeat layer and quarantine path; the existing stalled-terminal
  reclamation on the spec side is reused, not replaced.
- A generic cross-plugin "runner" abstraction that spans plugins neither agy nor saga own today —
  v1 scopes to the two verified concrete seams (agy delegation bundles, saga outcome dispatch); a
  third bridge is covered only if it can reuse the same module without a rewrite.
- UI/dashboard surfacing of quarantined or reaped runners — this issue is about the write-time
  mechanism and its evidence trail, not an operator-facing view of it.
- Retry/backoff policy for what happens *after* a runner is reaped (whether the unit is re-dispatched,
  how many times) — this issue only defines detection, fencing, and quarantine; re-dispatch policy is
  a fast-follow.

### Files expected to change
Indicative only — the exact set is `/plan`'s to determine.
- `plugins/agy/scripts/agy_delegate.py` — check the current lease epoch before accepting/landing an
  evidence write; reject a write from a superseded lease with `ORPHAN_WRITE_BLOCKED`.
- `plugins/saga/scripts/outcome_liveness.py` — extend/reuse for the quarantine-aside path
  (`quarantine_late_write()`) and add register/heartbeat primitives shared across bridges (proposed:
  `plugins/saga/scripts/delegation_runners.py` for register/heartbeat, `plugins/saga/scripts/
  reap_orphans.py` for the stalled-runner/late-writer reaper).
- `plugins/agy/skills/agy-delegate/references/delegation-contract.md` — document the fencing-token
  check and the quarantine-aside evidence shape as part of the required bundle contract.
- `tests/test_agy_delegate.py` (or new `tests/test_orphan_fencing.py`) — epoch-fencing-reject and
  quarantine-aside tests.
- `tests/test_outcome_liveness.py` (or new `tests/test_reap_orphans.py`) — heartbeat-reaper tests
  (stalled runner, empty-artifact runner, late-writer-after-close).

### Tests to add or update
- Epoch fencing: a stale-lease late write is rejected (`ORPHAN_WRITE_BLOCKED`) while the current-lease
  write for the same evidence slot persists unchanged.
- Lease quarantine: an expired-lease runner's write is moved aside to a quarantine location, not
  landed in the live evidence path and not silently dropped/lost.
- Heartbeat reaper: a runner with an aged heartbeat and a runner with an empty artifact directory are
  both flagged for reaping; a runner that heartbeats within budget is not flagged.
- Late-writer-after-close: a runner that writes evidence after its outcome/lease has already closed is
  flagged for reaping distinctly from a mid-run stall.
- Regression: existing `agy_delegate.py` bundle-write tests and `outcome.py` R31 stalled-terminal tests
  stay green — the fencing/quarantine/reaper layer must not change today's non-orphan write path.

## Definition of Done
Epoch fencing on evidence writes, lease quarantine for expired writers, and a shared
heartbeat reaper across bridges are merged: `run-lease.json` becomes a monotonic
fencing token checked on every evidence write (rejecting superseded writes with
`ORPHAN_WRITE_BLOCKED`), `quarantine_late_write()` moves expired-lease writes aside
instead of landing or dropping them, and `delegation_runners.py`/`reap_orphans.py`
flag stalled runners and late-writers-after-close — with stale-lease-rejected,
late-write-quarantined, and stalled-runner-flagged tests all passing.

### Acceptance criteria
- [ ] A superseded-lease write is rejected (`ORPHAN_WRITE_BLOCKED`) while the current-lease write for
  the same evidence slot persists. Check: `uv run pytest tests/test_orphan_fencing.py -k
  superseded_lease_rejected` → passes. (absorbed: T15-F1-8)
- [ ] An expired-lease runner's write is quarantined aside (moved to a distinguishable location), not
  landed and not lost. Check: `uv run pytest tests/test_orphan_fencing.py -k
  expired_lease_quarantined` → passes. (absorbed: T15-F2-7)
- [ ] A stalled runner (aged heartbeat) and a runner with empty artifacts are both flagged for
  reaping. Check: `uv run pytest tests/test_reap_orphans.py -k stalled_or_empty_flagged` → passes.
  (absorbed: T15-F4-4)
- [ ] A late-writer-after-close is flagged for reaping distinctly from a mid-run stall. Check:
  `uv run pytest tests/test_reap_orphans.py -k late_writer_after_close` → passes. (absorbed: T15-F4-4)
- [ ] Existing agy delegation bundle-write tests and saga `outcome.py` R31 stalled-terminal tests stay
  green (no behavior change to the non-orphan write path). Check: `uv run pytest
  plugins/agy/tests -k lease and tests/ -k outcome_liveness` → all pass.
- [ ] Full suite, format, lint, and types stay green. Check: `uv run pytest && uv run ruff format
  --check . && uv run ruff check . && uv run mypy plugins/ scripts/ tests/ --ignore-missing-imports`
  → all pass.

## Grounding References
- **T15-F1-8** (primary) — "Run-lease fencing so late orphan runner cannot clobber retry's evidence."
  Basis: `run-lease.json` (`plugins/agy/scripts/agy_delegate.py:319`) turned into a monotonic epoch
  fencing token checked on every evidence write, rejecting superseded-lease writes with
  `ORPHAN_WRITE_BLOCKED`; verified by a test where a stale-lease late write is rejected while the
  current-lease write persists.
- **T15-F2-7** (facet) — "Bridge-run liveness leases + late-write quarantine — automate git-status
  defense against orphans." Basis: bridge-run lease + `quarantine_late_write()` (reusing
  `outcome_liveness`) on the delegated-build path; verified by a test where an expired-lease runner's
  write is quarantined (moved aside) while a live-lease write lands. Distinct from T15-F1-8:
  quarantine-aside for *expired* leases vs. epoch-reject for *superseded* leases — the map's
  consolidation note explicitly calls out this distinction and both facets are kept because they cover
  different failure shapes.
- **T15-F4-4** (facet) — "Shared runner-liveness heartbeat + orphan reaper across teammate bridges."
  Basis: `delegation_runners.py` (register/heartbeat) + `reap_orphans.py` flagging stalled runners
  (aged heartbeat, empty artifacts) and late-writers; verified by a test covering late-write-after-
  close and idle/heartbeat-aged runners.
- **Duplicates killed into these three** (context only, not separately actioned): T15-F3-6 (kept-
  duplicate-of T15-F1-8: fencing-token tree guard), T15-F5-6 (kept-duplicate-of T15-F1-8: monotonic
  fencing-token mechanism), T15-F6-5 (kept-duplicate-of T15-F1-8: run-token/fencing late-write, also
  overlapping T15-F4-4's reaper), H-F5-2 (kept-duplicate-of T15-F4-4: dead-man's heartbeat watchdog).
- **Binding decisions this builds on**: `{#external-engines-never-gatekeepers}` (#283) and
  `{#external-engine-chaperone-dispatch}` (#318) — orphan fencing governs a delegated/chaperone
  *worker's* write path, it does not promote agy or any external engine to gatekeeper or a second
  executor kind; the fencing check is enforced Claude-side (or by the owning plugin's own code), not
  delegated to the external engine. `/outcome` campaign decisions (U1–U11, esp. derived-on-read status
  and HALT-not-degrade) — the reaper flags runners for reclamation, it does not introduce a new
  committed-status field; a flagged runner's disposition is still derived on read, consistent with the
  existing R31 `stalled` terminal in `plugins/saga/scripts/outcome.py:1055`.
- **Recurring-pain theme grounding**: `docs/plans/2026-07-03-plugin-fleet-grounding-brief.md`, section
  6, item 1 ("Silent no-ops in delegation & dead wiring... any bridge/delegation idea needs 'did it
  actually run/persist' verification" → theme 15, delegation integrity) and item 4 ("External-engine
  containment = hottest active frontier").
- **Pre-existing code seams verified during grounding**: `run-lease.json` write sites
  (`plugins/agy/scripts/agy_delegate.py:319,424,483,604`), the bundle contract documenting it
  (`plugins/agy/skills/agy-delegate/references/delegation-contract.md:110`), and the existing R31
  liveness processor (`plugins/saga/scripts/outcome.py:1055`, delegating to `outcome_liveness.
  harvest_liveness`).

### Recommended executor profile
- **Model**: sonnet
- **Effort**: high
- **Backend**: inline
- **External-LLM posture**: none
- **Justification**: mechanical, well-scoped change against two already-verified concrete code seams
  (`agy_delegate.py`'s lease writes, `outcome.py`'s liveness processor) with no architectural
  ambiguity left open — sonnet at high effort is sufficient; no case for opus-tier judgment or an
  external engine.

## Release Surface Checklist
This capability changes runtime behavior of the `agy` plugin's delegation-contract bundle shape (adds
the fencing-token check and quarantine-aside evidence path) and adds new shared modules under `saga`.
Update in the same PR:
- [ ] `plugins/agy/.claude-plugin/plugin.json` — version bump reflecting the delegation-contract
  behavior change.
- [ ] `plugins/saga/.claude-plugin/plugin.json` — version bump if `outcome_liveness` or new
  `delegation_runners.py`/`reap_orphans.py` modules ship under saga.
- [ ] `.claude-plugin/marketplace.json` — version/metadata sync for both plugins touched.
- [ ] `plugins/agy/CHANGELOG.md` and `plugins/saga/CHANGELOG.md` — entries describing the fencing/
  quarantine/reaper behavior change.
- [ ] Any version/metadata drift-guard tests in `tests/` — confirm they pass against the bumped
  versions before calling the PR ready.
- [ ] `plugins/agy/skills/agy-delegate/references/delegation-contract.md` — updated to document the
  fencing-token check and quarantine-aside bundle member as part of the required evidence contract.

### Verification
```bash
# New orphan-fencing and reaper tests
uv run pytest tests/test_orphan_fencing.py tests/test_reap_orphans.py -v

# Regression: existing lease-write and R31 stalled-terminal behavior unchanged
uv run pytest plugins/agy/tests tests/test_outcome_liveness.py -v

# Full repo gate (CI parity)
uv run pytest && uv run ruff format --check . && uv run ruff check . \
  && uv run mypy plugins/ scripts/ tests/ --ignore-missing-imports
```
Expected: all green; the epoch-fencing-reject, lease-quarantine, and heartbeat-reaper tests each
demonstrate their named failure mode being caught rather than silently landing or being lost.

### Handoff maturity
requirements-ready

### Suggested next action
Use `/plan <issue>` to create an implementation plan.

### Source context
- Source: docs/plans/2026-07-03-plugin-fleet-ideation-2026-07-03/survivors/T15.json (T15-F1-8,
  T15-F2-7, T15-F4-4) and docs/plans/2026-07-03-plugin-fleet-grounding-brief.md (sections 5–6)
- Source type: ideation-map
- Source title: Orphan runner containment: epoch fencing on evidence writes, lease quarantine,
  heartbeat reaper

### Context library links

_none_

## Created Issue

- URL: https://github.com/infiquetra/infiquetra-claude-plugins/issues/355
- Number: 355
- Created at: 2026-07-04T07:47:52.945327+00:00

