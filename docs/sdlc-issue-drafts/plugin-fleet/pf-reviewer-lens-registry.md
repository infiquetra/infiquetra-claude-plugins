---
title: "enhancement: one shared lens/reviewer registry feeding both consensus loci, with judgment-selected diversity-aware panel composition"
repo: infiquetra-claude-plugins
type: enhancement
tier: structural
objective: "Establish single-source-of-truth for shared primitives"
wave: wave-2
team: campps
project: operations
status: Idea
labels: enhancement, hermes-task, needs-plan
risk: medium
handoff_maturity: requirements-ready
executor_profile: {model: sonnet, effort: high, backend: inline, external_llm: none}
---

# enhancement: one shared lens/reviewer registry feeding both consensus loci, with judgment-selected diversity-aware panel composition

### Intent
Merge the fleet's two independently maintained review-membership definitions —
team-execution's `reviewer-registry.md` (keyword-triggered optional reviewers atop a fixed base 3)
and saga `/code-review`'s judgment-selected `lens-catalog.md` (4 always-on + conditional lenses) —
into one shared registry keyed by domain-trigger, with a thin per-locus selection adapter
(keyword-match for team-execution, judgment for code-review) reading the same catalog. Port
saga's judgment-selection philosophy into team-execution's panel composition and add an explicit
diversity-coverage check, so team-execution's always-spawned base 3 stops both overpaying (a
security reviewer on a docs-only diff) and under-diversifying (3 correlated reviewers jointly
missing a domain the diff actually needs).

## Problem / Motivation

- **Reviewer/lens membership is defined twice with divergent selection models, and neither file
  references the other.** `plugins/team-execution/skills/team-execution/references/reviewer-registry.md:9-42`
  defines 3 always-spawned base reviewers (`devils-advocate-reviewer`, `security-reviewer`,
  `architecture-reviewer`) plus 7 keyword-triggered optional reviewers, selected by literal
  keyword match against plan content. `plugins/saga/skills/code-review/SKILL.md:147-149` defines a
  structurally different mechanism: "4 always-on lenses ... plus conditional lenses ... Load
  `references/lens-catalog.md`," selected by an agent reading the full diff and using judgment,
  not keyword match. A domain added to one (e.g. a new `concurrency` or `privacy` perspective) has
  no mechanism to propagate to the other locus — it is a two-place authoring job today, and the
  two files can silently drift apart on what domains either locus actually covers.
- **The two loci hold contradictory panel-composition philosophies, and one of them names the
  failure mode explicitly.** `plugins/saga/skills/code-review/SKILL.md:48-50` states the rule by
  name: "Judgment-based lenses. Read the full diff and spawn only the lenses with real work to
  do — not a fixed specialist roster that re-opens 'reviewers that find nothing on this diff'."
  `plugins/team-execution/skills/team-execution/references/reviewer-registry.md:9-11` defines the
  exact pattern that rule rejects: "these three reviewers [are] spawned [on every] plan execution
  regardless of plan type [or] content." The fixed roster both overpays (a
  `security-reviewer` scoring a docs-only diff it has nothing to say about) and under-diversifies
  (3 correlated base reviewers can jointly miss a domain — e.g. concurrency, privacy — that the
  diff actually touches but that none of the fixed 3's rubrics name).
- **Duplicated-definition drift is this repo's most independently recurring consumer-side
  failure class, and this is the same shape applied to review membership.** The grounding brief's
  cross-repo consumer-side signal
  (`docs/plans/2026-07-03-plugin-fleet-grounding-brief.md` §3) names hand-copied contracts
  drifting from their source of truth as the top-ranked recurring finding across independently
  scanned repos (the concrete example: `validate_card_body`'s stale hand-copy of
  `card_validator.py`, 343 "clean" cards failing the live contract). A lens authored once with no
  shared source of truth for a second consumer locus is the identical failure shape, applied to
  review lenses/reviewers instead of validator contracts.
- **No consequence today when a reviewer's rubric goes stale relative to the panel it sits on.**
  `plugins/team-execution/skills/team-execution/references/consensus-protocol.md:17` caps
  iteration at 3 cycles regardless of whether the fixed base-3 panel was ever the right panel for
  the diff under review; nothing in the cycle re-examines panel composition, because
  `reviewer-registry.md` gives the Team Lead no "when NOT to spawn" signal to act on.

## Definition of Done

Merged PR(s) delivering:

1. A single shared lens/reviewer registry (e.g.
   `plugins/saga/skills/code-review/references/lens-catalog.md` promoted to the shared location,
   or a new file both loci' skills load — exact placement is `/plan`'s to determine) that is the
   only membership source for both consensus loci; `reviewer-registry.md` becomes either a thin
   view generated from the shared registry or is deleted in favor of a direct reference from
   `consensus-protocol.md`.
2. Two thin selection adapters reading the same shared registry: a keyword-match adapter for
   team-execution's Phase A reviewer suggestion, and a judgment-selection adapter for saga
   `/code-review`'s Phase 2 lens selection — neither adapter re-derives membership independently.
3. A "Panel composition" step added to `consensus-protocol.md` adopting judgment-selection (treat
   the base 3 as candidates, spawn those with real work on *this* diff) plus an explicit
   domain-coverage check so the selected panel spans the domains the diff touches rather than
   re-running the same three reviewers regardless of fit.
4. A "when NOT to spawn" column on the shared registry's reviewer entries (or equivalent explicit
   skip-condition field) so the selection rule is legible rather than implicit, cross-referenced
   from both `consensus-protocol.md` and `code-review/SKILL.md`.
