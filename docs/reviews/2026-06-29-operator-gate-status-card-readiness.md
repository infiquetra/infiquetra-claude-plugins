---
date: 2026-06-29
kind: doc-review
target: docs/plans/2026-06-29-operator-gate-status-card-plan.md
reviewed_revision: e3b1d23 (+ in-place review fixes applied this pass)
blocked: false
---

# Operator Gate-Status Card plan — readiness review

**READY to drive implementation.** No `P0` or `P1` findings remain open. One P1 dead-wiring defect
and three P2 coverage gaps were surfaced and **all fixed in place**; six P3 polish items were fixed
or (one) dropped as immaterial after adversarial verification. Method: an ultracode adversarial-verify
workflow — five readiness lenses (with a dedicated **agy-delegation-compliance** lens at xhigh), each
finding refuted by two perspective-diverse verifiers (evidence-accuracy + materiality), then
synthesized. 11 raw findings; 11 survived refute-2; the synthesizer dedup'd and finalized priorities,
dropping one to `none`.

## Special focus — agy delegation compliance (operator request)

The plan's Execution Method (KTD7) is **compliant** on all eight core documented `/agy:delegate`
findings: named-spawn-is-the-only-invocation (with the expected first-action-failure→recover note),
no `--background`, `/agy:delegate` front door (no hand-rolled shell), Claude sole-committer, post-hoc
verify, archive-each-draft provenance, commit-each-unit orphan hazard, tight allow-set. The model id
is correct (`--model pro` = `Gemini 3.1 Pro (High)`). Two real gaps against the canonical floor were
found and fixed: (a) the post-hoc floor had dropped **mutation-proofing** (kept only "read the diff" —
`blueprint.md:152-154` pairs both), and (b) the **first Pro run** carried no escalation contingency
(Pro's agency is unobserved; the clone-jail escalation trigger from DECISIONS `#agy-delegated-build-no-jail`
is now named).

## Applied fixes (in place, this review)

- **P1 — `project_resume` dead-wiring:** redefined the `/resume` summary rows from the mis-imported
  outcome-DAG concepts (Open leaves · Ready frontier) to what Phase 3a actually reconstructs for a
  single thread (Phase/destination · Blockers · Open questions · Last gate verdicts · Route), each
  sourced from a real Phase-3a output. Resolves the requirements' "(confirm at /plan)" flag.
- **P2 — mutation-proofing:** added to the post-hoc verification floor, paired with the diff-read.
- **P2 — `/qa` FAIL test:** added a U3 scenario asserting `project_qa` renders the failure glyph +
  ref on a FAIL verdict (never blocked/not-reached).
- **P2 — `--gate-verdict` colon-parse:** added the split-on-first-two-colons rule to U2 build and a
  U2 test scenario with a colon-bearing PR-URL ref.
- **P3 — Pro escalation trigger:** named the clone-jail escalation in the agency-leak risk row.
- **P3 — R12 external-read test:** added a U3 scenario for a determinable GitHub CI/merge ref.
- **P3 — AE10 guard:** named the specific status tokens to assert absent vs evidence tokens to keep.
- **P3 — U6 version pin:** added `tests/test_saga_plugin.py` to U6 files; reworded "stay green" to
  "update the pin in the same unit."
- **P3 — U1 `--self-test`:** added a subprocess self-test scenario mirroring `completeness_gate`.
- **P3 — outcome glyph clarity:** clarified non-terminal summary rows use shared glyphs with no
  per-node collapse (a per-node table would contradict R6/AE3).

## Findings by priority

| Pri | Finding | Lens | Status |
|-----|---------|------|--------|
| P1 | `project_resume` "Open leaves · Ready frontier" rows have no producer in `/resume`'s single-thread reconstruction | adversarial/dead-wiring | Fixed |
| P2 | Post-hoc verification floor omits mutation-proofing of delegate-written tests | agy-compliance | Fixed |
| P2 | AE9 `/qa` FAIL-verdict sub-case has no per-unit test | requirement-mapping | Fixed |
| P2 | U2 `--gate-verdict` colon-delimited parse has no test (refs contain colons) | test-realism | Fixed |
| P3 | First Pro run adopts Flash-validated posture without escalation contingency | agy-compliance | Fixed |
| P3 | R12 external-read ref type claimed but not positively tested | requirement-mapping | Fixed |
| P3 | Outcome-state vocabulary → card glyph mapping under-specified (finding partly misread R6/AE3) | adversarial/dead-wiring | Fixed (clarified, no per-node table) |
| P3 | U5/AE10 retired-marker guard too generic to prove R14 single-emitter | adversarial/dead-wiring | Fixed |
| P3 | U6 version bump breaks the hardcoded version pin in `test_saga_plugin.py` | test-realism | Fixed |
| P3 | U1 `--self-test` built but not exercised by any test | test-realism | Fixed |
| — | Scope guard omits structured channels (PLAN_GAP/TEST-CONFLICT/PATH-MISSING) | agy-compliance | Dropped (verifiers → `none`; free-form "STOP and report" adequate given containment) |

## Residual risk

- The P1 fix is a **design resolution** (the `/resume` rows now match Phase 3a's grounded outputs),
  not just an edit — it should be re-confirmed at `/work` U4 against the live `/resume` reconstruction
  state, but the row→source mapping is now explicit and derivable.
- The grounding-accuracy lens returned **zero findings** — the plan's cited `file:line` facts checked
  out — so confidence in the grounding is high.
- This remains the **first Pro delegated build**; Pro's agency profile is genuinely unobserved. The
  escalation trigger is now documented, but watch the first one or two units closely.

## Links

- Plan: `docs/plans/2026-06-29-operator-gate-status-card-plan.md`
- Issue: infiquetra/infiquetra-claude-plugins#278
- Source (requirements): `docs/brainstorms/2026-06-27-operator-gate-status-card-requirements.md`
- This artifact: `docs/reviews/2026-06-29-operator-gate-status-card-readiness.md`
