---
target: docs/plans/2026-07-03-verify-panel-robustness-plan.md
reviewed_revision: working tree (base 46b7001)
verdict: READY
blocked: false
issue: infiquetra/infiquetra-claude-plugins#293
date: 2026-07-03
---

# Readiness Review — Verify-Panel Robustness Plan

## Verdict

**READY for `/work`.** The plan is grounded against the current tree (saga 0.49.2) with every
cited surface re-read this session, and it correctly supersedes the issue's four drifted premises
(three reconciliation sites, throw-not-log consumer, no `team_emitter.py` surface, new Layer B
test file). Four findings were found and all four were fixed in place; nothing remains at any
priority.

## Applied fixes

All evidence-backed; the plan was edited in place.

| # | Priority | Finding | Fix |
|---|----------|---------|-----|
| F1 | P2 | R13, Problem Frame, and Risks claimed the `verifier-disagreement:` prefix is "machine-classified" by `completeness_gate.py`. In fact `classify()` (`completeness_gate.py:201-219`) checks presence/truncation/fanout/required-keys only; `FailureClass.VERIFIER_DISAGREEMENT` is constructed nowhere in production (only a hypothetical lambda in `tests/test_completeness_gate.py:97`). | Reworded all three sites: the prefix is pinned by existing test asserts (`tests/test_workflow_emitter.py:1522,1550,1624`) and kept string-aligned with the failure-class vocabulary; no production message-parser exists today. |
| F2 | P2 | U2's new accept-path `log()` intersects an existing contract guard the plan never named: `test_refuted_panel_emits_verifier_disagreement_halt` (`tests/test_workflow_emitter.py:1508-1526`) enforces throw-not-log-and-continue and asserts the phrase `review before relying on it` is absent from emitted scripts. The planned log passes both as designed, but an implementer unaware of the guard could word the message into a failure. | Added the guard to U2's approach and to R13: the missing-log is an annotation on the accept path, never a throw replacement, and its wording must avoid the banned phrase (the planned "verdict computed over …" complies). |
| F3 | P3 | U1's test-scenario cites mislabeled the emission shapes: `:763-784` and `:841-844` are both one-shot panels; the iterate-to-consensus singleton and thunk loops are covered at `:1528-1554` and `:1557+`. The `_emit_thunk` extraction range included the gate-call line (`:934`). | Corrected the shape-to-test mapping, added the iterate-loop test names, tightened the extraction range to `:935-955`, and extended the Sources cite to `:1504-1624`. |
| F4 | P3 | KTD1's null-on-error contract cited only harness documentation, with no in-repo evidence named. | Added the in-repo anchor: the shipped `v &&` guard at all three reconciliation sites is the existing code's acknowledgment that a verdict slot can be null. Also stamped the throw's provenance commit (b09ad50, saga 0.40.0) in the Problem Frame — verified via `git log -S` and `CHANGELOG.md`. |

## Readiness summary

- **Verification** — every `path:line` cite in the plan was checked against the working tree
  during this review or the same-session planning pass; the two claims that failed verification
  (F1's classifier, F3's test mapping) are fixed. The 0.40.0/#277 throw provenance, the absence of
  a JS test runner, the version pins (`tests/test_saga_plugin.py:48`,
  `tests/test_team_execution_plugin.py:64`), and the Layer B line cites all check out.
- **Assumptions** — the one non-repo assumption (harness resolves a failed verifier to `null`) is
  now labeled as harness contract with its in-repo corroboration (KTD1). The Q1 hang residue is
  resolved, not deferred silently (KTD2).
- **Requirement mapping** — issue R1–R11 adopted with stable IDs; plan R12–R15 trace to verified
  premise drift; acceptance examples AE1→U2, AE2→U4, AE3→U4 (`test_static_skip_no_floor`); the
  issue's `-k` filters (`missing_verifier`, `verify_panel`, `dimension_exclusion`,
  `static_skip_no_floor`) all have named tests in the matching files.
- **Open choices** — none left open: floor value (KTD3), timeout question (KTD2), message formats
  (High-Level Technical Design), and denominator arithmetic (KTD6) are all decided with rationale.

## Remaining findings

None. All four findings fixed in place.

## Residual risk

- Layer B remains prompt-enforced (no runtime computes the reviewer average); the plan's
  mitigation — drift-guard tests plus a worked "4 applicable → average 4" example — is the
  strongest enforcement available at that surface, but model compliance is still probabilistic.
- The `v && v.refuted` → null semantics rest on the cc-workflows harness contract; if the harness
  ever returns a non-null sentinel for failed agents, the missing-detection predicate needs
  revisiting (noted in KTD1).

## Links

- Plan: `docs/plans/2026-07-03-verify-panel-robustness-plan.md`
- Issue: infiquetra/infiquetra-claude-plugins#293
- Upstream requirements: `docs/brainstorms/2026-06-28-verify-panel-robustness-requirements.md`
- Prior readiness review (requirements): `docs/reviews/2026-06-28-verify-panel-robustness-readiness.md`
