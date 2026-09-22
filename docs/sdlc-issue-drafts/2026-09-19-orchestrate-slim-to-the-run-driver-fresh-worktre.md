---
title: Orchestrate: slim to the run driver, fresh worktrees, parent branches
repo: infiquetra-claude-plugins
type: capability
team: asgard
project: operations
status: Ready for Planning
stage: Shaping
labels: capability, needs-plan
risk: high
mode: execute
handoff_maturity: requirements-ready
---

# Orchestrate: slim to the run driver, fresh worktrees, parent branches

### Objective

Keep orchestrate's good half (worktree and branch per unit, launch through agent-launcher, send the unit's command, wait, merge back, clean) and remove its protective layer: the fixed-path run record (the A5 record replaces it, one per issue, so runs coexist), launch reservations, landing reservations, `redrive` and its state machine (recovery is a relaunch from the unit's branch), the receipt and writeback records, the `collect` path that can regress `main`, and the companion version floor's refusal of mutating subcommands (warn instead). Add: a fresh worktree on every launch, a virtual-environment step in the worktree helper, remove-worktree-before-delete-branch, one repair owner per shared blocker as a run-record field, a parent branch for a parent issue with children merging onto it by merge turn, and the one useful fleet-doctor check (managed worktrees with no live session) in the clean step.

### Intent

Orchestrate already implements the model the operator wants over herdr; its open defects are almost all in the protective layer, and the five collisions actually recorded (duplicate repairs, a shared JSONL file, a stale worktree relaunch, a remote branch held by a worktree, missing virtual environments) each map to one simple line above. Decided 2026-09-19 (SR R16, R17, question 2). Cards re-parented here keep their fixes; the superseded cards' concerns are acceptance criteria below.

### Inputs inventory

- A5's run record schema — the fixed-path run record A7 replaces reads and writes against the shape A5 defines.
- The five recorded collisions this card's test list is tied to (SR section 8; `research-board-cards.md` clusters A and B).
- SDLC/docs/process/parent-branch-integration.md — the parent-branch merge model this card implements.

### Out-of-scope / non-goals

- No lock, lease, reservation, or receipt, whatever a test would like.
- No global concurrency cap beyond the width number the run record carries for the account rate limit.
- No change to agent-launcher's pane-write door.

### Files expected to change

- `plugins/orchestrate/skills/orchestrate/scripts/orchestrate.py` (6,450 lines today; expected to lose the run record, reservation, landing, redrive, receipt, and collect code)
- `plugins/orchestrate/skills/orchestrate/scripts/herdr_events.py`
- `plugins/orchestrate/skills/orchestrate/SKILL.md`, `plugins/orchestrate/commands/orchestrate.md`
- `tests/test_orchestrate*.py`
- release surfaces (orchestrate 5.0.0)

### Tests to add or update

- Relaunching a unit always creates a fresh worktree from the unit's branch and never reuses a path (card 886).
- Two `go` calls in the launch window launch one unit once because the launch is persisted immediately (cards 900, 990).
- The width number in the run record bounds concurrent launches across calls (card 901).
- A merge that would revert a newer `main` file is refused by name (card 875, as a merge-turn rule).
- Cleanup runs for every unit even when one path cannot be removed, and names the leftovers (cards 960, 979, 991).
- The protected-branch check casefolds and strips before comparing (card 874); the close-failure record is kept (card 944); a plan is validated without mutation (card 879); workspaces and worktrees created by a run are released at merge (card 876).

### Context library links

- coding_standards: _none_

General references:
- SR R16, R17, section 8; SDLC/docs/process/parent-branch-integration.md; `research-board-cards.md` cluster A and B

### Acceptance criteria

- [ ] `uv run python plugins/orchestrate/skills/orchestrate/scripts/orchestrate.py --help` lists no `redrive`, `collect`, or `land` subcommand and does list `plan-check`, `start`, `go`, `merge`, and `clean`.
- [ ] `grep -c -E "reserved_landing_paths|launch_reservation|record_writeback_outcome" plugins/orchestrate/skills/orchestrate/scripts/orchestrate.py` prints 0.
- [ ] `uv run pytest tests/test_orchestrate*.py -q` passes with the tests above present.
- [ ] Two runs for two issues can be started in one repository at once and each has its own run record.

### Verification

```bash
uv run python plugins/orchestrate/skills/orchestrate/scripts/orchestrate.py --help
grep -c -E "reserved_landing_paths|launch_reservation|record_writeback_outcome" plugins/orchestrate/skills/orchestrate/scripts/orchestrate.py
uv run pytest tests/test_orchestrate*.py -q
```

### Failure modes / pre-mortem

A removed protection turns out to have been load-bearing for a case not in the record; the answer is to add the simplest mechanism that covers the demonstrated case, not to restore the layer.

### Stop conditions

Stop if the slim driver cannot pass the fresh-worktree and immediate-persist tests without a reservation, or if a merge-turn rule cannot express the `main` regression guard.

### Risk

high

it rewrites the driver that launches every unit; the guard is the test list above, each tied to a recorded collision or an open card.

### Handoff maturity
requirements-ready

### Recommended Tier Band
opus/high

## Created Issue

- URL: https://github.com/infiquetra/infiquetra-claude-plugins/issues/1025
- Number: 1025
- Created at: 2026-09-19T14:44:49.410464+00:00

