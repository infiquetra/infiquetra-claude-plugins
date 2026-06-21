# Doc Review — Saga Tiering & Execution-Mechanism Campaign (requirements)

**Verdict: READY to drive planning.** No P0/P1. Seven P2/P3 findings, all fixed in place against
verified evidence. The campaign frame maps all 15 ideation survivors to R-IDs with clean sequencing;
HOW-level decisions are correctly deferred to `/plan`.

## Review-result contract

| field | value |
|-------|-------|
| target | `docs/brainstorms/2026-06-20-saga-tiering-and-execution-campaign-requirements.md` |
| reviewed revision | working tree atop `main` `56bfec7` (the as-merged doc) |
| classification | requirements (path `docs/brainstorms/` + content signals) |
| rubric engine | not run — requirements docs use the readiness-skeptic pass, not idea/issue/spec rubrics |
| blocked status | **not blocked** (no P0/P1) |
| safe fixes applied | 7 (in place) |
| review artifact | `docs/reviews/2026-06-20-saga-tiering-and-execution-campaign-review.md` |
| upstream | ideation `docs/ideation/2026-06-20-net-new-skills-agents-ideation.md` + `…-execution-backend-representation-ideation.md` |

## Verification performed (verify-before-trusting)

| claim | result |
|-------|--------|
| `saga.py:71` ORCHESTRATION_MODES | ✓ exact |
| `lifecycle_state.py:158` is the `or needs_consensus` hard-force | ✓ line 158 is literally `or needs_consensus` |
| `plan/SKILL.md:253` offer under-sell | ✓ "broad independent fan-out without elevated risk" at :253 |
| `team-execution/SKILL.md:234` `## Team Structure` template | ✓ (3rd match) |
| "zero hooks" in the repo | ✓ no `hooks.json`, no `hooks/` dirs, no hook configs |
| context-fleet-audit workflow + plan paths | ✓ both exist |
| agent tiering count | ✗ **stale** — doc said "35 / ~10 inherit"; actual current tree is **30 agents, 25 pinned, 5 unpinned** |

## Findings (all fixed in place)

| id | pri | finding | fix | status |
|----|-----|---------|-----|--------|
| F1 | P2 | Stale agent count ("35 agent files", "~10 still inherit") — pre-cut figures | Corrected to "30 agents, 5 unpinned" in Problem Frame + Dependencies | fixed |
| F2 | P2 | The S1 drift-guard test lived only in Success Criteria, not as a requirement | Folded into R5 as an explicit, testable clause | fixed |
| F3 | P2 | Cross-cutting release-surface obligation (CLAUDE.md §6 + ideation Thread C) unstated — planning could omit version/CHANGELOG/marketplace/drift-guard updates | Added as a Dependencies/Assumptions bullet binding every epic | fixed |
| F4 | P2 | R2's target agent set was a filter ("still-unpinned survivor agents") — the doc itself preaches enumerate-not-filter (R10) | Enumerated the 5 agents in Dependencies | fixed |
| F5 | P3 | R14 (conditional nudge) had no acceptance example | Added AE6, faithful to R14 | fixed |
| F6 | P3 | Epics 3-4 carry no Key Flows and the omission was unnoted (contract asks for a note) | Added a one-line note (event-triggered guards, non-flow-shaped) | fixed |
| F7 | P3 | R12's sequencing (independent; baseline ideally precedes Epic 1) was unstated | Added a note to R12 | fixed |

## Residual risk

Low. The doc defers R7 (gated/advisory signal-acquisition), R8 (label encoding), R9 (spec location), and
R15 (manifest format) to `/plan` — these are genuine HOW decisions, correctly deferred, not gaps. The one
unverifiable claim is the assumption that the Workflow tool's per-agent `model`/`effort` and `budget` API
are stable; it is a platform assumption outside this repo and is flagged as an assumption, not asserted as
fact.
