---
name: work
description: Execute an Infiquetra plan with per-phase saga saves, issue updates, test gates, and work-session summaries.
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
5. Save a saga tick under `.claude/infiquetra-lifecycle/sagas/<saga_id>/` to record the active pointer.
   See `references/saga-spec.md` for the saga envelope contract.
6. When executing from a plan or requirements document, ask whether to run `/doc-review` first.
   If review runs and returns unresolved `P0` or `P1` findings, block execution unless the user
   explicitly overrides and provides a rationale.
7. Before executing, pick an execution backend: `inline` for small focused changes,
   `team-execution` for cross-repo, security, infra, large, or deployment-sensitive work, and
   `cc-workflows-ultracode` for many independent parallel streams.
   Use `references/operator-choice.md` as the selection rubric.
8. Execute one meaningful phase at a time.
9. After each phase, write a concise summary under `docs/work-sessions/`.
10. Comment issue progress through `sdlc-manager` with plan path, work-session path, commit SHA,
    checks run, blockers, handoff maturity/source, and any doc-review artifact, findings, block
    status, or override rationale.
11. Run hard test gates for behavior, security, infra, API, deployment, or data changes.
12. Run `/code-review` before PR or shipping gates.
13. If the destination includes nonprod deploy, hand off deployment mutation to `infiquetra-deploy`.

Do not close or move the issue until acceptance criteria and the selected destination are satisfied.

For doc-review gating, use same-session review output or the latest matching artifact under
`docs/reviews/`. Do not treat chat memory alone as durable evidence after resume.
