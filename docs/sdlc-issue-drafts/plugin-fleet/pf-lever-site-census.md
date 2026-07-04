---
title: "context-update: lever-site census — inventory every tier/gate decision point, cite the tier-lever contract from judgment commands"
repo: infiquetra-claude-plugins
type: context-update
team: campps
project: operations
status: Idea
labels: context-update, hermes-task, needs-plan
risk: medium
handoff_maturity: requirements-ready
tier: structural
objective: Gate fleet integrity (agent files, prompts, release surfaces)
wave: wave-2
---

# context-update: lever-site census — inventory every tier/gate decision point, cite the tier-lever contract from judgment commands

### Intent

`/plan`'s per-unit tier table (`plugins/saga/skills/plan/SKILL.md:296-352`) is today "the fleet's
ONE operator-facing model/effort lever" (`docs/plans/2026-07-03-plugin-fleet-grounding-brief.md`
§7, item 6: "Ad hoc tier reasoning every time" — "xhigh-Opus on everything is wasteful"; manual
per-unit tier tables reported across 3 repos as a recurring pain). Every other site in the fleet
that makes — or should make — a tier/gate decision (a hardcoded model in an agent frontmatter, a
judgment `SKILL.md`'s interactive phase, a fan-out spawn site) does so with no shared vocabulary,
no citation back to a single contract, and no coverage guarantee that a new site won't silently
skip the lever entirely. The grounding brief's correction (c) is explicit: the `{model, effort}`
tier vocabulary and `fable/xhigh` reachability live ONLY in `/plan`'s unit table and are "still
absent from `/ideate`, `/brainstorm`, `/work`'s interactive flow" — `fable/xhigh` is "unreachable
outside saga plan vocabulary."

This issue ships a merged lever-site/control-surface census: a generated document enumerating one
row per tier-decision site across the fleet's 8 plugins, a `tier-lever.md` contract that document
is generated against, citation of that contract from the three named judgment commands
(`/ideate`, `/brainstorm`, `/work`), and coverage/citation drift-guard tests that fail when a
tier-choosing site exists off-census or a judgment command drifts from the palette.

### Problem Frame

- `plugins/saga/skills/plan/SKILL.md:296-352` is the only place in the fleet today with a
  documented `{model, effort}` tier heuristic table and operator-override step — verified by direct
  read during grounding for this draft.
- Grounding brief correction (c) (cited via absorbed idea `T3-F6-2`): "the `{model,effort}` tier
  vocabulary and fable/xhigh reachability live ONLY in `/plan`'s unit table
  (`plan/SKILL.md:296-352`) and are absent from `/ideate`, `/brainstorm`, `/work`'s interactive
  flow" — `fable/xhigh` is "unreachable outside saga plan vocabulary."
- `docs/plans/2026-07-03-plugin-fleet-grounding-brief.md` §7 item 6 records this as a recurring,
  cross-repo pain: "Ad hoc tier reasoning every time — 'xhigh-Opus on everything is wasteful';
  manual per-unit tier tables; operator asking for mid-run model-change pauses (3 repos)."
- The fleet already has one working precedent for a site-inventory-plus-coverage-guard pattern:
  `plugins/saga/references/sandbox-spawn-sites.md`, which classifies every delegated-agent spawn
  site against a two-axis sandbox contract and is cited as the shape to mirror by absorbed idea
  `T12-F4-2`.
- Nothing today enumerates where a new agent, skill, or spawn site can introduce a hardcoded model
  choice, an unreachable `fable/xhigh` tier, or an un-cited judgment phase without any coverage
  check catching it — the fleet has a lever, but no map of where the lever does and doesn't reach.

### Requirements

R1. A generated lever-site census document exists enumerating every tier-choosing decision site
across the fleet's 8 plugins (one row per site: plugin, file, site description, current tier
mechanism if any), mirroring the shape of `plugins/saga/references/sandbox-spawn-sites.md`.

R2. A `tier-lever.md` contract document exists as the single canonical source for the `{model,
effort}` tier vocabulary (including `fable/xhigh` reachability rules), superseding the
implicit contract embedded only in `plan/SKILL.md:296-352`.

