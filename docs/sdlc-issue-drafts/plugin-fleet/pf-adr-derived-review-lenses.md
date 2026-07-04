---
title: "enhancement: one shared review-lens catalog for both consensus loci, with ADR-derived and ADR-pattern lenses"
repo: infiquetra-claude-plugins
type: enhancement
tier: structural
objective: "Enforce context-library standards at authoring time"
wave: wave-2
team: campps
project: operations
status: Idea
labels: enhancement, hermes-task, needs-plan
risk: medium
handoff_maturity: requirements-ready
executor_profile: {model: sonnet, effort: high, backend: inline, external_llm: none}
---

# enhancement: one shared review-lens catalog for both consensus loci, with ADR-derived and ADR-pattern lenses

### Intent
Give the fleet's two independent review loci — saga's `/code-review` (judgment-selected lens
catalog, `plugins/saga/skills/code-review/references/lens-catalog.md`) and team-execution's
reviewer consensus (fixed roster, `plugins/team-execution/skills/team-execution/references/reviewer-registry.md`)
— one shared lens source of truth instead of two independently hand-maintained ones, and make a
subset of that catalog's entries generated from the binding-decision register
(`docs/engineering-journal/DECISIONS.md`) rather than hand-authored, so a new binding decision
cannot silently go unenforced at review time. A third, advisory-only lens checks touched files
against ADR-derived code patterns, distinct from the generated-lens mechanism.

## Problem / Motivation

