# sdlc-manager

SDLC management for Infiquetra's Jeff Intent, Asgard, and Mount Olympus boards. This plugin provides a complete interface for managing the development lifecycle — from issue creation to flow metrics — reading board and workflow configuration from `infiquetra-sdlc` and vendored fallbacks.

## Overview

All operations run locally via the `gh` CLI, providing:

- **Project board operations** — view, move, add, archive, WIP analysis, standup prep across Jeff Intent, Asgard, and Olympus
- **Issue creation** — guided workflow with templates, auto-labeling, and project board integration
- **Label management** — deploy, audit, sync initiative/objective fields, auto-label rules
- **Flow metrics** — cycle time, throughput, WIP age using GitHub timeline events
- **Rollout tracking** — gap analysis and full SDLC deployment to any Infiquetra repo
- **Milestone management** — create and track Objectives via GitHub Milestones
- **Flow helpers** — `flow set-field` / `flow link-sub-issue` / `flow verify-label` / `flow validate-card` / `flow field-options` / `flow discover-project`. Operator-facing GraphQL + REST helpers for project field assignment, native sub-issue linking, self-healing label create, and card pre-flight validation

## Quick Start

### Prerequisites

- `gh` CLI installed and authenticated with github.com (Projects write scope required for `flow set-field` writes — see `gh auth status`)
- `infiquetra-sdlc` repo checked out at `~/workspace/infiquetra/infiquetra-sdlc` (or set `INFIQUETRA_SDLC_PATH`)
- Python 3.12+

### Script Location (after plugin install)

```bash
SCRIPT="$HOME/.claude/plugins/cache/infiquetra-plugins/sdlc-manager/1.5.0/scripts/sdlc_manager.py"
```

Or from source:
```bash
SCRIPT="$HOME/workspace/infiquetra/infiquetra-claude-plugins/plugins/sdlc-manager/scripts/sdlc_manager.py"
```

### Verify Configuration

```bash
python3 $SCRIPT config show
```

## Slash Commands

| Command | Description |
|---------|-------------|
| `/sdlc-board [mount-olympus]` | Quick board status with WIP check |
| `/sdlc-create [type] [--repo repo]` | Interactive issue creation |
| `/sdlc-triage repo#number` | Triage existing issue |
| `/sdlc-metrics [project] [--type metric]` | Flow metrics dashboard |

## Skills

| Skill | Activates When... |
|-------|------------------|
| `sdlc-board` | Board review, item movement, WIP analysis, standup prep |
| `sdlc-issues` | Issue creation, type selection, template guidance |
| `sdlc-labels` | Label deployment, field sync, audit |
| `sdlc-metrics` | Cycle time, throughput, WIP age analysis |
| `sdlc-rollout` | Rollout status, gap analysis, SDLC deployment |
| `sdlc-milestones` | Objective milestones, progress tracking |

## Agent

The `sdlc-operator` agent orchestrates complex multi-step operations:
- Full issue lifecycle (create -> label -> board -> fields -> milestone)
- Board grooming (archive + WIP check + standup)
- New initiative/objective setup (labels + field options + milestone)
- Objective progress tracking across repos
- Batch triage of untriaged issues
- Project field assignment via `flow set-field` (Initiative, Objective, Status, Target Team, Mode, and other live single-select fields)
- Native sub-issue linking via `flow link-sub-issue` (cross-repo, idempotent)
- Card body pre-flight validation via `flow validate-card`

## Architecture

sdlc-manager uses a single shared CLI (`scripts/sdlc_manager.py`) at the plugin root rather than per-skill scripts, because all 6 skills share the same execution backend. Each skill's SKILL.md documents the subset of CLI commands it uses, but they all invoke the same script.

## Script Reference

### Board Operations

```bash
# View board by column
python3 $SCRIPT board view --project mount-olympus

# Add issue to its default repo-mapped board
python3 $SCRIPT board add --repo athena-service --number 42

# Add or move issue on a specific board
python3 $SCRIPT board add --project asgard --repo infiquetra-sdlc --number 42
python3 $SCRIPT board move --project asgard --repo infiquetra-sdlc --number 42 --status "Active"
python3 $SCRIPT board move --repo athena-service --number 42 --status "Assigned"

# Archive terminal workflow items (use --dry-run first)
python3 $SCRIPT board archive --project mount-olympus --dry-run
python3 $SCRIPT board archive --project asgard --dry-run

# Check WIP counts vs limits
python3 $SCRIPT board wip --project mount-olympus

# Standup prep (right-to-left board review)
python3 $SCRIPT board standup --project mount-olympus
python3 $SCRIPT board standup --project jeff-intent

# Discover all project fields and options
python3 $SCRIPT board discover-fields --project mount-olympus
```

### Label Operations

