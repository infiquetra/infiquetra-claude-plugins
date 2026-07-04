---
title: "enhancement: closure gate — /outcome refuses to close a leaf on missing, stale-SHA, or unsuperseded-FAIL evidence"
repo: infiquetra-claude-plugins
type: enhancement
team: campps
project: operations
status: Idea
labels: enhancement, hermes-task, needs-plan
risk: medium
handoff_maturity: requirements-ready
tier: structural
wave: wave-2
objective: "Build the fleet telemetry and ledger substrate"
slug: pf-evidence-gated-closure
---

# enhancement: closure gate — /outcome refuses to close a leaf on missing, stale-SHA, or unsuperseded-FAIL evidence

### Objective
Build the fleet telemetry and ledger substrate.

### Intent

`outcome_orchestrator.harvest()` materializes a leaf as `done` the moment `barrier_satisfied()`
reports `satisfied=True` (`plugins/saga/scripts/outcome_orchestrator.py:145-172`, the
`verdict = barrier_satisfied(...)` / `if not verdict.satisfied: continue` / write-completion-event
sequence). That check consults only the current contract-satisfaction signal (canonical GitHub
event, in `barrier_satisfied` above `outcome_orchestrator.py:140-142`) — it never reads an evidence
ledger, never checks whether the required-check's commit SHA matches the SHA the outcome is
actually closing at, and never asks whether a FAIL result for that check was later silently
overwritten by a PASS. `manifest_store.py` (`plugins/saga/scripts/manifest_store.py`) confirms the
gap directly: `write_manifest`/`read_manifest` (`:119`, `:131`) persist one manifest per
`execution_id` with no append-only history and no supersession concept — a second write at the
same key simply replaces the first, so a probe re-run can overwrite a FAIL with a later PASS with
no record that a supersession occurred, no reason attached, and no gate to refuse it.

