---
name: sdlc-board
description: |
  Manage the Infiquetra Mount Olympus GitHub Projects board. Handles viewing board state,
  moving issues between columns, adding items to projects, archiving deployed items,
  WIP limit analysis, and standup preparation.
when_to_use: |
  Use this skill when the user wants to:

  Board review and status:
  - Review or view the project board ("review the mount-olympus board", "show me the project board",
    "let's look at the board", "board status", "what's on the board")
  - Check overall board health or get a snapshot of current work
  - See what's in a specific column ("what's in E2E Testing", "show me deployment ready items")

  Moving items between columns:
  - Move an issue to a different board column ("move this issue to testing",
    "move #42 to deployment ready", "advance this to E2E testing", "push this to In Development",
    "mark this as deployed")
  - Update an issue's board status after code review or testing is complete

  Adding items to the board:
  - Add an issue or PR to the project ("add this to the project", "put this on the board",
    "add issue #42 to mount-olympus")

  Archiving and cleanup:
  - Archive items that have been deployed ("archive deployed items", "clean up the board",
    "archive old deployed issues", "run board cleanup")
  - Remove stale or completed items

  WIP analysis and capacity:
  - Check WIP limit status ("are we over WIP limits", "how's our WIP", "capacity check",
    "are we within limits", "WIP analysis")
  - Identify bottlenecks caused by columns exceeding their limits

  Standup preparation:
  - Generate a standup summary ("standup prep", "daily standup summary",
    "prepare the standup", "what's in progress", "standup report")
  - Get a right-to-left board review for the daily standup

  General board health:
  - "what's blocked", "what's aging", "stale items", "items over WIP",
    "what's been sitting in development too long", "flag aging issues"
---

# SDLC Board

Manage the Infiquetra Mount Olympus project board: view board state, move items, add issues,
archive deployed work, check WIP limits, and prepare standup summaries.

## Script Location

```
$INFIQUETRA_SDLC_PATH/../infiquetra-claude-plugins/plugins/sdlc-manager/scripts/sdlc_manager.py
```

> If `$INFIQUETRA_SDLC_PATH` is unset, use `~/workspace/infiquetra/infiquetra-sdlc` as the default base path.

**IMPORTANT**: Always use `python3` (not `python`) to run the script.

## Project

| Project | Team |
|---------|------|
| mount-olympus | Mount Olympus (all Infiquetra repos) |

## Core Operations

### View Board

```bash
# View full board (all columns)
python3 sdlc_manager.py board view --project mount-olympus

# Filter to a specific column
python3 sdlc_manager.py board view --project mount-olympus --status "In Development"

# JSON output for programmatic use
python3 sdlc_manager.py board view --project mount-olympus --format json
```

#### Sample Output

```
Mount Olympus Board — 12 items

Ready (3/10):
  #45 [capability] Implement OAuth2 flow          (infiquetra-auth, 1d)
  #52 [enhancement] Add rate limiting              (infiquetra-core, 0d)
  #58 [defect]      Fix token refresh crash        (infiquetra-auth, 0d) [critical]

In Development (4/9 — WIP OK):
  #38 [capability] User onboarding service         (infiquetra-core, 3d) ⚠ aging
  #41 [capability] Admin dashboard API             (infiquetra-core, 1d)
  #49 [enhancement] Improve error messages         (infiquetra-auth, 2d)
  #51 [defect]      Fix pagination off-by-one      (infiquetra-core, 0d)

E2E Testing (2/3):
  #33 [capability] Notification service            (infiquetra-core, 1d)
  #36 [enhancement] Cache invalidation             (infiquetra-core, 0d)

Deployment Ready (1/5):
  #29 [capability] Audit log export                (infiquetra-core, 0d)

Deployed (2):
  #25 [capability] Search API v2                   (infiquetra-core, 5d)
  #27 [enhancement] Compression middleware         (infiquetra-core, 3d)
```

### Move Item to Column

```bash
# Move an issue to a different board column
python3 sdlc_manager.py board move --repo infiquetra-core --number 42 --status "E2E Testing"
python3 sdlc_manager.py board move --repo infiquetra-core --number 42 --status "Deployment Ready"
python3 sdlc_manager.py board move --repo infiquetra-core --number 42 --status "Deployed"
python3 sdlc_manager.py board move --repo infiquetra-core --number 42 --status "In Development"
python3 sdlc_manager.py board move --repo infiquetra-core --number 42 --status "Ready"
```

Valid status values: `Ready`, `In Development`, `E2E Testing`, `Deployment Ready`, `Deployed`

### Add Item to Project

```bash
# Add an issue or PR to the project based on repo mapping
python3 sdlc_manager.py board add --repo infiquetra-core --number 42
```

The script auto-detects which project a repo belongs to.

### Archive Deployed Items

```bash
# Dry run — preview what would be archived
python3 sdlc_manager.py board archive --project mount-olympus --dry-run

# Archive items that have been in Deployed status for 2+ weeks
python3 sdlc_manager.py board archive --project mount-olympus
```

### WIP Analysis

```bash
# Check WIP limits across all columns
python3 sdlc_manager.py board wip --project mount-olympus
```

