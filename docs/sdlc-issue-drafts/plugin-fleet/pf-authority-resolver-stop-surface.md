---
title: "capability: executable authority-order resolver + stop-and-surface conflict primitive for context-library standards"
repo: infiquetra-claude-plugins
type: capability
team: campps
project: operations
status: Idea
labels: capability, hermes-task, needs-plan
risk: medium
handoff_maturity: requirements-ready
tier: structural
objective: Enforce context-library standards at authoring time
wave: wave-2
---

# capability: executable authority-order resolver + stop-and-surface conflict primitive for context-library standards

### Objective

Enforce context-library standards at authoring time

### Problem / Motivation

`infiquetra-context-library`'s authority model is prose, not machinery. The priority order agents are
supposed to follow when sources conflict lives entirely as a numbered list in
`infiquetra-context-library/docs/governance/authority-model.md:32-38` — direct user instruction, then
nearest local repo instruction file, then project blueprint/ADR, then the context library, then
general tool knowledge — with a closing instruction (`authority-model.md:40`) to "stop and surface the
conflict if the choice affects correctness, security, deployment, or data handling." Nothing in this
repository (or any fleet plugin) reads that order, executes it, or enforces the stop instruction. An
agent authoring a plan or issue today either never notices a conflict, or notices it and picks a side
silently — the fleet has no code path that forces the halt the document already prescribes.

This repository's own grounding pass for the 2026-07-03 plugin-fleet ideation confirms the gap
directly: standards/ADR enforcement "already exists *inside* [the context] library" via CI
(`validate.yml` running `check_docs.py` and `context_census.py --check`,
`docs/plans/2026-07-03-plugin-fleet-grounding-brief.md:77-80`), but the brief lists as **absent**:
"pull[ing] the library into `mission-control:issue` / `saga:plan` creation" and "any ADR↔code-pattern
lint" (`docs/plans/2026-07-03-plugin-fleet-grounding-brief.md:82-83`). The same brief cites
`authority-model.md` by name as defining the order including "stop and surface conflict"
(`docs/plans/2026-07-03-plugin-fleet-grounding-brief.md:81`) — the document is known and referenced,
but never executed. Today, `saga:plan` (`plugins/saga/skills/plan/SKILL.md`) and
`mission-control:issue` (`plugins/mission-control/skills/issues/SKILL.md`) both author artifacts that
can collide with a `required` context-library standard or a repo's own `CLAUDE.md`, and neither has a
machine check that trips on that collision — the only thing standing between a silent wrong choice and
a surfaced conflict is an agent remembering to re-read prose on every invocation.

This consolidates two ideas that only make sense shipped together: an executable resolver with no
consumer is dead code, and a stop-and-surface primitive with no resolver behind it is unenforceable
prose repeated in a different file. `T9-F3-4` (the resolver) and `T9-F3-8` (the stop-and-surface
primitive, which explicitly depends on being "fed by [the] authority resolver") were absorbed together
for exactly this reason (see Grounding references below).

## Definition of Done

- A generated `authority_resolve.py` module whose priority order is derived from
  `infiquetra-context-library/docs/governance/authority-model.md`'s numbered "Agent Interpretation"
  list (`authority-model.md:32-38`) — not hand-copied prose — so the resolver and the document cannot
  silently drift apart. The generation/parity mechanism is `/plan`'s to design, but it must fail loud
  (not silently pass) if the source document's order changes without a matching resolver regeneration.
- A `standards_conflict_check.py` module, fed by the resolver's output, that classifies a candidate
  decision (e.g. a plan choice or issue draft field) against the resolved authority order and returns a
  typed verdict: clean, or `material-conflict` naming the two conflicting sources and which one the
  order says wins.
