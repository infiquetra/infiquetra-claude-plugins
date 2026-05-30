---
name: plan
description: Create durable Infiquetra implementation plans with issue, review, test, and deploy gates.
---

# Plan

Use this for multi-step work where chat history is not a reliable source of truth.

## Workflow

1. Read the issue, relevant docs, repository guidance, and local code before planning.
2. If the input is an issue, run `scripts/parse_issue.py` and inspect the `handoff` object.
3. For `idea-ready` or `requirements-ready` handoff issues, create or update a durable plan from
   the issue and linked source context.
4. For `plan-ready` or `resume-ready` handoff issues, tell the user `/work <issue>` is the more
   direct consumer unless they explicitly want to re-plan.
5. Ask for destination if unknown: plan only, PR, merge, or nonprod deploy.
6. Ask whether to file an SDLC issue first for non-trivial ad-hoc work.
7. Write concise plans under `docs/plans/`.
8. Include acceptance criteria, scope, files likely to change, checks, issue updates, review gates,
   deploy gates when relevant, and resume notes.
9. Comment compact progress back to the issue with plan path, handoff maturity, and source link
   when an issue is available.
10. Offer `team-execution` when risk, size, or parallelism justify the cost.

Keep the plan decision-complete but short enough to maintain during execution.
