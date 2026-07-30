---
title: enhancement(saga): U1 unwind lease settlement and successor handoff in outcome_compat
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

# enhancement(saga): U1 unwind lease settlement and successor handoff in outcome_compat

### Objective
Remove the fleet lease broker from saga's dispatch-settlement and successor-handoff path, so
`plugins/saga/scripts/outcome_compat.py` records settlement outcomes without a fencing token.

Unit **U1** of seven under parent issue #677 (retire the fleet lease broker). Plan:
`docs/plans/2026-07-30-issue-677-lease-broker-retirement-plan.md`. Board objective:
`defects-claude-plugins`.

### Intent
Settlement exists to give dispatched work at-least-once accounting. It did that by verifying a
resource-ref/token pair issued by the broker. With the broker gone, that pair does not exist, so the
verification has nothing to check.

Delete the lease verification from the six call sites and let settlement record outcomes directly.
The calls are `verify`, `prepare_agent_settlement`, `commit_agent_settlement`, `inspect_resource_head`,
`acquire_successor`, `verify` — at `:1328`, `:1393`, `:1413`, `:1545`, `:1643`, `:1664`.

Where a function's only job was to thread a token through, delete the function rather than leaving a
pass-through wrapper behind.

U1 through U4 are file-disjoint and may run in parallel. This unit blocks U5.

### Out-of-scope / non-goals
- Do not touch `plugins/saga/scripts/team_teardown.py` (U2), `engine_dispatch.py` or
  `outcome_worktrees.py` (U3), or the four light consumers (U4).
- Do not delete `plugins/fleet-core/scripts/fleet_commons/lease_broker.py` — that is U7.
- Do not delete `plugins/saga/scripts/lease_broker.py` (the thin saga wrapper) — that is U5.
- No plugin version bump in this unit. All three release surfaces move together in U7.
- Do not restore or redesign at-least-once accounting on a different mechanism. Losing the fencing
  token is an accepted loss recorded in the plan's Scope Decision, not a gap to backfill here.

### Files expected to change
- `plugins/saga/scripts/outcome_compat.py` (1,700 lines; 6 broker call sites)
- `tests/test_saga_outcome_compat.py`

All line references were measured against the working tree at revision `ddba53a0`. Re-grep before
editing rather than trusting the offsets.

### Tests to add or update
`tests/test_saga_outcome_compat.py`:

- A settlement records a terminal outcome with no lease present.
- A successor handoff completes without `acquire_successor`.
- A settlement for an unknown dispatch id still raises rather than silently passing. This is the
  regression guard — removing the token must not turn a real error into a no-op.

### Context library links
- Parent issue: https://github.com/Infiquetra/infiquetra-claude-plugins/issues/677
- Plan: `docs/plans/2026-07-30-issue-677-lease-broker-retirement-plan.md` (unit U1, requirement R1)
- Document review: `docs/reviews/doc-review-issue-677-2026-07-30.md`
- Origin of the settlement contract being unwound: issue #351 (dispatch settlement)

### Acceptance criteria
- [ ] `grep -rn "lease_broker\|lease_authority\|fleet_leases" plugins/saga/scripts/outcome_compat.py`
      returns no matches.
- [ ] `uv run pytest tests/test_saga_outcome_compat.py -q` passes, including the three new scenarios
      above.
- [ ] `uv run pytest -q` collects and passes with no failures attributable to this unit.
- [ ] `uv run ruff check . && uv run ruff format --check .` is clean.
- [ ] `uv run mypy plugins/ scripts/ tests/ --ignore-missing-imports` is clean.
- [ ] A `docs/engineering-journal/LEARNINGS.md` or `DECISIONS.md` entry ships in the same commit as
      the code change, per the repo rule.

### Verification
Baseline the suite before touching anything, so the collected-count delta is attributable:

```bash
rtk proxy uv run pytest -q
```

Then, after the change:

```bash
uv run pytest tests/test_saga_outcome_compat.py -q
uv run pytest -q
uv run ruff check . && uv run ruff format --check .
uv run mypy plugins/ scripts/ tests/ --ignore-missing-imports
uv run bandit -r plugins/
python3 scripts/lint_journal_order.py
grep -rn "lease_broker\|lease_authority\|fleet_leases" plugins/saga/scripts/outcome_compat.py
```

Cross-unit sentinel that must hold for every unit in this decomposition:

```bash
uv run pytest tests/test_agy_run_lease.py -q   # must pass UNMODIFIED
```

`tests/test_agy_run_lease.py` covers the *subprocess* lease (run id, pid, timeouts, shutdown state),
which is unrelated to the fleet broker despite sharing the word "lease". If it needs editing, the
deletion has gone too far.

### Notes / conventions
The word `lease` names two unrelated things in this repository. The fleet broker is one; agy's
subprocess supervision (`run-lease.json`) is the other. A case-insensitive `grep -i lease` also matches
"release", "released", and "releases" — use an anchored pattern such as
`grep -rEn "lease_broker|\blease(s|d)?\b"` when measuring.

### Handoff maturity
plan-ready

### Suggested next action
Use `/work <issue>` to execute from the plan-grade context.

### Source context
- Source: `docs/plans/2026-07-30-issue-677-lease-broker-retirement-plan.md` (implementation unit U1)
- Source type: local-file
- Source title: Retire the fleet lease broker — implementation unit U1

### Recommended Tier Band
sonnet/medium

## Created Issue

- URL: https://github.com/infiquetra/infiquetra-claude-plugins/issues/678
- Number: 678
- Created at: 2026-07-30T11:37:36.342400+00:00

