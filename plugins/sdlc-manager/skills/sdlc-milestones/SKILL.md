---
name: sdlc-milestones
description: |
  Manage GitHub Milestones for Infiquetra Objectives. Creates, lists, and tracks progress on
  milestones across Infiquetra repositories. Handles the full Objective lifecycle: creation,
  Capability linking, progress tracking, risk assessment, cross-repo coordination, and completion.
  Objectives are tracked as both GitHub Milestones and Beads parent tasks.
when_to_use: |
  Use this skill when the user wants to:

  Creating objectives and milestones:
  - "create an objective for the platform launch", "set up a new objective",
    "we're starting a new pilot program", "create a milestone for this objective"
  - "let's set up the v1.0 release milestone"
  - "create a program milestone for Q1 KR1"

  Progress and status:
  - "how's the platform-launch going", "objective progress",
    "milestone completion", "what's the status of the platform MVP"
  - "how many capabilities have been deployed toward this objective"
  - "are we on track for the release date"

  Milestone management:
  - "when is this objective due", "list all open milestones",
    "show me objectives for infiquetra-core"
  - "which milestones are at risk", "show upcoming deadlines"

  Linking issues to objectives:
  - "add this capability to the platform-launch objective",
    "link issue #42 to the platform MVP milestone",
    "assign this to the current objective"

  Completion and review:
  - "mark this objective as complete", "close the milestone",
    "show me all active objectives", "which objectives are at risk"
---

# SDLC Milestones

Manage GitHub Milestones for Infiquetra Objectives. Covers the full Objective lifecycle from
creation through completion, including progress tracking and cross-repo coordination.

## Script Location

```
$INFIQUETRA_SDLC_PATH/../infiquetra-claude-plugins/plugins/sdlc-manager/scripts/sdlc_manager.py
```

> If `$INFIQUETRA_SDLC_PATH` is unset, use `~/workspace/infiquetra/infiquetra-sdlc` as the default base path.

## Core Operations

### Create Milestone

```bash
python3 sdlc_manager.py milestones create \
  --repo infiquetra-core \
  --title "Pilot: Platform Launch" \
  --due-date 2026-04-15 \
  --description "Platform launch pilot — validate core workflows with early adopters"
```

The `--title` should follow the naming convention (see below). The `--description` can be brief;
full details live in the Objective issue.

### List Milestones

```bash
# List open milestones
python3 sdlc_manager.py milestones list --repo infiquetra-core

# List all (open and closed)
python3 sdlc_manager.py milestones list --repo infiquetra-core --state all

# List closed milestones
python3 sdlc_manager.py milestones list --repo infiquetra-core --state closed
```

### Track Progress

```bash
# Show completion % for a specific milestone
python3 sdlc_manager.py milestones progress --repo infiquetra-core --milestone 3
```

Output shows: total issues, open issues, closed issues, completion %, and due date.
Issues are from all types linked to the milestone (Capabilities, Enhancements, Defects).

### Link Issue to Milestone

```bash
# Link a capability to its parent objective milestone
python3 sdlc_manager.py milestones link \
  --repo infiquetra-core \
  --issue 42 \
  --milestone 3
```

Also do this via gh CLI:
```bash
gh issue edit 42 --repo Infiquetra/infiquetra-core --milestone "Pilot: Platform Launch"
```

## Naming Convention

### Milestone Title Format

```
{Type}: {Name} ({YYYY-MM-DD})
```

| Type | Example Milestone Title |
|------|------------------------|
| Pilot | `Pilot: Platform Launch (2026-04-15)` |
| MVP | `MVP: Core Integration (2026-02-28)` |
| Release | `Release: Olympus v1.0 (2026-05-30)` |
| Program | `Program: Q1 KR1 - User Adoption (2026-03-31)` |

### Label Format

The Objective issue gets a label `objective:{short-kebab-case}`:

| Milestone Title | Label |
|----------------|-------|
| `Pilot: Platform Launch (2026-04-15)` | `objective:platform-launch` |
| `Release: Olympus v1.0 (2026-05-30)` | `objective:olympus-v1` |
| `MVP: Core Integration (2026-02-28)` | `objective:core-integration` |
| `Program: Q1 KR1 - User Adoption (2026-03-31)` | `objective:q1-kr1` |

## Beads/Dolt Integration

Objectives are tracked in two systems:

1. **GitHub Milestones** — the backing store for progress tracking and issue linking
2. **Beads parent tasks** — the coordination layer for Mount Olympus agents

`bd` is the Beads/Dolt CLI for structured agent task coordination (see `docs/tools/index.md` for install instructions).

When creating an Objective:
```bash
# Create the Beads parent task
bd ready <objective-task-id>

# Child capabilities are Beads subtasks
bd claim <capability-task-id>  # An agent claims the capability
bd update <capability-task-id> in-progress
bd complete <capability-task-id>  # Syncs to GitHub Issue close
```

Beads tasks sync to GitHub Issues automatically. When a Beads subtask is completed,
the corresponding GitHub Issue is closed and the Milestone completion % updates.

## Objective Creation Workflow

When a user says "create an objective", run through these steps:

### Step 1: Create the Objective Issue

```bash
python3 sdlc_manager.py issue create --repo <repo> --type objective
```

