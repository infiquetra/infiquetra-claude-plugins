# Objective Workflow Reference

Complete reference for the Objective lifecycle in the Infiquetra AI-Native SDLC.
Synthesized from `docs/process/work-hierarchy.md` and `docs/process/issue-types.md`.

---

## What is an Objective?

An **Objective** is a time-bounded deliverable set with a specific target date. It coordinates
multiple Capabilities toward a common goal and provides the coordination layer between
strategic Initiatives and day-to-day Capability work.

**Objectives answer**: "What are we delivering by this date?"

| Attribute | Value |
|-----------|-------|
| Duration | 2-8 weeks |
| Scope | Coordinated set of Capabilities delivering business value |
| Work Happens Here | No — work happens in Capabilities |
| GitHub Construct | GitHub Milestone + Label (`objective:{name}`) |
| Beads Construct | Parent task with child capability subtasks |

**Key principle**: Objectives are for grouping and reporting only. They do not decompose into
tasks or get assigned to developers. Work flows at the Capability level.

---

## The Three-Tier Model

```
INITIATIVE
  Strategic objective spanning quarters (OKRs, Programs)
  GitHub: Label (initiative:{name}) + Project View
  |
  +-- OBJECTIVE  <--- This document
  |     Time-bounded deliverable (Pilots, MVPs, Releases)
  |     GitHub: Milestone + Label (objective:{name})
  |     Beads: Parent task
  |
  +-- CAPABILITY (primary unit of work)
        1-4 weeks, deployable, flows through Kanban
        GitHub: Issue
        Beads: Subtask (claimable by agents)
```

Initiatives and Objectives are for grouping and reporting. Capabilities are for doing.

---

## Objective Types

| Type | When to Use | Naming Example |
|------|-------------|----------------|
| **Pilot** | Customer validation with specific participants and success criteria | `Pilot: Platform Launch (2026-04-15)` |
| **MVP** | Minimum viable product for initial launch | `MVP: Core Integration (2026-02-28)` |
| **Release** | Versioned delivery requiring coordinated feature rollout | `Release: Olympus v1.0 (2026-05-30)` |
| **Program** | OKR milestone or strategic initiative phase | `Program: Q1 KR1 - User Adoption (2026-03-31)` |

---

## Naming Conventions

### GitHub Milestone Title

Format: `{Type}: {Name} ({YYYY-MM-DD})`

The date is included in the milestone title for quick scanning in GitHub's milestone list.

```
Pilot: Platform Launch (2026-04-15)
MVP: Core Integration (2026-02-28)
Release: Olympus v1.0 (2026-05-30)
Program: Q1 KR1 - User Adoption (2026-03-31)
```

### GitHub Label

Format: `objective:{short-kebab-case}` (no date — labels are for filtering)

```
objective:platform-launch
objective:core-integration
objective:olympus-v1
objective:q1-kr1
```

### Objective Issue Title

Format: `[OBJECTIVE] {Name}` (template auto-prepends `[OBJECTIVE] `)

```
[OBJECTIVE] Platform Launch MVP
[OBJECTIVE] Core Integration
[OBJECTIVE] Olympus v1.0 Release
[OBJECTIVE] Q1 KR1 - User Adoption
```

---

## Objective Sizing Guide

Objectives typically contain **3-10 Capabilities**:

| Size | Duration | Capabilities | Examples |
|------|----------|--------------|---------|
| **Small** | 2-4 weeks | 3-5 | Limited-scope pilot, focused MVP |
| **Medium** | 4-6 weeks | 5-8 | Standard MVP or minor release |
| **Large** | 6-8 weeks | 8-10 | Major release, program milestone |

If > 10 Capabilities: consider breaking into multiple Objectives or extending the timeline.
The goal is a coherent deliverable set, not an exhaustive backlog.

---

## Creation Workflow (Step by Step)

Typically performed during quarterly planning or when a new time-bounded deliverable is identified.

### 1. Create the Objective Issue

```bash
python3 sdlc_manager.py issue create --repo <repo> --type objective
```

