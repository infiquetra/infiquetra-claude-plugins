---
title: Saga Comprehensive Documentation System
type: docs
status: active
date: 2026-06-09
origin: docs/brainstorms/2026-06-09-saga-comprehensive-documentation-requirements.md
---

# Saga Comprehensive Documentation System

## Summary

Build Saga's v1 documentation system as an atlas-style manual backed by a maintained source model, generated presentation-ready SVG visuals, command-selection cards, scenario journeys, state/readiness explanations, and a narrow drift guard.

This is documentation infrastructure for the `saga` plugin. It should make a new user able to pick the right command and make a maintainer able to update docs safely when the command surface or lifecycle semantics change.

---

## Problem Frame

Saga now behaves like an operating model across ideation, planning, review, work routing, QA, handoff, resume, and retro loops. The current docs name many of the pieces, but the teaching path is distributed across the README, command wrappers, SKILL files, dispatch tables, state specs, scripts, and sibling Codex-port docs.

The documentation needs to explain the lifecycle without forcing users to reverse-engineer the plugin. The visual layer also needs a real maintenance contract: source data first, rendered assets second, and validation that catches drift.

---

## Requirements

Reader path and manual structure:

R1. The README presents Saga as an operating model first: lifecycle phases, command ownership, off-chain routes, gates, handoff, resume, destination horizon, and plugin-family boundaries.

R2. The README acts as an index into deeper manual pages instead of carrying the whole manual inline.

R3. The manual includes dedicated coverage for lifecycle, command selection, state/readiness, scenarios, boundaries, and visuals.

R4. The documentation states that Saga has 18 command files and 17 routable commands because `/ceo-review` aliases `/founder-review`.

Command selection:

R5. Every command has a comparable decision card covering purpose, use when, do not use when, inputs, outputs, durable artifacts, saga read/write behavior, routes in, routes out, gates, ownership boundaries, common mistakes, and one example invocation.

R6. Adjacent command pairs are distinguishable from the docs, including `/office-hours` vs `/ideate`, `/ideate` vs `/brainstorm`, `/brainstorm` vs `/spec`, `/plan` vs `/doc-review`, `/qa` vs `/optimize`, `/strategy` vs `/founder-review`, and `/loop` vs `/resume`.

R7. Command cards avoid duplicating full SKILL prose. They are selection surfaces, not replacement source docs.

Lifecycle, state, and readiness:

R8. The docs explain the three stored saga state axes: `lifecycle_phase`, `phase_status`, and `status`.

R9. The docs explain that `maturity` is derived at handoff time and must not be stored as saga state.

R10. The docs map durable artifact roots to handoff maturity: ideation to `idea-ready`, brainstorm/spec to `requirements-ready`, plans/reviews to `plan-ready`, and work-session/branch evidence to `resume-ready`.

R11. The docs explain which maturity levels are consumed by `/plan` and which are consumed by `/work`.

R12. The docs call out off-chain commands and their state behavior, especially `/spec`, `/investigate`, `/optimize`, `/strategy`, and `/retro`.

Visual system:

R13. V1 defines a structured source model for the visual kit that represents commands, routes, gates, maturity mappings, artifact roots, destinations, execution backends, and plugin-family boundaries.

R14. V1 renders the first source-generated visual assets from that model. The minimum set is a lifecycle atlas, a state/readiness ladder, a command matrix, and an ownership boundary map.

R15. Rendered visuals are readable in the README/manual and usable in a 16:9 presentation context without redrawing.

R16. Every rendered visual has a text fallback or nearby table so the docs remain useful in plain Markdown.

R17. The visual source model, not manually edited image output, is the maintained truth for diagrams.

Scenarios and examples:

R18. The manual includes a scenario journey gallery organized by user situation rather than command name.

R19. Each scenario shows the user's starting statement, selected command, produced artifact or state effect, stop condition, and next route.

R20. The minimum scenario set covers vague idea, chosen idea, vague WHAT, requirements-ready handoff, plan review, PR boundary, post-merge QA, QA failure, root-cause investigation, metric optimization, strategy refresh, cross-team handoff, cold resume, and retro learning.

