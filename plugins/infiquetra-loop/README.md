# infiquetra-loop

Infiquetra lifecycle workflow plugin for day-to-day engineering work.

## Commands

- `/loop` routes work to plan only, PR, merge, or nonprod deploy.
- `/office-hours`, `/ideate`, and `/brainstorm` support early thinking.
- `/strategy` maintains the root `STRATEGY.md`.
- `/plan`, `/work`, `/qa`, `/retro`, and `/resume` run the durable work loop.
- `/handoff` routes durable lifecycle artifacts to `sdlc-manager` prepared issue drafts.
- `/founder-review` and `/ceo-review` review ambition, scope, and operator risk.
- `/doc-review` reviews plans, requirements, and formal SDLC artifacts for implementation
  readiness.
- `/code-review` runs a structured pre-PR review.
- `/optimize` runs metric-driven improvement loops.

## Artifact Model

Durable artifacts are repo docs:

- `STRATEGY.md`
- `docs/ideation/`
- `docs/brainstorms/`
- `docs/plans/`
- `docs/reviews/`
- `docs/qa/`
- `docs/work-sessions/`
- `docs/retros/`
- `docs/engineering-journal/`

Ignored local state belongs under `.claude/infiquetra-loop/`.

## Boundaries

- `infiquetra-deploy` owns deployment mutation.
- `team-execution` stays independent and is offered when risk, size, or parallelism justify it.
- `sdlc-manager` owns SDLC issue creation, issue comments, and board movement.
- `infiquetra-loop` owns only the handoff envelope; `sdlc-manager` owns issue bodies, readiness,
  sidecars, labels, project fields, and GitHub mutation.
- `/plan <issue>` consumes `idea-ready` and `requirements-ready` handoff issues.
- `/work <issue>` consumes `plan-ready` and `resume-ready` handoff issues.

## Deterministic Helpers

- `scripts/parse_issue.py` extracts ADR, acceptance-criteria, handoff maturity, source context,
  round, and risk hints.
- `scripts/scaffold_checkpoint.py` writes ignored resume checkpoints under
  `.claude/infiquetra-loop/`.
- `scripts/find_inflight_work.py` ranks resumable loop state.
- `scripts/load_saga_context.py` reconstructs prior issue, PR, checkpoint, and journal context.
- `scripts/discover_subissues.py` discovers GitHub sub-issues through GraphQL.
- `scripts/detect_deploy_strategy.py` classifies tag-promotion workflow coverage.
- `scripts/issue_progress.py` renders issue comments, including doc-review status when present.
- `scripts/handoff_envelope.py` builds the thin source envelope for `/handoff`.
