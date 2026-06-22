---
date: 2026-06-21
target: docs/plans/2026-06-21-plan-work-backend-handoff-plan.md
revision: working tree
classification: plan
reviewer: /doc-review
blocked_for_work: no (0 P0, 0 P1; all findings fixed in place)
source_chain: ideation → requirements → requirements-review → plan (this review)
saga: task-plan-work-backend-handoff
---

# Doc Review: Plan→Work Execution-Backend Handoff (PLAN)

## Readiness summary

The plan is ready to drive implementation. It is well-grounded (every unit anchored to verified `file:line`), correctly dependency-ordered, and each unit is independently landable with concrete test scenarios. Adversarial verification against the code turned up four issues — two correctness/safety gaps (P2) and two precision nits (P3) — all evidence-backed and all **fixed in place**. No P0/P1; `/work` is not blocked.

## Applied fixes

| id | pri | fix | basis |
|---|---|---|---|
| F1 | P2 | U1: `dependency_layers` must treat a fan-out's `pilot` as an implicit barrier edge, else topological layering runs a fan-out in the same parallel wave as its pilot and the R3 gate is lost. Added to U1 approach. | `execution_spec.py` keeps `pilot` (`:131`) and `depends_on` (`:124`) as separate fields; `validate` only checks the pilot *resolves* (`:209-210`), not that it *orders before* the fan-out. |
| F2 | P2 | U3/KTD7: pin the provenance guard to the `save()` path (not the dataclass constructor or `render_envelope`), or the render/parse round-trip at `test_saga_saga.py:1259` (operator_choice ≠ default mode, unsaved) breaks. Added the placement constraint + a regression test scenario. | Verified: `:1259` sets `operator_choice="team-execution"` via render/parse (no save); the `save()`-path test `:1271` uses matching values; the degrade test `:295` pairs a downgrade note — so a `save()`-scoped guard is safe. |
| F3 | P3 | KTD7 reworded: the `operator_choice = (… or mode)` auto-derive (`saga.py:1074-1075`) stays and never conflicts; the guard fires only on an EXPLICIT `mode != operator_choice` pair. | `saga.py:1074-1075` — absent operator_choice resolves to mode (equal), so the original "stops auto-deriving when they conflict" was imprecise. |
| F4 | P3 | U2 integration scenario reworded from "parses (node --check-style)" to substring assertions (a `parallel(` block, N verifier `agent(` calls, tiers). | Existing emitter tests assert substrings (e.g. `"pilot: Upilot"` at `test_workflow_emitter.py:209`), not node execution. |

## Findings

All four findings above were resolved via safe in-place edits. No findings remain open.

## Verifications that PASSED (no finding)

- **KTD consistency** — KTD1 (direct spec authoring) resolves the requirements' deferred "direct vs converter"; KTD6 (`/work` halts, not recompile-down) is consistent with the requirements' KD2; KTD3 bounded-N addresses the rate-limit overcorrection. No internal contradictions.
- **Unit dependency order** — U1→U2; U3 independent; U4 (needs U1/U2); U5 (needs U1/U2/U3); U6 last. Coherent and each independently landable.
- **refute-N expressibility** — a `Unit.verify {n, pass_rule}` renders into the Workflow tool's documented `parallel()` judge-panel idiom (spawn N skeptics, majority-refute); feasible.
- **`/work` launch** — `Workflow({scriptPath})` accepts a file path; re-emitting from the canonical spec (KD3) and running it is feasible; off-host → halt is safe by construction.
- **team_emitter regression** — `verify` is an optional field; an absent field round-trips unchanged, so `tests/test_team_emitter.py` stays green (R5) as long as U1 keeps the default-none path.

## Residual risk from limited evidence

The harness opt-in behavior for `/work` launching the Workflow tool from a saga-recorded choice (no current-turn keyword) remains a runtime question — but the run-or-halt design is safe either way (U5 halts rather than silently substituting), so it is a confirm-during-build item, not a plan defect.

## Links

- Plan (target): `docs/plans/2026-06-21-plan-work-backend-handoff-plan.md`
- Requirements: `docs/brainstorms/2026-06-21-plan-work-backend-handoff-requirements.md`
- Requirements review: `docs/reviews/2026-06-21-plan-work-backend-handoff-doc-review.md`
- Ideation: `docs/ideation/2026-06-21-plan-work-backend-handoff-ideation.md`
