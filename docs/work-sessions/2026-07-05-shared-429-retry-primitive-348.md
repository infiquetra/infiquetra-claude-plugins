# Work session — shared 429 retry/backoff primitive (#348)

- **Date:** 2026-07-05
- **Issue:** [#348](https://github.com/infiquetra/infiquetra-claude-plugins/issues/348) —
  "one shared 429 retry/backoff primitive across emitted waves, engine bridges, and /outcome dispatch"
- **Plan:** `docs/plans/2026-07-05-shared-429-retry-primitive-348-plan.md`
- **Doc-review:** `docs/reviews/2026-07-05-shared-429-retry-primitive-348-doc-review.md` (1 P1 fixed in-plan)
- **Branch:** `feat/pf-429-retry-primitive-348`
- **Backend:** inline (mechanical breadth across saga + unifi×2 + fleet-core; no judgment fan-out warranted)
- **Driver:** Phase 0 autonomous driver, item 9 of 10 (`docs/plans/2026-07-05-phase0-autonomous-driver.md`)

## What shipped (U1–U5)

- **U1 — fleet-commons primitive** (`plugins/fleet-core/scripts/fleet_commons/retry_backoff.py`):
  `retry_with_backoff` (jittered exponential backoff, attempt cap, non-429 pass-through, injectable
  RNG/clock/sleep + `retry_after` seam), a `CircuitBreaker` (CLOSED→OPEN→HALF_OPEN→CLOSED over an
  injected clock), and `bridge_call`. Fault-injection tested (`tests/test_retry_backoff.py`, 7 tests).
- **U2 — unifi adoption:** both `unifi_network_client.py` and `unifi_protect_client.py` replace the
  inline `429 → sys.exit(1)` with `retry_with_backoff` (honoring `Retry-After`), keeping the existing
  typed error surface on exhaustion. Vendored the byte-identical `fleet_commons_shim.py` into each
  client dir and registered both in the drift-guard `VENDORED_SHIMS`.
- **U3 — emitted-wave retry** (`execution_spec.py`): emit `_JS_RETRY_HELPER` into every `.workflow.js`
  and wrap each `parallel([...])` wave thunk (all three `_emit_thunk` forms) and refute-N panel
  verifier `agent()` call in `__retry(() => agent(...), { unitId, maxAttempts })`. Wrapper fragments
  single-sourced (`_retry_open`/`_retry_close`/`_retry_opts_js`) so the four sites can't drift.
  Singleton `await agent()` calls stay unwrapped (R3 scopes retry to waves).
- **U4 — `/outcome` dispatch classification** (`outcome.py`, `outcome_dispatcher.py`): a
  `BackendRateLimitError` during dispatch is classified `retriable-pending` — a derived-on-read
  RESULT label (`AdvanceResult.retriable`), never a committed `NODE_STATE`. The 429'd leaf gets no
  commit → stays `ready` → the ready frontier re-picks it on the next `advance()` call. A per-call
  `retriable_seen` set de-hammers a `loop=True` run. Added the `RateLimitReceipt`/`BackendRateLimitError`
  vocabulary + a `make_dispatcher` `rate_limited`-status translation (production-capable).
- **U5 — release surfaces + writeback:** fleet-core 0.1.0→0.2.0, saga 0.58.0→0.59.0, unifi 1.1.0→1.2.0;
  regenerated `marketplace.json`; per-plugin CHANGELOG entries; saga version-literal drift-guard
  (`test_saga_plugin.py`) bumped; DECISIONS `{#shared-retry-backoff-primitive-348}`; execution-order
  row 9 ticked; this work-session.

## Key decisions (see DECISIONS `{#shared-retry-backoff-primitive-348}`)

- **KTD2 — `agy` scoped out:** verified `agy_delegate.py` has no HTTP 429 surface (rate-limit shows as
  a subprocess timeout). Deferring is *safer*, not just easier — the primitive is import-ready. No agy
  bump, no `test_agy_delegate.py` change.
- **KTD3 — dual-impl JS mirror:** the emitted JS can't import the Python primitive; `_JS_RETRY_HELPER`
  is `function`-only (no arrow fns) with deterministic backoff (no `Math.random`) so it perturbs no
  emitted-shape golden and won't trip the workflow runtime's randomness ban.
- **KTD4 — derived-on-read, no state edit:** the 429 re-pick writes no commit/ledger/git state.

## Golden-test handling (the delicate part)

The emitter goldens are pure-Python string assertions (no JS runtime). Wrapping put `() => agent(`
onto one line, so two goldens needed *faithful* updates (not loosening):
- `test_independent_units_emit_a_parallel_wave` — `count("() =>") == 2` → `count("__retry(() => agent(") == 2`.
- `test_layered_spec_with_verify_panel_full_emission` — `count("() => agent(") == 3` → `count("__retry(() => agent(") == 5` (2 wave thunks + 3 verifiers) + `count("agentType:") == 3` (verifier anchor).
- `test_parallel_iterate_to_consensus_emits_loop_in_thunk` — `result = await agent(` → `result = await __retry(() => agent(`.

Added `test_emitted_js_contains_retry_wrapper` (golden) + `test_retry_on_429_bounds_and_propagates_non_429`
(structural: 429 → bounded retry; non-429 → propagate/HALT). The panel-verifier `count("() => agent(") == 3`
goldens *survived* unchanged because `() => __retry(() => agent(` still contains the substring.

## Small defects fixed inline

Two latent U1 lint issues surfaced (the branch never hit CI): `SIM102` (nested `if` in
`CircuitBreaker.state`) and `N818` (`class Rate` → `RateError`) in `test_retry_backoff.py`.

## Gate

Full local gate green: `uv run pytest` (2035 passed), `ruff format --check .` (218 files),
`ruff check .` (passed), `mypy plugins/ scripts/ tests/ --ignore-missing-imports` (135 files, success),
`bandit` (no new medium/high on touched files), release-surface parity + diff-guard.
