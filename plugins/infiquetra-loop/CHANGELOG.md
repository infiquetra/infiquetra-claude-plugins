# Changelog

## Unreleased

- Add `/handoff` to route durable lifecycle artifacts to `sdlc-manager` prepared issue drafts.
- Add a thin handoff envelope helper that records source, maturity, target hints, blockers, open
  questions, and the `/create-issue --prepare` routing command without owning SDLC issue bodies.

## 0.1.0 - 2026-05-29

- Add the Infiquetra lifecycle command set from office-hours through resume.
- Add `/doc-review` for plan, requirements, and formal SDLC implementation-readiness review.
- Add durable repository artifact guidance and ignored local runtime-state guidance.
- Add helper scripts for destination selection, issue progress comments, deploy strategy
  detection, team-execution escalation, and engineering-journal triggers.
- Preserve VECU work-loop mechanics source-neutrally: issue parsing, ignored checkpoints,
  inflight resume discovery, saga context loading, sub-issue discovery, and cached deploy
  strategy detection.
