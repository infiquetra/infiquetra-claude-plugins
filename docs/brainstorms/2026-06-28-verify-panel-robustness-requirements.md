---
date: 2026-06-28
topic: verify-panel-robustness
maturity: requirements-ready
source: docs/ideation/2026-06-26-vecu-port-seeds-ideation.md (survivor R7/A7 — cc-workflows fan-out cost+robustness rubric; scope constrained in brainstorm per the ideation's own flag)
---

# Verify-Panel Robustness — Non-Applicable vs Failed Panel Members

## Summary

A verify/review panel must distinguish two reasons a member produces no verdict, and handle them on
two different paths. A member can be **statically non-applicable** — its precondition is absent and
known *before* dispatch (an architecture/ADR lens with no architecture docs) — or it can **fail at
runtime** — it errors, hangs, or times out *during* dispatch. They share one discipline (the absence
is recorded with its cause, never silently dropped) but must diverge at the quorum floor: a static
non-applicability is **excluded from the panel denominator at composition time** (so it never triggers
the floor or any escalation), while a runtime failure makes the pass-rule **recompute its threshold
over the members that reported**, down to a minimum-quorum floor below which the advisory result is
marked under-strength.

This is the genuine residue of the VECU R7/A7 seed after grounding against saga 0.38.0 *and the
emitter code*. The quorum rule, the panel cap, cache-coherent same-tier verifiers, and the
outcome-level cost levers are already shipped (`execution-spec.md:44-61`; `operator-choice.md:288`).
The two real gaps are (**Layer A**) that a runtime-missing verifier is today *silently* dropped from
the refute count while the threshold stays fixed — biasing the panel toward relying on an unverified
result — and (**Layer B**) that a non-applicable reviewer dimension today scores a *fabricated*
passing default into a consensus average instead of being excluded. The seed's "concurrency cap" and
"cost rubric" are deliberately out of scope — already shipped, and both review engines independently
affirmed excluding them.

## Problem Frame

**Layer A (cc-workflows verify panel).** The verify block (`execution-spec.md:44-61`) defines a panel
as `n` independent verifiers at the parent unit's `{model, effort}` tier, reconciled by `pass_rule`
(`majority` = a finding survives unless ≥ ⌈N/2⌉ refute it, or `unanimous`), capped at
`VERIFY_N_CAP=7`, default `n=3`/majority. The *generated* reconciliation
(`execution_spec.py:505-515`) is:

```
const X_refute_count = X_verdicts.filter((v) => v && v.refuted && v.refuted.length > 0).length
const X_refuted = X_refute_count >= threshold        // threshold = ⌈n/2⌉ of the DECLARED n (:486,:510)
if (X_refuted) log(`... refuted by ${count}/n verifiers — review before relying on it`)
```

The `v &&` guard means a null verifier does not crash — but it is **silently counted as "did not
refute,"** while `threshold` stays at ⌈n/2⌉ of the *original* n. So a hung or errored verifier
dilutes the refute count and can **mask a genuine majority refutation** (e.g. refute-3 majority,
threshold 2: if one verifier refutes and one nulls, `refute_count=1 < 2` → not refuted, where two
live refutals would have flipped it). That is the unsafe direction — a verifier failure makes the
panel *less* skeptical. The panel is explicitly **advisory** — a coarse "did enough skeptics refute
anything" signal whose only consumer is a `log()` warning (`execution_spec.py:477-481, 511-515`);
there is no re-spawn, no operator gate, no `inconclusive` control-flow state. Budget exhaustion is
*already* mitigated — `BUDGET_RIDER` makes a budget-exhausted verifier still emit
(`execution_spec.py:438,447`; tested at `tests/test_workflow_emitter.py:771`) — so the residue is a
verifier that dies or hangs *without* emitting.

**Layer B (team-execution review panel).** Three base reviewers always spawn, including architecture
(`reviewer-registry.md:9-17`); each scores five dimensions and the overall is their average
(`architecture-reviewer.md:34`), gated by unanimous-ACCEPT (overall ≥ 9.0, no dimension < 7.0;
`consensus-protocol.md:67`). When no architecture docs exist, the reviewer does *not* skip the
ADR-coverage dimension — it scores a fabricated **N/A (8.0 default)** that goes into the average
(`architecture-reviewer.md:75-80`). A fabricated passing score for a dimension that was never
assessed is the same disease as Layer A's silent null: a non-assessed member silently shapes a
consensus verdict.

## Key Decisions

- **KD1 — Two kinds of absence: one logging discipline, two resolution paths.** A panel member that
  produces no verdict is absent for one of two reasons that must NOT share the floor/escalate logic:
  **static non-applicability** (precondition absent, known before dispatch, permanent) or **runtime
  failure** (error/hang/timeout, discovered during dispatch, transient). Shared: both are recorded
  with cause, never silently dropped. Divergent: a static skip is excluded from the denominator at
  composition time (it never enters the floor); a runtime failure triggers a threshold recompute over
  reporters. *(This corrects an earlier "one mechanism, two triggers" framing the review found
  unsound: a permanent skip placed under the runtime floor either loops forever on re-spawn or
  bypasses the floor entirely.)*

- **KD2 — Today a runtime-missing verifier is silently uphold-biased.** `execution_spec.py:507`'s
  `v && v.refuted` drops a null from the refute count while the threshold stays ⌈n/2⌉ of the original
  n (`:486,:510`). A hung/errored verifier therefore counts as "did not refute" and can mask a genuine
  majority refutation. Layer A recomputes the threshold over the verifiers that reported and records
  the missing one; it adds no new control flow.

- **KD3 — The fix lives in the existing advisory surfaces, not a new subsystem.** cc-workflows verify
  is advisory: `_refuted` is consumed by a `log()` warning (`execution_spec.py:511-515`) over a coarse
  panel-level signal (`:477-481`). R7 makes that log *honest* (it states which verifiers were missing
  and the `(n−k)` the verdict was computed over); it does NOT add a re-spawn / operator-escalation /
  `inconclusive` control-flow state. That would be net-new and is out of v1.

- **KD4 — Layer B already exists and is flawed in the same family.** When the ADR precondition is
  absent, architecture-reviewer fabricates an N/A→8.0 dimension score into the average
  (`architecture-reviewer.md:34,75-80`). Layer B replaces the fabricated default with **exclusion**
  from the denominator: overall = mean of the dimensions that actually applied. The bug is not the
  bias *direction* (8.0 can pull either way) but that a non-assessed dimension contributes a
  fabricated number to a safety gate at all.

- **KD5 — Budget exhaustion is already handled; the residue is death/hang.** `BUDGET_RIDER`
  (`execution_spec.py:438,447`) makes a budget-exhausted verifier still emit. So Layer A's
  runtime-failure residue is specifically a verifier that dies or hangs without emitting — which is
  what Q1 (verifier-level liveness) resolves.

- **KD6 — Extend existing surfaces; honor the dead-wiring bar.** Layer A modifies the existing
  reconciliation (`execution_spec.py:505-515`) and its log consumer; Layer B modifies the existing
  N/A→8.0 default and the dimension average. codex confirmed there is no existing implementation or
  test for "minimum quorum" / "missing verdict" outside this doc — so those concepts must attach to
  the existing reconciliation, not float free. No new field is accepted without a real producer and a
  real spawned consumer (`docs/engineering-journal/LEARNINGS.md:126-136`).

## Requirements

### The two-kinds contract (shared core + the split)

- R1. A panel member that produces no verdict is recorded with its **cause** —
  `static-non-applicable` (precondition absent) or `runtime-failure` (error/hang/timeout). It is never
  dropped from the count without a record. *(Today a runtime null is silently dropped by the `v &&`
  guard, `execution_spec.py:507` — that silent drop is the gap; this is distinct from the fan-out
  *target* reconciliation that is already shipped at `execution-spec.md:86-89`.)*
- R2. **Static non-applicability** is resolved at panel-composition time: the verifier/dimension is
  excluded from the panel denominator *before* dispatch, so it never enters the threshold/floor
  computation and never triggers escalation.
- R3. **Runtime failure** is resolved at reconciliation time: the pass-rule recomputes its threshold
  over the `(n − k)` members that reported — `majority` ⇒ ⌈(n−k)/2⌉, `unanimous` ⇒ all `(n−k)` —
  provided `(n − k)` is at or above a minimum-quorum floor. The `⌈·⌉` rule makes even `(n−k)` ties
  deterministic.
- R4. Below the floor, the advisory result is marked **under-strength** in the existing log surface
  (KD3) rather than returning a confident verdict on too few reporters. v1 does not add a re-spawn or
  operator-escalation state; acting on an under-strength signal stays with the operator/runtime,
  consistent with the panel's advisory nature. The floor's numeric value is a `/plan` decision.

### Layer A — runtime robustness (cc-workflows verify panel)

- R5. The reconciliation (`execution_spec.py:505-515`) records each runtime-missing verifier and
  recomputes the threshold over reporters (R3), replacing today's silent dilution. The advisory log
  states which verifiers reported, which were missing and why, and the `(n − k)` the verdict was
  computed over.
- R6. Budget exhaustion is already handled by `BUDGET_RIDER` (KD5); the residue R5 must cover is a
  verifier that dies or hangs *without* emitting. Whether converting a *hung* (non-erroring) verifier
  into a recorded missing verdict needs a verifier-level timeout is Q1.

### Layer B — conditional reviewer (team-execution consensus)

- R7. When a reviewer dimension's repo-state precondition is absent (e.g. no architecture docs for the
  ADR-coverage dimension, `architecture-reviewer.md:75-80`), that dimension is **excluded from the
  overall computation** (overall = mean of applicable dimensions), replacing the fabricated N/A→8.0
  default. The exclusion is static (R2): determined before/at review time, never via the runtime
  floor.
