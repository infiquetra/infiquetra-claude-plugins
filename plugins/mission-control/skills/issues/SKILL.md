---
name: issues
description: |
  Create and manage SDLC issues in Infiquetra GitHub repositories using the 6-type issue
  taxonomy: capability, enhancement, defect, exploration, context-update, and objective.
  Handles issue type selection, template-guided creation, Hermes label application, project
  board assignment, and milestone linking.
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

  Prepared issue creation:
  - "create an issue from the brainstorm", "handoff the plan as an issue"
  - "create an Olympus issue from this text"
  - "create an Asgard issue from these notes"
  - "turn this queue entry into an issue for the router repo"
---

# SDLC Issues

Create and manage SDLC issues across Infiquetra repositories using the 6-type taxonomy.
Handles type selection, template-guided creation, Hermes label application, and project board
assignment.

## Script Location

```
$INFIQUETRA_SDLC_PATH/../infiquetra-claude-plugins/plugins/mission-control/scripts/sdlc_manager.py
```

> If `$INFIQUETRA_SDLC_PATH` is unset, use `~/workspace/infiquetra/infiquetra-sdlc` as the default base path.

## Issue Types

Six issue types cover all Infiquetra work:

| Type | Hermes Actionable | Duration | When to Use |
|------|-------------------|----------|-------------|
| **capability** | Yes | 1-4 weeks | New end-to-end deployable functionality |
| **enhancement** | Yes | 2-5 days | Improving existing functionality |
| **defect** | Yes | Hours-2 days | Broken functionality that an agent can fix |
| **objective** | No | 2-8 weeks | Coordinating multiple capabilities with a target date |
| **exploration** | No | 1-3 days | Research, POC, or architectural investigation |
| **context-update** | No | Hours-1 day | Updating Blueprint repository documentation |

See `references/issue-types.md` for the complete guide and decision tree.
See `references/templates-reference.md` for the generated template field and label reference.

## Hermes Actionable Contract

Actionable issue types are `capability`, `enhancement`, and `defect`. Their canonical templates
apply `hermes-task`, `needs-plan`, and the type label.

Each actionable card must render the following exact H3 section headers in the GitHub issue body:

- `### Objective`
- `### Acceptance criteria`
- `### Out-of-scope / non-goals`
- `### Files expected to change`
- `### Tests to add or update`
- `### Verification`

Hermes validation expects these semantics:

- `Acceptance criteria` includes at least one `- [ ]` checklist item.
- `Verification` includes exact commands, preferably in a fenced shell code block.
- `Files expected to change` includes at least one path-like line.
- Empty placeholder sections such as `_No response_` are invalid.

Optional actionable sections are `Notes / conventions` and `Context library links`. Capability cards
also include optional `Capability size (human planning hint)`.

## Non-actionable Templates

Objective, Exploration, and Context Update templates carry `hermes-not-actionable`. Do not present
these as Hermes task cards or dispatch them directly to agents. Use them for coordination,
research, or documentation context.

## Core Operations

### Prepared Issue Draft from Source Text

Use the prepared workflow when the user starts from rough text, notes, copied queue entries, or
asks for an Asgard/Olympus issue that should be reviewed before mutation.

`/issue` is the primary user-facing command for this path. `/issue` remains a
compatibility alias. `--prepare` is the canonical non-mutating mode; `--draft` means the same
thing. `--from` accepts a local path, GitHub issue/PR URL, branch ref, or natural search hint.
`--maturity` overrides inferred handoff maturity.

```bash
python3 sdlc_manager.py issue prepare \
  --repo hermes-claude-code-router \
  --type capability \
  --team olympus \
  --project mount-olympus \
  --risk medium \
  --title "Prepared issue workflow" \
  --from docs/plans/example.md \
  --maturity plan-ready

python3 sdlc_manager.py issue create-prepared docs/sdlc-issue-drafts/<draft>.md
```

The prepared workflow writes a markdown draft and JSON sidecar under
`docs/sdlc-issue-drafts/`. `issue create-prepared` re-runs readiness checks, renders the mutation
plan, asks for confirmation, repairs missing labels/templates after confirmation, opens a mapping
PR when needed, and only then creates the issue.

