---
title: "enhancement: offload economics guards — break-even halt, budget ceiling, cost-delta preview, net-savings ledger"
repo: infiquetra-claude-plugins
type: enhancement
team: campps
project: operations
status: Idea
labels: enhancement, hermes-task, needs-plan
risk: medium
tier: structural
objective: "Stand up the external-engine offload lane"
wave: wave-1
handoff_maturity: requirements-ready
---

# enhancement: offload economics guards — break-even halt, budget ceiling, cost-delta preview, net-savings ledger

### Objective

Stand up the external-engine offload lane

## Summary

The chaperone-dispatch capability (`{#external-engine-chaperone-dispatch}`, #318) lets a resident
Claude worker delegate units to an external engine (Codex, Gemini via agy) under an `offload` or
`second-opinion` intent, and it already defaults `offload` to `sonnet/medium` specifically "so a
heavier chaperone [doesn't erase] the token savings that motivated the delegation"
(`docs/engineering-journal/DECISIONS.md:2036`). That sentence is a claim about token economics with
no machinery behind it: nothing in `plugins/saga/scripts/engine_dispatch.py` or
`plugins/saga/scripts/engine_registry.py` today computes what the chaperone actually costs, compares
it against what the external dispatch was supposed to save, or halts a dispatch once it stops being
worth doing. The binding decision itself records this as an open revisit trigger: "`/retro` surfaces
that the sonnet/medium offload default is still eating more than it saves"
(`docs/engineering-journal/DECISIONS.md:2052`). This issue builds the missing economics layer so that
claim becomes a checked invariant instead of an assumption.

Five previously-separate ideation facets converged on the same gap and are absorbed here:

- A **break-even guard** that halts an external dispatch which isn't actually cheaper than doing the
  unit inline on Claude, and shows the comparison (`T2-F2-8`, primary; `T1-F2-3`, dedup-merged —
  same guard, framed from the chaperone side as "auto-collapse an uneconomic offload back to
  inline").
- A **per-provider budget ceiling** that halts spend at a declared cap rather than overshooting it
  (`T2-F1-8`).
- A **cost-delta preview** rendered on every engine-lane offer, naming a cheaper fallback when one
  exists (`T1-F1-8`).
- A **net-savings ledger** on the dispatch manifest — `net_savings = engine_tokens_avoided −
  chaperone_tokens_spent`, flagged when negative — so a completed offload can be audited after the
  fact, not just gated before it (`T1-F6-3`).
- A **zero-ledger fast path** for engines whose cost class is genuinely free, so the accounting
  machinery doesn't tax dispatches that have no economics to guard (`T1-F6-5`).

## Problem Frame

Three things are verified true today and none of them compute cost:

1. `plugins/saga/references/engine-registry.yaml` carries a `cost_speed_rank` field per engine
   variant (e.g. `:31`, `:61`, `:88`, `:118`), but the file's own header says what it is for:
   "`cost_speed_rank` is the KTD9 tie-break key: lower = cheaper+faster. It only breaks ties between"
   equally-rated capability variants (`plugins/saga/references/engine-registry.yaml:8`). It is an
   ordinal preference ranking, not a cost figure, and it is never read outside the capability
   tie-break (`{#external-engines-never-gatekeepers}`, KTD "capability tie-break = cost·speed",
   `docs/engineering-journal/DECISIONS.md:2009-2012`).
2. `plugins/saga/scripts/engine_dispatch.py` builds the dispatch manifest (attribution builder at
   `:124-186`) and runs the dispatch adapters (`:39-121`, including the `downgrade_note` fallback
   path at `:143-148`), but nothing in that module reads or writes a token count, a dollar figure, or
   a savings comparison. `grep -n cost plugins/saga/scripts/engine_dispatch.py` returns only unrelated
   docstring uses of the word ("evidence-only ceiling", `:70`/`:72`/`:333` — a permissions ceiling,
   not a spend ceiling).
3. The chaperone-tier decision (`docs/engineering-journal/DECISIONS.md:2035-2040`, KTD2) picks
   `sonnet/medium` for `offload` specifically to protect token savings, and the revisit trigger at
   `docs/engineering-journal/DECISIONS.md:2050-2052` names the exact failure mode this issue closes:
   discovering — only in hindsight, via `/retro` — that the chaperone has been eating more tokens
   than the offload saved, with no earlier checkpoint that could have caught it.

Net: the offload lane has a cost assumption baked into a tier default, and zero instrumentation to
confirm or refute that assumption before, during, or after a dispatch.

## Requirements

R1. Before an external dispatch proceeds under `offload` intent, the resolver/dispatch path computes
an estimated engine-side cost (tokens or dollars, whichever the engine's cost class supports) and an
estimated Claude-inline cost for the same unit, and compares them.

R2. If the external estimate is not cheaper than the Claude-inline estimate, the dispatch halts before
invoking the external engine adapter, returns a typed Resolution carrying both figures and a
recommended fallback (dispatch inline on Claude instead), and never silently proceeds at a loss.
Covers `T2-F2-8` / `T1-F2-3`.

R3. Each engine (or provider) in `engine-registry.yaml` may declare a budget ceiling (spend-per-run or
spend-per-window, engine's cost class determines the unit). Once cumulative spend against that ceiling
is reached, further dispatches to that engine/provider halt rather than overshoot the ceiling; the
halt is typed and reports which ceiling tripped and by how much the next dispatch would have
overshot. Covers `T2-F1-8`.

R4. Every point in the flow where an engine-lane dispatch is offered (plan-time tier table, run-time
dispatch confirmation) renders a cost-delta line: the estimated external cost, the estimated
Claude-inline cost, and the delta between them. Where a cheaper viable fallback exists (Claude-inline,
or a cheaper registry-ranked variant), it is named alongside the delta, not just implied by the
number. Covers `T1-F1-8`.

R5. The dispatch manifest (`engine_dispatch.py:124-186`'s attribution builder) gains a
`net_savings` field per completed dispatch: `engine_tokens_avoided − chaperone_tokens_spent` (using
whichever unit — tokens or dollars — the engine's cost class reports in). `engine_tokens_avoided` is
the estimated inline-Claude cost for the unit that was actually dispatched; `chaperone_tokens_spent`
is the resident chaperone worker's actual measured spend for that unit (resolve → dispatch → verify →
apply → test), not merely the external engine's own reported cost. When `net_savings` is negative, the
manifest entry is flagged (a distinct field or status value the manifest schema can assert on), not
silently recorded as a plain number. Covers `T1-F6-3`.

R6. Engines whose registry entry declares a genuinely free cost class (no metered spend, e.g. a
locally-run or zero-marginal-cost engine) skip R1–R3's estimate/compare/ceiling machinery entirely —
resolution proceeds with no budget check and no break-even comparison — but R5's manifest entry still
records `net_savings` using only the `chaperone_tokens_spent` side (external side is definitionally
zero), so the audit trail stays uniform even when there was no gate to pass. Covers `T1-F6-5`.

R7. None of R1–R6 introduces a second gated-verdict path. The break-even halt (R2) and the budget
ceiling halt (R3) are dispatch-time resolutions the chaperone or resolver returns, not a verdict an
external engine renders on its own dispatch — consistent with `{#external-engines-never-gatekeepers}`:
external engines occupy generator/advisory-reviewer/non-gated-worker roles only
(`docs/engineering-journal/DECISIONS.md:1992-1996`).

## Key Flows

F1. **Uneconomic offload, caught before dispatch.**
Trigger: resolver evaluates an `offload`-intent unit; estimated external cost ≥ estimated
Claude-inline cost.
Gate halts, names both figures, recommends inline fallback; external adapter is never invoked.
Covers R1, R2, R7.

F2. **Economic offload, ceiling not yet reached.**
Trigger: resolver evaluates an `offload`-intent unit; estimated external cost < inline estimate, and
cumulative provider spend is under its declared ceiling.
Dispatch proceeds normally; manifest records `net_savings` (positive) on completion.
Covers R1, R3, R5.

F3. **Ceiling reached mid-run.**
Trigger: a later dispatch to the same provider would push cumulative spend past its declared ceiling,
even though this individual unit would have been economical in isolation.
Dispatch halts with a typed ceiling-trip failure naming the ceiling and the overshoot amount, not a
generic error. Covers R3.

F4. **Free-class engine, zero friction.**
Trigger: unit routes to an engine whose registry entry declares a free cost class.
No estimate, no compare, no ceiling check; dispatch proceeds immediately. Manifest still records
`net_savings` using only the chaperone side. Covers R6.

F5. **Operator-facing preview.**
Trigger: `/plan`'s tier table, or a run-time dispatch confirmation, offers an engine-lane unit to the
operator.
Cost-delta line renders alongside the offer, naming the cheaper alternative when the shown option
isn't the cheapest available. Covers R4.

### Out-of-scope / non-goals
- Does not change the chaperone-tier default itself (`sonnet/medium` for `offload`,
  `opus/high` for `second-opinion`, `docs/engineering-journal/DECISIONS.md:2035-2040`) — this issue
  adds the instrumentation that would justify revisiting that default later, it does not revisit it
  now.
- Does not add a new gated verdict role for external engines — `{#external-engines-never-gatekeepers}`
  stands unchanged; break-even and ceiling halts are dispatch-time resolutions, not gates.
- Does not build a dollar-denominated billing/invoicing system — cost figures are whatever unit
  (tokens or provider-reported dollars) the engine's registry cost class already exposes; this issue
  does not add a new pricing-fetch integration per provider.
- Does not touch the `{#worker-cache-scheduling}` cache-economics theme (derive saga-side, reside
  team-side, `DECISIONS.md:292`) — that is a different economics axis (cache hit/miss scheduling),
  not offload break-even.
- Does not retrofit historical dispatch manifests with `net_savings` — the field applies to
  dispatches completed after this ships.
- Does not add a standing dashboard or scheduled reporting loop over `net_savings` data — that is a
  `/retro`-time or `/optimize`-time consumer of the ledger, not part of this issue's deliverable.

## Definition of Done

A completed offload dispatch is estimate-compared against Claude-inline cost before it runs (R1/R2),
halts rather than overshoots a declared per-provider budget ceiling (R3), renders a cost-delta line
naming a cheaper fallback at every engine-lane offer (R4), and records a `net_savings` figure on the
manifest — flagged when negative (R5) — while free-cost-class engines skip the estimate/ceiling
machinery entirely and still get a chaperone-side-only ledger entry (R6). None of this introduces a
new gated-verdict role for external engines (R7). All tests listed under "Tests to add or update" pass,
and the full repo gate (`uv run pytest && uv run ruff format --check . && uv run ruff check . && uv run
mypy plugins/ scripts/ tests/ --ignore-missing-imports`) is green.

### Acceptance criteria
- [ ] Break-even halt: an `offload`-intent unit whose estimated external cost is not cheaper than the
  Claude-inline estimate halts before the external adapter is invoked, and the halt carries both
  figures plus a recommended inline fallback. Covers R1, R2, R7 (Key Flow F1).
- [ ] Economical dispatch proceeds normally when the external estimate is cheaper than inline and the
  provider's cumulative spend is under its declared ceiling; the manifest records a positive
  `net_savings`. Covers R1, R3, R5 (Key Flow F2).
- [ ] Budget ceiling halt: a dispatch that would push cumulative provider spend past its declared ceiling
  halts with a typed failure naming the ceiling and the overshoot amount, even if the individual unit
  would have been economical in isolation. Covers R3 (Key Flow F3).
- [ ] Free-class fast path: a unit routed to a free-cost-class engine skips the estimate/compare/ceiling
  checks entirely, and its manifest entry still records `net_savings` using only the chaperone side.
  Covers R6 (Key Flow F4).
- [ ] Cost-delta preview: every engine-lane offer (plan-time tier table, run-time dispatch confirmation)
  renders the estimated external cost, the estimated Claude-inline cost, and the delta, naming a
  cheaper viable fallback when one exists. Covers R4 (Key Flow F5).
- [ ] Net-savings ledger, negative case: a completed dispatch whose `chaperone_tokens_spent` exceeded
  `engine_tokens_avoided` is flagged on the manifest, not silently recorded as a plain number. Covers
  R5.

## Grounding References

- `{#external-engine-chaperone-dispatch}` (#318) — `docs/engineering-journal/DECISIONS.md:2021-2053`:
  binding decision this issue instruments. KTD2 (`:2035-2040`) sets the `offload` → `sonnet/medium`
  default on a token-savings assumption; the revisit trigger (`:2050-2052`) names the exact
  discover-in-hindsight failure this issue prevents.
- `{#external-engines-never-gatekeepers}` (#283) — `docs/engineering-journal/DECISIONS.md:1985-2017`:
  binding constraint this issue must not violate (R7). `cost_speed_rank` tie-break KTD at `:2009-2012`
  is the existing (non-cost-figure) precedent this issue extends without widening.
- `plugins/saga/references/engine-registry.yaml:8,31,61,88,118` — existing `cost_speed_rank` field;
  confirmed ordinal tie-break only, not a cost/spend figure.
- `plugins/saga/scripts/engine_dispatch.py:39-121,124-186,143-148` — dispatch adapters, manifest
  attribution builder, and existing `downgrade_note` fallback path; the seam R1–R5 extend.
- **Absorbed ideas** (`docs/plans/plugin-fleet-ideation-2026-07-03/survivors/T1.json`,
  `T2.json`): `T2-F2-8` (primary — break-even guard), `T1-F2-3` (dedup-merged into T2-F2-8 — same
  guard, chaperone-side framing), `T2-F1-8` (per-provider budget ceiling), `T1-F1-8` (cost-delta
  preview on every engine-lane offer), `T1-F6-3` (net-savings ledger on the manifest), `T1-F6-5`
  ($0-engine zero-ledger fast path). `T2-F2-8`, `T2-F1-8` are `basis_type: direct`/`reasoned` against
  the cost-latency-telemetry axis; `T1-F2-3`, `T1-F1-8`, `T1-F6-3`, `T1-F6-5` are chaperone-economics
  / operator-ergonomics axis facets from the same theme cluster. Full dod_sketch text for these six
  ideas was compressed by a context-reference cache during ideation and had expired by drafting time;
  intent above is reconstructed from each idea's title, axis, tier_tag, and the binding-decision
  register in `docs/plans/2026-07-03-plugin-fleet-grounding-brief.md` section 2 (row for
  `{#external-engine-chaperone-dispatch}`) — a competent planner should re-derive exact wording during
  `/plan`, not treat this reconstruction as verbatim source.
- `docs/plans/2026-07-03-plugin-fleet-grounding-brief.md` sections 5-6: no pre-existing QUEUED.md seed
  or recurring-pain theme names this gap directly; it originates from the binding-decision register
  (section 2) and the fleet's cost-latency-telemetry ideation axis, not from a prior operator
  complaint.

## Dependencies / Assumptions

- Assumes `engine-registry.yaml` can be extended with per-engine cost-class metadata (free vs.
  metered, and the unit metered engines report in) without breaking `engine_resolver.py`'s existing
  tie-break read of `cost_speed_rank`.
- Assumes the resident chaperone worker's own token spend (resolve → dispatch → verify → apply → test)
  is already measurable by the existing execution/tier machinery (`plugins/saga/scripts/
  execution_spec.py` tier plumbing) — R5 consumes that measurement, it does not invent a new spend
  meter for the chaperone itself.
- Assumes the estimated Claude-inline cost for a unit (the R1/R2 comparison's other side) can be
  approximated from the unit's tier/effort assignment already present in the plan's tier table,
  without a full second execution.

## Recommended Executor Profile

- **Model:** Sonnet. **Effort:** medium. **Backend:** inline. **External LLM:** none.
- **Justification:** This is registry/schema plumbing plus a dispatch-time comparison and a manifest
  field addition inside an existing module (`engine_dispatch.py`, `engine_registry.py`,
  `engine-registry.yaml`) — mechanical, deterministic, well-scoped work against a design already
  settled by the absorbed ideation and the binding decisions above. It does not require adversarial
  judgment, cross-repo synthesis, or external-model second-opinion; sonnet/medium is the matching
  tier per this repo's own tiering convention (judgment/design/adversarial → Opus; mechanical or
  deterministic → Sonnet/Haiku).

## Release-Surface Checklist

This changes `saga` plugin behavior (new dispatch-time halts, new manifest field, new registry
schema fields) — the following must land in the same PR:

- [ ] `plugins/saga/.claude-plugin/plugin.json` — version bump (behavior change: new halt types, new
  manifest field, new registry schema fields).
- [ ] `.claude-plugin/marketplace.json` — matching version bump for the `saga` entry (`:84-90`).
- [ ] `plugins/saga/CHANGELOG.md` — entry documenting the break-even halt, budget ceiling, cost-delta
  preview, `net_savings` manifest field, and the free-class fast path.
- [ ] Version/metadata drift-guard tests (repo-root `tests/`) updated so plugin.json ↔ marketplace.json
  ↔ CHANGELOG version parity still holds for `saga`.
- [ ] `plugins/saga/references/engine-registry.yaml` schema/doc comments updated to document the new
  cost-class fields alongside the existing `cost_speed_rank` comment (`:8`).

### Files expected to change

Indicative only — `/plan` determines the exact set.

- `plugins/saga/references/engine-registry.yaml` — add per-engine cost-class metadata (free vs.
  metered, spend unit, budget ceiling).
- `plugins/saga/scripts/engine_registry.py` — load/validate the new cost-class fields.
- `plugins/saga/scripts/engine_resolver.py` — read cost-class metadata when resolving an `offload`
  dispatch; route free-class engines around the estimate/compare path (R6).
- `plugins/saga/scripts/engine_dispatch.py` — break-even estimate/compare + halt (R1/R2), budget
  ceiling tracking + halt (R3), `net_savings` manifest field in the attribution builder (`:124-186`)
  (R5).
- `plugins/saga/references/engine-dispatch.md` — document the new halts and manifest field for
  operators/planners.
- `tests/test_engine_dispatch.py` (new or extended) — break-even halt, ceiling halt, `net_savings`
  computation (positive and negative), free-class fast path.
- `plugins/saga/CHANGELOG.md`, `plugins/saga/.claude-plugin/plugin.json`,
  `.claude-plugin/marketplace.json` — release-surface updates per checklist above.

### Tests to add or update

- Break-even halt: a unit whose estimated external cost is not cheaper than the Claude-inline
  estimate halts before the external adapter is invoked, and the halt carries both figures. Check:
  `uv run pytest tests/test_engine_dispatch.py -k break_even_halt` → passes.
- Economical dispatch proceeds: a unit whose estimated external cost is cheaper than inline proceeds
  normally. Check: `uv run pytest tests/test_engine_dispatch.py -k break_even_proceeds` → passes.
- Budget ceiling halt: cumulative spend at or beyond a provider's declared ceiling halts the next
  dispatch to that provider, naming the ceiling and overshoot. Check: `uv run pytest
  tests/test_engine_dispatch.py -k budget_ceiling_halt` → passes.
- Cost-delta rendering: an engine-lane offer includes an estimated-cost line and, when a cheaper
  option exists, names it. Check: `uv run pytest tests/test_engine_dispatch.py -k cost_delta_preview`
  → passes.
- Net-savings ledger, positive case: a completed dispatch's manifest entry carries
  `net_savings = engine_tokens_avoided - chaperone_tokens_spent` correctly computed and unflagged.
  Check: `uv run pytest tests/test_engine_dispatch.py -k net_savings_positive` → passes.
- Net-savings ledger, negative case: a completed dispatch whose chaperone spend exceeded the avoided
  cost is flagged. Check: `uv run pytest tests/test_engine_dispatch.py -k net_savings_negative` →
  passes.
- Free-class fast path: a free-cost-class engine skips estimate/compare/ceiling checks entirely, and
  its manifest entry still records `net_savings` using only the chaperone side. Check: `uv run pytest
  tests/test_engine_dispatch.py -k free_class_fast_path` → passes.
- Full suite, format, lint, types stay green. Check: `uv run pytest && uv run ruff format --check . &&
  uv run ruff check . && uv run mypy plugins/ scripts/ tests/ --ignore-missing-imports` → all pass.

### Verification

```bash
# Unit + integration tests for the new economics guards
uv run pytest tests/test_engine_dispatch.py -v
# Full repo gate (CI parity)
uv run pytest && uv run ruff format --check . && uv run ruff check . && \
  uv run mypy plugins/ scripts/ tests/ --ignore-missing-imports
```
Expected: all green; break-even/ceiling halt tests demonstrate a halted dispatch never reaches the
external adapter call, and net-savings tests demonstrate both the positive and flagged-negative
manifest cases.

### Handoff maturity

requirements-ready — the absorbed-idea facets and binding-decision grounding are settled; exact field
names, schema shape, and estimate methodology are `/plan`'s to determine.

### Suggested next action

Use `/plan <issue>` to create an implementation plan.

### Source context

- Source: `docs/plans/plugin-fleet-ideation-2026-07-03/survivors/T1.json`,
  `docs/plans/plugin-fleet-ideation-2026-07-03/survivors/T2.json` (absorbed ideas `T2-F2-8`,
  `T1-F2-3`, `T2-F1-8`, `T1-F1-8`, `T1-F6-3`, `T1-F6-5`)
- Source: `docs/plans/2026-07-03-plugin-fleet-grounding-brief.md` (binding-decision register,
  section 2)
- Source type: ideation issue-map (plugin-fleet)
- Source title: Offload economics: break-even halt, per-provider budget ceiling, cost-delta preview,
  net-savings accounting

### Intent

The chaperone-dispatch capability (`{#external-engine-chaperone-dispatch}`, #318) lets a resident Claude worker delegate units to an external engine (Codex, Gemini via agy) under an `offload` or `second-opinion` intent, and it already defaults `offload` to `sonnet/medium` specifically "so a heavier chaperone [doesn't erase] the token savings that motivated the delegation" (`docs/engineering-journal/DECISIONS.md:2036`). That sentence is a claim about token economics with no machinery behind it: nothing in `plugins/saga/scripts/engine_dispatch.py` or `plugins/saga/scripts/engine_registry.py` today computes what the chaperone actually costs, compares it against what the external dispatch was supposed to save, or halts a dispatch once it stops being worth doing. The binding decision itself records this as an open revisit trigger: "`/retro` surfaces that the sonnet/medium offload default is still eating more than it saves" (`docs/engineering-journal/DECISIONS.md:2052`). This issue builds the missing economics layer so that claim becomes a checked invariant instead of an assumption.

### Context library links

_none_

## Created Issue

- URL: https://github.com/infiquetra/infiquetra-claude-plugins/issues/386
- Number: 386
- Created at: 2026-07-04T07:57:05.414379+00:00

