# Issue 609 board-move fail-loud plan

Date: 2026-07-16
Issue: `infiquetra/infiquetra-claude-plugins#609`
Risk: low
Canonical run: `99b64340-a05d-46ff-8eea-03c0ea7e218a` attempt 1

## Goal

Make `mission-control board move` return a nonzero process status whenever any
requested project move fails, while retaining complete result output and never
mutating a project when the requested Status is unavailable.

## Current state

`board_move()` appends error messages for missing items, missing Status fields or
options, and GraphQL mutation failures, but returns `None`. `main()` therefore
exits zero after all four failure classes. The successful mutation path and
human-readable output are otherwise correct.

Mission Control is version 2.10.0 in its manifest, generated marketplace, and
version guard. The repository releases this plugin from synchronized main-based
marketplace surfaces, not tags or GitHub Releases.

## Requirements

1. `board_move()` must process every selected project, emit the same per-project
   result messages, and return whether every move succeeded.
2. Missing item, Status field, Status option, or mutation success must count as
   failure. An invalid option must retain the available-status list and legacy
   hint, with no set-field mutation.
3. `main()` must exit 1 only after `board_move()` emits all results when the
   aggregate result is false. Successful invocations remain exit 0.
4. Add focused offline tests for success, unavailable Status/no mutation,
   missing item/field, mutation failure, multi-project aggregation, and the CLI
   exit boundary.
5. Bump mission-control 2.10.0 to 2.10.1 in the plugin manifest, generated
   marketplace, changelog, and version guard. Record the fail-loud CLI learning
   in the engineering journal.

## Implementation

- Change `board_move()` to maintain one aggregate success flag and return it
  after `_out()`.
- In the `board move` route, raise `SystemExit(1)` when that return is false.
  Do not raise inside the project loop, so later project outcomes remain visible.
- Add `plugins/mission-control/tests/test_board_move_exit.py` using patched
  config, project discovery, item lists, GraphQL, and output. No test performs a
  network call.
- Update the four release surfaces and durable learning in the same commit.

## Verification

```bash
uv run pytest plugins/mission-control/tests/test_board_move_exit.py -q
uv run pytest plugins/mission-control/tests/ -q
uv run pytest tests/test_mission_control.py tests/test_release_surface_parity.py -q
uv run ruff check plugins/mission-control/ tests/
uv run ruff format --check plugins/mission-control/ tests/
uv run mypy plugins/mission-control/ scripts/ tests/ --ignore-missing-imports
uv run python scripts/sync_marketplace.py --check
uv run python scripts/check_release_surface_parity.py
uv run python tools/release_surface_diff_guard.py --base-ref d198eac4acde5e4aaee7e8712c0d7181e6c59648
git diff --check
```

## Runtime and rollback

After merge, refresh the exact merged marketplace in the issue-scoped Claude
2.1.211 installation on VM 209. Invoke the installed script against a real
Operations item with a nonexistent Status, require exit 1, list available
statuses, and prove the item status did not change. Repeat version/enabled
readback in a fresh process. Roll back by removing the isolated canary root;
global npm, user Claude registry, and project state must remain unchanged.

## Scope boundary

No pagination or live-gate facet from #584, successful board mutation canary,
other plugin change, global install, tag/Release, ruleset, credential, or
production change is included.
