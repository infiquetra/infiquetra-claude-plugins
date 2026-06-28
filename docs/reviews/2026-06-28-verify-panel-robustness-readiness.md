---
date: 2026-06-28
target: docs/brainstorms/2026-06-28-verify-panel-robustness-requirements.md
reviewed_revision: working tree
review_type: requirements readiness (saga /doc-review)
verdict: READY
blocked: false
---

# Readiness Review — Verify-Panel Robustness (Non-Applicable vs Failed Panel Members)

## Verdict

**READY for `/plan`** after a heavy reframe. The draft unified two genuinely different absences — a
**statically non-applicable** reviewer (precondition absent, permanent) and a **runtime-failed**
verifier (error/hang, transient) — into one "missing verdict" mechanism governed by a single quorum
floor. A full three-engine adversarial panel plus a pre-registered Claude-side critique converged on
that unification as a `P0`: a permanent skip placed under the runtime floor either loops forever on
re-spawn or silently bypasses the floor. Separately, the draft's core premise was wrong — it called
the null-verifier case "undefined" when the emitter shows it is *defined and silently uphold-biased*.
Both defects are fixed in place: the mechanism is split (static non-applicability is excluded from the
denominator at composition; runtime failure recomputes the threshold over reporters), and both layers
are re-grounded in the existing code surfaces they actually modify. The scope did not change — the two
operator-chosen layers remain, both review engines affirmed excluding the already-shipped cost levers.
No `P0` remains.

## Method

Three external engines ran as gated generators under Claude-side verification; every finding was
checked against the document or repo source before adoption.

