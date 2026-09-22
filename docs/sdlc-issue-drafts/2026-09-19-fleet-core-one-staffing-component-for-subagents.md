---
title: Fleet-core: one staffing component for subagents, workflow units, and herdr roles
repo: infiquetra-claude-plugins
type: capability
team: asgard
project: operations
status: Ready for Planning
stage: Shaping
labels: capability, needs-plan
risk: medium
mode: execute
handoff_maturity: requirements-ready
---

# Fleet-core: one staffing component for subagents, workflow units, and herdr roles

### Objective

One data file and one resolver in fleet-core that answer "role or work shape, and for review the lens, → vendor, model, effort," merging the work-shape tier policy and model palette (fleet-core), the committed per-repository overlay (saga `tier_defaults.py`), the capability ratings per model family and trust tiers (saga `references/engine-registry.yaml`), and the sdlc's executor-verification ledger. The palette covers every vendor the roster helper can launch, not only Claude models.

### Intent

Choosing a subagent's model, a workflow unit's tier, and a herdr role's vendor and model are one decision whose inputs sit in four places today. The global instructions state the rule (classify every launch; least costly setting that reliably completes; judgment → Opus; the concurrency cap); this component is the rule's executable defaults so no session re-derives them. Decided 2026-09-19 (SR R29; `/tier` and `/engines` are removed in A13 and their knowledge lands here).

### Out-of-scope / non-goals

- No dispatch, bridge, calibration, or promotion machinery; the component answers a question and logs the answer.
- No automatic promotion of a suggestion to a choice; the typed-judgment input (B2) is advisory.
- No change to the global instruction files.

### Files expected to change

- `plugins/fleet-core/scripts/fleet_commons/staffing.py` (new resolver)
- `plugins/fleet-core/scripts/fleet_commons/staffing.json` (new data; absorbs `tier_policy.json`, `models.json`, the engine-registry ratings)
- `plugins/fleet-core/references/staffing.md` (new; supersedes `tier-palette.md` and `effort-convention.md`)
- `plugins/saga/scripts/tier_defaults.py` (moves or is replaced), `plugins/saga/references/engine-registry.yaml` (ratings migrate, file removed in A13)
- `plugins/fleet-core/.claude-plugin/plugin.json`, `.claude-plugin/marketplace.json`, `plugins/fleet-core/CHANGELOG.md`

### Tests to add or update

- `tests/test_staffing.py`: resolver returns the policy default per work shape; the repository overlay wins over the default; an off-palette model or an unsupported model-effort pair fails loud; a lens with no qualified executor returns the catalogue's documented-policy marker; every vendor in agent-launcher's kind list has a palette entry.
- Update `tests/test_tier_vocab_single_source.py` to point at the new single source.

### Context library links

- coding_standards: _none_

General references:
- SR R29 and section 9; TR R5; SDLC/config/executor-verifications.json; `plugins/fleet-core/references/tier-palette.md`

### Acceptance criteria

- [ ] `uv run python plugins/fleet-core/scripts/fleet_commons/staffing.py resolve --shape judgment` prints `opus/high` and `--shape read-only-survey` prints `sonnet/low`, matching the current policy.
- [ ] `uv run python plugins/fleet-core/scripts/fleet_commons/staffing.py resolve --role lens-reviewer --lens security` prints a vendor, model, and effort and the qualification status from the ledger.
- [ ] `uv run python plugins/fleet-core/scripts/fleet_commons/staffing.py explain --role functional-tester` lists the candidates in rating order with their ratings.
- [ ] `uv run pytest tests/test_staffing.py tests/test_tier_vocab_single_source.py -q` passes.

### Verification

```bash
uv run python plugins/fleet-core/scripts/fleet_commons/staffing.py resolve --shape judgment
uv run python plugins/fleet-core/scripts/fleet_commons/staffing.py explain --role lens-reviewer --lens correctness
uv run pytest tests/test_staffing.py -q
```

### Risk

medium

every spawn will read it, so a wrong default mis-tiers work; the guard is the single-source test and the fail-loud rule on off-palette values.

### Handoff maturity
requirements-ready

### Recommended Tier Band
opus/high

## Created Issue

- URL: https://github.com/infiquetra/infiquetra-claude-plugins/issues/1021
- Number: 1021
- Created at: 2026-09-19T14:42:48.254956+00:00

