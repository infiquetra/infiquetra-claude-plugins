# Run-fact ledger (`run_fact.v1`)

One append-only, hash-chained, **leaf-produced** ledger of realized-run facts — spend, cache,
engine-usage, delegation — that the fleet's telemetry writers all append into, so there is one canonical
format instead of N. Implemented in `plugins/saga/scripts/run_ledger.py` (#401, objective #338).

## Where it lives

A single file per repo under the git **common** dir, shared across worktrees and **never committed**:
`<git-common-dir>/saga-run-facts/run-facts.jsonl` (resolved via `outcome_store.resolve_common_dir`). It
is a **distinct** file from `outcome_store`'s replay `ledger.jsonl` (which is append-only but un-chained
and exists for crash-replay). Construct a handle with `RunLedger.resolve(repo_root)` or, in tests, with
an explicit `RunLedger(path=...)`.

## Record schema — `run_fact.v1`

Each line is one JSON object. Common fields on every fact:

| Field | Meaning |
|-------|---------|
| `schema` | `"run_fact.v1"` |
| `kind` | one of `spend` \| `cache` \| `engine` \| `delegation` |
| `subplot_id` | the **producing leaf** (facts are leaf-produced, KTD4) |
| `at` | ISO timestamp, caller-supplied (the ledger never reads the clock — deterministic) |
| `prev_hash` | the previous record's `this_hash` (`""` for the genesis record) — chain link |
| `this_hash` | `sha256` over the whole record **including `prev_hash`**, excluding `this_hash` |

Per-kind payload fields (build with `build_fact(kind, subplot_id=, at=, **fields)`):

- **spend** — `tokens`, `tokens_cached`, `tokens_fresh`, `wall_seconds`
- **cache** — cache-hit counts (`cached`, `fresh`) for a reuse view
- **engine** — `engine`, `variant`, `status`, `cost`, `latency_seconds`, `tokens`
  (advisory-call usage), plus optional offload economics fields
  `engine_tokens_avoided`, `chaperone_tokens_spent`, `net_savings_tokens`,
  `net_savings_status`, and `external_cost_usd`
- **delegation** — `evidence` (a **pointer/reference**, never inlined bytes), `engine`

`build_fact` rejects an unknown `kind`, an empty `subplot_id`, and any attempt to set the reserved
`prev_hash`/`this_hash` fields.

## Chain custody — `verify_chain`

`verify_chain(ledger) -> ChainReport(ok, break_index, reason)` recomputes the chain and reports the
first break. It **fails** on:

- an **in-place mutation** of any record field (the recomputed `this_hash` no longer matches), and
- a **reorder or middle-deletion** (a record's `prev_hash` no longer equals its predecessor's `this_hash`).

A torn trailing line (an incomplete append) is dropped by `read_facts` and is **not** a chain break.

**Threat-model bound — tamper-*evidence*, not tamper-*resistance*.** A writer with full file access can
recompute a fresh, internally-consistent chain, and trailing truncation of whole records yields a valid
prefix that still verifies. That is out of scope and acceptable: the store is machine-local and never
committed (the same trust boundary as the rest of `outcome_store`'s cache). The property this ledger
guarantees is that a recorded fact cannot be **silently altered or buried by an in-place edit** — which
is exactly the "a pass cannot be buried, a fail cannot be rewritten away" requirement.

## Derive-on-read views (no committed summary — KTD3)

Computed from the record stream on each call; nothing is persisted as a summary:

- `rollup(ledger, kind=None)` — per-numeric-field `{sum, avg, count}`.
- `reuse_ratio(ledger)` — cached / (cached + fresh) over `spend` facts; **`None`** (a defined empty)
  when there is no spend data.
- `last_n_prior(ledger, kind, field, n)` — average of `field` over the last `n` facts of `kind`; `None`
  when there is no data or `n <= 0`.

## Adoption note — how a future writer emits a fact

A wave-1 writer (e.g. #349 requeue, #366/#367 spend, #386 net-savings) records a fact in two lines:

```python
import run_ledger
ledger = run_ledger.RunLedger.resolve(repo_root)
run_ledger.append_fact(ledger, run_ledger.build_fact(
    "spend", subplot_id=my_subplot_id, at=iso_now,
    tokens=total, tokens_cached=cached, tokens_fresh=fresh, wall_seconds=elapsed,
))
```

Writers already wired (v1): `engine_dispatch.dispatch(..., ledger=, subplot_id=, at=)` records an
`engine` fact on any advisory call and a `delegation` fact for an `agy.delegation.v1` call —
**telemetry only, never a gate** (`{#external-engines-never-gatekeepers}`); omitting the ledger args is a
no-op. `lifecycle_state.recommend_execution_backend(..., ledger=)` surfaces a `last_n_prior` "last N runs
averaged X tokens" prior, additively (the `prior` key appears only when there is data).

**Not yet migrated (deferred):** `outcome_costs.py` keeps its own cost records for now (KTD7); porting it
and adopting the remaining wave-1 writers are follow-up work. This substrate lands empty of most
consumers on purpose so the format is fixed once.
