# infiquetra-lifecycle

Infiquetra engineering lifecycle plugin for day-to-day engineering work. Commands carry work
through five phases: **Think → Plan & execute → Hand off → Review → Improve & route**.

## Commands

The command set groups by lifecycle phase:

- **Think:** `/office-hours`, `/ideate`, `/brainstorm`, `/strategy`
- **Plan & execute:** `/plan`, `/work`, `/qa`, `/retro`, `/resume`
- **Hand off:** `/handoff` → `sdlc-manager`
- **Review:** `/founder-review`, `/ceo-review`, `/doc-review`, `/code-review`
- **Improve & route:** `/optimize`, `/loop`

What each command does:

- `/office-hours`, `/ideate`, and `/brainstorm` support early thinking.
- `/strategy` maintains the root `STRATEGY.md`.
- `/plan`, `/work`, `/qa`, `/retro`, and `/resume` run the durable work loop.
- `/handoff` routes durable lifecycle artifacts to `sdlc-manager` prepared issue drafts.
- `/founder-review` and `/ceo-review` review ambition, scope, and operator risk.
- `/doc-review` reviews plans, requirements, and formal SDLC artifacts for implementation
  readiness.
- `/code-review` runs a structured pre-PR review.
- `/optimize` runs metric-driven improvement loops.
- `/loop` routes work to plan only, PR, merge, or nonprod deploy.

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

Ignored local state belongs under `.claude/infiquetra-lifecycle/`. Durable, resumable work-state is
tracked as sagas: append-only, timestamped envelope logs under
`.claude/infiquetra-lifecycle/sagas/<saga_id>/`, plus a derived `state.json` index. See
[`references/saga-spec.md`](references/saga-spec.md) for the storage contract and
[`references/operator-choice.md`](references/operator-choice.md) for the execution-backend decision contract (`inline` / `team-execution` / `cc-workflows-ultracode`).

## Boundaries

- `infiquetra-deploy` owns deployment mutation.
- `team-execution` stays independent and is offered when risk, size, or parallelism justify it.
- `sdlc-manager` owns SDLC issue creation, issue comments, and board movement.
- `infiquetra-lifecycle` owns only the handoff envelope; `sdlc-manager` owns issue bodies, readiness,
  sidecars, labels, project fields, and GitHub mutation.
- `/plan <issue>` consumes `idea-ready` and `requirements-ready` handoff issues.
- `/work <issue>` consumes `plan-ready` and `resume-ready` handoff issues.

## Deterministic Helpers

- `scripts/parse_issue.py` extracts ADR, acceptance-criteria, handoff maturity, source context,
  round, and risk hints.
- `scripts/saga.py` is the saga engine: stable derived identity, save/restore/scan over the
  append-only envelope log, and gh-context aggregation.
- `scripts/scaffold_checkpoint.py` saves a saga envelope tick under
  `.claude/infiquetra-lifecycle/sagas/<saga_id>/` (thin wrapper over `saga.py`).
- `scripts/find_inflight_work.py` ranks resumable saga state.
- `scripts/load_saga_context.py` reconstructs prior issue, PR, saga, and journal context.
- `scripts/discover_subissues.py` discovers GitHub sub-issues through GraphQL.
- `scripts/detect_deploy_strategy.py` classifies tag-promotion workflow coverage.
- `scripts/issue_progress.py` renders issue comments, including doc-review status when present.
- `scripts/handoff_envelope.py` builds the thin source envelope for `/handoff`.
