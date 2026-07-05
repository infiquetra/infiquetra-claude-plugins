---
title: Doc-review — Run-fact ledger substrate (#401)
type: doc-review
date: 2026-07-05
target: docs/plans/2026-07-05-run-fact-ledger-401-plan.md
reviewed_revision: working tree (base 0a29f67; safe fixes applied in place, uncommitted at review time)
linked_issue: https://github.com/infiquetra/infiquetra-claude-plugins/issues/401
linked_plan: docs/plans/2026-07-05-run-fact-ledger-401-plan.md
work_session: (pending — created by /work)
blocked: false
---

# Doc-review: #401 run-fact ledger substrate

**Readiness verdict: READY to drive implementation** (with the applied fixes). No P0; two P2s and three
P3s, all resolved in place. The load-bearing element (R3 hash-chain custody) is now specified with an
explicit, honest threat-model bound and reorder/deletion test scenarios.

## 1. Applied fixes (in place)

| # | Pri | Fix | Evidence |
|---|-----|-----|----------|
| 1 | P2 | **U5 pinned to a real testable code surface.** The plan named "the `recommend_execution_backend` / tiering path" vaguely; it's a concrete function `lifecycle_state.recommend_execution_backend` (`lifecycle_state.py:99`, consumed at `outcome_dispatcher.py:411`, threaded at `saga.py:1386`). Pinned U5 there (not the un-testable prose tier-table in `plan/SKILL.md`) so the `tier-table-prior` scenario has something to assert; test home `tests/test_lifecycle_state.py`. | `lifecycle_state.py:99` def; consumers verified. |
| 2 | P2 | **R3 threat-model honesty.** Hash-chaining is tamper-*evidence*, not tamper-*resistance* — it catches in-place mutation / reorder / truncation, but a full-access writer can recompute a fresh chain. Added the explicit bound + noted it matches the machine-local never-committed git-common-dir trust boundary, and that the schema doc (U6) must state it so no consumer over-claims. | `outcome_store.py` common-dir cache is "never committed, machine-local"; `append_ledger:408` confirms no chaining today. |
| 3 | P3 | **U4 delegation surface anchored.** Named the concrete surface: `build_agy_delegation_envelope` (`engine_dispatch.py:68`, `agy.delegation.v1`) + `AdvisoryEvidence.evidence` (`:33`). | grep confirmed. |
| 4 | P3 | **U3/U4 relationship clarified.** Both derive from the same `engine_dispatch.dispatch()` → `AdvisoryEvidence`; U3 writes an `engine` fact on any advisory call, U4 a `delegation` fact only when the `agy.delegation.v1` envelope is present; independent `append_fact` writes. Added a non-delegation-writes-no-delegation-fact test. | `engine_dispatch.py:103` dispatch. |
| 5 | P3 | **U1 custody tests strengthened.** Added explicit reorder + middle-deletion → `verify_chain` FAIL scenarios (a chain must catch both, not just an in-place field mutation). | — |

## 2. Anchor verification (every file:line in the plan)

All verified against the live tree. This matters because #348/#379 edited `outcome.py` since the issue
was authored (2026-07-03) — but the ledger anchors are stable.

| Anchor | Claim | Verified |
|--------|-------|----------|
| `outcome_store.py:408` `append_ledger` | append-only O_APPEND, torn-tail healed, **not hash-chained** | ✅ — body writes a JSON line, no `prev_hash`; KTD2 premise holds |
| `outcome_store.py:429` `read_ledger`, `:93` `resolve_common_dir`, `_heal_torn_tail` | storage discipline to reuse | ✅ |
| `outcome_costs.py:41/94/153` `_NUMERIC_FIELDS`/`_latest_costs`/`rollup` | derive-on-read precedent (KTD3) | ✅ |
| `engine_dispatch.py:28/103/163/281` `AdvisoryEvidence`/`dispatch`/`build_dispatch_manifest`/`satisfy_gate` | U3 consumer surface | ✅ |
| `engine_dispatch.py:68` `build_agy_delegation_envelope` (`agy.delegation.v1`), `:33` `evidence` | U4 consumer surface | ✅ (added to plan) |
| `manifest_store.py` git-common-dir saga-scoped store | KTD1/KTD2 storage precedent | ✅ |
| `lifecycle_state.py:99` `recommend_execution_backend` | U5 surface | ✅ (added to plan) |

## 3. KTD scrutiny

- **KTD1 (saga-local, not fleet-commons)** — **sound.** Every consumer (`engine_dispatch`,
  `lifecycle_state.recommend_execution_backend`, `outcome`) is in saga; no cross-plugin consumer exists
  (the #348 fleet-commons trigger). `manifest_store`/`outcome_costs` are the right saga-local precedents.
- **KTD2 (distinct hash-chained ledger)** — **sound and verified.** The replay `ledger.jsonl` is
  append-only but un-chained and serves crash-replay; the run-fact ledger is genuinely separate,
  reusing the O_APPEND + torn-tail discipline and adding chaining. Not an overload.
- **KTD3 (derive-on-read, no committed summary)** — **sound.** Mirrors `outcome_costs.rollup`/`_latest_costs`;
  honors `#outcome-economics-stance`.
- **KTD4/KTD5/KTD6/KTD7** — sound (leaf-produced; engine fact telemetry-not-gate; `run_fact.v1` +
  forward-tolerant readers; no `outcome_costs` migration).

## 4. Remaining findings after fixes

None at P0/P1/P2. Residual: none material — the plan is right-sized for a `/work` inline build.

## 5. Residual risk / limited evidence

- **U5 placement** — surfacing the prior "in/alongside `recommend_execution_backend`'s computation" is
  the resolved direction, but the exact signature change (new optional param vs a new output field) is a
  `/work` implementation detail; the plan pins the surface and the no-data-fallback invariant, which is
  enough to drive it. Low risk.

## 6. Review-result contract

- **Target:** `docs/plans/2026-07-05-run-fact-ledger-401-plan.md`
- **Reviewed revision:** working tree (base `0a29f67`; 6 safe fixes applied, uncommitted)
- **Blocked:** No — READY for `/work` (no unresolved P0/P1)
- **Findings:** 2×P2 (applied), 3×P3 (applied)
- **Applied fixes:** §1
- **Links:** issue #401; plan; work-session pending
