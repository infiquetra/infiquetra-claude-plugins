---
title: "enhancement: persisted tier preferences — per-repo tier defaults with remembered overrides, plus issue-carried tier bands"
repo: infiquetra-claude-plugins
type: enhancement
team: campps
project: operations
status: Idea
labels: enhancement, hermes-task, needs-plan
risk: medium
handoff_maturity: requirements-ready
tier: structural
wave: wave-1
objective: "Make tier+effort a first-class priced resolvable lever"
---

# enhancement: persisted tier preferences — per-repo tier defaults with remembered overrides, plus issue-carried tier bands

### Objective
Make tier+effort a first-class priced resolvable lever.

### Tier
structural

### Wave
wave-1

## Problem / Motivation

The fleet has exactly one operator-facing model/effort lever: saga `/plan`'s unit tier table
(`plugins/saga/skills/plan/SKILL.md:296-352`), drawing from the tier vocabulary
`MODELS=("fable","opus","sonnet","haiku")` / `EFFORTS=(...,"xhigh")`
(`plugins/saga/scripts/execution_spec.py:52-53`). Every agent frontmatter across all 8 plugins
hardcodes `model:` and carries zero `effort:` fields, so this table is the only knob that exists.

That table is re-derived from scratch on every `/plan` run. The grounding brief's session-mining
synthesis ranks this as recurring pain pattern 6 across 3 repos: "Ad hoc tier reasoning every
time — xhigh-Opus on everything wasteful; manual per-unit tier tables; operator asking mid-run
model-change pauses" (`docs/plans/2026-07-03-plugin-fleet-grounding-brief.md:132-134`). Nothing
in the current tier table lifecycle carries a repo's or an operator's accreted judgment forward:
a repo that has already tuned its tiers pays the same full-derivation cost on run N as it did on
run 1. There is also no persistence hook anywhere in `execution_spec.py` today — tiers are
authored fresh into each spec, not loaded from any per-repo overlay file (verified: no
`tier-defaults`, `.saga/tier-defaults`, or equivalent loader exists in
`plugins/saga/scripts/execution_spec.py` as of this writing).

Two absorbed ideas name the same persistence gap at two different points in the lifecycle:

- **T12-F4-4** (primary): a per-repo `.saga/tier-defaults.json` overlay that layers repo-pinned
  work-shape→tier defaults over the shared tier-policy registry, plus write-back of the operator's
  last confirmed override per work-shape, so the *next* `/plan` run proposes the accreted
  preference instead of re-deriving from a blank table.
- **T12-F6-8** (facet): move the same lever one hop upstream — `mission-control:issue` stamps a
  recommended tier band (derived from issue type/labels) onto the issue body at creation time, and
  `/plan` Step 1 pre-fills its tier table from that band instead of deriving cold.

Both target the same underlying defect — tier judgment evaporates at the end of every run — from
different ends of the lifecycle (plan-time persistence vs. issue-time staging), so they are
consolidated into one issue rather than filed and built as two uncoordinated persistence
mechanisms that could disagree on precedence.

## Definition of Done

A merged PR that:

1. Adds a `.saga/tier-defaults.json` schema and a loader inside
   `plugins/saga/scripts/execution_spec.py` (or a small new sibling module it imports) that
   resolves tier for a given work-shape with overlay precedence: **repo defaults > shared tier
   registry** (the table at `plugins/saga/skills/plan/SKILL.md:296-352`).
2. Adds remembered-override write-back: when an operator confirms/changes a proposed tier for a
   work-shape during `/plan`, that confirmation is persisted into the repo's
   `.saga/tier-defaults.json` so the next run proposes it instead of the shared-registry default.
3. Adds a test proving a pinned repo default in `.saga/tier-defaults.json` overrides the shared
   registry's default for the same work-shape.
4. Adds a test (or documented manual verification sequence, since `/plan` is an interactive skill
   invocation, not a pure function) proving that a second consecutive `/plan` run in a repo with a
   confirmed override from the first run proposes that override without re-prompting on an
   unchanged work-shape.
