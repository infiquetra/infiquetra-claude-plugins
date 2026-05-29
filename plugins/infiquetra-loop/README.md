# infiquetra-loop

Infiquetra lifecycle workflow plugin for day-to-day engineering work.

## Commands

- `/loop` routes work to plan only, PR, merge, or nonprod deploy.
- `/office-hours`, `/ideate`, and `/brainstorm` support early thinking.
- `/strategy` maintains the root `STRATEGY.md`.
- `/plan`, `/work`, `/qa`, `/retro`, and `/resume` run the durable work loop.
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

## Deterministic Helpers

- `scripts/parse_issue.py` extracts ADR, acceptance-criteria, round, and risk hints.
- `scripts/scaffold_checkpoint.py` writes ignored resume checkpoints under
  `.claude/infiquetra-loop/`.
- `scripts/find_inflight_work.py` ranks resumable loop state.
- `scripts/load_saga_context.py` reconstructs prior issue, PR, checkpoint, and journal context.
- `scripts/discover_subissues.py` discovers GitHub sub-issues through GraphQL.
- `scripts/detect_deploy_strategy.py` classifies tag-promotion workflow coverage.
- `scripts/issue_progress.py` renders issue comments, including doc-review status when present.
