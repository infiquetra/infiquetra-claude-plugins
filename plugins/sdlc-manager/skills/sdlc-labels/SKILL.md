---
name: sdlc-labels
description: |
  Manage GitHub labels and project board field synchronization for Infiquetra repositories.
  Handles applying SDLC labels to issues, syncing initiative/objective labels to project board
  fields, auditing repos for missing labels, deploying the full label taxonomy, auto-labeling
  issues based on title/body patterns, and creating new field options when new initiatives or
  objectives are introduced.
when_to_use: |
  Use this skill when the user wants to:

  Applying labels to issues:
  - Apply a label to an issue ("label this issue", "add the capability label",
    "tag this as high priority", "mark this as an enhancement", "add the blocked label")
  - Set or correct issue type, priority, or status labels

  Syncing project board fields from labels:
  - Sync board fields after labels change ("sync the initiative field",
    "the objective field doesn't match the label", "sync fields for this issue",
    "update the board field to match the label")
  - Ensure initiative:* and objective:* labels are reflected in project board single-select fields

  Assigning initiatives and objectives:
  - "this belongs to olympus-v1", "assign to the platform-launch objective",
    "this issue is part of the core-platform initiative", "tag this with the Q1 objective"
  - Adding initiative:* or objective:* labels and syncing the corresponding board fields

  Auditing label coverage:
  - "check if this repo has all the SDLC labels", "audit labels on infiquetra-core",
    "what labels are missing from this repo", "run a label audit"
  - Comparing repo labels against the canonical SDLC label set

  Deploying labels to repos:
  - "push labels to this repo", "sync labels from the SDLC config",
    "deploy the SDLC labels to this repo", "set up labels on a new repo"
  - Creating or updating repo labels to match `labels.json`

  Auto-labeling based on content:
  - "auto-label this issue based on its content", "apply labels based on the title",
    "run auto-label rules on issue #42"
  - Pattern matching against issue title and body to apply appropriate labels

  Adding new initiatives or objectives:
  - "we have a new initiative", "add a new objective to the board",
    "create a new initiative option called platform-stability",
    "add platform-launch as a new objective"
  - Creating new single-select options on the project board for new initiatives/objectives

  Field discovery:
  - "what fields does the mount-olympus board have", "show me the board fields",
    "discover project fields"
---

# SDLC Labels

Manage Infiquetra issue labels and synchronize them with the GitHub Projects board fields.

## Script Location

```
$INFIQUETRA_SDLC_PATH/../infiquetra-claude-plugins/plugins/sdlc-manager/scripts/sdlc_manager.py
```

> If `$INFIQUETRA_SDLC_PATH` is unset, use `~/workspace/infiquetra/infiquetra-sdlc` as the default base path.

## Core Operations

### Sync Label Fields to Project Board

When initiative or objective labels are applied to an issue, the corresponding project board
single-select fields must be updated to match.

```bash
# Sync initiative/objective labels -> project board fields for an issue
python3 sdlc_manager.py labels sync-fields --repo infiquetra-core --number 42
```

This reads the issue's current labels, finds any `initiative:*` or `objective:*` labels, and
updates the corresponding single-select fields on the mount-olympus project.

### Audit Repo Labels

Check whether a repository has all required SDLC labels defined:

```bash
python3 sdlc_manager.py labels audit --repo infiquetra-core
```

Output shows: present labels, missing labels, and extra (non-SDLC) labels.

### Deploy Labels to Repo

Create or update a repo's labels to match the canonical SDLC label set from `labels.json`:

```bash
python3 sdlc_manager.py labels deploy --repo infiquetra-core
```

Safe to re-run — creates missing labels, updates color/description on existing ones,
does not delete extra labels.

### Auto-Label an Issue

Apply labels based on pattern matching against the issue title and body:

```bash
python3 sdlc_manager.py labels auto-label --repo infiquetra-core --number 42
```

See auto-label rules in `references/labels-reference.md`. Common patterns: `[CAPABILITY]` in
title adds `capability` + `needs-analysis`; `[DEFECT]` adds `defect` + `needs-triage`.

### Create a New Field Option

When a new initiative or objective is introduced, create the corresponding option on the
project board's single-select field:

```bash
# Add a new initiative option to the board
python3 sdlc_manager.py fields create-option --project mount-olympus --field initiative --option "platform-stability"

# Add a new objective
python3 sdlc_manager.py fields create-option --project mount-olympus --field objective --option "platform-launch"
```

### Discover Project Fields

```bash
python3 sdlc_manager.py fields discover --project mount-olympus
```

Shows all fields and their available options with IDs. Useful for confirming field names and
verifying that an initiative/objective option exists before trying to sync.

## Key Behaviors

### Label Rules

- **Every issue must have exactly ONE issue type label**: `capability`, `enhancement`,
  `defect`, `exploration`, or `context-update`
- **Defects must have exactly ONE priority label**: `critical`, `high-priority`,
  `medium-priority`, or `low-priority`
- **Other issue types**: priority is optional
- **AI usage labels**: Add when a PR is created — one per PR, tracks AI generation %
- **Size labels**: Add during Analysis phase — one per capability/enhancement
- **Risk labels**: Add during Analysis phase — one per capability
- **Status labels** (`ready`, `blocked`, `needs-analysis`, `needs-triage`): may be
  auto-managed as issues progress

### Initiative and Objective Synchronization

`initiative:*` and `objective:*` labels on an issue drive the project board's single-select
fields. Workflow:

1. Apply `initiative:olympus-v1` label to the issue
2. Run `labels sync-fields --repo <repo> --number <N>` to update the board field
3. The board's "Initiative" single-select field is updated to "olympus-v1"

When a new initiative or objective label is applied that doesn't yet exist as a board field
option, you must first create the option with `fields create-option`.

## Natural Language Examples

**"Label this issue as a capability"**
-> Apply `capability` label via `gh issue edit`

**"Add the high-priority label to defect #88"**
-> `gh issue edit 88 --add-label high-priority --repo Infiquetra/infiquetra-core`

**"This issue belongs to the Olympus v1 initiative"**
-> Apply `initiative:olympus-v1` label, then:
  `labels sync-fields --repo <repo> --number <N>`

**"Sync the initiative field for issue #42"**
-> `python3 sdlc_manager.py labels sync-fields --repo infiquetra-core --number 42`

**"Audit labels on infiquetra-core"**
-> `python3 sdlc_manager.py labels audit --repo infiquetra-core`

**"Deploy SDLC labels to a new repo"**
-> `python3 sdlc_manager.py labels deploy --repo infiquetra-new-service`

**"Auto-label issue #55 based on its title"**
-> `python3 sdlc_manager.py labels auto-label --repo infiquetra-core --number 55`

**"We have a new initiative called platform-stability — add it to the board"**
->
```bash
python3 sdlc_manager.py fields create-option --project mount-olympus --field initiative --option "platform-stability"
```

**"What fields does the mount-olympus board have?"**
-> `python3 sdlc_manager.py fields discover --project mount-olympus`

## Reference Documents

- `references/labels-reference.md` — Complete label taxonomy with colors, descriptions,
  auto-label rules, and usage rules
