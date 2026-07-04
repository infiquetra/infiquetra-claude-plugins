---
title: "capability: One append-only leaf-produced run-fact ledger substrate for spend, cache, engine, and delegation telemetry"
repo: infiquetra-claude-plugins
type: capability
team: campps
project: operations
status: Idea
labels: capability, hermes-task, needs-plan
risk: medium
handoff_maturity: requirements-ready
tier: structural
wave: wave-2
objective: Build the fleet telemetry and ledger substrate
type: capability
---

# capability: One append-only leaf-produced run-fact ledger substrate for spend, cache, engine, and delegation telemetry

### Objective
Build the fleet telemetry and ledger substrate

### Tier
structural

### Wave
wave-2

### Problem / motivation (grounded)

The fleet has grown several independent, purpose-built ledgers that all share the same
producer/consumer shape — a leaf reports a fact as it finishes, a coordinator only aggregates —
but there is no shared substrate, so each one reinvents schema, append semantics, and
derive-on-read compliance from scratch, and several telemetry gaps (cache economics, engine
usage, delegation evidence) have no ledger at all yet:

- `plugins/saga/scripts/outcome_costs.py:41` (`_NUMERIC_FIELDS = ("tokens", "wall_seconds",
  "operator_touches", "retries")`) is today's only realized cost ledger. It has no
  `cached_tokens`/`fresh_tokens` split, so the residency/cache-scheduling architecture landed by
  `{#worker-cache-scheduling}` (2026-06-27) has no falsifiable measurement of whether it actually
  reduces spend — the ledger cannot currently tell a reused-prefix run from a cold one.
- `plugins/saga/scripts/outcome_costs.py:44` (`record_cost`) and `plugins/saga/scripts/outcome.py:644-645`
  (the `cost_processor` that materializes the rollup into `spec.cost_rollup` after dispatch/harvest)
  establish the exact producer/consumer pattern this ledger substrate generalizes: leaf reports,
  coordinator only aggregates and materializes, per the bound `#outcome-economics-stance` decision
  ("cost is a LEAF-produced ledger fact, not coordinator-computed") — but this pattern currently
  exists only for `/outcome`'s cost rollup, not for engine usage, cache reuse, or delegation
  evidence.
- `plugins/saga/scripts/engine_dispatch.py:28` (`AdvisoryEvidence`) and its consumers
  (`build_dispatch_manifest`, `satisfy_gate` at `:281`) record every external-engine advisory call's
  disposition today, but nothing turns that call into a durable, queryable cost/latency fact — an
  advisory dispatch's tokens and wall time are not captured anywhere a later `/plan` or `/optimize`
  pass can read them back as a prior.
- `plugins/saga/references/engine-registry.yaml:6` states engine tier claims are "re-validated by
  use through `/retro` (R21), NOT by an automated measurement loop" — i.e. today's tier
  recommendations are re-reasoned from scratch each time rather than citing accumulated fact,
  because no fact store exists to cite.
- `plugins/saga/scripts/manifest_store.py` (git-common-dir-carried, versioned append/read/list
  store — `plugins/saga/CHANGELOG.md:183-194`) is the fleet's closest existing precedent for an
  append-only, saga-scoped store, but it is schema-scoped to provenance manifests, not general
  run facts — it is not a fit for spend/cache/engine/delegation telemetry without a dedicated
  ledger of its own.
- Ideation identified this as a negative-space consolidation target: the fleet pool surfaced 45
  distinct ledger-shaped ideas and 19 receipt-shaped ideas across themes (spend, cache, engine
  usage, delegation evidence, review evidence) with no shared substrate underneath any of them
  (`docs/plans/plugin-fleet-ideation-2026-07-03/pool-final.json`, id `G-negative-space-2`) — each
  would otherwise ship its own bespoke append/verify/query code.

## Definition of Done

Merged PR that:

1. Adds `run_ledger.py`: a versioned (`run_fact.v1`), append-only, leaf-produced record schema and
   writer helper covering four fact kinds — spend (tokens, cached/fresh split, wall time), cache
   (reuse ratio inputs), engine usage (advisory-call cost/latency), and delegation (evidence
   pointer) — plus a hash-chained `verify_chain()` that fails when a prior record is
   overwritten/deleted and passes on an honest append-only sequence.
2. Adds derived-view helpers (rollup, "last N runs averaged X" prior, cached-vs-fresh reuse ratio)
   that read the ledger on demand — no committed status/summary field is written anywhere; all
   views are derived-on-read per `#outcome-economics-stance` and the `/outcome` campaign's
   derive-on-read binding.