Prepared handoff drafts include `handoff_maturity` in the sidecar and a body section with the
suggested next action. Maturity values are:

- `idea-ready` -> suggest `/plan <issue>`.
- `requirements-ready` -> suggest `/plan <issue>`.
- `plan-ready` -> suggest `/work <issue>`.
- `resume-ready` -> suggest `/work <issue>`.
- `deferred-context` -> preserve context and clarify before execution.

Source artifact resolution:

- Explicit local path: `--from docs/brainstorms/example.md`.
- GitHub issue or PR URL: fetched through `gh issue view` or `gh pr view`.
- Branch ref: `--from branch:current` or `--from branch:<name>` captures resume context.
- Natural language such as "from the brainstorm" or "handoff the plan" searches durable
  lifecycle artifact directories before asking for a path.
- Ambiguous matches must be shown to the user; do not pick one silently.

Natural-language routing rules:

- "Create an issue from the brainstorm" -> search `docs/brainstorms/`, prepare, then
  create-prepared after review.
- "Create an Olympus issue from this text" -> prepare with `--team olympus --project mount-olympus`,
  then create-prepared after review.
- "Create an Asgard issue from this text" -> prepare with `--team asgard --project asgard`, then
  create-prepared after review.
- If team or project is ambiguous, ask. Do not guess.
- Do not bypass prepared readiness checks with ad hoc `gh issue create` when the prompt asks to
  create from source text.
- Do not suggest `/loop` to a team recipient. Use `/plan <issue>` or `/work <issue>` only when the
  recipient has `saga`.

Safe starting statuses:

- Asgard starts in `Shaping`.
- Mount Olympus starts in `Backlog`.
- Never auto-move a prepared issue to `Ready`.

### Create Issue with Template

```bash
# Launch interactive template for a specific issue type
python3 sdlc_manager.py issue create --repo infiquetra-core --type capability
python3 sdlc_manager.py issue create --repo infiquetra-auth --type defect
python3 sdlc_manager.py issue create --repo infiquetra-blueprint --type context-update

# Create via gh CLI directly (alternative)
gh issue create --repo Infiquetra/infiquetra-core --template capability.yml
```

After template creation, apply labels and add to the project board where applicable.

### Labels from Canonical Templates

**Actionable templates**:

- `capability` -> `capability`, `hermes-task`, `needs-plan`
- `enhancement` -> `enhancement`, `hermes-task`, `needs-plan`
- `defect` -> `defect`, `hermes-task`, `needs-plan`

**Non-actionable templates**:

- `objective` -> `objective`, `hermes-not-actionable`
- `exploration` -> `exploration`, `research`, `hermes-not-actionable`
- `context-update` -> `context-update`, `documentation`, `hermes-not-actionable`

**Apply labels manually** via gh CLI when a template did not apply them:

```bash
gh issue edit <N> --repo Infiquetra/<repo> --add-label "hermes-task,needs-plan,capability"
gh issue edit <N> --repo Infiquetra/<repo> --add-label "hermes-not-actionable"
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

### Sync Project Fields

Set project fields with the `flow` helpers after the issue is added to a board:

```bash
python3 sdlc_manager.py flow set-field \
  --repo <repo> \
  --number <N> \
  --project "Mount Olympus Operations" \
  --field Status \
  --option Backlog
```

Use live field discovery rather than cached field IDs.

## Issue Creation Workflow

Follow these steps when creating any issue:

### Step 1: Determine Issue Type

Use the decision tree (see `references/issue-types.md`) or ask the user:

- New end-to-end deployable functionality? -> **CAPABILITY**
- Improving existing functionality? -> **ENHANCEMENT**
- Broken functionality for an agent to fix? -> **DEFECT**
- Coordinating multiple capabilities with a target date? -> **OBJECTIVE**
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

For actionable cards, gather these exact required fields:

- Objective
- Acceptance criteria
- Out-of-scope / non-goals
- Files expected to change
- Tests to add or update
- Verification

Ask for optional Notes / conventions and Context library links when they would improve planning.
Ask for Capability size only for capability cards and treat it as a human planning hint.

For non-actionable cards, use the fields in `references/templates-reference.md` and preserve the
`hermes-not-actionable` distinction.

### Step 4: Create the Issue

```bash
# Interactive template (prompts for all fields)
python3 sdlc_manager.py issue create --repo <repo> --type <type>