Fill in the template:
- **Objective Name**: Descriptive (e.g., "Platform Launch MVP")
- **Objective Type**: Pilot / MVP / Release / Program
- **Target Date**: Specific date in YYYY-MM-DD
- **Success Criteria**: Measurable, testable checkboxes
- **Included Capabilities**: Preliminary list (can add more later)
- **Stakeholders**: Business Owner, Tech Lead, External contacts
- **Risk Level**: Overall delivery risk assessment

### 2. Create the GitHub Milestone

```bash
python3 sdlc_manager.py milestones create \
  --repo <repo> \
  --title "Pilot: Platform Launch" \
  --due-date 2026-04-15 \
  --description "Validate core workflows with 5 early adopters"
```

Record the milestone number returned (e.g., `#3`).

### 3. Create the Beads Parent Task

`bd` is the Beads/Dolt CLI for structured agent task coordination (see `docs/tools/index.md` for install instructions).

```bash
bd ready objective-platform-launch
```

This creates a parent task in Beads that child capability tasks will link to.

### 4. Apply Labels to the Objective Issue

```bash
# Primary objective label
gh issue edit <N> --repo Infiquetra/<repo> --add-label "objective:platform-launch"

# Parent initiative label (if applicable)
gh issue edit <N> --repo Infiquetra/<repo> --add-label "initiative:olympus-v1"
```

### 5. Link Objective Issue to Milestone

```bash
python3 sdlc_manager.py milestones link \
  --repo <repo> \
  --issue <N> \
  --milestone <M>
```

### 6. Add to Project Board and Sync Fields

```bash
python3 sdlc_manager.py board add --repo <repo> --number <N>
python3 sdlc_manager.py labels sync-fields --repo <repo> --number <N>
```

---

## Execution Workflow

How Capabilities flow toward the Objective during the 2-8 week window.

### Capability Creation (Just-in-Time)

Create Capabilities 2-3 weeks before work starts, not all upfront. For each Capability:

```bash
# Create capability
python3 sdlc_manager.py issue create --repo <repo> --type capability

# Apply hierarchy labels
gh issue edit <N> --repo Infiquetra/<repo> --add-label "objective:platform-launch"
gh issue edit <N> --repo Infiquetra/<repo> --add-label "initiative:olympus-v1"

# Link to objective milestone
python3 sdlc_manager.py milestones link --repo <repo> --issue <N> --milestone <M>

# Add to project board
python3 sdlc_manager.py board add --repo <repo> --number <N>
python3 sdlc_manager.py labels sync-fields --repo <repo> --number <N>

# Mark as ready for agent claiming in Beads
bd ready <capability-task-id>
```

### Capability Flow Through Kanban

Capabilities flow through the standard Kanban columns:

```
Backlog -> Ready -> In Development -> E2E Testing -> Deployment Ready -> Deployed
```

Progress is tracked via GitHub Milestone completion %:
- Milestone % = closed issues / total issues linked to milestone

### Standup Objective Check-in

During standup, add an Objective Check-in (when an active time-bounded Objective exists):
- Days until target date
- Progress: X of Y Capabilities deployed
- Any blockers risking the deadline?
- Scope adjustments needed?

### Progress Monitoring

```bash
# Check milestone progress
python3 sdlc_manager.py milestones progress --repo <repo> --milestone <M>
```

**At-risk signals**:
- < 7 days to due date AND < 80% completion -> flag as at-risk
- Any Capability blocked for > 1 day
- Capability aging > 3 days in In Development

---

## Completion Workflow

### Completion Criteria

An Objective is complete when ALL of the following are true:
1. All Capabilities linked to the milestone are in **Deployed** status
2. Success criteria in the Objective issue are validated and checked off
3. No Critical or High defects open against the Objective
4. Beads parent task marked complete

### Closing the Milestone

```bash
# Close the GitHub Milestone
gh api repos/Infiquetra/<repo>/milestones/<N> \
  -X PATCH \
  -f state=closed
```

### Completing the Objective Issue

1. Update the Objective issue with completion notes
2. Mark success criteria checkboxes as complete
3. Add comment summarizing what was delivered vs. what was planned
4. Close the issue
5. Complete the Beads parent task: `bd complete <objective-task-id>`

### Post-Objective Activities

- Schedule outcome measurement (if Pilot: gather user feedback, if Release: monitor metrics)
- Team retrospective if the Objective was a significant milestone
- Notify stakeholders via #mount-olympus Discord channel