Boundaries and portability:

R21. The docs show what Saga owns and what it must not own: Saga owns lifecycle choice, local saga state, routing, and handoff envelopes; `mission-control` owns SDLC mutation; `deploy` owns deployment mutation; `team-execution` owns reviewer/validator orchestration.

R22. The docs compare Claude Saga and Codex Saga at the right level: command surface, state root, backend availability, host-specific omissions, and invariant lifecycle semantics.

R23. Cross-host docs treat the Codex port as an adapter example, not as a replacement source of truth for Claude Saga.

Drift prevention:

R24. V1 includes a coverage matrix that accounts for commands, routes, maturity values, artifact roots, execution backends, external owners, scenario coverage, and generated visuals.

R25. V1 includes a narrow validation guard that catches stale command count, alias status, missing command cards, missing visual coverage, or broken source references.

R26. Validation starts narrow enough to avoid noisy false positives; broader style or prose-quality gates are deferred.

---

## Key Technical Decisions

KTD1. README as atlas, docs as manual: `plugins/saga/README.md` becomes the front door and route map, while deeper pages under `plugins/saga/docs/` carry detail. This keeps the README scannable and avoids making the command catalog the first teaching surface.

KTD2. Source model lives under `plugins/saga/docs/model/`: the visual and coverage truth should sit with the plugin manual, not in repo-level lifecycle artifacts. Rejected: deriving every visual only from scattered Markdown at render time, which would make curation and scenario coverage hard to review.

KTD3. Use one curated YAML model with validation, not many ad hoc tables: `plugins/saga/docs/model/saga-docs-model.yaml` should include commands, routes, gates, maturity mappings, artifact roots, destinations, execution backends, external owners, visual inventory, and scenarios. The validator can cross-check this model against command wrappers and canonical references.

KTD4. Render SVG directly with a small Python script: use `plugins/saga/scripts/render_docs_visuals.py` with stdlib SVG generation and existing `PyYAML`, rather than adding Graphviz, D2, Mermaid CLI, or a diagrams dependency. This keeps visuals deterministic, reviewable, and CI-friendly while still allowing presentation-grade layout.

KTD5. Commit generated SVG outputs: rendered assets under `plugins/saga/docs/assets/` are build artifacts, but they are part of the docs product and should be reviewable in PRs. The source model remains authoritative; tests should detect missing or stale generated outputs.

KTD6. Command cards are curated selection cards, not generated SKILL summaries: the model may reference wrappers and SKILL files, but the manual should contain concise decision cards with stable fields. This avoids copying long skill prose while still giving the operator comparable command-selection data.

KTD7. Readiness is documented as derived maturity: the plan must preserve the `saga-spec.md` distinction between stored state axes and handoff maturity. The docs should not imply that `idea-ready`, `requirements-ready`, `plan-ready`, or `resume-ready` are stored saga state values.

KTD8. Codex docs are comparative evidence only: sibling `infiquetra-codex-plugins` docs can inform portability language and visual inspiration, but this repo remains the Claude Saga source surface. Host-specific mechanics should be called out explicitly instead of merged into the core model.

KTD9. Drift guard starts as pytest: add focused tests under `tests/`, not a new top-level validation framework. This matches existing repo patterns and keeps the first guard narrow enough to be useful.

KTD10. Engineering journal entries land with implementation, not the plan: this plan records decisions now, and `/work` should mirror any committed plugin-pattern decision or non-obvious learning into `docs/engineering-journal/` in the same commit that ships the docs system.

---

## High-Level Technical Design

The docs system has four layers: source model, rendered visuals, human manual, and drift validation.