R3. Each of the three named interactive judgment `SKILL.md` files (`ideate`, `brainstorm`, `work`)
gains a compact `## Tier vocabulary` front-block naming the recommended `{model, effort}` per
internal sub-phase, citing the `tier-lever.md` contract anchor rather than re-deriving the
vocabulary inline.

R4. A coverage drift-guard test greps the fleet's agent frontmatter and skill tables and fails when
a tier-choosing site (for example a new hardcoded-model agent, or a new judgment-command phase) is
absent from the committed census.

R5. A citation drift-guard test asserts each of the three named judgment `SKILL.md` files (`ideate`,
`brainstorm`, `work`) cites the `tier-lever.md` doc anchor in its `## Tier vocabulary` block, and
fails if the citation is missing or if a cited tier string is not a member of the canonical
`{model, effort}` palette (rejecting bogus tiers such as `opus-max-plus`).

R6. `effort:` is admitted as a recognized key in the agent-frontmatter schema (not merely tolerated
ad hoc), with a corresponding `DECISIONS.md` entry recording the schema admission and linking each
ask-point (site where an operator or agent chooses tier/effort) to its `file:line`.

### Key Flows

F1. **New hardcoded-model agent added without a census row.** A contributor adds a new agent file
under `plugins/*/agents/` with a hardcoded model choice and no corresponding row in the committed
lever-site census. The coverage drift-guard test fails, naming the uncensused site. **Covers R1,
R4.**

F2. **Judgment command citing the tier-lever contract.** `/ideate`, `/brainstorm`, and `/work` each
carry a `## Tier vocabulary` block naming per-sub-phase `{model, effort}` recommendations and citing
`tier-lever.md`'s anchor. The citation drift-guard test passes because the anchor is present and
every cited tier string is a palette member. **Covers R2, R3, R5.**

F3. **Bogus tier string introduced.** A branch edits one of the three judgment `SKILL.md` files to
cite a non-palette tier string (for example `opus-max-plus`). The citation drift-guard test fails,
naming the offending file and string. **Covers R5.**

F4. **`effort:` admitted to schema.** An agent frontmatter file sets `effort: medium` alongside
`model: sonnet`. The agent-frontmatter schema validator accepts it (previously this key was either
absent or tolerated without validation), and `DECISIONS.md` records the admission with a linked
ask-point inventory. **Covers R6.**

### Acceptance criteria
- [ ] AC1. **Covers R1, R4.** Given a new agent file added under any `plugins/*/agents/` directory with
  a hardcoded `model:` and no corresponding row in the committed lever-site census, running the
  coverage drift-guard test fails and names the uncensused site. Check: `uv run pytest
  tests/test_lever_site_census.py -k coverage_drift_guard_fails_on_new_uncensused_agent` → fails
  before the census is updated, passes after; the test itself asserts the failure-then-pass
  behavior via a fixture agent file.
- [ ] AC2. **Covers R2, R3.** Each of `plugins/saga/skills/ideate/SKILL.md`,
  `plugins/saga/skills/brainstorm/SKILL.md`, and `plugins/saga/skills/work/SKILL.md` contains a
  `## Tier vocabulary` block. Check: `grep -l "## Tier vocabulary"
  plugins/saga/skills/ideate/SKILL.md plugins/saga/skills/brainstorm/SKILL.md
  plugins/saga/skills/work/SKILL.md | wc -l` → outputs `3`.
- [ ] AC3. **Covers R3, R5.** Each `## Tier vocabulary` block cites the `tier-lever.md` doc anchor.
  Check: `uv run pytest tests/test_lever_site_census.py -k
  judgment_commands_cite_tier_lever_anchor` → passes.
- [ ] AC4. **Covers R5.** Given a branch that edits one judgment `SKILL.md`'s `## Tier vocabulary`
  block to cite a non-palette tier string (for example `opus-max-plus`), the citation drift-guard
  test fails and names the offending file. Check: `uv run pytest tests/test_lever_site_census.py -k
  citation_drift_guard_fails_on_bogus_tier` → passes (test fixture reproduces the failure).
- [ ] AC5. **Covers R1.** The lever-site census document enumerates a tier-decision row for every
  distinct tier-choosing site type currently known in the fleet (agent-frontmatter model, judgment
  interactive phase, `/plan` unit table, fan-out spawn site). Check: `uv run python3
  scripts/lever_site_census.py --write docs/references/lever-sites.md && grep -c "^|" 
  docs/references/lever-sites.md` → returns a row count greater than 0 covering all four site
  types.
