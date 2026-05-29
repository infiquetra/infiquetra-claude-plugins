---
name: work
description: Execute an Infiquetra plan with phase checkpoints, issue updates, test gates, and work-session summaries.
---

# Work

Use this after a plan is approved or when resuming execution from a durable plan.

## Workflow

1. Load the plan and active issue or PR.
2. Record the active pointer in `.claude/infiquetra-loop/`.
3. When executing from a plan or requirements document, ask whether to run `/doc-review` first.
   If review runs and returns unresolved `P0` or `P1` findings, block execution unless the user
   explicitly overrides and provides a rationale.
4. Execute one meaningful phase at a time.
5. After each phase, write a concise summary under `docs/work-sessions/`.
6. Comment issue progress through `sdlc-manager` with plan path, work-session path, commit SHA,
   checks run, blockers, and any doc-review artifact, findings, block status, or override
   rationale.
7. Run hard test gates for behavior, security, infra, API, deployment, or data changes.
8. Run `/code-review` before PR or shipping gates.
9. If the destination includes nonprod deploy, hand off deployment mutation to `infiquetra-deploy`.

Do not close or move the issue until acceptance criteria and the selected destination are satisfied.

For doc-review gating, use same-session review output or the latest matching artifact under
`docs/reviews/`. Do not treat chat memory alone as durable evidence after resume.
