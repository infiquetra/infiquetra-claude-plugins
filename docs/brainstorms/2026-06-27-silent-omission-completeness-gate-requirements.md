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
- **Dominant failure class wired now, enum extensible.** Only `budget-exhaustion` is implemented
  end-to-end in v1; the typed-failure enum is built so the other classes slot in later without rework.

## Actors

- A1. Completeness gate — the new system actor; runs at each leaf boundary on the fan-out backends and
  owns the trip/pass decision and failure classification.
- A2. Leaf agent — the spawned worker whose result is inspected; may die, truncate, or omit.
- A3. Operator — sees a loud typed failure instead of a falsely-green run, and invokes `--self-test`
  on demand.

## Requirements

What must be true about the gate, grouped by concern. IDs are stable and continuous.

**Mechanical detection (always-on, every leaf)**

R1. After every leaf agent returns, the gate inspects the result before any dependent consumes it; a
`null`/absent result, or one where the agent never emitted its structured output, is a trip — never
treated as an empty-but-valid output.

R2. A structurally truncated output (cut off mid-structure, incomplete envelope) is a trip rather than
being parsed as complete.

R3. When a leaf declares a count of expected items (e.g. "N targets", "N files") and produces fewer,
the shortfall is a trip — the count-level completeness check.

R4. On any trip the gate fails loud with a typed, named failure and never releases the null/partial
result downstream. Silent degrade is prohibited (halt-not-degrade).

**Manifest completeness (opportunistic)**

R5. A leaf may declare a machine-diffable contract of its required named outputs, lifted from today's
prose-only form into a form the gate can compare against.

R6. Where a contract is present, the gate diffs declared-vs-produced named outputs and trips on any
declared output that is missing, naming the omission.

R7. The manifest check is opportunistic: a leaf with no contract receives the mechanical detector
only. v1 does not require a contract on every leaf.

**Typed failures and bounded iteration**

R8. Failures carry a typed class. v1 wires the dominant class (`budget-exhaustion`) end-to-end and
ships the enum extensible so additional classes (malformed-output, tool-denial, stale-context,
merge-conflict, verifier-disagreement) slot in later without rework.

R9. The emitted-workflow path gains the iteration/ping-pong cap it currently lacks; reaching the cap
emits a typed `verifier-disagreement` failure that names the upstream cause instead of silently
exiting the loop.

R10. The cap is overridable when iterate-to-consensus is the intended behavior — e.g. differential
spec-validation, where divergence signals an ambiguous spec rather than a defect.

**Coverage**

R11. The primary v1 seam is the emitted `.workflow.js` path: every emitted agent result is
gate-checked before a dependent reads it (this path has no null-check today).

R12. The team-execution path gains an evidence-absence check: an expected validator or leaf evidence
record that was never written is a trip (fail), not a skip or silent `warn`.

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
**Covers R1, R2, R3, R5, R6, R7.**

F2. Omission caught.
**Trigger:** a leaf returns null, a truncated output, fewer items than declared, or a result missing a
declared output. The gate trips, classifies the failure as a typed class, withholds the result from
every dependent, and routes by class — retry (e.g. `budget-exhaustion` → retry with reduced scope) or
halt with the typed cause. No dependent ever observes the partial result.
**Covers R1, R2, R3, R4, R8, R9, R11, R12.**

F3. Self-test.
**Trigger:** the operator runs `--self-test` out-of-band. The harness injects a known planted omission
into a throwaway context, asserts the gate trips, reports pass/fail, and exits — touching no live
workspace.
**Covers R13.**

## Acceptance Examples

The conditional cases where prose alone leaves edge-case ambiguity.

AE1. **Covers R1.** A cheap-tier leaf exhausts its budget and returns without emitting its structured
output → the gate marks it `budget-exhaustion`, blocks the dependent, and surfaces the failure; the
empty result is not treated as a valid empty output.

AE2. **Covers R2.** An agent's structured output is cut off mid-object → the gate trips rather than
parsing the partial envelope as complete.

AE3. **Covers R3.** A fan-out leaf declares 12 targets and reconciles only 9 → the 3-target shortfall
is reported as an omission, not a success.

AE4. **Covers R6.** A leaf's contract names `migration.sql`, `rollback.sql`, `test_migration.py` and
the produced set omits `rollback.sql` → the gate names the missing output and fails.

AE5. **Covers R7.** A leaf has no contract → a complete-but-unverifiable output passes the manifest
layer and remains subject only to the mechanical detector.

AE6. **Covers R9, R10.** Reviewer↔implementer iteration reaches the cap without consensus → the engine
emits `verifier-disagreement` naming the unresolved point; unless the unit is flagged
iterate-to-consensus, in which case the cap is lifted and the loop continues.

AE7. **Covers R13.** `--self-test` runs against a healthy gate → the planted omission is caught and the
command reports pass; if the gate fails to catch it, the command reports fail.

## Scope Boundaries

What v1 deliberately excludes, and why.

- Generated-patch and command-input hostile-input validation — deferred to a fast-follow designed with
  the live R14 read-only verify/review profile, so the least-privilege check is not built twice.
- A standing/scheduled spike-calibration harness that tracks catch-rate over time — killed; the S-6
  measurement-ceremony shape already rejected for a solo tool. The on-demand `--self-test` replaces it.
- Backfilling output contracts onto existing leaves — the manifest layer stays opportunistic.
- Full implementations of the five non-dominant failure classes — the enum is extensible, but only
  `budget-exhaustion` is wired end-to-end in v1.
- The inline backend — it has no fan-out seam where an agent result crosses into a dependent.

## Dependencies / Assumptions

Upstream dependencies and load-bearing assumptions, including absences verified during grounding.

- The manifest half depends on lifting the output contract from its current prose-in-prompt form
  (`plugins/saga/scripts/execution_spec.py`, the agent-prompt builder) into a machine-diffable
  declaration. Verified: the contract exists today only as prose injected into the agent prompt.
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
  after emitted agent calls), the verify-panel emitter, `BUDGET_RIDER`, and the agent-prompt builder
  where the output contract lives as prose.
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
