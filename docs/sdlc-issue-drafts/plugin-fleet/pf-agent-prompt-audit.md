---
title: "exploration: agent-prompt quality audit — scored rubric, prompt-contract auditor, scheduled advisory re-grade"
repo: infiquetra-claude-plugins
type: exploration
team: campps
project: operations
status: Idea
labels: exploration, hermes-task, needs-plan
risk: medium
handoff_maturity: requirements-ready
tier: structural
objective: "Gate fleet integrity (agent files, prompts, release surfaces)"
wave: wave-2
---

# exploration: agent-prompt quality audit — scored rubric, prompt-contract auditor, scheduled advisory re-grade

## Objective

Gate fleet integrity (agent files, prompts, release surfaces).

## Summary

The fleet has 34 agent files across 8 plugins (`find plugins -path '*/agents/*.md' | wc -l` → 34,
verified 2026-07-03) with no durable, scored record of prompt quality, no mechanism that flags a
prompt or frontmatter claim ("uses tool X", "runs at effort Y") that isn't backed by executable
code, and no recurring re-grade as agents drift. This issue is the judgment-shaped counterpart to
a mechanical frontmatter lint (tracked separately): it produces (1) a durable scorecard document
scoring every agent against a written rubric, (2) a `plugin_contract_audit.py` script that flags
prompt/frontmatter claims unbacked by code or tests, and (3) a scheduled advisory re-grade routine
where Claude remains verifier-of-record and the grade is non-gating.

## Problem / Motivation

- 33 of 34 agent files hardcode a `model:` frontmatter field; 0 declare an `effort:` field
  (`grep -rn "^model:" plugins/*/agents/*.md | wc -l` → 33, `grep -rln "^effort:" plugins/*/agents/*.md | wc -l`
  → 0, verified 2026-07-03). This mirrors the grounding brief's citation of "25 agent-frontmatter
  model literals, 0 effort fields" (`docs/plans/2026-07-03-plugin-fleet-grounding-brief.md` §5,
  seed `{#team-execution-per-teammate-effort}`) and the pre-existing seed `S-37` ("review all
  agents defined in any plugin for improvement" — operator statement, cited against the same
  brief §1 finding).
- The repo's own CLAUDE.md step 6 requires plugin-behavior changes to update release surfaces
  (`plugin.json`, `marketplace.json`, `CHANGELOG.md`, drift-guard tests) in the same PR, but the
  grounding brief's recurring-pain synthesis names "release-surface drift persists despite
  CLAUDE.md step 6" as an open theme with "room for automation" (`docs/plans/2026-07-03-plugin-fleet-grounding-brief.md`
  §6, item 3).
- The repo already treats silent no-ops and unverified claims as its hottest recurring failure
  class: "provenance/status claims must be re-verified against current state" (4 learnings) and
  "silent no-ops in delegation & dead wiring" (5+ learnings) are both named recurring themes in the
  same brief (§6, items 1–2). An agent prompt that claims a capability, tool, or effort lever it
  does not actually exercise is the prompt-layer instance of exactly this failure class, and today
  nothing in the fleet catches it.
- Existing drift-guard precedent in this repo (`tests/test_agent_registration_drift.py`,
  `tests/test_operator_choice_drift.py`, the cross-module drift guard in
  `tests/test_outcome_spec.py:539`) establishes the pattern this issue extends to prompt-content
  claims, not just registration/schema drift.