```bash
# Set initiative/objective project fields directly
python3 $SCRIPT flow set-field --project mount-olympus \
  --repo athena-service --number 42 \
  --field Objective --option "platform-launch"

# Audit repo labels
python3 $SCRIPT labels audit --repo athena-service

# Deploy all SDLC labels to a repo
python3 $SCRIPT labels deploy --repo athena-service

# Auto-label based on title/body content
python3 $SCRIPT labels auto-label --repo athena-service --number 42

# Create new field option on project board
python3 $SCRIPT fields create-option --project mount-olympus --field initiative --option "new-initiative"

# Discover all field options
python3 $SCRIPT fields discover --project mount-olympus
```

### Metrics Operations

```bash
# Cycle time percentiles (uses timeline events — may take 30-60s)
python3 $SCRIPT metrics cycle-time --project mount-olympus --days 30
python3 $SCRIPT metrics cycle-time --project mount-olympus --type capability

# Throughput by week
python3 $SCRIPT metrics throughput --project mount-olympus --weeks 4

# WIP age (fast)
python3 $SCRIPT metrics wip-age --project mount-olympus

# Time in each column for specific item
python3 $SCRIPT metrics column-time --project mount-olympus --number 42
```

### Milestone Operations

```bash
# Create milestone for Objective
python3 $SCRIPT milestones create \
  --repo athena-service \
  --title "Pilot: Auth MVP" \
  --due-date 2026-04-15

# List milestones
python3 $SCRIPT milestones list --repo athena-service --state open

# Show milestone progress
python3 $SCRIPT milestones progress --repo athena-service --milestone 1

# Link issue to milestone
python3 $SCRIPT milestones link --repo athena-service --issue 42 --milestone 1
```

### Rollout Operations

```bash
# Show rollout status
python3 $SCRIPT rollout status
python3 $SCRIPT rollout status --team mount-olympus

# Gap analysis for a repo
python3 $SCRIPT rollout gap-analysis --repo athena-service

# Deploy labels to repo
python3 $SCRIPT rollout deploy-labels --repo athena-service

# Deploy issue templates to repo
python3 $SCRIPT rollout deploy-templates --repo athena-service

# Full SDLC deployment (labels + templates)
python3 $SCRIPT rollout deploy-all --repo athena-service

# Update rollout tracking
python3 $SCRIPT rollout update --repo athena-service --field labels --status complete
```

### Flow Operations (Phase C)

Operator-facing GraphQL + REST helpers. See `skills/sdlc-flow/SKILL.md` for the full per-command idempotency contract.

```bash
# Set Initiative or Objective on a card (project FIELDS, not labels)
python3 $SCRIPT flow set-field --project mount-olympus \
    --repo campps-mvp --number 42 \
    --field Initiative --option olympus-quality

# List the live options on a project field (IDs rotate on rename)
python3 $SCRIPT flow field-options --project mount-olympus --field Objective

# Resolve which project a repo maps to
python3 $SCRIPT flow discover-project --repo athena-service

# Link child as native sub-issue of parent (cross-repo, idempotent)
python3 $SCRIPT flow link-sub-issue \
    --parent-repo campps-context-library --parent-number 1 \
    --child-repo campps-mvp --child-number 42

# Self-healing label create (404 → create; exists → no-op; auth/server errors raise)
python3 $SCRIPT flow verify-label --repo campps-mvp \
    --name high-priority --color D93F0B --description "High priority"

# Pre-flight card body against the card_validator schema
python3 $SCRIPT flow validate-card --repo campps-mvp --number 42
```

## Configuration

### Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `INFIQUETRA_SDLC_PATH` | `~/workspace/infiquetra/infiquetra-sdlc` | Path to infiquetra-sdlc checkout |

### Config Files (from infiquetra-sdlc)

| File | Purpose |
|------|---------|
| `config/project-mappings.json` | Project IDs, field IDs, repo-to-project mapping |
| `config/sdlc-schema.json` | Canonical board/team/workflow/WIP/deployment-state schema |
| `config/labels.json` | Label definitions and auto-label rules |
| `config/beads-config.json` | (legacy — file removed from infiquetra-sdlc on 2026-04-26; reads degrade gracefully to `{}`. The `legacy_rollout_config` key in `load_config` documents the migration.) |

## Projects

| Project | Team | Purpose |
|---------|------|---------|
| Jeff Intent | Jeff | Raw intent, approvals, personal/operator work, and shaping before team execution |
| Asgard | Asgard | Rapid action, incubation, and mission-mode work close to Jeff |
| Olympus | Mount Olympus | Primary engineering execution pipeline |

## WIP Limits

| Board / Column | Limit |
|--------|-------|
| Jeff Intent / Shaping | 10 |
| Jeff Intent / Active | 5 |
| Asgard / Active | 5 |
| Olympus / Ready | 10 |
| Olympus / Planning | 3 |
| Olympus / Assigned | 3 per assigned agent |
| Olympus / In Review | 5 |

## Metric Targets

| Type | Cycle Time P85 |
|------|---------------|
| Capability | < 5 days |
| Enhancement | < 2 days |
| Defect | < 1 day |

## Related

- **infiquetra-sdlc**: Source of SDLC configuration, issue templates, and process documentation
- **olympus-blueprint**: Context repository for all capabilities
