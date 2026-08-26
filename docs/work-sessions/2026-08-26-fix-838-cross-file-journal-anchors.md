# Work session — validate cross-file journal fragment citations (#838)

**Saga:** `issue-838` · **Plan:** `docs/plans/2026-08-26-improve-claude-plugins-847-run-plan.md` (Unit U2) ·
**Branch:** `orch/orch-2026-08-26-847-847-g2-838` · **Destination:** PR ·
**Backend:** `inline` (operator-approved in run directive)

## Summary of Changes

Extended `scripts/lint_journal_order.py` to validate cross-file Markdown fragment links (`](FILE.md#anchor)`) among the covered journal set (`LEARNINGS.md`, `DECISIONS.md`, `ARCHIVE.md`, `QUEUED.md`, `README.md`) against both explicit `{#slug}` heading anchors and GitHub-generated Markdown heading anchor slugs. Repaired all 18 broken cross-file citations catalogued in PR #832 across `docs/engineering-journal/`.

### 1. Linter Implementation (`scripts/lint_journal_order.py`)
- Added `_github_slug` and `_heading_slugs` to compute GitHub-compliant anchor slugs from heading lines.
- Updated `_references` to extract both same-file anchor mentions (`{#slug}` / `](#slug)`) and cross-file Markdown fragment links (`](FILE.md#anchor)`).
- Updated `check_anchors` to resolve destination files strictly by path (source-relative and repo-relative) without loose basename fallback.
- Added `docs/engineering-journal/README.md` to `ANCHOR_EXTRA` so that `README.md` heading anchors and fragment links are fully guarded by CI.
- Updated CLI description in `main()` to declare both same-file and cross-file fragment citation checks (#407, #838).

### 2. Broken Citation Repairs across Engineering Journal
- `docs/engineering-journal/ARCHIVE.md`:
  - Added missing heading `### "Anthropic tool schemas reject top-level oneOf outright" (pre-correction of `#toplevel-oneof-schema-dispatch-400`)  {#toplevel-oneof-schema-dispatch-400-v1}` at line 534.
  - Repaired citations to `#investigate-systematic-debugging-engine-shipped` (lines 156, 217, 219) with aligned status phrasing.
  - Repaired citation to `#optimize-engine-rebuild-shipped` (line 195).
  - Repaired citations to `#code-review-defect2-shipped` for Defect 2 closures (lines 248, 255, 261, 263).
  - Repaired citation to `#brainstorm-spec-interrogation-seam-resolved` (line 345).
- `docs/engineering-journal/DECISIONS.md`:
  - Repaired citation to `QUEUED.md#brainstorm-ideate-convergence-bias` (line 7587).
  - Repaired citations to `ARCHIVE.md#investigate-systematic-debugging-engine-shipped` (lines 8189, 8289) with aligned status phrasing.
  - Repaired citations to `ARCHIVE.md#code-review-defect2-shipped` for Defect 2 (lines 8353, 8366).
  - Repaired citations to `ARCHIVE.md#brainstorm-spec-interrogation-seam-resolved` (lines 8467, 8475, 8477).
- `docs/engineering-journal/LEARNINGS.md`:
  - Repaired citation to `ARCHIVE.md#marketplace-ci-guard-pruned` (line 9397).
- `docs/engineering-journal/README.md`:
  - Repaired citation to `ARCHIVE.md#marketplace-ci-guard-pruned` (line 39).

### 3. Tests & Quality Verification
- Added comprehensive unit tests in `tests/test_lint_journal_order.py`:
  - `test_cross_file_valid_fragment_explicit_and_generated`
  - `test_cross_file_missing_anchor_reports_source_and_destination`
  - `test_cross_file_slug_in_other_covered_file_but_missing_in_target_fails` (mutation proof: destination-local misses fail even if slug exists elsewhere)
  - `test_cross_file_destination_outside_covered_set_or_missing`
  - `test_cross_file_non_covered_path_with_covered_basename_is_rejected` (mutation proof: basename fallback rejected)
  - `test_cross_file_relative_path_navigation`
  - `test_cross_file_invalid_relative_path_fails`
  - `test_cross_file_external_links_ignored`
- Updated module docstring to describe the #838 covered-set cross-file fragment contract.
- Verified test suite: `uv run pytest tests/test_lint_journal_order.py -q` passes (42 tests).
- Verified linter on real repo: `uv run python scripts/lint_journal_order.py` reports 0 violations across 5 files.
- Verified formatting, types, and git hygiene: `ruff check`, `ruff format --check`, `mypy`, and `git diff --check` green.
