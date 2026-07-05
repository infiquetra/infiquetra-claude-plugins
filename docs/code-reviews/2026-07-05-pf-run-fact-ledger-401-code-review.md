---
title: Code review — Run-fact ledger substrate (#401)
type: code-review
date: 2026-07-05
target: branch feat/pf-run-fact-ledger-401 (diff origin/main...HEAD)
reviewed_sha: 146cbf58d6a80fcdd85b4e9a6daed57f4493a9df
base: origin/main (0a29f67)
mode: programmatic
blocked: false
verdict: CLEAN
linked_issue: https://github.com/infiquetra/infiquetra-claude-plugins/issues/401
linked_plan: docs/plans/2026-07-05-run-fact-ledger-401-plan.md
doc_review: docs/reviews/2026-07-05-run-fact-ledger-401-doc-review.md
work_session: docs/work-sessions/2026-07-05-run-fact-ledger-401.md
---

# Code review: #401 run-fact ledger — CLEAN

**Verdict: CLEAN — not blocked. 0 code findings.** One cosmetic plan-doc reference (a non-existent
test-file name) was corrected post-review. Reviewed SHA `146cbf5`.

## Scope

16 files, ~1021 insertions, on `feat/pf-run-fact-ledger-401` vs `origin/main` (0a29f67) — exactly the
7-unit #401 change (new `run_ledger.py` + two consumer wirings + a tier prior + docs + release
surfaces). Full local gate green at review time: pytest 2079, ruff format+check, mypy 137 files,
bandit no issues on touched files, release-surface parity.

## Scope check: CLEAN

Intent (a leaf-produced hash-chained run-fact ledger + 2 consumers, landed empty) matches delivered. No
scope creep; the only non-substrate code change (`engine_dispatch.dispatch` consolidation) is required
by U3/U4 and preserves behavior.

## Plan-completion audit (7/7 DONE)

| Unit | Status | Evidence |
|------|--------|----------|
| U1 schema + hash-chain | **DONE** | `run_ledger.py` build_fact/append_fact/verify_chain; custody tests pass |
| U2 derive-on-read views | **DONE** | rollup/reuse_ratio/last_n_prior; None on no-data verified |
| U3 engine fact | **DONE** | `engine_dispatch.dispatch(ledger=…)`; byte-identical evidence verified |
| U4 delegation fact | **DONE** | `agy.delegation.v1` discrimination verified; content-address pointer |
| U5 tier prior | **DONE** | `recommend_execution_backend(ledger=…)`; no `prior` key without data |
| U6 docs + DECISIONS | **DONE** | `references/run-fact-ledger.md`; `{#run-fact-ledger-401}` KTD1-KTD7 |
| U7 release surfaces | **DONE** | saga 0.61.0 lockstep; parity OK; execution-order row 10 `[x]` |

## Adversarial verification (3 read-only verifiers, disposable worktrees) — all UPHELD

1. **Custody / tamper-evidence:** live on-disk tampering of a real ledger. In-place field mutation,
   `this_hash` overwrite, middle-deletion, and reorder are **all caught** (`verify_chain` ok=False with
   the right break_index/reason). The two documented bounds — a full-access chain recompute and trailing
   truncation (valid prefix) — reproduce exactly as disclosed in `references/run-fact-ledger.md`, i.e.
   honestly documented, not silently claimed as protected. Determinism holds (`_canonical` sort_keys);
   `build_fact` rejects reserved-field injection. 15 tests pass.
2. **Backward-compat / telemetry-not-gate:** `dispatch` returns an identical `AdvisoryEvidence` with vs
   without a ledger on **both** the ok and failure(`halt=note`) paths (the two returns were consolidated
   into one `evidence` var; the ledger write is a pure post-hoc side effect). `_record_advisory_facts`
   early-returns when ledger/subplot_id/at are absent. `recommend_execution_backend` adds `prior` only
   with data; the one real caller (`outcome_dispatcher.py:411`) passes no ledger → unaffected.
   Delegation discrimination correct; evidence pointer is `sha256:…`, not bytes.
3. **Completeness / decoupling / parity:** `run_ledger.py` imports only stdlib + sibling `outcome_store`
   (AST-verified; not in fleet-commons). Derive-on-read confirmed (None on no-data, no committed
   summary). `check_release_surface_parity` → all in parity; drift-guard asserts 0.61.0; CHANGELOG
   grammar exact. 87 tests pass; 4 scenario categories covered; no dead-wiring (real consumers call the
   ledger, not just tests).

## Finding (cosmetic, fixed)

- **P3 (plan-doc, fixed post-review):** the plan's U5 named `tests/test_lifecycle_state.py` as the test
  home, but that file does not exist — the tests actually landed in `tests/test_saga_execution_spec.py`
  (the real home for `recommend_execution_backend`). Corrected the plan reference. No code impact.
- **Citation note:** the review brief cited `saga.py:1386` as a `recommend_execution_backend` call site;
  it is a `--help` string, not a call. The only real call site is `outcome_dispatcher.py:411` (verified
  to pass no ledger). No code impact.

## Residual risk

- None material. The tamper-evidence bound (not tamper-resistance) is inherent to a machine-local,
  never-committed store and is documented; consumers must not over-claim, which `references/run-fact-ledger.md`
  states explicitly.

## Review-result contract

- **Target / reviewed revision:** `feat/pf-run-fact-ledger-401` @ `146cbf5` (code); a subsequent
  doc-only commit corrects the plan's U5 test-file reference (no code change).
- **Blocked:** No (CLEAN)
- **Findings:** 0 code; 1 P3 plan-doc reference fixed
- **Plan completion:** 7/7 DONE
- **Scope check:** CLEAN
- **Coverage:** full local gate green; `run_ledger.py` 94%
- **Links:** issue #401; plan; doc-review; work-session (front-matter)