- `saga:plan` and `mission-control:issue` both call `standards_conflict_check.py` at a determinate point
  in their authoring flow (`/plan`'s Phase 0 warranted-gate or an equivalent authoring checkpoint;
  `mission-control:issue`'s issue-creation workflow, `plugins/mission-control/skills/issues/SKILL.md:239`)
  and HALT for operator adjudication when the check returns `material-conflict` — the check never
  silently downgrades to a warning and never auto-resolves the conflict itself. Per
  `{#external-engines-never-gatekeepers}`, Claude/the CLI is the arbiter of the halt, not an external
  engine — this primitive HALTs a Claude-orchestrated flow; it does not delegate the adjudication call.
- A golden-case fixture table covering the documented authority order (repo-instruction-overrides
  library, project-ADR-overrides-general-library-guidance, direct-user-instruction-overrides-everything,
  etc., per `authority-model.md:32-38`) passes against the resolver.
- A seeded conflict (a fabricated plan choice that contradicts this repository's own `CLAUDE.md`) halts
  `saga:plan` for adjudication instead of the agent silently picking a side.

### Acceptance criteria
- [ ] **Resolver order matches the source document (parity check).** `authority_resolve.py`'s emitted
  priority order is asserted equal to the five-level order in
  `infiquetra-context-library/docs/governance/authority-model.md:32-38`, and the parity check fails
  (not warns) when the source document's order is edited without a matching resolver regeneration.
  Check: `uv run pytest tests/test_authority_resolve.py -k order_parity` → passes; a mutated fixture copy
  of `authority-model.md` with a reordered list makes the same test fail.
- [ ] **Golden-case table passes.** A fixture table of authority-conflict cases (repo-override-wins,
  project-ADR-overrides-library, direct-user-instruction-wins, library-vs-general-tool-knowledge) each
  resolve to the documented winner. Check: `uv run pytest tests/test_authority_resolve.py -k golden_case`
  → all rows pass.
- [ ] **`standards_conflict_check.py` classifies clean vs. material conflict.** Given two non-conflicting
  sources, it returns clean; given two sources whose guidance materially diverges, it returns
  `material-conflict` naming both sources and the resolved winner. Check:
  `uv run pytest tests/test_standards_conflict_check.py -v` → passes.
- [ ] **`saga:plan` halts on a seeded conflict.** A seeded fixture plan choice that contradicts this
  repository's `CLAUDE.md` trips `standards_conflict_check.py` and the plan flow halts for operator
  adjudication rather than silently proceeding. Check:
  `uv run pytest tests/test_saga_plan_authority_gate.py -k seeded_conflict_halts` → passes.
- [ ] **`mission-control:issue` halts on the same class of seeded conflict.** Check:
  `uv run pytest plugins/mission-control/tests/test_issue_prepare.py -k authority_conflict_halts` →
  passes.
- [ ] **No silent degrade.** A test asserts that a `material-conflict` verdict cannot be swallowed into
  a warning-only path in either caller — the halt is the only exit for that verdict. Check:
  `uv run pytest tests/test_standards_conflict_check.py -k no_silent_degrade` → passes.
- [ ] **Full suite, format, lint, types, and security stay green.** Check:
  `uv run pytest && uv run ruff format --check . && uv run ruff check . && uv run mypy plugins/ scripts/ tests/ --ignore-missing-imports && uv run bandit -r plugins/`
  → all pass.

### Out-of-scope / non-goals
In scope: one executable authority-order resolver derived from
`infiquetra-context-library/docs/governance/authority-model.md`; one stop-and-surface conflict-check
primitive consuming the resolver's output; wiring both into `saga:plan` and `mission-control:issue` as
authoring-time HALT gates.

Out of scope / non-goals:

- **Any ADR↔code-pattern lint** beyond the authority-order resolver itself. The grounding brief lists
  this as a separate absent capability (`docs/plans/2026-07-03-plugin-fleet-grounding-brief.md:83`); it
  is not bundled here to keep blast radius to the resolver/stop-surface pair.
- **Whole-library injection or runtime-fetching of `infiquetra-context-library` content.** The org
  convention is schema-validate-in-CI plus self-describing index
  (`docs/plans/2026-07-03-plugin-fleet-grounding-brief.md:79-80`); this issue does not change that
  consumption shape — it reads the one governance document needed for the authority order, not the
  library at large.
- **Auto-resolving conflicts.** The primitive only classifies and halts; it never picks a winner on the
  operator's behalf beyond reporting what the documented order says — the operator still adjudicates.
  Per `{#external-engines-never-gatekeepers}`, Claude/the CLI stays the gate; no external engine is
  introduced to arbitrate.
- **Wiring into any authoring surface beyond `saga:plan` and `mission-control:issue`** (e.g.
  `saga:brainstorm`, `saga:work`) — those are `/plan`'s to consider as a fast-follow if the pattern
  proves out, not this issue's scope.
- **Changing `infiquetra-context-library`'s own CI** (`validate.yml`, `check_docs.py`,
  `context_census.py`) — that enforcement already exists inside the library repo and is untouched here;
  this issue only builds the consumer-side resolver in `infiquetra-claude-plugins`.

## Grounding References

- `T9-F3-4` (primary) — "Authority-order executable resolver, not trusted prose." Basis: thin seed
  (frame-scan facet, no expanded body) reconstructed from its `dod_sketch` — "Merged
  `authority_resolve.py` generated [from] `authority-model.md`'s order + golden-case table
  (repo-override-wins, library-standard-wins, plan-wins) + parity check resolver order == doc order" —
  and grounding brief section 4, which names `authority-model.md` as defining "agent priority order
  incl. 'stop and surface conflict'" (`docs/plans/2026-07-03-plugin-fleet-grounding-brief.md:81`) and
  lists pulling the library into authoring flows as absent (`:82-83`).
- `T9-F3-8` (facet) — "Stop-and-surface invokable primitive inside plugin flows." Basis: thin seed
  reconstructed from its `dod_sketch` — "Merged `standards_conflict_check.py` (fed by [the] authority
  resolver) + wire-ins `saga:plan` [and] `mission-control:issue` HALT for operator adjudication on
  material conflict; verified by [a] seeded plan-vs-CLAUDE.md conflict halting instead [of the] agent
  silently picking a side. Correctly keeps Claude/CI as arbiter per
  `{#external-engines-never-gatekeepers}`." This facet is the direct consumer of `T9-F3-4`'s resolver —
  consolidation rationale: shipping them apart "leaves either dead wiring or trusted prose."
