---
title: Create-Prepared Partial GraphQL Error Defect Plan
type: fix
status: active
date: 2026-06-28
origin: docs/brainstorms/2026-06-27-create-prepared-partial-graphql-error-defect.md
---

# Create-Prepared Partial GraphQL Error Defect Plan

## Summary

Fix issue #280 by removing the speculative GraphQL branch that makes `issue create-prepared` die after creating an issue but before board-add and Status assignment.

The plan uses GitHub's `issueOrPullRequest(number:)` union resolver, keeps shared GraphQL error handling strict, and adds a resumable post-create guard so a genuine failure after issue creation can be retried without creating a duplicate issue.

---

## Problem Frame

`mission-control issue create-prepared` creates the GitHub issue, then calls `board_add`, then sets Status (`plugins/mission-control/scripts/sdlc_manager.py:3984`). The failing path is reproducible across four observed issue creations and is already captured in the requirements source (`docs/brainstorms/2026-06-27-create-prepared-partial-graphql-error-defect.md:46`).

The root cause is narrow but operationally expensive: `board_add` resolves node identity with a query that asks for both `issue(number:)` and `pullRequest(number:)` (`plugins/mission-control/scripts/sdlc_manager.py:707`). For an issue, the PR branch can emit a GraphQL `NOT_FOUND` while the issue data is present; `_gh` raises on the non-zero `gh api graphql` exit and `_graphql` remains strict on `errors` (`plugins/mission-control/scripts/sdlc_manager.py:617`, `plugins/mission-control/scripts/sdlc_manager.py:649`).

---

## Requirements

- R1. `board_add` resolves issue and PR content nodes through `issueOrPullRequest(number:)`, using inline fragments, with no speculative `pullRequest` lookup for issue numbers.
- R2. `QUERY_GET_ITEM_LABELS` is converted to the same union shape so label-field sync cannot reintroduce the partial `NOT_FOUND` path.
- R3. Shared `_graphql` and `_gh` strictness remains unchanged for the primary fix.
- R4. Partially failed mutations still fail loudly; no implementation may return success merely because the GraphQL envelope has non-null `data`.
- R5. `issue create-prepared` completes issue creation, board-add, and Status assignment with zero manual recovery for those two post-create steps.
- R6. A genuine failure after issue creation reports the created issue URL/number and the remaining post-create steps. It must not auto-delete the issue.
- R7. Re-running `issue create-prepared` against a post-create failure resumes from sidecar state and does not call `_create_github_issue` again.
- R8. Regression tests drive the real `_gh`/`GhApiError.stdout` mechanism or the fixed union-success path, not only the dead direct `_graphql` envelope path.
- R9. Negative tests cover `data: null` plus errors, field-level fatal errors such as `repository: null`, empty or non-JSON exception stdout, and partial mutation failure.
- R10. PR-direction symmetry stays covered: a number that is a PR resolves to a PR node through the union resolver.
- R11. Mission-control release surfaces stay coherent for the behavior fix: plugin metadata, marketplace metadata, changelog, and drift tests agree.

---

## Key Technical Decisions

KTD1. Use `issueOrPullRequest(number:)` as the primary resolver: it eliminates the spurious 404 before the error path, matches the live probe in the source doc, and avoids widening shared error handling.

KTD2. Keep `_graphql` strict: the same helper protects mutation call sites at `plugins/mission-control/scripts/sdlc_manager.py:1043`, `plugins/mission-control/scripts/sdlc_manager.py:1128`, `plugins/mission-control/scripts/sdlc_manager.py:1170`, `plugins/mission-control/scripts/sdlc_manager.py:1340`, and `plugins/mission-control/scripts/sdlc_manager.py:2199`.

KTD3. Use inline fragments for the union fields: `issueOrPullRequest` cannot be treated as the old `issue`/`pullRequest` object pair, so response parsing should consume one resolved node with a `__typename`.

KTD4. Make the post-create boundary a resumable state transition: persist created issue identity before board-add and Status, then finalize the draft only after both post-create steps are complete.

