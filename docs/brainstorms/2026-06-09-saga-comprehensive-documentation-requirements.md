---
date: 2026-06-09
topic: saga-comprehensive-documentation
maturity: requirements-ready
source: docs/ideation/2026-06-09-saga-comprehensive-documentation-ideation.md - Ranked Survivors 1-7
---

# Requirements: Saga Comprehensive Documentation

## Summary

Build a v1 Saga documentation system that makes the plugin understandable from the repository alone: an atlas-style manual, comparable command cards, a state/readiness passport, scenario journeys, cross-host boundary docs, a source-generated visual kit, and a narrow drift guard.

## Problem Frame

Saga is now a full lifecycle spine rather than a small command bundle. The current README accurately names the command groups, but it does not teach the operating model: where a user starts, which command owns which phase, which commands are off-chain, how readiness maturity works, when state is stored, and where Saga stops in favor of `mission-control`, `deploy`, or `team-execution`.

The strongest source of truth is already in the repo, especially the dispatch table and saga spec. The documentation problem is that those facts are distributed across wrappers, SKILL files, references, scripts, and journal entries. A new user should not need to reverse-engineer the lifecycle before using the plugin.

## Key Decisions

**Atlas-first, not catalog-first.** The README becomes the front-door atlas and index into deeper docs. The command catalog remains important, but it sits under the operating model rather than replacing it.

**Visuals are generated from source contracts.** V1 includes the source model and first rendered visuals. Mermaid may be useful as a sketch or fallback, but the primary presentation assets must be generated from maintained source data that reflects Saga commands, routes, readiness, and boundaries.

**Command docs are decision cards.** Every command gets a comparable card optimized for command selection and adjacent-command comparison. `/ceo-review` is documented as an alias, not a separate lifecycle node.

**Readiness is a passport, not stored state.** The docs must clearly separate stored saga state from derived handoff maturity, including the off-chain `/spec` case.

**Codex is an adapter example.** The Codex port informs the docs, but Claude Saga remains the source surface for this repo. Cross-host documentation must distinguish invariant lifecycle semantics from host-specific mechanics.

## Actors

- A1. **First-time Saga user.** Needs to understand what Saga is, where to start, and which command to invoke.
- A2. **Active operator.** Needs to route a real work situation without reading every SKILL file.
- A3. **Maintainer.** Needs to update Saga docs safely when commands, routes, state, or host behavior change.
- A4. **Planner or reviewer.** Needs requirements, plans, and reviews to cite the same lifecycle language and readiness model.
- A5. **Port reader.** Needs to compare Claude Saga and Codex Saga without confusing host adapters for core Saga semantics.

## Requirements

**Reader path and manual structure**

- R1. The README must present Saga as an operating model first: lifecycle phases, command ownership, off-chain routes, gates, handoff, resume, destination horizon, and plugin-family boundaries.
- R2. The README must act as an index into deeper manual pages rather than carrying the entire documentation payload inline.
- R3. The manual must include dedicated coverage for lifecycle, command selection, state/readiness, scenarios, boundaries, and visuals.
- R4. The documentation must state that Saga has 18 command files and 17 routable commands because `/ceo-review` aliases `/founder-review`.

**Command selection**

- R5. Every command must have a comparable decision card covering purpose, use when, do not use when, inputs, outputs, durable artifacts, saga read/write behavior, routes in, routes out, gates, ownership boundaries, common mistakes, and one example invocation.
- R6. Adjacent command pairs must be distinguishable from the docs, including `/office-hours` vs `/ideate`, `/ideate` vs `/brainstorm`, `/brainstorm` vs `/spec`, `/plan` vs `/doc-review`, `/qa` vs `/optimize`, `/strategy` vs `/founder-review`, and `/loop` vs `/resume`.
- R7. Command cards must avoid duplicating full SKILL prose. They are selection surfaces, not replacement source docs.

**Lifecycle, state, and readiness**

- R8. The docs must explain the three stored saga state axes: `lifecycle_phase`, `phase_status`, and `status`.
- R9. The docs must explain that `maturity` is derived at handoff time and must not be stored as saga state.
- R10. The docs must map durable artifact roots to handoff maturity: ideation to `idea-ready`, brainstorm/spec to `requirements-ready`, plans/reviews to `plan-ready`, and work-session/branch evidence to `resume-ready`.
- R11. The docs must explain which maturity levels are consumed by `/plan` and which are consumed by `/work`.
- R12. The docs must call out off-chain commands and their state behavior, especially `/spec`, `/investigate`, `/optimize`, `/strategy`, and `/retro`.

**Visual system**

- R13. V1 must define a structured source model for the visual kit that represents commands, routes, gates, maturity mappings, artifact roots, destinations, execution backends, and plugin-family boundaries.
- R14. V1 must render the first source-generated visual assets from that model. The minimum set is a lifecycle atlas, a state/readiness ladder, a command matrix, and an ownership boundary map.
- R15. Rendered visuals must be readable in the README/manual and usable in a 16:9 presentation context without redrawing.
- R16. Every rendered visual must have a text fallback or nearby table so the docs remain useful in plain Markdown.
- R17. The visual source model, not manually edited image output, must be the maintained truth for diagrams.

**Scenarios and examples**

- R18. The manual must include a scenario journey gallery organized by user situation rather than command name.
- R19. Each scenario must show the user's starting statement, selected command, produced artifact or state effect, stop condition, and next route.
- R20. The minimum scenario set must cover vague idea, chosen idea, vague WHAT, requirements-ready handoff, plan review, PR boundary, post-merge QA, QA failure, root-cause investigation, metric optimization, strategy refresh, cross-team handoff, cold resume, and retro learning.

**Boundaries and portability**