# Or open gh CLI template directly
gh issue create --repo Infiquetra/<repo> --template <type>.yml
```

### Step 5: Verify Labels

1. Confirm actionable templates applied `hermes-task`, `needs-plan`, and the type label.
2. Confirm non-actionable templates applied `hermes-not-actionable` and their context labels.
3. Use `flow verify-label` for any required label that is missing.

### Step 6: Add to Project Board

```bash
python3 sdlc_manager.py board add --repo <repo> --number <N>
```

Issue starts in **Backlog** unless the current project workflow moves it elsewhere.

### Step 7: Link Parent or Milestone

```bash
# If part of an objective, link as a native sub-issue or attach to the objective milestone
python3 sdlc_manager.py flow link-sub-issue \
  --parent-repo <parent-repo> \
  --parent-number <parent-number> \
  --child-repo <repo> \
  --child-number <N>
```

When creating an Objective issue, also create a corresponding GitHub Milestone if the workflow
still uses milestones for that repository.

## Natural Language Examples

**"Create a capability in infiquetra-core"**
-> `issue create --repo infiquetra-core --type capability`

**"File a defect for the auth API crashing"**
-> `issue create --repo infiquetra-auth --type defect`

**"Create an exploration to research biometric SDK options"**
-> `issue create --repo infiquetra-blueprint --type exploration`

**"Create an issue from the plan"**
-> Search `docs/plans/`; if one plan matches, prepare with
`issue prepare --from <plan> --maturity plan-ready`. If multiple plans match, ask the user to
choose.

**"Create an Olympus issue from this text for the router repo"**
-> Prepare an Olympus draft with `issue prepare --team olympus --project mount-olympus`, review
readiness gaps, then use `issue create-prepared`.

**"Create an Asgard issue from these notes"**
-> Ask for the target repo if missing, prepare an Asgard draft with
`issue prepare --team asgard --project asgard`, review gaps, then use `issue create-prepared`.

**"Is this a capability or enhancement?"**
-> Walk through decision tree: Is it new end-to-end deployable functionality? If yes -> capability.
If it improves existing functionality -> enhancement.

**"Create issues for all the capabilities in this objective"**
-> List capabilities from the objective description, create each with `--type capability`, and link
each to the objective parent or milestone.

**"What type of issue should this be?"**
-> Present the decision tree from `references/issue-types.md`.

## Label Reference

### Actionable Labels

| Type | Labels |
|------|--------|
| `capability` | `capability`, `hermes-task`, `needs-plan` |
| `enhancement` | `enhancement`, `hermes-task`, `needs-plan` |
| `defect` | `defect`, `hermes-task`, `needs-plan` |

### Non-actionable Labels

| Type | Labels |
|------|--------|
| `objective` | `objective`, `hermes-not-actionable` |
| `exploration` | `exploration`, `research`, `hermes-not-actionable` |
| `context-update` | `context-update`, `documentation`, `hermes-not-actionable` |

### Content Labels

| Label | Applied When |
|-------|-------------|
| `security` | Security vulnerability or CVE |
| `performance` | Performance regression or optimization |
| `breaking-change` | API or interface breaking change |

## Key Behaviors

- **Always confirm issue type** before creating — wrong type causes downstream confusion.
- **Preserve Hermes actionable/non-actionable distinction** — only capability, enhancement, and defect are Hermes task cards.
- **Use exact actionable H3 headers** — the Hermes validator matches section header text.
- **Require checklist acceptance criteria** — at least one `- [ ]` item is mandatory.
- **Require verification commands** — commands should be copy-pasteable and prove success.
- **Unmapped repos** will warn on board add — this is expected for newer repos.

## Reference Documents

- `references/issue-types.md` — Complete guide to all 6 issue types with decision tree
- `references/templates-reference.md` — Generated view of canonical issue templates
