---
date: 2026-06-09
topic: saga-comprehensive-documentation
focus: comprehensive Saga plugin documentation, lifecycle atlas, state/readiness, scenarios, visuals, Codex-port influence
scope: broad
repo: infiquetra-claude-plugins
maturity: idea-ready
---

# Ideation: Saga Comprehensive Documentation

## Grounding Context

**Repo:** `infiquetra-claude-plugins` is a Python/uv Claude plugin monorepo with plugin sources under `plugins/`, validation under `scripts/` and `marketplace/`, tests under `tests/`, and durable lifecycle docs under `docs/`. The `saga` plugin is the lifecycle spine. Its README gives a concise five-phase grouping, but a new reader has to assemble the full model from the README, command wrappers, skill docs, dispatch table, saga spec, operator-choice, and journal.

**Verified surfaces:** `plugins/saga/README.md` groups Saga around Think, Plan & execute, Hand off, Review, and Improve & route. `plugins/saga/skills/loop/references/dispatch-table.md` is the strongest lifecycle atlas source: routable commands, shipped/stub state, cold-start routing, the main chain, off-chain commands, gates, and destination horizons. `plugins/saga/references/saga-spec.md` is the state source of truth: `lifecycle_phase`, `phase_status`, and `status` are stored; `maturity` is derived at `/handoff` time.

**State/readiness:** The artifact path mapping is central. `docs/ideation/` maps to `idea-ready`; `docs/brainstorms/` and `docs/specs/` map to `requirements-ready`; `docs/plans/` and `docs/reviews/` map to `plan-ready`; `docs/work-sessions/` and branch refs map to `resume-ready`. `/spec` is off-chain: it produces a `requirements-ready` source without adding a `spec` lifecycle phase.

**Journal guidance:** Saga schema fields are read by humans and LLMs rather than a field-level parser, so documentation should optimize for legibility. The journal also warns that adaptation notes and campaign briefs are hypotheses: source mechanics must be verified before turning them into diagrams or docs.

**Named repo:** `infiquetra-codex-plugins` was consulted as an adapter example. The Codex port is useful because it documents boundaries, state roots, portability/capability maps, known-use mappings, and host-specific behavior. It did not contain a hidden lifecycle-atlas PNG/SVG asset; the useful pattern is structural, especially dispatch-table-as-atlas.

## Topic Axes

- **A1** - Reader orientation and information architecture.
- **A2** - Command catalog and selection UX.
- **A3** - Lifecycle, state, and readiness maturity model.
- **A4** - Presentation-worthy visuals and source-generated assets.
- **A5** - Scenarios, examples, and user journeys.
- **A6** - Cross-host/portability and plugin-family boundaries.

## At A Glance

The survivor set points to one combined documentation system.

| # | Survivor | Axis | Decision it settles | Confidence | Complexity |
|---|---|---|---|:---:|:---:|
| 1 | Saga Atlas Manual | A1 | The README becomes the atlas/index, not the whole manual | 92 | Med |
| 2 | Source-Generated Lifecycle Visual Kit | A4 | Visuals come from source contracts, not hand drawings | 88 | High |
| 3 | Every-Command Decision Cards | A2 | Every command gets a comparable selection surface | 90 | Med |
| 4 | State And Readiness Passport | A3 | Stored state and derived maturity are explained separately | 91 | Low-Med |
| 5 | Scenario Journey Gallery | A5 | Users learn by situation as well as command name | 86 | Med |
| 6 | Cross-Host Boundary Map | A6 | Claude/Codex and plugin-family boundaries are explicit | 84 | Med |
| 7 | Coverage Matrix And Drift Guard | A4 | The docs stay synchronized as Saga changes | 79 | Med |

## Ranked Survivors

### 1. Saga Atlas Manual

Rebuild the README as the atlas/index into a deeper Saga manual.

