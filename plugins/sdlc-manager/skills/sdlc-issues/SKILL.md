---
name: sdlc-issues
description: |
  Create and manage SDLC issues in Infiquetra GitHub repositories using the 6-type issue
  taxonomy: capability, enhancement, defect, exploration, context-update, and objective.
  Handles issue type selection, template-guided creation, label application, project board
  assignment, and milestone linking.
when_to_use: |
  Use this skill when the user wants to:

  Direct issue creation:
  - "create a capability", "create a defect for this bug", "let's create an objective",
    "file an enhancement", "open an exploration", "create a context update"
  - "create an issue in infiquetra-core", "file a bug against the auth service"
  - "create an issue of type capability", "I need to open a defect"

  Blueprint-driven creation:
  - "review the blueprint and create issues", "look at the blueprint and figure out what
    issues we need", "create issues for all the capabilities in this objective"
  - "based on the spec, what issues should we create?"

  Contextual issue creation:
  - "this needs to be tracked as a defect", "let's turn this into a capability issue"
  - "we should track this work", "open an issue for this"

  Issue type guidance:
  - "what type of issue should this be", "is this a capability or enhancement",
    "how should I categorize this work", "help me pick the right issue type"

  Batch creation:
  - "create issues for all the capabilities in this objective"
  - "set up the issues for the platform launch objective"
---

# SDLC Issues

Create and manage SDLC issues across Infiquetra repositories using the 6-type taxonomy.
Handles type selection, template-guided creation, label application, and project board assignment.

## Script Location

```
$INFIQUETRA_SDLC_PATH/../infiquetra-claude-plugins/plugins/sdlc-manager/scripts/sdlc_manager.py
```

> If `$INFIQUETRA_SDLC_PATH` is unset, use `~/workspace/infiquetra/infiquetra-sdlc` as the default base path.

## Issue Types

Six issue types cover all Infiquetra work:

| Type | Duration | When to Use |
|------|----------|-------------|
| **objective** | 2-8 weeks | Coordinating multiple capabilities with a target date |
| **capability** | 1-4 weeks | New end-to-end deployable functionality |
| **enhancement** | 2-5 days | Improving existing functionality |
| **defect** | Hours-2 days | Broken functionality in production |
| **exploration** | 1-3 days | Research, POC, or architectural investigation |
| **context-update** | Hours-1 day | Updating Blueprint repository documentation |

See `references/issue-types.md` for the complete guide and decision tree.

## Core Operations

### Create Issue with Template

```bash
# Launch interactive template for a specific issue type
python3 sdlc_manager.py issue create --repo infiquetra-core --type capability
python3 sdlc_manager.py issue create --repo infiquetra-auth --type defect
python3 sdlc_manager.py issue create --repo infiquetra-blueprint --type context-update

# Create via gh CLI directly (alternative)
gh issue create --repo Infiquetra/infiquetra-core --template capability.yml
```

After template creation, apply labels and add to project board (see below).

### Apply Labels

Labels are applied in two ways: auto-applied by the template, and manually added for context.

**Auto-applied by template** (from `.github/ISSUE_TEMPLATE/*.yml`):
- `capability` -> adds `capability`, `needs-analysis`
- `defect` -> adds `defect`, `needs-triage`
- `enhancement` -> adds `enhancement`, `needs-analysis`
- `exploration` -> adds `exploration`, `research`
- `context-update` -> adds `context-update`, `documentation`
- `objective` -> adds `objective`

**Auto-label rules** — apply additional labels based on content:
```bash
python3 sdlc_manager.py labels auto-label --repo <repo> --number <N>
```

Auto-label logic:
- `[CAPABILITY]` in title -> adds `capability`, `needs-analysis`
- `[DEFECT]` in title -> adds `defect`, `needs-triage`
- Mentions security/vulnerability/CVE -> adds `security`
- Mentions performance/latency -> adds `performance`
- Mentions breaking change -> adds `breaking-change`

**Apply labels manually** via gh CLI:
```bash
gh issue edit <N> --repo Infiquetra/<repo> --add-label "objective:platform-launch"
gh issue edit <N> --repo Infiquetra/<repo> --add-label "initiative:olympus-v1"
gh issue edit <N> --repo Infiquetra/<repo> --add-label "high-priority"
```

### Add to Project Board

```bash
# Auto-detect project from repo mapping and add
python3 sdlc_manager.py board add --repo infiquetra-core --number <N>
```

The script reads `project-mappings.json` from the infiquetra-sdlc config to determine which
project a repo belongs to.

**If the repo is unmapped**: warn the user and offer to add manually via the GitHub web UI.
Most new repos need to be added to `project-mappings.json` first.

### Sync Labels to Project Fields

After applying initiative/objective labels, sync them to the GitHub Projects custom fields:

```bash
python3 sdlc_manager.py labels sync-fields --repo <repo> --number <N>
```

This copies `initiative:*` and `objective:*` labels to the corresponding project board fields
so the issue appears in filtered views.

## Issue Creation Workflow

Follow these steps when creating any issue:

### Step 1: Determine Issue Type

Use the decision tree (see `references/issue-types.md`) or ask the user:
- Coordinating multiple capabilities with a target date? -> **OBJECTIVE**
- Something broken in production? -> **DEFECT**
- New end-to-end deployable functionality? -> **CAPABILITY**
- Improving existing functionality? -> **ENHANCEMENT**
- Researching or investigating? -> **EXPLORATION**
- Updating Blueprint documentation? -> **CONTEXT UPDATE**

