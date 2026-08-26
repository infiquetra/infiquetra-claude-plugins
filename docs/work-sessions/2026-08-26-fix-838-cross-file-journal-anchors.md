# Work session — validate cross-file journal fragment citations (#838)

**Saga:** `issue-838` · **Plan:** `docs/plans/2026-08-26-improve-claude-plugins-847-run-plan.md` (Unit U2) ·
**Branch:** `orch/orch-2026-08-26-847-847-g2-838` · **Destination:** PR ·
**Backend:** `inline` (operator-approved in run directive)

## Summary of Changes

Extended `scripts/lint_journal_order.py` to validate cross-file Markdown fragment links (`](FILE.md#anchor)`) among the covered journal set (`LEARNINGS.md`, `DECISIONS.md`, `ARCHIVE.md`, `QUEUED.md`) against both explicit `{#slug}` heading anchors and GitHub-generated Markdown heading anchor slugs. Repaired all 18 broken cross-file citations catalogued in PR #832 across `docs/engineering-journal/`.

### 1. Linter Implementation (`scripts/lint_journal_order.py`)
- Added `_github_slug` and `_heading_slugs` to compute GitHub-compliant anchor slugs from heading lines.
- Updated `_references` to extract both same-file anchor mentions (`{#slug}` / `](#slug)`) and cross-file Markdown fragment links (`](FILE.md#anchor)`).
- Updated `check_anchors` to resolve destination files relative to the referencing document (handling relative paths like `../DECISIONS.md` in `docs/engineering-journal/narratives/`) as well as repo-relative paths and basenames.
- Enforced rejection of missing anchors with source line and destination file identification.
- Enforced rejection of citations to files outside the covered journal set.

### 2. Broken Citation Repairs across Engineering Journal
- `docs/engineering-journal/ARCHIVE.md`:
  - Added missing heading `### "Anthropic tool schemas reject top-level oneOf outright" (pre-correction of `#toplevel-oneof-schema-dispatch-400`)  {#toplevel-oneof-schema-dispatch-400-v1}` at line 534.
  - Repaired citations to `#investigate-systematic-debugging-engine-shipped` (lines 156, 217, 219).
  - Repaired citation to `#optimize-engine-rebuild-shipped` (line 195).
  - Repaired citations to `#code-review-saga-scan-touchups-shipped` (lines 255, 261, 263).
  - Repaired citation to `#brainstorm-spec-interrogation-seam-resolved` (line 345).
- `docs/engineering-journal/DECISIONS.md`:
  - Repaired citation to `QUEUED.md#brainstorm-ideate-convergence-bias` (line 7587).
  - Repaired citations to `ARCHIVE.md#investigate-systematic-debugging-engine-shipped` (lines 8189, 8289).
  - Repaired citations to `ARCHIVE.md#code-review-saga-scan-touchups-shipped` (lines 8353, 8366).
  - Repaired citations to `ARCHIVE.md#brainstorm-spec-interrogation-seam-resolved` (lines 8467, 8475, 8477).
- `docs/engineering-journal/LEARNINGS.md`:
  - Repaired citation to `ARCHIVE.md#marketplace-ci-guard-pruned` (line 9397).
- `docs/engineering-journal/README.md`:
  - Repaired citation to `ARCHIVE.md#marketplace-ci-guard-pruned` (line 39).

### 3. Tests & Quality Verification
- Added 5 new unit tests in `tests/test_lint_journal_order.py`:
  - `test_cross_file_valid_fragment_explicit_and_generated`
  - `test_cross_file_missing_anchor_reports_source_and_destination`
  - `test_cross_file_destination_outside_covered_set_or_missing`
  - `test_cross_file_relative_path_navigation`
  - `test_cross_file_external_links_ignored`
- Verified complete test suite: `uv run pytest tests/test_lint_journal_order.py -q` passes (39 tests).
- Verified linter on real repo: `uv run python scripts/lint_journal_order.py` reports 0 violations.
- Verified gate and formatting: `ruff check`, `ruff format --check`, `mypy`, `gate.sh`, and `git diff --check` green.
