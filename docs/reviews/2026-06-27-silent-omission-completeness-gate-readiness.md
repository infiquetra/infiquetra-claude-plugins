---
date: 2026-06-27
kind: doc-review
target: docs/brainstorms/2026-06-27-silent-omission-completeness-gate-requirements.md
reviewed_revision: working tree (fixes applied on top of commit 5e2a53b)
blocked: false
---

# Readiness Review — Silent-Omission Completeness Gate

## Readiness summary

**READY to drive planning.** No `P0` or `P1` findings remain open. Six `P1`s surfaced by the adversarial
pass were all resolved by evidence-backed in-place fixes; the residual `P2`/`P3` items are deferred-planning
questions (`/plan` resolves them during code design), not blockers.

This review ran codex (`gpt-5.5`, xhigh, read-only with repo access) and agy (`Gemini 3.1 Pro (High)`,
hermetic) as **gated generators under Claude-side verification** — they generated findings, each finding
was checked against the doc or the cited source before adoption. The two engines disagreed on emphasis and
each surfaced distinct findings (no parroting); codex's one codebase-fact claim was verified true against
`execution_spec.py:180` before adoption.

## Applied fixes (12)

All edits are evidence-backed (verified source or internal consistency).

- **Typed-failure model corrected.** v1's base class is `missing-output` (observable), not
  `budget-exhaustion` (a cause not attributable from absence); v1 wires `missing-output` +
  `malformed-output` + `verifier-disagreement`, resolving the R8↔R9 contradiction. (R8, AE1, Key Decision,
  Scope Boundaries)
- **Expectation anchor added.** The detector trips on absence only where output was *expected*
  (schema-bearing agent, fan-out targets, non-empty contract); legitimately-empty leaves and
  `skipped-by-config` validators are not tripped. (Mechanical-detection lead, R1, R12, AE9)
- **`returns` correction.** The output contract already exists as the structured field `Unit.returns`
  (`execution_spec.py:180`); the gap is *enforcement*, not schema. The manifest surface is structured-output
  *keys*, not files. (R5, R6, AE4, Dependencies, Sources)
- **Retry hardened.** "retry with reduced scope" → a bounded retry that re-runs the unit unchanged (never
  shrinks declared outputs) or halts. (F2, R4)
- **Both evaluation models.** F2 trigger now covers the synchronous return *and* the team-execution
  check-at-exit model; added AE8 for missing evidence. (F2, R11, R12, AE8)
- **Unbounded loops closed.** R10 override raises the bound, never removes it. (R10, AE6)
- **Scope clarified.** R9 is scoped to the emitted-workflow path; v1 does not change team-execution's
  existing proceed-best-available cap. (R11, Scope Boundaries)
- **Withhold scoped.** The gate withholds the return *envelope* (blocks dependent launch), not on-disk
  side-effects (that containment is the deferred R14 work). (R4)
- Minor: R3 count source named (fan-out targets); F1 covers-list no longer claims trip-only requirements.

## Findings by priority

| Pri | Finding | Source | Status |
|-----|---------|--------|--------|
| P1 | R8 said only `budget-exhaustion` wired, but R2/R9/R12 trips need more classes in v1 | agy + codex | Fixed |
| P1 | `budget-exhaustion` asserted from absence — cause not observable | codex | Fixed |
| P1 | "absence = trip" false-trips legitimately-empty leaves / `skipped-by-config` validators | claude + codex | Fixed |
| P1 | "retry with reduced scope" forces a semantic re-plan and conflicts with R3/R6 | agy + codex + claude | Fixed |
| P1 | R10 override "loop continues" is unbounded | codex | Fixed |
| P1 | Codebase claim wrong: `returns` is structured (`:180`), not prose-only | codex | Fixed |
| P2 | F2 sync trigger doesn't cover team-execution evidence-absence (async) | agy + codex | Fixed |
| P2 | R4/F2 overclaim — gate withholds the envelope, not on-disk side-effects | agy | Fixed |
| P2 | R9 silently changes team-execution proceed-best-available semantics | codex | Fixed |
| P2 | Output surface ambiguous (structured keys vs files) | claude | Fixed |
| P2 | R3 count source unspecified | claude + agy + codex | Fixed |
| P3 | F1 covers-list included trip-only R2/R3 | agy | Fixed |
| P3 | R11/R12 lacked acceptance examples | codex | Fixed |
| P2 | `--self-test` out-of-band injection mechanism unspecified | claude | Deferred → /plan |
| P2 | bounded-retry budget (the number) unspecified | claude + codex | Deferred → /plan |
| P3 | iterate-to-consensus flag schema/location undefined | agy | Deferred → /plan |

## Residual risk from limited evidence

Low. The three deferred items are genuinely `/plan`'s to resolve (a mechanism and two magic numbers), not
unverified assumptions. The one codebase claim the doc makes that drives design — that `Unit.returns` is a
structured-but-unenforced contract — was verified true at `plugins/saga/scripts/execution_spec.py:180`.