The README should open with the operating model: lifecycle position, command ownership, hard gates, off-chain routes, handoff, resume, and destination horizons. It should link to deeper pages for lifecycle, commands, state/readiness, scenarios, boundaries, and visuals rather than trying to carry every detail itself.

The dispatch table already contains the truth; the documentation should make that truth readable. The main tradeoff is sequencing: the README, linked docs, and visuals need to land coherently rather than as disconnected polish.

| field | value |
|---|---|
| basis | direct: `plugins/saga/README.md:3-14`; direct: `plugins/saga/skills/loop/references/dispatch-table.md:1-11` |
| confidence | 92 |
| complexity | Med |
| axis | A1 - Reader orientation and information architecture |
| status | Explored |

### 2. Source-Generated Lifecycle Visual Kit

Create the visual system from Saga source contracts.

Build a source-generated visual set from the dispatch table, command wrappers, saga spec, handoff rules, and boundary docs. Render deck-grade SVG/PNG/HTML assets plus Markdown fallbacks: lifecycle metro map, off-chain orbit, state/readiness ladder, command matrix, destination horizon, and ownership boundary map.

This directly answers the concern that generic Mermaid/PNG output often disappoints. Presentation-worthy graphics need controlled layout and a source model so the diagrams stay faithful as Saga changes.

| field | value |
|---|---|
| basis | direct: `plugins/saga/skills/loop/references/dispatch-table.md:61-130`; direct: no lifecycle-atlas PNG/SVG asset was found in either Saga repo |
| confidence | 88 |
| complexity | High |
| axis | A4 - Presentation-worthy visuals and source-generated assets |
| status | Explored |

### 3. Every-Command Decision Cards

Give each command a comparable selection card.

Each card should cover purpose, use when, do not use when, inputs, outputs, artifact paths, saga read/write behavior, routes in, routes out, gates, owner boundaries, common mistakes, and one example invocation. `/ceo-review` should be presented as an alias card for `/founder-review`, not as a separate lifecycle node.

The cards solve the concrete user question "which command do I run?" without forcing readers into full SKILL files. They also become structured input for the command matrix visual.

| field | value |
|---|---|
| basis | direct: `plugins/saga/commands/*.md`; direct: repo has 18 command files but 17 routable commands |
| confidence | 90 |
| complexity | Med |
| axis | A2 - Command catalog and selection UX |
| status | Explored |

### 4. State And Readiness Passport

Make stored state and handoff readiness impossible to confuse.

Create a visual state/readiness page that separates `lifecycle_phase`, `phase_status`, `status`, and derived-only `maturity`. Show the artifact-path-to-maturity ladder and consumer commands: `idea-ready` / `requirements-ready` feed `/plan`; `plan-ready` / `resume-ready` feed `/work`.

This is the highest-risk conceptual confusion in the system. Maturity is public at handoff time but must not become stored saga state.

| field | value |
|---|---|
| basis | direct: `plugins/saga/references/saga-spec.md:158-189`; direct: `plugins/saga/skills/handoff/SKILL.md:52-68` |
| confidence | 91 |
| complexity | Low-Med |
| axis | A3 - Lifecycle, state, and readiness maturity model |
| status | Explored |

### 5. Scenario Journey Gallery

Teach Saga through real operator situations.

Document common journeys as "user says -> command -> artifact/state -> next route": greenfield idea, vague WHAT, chosen idea, requirements-ready handoff, plan review, PR boundary, post-merge QA, QA failure, root-cause investigation, metric optimization, strategy refresh, cross-team handoff, cold resume, and retro learning.

Users arrive with situations, not command names. Scenarios turn the lifecycle into an operator manual and expose edge cases like `/qa` vs `/investigate` or `/strategy` vs `/founder-review`.

| field | value |
|---|---|
| basis | direct: `plugins/saga/skills/loop/references/dispatch-table.md:42-130` |
| confidence | 86 |
| complexity | Med |
| axis | A5 - Scenarios, examples, and user journeys |
| status | Explored |