KTD5. Do not parse command output to infer post-create success: create-prepared needs explicit success/failure from the board-add and Status helpers, or a strict internal helper, so failures are not hidden behind human-oriented text.

KTD6. Release as a mission-control patch: the defect fix changes user-facing behavior but is backward-compatible, so the expected version move is `2.3.0` to `2.3.1`.

---

## Implementation Units

### U1. Replace dual-branch GraphQL resolvers

Make the content-node and label resolvers ask GitHub for one union node instead of two mutually exclusive branches.

**Goal:**

Eliminate the partial `NOT_FOUND` response in both resolver queries while preserving issue and PR support.

**Requirements:**

R1, R2, R3, R10.

**Dependencies:**

None.

**Files:**

`plugins/mission-control/scripts/sdlc_manager.py`

`plugins/mission-control/skills/board/references/graphql-queries.md`

`plugins/mission-control/tests/test_graphql_issue_resolution.py`

`plugins/mission-control/tests/test_board_add_multi_project.py`

**Approach:**

Update `QUERY_GET_ITEM_NODE_ID` and `QUERY_GET_ITEM_LABELS` to use `repository.issueOrPullRequest(number:)` with `... on Issue` and `... on PullRequest` fragments. Adjust `board_add` parsing at `plugins/mission-control/scripts/sdlc_manager.py:1032` to read a single node rather than `repo_data.get("issue") or repo_data.get("pullRequest")`.

Keep current CLI-facing `board_add` behavior for explicit multi-project membership. Existing tests in `plugins/mission-control/tests/test_board_add_multi_project.py` already assert one node lookup and multiple add mutations, so update their fixtures to the union response shape rather than weakening the behavior.

**Edge cases:**

Issue number resolves to `Issue`; PR number resolves to `PullRequest`; repository exists but union node is null; repository itself is null or missing.

**Error / failure paths:**

Fatal GraphQL errors still raise through `_gh` or `_graphql`. A missing union node should fail with the existing "Could not find issue/PR" operator message rather than a Python `KeyError`.

**Integration scenarios:**

`board_add` still adds one content node to one or more configured projects. Label-field sync still reads labels for issues and PRs through the same resolver family.

**Test scenarios:**

Add a new resolver-focused test file that patches `_gh` or `_graphql` at the module boundary and proves issue and PR union fixtures return the expected node. Update the board-add tests so their node fixture is `{"repository": {"issueOrPullRequest": {"__typename": "Issue", "id": ...}}}`.

**Verification:**

`uv run pytest plugins/mission-control/tests/test_graphql_issue_resolution.py plugins/mission-control/tests/test_board_add_multi_project.py`

### U2. Pin strict GraphQL failure behavior

Prove the fix did not turn real GraphQL failures into silent success.

**Goal:**

Protect the shared `_graphql` mutation surface while adding regression coverage for the original partial-error shape.

**Requirements:**

R3, R4, R8, R9.

**Dependencies:**

U1.

**Files:**

`plugins/mission-control/scripts/sdlc_manager.py`

`plugins/mission-control/tests/test_graphql_issue_resolution.py`

`plugins/mission-control/tests/test_typed_exceptions.py`

**Approach:**

Do not add blanket partial-data tolerance to `_graphql`. If an implementation needs a small parsing helper for union nodes, keep it local to read resolvers and do not add an `allow_partial` path unless the implementation can prove every mutation remains outside it.

The regression should model the live mechanism from the source doc: `gh api graphql` exits non-zero and `_gh` raises `GhApiError` carrying usable stdout. Post-fix, the main happy path should avoid that shape by using the union query and returning a normal zero-exit payload.

**Edge cases:**

Empty stdout; non-JSON stdout; `data` is null; `data.repository` is null; target node is null; GraphQL response contains a partial mutation payload with errors.

**Error / failure paths:**

The original exception must be re-raised when stdout is empty or malformed. `RuntimeError("GraphQL errors: ...")` remains valid for direct `_graphql` error envelopes.

**Integration scenarios:**

`flow_set_field` and label-field sync continue to rely on `_graphql` failing on mutation and field errors. The test suite should include at least one mutation-shaped payload where the intended mutation payload is null and `errors` is present.

