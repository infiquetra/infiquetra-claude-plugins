---
title: "capability: /tier mid-run lever — session ceiling plus re-emit from the canonical spec, no restart"
repo: infiquetra-claude-plugins
type: capability
team: campps
project: operations
status: Idea
labels: capability, hermes-task, needs-plan
risk: medium
handoff_maturity: requirements-ready
tier: structural
wave: wave-1
objective: Make tier+effort a first-class priced resolvable lever
---

# capability: /tier mid-run lever — session ceiling plus re-emit from the canonical spec, no restart

### Objective

Make tier+effort a first-class priced resolvable lever.

### Intent

Give the operator a live, mid-run lever over model/effort tier that never requires aborting and
re-planning a run. Today the only tier lever is authored once, up front, in `/plan`'s per-unit tier
table (`plugins/saga/skills/plan/SKILL.md:295-296`) and locked into the `ExecutionSpec` JSON at emit
time (`plugins/saga/skills/plan/SKILL.md:291-293`: "the spec JSON — not the prose plan — is the single
source of truth"). Session mining across 3 repos recorded operators pausing mid-run to manually
negotiate a model change with no first-class command for it (grounding brief pattern 6,
`docs/plans/2026-07-03-plugin-fleet-grounding-brief.md`: "Ad hoc tier reasoning every time... manual
per-unit tier tables; operator asking mid-run model-change pauses (3 repos)"). Every agent frontmatter
across all 8 plugins hardcodes `model:` with zero `effort:` fields and no dispatch-time override lever
anywhere except saga's readonly-verifier per-call pattern (grounding brief §1).

This capability adds a `/tier` lever with two cooperating mechanisms so the operator sets intent once
and the run self-enforces it, instead of the recurring interrupt-and-negotiate step:

1. **Session ceiling (ratchet-down clamp).** `/tier` writes a run-scoped cap (e.g. "nothing above
   sonnet/medium this run") to a session-local override file. The tier resolver honors it on every
   subsequent spawn, clamping any resolved unit above the ceiling down to it, with a logged downgrade
   and no re-prompt.
2. **Mid-run re-emit (targeted edit).** At a saga tick / segment boundary, `/tier` edits the tier of
   not-yet-run units in the canonical `ExecutionSpec` JSON, re-validates via
   `python3 plugins/saga/scripts/execution_spec.py validate`, and re-emits the downstream workflow via
   `execution_spec.py emit` — reusing the existing re-emit seam
   (`plugins/saga/skills/plan/SKILL.md:291-293`, Step 4/Step 5) instead of building new machinery.
   Already-run units are left untouched; a mid-run escalation is gated by the spend-delta classifier
   (deciding ask-vs-silent) rather than this capability re-implementing that asymmetry.

For team-execution's segment-based backend, the same override file is read at the R11 segment-shed
boundary (`plugins/team-execution/skills/team-execution/SKILL.md:303` Step B1, `:311` "Context Shedding
(R11): Shed a resident worker at its segment boundary") so a tier change between segments changes only
the *next* segment's worker spec, not the one already dispatched.

### Problem Frame

- The fleet has exactly one operator-facing model/effort lever today: the `/plan`-authored, one-time
  tier table (`plugins/saga/skills/plan/SKILL.md:295-296`), backed by the closed vocabularies
  `MODELS = ("fable", "opus", "sonnet", "haiku")` / `EFFORTS = ("low", "medium", "high", "xhigh")`
  (`plugins/saga/scripts/execution_spec.py:52-53`).
- There is no mid-run lever: changing tier today means aborting the run and re-planning.
- Session mining recorded this exact gap as a recurring, cross-repo pain (grounding brief §7, pattern
  6, 3 repos) — the interrupt is a manual pause-and-ask with no persisted, resolver-honored mechanism.
- The re-emit seam this capability rides already exists and is load-bearing elsewhere: the
  `ExecutionSpec` JSON is documented as the canonical artifact `/work` re-emits from
  (`plugins/saga/skills/plan/SKILL.md:291-293`), and `MODELS`/`EFFORTS` ordering is already used for
  upgrade-only merge arithmetic in `segment_units()` (`plugins/saga/scripts/execution_spec.py:52-58`:
  "ORDERING IS LOAD-BEARING: segment_units() merges tiers upgrade-only via min(MODELS.index) /
  max(EFFORTS.index)").
- Binding decision engaged: `{#operator-choice-framework}` — "Operator-choice = doc-only, CLI-driven
  `/work`" — `/tier` stays a CLI command writing a config file the resolver reads, not a runtime
  injection mechanism, so it does not require revisiting that decision.

### Actors

- **Operator** — invokes `/tier` to set a session ceiling or to patch not-yet-run units' tiers mid-run.
- **Tier resolver** (`execution_spec.py` / segment-boundary reader in team-execution) — reads the
  session-override file and the patched spec; clamps or applies as appropriate.
- **Spend-delta classifier** (existing/adjacent primitive — silent-vs-ask asymmetry) — decides whether
  a mid-run tier change requires operator confirmation (escalation) or proceeds silently (cheapen or
  lateral). This capability calls into that classifier; it does not re-implement the asymmetric rule.

### Requirements

R1. `/tier <ceiling>` (e.g. `/tier sonnet/medium`) writes a session-local override file recording a
    run-scoped tier ceiling.

R2. The tier resolver reads the session-override file on every subsequent unit spawn and clamps any
    resolved `{model, effort}` above the ceiling down to it, using the existing ordered-ladder
    comparison (`MODELS`/`EFFORTS` index arithmetic, `execution_spec.py:52-58`) — never silently
    raising a unit's tier.

R3. Every clamp is logged (unit id, original tier, clamped tier) and does not re-prompt the operator.

R4. `/tier <unit-selector> <new-tier>` (mid-run patch form) edits the tier of the named not-yet-run
    unit(s) in the canonical `ExecutionSpec` JSON, leaving already-run units' recorded tiers untouched.

R5. After a patch, `/tier` re-runs `execution_spec.py validate` on the patched spec (hard block on
    failure — do not proceed on an invalid spec) and, on success, re-runs `execution_spec.py emit` to
    regenerate the downstream `.workflow.js`.

R6. A mid-run tier *escalation* (up-ladder per the existing ordering) is routed through the
    spend-delta classifier and requires explicit operator confirmation before the patched spec is
    validated/emitted; a cheapen-or-lateral move proceeds without a prompt.

R7. For the team-execution segment-based backend, the same session-override file is read at the R11
    segment-shed boundary (`plugins/team-execution/skills/team-execution/SKILL.md:303-311`); a tier
    change written between segments affects only the next segment's worker spec, never the
    already-dispatched one.

### Out-of-scope / non-goals
- In scope: `/tier` command (doc + invocation), session-override file schema, resolver clamp logic in
  `execution_spec.py`, mid-run spec-patch + re-validate + re-emit path, team-execution R11
  segment-boundary override read, tests for all of the above.
- Non-goal: building a new spend-delta classifier from scratch if a shared one already exists or is
  landing in a companion capability — this issue calls into it, and if it does not yet exist, this
  issue implements the minimal ask/silent gate needed for R6 only (an up-ladder move always asks; it
  does not attempt to generalize spend comparison across `fable`/`xhigh` cost weighting).
- Non-goal: changing team-execution's existing proceed-best-available cap or any other unrelated
  segment-boundary behavior.
- Non-goal: a runtime-injection mid-run override mechanism that bypasses the CLI-driven,
  spec-re-emit seam — `{#operator-choice-framework}` stays doc-only/CLI-driven.
- Non-goal: retroactively changing already-run units' recorded tier in the spec or saga tick history.

### Grounding References

- `T12-F2-7` (primary) — session ceiling + resolver clamp. Basis: grounding brief session-mining
  pattern 6 (`docs/plans/2026-07-03-plugin-fleet-grounding-brief.md` §7, line ~133): "operator asking
  mid-run model-change pauses" (recurring pain, 3 repos). Engages `{#operator-choice-framework}`
  (revisit-when it stops being doc-only/CLI-driven) — `/tier` stays a CLI command writing a
  resolver-read config file.
- `T12-F4-6` (facet) — mid-run re-emit from the canonical spec instead of restarting. Basis:
  `plugins/saga/skills/plan/SKILL.md:291-293` ("author a structured ExecutionSpec... the spec JSON —
  not the prose plan — is the single source of truth (KTD1)... the canonical artifact `/work`
  re-emits from") plus the same grounding-brief pattern 6. Gates escalation via the spend-delta
  classifier (`T12-F4-3`, referenced not absorbed) so every backend that already re-emits from the
  spec inherits mid-run tier control with no per-backend work.
- `T6-F2-3` (dedup-merged) — segment-boundary tier re-derivation for team-execution. Reconstructed
  from its `basis`/`dod_sketch` (its idea body was a thin seed): an operator-writable tier-override
  read at the R11 segment-shed boundary
  (`plugins/team-execution/skills/team-execution/SKILL.md:303` Step B1, `:311` Context Shedding R11),
  applicable to `/work` unit boundaries too, with a documented override-file contract; a test writes
  an override between segments and asserts only the *next* segment's worker spec reflects the new
  tier.
- Binding decisions this builds on: `{#operator-choice-framework}` (Operator-choice = doc-only,
  CLI-driven `/work`); `MODELS`/`EFFORTS` ordering as the load-bearing comparison primitive
  (`plugins/saga/scripts/execution_spec.py:52-58`).

### Definition of Done

Merged PR adding:
- a `/tier` command (doc under `plugins/saga/commands/` or `plugins/saga/skills/` per existing saga
  command conventions — match `plugins/saga/commands/*.md` house pattern),
- a session-override file schema (documented, e.g. JSON with `ceiling: {model, effort}` and/or
  `unit_overrides: {<unit_id>: {model, effort}}`),
- resolver clamp logic wired into `plugins/saga/scripts/execution_spec.py`,
- the mid-run patch → validate → emit path,
- the team-execution R11 segment-boundary override read,
- and tests covering the clamp, the re-emit, and the segment-boundary isolation.

Verified by:
- a test that sets a sonnet/medium ceiling and asserts a subsequently-resolved opus/high unit is
  clamped to the ceiling with a logged downgrade and no prompt (R1-R3);
- a test that a mid-run tier change on a pending unit re-emits a valid workflow and leaves
  already-run units' recorded tiers untouched (R4-R6);
- a test that writes an override between team-execution segments and asserts only the *next*
  segment's worker spec reflects the new tier (R7).

### Acceptance criteria
- [ ] `/tier <ceiling>` writes a session-local override file recording the ceiling. Check:
  `uv run pytest tests/test_execution_spec.py -k tier_ceiling_write` → passes.
- [ ] Sonnet/medium ceiling clamps a later-resolved opus/high unit, with a logged downgrade and no
  prompt. Check: `uv run pytest tests/test_execution_spec.py -k tier_ceiling_clamp` → passes.
- [ ] Resolver never raises a unit's tier via the ceiling mechanism (clamp is downward-only). Check:
  `uv run pytest tests/test_execution_spec.py -k tier_ceiling_never_escalates` → passes.
- [ ] Mid-run `/tier <unit> <new-tier>` patches only the named not-yet-run unit(s) in the spec JSON.
  Check: `uv run pytest tests/test_execution_spec.py -k tier_patch_unrun_only` → passes.
- [ ] Patched spec is re-validated (hard block on failure) before re-emit. Check:
  `uv run pytest tests/test_execution_spec.py -k tier_patch_validate_gate` → passes.
- [ ] A mid-run change re-emits a valid `.workflow.js` and leaves already-run units untouched. Check:
  `uv run pytest tests/test_execution_spec.py -k tier_patch_reemit` → passes.
- [ ] A mid-run up-ladder (escalating) tier change requires explicit operator confirmation before
  emit; a cheapen-or-lateral change proceeds silently. Check:
  `uv run pytest tests/test_execution_spec.py -k tier_patch_spend_delta_gate` → passes.
- [ ] team-execution R11 segment-boundary override: writing an override between segments changes
  only the next segment's worker spec, not the already-dispatched one. Check:
  `uv run pytest tests/test_team_execution.py -k segment_boundary_tier_override` → passes.
- [ ] Full suite, format, lint, types stay green. Check:
  `uv run pytest && uv run ruff format --check . && uv run ruff check . && uv run mypy plugins/ scripts/ tests/ --ignore-missing-imports` → all pass.

### Files expected to change

Indicative only — exact set is `/plan`'s to determine.

- `plugins/saga/scripts/execution_spec.py` — session-override read, clamp logic, mid-run patch helper.
- `plugins/saga/commands/tier.md` (new) — `/tier` command doc.
- `plugins/saga/skills/plan/SKILL.md` — document the mid-run lever and its relationship to the
  authored tier table.
- `plugins/team-execution/skills/team-execution/SKILL.md` — document the R11 segment-boundary
  override read.
- `tests/test_execution_spec.py` — clamp, patch, validate-gate, re-emit, spend-delta-gate tests.
- `tests/test_team_execution.py` — segment-boundary override isolation test.
- `plugins/saga/.claude-plugin/plugin.json`, `.claude-plugin/marketplace.json`,
  `plugins/saga/CHANGELOG.md` — release-surface bump (new command, new schema, new resolver behavior).
- `plugins/team-execution/.claude-plugin/plugin.json`, `plugins/team-execution/CHANGELOG.md` — release
  surface bump for the segment-boundary read (behavior/doc change).

### Out-of-scope / non-goals

- Building the spend-delta classifier as a general-purpose fleet-wide primitive (see Scope &
  Non-Goals above) — this issue implements only the minimal ask-gate needed for R6.
- Changing team-execution's existing proceed-best-available cap.
- A runtime-injection override mechanism outside the CLI-driven, spec-re-emit seam.
- Retroactive edits to already-run units' recorded tier history.

### Tests to add or update

- `tests/test_execution_spec.py`: `tier_ceiling_write`, `tier_ceiling_clamp`,
  `tier_ceiling_never_escalates`, `tier_patch_unrun_only`, `tier_patch_validate_gate`,
  `tier_patch_reemit`, `tier_patch_spend_delta_gate`.
- `tests/test_team_execution.py`: `segment_boundary_tier_override`.

### Verification

```bash
# Unit + integration tests for the new lever
uv run pytest tests/test_execution_spec.py -k tier -v
uv run pytest tests/test_team_execution.py -k segment_boundary_tier_override -v

# Full repo gate (CI parity)
uv run pytest
uv run ruff format --check .
uv run ruff check .
uv run mypy plugins/ scripts/ tests/ --ignore-missing-imports
```

Expected: all green; the clamp test shows a logged downgrade and no operator prompt; the mid-run
patch test shows already-run units untouched in the re-emitted spec; the segment-boundary test shows
only the next segment picking up the new tier.

### Release-surface checklist

- [ ] `plugins/saga/.claude-plugin/plugin.json` version bumped for the new `/tier` command + resolver
  behavior change.
- [ ] `plugins/team-execution/.claude-plugin/plugin.json` version bumped for the R11 segment-boundary
  override read.
- [ ] `.claude-plugin/marketplace.json` entries for `saga` and `team-execution` updated to match.
- [ ] `plugins/saga/CHANGELOG.md` and `plugins/team-execution/CHANGELOG.md` entries added.
- [ ] Any version/metadata drift-guard tests updated to reflect the new command and schema.

### Recommended executor profile

- **Model:** sonnet
- **Effort:** medium
- **Backend:** inline
- **External LLM posture:** none
- **Justification:** Mechanical, deterministic work — a new CLI command, a config-file schema, clamp
  arithmetic reusing an already-established ordered-ladder comparison, and a spec-patch/re-validate/
  re-emit path riding an existing seam. No architectural judgment call or adversarial review is
  needed; sonnet/medium matches the fleet's own work-shape heuristic
  (`plugins/saga/skills/plan/SKILL.md:296-300`: "Mechanical, deterministic, scripted transforms,
  scaffolding → sonnet / medium").

### Handoff maturity

requirements-ready

### Suggested next action

Use `/plan <issue>` to create the implementation plan.

### Source context

- Source: `docs/plans/plugin-fleet-ideation-2026-07-03/survivors/` (ideas `T12-F2-7`, `T12-F4-6`,
  `T6-F2-3`) and `docs/plans/2026-07-03-plugin-fleet-grounding-brief.md`.
- Source type: ideation survivor consolidation (issue-map)
- Source title: `/tier` mid-run lever: session ceiling plus re-emit from the canonical spec, no restart

### Context library links

_none_

## Created Issue

- URL: https://github.com/infiquetra/infiquetra-claude-plugins/issues/365
- Number: 365
- Created at: 2026-07-04T07:51:01.518092+00:00

