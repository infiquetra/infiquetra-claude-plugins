---
title: "Shared 429 retry/backoff primitive (fleet-commons) adopted across the fleet's 429 surfaces"
type: feat
status: active
date: 2026-07-05
origin: https://github.com/infiquetra/infiquetra-claude-plugins/issues/348
---

# Shared 429 retry/backoff primitive (fleet-commons) adopted across the fleet's 429 surfaces

Phase 0 item 9. Replace four independent, partial (or absent) responses to HTTP 429 with one shared,
hardened retry/backoff primitive in **fleet-commons** (#463), adopted at the surfaces that actually die
on rate-limiting today, so a 429 becomes an invisible retry / re-queue / re-pick instead of a dead agent
or a hand-resume.

## Problem & grounding

The fleet's dominant rate-limit failure is not "no handling" — it's four disconnected, non-retrying
responses to the same failure mode. Verified during planning (Explore + direct reads):

- **fleet-commons is the shipped home for cross-plugin primitives** (#463). Shared modules live under
  `plugins/fleet-core/scripts/fleet_commons/` (stdlib-only, loaded by path); a consumer vendors a
  byte-identical `fleet_commons_shim.py` and calls `fleet_commons_shim.load("<mod>")`
  (`plugins/saga/scripts/execution_spec.py:46-61` is the reference idiom). Existing consumers: saga
  (`execution_spec`) + mission-control (`executor_profile_lint`). DECISIONS `{#fleet-commons-mechanism-463}`
  (`DECISIONS.md:309-325`) explicitly rejected saga-hosted commons (couples consumers to saga's churn).
- **unifi clients hard-exit on 429, no retry:** `unifi_network_client.py:151-159` and
  `unifi_protect_client.py:158-166` both compute `Retry-After` then `self._error(...); sys.exit(1)`.
- **The emitted parallel-wave path has NO 429 handling:** `execution_spec.py` emits `parallel([...])`
  waves of `agent()` thunks (`:1025 _emit_thunk`, `:953` panel `parallel`) with no wrapper
  distinguishing a transient 429 from a real agent failure. `LEARNINGS.md:954` records transient 429s
  eating retry budget in a live fan-out run.
- **`/outcome` degrades-on-read but does not retry:** `outcome_github.py:1-27` returns `"unknown"` on a
  rate-limited read (never a false merged/closed); `outcome.py advance()` dispatches the ready frontier
  via an injected `dispatcher` with no transient-429 re-pick.
- **agy makes no HTTP calls:** `agy_delegate.py` launches the guarded `agy` wrapper via
  `subprocess.Popen` (`:691-697`) with timeout-only supervision — **no rate-limit signal at that
  boundary** (see KTD2).
- Current versions: saga **0.58.0**, fleet-core **0.1.0**, unifi (bump in `/work`).

## Requirements

- **R1.** A stdlib-only `retry_backoff` module in `plugins/fleet-core/scripts/fleet_commons/` exposes
  `retry_with_backoff(fn, *, on_status=429, max_attempts, base_delay, ...)` — jittered exponential
  backoff, attempt cap, non-429 pass-through (a non-retryable error propagates immediately) — plus
  `bridge_call(fn, ...)` adding circuit-breaker state (OPEN on a run of 429s, cooldown, HALF-OPEN probe,
  CLOSE on success).
- **R2.** `unifi-network` and `unifi-protect` clients call the shared primitive instead of their inline
  `sys.exit(1)` on 429, and their existing tests stay green (no test deleted/weakened).
- **R3.** The emitted `.workflow.js` `parallel([...])` wave wraps each `agent()` thunk in a bounded
  retry (a JS helper mirroring the primitive, KTD3): a 429'd agent re-queues (bounded) instead of
  counting as a wave failure; a genuine non-429 error still propagates and HALTs the wave (no silent
  degrade). The emitted JS contains the retry wrapper (golden assertion).
- **R4.** `/outcome` `advance()`/dispatch classifies a 429'd leaf dispatch as `retriable-pending` —
  **derived-on-read**, never a committed status field — so the next `advance` tick re-picks it without
  operator action. Every non-429 failure keeps HALTing exactly as today.
- **R5.** The circuit-breaker (`bridge_call`) is fully built and fault-injection tested (OPEN /
  short-circuit-during-cooldown / HALF-OPEN / CLOSE), ready for engine-bridge adoption (see KTD2).

## Key Technical Decisions

**KTD1 — the primitive lives in fleet-commons, consumers vendor the shim.** Per #463 and the
execution-order doc ("#348 follows #463 so its packaging conforms"), `retry_backoff.py` goes in
`plugins/fleet-core/scripts/fleet_commons/`, stdlib-only. unifi becomes a NEW fleet-commons consumer:
vendor a byte-identical `fleet_commons_shim.py` adjacent to (or on the path of) each unifi client and
`load("retry_backoff")`. Rejected: `plugins/saga/scripts/retry_backoff.py` — recreates the exact
cross-plugin-to-saga coupling fleet-core was built to remove.

**KTD2 — agy_delegate.py adoption is scoped OUT of v1; the breaker is still built + tested.**
`agy_delegate.py` makes no HTTP calls (it `Popen`s the external agy wrapper; supervision is timeout-only)
— there is no 429 signal at that boundary; agy's rate-limits live inside the wrapper subprocess,
invisible here. So `bridge_call()` + the circuit-breaker are built and fault-injection tested in the
primitive (R5 — satisfying the breaker acceptance intent), but the agy_delegate WIRING is deferred:
adopting it would require inventing speculative subprocess-relaunch-retry semantics, which is not this
mechanical consolidation. This is **safer, not merely easier**: an agy run is long and token-expensive,
and with no clean rate-limit signal at the subprocess boundary, auto-relaunching on an ambiguous failure
would risk double-spending tokens on a genuinely non-transient failure. The primitive is import-ready for
agy/codex when a bridge exposes a real rate-limit signal. **Consequence:** the `agy` plugin is NOT touched (no agy release bump, no
`test_agy_delegate.py` change). Surfaced, not silent.

**KTD3 — the emitted-wave retry is a JS helper mirroring the Python primitive.** The workflow runs as
JS, so the `parallel([...])` wave cannot import the Python module. `execution_spec.py` emits a
`_JS_RETRY_HELPER` (a JS function, like the existing `_JS_GATE_HELPER` at `:142`) that wraps each
thunk's `agent()` call in bounded 429 retry. Shared-in-concept, dual-impl (Python primitive + emitted
JS helper). The golden test asserts the emitted JS contains the wrapper.

**KTD4 — `retriable-pending` is a dispatch-result label, NOT a `NODE_STATE`.** `NODE_STATES`
(`outcome_spec.py:61-73`) does not contain `retriable-pending`, and adding it would be the committed
status-field change the issue forbids — so a 429'd dispatch must **not** write it as a node state. The
correct derived-on-read design: a rate-limited dispatch simply **fails to advance the leaf to
`dispatched`** (the dispatch did not happen), so the leaf's derived state **stays `ready`** and the
ready-frontier derivation re-picks it on the next `advance` tick with no operator action.
`retriable-pending` is the descriptive classification the dispatcher returns *in its result record* (so
the tick can log "rate-limited, will re-pick") — never a persisted node state. Only 429 is added to the
transient-retryable class; every other dispatch failure keeps HALTing exactly as today.

## Implementation Units

### U1 — `retry_backoff.py` in fleet-commons (the primitive)

New `plugins/fleet-core/scripts/fleet_commons/retry_backoff.py` (stdlib-only): `retry_with_backoff` +
`bridge_call` + a small `CircuitBreaker`. `on_status` accepts an int (429) or a predicate so non-HTTP
callers can classify their own retryable condition. Deterministic jitter seam (injectable RNG/clock) for
tests.

**Tests** (`tests/test_retry_backoff.py`, new): retry-then-success; non-429 propagates immediately;
attempt cap honored; jittered delay within bounds (injected clock); breaker OPEN on N consecutive 429s;
short-circuit during cooldown; HALF-OPEN probe; CLOSE on success (R5).

### U2 — unifi clients adopt the primitive

Vendor byte-identical `fleet_commons_shim.py` into unifi; `unifi_network_client.py` +
`unifi_protect_client.py` replace the inline `429 -> sys.exit(1)` with `retry_with_backoff` around the
request (honoring `Retry-After`); on exhaustion, keep the existing typed error surface.

**Tests:** `tests/test_unifi_network_client.py` + `tests/test_unifi_protect_client.py` stay green
(no weakening, R2); add one retry-then-success case per client; add the shim byte-identity assertion
(mirrors `test_fleet_commons_resolution.py`).

### U3 — emitted-wave retry (`_JS_RETRY_HELPER`)

`execution_spec.py` gains `_JS_RETRY_HELPER` and wraps each emitted thunk's `agent()` call in it (both
`_emit_thunk` `:1025` and the panel `parallel` `:953`). Bounded retry on a 429-shaped result; a non-429
error still throws and HALTs the wave.

**Tests** (`tests/test_execution_spec.py`): `retry_on_429` (stub 429-then-success agent in a wave →
wave completes; non-429 in the same wave → HALTs); `emitted_js_contains_retry_wrapper` (golden).

### U4 — `/outcome` `retriable-pending` dispatch classification

`outcome.py` `advance()`/dispatch: when a leaf's dispatch raises/returns a 429-shaped result, do **not**
advance the leaf to `dispatched` — record a `retriable-pending` classification in the dispatch RESULT
(a log/record label, not a node state, KTD4) and leave the leaf at its derived `ready` state so the
ready-frontier re-picks it next tick. No committed status field.

**Tests** (`tests/test_outcome.py`): `retriable_pending` — a rate-limited dispatch leaf's derived state
stays `ready` and it reappears in the ready frontier on the next `advance` with no operator action; the
node's persisted `state` is never set to `retriable-pending` (schema-valid); `git`/persisted artifacts
show no new committed status field.

### U5 — release surfaces + DECISIONS

Bump **fleet-core** (new module), **saga** 0.58.0 → 0.59.0 (emitted-wave retry + dispatch classification);
bump **unifi** (adopts the primitive). Regenerate `marketplace.json`; CHANGELOG entries for fleet-core +
saga + unifi; version literals in any drift-guard tests. NOT agy (KTD2). Add a DECISIONS entry
`{#shared-retry-backoff-primitive-348}`.

## Scope Boundaries

**In:** fleet-commons `retry_backoff` (retry + breaker), unifi×2 adoption, emitted-wave JS retry,
`/outcome` retriable-pending classification, release surfaces.

**Out (true non-goals):**
- **agy_delegate.py wiring (KTD2)** — no 429 surface; the primitive is import-ready for it.
- `mission-control`'s `_classify_gh_error` / gh-CLI path (issue out-of-scope; gh has its own retry).
- Any change to `/outcome`'s HALT-not-degrade posture for non-429 failures.
- Backfilling retry onto call sites not named here; a fleet-wide HTTP-client rewrite.

## Definition of Done

- One fleet-commons `retry_backoff` (retry + fault-injection-tested breaker); unifi×2 adopt it, tests
  green; emitted waves re-queue 429'd agents (non-429 still HALTs, golden-verified); `/outcome` re-picks
  a 429'd leaf via derived `retriable-pending`.
- Full gate green: `uv run pytest && uv run ruff format --check . && uv run ruff check . && uv run mypy
  plugins/ scripts/ tests/ --ignore-missing-imports && uv run bandit -r plugins/`; release surfaces in
  lockstep (fleet-core + saga + unifi).
