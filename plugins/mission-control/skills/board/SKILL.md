---
name: board
description: |
  Manage the Infiquetra GitHub Projects boards: Jeff Intent, Asgard, and Mount Olympus.
  Handles board views, status moves, item adds, terminal-item archive, WIP analysis,
  field discovery, and standup preparation.
when_to_use: |
  Use this skill when the user wants to:

  Board review and status:
  - Review or view Jeff Intent, Asgard, or Mount Olympus board state
  - Check overall board health or get a snapshot of current work
  - See what's in a specific status, such as Shaping, Active, Assigned, or In Review

  Moving items between statuses:
  - Move an issue to a different board status
  - Update an issue's board status after shaping, implementation, review, or verification

  Adding items to boards:
  - Add an issue or PR to its default repo-mapped board
  - Add an issue or PR to a specific board with --project

  Archiving and cleanup:
  - Archive terminal workflow items after reviewing a dry run
  - Remove stale completed items from active board views

  WIP analysis and standup:
  - Check WIP limits and bottlenecks
  - Generate a right-to-left standup or board-review summary
  - Identify blocked or aging work
---

# SDLC Board

Manage Infiquetra's current project boards:

| Project key | Board | Workflow |
|-------------|-------|----------|
| `jeff-intent` | Jeff Intent | `Idea -> Shaping -> Ready -> Active -> Verify -> Done` |
| `asgard` | Asgard | `Idea -> Shaping -> Ready -> Active -> Verify -> Done` |
| `mount-olympus` | Olympus | `Backlog -> Ready -> Planning -> Assigned -> In Review -> Done / Closed` |

Olympus still has a live `In Progress` Status option. Treat it as a live legacy option:
show it when present, but prefer `Assigned` for new movement. Deployment state is not a
workflow status; use deployment fields and GitHub Deployments/Environments for environment
movement.

## Script Location

```bash
$INFIQUETRA_SDLC_PATH/../infiquetra-claude-plugins/plugins/mission-control/scripts/sdlc_manager.py
```

If `$INFIQUETRA_SDLC_PATH` is unset, use `~/workspace/infiquetra/infiquetra-sdlc` as the default base path.
Always run the script with `python3`.

## Core Operations

### View Board

```bash
# View a board by status
python3 sdlc_manager.py board view --project jeff-intent
python3 sdlc_manager.py board view --project asgard
python3 sdlc_manager.py board view --project mount-olympus

# Filter to a specific status
python3 sdlc_manager.py board view --project asgard --status "Active"
python3 sdlc_manager.py board view --project mount-olympus --status "Assigned"
```

### Add Item

```bash
# Add an issue or PR to the default repo-mapped board
python3 sdlc_manager.py board add --repo infiquetra-sdlc --number 42

# Add an item to a specific board
python3 sdlc_manager.py board add --project asgard --repo infiquetra-sdlc --number 42
python3 sdlc_manager.py board add --project jeff-intent --repo infiquetra-sdlc --number 42
```

### Move Item

```bash
# Intent-flow boards
python3 sdlc_manager.py board move --project asgard --repo infiquetra-sdlc --number 42 --status "Active"
python3 sdlc_manager.py board move --project jeff-intent --repo infiquetra-sdlc --number 42 --status "Shaping"

# Olympus engineering flow
python3 sdlc_manager.py board move --repo athena-service --number 42 --status "Assigned"
python3 sdlc_manager.py board move --repo athena-service --number 42 --status "In Review"
python3 sdlc_manager.py board move --repo athena-service --number 42 --status "Done"
```

Use `board discover-fields` when unsure which Status options exist live.

### Archive Terminal Items

```bash
# Always preview first
python3 sdlc_manager.py board archive --project mount-olympus --dry-run
python3 sdlc_manager.py board archive --project asgard --dry-run

# Run only after operator confirmation
python3 sdlc_manager.py board archive --project mount-olympus
```

The command archives terminal workflow items. For Jeff Intent and Asgard that means `Done`.
For Olympus that means `Done`, `Closed`, `Cancelled`, plus legacy `Deployed` if old cards still carry it.

### WIP And Standup

```bash
python3 sdlc_manager.py board wip --project mount-olympus
python3 sdlc_manager.py board wip --project asgard
python3 sdlc_manager.py board standup --project mount-olympus
python3 sdlc_manager.py board standup --project jeff-intent
```

Standup output walks each board right-to-left using the schema-backed workflow order.

### Discover Fields

```bash
python3 sdlc_manager.py board discover-fields --project mount-olympus
python3 sdlc_manager.py board discover-fields --project asgard
python3 sdlc_manager.py board discover-fields --project jeff-intent
```

## WIP Limits Reference

| Board | Status | Limit |
|-------|--------|-------|
| Jeff Intent | Shaping | 10 |
| Jeff Intent | Ready | 10 |
| Jeff Intent | Active | 5 |
| Jeff Intent | Verify | 5 |
| Asgard | Shaping | 8 |
| Asgard | Ready | 8 |
| Asgard | Active | 5 |
| Asgard | Verify | 5 |
| Olympus | Ready | 10 |
| Olympus | Planning | 3 |
| Olympus | Assigned | 3 per assigned agent |
| Olympus | In Review | 5 |

When WIP is exceeded, stop pulling new work on that board and focus on finishing, swarming,
or moving blocked cards to the right pause state.

## Natural Language Examples

**"Review the Asgard board"**
-> `board view --project asgard`

**"Move issue #42 in infiquetra-sdlc to Active on Asgard"**
-> `board move --project asgard --repo infiquetra-sdlc --number 42 --status "Active"`

**"Add this issue to Jeff Intent"**
-> Confirm repo and issue number, then `board add --project jeff-intent --repo <repo> --number <N>`

**"Are we over WIP limits?"**
-> Run `board wip` for the relevant board.

**"Let's prep for standup"**
-> `board standup --project mount-olympus` or the requested board.

## Reference Documents

- `references/kanban-workflow.md` - Board structure, status definitions, WIP limits, and standup format
- `references/graphql-queries.md` - GraphQL queries used by the script
