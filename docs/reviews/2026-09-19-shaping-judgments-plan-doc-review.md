# Doc review — the shaping-judgments plan

The plan is ready to drive implementation. Eight evidence-backed fixes were applied in place; three findings remain, none of them blocking.

## Review result

| Field | Value |
|---|---|
| Target | `docs/plans/2026-09-19-shaping-judgments-plan.md` |
| Reviewed revision | working tree, on branch `issue/1037` at base commit `866d3670` |
| Classification | plan (path tie-breaker `docs/plans/`, plus `origin:`, `Implementation Units`, `Key Technical Decisions`, `U1`) |
| Formal SDLC rubric phase | none — the artifact is neither a blueprint, an ADR, an issue, nor a spec, so no idea-phase or issue-phase rubric applies; the readiness-skeptic pass ran alone |
| Blocked | no |
| Findings | 11 raised; 8 fixed in place; 3 remain, all `P2` or `P3` |
| Linked issue | infiquetra/infiquetra-claude-plugins#1037, child of #1019 |
| Review artifact | `docs/reviews/2026-09-19-shaping-judgments-plan-doc-review.md` |
| External reviewer panel | not invoked — opt-in only, and the operator did not ask for one |

## Applied fixes

Each one is supported by the document, the card, or repository source that the plan already cites.

| Key | Priority | Finding | Fix applied |
|---|---|---|---|
| D1 | P1 | Office-hours state was described as "the topic and diagnostic answers", which is dialogue — the fleet-core data rule excludes a session transcript even after redaction | R7 and R19 now name the Phase 2 settled frame as the state, and R7 states the transcript exclusion and its reason |
| D2 | P1 | The critique rubric scores were to cover every dimension at `convergence-and-partnership.md:46-60`, which includes axis spread — a dimension that same reference calls "a list-level concern, not per-idea" | R13 now enumerates the eight per-idea dimensions and excludes axis spread, with the reason |
| D3 | P1 | The eleven judgments were never named, yet U5's guard test asserts each is named in its skill's markdown; an implementer would have invented eleven identifiers | U1 now carries the registry table — name, requirement, owning command and state shape — and states the name is also the subcommand and the `decision_id` suffix |
| D4 | P1 | The card's two acceptance criteria appeared nowhere in the plan | A `Verification` section carries both commands verbatim, notes that only the first makes a live call, and names the repository gate |
| D5 | P2 | The dedupe cap was "a documented request cap" with no number, leaving an implementation choice open | R9 fixes it as one named constant defaulting to 64, derived from ideate's own volume ceiling; KTD2 now refers to that cap instead of describing a second one |
| D6 | P2 | A confident grounding-fit or scope-tier answer could be read as permission to skip a question the skill asks today, which would make an advisory judgment a gate | R11 states explicitly that a confident answer never suppresses an existing ask, and extends the rule to R15 |
| D7 | P2 | The readiness criteria were "one named list" with no list, so the acceptance criterion "one probability per readiness criterion" had nothing to count against | R18 enumerates seven criteria, each mapped to the requirements-section contract |
| D8 | P2 | Neither the initial confidence floor nor the calling convention was pinned | R2 adopts fleet-core's `0.6` default with that file's stated reason; a new R2a says the skills call the module as a shell command |

Two smaller corrections rode along: U1 gained a test scenario for empty state, and U5's regression expectation now names the three guard-test files by path instead of describing them.

## Remaining findings

| Key | Priority | Finding | Status |
|---|---|---|---|
| D9 | P2 | R8 says every call records a verdict, but the plan does not say whether a declined judgment (above the dedupe cap, or an empty state) or a failed call records one. The evaluation harness's denominator depends on the answer | open — a decision for the implementer, recorded rather than invented |
| D10 | P3 | R17 asks for two scores per candidate question and says code orders them, but not how the two combine. The skill's own phrase is "the greatest combination of consequence and uncertainty", which does not name an operation | open — low rework risk, resolvable at implementation |
| D11 | P3 | The plan does not restate the repository's Python standards (type hints, the hundred-character line limit, the eighty-percent coverage floor). They bind regardless | open — the repository gate enforces them, so restating is polish |

## Residual risk from limited evidence

One thing this review could not verify: the plan asserts that issue 1030's release makes the three shaping commands stateless, which is why KTD7 writes no saga tick. That release is not on this branch's base commit, so the claim rests on the card's own non-goal rather than on code read here. If it slips, the only consequence is that these three commands remain tick-writing for other reasons — nothing in this plan adds or removes a tick either way.

Everything else was checked against source on this branch: the fleet-core client's entry point and its `answer_confidence` seam, the verb-registry shape, the data rule, the three skills' phases and line numbers, the brainstorm guard predicates, and saga's version `0.159.3`.