- Constitutional constraint: external engines are never gatekeepers
  (`{#external-engines-never-gatekeepers}`, decision #283, `docs/engineering-journal/DECISIONS.md:1985`) —
  Claude is verifier-of-record for every gated decision; an external-engine second opinion may
  inform the scheduled re-grade but must not gate merges or agent removal on its own say-so.

## Definition of Done

- `docs/agent-prompt-audit.md` exists, contains one row per agent file (34 rows, one per
  `plugins/*/agents/*.md`), and each row is scored against a written rubric committed in the same
  document (rubric dimensions must include, at minimum: trigger-condition clarity, tool/capability
  claims vs. actual tool grants, model/effort-lever correctness, and consolidation/duplication risk
  against the fleet's 17→7 groom precedent `{#plugin-portfolio-groom-17-to-7}`).
- `plugin_contract_audit.py` (script path proposed at `scripts/plugin_contract_audit.py` or
  `plugins/saga/scripts/plugin_contract_audit.py` — `/plan` to determine final location) exists,
  scans agent/skill/command frontmatter and prose for claims about tools, models, effort levels,
  consensus behavior, or bridge/delegation wiring, and flags any claim it cannot match to
  executable code or a passing test.
- A scheduled advisory re-grade routine is defined (via the `schedule` skill's cron-based routine
  mechanism or an equivalent committed mechanism) that re-runs the rubric scoring and the contract
  auditor on a recurring cadence, is explicitly non-gating (does not block merges or CI), and names
  Claude as verifier-of-record for interpreting any re-grade delta — external-engine second opinion
  may be solicited but never gates.
- A coverage test asserts `docs/agent-prompt-audit.md` row count equals the live count of
  `plugins/*/agents/*.md` files, so the scorecard cannot silently drift stale as agents are
  added/removed.
- A seeded unbacked claim (a frontmatter or prose claim about a tool/model/effort/consensus
  behavior that does not exist in code) is planted in a fixture and the auditor is proven to flag
  it.
- A follow-up scheduled run against a changed fixture set emits a computed per-agent delta section
  (score change, new/resolved flags) versus the prior run's baseline.
- Release-surface checklist completed for every plugin whose `agents/*.md` frontmatter or prompt
  text is edited as part of remediating audit findings (see checklist below); no plugin's behavior
  changes without its `plugin.json`/`marketplace.json`/`CHANGELOG.md` telling the same story as the
  diff.

### Acceptance criteria
- [ ] **Coverage.** `docs/agent-prompt-audit.md` has exactly one scored row per file matched by
      `find plugins -path '*/agents/*.md'`. Check: a coverage test asserts
      `row_count == len(glob('plugins/*/agents/*.md'))`; run via
      `uv run pytest tests/test_agent_prompt_audit_coverage.py -v` → passes. *(Covers T11-F4-2.)*
- [ ] **Rubric is written and scored, not vibes.** The audit doc contains a named rubric section
      (dimensions listed above) applied consistently across all 34 rows — spot-check: every row has
      a non-empty score cell for every rubric dimension. *(Covers S-37 / T11-F4-2.)*
- [ ] **Auditor flags a seeded unbacked claim.** A fixture agent file is planted with a frontmatter
      or prose claim (e.g., "invokes `readonly-verifier` in worktree isolation") not backed by any
      matching code path or test. Check: `plugin_contract_audit.py` run against the fixture set
      emits a flag naming that specific claim; a test asserting this (e.g.
      `uv run pytest tests/test_plugin_contract_audit.py -k seeded_unbacked_claim`) passes.
      *(Covers X-codex-14.)*
- [ ] **CI output grouped by plugin.** `plugin_contract_audit.py` output (or its CI wrapper) groups
      flagged claims by plugin name, not as a flat undifferentiated list. Check: run
      `python3 <auditor path> --format=grouped` (or repo-chosen invocation) against the fixture set
      and confirm output sections are keyed per plugin. *(Covers X-codex-14.)*
- [ ] **Distinct from the mechanical frontmatter lint.** The contract auditor's scope is
      claim-reachability (does the prompt/frontmatter claim map to real code/tests), not
      frontmatter schema validity — confirmed by a short doc note distinguishing the two, so the
      two tools are not built as duplicates. *(Covers X-codex-14 non-goal note.)*
- [ ] **Scheduled advisory re-grade exists and is non-gating.** A committed scheduling artifact
      (cron routine definition, or equivalent) re-runs the rubric scoring and the auditor on a
      recurring cadence; the routine's definition explicitly states it does not block CI or merges.
      *(Covers T11-F5-2.)*
- [ ] **Baseline report committed.** `docs/agent-audit/REPORT.md` (or equivalent path —
      `/plan` to finalize) exists as the first committed baseline re-grade output. *(Covers
      T11-F5-2.)*
- [ ] **Follow-up run emits a computed delta.** Running the scheduled routine a second time against
      a changed fixture (one agent file edited, one added) produces a "delta" section in the report
      showing score/flag changes versus the prior baseline, computed (not hand-written). Check:
      `uv run pytest tests/test_agent_audit_delta.py -v` → passes. *(Covers T11-F5-2.)*
- [ ] **Verifier-of-record boundary respected.** If an external-engine second opinion is solicited
      as part of the scheduled re-grade, the routine's output shows Claude reconciling/adjudicating
      the external opinion rather than accepting it as final — consistent with
      `{#external-engines-never-gatekeepers}` (#283). Check: manual review of one re-grade run's
      output confirms an explicit reconciliation step/note.
- [ ] **Full suite, format, lint, types stay green.**
      Check: `uv run pytest && uv run ruff format --check . && uv run ruff check . && uv run mypy plugins/ scripts/ tests/ --ignore-missing-imports` → all pass.

### Out-of-scope / non-goals
**In scope:**
- A durable scorecard document (`docs/agent-prompt-audit.md`) and its written rubric.
- A contract-auditor script flagging prompt/frontmatter claims unbacked by code, grouped by
  plugin in its output.
- A scheduled, non-gating advisory re-grade routine plus its first committed baseline report and
  computed per-run delta.
- Coverage and seeded-flag tests proving both the scorecard and the auditor actually work.

**Out of scope / non-goals:**
- Fixing every flagged agent prompt in this issue. This issue delivers the audit mechanism and its
  first baseline pass; remediating individual agents' prompts is follow-on work tracked separately
  per flagged finding (each remediation PR triggers its own release-surface checklist).
- A mechanical frontmatter schema lint (field presence/type validation) — that is a separate,
  narrower mechanical issue; this issue's auditor is scoped to claim-reachability, not schema
  shape, and must not duplicate it.
- Making the re-grade gating. The routine is explicitly advisory; making it block CI/merges is a
  future decision requiring its own approval, not implied by this issue.
- Backfilling `effort:` fields onto all 33 agents that currently hardcode `model:` — that is
  `{#team-execution-per-teammate-effort}` (a separate seed) and is out of scope here; this issue
  only needs to *flag* the effort-field absence as a rubric/audit finding, not remediate it.
- Any external-engine participation beyond advisory second opinion — no external engine becomes a
  gatekeeper, executor, or git participant as part of this routine
  (`{#external-engines-never-gatekeepers}`, `{#external-engine-chaperone-dispatch}`).

## Grounding References

- **T11-F4-2** (primary, keeper) — "One durable agent-prompt scorecard doc scoring all 34 agents on
  a written quality rubric." Basis: theme T11 / frame F4, survivor set
  `docs/plans/plugin-fleet-ideation-2026-07-03/survivors/T11.json`. `dod_sketch`: merged
  `docs/agent-prompt-audit.md` scoring every agent (one row each) + rubric section; verified by a
  coverage test asserting row-count == agent-file count.
- **S-37** (dedup-merged into T11-F4-2) — "Review all agents defined in any plugin for
  improvement." Basis (`basis_type: direct`): operator statement "review all agents defined in any
  plugin for improvement"; grounded against brief §1 finding "25 agent-frontmatter model literals,
  0 effort fields" (`docs/plans/2026-07-03-plugin-fleet-grounding-brief.md` §1/§5). Per the
  ideation dedup-map, keeper T11-F4-2 subsumes this seed.
- **T11-F5-2** (facet) — "Airworthiness-directive cycle: scheduled advisory LLM grade of every
  agent prompt." Basis: theme T11 / frame F5, same survivor set. `dod_sketch`: merged scheduled
  advisory routine + rubric doc + first committed `docs/agent-audit/REPORT.md` baseline (Claude
  verifier-of-record, non-gating); verified a follow-up run emits a computed per-agent delta
  section.
- **X-codex-14** (facet) — "Prompt Contract Auditor." Basis: external-frame idea, theme T11,
  `tier_guess: sonnet/high`. `dod_sketch`: merged `plugin_contract_audit.py` flagging
  prompt/frontmatter/command claims about tools/models/efforts/consensus/bridge-wiring not backed
  by executable code or tests + CI output grouped by plugin; verified it flags a seeded unbacked
  claim. Explicitly distinct from a frontmatter lint: audits claim↔code reachability, not schema
  shape.
- **Binding decisions this issue must respect:**
  - `{#external-engines-never-gatekeepers}` (#283, `docs/engineering-journal/DECISIONS.md:1985`) —
    Claude is verifier-of-record for every gated decision; external engines are generator/advisory
    only, never gatekeepers.
  - `{#external-engine-chaperone-dispatch}` (#318) — any external-engine use in the scheduled
    re-grade must be chaperone dispatch (offload/second-opinion), never a second executor or git
    participant.
  - `{#readonly-verifier-fallback-ladder-325}` — any verify/review-class agent spawn this issue's
    tooling triggers (e.g. the auditor invoking a review pass) must use the read-only fallback
    ladder per `plugins/saga/references/sandbox-spawn-sites.md`, not an unsandboxed spawn.
  - `{#plugin-portfolio-groom-17-to-7}` — new-plugin ideas carry a consolidation burden of proof;
    this issue must not spawn a new plugin, it extends existing docs/tooling within the current
    fleet.
- **Ideation source:** `docs/plans/2026-07-03-plugin-fleet-grounding-brief.md` (see §1 decision
  table, §5 pre-existing seeds, §6 recurring-pain themes) and
  `docs/plans/plugin-fleet-ideation-2026-07-03/survivors/T11.json` /
  `docs/plans/plugin-fleet-ideation-2026-07-03/survivors/seeds.json` for the four absorbed entries
  above.

## Recommended Executor Profile

- **Model:** Opus
- **Effort:** High
- **Backend:** Inline
- **External LLM posture:** Second-opinion (advisory only, chaperone-dispatched per
  `{#external-engine-chaperone-dispatch}`; Claude remains verifier-of-record per
  `{#external-engines-never-gatekeepers}`).
- **Justification (required — above Sonnet):** This is adversarial prompt-quality judgment applied
  across 34 heterogeneous agent files spanning 8 plugins, requiring consistent rubric application,
  nuanced claim-vs-code reachability analysis (distinguishing a legitimate abstraction from an
  unbacked claim requires judgment, not pattern-matching), and reconciliation of an explicitly
  in-scope external second opinion. The scheduled re-grade's delta computation and the auditor's
  false-positive/false-negative tradeoffs also warrant high effort. Mechanical sub-tasks (the
  coverage test, the fixture scaffolding) may be delegated to Sonnet/Haiku sub-work once the rubric
  and auditor design are settled, but the pilot judgment call belongs at Opus/high.

## Release-Surface Checklist

Required only for plugin(s) whose behavior, agent files, or commands change as part of this work
(e.g., if the contract auditor or scheduled routine ships as a `saga` or `team-execution` skill
addition, or if any `plugins/*/agents/*.md` file is edited to remediate a flagged finding):

- [ ] `plugins/<plugin>/.claude-plugin/plugin.json` version bumped and description updated if
      behavior changed.
- [ ] `.claude-plugin/marketplace.json` entry updated to match.
- [ ] `plugins/<plugin>/CHANGELOG.md` entry added describing the audit tooling or remediated
      agent(s).
- [ ] Version/metadata drift-guard tests (e.g. `tests/test_agent_registration_drift.py` or a new
      equivalent for this tooling) updated or added and passing.
- [ ] Confirmed installed-plugin metadata tells the same story as the diff before marking PR-ready
      (per CLAUDE.md step 6).

### Verification
```bash
# Coverage: scorecard row count matches live agent-file count
uv run pytest tests/test_agent_prompt_audit_coverage.py -v

# Auditor flags a seeded unbacked claim
uv run pytest tests/test_plugin_contract_audit.py -k seeded_unbacked_claim -v

# Scheduled re-grade produces a computed delta on a second run
uv run pytest tests/test_agent_audit_delta.py -v

# Full repo gate (CI parity)
uv run pytest && uv run ruff format --check . && uv run ruff check . && uv run mypy plugins/ scripts/ tests/ --ignore-missing-imports
```

Expected: all green; coverage test asserts exact row/file-count match; auditor test confirms the
seeded claim is named in its flagged output; delta test confirms a non-empty, computed
score/flag-change section on the second scheduled run.

### Handoff maturity
requirements-ready

### Suggested next action
Use `/plan <issue>` to create an implementation plan (rubric dimensions, auditor's claim-extraction
approach, and scheduling mechanism are HOW decisions left to `/plan`).

### Source context
- Source: `/private/tmp/claude-501/-Users-jefcox-workspace-infiquetra-infiquetra-claude-plugins/c23d3bf9-9081-4727-8e0d-140ebc73f63f/scratchpad/ideation/issue-map/issue-map-final.json` (slug `pf-agent-prompt-audit`)
- Source type: ideation issue-map (fan-out from `saga:ideate`)
- Source title: "Agent-prompt quality: scored rubric over all agents, prompt-contract auditor, scheduled advisory re-grade"

### Intent

The fleet has 34 agent files across 8 plugins (`find plugins -path '*/agents/*.md' | wc -l` → 34, verified 2026-07-03) with no durable, scored record of prompt quality, no mechanism that flags a prompt or frontmatter claim ("uses tool X", "runs at effort Y") that isn't backed by executable code, and no recurring re-grade as agents drift. This issue is the judgment-shaped counterpart to a mechanical frontmatter lint (tracked separately): it produces (1) a durable scorecard document scoring every agent against a written rubric, (2) a `plugin_contract_audit.py` script that flags prompt/frontmatter claims unbacked by code or tests, and (3) a scheduled advisory re-grade routine where Claude remains verifier-of-record and the grade is non-gating.

### Context library links

_none_

### Files expected to change

- `docs/plans/2026-07-03-plugin-fleet-grounding-brief.md`
- `tests/test_agent_registration_drift.py`
- `tests/test_operator_choice_drift.py`
- `docs/agent-prompt-audit.md`
- `scripts/plugin_contract_audit.py`
- `plugins/saga/scripts/plugin_contract_audit.py`
- `docs/agent-audit/REPORT.md`
- `docs/plans/plugin-fleet-ideation-2026-07-03/survivors/T11.json`

### Tests to add or update

- `tests/test_agent_audit_delta.py`
- `tests/test_agent_prompt_audit_coverage.py`
- `tests/test_agent_registration_drift.py`
- `tests/test_operator_choice_drift.py`
- `tests/test_outcome_spec.py`
- `tests/test_plugin_contract_audit.py`

### Objective

"Gate fleet integrity (agent files, prompts, release surfaces)"
