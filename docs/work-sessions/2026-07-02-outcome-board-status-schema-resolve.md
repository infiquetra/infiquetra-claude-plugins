---
title: Fix /outcome hardcoded board status — schema-resolve instead of "In Progress"
status: pr-ready
date: 2026-07-02
issue_ref: infiquetra/infiquetra-claude-plugins#326
plan_path: docs/plans/2026-07-02-outcome-board-status-schema-resolve-plan.md
---

# Work session — #326 schema-resolve /outcome board status

Both plan units shipped on `fix/outcome-board-status-326`; the fix is tested against the real
schema, no regressions across the repo test suite.

## Built (by U-ID)

**U1** (`5eb9257`) — schema-resolved status in `_candidate_ops` + project threading.

- `plugins/saga/scripts/outcome_board_sync.py`: added `_default_schema_path()` (module-file-relative
  default) and `_resolve_status_map(schema_path, project)` (reads
  `saga_lifecycle.phase_board_map`, `ready` via the `review` row, `dispatched` via the `work` row).
  `_candidate_ops` now takes `status_map` and looks up the resolved value instead of the
  `"In Progress"` literal. `reconcile_board` gained `project: str = "operations"` and
  `schema_path: Path | None = None`; resolution is lazy (attempted once per call, only when a leaf
  is actually `ready`/`dispatched`) and a failure produces a `{status: "failed"}` record with no
  ledger key (retryable) while the coalesced progress comment still proceeds.
- `plugins/saga/scripts/outcome.py`: `advance()` gained `project: str = "operations"`, threaded to
  both `_default_board_writer(repo_root, project=project)` and `reconcile_board(..., project=project)`
  — one source of the target board for both consumers.
- `tests/test_outcome_board_sync.py`: corrected AE1 (`"In Progress"` → `"Ready"`), added a
  parametrized per-project test (operations/asgard `dispatched` → `Active`; campps `dispatched` →
  `In Progress`; campps `ready` → `Committed`), a no-hardcoded-literal source guard, three
  schema-resolution-failure tests (missing file, unknown project, retry-succeeds-after), a
  lazy-resolution guard (a done-only leaf never touches a bogus schema path), and fixed the
  `_candidate_ops` direct-call signature in the pre-existing negative-terminals regression test.

**U2** (`3fcf4a1`) — release surfaces + journal.

- `plugins/saga/.claude-plugin/plugin.json` and `.claude-plugin/marketplace.json`: 0.49.0 → 0.49.1.
- `plugins/saga/CHANGELOG.md`: entry naming the fix and the campps `ready → "Committed"` behavior
  change explicitly.
- `tests/test_saga_plugin.py:48`: version-parity literal bumped to match.
- `docs/engineering-journal/DECISIONS.md`: KTD entry `{#outcome-board-status-schema-resolve-326}`
  (written during `/plan`, confirmed unchanged by execution).

## Key decisions

Per the plan's KTD1-4 (schema-resolve over a literal swap; `ready`→review row, `dispatched`→work
row; module-file-relative default `schema_path` with lazy resolution so existing test call sites
needed no threading edits; fail-loud + retryable resolution failure that doesn't block the
coalesced comment). No deviations from the doc-reviewed plan during execution.

**Review-response** (`b3911f3`) — closed the /code-review gaps (see below).

- `tests/test_outcome_board_sync.py`: added the `advance(project=...)` real-entrypoint integration
  test (asgard/campps, dispatched-state — a ready leaf is dispatched within the same `advance()`
  tick before board-sync runs, so that's the naturally-reached path), a `_default_board_writer`
  non-default-project unit test, the `asgard`+`ready` matrix cell, three corrupt-schema edge-case
  tests (malformed JSON, missing `saga_lifecycle`/`phase_board_map` keys, empty status list), and
  strengthened the unknown-project failure test to assert the full failed-record shape.

## Files modified

`plugins/saga/scripts/outcome_board_sync.py` | `plugins/saga/scripts/outcome.py` |
`tests/test_outcome_board_sync.py` | `plugins/saga/.claude-plugin/plugin.json` |
`.claude-plugin/marketplace.json` | `plugins/saga/CHANGELOG.md` | `tests/test_saga_plugin.py` |
`docs/engineering-journal/DECISIONS.md`

## Checks run

- `uv run pytest tests/test_outcome_board_sync.py -v` — 36 passed (final; 99% module coverage, one
  pre-existing unrelated uncovered line).
- `uv run pytest tests/ -q` (full repo suite, post-review-response) — 1635 passed.
- `uv run ruff check` / `uv run mypy plugins/ scripts/ tests/ --ignore-missing-imports` — clean on
  all touched files, both before and after the review-response commit.

## Code review

`/code-review` ran programmatically (3 lenses: correctness+reliability, security+maintainability,
testing scenario-completeness) against `REVIEWED_SHA=3fcf4a1`. No P0 correctness/security defects.
One P1 (no test proved `project` threading through the real `advance()` entrypoint for a
non-default project) plus three P2 test-coverage gaps — all four fixed in `b3911f3`. Three P3s
recorded as deferred/advisory (a latent, currently-unreachable `"note"`-key edge case in
`_resolve_status_map`, flagged independently by two lenses; the plan's own documented
`--project`-CLI-flag scope boundary; a narrow test-robustness nit). Re-verified clean at
`REVIEWED_SHA=b3911f3` — commits since: `git rev-list b3911f3..HEAD --count` = 0, not stale.
Durable artifact: `docs/code-reviews/2026-07-03-fix-outcome-board-status-326-code-review.md`.

## Next step

Offer PR-open + reviewer request under confirmation (clean gate at `b3911f3`).
