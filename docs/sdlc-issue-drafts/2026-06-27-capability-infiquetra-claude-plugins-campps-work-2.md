---
title: capability: infiquetra-claude-plugins campps work
repo: infiquetra-claude-plugins
type: capability
team: campps
project: operations
status: Idea
labels: capability, hermes-task, needs-plan
risk: medium
handoff_maturity: requirements-ready
---

# capability: infiquetra-claude-plugins campps work

### Objective
---
date: 2026-06-27
topic: silent-omission-completeness-gate
maturity: requirements-ready
source: docs/ideation/2026-06-26-vecu-port-seeds-ideation.md — survivor S-7 "Silent-Omission + Seam-Validation Gate, Spike-Calibrated"
---

# Silent-Omission Completeness Gate

## Summary

A required completeness gate for the saga execution engine that turns the engine's single most
recorded failure — a leaf agent that silently produces nothing — into a loud, typed, retryable
failure. It compares expected-vs-produced output at two granularities (a universal mechanical
detector on every leaf, plus an itemized manifest diff wherever a unit declares a contract) and ships
with an on-demand self-test that proves the gate still fires.

## Problem Frame

The engine's dominant recorded failure mode is silent omission, not incorrectness. In one real run
(`wf_4a5f04b6`), 16 of 19 fan-out agents finished without ever emitting their structured output —
budget exhaustion, the agents over-read and ran out of tokens before producing a result
(`docs/engineering-journal/LEARNINGS.md:603`/`:607`).

Today nothing detects this. The only defense is a prophylactic prompt instruction (`BUDGET_RIDER` in
`plugins/saga/scripts/execution_spec.py`) that asks cheap agents to always emit. When it fails, the
two execution paths `/plan` actually emits both swallow the failure: the auto-emitted `.workflow.js`
path passes the resulting `null` straight to dependents with no null-check, and the team-execution
path produces a silently-absent evidence record the orchestrator may treat as a skip or `warn`. The
run still looks green while downstream work is built on nothing.

This is the omission a correctness gate cannot catch: refute-N and the reviewer panel ask "is what's
here right?" — but there is nothing on the page to refute. The thing that is wrong is the absence.

## Key Decisions

These framing choices were made during the brainstorm and constrain the requirements below.

- **Two granularities, one comparison (Option C).** The gate is one expected-vs-produced comparison
  at two levels: a mechanical presence/count detector that runs on every leaf, and an itemized
  manifest diff that runs wherever a unit declares a contract. They catch different absences — the
  detector catches "the agent vanished," the manifest catches "the agent half-did it."
- **Manifest is opportunistic, not mandated.** The itemized diff fires only where a machine-diffable
  output contract exists. Leaves without one get the detector only. v1 does not backfill contracts
  across the codebase.
- **Omission gate first; seam-hardening deferred.** The structured-output seam is covered by the
  detector and the JSON-parse seam is already hardened in code, so v1 is the omission gate. Validating
  generated patches and command inputs as hostile is a fast-follow designed alongside the live R14
  read-only verify/review profile, so the least-privilege check is not built twice.
- **On-demand self-test, not standing calibration.** Proving the gate works is a `--self-test` you run
  on demand — the "test" button on a smoke detector — not a scheduled harness that tracks catch-rate
  over time. A standing measurement loop is the S-6 ceremony shape already rejected for a solo tool.
- **Silent omission detected now, typed-failure enum extensible.** v1 detects the omission and emits
  the observable class `missing-output` (its dominant recorded cause is budget exhaustion, but the gate
  does not assert cause from absence); `malformed-output` and `verifier-disagreement` are the other two
  v1 classes. The enum is built so future classes slot in later without rework.

## Actors

- A1. Completeness gate — the new system actor; runs at each leaf boundary on the fan-out backends and
  owns the trip/pass decision and failure classification.
- A2. Leaf agent — the spawned worker whose result is inspected; may die, truncate, or omit.
- A3. Operator — sees a loud typed failure instead of a falsely-green run, and invokes `--self-test`
  on demand.

## Requirements

What must be true about the gate, grouped by concern. IDs are stable and continuous.

