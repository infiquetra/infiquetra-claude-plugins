# Document Review — Saga Plan improvement, issue 918 Wave 1

**The plan is sound enough to have driven implementation, and it did — but this review ran after the
fact, so it reports rather than gates.** Two P1 findings remain, neither of which invalidates the work
already built.

## Review-result contract

| Field | Value |
|---|---|
| Target path | `docs/plans/2026-08-30-saga-plan-improvement-918-wave1-plan.md` |
| Reviewed revision | `5ec8ea7682706aa9f06e359c373cfd2032ee6ba9` |
| Classification | Plan document (`docs/plans/` tie-breaker; plan content signals present: `Implementation Units`, `Key Technical Decisions`, `U1`, file lists, test scenarios, verification) |
| Rubric phase run | `issue` — the document is issue-derived, planning issues 922, 923, 924 and 925 |
| Rubrics applied | Core: `acceptance_criteria_clarity`, `devils_advocate_issue`, `spec_fidelity`. Extras: `context_completeness`, `issue_sizing`, `prerequisite_mapping` |
| Blocked status | **Not blocking.** Advisory — implementation is already complete and merged at the reviewed revision |
| Applied fixes | **None.** See the override rationale below |
| Review artifact path | `docs/reviews/doc-review-issue-918-2026-08-30.md` |
| Linked issue | 918, with children 922, 923, 924, 925 |

## Override rationale — why no safe in-place fixes were applied

Safe fixes are on by default and would edit the reviewed document in place. **This document sits at a
frozen revision that an in-flight Saga Code Review is bound to** (`criteria-code-review-5ec8ea76….json`,
scope `bbac725a…5ec8ea76…`). Mutating it mid-review would break that binding, so every fix that would
otherwise have been applied is reported as a finding instead.

## Provenance — this is a mechanism-correction pass

An earlier review of this same document was **hand-authored without invoking this skill.** It produced
a substantive markdown file at a scratchpad path, found eleven majors including the `#808` pin hazard
that would have turned the gate red, and its findings were all dispositioned in the plan's cycle 2
revision. That content is preserved as prior evidence and folded in below; it is not re-derived and not
discarded. What it lacked was the mechanism: no rubric pass, no durable artifact under `docs/reviews/`,
no typed result. This pass supplies those.

## Findings

| # | Priority | Finding | Status |
|---|---|---|---|
| 1 | **P1** | `backend: inline` contradicts how this wave actually executed | Open — needs an operator ruling |
| 2 | **P1** | This review is retroactive and cannot gate what it reviews | Open — process finding, not repairable in the document |
| 3 | P2 | The design record is unverifiable from this repository | Open — accepted risk, worth recording |
| 4 | P2 | Requirement R8 is not pass/fail testable as written | Resolved in implementation, unresolved in the document |
| 5 | P3 | Requirement R6's line anchor is stale at the reviewed revision | Open — cosmetic; the contract itself is guarded |

### 1 — P1. `backend: inline` contradicts the actual execution path

The document's frontmatter declares `backend: inline`. `plugins/saga/references/operator-choice.md:40`
defines `inline` as "The agent does the work itself, single-context / serial."

Wave 1 was executed by **two Qwen 3.8 Max workers in separate worktrees under Herdr**, with units U1
and U2 running **concurrently**. That is neither the agent doing the work itself nor single-context
nor serial.

This matters because the field has a named consumer that trusts it: `plan-sections.md:187-188` states
`/work` "honours it and does not re-offer." A resumption from this plan would be routed inline, which
is not how the work was done. The enum `inline | team-execution | cc-workflows-ultracode` has **no
value** describing external multi-vendor worker dispatch, so this is a gap in the contract rather than
a wrong choice among available options. The finding is sharpened by this run's own unit U1 having made
the field mandatory: the run tightened a contract and then recorded a value for itself that does not
describe what happened.

### 2 — P1. The review is retroactive

A document review exists to gate implementation. All four units are implemented, merged, and green at
the reviewed revision, so nothing this pass finds can prevent what it reviews. The gating work was
done in substance by the hand-authored pass, whose eleven majors were dispositioned before any worker
was dispatched — but that pass produced no typed result and no durable artifact, which is precisely
the defect this pass corrects. Recorded so the run's evidence trail states plainly what ran when.

### 3 — P2. The design record cannot be verified from this repository

The plan names `docs/operations/saga-plan-evidence-package.md` in `infiquetra/infiquetra-agent-operations`
as its discussion authority, and states it is an **uncommitted working file in another repository**.
No reader of this repository can check the plan against its source. The plan is explicit that the
package is discussion authority only and not source authority, which is the right framing, but spec
fidelity remains unverifiable by anyone but its author.

### 4 — P2. Requirement R8 is not pass/fail testable as written

R8 reads: "Plan's phases 0–2 and 4 gain no question, checklist, questionnaire, or fixed sequence." As
an absolute-absence assertion this is untestable, because Phase 1 and Phase 4 already contain the word
"checklist" legitimately today. The implementing worker discovered this at implementation time and
narrowed the pin to the subsection its unit adds, then flagged the choice. The narrowing is sound; the
requirement should have stated the scoping rule rather than leaving a worker to invent it under time
pressure. The `acceptance_criteria_clarity` rubric's test — would an agent and a reviewer reach the
same verdict from the AC text alone? — fails here.

### 5 — P3. Requirement R6's line anchor is stale

R6 cites the marker triple at `plugins/saga/skills/plan/SKILL.md:224-226`. At the reviewed revision it
lives at line 254, a 30-line drift caused by this run's own edits. The plan instructs readers to
re-resolve every line reference, so this is self-aware rather than misleading, and the implementation
pins the marker triple **by content** rather than by line
(`tests/test_plan_artifact_conformance.py:31-33`), so the contract is genuinely guarded. Only the
document's prose is stale.

## Rubric verdicts

**`acceptance_criteria_clarity` — mostly strong, one gap.** Requirements R1 through R33 are numbered
and name observable artifacts, and each unit carries an acceptance mapping tying issue criteria to
steps and tests. R8 is the exception, recorded as finding 4.

**`devils_advocate_issue` — the framing survives scrutiny.** Unit U4 bundles three sub-parts and was
genuinely oversized; it fired its own stop condition, and the operator ruled the emitter-only
boundary. That is the rubric's smallest-useful-slice test being applied and answered rather than
skipped.

**`spec_fidelity` — traceable within this repository, unverifiable outside it.** Every requirement
traces to a named issue criterion, and issue 922's withdrawn criterion 5 is recorded both in the plan
and on the issue. The upstream design record is the gap, recorded as finding 3.

**Extras.** `context_completeness`: strong — preflight findings, per-unit custody, and must-not-touch
lists. `issue_sizing`: exercised and resolved by operator ruling. `prerequisite_mapping`: the unit
order and its dependency reasons are stated explicitly, and the concurrent pair's shared file is named
down to the section.

## Prior evidence folded in

The hand-authored pass's eleven majors are preserved at
`scratchpad/plan-review-918-wave1.md` and are all marked accepted in the plan's own "Review
dispositions — cycle 2" table. The highest-value one — that deleting the six counterfactual
recommendation branches would fail the `#808` pin tests at `tests/test_saga_plugin.py:714` and `:742` —
was independently confirmed from source and is the reason unit U4 rewrote one branch per file instead
of deleting them. None of those findings is reopened here.

## Residual risk from limited evidence

This pass could not verify the plan against its upstream design record, which lives uncommitted in
another repository. It also reviews a document whose implementation is already complete, so the
readiness question it is designed to answer is counterfactual. Both limits are stated rather than
worked around.
