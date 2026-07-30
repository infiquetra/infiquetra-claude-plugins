---
title: "defect(tests): test_outcome_cross_runtime lacks the _pin_script_modules repair — one test fails only in full-suite order"
repo: infiquetra-codex-plugins
type: defect
team: asgard
project: operations
status: Shaping
labels: defect, hermes-task, needs-plan
risk: medium
mode: implement
handoff_maturity: requirements-ready
---

# defect(tests): test_outcome_cross_runtime lacks the _pin_script_modules repair — one test fails only in full-suite order

### Objective

Make `tests/test_outcome_cross_runtime.py` order-independent by giving it the same per-test module
re-pinning every sibling `test_outcome_*` module already has, so the authoritative full-suite gate in
this CI-free repository reports a true `0 failed`.

### Intent

`tests/test_outcome_cross_runtime.py::TestAttachedAdvance::test_frontier_change_halts_rather_than_broadening`
**fails inside the full suite and passes when run alone**, in a clean detached worktree at the
pristine pre-`#54` commit `d0982fe`. It is not introduced by any recent port; it was measured as the
single failure in the `#54` baseline run (`1 failed, 2309 passed, 4 skipped`) and reproduced again in
the post-merge run.

This is the codex#45 P1 #3 defect class. These test modules load plugin scripts by path and register
them under a fixed key: `tests/test_outcome_cross_runtime.py` does
`sys.modules["outcome_compat"] = module` (line 39), `sys.modules["_test_fleet_lease_broker"] = module`
(line 695), and `sys.modules["outcome"] = module` (line 970). When another module loads the same
script under the same key, the last loader wins, while module-level globals captured earlier in this
module keep pointing at the now-orphaned earlier object. Collection order therefore decides the
outcome.

The repair already exists in this repo and is applied inconsistently. Twelve sibling modules define a
`_pin_script_modules` autouse fixture that re-pins each loaded script per test — for example
`tests/test_outcome_completion.py:42`, `tests/test_outcome_replay.py:38`,
`tests/test_outcome_dispatcher.py:42`, `tests/test_outcome_integration.py:48`,
`tests/test_outcome_merge_queue.py:41`. `test_outcome_cross_runtime.py` has no such fixture. Four
other `test_outcome_*` modules also lack it (`test_outcome_cross_runtime_parity_port_contract.py`,
`test_outcome_dispatch_migration.py`, `test_outcome_spec.py`, `test_outcome_store.py`); planning must
determine which of those genuinely load scripts into shared `sys.modules` keys and are therefore
latently exposed, versus which never load a script at all.

Severity is raised by the environment: **this repository has no CI** (`.github` exists,
`.github/workflows` does not). Every gate is a local full-suite run, so a permanently red test in the
authoritative gate trains operators to read `1 failed` as normal and destroys the signal that the
gate exists to carry.

### Out-of-scope / non-goals

- Changing any production behavior in `plugins/`. This is a test-isolation defect; the assertion
  under test is correct and its subject code is not suspected.
- Rewriting the module-loading helper into a shared conftest utility. That may be the right long-term
  shape, but it widens the blast radius across every `test_outcome_*` module; propose it separately if
  planning finds it warranted.
- The eight full-suite skips governed by `CODEX_PORT_SOURCE_REPO`. Same run, different mechanism,
  filed separately.
- codex#56 (`.gitignore` omits `.claude/`), which is why full-suite gates must run in a clean detached
  worktree. Independent.

### Files expected to change

- `tests/test_outcome_cross_runtime.py` — add the `_pin_script_modules` autouse fixture and the
  module-list constant the sibling modules use.
- `tests/test_outcome_cross_runtime_parity_port_contract.py` — only if planning confirms it loads
  scripts into shared keys.
- `tests/test_outcome_dispatch_migration.py` — same condition.
- `tests/test_outcome_spec.py` — same condition.
- `tests/test_outcome_store.py` — same condition.

### Tests to add or update

- Red-first: capture the failure deterministically before the fix by running the ordered pair that
  produces it, so the repair is demonstrated rather than asserted.
- The existing `test_frontier_change_halts_rather_than_broadening` body must **not** be edited. If the
  fix requires changing the assertion, the diagnosis is wrong and planning must stop and re-derive.
