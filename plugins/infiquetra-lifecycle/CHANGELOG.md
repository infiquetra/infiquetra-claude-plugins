# Changelog

## 0.3.0 - 2026-06-01

- Rebuild `/ideate` from a thin facilitative stub into a full divergent→convergent engine ported from
  compound-engineering and adapted to the infiquetra world: parallel frame agents generate many
  grounded candidates, the orchestrator critiques all and presents only the survivors, and cut ideas
  stay first-class and revivable. Adds a two-way thought-partnership — the operator's seed ideas feed
  *into* the frame agents (build on / challenge / combine) and face the identical critique — and a
  revival state machine that re-enters the filter with new evidence, preserving explicit rejection as
  the quality mechanism.
- Add infiquetra-specific grounding to `/ideate`: a grounding-fit gate (proceed / decline /
  recommend `/office-hours` / ask) weighing idea breadth against available grounding; a
  context-library reader (`*-context-library` repos via `gh`, local-clone preferred); a named-repo
  reader for multi-repo asks; read-only `gh` issue-theme clustering on backlog intent; and smart-auto
  web research for the cross-domain-analogy frame. Adaptive frame count (1–6) scales to scope.
- Rebuild `/brainstorm` into a thinking-partner engine that deep-dives one chosen idea (a `/ideate`
  survivor or a named topic) into a right-sized requirements document: scope assessment, a product
  pressure-test, one-question-at-a-time dialogue, 2–3 approaches with a non-obvious angle, and a
  `requirements-ready` artifact under `docs/brainstorms/` for `/plan`.
- Add reference files: `skills/ideate/references/convergence-and-partnership.md`,
  `skills/ideate/references/ideation-artifact.md`, and
  `skills/brainstorm/references/requirements-sections.md`. Self-contained — no runtime dependency on
  compound-engineering.
- Add `/handoff` to route durable lifecycle artifacts to `sdlc-manager` prepared issue drafts, with a
  thin handoff-envelope helper that records source, maturity, target hints, blockers, open questions,
  and the `/create-issue --prepare` routing command without owning SDLC issue bodies. Teach
  `/plan <issue>` and `/work <issue>` to consume handoff maturity and source context from prepared
  SDLC issues.

## 0.2.0 - 2026-05-31

- Rename the plugin from `infiquetra-loop` to `infiquetra-lifecycle`; "loop" named only the `/loop`
  router command, not the whole idea-to-ship lifecycle the plugin covers. The `/loop` command name
  is unchanged.
- Rename the ignored runtime-state directory from `.claude/infiquetra-loop/` to
  `.claude/infiquetra-lifecycle/`; `sdlc-manager` updated in lockstep.
- Rename the handoff-envelope `loop_owner` field to `lifecycle_owner`.
- Document the command set by lifecycle phase: Think, Plan & execute, Hand off, Review, and
  Improve & route.

## 0.1.0 - 2026-05-29

- Add the Infiquetra lifecycle command set from office-hours through resume.
- Add `/doc-review` for plan, requirements, and formal SDLC implementation-readiness review.
- Add durable repository artifact guidance and ignored local runtime-state guidance.
- Add helper scripts for destination selection, issue progress comments, deploy strategy
  detection, team-execution escalation, and engineering-journal triggers.
- Preserve VECU work-loop mechanics source-neutrally: issue parsing, ignored checkpoints,
  inflight resume discovery, saga context loading, sub-issue discovery, and cached deploy
  strategy detection.
