# Issue #394 Second-Opinion U1 Work Session

Date: 2026-07-10
Branch: `work/394-second-opinion-triggers`
Plan: `docs/plans/2026-07-10-issue-394-second-opinion-triggers-plan.md`
Review: `docs/reviews/2026-07-10-issue-394-second-opinion-triggers-plan-review.md`

## Scope

Complete U1, the shared advisory-only coordinator required before the independent `/work`,
`/code-review`, and `/doc-review` consumers can start. The root owns the inline Codex DAG, Saga state,
integration, and validation; the fresh-context reviewer is read-only and has no lifecycle or Git authority.

## Completed Work

- Added `second_opinion.py`: immutable source/finding/request/claim/adjudication records, canonical bounded
  context, stable route-bound IDs, a metadata-only `0600` atomic claim store, and closed external-opinion
  projection.
- Enforced no-repeat dispatch: only the creator of an atomic `requested` claim may invoke a wrapper. Unknown
  recovery becomes visible unavailable; an ID naming another request digest is a hard error.
- Added conservative pre-resolution sensitive-content detection. Operator marking, credential/secret
  signatures, and private customer/tenant markers force local-only recommendation; with the current registry,
  no resolver or wrapper call occurs.
- Normalized established wrapper statuses at the coordinator boundary. Timeout, halt, empty typed findings,
  malformed/non-object output, oversized output, and gatekeeper-shaped output become nonblocking unavailable
  evidence and retain the replay guard.
- Completed the durable order: idempotent `reconcile` fact, consumer-owned atomic enriched artifact,
  `available` claim, then idempotent `apply` fact. Raw external opinion and Claude rationale remain in the
  consumer artifact, never a run fact. Before-artifact crashes are unavailable; after-artifact recovery
  completes only the missing marker/apply transition without rerunning a wrapper.
- Added additive `role_kind` validation and propagation to advisory evidence and all dispatch paths. Advisory
  reviewer/panel calls use reviewer read-only or no-write wrapper posture; omitted callers retain `worker`.
- Updated the engine-dispatch and trust-boundary references plus the issue decision/plan/review record to
  capture the operational contract and the corrected crash boundary.

## Checks

- `uv run pytest tests/test_review_second_opinion.py tests/test_saga_engine_dispatch.py tests/test_engine_output_trust_boundary.py -q`
  - 152 passed
- `uv run ruff check plugins/saga/scripts/second_opinion.py tests/test_review_second_opinion.py`
  - passed
- `uv run ruff format --check plugins/saga/scripts/second_opinion.py tests/test_review_second_opinion.py`
  - passed
- `uv run mypy plugins/saga/scripts/second_opinion.py`
  - passed
- `uv run bandit plugins/saga/scripts/second_opinion.py`
  - passed
- `uv run bandit plugins/saga/scripts/second_opinion.py plugins/saga/scripts/engine_dispatch.py`
  - no medium/high findings; reports the pre-existing low B101 assertion in `engine_dispatch.py`, unchanged
    from `origin/main`
- `git diff --check`
  - passed

## Review Status

The required native fresh-context review found four U1 P1 gaps: unmarked secret egress, an uncompleted
successful claim, malformed/empty runner output escaping the advisory boundary, and verbose terminal runner
text reaching metadata-only claim storage. All four were fixed. The re-review confirmed no remaining P0-P3
findings, and the focused checks above were rerun.

## Next DAG Frontier

After the root records U1 acceptance, U2 (`/work`), U3 (`/code-review`), and U4 (`/doc-review`) become
eligible. Their shared Markdown/contract files remain root-serialized in the common worktree; U5 waits for
all three consumers and owns release closure.