- **Two review loci, two independently maintained lens/reviewer lists, no shared source.**
  `plugins/saga/skills/code-review/references/lens-catalog.md` defines saga's judgment-selected
  lens set (4 always-on + conditional lenses, spawned via generic `Explore`/`Task` agents — the
  file states explicitly "orchestrator reads full diff, spawns only lenses with real work to do").
  `plugins/team-execution/skills/team-execution/references/reviewer-registry.md` defines a
  structurally different mechanism: 3 always-spawned named reviewer agents
  (`devils-advocate-reviewer`, `security-reviewer`, `architecture-reviewer`) plus 7 keyword-triggered
  optional reviewer agents (`infra-reviewer`, `api-reviewer`, `testing-reviewer`,
  `code-quality-reviewer`, `privacy-reviewer`, `clarity-reviewer`, `ai-usefulness-reviewer` —
  `reviewer-registry.md:9-42`), for 10 reviewer agents total in `plugins/team-execution/agents/`
  that are described as reviewers (as opposed to the plugin's separate validator/tester/scanner/
  monitor agent family). Neither file references the other; a domain added to one (e.g. a new
  security sub-domain in saga's `security` lens) has no mechanism to propagate to the other locus'
  reviewer roster, and vice versa.
- **Standards enforcement exists inside the context library, not at authoring time in this repo.**
  Per the grounding brief's standards/ADR-enforcement survey
  (`docs/plans/2026-07-03-plugin-fleet-grounding-brief.md` §4): enforcement already exists *inside*
  infiquetra-context-library (`validate.yml` CI running `check_docs.py` schema/frontmatter/link
  lint plus promotion-ledger checks, and `context_census.py --check` keeping `llms.txt` honest) —
  the org convention is **schema-validate-in-CI + self-describing index, not runtime-injected
  blobs**. But the same brief's §4 names the gap directly: "**Absent:** any pull of the library
  into `mission-control:issue` / `saga:plan` creation; any ADR↔code-pattern lint; any reference to
  the library from this repo's CI." This issue closes the ADR↔code-pattern half of that gap for
  this repo's own binding-decision register, using the same schema-validate-in-CI shape rather
  than a new runtime-injection mechanism.
- **A binding decision can land in `DECISIONS.md` with no corresponding review check.** The
  binding-decision register (`docs/plans/2026-07-03-plugin-fleet-grounding-brief.md` §2) lists
  eight anchors — e.g. `{#external-engines-never-gatekeepers}` (#283,
  `docs/engineering-journal/DECISIONS.md:1985`) and `{#external-engine-chaperone-dispatch}` (#318,
  `docs/engineering-journal/DECISIONS.md:2021`) — each imposing a standing constraint on future
  work. Today nothing checks a diff against these anchors at review time; a PR could reintroduce
  exactly the pattern a binding decision forbids (e.g. an external engine holding a gated verdict)
  and no lens in either catalog would name it, because no lens is derived from the register.
- **Rename/contract-mirror drift is the repo's most independently recurring consumer-side finding.**
  The grounding brief's cross-repo consumer-side signal (§3, ranked #1 of 5 by independent-repo
  recurrence, 4 repos) names exactly this failure shape: a hand-copied contract or vocabulary
  drifting from its source of truth (the concrete example: `validate_card_body`'s stale hand-copy
  of `card_validator.py`, 343 "clean" cards failing the live contract → issue #222). A hand-authored
  lens catalog with no generation step from its source of truth (the binding register) is the same
  failure shape applied to review lenses themselves.

## Definition of Done

Merged PR(s) delivering:

1. `plugins/saga/skills/code-review/references/review-lens-catalog.md` — the promoted, shared lens
   catalog (superseding the saga-only `lens-catalog.md` as the canonical source; saga's
   `code-review` skill and its `SKILL.md` reference updated to point at the new path) consumed by
   both loci: team-execution's `reviewer-registry.md` gains a `lens:` column mapping each of its 10
   reviewer agents to the catalog entry/entries it covers.
2. `plugins/saga/skills/code-review/references/adr-lenses.md` — generated (not hand-authored) from
   the binding-decision anchors in `docs/engineering-journal/DECISIONS.md` (the `{#anchor-name}`
   headings), each rendered as one lens entry naming the anchor, its constraint, and a check
   prompt for the reviewing agent.
3. A generator script (e.g. `plugins/saga/scripts/adr_lens_generator.py`) that reads
   `DECISIONS.md`'s binding anchors and re-renders `adr-lenses.md`, plus a parity test asserting
   the set of binding-register anchors equals the set of derived lenses (fails when they diverge
   in either direction — a new anchor with no lens, or a stale lens with no anchor).
4. `plugins/saga/skills/code-review/references/adr-patterns.md` — an advisory (non-blocking) lens
   distinct from #2/#3: it asserts ADR-derived *code patterns* (not binding-register presence)
   against touched files (e.g. "a diff touching `docs/engineering-journal/` without a dated entry"
   per this repo's own auto-maintain journal convention, `CLAUDE.md` §"Engineering journal —
   auto-maintain"), registered on the shared catalog from #1 as an explicitly advisory,
   never-blocking lens.
5. Release-surface updates (see checklist below) reflecting the lens-catalog promotion/rename and
   the new generated-lens mechanism as a fleet-behavior change touching both `saga` and
   `team-execution`.

Verify: parity test is red before the generator exists (proving it actually detects
register/lens divergence), green after; adding a stub binding anchor to a scratch copy of
`DECISIONS.md` reds the parity test until `adr-lenses.md` is regenerated; every reviewer row in
`reviewer-registry.md` resolves its `lens:` value to a real entry in `review-lens-catalog.md`; the
`adr-patterns` lens fires an advisory (non-blocking) finding on a scratch diff touching
`docs/engineering-journal/` without a dated entry, and stays silent when a dated entry is present.

### Acceptance criteria
- [ ] **AC1 (T9-F3-2, primary).** The set of binding-decision anchors in `DECISIONS.md` equals the set
  of lenses derived into `adr-lenses.md` — no anchor without a lens, no lens without a surviving
  anchor. Check: `uv run pytest tests/test_adr_lens_generator.py -k parity` → passes on the merged
  tree; temporarily adding a stub `{#scratch-anchor}` heading to a scratch copy of `DECISIONS.md`
  and re-running the same check fails until `adr-lenses.md` is regenerated.
- [ ] **AC2 (T9-F3-2, primary).** `adr-lenses.md` is machine-generated, not hand-edited — a direct edit
  to `adr-lenses.md` that is not reproducible by re-running the generator against current
  `DECISIONS.md` content is detected. Check: `uv run pytest tests/test_adr_lens_generator.py -k
  generated_matches_source` → passes; hand-editing one rendered lens line without touching
  `DECISIONS.md` and re-running the check fails.
- [ ] **AC3 (T11-F4-3, facet).** Every reviewer agent in `reviewer-registry.md` (currently 10 across
  the Base + Optional Code/Implementation + Optional Docs/Spec sections,
  `reviewer-registry.md:9-42`) carries a `lens:` value that resolves to a real entry in
  `review-lens-catalog.md`. Check: `uv run pytest tests/test_review_lens_catalog.py -k
  reviewer_lens_resolves` → passes for all rows; a scratch row with a `lens:` value that does not
  exist in the catalog fails the same check.
- [ ] **AC4 (T9-F4-8, facet).** `adr-patterns.md` exists as a registered lens on the shared catalog,
  is marked advisory/non-blocking (does not participate in team-execution's unanimous-ACCEPT gate
  or saga `/code-review`'s P0/P1 hard-gate categories), and emits a finding on a diff touching
  `docs/engineering-journal/` without a same-commit dated entry, staying silent when one is
  present. Check: `uv run pytest tests/test_adr_patterns_lens.py -k journal_entry_check` → passes
  on both the emitting and silent cases; `uv run pytest tests/test_adr_patterns_lens.py -k
  advisory_not_blocking` → confirms the lens's finding never sets a blocking/P0 severity.
- [ ] **AC5.** Saga's `code-review` `SKILL.md` and `plugins/saga/skills/code-review/references/`
  no longer reference the pre-promotion `lens-catalog.md` path; all internal references point to
  `review-lens-catalog.md`. Check: `grep -rn "lens-catalog.md" plugins/saga/skills/code-review/`
  → no match (only `review-lens-catalog.md` remains).

### Out-of-scope / non-goals
**In scope:** promoting/renaming the existing saga-only lens catalog into a shared file consumed
by both loci; adding a `lens:` column to `reviewer-registry.md`; the ADR-anchor-to-lens generator,
its parity test, and the generated `adr-lenses.md`; the advisory `adr-patterns.md` lens and its
registration; release-surface updates on both `saga` and `team-execution`.

**Non-goals (deferred, explicitly out of scope for this issue):**
- Pulling infiquetra-context-library content (`llms.txt`, per-topic READMEs) into this repo's
  review flow — that is the separate "pull the library into `mission-control:issue`/`saga:plan`
  creation" gap named in the grounding brief §4 and is not addressed here; this issue only
  operates on this repo's own `DECISIONS.md` binding register.
- Any change to how saga `/code-review` selects *conditional* lenses (judgment-based selection
  stays as-is) or to team-execution's keyword-trigger mechanism for optional reviewers — this
  issue adds lens entries and a `lens:` mapping column, not a new selection algorithm.
- Making the `adr-patterns` lens blocking — AC4 requires it stay advisory; promoting it to a
  blocking gate is separate follow-on work requiring its own review-readiness bar.
- A standing/scheduled catch-rate measurement harness for the generator or the patterns lens —
  per the binding decision on avoiding new measurement-ceremony shapes (`{#tier-vocab-ordering}`-
  adjacent precedent; this repo's own rejected "S-6 ceremony shape" pattern), verification here is
  the parity test and the advisory-finding tests, not a scheduled calibration loop.
- Reworking the context-library's own `validate.yml`/`check_docs.py`/`context_census.py`
  enforcement — those already exist and are out of this repo's blast radius (grounding brief §4).

## Grounding References

| Absorbed idea | Basis | Role |
|---|---|---|
| `T9-F3-2` | `docs/plans/plugin-fleet-ideation-2026-07-03/survivors/T9.json` (`dod_sketch`: "Merged adr-lenses.md (generated from DECISIONS.md binding anchors) + generator + parity test asserting binding-register anchors == derived lenses; verified by adding a stub binding anchor and watching the parity test go red until the lens is regenerated"); `docs/plans/2026-07-03-plugin-fleet-grounding-brief.md` §2 (binding-decision register table) and §4 ("any ADR↔code-pattern lint" named as absent) | primary |
| `T9-F4-8` | `docs/plans/plugin-fleet-ideation-2026-07-03/survivors/T9.json` (`dod_sketch`: "Merged adr-patterns lens + adr_patterns.json registry consumed by saga /code-review, checking touched files against ADR-derived pattern assertions (advisory, not blocking) — distinct from F3-2 (which generates lenses from anchors; this asserts code patterns)"); grounding brief §4 (org convention is schema-validate-in-CI, not runtime-injected blobs — informs keeping this lens advisory/CI-shaped rather than a new blocking gate) | facet |
| `T11-F4-3` | `docs/plans/plugin-fleet-ideation-2026-07-03/survivors/T11.json` (`dod_sketch`: "Merged review-lens-catalog.md + a lens: field on each team-execution reviewer + test asserting every reviewer's lens resolves to a catalog entry; verified catalog covers all 12 reviewers" — current repo state has 10 reviewer agents in `reviewer-registry.md:9-42`; the exact count is verified live by AC3's test rather than hardcoded, since the sketch's figure predates this repo's current reviewer roster); `plugins/saga/skills/code-review/references/lens-catalog.md` (existing saga-only catalog to be promoted); `plugins/team-execution/skills/team-execution/references/reviewer-registry.md` (existing team-execution-only roster to gain the `lens:` column) | facet |

**Binding decisions this issue builds on / must not contradict:**
- Standards/ADR-enforcement org convention (`docs/plans/2026-07-03-plugin-fleet-grounding-brief.md`
  §4): schema-validate-in-CI + self-describing index, not runtime-injected blobs. The generator +
  parity test (AC1/AC2) and the advisory patterns lens (AC4) both follow this shape rather than
  introducing a new runtime-injected enforcement blob.
- Consumer-side signal #1, rename/contract-mirror drift (`docs/plans/2026-07-03-plugin-fleet-grounding-brief.md`
  §3): this issue's entire premise (generate lenses from the register instead of hand-copying them)
  operationalizes the fix for exactly this recurring failure class, applied to review lenses.
- `{#external-engines-never-gatekeepers}` (#283, `DECISIONS.md:1985`): review lenses derived under
  this issue are consumed by Claude-run review loci only; this issue does not add or imply any
  external-engine gatekeeper role in either review locus.

## Recommended Executor Profile

- **Model:** sonnet
- **Effort:** high
- **Backend:** inline
- **External LLM:** none
- **Justification:** this is a mechanical-but-careful consolidation (promote/rename an existing
  file, add a generator over an already-structured markdown source, add a mapping column, add
  parity/resolution tests) rather than novel design or adversarial judgment — sonnet/high matches
  the fleet's own work-shape heuristic for bounded mechanical transforms with real cross-file
  correctness risk (two consumer loci must both resolve correctly). No external-LLM chaperone
  dispatch is warranted; this stays inline within saga's and team-execution's own script/reference
  trees.

## Release-Surface Checklist

This issue changes both saga's and team-execution's skill-consumed reference documents and adds a
new saga script (the generator), so the following must update in the same PR:
- [ ] `plugins/saga/.claude-plugin/plugin.json` — version bump reflecting the lens-catalog
      promotion/rename and the new ADR-lens generator + parity test.
- [ ] `plugins/team-execution/.claude-plugin/plugin.json` — version bump reflecting the new
      `lens:` column on `reviewer-registry.md` and its resolution test.
- [ ] `.claude-plugin/marketplace.json` — both `saga` and `team-execution` entries' versions/
      descriptions kept in sync with their respective `plugin.json` bumps.
- [ ] `plugins/saga/CHANGELOG.md` — entry describing the catalog promotion/rename,
      `adr-lenses.md` generator, and `adr-patterns.md` advisory lens.
- [ ] `plugins/team-execution/CHANGELOG.md` — entry describing the `lens:` column addition and its
      resolution test.
- [ ] Drift-guard/version-metadata tests (repo's existing marketplace/plugin-metadata drift tests)
      updated or confirmed still green against both version bumps.

## Files Expected to Change

- `plugins/saga/skills/code-review/references/lens-catalog.md` — renamed/promoted to
  `review-lens-catalog.md`.
- `plugins/saga/skills/code-review/references/adr-lenses.md` — new, generated file.
- `plugins/saga/skills/code-review/references/adr-patterns.md` — new advisory lens.
- `plugins/saga/scripts/adr_lens_generator.py` — new generator script.
- `plugins/saga/skills/code-review/SKILL.md` — updated reference paths.
- `plugins/team-execution/skills/team-execution/references/reviewer-registry.md` — new `lens:`
  column.
- `tests/test_adr_lens_generator.py` — new parity/generation tests.
- `tests/test_review_lens_catalog.py` — new reviewer-to-lens resolution test.
- `tests/test_adr_patterns_lens.py` — new advisory-lens behavior tests.
- `plugins/saga/.claude-plugin/plugin.json`, `plugins/team-execution/.claude-plugin/plugin.json`,
  `.claude-plugin/marketplace.json`, `plugins/saga/CHANGELOG.md`,
  `plugins/team-execution/CHANGELOG.md` — release-surface updates.

## Tests to Add or Update

- `tests/test_adr_lens_generator.py::test_parity_anchors_equal_lenses` — binding-register anchors
  == derived lenses; red on an added stub anchor until regenerated.
- `tests/test_adr_lens_generator.py::test_generated_matches_source` — hand-edited lens content
  not reproducible from current `DECISIONS.md` is detected.
- `tests/test_review_lens_catalog.py::test_reviewer_lens_resolves` — every `reviewer-registry.md`
  row's `lens:` value resolves to a `review-lens-catalog.md` entry.
- `tests/test_adr_patterns_lens.py::test_journal_entry_check` — fires on a journal-touching diff
  missing a dated entry; silent when present.
- `tests/test_adr_patterns_lens.py::test_advisory_not_blocking` — the lens's finding never carries
  a blocking/P0 severity.

### Verification
```bash
# New ADR-lens generator/parity suite
uv run pytest tests/test_adr_lens_generator.py -v

# Reviewer-to-catalog resolution
uv run pytest tests/test_review_lens_catalog.py -v

# Advisory ADR-pattern lens behavior
uv run pytest tests/test_adr_patterns_lens.py -v

# Full repo gate (CI parity)
uv run pytest && uv run ruff format --check . && uv run ruff check . && uv run mypy plugins/ scripts/ tests/ --ignore-missing-imports
```
Expected: all green; adding a stub binding anchor to a scratch copy of `DECISIONS.md` without
regenerating `adr-lenses.md` turns the parity test red; a scratch `reviewer-registry.md` row with
an unresolvable `lens:` value turns the resolution test red.

## Handoff Maturity

requirements-ready

## Suggested Next Action

Use `/plan <issue>` to create an implementation plan.

## Source Context

- Source: `docs/plans/plugin-fleet-ideation-2026-07-03/survivors/T9.json` (ids `T9-F3-2`,
  `T9-F4-8`), `docs/plans/plugin-fleet-ideation-2026-07-03/survivors/T11.json` (id `T11-F4-3`)
- Source type: ideation survivors + issue-map consolidation
- Source title: One shared review-lens catalog for both consensus loci, with ADR-derived and
  ADR-pattern lenses

### Context library links

_none_

### Files expected to change

- `plugins/saga/skills/code-review/references/lens-catalog.md`
- `plugins/team-execution/skills/team-execution/references/reviewer-registry.md`
- `docs/engineering-journal/DECISIONS.md`
- `docs/plans/2026-07-03-plugin-fleet-grounding-brief.md`
- `plugins/saga/skills/code-review/references/review-lens-catalog.md`
- `plugins/saga/skills/code-review/references/adr-lenses.md`
- `plugins/saga/scripts/adr_lens_generator.py`
- `plugins/saga/skills/code-review/references/adr-patterns.md`

### Tests to add or update

- `tests/test_adr_lens_generator.py`
- `tests/test_adr_patterns_lens.py`
- `tests/test_review_lens_catalog.py`

### Objective

"Enforce context-library standards at authoring time"

## Created Issue

- URL: https://github.com/infiquetra/infiquetra-claude-plugins/issues/403
- Number: 403
- Created at: 2026-07-04T08:02:36.087697+00:00