**Mechanical detection (always-on, every leaf)**

These checks trip on *absence where output was expected* — a schema-bearing agent, a fan-out unit's
enumerated targets, or a non-empty `returns` contract. A leaf that legitimately returns no structured
output is not tripped on absence. A detected absence carries the base class `missing-output` (the cause
is not inferable from absence alone — see R8).

R1. After every leaf agent returns, the gate inspects the result before any dependent consumes it; for
an agent expected to emit structured output, a `null`/absent result or a missing emit is a trip
(`missing-output`), never treated as an empty-but-valid output.

R2. A structurally truncated output (cut off mid-structure, incomplete envelope) is a trip
(`malformed-output`) rather than being parsed as complete.

R3. When a leaf declares a count of expected items — for v1, a fan-out unit's enumerated target list
(`Unit.targets`) — and produces fewer, the shortfall is a trip (`missing-output`). A generic count
source beyond fan-out targets is deferred.

R4. On any trip the gate fails loud with a typed, named failure and never releases the partial *return
envelope* downstream — the dependent is not launched with it. Containing on-disk side-effects an agent
already wrote is out of v1 scope (the deferred R14 workspace-isolation work). Silent degrade is
prohibited (halt-not-degrade).

**Manifest completeness (opportunistic)**

R5. A leaf's required named outputs already exist as a structured contract today — `Unit.returns`, a
list of required structured-output keys mirroring the unit schema's `required`. The gap is enforcement:
`returns` is rendered into the agent prompt but never diffed against what the agent emits. v1 enforces
it (it does not invent the schema).

R6. Where a `returns` contract is non-empty, the gate diffs the declared required keys against the keys
the agent actually emitted in its structured output, and trips (`missing-output`) on any declared key
that is absent, naming the omission.

R7. The manifest check is opportunistic: a leaf with no contract receives the mechanical detector
only. v1 does not require a contract on every leaf.

**Typed failures and bounded iteration**

R8. Every trip carries a typed class. v1 wires the classes its own trips produce: `missing-output`
(absence / short count / missing key — the dominant case, whose recorded cause is budget exhaustion but
which the gate cannot attribute from absence alone), `malformed-output` (truncation, R2), and
`verifier-disagreement` (cap, R9). The enum is extensible so genuinely-future classes (`tool-denial`,
`stale-context`, `merge-conflict`) slot in later without rework.

R9. The emitted-workflow path gains the iteration/ping-pong cap it currently lacks; reaching the cap
emits a typed `verifier-disagreement` failure that names the upstream cause instead of silently
exiting the loop.

R10. The cap is overridable when iterate-to-consensus is the intended behavior — e.g. differential
spec-validation, where divergence signals an ambiguous spec rather than a defect. An override still
terminates: it raises the bound or hands to a manual continuation, never removes it — an uncapped loop
is prohibited.

**Coverage**

R11. The primary v1 seam is the emitted `.workflow.js` path: every emitted agent result is
gate-checked before a dependent reads it (this path has no null-check today). This is the synchronous
model — the gate inspects a returned value. The R9 cap addition applies here; v1 does not change
team-execution's existing proceed-best-available cap.

R12. The team-execution path gains an evidence-absence check evaluated at validator/leaf process exit
(there is no return value to inspect): a *required, non-skipped* validator or leaf whose evidence record
was never written is a trip (`missing-output` / fail). A validator legitimately `skipped-by-config` or
optional is not tripped.

**Self-test**

R13. A `--self-test` mode plants one known omission, asserts the gate trips on it, reports the result,
and exits. It runs out-of-band — not in a live execution's workspace or context — and is invoked on
demand, never on a standing schedule.

## Key Flows

The gate's behavior at a leaf boundary, plus the self-test path.

F1. Normal completion.
**Trigger:** a leaf agent returns a result. The gate runs the mechanical detector (always) and the
manifest diff (if a contract exists). Both clean → the result is released to dependents and the leaf
is ticked complete.
**Covers R1, R5, R6, R7** (the clean pass; the R2–R4 trip conditions are exercised in F2).