---

## Cross-Repo Coordination

For Objectives spanning multiple repositories:

### Setup

Create the same milestone title in each affected repo:

```bash
# Primary repo
python3 sdlc_manager.py milestones create \
  --repo infiquetra-core \
  --title "Pilot: Platform Launch (2026-04-15)" \
  --due-date 2026-04-15

# Secondary repos with matching title
python3 sdlc_manager.py milestones create \
  --repo infiquetra-auth \
  --title "Pilot: Platform Launch (2026-04-15)" \
  --due-date 2026-04-15
```

Apply consistent labels across all repos (`objective:platform-launch`, `initiative:olympus-v1`).

### Tracking

Check progress in each repo:
```bash
python3 sdlc_manager.py milestones progress --repo infiquetra-core --milestone <M1>
python3 sdlc_manager.py milestones progress --repo infiquetra-auth --milestone <M2>
```

Use GitHub Projects filter by `objective:platform-launch` label to see all Capabilities
across all repos in one view.

---

## Examples of Good Objectives

### Example 1: Pilot Objective

```
Objective: Pilot: Platform Launch (2026-04-15)
Type: Pilot
Initiative: initiative:olympus-v1

Success Criteria:
- [ ] 5 early adopters onboarded and trained
- [ ] Complete onboarding flow operational (signup + setup + first use)
- [ ] Operations team has real-time dashboard visibility
- [ ] No critical defects during the 2-week pilot period
- [ ] > 80% onboarding completion rate without support intervention

Included Capabilities (4):
1. User Onboarding Service with REST API
2. Auth Integration with OAuth2/OIDC
3. Operations Dashboard MVP
4. User Self-Service Flow

Risk: Medium — new third-party integrations, early adopter availability
```

### Example 2: Release Objective

```
Objective: Release: Olympus v1.0 (2026-05-30)
Type: Release
Initiative: initiative:olympus-v1

Success Criteria:
- [ ] All v1.0 features deployed to production
- [ ] 99.9% uptime for 2 weeks before release
- [ ] All security reviews passed
- [ ] Documentation complete and published
- [ ] No open Critical or High defects

Included Capabilities (7):
1. Multi-Tenant Support
2. Full User Workflow (signup + config + usage)
3. Reporting Dashboard
4. Self-Service Onboarding Portal
5. Performance Optimization (p95 < 200ms)
6. Audit Log Export
7. Admin Role Management

Risk: High — complex coordination, performance targets aggressive
```

### Example 3: Program Objective (OKR)

```
Objective: Program: Q1 KR1 - User Adoption (2026-03-31)
Type: Program
Initiative: initiative:q1-2026-okrs

Key Result: 10 users actively using the platform

Success Criteria:
- [ ] 10+ users registered and active (at least 1 session per week)
- [ ] Average 50+ transactions per user per week
- [ ] 80%+ user satisfaction score (survey)

Included Capabilities (3):
1. Self-Service Onboarding Portal
2. Interactive Tutorial Integration
3. Simplified Workflow (feedback from pilot)

Risk: Medium — user adoption is behavior change, not just technical delivery
```

---

## Common Questions

**Q: Do all Capabilities need to be in an Objective?**

No. Objectives are optional. Use them when:
- Multiple Capabilities must deliver together (pilot, release)
- Time-bounded coordination is needed
- Executive visibility is required

For ongoing enhancements, defect fixes, or single Capabilities: skip the Objective.

**Q: Can a Capability belong to multiple Objectives?**

No. A Capability should belong to at most one Objective. If it truly enables multiple,
consider if the Objective boundaries are right.

**Q: What if an Objective scope changes mid-flight?**

Document the change in the Objective issue as a comment. Update the success criteria.
If timeline changes, update the Milestone due date. Notify stakeholders.

**Q: Can Enhancements and Defects be linked to Objectives?**

Yes, if they're critical for the Objective's success (e.g., a blocking defect during
a pilot). Otherwise, leave them unassigned to the Objective.

**Q: How do I track progress when Capabilities span multiple repos?**

Check each repo's milestone separately. The GitHub Projects board filtered by
`objective:{name}` label gives a unified cross-repo view.