```text
plugins/saga/commands/*.md
plugins/saga/skills/**/SKILL.md
plugins/saga/skills/loop/references/dispatch-table.md
plugins/saga/references/saga-spec.md
plugins/saga/skills/handoff/SKILL.md
        |
        v
plugins/saga/docs/model/saga-docs-model.yaml
        |
        +--> plugins/saga/scripts/render_docs_visuals.py
        |        |
        |        v
        |   plugins/saga/docs/assets/*.svg
        |
        +--> plugins/saga/docs/*.md
        |
        v
tests/test_saga_docs_coverage.py
```

The source model is curated. It should not pretend that every field can be mechanically extracted from Markdown, but it should cite the canonical sources and make all user-facing command cards, scenarios, maturity mappings, and visuals traceable.

The renderer should be intentionally boring: read the model, compute fixed 16:9-friendly SVG canvases, and write deterministic assets. The minimum visual set is:

| asset | purpose | source sections |
|-------|---------|-----------------|
| `lifecycle-atlas.svg` | Shows the spine from frame-finding through handoff/retro, including off-chain routes | commands, routes, gates, destinations |
| `state-readiness-ladder.svg` | Separates stored state axes from derived readiness maturity | state axes, artifact roots, maturity mappings |
| `command-matrix.svg` | Helps compare 17 routable commands and the `/ceo-review` alias | command cards, lifecycle ownership, state behavior |
| `ownership-boundary-map.svg` | Shows Saga vs `mission-control`, `deploy`, and `team-execution` ownership | external owners, destinations, execution backends |

The manual pages should use the SVGs as teaching aids, then provide tables as text fallbacks. A reader using plain Markdown should still get the same operational answer.

---

## Implementation Units

### U1. Establish the Docs Source Model

Create the maintained truth for command cards, routes, readiness, scenarios, and visuals.

**Goal:**

Add `plugins/saga/docs/model/saga-docs-model.yaml` as the curated source model for the documentation system, with enough structure to drive visuals and coverage validation.

**Requirements:**

R4, R5, R8, R9, R10, R11, R12, R13, R17, R21, R22, R24.

**Dependencies:**

None.

**Files:**

`plugins/saga/docs/model/saga-docs-model.yaml`

`plugins/saga/docs/model/README.md`

`tests/test_saga_docs_coverage.py`

**Approach:**

Create a single YAML model with top-level sections for `commands`, `aliases`, `routes`, `state_axes`, `maturity`, `artifact_roots`, `destinations`, `execution_backends`, `external_owners`, `scenarios`, `visuals`, and `sources`.

Each command entry should include stable card fields: purpose, use_when, do_not_use_when, inputs, outputs, durable_artifacts, saga_state_behavior, routes_in, routes_out, gates, owner_boundary, common_mistakes, example_invocation, and source_refs. Model `/ceo-review` as an alias to `/founder-review`, not an eighteenth routable node.

Keep the model curated but checkable. Do not attempt to parse full SKILL prose into cards; instead, cite canonical wrappers and reference files so reviewers can verify intent.

**Patterns to follow:**

Use the route vocabulary from `plugins/saga/skills/loop/references/dispatch-table.md`.

Use state and maturity language from `plugins/saga/references/saga-spec.md` and `plugins/saga/skills/handoff/SKILL.md`.

Use short, table-friendly prose consistent with `plugins/saga/references/formatting-style.md`.

**Test scenarios:**

Happy path: a complete model with 18 command files, 17 routable commands, and one `/ceo-review` alias passes coverage validation.

Edge case: a command wrapper exists without a model card, or a model card names a missing wrapper, and the test fails with the command name.

Edge case: the model stores `maturity` as a saga state axis instead of derived readiness, and the test fails.

Error path: a source reference path in the model does not exist, and the test reports the broken path.

Integration scenario: all required visual IDs and scenario IDs from R14/R20 appear in the model and are available to later units.

**Verification:**

The model is reviewable as the source of truth, and `tests/test_saga_docs_coverage.py` can load it, count the command surface, verify alias handling, verify required source paths, and verify required coverage categories.

### U2. Build the Visual Renderer and First SVG Assets

Turn the source model into deterministic, presentation-ready visuals.

**Goal:**

Add a small renderer that emits the first four SVG assets from the model: lifecycle atlas, state/readiness ladder, command matrix, and ownership boundary map.

