---
title: "enhancement: spend observability on the ledger — estimate-reconcile, itemized receipts, spend retro, tier-efficacy and shadow-audit evidence"
repo: infiquetra-claude-plugins
type: enhancement
team: campps
project: operations
status: Idea
labels: enhancement, hermes-task, needs-plan
risk: medium
handoff_maturity: requirements-ready
tier: structural
objective: "Build the fleet telemetry and ledger substrate"
wave: wave-2
---

# enhancement: spend observability on the ledger — estimate-reconcile, itemized receipts, spend retro, tier-efficacy and shadow-audit evidence

### Intent

Give the fleet a read side for spend. `/outcome`'s leaf-produced cost ledger
(`plugins/saga/scripts/outcome_costs.py`) already records what a run actually cost, but nothing
today (a) previews spend before tiers lock, (b) contrasts what was spent against what the declared
cheaper fallback would have cost, (c) aggregates that history into a per-repo trend anyone can read,
(d) turns that history into a gated tier-default adjustment proposal, or (e) produces ground truth
for whether a tier choice was actually necessary. The mined pain is a belief, not a measurement:
"xhigh-Opus on everything is wasteful" is asserted across repos but never checked against the
ledger the fleet already writes (`docs/plans/2026-07-03-plugin-fleet-grounding-brief.md` section 7,
recurring pattern 6: "Ad hoc tier reasoning every time — xhigh-Opus on everything is wasteful;
manual per-unit tier tables; operator asking for mid-run model-change pauses (3 repos)").

This issue builds the observability and reporting layer over the existing ledger: a pre-run
estimate + post-run reconcile, an itemized receipt with a cheap-fallback counterfactual, a
cross-run spend retro, an evidence-gated `/retro` tier-efficacy pass, and a sampled shadow-audit
that replays completed units one tier down to produce empirical per-stage tier-sufficiency data.
Every piece is strictly a reader of the leaf-produced ledger or an appender to it — none of them
writes a status field, and none of them auto-applies a tier change. This mirrors the binding
`/outcome` campaign decision that the cost ledger is a leaf-produced fact, derived-on-read, never
committed by the orchestrator (`docs/plans/2026-07-03-plugin-fleet-grounding-brief.md` section 2).

Full context: `docs/plans/2026-07-03-plugin-fleet-grounding-brief.md` sections 1–2, 5–7;
`docs/plans/plugin-fleet-ideation-2026-07-03/survivors/T12.json` (ideas `T12-F4-5`, `T12-F5-8`,
`T12-F2-8`, `T12-F1-8`, `T12-F5-7`); `docs/plans/plugin-fleet-ideation-2026-07-03/survivors/T3.json`
(idea `H-F6-1`).

### Problem / motivation

- **No pre-run cost estimate, no post-run reconciliation.** `/plan`'s tier table
  (`plugins/saga/skills/plan/SKILL.md:296-307`) presents the operator a `{model, effort}` table to
  confirm or override with no cost dimension at all — "present full tier table ... ask operator to
  confirm or override before proceeding. Do not lock tiers silently" carries no cost column. After
  the run, `plugins/saga/scripts/outcome_costs.py` (`rollup()`, line 153) already computes a
  leaf-produced cost rollup, but nothing reads it back against what was estimated before the run —
  the operator confirms tiers blind and never sees whether the run cost what the table implied.
  (`T12-F4-5`)
- **No itemized receipt, no cheap-fallback counterfactual.** The operator sees an absolute bill
  (the rollup total) with nothing to compare it against. There is no rendering of "this run cost
  X; the all-cheap-fallback plan would have cost ~0.4X, giving up `<named tradeoffs>`" — the single
  most direct pressure against over-tiering is missing, so waste is never made visible in
  retrospect. (`T12-F5-8`)
- **"xhigh-Opus is wasteful" is an unmeasured claim.** The user's own global validation-discipline
  rule ("Do not state anything about system state, behavior, performance, or data without verifying
  it from a direct, current source") is being violated by the fleet's own mined complaint: the
  claim recurs across repos with no aggregation of the leaf-produced ledger that could confirm or
  falsify it. Nothing rolls per-repo tier-mix and premium-spend-vs-outcome into a readable summary.
  (`T12-F2-8`)
- **Tier defaults never get evidence-tuned.** Even once ledger history exists, nothing closes the
  loop back into `.saga/tier-defaults.json`-style config: no mechanism mines completed runs' cost
  vs. outcome (findings surfaced, review verdicts, rework) to propose "the last N mechanical units
  ran opus/high at Nx baseline cost with zero findings a cheaper rung wouldn't have gotten —
  downgrade the default." Recommendations stay frozen at authoring-time quality forever with no
  feedback signal. (`T12-F1-8`)
- **Tier tables carry a flat, un-evidenced recommendation regardless of stakes or remaining
  budget.** The `/plan` heuristic (`plugins/saga/skills/plan/SKILL.md:298-304`) looks up
  work-shape → tier from a fixed table; it has no notion of payoff-at-stake (blast radius,
  irreversibility, whether the unit feeds a gated decision) or of how much of the run's spend
  envelope remains, so a low-stakes unit late in a depleted budget gets the same recommendation
  strength as a high-stakes unit early in a fresh one. (`T12-F5-7`)
- **No sampled ground truth for whether a tier choice was actually necessary.** Every tier-value
  claim in the fleet today is reasoning re-derived each session, never measured. There is no
  mechanism that periodically replays a *completed* unit one rung down the ordered escalation
  ladder (`MODELS`/`EFFORTS`, `plugins/saga/scripts/execution_spec.py:52-53` — "ORDERING IS
  LOAD-BEARING") and diffs the outputs to produce sufficient/insufficient evidence. Because
  sampling replay is itself spend-increasing, the fleet's own asymmetric-approval intake rule
  (spend-increasing choices always require explicit operator yes; cache-first is the only silent
  default) applies to it and is currently unenforceable because the mechanism doesn't exist.
  (`H-F6-1`)

### Key decisions

These constraints from the ideation/grounding pass bound the requirements below; violating any one
crosses a binding decision this repo has already made.

- **Everything here is a reader (or a leaf-produced appender), nothing here is a status writer.**
  The `/outcome` campaign binding decision (`docs/plans/2026-07-03-plugin-fleet-grounding-brief.md`
  section 2: "cost ledger = leaf-produced fact ... Derived-on-read status, never committed status
  fields") means the pre-run estimate, the receipt, the spend retro, and the shadow-audit report all
  derive their numbers by reading `outcome_costs.py`'s existing ledger/rollup at render time — none
  of them writes back a computed value as if it were ledger fact.
- **Tier-default and tier-policy adjustments are gated diffs, never auto-applied.** Both the
  `/retro` tier-efficacy pass (`T12-F1-8`) and the shadow-audit report (`H-F6-1`) may only *propose*
  a change (e.g. a diff against `.saga/tier-defaults.json`); nothing in this issue writes that file
  autonomously.
- **Shadow-audit sampling is spend-increasing and therefore subject to the fleet's asymmetric-
  approval rule.** Per intake tension 1 (cited in `H-F6-1`'s basis), it must default off in attended
  mode without an explicit operator yes, and must be budget-capped in unattended mode. It is never a
  silent default.
- **No dollar-precision, ordinal cost weights only.** Estimates and counterfactuals are relative
  (index-weighted against the ordered `MODELS`/`EFFORTS` ladder), not dollar amounts — avoiding false
  precision the fleet cannot actually back with real pricing data.
- **`{#tier-vocab-ordering}`** — tier tuples are ordered escalation ladders, not just closed sets;
  "one rung cheaper/dearer" is well-defined only because of this ordering
  (`plugins/saga/scripts/execution_spec.py:52-53`). Every counterfactual, estimate, and shadow-audit
  "one tier down" computation in this issue depends on that ordering and must not silently assume a
  different one.

## Definition of Done

A merged PR to `infiquetra-claude-plugins` that adds, under `plugins/saga/scripts/`:

1. `spend_estimate.py` (or equivalent module) — a pre-run relative-cost estimator that renders an
   estimate column alongside `/plan`'s tier table (`plugins/saga/skills/plan/SKILL.md` §5.2a) and a
   post-run reconcile step that reads `outcome_costs.py`'s rollup and prints `estimate / actual /
   delta` per unit and in total. Writes nothing back to the ledger or to any status field.
2. `spend_receipt.py` — a per-unit/per-tier itemized receipt renderer invoked at run end that also
   computes a cheap-fallback counterfactual total (sum of each unit's declared fallback-tier cost
   weight) and names the tradeoff given up for each unit that ran above its fallback tier.
3. `spend_retro.py` — a cross-run aggregator that reads leaf-produced cost ledgers across completed
   sagas in a repo and emits a `docs/engineering-journal/` spend-summary table (tier-mix, premium
   spend share, spend-vs-outcome) so the "xhigh-Opus is wasteful" claim becomes checkable against
   real numbers.
4. A `/retro` tier-efficacy pass (edit to `plugins/saga/skills/retro/SKILL.md` plus a supporting
   script) that mines completed runs' recorded cost-vs-outcome (findings surfaced, review verdicts,
   rework) and emits a gated diff proposal against `.saga/tier-defaults.json` — never auto-applied.
5. A tier-value scoring helper (module or function, e.g. in `spend_estimate.py`) that factors
   payoff-at-stake and remaining spend envelope into the recommendation strength shown alongside the
   estimate, so the estimate/reconcile surface communicates *why* a tier was worth it in the same
   terms an operator reasons in — deterministic, Claude-side, operator-confirmed; never an external
   engine adjudicating the decision.
6. `shadow_audit.py` (or equivalent) — a sampling hook usable from `/work`/team-execution that
   re-runs 1-in-N completed units one rung down the ordered `MODELS`/`EFFORTS` ladder, diffs the
   output against the original, and logs sufficient/insufficient to a tier-evidence ledger; plus a
   report path that renders per-stage tier-sufficiency rates. Off by default in attended mode without
   an explicit operator yes; budget-capped in unattended mode.
7. Tests for every module above under `tests/` (repo-root collected, matching this repo's
   `test_<plugin_client>.py` convention), each asserting the acceptance criteria below.
8. Release-surface updates: `plugins/saga/.claude-plugin/plugin.json` version bump,
   `.claude-plugin/marketplace.json` saga entry version bump, `plugins/saga/CHANGELOG.md` entry
   describing the new spend-observability surface, and any drift-guard test that already checks
   plugin/marketplace/CHANGELOG version parity stays green.

Verification: `uv run pytest`, `uv run ruff check .`, `uv run mypy plugins/ scripts/ tests/
--ignore-missing-imports`, and `uv run bandit -r plugins/` all pass; the new scripts are runnable
standalone (`python3 plugins/saga/scripts/<module>.py --help` exits 0).

### Acceptance criteria
- [ ] **(T12-F4-5)** Estimate/actual/delta prints for a sample plan and no ledger or status field is
  written by the estimate/reconcile step. Check: `uv run pytest tests/test_spend_estimate.py -k
  estimate_reconcile_no_write` → passes, and the test asserts no call into any ledger-write path.
- [ ] **(T12-F5-8)** A receipt's cheap-fallback counterfactual total equals the sum of each unit's
  declared fallback-tier estimate, and each above-fallback unit's tradeoff is named. Check: `uv run
  pytest tests/test_spend_receipt.py -k counterfactual_total_matches_fallback_sum` → passes.
- [ ] **(T12-F2-8)** A golden spend-summary test over a fixture set of leaf-produced ledgers matches
  expected aggregate tier-mix and premium-spend-share figures. Check: `uv run pytest
  tests/test_spend_retro.py -k golden_spend_summary` → passes.
- [ ] **(T12-F1-8)** A fixture history of overspent units with zero marginal findings yields a
  downgrade proposal from the `/retro` tier-efficacy pass, expressed as a diff object/patch against
  `.saga/tier-defaults.json` that is never applied by the test itself. Check: `uv run pytest
  tests/test_tier_efficacy_retro.py -k overspent_zero_marginal_yields_downgrade_proposal` → passes,
  and the test asserts the target `.saga/tier-defaults.json` fixture file is unchanged on disk after
  the pass runs.
- [ ] **(T12-F5-7)** A tier-value scoring test over a matrix of (payoff-at-stake, remaining-budget)
  pairs shows a high-stakes/full-budget unit scores at or above the top ladder rung's recommendation
  strength and a low-stakes/depleted-budget unit scores at or below a pushed-down rung, matching the
  ordered `MODELS`/`EFFORTS` index comparison. Check: `uv run pytest tests/test_spend_estimate.py -k
  tier_value_scoring_matrix` → passes.
- [ ] **(H-F6-1)** Shadow audit is off in attended mode without an explicit operator-yes flag/config
  value set, and is budget-capped (bounded max-samples) in unattended mode. Check: `uv run pytest
  tests/test_shadow_audit.py -k off_by_default_attended_and_budget_capped_unattended` → passes.
- [ ] **(H-F6-1)** The shadow-audit report renders per-stage tier-sufficiency rates (e.g. percentage
  of sampled units where one-rung-down was sufficient, broken out by work-shape/stage). Check: `uv
  run pytest tests/test_shadow_audit.py -k report_renders_per_stage_sufficiency_rates` → passes.
- [ ] **(binding decision)** None of the new modules writes a committed status field; every reported
  number is derived by reading `outcome_costs.py`'s existing ledger/rollup at render time. Check:
  `uv run pytest tests/test_spend_estimate.py tests/test_spend_receipt.py tests/test_spend_retro.py
  tests/test_shadow_audit.py -k derived_on_read` → passes (a shared fixture/test asserting no module
  under test calls a ledger-write function).
- [ ] Full suite, lint, types, and security scan stay green. Check: `uv run pytest && uv run ruff
  check . && uv run mypy plugins/ scripts/ tests/ --ignore-missing-imports && uv run bandit -r
  plugins/` → all pass.
- [ ] Release surfaces tell the same story as the diff. Check: `plugins/saga/.claude-plugin/plugin.json`
  version, `.claude-plugin/marketplace.json` saga entry version, and the latest
  `plugins/saga/CHANGELOG.md` heading all match, and any existing plugin-metadata drift-guard test
  passes: `uv run pytest -k plugin_metadata_drift` (or the repo's actual drift-guard test name, if
  differently named — confirm via `grep -rl "drift" tests/`).

### Out-of-scope / non-goals
In scope: the six reporting/ledger-reading surfaces above, all built as readers of the existing
`outcome_costs.py` ledger, plus one new tier-evidence ledger (append-only, written by the
shadow-audit sampling hook only) for shadow-audit results.

Out of scope / non-goals:
- Building the tier recommendation *registry* itself (`tier_advisor.py` / `tier-policy.json` /
  `tier_recommender.py` from sibling ideas in the same theme, e.g. `T12-F4-1`, `T12-F1-4`,
  `T12-F3-2`) — this issue consumes whatever baseline/fallback tier a unit already declares
  (`fallback_tier`, `tier_justification` fields on `ExecutionSpec` units) and does not invent that
  schema. If those fields don't exist yet at implementation time, stub a minimal fallback-tier
  lookup keyed on the existing `plan/SKILL.md:298-304` work-shape table rather than blocking on the
  sibling issue.
- Auto-applying any tier-default or tier-policy change — every proposal in this issue is a gated
  diff an operator reviews and applies manually.
- Dollar-denominated cost — all estimates/receipts/reports use ordinal, index-weighted relative cost
  units tied to the `MODELS`/`EFFORTS` ladder ordering, never asserted real provider pricing.
  (`{#tier-vocab-ordering}`)
- The spend-delta classifier / spend-envelope gating machinery that decides silent-vs-ask on a tier
  change (`T12-F4-3`, `T12-F3-3`) — this issue reports and reconciles spend, it does not gate
  choices.
- Making the shadow-audit sampling hook's spawn sites bypass the fleet's sandbox-spawn-site
  discipline: any Agent-tool spawn this issue adds for the replay-one-rung-down step must go through
  `subagent_type: saga:readonly-verifier` + `isolation: "worktree"` per
  `plugins/saga/references/sandbox-spawn-sites.md`, with the documented fallback ladder if that
  subagent type is unavailable — never an unsandboxed spawn.
- Changing `/plan`'s tier-table authoring flow beyond adding the estimate column — the underlying
  work-shape → tier heuristic stays as-is in this issue.

## Grounding References

- `T12-F4-5` — "Estimate-then-reconcile spend envelope built on the leaf-produced cost ledger."
  Basis: `docs/plans/2026-07-03-plugin-fleet-grounding-brief.md` section 2, binding `/outcome`
  campaign decision ("cost ledger = leaf-produced fact"; "Derived-on-read status, never committed
  status fields").
- `T12-F5-8` — "Itemized spend receipt with a cheap-fallback counterfactual." Basis (reasoned):
  the mined "xhigh-Opus on everything wasteful" complaint persists because spend is never contrasted
  against a cheaper alternative; reuses the `fallback_tier` field and the leaf cost ledger, no new
  spend-tracking substrate.
- `T12-F2-8` — "Spend retro: make 'xhigh-Opus is wasteful' a measured fact, not a belief." Basis
  (reasoned): the user's own validation-discipline rule forbids asserting cost claims without a
  source; nothing today aggregates the ledger to check the claim.
- `T12-F1-8` — "/retro tier-efficacy pass — evidence-tuned defaults from past cost-vs-outcome, not
  vibes." Basis (reasoned, first-principles): a recommender with no feedback signal cannot improve;
  the heuristic table is frozen at authoring quality forever without it.
- `T12-F5-7` — "Kelly-sized tier recommender: spend proportional to edge and remaining budget."
  Basis (external): Kelly criterion / bankroll-management position-sizing (Kelly 1956); deterministic
  Claude-side scoring, operator-confirmed, respects `{#external-engines-never-gatekeepers}` (no
  external engine adjudicates the decision) and `{#tier-vocab-ordering}` (only moves along the
  ordered ladder).
- `H-F6-1` — "Tier shadow audit: sampled counterfactual replay one tier down turns tier tables from
  vibes into evidence." Basis (direct): `docs/plans/2026-07-03-plugin-fleet-grounding-brief.md`
  section 7 pattern 6 (the mined "ad hoc tier reasoning every time" pain); intake tension 4 (every
  tier line needs a measured recommendation); `plugins/saga/scripts/execution_spec.py:52-53`
  (ordered `MODELS`/`EFFORTS` ladders make "one tier lower" well-defined).
- Binding decisions this issue must not cross: `/outcome` campaign (derived-on-read, leaf-produced
  cost ledger fact, never a committed status field); `{#tier-vocab-ordering}` (tier tuples are
  ordered escalation ladders); `{#external-engines-never-gatekeepers}` (any scoring/recommendation
  here stays Claude-side and operator-confirmed, never an external-engine gate); intake tension 1
  (spend-increasing choices — including shadow-audit sampling — always require explicit operator
  yes in attended mode, cache-first/budget-capped only in unattended mode).

### Recommended executor profile

- **Model:** sonnet
- **Effort:** high — *target posture: not a live team-execution dispatch knob until `pf-effort-first-class` lands; teammates inherit session tier until then*
- **Backend:** team-execution
- **External LLM posture:** offload permitted
- **Justification:** the report/aggregation facets here (estimate rendering, receipt counterfactual
  arithmetic, ledger aggregation, golden-fixture summaries) are mechanical work over a fixed,
  already-existing schema (`outcome_costs.py`'s rollup) — bounded transforms, not open-ended design
  judgment. The `/retro` tier-efficacy pass and shadow-audit report add a small amount of
  evidence-classification logic but stay within a fixed enum (sufficient/insufficient,
  downgrade/no-change), which keeps the whole issue at sonnet/high rather than requiring an opus
  tier. Per this repo's model-tiering guidance, offload to an external engine is permitted for this
  work-shape (mechanical, verify-apply-test chaperone pattern), consistent with
  `{#external-engine-chaperone-dispatch}`.

### Release-surface checklist

- [ ] `plugins/saga/.claude-plugin/plugin.json` — version bump reflecting the new spend-observability
  scripts and `/retro` skill edit.
- [ ] `.claude-plugin/marketplace.json` — saga entry version bumped to match.
- [ ] `plugins/saga/CHANGELOG.md` — new entry describing the estimate/reconcile, receipt, spend
  retro, tier-efficacy retro pass, and shadow-audit additions.
- [ ] Any existing plugin-metadata drift-guard test (`grep -rl "drift" tests/` to find its current
  name) passes with the bumped versions.
- [ ] `plugins/saga/skills/retro/SKILL.md` documents the new tier-efficacy pass as an added step,
  not a silent behavior change.
- [ ] `plugins/saga/references/sandbox-spawn-sites.md` gains a row for the shadow-audit replay spawn
  site if it adds a new Agent-tool call site.

### Tests to add or update

- `tests/test_spend_estimate.py` — estimate/reconcile no-write assertion; tier-value scoring matrix.
- `tests/test_spend_receipt.py` — counterfactual-total-matches-fallback-sum; named tradeoffs.
- `tests/test_spend_retro.py` — golden spend-summary over fixture ledgers; derived-on-read assertion.
- `tests/test_tier_efficacy_retro.py` — overspent/zero-marginal-finding fixture yields a gated
  downgrade proposal; target file unchanged after the pass.
- `tests/test_shadow_audit.py` — off-by-default in attended mode, budget-capped in unattended mode;
  per-stage sufficiency-rate rendering.

### Verification

```bash
uv run pytest
uv run ruff check .
uv run mypy plugins/ scripts/ tests/ --ignore-missing-imports
uv run bandit -r plugins/
python3 plugins/saga/scripts/spend_estimate.py --help
python3 plugins/saga/scripts/spend_receipt.py --help
python3 plugins/saga/scripts/spend_retro.py --help
python3 plugins/saga/scripts/shadow_audit.py --help
```
Expected: all green; each script's `--help` exits `0`.

### Handoff maturity
requirements-ready

### Suggested next action
Use `/plan <issue>` to create an implementation plan.

### Source context
- Source: docs/plans/plugin-fleet-ideation-2026-07-03/survivors/T12.json (ideas T12-F4-5, T12-F5-8,
  T12-F2-8, T12-F1-8, T12-F5-7), docs/plans/plugin-fleet-ideation-2026-07-03/survivors/T3.json
  (idea H-F6-1)
- Source type: ideation issue-map
- Source title: Spend observability on the ledger: estimate-reconcile, itemized receipts with
  counterfactuals, spend retro, tier-efficacy and shadow-audit evidence

### Context library links

_none_

### Files expected to change

- `plugins/saga/scripts/outcome_costs.py`
- `docs/plans/2026-07-03-plugin-fleet-grounding-brief.md`
- `docs/plans/plugin-fleet-ideation-2026-07-03/survivors/T12.json`
- `docs/plans/plugin-fleet-ideation-2026-07-03/survivors/T3.json`
- `.saga/tier-defaults.json`
- `plugins/saga/skills/plan/SKILL.md`
- `plugins/saga/skills/retro/SKILL.md`
- `plugins/saga/.claude-plugin/plugin.json`

### Objective

"Build the fleet telemetry and ledger substrate"

## Created Issue

- URL: https://github.com/infiquetra/infiquetra-claude-plugins/issues/402
- Number: 402
- Created at: 2026-07-04T08:02:13.629648+00:00

