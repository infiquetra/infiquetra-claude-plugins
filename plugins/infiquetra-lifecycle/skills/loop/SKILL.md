---
name: loop
description: |
  Infiquetra lifecycle router for strategy, ideation, planning, work execution, QA, issue
  progress, engineering-journal updates, review, SDLC handoff, deployment handoff, retro, and
  resume.
---

# Loop

Use this skill when the user wants to start, route, or continue Infiquetra work.

## Start

At loop start, identify the entry point and ask how far to take the work when it is not already
clear:

- `plan-only`: create durable thinking and stop before implementation.
- `pr`: implement, verify, and prepare a PR.
- `merge`: continue through PR readiness and merge coordination.
- `nonprod-deploy`: continue through nonprod deployment evidence.

Use `scripts/lifecycle_state.py` for destination normalization and escalation decisions.
Use `scripts/parse_issue.py` for ADR, acceptance-criteria, round, and risk hints when an issue
body is available.

When the lifecycle reaches a branch point, ask whether to carry the work forward in the current
thread or hand it off. If handing off, route to `/handoff`.

## Durable Artifacts

Repository docs are the source of truth:

- `STRATEGY.md`
- `docs/ideation/`
- `docs/brainstorms/`
- `docs/plans/`
- `docs/reviews/`
- `docs/qa/`
- `docs/work-sessions/`
- `docs/retros/`
- `docs/engineering-journal/`

Ignored local runtime state lives under `.claude/infiquetra-lifecycle/`. Use it only for active session
pointers, durable saga envelope state, API caches, validator JSON, and resume scratch data.
Durable work-state is tracked as sagas; see `references/saga-spec.md` for the saga contract that
`/plan`, `/work`, `/resume`, and `/loop` implement against.

## SDLC Issue Behavior

For non-trivial ad-hoc work, ask whether to file an SDLC issue first through `sdlc-manager`.
For lifecycle artifacts that another team or session should pick up, use `/handoff` to prepare a
source envelope and route to `sdlc-manager` `/create-issue --prepare`.
If an issue exists, keep issue progress current:

- Start comment: selected destination, plan link, and scope summary.
- Phase comments: progress, committed `docs/work-sessions/` summary, commit SHA, checks run,
  and blockers.
- PR comment: PR link, review status, and remaining gates.
- Nonprod comment: deployment status, workflow URL, and evidence link.
- Completion comment: close or move only after acceptance criteria and destination are satisfied.

Use `scripts/issue_progress.py` to render comments. Use `sdlc-manager` for issue comments and board
movement at Infiquetra SDLC phase boundaries.

## Gates

- Behavior, security, infra, API, deployment, and data changes require tests.
- Docs, config, and trivial changes may skip tests only with an explicit rationale.
- Before `/work` executes from a plan or requirements document, ask whether to run `/doc-review`.
  If review runs and reports unresolved `P0` or `P1` findings, block execution unless the user
  explicitly overrides and gives a rationale.
- Run an engineering review before execution on risky plans and before shipping gates.
- Suggest founder review for strategy, scope, product, or user-facing work.

## Integrations

- Use `infiquetra-deploy` only when the selected destination includes deployment.
- Offer or invoke `team-execution` for cross-repo, security, infra, large, deployment-sensitive,
  or high-parallelism work.
- Use `/handoff` for SDLC issue handoff. `sdlc-manager` owns issue bodies, prepared drafts,
  readiness, labels, board fields, and GitHub mutation.
- Fall back cleanly when `infiquetra-deploy`, `team-execution`, or `sdlc-manager` is unavailable:
  explain the missing integration and continue with manual evidence where safe.

## Resume

Resume from durable artifacts first: plan, issue, PR, work sessions, QA notes, retros, and
engineering-journal entries. Use `.claude/infiquetra-lifecycle/` only to recover saga state and raw
scratch data. For recovery mechanics, use `scripts/find_inflight_work.py`,
`scripts/load_saga_context.py`, and `scripts/scaffold_checkpoint.py`.
