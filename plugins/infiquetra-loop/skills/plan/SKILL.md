---
name: plan
description: Create durable Infiquetra implementation plans with issue, review, test, and deploy gates.
---

# Plan

Use this for multi-step work where chat history is not a reliable source of truth.

## Workflow

1. Read the issue, relevant docs, repository guidance, and local code before planning.
2. Ask for destination if unknown: plan only, PR, merge, or nonprod deploy.
3. Ask whether to file an SDLC issue first for non-trivial ad-hoc work.
4. Write concise plans under `docs/plans/`.
5. Include acceptance criteria, scope, files likely to change, checks, issue updates, review gates,
   deploy gates when relevant, and resume notes.
6. Offer `team-execution` when risk, size, or parallelism justify the cost.

Keep the plan decision-complete but short enough to maintain during execution.
