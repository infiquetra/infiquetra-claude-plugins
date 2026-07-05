---
title: One append-only leaf-produced run-fact ledger substrate (#401)
type: feat
status: active
date: 2026-07-05
origin: https://github.com/infiquetra/infiquetra-claude-plugins/issues/401
---

# One append-only leaf-produced run-fact ledger substrate (#401)

Phase 0 item 10 (final). A single versioned, append-only, **hash-chained**, leaf-produced run-fact
ledger (`run_fact.v1`) that spend / cache / engine-usage / delegation telemetry all write into, plus
derive-on-read views — landed empty of most consumers so the ≥8 wave-1 writers (#349, #351, #366/#367,
#386, #393, …) inherit one format instead of N incompatible ones to reconcile later.

## Problem Frame

`#338` (objective: fleet telemetry and ledger substrate) needs one canonical shape for realized-run
facts. Today cost lives in `outcome_costs.py` (its own `_latest_costs`/`rollup` over
`outcome_store.append_ledger`), engine advisory calls carry cost/latency on `AdvisoryEvidence`
(`engine_dispatch.py:28`) with no durable ledger, and cache reuse is unmeasured. Building the substrate
now — before the wave-1 writers exist — is the whole point: it fixes the format once. Per
`#outcome-economics-stance`, cost is a **leaf-produced ledger fact** the coordinator only aggregates;
per derive-on-read, there is **no committed status/summary field**.

## Requirements

- **R1.** A versioned `run_fact.v1` record schema with a `kind` discriminator covering four fact kinds:
  `spend` (tokens, cached/fresh token split, wall seconds), `cache` (reuse-ratio inputs: cached vs
  fresh counts/tokens), `engine` (advisory-call engine id, cost, latency), `delegation` (evidence
  pointer). Every fact is **leaf-produced** and carries its producing `subplot_id` + `at` timestamp.
- **R2.** An append-only, **hash-chained** writer: `append_fact(store, fact)` appends one record with a
  `prev_hash`→`this_hash` chain link, using the same durable-append discipline as the existing replay
  ledger (`resolve_common_dir()` git-common-dir carrier, `O_APPEND`, torn-trailing-line tolerant). A
  distinct file from `outcome_store`'s replay `ledger.jsonl` (different purpose).
- **R3.** `verify_chain(store) -> bool|report` recomputes the chain and **fails on any mutation,
  reorder, or deletion** of a prior record — a passed record cannot be silently altered and a failed
  fact cannot be buried by rewriting history (tamper-evidence).
- **R4.** Derive-on-read views over the fact stream (no committed summary): `rollup` (per-field
  aggregate), `reuse_ratio` (cached vs fresh, with a defined empty result when there is no data), and
  `last_n_prior(kind, field, n)` ("last N runs averaged X").
- **R5.** Two real consumers wired: (a) an `engine` fact written from `engine_dispatch`'s
  `AdvisoryEvidence` on an advisory call; (b) a `delegation` fact carrying the evidence pointer at the
  delegation point. The engine fact is **telemetry, never gating** (`#external-engines-never-gatekeepers`).
- **R6.** The `/plan` tier recommendation surfaces a ledger-derived prior ("last N runs averaged X
  tokens") from `last_n_prior`, with a defined no-data fallback.
- **R7.** A schema doc + adoption note (how a future writer emits a `run_fact.v1`) and a DECISIONS entry.
- **R8.** Release surfaces for saga: plugin.json bump, marketplace regen, CHANGELOG, version-literal
  drift-guard, execution-order row 10, work-session.

## Key Technical Decisions

**KTD1 — the module is saga-local (`plugins/saga/scripts/run_ledger.py`), not fleet-commons.** Every
consumer in scope — `engine_dispatch.py`, the `/plan` tiering surface, `outcome` — lives in saga.
Unlike the #348 retry primitive (fleet-commons *because* unifi, a different plugin, consumed it), there
is no cross-plugin consumer here, so vendoring a shim would be dead ceremony. Precedent: `manifest_store.py`
(saga-scoped git-common-dir store) and `outcome_costs.py` (saga-local ledger over `outcome_store`).
Fleet-wide adoption is a documented follow-up (R7 adoption note), not this issue.

**KTD2 — a distinct hash-chained `run-facts.jsonl`, separate from the replay `ledger.jsonl`.** The
existing `outcome_store` replay ledger (`ledger.jsonl`, `append_ledger`/`read_ledger`,
`outcome_store.py:408/429`) is append-only + torn-tail tolerant but **not** hash-chained and serves
crash-replay (R30). The run-fact ledger is a **distinct** tamper-evident telemetry ledger: it **reuses
the storage discipline** (`resolve_common_dir()`, `O_APPEND`, `_heal_torn_tail`) but writes its own
namespaced file and adds the `prev_hash`/`this_hash` chain. Do not overload the replay ledger.

**KTD3 — derive-on-read views, no committed status/summary.** `rollup`/`reuse_ratio`/`last_n_prior` are
computed from the record stream on each read, mirroring `outcome_costs._latest_costs`/`rollup`
(`outcome_costs.py:94/153`). Binding: `#outcome-economics-stance` derive-on-read — a committed summary
field is forbidden (it would be the same dead-wiring/stale-state class the outcome model already rejects).

**KTD4 — leaf-produced facts; the coordinator only aggregates.** Each fact carries the producing
`subplot_id`. The coordinator never writes a fact; it reads via the derive-on-read views. Binding:
`#outcome-economics-stance`.

**KTD5 — the `engine` fact is telemetry, never a gate.** Writing an engine-usage fact must not change
dispatch/gate behavior. Binding: `#external-engines-never-gatekeepers` (Claude stays verifier-of-record;
an external engine's recorded cost never gates).

**KTD6 — schema versioning: `run_fact.v1` + a `kind` discriminator, forward-tolerant readers.** The
record carries `schema: "run_fact.v1"` and `kind`. Readers tolerate unknown kinds/fields and a torn
trailing line (never crash on a partially-written or newer-schema record). A `v2` is additive follow-up.

**KTD7 — no migration of `outcome_costs.py` in this issue (non-goal).** `run_ledger` coexists with the
existing cost store; porting `outcome_costs`/`outcome_store` cost records onto the new ledger, and
adopting the ≥8 wave-1 writers, are explicitly deferred. This issue lands the substrate + 2 consumers.

## Implementation Units

### U1. `run_ledger.py` core — schema + hash-chained append + verify

`plugins/saga/scripts/run_ledger.py`: a `RunFact` shape (frozen dataclass or TypedDict) with
`schema="run_fact.v1"`, `kind` ∈ {spend, cache, engine, delegation}, `subplot_id`, `at`, and the
per-kind numeric/pointer fields; `append_fact(store, fact)` (hash-chained: `this_hash =
H(prev_hash + canonical(fact))`, `O_APPEND`, git-common-dir via `resolve_common_dir()`, torn-tail
tolerant); `read_facts(store)`; `verify_chain(store)`. Follow `manifest_store.py`'s store/`resolve_common_dir`
pattern; reuse `outcome_store._heal_torn_tail` discipline (do not re-implement torn-tail healing —
import or mirror it).

**Test scenarios** (`tests/test_run_ledger.py`): a fact of each of the 4 kinds round-trips through
append→read with all its fields (schema-covers-all-kinds); a second append chains onto the first
(`prev_hash` == the first's `this_hash`); `verify_chain` returns pass on an untouched ledger; **custody
chain: a mutated or deleted prior record makes `verify_chain` FAIL** (a pass cannot be buried, a fail
cannot be rewritten away); a torn trailing line is tolerated (read/verify do not crash).

### U2. Derive-on-read views

In `run_ledger.py`: `rollup(store, kind=None)` (per-field aggregate over facts), `reuse_ratio(store)`
(cached vs fresh from `spend`/`cache` facts; a **defined empty result**, not a crash, when there is no
data), `last_n_prior(store, kind, field, n)` ("last N runs averaged X"). No committed summary; compute
on read (KTD3). Mirror `outcome_costs.rollup`.

**Test scenarios:** `reuse_ratio` over known cached/fresh facts returns the expected ratio; `reuse_ratio`
with **no data** returns the defined empty (e.g. `None`/`0.0` per the schema doc), not an error;
`last_n_prior` averages the last N and ignores older records.

### U3. Consumer 1 — engine-usage fact from `engine_dispatch`

Wire an `engine` `run_fact` write from `engine_dispatch.py`'s `AdvisoryEvidence` (`:28`) path (advisory
engine id + cost + latency + tokens → `append_fact`). **Telemetry only** — no change to
`satisfy_gate`/dispatch behavior (KTD5). Inject the ledger store so the write is unit-testable and a
missing/None store is a no-op (never breaks dispatch).

**Test scenarios:** an advisory call writes exactly one `engine` fact with the engine id/cost/latency;
dispatch/gate behavior is unchanged whether or not a store is present (telemetry-not-gate).

### U4. Consumer 2 — delegation-evidence fact

Write a `delegation` `run_fact` carrying the evidence pointer at the `engine_dispatch` delegation/evidence
point (the concrete in-saga delegation surface; the team-execution evidence path is a documented
alternative home, not required for v1). Evidence pointer is a reference, not inlined bytes.

**Test scenarios:** a delegation records a `delegation` fact whose evidence pointer resolves to the
delegated run's evidence; absence of a store is a no-op.

### U5. `/plan` tier-table ledger prior

Surface a `last_n_prior`-derived prior ("last N runs averaged ~X tokens") in the `/plan` tier
recommendation surface (the `recommend_execution_backend` / tiering path). Read-only over the ledger;
a **defined no-data fallback** (the tier recommendation still works with an empty ledger).

**Test scenarios:** with N prior facts, the tier surface reports the averaged prior; with **no ledger
data**, it falls back cleanly (no crash, tier recommendation unchanged).

### U6. Schema doc + adoption note + DECISIONS

`plugins/saga/references/run-fact-ledger.md` — the `run_fact.v1` schema (all 4 kinds), the hash-chain +
`verify_chain` contract, the derive-on-read views, and an **adoption note** (how a future wave-1 writer
emits a fact). DECISIONS `{#run-fact-ledger-401}` (KTD1-KTD7). **Test expectation: none** (docs; covered
by the drift-guard + U1-U5 tests).

### U7. Release surfaces + writeback

saga plugin.json bump + CHANGELOG (`## [X.Y.Z] - YYYY-MM-DD`); regen `marketplace.json`
(`scripts/sync_marketplace.py`); version-literal drift-guard (`tests/test_saga_plugin.py`);
execution-order row 10 `[x]`; work-session. **Test expectation: none** (release metadata; drift-guard
asserts the version).

## Scope Boundaries

**In:** the `run_fact.v1` schema + hash-chained append/read/`verify_chain`; derive-on-read
rollup/reuse-ratio/prior; two real consumers (engine-usage, delegation-evidence); the `/plan` tier
prior; schema doc + adoption note; saga release surfaces.

**Out (true non-goals):**
- Migrating `outcome_costs.py` / `outcome_store` cost records onto the new ledger (KTD7).
- Adopting the ≥8 wave-1 writers (#349, #351, #366/#367, #386, #393, …) — the substrate lands empty.
- A `bridge_receipt.v1` or any second schema; a dashboard/visualization; any gating behavior change.
- Fleet-commons vendoring (KTD1 — saga-local until a cross-plugin consumer exists).

**Deferred to Follow-Up Work:**
- Fleet-wide adoption + a fleet-commons move if/when a non-saga plugin needs to write facts.
- `outcome_costs` → `run_ledger` migration (its own issue).

## Definition of Done

- `run_ledger.py` lands with the `run_fact.v1` schema, hash-chained `append_fact`/`read_facts`/
  `verify_chain`, and the three derive-on-read views; a mutated/deleted record makes `verify_chain`
  fail; two real consumers write facts; the `/plan` tier surface shows a ledger prior with a no-data
  fallback; schema doc + adoption note + DECISIONS present.
- Full gate green: `uv run pytest && uv run ruff format --check . && uv run ruff check . && uv run mypy
  plugins/ scripts/ tests/ --ignore-missing-imports && uv run bandit -r plugins/`; saga release surfaces
  in lockstep; execution-order row 10 `[x]`.

## Backend recommendation

**inline** (cheapest-correct). This is a bounded, sequential substrate build (one new module + two
consumer wirings + derive-on-read views + a tier-surface read + docs + tests) with its KTDs pre-resolved
by the issue's binding decisions — no gated-consensus need and no broad enumerated fan-out. The standard
programmatic `/code-review` gate (readonly-verifier panel, with a custody-chain / tamper-evidence lens)
provides the review depth. The issue's indicative `sonnet/high/team-execution` is surfaced as the
alternative; team-execution's value (a verdict that blocks/persists) is not warranted here. Destination:
merge.