This is not hypothetical. The grounding brief for this ideation wave records the exact incident:
"a probe script overwriting a FAIL evidence artifact with a later PASS (audit chain-of-custody)"
(`docs/plans/2026-07-03-plugin-fleet-grounding-brief.md:150-151`). The repo's own Validation
Discipline mandate ("never assert 'fixed'/'working'/'shipped' without a confirming signal;
components-deployed does not equal end-to-end-verified") is exactly the property the closure path
currently cannot enforce, because nothing between "an evidence artifact exists" and "the leaf is
marked done" checks *which* SHA that artifact proves, or whether it was the last word on that
check.

This issue is the **consumer** half of the evidence-ledger substrate: a `closure_gate.py` module
that reads an append-only supersession chain and a required-check set, and wires its verdict into
the `harvest()` / close path so that:

1. **Supersession validator** (absorbed `T7-F4-3`) — closure is refused until any FAIL entry for a
   required check has a later, explicitly-justified supersession entry appended over it in the
   chain; an unexplained newer PASS does not silently clear a FAIL.
2. **Stale-SHA / missing-evidence HALT** (absorbed `T7-F1-8`) — if the required check's evidence
   entry's recorded SHA does not match the SHA the outcome is closing at, or the required check has
   no evidence entry at all, the leaf derives `HALT` with a named reason instead of `done`; a
   matching-SHA PASS derives `closed`.

Both facets are one wiring point (the `harvest()` barrier check) and one golden fixture (the
FAIL-overwritten-by-PASS incident), so they ship together rather than as two separate half-gates
that could each be bypassed by the other's absent half.

## Grounding References

- `T7-F4-3` — "Closure-gate consumer that derives eligibility from an immutable supersession
  chain" (`docs/plans/plugin-fleet-ideation-2026-07-03/survivors/T7.json`). `dod_sketch`: "Merged
  `closure_gate.py` (chain reader + supersession validator) wired into outcome harvest and the
  close path; golden fixture reproduces the FAIL-overwritten-by-PASS incident and asserts closure
  is refused until a justified supersession is appended." — basis is direct: the grounding brief's
  probe-script incident (`docs/plans/2026-07-03-plugin-fleet-grounding-brief.md:150-151`).
- `T7-F1-8` — "Evidence-gated leaf closure: /outcome refuses to close on missing or stale-SHA
  evidence" (`docs/plans/plugin-fleet-ideation-2026-07-03/survivors/T7.json`). `dod_sketch`:
  "Merged closure-gate check in the outcome derive path consulting the evidence ledger + intent
  required-check set; test asserts a FAIL or stale-SHA check derives HALT with a named reason and a
  matching-SHA PASS derives closed."
- Binding decisions this issue must not violate
  (`docs/plans/2026-07-03-plugin-fleet-grounding-brief.md:41-52`):
  - `/outcome` campaign (U1–U11) — **derived-on-read status, never committed status fields;
    HALT-not-degrade**. The gate must derive its verdict on read from the ledger + spec each
    reconcile tick, exactly like the existing `barrier_satisfied` check it augments — it must not
    introduce a new operator-writable or cached closure-status field, and a failed check must HALT,
    never silently proceed with a degraded/best-effort close.
  - `{#external-engines-never-gatekeepers}` (#283) — Claude remains verifier-of-record for this
    gated decision; the gate's supersession-justification step is not delegable to an external
    engine as an autonomous approver.
  - `{#readonly-verifier-fallback-ladder-325}` — if this work spawns any verify/review-class
    subagent outside a saga skill, it must use `subagent_type: saga:readonly-verifier` +
    `isolation: "worktree"` per `plugins/saga/references/sandbox-spawn-sites.md`, with the
    documented fallback ladder if that profile is unavailable.
- Existing code this issue must build on rather than reinvent: `outcome_orchestrator.harvest()`
  and `barrier_satisfied()` (`plugins/saga/scripts/outcome_orchestrator.py:1-172`),
  `manifest_store.py` write/read primitives (`plugins/saga/scripts/manifest_store.py:119-217`),
  `outcome_report.py`'s existing HALT-tier vocabulary (`TIER_AMBIGUITY`, "backend HALT — needs
  decision (R23)", `plugins/saga/scripts/outcome_report.py:42,145`) which this gate's new HALT
  reason should extend rather than duplicate.
- Sibling issue: `docs/sdlc-issue-drafts/plugin-fleet/pf-residency-evidence.md` is an unrelated
  cache-economics exploration from the same ideation wave — cited here only to show the house
  format this draft follows, not as a dependency.

### Out-of-scope / non-goals
In scope:
- A `closure_gate.py` module (or equivalently-named module under `plugins/saga/scripts/`) that:
  reads the evidence/supersession chain for a subplot's required checks, validates SHA-match
  against the outcome's current close SHA, validates that any FAIL entry has a later justified
  supersession before a subsequent PASS is honored, and returns a typed verdict (`closed` /
  `HALT:<reason>`).
- Wiring that verdict into `outcome_orchestrator.harvest()`'s `barrier_satisfied()` path so a leaf
  is never written as a `done` completion event without passing the gate.
- A golden fixture/test reproducing the FAIL-overwritten-by-PASS incident end to end (ledger has a
  FAIL, then an unexplained PASS at a later time, no supersession entry in between) and asserting
  closure is refused.
- Tests asserting: stale-SHA required check → HALT with a named reason; missing required-check
  evidence entry → HALT with a named reason; matching-SHA PASS with no supersession history →
  closed.

Out of scope (non-goals):
- **The evidence-ledger writer/producer.** This issue is the *consumer* (chain reader +
  supersession validator + gate wiring). Any new append-only ledger storage format, its write path,
  or migration of `manifest_store.py`'s current single-manifest-per-execution-id shape into a
  chain-of-entries shape is out of scope here unless a companion producer issue already exists to
  supply that format — `/plan` must confirm which repository artifact is the source of truth for
  the chain before implementation and file a follow-up if the producer does not yet exist.
- Changing `/outcome`'s derived-on-read architecture, or adding any committed/cached closure-status
  field — the gate's verdict stays a pure read-time derivation, consulted at harvest time exactly
  like the existing `barrier_satisfied()` check.
- Any UI/report rendering of the supersession chain in `outcome_report.py` beyond reusing its
  existing HALT-tier vocabulary — a dedicated chain-visualization surface is a separate follow-up.
- Retroactively re-validating or repairing evidence already recorded before this gate ships.
- Any change to the `{#readonly-verifier-fallback-ladder-325}` spawn policy itself — this issue
  only complies with it if a verify/review subagent spawn is introduced.

## Definition of Done

- `closure_gate.py` (chain reader + supersession validator) merged and wired into
  `outcome_orchestrator.harvest()`'s barrier check, so no leaf's `done` completion event is written
  without passing the gate.
- A golden fixture reproduces the FAIL-overwritten-by-PASS incident and a test asserts closure is
  refused until a justified supersession entry is appended over the FAIL.
- A test asserts a stale-SHA or missing-evidence required check derives `HALT` with a named,
  distinct reason string (not the generic barrier-unsatisfied path).
- A test asserts a matching-SHA PASS with no unresolved supersession gap derives `closed`.
- Full repo gate green: `uv run pytest`, `uv run ruff format --check .`, `uv run ruff check .`,
  `uv run mypy plugins/ scripts/ tests/ --ignore-missing-imports`.
- Release-surface checklist (below) completed or explicitly marked not-applicable in the PR.

### Acceptance criteria
- [ ] **(T7-F4-3)** Closure is refused when the chain holds a FAIL for a required check followed
      only by an unexplained PASS (no supersession entry). Check:
      `uv run pytest tests/test_closure_gate.py -k fail_overwritten_by_unexplained_pass` → the
      gate's verdict is `HALT`, not `closed`.
- [ ] **(T7-F4-3)** Closure proceeds once a justified supersession entry is appended over the FAIL
      (naming a reason) followed by a PASS. Check:
      `uv run pytest tests/test_closure_gate.py -k fail_superseded_with_justification` → the gate's
      verdict is `closed`.
- [ ] **(T7-F1-8)** A required check whose evidence entry's SHA does not match the outcome's
      current close SHA derives `HALT` with a named reason (e.g. `stale-sha:<check-id>`). Check:
      `uv run pytest tests/test_closure_gate.py -k stale_sha_halts` → passes.
- [ ] **(T7-F1-8)** A required check with no evidence entry at all derives `HALT` with a named
      reason (e.g. `missing-evidence:<check-id>`), never a silent pass-through. Check:
      `uv run pytest tests/test_closure_gate.py -k missing_evidence_halts` → passes.
- [ ] **(T7-F1-8)** A required check whose evidence entry's SHA matches the current close SHA and
      is `PASS` (with no unresolved supersession gap) derives `closed`. Check:
      `uv run pytest tests/test_closure_gate.py -k matching_sha_pass_closes` → passes.
- [ ] `outcome_orchestrator.harvest()` calls the gate before writing any `done` completion event;
      a leaf that fails the gate is never harvested. Check:
      `uv run pytest tests/test_outcome_orchestrator.py -k gate_blocks_harvest` → passes.
- [ ] The golden FAIL-overwritten-by-PASS fixture from the grounding-brief incident is checked in
      and exercised by the test suite (not just described in a docstring). Check:
      `uv run pytest tests/test_closure_gate.py -k golden_fixture` → passes.
- [ ] Full suite, format, lint, and types stay green. Check:
      `uv run pytest && uv run ruff format --check . && uv run ruff check . && uv run mypy plugins/ scripts/ tests/ --ignore-missing-imports`
      → all pass.

### Files expected to change

Indicative only; exact set is `/plan`'s to determine.

- `plugins/saga/scripts/closure_gate.py` (new) — chain reader, supersession validator, SHA-match
  check, typed verdict.
- `plugins/saga/scripts/outcome_orchestrator.py` — wire the gate's verdict into `harvest()`'s
  `barrier_satisfied()` path (`:145-172`).
- `plugins/saga/scripts/manifest_store.py` — extend only if `/plan` determines the chain must be
  read through this module's existing `read_manifest`/`list_manifests` surface rather than a new
  reader; do not change its write path unless a producer issue is confirmed to own that change.
- `tests/test_closure_gate.py` (new) — golden fixture + unit tests above.
- `tests/test_outcome_orchestrator.py` — harvest-blocks-on-gate-failure test.
- `plugins/saga/references/outcome-spec.md` — document the new closure-gate consultation as part
  of the harvest contract, if `/plan` determines the spec doc needs updating.

### Out-of-scope / non-goals

See "Scope & non-goals" above.

### Recommended executor profile

- Model: sonnet
- Effort: medium
- Backend: inline
- External LLM: none
- Justification: not above sonnet — bounded, mechanically-testable wiring work (one new module, one
  call-site wire-in, one golden fixture) against an already-documented `dod_sketch`/`ac_sketch`
  pair with no open architectural ambiguity. No external-engine involvement: this is a
  verifier-of-record closure decision (`{#external-engines-never-gatekeepers}`), so the gate logic
  itself must be authored and verified by Claude, not delegated.

### Release-surface checklist

Complete or explicitly mark not-applicable in the PR, per the repo's step-6 requirement to keep
plugin metadata and the diff telling the same story:

- [ ] `plugins/saga/.claude-plugin/plugin.json` — version bump if this changes `saga`'s shipped
      behavior (it does: the harvest/close contract gains a new gating check).
- [ ] `.claude-plugin/marketplace.json` — updated if the `saga` plugin entry's version/description
      needs to reflect the change.
- [ ] `plugins/saga/CHANGELOG.md` — entry describing the new closure gate and its HALT reasons.
- [ ] Any version/metadata drift-guard tests in `tests/` — confirmed still green and, if a new
      guard is warranted for the new gate's presence, added.
- [ ] If `/plan` determines no release-surface artifact needs to change, the PR description must
      say so explicitly rather than leaving the checklist silently unaddressed.

### Verification

```bash
# New closure-gate module + fixtures
uv run pytest tests/test_closure_gate.py -v

# Harvest wiring
uv run pytest tests/test_outcome_orchestrator.py -k gate_blocks_harvest -v

# Full repo gate (CI parity)
uv run pytest && uv run ruff format --check . && uv run ruff check . && uv run mypy plugins/ scripts/ tests/ --ignore-missing-imports
```

Expected: all green; the golden FAIL-overwritten-by-PASS fixture is refused until a justified
supersession is appended, and stale-SHA/missing-evidence required checks derive `HALT` with a
named reason rather than a silent close.

### Handoff maturity
requirements-ready

### Suggested next action
Use `/plan <issue>` to create an implementation plan.

### Source context
- Source: docs/plans/plugin-fleet-ideation-2026-07-03/survivors/T7.json (ids `T7-F4-3`, `T7-F1-8`)
- Source type: ideation-issue-map
- Source title: Closure gate: /outcome refuses to close a leaf on missing, stale-SHA, or
  unsuperseded-FAIL evidence

### Context library links

_none_

### Tests to add or update

- `tests/test_closure_gate.py`
- `tests/test_outcome_orchestrator.py`

## Created Issue

- URL: https://github.com/infiquetra/infiquetra-claude-plugins/issues/397
- Number: 397
- Created at: 2026-07-04T08:00:47.063323+00:00

