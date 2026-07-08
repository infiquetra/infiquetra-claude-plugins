# Code-review — repo argument normalization (#505)

- **Scope:** `fix/505-repo-normalization` vs `origin/main`.
- **Mode:** inline code-review gate after `/work`.
- **Verdict:** PASS — no P0/P1/P2 findings. PR-ready.

## Findings

| Priority | Finding | Status |
|---|---|---|
| P0 | None. | Clean. |
| P1 | None. | Clean. |
| P2 | None. | Clean. |

## Lenses Applied

| Lens | Result |
|---|---|
| Built-vs-planned audit | PASS — U1/U2/U3/U4 from the reviewed plan are implemented. |
| Parser boundary correctness | PASS — normalization happens at argparse before command dispatch, preserving existing bare-repo helper contracts. |
| Foreign-owner safety | PASS — owner-qualified repos outside `infiquetra` fail during parse before any GitHub mutation or network call. |
| Command surface coverage | PASS — all repository-valued parser flags use the same helper, including `--repo`, `--parent-repo`, and `--child-repo`. |
| Release surface parity | PASS — mission-control metadata, changelog, marketplace registry, and release-surface guard checks are updated. |

## Gates Reviewed

- `uv run pytest plugins/mission-control/tests/test_flow_subcommands.py -k "repo_arg or link_sub_issue_normalizes" -v`
- `uv run pytest plugins/mission-control/tests/test_flow_subcommands.py -k "repo_arg or link_sub_issue_normalizes or field_options or set_field" -v`
- `uv run python -m ruff check plugins/mission-control/scripts/sdlc_manager.py plugins/mission-control/tests/test_flow_subcommands.py`
- `uv run python -m ruff format --check plugins/mission-control/scripts/sdlc_manager.py plugins/mission-control/tests/test_flow_subcommands.py`
- `uv run python -m mypy plugins/mission-control/scripts/sdlc_manager.py plugins/mission-control/tests/test_flow_subcommands.py --ignore-missing-imports`
- `python3 scripts/check_release_surface_parity.py`
- `uv run python scripts/sync_marketplace.py --check`
- `python3 tools/release_surface_diff_guard.py --base-ref origin/main`
- Live acceptance: `labels audit` succeeded with both `infiquetra/infiquetra-claude-plugins` and
  `infiquetra-claude-plugins`.
- `git diff --check`

## Residual Risk

No blocking residual risk. The implementation relies on a shared parser boundary rather than
duplicating tests for every command family; this matches the chosen design and keeps the regression
surface focused.
