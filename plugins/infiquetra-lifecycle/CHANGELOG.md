# Changelog

## 0.2.0 - 2026-05-31

- Rename the plugin from `infiquetra-loop` to `infiquetra-lifecycle`; "loop" named only the `/loop`
  router command, not the whole idea-to-ship lifecycle the plugin covers. The `/loop` command name
  is unchanged.
- Rename the ignored runtime-state directory from `.claude/infiquetra-loop/` to
  `.claude/infiquetra-lifecycle/`; `sdlc-manager` updated in lockstep.
- Rename the handoff-envelope `loop_owner` field to `lifecycle_owner`.
- Document the command set by lifecycle phase: Think, Plan & execute, Hand off, Review, and
  Improve & route.

## Unreleased

- Add `/handoff` to route durable lifecycle artifacts to `sdlc-manager` prepared issue drafts.
- Add a thin handoff envelope helper that records source, maturity, target hints, blockers, open
  questions, and the `/create-issue --prepare` routing command without owning SDLC issue bodies.
- Teach `/plan <issue>` and `/work <issue>` to consume handoff maturity and source context from
  prepared SDLC issues.

## 0.1.0 - 2026-05-29

- Add the Infiquetra lifecycle command set from office-hours through resume.
- Add `/doc-review` for plan, requirements, and formal SDLC implementation-readiness review.
- Add durable repository artifact guidance and ignored local runtime-state guidance.
- Add helper scripts for destination selection, issue progress comments, deploy strategy
  detection, team-execution escalation, and engineering-journal triggers.
- Preserve VECU work-loop mechanics source-neutrally: issue parsing, ignored checkpoints,
  inflight resume discovery, saga context loading, sub-issue discovery, and cached deploy
  strategy detection.
