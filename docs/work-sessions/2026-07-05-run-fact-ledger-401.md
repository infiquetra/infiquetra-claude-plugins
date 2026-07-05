# Work session — Run-fact ledger substrate (#401)

- **Date:** 2026-07-05
- **Issue:** [#401](https://github.com/infiquetra/infiquetra-claude-plugins/issues/401) — Phase 0 item 10 (final)
- **Plan:** `docs/plans/2026-07-05-run-fact-ledger-401-plan.md`
- **Doc-review:** `docs/reviews/2026-07-05-run-fact-ledger-401-doc-review.md` (READY; 5 fixes applied in-plan)
- **Backend:** inline
- **Branch:** `feat/pf-run-fact-ledger-401`
- **Destination:** merge

## What was built (by U-ID)

- **U1** — `plugins/saga/scripts/run_ledger.py` (new, saga-local, stdlib-only): `run_fact.v1` schema
  (`build_fact`, `kind` ∈ spend|cache|engine|delegation, leaf-produced), hash-chained `append_fact`
  (`prev_hash`→`this_hash`, `resolve_common_dir` + `O_APPEND` + reuse of `outcome_store._heal_torn_tail`
  in a distinct `run-facts.jsonl`), `read_facts`, `verify_chain` (`ChainReport`).
- **U2** — derive-on-read views `rollup` / `reuse_ratio` (None on no data) / `last_n_prior`; no committed
  summary.
- **U3** — `engine_dispatch.dispatch(ledger=, subplot_id=, at=)` records an `engine` fact (telemetry
  only, no-op without a ledger; consolidated `dispatch`'s two evidence returns into one + a telemetry
  hook, byte-identical returns).
- **U4** — a `delegation` fact for an `agy.delegation.v1` call, carrying a content-addressed evidence
  pointer (`_evidence_pointer`); a non-delegation advisory call writes no delegation fact.
- **U5** — `lifecycle_state.recommend_execution_backend(ledger=, prior_n=)` attaches a `last_n_prior`
  "prior" key only when data exists (byte-identical with no ledger/data); lazy `run_ledger` import keeps
  `lifecycle_state` light.
- **U6** — `plugins/saga/references/run-fact-ledger.md` (schema, chain custody + threat-model bound,
  views, adoption note) + DECISIONS `{#run-fact-ledger-401}` (KTD1-KTD7).
- **U7** — saga 0.60.0 → **0.61.0**; marketplace regen (9 entries, parity OK); CHANGELOG; drift-guard
  literal `tests/test_saga_plugin.py`; execution-order row 10 `[x]`.

## Key decisions

- KTD1 saga-local (not fleet-commons); KTD2 distinct hash-chained ledger reusing outcome_store's
  discipline; KTD3 derive-on-read; KTD5 engine fact is telemetry not a gate. Tamper-evidence (not
  resistance) — verify_chain catches in-place mutation/reorder/middle-deletion, documented bound.

## Files modified

- `plugins/saga/scripts/run_ledger.py` (new)
- `plugins/saga/scripts/engine_dispatch.py` (dispatch telemetry hook + `_record_advisory_facts`)
- `plugins/saga/scripts/lifecycle_state.py` (recommend_execution_backend prior)
- `tests/test_run_ledger.py` (new), `tests/test_saga_engine_dispatch.py` (+5), `tests/test_saga_execution_spec.py` (+3)
- `plugins/saga/references/run-fact-ledger.md` (new)
- release surfaces: `plugin.json`, `.claude-plugin/marketplace.json`, saga `CHANGELOG.md`, `tests/test_saga_plugin.py`
- `docs/engineering-journal/DECISIONS.md`, `docs/plans/2026-07-04-plugin-fleet-execution-order.md`
- `docs/plans/2026-07-05-run-fact-ledger-401-plan.md` (+ doc-review artifact) — carried from review

## Checks run

- Component tests green (run_ledger 15, dispatch consumers 5, recommend prior 3). Full gate: pending.

## Next step

Full-repo gate → programmatic `/code-review` (custody-chain lens) → ship to MERGED. Final Phase 0 item.