5. As a stretch criterion (T12-F6-8 facet), adds a `recommended-tier-band` field to the
   mission-control issue template/schema and a `/plan` Step 1 reader that pre-fills the tier table
   from it when present on the source issue, verified against a fixture defect-type issue that
   pre-fills the opus/high judgment band.
6. Updates the release-surface artifacts for every plugin whose behavior, schema, or
   operator-facing guidance changed (see checklist below).

### Acceptance criteria
- [ ] **AC1 (T12-F4-4 — overlay schema + precedence).** A `.saga/tier-defaults.json` file with a
  repo-pinned tier for work-shape `mechanical` resolves to that pinned tier in `/plan`'s tier
  table, overriding the shared registry's `sonnet / medium` default for that shape. Check:
  `uv run pytest tests/test_execution_spec.py -k tier_defaults_overlay_precedence` passes.
- [ ] **AC2 (T12-F4-4 — write-back).** Confirming a tier override for a work-shape during a
  `/plan` run persists that override into `.saga/tier-defaults.json` under the correct
  work-shape key, without clobbering other unrelated keys already present in the file. Check:
  `uv run pytest tests/test_execution_spec.py -k tier_defaults_writeback` passes.
- [ ] **AC3 (T12-F4-4 — second-run reuse, the compounding claim).** Given a repo whose
  `.saga/tier-defaults.json` already carries a confirmed override from a prior run, a second
  `/plan` run proposes that override as the starting table entry for the unchanged work-shape and
  does not re-prompt the operator for it. Check: `uv run pytest tests/test_execution_spec.py -k
  tier_defaults_second_run_reuse` passes (a scripted two-invocation fixture, not a live
  interactive session).
- [ ] **AC4 (T12-F4-4 — malformed/missing overlay is non-fatal).** A missing
  `.saga/tier-defaults.json` falls back cleanly to the shared registry with no error; a malformed
  one fails loud with a named error rather than silently ignoring the file (consistent with the
  repo's halt-not-degrade convention, `docs/engineering-journal/DECISIONS.md` parse-seam
  precedent). Check: `uv run pytest tests/test_execution_spec.py -k tier_defaults_malformed`
  passes.
- [ ] **AC5 (T12-F6-8 — issue-carried tier band, stretch).** `mission-control:issue` writes a
  `recommended-tier-band` structured field into a created issue's body, derived from a
  type/label→band mapping (e.g., defect-investigation → `opus / high`, mechanical
  context-update → `sonnet / medium`, read-only survey → `sonnet / low`). Check:
  `uv run pytest plugins/mission-control/tests/test_card_validator.py -k
  recommended_tier_band_field` passes.
- [ ] **AC6 (T12-F6-8 — /plan reads the band, stretch).** Given a fixture defect-type issue
  carrying a `recommended-tier-band` field, `/plan` Step 1 pre-fills its tier table from that band
  instead of deriving cold, and the operator confirms once rather than re-deriving from scratch.
  Check: `uv run pytest tests/test_execution_spec.py -k tier_band_prefill_from_issue` passes.
- [ ] **AC7 (precedence between the two mechanisms is defined, not implicit).** When both a
  repo-level `.saga/tier-defaults.json` override and an issue-carried `recommended-tier-band`
  are present for the same work-shape, the merged PR documents and tests which one wins (repo
  override is closer to the point of execution and should take precedence over the coarser
  issue-time band). Check: `uv run pytest tests/test_execution_spec.py -k
  tier_defaults_vs_issue_band_precedence` passes.
- [ ] **AC8 (repo-wide gates stay green).** Check:
  `uv run pytest && uv run ruff check . && uv run mypy plugins/ scripts/ tests/
  --ignore-missing-imports && uv run bandit -r plugins/`.

### Out-of-scope / non-goals
In scope:
- The `.saga/tier-defaults.json` overlay loader, precedence rule, and write-back inside saga's
  `/plan` skill and `execution_spec.py`.
