---
title: Spend observability on the ledger — estimate-reconcile, itemized receipts, spend retro, tier-efficacy and shadow-audit evidence
type: feat
status: active
date: 2026-07-12
origin: infiquetra/infiquetra-claude-plugins#402
---

# Spend observability on the ledger — estimate-reconcile, itemized receipts, spend retro, tier-efficacy and shadow-audit evidence

## Summary

Build a read-only observability layer over the leaf-produced cost ledger
(`plugins/saga/scripts/outcome_costs.py`): a pre-run estimate + post-run reconcile
(`spend_estimate.py`), an itemized receipt with a cheap-fallback counterfactual
(`spend_receipt.py`), a cross-run spend retro (`spend_retro.py`), a `/retro` tier-efficacy pass
proposing gated `.saga/tier-defaults.json` diffs, and a sampled shadow-audit
(`shadow_audit.py`) that replays completed units one tier down to produce empirical
tier-sufficiency evidence. Implements infiquetra/infiquetra-claude-plugins#402, leaf sub-402 of
outcome `evidence-integrity` — the last of the four leaves building on #398's merged evidence
ledger (`plugins/saga/scripts/evidence_ledger.py`).

## Problem Frame

`/outcome`'s leaf-produced cost ledger already records what a run actually cost
(`outcome_costs.py rollup()`), but nothing today previews spend before tiers lock, contrasts
spend against the declared cheaper fallback, aggregates history into a per-repo trend, turns
history into a gated tier-default proposal, or produces ground truth for whether a tier choice
was necessary. The mined pain — "xhigh-Opus on everything is wasteful" — is asserted across
repos but never checked against the ledger the fleet already writes
(`docs/plans/2026-07-03-plugin-fleet-grounding-brief.md` section 7, recurring pattern 6).

This is purely an observability layer: every module here is a reader of the existing ledger or a
leaf-appender to a new evidence-ledger namespace. None writes a status field, and none
auto-applies a tier change — mirroring the binding `/outcome` campaign decision that the cost
ledger is a leaf-produced fact, derived-on-read, never committed by the orchestrator
(`docs/plans/2026-07-03-plugin-fleet-grounding-brief.md` section 2).

## Requirements

- **R1.** A pre-run relative-cost estimate column renders inside `/plan`'s own tier table
  (`plugins/saga/skills/plan/SKILL.md` §5.2a Step 1) for a single-session `ExecutionSpec`'s
  units — the issue's own literal DoD anchor. A separate, reusable node-tier resolver serves the
  `/outcome` DAG (`OutcomeSpec` node) granularity that `spend_receipt.py` (U2) and
  `spend_retro.py` (U3) consume for cross-run aggregation; `/plan` itself never renders an
  outcome-node table (`/plan` is single-session-scoped). Both surfaces are ordinal only, never a
  dollar amount. (T12-F4-5)
- **R2.** A post-run reconcile reads `outcome_costs.py`'s rollup (pure read; no ledger or status
  write) and prints per-unit/per-subplot `estimate / actual / delta` plus a run total.
  Commensurable fields (`operator_touches`, `retries`) get a numeric delta; non-commensurable
  real-telemetry fields (`tokens`, `wall_seconds`) render as labeled context, never coerced into
  the ordinal axis. (T12-F4-5)