F2. Omission caught.
**Trigger:** an inspected leaf result is null / truncated / short / missing a declared key (synchronous
model), OR a required evidence record is absent at process exit (team-execution model). The gate trips,
classifies the failure, and withholds the partial return envelope from every dependent. It then routes
by class within a bounded retry budget — a retry re-runs the unit *unchanged* (it never shrinks the
unit's declared required outputs) or halts with the typed cause. No dependent is launched on the partial
envelope.
**Covers R1, R2, R3, R4, R8, R9, R11, R12.**

F3. Self-test.
**Trigger:** the operator runs `--self-test` out-of-band. The harness injects a known planted omission
into a throwaway context, asserts the gate trips, reports pass/fail, and exits — touching no live
workspace.
**Covers R13.**

## Acceptance Examples

The conditional cases where prose alone leaves edge-case ambiguity.

AE1. **Covers R1, R8.** A cheap-tier leaf exhausts its budget and returns without emitting its
structured output → the gate trips `missing-output` (the dominant recorded cause is budget exhaustion,
but the gate does not assert cause from absence), blocks the dependent, and surfaces the failure; the
empty result is not treated as a valid empty output.

AE2. **Covers R2.** An agent's structured output is cut off mid-object → the gate trips rather than
parsing the partial envelope as complete.

AE3. **Covers R3.** A fan-out leaf declares 12 targets and reconciles only 9 → the 3-target shortfall
is reported as an omission, not a success.

AE4. **Covers R6.** A leaf's `returns` contract requires the keys `migration_sql`, `rollback_sql`,
`test_file` and the agent emits a structured result omitting `rollback_sql` → the gate names the missing
key and fails (`missing-output`).

AE5. **Covers R7.** A leaf has no contract → a complete-but-unverifiable output passes the manifest
layer and remains subject only to the mechanical detector.

AE6. **Covers R9, R10.** An emitted-workflow verify/iteration loop reaches the cap without consensus →
the engine emits `verifier-disagreement` naming the unresolved point and halts; unless the unit is
flagged iterate-to-consensus, in which case the bound is raised (never removed) and the loop continues
to a higher bound.

AE7. **Covers R13.** `--self-test` runs against a healthy gate → the planted omission is caught and the
command reports pass; if the gate fails to catch it, the command reports fail.

AE8. **Covers R12.** A required team-execution validator never writes its evidence record (its agent
died) → at process exit the gate finds the expected record absent and trips (fail), instead of treating
the silent gap as `skipped`/`warn`. A validator `skipped-by-config` is not tripped.

AE9. **Covers R1, R7.** A prose-return or side-effect-only leaf that declares no structured-output
contract returns no keys → the gate does not trip on the absence (output was not expected),
distinguishing a legitimate empty from an omission.

## Scope Boundaries

What v1 deliberately excludes, and why.

- Generated-patch and command-input hostile-input validation — deferred to a fast-follow designed with
  the live R14 read-only verify/review profile, so the least-privilege check is not built twice.
- A standing/scheduled spike-calibration harness that tracks catch-rate over time — killed; the S-6
  measurement-ceremony shape already rejected for a solo tool. The on-demand `--self-test` replaces it.
- Backfilling output contracts onto existing leaves — the manifest layer stays opportunistic.
- Full implementations of the non-triggered failure classes (`tool-denial`, `stale-context`,
  `merge-conflict`) — the enum is extensible, but v1 wires only the classes its own trips produce
  (`missing-output`, `malformed-output`, `verifier-disagreement`).
- Changing team-execution's existing proceed-best-available cap — R9 adds the typed cap to the
  emitted-workflow path; the team-execution cap stays as-is in v1.
- The inline backend — it has no fan-out seam where an agent result crosses into a dependent.

## Dependencies / Assumptions

Upstream dependencies and load-bearing assumptions, including absences verified during grounding.

- The manifest half enforces an output contract that already exists in structured form — `Unit.returns`
  (`plugins/saga/scripts/execution_spec.py:180`), a list of required structured-output keys mirroring
  the unit schema's `required`. Verified: `returns` is structured today but is only rendered into the
  agent prompt, never diffed against what the agent emits. v1 adds the enforcement, not the schema.
- Verified absent today and load-bearing: the emitted `.workflow.js` path performs no null-check after
  agent calls; the team-execution path has no detection when an evidence record is never written; no
  typed failure classes exist anywhere; the iteration caps exist only in team-execution prose
  (`plugins/team-execution/.../consensus-protocol.md:17`,
  `plugins/team-execution/.../validator-execution-order.md:27`), not on the emitted path.
- Assumes the two fan-out backends (emitted `.workflow.js`, team-execution) are the seams worth
  guarding; the inline backend is excluded by design.
- The gate extends existing patterns rather than inventing them: spec-construction validation already
  fails loud (`ExecutionSpec.validate` / `OutcomeSpec.validate`), and the JSON-parse seam already
  rejects silent coercions (`plugins/saga/scripts/outcome_spec.py` input helpers). This adds the
  missing output-seam and completeness checks.

## Success Criteria

Signals beyond the requirements themselves.

- The engine's dominant recorded failure — a leaf that silently produces nothing — surfaces as a loud,
  typed, named failure instead of a green-looking run with corrupted downstream work.
- No null or partial leaf result reaches a dependent on the emitted-workflow path.
- `--self-test` demonstrably trips the gate on a planted omission and reports it.
- The doc hands off clean: `/doc-review` can assess readiness without follow-ups, and `/plan` can
  design the mechanism (where the check sits, how the contract is encoded, how retries route by class)
  without inventing user-facing behavior or scope.

## Sources / Research

Breadcrumbs for the planner reading cold.

- Dominant failure mode: `docs/engineering-journal/LEARNINGS.md:603`/`:607` (16/19 agents died without
  emitting StructuredOutput — budget exhaustion, not rate limits); `:423` (fan-out agents hedge on
  output conventions unless given the exact form).
- Emitted-workflow seam: `plugins/saga/scripts/execution_spec.py` — the workflow emitter (no null-check
  after emitted agent calls), the verify-panel emitter, `BUDGET_RIDER`, and `Unit.returns` (`:180`), the
  structured return contract that is rendered into the prompt but enforced nowhere.
- Parse-seam already hardened: `plugins/saga/scripts/outcome_spec.py` — strict input helpers reject
  silent coercions; `ExecutionSpec.validate` / `OutcomeSpec.validate` fail loud at spec construction.
- team-execution seams: `validator-registry.md` (validator-family dispatch — the completeness check's
  natural plug-in point), `validator-criteria.md` (gate-outcome statuses), `consensus-protocol.md:17`
  and `validator-execution-order.md:27` (the existing untyped iteration caps), and the Phase B step
  that trusts the emitted `## Team Structure` unconditionally.
- Engine patterns extended: `docs/engineering-journal/DECISIONS.md:286` (parallel-layer emitter +
  refute-N panels + provenance guard at save), `:348` (one spec, two emitters), `:960` (append-only
  canonical log), `:1097` (CLI stays deterministic; skills own interpretation).
- Ideation provenance: `docs/ideation/2026-06-26-vecu-port-seeds-ideation.md`, survivor S-7 (and its
  absorbed R12: typed failure classes + overridable cap).

### Intent
Add a required completeness gate to the saga execution engine that converts the engine's #1 recorded
failure — a leaf agent that silently produces nothing (16/19 agents in run `wf_4a5f04b6` died without
emitting StructuredOutput) — into a loud, typed, retryable failure. The gate is one expected-vs-produced
comparison at two granularities: an always-on mechanical detector (catches the death/truncation) plus an
opportunistic manifest diff that enforces the existing-but-unenforced `Unit.returns` contract (catches the
half-job). Ships with an on-demand `--self-test`. Full requirements, flows, and acceptance examples are in
the embedded brainstorm above and at
`docs/brainstorms/2026-06-27-silent-omission-completeness-gate-requirements.md` (doc-review verdict READY —
`docs/reviews/2026-06-27-silent-omission-completeness-gate-readiness.md`).

### Out-of-scope / non-goals
- Generated-patch + command-input hostile-input validation — deferred to a fast-follow designed with the
  live R14 read-only verify/review profile (don't build the least-privilege check twice).
- A standing/scheduled spike-calibration harness that tracks catch-rate over time — killed (the S-6
  measurement-ceremony shape already rejected for a solo tool); the on-demand `--self-test` replaces it.
- Backfilling `returns` contracts onto existing leaves — the manifest layer stays opportunistic.
- Full implementations of the non-triggered failure classes (`tool-denial`, `stale-context`,
  `merge-conflict`) — the enum is extensible, but v1 wires only `missing-output`, `malformed-output`,
  `verifier-disagreement`.
- Changing team-execution's existing proceed-best-available cap — R9 adds the typed cap to the
  emitted-workflow path only.
- The inline backend — it has no fan-out seam where an agent result crosses into a dependent.

### Files expected to change
Indicative only — the exact set is `/plan`'s to determine.
- `plugins/saga/scripts/execution_spec.py` — null-check / typed-trip after each emitted `agent()` call; enforce `Unit.returns`.
- `plugins/saga/scripts/completeness_gate.py` — new gate + classifier module + `--self-test` (proposed path).
- `plugins/team-execution/skills/team-execution/references/validator-execution-order.md` — required-evidence-absence check at process exit.
- `tests/test_completeness_gate.py` — new detector / manifest / self-test tests (repo-root collected).

### Tests to add or update
- Detector: trips on null/no-emit, truncated output, and declared-count shortfall; does NOT trip on a legitimately-empty (no-contract) leaf.
- Manifest: trips on a missing declared `Unit.returns` key; passes when all required keys are present.
- Typed failures: `missing-output` / `malformed-output` / `verifier-disagreement` emitted on the correct triggers; enum proven extensible.
- Self-test: `--self-test` plants a known omission and reports caught vs uncaught.
- Coverage: emitted-workflow path null-checks every agent result; team-execution required-evidence-absence trips (a `skipped-by-config` validator does not).

### Context library links
- source_context: docs/brainstorms/2026-06-27-silent-omission-completeness-gate-requirements.md

### Acceptance criteria
- [ ] Detector trips on a null/no-emit leaf result with class `missing-output`. Check: `uv run pytest tests/test_completeness_gate.py -k missing_output` → passes.
- [ ] Detector trips on a truncated structured output with class `malformed-output`. Check: `uv run pytest tests/test_completeness_gate.py -k malformed_output` → passes.
- [ ] Manifest diff trips on a missing declared `Unit.returns` key. Check: `uv run pytest tests/test_completeness_gate.py -k manifest_missing_key` → passes.
- [ ] A legitimately-empty (no-contract) leaf is NOT tripped on absence. Check: `uv run pytest tests/test_completeness_gate.py -k legitimate_empty` → passes.
- [ ] `--self-test` plants a known omission and reports it caught. Check: `python3 plugins/saga/scripts/completeness_gate.py --self-test` → exit `0`, output contains `caught`.
- [ ] The emitted-workflow path null-checks every emitted agent result before a dependent reads it. Check: `uv run pytest tests/test_execution_spec.py -k emitted_null_check` → passes.
- [ ] Full suite, format, lint, and types stay green. Check: `uv run pytest && uv run ruff format --check . && uv run ruff check . && uv run mypy plugins/` → all pass.

### Verification
```bash
# Unit + integration for the new gate
uv run pytest tests/test_completeness_gate.py -v
# Self-test proves the gate fires on a planted omission (out-of-band)
python3 plugins/saga/scripts/completeness_gate.py --self-test
# Full repo gate (CI parity)
uv run pytest && uv run ruff format --check . && uv run ruff check . && uv run mypy plugins/
```
Expected: all green; `--self-test` exits `0` and reports the planted omission caught.

### Handoff maturity
requirements-ready

### Suggested next action
Use `/plan <issue>` to create an implementation plan.

### Source context
- Source: docs/brainstorms/2026-06-27-silent-omission-completeness-gate-requirements.md
- Source type: brainstorm
- Source title: Silent-Omission Completeness Gate