Output shows current WIP vs. limit for each column, flags any violations.

### Standup Preparation

```bash
# Generate right-to-left board summary for standup
python3 sdlc_manager.py board standup --project mount-olympus
```

Output walks Deployed -> Deployment Ready -> E2E Testing -> In Development -> Ready,
flagging blocked items, aging items, and WIP violations.

### Discover Project Fields

```bash
# Inspect available fields and options on the board
python3 sdlc_manager.py board discover-fields --project mount-olympus
```

Useful when status options or field IDs need verification.

## WIP Limits Reference

| Column | WIP Limit | Notes |
|--------|-----------|-------|
| Ready | 10 | Buffer for capacity matching |
| In Development | 3 per developer | Dynamic: team size x 3 |
| E2E Testing | 3 | Manual testing capacity |
| Deployment Ready | 5 | Deployment window constraint |
| Deployed | Unlimited | Auto-archive after 2 weeks |

When In Development is over WIP: stop pulling new work, swarm on finishing existing items.
Critical defects can temporarily bypass WIP limits.

## Strategic Direction Board

The `strategic` project provides a high-level view of Objectives and Initiatives — distinct
from the day-to-day Kanban board used for Capabilities.

```bash
# View the strategic direction board
python3 sdlc_manager.py board view --project strategic
```

### Columns

| Column | Purpose |
|--------|---------|
| Backlog | Objectives and Initiatives under consideration but not yet committed |
| This Quarter | Committed for the current quarter — actively being planned or staffed |
| In Flight | Actively being executed — Capabilities flowing through the Kanban board |
| Shipped | Completed Objectives — all Capabilities deployed, milestone closed |

### Key Differences from the Kanban Board

- **Items are Objectives and Initiatives**, not Capabilities
- **No per-agent WIP limits** — strategic items are coordination constructs, not developer work
- **Progress is measured by Milestone completion %**, not column dwell time
- **Movement is quarterly**, not daily — items move during planning ceremonies

### Interpretation Rules

- **Backlog items** are candidates for next quarter — review during quarterly planning
- **This Quarter items** should each have a GitHub Milestone with a due date
- **In Flight items** should have active Capabilities on the Kanban board
- **Shipped items** should have closed Milestones and completed Beads parent tasks
- If an In Flight Objective has < 80% completion with < 7 days to due date, flag as at-risk

## Beads/Dolt Integration

The Mount Olympus team uses Beads/Dolt as the primary coordination layer. Board status
syncs with Beads task status:

```bash
# When moving an item on the board, also update in Beads
bd update <task-id> in-development
bd update <task-id> testing
bd update <task-id> deployed
```

Beads tasks automatically sync to GitHub Issues, so board moves triggered via Beads
will reflect on the GitHub Projects board.

## Natural Language Examples

**"Review the mount-olympus board"**
-> `board view --project mount-olympus`

**"Move issue #42 in infiquetra-core to E2E testing"**
-> `board move --repo infiquetra-core --number 42 --status "E2E Testing"`

**"Add this issue to the project"**
-> Confirm repo and issue number, then: `board add --repo <repo> --number <N>`

**"Archive deployed items"**
-> `board archive --project mount-olympus --dry-run` (confirm first), then without `--dry-run`

**"Are we over WIP limits?"**
-> `board wip --project mount-olympus`

**"Let's prep for standup"**
-> `board standup --project mount-olympus`

**"What's been aging in development?"**
-> `board view --project mount-olympus --status "In Development"` and flag items > 3 days

**"What's blocked?"**
-> `board view --project mount-olympus` — look for items with `blocked` label

## Key Behaviors

- **Items aging >3 days in In Development** should be flagged proactively when viewing the board
- **Items aging >2 days in E2E Testing** should be flagged as potentially stale
- **Blocked items** (with `blocked` label) get special attention in standup output
- **Critical defects** bypass the Ready queue — they can be pulled directly to In Development
- **Standup order**: right-to-left — Deployed -> Deployment Ready -> E2E Testing -> In Development -> Ready

## Workflow Examples

### Example 1: Daily Standup Preparation

```bash
# Generate standup summary
python3 sdlc_manager.py board standup --project mount-olympus
```

Review output right-to-left. For each column: note items that are blocked, aging,
or causing bottlenecks. Share summary in #mount-olympus Discord channel.

### Example 2: End-of-Sprint Board Cleanup

```bash
# 1. Preview items that would be archived
python3 sdlc_manager.py board archive --project mount-olympus --dry-run

# 2. Confirm with user, then archive
python3 sdlc_manager.py board archive --project mount-olympus
```

### Example 3: Moving a Feature Through the Board

```bash
# Developer finishes work and creates PR
python3 sdlc_manager.py board move --repo infiquetra-core --number 42 --status "E2E Testing"

# E2E testing passes
python3 sdlc_manager.py board move --repo infiquetra-core --number 42 --status "Deployment Ready"

# Deployed to production
python3 sdlc_manager.py board move --repo infiquetra-core --number 42 --status "Deployed"
```

## Reference Documents

- `references/kanban-workflow.md` — Board structure, column definitions, WIP limits, standup format
- `references/graphql-queries.md` — GraphQL queries used by the script (developer reference)