- **R3.** A tier-value scoring helper factors payoff-at-stake and remaining spend envelope into a
  recommendation-strength signal alongside the estimate, using the ordered `MODELS`/`EFFORTS`
  ladder comparison — deterministic and Claude-side, never an external engine. The helper takes an
  abstract `{irreversible, gated, destructive}` signal triple so either caller can supply it: at
  the `/plan` `ExecutionSpec.Unit` level (R1's literal surface) it is derived from the unit's own
  fields — `sandbox` (`mutation_policy=read-write` + `workspace_isolation=ambient` = higher
  blast-radius/irreversibility than `read-only`/`disposable-worktree`), whether it carries a
  `verify` panel or is a fan-out's `pilot` (a gated decision) — and at the `outcome_spec.Node`
  level it is read directly from the node's own `gated`/`risky`/`destructive`/`guarantee_tags`
  fields, which already exist there. (T12-F5-7)
- **R4.** `spend_receipt.py` renders an itemized per-unit/per-tier receipt whose cheap-fallback
  counterfactual total equals the sum of each unit's declared fallback-tier cost, naming the named
  tradeoff for every unit that ran above its fallback tier. (T12-F5-8)
- **R5.** `spend_retro.py` aggregates the leaf-produced `cost_rollup` across every committed
  `docs/outcomes/*/outcome-spec.json` into a tier-mix / premium-spend-share / spend-vs-outcome
  summary, appended to `docs/engineering-journal/` as a spend-summary table; a golden-fixture test
  pins the aggregate figures. (T12-F2-8)
- **R6.** A `/retro` tier-efficacy pass mines the cross-run cost-vs-outcome evidence and, for a
  work-shape pattern of sustained overspend with zero marginal findings, emits a gated diff
  proposal against `.saga/tier-defaults.json` — never auto-applied. (T12-F1-8)
- **R7.** `shadow_audit.py` samples 1-in-N completed units, computes the one-rung-down tier,
  records a sufficient/insufficient verdict into the evidence ledger under a shadow-audit
  namespace, and renders a per-stage tier-sufficiency-rate report. (H-F6-1)
- **R8.** Shadow-audit sampling is off by default in attended mode absent an explicit
  operator-yes, and is budget-capped (a mandatory bounded `max-samples`) in unattended mode —
  never a silent default. (H-F6-1, intake tension 1)
- **R9.** Every module is a reader or a leaf-appender only: none writes a cost/status field back
  into `outcome_costs.py`'s ledger or an `outcome-spec.json` in place, and none auto-applies a
  tier-default/tier-policy change. A shared derived-on-read test fixture asserts no module under
  test calls a ledger-write function. (binding `/outcome` campaign decision)
- **R10.** All estimates, receipts, counterfactuals, and reports use ordinal, index-weighted
  relative cost units tied to the `MODELS`/`EFFORTS` ladder ordering — never a dollar amount.
  (`{#tier-vocab-ordering}`)
- **R11.** Any new Agent-tool spawn site this issue adds (the shadow-audit replay dispatch) is
  documented in `plugins/saga/references/sandbox-spawn-sites.md` and follows the ad-hoc rule
  (`saga:readonly-verifier` + `isolation: "worktree"`, with the documented fallback ladder) —
  never unsandboxed.
- **R12.** Release surfaces (`plugin.json`, `marketplace.json`, `CHANGELOG.md`) tell the same
  version story as the diff, and the existing release-surface drift-guard tests
  (`tests/test_release_triad.py`, `tests/test_release_surface_parity.py`) stay green.
- **R13.** The full repo gate stays green: `pytest`, `ruff check`, `ruff format --check`, `mypy
  plugins/ scripts/ tests/ --ignore-missing-imports`, `bandit -r plugins/`.

## Key Technical Decisions

**KTD1 — Two estimate granularities, one ordinal currency, one new fallback lookup sourced ONLY
from durable (committed/GitHub) state, never the git-ignored saga cache.**
`spend_estimate.py` estimates at both the single-session `ExecutionSpec.Unit` granularity
(reusing the already-shipped `unit_spend()`/`to_spend()`, `plugins/saga/scripts/
execution_spec.py:1110-1129`) and the `/outcome` DAG `Node` granularity. `outcome_spec.Node`
(`plugins/saga/scripts/outcome_spec.py:186-225`) carries no tier field — only an open `cost:
dict` pass-through and no `spec_path`/plan-path field either — so a new fallback-tier lookup
resolves each node's tier by, in order: (a) the node's linked GitHub issue's stamped `###
Recommended Tier Band` via `tier_defaults.parse_tier_band` (`plugins/saga/scripts/
tier_defaults.py:135-176`), read via `gh issue view` off the node's committed `github.issue`
field (`outcome_spec.py` `Node.github`) — durable and cross-machine; (b) else the shared
`SPEND_BASELINE` (`sonnet/high`, `execution_spec.py:2086`) as an explicit, clearly-labeled
default-not-derived estimate. Rejected: resolving via the leaf's own saga `orchestration_ref` or
any `.claude/saga/` state — that cache is git-ignored, machine-local, and explicitly "the anchor,
not the authority" per this repo's own precedence (`resume/SKILL.md` Core Principle 1: committed
`docs/*` and GitHub win over the cache), so `spend_retro.py`'s cross-run aggregation (U3, which
must work long after the fact, possibly from a different machine or a fresh clone) cannot depend
on it. Also rejected: adding a tier field to `Node`'s own schema (owned by `#287`/
`outcome_spec.py`, a separate concern) and classifying an arbitrary node into a work-shape via an
LLM call (unverifiable, not a pure function — this module must stay testable offline).

**KTD2 — `execution_spec.Unit` already carries the issue's anticipated `fallback_tier`/
`tier_justification` fields; no stub needed there.** `Unit.cheaper_fallback: Tier | None` and
`Unit.worth_it_because: str` (`execution_spec.py:883-884`, shipped by `#367`/`#565`) are
functionally identical to what the issue's non-goals section names — verified by direct read,
not assumed from the issue's own wording. The KTD1 fallback lookup is needed **only** at the
`outcome_spec.Node` granularity, where no equivalent field has ever existed.

**KTD3 — Reconcile only commensurable fields; never invent a token-to-ordinal exchange rate.**
The post-run reconcile in `spend_estimate.py` compares `operator_touches` and `retries` (both
implicitly estimated at 0 in a clean-run baseline) against `outcome_costs.py`'s rollup with a
true numeric delta. `tokens` / `wall_seconds` render alongside as labeled real-world context
("not unit-commensurable with the ordinal estimate"), and the categorical `executor` is compared
against the node's declared `backend` as a plan-vs-reality flag. This keeps R10 intact — no repo
data validates a token-per-ordinal-unit exchange rate today, so none is fabricated (both example
committed outcome specs carry an empty `cost_rollup: {}` — verified by direct read, zero real
telemetry exists yet).

**KTD4 — `spend_retro.py`'s cross-run source is every committed `docs/outcomes/*/outcome-
spec.json`'s materialized `cost_rollup`, not a new store.** This is the leaf-produced,
derived-on-read fact the binding `/outcome` campaign decision names. Both committed example specs
(`docs/outcomes/antigravity-teammate-plugin/`, `docs/outcomes/external-engine-offload/`) carry an
empty rollup today — `spend_retro.py` renders "no data yet" honestly for that real case (the U8
honesty rule `outcome_costs.py` already established, never a fabricated zero), while its golden-
fixture test exercises synthetic ledgers so coverage does not depend on real telemetry existing.

**KTD5 — The `/retro` tier-efficacy pass is a new Phase-5 propose-diff-and-wait target, never a
journal append.** `plugins/saga/skills/retro/SKILL.md`'s Phase 5 already lists four gated
meta-improvement passes — (a) new-skill detection, (b) refine-lifecycle, (c) refine-directives,
(d) memory pruning (`SKILL.md:369-384`) — each propose-diff-and-wait per THE TIERED SELF-EDIT
SAFETY CONTRACT (`SKILL.md:81-112`). The tier-efficacy pass is a fifth: it computes a candidate
`.saga/tier-defaults.json` diff (via `tier_defaults.py`'s existing validated shape) but never
calls `write_tier_default()` itself — it renders the diff and asks, exactly mirroring (b)/(c)
rather than widening AUTO-APPLY beyond the contract's one carve-out (a pure new journal entry).
Its evidence-gathering half lands as a new Phase-1 sub-section (1.10), beside the existing R12
override-rate reader (1.6), gate-divergence reader (1.6a), and R24 realized-economics pass (1.7) —
the same "reader in Phase 1, propose in Phase 5" shape those three already establish.

**KTD6 — `shadow_audit.py` never spawns an Agent itself.** A Python script cannot call the Agent
tool — only a Claude-driven flow can. `shadow_audit.py` owns the sampling decision, the
one-rung-down tier computation (reusing the already-shipped `execution_spec.adjacent_tier`,
`execution_spec.py:2122-2159`), the sufficient/insufficient classification (a built-in
whitespace-normalized exact-match `classify()` helper for simple diffable outputs, or a verdict
accepted verbatim from the invoking flow when judgment was required — the module never
fabricates an unvalidated AI-output-similarity score), and the ledger write + report. The actual
replay dispatch is performed by whichever Claude-driven flow invokes the module, and that flow's own Agent-tool
spawn for the replay MUST follow the sandbox-spawn-site ad-hoc rule
(`subagent_type: saga:readonly-verifier` + `isolation: "worktree"`, work-shape `judgment`) — a
new row in `sandbox-spawn-sites.md` documents this spawn site (R11).

**KTD7 — The tier-evidence ledger IS `evidence_ledger.py` (#398), reused via a namespaced
`check_id`, never a new file format.** `docs/engineering-journal/DECISIONS.md`
`{#evidence-ledger-ktds-398}` names its own extension seam: "sub-396/402 need entry kinds beyond
`evidence`/`criteria`/`closure` (the open `payload` dict is the extension seam)." `shadow_audit.py`
writes through `evidence_ledger.write(check_id="shadow-audit:<stage>:<unit-id>", verdict=
"sufficient"|"insufficient", payload={...tier comparison, diff summary...})` — reusing the
existing content-addressed, hash-chained custody log rather than inventing a second ledger.

**KTD8 — No wiring into `/work`'s or team-execution's default execution path in this PR.**
Neither is in the issue's own "Files expected to change" list or its release-surface checklist.
`shadow_audit.py` ships as a standalone, explicitly-invoked CLI/library — the smallest-blast-
radius reading of "usable from `/work`/team-execution" (capability exists; mandatory wiring is a
follow-up), and it keeps R8's "off by default" honest (nothing silently starts sampling from
inside an existing flow).

**KTD9 — Attended/unattended gating reuses the existing `unattended` vocabulary, never invents new
terms.** `execution_spec.emit_workflow_script`'s `unattended: bool` parameter (`#364` KTD3,
`execution_spec.py:2196-2199`) is the established attended-vs-unattended distinction in this
codebase. `shadow_audit.py` takes the same `--unattended` flag: attended (default) requires an
explicit `--yes` (or a `.saga/shadow-audit.json` `{"enabled": true}`) before sampling anything and
otherwise reports a clear "disabled" status (never a silent no-op mistaken for "ran, found
nothing"); unattended mode requires a mandatory `--max-samples` (an unattended run with no cap
HALTs rather than sampling unbounded).

