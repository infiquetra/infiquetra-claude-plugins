---
title: "capability: earned ratings — dispatch/benchmark evidence drives retro-gated engine-registry calibration (SPC drift, Elo, staleness report)"
repo: infiquetra-claude-plugins
type: capability
team: campps
project: operations
status: Idea
labels: capability, hermes-task, needs-plan
risk: medium
handoff_maturity: requirements-ready
tier: moonshot
objective: "Build the fleet telemetry and ledger substrate"
wave: wave-3
---

# capability: earned ratings — dispatch/benchmark evidence drives retro-gated engine-registry calibration (SPC drift, Elo, staleness report)

### Objective
Build the fleet telemetry and ledger substrate

### Summary
`plugins/saga/references/engine-registry.yaml` and its loader
(`plugins/saga/scripts/engine_registry.py`) hold every external-engine capability rating
(`WEAK`/`MODERATE`/`STRONG`, `RATINGS` at `engine_registry.py:22-24`) and `last_validated` date
(`EngineEntry.last_validated`, `engine_registry.py:176`) as **authored, single-write oracle
data** — nothing in the fleet today re-derives a rating or a staleness signal from what actually
happened when an engine was dispatched. Six independently found ideation facets converge on the
same closed loop: an append-only, tamper-evident per-call ledger of dispatch facts; a benchmark
harness that runs a fixed eval suite against a registry claim; SPC control charts that flag
cost/latency drift from that telemetry; an Elo-style rating that moves from reconciliation
win/loss outcomes; a staleness report that names which registry cells have no recent
corroborating evidence; and the `/retro` sub-step that turns all four signals into human-approved
registry-diff proposals — never an automatic write. This issue lands all six as one coherent
evidence-to-proposal pipeline, because every one of them either produces or consumes the same
ledger and the same non-negotiable seam: nothing but a human, via `/retro`, ever edits
`engine-registry.yaml`.

### Problem Frame
Confirmed directly in this repo:

- `plugins/saga/scripts/engine_registry.py:22-24` — `RATINGS = ("WEAK", "MODERATE", "STRONG")`
  and `_RATING_SCORE` are authored per row in `engine-registry.yaml` and consulted by
  `Registry.by_capability` (`engine_registry.py:349-350`, sorting on `-_RATING_SCORE[...]` then
  `cost_speed_rank`) with **no feedback path** — a rating that was wrong on day one, or has gone
  stale, stays exactly as authored until a human manually re-edits the YAML.
- `plugins/saga/scripts/engine_registry.py:174-176` (`EngineEntry`) carries `last_validated: date`
  and `Registry.stale()` (`engine_registry.py:377-385`, confirmed present via
  `grep -n "def stale" plugins/saga/scripts/engine_registry.py`) already compares it against a
  cutoff — but nothing populates `last_validated` from **evidence**; it is bumped by hand, the
  same authored-oracle problem the rating field has.
- `plugins/saga/scripts/engine_resolver.py:178-214` (`_resolve_capability` /
  `_resolve_entry`) and `engine_resolver.py:346-350` (`_capability_fit_failure`) read the
  registry's `capability_profile[capability]["rating"]` at every dispatch decision — every one of
  those calls is a data point about whether the claimed rating held up, and today none of it is
  captured anywhere.
- No per-call dispatch ledger exists anywhere in the engine-dispatch path: `grep -rn
  "dispatch.*ledger\|engine.*ledger" plugins/saga/scripts` (run 2026-07-03) returns nothing under
  `engine_resolver.py` or `engine_registry.py`. The append-only, hash-chained ledger pattern
  already exists one layer over in the outcome subsystem — `outcome_store.py:408`
  (`append_ledger`) and its replay ledger (`outcome_store.py:18-20`, `:377-408`) — but that ledger
  records outcome-orchestration events, not per-engine-dispatch cost/rating facts, and carries no
  hash-chaining / tamper-evidence (confirmed via `grep -n "hash" plugins/saga/scripts/outcome_store.py`
  returning no match).
