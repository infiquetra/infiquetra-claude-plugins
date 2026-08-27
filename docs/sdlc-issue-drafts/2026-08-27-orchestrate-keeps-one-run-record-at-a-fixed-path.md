---
title: Orchestrate keeps one run record at a fixed path so a stale run blocks the next and two runs cannot coexist
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

# Orchestrate keeps one run record at a fixed path, so a stale run blocks the next one and two runs cannot coexist

### Objective

Let a repository hold more than one Orchestrate run record, and let a completed run stop standing in
the way of the next one.

### Intent

The run record is a module-level constant:

```python
RUN_FILE = Path(".orchestrate/run.json")
```

Every subcommand loads and saves that one path, and **no subcommand accepts a flag naming which run
to act on** — there are zero `--run` arguments in the script. Two consequences follow:

- **A stale record blocks the next run.** After a campaign completes, its record remains the active
  one. Starting the next run means displacing it, and the only durable-looking convention today is
  the hand-made archive copy (`.orchestrate/run-orch-<id>-FINAL.json`) that this repository writes
  by hand at closeout. That convention is operator practice, not something the tool knows about or
  enforces.
- **Two runs cannot coexist.** A second concurrent run has nowhere to live.

**Found during the Auralis preflight on installed Orchestrate 3.0.7**, where the fixed record was
identified as preventing another run while a stale record was present.

This compounds the separately-filed single-Code-Review-controller constraint: when a campaign is too
large for one review controller, the natural workaround is several runs — which this makes
unavailable. Together they leave some approved campaign shapes with no representable form at all.

### Out-of-scope / non-goals

- Do not silently delete, overwrite, or migrate an existing run record.
- Do not break reading a `run.json` written by an older version; the record is already documented as
  read as-is with no migration.
- Do not require existing single-run repositories to change anything; the default path must keep
  working untouched.
- Do not build run scheduling, queuing, or cross-run coordination.

### Files expected to change

- `plugins/orchestrate/skills/orchestrate/scripts/orchestrate.py`
- `plugins/orchestrate/skills/orchestrate/SKILL.md`
- `tests/test_orchestrate_settlement.py` or the run-record test module
- Orchestrate release surfaces required by repository policy

### Tests to add or update

- With no selector given, behaviour is byte-for-byte today's: `.orchestrate/run.json` is used.
- A second run can be started while a completed run's record still exists, without displacing it.
- Each subcommand acts on the selected run and never mutates a different one.
- Starting a run that would displace an existing **active** record is refused, naming that record.
- A record written by an older version still loads unchanged.
- Mutation-prove isolation: making two runs share a record must fail a test.

### Context library links

- Current constant and its readers: `plugins/orchestrate/skills/orchestrate/scripts/orchestrate.py` (`RUN_FILE`)
- Existing hand-made archive convention: `.orchestrate/run-orch-*-FINAL.json`, five records to date
- Discovery context: Auralis preflight on installed Orchestrate 3.0.7
- The related single-controller constraint, filed separately in this same retrospective
- Forward-compatibility precedent for run records: issue 617

### Verification

```bash
uv run pytest tests/test_orchestrate_settlement.py -q
uv run ruff check plugins/orchestrate/skills/orchestrate/scripts/orchestrate.py
GATE_LOG_DIR=/tmp/gate-run bash scripts/gate.sh > /tmp/gate.log 2>&1
cat /tmp/gate-run/result.txt
```

### Acceptance criteria

- [ ] More than one run record can exist without the records colliding.
- [ ] A completed run no longer blocks starting the next one.
- [ ] Omitting any selector reproduces today's behaviour exactly.
- [ ] Displacing an active run record is refused, and the refusal names it.
- [ ] Older run records still load without migration.
- [ ] `bash scripts/gate.sh` exits 0 with Orchestrate release surfaces aligned.

### Notes / conventions

Archiving a finished run is currently an operator habit this repository performs by hand. Whatever
shape the fix takes, promoting that habit into something the tool understands is the part worth
keeping, because it is what makes "the previous run is done" a fact the tool can act on rather than
a convention it cannot see.

## Created Issue

- URL: https://github.com/infiquetra/infiquetra-claude-plugins/issues/878
- Number: 878
- Created at: 2026-08-27T00:58:44.378562+00:00