## Implementation Units

### U1. `spend_estimate.py` — pre-run estimate, tier-value scoring, post-run reconcile

**Goal:** one module rendering an ordinal estimate column alongside `/plan`'s tier table for both
a single-session `ExecutionSpec` and an `/outcome` `OutcomeSpec`, a payoff-at-stake ×
remaining-budget tier-value score, and a post-run reconcile CLI verb reading `outcome_costs.py`'s
rollup per KTD3.

**Requirements:** R1, R2, R3, R9, R10.

**Dependencies:** none (reuses already-shipped `execution_spec.py`, `outcome_spec.py`,
`outcome_costs.py`, `tier_defaults.py`, and `fleet_commons.cost_weights`/`tier_palette` via
`fleet_commons_shim`).

**Files:** `plugins/saga/scripts/spend_estimate.py` (new), `tests/test_spend_estimate.py` (new),
`plugins/saga/skills/plan/SKILL.md` (edit — Phase 5.2a Step 1 tier table gains an Estimate
column, per the issue's own DoD anchor).

**Approach:** follow the house pattern in `outcome_costs.py`/`effort_ledger.py` — pure functions,
no I/O at import, a thin argparse CLI (`estimate` and `reconcile` verbs). Resolve
`fleet_commons_shim.load("tier_palette"/"cost_weights"/"tier_resolver")` exactly as
`execution_spec.py`/`tier_defaults.py` already do. The node-level fallback-tier lookup (KTD1) is a
small, separately-testable function (`resolve_node_tier(node, issue_body=None) -> Tier`) since
`spend_receipt.py` (U2) and `spend_retro.py` (U3) both reuse it. The R3 tier-value scorer
(`tier_value_score(tier, *, irreversible, gated, destructive, remaining_budget, envelope) ->
float`) takes the abstract signal triple directly (never a `Unit`/`Node` object), so both callers
map their own domain fields into it and the scorer itself stays a small pure function tested in
isolation. The `plan/SKILL.md` edit adds one
sentence + a worked-example column to the existing tier-table instructions (Phase 5.2a Step 1,
`plan/SKILL.md:329-345`): after resolving each unit's tier, call `spend_estimate.py estimate`
against the in-progress spec and render its per-unit ordinal figure as a fourth table column
beside Work shape / Default tier / Rationale — the table `/plan` already builds, not a new one.

**Patterns to follow:** `plugins/saga/scripts/effort_ledger.py` (CLI verb shape, `--ledger`
default path convention); `plugins/saga/scripts/execution_spec.py`'s `spend` CLI verb
(`execution_spec.py:2769-2795`, the existing per-unit spend printer this estimate column
extends); `outcome_costs.py`'s "no data yet" honesty rule (`rollup()`, lines 199-200).

**Test scenarios:**

- Happy path — a 3-unit `ExecutionSpec` and a 3-node `OutcomeSpec` each render an estimate table
  whose per-row and total ordinal figures match hand-computed `to_spend()` sums.
- Tier-value scoring matrix — a matrix of (payoff-at-stake, remaining-budget) pairs: a
  high-stakes/full-budget unit scores at or above the top ladder rung's recommendation strength;
  a low-stakes/depleted-budget unit scores at or below a pushed-down rung (the AC).
- Reconcile-no-write — monkeypatch `outcome_store._write_once`, `outcome_store.append_ledger`,
  and `evidence_ledger.write` to raise if called; run `reconcile()` against a populated rollup and
  assert it prints estimate/actual/delta and none of the patched functions fired (the AC).
- Empty-rollup renders "no data yet" for every subplot, never a fabricated zero delta.
- A node with no discoverable spec and no parseable tier band falls back to `SPEND_BASELINE`,
  rendered with an explicit "(default, no tier data)" label rather than silently blending in with
  a real estimate.

**Verification:** `python3 plugins/saga/scripts/spend_estimate.py --help` exits 0;
`.venv/bin/python3 -m pytest tests/test_spend_estimate.py -k estimate_reconcile_no_write` and
`-k tier_value_scoring_matrix` pass; `tests/test_saga_docs_coverage.py` (the existing SKILL.md
structural-coverage test) stays green after the `plan/SKILL.md` edit.

### U2. `spend_receipt.py` — itemized receipt + cheap-fallback counterfactual

**Goal:** a per-unit/per-tier receipt renderer (CLI verb over a single-session `ExecutionSpec`)
computing `counterfactual_total` = the sum of each unit's declared fallback-tier cost, and naming
the tradeoff for every unit that ran above its fallback tier. An `OutcomeSpec`/node-level receipt
is out of scope for this PR (see Deferred to Follow-Up Work, added during code-review — an earlier
draft of this section and the module's own docstring overclaimed it) — `spend_retro.py` (U3)
already covers the cross-run outcome-DAG aggregation case that would otherwise motivate it.

**Requirements:** R4, R9, R10.

**Dependencies:** none (does not use U1's `resolve_node_tier` — see above).

**Files:** `plugins/saga/scripts/spend_receipt.py` (new), `tests/test_spend_receipt.py` (new).

**Approach:** for each unit, resolve its fallback tier in priority order: the unit's own declared
`cheaper_fallback` (`execution_spec.Unit.cheaper_fallback`, when set) → `adjacent_tier(tier,
"cheaper")` (`execution_spec.py:2122-2159`). Sum `to_spend(fallback.model,
fallback.effort)` across every unit for the counterfactual total; for a unit already at the
cheapest tier (`adjacent_tier` raises `SpecError`), report "already cheapest — no
counterfactual" rather than propagating the exception.

**Patterns to follow:** `execution_spec.py`'s `spend` CLI verb output shape
(`execution_spec.py:2769-2795`) for the per-unit receipt line format; `Unit.worth_it_because`
(`execution_spec.py:877-884`) as the tradeoff text when present.

**Test scenarios:**

- Counterfactual-total-matches-fallback-sum — a spec with mixed above/at/below-baseline units;
  assert `counterfactual_total == sum(to_spend(fallback) for each unit)` (the AC).
- Every above-fallback unit names a tradeoff (`worth_it_because` when present, else "no
  justification recorded"); at-or-below-fallback units name none.
- A unit with no declared `cheaper_fallback` falls back to `adjacent_tier`'s one-rung-down.
- A unit already at the cheapest tier renders "already cheapest — no counterfactual" without
  raising.
- Derived-on-read — the same no-write guard as U1 (monkeypatch the three write functions to
  raise; assert none fire).

**Verification:** `--help` exits 0; `.venv/bin/python3 -m pytest tests/test_spend_receipt.py -k
counterfactual_total_matches_fallback_sum` passes.

### U3. `spend_retro.py` — cross-run aggregator + journal spend-summary

**Goal:** scan every committed `docs/outcomes/*/outcome-spec.json`, read each's materialized
`cost_rollup` plus per-node tier-mix (via U1's `resolve_node_tier`), aggregate tier-mix /
premium-spend-share (`execution_spec.is_escalation(SPEND_BASELINE, tier)` defines "premium") /
spend-vs-outcome (terminal-state counts vs spend), and append a dated
`docs/engineering-journal/` spend-summary table entry.

**Requirements:** R5, R9, R10, KTD4.

**Dependencies:** U1 (`resolve_node_tier`).

**Files:** `plugins/saga/scripts/spend_retro.py` (new), `tests/test_spend_retro.py` (new).

**Approach:** glob `docs/outcomes/*/outcome-spec.json`, parse each via
`outcome_spec.OutcomeSpec.from_dict` (read-only — never write the spec back), pull `cost_rollup`
and iterate `spec.nodes` for `state`/`backend`/`github` fields. Append the summary as a new
`## <date> Spend Retro` section to `docs/engineering-journal/LEARNINGS.md` (a pure append, no
existing content edited — mirrors the retro engine's own "AUTO is only a pure additive append"
rule, `retro/SKILL.md:86-90`).

**Patterns to follow:** `outcome_report.py`'s existing pattern for reading/rendering a committed
`OutcomeSpec` (a sibling consumer of the same file); `tests/test_outcome_economics.py`'s
`_load()` dynamic-import helper for pulling `plugins/saga/scripts/*.py` modules into a test
process (this repo's scripts are not an installed package).

**Test scenarios:**

- Golden spend-summary — a fixture set of 2-3 synthetic `outcome-spec.json`-shaped dicts (written
  to a `tmp_path`, not the repo's real committed examples) with populated `cost_rollup` and known
  node tiers; assert the rendered aggregate table (tier-mix, premium-spend-share) matches an exact
  expected value (the AC).
- Derived-on-read — asserts `spend_retro.py` never calls `outcome_store._write_once`,
  `outcome_store.append_ledger`, or `evidence_ledger.write`, and never rewrites an
  `outcome-spec.json` file in place (only reads it).
- Zero outcomes discovered in the repo renders "no data yet."
- Outcomes discovered but every rollup is empty (today's real repo state, verified) renders "no
  data yet" per outcome without crashing — a direct regression guard against the two real
  committed examples this issue found.

**Verification:** `--help` exits 0; `.venv/bin/python3 -m pytest tests/test_spend_retro.py -k
golden_spend_summary` and `-k derived_on_read` pass.

### U4. `/retro` tier-efficacy pass — SKILL.md edit + `tier_efficacy.py`

**Goal:** `plugins/saga/skills/retro/SKILL.md` gains a new Phase-1.10 evidence sub-section
(mining `spend_retro.py`'s aggregation for cost-vs-outcome per work-shape) and a new Phase-5(e)
propose-diff-and-wait target — a `.saga/tier-defaults.json` diff for a work-shape pattern of
sustained overspend with zero marginal findings — mirroring existing (b)/(c) exactly. Supporting
module `tier_efficacy.py` computes the candidate diff; it never calls `write_tier_default()`.

**Requirements:** R6, R9, KTD5.

**Dependencies:** U3 (consumes `spend_retro.py`'s cost-vs-outcome aggregation).

**Files:** `plugins/saga/skills/retro/SKILL.md` (edit), `plugins/saga/scripts/tier_efficacy.py`
(new), `tests/test_tier_efficacy_retro.py` (new).

**Approach:** `tier_efficacy.py` exposes `propose_downgrades(history, min_samples=3) ->
list[DowngradeProposal]` over `history: list[RunRecord]` (`RunRecord = {work_shape, tier, spend,
marginal_findings}`, a small explicit dataclass — the pure-function boundary tests construct
directly). Each proposal names the work-shape, the current vs proposed tier (one rung cheaper via
`adjacent_tier`), and the supporting evidence (N runs, spend delta, zero marginal findings). In a
real (non-test) invocation Phase 1.10 assembles `RunRecord`s by joining `spend_retro.py`'s
per-outcome spend aggregation with each check's verdict history from `evidence_ledger.py`'s
`latest()` reader (`superseded_fail`/attempt-count over `(check_id, reviewed_sha)` is the
"marginal findings"/"rework" signal: a run whose only attempt passed clean contributes zero
marginal findings; a superseded-FAIL or a multi-attempt history contributes nonzero).
`tier_efficacy.py` reads `.saga/tier-defaults.json` (via `tier_defaults.load_tier_defaults`) only to
compute the diff preview text — it never calls `write_tier_default`. The `SKILL.md` edit adds
Phase 1.10 (a reader, mirroring 1.6/1.6a/1.7's shape) and Phase 5(e) (the propose-diff step,
mirroring (b)/(c)'s `AskUserQuestion` apply/skip/modify pattern).

**Patterns to follow:** `retro/SKILL.md` Phase 5 (b)/(c) (`SKILL.md:375-378`) for the
propose-diff-and-wait presentation; `tier_defaults.py`'s `write_tier_default` (`tier_defaults.py:
179-190`) for the exact target-file shape the diff proposal previews.

**Test scenarios:**

- Overspent-zero-marginal-yields-downgrade-proposal — a fixture history of a work-shape running
  consistently above baseline tier with zero marginal findings across N runs yields a downgrade
  `DowngradeProposal`; assert the target `.saga/tier-defaults.json` **fixture file is byte-
  unchanged on disk** after the pass runs (the AC).
- A work-shape with mixed cost-vs-findings evidence (some runs found real issues) proposes no
  change.
- A work-shape with fewer than `min_samples` data points proposes no change rather than
  overfitting a single run.
- `retro/SKILL.md`'s edit keeps the file's existing structural contract (`saga_docs_coverage`-style
  invariants, if any apply to SKILL.md structure) — verified by re-running the existing saga docs
  coverage test after the edit.

**Verification:** `--help` exits 0; `.venv/bin/python3 -m pytest tests/test_tier_efficacy_retro.py
-k overspent_zero_marginal_yields_downgrade_proposal` passes.

### U5. `shadow_audit.py` — sampling hook, replay-one-rung-down, tier-evidence ledger

**Goal:** sample 1-in-N completed units (deterministic given a seed, for testability), compute
each sample's one-rung-down tier, classify sufficient/insufficient, record the verdict into the
evidence ledger under a `shadow-audit:<stage>:<unit-id>` namespace, and render a per-stage
tier-sufficiency-rate report. Gated per R8/KTD9.

**Requirements:** R7, R8, R9, R11.

**Dependencies:** none structurally (reuses already-shipped `execution_spec.adjacent_tier` and
`evidence_ledger.py`); sequenced last among the implementation units as the highest-novelty piece.

**Files:** `plugins/saga/scripts/shadow_audit.py` (new), `tests/test_shadow_audit.py` (new),
`plugins/saga/references/sandbox-spawn-sites.md` (new row in the "In-scope: verify/review-class
skill spawns" table).

**Approach:** CLI verbs `sample` (given a list of completed units + N + a seed, deterministically
pick 1-in-N eligible ones — a unit already at the cheapest tier is ineligible since
`adjacent_tier(tier, "cheaper")` would raise), `tier-down` (report the one-rung-cheaper tier for a
sampled unit), `record` (append a sufficient/insufficient verdict via
`evidence_ledger.write(check_id=f"shadow-audit:{stage}:{unit_id}", ...)`), and `report` (glob
`docs/evidence/*/ledger.jsonl`, filter entries whose `check_id` starts with `shadow-audit:`, and
tally sufficient/insufficient per stage).

`record`'s verdict comes from one of two sources, both accepted by the same CLI flag
(`--verdict sufficient|insufficient`, always caller-supplied — `record` itself never computes
one): (1) a built-in `classify(original: str, replayed: str) -> Literal["sufficient",
"insufficient"]` helper the invoking flow may call first for simple diffable text/JSON outputs —
concretely, whitespace-normalized exact string equality is `sufficient`; anything else is
`insufficient` (a strict, conservative default — no fuzzy-similarity threshold, since an
unvalidated similarity score is exactly the false-precision this issue's ordinal-only discipline
forbids elsewhere); or (2) a verdict the invoking Claude flow decided itself via judgment (a
`judgment`-tier spawned agent's own comparison), for outputs `classify()`'s exact-match is too
strict for. Either way `record` only accounts, per KTD6.

Gating per KTD9: `--unattended` absent (attended, default) requires `--yes` (a one-shot CLI
override for this single invocation) OR a `.saga/shadow-audit.json` `{"enabled": true}` (a
standing per-repo default) before `sample` returns anything — either satisfies the gate, checked
`--yes` first since it is the more explicit, narrower-scoped signal; `--unattended` requires a
mandatory `--max-samples` (absent → HALT, never sample unbounded).

**Patterns to follow:** `spend_authority.py`'s `.saga/`-committed-config + safe-default pattern
(`spend_authority.py:1-116`) for the attended/unattended gate config; `evidence_ledger.py`'s
`write`/`verify_chain` API (`evidence_ledger.py:213-284`, `418-480`) for the ledger reuse; the
existing `override_rate_reader.py`/`gate_divergence_reader.py`/`manifest_reader.py` house pattern
(scan-a-tree, aggregate, `--json` flag, "no data yet" zero-data contract) for the `report` verb.

**Test scenarios:**

- Off-by-default-attended — no `--yes`/config: `sample` returns zero eligible units and a clear
  `"disabled"` status (never a silent empty result indistinguishable from "ran, found nothing")
  (the AC); either `--yes` alone or a `.saga/shadow-audit.json` `{"enabled": true}` alone is
  sufficient to unblock `sample` in attended mode.
- `classify()` exact-match — whitespace-only differences classify `sufficient`; any other
  content difference classifies `insufficient` (the strict, no-fuzzy-threshold default).
- Budget-capped-unattended — `--unattended` with no `--max-samples` HALTs with a named error;
  `--unattended --max-samples 2` over 10 eligible units samples at most 2 (the AC).
- Report-renders-per-stage-sufficiency-rates — fixture ledger entries across 2 stages; `report`
  renders the correct sufficient/total ratio per stage (the AC).
- Ledger reuse round-trip — a recorded verdict passes `evidence_ledger.verify_chain` with no
  tamper.
- A unit already at the cheapest tier is excluded from sampling eligibility rather than crashing
  the batch when `adjacent_tier` would raise.

**Verification:** `--help` exits 0; `.venv/bin/python3 -m pytest tests/test_shadow_audit.py -k
off_by_default_attended_and_budget_capped_unattended` and `-k
report_renders_per_stage_sufficiency_rates` pass; the new `sandbox-spawn-sites.md` row matches
the existing table's column shape (Skill / File / Spawn site / Resolver work-shape = `judgment`).

### U6. Release surfaces + full CI gate

**Goal:** saga 0.81.0 → 0.82.0 in `plugins/saga/.claude-plugin/plugin.json`, the matching
`.claude-plugin/marketplace.json` saga entry, and a `plugins/saga/CHANGELOG.md` entry describing
the five new spend-observability modules plus the `/retro` tier-efficacy phase edit; full repo
gate green.

**Files:** `plugins/saga/.claude-plugin/plugin.json`, `.claude-plugin/marketplace.json`,
`plugins/saga/CHANGELOG.md`.

**Test expectation:** none — release bookkeeping; covered by `tests/test_release_triad.py`,
`tests/test_release_surface_parity.py`, and the full-suite run (R12, R13).

**Depends on:** U1–U5.

## Execution prerequisites

**Orchestration.** Inline, matching how sibling leaf #398 (this same outcome) executed — a single
session drives `/plan` → `/doc-review` → `/work` without a separate team-execution/dynamic-
workflows dispatch. This is a documented assumption (no operator interaction possible mid-flight
for this leaf); the more conservative, better-documented choice given the sibling precedent.

**Branch and merge target.** Leaf work branches from `main` (e.g. `work/402-spend-observability`);
the PR merges to `main`. The outcome branch `outcome/evidence-integrity` holds only the spec — the
outcome coordinator harvests sub-402 completion from the merged PR.

## Scope Boundaries

Out of scope (from the issue, binding):

- Building the tier-recommendation *registry* itself (`tier_advisor.py` / `tier-policy.json` /
  `tier_recommender.py`) — this issue consumes whatever fallback tier a unit or node already
  declares or can be resolved to (KTD1/KTD2), it does not invent that schema.
- Auto-applying any tier-default or tier-policy change — every proposal (U4, and any receipt/
  estimate finding) is a gated diff an operator reviews and applies manually.
- Dollar-denominated cost — every module uses ordinal, index-weighted relative cost units (R10).
- The spend-delta classifier / spend-envelope gating machinery that decides silent-vs-ask on a
  tier change (`#366`/`#367`, already shipped) — this issue reads and reuses it, it does not
  rebuild it.
- Wiring `shadow_audit.py` into `/work`'s or team-execution's default execution path (KTD8) — not
  in the issue's own files-expected-to-change list.
- Changing `/plan`'s tier-table authoring heuristic beyond adding the estimate column.
- Adding a tier field to `outcome_spec.Node`'s own schema — the KTD1 fallback-tier lookup is a
  read-time convenience function, not a spec-schema change (that's `#287`/`outcome_spec.py`'s
  concern).
- Modifying the real `.saga/tier-defaults.json` — this PR's shipped code only *reads* it (via
  `tier_defaults.load_tier_defaults`) and *previews* a diff (U4); the only place a
  `tier-defaults.json`-shaped file changes on disk is a test fixture under `tmp_path`, and U4's
  own AC asserts that fixture is byte-unchanged after the pass runs. The issue's own
  "Files expected to change" list names it advisory (same treatment `#398`'s plan gave its own
  advisory file list), not a required diff.
- Wiring `spend_receipt.py` into `/work`'s "run end" step — `/work`'s `SKILL.md` is not in the
  issue's own files-expected-to-change list; `spend_receipt.py` ships as a standalone CLI an
  operator (or a later `/work` wiring) invokes explicitly, the same smallest-blast-radius reading
  KTD8 applies to `shadow_audit.py`.

Deferred to Follow-Up Work (not non-goals):

- An `outcome_spec.OutcomeSpec`/node-level receipt in `spend_receipt.py` (using U1's
  `resolve_node_tier` KTD1 fallback for a node with no unit-level field at all) — an earlier draft
  of U2's Goal/Approach and the module's own docstring overclaimed this as already built; found and
  corrected during `/code-review` (correctness lens, P2). `spend_retro.py` (U3) already covers the
  cross-run outcome-DAG aggregation case a node-level receipt would otherwise serve, so this is
  genuinely deferrable rather than an unmet requirement — no `R4` acceptance criterion names an
  `OutcomeSpec` receipt, only `ExecutionSpec`.
- Wiring `shadow_audit.py` into `/work`'s live per-round loop once an operator wants it default-on
  for a repo (KTD8).
- A richer token-to-ordinal calibration once enough real `outcome_costs.py` telemetry accrues to
  validate one — today, zero real telemetry exists in this repo (KTD3/KTD4), so no calibration is
  defensible yet.
- Extending the `/retro` tier-efficacy pass to cross-repo evidence — stays single-repo per this
  issue, matching `/retro`'s existing single-repo boundary (cross-repo aggregation is `/promote`'s
  job).
- Survivor JSON stamping (`docs/plans/plugin-fleet-ideation-2026-07-03/survivors/{T12,T3}.json`)
  — advisory issue-map metadata, not a code deliverable; confirm at `/handoff`/`/retro` whether
  the issue-map tooling stamps them, per the same precedent `#398`'s plan set.
