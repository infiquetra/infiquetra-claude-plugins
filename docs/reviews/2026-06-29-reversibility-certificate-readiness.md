# Readiness Review — Reversibility/Idempotency Certificate (#279)

**Verdict: READY — blocked = false.** No P0/P1 findings. All confirmed actionable findings (5 P2,
2 P3) were applied as safe in-place fixes to the plan. `/work` is unblocked.

## Review-result contract

| Field | Value |
|---|---|
| Target | `docs/plans/2026-06-29-reversibility-certificate-plan.md` |
| Reviewed revision | working tree at commit `1cdc294` (branch `feat/279-reversibility-certificate`) |
| Blocked | **false** (0 P0, 0 P1) |
| Findings | 18 raw → 10 confirmed (0 P0 · 0 P1 · 5 P2 · 5 P3) / 8 refuted |
| Applied fixes | 7 (5 P2 + 2 P3 actionable) — see below |
| Review artifact | `docs/reviews/2026-06-29-reversibility-certificate-readiness.md` (this file) |
| Linked issue / plan / saga | #279 · `docs/plans/2026-06-29-reversibility-certificate-plan.md` · saga `issue-279` |
| Method | 4-lens adversarial workflow (agy-contract, req/AE mapping, technical soundness, adversarial) + refute-pass verifier (22 agents) |

## Readiness summary

The plan can safely drive implementation. The agy-delegation contract (KTD7) — the operator's special
focus — was found **fully compliant** with the documented `/agy:delegate` findings; its only hit was a P3
bookkeeping wording nit. Technical soundness independently **confirmed** the headline claims against live
code: the two-plugin scope (mission-control genuinely lacks the issue close/reopen/comment/label verbs),
the KTD5 subsumption method, every cited `file:line` anchor, and both version bumps. The confirmed P2s
were precision/hardening gaps, not design faults, and all were safe-fixable from repository evidence.

## Applied fixes (safe, evidence-backed)

| # | Pri | Area | Fix |
|---|-----|------|-----|
| 1 | P2 | KTD4 + Grounding Δ2 | Board-sync uses a **separate namespaced** idempotency ledger (reusing only the write-once `os.link` mechanism + `"written"/"skipped"`), never `write_completion_event`/`events_dir` — which require terminal `COMPLETION_STATES` (`outcome_store.py:264`) and feed `derive_states` (`:350-366`). A board-op key would crash `validate` or pollute the frontier. |
| 2 | P2 | KTD5 + U2 test | Added the `side_effected == node.destructive` **pass-through identity** test at the real call site (`outcome.py:623`); the 7 golden `degrade_decision` tuples alone never exercised the substitution seam where `True→HALT` could flip to `False→degrade` (the R14 corruption). |
| 3 | P2 | R1 + U4 test | Added a U4 spy/mock test asserting the board-sync consumer **invokes** `authorize_write` for its verdict — the only falsifiable test of "no consumer re-derives" (R1 had no acceptance example and U1's 7 scenarios never tagged it). |
| 4 | P2 | KTD7 + U3 write-set | Added an **autouse no-live-`gh` conftest guard** for the GitHub-write test modules; the existing `mock_subprocess_run` is opt-in (`conftest.py:66`), so "the build touches no live GitHub" rested on convention. This becomes the concrete tripwire for the escalate-off-agy trigger. |
| 5 | P2 | U4 + KTD6 | Fixed the wiring entrypoint: board-sync fires from the **`advance` reconcile tick** (`AdvanceResult`, `outcome.py:398-544`), gated to `--autonomous`; the `prune` deferral note (`:1062-1065`) is replaced only for `sub-issue-close`, not the sole site. |
| 6 | P3 | KTD6 + Scope | Declared **negative-terminal board-revert** (`failed`/`rejected`/`stalled`) an explicit deferred non-goal (recoverable drift; derived-on-read stays the source of truth). |
| 7 | P3 | KTD7 Track-3 | Reworded the bookkeeping bullet: only the n=3 #278 README rows are owed (n=2 #277 already exist, README `:65`/`:80-84`) + add n=4 #279 rows — avoids a duplicate #277 entry. |

## Confirmed findings (positive — no action)

- **Two-plugin scope is TRUE** — `sdlc_manager.py` issue subparsers (`:4823-4928`) are only
  create/prepare/create-prepared/approve; no close/reopen/comment, and `flow verify-label` is repo
  label-definition create, not issue-label add/remove. U3 is genuine new work, not redundant.
- **KTD5 method is SOUND** — exactly 7 `degrade_decision` case functions exist
  (`tests/test_outcome_backends.py:75-146`); routing only `had_side_effect` is behavior-preserving.
- **All anchors + versions correct** — dispatcher:271, projection:81, outcome.py:1062-1065,
  github.py:175-192, lifecycle_state:180, sdlc_manager:2172/:993; saga 0.41.0→0.42.0, mc 2.3.1→2.4.0.

## Refuted findings (8 — dropped by the verifier as already-guarded or over-stated)

R4 coverage (already exercised by U1 scenarios 1/2/6/7); R20/AE7 membership-vs-verdict (already pinned to
`authorize_write`); R21/AE9 coincidental snapshot (write-set exclusion is a stronger proof); side_effected
conceptual coupling (already separated in KTD1); KTD8 dead-wiring (already guarded); KTD4 reuse-is-real
(no defect, restated as fix #1's hardening); KTD6 not-grounded (over-stated — already pins derive_states);
no-dry-run for the maiden write (already guarded by reversible-tier + tick + default-deny + operator-present
`advance`).

## Residual risk

Low. The highest-stakes items (subsumption equivalence U2, autonomous writes U4) are now backed by the
pass-through identity test, the autouse `gh` guard, and an adversarial-verify pass scheduled at `/work`.
The plan defers negative-terminal board-revert explicitly; if an `/outcome` campaign in practice shows the
board drifting on leaf regressions, promote it.