- Regression guard: a check that every `test_outcome_*` module which assigns into `sys.modules`
  also defines `_pin_script_modules`, so the next module to load a script cannot silently reintroduce
  this class.

### Context library links

_none_

### Acceptance criteria

- [ ] The test passes in full-suite order. `PYTHONPATH=. uv run pytest -q` in a clean detached
      worktree reports `0 failed`.
- [ ] The test still passes in isolation. `PYTHONPATH=. uv run pytest tests/test_outcome_cross_runtime.py -q`
      reports `0 failed`.
- [ ] Order-independence is proven, not assumed. `PYTHONPATH=. uv run pytest -q -p no:randomly` and a
      second run with `--forked` or a reversed-order selection both report `0 failed`, and the two
      invocations are recorded in the work-session file.
- [ ] Red-first is demonstrated. The ordered repro is run against the pre-fix tree via
      `git stash && PYTHONPATH=. uv run pytest -q <ordered selection>; git stash pop`, showing exactly
      that one test failing, with the output pasted into the work-session record.
- [ ] The assertion under test is unchanged. `git diff -- tests/test_outcome_cross_runtime.py` shows
      additions only within the fixture and its module-list constant, and no deletions inside
      `test_frontier_change_halts_rather_than_broadening`.
- [ ] The regression guard is real. Deleting `_pin_script_modules` from any one covered module makes
      the new guard fail: `PYTHONPATH=. uv run pytest tests/ -q -k "pin_script_modules"` reports a
      failure under that mutation.
- [ ] Plugin validation stays clean. `python3 scripts/validate_codex_plugins.py` exits `0` in a clean
      detached worktree.

### Verification

Only `PYTHONPATH=. uv run pytest` collects in this repo — plain `uv run pytest` fails with 11
collection errors and `python3 -m pytest` with 16, including a missing `PIL`. Run every full-suite
gate in a **clean detached worktree**, never the primary tree (codex#56).

```bash
# 1. Reproduce: fails inside the suite.
git worktree add --detach /tmp/codex-pin d0982fec60465b35e3ae5a15cf5e69197e4bf7f5
cd /tmp/codex-pin && PYTHONPATH=. uv run pytest -q 2>&1 | tail -5
# Observed at d0982fe: 1 failed, 2309 passed, 4 skipped
#   FAILED tests/test_outcome_cross_runtime.py::TestAttachedAdvance::
#          test_frontier_change_halts_rather_than_broadening

# 2. Contrast: passes alone.
PYTHONPATH=. uv run pytest \
  "tests/test_outcome_cross_runtime.py::TestAttachedAdvance::test_frontier_change_halts_rather_than_broadening" -q
# Observed: 1 passed

# 3. Confirm the missing repair.
grep -c "_pin_script_modules" tests/test_outcome_cross_runtime.py   # 0
grep -c "_pin_script_modules" tests/test_outcome_completion.py      # non-zero
```

Evidence anchors, verified live at `main` `8fdbe36`:

```
tests/test_outcome_cross_runtime.py:39     sys.modules["outcome_compat"] = module
tests/test_outcome_cross_runtime.py:695    sys.modules["_test_fleet_lease_broker"] = module
tests/test_outcome_cross_runtime.py:970    sys.modules["outcome"] = module
tests/test_outcome_completion.py:42        def _pin_script_modules(...)   <- the repair
tests/test_outcome_replay.py:38            def _pin_script_modules(...)
tests/test_outcome_dispatcher.py:42        def _pin_script_modules(...)
tests/test_outcome_integration.py:48       def _pin_script_modules(...)
tests/test_outcome_merge_queue.py:41       def _pin_script_modules(...)
```

12 of 17 `test_outcome_*` modules define the fixture; `test_outcome_cross_runtime.py` is one of the 5
that do not.

### Handoff maturity

requirements-ready

### Suggested next action

Use `/plan <issue>` to create an implementation plan.

### Recommended Tier Band

sonnet/medium

## Created Issue

- URL: https://github.com/infiquetra/infiquetra-codex-plugins/issues/66
- Number: 66
- Created at: 2026-07-27T00:55:33.395382+00:00