- `outcome_costs.py:1-23` (`record_cost` / `rollup`) already establishes the house pattern this
  issue extends: telemetry is a **leaf-produced fact** written by the party that did the work,
  never fabricated, with an explicit "no data yet" state for missing telemetry rather than a
  silent zero (per binding decision `/outcome` campaign U8 stance). No equivalent producer exists
  for per-engine-capability dispatch facts.
- `plugins/saga/skills/retro/SKILL.md:3-25` — `/retro` is already the fleet's terminal, advisory,
  gated meta-improvement phase ("every one gated... never self-applies a non-journal edit") that
  promotes findings into `docs/engineering-journal/`, but its current scope
  (`grep -n "engine\|registry\|calibrat" plugins/saga/skills/retro/SKILL.md`, run 2026-07-03)
  never mentions the engine registry — the natural gated home for a rating-drift proposal does
  not yet consume registry/dispatch evidence at all.

This is the primary consolidation target for its ideation theme in
`docs/plans/plugin-fleet-ideation-2026-07-03/survivors/`: `T1-F3-7` is the primary (the
`/retro`-gated proposal mechanism that ties everything together); `T2-F1-7`, `T2-F4-7`,
`T2-F5-5`, `T2-F5-7`, and `T2-F5-8` are absorbed facets of the same calibration-evidence problem
(theme T2, frames F1/F4/F5). Binding decision `{#external-engines-never-gatekeepers}` (#283)
constrains all of this directly: none of the added telemetry, benchmarks, drift detection, or
rating math is permitted to write the registry autonomously — every signal terminates in a
**proposal** that `/retro` surfaces and a human applies.

### Key Decisions
- **One ledger, six consumers, one write seam.** The tamper-evident per-call ledger
  (`T2-F5-8`) is the single producer; the benchmark harness (`T2-F1-7`), SPC drift detector
  (`T2-F5-7`), Elo updater (`T2-F5-5`), and staleness report (`T2-F4-7`) are four independent
  readers/reducers over it; `/retro`'s calibration sub-step (`T1-F3-7`) is the single writer of
  proposals — and the only thing a human ever applies to `engine-registry.yaml` stays a manual
  edit. This ships as one coherent evidence pipeline, not six patches that could disagree about
  what "evidence" means.
- **Proposal-only, always.** Every one of the four signals (benchmark result, SPC flag, Elo
  delta, staleness cell) is surfaced as a named diff proposal against `engine-registry.yaml` — a
  rating, `last_validated` bump, or cost-field change a human/`/retro` operator must explicitly
  accept. None of the four call sites is permitted a direct-write code path; this is the same
  posture `{#external-engines-never-gatekeepers}` (#283) already imposes on external-engine
  outputs generally, applied here to the registry's own data.
- **The ledger is append-only and hash-chained, not merely append-only.** `T2-F5-8` explicitly
  hardens against the documented chain-of-custody failure already recorded in this repo's journal
  (a probe script overwriting a FAIL evidence artifact with a later PASS — grounding brief §7
  singleton) — mutating or deleting an earlier dispatch record must fail verification, not merely
  be discouraged by convention.
- **SPC drift detection is common-cause-vs-shift, not a static staleness threshold.** `T2-F5-7`
  is explicitly distinct from `T2-F4-7`'s seed-vs-observed staleness report: SPC control charts
  detect a *shift* in a provider's cost/latency time series (a drift flag consumed by
  deprioritization), while the staleness report answers a different question — which cells lack
  *any* recent corroborating evidence at all, regardless of drift.
- **Elo learns from live match outcomes, not a synthetic suite.** `T2-F5-5` is explicitly
  distinct from the benchmark harness (`T2-F1-7`): Elo moves from real reconciliation win/loss
  records (a provider that loses repeated reconciliations drops below a rival), while the
  benchmark harness runs a fixed eval suite independent of any live dispatch outcome. Both feed
  proposals; neither substitutes for the other.
- **Benchmark harness actively runs, it does not just observe.** `T2-F1-7` is distinct from the
  passive telemetry ledger: it is a `engine_benchmark.py` + fixed per-capability eval-suite that
  runs a real query against a real engine and compares the measured result to the authored rating
  — this is active measurement, not a reduction over passively-collected dispatch facts.

### Actors
- A1. Dispatch ledger writer (new, `T2-F5-8`) — appends a hash-chained record for every
  engine-dispatch call in `engine_resolver.py`'s `resolve`/`_resolve_capability` path.
- A2. Benchmark harness (new, `T2-F1-7`) — runs a fixed eval suite against a live engine and
  compares measured vs. authored rating.
- A3. SPC control-chart reducer (new, `T2-F5-7`) — computes rolling per-provider cost/latency
  bands over the ledger and flags out-of-control shifts.
- A4. Elo updater (new, `T2-F5-5`) — updates a per-capability Elo-style score from reconciliation
  win/loss records.
- A5. Staleness report (new, `T2-F4-7`) — joins the ledger against `EngineEntry.last_validated`
  and corroboration state, emitting per-(engine, capability) corroborated / contradicted /
  unexercised verdicts.
- A6. `/retro` calibration sub-step (new, `T1-F3-7`) — aggregates A2-A5's output into
  per-cell rating-drift proposals against `engine-registry.yaml`, surfaced for human approval;
  never writes the registry directly.
- A7. `engine-registry.yaml` / `engine_registry.py` — the existing registry and loader (unchanged
  schema in this issue; see `pf-engine-registry-schema`, a sibling issue, for schema evolution).
  This issue's proposals target its `rating` and `last_validated` fields.

### Requirements
**Tamper-evident dispatch ledger (T2-F5-8)**
R1. Every call through `engine_resolver.py`'s dispatch path appends an append-only,
hash-chained record (engine id, capability, timestamp, outcome) to a dedicated engine-dispatch
ledger; a `verify_ledger` check detects any mutation or deletion of an earlier record and fails.

**Benchmark harness (T2-F1-7)**
R2. A benchmark harness (`engine_benchmark.py`) runs a fixed per-capability eval suite against a
live engine and emits a registry-diff **proposal** (never a write) when the measured rating
contradicts the authored one in `engine-registry.yaml`.

**Staleness report (T2-F4-7)**
R3. A stale-report reducer joins the dispatch ledger against each row's `last_validated` and
corroboration history, emitting a per-(engine, capability) verdict of `corroborated`,
`contradicted`, or `unexercised`, consumed as an input bullet by `/retro`.

**Elo-style reconciliation ratings (T2-F5-5)**
R4. A `capability_elo` updater derives an Elo-style score per (engine, capability) from
reconciliation win/loss outcomes; the updater output is consulted alongside the static
`rating` field as a prior/fallback signal in resolution, and is itself only ever surfaced as a
proposal — it does not silently override the authored `rating`.

**SPC drift detection (T2-F5-7)**
R5. A `provider_control_chart` reducer computes rolling per-provider cost/latency control bands
from the ledger and emits a drift flag when a provider's cost or latency shifts out of its
band; the flag is consumed as a deprioritization signal at resolution time, and is surfaced to
`/retro` as a re-validation-needed proposal.

**Retro-gated proposal mechanism (T1-F3-7)**
R6. `/retro` gains a calibration sub-step that aggregates R2-R5's output into per-cell
rating/`last_validated` diff proposals against `engine-registry.yaml`; the sub-step never writes
the registry file — it only emits a proposal for the operator to apply by hand.

### Key Flows
F1. **Dispatch fact recorded.** Trigger: `engine_resolver.resolve` completes a dispatch. The
ledger writer appends a hash-chained record of the call. Covers R1.

F2. **Benchmark contradicts a claim.** Trigger: the benchmark harness runs its fixed eval suite
against an engine whose measured capability result disagrees with its authored `rating`. The
harness emits a registry-diff proposal naming the contradicted row; no write occurs
automatically. Covers R2.

F3. **Staleness report feeds `/retro`.** Trigger: `/retro` runs. The stale-report reducer joins
the ledger against `last_validated` and corroboration state and returns one verdict per
(engine, capability) cell; `/retro` surfaces cells with `unexercised` or `contradicted` verdicts
as calibration candidates. Covers R3, R6.

F4. **Reconciliation loss drops an Elo score.** Trigger: a provider loses repeated
reconciliations recorded in the ledger. The Elo updater lowers that provider's score below a
rival for the same capability; resolution logic that consults Elo as a prior/fallback stops
selecting it, while the authored `rating` field itself remains unchanged until a human applies
the corresponding `/retro` proposal. Covers R4.

F5. **Cost/latency drift flags a provider.** Trigger: a synthetic or real latency spike series
for a provider crosses its computed control band. The SPC reducer emits an out-of-control flag;
resolution deprioritizes the flagged provider, and `/retro` surfaces a re-validation proposal for
its row. Covers R5.

F6. **`/retro` emits a calibration proposal, never a write.** Trigger: `/retro` runs with
non-empty benchmark/staleness/Elo/SPC signals accumulated since the last run. The calibration
sub-step emits one aggregated rating-drift proposal (with `last_validated` bumps) for the
operator to review and apply; a test asserts the registry file itself is unchanged by the
`/retro` run. Covers R6.

### Acceptance Examples
AE1. **Covers R1.** A test appends three dispatch records, then mutates the middle record's
payload in place — `verify_ledger` fails chain verification; with the mutation reverted, it
passes.

AE2. **Covers R2.** A test seeds a fake provider whose authored `rating` is `STRONG` for a
capability but whose measured benchmark result is `WEAK` — the harness emits a registry DIFF
PROPOSAL naming that row and capability; asserting no write occurred to the registry file.

AE3. **Covers R3.** Synthetic ledger + registry fixtures cover all three staleness verdicts:
a row with recent corroborating ledger evidence reports `corroborated`; a row whose ledger
evidence disagrees with its authored rating reports `contradicted`; a row with no ledger
evidence at all reports `unexercised`.

AE4. **Covers R4.** A test seeds reconciliation records where provider A loses to provider B
five times running for the same capability — provider A's Elo score drops below provider B's,
and a resolution call consulting Elo as a fallback prior selects B; the authored `rating` field
for A is unchanged until a `/retro` proposal is applied.

AE5. **Covers R5.** A test feeds a synthetic latency series with a sudden sustained spike for
one provider — the SPC reducer flags that provider out-of-control while a second provider with
normal common-cause variation is not flagged.

AE6. **Covers R6.** A `/retro` run over seeded ledger fragments (with benchmark, staleness, Elo,
and SPC signals present) emits a rating-change proposal with `last_validated` bumps as its
output artifact; a test asserts `engine-registry.yaml`'s on-disk contents are byte-identical
before and after the `/retro` run.

## Definition of Done
This capability is done when the dispatch ledger, benchmark harness, staleness report, Elo
updater, and SPC reducer all exist and feed `/retro`'s calibration sub-step, which emits
per-cell rating-drift proposals but never writes `engine-registry.yaml` directly (verified by
a test that the file is byte-identical before and after a `/retro` run). It also requires the
full acceptance-criteria checklist below to pass and release-surface metadata (plugin version,
marketplace entry, CHANGELOG) to be updated in the same PR.

### Out-of-scope / non-goals
- This issue does not change `engine-registry.yaml`'s schema (capability vocabulary, family
  inheritance, cost/latency fields) — that is `pf-engine-registry-schema`, a sibling wave-1
  issue; this issue's proposals target the existing `rating` and `last_validated` fields only.