**Requirements:**

R13, R14, R15, R16, R17, R24, R25, R26.

**Dependencies:**

U1.

**Files:**

`plugins/saga/scripts/render_docs_visuals.py`

`plugins/saga/docs/assets/lifecycle-atlas.svg`

`plugins/saga/docs/assets/state-readiness-ladder.svg`

`plugins/saga/docs/assets/command-matrix.svg`

`plugins/saga/docs/assets/ownership-boundary-map.svg`

`tests/test_saga_docs_visuals.py` or `tests/test_saga_docs_coverage.py`

**Approach:**

Implement a deterministic SVG renderer that reads `saga-docs-model.yaml` and writes fixed-layout assets. Prefer direct SVG strings or `xml.etree.ElementTree`; avoid introducing rendering dependencies unless local investigation proves the existing environment already supports them cleanly.

Design the visual language for readability: stable 16:9-friendly canvases, strong labels, restrained color, clear grouping, and no tiny text that only works in source view. Include a short file header in generated SVG comments naming the model path and renderer command.

Add a `--check` mode or test helper that rerenders into a temporary directory and compares outputs to committed assets. If exact byte-for-byte comparison is too brittle, compare normalized SVG text plus required IDs/titles.

**Patterns to follow:**

Use existing Python script style under `plugins/saga/scripts/`.

Use existing pytest style in `tests/test_saga_doc_formatting.py` and `tests/test_saga_saga.py`.

Use the "lifecycle atlas" idea from the Codex-port docs as inspiration only; keep this repo's source model authoritative.

**Test scenarios:**

Happy path: renderer reads the complete model and writes all four expected SVG files.

Edge case: a required visual ID is missing from the model, and validation fails before writing partial assets.

Error path: a model entry references a command ID the model does not define, and rendering fails with a useful message.

Integration scenario: committed SVG files include accessible `<title>` or equivalent labels, are non-empty, and match the current model according to the chosen staleness check.

**Verification:**

The four SVGs render legibly in Markdown preview, fit a 16:9 slide without redrawing, and the pytest guard catches missing or stale assets.

### U3. Rework the README as the Atlas and Index

Make the plugin front page teach the operating model before the catalog.

**Goal:**

Update `plugins/saga/README.md` so a first-time reader sees the lifecycle atlas, learns the command-selection frame, and can jump to the right manual page.

**Requirements:**

R1, R2, R3, R4, R15, R16, R21.

**Dependencies:**

U1, U2.

**Files:**

`plugins/saga/README.md`

`plugins/saga/docs/README.md`

**Approach:**

Restructure the README around the reader path: what Saga is, when to start with frame-finding vs ideation vs planning, the lifecycle atlas, the command count/alias note, the state/readiness warning, plugin-family boundaries, and links into the manual.

Keep the README concise. Move command-card detail, scenario detail, and cross-host comparisons into dedicated manual pages. Add a nearby Markdown table fallback for each embedded visual so the page remains useful without image rendering.

**Patterns to follow:**

Preserve existing README tone and plugin metadata where still accurate.

Follow `plugins/saga/references/formatting-style.md` for short paragraphs and comparative tables.

Use relative links within `plugins/saga/`.

**Test scenarios:**

Happy path: README links to all manual pages and embeds or references all four v1 visual assets.

Edge case: README says 18 command files and 17 routable commands, and the coverage test checks that statement against the filesystem/model.

Error path: a README link points to a missing manual page or asset, and validation fails.

**Verification:**

A reader can identify the right next manual page from the README alone, and link/reference validation passes.

### U4. Write the Command Selection Manual

Give every command a comparable decision card without replacing the SKILL files.

**Goal:**

Create a command-selection page that lets operators compare commands, avoid adjacent-command mistakes, and understand the artifact/state effect before invoking a command.

**Requirements:**

R4, R5, R6, R7, R12, R21, R24, R25.

**Dependencies:**

U1.

**Files:**

`plugins/saga/docs/commands.md`

