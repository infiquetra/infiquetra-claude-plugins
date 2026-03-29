---
name: sdlc-board
description: Quick board status view with WIP check for Infiquetra project boards
---

Show the current status of an Infiquetra project board (mount-olympus or strategic) including WIP counts, aging items, and blockers.

## Usage

```
/sdlc-board [mount-olympus|strategic]
```

## Arguments

- `mount-olympus` — Show Mount Olympus Operations board (default)
- `strategic` — Show Strategic Direction board

## What This Does

1. Fetches all items from the specified project board
2. Groups items by status column (Ready, In Development, E2E Testing, Deployment Ready, Deployed)
3. Shows WIP counts vs. limits with violation warnings
4. Flags aging items (>3 days in development, >1 day in E2E)
5. Highlights blocked items

## Examples

```
/sdlc-board
/sdlc-board mount-olympus
/sdlc-board strategic
```

## Script Command

```bash
python3 ~/.claude/plugins/cache/infiquetra-plugins/sdlc-manager/1.0.0/scripts/sdlc_manager.py \
  board view --project mount-olympus
```

For WIP check only:
```bash
python3 ~/.claude/plugins/cache/infiquetra-plugins/sdlc-manager/1.0.0/scripts/sdlc_manager.py \
  board wip --project mount-olympus
```

## Instructions

When the user invokes `/sdlc-board [project]`:

1. Determine target project (default: mount-olympus)
2. Run the board view command
3. Run the WIP check command
4. Present a clean summary with:
   - Items by column with age
   - WIP violations (if any)
   - Blocked items highlighted
   - Aging items flagged
5. Offer follow-up actions: standup prep, move items, archive deployed

Use the `sdlc-board` skill for detailed board operations or the `sdlc-operator` agent for multi-step workflows.
