---
name: flow
description: |
  Operator-facing GraphQL + REST helpers for the active project boards. Wraps
  the GitHub APIs the orchestrator uses, so Jeff can do per-card work
  (set Initiative/Objective fields, link sub-issues, validate card bodies,
  self-heal labels, discover project mappings) without writing GraphQL by
  hand. Each command is idempotent where possible, and surfaces partial
  failures clearly.
when_to_use: |
  Use this skill when the user wants to:

  Set Initiative or Objective on a card (project FIELDS, not labels):
  - "Set Initiative on this card to platform-quality"
  - "Mark this issue as part of the Auth MVP Objective"
  - "Update the Objective field on campps-mvp#42"

  Discover what fields/options exist on a project (live, not cached):
  - "What Initiative options exist?"
  - "List the Objective field options"
  - "What can I set Initiative to?"

  Find which project a repo belongs to:
  - "Which project does athena-service map to?"
  - "Where do I add cards from this repo?"

  Link a child issue as a sub-issue of a parent:
  - "Link #43 as a sub-issue of #42"
  - "Make this a child of campps-context-library#1"
  - "Set up the parent/child relationship between these issues"

  Self-heal missing labels (so other operations don't fail mid-flow):
  - "Make sure the high-priority label exists on campps-mvp"
  - "Verify hermes-task is on this repo's label set"
  - "Create the capability label if it's missing"

  Pre-flight an issue body against the card_validator schema:
  - "Validate the card body for #42"
  - "Will this issue pass plan-review?"
  - "Check if my issue body matches the card_validator contract"

  Don't use this skill for:
  - Creating issues (use `issues:create`)
  - Moving cards between Status columns (use `board:move`)
  - General board health (use `board:view`)

  These are *helpers*, not full workflows. The full sub-issue-first
  card-creation workflow is in `infiquetra-sdlc/docs/workflows/blueprint-to-issue.md`;
  this skill provides the building blocks the workflow uses.
---

# flow

Operator-facing helpers over the GraphQL + REST APIs the active boards use.
Each command is a thin wrapper with idempotency + clear error messages.

## Commands

```bash
# Set a single-select project field on a card
sdlc_manager.py flow set-field \
  --project campps --repo campps-mvp --number 42 \
  --field Initiative --option platform-quality

# List the options on a project field (live discovery — IDs rotate)
sdlc_manager.py flow field-options \
  --project campps --field Objective

# Resolve which project a repo maps to
sdlc_manager.py flow discover-project --repo athena-service

# Link child as native sub-issue of parent (cross-repo OK; idempotent)
sdlc_manager.py flow link-sub-issue \
  --parent-repo campps-context-library --parent-number 1 \
  --child-repo campps-mvp --child-number 42

# Self-healing label: 404 → create; exists → no-op; other errors raise
sdlc_manager.py flow verify-label \
  --repo campps-mvp --name high-priority \
  --color D93F0B --description "High priority"

# Pre-flight a card body against the card_validator schema
sdlc_manager.py flow validate-card --repo campps-mvp --number 42
```

## Idempotency contract (per command)

| Command | Idempotent? | Failure behavior |
|---|---|---|
| `set-field` | yes (same option = same final state) | Raises if option doesn't exist; error message lists current options |
| `field-options` | read-only | Raises if project or field doesn't exist |
| `discover-project` | read-only | Returns "not mapped" or "excluded" without erroring |
| `link-sub-issue` | yes (re-POST returns 422 "already exists" → success) | Raises on non-422 errors; rejects PR-as-parent |
| `verify-label` | yes (no-op if exists; create if 404) | Raises on auth/rate-limit/server errors (NOT silently treated as missing) |
| `validate-card` | read-only | Exits non-zero if card body fails validation |

## Hard rules

- **Never apply `objective:*` or `initiative:*` colon-prefixed labels.** Both are project FIELDS (decided 2026-05-03; see [DECISIONS](https://github.com/infiquetra/infiquetra-sdlc/blob/main/docs/engineering-journal/DECISIONS.md)). Use `flow set-field` instead.
- **Field option IDs rotate on rename/recreate.** Never cache them. Every command that reads field state calls `flow field-options` (or its equivalent GraphQL query) at start.
- **Verify-label distinguishes 404 from other errors.** A 401/403/5xx must NOT be silently treated as missing — that would create labels under the wrong auth context or mask real failures.
- **Link-sub-issue requires an issue parent.** PRs can't be parents in GitHub's native sub-issue API; the command rejects them with a clear error.

## Where this fits in the broader workflow

The Phase A carry-over #2 decision (Initiative + Objective as project
fields) made `flow set-field` the canonical mechanism for hierarchy
assignment. The blueprint-to-issue workflow's Step 8 calls into:

- `flow link-sub-issue` (parent/child relationship)
- `flow set-field` (Initiative + Objective + Status fields)

`validate-card` is the pre-flight check before plan-review fires. If a card
body doesn't pass `validate-card`, the orchestrator will reject it on the
Ready → Planning transition; running this command before pushing the card
to Ready saves a round-trip.

## Authoritative source

The card_validator schema is mirrored from
`home-lab/ansible/roles/hermes_orchestrator/files/card_validator.py`. When
that file's contract changes, update `validate_card_body` in
`scripts/sdlc_manager.py` to match.

## Related

- `issues` — issue creation flows (will adopt sub-issue-first interactive flow in a follow-up Phase C PR)
- `board` — Status column moves + board view
- `labels` — bulk label deploy (this skill's `verify-label` is the per-call self-heal)
- `milestones` — per-repo milestone management (Objective tracking is now project-field-based; milestones are an optional secondary mechanism)
- `infiquetra-sdlc/docs/engineering-journal/DECISIONS.md` — Initiative/Objective decision (2026-05-03)
- `infiquetra-sdlc/docs/workflows/blueprint-to-issue.md` — full 8-step issue-creation playbook