- Binding decision `{#external-engines-never-gatekeepers}` (#283, cited in
  `docs/plans/2026-07-03-plugin-fleet-grounding-brief.md:45` and `plugins/saga/scripts/... DECISIONS.md
  {#external-engines-never-gatekeepers}`): Claude/CI is the verifier-of-record for every gated decision;
  this issue's HALT is adjudicated by the operator through the Claude-orchestrated flow, never handed to
  an external engine to resolve.
- Source document for the resolver: `infiquetra-context-library/docs/governance/authority-model.md`
  (priority order at lines 32-38; stop-and-surface instruction at line 40).

### Recommended executor profile

- **Model:** Sonnet
- **Effort:** Medium
- **Backend:** Inline
- **External-LLM posture:** None

Justification: this is a well-bounded extraction-and-wiring task — parse one governance document's
existing numbered list into a resolver, build one classifier consuming it, and wire two known call
sites to HALT on its verdict. No architectural ambiguity, no cross-repo novel design, and no case for
escalating above Sonnet/medium; matches the CLAUDE.md tiering guidance (mechanical/deterministic work →
Sonnet or Haiku) rather than judgment/design work that would justify Opus.

### Release-surface checklist

This issue changes runtime behavior in the `saga` plugin (`/plan`'s authoring flow gains a HALT gate)
and the `mission-control` plugin (`issues` skill's creation workflow gains the same gate). Update in the
same PR:

- [ ] `plugins/saga/.claude-plugin/plugin.json` — version bump (new authoring-time HALT gate in
      `/plan`).
- [ ] `plugins/mission-control/.claude-plugin/plugin.json` — version bump (new authoring-time HALT gate
      in `mission-control:issue`).
- [ ] `.claude-plugin/marketplace.json` — reflect both version bumps.
- [ ] `plugins/saga/CHANGELOG.md` — entry describing the authority resolver + stop-and-surface gate
      added to `/plan`.
- [ ] `plugins/mission-control/CHANGELOG.md` — entry describing the same gate added to
      `mission-control:issue`.
- [ ] Any existing plugin-metadata/version drift-guard tests re-run green after both bumps.
- [ ] `docs/engineering-journal/DECISIONS.md` — new entry recording that context-library standards are
      now enforced at authoring time via an executable resolver + HALT primitive (rather than remaining
      trusted prose), with a revisit-when condition (e.g., a third authoring surface needs the same
      gate, or the authority-model document's shape changes beyond a simple ordered list).

### Files expected to change

Indicative only — the exact set is `/plan`'s to determine.

- `plugins/saga/scripts/authority_resolve.py` — new resolver module (proposed path; generated from /
  parsing `infiquetra-context-library/docs/governance/authority-model.md`).
- `plugins/saga/scripts/standards_conflict_check.py` — new stop-and-surface classifier module (proposed
  path), consumes `authority_resolve.py`'s output.
- `plugins/saga/skills/plan/SKILL.md` — wire the HALT gate into Phase 0 or an equivalent authoring
  checkpoint.
- `plugins/mission-control/skills/issues/SKILL.md` — wire the same HALT gate into the issue-creation
  workflow (`:239`).
- `tests/test_authority_resolve.py` — new resolver/parity/golden-case tests.
- `tests/test_standards_conflict_check.py` — new classifier tests (clean / material-conflict / no
  silent degrade).
- `tests/test_saga_plan_authority_gate.py` — new seeded-conflict HALT test for `saga:plan`.
- `plugins/mission-control/tests/test_issue_prepare.py` — extended with an authority-conflict HALT case.
- `docs/engineering-journal/DECISIONS.md` — new entry (see release-surface checklist).

### Tests to add or update

- Resolver: emits the same five-level order as `authority-model.md:32-38`; fails loud on a mutated
  source-document fixture with a reordered list.
- Golden-case table: repo-override-wins, project-ADR-overrides-library, direct-user-instruction-wins,
  library-vs-general-tool-knowledge — each resolves to the documented winner.
- Classifier: clean verdict on non-conflicting sources; `material-conflict` verdict naming both sources
  and the winner on divergent sources; no code path can downgrade `material-conflict` to a warning.
- `saga:plan` seeded-conflict test: a fabricated plan choice contradicting this repo's `CLAUDE.md` halts
  the flow for operator adjudication.
- `mission-control:issue` seeded-conflict test: same halt behavior in the issue-creation workflow.

### Verification

```bash
uv run pytest tests/test_authority_resolve.py tests/test_standards_conflict_check.py \
  tests/test_saga_plan_authority_gate.py -v
uv run pytest plugins/mission-control/tests/test_issue_prepare.py -k authority_conflict_halts -v
uv run pytest && uv run ruff format --check . && uv run ruff check . \
  && uv run mypy plugins/ scripts/ tests/ --ignore-missing-imports && uv run bandit -r plugins/
```

Expected: all green; the seeded-conflict tests demonstrate a HALT for operator adjudication rather than
a silently-picked side.

### Handoff maturity

requirements-ready

### Suggested next action

Use `/plan <issue>` to create an implementation plan.

### Source context

- Source: docs/plans/plugin-fleet-ideation-2026-07-03/issue-map/issue-map-final.json
- Source type: issue-map
- Source title: Executable authority-order resolver + stop-and-surface conflict primitive

### Context library links

_none_

### Intent

`infiquetra-context-library`'s authority model is prose, not machinery. The priority order agents are supposed to follow when sources conflict lives entirely as a numbered list in `infiquetra-context-library/docs/governance/authority-model.md:32-38` — direct user instruction, then nearest local repo instruction file, then project blueprint/ADR, then the context library, then general tool knowledge — with a closing instruction (`authority-model.md:40`) to "stop and surface the conflict if the choice affects correctness, security, deployment, or data handling." Nothing in this repository (or any fleet plugin) reads that order, executes it, or enforces the stop instruction. An agent authoring a plan or issue today either never notices a conflict, or notices it and picks a side silently — the fleet has no code path that forces the halt the document already prescribes.

## Created Issue

- URL: https://github.com/infiquetra/infiquetra-claude-plugins/issues/404
- Number: 404
- Created at: 2026-07-04T08:02:50.698075+00:00

