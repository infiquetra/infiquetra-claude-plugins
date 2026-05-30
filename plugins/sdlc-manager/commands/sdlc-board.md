---
name: sdlc-board
description: Quick board status view with WIP check for Infiquetra project boards
---

Show current status for an Infiquetra project board, including WIP counts, aging items,
and blockers.

## Usage

```
/sdlc-board [jeff-intent|asgard|mount-olympus]
```

## Arguments

- `mount-olympus` - Show Olympus engineering execution board (default)
- `asgard` - Show Asgard rapid-action/incubation board
- `jeff-intent` - Show Jeff's intent and shaping board

## What This Does

1. Fetches items from the selected GitHub Project.
2. Groups items by schema-backed Status.
3. Shows WIP counts and violations where configured.
4. Flags aging and blocked items.
5. Keeps deployment state separate from workflow Status.

## Examples

```
/sdlc-board
/sdlc-board mount-olympus
/sdlc-board asgard
/sdlc-board jeff-intent
```

## Script Commands

```bash
SCRIPT=~/.claude/plugins/cache/infiquetra-plugins/sdlc-manager/1.5.0/scripts/sdlc_manager.py

python3 $SCRIPT board view --project mount-olympus
python3 $SCRIPT board wip --project mount-olympus
```

Replace `mount-olympus` with `asgard` or `jeff-intent` for those boards.

## Instructions

When the user invokes `/sdlc-board [project]`:

1. Determine target project, defaulting to `mount-olympus`.
2. Run `board view --project <project>`.
3. Run `board wip --project <project>`.
4. Summarize items by status, WIP violations, blockers, and aging work.
5. Suggest concrete follow-up actions when useful: standup prep, move cards, or dry-run archive.

Use the `sdlc-board` skill for detailed board operations or the `sdlc-operator` agent for
multi-step workflows.