- The mission-control issue-template `recommended-tier-band` field and its `/plan`-side reader
  (facet, stretch — may be split to a fast-follow issue at plan time if `/plan` finds it exceeds
  the structural-tier budget for this issue; see Recommended executor profile).

Non-goals (do not build in this issue):
- Any change to the shared tier-policy registry's own defaults or vocabulary
  (`MODELS`/`EFFORTS` closed sets in `execution_spec.py:52-53`) — this issue only adds an overlay
  in front of it.
- Automatic (non-confirmed) tier changes — every persisted override still originates from an
  explicit operator confirmation during a `/plan` run; the mechanism never silently promotes or
  demotes a tier on its own.
- A cross-repo or shared/org-level tier-preference store — `.saga/tier-defaults.json` is
  per-repo only in v1; a fleet-wide aggregation of preferences is out of scope.
- Extending `team-execution`'s per-teammate effort fields or agent frontmatter `model:` hardcoding
  — those are separate, already-tracked surfaces (`{#team-execution-per-teammate-effort}` in
  QUEUED.md) and are not touched here.
- Spend-increase confirmation UX (asking the operator before a tier escalation that raises cost) —
  that is idea T12-F4-3's territory and is assumed as an existing/parallel gate this overlay sits
  behind, not something this issue redesigns.

## Grounding References

- **T12-F4-4** (primary, absorbed) — basis: grounding brief session-mining pattern 6, "Ad hoc tier
  reasoning every time — xhigh-Opus on everything wasteful; manual per-unit tier tables; operator
  asking mid-run model-change pauses (3 repos)"
  (`docs/plans/2026-07-03-plugin-fleet-grounding-brief.md:132-134`). `dod_sketch`: merged
  `.saga/tier-defaults.json` overlay loader (repo defaults > shared registry) + remembered-override
  write-back; verified by a two-run test where the second `/plan` proposes the first run's
  confirmed overrides without re-asking unchanged shapes.
- **T12-F6-8** (facet, absorbed) — basis: the same session-mining pattern 6, plus the existing
  6-type issue taxonomy (capability/enhancement/defect/exploration/context-update/objective)
  already carried by `mission-control:issue`; explicitly satisfies the plugin-sprawl guard
  `{#plugin-portfolio-groom-17-to-7}` (no new plugin — the field lives on the existing
  mission-control issue template). `dod_sketch`: merged recommended-tier-band field on the
  mission-control issue template + type/label→band mapping + saga `/plan` reader; verified by a
  fixture defect issue confirming `/plan` pre-fills the opus/high judgment band.
- Binding decisions this issue must not violate: `{#tier-vocab-ordering}` — tier tuples are
  ordered escalation ladders, not just closed sets, so the overlay must resolve to a value drawn
  from the existing ordered vocabulary, never invent a new tier value.
  `{#plugin-portfolio-groom-17-to-7}` — plugin sprawl is an active concern; this issue adds fields
  and a loader to two existing plugins (saga, mission-control), it does not introduce a new one.
  `{#operator-choice-framework}` — operator-choice stays doc-only/CLI-driven through `/plan`; this
  issue must not turn tier selection into a silent, un-confirmed automatic process.

## Recommended Executor Profile

- **Model:** sonnet
- **Effort:** medium
- **Backend:** inline
- **External LLM posture:** none
- **Justification:** this is schema/loader/write-back plumbing over an already-well-specified tier
  vocabulary and an existing, documented tier table — mechanical, deterministic scaffolding work,
  not judgment or architectural design. The AC5/AC6 stretch facet (issue-template field +
  cross-plugin reader) is the part most likely to want a plan-time split if it grows the diff
  past a single structural-tier unit; `/plan` should size that at plan time rather than this issue
  presupposing a bigger tier.

## Release-Surface Checklist

Plugin behavior, schema, and operator-facing guidance change in both saga and mission-control, so
update in the same PR:
- [ ] `plugins/saga/.claude-plugin/plugin.json` — version bump for the tier-overlay/write-back
  behavior change.
