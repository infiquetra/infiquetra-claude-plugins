# Work Hierarchy Reference

Practical reference for the Infiquetra three-tier work hierarchy.
Source: `$INFIQUETRA_SDLC_PATH/docs/process/work-hierarchy.md` and `docs/process/issue-types.md`.

---

## The Three-Tier Model

```
Initiative (Strategic — quarters / OKRs)
    +-- Objective (Time-bounded — Pilots / MVPs / Releases)
            +-- Capability (Primary unit of work — Kanban flow)
```

**Key principle**: Initiative and Objective exist for grouping, coordination, and reporting
only. All actual work happens at the Capability level. WIP limits, flow metrics, and daily
standup operate at the Capability level.

---

## Level 1: Initiative

**Definition**: Strategic objective spanning one or more quarters. Answers: "What are we
trying to achieve this year?"

**Duration**: 1-4 quarters

**GitHub construct**: Label (`initiative:{short-kebab-case}`) + Project View

**When to create**:
- Multi-quarter strategic goals or OKRs
- Aligning work with company/team OKRs
- Coordinating multiple related Objectives
- Providing executive-level program visibility

**When NOT to create**:
- Single capabilities or enhancements
- Short-term work (< 1 quarter)

**Naming**: `initiative:{short-kebab-case}`
Examples: `initiative:olympus-v1`, `initiative:q1-2026-okrs`, `initiative:security-compliance`

**Label color**: Dark blue (`#0052CC`)

**Key behavior**: Initiatives are NOT issue types — no GitHub Issue template.
Tracked purely via labels applied to Objectives and Capabilities.

---

## Level 2: Objective

**Definition**: Time-bounded deliverable set with a specific target date. Answers: "What
are we delivering by this date?"

**Duration**: 2-8 weeks

**GitHub construct**: GitHub Milestone + Label (`objective:{short-kebab-case}`)

**Beads construct**: Parent task with child capability subtasks

**Objective types**:
| Type | Description | Example |
|------|-------------|---------|
| Pilot | Customer validation with specific participants | "Pilot: Platform Launch with 5 early adopters" |
| MVP | Minimum viable product for initial launch | "MVP: Core Auth Integration" |
| Release | Versioned delivery with coordinated features | "Release: Olympus v1.0" |
| Program | OKR/Initiative phase or milestone | "Program: Q1 KR1 - User Adoption" |

**When to create**:
- Time-bounded deliverable with specific target date
- Coordinating multiple Capabilities for unified delivery
- Customer pilot or beta program
- Versioned release requiring coordination
- OKR milestone requiring focus

**When NOT to create**:
- Single Capability (assign directly to Initiative or leave unassigned)
- Informal team coordination (use daily standup)
- Ongoing work without delivery target

**Naming**:
- Milestone: `{Type}: {Name} ({YYYY-MM-DD})` — e.g., `Pilot: Platform Launch (2026-04-15)`
- Label: `objective:{short-kebab-case}` — e.g., `objective:platform-launch`

**Label color**: Blue (`#1D76DB`)

**Typical size**: 3-10 Capabilities
- Small (2-4 weeks): 3-5 capabilities
- Medium (4-6 weeks): 5-8 capabilities
- Large (6-8 weeks): 8-10 capabilities

**Cross-repo coordination**: Create identical milestones in each affected repo, apply
consistent labels across all repos, use Project for unified view.

---

## Level 3: Capability

**Definition**: Complete, deployable piece of system functionality. The PRIMARY unit of
work in the SDLC. This level is unchanged by the hierarchy extension.

**Duration**: 1-4 weeks with AI assistance

**GitHub construct**: Issue (with optional Milestone and Initiative label links)

**Beads construct**: Subtask (claimable by Mount Olympus agents via `bd claim`)

**Sizes**:
| Size | Duration | Examples |
|------|----------|---------|
| XS | 1-2 days | Add new API endpoint with basic CRUD |
| S | 3-5 days | Implement auth integration with external provider |
| M | 1-2 weeks | Build notification system with message queue + workers |
| L | 2-4 weeks | Create identity verification service with multiple providers |

**Cycle time target (P85)**: < 5 days

**What changes with hierarchy**: Capabilities can now optionally link to parent Objectives
(via milestone) and Initiatives (via label). This does not change how Capabilities flow.

---

## How the Hierarchy Flows in Practice

```
Quarterly planning (1-2 hours, end of each quarter)
    +- Team identifies Initiatives for Q+1
       +- Team defines Objectives with target dates within each Initiative
          +- Team estimates Capabilities needed per Objective

Just-in-time (2-3 weeks before work starts)
    +- Capabilities created and linked to Objective milestone
       +- Capabilities move to Ready when prioritized
       +- Beads tasks created and marked ready for claiming

Daily work (continuous Kanban flow)
    +- Agent or developer claims Capability (bd claim <task-id>)
       +- Capability flows: In Development -> E2E Testing -> Deployment Ready -> Deployed

Objective complete when all Capabilities deployed
    +- GitHub Milestone closes
       +- Beads parent task marked complete
```

---

## Beads/Dolt Integration

The Mount Olympus team uses Beads/Dolt as the primary coordination layer for agent-driven
development:

| Level | Beads Construct | Sync |
|-------|----------------|------|
| Initiative | -- | Label only, no Beads task |
| Objective | Parent task | Syncs to GitHub Milestone progress |
| Capability | Subtask (claimable) | Syncs to GitHub Issue state |

`bd` is the Beads/Dolt CLI for structured agent task coordination (see `docs/tools/index.md` for install instructions).

### Agent Workflow with Beads

```bash
# Task is made available for claiming
bd ready <capability-task-id>

# An agent (e.g., Hermes, Athena) claims the task
bd claim <capability-task-id>

# Agent updates progress
bd update <capability-task-id> in-progress

# Agent completes the task (syncs to GitHub Issue close)
bd complete <capability-task-id>
```

---

## GitHub Constructs Summary

| Level | Label | Milestone | Issue Template |
|-------|-------|-----------|----------------|
| Initiative | `initiative:{name}` (dark blue) | -- | None — label only |
| Objective | `objective:{name}` (blue) + `objective-type:{type}` (yellow) | Yes, with due date | `objective.yml` |
| Capability | `capability` | Optional (link to Objective) | `capability.yml` |

---

## Labels Reference

**Initiative labels** (dark blue `#0052CC`): `initiative:{kebab-name}`

**Objective labels** (blue `#1D76DB`): `objective:{kebab-name}`

**Objective type labels** (yellow `#FBCA04`):
- `objective-type:pilot`
- `objective-type:mvp`
- `objective-type:release`
- `objective-type:program`

---

## Common Questions

**Do I need an Objective for every Capability?**
No. Objectives are optional. Use them when time-bounded coordination is needed (pilots,
releases, OKR milestones). For standalone or ongoing work, skip the Objective.

**Can Enhancements and Defects be assigned to Objectives?**
Yes, but it's optional. Assign them only if they are critical for an Objective's success
(e.g., a defect blocking a pilot). Otherwise leave them unassigned.

**Can a Capability belong to multiple Initiatives?**
Technically yes (apply multiple labels), but discouraged. A Capability should contribute
to one Initiative. If it truly spans multiple, check whether Initiative boundaries need
to be redrawn.

**Can Objectives span multiple Initiatives?**
No. Each Objective belongs to exactly one Initiative for clear strategic alignment.

**How do I track progress toward an Objective?**
Two ways: (1) GitHub Milestone completion % (closed vs. open issues) and (2)
Project filtered by Objective — shows Kanban status of all linked Capabilities.