5. A drift-guard test asserting a probe lens/reviewer added once to the shared registry is
   selectable by both adapters, and a composition test asserting a docs-only diff skips
   `security-reviewer` under the new team-execution panel-composition step.
6. Release-surface updates (see checklist below) reflecting the shared-registry consolidation and
   the panel-composition behavior change to `saga` and `team-execution`.

Verify: the drift-guard test is red before the shared registry exists (a lens added only to one of
today's two files is not selectable by the other adapter), green after; the docs-only-diff
composition test is red against today's `consensus-protocol.md` (base 3 always spawn) and green
after the panel-composition step lands; no existing panel becomes unconstructible — every
reviewer/lens selectable today under either locus remains selectable after migration.

### Acceptance criteria
- [ ] **AC1 (T5-F4-5, primary).** The shared registry is the only membership source consumed by both
  loci — `reviewer-registry.md` and `lens-catalog.md` (or their successors) either read from the
  shared registry or are deleted, with no independent hand-authored membership list surviving in
  either file. Check: `uv run pytest tests/test_lens_reviewer_registry.py -k single_source` →
  passes; a `grep` for a reviewer/lens name hand-listed outside the shared registry in either
  consuming file returns no match.
- [ ] **AC2 (T5-F4-5, primary).** A probe lens/reviewer added once to the shared registry is
  selectable by both the keyword-match adapter (team-execution) and the judgment-selection adapter
  (code-review) — no reauthoring required in either consumer. Check:
  `uv run pytest tests/test_lens_reviewer_registry.py -k drift_guard` → passes on the merged tree;
  adding a probe entry only to one adapter's legacy list (simulating pre-migration drift) fails
  the same check.
- [ ] **AC3 (T5-F4-5, primary).** No lens or reviewer selectable today under either locus is silently
  lost in migration — every entry present in current `reviewer-registry.md` (10 reviewers,
  `reviewer-registry.md:9-42`) and current `lens-catalog.md` (4 always-on + conditional lenses)
  resolves to an entry in the shared registry post-migration. Check:
  `uv run pytest tests/test_lens_reviewer_registry.py -k no_lost_entries` → passes, comparing the
  pre-migration entry set (fixture snapshot) against the shared registry's post-migration entry
  set.
- [ ] **AC4 (T5-F1-7, facet).** `consensus-protocol.md` gains a "Panel composition" step that treats
  the base 3 as candidates and spawns only reviewers with real work to do on the diff under
  review, plus an explicit domain-coverage check. Check: a docs-only scratch diff (no code,
  security surface, or architecture-relevant change) run through the new panel-composition step
  skips `security-reviewer`; `uv run pytest tests/test_panel_composition.py -k
  docs_only_skips_security` → passes.
- [ ] **AC5 (T5-F1-7, facet).** The shared registry (or its reviewer-facing view) carries a
  "when NOT to spawn" column/field for each reviewer, and `code-review/SKILL.md` and
  `consensus-protocol.md` both cite the same selection principle (judgment-based, not fixed
  roster). Check: `uv run pytest tests/test_panel_composition.py -k
  consistent_selection_principle` → passes, asserting both files' selection-principle text
  resolves to the same source string rather than two independently worded statements.

### Out-of-scope / non-goals
**In scope:** consolidating `reviewer-registry.md` and `lens-catalog.md` (or their functional
successors) into one shared registry; the two thin selection adapters (keyword-match,
judgment-selection); the `consensus-protocol.md` panel-composition step and domain-coverage check;
the "when NOT to spawn" field; drift-guard and no-lost-entry tests; release-surface updates on
`saga` and `team-execution`.

**Non-goals (deferred, explicitly out of scope for this issue):**
- Generating lens entries from `DECISIONS.md`'s binding-decision register, or an ADR-derived
  advisory code-pattern lens — that is the separate `pf-adr-derived-review-lenses` issue's scope
  (`docs/sdlc-issue-drafts/plugin-fleet/pf-adr-derived-review-lenses.md`); this issue only
  consolidates the *existing* two membership definitions and ports panel-composition philosophy,
  it does not add a new lens-generation mechanism. If both issues land, the shared registry this
  issue produces is the file the ADR-lens generator writes into — sequencing is `/plan`'s call.
- Changing team-execution's unanimous-ACCEPT consensus gate or its 3-cycle iteration cap
  (`consensus-protocol.md:17`) — this issue changes *who* sits on the panel, not the scoring
  rubric or the escalation/iteration mechanics around it.
- Changing saga `/code-review`'s P0/P1 findings-gate semantics — this issue changes *how lens
  membership is sourced*, not the confidence-gating or dedup rules in `code-review/SKILL.md`.
- A new plugin — both consuming loci already exist inside `saga` and `team-execution`; the shared
  registry lives inside one of those two plugin trees (exact placement is `/plan`'s call), per the
  fleet's active plugin-sprawl concern (`{#plugin-portfolio-groom-17-to-7}`).
- Reworking the keyword list itself (which strings trigger which optional reviewer) beyond what is
  needed to point the existing keyword table at the shared registry — the keyword vocabulary is
  unchanged.

## Grounding References

| Absorbed idea | Basis | Role |
|---|---|---|
| `T5-F4-5` | `docs/plans/plugin-fleet-ideation-2026-07-03/survivors/T5.json` (`dod_sketch`: "Merged: one shared lens/reviewer registry with two selection adapters (keyword for team-execution, judgment for code-review); drift-guard test asserts a probe lens added once is selectable by both adapters"); basis verified live at `plugins/team-execution/skills/team-execution/references/reviewer-registry.md:9-42` (base 3 + keyword-optional table) and `plugins/saga/skills/code-review/SKILL.md:147-149` ("4 always-on lenses ... Load references/lens-catalog.md"); grounding brief §3 (duplicated-definition drift named as an active repo disease) | primary |
| `T5-F1-7` | `docs/plans/plugin-fleet-ideation-2026-07-03/survivors/T5.json` (`dod_sketch`: "Merged: a 'Panel composition' judgment-selection + domain-coverage step in consensus-protocol.md and a 'when NOT to spawn' column in reviewer-registry.md; test asserts a docs-only diff skips security-reviewer and both plugins cite the same selection principle"); basis verified live at `plugins/saga/skills/code-review/SKILL.md:48-50` (names and rejects the fixed-roster pattern) and `plugins/team-execution/skills/team-execution/references/reviewer-registry.md:9-11` ("these three reviewers spawned [on every] plan execution regardless of plan type [or] content" — the exact pattern SKILL.md:48-50 rejects) | facet |

**Binding decisions this issue builds on / must not contradict:**
- Plugin-sprawl concern (`{#plugin-portfolio-groom-17-to-7}`,
  `docs/plans/2026-07-03-plugin-fleet-grounding-brief.md` §2): this issue creates no new plugin —
  the shared registry lives inside the existing `saga` or `team-execution` plugin tree.
- `{#external-engines-never-gatekeepers}` (#283): the judgment-selection adapter and
  domain-coverage check operate on Claude-run review loci only; this issue adds no external-engine
  gatekeeper role to either consensus locus.
- Consumer-side signal #1, rename/contract-mirror drift (grounding brief §3): this issue's entire
  premise (one shared registry instead of two hand-authored ones) operationalizes the fix for this
  recurring failure class, applied to review membership.

## Recommended Executor Profile

- **Model:** sonnet
- **Effort:** high
- **Backend:** inline
- **External LLM:** none
- **Justification:** this is a bounded consolidation of two already-structured markdown
  registries into one, plus two thin selection adapters and a panel-composition step ported from
  an existing, already-proven pattern in the same repo (saga's judgment-selection) — mechanical
  but requires real cross-file correctness care (two independent consumer loci must both resolve
  correctly against the merged source, and no existing panel may silently lose a member in
  migration). Sonnet/high matches the fleet's own work-shape heuristic for this kind of bounded,
  cross-file mechanical transform; no adversarial judgment or novel design is required, so no
  external-LLM chaperone dispatch is warranted.

## Release-Surface Checklist

This issue changes both saga's and team-execution's skill-consumed reference documents, so the
following must update in the same PR:
- [ ] `plugins/saga/.claude-plugin/plugin.json` — version bump reflecting the shared-registry
      consolidation and the judgment-selection adapter.
- [ ] `plugins/team-execution/.claude-plugin/plugin.json` — version bump reflecting the
      panel-composition step, the "when NOT to spawn" field, and the keyword-match adapter.
- [ ] `.claude-plugin/marketplace.json` — both `saga` and `team-execution` entries' versions/
      descriptions kept in sync with their respective `plugin.json` bumps.
- [ ] `plugins/saga/CHANGELOG.md` — entry describing the shared-registry consolidation and its
      judgment-selection adapter.
- [ ] `plugins/team-execution/CHANGELOG.md` — entry describing the panel-composition step, the
      domain-coverage check, and the "when NOT to spawn" field.
- [ ] Drift-guard/version-metadata tests (repo's existing marketplace/plugin-metadata drift tests)
      updated or confirmed still green against both version bumps.

## Files Expected to Change

- `plugins/saga/skills/code-review/references/lens-catalog.md` — promoted to (or replaced by) the
  shared registry location.
- `plugins/team-execution/skills/team-execution/references/reviewer-registry.md` — becomes a thin
  view over the shared registry, or is deleted in favor of a direct reference; gains a
  "when NOT to spawn" column if retained.
- `plugins/team-execution/skills/team-execution/references/consensus-protocol.md` — new "Panel
  composition" step (judgment-selection + domain-coverage check).
- `plugins/saga/skills/code-review/SKILL.md` — updated reference path(s) if the shared registry
  moves location; cross-reference to the shared selection principle.
- `tests/test_lens_reviewer_registry.py` — new single-source, drift-guard, and no-lost-entry
  tests.
- `tests/test_panel_composition.py` — new docs-only-diff composition test and
  consistent-selection-principle test.
- `plugins/saga/.claude-plugin/plugin.json`, `plugins/team-execution/.claude-plugin/plugin.json`,
  `.claude-plugin/marketplace.json`, `plugins/saga/CHANGELOG.md`,
  `plugins/team-execution/CHANGELOG.md` — release-surface updates.

## Tests to Add or Update

- `tests/test_lens_reviewer_registry.py::test_single_source` — no hand-authored membership list
  survives outside the shared registry in either consuming file.
- `tests/test_lens_reviewer_registry.py::test_drift_guard` — a probe lens/reviewer added once to
  the shared registry is selectable by both adapters.
- `tests/test_lens_reviewer_registry.py::test_no_lost_entries` — every reviewer/lens present in
  the pre-migration files resolves to an entry in the shared registry post-migration.
- `tests/test_panel_composition.py::test_docs_only_skips_security` — a docs-only scratch diff
  skips `security-reviewer` under the new panel-composition step.
- `tests/test_panel_composition.py::test_consistent_selection_principle` — `code-review/SKILL.md`
  and `consensus-protocol.md` cite the same selection-principle source string.

### Verification
```bash
# New shared-registry consolidation suite
uv run pytest tests/test_lens_reviewer_registry.py -v

# New panel-composition behavior suite
uv run pytest tests/test_panel_composition.py -v

# Full repo gate (CI parity)
uv run pytest && uv run ruff format --check . && uv run ruff check . && uv run mypy plugins/ scripts/ tests/ --ignore-missing-imports
```
Expected: all green; a probe lens/reviewer added to only one of the pre-migration files (simulated
via a fixture) turns the drift-guard test red; a fixture docs-only diff run through the
pre-migration `consensus-protocol.md` (no panel-composition step) turns the composition test red,
green after the step lands.

## Handoff Maturity

requirements-ready

## Suggested Next Action

Use `/plan <issue>` to create an implementation plan.

## Source Context

- Source: `docs/plans/plugin-fleet-ideation-2026-07-03/survivors/T5.json` (ids `T5-F4-5`,
  `T5-F1-7`)
- Source type: ideation survivors + issue-map consolidation
- Source title: One shared lens/reviewer registry feeding both consensus loci, with
  judgment-selected diversity-aware panel composition

### Context library links

_none_

### Files expected to change

- `references/lens-catalog.md`
- `docs/plans/2026-07-03-plugin-fleet-grounding-brief.md`
- `plugins/saga/skills/code-review/references/lens-catalog.md`
- `code-review/SKILL.md`
- `docs/sdlc-issue-drafts/plugin-fleet/pf-adr-derived-review-lenses.md`
- `docs/plans/plugin-fleet-ideation-2026-07-03/survivors/T5.json`
- `plugins/saga/.claude-plugin/plugin.json`
- `plugins/team-execution/.claude-plugin/plugin.json`

### Tests to add or update

- `tests/test_lens_reviewer_registry.py`
- `tests/test_panel_composition.py`

### Objective

"Establish single-source-of-truth for shared primitives"

## Created Issue

- URL: https://github.com/infiquetra/infiquetra-claude-plugins/issues/418
- Number: 418
- Created at: 2026-07-04T08:07:24.404408+00:00

