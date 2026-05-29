---
name: work
description: Execute an Infiquetra plan with phase checkpoints, issue updates, test gates, and work-session summaries.
---

# Work

Use this after a plan is approved or when resuming execution from a durable plan.

## Workflow

1. Load the plan and active issue or PR.
2. Record the active pointer in `.claude/infiquetra-loop/`.
3. Execute one meaningful phase at a time.
4. After each phase, write a concise summary under `docs/work-sessions/`.
5. Comment issue progress through `sdlc-manager` with plan path, work-session path, commit SHA,
   checks run, and blockers.
6. Run hard test gates for behavior, security, infra, API, deployment, or data changes.
7. Run `/code-review` before PR or shipping gates.
8. If the destination includes nonprod deploy, hand off deployment mutation to `infiquetra-deploy`.

Do not close or move the issue until acceptance criteria and the selected destination are satisfied.