`plugins/saga/docs/assets/command-matrix.svg`

`plugins/saga/docs/model/saga-docs-model.yaml`

`tests/test_saga_docs_coverage.py`

**Approach:**

Author command cards from the model using stable headings and compact tables. Include all 18 command files, with `/ceo-review` clearly marked as an alias of `/founder-review` and excluded from the 17 routable-command count.

Add an adjacent-command comparison section for the pairs named in R6. Keep each distinction operational: "use this when..." and "do not use this when..." beats abstract taxonomy.

Do not paste full SKILL instructions. Link to source files for maintainers who need implementation-level detail.

**Patterns to follow:**

Use the wrappers in `plugins/saga/commands/` for invocation examples.

Use `plugins/saga/skills/loop/references/dispatch-table.md` for routes and shipped/stub status.

Use `plugins/saga/references/operator-choice.md` for backend and destination wording.

**Test scenarios:**

Happy path: every command wrapper has one card or alias entry in `commands.md`.

Edge case: `/ceo-review` appears as an alias and not as a separate lifecycle node.

Edge case: every R6 adjacent pair appears in the comparison section.

Error path: a command card is missing a required field, and the coverage test reports the command and field.

Integration scenario: routes in/out named in command cards correspond to IDs in the model.

**Verification:**

An operator can distinguish adjacent commands from `commands.md`, and the coverage test fails on missing command cards or missing comparison pairs.

### U5. Write Lifecycle, State, and Readiness Pages

Explain the spine, stored state, derived maturity, and handoff consumers.

**Goal:**

Create manual pages that teach Saga's lifecycle and state/readiness model without confusing stored saga state with handoff maturity.

**Requirements:**

R1, R3, R8, R9, R10, R11, R12, R14, R16, R21, R24.

**Dependencies:**

U1, U2.

**Files:**

`plugins/saga/docs/lifecycle.md`

`plugins/saga/docs/state-readiness.md`

`plugins/saga/docs/assets/lifecycle-atlas.svg`

`plugins/saga/docs/assets/state-readiness-ladder.svg`

`plugins/saga/docs/model/saga-docs-model.yaml`

`tests/test_saga_docs_coverage.py`

**Approach:**

In `lifecycle.md`, describe the main chain, off-chain commands, gates, destination horizon, and how `/loop` routes a user back to the right phase. Keep the lifecycle atlas near the top and include a text fallback table for users reading plain Markdown.

In `state-readiness.md`, separate stored axes from derived maturity. Show artifact root to maturity mapping and name which maturities `/plan` and `/work` consume. Call out `/spec` as a requirements artifact path that does not become a stored lifecycle phase.

**Patterns to follow:**

Use `plugins/saga/references/saga-spec.md` as the canonical state source.

Use `plugins/saga/skills/handoff/SKILL.md` for artifact-root maturity mapping.

Use `plugins/saga/skills/loop/references/dispatch-table.md` for lifecycle routing.

**Test scenarios:**

Happy path: state/readiness docs name all three stored state axes and all four derived maturity values.

Edge case: docs mention `/spec` in the requirements-ready artifact path but do not list `spec` as a stored lifecycle phase.

Edge case: lifecycle docs name off-chain commands and identify their state behavior.

Error path: a maturity value appears in docs but not in the model, and validation fails.

Integration scenario: visual fallbacks and model maturity mappings agree.

**Verification:**

A reader can start from an artifact path or saga state and determine whether to route to `/plan`, `/work`, `/handoff`, `/resume`, or an off-chain command without inventing new state.

### U6. Write Scenario and Boundary Manuals

Teach Saga through user situations and clarify where Saga stops.

**Goal:**

Create scenario journeys and plugin-family boundary docs that help users route real situations and avoid assigning Saga responsibilities to adjacent plugins.

**Requirements:**

R18, R19, R20, R21, R22, R23, R24.

**Dependencies:**

U1, U2, U4, U5.

**Files:**

`plugins/saga/docs/scenarios.md`

