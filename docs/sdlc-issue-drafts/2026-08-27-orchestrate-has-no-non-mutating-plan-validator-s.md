---
title: Orchestrate has no non-mutating plan validator so a bad plan is only discovered by starting a run
repo: infiquetra-claude-plugins
type: enhancement
team: asgard
project: operations
status: Shaping
labels: enhancement, needs-plan
risk: medium
mode: execute
handoff_maturity: requirements-ready
---

# Orchestrate has no non-mutating plan validator, so a bad plan is only discovered by starting a run

### Objective

Let an operator check a plan completely before anything is created, so a malformed plan fails as a
report rather than as a partly built run.

### Intent

The only subcommand that reads a plan is `start`, whose own help says what it does: **"create
worktrees and the run file from a plan"**. It takes `--plan` and `--base` and nothing else — there
is no `--dry-run`, no `--check`, no validate-only mode. `expand` is likewise mutating, appending
units to a live run.

`check` exists but is not this: it "report[s] where the run record and the repository disagree",
which requires a run to already exist.

So every plan defect — an unreachable dependency, a bad review-transport shape, an unsupported
vendor, a colliding unit name, an unrepresentable review-controller count — is discovered *after*
worktrees have been created and a run record written. Recovery then means unwinding real state:
removing worktrees, deleting branches, and clearing a run record that, per the separately-filed
fixed-path constraint, is also the thing standing in the way of the next attempt.

**Found during the Auralis preflight on installed Orchestrate 3.0.7.** The preflight wanted to
verify an approved plan before committing to it and had no way to do so.

The validation logic itself already exists and is good — `assert_dependencies_reachable`,
`assert_review_transport`, `assert_vendors_available`, `assert_safe_unit_names`,
`assert_saga_reachable`, `assert_no_engine_prefs`. The gap is purely that it is reachable only
through a mutating door.

### Out-of-scope / non-goals

- Do not change what the existing assertions check; this is about reaching them without mutating.
- Do not weaken `start`; it must keep running the same validation it runs today.
- Do not add a partial or best-effort mode that reports some problems and starts anyway.
- Do not create worktrees, branches, tabs, agents, or a run record on the validation path.

### Files expected to change

- `plugins/orchestrate/skills/orchestrate/scripts/orchestrate.py`
- `plugins/orchestrate/skills/orchestrate/SKILL.md`
- `plugins/orchestrate/commands/orchestrate.md`
- `tests/test_orchestrate_settlement.py` or the plan-validation test module
- Orchestrate release surfaces required by repository policy

### Tests to add or update

- A valid plan validates clean and creates **nothing**: assert no worktree, no branch, no tab, no
  run record, and an unchanged working tree afterward.
- Each existing assertion is reachable from the validation path and reports the same failure `start`
  would give: unreachable dependency, bad review transport, unavailable vendor, unsafe unit name,
  unreachable saga capability.
- Validation is safe with an active run present and does not touch that run's record.
- Exit status distinguishes valid from invalid, so it is usable in a gate.
- Mutation-prove non-mutation: making the validation path write anything must fail a test.

### Context library links

- Existing assertions: `assert_dependencies_reachable`, `assert_review_transport`, `assert_vendors_available`, `assert_safe_unit_names`, `assert_saga_reachable`, `assert_no_engine_prefs`
- The mutating entry points: `cmd_start`, `cmd_expand`
- The post-hoc reconciler this is not: `cmd_check`
- Discovery context: Auralis preflight on installed Orchestrate 3.0.7
- Related constraints filed separately in this retrospective: single Code Review controller, single fixed run record

### Verification

```bash
uv run pytest tests/test_orchestrate_settlement.py -q
uv run ruff check plugins/orchestrate/skills/orchestrate/scripts/orchestrate.py
GATE_LOG_DIR=/tmp/gate-run bash scripts/gate.sh > /tmp/gate.log 2>&1
cat /tmp/gate-run/result.txt
```

### Acceptance criteria

- [ ] A plan can be validated without creating a worktree, branch, tab, agent, or run record.
- [ ] Validation runs the same assertions `start` runs and reports the same failures.
- [ ] It is safe to run while another run is active, and leaves that run untouched.
- [ ] Exit status is usable as a gate step.
- [ ] `start` behaviour is unchanged.
- [ ] `bash scripts/gate.sh` exits 0 with Orchestrate release surfaces aligned.

### Notes / conventions

The cheapest sound shape is to split plan loading and assertion away from resource creation inside
`cmd_start`, then expose the first half. That keeps one code path as the source of truth and removes
any chance of a validator that agrees with a `start` it no longer matches.

## Created Issue

- URL: https://github.com/infiquetra/infiquetra-claude-plugins/issues/879
- Number: 879
- Created at: 2026-08-27T00:59:31.782230+00:00

