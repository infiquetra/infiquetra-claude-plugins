# Work session — issue #620 board-sync plugin resolution

**Status: PR-ready pending code-review gate.** Built U1–U4 on branch
`work/620-board-sync-plugin-resolution` from base `7e4d2db0` (= origin/main, unmoved). Full test
suite green (5436 passed, 0 failed, 1 skipped); all repo gates pass.

Leaf `sub-620` of outcome `governed-execution-integrity` (Objective #639). Native work saga
`issue-620`; harvest maps it to `leaf-governed-execution-integrity-sub-620` at close.

## What was built (by U-ID)

**U1 — generic resolver in fleet-core.** New
`plugins/fleet-core/scripts/fleet_commons/plugin_resolution.py`:
`resolve_plugin_root(name, *, markers, env_var, anchor) -> (Path, int)`, a five-rung ladder
generalizing the byte-frozen shim's fleet-core-only ladder to an arbitrary sibling plugin. `markers`
is a sequence (all must exist); default `anchor` is the module's own file so the installed-cache
layout misses rung 2 instead of resolving one directory short. 17 tests in
`tests/test_fleet_commons_plugin_resolution.py`.

**U2 — saga board-sync rewire.** `reconcile_board` resolves the mission-control root once per tick
and threads it to both the `sdlc_manager.py` CLI and the `sdlc-schema.json` read.
`default_board_writer` now takes a resolved `mission_control_root` (keyword-only) instead of a
`repo_root`. Two distinct failure modes (KTD3): root-unresolvable — including the KTD6 stale-fleet-core
`RuntimeError` — withholds the cohort with one `unavailable` record and no retry; resolved-but-schema-
unreadable keeps the prior per-op `failed`-with-comment-flowing behavior. Records carry
`board_sync_root` + `board_sync_rung` (R7). Touched `board_progression.py`, `outcome_board_sync.py`,
`outcome.py` (re-export + two call sites), `reconcile_controller.py`.

**U3 — /pulse rewire.** `pulse.default_sdlc_manager` shares the resolver; soft-failure telemetry
contract preserved (unavailable panel, never raises); reason names the ladder.

**U4 — release surfaces.** fleet-core 0.22.0 → 0.23.0, saga 0.113.0 → 0.114.0; marketplace +
CHANGELOGs + drift pins + DECISIONS `{#board-sync-plugin-resolution-620}` (KTD1–KTD6).
mission-control unchanged.

## Key decisions

Full rationale in `docs/plans/2026-07-24-issue-620-board-sync-plugin-resolution-plan.md` and DECISIONS
`{#board-sync-plugin-resolution-620}`. Load-bearing: the resolver lives in fleet-core's loaded package
(not the frozen shim), saga keeps reading the schema file directly (mission-control's own resolver
hits the network first), and a stale fleet-core degrades to the terminal record rather than an
uncaught import error.

## Sites fixed — four, not the two in the issue

`board_progression.py:318` (CLI), `outcome_board_sync.py:123` (schema, the version-less-path
arithmetic), `pulse.py:86`, `outcome_reconcile.py:233`. Plus a fifth production caller the doc-review
missed: `reconcile_controller.py:423`.

## Files modified

- `plugins/fleet-core/scripts/fleet_commons/plugin_resolution.py` (new)
- `plugins/saga/scripts/{board_progression,outcome_board_sync,outcome,reconcile_controller,pulse}.py`
- `plugins/{fleet-core,saga}/.claude-plugin/plugin.json`, `.claude-plugin/marketplace.json`
- `plugins/{fleet-core,saga}/CHANGELOG.md`, `docs/engineering-journal/DECISIONS.md`
- `tests/test_fleet_commons_plugin_resolution.py` (new); `tests/test_{outcome_board_sync,`
  `board_progression,outcome_reconcile,pulse_telemetry,saga_plugin,liveness_events,`
  `team_execution_liveness}.py`

## Checks run (all green at HEAD)

- Full suite: 5436 passed, 0 failed, 1 skipped
- `ruff check` + `ruff format --check`: clean on all changed files
- `mypy plugins/ scripts/ tests/ --ignore-missing-imports`: exit 0
- `bandit` delta: zero new (base had the identical 1 High B324 + 2 Low B404; new file adds none)
- `check_release_surface_parity.py`: all plugins in parity

## Gotcha captured

Three new U2 tests passed in isolation but failed in the full suite: `reconcile_board` imports
`board_progression` lazily through `sys.modules`, and every test-module `_load` reassigns that slot,
so a collection-time module handle went stale and the monkeypatch missed. Fixed by patching the
run-time-live `sys.modules` entry (`_live_bp()`), which is order-independent.

## Next step

Code-review gate (`/code-review` programmatic), then PR to merge. Destination merge, backend inline.
Post-merge: #642 hand-repair (this ships fleet-core 0.23.0 + saga 0.114.0 — a new release, so the
install registry will go stale five-for-five), R10 live acceptance from a non-monorepo repo, and the
sub-620 harvest.
