# Code review: external-engine HTTP bridge + bridge_receipt.v1 keystone pair

**Target:** branch `feat/387-383-http-bridge-receipt-pair` vs merge base `9a84311` (main)
**Reviewed revision:** `58e513f` (full five-lens pass) + delta `39569c4` (scoped fix commit — see below)
**Mode:** programmatic / report-only, called by `/work` (saga `issue-387`)
**Linked:** issues #387 + #383 · plan `docs/plans/2026-07-06-external-engine-http-bridge-receipt-pair-plan.md` · work-session `docs/work-sessions/2026-07-06-external-engine-http-bridge-receipt-pair.md`
**Blocked:** no — zero P0/P1; the single P2 was validated and fixed in-branch

## Verdict

Clean to PR. Five lenses (correctness, security, testing, maintainability — always-on — plus
reliability for the new network I/O surface), each run as `saga:readonly-verifier` in a
disposable worktree against the materialized branch code. One finding survived Stage A; its
Stage-B validator confirmed it; it was fixed with a regression assertion in `39569c4`.

## Scope check

**CLEAN.** Intent: one PR closing #387 (generic OpenAI-compatible HTTP bridge, cloud-first
rows `ollama-cloud`/`deepseek`) and #383 (`bridge_receipt.v1` proof-of-execution contract).
Delivered: exactly the plan's eight units plus two in-scope additions — a mypy cast in a
plan-owned test helper and the verify-panel journal learning.

## Findings

| # | Pri | Lens | File | Issue | Status |
|---|-----|------|------|-------|--------|
| 1 | P2 | reliability | `plugins/saga/scripts/engine_bridge_http.py:127` | `HTTPError` handler returned failure without closing the exception's live response handle — every non-2xx (401/429/5xx) leaked a socket until GC | Validated (real, introduced by diff, unhandled elsewhere) → **Fixed** in `39569c4`: `exc.close()` + closure assertion in `tests/test_engine_bridge_http.py` (assertion reds without the fix) |

Suppressed: 0. Non-defect notes (not findings): a dispatch comment says "transport-keyed"
while the branch keys on the row's `via` invocation field — behavior verified correct and the
comment cites the actual mechanism; a latent `no-any-return` in `agy_delegate.py` sits in a
path `pyproject.toml` excludes from CI mypy (pre-existing checking posture, not a regression).

## Plan-completion audit

All eight units **DONE** (DIFF verification, with refute-panel and test evidence per unit):
U1 receipt schema · U3 registry transport/rows/`receipt_emitter` · U4 transport-aware
preflight + RunMemo · U5 HTTP bridge + adapter dispatch + secret lifecycle · U6 receipt-gated
`UNPROVEN` disposition + never-gatekeeper guard · U2 agy emission via vendored shim ·
U7 forcing-function drift guard · U8 four-plugin release surfaces + journal.

## Coverage and residual risk

- Checks at reviewed revisions: pytest 2423 passed / 1 skipped (availability-gated Ollama
  smoke, skip-not-fail without `OLLAMA_API_KEY`); ruff clean; mypy clean (CI scope, 152
  files); bandit — no findings introduced (agy subprocess and resolver assert are
  pre-existing).
- Refute-3 verify panels (unit tier): U5 3/3 upheld, U6 3 upholding verdicts after the two
  main-revision false-kill slots were re-run against `df42a39`, U7 3/3 upheld.
- Residual: provider base URLs / wire model ids are seed values verified against provider
  docs; the availability-gated smoke is the live proof on first keyed dispatch (accepted at
  plan time, same posture as the 2026-06-27 seed rows).

## Post-review delta rationale

Commits past the reviewed SHA `58e513f`: `39569c4` — exclusively the validated P2 fix and
its regression assertion (2 files, +8/−2); a docs commit adding this artifact and the
work-session; and a formatting-only commit (`ruff format` over 8 pair-touched files —
CI's Lint job checks `ruff format --check`, which the local gate run had not mirrored;
zero semantic change). Full suite green at `39569c4`; targeted suites (104 tests) plus
both ruff gates and mypy green after formatting. Recorded here in lieu of a five-lens
re-pass per the override-with-recorded-rationale rule; the staleness window contains no
unreviewed logic change.
