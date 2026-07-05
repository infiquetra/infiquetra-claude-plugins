# Code review — shared 429 retry/backoff primitive (#348)

- **Target:** branch `feat/pf-429-retry-primitive-348` vs `main` (diff `origin/main...HEAD`)
- **Reviewed SHA:** `a1ce28bcc82d19d0eb5ab31e035372e0ee4a4f81`
- **Date:** 2026-07-05
- **Mode:** programmatic (Phase-0 driver pre-PR gate)
- **Plan:** `docs/plans/2026-07-05-shared-429-retry-primitive-348-plan.md`
- **Work-session:** `docs/work-sessions/2026-07-05-shared-429-retry-primitive-348.md`
- **Backend:** inline (4 adversarial readonly-verifier lenses, disposable worktrees)

## Verdict: ✅ CLEAN — not blocked (zero findings)

No P0/P1/P2/P3 findings survived validation. Safe to merge.

## Scope check: CLEAN

- **Intent:** consolidate the fleet's four disconnected 429 responses onto one shared fleet-commons
  `retry_backoff` primitive (emitted waves, engine bridges, `/outcome` dispatch, unifi clients).
- **Delivered:** exactly that, across U1–U5. No scope creep; agy deliberately untouched (KTD2,
  verified — `git diff origin/main...HEAD --stat -- plugins/agy` empty). No requirements missing.

## Plan-completion audit (5/5 DONE)

| Unit | Deliverable | Status | Evidence |
|---|---|---|---|
| U1 | fleet-commons `retry_backoff` (retry + `CircuitBreaker` + `bridge_call`) | DONE | `retry_backoff.py`; `test_retry_backoff.py` 7/7, breaker state machine verified |
| U2 | both unifi clients adopt primitive; vendored shim | DONE | client diffs; typed-error surface preserved on exhaustion; shim `cmp` byte-identical; `VENDORED_SHIMS` extended |
| U3 | emitted-wave `__retry` (3 thunk forms + panel verifiers) | DONE | `execution_spec.py`; `node --check` + live-exec passed; parens balanced; singletons unwrapped |
| U4 | `/outcome` 429 → `retriable-pending` (derived-on-read) | DONE | `outcome.py`/`outcome_dispatcher.py`; no commit/ledger/git mutation; re-pick + de-hammer tested |
| U5 | release surfaces + journal + tick + work-session | DONE | fleet-core 0.2.0 / saga 0.59.0 / unifi 1.2.0; parity + diff-guard pass; DECISIONS + row-9 tick |

## Lenses run (4 adversarial readonly-verifiers, worktree-isolated)

1. **Correctness × emitter** — `node --check` on the extracted `_JS_RETRY_HELPER`; rendered specs
   (independent wave + verify panel + iterate-to-consensus + external-engine) and executed the emitted
   `.workflow.js` under node with stub `agent`/`parallel`/`log`; confirmed paren balance at all 4 wrap
   sites, singletons unwrapped, no `Math.random`/arrow-fns in the helper, golden updates faithful.
   **NO FINDINGS.**
2. **Correctness/reliability × dispatch** — traced the `BackendRateLimitError` path: releases lock,
   writes no commit/ledger, leaf stays derived-`ready`; the dangling `intent` is a pre-existing shared
   characteristic (identical to the HALT path), not introduced here; re-pick + per-call `retriable_seen`
   de-hammer + quiescence break verified; `make_dispatcher` `rate_limited` branch is tested + documented
   (KTD2 forward-wire, not dead); exception hierarchy disjoint; `AdvanceResult.retriable` additive-safe.
   **NO FINDINGS.**
3. **Correctness/reliability × primitive + unifi** — retry bounds/jitter/non-429-propagation; breaker
   transitions; the SIM102 `state`-property refactor semantically identical to pre-diff; unifi typed
   error preserved on exhaustion; no test weakened; shim byte-identity via `cmp`. **NO FINDINGS.**
4. **Testing + conventions** — falsification-tested the suite: mutating `attempt < maxAttempts`,
   `throw caught`, and the de-hammer skip each broke a specific test (then reverted) — proving the tests
   bite, not tautologies; goldens strengthened not loosened; release parity + diff-guard + full gate
   green; agy untouched. **NO FINDINGS.**

## Coverage

- **Suppressed:** 0. **Residual risks:** the emitted-JS retry is asserted structurally (no JS runtime in
  the pytest suite — consistent with every other emitter test; verifier 1 additionally executed it under
  node out-of-band). **Testing gaps:** none material; the `make_dispatcher` `rate_limited` producer is a
  documented forward-wire awaiting an engine-bridge 429 source (agy/codex, KTD2).
- **Full gate:** `pytest` 2035 passed; `ruff format --check .` + `ruff check .` clean; `mypy` (135
  files) success; `bandit` no new medium/high on touched files; release-surface parity + diff-guard pass.

## Route

Clean (no P0/P1) → proceed to PR + ship. `Fixes #348` in the PR body auto-closes the issue on squash-merge.
