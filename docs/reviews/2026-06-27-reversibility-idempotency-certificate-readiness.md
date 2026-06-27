---
date: 2026-06-27
kind: doc-review
target: docs/brainstorms/2026-06-27-reversibility-idempotency-certificate-requirements.md
reviewed_revision: working tree (fixes applied on top of commit aea37b9)
blocked: false
---

# Readiness Review — Reversibility/Idempotency Certificate

## Readiness summary

**READY to drive planning.** No `P0` or `P1` findings remain open. This was a heavy but coherent
revision: the core thesis (one conservative, enumerated, default-gate authority for reversibility-gated
autonomy, autonomy-write-first, subsuming the reversibility-based checks) survived intact, but the first
draft over-simplified the shipped degrade semantics, named abstract ops instead of the real
mission-control verbs, assumed a write adapter that does not exist, and overclaimed "one authority for
autonomy." Eight `P1`s, five `P2`s, and two `P3`s surfaced; all were resolved by evidence-backed
in-place fixes. The residual deferred items are genuine `/plan` mechanism (certificate home, registered-
inverse representation, board idempotency-key design, equivalence-proof method, leaf-state→board
mapping), not unverified assumptions.

This review ran codex (`gpt-5.5`, xhigh, read-only with repo access) and agy (`Gemini 3.1 Pro (High)`,
hermetic) as **gated generators under Claude-side verification** — each finding was checked against the
doc or cited source before adoption. The two engines plus Claude converged on the two load-bearing
problems (the "one authority" overclaim and the unbounded comment abort-cost); each surfaced distinct
net-new findings (codex from repo access: `had_side_effect` is duplicate-prevention not reversibility,
the degrade order is 5-way not "default DEGRADE," the allowlist omits the real `sdlc_manager` ops, the
close adapter is deferred/unbuilt; agy: facts-only re-scatters policy, the boundary lacks failure
bounds; Claude: the op-type-vs-op-instance subject ambiguity and the `computes`/`enumerated`
contradiction), and neither parroted. Every codex codebase claim was verified true before adoption —
including the citation correction that the doc's `outcome.py:369-373` pointed at the cockpit snapshot,
not the deferral, which actually lives at `outcome.py:1062-1065`.

## Applied fixes (15)

All edits are evidence-backed (verified source or internal consistency).

- **Scoped the "one authority" claim (title + KD3 + new R13).** Verified `degrade_decision`
  (`outcome_dispatcher.py:256-290`) gates on `attending` and `guarantee_bearing` — neither a
  reversibility fact — and `elevated_risk` (`lifecycle_state.py:180`) gates backend selection, not
  autonomy. The certificate now owns "the reversibility/duplicate-side-effect facts that gate autonomous
  writes," not all autonomy.
- **Centralized verdict, not raw facts (KD1 + R1).** The certificate exposes an `authorize_write`
  verdict for the new writer (policy in the authority), while supplying only the `side_effected` fact
  into the *unchanged* degrade order — resolving the "facts-only re-scatters policy" objection.
- **`had_side_effect` preserved as duplicate-prevention, not reversibility (KD3 + R10).** It is the R23
  no-duplicate-side-effect HALT (`outcome_dispatcher.py:271`); kept verbatim in behavior, not recast.
- **Full degrade order preserved (R11 + F3 + AE6).** The "default DEGRADE" framing was wrong; the doc
  now names the 5-way order (`available → attending → guarantee_bearing → side_effected →
  lower-rung-or-HALT`) and supplies only one fact into it.
- **Allowlist named in real mission-control ops (KD4 + A3 + R5/R16).** Abstract "status-move" → real
  verbs (`set-field` Status, issue-label add/remove, sub-issue close, comment), per `sdlc_manager.py`.
- **Close adapter is v1 work (R15 + AE2).** Verified deferred/unbuilt (`outcome.py:1062-1065`,
  `issue_close = None`); an op cannot be allowlisted without its adapter + inverse.
- **Comment abort-cost bounded by construction (R6).** Autonomous comments are coalesced (one per
  meaningful transition), so the additive justification is enforced, not asserted.
