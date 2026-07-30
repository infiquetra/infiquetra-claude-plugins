---
title: enhancement(saga): U5 delete the lease lifecycle hook and the saga lease_broker wrapper
repo: infiquetra-claude-plugins
type: enhancement
team: campps
project: operations
status: Idea
labels: enhancement, hermes-task, needs-plan
risk: medium
handoff_maturity: plan-ready
approval_state: needs_operator_approval
---

# enhancement(saga): U5 delete the lease lifecycle hook and the saga lease_broker wrapper

### Objective
Delete saga's two remaining lease files outright — the lease lifecycle hook and the thin saga wrapper
around the fleet broker — and remove the hook's registration from the plugin manifest in the same
commit.

Unit **U5** of seven under parent issue #677 (retire the fleet lease broker). Plan:
`docs/plans/2026-07-30-issue-677-lease-broker-retirement-plan.md`. Board objective:
`defects-claude-plugins`.

### Intent
Two whole-file deletions, unblocked once U1 through U4 have landed and no saga module imports the
wrapper any more:

- `plugins/saga/hooks/lease_lifecycle_hook.py` (92 lines)
- `plugins/saga/scripts/lease_broker.py` (574 lines)

**The hook's registration must be removed in the same commit as the file.** A dangling registration is
a startup error, not a dead entry. Confirm the manifest surface by *reading* it, not by grepping
Python — the registration lives in the plugin's hook manifest, not in the module.

Verify there is no remaining `import lease_broker` anywhere in saga before deleting the wrapper.

**Depends on:** U1, U2, U3, U4. All four must be merged first.

### Out-of-scope / non-goals
- Do not delete anything under `plugins/fleet-core/` — that is U7. This unit removes saga's wrapper,
  not the broker it wraps.
- Do not touch `plugins/team-execution/` — that is U6.
- Do not start this unit before U1 through U4 have merged. Deleting the wrapper while a consumer still
  imports it breaks saga at import time.
- No plugin version bump in this unit. All three release surfaces move together in U7.

### Files expected to change
- `plugins/saga/hooks/lease_lifecycle_hook.py` — delete (92 lines)
- `plugins/saga/scripts/lease_broker.py` — delete (574 lines)
- The saga plugin's hook manifest — remove the lease hook registration
- `tests/test_saga_plugin.py`
- `tests/test_saga_hooks.py`

Line counts were measured at revision `ddba53a0`.

### Tests to add or update
`tests/test_saga_plugin.py`:

- The hook manifest contains no reference to the deleted hook.
- The plugin loads with no lease hook registered.

`tests/test_saga_hooks.py`:

- The remaining hooks still fire. This is the guard against the manifest edit taking a neighbouring
  registration with it.

### Context library links
- Parent issue: https://github.com/Infiquetra/infiquetra-claude-plugins/issues/677
- Plan: `docs/plans/2026-07-30-issue-677-lease-broker-retirement-plan.md` (unit U5)
- Document review: `docs/reviews/doc-review-issue-677-2026-07-30.md`
- Blocked on: U1, U2, U3, U4 (the four consumer-unwind units)

### Acceptance criteria
- [ ] Both files are gone: `test ! -e plugins/saga/hooks/lease_lifecycle_hook.py && test ! -e plugins/saga/scripts/lease_broker.py`
      exits 0.
- [ ] `grep -rn "lease_lifecycle_hook\|lease_broker" plugins/saga/` returns no matches, including the
      hook manifest.
- [ ] `uv run pytest tests/test_saga_plugin.py tests/test_saga_hooks.py -q` passes, proving the plugin
      loads and the surviving hooks still fire.
- [ ] `uv run pytest -q` passes with no failures attributable to this unit.
- [ ] `uv run ruff check . && uv run ruff format --check .` is clean.
- [ ] `uv run mypy plugins/ scripts/ tests/ --ignore-missing-imports` is clean.

### Verification
```bash
rtk proxy uv run pytest -q                      # baseline BEFORE touching anything
uv run pytest tests/test_saga_plugin.py tests/test_saga_hooks.py -q
uv run pytest -q
uv run ruff check . && uv run ruff format --check .
uv run mypy plugins/ scripts/ tests/ --ignore-missing-imports
uv run bandit -r plugins/
python3 scripts/lint_journal_order.py
grep -rn "lease_lifecycle_hook\|lease_broker" plugins/saga/
```

Cross-unit sentinel:

```bash
uv run pytest tests/test_agy_run_lease.py -q   # must pass UNMODIFIED
```

### Notes / conventions
This is the cheapest unit in the decomposition and the one most likely to be attempted early. It
cannot be — the wrapper stays imported until U1 through U4 land.

### Handoff maturity
plan-ready

### Suggested next action
Use `/work <issue>` to execute from the plan-grade context.

### Source context
- Source: `docs/plans/2026-07-30-issue-677-lease-broker-retirement-plan.md` (implementation unit U5)
- Source type: local-file
- Source title: Retire the fleet lease broker — implementation unit U5

### Recommended Tier Band
sonnet/medium

## Created Issue

- URL: https://github.com/infiquetra/infiquetra-claude-plugins/issues/682
- Number: 682
- Created at: 2026-07-30T11:38:30.195520+00:00

