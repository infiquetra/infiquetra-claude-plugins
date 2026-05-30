---
name: work
description: Execute an Infiquetra plan with phase checkpoints, issue updates, test gates, and work-session summaries.
---

# Work

Use this after a plan is approved or when resuming execution from a durable plan.

## Workflow

1. Load the plan and active issue or PR.
2. If the input is an issue, run `scripts/parse_issue.py` and inspect the `handoff` object.
3. Proceed directly from handoff issues marked `plan-ready` or `resume-ready` when the issue has
   plan-grade execution context or linked source context.
4. For `idea-ready` or `requirements-ready` handoff issues, route to `/plan <issue>` unless the
   user explicitly overrides the missing plan step.
5. Record the active pointer in `.claude/infiquetra-loop/`.
6. When executing from a plan or requirements document, ask whether to run `/doc-review` first.
   If review runs and returns unresolved `P0` or `P1` findings, block execution unless the user
   explicitly overrides and provides a rationale.
7. Execute one meaningful phase at a time.
8. After each phase, write a concise summary under `docs/work-sessions/`.
9. Comment issue progress through `sdlc-manager` with plan path, work-session path, commit SHA,
   checks run, blockers, handoff maturity/source, and any doc-review artifact, findings, block
   status, or override rationale.
10. Run hard test gates for behavior, security, infra, API, deployment, or data changes.
11. Run `/code-review` before PR or shipping gates.
12. If the destination includes nonprod deploy, hand off deployment mutation to `infiquetra-deploy`.

Do not close or move the issue until acceptance criteria and the selected destination are satisfied.

For doc-review gating, use same-session review output or the latest matching artifact under
`docs/reviews/`. Do not treat chat memory alone as durable evidence after resume.
