# Work Hierarchy Reference

Practical reference for the Infiquetra work hierarchy. Source of truth:
`$INFIQUETRA_SDLC_PATH/docs/process/work-hierarchy.md` and
`$INFIQUETRA_SDLC_PATH/config/sdlc-schema.json`.

---

## The Model

```
Initiative
  +-- Objective
        +-- Capability / Enhancement / Defect / Exploration / Context Update
```

Initiative and Objective are grouping and reporting fields. Actual execution happens on
issues, usually under an Objective parent issue or milestone when the work needs a delivery
target.

---

## Initiative

**Definition**: A broad strategic grouping that may span multiple Objectives.

**GitHub construct**: Project field option, not a label by default.

Use an Initiative when:

- The work groups multiple Objectives.
- Reporting needs a stable strategic category.
- The grouping will outlive a single short task.

Do not create an Initiative for one-off work or raw operator intent.

---

## Objective

**Definition**: A time-bounded deliverable set with a target date.

**GitHub constructs**:

- Objective issue, when the Objective itself needs discussion and acceptance criteria.
- Project `Objective` field option for reporting.
- GitHub Milestone when progress rollup by repo is useful.
- Native GitHub sub-issues for child work.

Use an Objective when multiple issues must land together or when Jeff needs a progress view.

---

## Capability And Other Work Items

Capabilities, enhancements, defects, explorations, and context updates are execution cards.
They flow through the target board:

| Board | Flow |
|-------|------|
| Jeff Intent / Asgard | Idea -> Shaping -> Ready -> Active -> Verify -> Done |
| Olympus | Backlog -> Ready -> Planning -> Assigned -> In Review -> Done / Closed |

Use native GitHub sub-issues for parent/child structure. Do not rely on removed Beads/Dolt
task state.

---

## GitHub Constructs Summary

| Level | Preferred construct | Optional construct |
|-------|---------------------|--------------------|
| Initiative | Project field option | Label only when repo-local filtering needs it |
| Objective | Objective issue + project field option | Milestone for due-date rollup |
| Work item | GitHub Issue / PR card | Native sub-issue relationship |

---

## Common Questions

**Do I need an Objective for every Capability?**
No. Use Objectives when a time-bounded delivery target or progress rollup is useful.

**Can Enhancements and Defects belong to Objectives?**
Yes, when they materially affect the Objective. Otherwise leave them outside the Objective.

**How do I track progress toward an Objective?**
Use the Objective project field, the Objective issue's sub-issue tree, and optional
GitHub Milestone progress.
