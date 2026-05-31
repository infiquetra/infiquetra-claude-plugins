---
title: "fix(infiquetra-deploy): query_deployments.py GET + tag-ref selection"
date: "2026-05-30"
issue: 161
plan: "docs/plans/2026-05-30-003-fix-deploy-status-query-deployments-plan.md"
status: "implemented — pending PR"
---

# Work session: fix deploy-status query_deployments.py

## What changed

`plugins/infiquetra-deploy/scripts/query_deployments.py`:

- `latest_deployment()` now issues `gh api --method GET` (was defaulting to POST via bare `-f`,
  causing HTTP 422 "ref wasn't supplied"). Fetches `per_page=20`.
- New `is_tag_ref()` helper: a ref is a tag only if it matches a `TAG_PREFIXES` entry followed
  by a version digit. Branch/SHA refs (`main`, `feature/*`, SHAs, `version-bump`) are rejected.
- `latest_deployment()` walks the newest-first page and returns the first tag-ref record,
  skipping CI-auto-created `environment:`-key deployments.
- Typed `data` as `list[dict[str, Any]]` to satisfy mypy (no `Any` return).

`tests/test_infiquetra_deploy_plugin.py` — 4 new tests:

- `test_is_tag_ref_accepts_tags_and_rejects_branches`
- `test_latest_deployment_issues_get_and_selects_newest_tag_ref` (AC4 + AC6)
- `test_latest_deployment_returns_none_without_tag_refs`
- `test_render_status_reports_and_omits_drift` (AC5)

## Checks run

| Gate | Result |
|------|--------|
| `ruff check` (script + tests) | All checks passed |
| `mypy` (script) | Success: no issues |
| `bandit` (script) | 0 issues |
| `pytest tests/test_infiquetra_deploy_plugin.py` | 9 passed |
| Live smoke (`--repo campps-identity-access`) | `nonprod: v0.1.0 (version 0.1.0)`, no HTTP 422 |
| Ground-truth GET (`.[0].ref`) | `v0.1.0` (matches) |

## Acceptance criteria

- AC1 GET, no 422 — met (live smoke + AC6 test)
- AC2 per-env versions live — met (campps-identity-access nonprod v0.1.0)
- AC3 non-tag refs ignored — met (`is_tag_ref`)
- AC4 newest-tag over newest-record — met (fixture test)
- AC5 drift still works — met (render_status test)
- AC6 GET assertion regression guard — met

## Next

- `/code-review` on the diff, then open PR `Closes #161`.
- Auto-merge once CI green (just-Jeff-and-Claude repo).