**Test scenarios:**

Test `GhApiError(stdout=<partial resolver envelope>)` where an old dual-branch envelope is present only as regression documentation. Test that fatal data-null and repository-null envelopes raise. Test that a mutation envelope with non-null outer `data` but null intended payload raises.

**Verification:**

`uv run pytest plugins/mission-control/tests/test_graphql_issue_resolution.py plugins/mission-control/tests/test_typed_exceptions.py`

### U3. Add resumable post-create guard

Make create-prepared recoverable when an issue exists but board-add or Status has not completed.

**Goal:**

Ensure a failure after `_create_github_issue` leaves durable sidecar state that lets the next run finish board-add and Status without creating a second GitHub issue.

**Requirements:**

R5, R6, R7, R9.

**Dependencies:**

U1, U2.

**Files:**

`plugins/mission-control/scripts/sdlc_manager.py`

`plugins/mission-control/tests/test_issue_create_prepared.py`

**Approach:**

Persist the created issue URL and number immediately after `_create_github_issue`, before invoking `board_add` or `flow_set_field`. Use a sidecar state such as `post_create_pending` with a `remaining_steps` list, then transition to `created` only after board-add and Status both complete.

On entry, if the sidecar already has a created issue number in a pending post-create state, skip `_create_github_issue` and resume the remaining post-create steps. For create-prepared's internal path, expose post-create failures as exceptions or structured results rather than human text, so the command can stop loudly and keep accurate remaining-step state.

`board_add` currently catches per-project add failures and appends human-readable text, so `issue_create_prepared` should call a strict internal helper or structured result path rather than parsing CLI output. On resume, use the existing project item lookup pattern that `flow_set_field` already relies on to verify whether a board membership exists before deciding which remaining steps to run.

**Edge cases:**

Approved draft with no created issue proceeds normally; pending sidecar with issue number resumes; pending sidecar with missing URL or number fails before mutation; rerun after board-add succeeded but Status failed does not create another issue; rerun after project membership already exists treats verified membership as satisfied.

**Error / failure paths:**

Network failure during node resolution, true not-found, project add failure, field option lookup failure, and Status mutation failure all leave the issue URL/number in sidecar state and print the remaining manual or resumable steps. No path auto-deletes the created issue.

**Integration scenarios:**

`issue_create_prepared` should still respect readiness and approval gates before any mutation. Mapping-PR stop and mapping override flows keep their current behavior; only the post-create segment becomes resumable.

**Test scenarios:**

Extend `test_issue_create_prepared.py` with a failure after `_create_github_issue` where `board_add` raises, asserting sidecar state is pending, the created number is recorded, `_append_created_issue_to_draft` has enough information for the operator, and the next run skips `_create_github_issue` while calling board-add and Status. Add a second test where Status fails after board-add and the rerun completes without another create call.

Add a resume test where board membership is already present but Status is still pending, proving the retry verifies existing membership instead of blindly adding another project item.

**Verification:**

`uv run pytest plugins/mission-control/tests/test_issue_create_prepared.py`

### U4. Update release surfaces and end-to-end proof

Ship the behavior fix as a coherent mission-control patch release with targeted and full validation.

**Goal:**

Keep installed-plugin metadata, marketplace metadata, changelog, tests, and manual dogfood evidence aligned.

**Requirements:**

R5, R11.

**Dependencies:**

U1, U2, U3.

**Files:**

`plugins/mission-control/.claude-plugin/plugin.json`

`.claude-plugin/marketplace.json`

`plugins/mission-control/CHANGELOG.md`

`plugins/mission-control/tests/test_prompt_alignment.py`

`tests/test_release_triad.py`

**Approach:**

Bump mission-control from `2.3.0` to `2.3.1` in plugin metadata and the marketplace entry, then add a changelog entry naming the union resolver and resumable post-create guard. Update version-pinning tests that intentionally assert the current mission-control version.

After unit tests pass, run a throwaway prepared-draft manual test against GitHub: create a draft, approve it, run `issue create-prepared`, and confirm the resulting issue is on the target board with Status set. This manual test is the acceptance proof for the operator-visible failure mode.