3. Wires the ledger as the write path for at least two real consumers currently missing one:
   engine-usage facts from `engine_dispatch.py`'s `AdvisoryEvidence` path, and a delegation-evidence
   entry consumed by the review/evidence ledger — proving the substrate is load-bearing, not
   speculative.
4. Adds a `/plan` tier-table step (or equivalent surfaced prior) that reads accumulated ledger facts
   and renders a "last N runs averaged X" line alongside a tier recommendation, replacing pure
   re-reasoning with a cited prior per `engine-registry.yaml:6`'s gap.
5. Adds `docs/plans/.../run-ledger-schema.md` (or equivalent) documenting the `run_fact.v1` schema
   and an adoption note for future ledger-shaped issues to write through this substrate instead of
   inventing their own.
6. Is verified by: schema + append-only immutability tests, a cached-vs-fresh reuse-ratio
   computation test (including the "no data yet" case when fields are absent), and a real run
   artifact showing an estimate-vs-actual spend view rendered from ledger data.

### Acceptance criteria
- [ ] `run_fact.v1` schema covers all four fact kinds (spend, cache, engine usage, delegation
      evidence) in one shared record shape with a `kind` discriminator. Check:
      `uv run pytest tests/test_run_ledger.py -k schema_covers_all_kinds` → passes. *(covers
      G-hybrids-1, primary — unified run-fact ledger spine)*
