# Board Workflow Reference

Condensed reference for the Infiquetra GitHub Projects boards. The canonical source of
truth is `$INFIQUETRA_SDLC_PATH/config/sdlc-schema.json`, with prose context in
`$INFIQUETRA_SDLC_PATH/docs/process/board-topology.md` and
`$INFIQUETRA_SDLC_PATH/docs/process/kanban-workflow.md`.

---

## Boards

| Project key | Board | Purpose |
|-------------|-------|---------|
| `jeff-intent` | Jeff Intent | Raw operator intent, approvals, personal/operator work, and shaping |
| `asgard` | Asgard | Jeff-proximal rapid action, incubation, and mission-mode work |
| `mount-olympus` | Olympus | Primary autonomous engineering execution pipeline |

Prefer project views over new boards until scale, automation, or reporting needs justify
a separate board.

---

## Workflows

### Jeff Intent And Asgard

```
Idea -> Shaping -> Ready -> Active -> Verify -> Done
```

| Status | Purpose |
|--------|---------|
| Idea | Captured thought or opportunity. Not shaped enough for execution. |
| Shaping | Intent is being clarified, scoped, or turned into an actionable card. |
| Ready | Work is shaped enough to route or start. Jeff Intent must name a target team before promotion. |
| Active | The owner is working the card. |
| Verify | Outcome is being checked before closure or promotion. |
| Done | Completed or intentionally closed for this board. |

Asgard modes:

| Mode | Use |
|------|-----|
| Rapid Action | Reversible, time-sensitive work that benefits from low ceremony. |
| Incubator | Exploratory work likely to define future Olympus execution. |
| Mission | Focused, high-leverage work close to Jeff with a clear outcome. |

### Mount Olympus

```
Backlog -> Ready -> Planning -> Assigned -> In Review -> Done / Closed
```

| Status | Purpose |
|--------|---------|
| Backlog | Accepted but not yet ready for engineering execution. |
| Ready | Meets issue schema, has acceptance criteria, and is eligible for dispatch. |
| Planning | Plan or execution approach is being prepared or reviewed. |
| Assigned | An agent owns implementation and is within WIP capacity. |
| In Review | PR, work artifact, or verification evidence is under team-owned review. |
| Done | Work is completed. |
| Closed | Work is closed without further active flow. |

Pause states: `Plan-Approved`, `Needs Review`, `Needs Question`, `Blocked`, `Cancelled`.

Olympus still exposes a live `In Progress` option. Treat it as a live legacy option:
display it when present, but use `Assigned` for new work. Older status names such as
`In Development`, `E2E Testing`, `Deployment Ready`, and `Deployed` are legacy migration
terms. Deployment state belongs in deployment fields and GitHub Deployments/Environments,
not in the core Status workflow.

---

## WIP Limits

| Board | Status | Limit |
|-------|--------|-------|
| Jeff Intent | Shaping | 10 |
| Jeff Intent | Ready | 10 |
| Jeff Intent | Active | 5 |
| Jeff Intent | Verify | 5 |
| Asgard | Shaping | 8 |
| Asgard | Ready | 8 |
| Asgard | Active | 5 |
| Asgard | Verify | 5 |
| Olympus | Ready | 10 |
| Olympus | Planning | 3 |
| Olympus | Assigned | 3 per assigned agent |
| Olympus | In Review | 5 |

When a limit is exceeded, finish or unblock current work before pulling more into that status.
Critical defects can temporarily override WIP, but the exception should be visible in the card.

---

## Standup Format

Walk right-to-left through the relevant board:

| Board | Review order |
|-------|--------------|
| Jeff Intent / Asgard | Done -> Verify -> Active -> Ready -> Shaping -> Idea |
| Olympus | Closed -> Done -> In Review -> Assigned -> Planning -> Ready -> Backlog |

Ask:

- What is terminal and safe to archive?
- What is waiting for verification or review?
- What is actively owned, and is it aging?
- What is blocked or waiting on Jeff?
- What should move next, and what should stay out of WIP?

---

## Common Scenarios

### Raw Intent From Jeff

1. Capture on Jeff Intent as `Idea`.
2. Shape until target team and context pack are clear.
3. Move to `Ready`.
4. Route to Asgard, Olympus, Jeff, or External/Deferred based on target team.

### Explicit Cross-Team Transfer

1. Treat Asgard and Olympus as sibling target boards, not stages in a default funnel.
2. Keep work on the selected board unless an operator explicitly routes, transfers, clones, or links it elsewhere.
3. When a transfer is requested, make the receiving issue self-contained: target repo or surface, acceptance criteria, verification, risk, approvals, and context links must be clear.

### Olympus Engineering Flow

1. Start in `Backlog` or `Ready` depending on issue maturity.
2. Move through `Planning`, `Assigned`, and `In Review`.
3. Close as `Done` or `Closed`.
4. Track environment promotion separately through deployment fields and deployment records.

---

## Metrics Boundaries

Cycle time starts when active ownership begins:

| Board | Start | Terminal |
|-------|-------|----------|
| Jeff Intent / Asgard | Active | Done |
| Olympus | Assigned | Done, Closed, Cancelled |

Legacy Olympus timeline values may still include `In Progress`, `In Development`, or
`Deployed`; tooling may read them for history but should not create new cards with those statuses.