**Edge cases:**

Marketplace version matches plugin version; changelog first release heading matches both; prompt alignment test keeps current Operations/CAMPPS wording.

**Error / failure paths:**

If manual dogfood fails after issue creation, the newly added sidecar state should make the failure recoverable and should be captured in the work log rather than manually patched without evidence.

**Integration scenarios:**

The full plugin suite should still pass with coverage and release-triad guards. CI already runs pytest over `tests` and `plugins/*/tests` via `pyproject.toml:83`.

**Test scenarios:**

Targeted metadata tests pass after the version bump. Full suite proves the fix composes with prepared issue creation, board-add membership, typed exceptions, prompt alignment, and release-triad checks.

**Verification:**

`uv run pytest plugins/mission-control/tests/test_graphql_issue_resolution.py plugins/mission-control/tests/test_issue_create_prepared.py plugins/mission-control/tests/test_board_add_multi_project.py plugins/mission-control/tests/test_typed_exceptions.py plugins/mission-control/tests/test_prompt_alignment.py tests/test_release_triad.py`

`uv run pytest`

`uv run ruff check .`

`uv run ruff format --check .`

`uv run mypy plugins/`

`uv run bandit -r plugins/`

---

## Scope Boundaries

This plan includes the dual-branch resolver bug, label resolver parity, strict GraphQL failure tests, and the fail-loud/resumable guard around create-prepared's post-create steps.

Deferred to follow-up work: optional scoped partial-tolerance for future read resolvers, if future query patterns justify it.

Out of scope: Objective auto-set, title recovery, `deploy-templates` 404s, broad `_graphql` partial-data tolerance, and auto-deleting created issues after post-create failure.

---

## Risks & Dependencies

| Risk | Impact | Mitigation |
|------|--------|------------|
| Union query shape is wrong | The core fix still fails at runtime | Use inline fragments and pin issue plus PR fixtures before manual dogfood. |
| Resumability creates duplicate board membership | Rerun repairs issue but adds board noise | Verify membership before retry or treat already-on-project as satisfied only after reading project items. |
| Text-only post-create helpers hide failures | create-prepared records success after a failed add or Status step | Add a strict helper or structured result path for create-prepared and keep human text as CLI presentation only. |
| Strict mutation failures are accidentally weakened | Failed board-add or Status appears successful | Keep `_graphql` strict and add mutation-shaped negative tests. |
| Sidecar pending state traps a draft | Operator cannot complete or restart cleanly | Make pending state explicit, include URL/number/remaining steps, and allow the next run to resume deterministically. |

---

## Sources

- `docs/brainstorms/2026-06-27-create-prepared-partial-graphql-error-defect.md:18` - root-cause summary and union resolver recommendation.
- `docs/brainstorms/2026-06-27-create-prepared-partial-graphql-error-defect.md:118` - KDs carried forward into this plan.
- `docs/reviews/2026-06-27-create-prepared-partial-graphql-error-readiness.md:37` - readiness review convergence on Option B and strict `_graphql`.
- `plugins/mission-control/scripts/sdlc_manager.py:707` - current dual-branch item node query.
- `plugins/mission-control/scripts/sdlc_manager.py:816` - current dual-branch labels query.
- `plugins/mission-control/scripts/sdlc_manager.py:1032` - `board_add` resolves before its per-project try/except.
- `plugins/mission-control/scripts/sdlc_manager.py:1056` - `board_add` currently converts per-project exceptions into text results.
- `plugins/mission-control/scripts/sdlc_manager.py:2183` - `flow_set_field` already verifies project membership through project item lookup.
- `plugins/mission-control/scripts/sdlc_manager.py:3824` - existing draft/sidecar update helpers.
- `plugins/mission-control/scripts/sdlc_manager.py:3984` - create-prepared order creates issue, board-adds, then sets Status.
- `plugins/mission-control/tests/test_issue_create_prepared.py:212` - existing create-prepared success-path test anchor.
- `plugins/mission-control/tests/test_prompt_alignment.py:16` and `tests/test_release_triad.py:1` - release-surface drift guards.