`plugins/saga/docs/boundaries.md`

`plugins/saga/docs/assets/ownership-boundary-map.svg`

`plugins/saga/docs/model/saga-docs-model.yaml`

`tests/test_saga_docs_coverage.py`

**Approach:**

Organize `scenarios.md` by user situation rather than command name. Each scenario should show starting statement, selected command, produced artifact or state effect, stop condition, and next route. Cover the full minimum scenario set from R20.

In `boundaries.md`, document Saga's ownership against `mission-control`, `deploy`, and `team-execution`. Add a Claude vs Codex comparison at the invariant/adapter level: command surface, state root, backend availability, host-specific omissions, and unchanged lifecycle semantics.

**Patterns to follow:**

Use `plugins/saga/references/operator-choice.md` for backend and destination concepts.

Use sibling Codex docs only as comparative context: `../infiquetra-codex-plugins/plugins/saga/PORTABILITY.md`, `../infiquetra-codex-plugins/docs/portability/saga-family-state-policy.md`, and `../infiquetra-codex-plugins/docs/portability/saga-family-capability-map.md`.

Use `plugins/saga/references/formatting-style.md` for scenario tables and short explanatory prose.

**Test scenarios:**

Happy path: every R20 scenario appears with starting statement, selected command, artifact/state effect, stop condition, and next route.

Edge case: boundary docs name Saga-owned and non-Saga-owned responsibilities for each external owner.

Edge case: Codex comparison explicitly labels Codex as an adapter example rather than source of truth.

Error path: a scenario references a command or owner not present in the model, and validation fails.

Integration scenario: ownership boundary map, boundary table, and model owner entries agree.

**Verification:**

A reader can route the common scenarios without command-name-first guessing, and can explain when to use `mission-control`, `deploy`, or `team-execution` instead of Saga.

### U7. Add Drift Guard, Docs Index Validation, and Release Records

Make the docs system maintainable after v1 ships.

**Goal:**

Complete focused validation for model coverage, docs links, generated visuals, and release/journal records.

**Requirements:**

R15, R16, R17, R24, R25, R26.

**Dependencies:**

U1, U2, U3, U4, U5, U6.

**Files:**

`tests/test_saga_docs_coverage.py`

`tests/test_saga_docs_visuals.py` or folded coverage in `tests/test_saga_docs_coverage.py`

`plugins/saga/CHANGELOG.md`

`docs/engineering-journal/DECISIONS.md`

`docs/engineering-journal/LEARNINGS.md`

`plugins/saga/.claude-plugin/plugin.json`

**Approach:**

Extend the focused pytest guard to validate command counts, alias handling, required card fields, required adjacent-pair comparisons, required maturity values, required scenario coverage, required visual files, model source references, README/manual links, and generated asset freshness.

Keep the guard narrow. Avoid prose-quality assertions that will be brittle. Prefer exact structural checks that correspond to R24/R25.

Record any committed plugin-pattern decisions in `DECISIONS.md` and any non-obvious implementation learnings in `LEARNINGS.md` when the work ships. Add a `CHANGELOG.md` entry and bump `plugin.json` only if repo release conventions or reviewer expectation require it for documentation-system changes.

**Patterns to follow:**

Use existing pytest structure from `tests/test_saga_doc_formatting.py`.

Use existing engineering-journal entry format in `docs/engineering-journal/`.

Use existing Saga changelog/version style in `plugins/saga/CHANGELOG.md` and `plugins/saga/.claude-plugin/plugin.json`.

**Test scenarios:**

Happy path: all docs, model, links, and SVG outputs are present and synchronized.

Edge case: a docs page has a relative link to a missing file, and validation fails with the source page and target.

Edge case: the model omits one required scenario from R20, and validation fails with that scenario ID.

Error path: generated SVG output is stale relative to the model, and the test instructs the maintainer to rerun the renderer.

Integration scenario: `uv run pytest tests/test_saga_doc_formatting.py tests/test_saga_docs_coverage.py` passes after the implementation.

**Verification:**

