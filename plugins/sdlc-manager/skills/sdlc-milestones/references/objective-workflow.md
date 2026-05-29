# Objective Workflow Reference

Complete reference for Objective lifecycle in the Infiquetra SDLC. Source of truth:
`$INFIQUETRA_SDLC_PATH/docs/process/work-hierarchy.md`,
`$INFIQUETRA_SDLC_PATH/docs/process/board-topology.md`, and
`$INFIQUETRA_SDLC_PATH/config/sdlc-schema.json`.

---

## What Is An Objective?

An Objective is a time-bounded deliverable set with a target date. It coordinates multiple
work items toward a common outcome.

| Attribute | Value |
|-----------|-------|
| Duration | Usually 2-8 weeks |
| Scope | Coordinated set of Capabilities, Enhancements, Defects, Explorations, or Context Updates |
| Work happens here | No - work happens on child issues |
| GitHub constructs | Objective issue, project field option, native sub-issues |
| Optional construct | GitHub Milestone for repo-level due-date rollup |

---

## Objective Types

| Type | When to use | Example |
|------|-------------|---------|
| Pilot | Customer or operator validation with explicit success criteria | `Pilot: Platform Launch (2026-04-15)` |
| MVP | Minimum viable product or service slice | `MVP: Core Integration (2026-02-28)` |
| Release | Versioned delivery requiring coordination | `Release: Olympus v1.0 (2026-05-30)` |
| Program | OKR or strategic initiative phase | `Program: Q1 KR1 - User Adoption (2026-03-31)` |

---

## Creation Workflow

### 1. Create The Objective Issue

```bash
python3 sdlc_manager.py issue create --repo <repo> --type objective
```

Capture:

- Objective name
- Objective type
- Target date
- Success criteria
- Included or expected child work
- Risks and explicit non-goals

### 2. Create A Milestone When Useful

```bash
python3 sdlc_manager.py milestones create \
  --repo <repo> \
  --title "Pilot: Platform Launch (2026-04-15)" \
  --due-date 2026-04-15 \
  --description "Validate core workflows with early adopters"
```

Use milestones when a repo-level due date and GitHub progress rollup help. Skip them for
lightweight or exploratory Objectives where the Objective field and sub-issue tree are enough.

### 3. Add To Board And Set Fields

```bash
python3 sdlc_manager.py board add --repo <repo> --number <N>
python3 sdlc_manager.py flow set-field --project mount-olympus \
  --repo <repo> --number <N> \
  --field Objective --option "<Objective name>"
```

Field helpers discover live board fields and fail with available options when a field or
option is missing.

### 4. Create Child Work Just In Time

For each child item:

```bash
python3 sdlc_manager.py issue create --repo <repo> --type capability
python3 sdlc_manager.py board add --repo <repo> --number <N>
python3 sdlc_manager.py flow link-sub-issue \
  --parent-repo <objective-repo> --parent-number <objective-number> \
  --child-repo <repo> --child-number <N>
python3 sdlc_manager.py milestones link --repo <repo> --issue <N> --milestone <M>
```

Use the milestone link only if a milestone exists.

---

## Execution Flow

Child work flows through the target board:

| Board | Flow |
|-------|------|
| Jeff Intent / Asgard | Idea -> Shaping -> Ready -> Active -> Verify -> Done |
| Olympus | Backlog -> Ready -> Planning -> Assigned -> In Review -> Done / Closed |

Progress can be read from:

- Objective issue sub-issues.
- Project field filters by Objective.
- GitHub Milestone completion percentage when a milestone exists.

---

## At-Risk Signals

- Due date is less than 7 days away and milestone completion is below 80%.
- Linked work is blocked or waiting on Jeff.
- Linked work is aging in active/review/verify statuses.
- Success criteria are still ambiguous after shaping.
- Critical/high defects remain open against the Objective.

---

## Completion Criteria

An Objective is complete when:

1. Linked child work is in terminal workflow status.
2. Success criteria are validated and checked off.
3. Open critical/high defects are resolved or explicitly deferred.
4. The milestone is closed if one was created.
5. The Objective issue has completion notes and is closed.

---

## Cross-Repo Coordination

For Objectives spanning multiple repositories:

1. Create matching milestone titles in each repo if milestone rollup is useful.
2. Use the same Objective field option across project boards.
3. Link child work to the Objective issue using native sub-issues.
4. Track aggregate progress through board filters and per-repo milestone progress.