- [ ] AC6. **Covers R6.** `effort:` is a recognized key in the agent-frontmatter schema, and
  `DECISIONS.md` carries an entry recording the admission. Check: `uv run pytest
  tests/test_agent_frontmatter_schema.py -k effort_key_admitted` → passes; `grep -n "effort:"
  docs/engineering-journal/DECISIONS.md` → matches found.
- [ ] AC7. **Covers R2.** A `tier-lever.md` contract document exists and is the sole document defining
  the `{model, effort}` palette and `fable/xhigh` reachability rules (not re-derived inline in
  `plan/SKILL.md`). Check: `test -f plugins/saga/references/tier-lever.md && grep -n "fable" 
  plugins/saga/references/tier-lever.md` → file exists and matches found.

## Definition of Done

A merged lever-sites/control-surface census document exists (one row per tier-decision site across
the fleet's 8 plugins) alongside a canonical `tier-lever.md` `{model, effort}` contract, with
`ideate`, `brainstorm`, and `work` each citing that contract's anchor from a `## Tier vocabulary`
block. Coverage and citation drift-guard tests fail when a tier-choosing site is absent from the
census or a judgment command cites a non-palette tier string, and pass once the census, contract,
and citations are in place. `effort:` is admitted to the agent-frontmatter schema with a
corresponding `DECISIONS.md` entry.

### Out-of-scope / non-goals
- v1 covers the three named judgment commands (`ideate`, `brainstorm`, `work`) for the `## Tier
  vocabulary` front-block and citation requirement; it does not retrofit every skill in the fleet
  with a tier-vocabulary block — only the ones the grounding brief names as currently missing the
  vocabulary.
- v1 does not change `/plan`'s existing tier-table mechanism or its operator-override flow
  (`plan/SKILL.md:296-352`) — it extracts the vocabulary into `tier-lever.md` as the shared source
  of truth and has `/plan` (along with the three judgment commands) cite it, without altering
  `/plan`'s UX.
- v1 does not build a runtime enforcement layer that blocks a mismatched tier choice at spawn time
  — the drift-guard tests are static/CI-time checks against committed documents and frontmatter,
  not a runtime gate on live dispatch.
- v1 does not backfill `effort:` onto every existing agent file; it admits the key to the schema
  and records the decision. Retrofitting existing agents with explicit `effort:` values is separate,
  future work.
- v1 does not change the sandbox-spawn-site inventory (`sandbox-spawn-sites.md`) itself — it is
  cited as prior art for the census shape, not edited by this issue.

### Files expected to change

- `scripts/lever_site_census.py` — new script: scans agent frontmatter, judgment-command
  `SKILL.md` files, `/plan`'s unit table, and fan-out spawn sites for tier-choosing decision
  points; emits/diffs the committed census document.
- `docs/references/lever-sites.md` (or `plugins/saga/references/lever-sites.md`) — new committed
  census document, one row per tier-decision site.
- `plugins/saga/references/tier-lever.md` — new canonical `{model, effort}` tier-vocabulary
  contract document, including `fable/xhigh` reachability rules.
- `plugins/saga/skills/ideate/SKILL.md` — add `## Tier vocabulary` front-block citing
  `tier-lever.md`.
- `plugins/saga/skills/brainstorm/SKILL.md` — add `## Tier vocabulary` front-block citing
  `tier-lever.md`.
- `plugins/saga/skills/work/SKILL.md` — add `## Tier vocabulary` front-block citing
  `tier-lever.md`.
- `plugins/saga/skills/plan/SKILL.md` — update tier-table section (~lines 296-352) to cite
  `tier-lever.md` as the vocabulary source instead of re-deriving it inline.
- Agent-frontmatter schema (wherever validated today, for example
  `scripts/validate_plugins.py` or an equivalent schema file) — admit `effort:` as a recognized
  key.
- `docs/engineering-journal/DECISIONS.md` — new entry recording the `effort:` schema admission and
  linking each ask-point to its `file:line`.
- `tests/test_lever_site_census.py` — new test file: coverage drift-guard, citation drift-guard,
  bogus-tier rejection.
- `tests/test_agent_frontmatter_schema.py` — updated or new test asserting `effort:` is accepted.

### Tests to add or update

- `tests/test_lever_site_census.py::test_coverage_drift_guard_fails_on_new_uncensused_agent` — a
  new hardcoded-model agent with no census row fails the coverage check.
- `tests/test_lever_site_census.py::test_judgment_commands_cite_tier_lever_anchor` — `ideate`,
  `brainstorm`, and `work` each cite the `tier-lever.md` anchor.
- `tests/test_lever_site_census.py::test_citation_drift_guard_fails_on_bogus_tier` — a non-palette
  tier string in a judgment command's `## Tier vocabulary` block fails the citation check.
- `tests/test_agent_frontmatter_schema.py::test_effort_key_admitted` — `effort:` is accepted by the
  agent-frontmatter schema validator.

### Verification

```bash
# New census + drift-guard tests
uv run pytest tests/test_lever_site_census.py -v

# Agent-frontmatter schema accepts effort:
uv run pytest tests/test_agent_frontmatter_schema.py -k effort_key_admitted -v

# Regenerate the committed census and confirm no undiffed drift
uv run python3 scripts/lever_site_census.py --write docs/references/lever-sites.md
git diff --stat docs/references/lever-sites.md

# Full repo gate (CI parity)
uv run pytest && uv run ruff check . && uv run ruff format --check . && uv run mypy plugins/ scripts/ tests/ --ignore-missing-imports
```

Expected: all green; the coverage and citation drift-guard tests demonstrably fail on their
respective fixture cases before the corresponding fix and pass after; `effort:` is accepted by the
schema; `docs/references/lever-sites.md` and `plugins/saga/references/tier-lever.md` are committed.

### Release-surface checklist

This issue changes `saga` plugin skill content (`ideate`, `brainstorm`, `work`, `plan` `SKILL.md`
files) and adds a new reference document plus a schema change (admitting `effort:`), so the saga
plugin's release surfaces are implicated:

- [ ] `plugins/saga/.claude-plugin/plugin.json` version bumped to reflect the new
      `## Tier vocabulary` blocks, the new `tier-lever.md` reference, and the `effort:` schema
      admission.
- [ ] `.claude-plugin/marketplace.json` updated to match the bumped `saga` version.
- [ ] `plugins/saga/CHANGELOG.md` gets an entry describing the lever-site census, the
      `tier-lever.md` contract, the judgment-command citations, and the `effort:` schema admission.
- [ ] Any version/metadata drift-guard tests (for example plugin-manifest parity tests under
      `tests/`) are updated to cover the new reference files and schema field.

## Grounding References

- Absorbed idea `T12-F4-2` — "A model/effort lever-site inventory registry, mirroring
  sandbox-spawn-sites.md" (role: primary). Basis: `docs/plans/plugin-fleet-ideation-2026-07-03/
  survivors/T12.json`. DoD sketch: "Merged lever-sites.md registry (one row per tier-decision site)
  + coverage test that greps frontmatter/skill tables and fails if a tier-choosing site is absent
  from the registry." This drives R1, R4 and AC1, AC5.
- Absorbed idea `G-negative-space-9` — "The fleet control-surface census: one generated,
  always-current map of every operator lever, gate, and envelope across all plugins" (role: facet).
  Basis: `docs/plans/plugin-fleet-ideation-2026-07-03/survivors/T12.json`. Outcome shape: "PR adding
  `scripts/control_surface_census.py` (extracts levers/gates/envelope fields from skill frontmatter
  + registries into `docs/references/fleet-control-surface.md`) + a CI check failing when a lever
  exists off-census; first generated census committed." This drives R1, R4 and AC1, AC5 — the
  general control-surface census is scoped down in this issue to the tier/gate lever subset named
  by `T12-F4-2`.
- Absorbed idea `T12-F6-5` — "Fleet lever-placement inventory: name the ask-points and open the
  effort seam" (role: facet). Basis: `docs/plans/plugin-fleet-ideation-2026-07-03/survivors/
  T12.json`. DoD sketch: "Merged DECISIONS entry + lever-placement.md ask-point inventory + effort:
  admitted to the agent-frontmatter schema; verified by a schema test accepting `effort:` on an
  agent and DECISIONS linking each ask-point to file:line." This drives R6 and AC6.
- Absorbed idea `T12-F1-1` — "Tier-lever decision contract cited by every judgment command, not
  just `/plan`" (role: facet). Basis: `docs/plans/plugin-fleet-ideation-2026-07-03/survivors/
  T12.json`. DoD sketch: "Merged `saga/references/tier-lever.md` contract + offer-hook lines in
  ideate/brainstorm/work SKILLs + release-surface bump; verified by a citation drift-guard test
  asserting each named SKILL references the doc anchor." This drives R2, R3, R5 and AC2, AC3, AC4,
  AC7.
- Absorbed idea `T3-F6-2` — "Per-phase tier declaration blocks in the interactive judgment skills"
  (role: facet). Basis: `docs/plans/plugin-fleet-ideation-2026-07-03/survivors/T3.json`. Grounded
  in grounding-brief correction (c): "the {model,effort} tier vocabulary and fable/xhigh
  reachability live ONLY in `/plan`'s unit table (`plan/SKILL.md:296-352`) and are absent from
  `/ideate`, `/brainstorm`, `/work`'s interactive flow"; `fable/xhigh` "unreachable outside saga
  plan vocabulary." DoD sketch: "Merged Tier-vocabulary front-block added to ideate/brainstorm/work
  SKILL.md + grep-based doc-lint asserting block presence and palette-membership of cited tiers;
  verify: lint fails a branch citing a bogus tier like opus-max-plus." This drives R3, R5 and AC2,
  AC3, AC4.
- Grounding brief `docs/plans/2026-07-03-plugin-fleet-grounding-brief.md` §7, item 6 — recurring
  cross-repo pain: "Ad hoc tier reasoning every time — 'xhigh-Opus on everything is wasteful';
  manual per-unit tier tables; operator asking for mid-run model-change pauses (3 repos). → theme
  12."
- Prior-art pattern this issue mirrors: `plugins/saga/references/sandbox-spawn-sites.md` — an
  existing site-inventory-plus-classification document for sandbox spawn sites, confirmed present
  via direct read during grounding for this draft; cited directly by `T12-F4-2`'s idea text.
- Existing tier-table baseline this issue extracts a shared vocabulary from:
  `plugins/saga/skills/plan/SKILL.md:296-352` (Step 1 — Derive per-unit tiers, the work-shape
  heuristic table), confirmed via direct read during grounding for this draft.
- Consolidation rationale (issue map): the five absorbed ideas span the same underlying gap — a
  tier/gate lever that exists in exactly one place (`/plan`) with no fleet-wide inventory, no
  shared vocabulary contract, no citation from other judgment commands, and no schema support for
  `effort:` — so they are merged into one structural context-update rather than shipped as five
  separate issues.

### Recommended executor profile

- **Model:** sonnet
- **Effort:** medium
- **Backend:** inline
- **External LLM:** none
- **Justification:** This is document-generation, doc-lint, and schema-admission work — a census
  script, a contract document, front-block insertions into three known files, and grep-based
  drift-guard tests — with no adversarial judgment or architectural ambiguity beyond what the five
  absorbed ideas already specify. It matches the fleet's tiering guidance for mechanical,
  deterministic transforms (sonnet/medium), and the census-generation nature of the read-only scan
  portion does not by itself warrant a lower tier since the doc-lint and schema-edit portions carry
  write risk that benefits from medium effort.

### Handoff maturity

requirements-ready

### Suggested next action

Use `/plan <issue>` to create an implementation plan.

### Source context

- Source: `docs/plans/plugin-fleet-ideation-2026-07-03/survivors/T12.json` (ids `T12-F4-2`,
  `G-negative-space-9`, `T12-F6-5`, `T12-F1-1`), `docs/plans/plugin-fleet-ideation-2026-07-03/
  survivors/T3.json` (id `T3-F6-2`)
- Source type: ideation survivor absorption (issue-map)
- Source title: Lever-site census: inventory every tier/gate decision point, cite the tier-lever
  contract from judgment commands, generate the fleet control-surface map

### Context library links

_none_

### Objective

Gate fleet integrity (agent files, prompts, release surfaces)