If uncertain, present the decision tree and ask clarifying questions.

### Step 2: Choose Target Repository

Issue can be created in any Infiquetra repo. Common repos:
- `infiquetra-core`, `infiquetra-auth`, `infiquetra-infra`
- `infiquetra-blueprint` — for Context Updates and Explorations
- `infiquetra-claude-plugins`

If the user doesn't specify, ask which repo the work belongs to.

### Step 3: Gather Required Fields

Each issue type has required fields (see `references/templates-reference.md` for complete
field lists). At minimum:

- **Capability**: objective statement, business value, acceptance criteria, context links, size
- **Defect**: problem description, priority, steps to reproduce, impact
- **Enhancement**: what's being improved, current state, proposed improvement, acceptance criteria
- **Exploration**: research question, context, success criteria, timebox
- **Context Update**: what's being updated, why, files to update
- **Objective**: objective name, type, target date, success criteria

### Step 4: Create the Issue

```bash
# Interactive template (prompts for all fields)
python3 sdlc_manager.py issue create --repo <repo> --type <type>

# Or open gh CLI template directly
gh issue create --repo Infiquetra/<repo> --template <type>.yml
```

### Step 5: Apply Labels

1. Confirm template auto-applied type and status labels
2. Run auto-label to catch content-based labels:
   ```bash
   python3 sdlc_manager.py labels auto-label --repo <repo> --number <N>
   ```
3. Apply priority label if known: `critical`, `high-priority`, `medium-priority`
4. Apply objective label if part of an objective: `objective:platform-launch`
5. Apply initiative label if part of an initiative: `initiative:olympus-v1`

### Step 6: Add to Project Board

```bash
python3 sdlc_manager.py board add --repo <repo> --number <N>
```

Issue starts in **Backlog** (or **Ready** for defects with Critical/High priority).

### Step 7: Sync Fields and Link Milestone

```bash
# Sync initiative/objective labels to project fields
python3 sdlc_manager.py labels sync-fields --repo <repo> --number <N>

# If part of an objective, link to milestone
python3 sdlc_manager.py milestones link --repo <repo> --issue <N> --milestone <M>
```

### Step 8: Create Beads Task (if applicable)

For work that will be claimed by Mount Olympus agents:
```bash
# Mark the task as ready for agent claiming
bd ready <task-id>
```

Beads tasks sync to GitHub Issues automatically, so the issue will be tracked in both systems.

### Step 9: For Objectives — Create Milestone

When creating an Objective issue, also create a corresponding GitHub Milestone:

```bash
python3 sdlc_manager.py milestones create \
  --repo <repo> \
  --title "Pilot: Platform Launch" \
  --due-date 2026-04-15 \
  --description "Platform launch pilot objective"
```

Then link the Objective issue to the new milestone:
```bash
python3 sdlc_manager.py milestones link --repo <repo> --issue <N> --milestone <M>
```

See the `sdlc-milestones` skill for complete Objective/Milestone workflow.

## Natural Language Examples

**"Create a capability in infiquetra-core"**
-> `issue create --repo infiquetra-core --type capability`

**"File a defect for the auth API crashing"**
-> `issue create --repo infiquetra-auth --type defect` (gather steps to reproduce, priority)

**"Create an exploration to research biometric SDK options"**
-> `issue create --repo infiquetra-blueprint --type exploration`

**"Is this a capability or enhancement?"**
-> Walk through decision tree: Is it new end-to-end deployable functionality? If yes -> capability.
   If it improves existing functionality -> enhancement.

**"Create issues for all the capabilities in this objective"**
-> List capabilities from the objective description, create each with `--type capability`,
   link each to the objective milestone

**"What type of issue should this be?"**
-> Present the decision tree from `references/issue-types.md`

## Label Reference

### Type Labels
| Label | Color | Applied To |
|-------|-------|------------|
| `capability` | Green | Capability issues |
| `enhancement` | Blue | Enhancement issues |
| `defect` | Red | Defect issues |
| `exploration` | Purple | Exploration issues |
| `context-update` | Gray | Context Update issues |
| `objective` | Dark blue | Objective issues |

### Status Labels
| Label | Meaning |
|-------|---------|
| `needs-analysis` | Requires context gathering before development |
| `needs-triage` | Defect needs priority assessment |
| `blocked` | Cannot progress — dependency or blocker identified |
| `in-progress` | Actively being worked on |

### Priority Labels (Defects)
| Label | SLA |
|-------|-----|
| `critical` | 4 hours |
| `high-priority` | 1 day |
| `medium-priority` | 3 days |
| `low-priority` | When capacity |

### Content Labels
| Label | Applied When |
|-------|-------------|
| `security` | Security vulnerability or CVE |
| `performance` | Performance regression or optimization |
| `breaking-change` | API or interface breaking change |

### Hierarchy Labels
| Format | Example | Description |
|--------|---------|-------------|
| `objective:{name}` | `objective:platform-launch` | Parent objective |
| `initiative:{name}` | `initiative:olympus-v1` | Parent initiative |

## Key Behaviors

- **Always confirm issue type** before creating — wrong type causes downstream confusion
- **Defects with Critical priority** should be pulled directly to In Development, bypassing Ready
- **Every Capability should create a paired Context Update** to document what was built
- **Objectives auto-create a milestone** — don't skip this step
- **Unmapped repos** will warn on board add — this is expected for newer repos

## Reference Documents

- `references/issue-types.md` — Complete guide to all 6 issue types with decision tree
- `references/templates-reference.md` — Rendered view of all 6 issue templates with examples