### 6. Cross-Host Boundary Map

Document invariant Saga behavior separately from host adapters.

Add a boundary chapter and companion visual comparing Claude Saga and Codex Saga: slash commands vs namespaced skills, `.claude/saga/` vs `.codex/saga/`, backend availability, receiving-plugin re-verification, and Saga / mission-control / deploy / team-execution ownership.

The Codex port is useful as an adapter example, but the docs must keep source truth and host-specific behavior distinct. This prevents false parity and mutation ownership drift.

| field | value |
|---|---|
| basis | direct: `plugins/saga/references/operator-choice.md:23-39`; external: Codex port boundary and state-policy docs |
| confidence | 84 |
| complexity | Med |
| axis | A6 - Cross-host/portability and plugin-family boundaries |
| status | Explored |

### 7. Coverage Matrix And Drift Guard

Keep the documentation synchronized with Saga as it changes.

Add a docs coverage matrix and validation check that accounts for every command, route, maturity value, artifact folder, backend, external owner, and generated visual. A command, dispatch-table, or state-contract change should fail a narrow docs check until the atlas/manual is updated.

Comprehensive docs are an investment only if they stay synchronized with Saga's moving surface. The matrix also acts as an implementation checklist.

| field | value |
|---|---|
| basis | direct: `docs/engineering-journal/DECISIONS.md:51-56`; direct: journal learnings warn that prompt docs and source adaptations drift when not verified |
| confidence | 79 |
| complexity | Med |
| axis | A4 - Presentation-worthy visuals and source-generated assets |
| status | Explored |

## Did Not Survive (Revivable)

Explicit rejection is the quality mechanism. Cut ideas keep stable ids so they can be revived with new evidence.

| id | title | summary | reason | status |
|---|---|---|---|---|
| R1 | Single giant README | Put all atlas, command, state, scenario, boundary, and visual content in one README. | Too bulky for the reader and maintainers; the README should be the atlas/index, not the whole manual. | rejected |
| R2 | Hand-maintained Mermaid/PNG refresh | Draw a few Mermaid diagrams or exported PNGs by hand. | Conflicts with the presentation-quality goal and creates drift risk; useful only as a sketch layer inside survivor #2. | rejected |
| R3 | Copy the Codex port docs directly | Reuse the Codex Saga docs as the Claude Saga documentation shape. | False parity risk; Codex is an adapter example, not the Claude source of truth. | rejected |
| R4 | Static docs microsite first | Build an interactive static site with filters and visual navigation. | Potentially valuable later, but too expensive before the manual/source model exists. | rejected |
| R5 | Separate slide deck as primary artifact | Create a presentation deck apart from the repository docs. | Presentation value should come from reusable docs assets; a detached deck would drift. | rejected |
| R6 | Exhaustive SKILL prose reference | Write long prose summaries for every SKILL file. | Duplicates source docs and is less usable than command cards plus scenarios. | rejected |

## Co-Ideation Log

| source | entered | idea / seed | outcome |
|---|---|---|---|
| user-seed | Phase 0 | Comprehensive documentation for every Saga command | Survived as #1 and #3 |
| user-seed | Phase 0 | Full lifecycle, states, readiness maturity, scenarios, use cases | Survived as #4 and #5 |
| user-seed | Phase 0 | More presentation-worthy diagrams than default Mermaid/PNG | Survived as #2 |
| user-seed | Phase 0 | Consider the Codex port and lifecycle-atlas feel | Survived as #6 and informed #1/#2 |
| frame-agent | Phase 2 | Drift guard and coverage matrix | Survived as #7 |

## Suggested Plan Shape

Build the manual and source model together, then render the first visuals from that model. Sequence the work as: atlas/index, command/source model, state/readiness model, visual kit, scenarios, boundary chapter, then drift guard. The first implementation should prove the system with real rendered assets, not leave visuals as a future promise.
