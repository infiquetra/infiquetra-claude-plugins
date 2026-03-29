---
name: sdlc-triage
description: Triage an existing GitHub issue with label recommendations, priority assessment, and project board placement
---

Triage an existing issue by analyzing its content, recommending appropriate labels and priority, adding it to the project board, and moving it to the correct status.

## Usage

```
/sdlc-triage repo#number
```

## Arguments

- `repo#number` — Repository and issue number, e.g., `athena-service#42`

## What This Does

1. Reads the issue content (title, body, existing labels)
2. Recommends issue type label if missing
3. Recommends priority label for defects
4. Recommends initiative/objective labels based on context
5. Applies auto-label rules
6. Adds to project board if not already there
7. Syncs project field values from labels
8. Recommends initial board status (Ready if context complete, stays in analysis if missing context)

## Examples

```
/sdlc-triage athena-service#42
/sdlc-triage hermes-gateway#15
/sdlc-triage apollo-engine#89
```

## Script Commands

```bash
SCRIPT=~/.claude/plugins/cache/infiquetra-plugins/sdlc-manager/1.0.0/scripts/sdlc_manager.py

# Auto-label based on content
python3 $SCRIPT labels auto-label --repo athena-service --number 42

# Add to project
python3 $SCRIPT board add --repo athena-service --number 42

# Sync fields after labeling
python3 $SCRIPT labels sync-fields --repo athena-service --number 42
```

## Instructions

When the user invokes `/sdlc-triage repo#number`:

1. Parse repo and number from the argument (format: `repo#number` or `repo #number`)
2. Fetch issue via `gh issue view <number> --repo infiquetra/<repo> --json title,body,labels`
3. Analyze content:
   - Is there already a type label? If not, recommend one using the decision tree
   - Is it a defect without a priority? Ask user for priority (critical/high/medium/low)
   - Does title/body mention an initiative or objective? Suggest those labels
4. Apply auto-label rules:
   - `python3 $SCRIPT labels auto-label --repo <repo> --number <N>`
5. Manually apply recommended labels:
   - `gh issue edit <N> --repo infiquetra/<repo> --add-label "capability,needs-analysis"`
6. Add to project board:
   - `python3 $SCRIPT board add --repo <repo> --number <N>`
7. Sync initiative/objective fields:
   - `python3 $SCRIPT labels sync-fields --repo <repo> --number <N>`
8. Recommend status:
   - Defect (critical/high): Move directly to In Development
   - Has complete context: Ready
   - Needs more context: Add `needs-analysis` label, leave in backlog
9. Show summary of all actions taken

If the issue is a defect with `critical` label, flag urgency: "This is a critical defect with a 4-hour SLA. Moving to In Development now."

Use the `sdlc-operator` agent for batch triage of multiple issues.