- **Failure path added (R18 + F4 + AE8).** AUTHORIZED-then-failed writes get bounded idempotent retry +
  fail-loud-to-operator; the recurring `create-prepared` defect lives on exactly this boundary.
- **Idempotency demoted from tier to universal precondition (KD4 + R9).** It applies to every write, so
  it is not a membership tier — leaving two reason-tiers (reversible, additive).
- **`computes` → `declares` (R2).** Reconciled with KD2's "enumerated, not a solver"; facts are declared
  per allowlisted op.
- **Op-kind vs op-instance subjects distinguished (R2).** Reversible/additive are op-kind facts;
  `side_effected` is an op-instance fact; the authority answers both.
- **Label scope narrowed (KD4 + R5).** Issue-field labels only; repo label-definition mutations excluded.
- **Citation corrected.** `outcome.py:369-373` (cockpit snapshot) → `outcome.py:1062-1065` (the real
  deferral) and `outcome_projection.py:12-18` (no auto-push).
- **Parent-close justification fixed (KD3 + R7 + AE3).** It is in `ALWAYS_OPERATOR` because it is
  deliberate policy (R25), independent of reversibility — the unsourced "reversible" rationale removed.
- **Idempotency-key pointer softened (Outstanding Questions).** `promote_scan.py:47` is scanner-specific;
  board ops need their own key (issue-number + target-state).

## Findings by priority

| Pri | Finding | Source | Status |
|-----|---------|--------|--------|
| P1 | "One authority for autonomy" overclaims — attending/guarantee/elevated_risk not subsumed | codex + agy + claude | Fixed |
| P1 | Facts-only leaves policy scattered into consumers — expose a centralized write verdict | agy + claude | Fixed |
| P1 | `had_side_effect` is duplicate-prevention (R23), not a reversibility check | codex | Fixed |
| P1 | Degrade "default DEGRADE" over-simplifies the shipped 5-way order | codex | Fixed |
| P1 | Allowlist names abstract ops, not the real `sdlc_manager` board verbs | codex | Fixed |
| P1 | Allowlisted nonprod-close adapter is deferred/unbuilt — v1 must build it | codex | Fixed |
| P1 | Comment abort-cost asserted, not bounded (notification spam risk) | codex + agy + claude | Fixed |
| P1 | New autonomous saga↔mission-control boundary lacks failure bounds | agy + claude | Fixed |
| P2 | "Idempotent" listed as a tier but is a universal precondition | agy + claude | Fixed |
| P2 | R2 "computes" contradicts KD2 "enumerated, not a solver" | claude | Fixed |
| P2 | Certificate subject ambiguous — op-kind vs op-instance facts | claude | Fixed |
| P2 | Label add/remove ambiguous across issue-field and repo labels | codex | Fixed |
| P2 | Deferred-mutation citation pointed at the cockpit snapshot | codex | Fixed |
| P3 | Parent-close "reversible" justification unsourced and irrelevant | codex | Fixed |
| P3 | Idempotency-key reuse pointer cites a scanner-specific key | codex | Fixed |

## Residual risk from limited evidence

Low-to-moderate. The doc now names each subsumed check and real op against **verified** source
(`outcome_dispatcher.py:256-290`/`:271`, `outcome_projection.py:81`, `outcome.py:1062-1065`,
`sdlc_manager.py:1043`, `lifecycle_state.py:164-183/:180`). The genuine sizing risk is concentrated in
the net-new write/close adapters and the failure-handling path on a boundary with a known recurring
defect — located and scoped by R15/R18, not hidden. The equivalence-proof obligation (R10–R14) is real
but bounded: `degrade_decision` is a small pure function with an enumerable decision table, so golden
tests are a tractable `/plan` step.

## Scope observation (operator's call, not a blocker)

The v1 scope (autonomy authority only; subsume both reversibility-based invariants; do not touch the
backend recommender) is a deliberate operator decision confirmed during brainstorm. Both engines
respected it. The one place a reviewer could still push: v1 now includes net-new adapter code (write +
close/reopen) plus a failure-handling path, which is more build surface than a pure "add an authority"
framing implies — but it is the irreducible cost of shipping the *first* autonomous writer, and the doc
states it plainly (R15, R18). No reduction is required for readiness.