Gather during template:
- Objective Name (descriptive, e.g., "Platform Launch MVP")
- Objective Type: Pilot / MVP / Release / Program
- Target Date (YYYY-MM-DD)
- Success Criteria (testable checkboxes)
- Included Capabilities list (even if not yet created)
- Stakeholders
- Risk Level

### Step 2: Create the GitHub Milestone

```bash
python3 sdlc_manager.py milestones create \
  --repo <repo> \
  --title "{Type}: {Name}" \
  --due-date {YYYY-MM-DD} \
  --description "{Brief description}"
```

Note the milestone number returned — you'll need it for linking.

### Step 3: Apply Labels to the Objective Issue

```bash
# Apply objective label
gh issue edit <N> --repo Infiquetra/<repo> --add-label "objective:{short-name}"

# Apply initiative label if applicable
gh issue edit <N> --repo Infiquetra/<repo> --add-label "initiative:{name}"
```

### Step 4: Link the Objective Issue to the Milestone

```bash
python3 sdlc_manager.py milestones link --repo <repo> --issue <N> --milestone <M>
```

### Step 5: Add to Project Board and Sync Fields

```bash
# Add to project board
python3 sdlc_manager.py board add --repo <repo> --number <N>

# Sync labels to project fields
python3 sdlc_manager.py labels sync-fields --repo <repo> --number <N>
```

### Step 6: Create Capabilities

Create individual Capability issues for the work inside the Objective.
For each capability:
1. `python3 sdlc_manager.py issue create --repo <repo> --type capability`
2. Apply `objective:{name}` and `initiative:{name}` labels
3. Link to the milestone: `milestones link --repo <repo> --issue <N> --milestone <M>`
4. Add to project board: `board add --repo <repo> --number <N>`

## Risk Assessment

Flag objectives as at-risk when:
- Due date is **< 7 days away** AND milestone completion is **< 80%**
- Any Capability in the milestone is **blocked**
- Capabilities are **aging in development** (> 3 days in In Development)

Check progress and calculate risk:
```bash
python3 sdlc_manager.py milestones progress --repo <repo> --milestone <N>
```

When flagging at-risk: surface the due date, current completion %, and identify which
specific issues are blocking progress.

## Cross-Repo Coordination

For Objectives that span multiple repositories:

1. **Create identical milestones in each affected repo**:
   ```bash
   python3 sdlc_manager.py milestones create \
     --repo infiquetra-core \
     --title "Pilot: Platform Launch (2026-04-15)" \
     --due-date 2026-04-15

   python3 sdlc_manager.py milestones create \
     --repo infiquetra-auth \
     --title "Pilot: Platform Launch (2026-04-15)" \
     --due-date 2026-04-15
   ```

2. **Apply consistent labels across all repos** — same `objective:*` and `initiative:*` labels

3. **Link each repo's Capability issues to its local milestone**

4. **Track aggregate progress** by checking progress across all repos:
   ```bash
   python3 sdlc_manager.py milestones progress --repo infiquetra-core --milestone <M>
   python3 sdlc_manager.py milestones progress --repo infiquetra-auth --milestone <M>
   ```

## Natural Language Examples

**"Create an objective for the platform launch"**
-> Run `issue create --type objective`, then `milestones create`, apply labels, link issue to milestone

**"How's the platform launch going?"**
-> Find the milestone number, run `milestones progress --repo <repo> --milestone <N>`

**"Add capability #42 to the platform-launch objective"**
-> Find milestone number for `objective:platform-launch`, then `milestones link --repo <repo> --issue 42 --milestone <M>`

**"Show me all active objectives"**
-> `milestones list --repo <repo>` for each active repo; look for open milestones

**"Which objectives are at risk?"**
-> Run progress for each open milestone, flag those with < 80% completion and < 7 days remaining

**"Mark the platform launch as complete"**
-> Close the GitHub milestone via gh CLI:
   ```bash
   gh api repos/Infiquetra/<repo>/milestones/<N> -X PATCH -f state=closed
   ```

**"Create a release milestone for Olympus v1.0"**
-> `milestones create --repo infiquetra-core --title "Release: Olympus v1.0" --due-date 2026-05-30`

## Objective Completion Criteria

An Objective is complete when:
- All Capabilities are in **Deployed** status on the board
- Success criteria in the Objective issue are validated
- GitHub Milestone is closed
- Beads parent task is marked complete (`bd complete <objective-task-id>`)

Completion checklist:
1. Confirm all linked Capabilities are Deployed
2. Review success criteria — mark each as complete
3. Close milestone: `gh api repos/Infiquetra/<repo>/milestones/<N> -X PATCH -f state=closed`
4. Update Objective issue with completion notes and close it
5. Notify stakeholders via #mount-olympus Discord channel

## Key Behaviors

- **Always create a milestone when creating an Objective** — the milestone is how progress is tracked
- **Milestone title includes the date** — format: `{Type}: {Name} ({YYYY-MM-DD})`
- **Issue label uses short-name** — format: `objective:{short-kebab-case}` (no date)
- **Cross-repo objectives** need milestones in every affected repo with identical titles
- **At-risk flag** triggers at < 7 days + < 80% completion — surface proactively
- **Capabilities are linked just-in-time** — 2-3 weeks before work starts, not all upfront
- **Beads parent tasks** mirror Objectives for agent coordination

## Reference Documents

- `references/objective-workflow.md` — Complete Objective lifecycle, types, sizing, and examples
