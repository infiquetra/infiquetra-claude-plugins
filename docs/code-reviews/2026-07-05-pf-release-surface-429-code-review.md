# Code review: `feat/pf-release-surface-429` (#429)

**Target:** branch `feat/pf-release-surface-429` vs `main` (`git diff main...HEAD`).
**Reviewed SHA:** `4fb08943a8afc0b984774092101901405435bff`.
**Blocked:** No (both P1 findings fixed in this review round; PR is now clean).
**Mode:** programmatic (called by `/work`'s pre-PR gate).
**Linked plan:** `docs/plans/2026-07-05-release-surface-single-source-plan.md`. **Linked saga:** `issue-429`.

## Scope check

**CLEAN.** Intent: implement #429's generator + tri-lock parity gate + diff-aware bump guard +
canonical CHANGELOG grammar for the plugin fleet. Delivered: exactly that — no unrelated files
touched, no scope creep. All 6 planned units (U1-U6) present in the diff.

## Plan-completion audit

| Unit | Status | Evidence |
|---|---|---|
| U1 — sync_marketplace.py generator + `--check` | DONE | `scripts/sync_marketplace.py`; 8 tests in `tests/test_sync_marketplace.py`, all passing |
| U2 — canonical CHANGELOG grammar + heading lint | DONE | `scripts/changelog_heading_lint.py`; KTD1 recorded in `DECISIONS.md`; 3 tests |
| U3 — reformat 9 CHANGELOGs + bump 4 + regenerate marketplace.json | DONE | `deploy 0.1.3, saga 0.54.1, team-execution 2.9.1, mission-control 2.5.1`; `.claude-plugin/marketplace.json` regenerated; `changelog_heading_lint.py` fleet baseline passes |
| U4 — check_release_surface_parity.py tri-lock gate | DONE (post-fix) | `scripts/check_release_surface_parity.py`; 4 tests incl. 2 regression tests added this review round |
| U5 — release_surface_diff_guard.py diff-aware bump guard | DONE (post-fix) | `tools/release_surface_diff_guard.py`; 10 tests incl. `docs/**` regression + argv-wiring tests added this review round |
| U6 — CI wiring + journal writeback | DONE | new `release-surfaces` job in `.github/workflows/ci.yml`; `LEARNINGS.md` dated entry |

No PARTIAL / NOT-DONE / CHANGED / UNVERIFIABLE items.

## Findings

Two P1s were found and fixed in this review round; both are resolved as of the reviewed SHA above.
No P0s. No P1s remain.

| # | File | Issue | Reviewer | Confidence | Route | Status |
|---|---|---|---|---|---|---|
| 1 | `scripts/check_release_surface_parity.py:42-43` (pre-fix) | Tri-lock's marketplace leg regenerated the version from `plugin.json` instead of reading the committed `marketplace.json` entry — a tautology by construction, defeating the leg's purpose | correctness | 100 | manual -> human | **Fixed** — rewritten to read `marketplace["plugins"]` directly; regression test `test_tri_lock_catches_stale_committed_marketplace_version` added |
| 2 | `tools/release_surface_diff_guard.py:7,25` (pre-fix) | Docstring promised a `docs/**` exemption `DOC_EXEMPT_SUFFIXES` never implemented — a doc-only PR under a plugin's `docs/` tree would be wrongly flagged | correctness + testing (cross-reviewer agreement) | 100 | safe_auto -> review-fixer | **Fixed** — `DOC_EXEMPT_PREFIX` added; 2 regression cases added to `test_doc_only_change_not_required_to_bump` |
| 3 | `scripts/check_release_surface_parity.py` (pre-fix) | No test exercised the `ParityError` / missing-dated-heading branch | testing | 90 | test-gap -> downstream-resolver | **Fixed** — `test_tri_lock_catches_missing_dated_heading` added |
| 4 | `scripts/sync_marketplace.py`, `tools/release_surface_diff_guard.py` | No test called either script's `main()`/argparse wiring end-to-end | testing | 80 | test-gap -> downstream-resolver | **Fixed** — `test_main_parses_check_and_category_flags`, `test_main_parses_base_ref_flag`, `test_main_defaults_base_ref_to_origin_main` added |
| 5 | `scripts/sync_marketplace.py:64-71` | `--category` override precedence over an *existing* entry's category was untested (docstring implies new-plugin-only use) | testing | 75 | test-gap -> downstream-resolver | **Fixed** — `test_category_override_replaces_existing_category` added; documents the actual (override-always) behavior rather than silently diverging from it |
| 6 | `tools/release_surface_diff_guard.py:32` (pre-fix) | `changed_files`'s `runner` param wasn't keyword-only/typed, unlike the house runner-injection convention (`ship_ceremony.py`, `outcome_store.py`) | maintainability | 90 | safe_auto -> review-fixer | **Fixed** — now `*, runner: Callable[..., Any] \| None = None` |
| 7 | `scripts/check_release_surface_parity.py:13-16` (pre-fix) | Used `sys.path.insert` + bare import instead of the house `importlib.util.spec_from_file_location` convention every other cross-script consumer uses | maintainability | 85 | safe_auto -> review-fixer | **Fixed** as a byproduct of the U4 rewrite (now uses the standard `spec_from_file_location` + `sys.modules` registration pattern) |
| 8 | `scripts/check_release_surface_parity.py`, `scripts/sync_marketplace.py`, `scripts/changelog_heading_lint.py` | Three-way ad hoc import coupling between sibling CLI scripts rather than a shared common module | maintainability | 75 | manual -> human | **Residual, not fixed** — see below |

## Residual risk

Finding #8 (three-script coupling) is a defensible design call at this scope, not a bug: each
script remains independently invocable (own `argparse`, own `__main__`), and factoring a shared
`scripts/_release_surface_common.py` module is a refactor the plan explicitly didn't scope (the
plan targets "a small set of mechanical Python scripts," not a shared-library extraction). Left as
documented residual risk rather than expanded scope; revisit if a 4th consumer of
`VERSION_HEADING_RE`/`build_target_plugins` emerges.

## Coverage

- Suppressed count: 0 (no findings fell in the 25-74 confidence band across any lens).
- Testing gaps: none remaining — all 5 testing-lens findings closed.
- Full gate: `uv run pytest` (1987 passed), `ruff format --check .`, `ruff check .`, `mypy plugins/
  scripts/ tests/ --ignore-missing-imports` (clean), `bandit -r plugins/ scripts/ tools/ -ll` (0 new
  medium/high findings in touched files).
- Live baseline: `sync_marketplace.py --check`, `check_release_surface_parity.py`, and the
  `fleet_baseline` heading-lint test all pass against the actual 9-plugin fleet, no fixtures.
- Self-dogfood: `tools/release_surface_diff_guard.py --base-ref main` run against this branch's own
  diff reports all changed plugins correctly bumped.

## Linked paths

Plan: `docs/plans/2026-07-05-release-surface-single-source-plan.md`. Doc-review:
`docs/reviews/2026-07-05-release-surface-single-source-429-doc-review.md`. Work-session:
`docs/work-sessions/2026-07-05-release-surface-single-source.md`.

> **Verdict:** CLEAN. Both P1s found this round are fixed and regression-tested. No P0/P1 remains.
> Route: PR-ready.