- [ ] `plugins/mission-control/.claude-plugin/plugin.json` — version bump if AC5/AC6 land in this
  PR (issue-template schema change).
- [ ] `.claude-plugin/marketplace.json` — bump the corresponding entries for both plugins.
- [ ] `plugins/saga/CHANGELOG.md` — entry describing the `.saga/tier-defaults.json` overlay,
  precedence rule, and write-back.
- [ ] `plugins/mission-control/CHANGELOG.md` — entry describing the `recommended-tier-band` field,
  if AC5/AC6 land in this PR.
- [ ] Drift-guard tests — extend `plugins/mission-control/tests/test_template_sync.py` and
  `plugins/mission-control/tests/test_card_validator.py` to assert the new field is recognized by
  the card validator; extend `execution_spec.py`'s existing spec-validation tests to cover the new
  overlay schema so a malformed `.saga/tier-defaults.json` fails the same way other malformed spec
  inputs do today.

### Files expected to change
- `plugins/saga/scripts/execution_spec.py` — tier overlay loader, precedence resolution,
  write-back of confirmed overrides.
- `plugins/saga/skills/plan/SKILL.md` — Step 1 documentation of the overlay/precedence behavior
  and (if AC5/AC6 in scope) the issue-band prefill step.
- `plugins/mission-control/skills/issues/references/templates-reference.md` — new
  `recommended-tier-band` field definition (stretch, AC5/AC6).
- `plugins/mission-control/scripts/sync_template_docs.py` and/or `card_validator.py` path —
  validation of the new field (stretch, AC5/AC6).
- `tests/test_execution_spec.py` — new overlay/write-back/precedence tests.
- `plugins/mission-control/tests/test_card_validator.py` — new field-recognition test (stretch).

### Tests to add or update
- Overlay precedence: repo-pinned tier wins over shared-registry default for the same work-shape.
- Write-back: confirmed override persists into `.saga/tier-defaults.json` without clobbering
  unrelated keys.
- Second-run reuse: persisted override is proposed (not re-derived) on the next run.
- Malformed/missing overlay file: missing falls back cleanly; malformed fails loud, named.
- (Stretch) Issue-template field recognized by card validator; `/plan` prefill from a fixture
  defect issue's band; repo-override-vs-issue-band precedence.

### Verification
```bash
uv run pytest tests/test_execution_spec.py -k tier_defaults -v
uv run pytest plugins/mission-control/tests/test_card_validator.py -k tier_band -v
uv run pytest && uv run ruff check . && uv run mypy plugins/ scripts/ tests/ --ignore-missing-imports && uv run bandit -r plugins/
```
Expected: all green.

### Handoff maturity
requirements-ready

### Suggested next action
Use `/plan <issue>` to create an implementation plan. At plan time, confirm whether AC5/AC6 (the
T12-F6-8 facet) ship in this PR or split to a fast-follow issue if the combined diff exceeds a
single structural-tier unit.

### Source context
- Source: `docs/plans/plugin-fleet-ideation-2026-07-03/survivors/` (ids `T12-F4-4`, `T12-F6-8`)
- Source type: ideation survivor consolidation
- Source title: Persisted tier preferences: per-repo defaults with remembered overrides, and
  issue-carried tier bands

### Intent

The fleet has exactly one operator-facing model/effort lever: saga `/plan`'s unit tier table (`plugins/saga/skills/plan/SKILL.md:296-352`), drawing from the tier vocabulary `MODELS=("fable","opus","sonnet","haiku")` / `EFFORTS=(...,"xhigh")` (`plugins/saga/scripts/execution_spec.py:52-53`). Every agent frontmatter across all 8 plugins hardcodes `model:` and carries zero `effort:` fields, so this table is the only knob that exists.

### Context library links

_none_

## Created Issue

- URL: https://github.com/infiquetra/infiquetra-claude-plugins/issues/368
- Number: 368
- Created at: 2026-07-04T07:51:44.414302+00:00