- This issue does not build the `engine_offer` helper or routing-policy-as-data
  (`surface_intent_defaults`) — those are separate sibling issues (`pf-engine-offer-helper`,
  `pf-engine-registry-schema`).
- It does not grant any external engine or automated reducer write access to
  `engine-registry.yaml` — every signal (benchmark, SPC, Elo, staleness) terminates in a
  `/retro`-surfaced proposal that only a human applies. This is a structural constraint, not an
  implementation detail; a PR that writes the registry directly from any of R2-R5 fails review.
- It does not change `{#external-engines-never-gatekeepers}` (#283) — Claude remains
  verifier-of-record; this issue only gives `/retro` more evidence to reason with.
- It does not build a standing, scheduled calibration ceremony that runs independent of
  `/retro` — calibration is computed on `/retro`'s existing cadence (operator-invoked, terminal
  lifecycle phase), not a new cron-like mechanism.
- It does not depend on or block the wave-1 registry-schema issue's cost/latency field
  additions; it depends on the wave-2 ledger spine per the consolidation rationale (hence
  wave-3 despite this objective's wave-2 home).

### Dependencies / Assumptions
- Binding: DECISIONS `{#external-engines-never-gatekeepers}` (#283) — every signal this issue
  adds terminates in a human-applied proposal; none gains write access to the registry.
- Binding: DECISIONS `{#external-engine-chaperone-dispatch}` (#318) — dispatch mechanics
  (offload/second-opinion routing) are unchanged; this issue only instruments and evidences them.
- Depends on the wave-2 ledger spine (per the consolidation rationale in
  `docs/plans/plugin-fleet-ideation-2026-07-03/issue-map/issue-map-final.json`'s
  `consolidation_rationale` for this issue) — the tamper-evident dispatch ledger this issue builds
  extends the existing house pattern already proven in `outcome_costs.py` (`record_cost`/
  `rollup`, leaf-produced-fact discipline) and `outcome_store.py:408` (`append_ledger`), but
  neither of those modules is hash-chained or engine-dispatch-scoped today — verified via
  `grep -n "hash" plugins/saga/scripts/outcome_store.py` (no match) and no
  `dispatch.*ledger`/`engine.*ledger` hit under `plugins/saga/scripts` (run 2026-07-03).
- Verified absent today: no per-engine-dispatch ledger, no benchmark harness, no SPC reducer, no
  Elo updater, and no `/retro` engine-registry calibration step exist anywhere in this repo
  (`grep -n "engine\|registry\|calibrat" plugins/saga/skills/retro/SKILL.md` returns no
  registry-calibration content; `find plugins/saga/scripts -iname "*ledger*"` returns no
  engine-dispatch ledger file).
- Reuses existing, already-implemented primitives rather than re-inventing them:
  `Registry.stale()` (`engine_registry.py:377-385`), `RATINGS`/`_RATING_SCORE`
  (`engine_registry.py:22-24`), and the leaf-produced-fact / "no data yet" honesty discipline
  already established by `outcome_costs.py`.
- Grounding references (absorbed ideas, from
  `docs/plans/plugin-fleet-ideation-2026-07-03/survivors/T1.json` and
  `docs/plans/plugin-fleet-ideation-2026-07-03/survivors/T2.json`):
  - `T1-F3-7` (primary, tier `moonshot`) — "The registry calibrates itself from real
    reconciliation outcomes — retro-gated." Basis: `dod_sketch` calls for a `/retro` sub-step
    aggregating reconciliation-ledger outcomes into per-cell rating-drift proposals against
    `engine-registry.yaml` (proposal-only, human-applied), verified by a `/retro` run over
    seeded ledger fragments emitting a rating-change proposal with `last_validated` bumps and a
    test it never writes the registry directly.
  - `T2-F1-7` (facet, tier `moonshot`, basis type `direct`) — "Automated provider-benchmark
    harness proposing registry rating/cost updates." Basis: `dod_sketch` calls for
    `engine_benchmark.py` + a per-capability eval-suite fixture + a `benchmark-loop.md`
    documenting the propose-not-commit gate, verified by running against a fake provider whose
    measured rating contradicts its authored one and asserting it emits a registry DIFF PROPOSAL
    (never a write) requiring human/Claude-step approval.
  - `T2-F4-7` (facet, tier `moonshot`, basis type `direct`) — "Ledger-fed staleness report that
    arms `/retro` to revalidate ratings from evidence." Basis: `dod_sketch` calls for a
    stale-report subcommand joining the usage ledger against per-row `last_validated`/
    corroboration, emitting per-(engine, capability) corroborated/contradicted/unexercised plus a
    `/retro` SKILL.md input bullet, verified by a test over synthetic ledger+registry fixtures
    covering all three cell verdicts.
  - `T2-F5-5` (facet, tier `moonshot`, basis type `external`) — "Elo-rated capabilities: ratings
    that learn from reconciliation outcomes." Basis: `dod_sketch` calls for a `capability_elo`
    updater + an optional `elo` field consulted with the static rating as prior/fallback in
    `resolve_capability`, fed by reconciliation-outcome records, verified by a test that a
    provider losing repeated reconciliations drops below a rival and stops being selected.
  - `T2-F5-7` (facet, tier `structural`, basis type `external`) — "SPC control charts for
    providers: detect cost/latency drift and auto-flag rows for re-validation." Basis:
    `dod_sketch` calls for a telemetry-record emit + `provider_control_chart.py` computing
    rolling per-provider bands + a drift flag consumed by resolver deprioritization, verified by a
    test feeding a synthetic latency spike series and asserting the provider is flagged
    out-of-control.
  - `T2-F5-8` (facet, tier `structural`, basis type `direct`) — "Flight-data-recorder cost
    ledger: append-only, tamper-evident per-call records." Basis: `dod_sketch` calls for an
    append-only + hash-chained telemetry ledger writer + a `verify_ledger` check wired into the
    `/outcome` cost-ledger read path, verified by a test that mutating or deleting an earlier
    record fails chain verification.
  - Consolidation rationale (`docs/plans/plugin-fleet-ideation-2026-07-03/` issue-map,
    `issue-map-final.json`): "Six moonshot-leaning survivors form one closed loop: tamper-evident
    per-call records (T2-F5-8), a benchmark harness, SPC drift detection, Elo-style ratings from
    reconciliation outcomes, a staleness report, and the /retro-gated proposal mechanism
    (T1-F3-7) that applies none of it automatically. Depends on the wave-2 ledger spine, hence
    wave-3 despite the objective's wave-2 home."

### Files expected to change
Indicative only — the exact set is `/plan`'s to determine.
- `plugins/saga/scripts/engine_dispatch_ledger.py` (new) — append-only, hash-chained per-call
  dispatch-fact writer + `verify_ledger` check.
- `plugins/saga/scripts/engine_resolver.py` — call site appending a ledger record at
  `resolve`/`_resolve_capability`.
- `plugins/saga/scripts/engine_benchmark.py` (new) — fixed per-capability eval-suite harness
  emitting registry-diff proposals.
- `plugins/saga/scripts/provider_control_chart.py` (new) — SPC rolling-band reducer over the
  ledger.
- `plugins/saga/scripts/capability_elo.py` (new) — Elo-style updater fed by reconciliation
  win/loss records.
- `plugins/saga/scripts/engine_stale_report.py` (new) — staleness reducer emitting
  corroborated/contradicted/unexercised verdicts.
- `plugins/saga/skills/retro/SKILL.md` — new calibration sub-step aggregating the four signals
  into `/retro`-surfaced, human-applied registry-diff proposals.
- `plugins/saga/references/benchmark-loop.md` (new) — documents the propose-not-commit gate.
- `plugins/saga/.claude-plugin/plugin.json` — version bump.
- `.claude-plugin/marketplace.json` — plugin metadata sync.
- `plugins/saga/CHANGELOG.md` — entry for the ledger, benchmark harness, SPC/Elo/staleness
  reducers, and the `/retro` calibration sub-step.
- `docs/engineering-journal/DECISIONS.md` — entry recording the proposal-only calibration
  posture, with a revisit-when condition.
- `tests/test_engine_dispatch_ledger.py` (new) — chain-verification tests.
- `tests/test_engine_benchmark.py` (new) — benchmark-harness proposal tests.
- `tests/test_provider_control_chart.py` (new) — SPC drift-flag tests.
- `tests/test_capability_elo.py` (new) — Elo updater/selection tests.
- `tests/test_engine_stale_report.py` (new) — staleness-verdict tests.
- `tests/test_saga_retro_calibration.py` (new) — `/retro` calibration-proposal + never-writes
  tests.

### Tests to add or update
- Ledger: chain verification fails on a mutated/deleted earlier record, passes when clean.
- Benchmark: emits a registry-diff proposal (never a write) when measured rating contradicts
  authored rating for a fake provider.
- Staleness: synthetic ledger+registry fixtures produce all three verdicts
  (`corroborated`/`contradicted`/`unexercised`).
- Elo: a provider losing repeated reconciliations drops below a rival and stops being selected
  via the fallback-prior path; the authored `rating` field is untouched.
- SPC: a synthetic latency spike series flags the provider out-of-control; normal variation does
  not flag.
- `/retro` calibration: a run over seeded ledger fragments emits a rating-change proposal with
  `last_validated` bumps; `engine-registry.yaml` is byte-identical before and after the run.

## Grounding References
- source_context: `docs/plans/plugin-fleet-ideation-2026-07-03/survivors/T1.json` (id `T1-F3-7`)
- source_context: `docs/plans/plugin-fleet-ideation-2026-07-03/survivors/T2.json` (ids
  `T2-F1-7`, `T2-F4-7`, `T2-F5-5`, `T2-F5-7`, `T2-F5-8`)
- source_context: `docs/plans/2026-07-03-plugin-fleet-grounding-brief.md` §2 (binding-decision
  register), §8 item 2 (provider/model routing beyond CLI engines — this issue's objective home)

### Acceptance criteria
- [ ] A dispatch-ledger writer appends a hash-chained record for every engine-dispatch call, and
  `verify_ledger` fails when an earlier record is mutated or deleted. Check:
  `uv run pytest tests/test_engine_dispatch_ledger.py -k chain_verification` → passes.
- [ ] The benchmark harness emits a registry-diff proposal (never a write) when a fake provider's
  measured rating contradicts its authored rating. Check:
  `uv run pytest tests/test_engine_benchmark.py -k contradicted_rating` → passes; test asserts no
  mutation to the on-disk `engine-registry.yaml` fixture.
- [ ] The staleness report produces all three verdicts (`corroborated`/`contradicted`/
  `unexercised`) over synthetic ledger+registry fixtures. Check:
  `uv run pytest tests/test_engine_stale_report.py -k all_verdicts` → passes.
- [ ] The Elo updater drops a repeatedly-losing provider below a rival and the fallback-prior
  resolution path stops selecting it, while the authored `rating` field remains unchanged. Check:
  `uv run pytest tests/test_capability_elo.py -k elo_drop_reroutes` → passes.
- [ ] The SPC reducer flags a synthetic sustained latency spike as out-of-control and does not
  flag normal common-cause variation. Check:
  `uv run pytest tests/test_provider_control_chart.py -k spc_drift_flag` → passes.
- [ ] `/retro`'s calibration sub-step emits an aggregated rating-drift proposal (with
  `last_validated` bumps) over seeded ledger fragments, and `engine-registry.yaml` is
  byte-identical before and after the run. Check:
  `uv run pytest tests/test_saga_retro_calibration.py -k proposal_only_never_writes` → passes.
- [ ] `DECISIONS.md` carries an entry for the proposal-only calibration posture with a
  revisit-when condition. Check: `grep -n "revisit-when" docs/engineering-journal/DECISIONS.md`
  → includes a new entry for this change.
- [ ] Release-surface metadata (plugin version, marketplace entry, CHANGELOG) is updated in the
  same PR. Check: `git diff --name-only` includes `plugins/saga/.claude-plugin/plugin.json`,
  `.claude-plugin/marketplace.json`, and `plugins/saga/CHANGELOG.md`.
- [ ] Full suite, format, lint, and types stay green. Check:
  `uv run pytest && uv run ruff format --check . && uv run ruff check . && uv run mypy plugins/ scripts/ tests/ --ignore-missing-imports`
  → all pass.

### Verification
```bash
# Ledger chain-verification, benchmark, staleness, Elo, and SPC reducers
uv run pytest tests/test_engine_dispatch_ledger.py tests/test_engine_benchmark.py \
  tests/test_engine_stale_report.py tests/test_capability_elo.py \
  tests/test_provider_control_chart.py -v

# /retro calibration sub-step: proposal emitted, registry file never written
uv run pytest tests/test_saga_retro_calibration.py -v

# Confirm DECISIONS.md carries the required entry
grep -n "revisit-when" docs/engineering-journal/DECISIONS.md | tail -5

# Full repo gate (CI parity)
uv run pytest && uv run ruff format --check . && uv run ruff check . && uv run mypy plugins/ scripts/ tests/ --ignore-missing-imports
```
Expected: all green; the `/retro` calibration test asserts `engine-registry.yaml`'s on-disk bytes
are unchanged by the run while a rating-change proposal artifact is produced; `DECISIONS.md`
contains a new entry with a revisit-when condition for the proposal-only calibration posture.

### Recommended executor profile
- **Model:** sonnet
- **Effort:** high — *target posture: not a live team-execution dispatch knob until `pf-effort-first-class` lands; teammates inherit session tier until then*
- **Backend:** team-execution
- **External-LLM posture:** none
- **Justification:** This issue lands five new reducer/harness modules plus a `/retro` skill
  extension that must compose correctly around one non-negotiable invariant (no signal ever
  writes the registry) — team-execution's consensus review is the right backend to catch a
  reviewer missing a direct-write path in any of the five new modules, and sonnet/high is
  sufficient because every mechanism (hash-chained ledger, fixed-suite benchmark, SPC control
  charts, Elo updates, staleness joins) is a well-specified, already-precedented pattern (the
  house `outcome_costs.py` leaf-produced-fact discipline, `Registry.stale()`) rather than a novel
  architecture call — no case for opus (no unresolved design ambiguity) or an external engine
  (this is registry-calibration logic and test-writing, not a task an external engine reviews or
  generates with an advantage).

### Release-surface checklist
This issue changes plugin behavior (new dispatch-ledger writer, benchmark harness, SPC/Elo/
staleness reducers, and a new `/retro` calibration sub-step), so the following must land in the
same PR:
- [ ] `plugins/saga/.claude-plugin/plugin.json` — version bump.
- [ ] `.claude-plugin/marketplace.json` — plugin metadata sync.
- [ ] `plugins/saga/CHANGELOG.md` — entry describing the dispatch ledger, benchmark harness, SPC
  drift detection, Elo ratings, staleness report, and the `/retro` calibration sub-step.
- [ ] Drift-guard/lint coverage (`tests/test_saga_retro_calibration.py`) asserting `/retro` never
  writes `engine-registry.yaml` directly, wired into the standard `uv run pytest` CI run so a
  future regression that adds a direct-write path fails CI instead of silently shipping.

### Handoff maturity
requirements-ready

### Suggested next action
Use `/plan <issue>` to create an implementation plan.

### Source context
- Source: `docs/plans/plugin-fleet-ideation-2026-07-03/survivors/T1.json` (id `T1-F3-7`) and
  `docs/plans/plugin-fleet-ideation-2026-07-03/survivors/T2.json` (ids `T2-F1-7`, `T2-F4-7`,
  `T2-F5-5`, `T2-F5-7`, `T2-F5-8`)
- Source type: ideation-survivor
- Source title: Earned ratings: dispatch/benchmark evidence drives retro-gated registry
  calibration (SPC drift, Elo, staleness report)

### Context library links

_none_

### Intent

`plugins/saga/references/engine-registry.yaml` and its loader (`plugins/saga/scripts/engine_registry.py`) hold every external-engine capability rating (`WEAK`/`MODERATE`/`STRONG`, `RATINGS` at `engine_registry.py:22-24`) and `last_validated` date (`EngineEntry.last_validated`, `engine_registry.py:176`) as **authored, single-write oracle data** — nothing in the fleet today re-derives a rating or a staleness signal from what actually happened when an engine was dispatched. Six independently found ideation facets converge on the same closed loop: an append-only, tamper-evident per-call ledger of dispatch facts; a benchmark harness that runs a fixed eval suite against a registry claim; SPC control charts that flag cost/latency drift from that telemetry; an Elo-style rating that moves from reconciliation win/loss outcomes; a staleness report that names which registry cells have no recent corroborating evidence; and the `/retro` sub-step that turns all four signals into human-approved registry-diff proposals — never an automatic write. This issue lands all six as one coherent evidence-to-proposal pipeline, because every one of them either produces or consumes the same ledger and the same non-negotiable seam: nothing but a human, via `/retro`, ever edits `engine-registry.yaml`.

## Created Issue

- URL: https://github.com/infiquetra/infiquetra-claude-plugins/issues/459
- Number: 459
- Created at: 2026-07-04T08:25:48.686819+00:00