- R21. The docs must show what Saga owns and what it must not own: Saga owns lifecycle choice, local saga state, routing, and handoff envelopes; `mission-control` owns SDLC mutation; `deploy` owns deployment mutation; `team-execution` owns reviewer/validator orchestration.
- R22. The docs must compare Claude Saga and Codex Saga at the right level: command surface, state root, backend availability, host-specific omissions, and invariant lifecycle semantics.
- R23. Cross-host docs must treat the Codex port as an adapter example, not as a replacement source of truth for Claude Saga.

**Drift prevention**

- R24. V1 must include a coverage matrix that accounts for commands, routes, maturity values, artifact roots, execution backends, external owners, scenario coverage, and generated visuals.
- R25. V1 must include a narrow validation guard that catches stale command count, alias status, missing command cards, missing visual coverage, or broken source references.
- R26. Validation must start narrow enough to avoid noisy false positives; broader style or prose-quality gates can be deferred.

## Key Flows

- F1. **New-reader flow.** A first-time user opens the README, sees the lifecycle atlas, identifies their current situation, follows the relevant scenario or command card, and knows which command to run next.
- F2. **Command-selection flow.** An operator compares adjacent command cards, selects the command that owns the current phase, and sees the expected artifact/state effect before running it.
- F3. **State/readiness flow.** A user starts from an artifact path or saga state, uses the passport/ladders to determine readiness maturity, and routes to `/plan`, `/work`, `/handoff`, or a non-spine command without inventing state.
- F4. **Visual-maintenance flow.** A maintainer updates the source model when a command, route, maturity value, or owner changes, regenerates visuals, and runs the drift guard.
- F5. **Cross-host flow.** A reader compares Claude Saga and Codex Saga, identifies what changed because of the host, and preserves invariant Saga ownership and routing semantics.

## Acceptance Examples

- AE1. **Given** a user says "I have a rough idea but do not know the frame," **when** they read the scenario gallery, **then** the docs route them to `/office-hours` or `/ideate` with a reason for the distinction.
- AE2. **Given** a user has `docs/specs/example-spec.md`, **when** they use the state/readiness passport, **then** they can identify it as `requirements-ready` without believing `spec` is a stored lifecycle phase.
- AE3. **Given** a user asks whether `/qa` or `/optimize` should run, **when** they compare command cards, **then** they see `/qa` is a shipped-change acceptance gate and `/optimize` is a metric-driven experiment loop.
- AE4. **Given** a maintainer adds or renames a Saga command, **when** they run the relevant validation, **then** missing command-card or coverage-matrix updates are caught.
- AE5. **Given** a reader is explaining Saga in a meeting, **when** they use the rendered lifecycle atlas and ownership boundary map, **then** the graphics remain legible without opening source files or redrawing diagrams.

## Success Criteria

- A new user can identify the right Saga command for common situations without opening individual SKILL files.
- A maintainer can explain stored saga state, derived maturity, and handoff consumers without consulting `saga.py`.
- The first visual kit is presentation-worthy enough to use in a README, docs page, or slide without manual cleanup.
- The docs make off-chain commands and plugin-family ownership boundaries explicit.
- A narrow drift guard prevents the command surface or lifecycle map from silently falling out of sync.

## Scope Boundaries

**In v1**

- README atlas/index.
- Manual pages for lifecycle, commands, state/readiness, scenarios, boundaries, and visuals.
- Structured source model for visual generation and coverage.
- First rendered visual assets from that model.
- Coverage matrix and narrow validation guard.

**Deferred for later**

- Full interactive static docs site.
- Separate presentation deck.
- Broader prose-quality or visual-polish lint beyond the first drift guard.
- Additional visual formats beyond the first generated asset set.

**Outside this work**

- Rewriting Saga command behavior.
- Copying Codex docs directly into Claude Saga docs.
- Treating hand-maintained Mermaid/PNG diagrams as the primary visual source.
- Replacing SKILL files with prose summaries.

## Dependencies / Assumptions

- The dispatch table and saga spec are the authoritative sources for lifecycle and state semantics.
- Command wrappers are the best starting source for command-card purpose, argument, and boundary text.
- The current Saga formatting contract applies to generated documentation: short paragraphs, summary-first sections, tables for comparative data, and no stacked bold-label fields.
- Exact visual tooling, source-model file format, and generated asset paths are deferred to `/plan`.
- The first drift guard should reuse existing Python/pytest validation patterns where practical, but exact implementation belongs to `/plan`.

## Outstanding Questions

**Deferred to planning**

- Which rendering tool should produce the first visual assets.
- What exact source-model file format should represent commands/routes/readiness/boundaries.
- Which generated asset formats should be committed first beyond SVG/PNG/HTML candidates.
- Whether the drift guard belongs in the existing Saga doc-format test, plugin validator, or a new focused test.

## Sources / Research

- `docs/ideation/2026-06-09-saga-comprehensive-documentation-ideation.md`
- `plugins/saga/README.md`
- `plugins/saga/commands/`
- `plugins/saga/skills/loop/references/dispatch-table.md`
- `plugins/saga/references/saga-spec.md`
- `plugins/saga/skills/handoff/SKILL.md`
- `plugins/saga/references/operator-choice.md`
- `plugins/saga/references/formatting-style.md`
- `tests/test_saga_doc_formatting.py`
- `docs/engineering-journal/LEARNINGS.md`
- `docs/engineering-journal/DECISIONS.md`
- `../infiquetra-codex-plugins/plugins/saga/README.md`
- `../infiquetra-codex-plugins/plugins/saga/PORTABILITY.md`
- `../infiquetra-codex-plugins/docs/portability/saga-family-state-policy.md`
- `../infiquetra-codex-plugins/docs/portability/saga-family-capability-map.md`
