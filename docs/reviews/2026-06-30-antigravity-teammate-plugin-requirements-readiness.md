---
date: 2026-06-30
target: docs/brainstorms/2026-06-30-antigravity-teammate-plugin-requirements.md
reviewed_revision: working tree (base HEAD 760ef90)
blocked: false
review_type: requirements-readiness
---

# Antigravity Teammate Plugin Requirements Readiness

## Review Result

The requirements are ready to feed `/plan` after safe in-place fixes. The remaining uncertainty is
properly framed as planning work and harness proof, not unresolved product scope.

| field | value |
|---|---|
| target path | `docs/brainstorms/2026-06-30-antigravity-teammate-plugin-requirements.md` |
| reviewed revision | working tree (base HEAD `760ef90`) |
| blocked status | not blocked |
| review artifact path | `docs/reviews/2026-06-30-antigravity-teammate-plugin-requirements-readiness.md` |
| linked artifact | `docs/ideation/2026-06-30-antigravity-teammate-plugin-ideation.md` |

## Applied Fixes

The safe fixes tighten existing requirements against cited repo evidence; they do not add new product
scope.

| priority | status | fix | evidence |
|---|---|---|---|
| P1 | closed | Tightened R12 so it no longer implies named spawn shape is enough; per-run transcript proof remains mandatory. | `docs/engineering-journal/LEARNINGS.md` records named-spawn Claude-clone fallback and says transcript proof is the only reliable discriminator. |
| P1 | closed | Tightened R19 and AE1 so `auto-if-clean` requires compatible pre-run git state and an explicit verification policy, avoiding vacuous clean applies. | `docs/external-agent-delegation/blueprint.md` requires re-derived git proof and full verification before importing delegated changes. |
| P2 | closed | Tightened R23, assumptions, and outstanding questions so repo patch containment is not misrepresented as whole-machine filesystem containment. | `docs/external-agent-delegation/blueprint.md` says clone/worktree boundaries do not contain writes to sibling repos or global config without an OS sandbox. |
| P3 | closed | Updated the source note for `agy-plugin-fork-decision.md` to mark named/recovery path evidence as historical and to read it beside the newer fallback audit. | `docs/engineering-journal/LEARNINGS.md` supersedes the earlier "named spawn is enough" interpretation. |

## Readiness Summary

The document now gives planning enough stable WHAT decisions: new plugin, write-capable v1,
teammate-first surface, shared envelope, evidence-first return contract, explicit write-set
auto-apply, and required live Claude harness proof.

The idea-phase rubric review passed at readiness level. Problem framing is specific, assumptions are
surfaced, alternatives are captured through the upstream ideation survivor/cut set, and falsification is
anchored in direct wrapper tests plus live Claude transcript audits.

## Remaining Findings By Priority

No unresolved P0 or P1 findings remain. `/plan` is not blocked.

| priority | status | finding | impact |
|---|---|---|---|
| P2 | accepted residual risk | The final plugin directory/name and command namespace are deferred to planning. | This is acceptable for requirements because the repo naming convention is clear, but `/plan` should decide it early before scaffolding release surfaces. |
| P2 | accepted residual risk | The exact Claude Code agent tool constraints and live harness automation are deferred to planning. | This is the central feasibility proof, but the requirements correctly make it a readiness gate rather than pretending it is already solved. |
| P3 | accepted residual risk | Evidence bundle field names and status enum spellings are deferred to planning. | The required concepts are stable enough for planning; exact schema belongs in the implementation plan. |

## Rubric Notes

The idea-phase core rubrics were applied: assumption audit, devil's advocate, internal consistency, and
problem framing. The applicable extras were alternatives explored, binding constraint, falsifiability,
incentive audit, prior art check, and stakeholder coverage.

| rubric | result |
|---|---|
| assumption audit | Pass. Load-bearing assumptions are named in Dependencies / Assumptions and do not masquerade as verified facts. |
| devil's advocate | Pass. The doc keeps the strongest counterarguments visible: raw runner rejection, no read-only-only v1, fallback detection, no static-test-only proof. |
| internal consistency | Pass after safe fixes. Write-capable v1, no auto-apply without explicit boundaries, and transcript-backed provenance now align across sections. |
| problem framing | Pass. The problem is framed as harness misuse, liveness, and false delegation provenance, not generic "better Antigravity." |
| alternatives explored | Pass via source linkage. The ideation doc's rejected ideas and the requirements scope boundaries preserve why the chosen path won. |
| binding constraint | Pass. The binding constraint is the Claude Code to `agy` harness proof, and the doc sequences success around it. |
| falsifiability | Pass. The proof matrix and acceptance examples define concrete ways to fail: fallback-suspected, no-output, out-of-scope mutation, direct Claude solving. |
| incentive audit | Pass. The doc accounts for the orchestrator, operator, teammate agents, wrapper, and external engine incentives, especially Claude's incentive to solve directly. |
| prior art check | Pass. The doc cites upstream `antigravity-cc/agy`, Hermes-adjacent mechanics via the seed, local delegation docs, and adjacent requirements artifacts. |
| stakeholder coverage | Pass. Operator, orchestrator, bridge agents, wrapper, and external engine are named; ops/security concerns are carried through evidence and containment limits. |

## Residual Risk

The review did not execute Claude Code or `agy`. The strongest remaining risk is still empirical:
whether a plugin-packaged `agy-coder` or `agy-reviewer` can be forced or proven to act as a bridge in a
live Claude Code harness. The requirements now make that a blocking proof for implementation readiness
rather than an assumption.