- R8. Exclusion is dimension-granular: the reviewer still scores its precondition-independent
  dimensions; only the non-applicable one is dropped. A reviewer whose *entire* lens is non-applicable
  is excluded whole (and logged) — removed from the consensus denominator rather than scored.

### Composition and safety

- R9. A statically-excluded member and a runtime-missing member carry distinct causes (R1) and run on
  distinct paths (R2 vs R3); they are never conflated. *(This is the corrected form of the original
  single-mechanism framing.)*
- R10. This work changes only the handling of missing / non-applicable members. A panel where every
  member applies and reports behaves exactly as today: `n`, `pass_rule` for present verdicts,
  `VERIFY_N_CAP`, the same-tier rule, and every shipped cost lever are unchanged.
- R11. Every new field/behavior attaches to an existing surface with a real producer and consumer —
  the reconciliation and its log (Layer A); the dimension average (Layer B) — with no free-floating
  concept (`LEARNINGS.md:126-136`).

## Key Flows

### F1 — Runtime-missing verifier (Layer A)

- **Trigger:** an `n=3` / majority panel runs; verifier B errors (harness → `null`) or is reclaimed by
  a verifier-level timeout.
- B is recorded `runtime-failure`; the threshold recomputes over `{A, C}`: `majority` ⇒ ⌈2/2⌉ = 2.
- If A and C both refute → refuted. If only A refutes → not refuted, and the log states "1 verifier
  missing (failure); verdict computed over 2/3; floor [met/violated]." *(Contrast today: `refute_count
  = 1 < 2` → silently not refuted, threshold still 2-of-3 — a masked refutation.)*

### F2 — Statically non-applicable dimension (Layer B)

- **Trigger:** architecture-reviewer runs on a repo with no architecture docs
  (`architecture-reviewer.md:75-80`).
- The ADR-coverage dimension is excluded at review time (not scored N/A→8.0); overall = mean of the
  other four dimensions; the unanimous-ACCEPT gate (≥9.0 overall, no dimension < 7.0) is evaluated over
  the four applicable dimensions.

## Acceptance Examples

- AE1. **Covers R3/R5.** `n=3`, threshold 2, one verifier null → recompute over 2 (⌈2/2⌉ = 2); both
  refute → refuted; only one refutes → not refuted *and* the log records "1 verifier missing
  (failure); verdict over 2/3." (Today: silently not refuted under a fixed 2-of-3 threshold.)
- AE2. **Covers R7/R8.** architecture-reviewer on a repo with no architecture docs → the ADR-coverage
  dimension is excluded; overall = mean of the four scored dimensions (not five with a fabricated 8.0);
  each scored dimension still gates at ≥ 7.0.
- AE3. **Covers R2/R9.** A precondition-skipped dimension does NOT push the panel below the runtime
  floor and does NOT trigger escalation — it was excluded at composition, never a "missing reporter."
  This is the observable static-vs-runtime boundary: a skip is not a failure.

## Scope Boundaries

**In scope (v1 — Option 2: robustness + conditional reviewer):**

- The two-kinds contract (R1–R4): static exclusion vs runtime recompute, with a minimum-quorum floor
  as an under-strength marker.
- Layer A (R5–R6): record runtime-missing verifiers and recompute the threshold over reporters in the
  existing reconciliation + advisory log.
- Layer B (R7–R8): exclude a non-applicable dimension from the overall average, replacing the
  fabricated N/A→8.0 default.

**Deferred (not v1):**

- A re-spawn / operator-escalation / `inconclusive` control-flow state — net-new beyond the existing
  advisory log; v1 only makes the log honest.
- The floor's numeric value, and the verifier-level timeout mechanism (Q1).

**Out of scope — already shipped, or scope-locked (both review engines affirmed):**

- A single-saga **cost rubric** (width × wall-clock, TTL batching, panel sizing) — the outcome-level
  frontier-budget + `fork_is_cheap` lever already governs fan-out cost (`operator-choice.md:288-292`).
- A **new concurrency cap** — `VERIFY_N_CAP=7` (`execution-spec.md:53`) plus the harness's own
  `min(16, cores−2)` already bound width.
- **Model homogeneity** — already enforced via same-tier verifiers (`execution-spec.md:48`).
- Changing `pass_rule` semantics for members that *do* report, or the gated/advisory governance split.

## Dependencies / Assumptions

- **Verified (code, saga 0.38.0):** the reconciliation drops a null silently and `log()`-consumes
  `_refuted` over a coarse advisory signal (`execution_spec.py:477-481, 505-515`); the threshold is
  ⌈n/2⌉ fixed from the declared n (`:486,:510`); `BUDGET_RIDER` makes a budget-exhausted verifier
  still emit (`:438,447`; test `tests/test_workflow_emitter.py:771`).
- **Verified:** architecture-reviewer averages five dimensions (`architecture-reviewer.md:34`) and
  scores a fabricated N/A→8.0 for ADR-coverage when no docs exist (`:75-80`); the consensus gate is
  unanimous-ACCEPT ≥ 9.0 / dimension ≥ 7.0 (`consensus-protocol.md:67`); base reviewers always spawn
  (`reviewer-registry.md:9-17`).
- **Verified (codex, repo grep):** no existing implementation or test references "minimum quorum,"
  "missing verdict," or "precondition-skip" outside this doc — so the new behavior must attach to the
  existing reconciliation and dimension-average surfaces (R11), not a new subsystem.
- **Unverified (resolve at plan — Q1):** whether the harness's terminal-error → `null` covers the
  failure modes, or a verifier-level timeout is needed to convert a *hung* verifier into a recorded
  missing verdict.
- **Relationship:** Layer A (cc-workflows refute-N majority) and Layer B (team-execution
  unanimous-ACCEPT) are different reconciliations; the two-kinds contract (R1–R4) is the shared
  principle, but its arithmetic differs per surface — recompute the refute threshold (A) vs exclude
  from the dimension average (B).

## Outstanding Questions

**Resolve before planning:**

- Q1. **Verifier-level liveness.** The harness resolves an *errored* verifier to `null`, but a *hung*
  (slow, non-erroring) verifier blocks the panel's `parallel([...])`. Does Layer A require a
  verifier-level timeout (a per-verifier analog of the R31 leaf heartbeat,
  `operator-choice.md:284-286`) to turn a hang into a recorded missing verdict, or does it rely only
  on terminal-error → `null`? This bounds what R5/R6 cover and is the first `/plan` task.

**Deferred to planning:**

- The minimum-quorum floor value and whether it scales with `n` (R3/R4).
- The exact representation of an excluded dimension in a reviewer's structured output, and of a
  recorded missing verifier in the advisory log (R5, R7).
- Whether the advisory-log format change needs a downstream consumer update (R11).

## Sources

- `docs/ideation/2026-06-26-vecu-port-seeds-ideation.md:38-39,313` — R7/A7 survivor framing and the
  "scope to be constrained in brainstorm — full bundle likely more than wanted" flag.
- `plugins/saga/scripts/execution_spec.py:438,447` (BUDGET_RIDER), `:477-481` (advisory coarse panel),
  `:486,:510` (threshold = ⌈n/2⌉ of declared n), `:505-515` (reconciliation: `v && v.refuted` silent
  drop + `log()` consumer) — the Layer A surface and the verified premise.
- `plugins/saga/references/execution-spec.md:44-61` (verify block contract), `:48` (same-tier
  verifiers), `:53` (`VERIFY_N_CAP=7`), `:86-89` (fan-out target reconciliation — shipped, distinct
  from verdict-drop).
- `plugins/saga/references/operator-choice.md:81-95` (gated vs advisory), `:284-286` (R31 leaf
  liveness), `:288-292` (outcome-level cost levers — shipped, out of scope).
- `plugins/team-execution/agents/architecture-reviewer.md:34` (overall = average of 5 dimensions),
  `:75-80` (N/A→8.0 default when no architecture docs) — the Layer B surface.
- `plugins/team-execution/skills/team-execution/references/reviewer-registry.md:9-17` (base reviewers);
  `consensus-protocol.md:67` (unanimous-ACCEPT gate).
- `tests/test_workflow_emitter.py:771` — `test_haiku_verify_panel_carries_budget_rider` (BUDGET_RIDER
  is real and tested).
- `docs/engineering-journal/LEARNINGS.md:126-136` — dead-wiring rule (a new field needs a real producer
  and a real spawned consumer) — the bar KD6/R11 must clear.
