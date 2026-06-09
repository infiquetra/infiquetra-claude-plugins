# Saga Scenarios

Use scenarios when the user's situation is clearer than the command name.

| ID | Starting statement | Command | Effect | Stop condition | Next route |
|----|--------------------|---------|--------|----------------|------------|
| vague-idea | I have a rough idea but do not know the frame. | `/office-hours` | Names the frame and routes to the next thinking command. | The real problem and key assumptions are nameable. | `/ideate` or `/brainstorm` |
| chosen-idea | We picked this idea; now shape it. | `/brainstorm` | Writes requirements-ready context under `docs/brainstorms/`. | Requirements and acceptance examples are clear. | `/plan` |
| vague-what | Build something like this, but the WHAT is fuzzy. | `/spec` | Writes a precise WHAT spec under `docs/specs/`. | Scope, MVP, non-goals, and failure modes are pinned. | `/plan` or `/handoff` |
| requirements-ready-handoff | This requirements doc should become work for a team. | `/handoff` | Produces a handoff envelope for mission-control. | Source, maturity, target repo, target team, and issue type are clear. | `mission-control` |
| plan-review | This plan looks ready; check it before build. | `/doc-review` | Writes readiness findings and applies safe fixes. | No unresolved P0/P1 findings or override is recorded. | `/work` |
| pr-boundary | The branch is built and needs PR readiness. | `/code-review` | Writes a structured code review and gate verdict. | No unresolved P0/P1 findings and review is fresh. | PR via `/work` |
| post-merge-qa | This merged; prove it actually works. | `/qa` | Writes acceptance evidence and a ship verdict. | Verdict is ship or ship-with-deferred. | `/retro` or `/handoff` |
| qa-failure | QA failed and we need the right repair path. | `/qa` | Classifies severity and routes by merge state. | Failure is classified as pre-merge repair, post-merge defect, or root-cause investigation. | `/work`, `/handoff`, or `/investigate` |
| root-cause-investigation | Why is this failing? | `/investigate` | Writes a debug report with causal chain and evidence. | Root cause is explained with no causal gaps. | `/work`, `/handoff`, or `/brainstorm` |
| metric-optimization | Make this workflow faster and cheaper. | `/optimize` | Runs bounded experiments against a metric. | Target is hit, budget is spent, or a winning change is selected. | `/work` |
| strategy-refresh | The repo direction or metrics need updating. | `/strategy` | Updates `STRATEGY.md` through interview and pushback. | Direction, metrics, and tracks are coherent. | `/ideate`, `/brainstorm`, or `/plan` |
| cross-team-handoff | Another team should pick this up. | `/handoff` | Builds a self-contained envelope for mission-control issue preparation. | Recipient can act without Saga context. | `mission-control` |
| cold-resume | Reconstruct where this work stopped. | `/resume` | Reads full saga/PR/doc context and writes a re-entry tick. | Next owning command is unambiguous. | `/work` or `/handoff` |
| retro-learning | This is finished; capture what we learned. | `/retro` | Records durable learning or proposed lifecycle improvement. | Learning is journaled or a gated improvement proposal exists. | terminal or `/handoff` |

## Adjacent Choice Notes

`/office-hours` finds the frame; `/ideate` generates options once a frame is usable.

`/ideate` creates and critiques many candidates; `/brainstorm` deepens one chosen candidate into requirements.

`/brainstorm` explores requirements and approaches; `/spec` interrogates an ambiguous WHAT until it is precise.

`/plan` writes implementation units and decisions; `/doc-review` checks whether that plan is safe to execute.

`/qa` gates a shipped or merge-bound change; `/optimize` loops toward a metric target.

`/strategy` records direction; `/founder-review` challenges direction, ambition, and scope.

`/loop` routes by current state; `/resume` reconstructs a confusing or cold thread in depth.
