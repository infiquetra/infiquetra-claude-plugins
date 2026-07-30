---
title: enhancement(saga): U4 unwind the four light lease consumers and the emitted contract
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

# enhancement(saga): U4 unwind the four light lease consumers and the emitted contract

### Objective
Remove the fleet lease broker from saga's four remaining light consumers — `outcome.py`,
`second_opinion.py`, `outcome_dispatcher.py`, and `workflow_emitter.py` — and re-narrow the exception
handler in the emitter that currently catches two lease exception types that are about to stop
existing.

Unit **U4** of seven under parent issue #677 (retire the fleet lease broker). Plan:
`docs/plans/2026-07-30-issue-677-lease-broker-retirement-plan.md`. Board objective:
`defects-claude-plugins`.

### Intent
These four files are grouped because none needs restructuring — the work is mostly deleting a broker
construction and an `acquire_agent` call.

- `plugins/saga/scripts/outcome.py` — 2 sites: `:1853` broker construction, `:2810` `acquire_agent`.
- `plugins/saga/scripts/second_opinion.py` — ~3 sites.
- `plugins/saga/scripts/outcome_dispatcher.py` — ~3 sites; loads at `:88`, `:259`, `:281`.
- `plugins/saga/scripts/workflow_emitter.py` — sites at `:117`, `:151`, `:186` broker construction,
  **`:187` the live `renew_batch`**, `:198`, `:254`, `:255`.

`workflow_emitter.py` is the exception to "mostly deleting". It holds the live `renew_batch` call at
`:187`, and it catches `lease_broker.HookInputError` and `lease_broker.authority.LeaseBrokerError` at
`:254-255`. **Both of those exception types disappear with the module, so the surrounding `except`
must be re-narrowed, not merely shortened.** Catching nothing where it used to catch lease errors is a
behavior change and belongs in the CHANGELOG under a `Changed` heading.

U1 through U4 are file-disjoint and may run in parallel. This unit blocks U5.

### Out-of-scope / non-goals
- Do not touch `outcome_compat.py` (U1), `team_teardown.py` (U2), `engine_dispatch.py` or
  `outcome_worktrees.py` (U3).
- Do not delete `plugins/saga/hooks/lease_lifecycle_hook.py` or `plugins/saga/scripts/lease_broker.py`
  — those are U5.
- Do not delete anything under `plugins/fleet-core/` — that is U7.
- Do not replace the `renew_batch` call with a substitute renewal mechanism. There is no lease left to
  renew.
- No plugin version bump in this unit. Release surfaces move in U7.

### Files expected to change
- `plugins/saga/scripts/outcome.py` (2 sites)
- `plugins/saga/scripts/second_opinion.py` (~3 sites)
- `plugins/saga/scripts/outcome_dispatcher.py` (~3 sites)
- `plugins/saga/scripts/workflow_emitter.py` (7 sites, incl. the live `renew_batch` at `:187`)
- `tests/test_workflow_emitter.py`
- `tests/test_saga_outcome.py`

Line references were measured at revision `ddba53a0`. Re-grep before editing.

### Tests to add or update
`tests/test_workflow_emitter.py`:

- An emit completes with no batch lease.
- An emit whose child fails still surfaces the failure through the **re-narrowed** handler. This is
  the guard against the re-narrowing swallowing or dropping a real error.

`tests/test_saga_outcome.py`:

- An outcome run starts with no broker constructed.

### Context library links
- Parent issue: https://github.com/Infiquetra/infiquetra-claude-plugins/issues/677
- Plan: `docs/plans/2026-07-30-issue-677-lease-broker-retirement-plan.md` (unit U4, decision KTD4)
- Document review: `docs/reviews/doc-review-issue-677-2026-07-30.md`

### Acceptance criteria
- [ ] `grep -rn "lease_broker\|lease_authority\|fleet_leases" plugins/saga/scripts/outcome.py plugins/saga/scripts/second_opinion.py plugins/saga/scripts/outcome_dispatcher.py plugins/saga/scripts/workflow_emitter.py`
      returns no matches.
- [ ] The `except` at `workflow_emitter.py:254-255` is re-narrowed to concrete surviving exception
      types — not left bare, and not deleted outright.
- [ ] `uv run pytest tests/test_workflow_emitter.py tests/test_saga_outcome.py -q` passes, including
      the failing-child test through the re-narrowed handler.
- [ ] The CHANGELOG records the exception-handling behavior change under `Changed`.
- [ ] `uv run pytest -q` passes with no failures attributable to this unit.
- [ ] `uv run ruff check . && uv run ruff format --check .` is clean.
- [ ] `uv run mypy plugins/ scripts/ tests/ --ignore-missing-imports` is clean.

### Verification
```bash
rtk proxy uv run pytest -q                      # baseline BEFORE touching anything
uv run pytest tests/test_workflow_emitter.py tests/test_saga_outcome.py -q
uv run pytest -q
uv run ruff check . && uv run ruff format --check .
uv run mypy plugins/ scripts/ tests/ --ignore-missing-imports
uv run bandit -r plugins/
python3 scripts/lint_journal_order.py
grep -rn "lease_broker\|lease_authority\|fleet_leases" plugins/saga/scripts/outcome.py plugins/saga/scripts/second_opinion.py plugins/saga/scripts/outcome_dispatcher.py plugins/saga/scripts/workflow_emitter.py
```

Cross-unit sentinel:

```bash
uv run pytest tests/test_agy_run_lease.py -q   # must pass UNMODIFIED
```

### Notes / conventions
The `renew_batch` call at `workflow_emitter.py:187` is live — it is the site the plan singles out as
load-bearing, and an earlier draft of the unit's file list stopped at `:186` and omitted it. Confirm
it is in the diff.

### Handoff maturity
plan-ready

### Suggested next action
Use `/work <issue>` to execute from the plan-grade context.

### Source context
- Source: `docs/plans/2026-07-30-issue-677-lease-broker-retirement-plan.md` (implementation unit U4)
- Source type: local-file
- Source title: Retire the fleet lease broker — implementation unit U4

### Recommended Tier Band
sonnet/medium

## Created Issue

- URL: https://github.com/infiquetra/infiquetra-claude-plugins/issues/681
- Number: 681
- Created at: 2026-07-30T11:38:16.384383+00:00