- **Codex / gpt-5.5** at `xhigh`, read-only, repo access — ran **wrapped through Headroom** this pass
  (`headroom wrap codex -- exec …`; the wrap arg-forwarding passed its smoke test, so this is the
  first confirmed wrapped run — the R15b session had to let a bare run stand). Codex independently
  reframed the premise (it found `v && v.refuted` at `execution_spec.py:507` "silently becomes 'no
  refutation' under the original N threshold, with no missing-verdict record, floor, or escalation")
  and confirmed via repo grep that no implementation/test exists for the new concepts (a dead-wiring
  signal). It also surfaced the `architecture-reviewer.md:79-80` N/A→8.0 default that reframed Layer B.
- **agy / Gemini 3.1 Pro** and **agy / Gemini 3.5 Flash**, hermetic (doc inlined, no repo access) —
  both independently raised the unification `P0` (Pro via the infinite re-spawn loop on a permanent
  skip; Flash via the skip bypassing the floor), the deferred team-execution denominator, and the
  even-`(n−k)` tie gap. Both affirmed the scope exclusions as correct.
- **Claude-side pre-registration + independent code read** — four findings predicted before the
  engines returned; the emitter (`execution_spec.py`) was read directly, which found the premise
  reframe (silent uphold-bias) and the invented-escalation gap before the engines confirmed them.

**Convergence as evidence.** The `P0` was hit by both agy engines independently and is logically sound
on inspection; the premise reframe was found by Claude's code read *and* codex's repo access. Three
independent angles, one defect each — strong signal these are real, not single-model artifacts. One
hermetic finding (agy-Pro: "remove 'never silently dropped', already shipped") was **rejected as
stated** — it conflated the shipped fan-out *target* reconciliation with verifier *verdict* dropping,
which the code shows is the actual gap; downgraded to a precision clarification.

## Applied fixes

All evidence-backed; the document was edited in place.

| # | Fix | Source | Evidence |
|---|---|---|---|
| 1 | Split the unification: static non-applicability excluded at composition (R2); runtime failure recomputes over reporters (R3). Resolves the infinite-loop / floor-bypass `P0` | agy-Pro `P0` + agy-Flash `P0` + Claude (pre-registered) | a permanent skip under the floor re-spawns forever or bypasses it (doc KD1, R2-R4) |
| 2 | Premise restated: not "undefined" but "silently uphold-biased" — a null is dropped from the count while the threshold stays fixed | Claude (code read) + Codex | `execution_spec.py:507` (`v && v.refuted`), `:486,:510` (⌈n/2⌉ of declared n) |
| 3 | R3/R4 escalation rescoped to the existing advisory `log()` — no invented re-spawn/operator/`inconclusive` state | Claude + Codex | only consumer is a `log()` warning; coarse advisory signal (`execution_spec.py:477-481, 511-515`) |
| 4 | Layer B regrounded: it is not absent — the fix replaces the fabricated N/A→8.0 dimension default with exclusion from the average | Codex (repo grep) + Claude | `architecture-reviewer.md:34, 75-80` |
| 5 | team-execution unanimous-ACCEPT denominator defined now (exclude the skipped dimension), not deferred | agy-Pro `P1` + agy-Flash `P1` | `consensus-protocol.md:67` |
| 6 | Even-`(n−k)` tie handling made explicit: `majority` ⇒ ⌈(n−k)/2⌉ | agy-Pro `P2` + agy-Flash `P1` | matches the shipped ⌈n/2⌉ rule (`execution_spec.py:486`) |
| 7 | Budget-exhaustion mitigation acknowledged; residue narrowed to die/hang-without-emitting | Claude (code read) | `BUDGET_RIDER` `execution_spec.py:438,447`; test `:771` |
| 8 | Acceptance examples made concrete; AE3 rewritten from a no-op to the static-vs-runtime boundary | agy-Pro `P3` + agy-Flash `P2` | doc AE1-AE3 |
| 9 | Dead-wiring guard strengthened: every new field attaches to an existing producer+consumer surface | Codex | no impl/test for the new concepts (`LEARNINGS.md:126-136`) |

## Findings by priority (post-fix status)

| Priority | Finding | Engine(s) | Status |
|---|---|---|---|
| P0 | Static skip + runtime failure unified under one floor (loop / bypass) | agy-Pro + agy-Flash + Claude | Fixed (split at the floor; static excluded at composition) |
| P1 | Premise mis-stated ("undefined" vs silently uphold-biased) | Claude + Codex | Fixed (restated against the emitter) |
| P1 | R3 escalation invents machinery (re-spawn/operator) | Claude + Codex | Fixed (rescoped to the advisory log) |
| P1 | team-execution denominator deferred | agy-Pro + agy-Flash | Fixed (defined now) |
| P1 | Layer B treated as absent; N/A→8.0 default ignored | Codex + Claude | Fixed (exclusion replaces the fabricated default) |
| P2 | Even-`(n−k)` tie handling | agy-Pro + agy-Flash | Fixed (⌈(n−k)/2⌉) |
| P2 | Acceptance examples not concrete | agy-Pro + agy-Flash | Fixed |
| P3 | R1 "never silently dropped" imprecise | agy-Pro (downgraded) | Fixed (clarified target-reconcile vs verdict-drop) |
| P3 | Dead-wiring guard | Codex | Fixed (R11 attaches to existing surfaces) |
| — | Scope exclusions correct | agy-Flash (affirm) | Confirmed (no change) |

## Residual risk

- **The win is a more honest advisory signal, not a new gate.** Layer A keeps the panel advisory — it
  makes the `log()` truthful about missing verifiers and the recomputed denominator. It does not add a
  blocking gate, by design; an operator still acts on the signal. This is recorded honestly rather than
  oversold.
- **Q1 is genuinely unresolved.** Converting a *hung* (non-erroring) verifier into a recorded missing
  verdict may need a verifier-level timeout; if none cleanly exists, Layer A covers errored-but-not-hung
  verifiers only. This is the first `/plan` task.
- **Two-plugin blast radius.** Layer A lives in saga (`execution_spec.py`); Layer B in team-execution
  (`architecture-reviewer.md`, the consensus average). The shared principle is clean, but the two
  surfaces are edited independently and must be planned as such.
- **The static/runtime split must hold in implementation.** The whole `P0` fix rests on resolving a
  precondition *before* dispatch. A plan that resolves it at reconciliation time would reintroduce the
  loop/bypass; `/plan` must keep the composition-time boundary.
- **Single-routing note (positive).** codex ran wrapped through Headroom this pass (routing +
  accounting captured); no integrity caveat.

## Next step

Hand off to `mission-control` as a `capability` issue on the operations board (objective
`improve-claude-plugins`, team `campps`), same pipeline as S-1 (#275) … R15b (#291). Recipient action:
`/plan`, whose first task is the Q1 verifier-liveness gate, then the minimum-quorum floor value and the
representation of an excluded dimension / recorded missing verifier. Build Layer A (the saga
reconciliation) and Layer B (the team-execution dimension average) as independently-gated surfaces.
