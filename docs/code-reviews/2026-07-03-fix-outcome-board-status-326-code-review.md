# Code Review — fix/outcome-board-status-326

Clean at the reviewed SHA below — no P0/P1 findings remain. One P1 gap surfaced by the initial
pass was closed in a same-branch follow-up commit; three P3s are recorded as deferred/advisory.

## Review-result contract

**Target:** `fix/outcome-board-status-326` (branch, no PR open yet).

**Base / diff scope:** `git diff 373219a1c052af568dd55877aa2530593e4da5bc..HEAD` (merge-base with
`origin/main`).

**Reviewed revision (final):** `b3911f31995f1a2e31b095ce503616e4ee1df114` — working tree clean at
this SHA.

**Initial-pass revision:** `3fcf4a1d80fd0fb715b44215a34f2a665bf45954` (the P1 below was found
against this SHA and fixed in the immediately following commit).

**Blocked:** no (clean at the final reviewed SHA).

**Linked issue:** infiquetra/infiquetra-claude-plugins#326. **Plan:**
`docs/plans/2026-07-02-outcome-board-status-schema-resolve-plan.md`. **Doc-review:**
`docs/reviews/2026-07-02-outcome-board-status-schema-resolve-review.md`. **Work-session:**
`docs/work-sessions/2026-07-02-outcome-board-status-schema-resolve.md`. **Saga:** `issue-326`.

## Scope check

**CLEAN.** Intent (from commit messages + the plan doc): schema-resolve `/outcome`'s hardcoded
`"In Progress"` board-status literal. Delivered: exactly that — `outcome_board_sync.py`,
`outcome.py`'s `advance()` project-threading, the corresponding test file, and the release
surfaces (`plugin.json`, `marketplace.json`, `CHANGELOG.md`, the version-parity test literal) named
in the plan's U1/U2. No files touched outside the plan's stated scope.

## Plan-completion audit

| Unit | Status | Evidence |
|---|---|---|
| U1 — schema-resolved status + project threading | DONE | `outcome_board_sync.py` (`_default_schema_path`, `_resolve_status_map`, `_candidate_ops`, `reconcile_board`), `outcome.py` `advance()`; 36/36 tests green in `tests/test_outcome_board_sync.py` |
| U2 — release surfaces + journal | DONE | `plugin.json`/`marketplace.json` 0.49.1, `CHANGELOG.md` entry, `tests/test_saga_plugin.py:48` literal bumped, `DECISIONS.md` entry `{#outcome-board-status-schema-resolve-326}` |

## Lenses run

Three lenses, spawned as isolated-worktree read-only agents (the skill's `saga:readonly-verifier`
subagent type is not present in this session's registry — a known, previously-flagged roster gap;
substituted `general-purpose` with explicit read-only instructions plus worktree isolation):

- **Correctness + reliability** — traced the resolution/threading/failure-branch logic against the
  real schema and the real call chain; ran the test suite directly (29/29 at the time, 99% branch
  coverage).
- **Security + maintainability** — traced `project`'s only two uses (dict-key lookup, list-argv
  subprocess arg) for injection surface; verified house-pattern conventions and existing
  broad-except precedent.
- **Testing (scenario completeness)** — audited the four standard categories against the new/changed
  behavior specifically.

## Findings

| # | Severity | File | Issue | Reviewer(s) | Confidence | Route | Status |
|---|---|---|---|---|---|---|---|
| 1 | P1 | `plugins/saga/scripts/outcome.py` / `outcome_board_sync.py` | No test proved `project` threads through the real `advance()` entrypoint for a non-default project (only unit-level `reconcile_board` coverage existed) | testing | 100 | safe_auto → review-fixer | **fixed** (`b3911f3`) |
| 2 | P2 | `tests/test_outcome_board_sync.py` | Missing `asgard`+`ready` matrix cell | testing | 75 | safe_auto → review-fixer | **fixed** (`b3911f3`) |
| 3 | P2 | `tests/test_outcome_board_sync.py` | No edge-case tests for malformed JSON / missing schema keys / empty status list | testing | 75 | safe_auto → review-fixer | **fixed** (`b3911f3`) |
| 4 | P2 | `tests/test_outcome_board_sync.py` | Unknown-project failure test asserted only `status=="failed"`, not the full failed-record shape the missing-file test already proves | testing | 75 | safe_auto → review-fixer | **fixed** (`b3911f3`) |
| 5 | P3 | `plugins/saga/scripts/outcome_board_sync.py:130-146` | `_resolve_status_map` doesn't validate `project` against the schema's real key set — a `project="note"` would silently return a truncated character instead of raising (the schema's `phase_board_map` rows carry a `"note"` commentary key). Not reachable today: no CLI exposes `project`, and no call site ever passes an untrusted value. | correctness+reliability, security+maintainability (cross-reviewer agreement) | 75 | gated_auto → downstream-resolver | deferred |
| 6 | P3 | `plugins/saga/scripts/outcome.py` | `advance`'s CLI subparser exposes no `--project` flag — non-default board targeting only works via direct Python API today. This is the plan's own documented Scope Boundary, not a defect this diff introduced. | correctness+reliability | 100 | advisory → release | informational, matches plan |
| 7 | P3 | `tests/test_outcome_board_sync.py` | The hardcoded-literal source guard is a double-quote-only substring match; a single-quote reintroduction would bypass it. Low real risk given this file's consistent ruff double-quote formatting. | testing | 50 | advisory → downstream-resolver | deferred |

No findings suppressed below the confidence-75 gate other than the two P3s reported at anchor 50
(both route to `advisory`, the schema's stated exception for synthesis-routed-to-advisory
reporting).

## Coverage

- **Suppressed:** none below the reporting threshold beyond the two noted above.
- **Residual risk:** finding #5 (`"note"`-key edge case) and #6 (no `--project` CLI flag yet) are
  intentionally deferred — both require the `project` operator-configurability follow-up the plan
  explicitly scoped out. Finding #7 is a narrow test-robustness nit.
- **Testing:** all four scenario-completeness categories now have direct coverage for the new
  behavior (happy path across all three projects × both `ready`/`dispatched`, corrupt-schema edge
  cases, the fail-loud/retryable error path with full record-shape assertions, and integration
  through both `reconcile_board` directly and the real `advance()` entrypoint).

## Verification

`uv run pytest tests/test_outcome_board_sync.py -v` — 36/36 passed, 99% module branch coverage (one
pre-existing, unrelated uncovered line). `uv run pytest tests/ -q` (full repo suite) — 1635 passed.
`uv run ruff check` / `uv run mypy plugins/ scripts/ tests/ --ignore-missing-imports` — clean on all
touched files.

## Route

Clean at `b3911f3` — recommend **PR-open** next (`/work`'s Phase 5.4).
