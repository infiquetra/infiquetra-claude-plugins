# Issue #394 Second-Opinion Triggers Work Session

Date: 2026-07-10
Branch: `work/394-second-opinion-triggers`
Plan: `docs/plans/2026-07-10-issue-394-second-opinion-triggers-plan.md`
Plan review: `docs/reviews/2026-07-10-issue-394-second-opinion-triggers-plan-review.md`
U1 checkpoint: `docs/work-sessions/2026-07-10-issue-394-second-opinion-u1.md`

## Outcome

Implemented all five units of issue #394 as the root-owned inline Codex DAG. U1 landed separately as
`98ce9b7`; this session records the completed U2/U3/U4 frontier and U5 release closure. No external
wrapper, issue, board, PR, merge, or deployment mutation occurred.

## Completed Units

### U2 — `/work` repeated-failure trigger

- Added `saga.work-second-opinion.v1`, an atomic private sidecar beside a Markdown work-session.
- Records bounded completed fix/test attempts, normalizes repo-relative pytest targets, and emits one exact
  operator-confirmed offer on a target-specific three-fix streak.
- A pass resets all targets; a missing target resets and expires only that target's unresolved offer; reruns
  are idempotent and cannot advance a streak. `none` suppresses automatic offers; `offload` cannot change
  the trigger into offload.
- Persists accepted request identity before dispatch and writes terminal external outcomes back as
  `unavailable`, preventing a resume from replaying a wrapper call.

### U3 — `/code-review` point-out

- Added a Stage-A-after-numbering `#N` point-out contract with human-confirmed and Claude-prompted paths.
- Programmatic/report-only output adds a typed `state=recommended` block and remains prompt-free and
  dispatch-free through the existing `Review complete` terminator.
- Added the optional native finding projection and separate Claude adjudication contract. Only final
  Claude severity/status and `pre_existing` remain verdict inputs.

### U4 — `/doc-review` point-out

- Added deterministic `D1..Dn` ordering by priority, normalized source anchor, and title for one reviewed
  document revision.
- Reused U3's exact optional projection while retaining doc-review's native P0-P3 artifact and safe-fix
  semantics; no review-schema migration occurred.

### U5 — release closure

- Bumped Saga from `0.75.21` to `0.75.22` across plugin metadata, marketplace, changelog, and contract test.
- Updated the #394 journal decision from plan-ready to shipped status.

## Review Remediation

The required fresh-context U2-U4 review found and verified fixes for three gaps:

- stale offered prompts could survive a target reset;
- a terminal dispatch failure could remain `accepted` in the work sidecar; and
- pre-acceptance recommended/declined projections could expose fabricated request identities.

The final re-review found no P0-P3 findings. The fixes are covered by reset, terminal-failure/replay, and
state-specific projection regressions.

## Checks

- Focused U2/U3/U4 matrix: 99 passed
  - `tests/test_work_second_opinion.py`
  - `tests/test_review_second_opinion.py`
  - `tests/test_saga_plugin.py`
  - `tests/test_saga_doc_formatting.py`
- Ruff check and format over changed code/tests
- Mypy on `plugins/saga/scripts/second_opinion.py`
- Bandit on `plugins/saga/scripts/second_opinion.py`
- Marketplace sync and release-surface parity/diff checks
- Full repository suite: 3,080 collected tests passed (one existing skip)
- Repository Ruff check and format: passed (299 files formatted)
- Mypy over `plugins/`: passed
- Plugin validator completed with its existing no-plugin-files warning; it returned success

## Next Step

Run the full repository quality and release matrix, then run the `/code-review` gate against the completed
implementation before any PR-open offer.
