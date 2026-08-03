---
title: Workflow execution lease expires long before the run it guards
repo: infiquetra-claude-plugins
type: defect
team: asgard
project: operations
status: Shaping
labels: defect, hermes-task, needs-plan
risk: medium
mode: actionable
handoff_maturity: requirements-ready
---

# Workflow execution lease expires long before the run it guards

### Objective
Make the workflow execution lease outlive the workflow it guards, so the concurrency guarantee it
exists to provide actually holds for the duration of a run.

### Intent
`plugins/saga/scripts/execution_spec.py:3582` hard-codes `"execution_ttl_seconds": 300` for the
lease minted before a `cc-workflows-ultracode` launch. That lease is what enforces the operator's
concurrency cap across the fleet.

Five minutes is shorter than the runs it guards. The #686 execution ran 32.2 minutes of wall clock
against that 300-second lease. The slots were swept roughly five minutes in, while three subagents
were still executing. Nothing over-subscribed in that instance, but for the remaining 27 minutes the
lease was not providing the guarantee it was minted for — the fleet had no record that those slots
were in use.

A renewal path exists: `plugins/saga/scripts/lease_broker.py:437` defines a `renew` subcommand and
line 406 calls `renew_batch`. Nothing in the `/work` skill invokes it during a workflow run. The
skill's only documented mid-run checkpoint is the phase/segment boundary
(`plugins/saga/skills/work/SKILL.md:552`, which reads the adjustment envelope and explicitly is
"not a new poll loop"), and a single background workflow call has no phase boundary inside it. So
there is currently no moment at which a renewal could be issued.

Teardown makes this hard to notice: `release` returned an empty list, which is indistinguishable
from a clean release of leases that were still held.

### Out-of-scope / non-goals
- Do not introduce a polling loop in the driving session; the skill deliberately avoids one.
- Do not change the operator concurrency cap itself.
- Do not change lease semantics for non-workflow backends (`inline`, `team-execution`).

### Files expected to change
- `plugins/saga/scripts/execution_spec.py` (the lease payload around line 3582)
- `plugins/saga/skills/work/SKILL.md` (renewal or long-TTL guidance at launch)
- `plugins/saga/scripts/lease_broker.py` if the renewal path needs a background-safe entry point
- `tests/` coverage for the emitted lease payload
- `plugins/saga/CHANGELOG.md`, `plugins/saga/.claude-plugin/plugin.json`,
  `.claude-plugin/marketplace.json`

### Tests to add or update
- A test asserting the emitted lease TTL is derived from the run's expected duration rather than a
  fixed 300, or that a renewal is scheduled if it is not.
- A test that `release` distinguishes "released N held leases" from "there was nothing to release",
  so a swept lease cannot read as a clean teardown.

### Context library links
- `docs/engineering-journal/LEARNINGS.md` anchor `{#workflow-lease-ttl-outlives-no-poll-contract}`
- `plugins/saga/skills/work/SKILL.md` line 552
- `docs/work-sessions/2026-08-03-verify-panel-severity-axis.md`

### Acceptance criteria
- [ ] A workflow lease minted for a run of arbitrary length is still held at the 10-minute mark, proven
   by a test that advances time past 300 seconds.
- [ ] `grep -c '"execution_ttl_seconds": 300' plugins/saga/scripts/execution_spec.py` returns 0.
- [ ] Teardown reports a distinguishable result for "released held leases" versus "nothing to release",
   pinned by a test.
- [ ] Reverting the TTL change in a scratch copy makes the new test fail (mutation proof).
- [ ] `uv run python -m pytest -q` exits 0.

### Verification
```bash
uv run python -m pytest tests/ -q -k 'lease or workflow'
uv run python -m pytest -q
grep -n 'execution_ttl_seconds' plugins/saga/scripts/execution_spec.py
uv run python scripts/check_release_surface_parity.py
```

### Handoff maturity
requirements-ready

### Suggested next action
Use `/plan <issue>` to create an implementation plan.

### Source context
- Source: /private/tmp/claude-501/-Users-jefcox-workspace-infiquetra-infiquetra-claude-plugins/69f09efc-465e-4e84-9258-fcca4901722b/scratchpad/cards/04-workflow-lease-ttl.md
- Source type: local-file
- Source title: 04-workflow-lease-ttl

### Recommended Tier Band
opus/high

## Created Issue

- URL: https://github.com/infiquetra/infiquetra-claude-plugins/issues/694
- Number: 694
- Created at: 2026-08-03T19:54:57.623386+00:00

