---
name: sdlc-create
description: Interactive SDLC issue creation with template guidance, auto-labeling, and project board integration
---

Create a new SDLC issue in any Infiquetra repository with guided template selection, automatic label application, and project board integration.

## Usage

```
/sdlc-create [type] [--repo repository-name]
```

## Arguments

- `type` — Optional issue type: `capability`, `enhancement`, `defect`, `exploration`, `context-update`, `objective`
- `--repo` — Optional repository name (without org prefix)

## What This Does

1. Guides you through issue type selection using the decision tree (if type not specified)
2. Asks for the target repository (any Infiquetra repo)
3. Walks through required template fields for the selected type
4. Creates the issue via `gh issue create`
5. Automatically applies appropriate labels
6. Adds to project board (if repo is mapped)
7. Syncs initiative/objective labels to project fields
8. Creates milestone (for Objective type)

## Issue Type Decision Tree

```
Coordinating multiple capabilities with a target date? -> OBJECTIVE
Is it broken in production? -> DEFECT
New end-to-end deployable functionality? -> CAPABILITY
Improving existing functionality? -> ENHANCEMENT
Researching or investigating? -> EXPLORATION
Updating documentation? -> CONTEXT UPDATE
```

## Examples

```
/sdlc-create
/sdlc-create capability --repo athena-service
/sdlc-create defect --repo hermes-gateway
/sdlc-create objective --repo olympus-blueprint
/sdlc-create exploration
```

## Script Command

```bash
python3 ~/.claude/plugins/cache/infiquetra-plugins/sdlc-manager/1.0.0/scripts/sdlc_manager.py \
  issue create --repo athena-service --type capability
```

Then add to project:
```bash
python3 ~/.claude/plugins/cache/infiquetra-plugins/sdlc-manager/1.0.0/scripts/sdlc_manager.py \
  board add --repo athena-service --number <new-issue-number>
```

## Instructions

When the user invokes `/sdlc-create`:

1. If no type given, walk through the decision tree with the user
2. If no repo given, ask which Infiquetra repo this belongs to
3. Use `sdlc-issues` skill to guide the issue creation
4. After creation, automatically:
   - Apply type label + status label (needs-analysis for capabilities/enhancements, needs-triage for defects)
   - Run auto-label rules against title/body
   - Add to project board if repo is mapped
   - Sync initiative/objective labels to project fields
5. For Objectives: also create a GitHub Milestone
6. Show summary of everything created/applied

If user provides partial info (just "create a defect about the auth timeout"), infer:
- Type: defect
- Suggest appropriate repo or ask to confirm
- Pre-fill: title based on description

Use the `sdlc-operator` agent for batch issue creation or complex multi-repo scenarios.
