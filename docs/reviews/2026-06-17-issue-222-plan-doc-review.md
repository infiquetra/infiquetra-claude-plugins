# Issue #222 Plan Doc Review

Date: 2026-06-17

Target: `docs/plans/2026-06-17-mission-control-issue-contract-sync-plan.md`

Reviewed revision: working tree on `main` at `78fe40eeb443` plus the local plan edits from this review.

Issue: https://github.com/infiquetra/infiquetra-claude-plugins/issues/222

Result: ready for `/work` after the safe fix below. No unresolved P0/P1 findings.

## Review Scope

Formal issue-phase rubrics applied:

- `acceptance_criteria_clarity`
- `devils_advocate_issue`
- `spec_fidelity`
- `context_completeness`
- `issue_sizing`
- `prerequisite_mapping`

Readiness-skeptic focus:

- Does the plan close the actual drift named by issue #222?
- Does it respect the source/consumer boundary for generated issue-contract data?
- Does it cover the mutation boundary where prepared drafts become GitHub issues?
- Does it avoid copying issue templates into Saga?

## Findings

| ID | Severity | Status | Finding | Evidence | Resolution |
| --- | --- | --- | --- | --- | --- |
| DR-222-1 | P2 | Resolved | The original plan covered prepare-time validation and compile tests, but did not explicitly include the prepared-create mutation boundary. That left a small regression risk where a draft could compile correctly but fail or lose sidecar/project-field behavior when created. | `plugins/mission-control/tests/test_issue_create_prepared.py:21` already models the full U8 body, and `plugins/mission-control/tests/test_issue_create_prepared.py:212` verifies approval, GitHub creation, board mutation, status mutation, and sidecar update. | Added `plugins/mission-control/tests/test_issue_create_prepared.py` to U2 and U3, plus a U3 integration scenario requiring compiled contract drafts to pass `issue_create_prepared` while preserving mutation and sidecar behavior. |

## Rubric Results

Acceptance criteria clarity: PASS. The plan has observable requirements, executable acceptance expectations, and a verification path per unit.

Devil's advocate issue: PASS. The plan is a single consumer-sync slice, with source-repo schema generation and Saga ownership explicitly bounded.

Spec fidelity: PASS. The plan traces to issue #222 and reflects the current repo state: the old six-header validator claim is partially superseded, while prepared-body compilation, context-aware validation, stale docs, and vendored schema parity remain.

Context completeness: PASS. The plan names the relevant mission-control, Saga, generated-data, tests, and source-repo files. The review fix adds the missing prepared-create test boundary.

Issue sizing: PASS. The unit split is one coherent PR, but broad enough to prevent a cosmetic-only validator patch.

Prerequisite mapping: PASS. The plan identifies `infiquetra-sdlc origin/main` as the source of truth and calls out the dirty sibling checkout risk without requiring mutation there.

## Applied Fix

Updated the plan to require `plugins/mission-control/tests/test_issue_create_prepared.py` in:

- U2 context-aware contract validation file list.
- U3 prepared-body compiler file list.
- U3 integration testing, covering approved prepared draft creation, project-field mutation behavior, and sidecar recording.

## Non-Blocking Risks

- `mission-control issue create` remains a browser-driven `gh issue create --web` flow; it depends on target-repo GitHub issue forms rather than local body compilation. Current `infiquetra-sdlc origin/main` capability template has the generated issue-contract region with `Intent`, `Context library links`, and executable contract fields, so this is acceptable for issue #222, but implementation should not conflate web form deployment with prepared-body compilation.
- The implementation must preserve `validate_card_body(body)` compatibility for body-only callers while adding the context-aware wrapper for prepared issues. Replacing the public function wholesale would risk breaking `flow validate-card` callers that lack issue type and risk.

## Review Decision

Ready for `/work`.

Blocker policy: `/work` is not blocked because there are no unresolved P0/P1 findings. The resolved P2 fix is already applied to the plan artifact.
