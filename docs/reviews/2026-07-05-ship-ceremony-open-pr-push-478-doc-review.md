# Doc-review — ship_ceremony.py open_pr push fix (#478)

- **Target:** `docs/plans/2026-07-05-ship-ceremony-open-pr-push-478-plan.md`
- **Reviewed revision:** working tree (plan authored this session; saga `issue-478`, plan phase)
- **Classification:** plan artifact (`docs/plans/`; `origin:`, `Implementation Units`, `Key Technical Decisions`, `U1` all present) — readiness-skeptic pass, no formal SDLC rubric engine
- **Blocked status:** not blocked
- **Linked issue / plan:** [#478](https://github.com/infiquetra/infiquetra-claude-plugins/issues/478) · plan above · DECISIONS `{#ship-ceremony-open-pr-push-478}`

## Readiness summary

Ready to drive implementation. Every `path:line` citation was verified against source, the
load-bearing scope decision (don't push at `merge`) is grounded in the consumer's own contract,
and the single new test scenario is sound against the actual `ceremony_repo`/`FakeGh` fixture
mechanics. No findings survive.

## Applied fixes

None — no safe fix was warranted.

## Findings by priority

| Priority | Finding | Status |
|---|---|---|
| — | None | — |

## Verification performed

- `_do_merge` is `gh pr merge <N> --squash` with **no `--auto`** (`ship_ceremony.py:293`) —
  confirms KTD2's claim that a merge-time push would reset CI to pending and then fail the merge.
- `/work` round-N loop re-pushes on `CHANGES_REQUESTED` and not-mergeable
  (`work/references/pr-continuation-loop.md:33,35`); staleness gate re-runs `/code-review` on
  commits-since-reviewed-SHA (`:36`) — confirms the only unpushed window is `start()`→`open_pr`.
- `_do_commit` push argv is `["git","push","-u","origin",<branch>]` (`ship_ceremony.py:241`);
  extracting `_push_branch` keeps it identical, so `test_transition_failure_does_not_advance_state`'s
  `fail_prefix=["git","push","-u","origin"]` still matches (KTD1 behavior-preservation).
- Fixture mechanics: `ceremony_repo` never pushes the feature branch; `start()` is the first push,
  so `origin/feat/pf-throwaway-345` exists only after `start()`, and a subsequent local commit
  leaves the remote-tracking ref stale — exactly the pre-fix "behind HEAD" state the U1 test asserts.
- Version literal `0.54.2` at `tests/test_saga_plugin.py:48` — U2's `0.54.3` bump lands there.

## Residual risk from limited evidence

Low. The one nuance not exhaustively traced: a *proactive* code-review fix that makes a review
stale without a formal `CHANGES_REQUESTED` round (`pr-continuation-loop.md:36`) routes through
"re-run `/code-review`", which does not itself name a re-push. This does not change KTD2 — a
merge-time push is the wrong remedy for that edge regardless (it breaks CI gating); ensuring
proactive commits are pushed is a `/work` concern, not the ceremony's.
