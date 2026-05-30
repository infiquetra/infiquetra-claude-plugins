---
name: sdlc-create
description: Compatibility alias for /create-issue with canonical SDLC issue guidance
---

Compatibility command for `/create-issue`. Prefer `/create-issue` for new prepared handoff work,
especially when using `--prepare`, `--draft`, `--from`, or `--maturity`.

## Usage

```
/sdlc-create [type] [--repo repository-name] [--prepare|--draft] [--from artifact] [--maturity value]
```

## Arguments

- `type` — Optional issue type: `capability`, `enhancement`, `defect`, `exploration`, `context-update`, `objective`
- `--repo` — Optional repository name (without org prefix)
- `--prepare` — Write a prepared draft without mutating GitHub
- `--draft` — Alias for `--prepare`
- `--from` — Source artifact path, GitHub issue/PR URL, branch ref, or search hint
- `--maturity` — Override inferred handoff maturity

## What This Does

1. Guides issue type selection using the decision tree when type is not specified
2. Asks for the target repository when repo is not specified
3. Walks through canonical template fields for the selected type
4. For source-text or source-artifact requests, prepares a reviewable draft before mutation
5. Creates the issue via `gh issue create` or `issue create-prepared`
6. Verifies canonical Hermes labels
7. Adds to project board when repo is mapped or explicitly targeted
8. Sets project fields with flow helpers when requested
9. Creates milestone for Objective type when the target workflow uses milestones

## Issue Type Decision Tree

```
New end-to-end deployable functionality? -> CAPABILITY
Improving existing functionality? -> ENHANCEMENT
Broken functionality for an agent to fix? -> DEFECT
Coordinating multiple capabilities with a target date? -> OBJECTIVE
Researching or investigating? -> EXPLORATION
Updating documentation? -> CONTEXT UPDATE
```

## Hermes Label Contract

Actionable templates are planned and dispatched by Hermes:

- `capability` -> `capability`, `hermes-task`, `needs-plan`
- `enhancement` -> `enhancement`, `hermes-task`, `needs-plan`
- `defect` -> `defect`, `hermes-task`, `needs-plan`

Non-actionable templates are not Hermes task cards:

- `objective` -> `objective`, `hermes-not-actionable`
- `exploration` -> `exploration`, `research`, `hermes-not-actionable`
- `context-update` -> `context-update`, `documentation`, `hermes-not-actionable`

## Actionable Field Contract

For `capability`, `enhancement`, and `defect`, gather these exact fields so GitHub renders the
required `###` section headers expected by the Hermes validator:

- Objective
- Acceptance criteria
- Out-of-scope / non-goals
- Files expected to change
- Tests to add or update
- Verification

Validation expectations:

- Acceptance criteria must include at least one `- [ ]` checklist item.
- Verification should include exact commands, preferably in a fenced shell code block.
- Files expected to change should include path-like lines.

Optional actionable sections are `Notes / conventions` and `Context library links`. Capability also
has optional `Capability size (human planning hint)`.

## Examples

```
/sdlc-create
/sdlc-create capability --repo athena-service
/sdlc-create defect --repo hermes-gateway
/sdlc-create objective --repo olympus-blueprint
/sdlc-create exploration
/sdlc-create "create an Olympus issue from this text for hermes-claude-code-router"
/sdlc-create "create an Asgard issue from these notes"
/sdlc-create --draft --from docs/plans/example.md --maturity plan-ready
```

## Script Command

```bash
python3 ~/.claude/plugins/cache/infiquetra-plugins/sdlc-manager/1.6.0/scripts/sdlc_manager.py \
  issue create --repo athena-service --type capability
```

Then add to project:

```bash
python3 ~/.claude/plugins/cache/infiquetra-plugins/sdlc-manager/1.6.0/scripts/sdlc_manager.py \
  board add --repo athena-service --number <new-issue-number>
```

Prepared-draft path:

```bash
python3 ~/.claude/plugins/cache/infiquetra-plugins/sdlc-manager/1.6.0/scripts/sdlc_manager.py \
  issue prepare --repo hermes-claude-code-router --type capability \
  --team olympus --project mount-olympus --risk medium \
  --title "Prepared issue workflow" --from docs/plans/example.md --maturity plan-ready

python3 ~/.claude/plugins/cache/infiquetra-plugins/sdlc-manager/1.6.0/scripts/sdlc_manager.py \
  issue create-prepared docs/sdlc-issue-drafts/<draft>.md
```

## Instructions

When the user invokes `/sdlc-create`:

1. If no type given, walk through the decision tree with the user.
2. If no repo given, ask which Infiquetra repo this belongs to.
3. Use the `sdlc-issues` skill to guide issue creation.
4. If the user asks to create an Asgard or Olympus issue from text, notes, a queue entry, existing
   artifact, or other rough source, use the prepared-draft path: `issue prepare`, review gaps with
   the user, then `issue create-prepared` after final confirmation.
5. If the user implies a source artifact exists, such as "from the brainstorm" or "handoff the
   plan", search durable lifecycle artifacts before asking for a path.
6. For actionable Olympus types, confirm the body includes the exact required field headers and Hermes validator semantics.
7. If team or project is ambiguous, ask. Do not guess between Asgard and Mount Olympus.
8. After creation, verify labels:
   - Actionable: type label + `hermes-task` + `needs-plan`
   - Non-actionable: `hermes-not-actionable` plus the template-specific context labels
9. Add to project board if repo is mapped or the prepared draft supplied an explicit project.
10. Set project fields with `flow set-field` when requested.
11. For Objectives, create a GitHub Milestone when the target workflow still uses milestones.
12. Show a concise summary of everything created or applied.

If user provides partial info, infer the likely type and ask for confirmation. Example: "create a
defect about the auth timeout" implies `defect`, but still confirm target repo and required fields.

Use the `sdlc-operator` agent for batch issue creation or complex multi-repo scenarios.
