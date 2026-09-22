---
title: Integrate, release, functional test, close, and retro capture as automatic steps, with the six board moves
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

# Integrate, release, functional test, close, and retro capture as automatic steps, with the six board moves

### Objective

After an accepted review: the merging worker takes the merge turn (a run-record field), merges onto the parent branch or `main` per the destination, resolves ordinary conflicts, and re-integrates `main` into surviving branches; the Release Worker merges the parent through the repository's pull-request path, waits for required checks on the exact head, and deploys to the non-production destination through the deploy plugin's existing handoff; the Functional Tester runs the plan's scenarios (through `/qa`) against the real environment, and a failure re-enters the build loop under the post-merge allowance; the closing comment carries the sdlc's links; the journal entries are written in the shipping commit; and at each real boundary saga submits the one board move the sdlc allows it through mission-control's constrained lifecycle-field mutation (admission exit, plan-review pass, build start, review acceptance, merge plus deploy, close).

### Intent

Saga has written zero of the six board rungs since releases W7 and W8 and "names the move and invokes nothing"; `/work` stops after merge and routes to `/qa` advisorily. The sdlc's merge-turn design has no lock service and no integration worker (SR R6, R7, R19). Card 875's concern (never revert a newer `main`) is a merge-turn rule here.

### Inputs inventory

- A2's corrected board-schema vocabulary — the six board moves this card submits depend on it matching the live boards.
- A5's run record — merge-turn and destination fields, and the record this card's board moves and deploy handoff read.
- A7's run driver — the merge-back mechanics this card's merge turn extends into integrate, release, and close.
- SDLC/docs/process/parent-branch-integration.md, SDLC/docs/process/saga-board-write-authority.md, SDLC/docs/process/terminal-outcomes.md.

### Out-of-scope / non-goals

- No board write by saga itself: every move goes through mission-control.
- No production deployment; the destination is non-production.
- No change to `/qa`'s content (A15 redesigns it later); it reads the run record instead of the ledgers.

### Files expected to change

- `plugins/saga/skills/work/SKILL.md` (integrate and release steps), `plugins/saga/skills/qa/SKILL.md` (reads the run record), `plugins/saga/skills/retro/SKILL.md` (journal capture; engine, ledger, spend, and tier-efficacy readers removed)
- `plugins/saga/scripts/merge_turn.py` (new), `plugins/saga/scripts/board_progression.py` (rewritten thin: the six moves via mission-control), `plugins/saga/scripts/deploy_handoff.py` (kept)
- `plugins/saga/scripts/evidence_ledger.py`, `run_ledger.py`, `dispatch_settlement.py`, `effort_ledger.py` and the override readers (removed)
- release surfaces

### Tests to add or update

- Merge turn: only the holder merges; a merge that would revert a newer `main` file is refused by name; `main` is re-integrated into surviving branches after each merge.
- Board moves: each boundary submits exactly its one allowed move through mission-control's mutation entry point and nothing else; a refused move is reported, not retried silently.
- Functional test failure re-enters the loop and is counted against the post-merge allowance.

### Context library links

- coding_standards: _none_

General references:
- SDLC/docs/process/parent-branch-integration.md; SDLC/docs/process/saga-board-write-authority.md; SDLC/docs/process/terminal-outcomes.md; SR R6, R7, R19

### Acceptance criteria

- [ ] `uv run python plugins/saga/scripts/board_progression.py --record <path> --boundary review-accepted --dry-run` prints the single mission-control move it would submit.
- [ ] `test ! -f plugins/saga/scripts/evidence_ledger.py`
- [ ] `uv run pytest tests/test_merge_turn.py tests/test_board_progression.py -q` passes.
- [ ] A real run moved its card through Implementing, Ready to merge, and Closeout on the Operations board without an operator board edit, and its closing comment carries the pull request and deployment links.

### Verification

```bash
uv run python plugins/saga/scripts/board_progression.py --record <path> --boundary review-accepted --dry-run
uv run pytest tests/test_merge_turn.py tests/test_board_progression.py -q
gh project item-list 3 --owner infiquetra --format json --limit 600 | jq -r '.items[] | select(.content.number==<N>) | .status'
```

### Failure modes / pre-mortem

A board move at the wrong boundary misfiles a card; mission-control's all-boards-or-none write and the dry-run make each move inspectable.

### Stop conditions

Stop if a merge-turn case would need a lock to be correct, or if mission-control refuses a move the sdlc allows.

### Risk

high

it merges, deploys, and writes the board; every step is dry-runnable and the deploy uses the existing handoff.

### Handoff maturity
requirements-ready

### Recommended Tier Band
opus/high

## Created Issue

- URL: https://github.com/infiquetra/infiquetra-claude-plugins/issues/1028
- Number: 1028
- Created at: 2026-09-19T14:46:20.140829+00:00

