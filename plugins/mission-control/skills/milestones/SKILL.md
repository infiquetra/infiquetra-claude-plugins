---
name: milestones
description: |
  Manage GitHub Milestones for Infiquetra Objectives. Creates, lists, links, and tracks
  milestone progress when an Objective needs due-date rollup across one or more repos.
when_to_use: |
  Use this skill when the user wants to:

  Creating objectives and milestones:
  - "create an objective for the platform launch", "set up a new objective"
  - "create a milestone for this objective", "set up the v1.0 release milestone"

  Progress and status:
  - "objective progress", "milestone completion", "are we on track for the release date"

  Milestone management:
  - "when is this objective due", "list all open milestones"
  - "which milestones are at risk", "show upcoming deadlines"

  Linking issues to objectives:
  - "link issue #42 to the platform MVP milestone"
  - "assign this to the current objective"
---

# SDLC Milestones

Manage GitHub Milestones as an optional Objective progress surface. The canonical hierarchy
is still Initiative -> Objective -> work item, with Initiative and Objective represented as
project fields when the board exposes them. Milestones are useful for repo-level due dates,
GitHub progress rollups, and release coordination.

## Script Location

```bash
$INFIQUETRA_SDLC_PATH/../infiquetra-claude-plugins/plugins/mission-control/scripts/sdlc_manager.py
```

If `$INFIQUETRA_SDLC_PATH` is unset, use `~/workspace/infiquetra/infiquetra-sdlc` as the default base path.
Always run the script with `python3`.

## Core Operations

### Create Milestone

```bash
python3 sdlc_manager.py milestones create \
  --repo infiquetra-core \
  --title "Pilot: Platform Launch (2026-04-15)" \
  --due-date 2026-04-15 \
  --description "Validate core workflows with early adopters"
```

### List Milestones

```bash
python3 sdlc_manager.py milestones list --repo infiquetra-core
python3 sdlc_manager.py milestones list --repo infiquetra-core --state all
python3 sdlc_manager.py milestones list --repo infiquetra-core --state closed
```

### Track Progress

```bash
python3 sdlc_manager.py milestones progress --repo infiquetra-core --milestone 3
```

Progress uses GitHub's open/closed issue counts for issues linked to that milestone.

### Link Issue To Milestone

```bash
python3 sdlc_manager.py milestones link \
  --repo infiquetra-core \
  --issue 42 \
  --milestone 3
```

Equivalent gh CLI:

```bash
gh issue edit 42 --repo infiquetra/infiquetra-core --milestone "Pilot: Platform Launch (2026-04-15)"
```

## Naming Convention

Milestone title:

```text
{Type}: {Name} ({YYYY-MM-DD})
```

| Type | Example |
|------|---------|
| Pilot | `Pilot: Platform Launch (2026-04-15)` |
| MVP | `MVP: Core Integration (2026-02-28)` |
| Release | `Release: Olympus v1.0 (2026-05-30)` |
| Program | `Program: Q1 KR1 - User Adoption (2026-03-31)` |

## Objective Creation Workflow

1. Create the Objective issue.
2. Create the GitHub Milestone if due-date rollup is useful.
3. Add the Objective issue to the target board.
4. Set `Initiative`, `Objective`, and `Status` project fields when those fields exist.
5. Create child work items just in time.
6. Link child issues as native GitHub sub-issues and, when useful, to the milestone.

Example field update:

```bash
python3 sdlc_manager.py flow set-field --project mount-olympus \
  --repo <repo> --number <N> \
  --field Objective --option "<Objective name>"
```

## Risk Assessment

Flag Objectives as at-risk when:

- Due date is less than 7 days away and milestone completion is below 80%.
- Any linked work item is blocked.
- Linked work is aging in `Assigned`, `In Review`, `Active`, or `Verify`.
- A required Jeff decision is still in `Needs Question` or equivalent state.

Check progress:

```bash
python3 sdlc_manager.py milestones progress --repo <repo> --milestone <N>
```

## Cross-Repo Coordination

For Objectives spanning multiple repositories:

1. Create matching milestone titles in each affected repo when milestone rollup is useful.
2. Use the same Objective project field option across boards where available.
3. Link each repo's work items to its local milestone.
4. Use native sub-issues for parent/child structure.
5. Track aggregate progress through project fields plus per-repo milestone progress.

## Objective Completion Criteria

An Objective is complete when:

- Linked work items are in a terminal workflow status (`Done`, `Closed`, or equivalent).
- Success criteria in the Objective issue are validated.
- No critical/high defects remain open against the Objective.
- The GitHub Milestone is closed if one was created.
- The Objective issue has completion notes and is closed.

## Natural Language Examples

**"Create an objective for the platform launch"**
-> Create the Objective issue, create a milestone if useful, add to board, and set fields.

**"How's the platform launch going?"**
-> Find the milestone number and run `milestones progress`.

**"Add capability #42 to the platform-launch objective"**
-> Set the Objective field, link as a sub-issue, and link to the milestone if one exists.

**"Which objectives are at risk?"**
-> Run progress for each open milestone and check linked board status / WIP age.

## Reference Documents

- `references/objective-workflow.md` - Objective lifecycle, types, sizing, and examples