The docs system fails loudly on the drift cases that matter and stays quiet on editorial prose changes.

---

## Scope Boundaries

In scope for v1:

- `plugins/saga/README.md` as the atlas and index.
- Manual pages under `plugins/saga/docs/` for lifecycle, command selection, state/readiness, scenarios, boundaries, and visual maintenance.
- `plugins/saga/docs/model/saga-docs-model.yaml` as the maintained source model.
- Four generated SVG assets under `plugins/saga/docs/assets/`.
- Focused pytest validation for command/model/docs/visual coverage.
- Release, changelog, and engineering-journal updates if implementation creates plugin-pattern decisions or non-obvious learnings.

Deferred to follow-up work:

- A full interactive static docs site.
- A separate slide deck or PowerPoint export.
- PNG export unless there is a concrete consumer that cannot use SVG.
- Broad prose-style linting beyond the existing formatting contract and the focused drift guard.
- Automated generation of all manual prose from the model.

Outside this work:

- Changing Saga command behavior, routing behavior, or saga state persistence.
- Replacing SKILL files with manual prose.
- Copying Codex-port docs into Claude Saga docs.
- Making Mermaid or manually edited PNGs the primary visual source.
- Mutating `mission-control`, `deploy`, or `team-execution` plugin behavior.

---

## Risks & Dependencies

| risk/dependency | impact | mitigation |
|-----------------|--------|------------|
| Visual quality is too low for the user's presentation-worthy bar | The docs technically work but fail the main communication goal | Use fixed SVG layout, review rendered assets visually, and keep visuals simple enough to polish without new dependencies |
| Source model becomes duplicated truth | Maintainers may update docs prose but forget model fields | Add pytest coverage for model-to-docs references and make model update part of the manual maintenance instructions |
| Renderer grows into a diagram framework | More code than the docs system needs | Limit v1 renderer to four named assets and deterministic SVG primitives |
| PyYAML availability differs between local and CI | Validation or renderer may fail outside the current environment | Confirm dependency availability during `/work`; if needed, use JSON instead of YAML rather than adding a dependency |
| Cross-host comparison overstates Codex parity | Readers may treat adapter behavior as core Saga behavior | Keep Codex material in `boundaries.md`, label it as an adapter example, and cite Claude Saga as source of truth |
| Drift guard becomes noisy | Maintainers ignore failing docs checks | Start with structural checks tied to R24/R25, not prose assertions |

---

## Alternatives Considered

Manual Markdown diagrams only: rejected because the user explicitly wants graphics beyond weak Mermaid/PNG output, and manual diagrams drift quickly.

Mermaid as primary visual source: rejected for v1 primary assets because Mermaid is readable as source but often weak for polished presentation graphics. It can remain a sketch or fallback pattern later.

Graphviz, D2, or Python Diagrams dependency: rejected for v1 because the repo does not already carry the dependency for Saga docs, and the first four visuals are simple enough for deterministic SVG.

Generated docs site first: rejected because a static site is a larger product surface than the immediate need. The first screen should be the plugin README plus manual pages.

Fully generated command manual: rejected because command-selection cards need curated operational judgment. The model can validate coverage, but generated prose would flatten important distinctions.

---

## Success Metrics

- A first-time reader can choose a Saga command for common situations without opening individual SKILL files.
- The README names 18 command files, 17 routable commands, and the `/ceo-review` alias without ambiguity.
- The manual clearly separates stored saga state from derived handoff maturity.
- The four SVG visuals are readable in Markdown preview and suitable for a 16:9 presentation without redrawing.
- The scenario gallery covers all R20 situations with starting statement, selected command, artifact/state effect, stop condition, and next route.
- The boundary docs prevent Saga from absorbing `mission-control`, `deploy`, or `team-execution` responsibilities.
- Focused tests fail on missing command cards, broken source refs, missing required visuals, missing required scenarios, or stale generated assets.

---

## Sources / Research

- `docs/brainstorms/2026-06-09-saga-comprehensive-documentation-requirements.md`
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