- [ ] The ledger is append-only: attempting to mutate or delete a prior record fails
      `verify_chain()`, while an honest append-only sequence verifies clean. Check:
      `uv run pytest tests/test_run_ledger.py -k append_only_immutability` → passes; a mutation
      test asserts `verify_chain()` raises. *(covers G-negative-space-2 — consolidation substrate
      under today's 45 ledger-shaped and 19 receipt-shaped ideas)*
- [ ] A `run_fact.v1` spend record carries distinct `cached_tokens` and `fresh_tokens` fields, and
      a derived view computes a reuse ratio from them; when both fields are absent (no telemetry
      yet), the view reports "no data yet" rather than a fabricated ratio or a crash. Check:
      `uv run pytest tests/test_run_ledger.py -k cached_fresh_reuse_ratio` → passes for both the
      populated and the absent-fields case. *(covers T4-F4-6 — cached-vs-fresh token fields so
      residency's value is falsifiable)*
- [ ] A `/plan` tier-table run against a ledger seeded with prior facts for a matching work-shape
      surfaces a "last N runs averaged X" prior line instead of re-reasoning the tier from scratch.
      Check: `uv run pytest tests/test_plan_tier_table.py -k ledger_prior_surfaced` → passes.
      *(covers H-F4-4 — fleet-wide cost-fact ledger so tier recommendations cite priors)*
- [ ] Every `engine_dispatch.py` `AdvisoryEvidence`-producing call writes a leaf-produced
      engine-usage `run_fact.v1` record (cost + latency) through the shared ledger. Check:
      `uv run pytest tests/test_saga_engine_dispatch.py -k advisory_call_writes_ledger_fact` →
      passes. *(covers T2-F4-6 — dispatch-fed engine-usage ledger)*
- [ ] A delegation-evidence entry written through the ledger is hash-chained: a later PASS record
      cannot bury, overwrite, or otherwise erase an earlier FAIL record for the same delegation
      chain — verified by an explicit adversarial test. Check: `uv run pytest
      tests/test_run_ledger.py -k custody_chain_pass_cannot_bury_fail` → passes. *(covers
      T15-F2-8 — hash-chain append-only chain-of-custody for delegation evidence)*
- [ ] No committed status/summary field is written anywhere in the ledger substrate or its
      consumers — every view (rollup, reuse ratio, prior) is computed on read from the append-only
      record stream. Check: `grep -rn "cost_rollup\s*=" plugins/saga/scripts/run_ledger.py` returns
      nothing outside a documented derive-on-read helper (no assignment to a persisted summary
      field); code review confirms no new committed status field.
- [ ] A real run artifact (from an actual `/work` or team-execution exit) renders an
      estimate-vs-actual spend view sourced from ledger data. Check: PR description links or embeds
      one such rendered artifact.
- [ ] Full suite, format, lint, and types stay green. Check: `uv run pytest && uv run ruff format
      --check . && uv run ruff check . && uv run mypy plugins/ scripts/ tests/
      --ignore-missing-imports` → all pass.

### Out-of-scope / non-goals
**In scope:**
- `run_ledger.py` — schema, append writer, hash-chain `verify_chain()`, and derived-view helpers
  (rollup, reuse ratio, "last N runs" prior).
- Wiring two real consumers through the ledger: `engine_dispatch.py`'s advisory-call path and a
  delegation/review-evidence entry.
- A `/plan` tier-table step surfacing ledger priors.
- Schema documentation and an adoption note for future ledger-shaped work.

**Non-goals / explicitly out of scope:**
- Migrating `/outcome`'s existing `outcome_costs.py` / `spec.cost_rollup` pipeline onto the new
  substrate in this PR — that pipeline stays as-is; this issue adds the shared substrate and wires
  new, currently-missing consumers (engine usage, delegation evidence) onto it. A follow-up
  migration of the `/outcome` cost path is out of scope here.
- Migrating all 45 ledger-shaped / 19 receipt-shaped ideas from the pool onto this substrate — this
  issue proves the substrate with two real consumers; broader fleet-wide migration is future work
  tracked by the adoption note this issue ships.
- Building `bridge_receipt.v1` or any bridge-specific proof-of-execution contract — that is a
  separate, already-drafted capability (`pf-delegation-receipt-contract.md`); this issue supplies
  the underlying fact-storage substrate a receipt could write through, it does not define the
  receipt schema itself.
- A standing measurement/calibration dashboard over ledger data — this ships the substrate and its
  derived-view helpers, not an ongoing monitoring service.
- Changing who is verifier-of-record or team residency/scheduling architecture — this is a
  telemetry substrate, not a scheduling or gating change; `{#worker-cache-scheduling}` and
  `{#external-engines-never-gatekeepers}` stay as decided.

## Grounding References

- Absorbed ideas:
  - `G-hybrids-1` (primary) — "One leaf-produced run-fact ledger spine serving spend, cache,
    engine, and delegation telemetry" (`docs/plans/plugin-fleet-ideation-2026-07-03/survivors/T12.json`,
    `pool-final.json`). `basis_type: reasoned`; parents `T12-F4-5`, `T4-F3-5`, `T2-F4-6`,
    `T15-F2-8`, `H-F4-4`. `dod_sketch`: merged `run_ledger.py` (versioned append-only
    leaf-produced records incl. `cached_tokens`/`fresh_tokens`, engine and delegation facts) +
    derived-view helpers wired into `/work` and team-execution exits, honoring derive-on-read.
  - `G-negative-space-2` (facet) — "One append-only ledger substrate under the pool's 45 ledgers
    and 19 receipts" (`docs/plans/plugin-fleet-ideation-2026-07-03/survivors/OTHER.json`,
    `pool-final.json`). `basis_type: direct`; `dod_sketch`: merged PR — `fleet_ledger.py`
    (hash-chained JSONL append/verify/query) + a ledger-kinds registry doc + two migrated
    consumers; verified by a conformance test proving a later PASS row cannot mutate/overwrite an
    earlier FAIL row.
  - `T4-F4-6` (dedup-merged) — "Add cached-vs-fresh token fields to the cost ledger so residency's
    value is falsifiable" (`docs/plans/plugin-fleet-ideation-2026-07-03/survivors/T4.json`).
    `basis_type: direct`.
  - `H-F4-4` (dedup-merged) — "Fleet-wide cost-fact ledger so tier recommendations cite priors
    instead of re-reasoning" (`docs/plans/plugin-fleet-ideation-2026-07-03/survivors/T12.json`).
    `basis_type: direct`; `dod_sketch`: merged append-only cost-fact JSONL ledger schema + writer
    helper + `/plan` tier-table step surfacing ledger priors; verified by a test that seeded
    ledger rows produce a "last N runs averaged X" prior line on the matching work-shape.
  - `T2-F4-6` (dedup-merged) — "Dispatch-fed engine-usage ledger — every advisory call a
    leaf-produced cost/latency fact" (`docs/plans/plugin-fleet-ideation-2026-07-03/survivors/T2.json`).
    `basis_type: direct`; thin seed in the survivors file (no `idea`/`basis` body captured) —
    intent reconstructed from its title, its `axis: cost-latency-telemetry`, and grounding brief
    §7 (recurring-pain synthesis on cost/latency visibility) plus the parallel `T2-F2-8`
    break-even-guard entry in the same theme, which depends on the same dispatch-fed ledger
    existing.
  - `T15-F2-8` (dedup-merged) — "Cross-bridge append-only chain-of-custody ledger for delegation
    evidence" (`docs/plans/plugin-fleet-ideation-2026-07-03/survivors/T15.json`). `tier_guess:
    moonshot`; `dod_sketch`: merged PR adds `custody_ledger.py` (content-address + hash-chain
    append) over `manifest_store.py` + `verify_chain()`; verified by a test that
    overwriting/deleting a prior evidence entry fails `verify_chain` while an honest append-only
    sequence verifies clean. Canonical hash-chain-ledger idea for its theme (dedup-kept over
    `T15-F3-7`, `T15-F5-7`, `T15-F6-6`, all killed as duplicates of this id).
- Consolidation rationale (issue-map, `G-hybrids-1` node): the fleet's cost ledger
  (`outcome_costs.py`), the missing cache-reuse telemetry, the missing engine-usage ledger, and the
  missing delegation-evidence chain-of-custody all share one producer/consumer shape — a leaf
  reports as it finishes, a coordinator only aggregates/materializes on read — so building four
  bespoke stores would duplicate append/verify/schema code four times; one substrate underneath
  all four closes that duplication before any of the four ships independently.
- Binding decisions this capability builds on and must not violate:
  - `#outcome-economics-stance` (`docs/engineering-journal/DECISIONS.md:718`) — cost is a
    LEAF-produced ledger fact, never coordinator-computed; the coordinator only aggregates
    (`rollup`) and materializes into a canonical field guarded on change. This ledger substrate
    generalizes that exact shape to the other three fact kinds.
  - `/outcome` campaign (U1–U11) derive-on-read binding — status/summaries are never committed
    fields; this substrate's rollup/reuse-ratio/prior views must all be computed on read from the
    append-only stream, never persisted as authoritative state.
  - `{#worker-cache-scheduling}` (2026-06-27, `docs/engineering-journal/DECISIONS.md:1950`) — cache
    economics architecture (derive saga-side, reside team-side) is already settled; this issue adds
    the missing falsifiability measurement (cached/fresh split) for that architecture, it does not
    revisit the scheduling design itself.
  - `{#external-engines-never-gatekeepers}` (#283) — external engines remain advisory/generator
    only; the engine-usage ledger fact this issue adds is a telemetry record of an advisory call,
    not a change to gating authority.
- Current-state code citations verified during grounding (2026-07-03):
  - `plugins/saga/scripts/outcome_costs.py:41` (`_NUMERIC_FIELDS`, no cached/fresh split today).
  - `plugins/saga/scripts/outcome_costs.py:44` (`record_cost`, the existing leaf-produced-fact
    precedent).
  - `plugins/saga/scripts/outcome.py:644-645` (`cost_processor` materializing `spec.cost_rollup`
    post-dispatch/harvest).
  - `plugins/saga/scripts/outcome_spec.py:372` (`cost_rollup` field on the canonical spec).
  - `plugins/saga/scripts/engine_dispatch.py:28` (`AdvisoryEvidence` dataclass) and `:281`
    (`satisfy_gate`) — advisory-call disposition path with no cost/latency fact capture today.
  - `plugins/saga/references/engine-registry.yaml:6` — tier claims "re-validated by use through
    `/retro` (R21), NOT by an automated measurement loop," the gap `H-F4-4` closes.
  - `plugins/saga/scripts/manifest_store.py` and `plugins/saga/CHANGELOG.md:183-194` — the
    fleet's closest existing append-only-store precedent, schema-scoped to provenance manifests
    only (not a fit for general run facts without a dedicated ledger).
  - `docs/plans/plugin-fleet-ideation-2026-07-03/pool-final.json` — 45 ledger-shaped and 19
    receipt-shaped ideas surfaced across the pool, the negative-space evidence for
    `G-negative-space-2`.

### Recommended executor profile

- **Model:** sonnet
- **Effort:** high — *target posture: not a live team-execution dispatch knob until `pf-effort-first-class` lands; teammates inherit session tier until then*
- **Backend:** team-execution
- **External-LLM posture:** none
- **Justification:** not applicable above sonnet — the schema shape, append-only semantics, and
  the two consumer wiring points are already fully specified across the absorbed ideas'
  `dod_sketch`es; this is a bounded substrate-and-two-consumers build with no open design
  ambiguity requiring opus-tier judgment. `team-execution` backend (rather than inline) is
  recommended because the DoD spans four coordinated pieces (schema module, two consumer wirings,
  a `/plan` step, and documentation) that benefit from validator-gated sequencing.

### Release-surface checklist (plugin behavior changes — required)

- [ ] `plugins/saga/.claude-plugin/plugin.json` — version bump + description update reflecting the
      new `run_ledger.py` substrate and the `/plan` tier-table prior-surfacing step.
- [ ] `.claude-plugin/marketplace.json` — saga plugin entry's version/description kept in sync
      with the bump above.
- [ ] `plugins/saga/CHANGELOG.md` — entry documenting `run_fact.v1`, the append-only/hash-chain
      guarantee, the two newly-wired consumers (engine usage, delegation evidence), and the
      `/plan` prior-surfacing step.
- [ ] Version/metadata drift-guard tests (if present in `tests/`) updated or added to assert
      `plugin.json` / `marketplace.json` / `CHANGELOG.md` tell the same story as the diff.

### Files expected to change

Indicative only — exact set is `/plan`'s to determine.

- `plugins/saga/scripts/run_ledger.py` — new schema + append writer + `verify_chain()` + derived
  views (proposed path).
- `plugins/saga/scripts/engine_dispatch.py` — `AdvisoryEvidence` path wired to write a
  `run_fact.v1` engine-usage record.
- `plugins/saga/skills/plan/` (or `plugins/saga/scripts/` tier-table step) — surfaces "last N runs
  averaged X" prior from ledger data.
- A delegation/review-evidence consumer wired to write through the ledger (exact module
  determined during planning — candidate: the evidence ledger referenced in team-execution's
  validator path).
- `docs/plans/.../run-ledger-schema.md` (or equivalent) — schema + adoption-note documentation
  (proposed path).
- `tests/test_run_ledger.py` — schema, append-only immutability, reuse-ratio, and custody-chain
  tests (new).
- `tests/test_saga_engine_dispatch.py` — advisory-call-writes-ledger-fact case (extended).
- `tests/test_plan_tier_table.py` — ledger-prior-surfaced case (new or extended).

### Tests to add or update

- Schema test: `run_fact.v1` record validates for all four fact kinds under one discriminated
  shape.
- Append-only immutability test: mutating/deleting a prior record fails `verify_chain()`; an
  honest append-only sequence verifies clean.
- Cached-vs-fresh reuse-ratio test: populated fields compute a ratio; absent fields report
  "no data yet" rather than crashing or fabricating a value.
- Tier-table prior test: seeded ledger rows produce a "last N runs averaged X" line for a matching
  work-shape.
- Engine-dispatch test: every `AdvisoryEvidence`-producing call writes a ledger record.
- Custody-chain test: a later PASS record cannot bury/overwrite an earlier FAIL record for the
  same delegation chain.

### Verification

```bash
uv run pytest tests/test_run_ledger.py -v
uv run pytest tests/test_saga_engine_dispatch.py -k ledger -v
uv run pytest tests/test_plan_tier_table.py -k ledger_prior -v
uv run pytest && uv run ruff format --check . && uv run ruff check . && uv run mypy plugins/ scripts/ tests/ --ignore-missing-imports
```

Expected: all green; the append-only test fails only when a mutation path is deliberately
introduced into `run_ledger.py` (verify by temporarily adding an in-place mutation and confirming
`verify_chain()` goes red, then reverting).

### Handoff maturity
requirements-ready

### Suggested next action
Use `/plan <issue>` to create an implementation plan.

### Source context
- Source: /private/tmp/claude-501/-Users-jefcox-workspace-infiquetra-infiquetra-claude-plugins/c23d3bf9-9081-4727-8e0d-140ebc73f63f/scratchpad/ideation/issue-map/issue-map-final.json
  (slug: `pf-run-fact-ledger`; absorbed ids: `G-hybrids-1` (primary), `G-negative-space-2`,
  `T4-F4-6`, `H-F4-4`, `T2-F4-6`, `T15-F2-8` (dedup-merged facets))
- Source type: ideation issue-map
- Source title: One append-only leaf-produced run-fact ledger substrate for spend, cache, engine,
  and delegation telemetry

### Context library links

_none_

### Intent

The fleet has grown several independent, purpose-built ledgers that all share the same producer/consumer shape — a leaf reports a fact as it finishes, a coordinator only aggregates — but there is no shared substrate, so each one reinvents schema, append semantics, and derive-on-read compliance from scratch, and several telemetry gaps (cache economics, engine usage, delegation evidence) have no ledger at all yet:

## Created Issue

- URL: https://github.com/infiquetra/infiquetra-claude-plugins/issues/401
- Number: 401
- Created at: 2026-07-04T08:01:57.951377+00:00

