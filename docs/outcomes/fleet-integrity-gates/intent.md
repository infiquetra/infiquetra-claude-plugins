# Campaign intent envelope — fleet-integrity-gates → intent-envelope-autonomy

**Approved by the operator (Jeff) 2026-07-14 via explicit up-front interview.** This is the
run-start posture for a nonstop autonomous campaign over two sequential outcomes. (It is also a
manual dry run of exactly what #380/#373 will make first-class.)

## Envelope

| Decision | Value |
|---|---|
| Backend | Emitted Workflows per wave; total in-flight agents ≤ 3 (hard pool) |
| Tier | Mixed by work shape: Opus judgment builders, Sonnet mechanical, **Fable xhigh on every adversarial verify panel**. Discretionary builder upgrade to Fable when a leaf is architecture/contract-defining, novel design, or a prior Opus attempt failed verify. |
| Merges | Auto-merge green PRs serially (sibling-collision protocol: merge → pull main into next sibling → hand re-bump → CI arbitrates). Page only on CI red after one fix attempt, or a risky diff. |
| Pacing | Nonstop until BOTH outcomes complete; page only at genuine gates/exceptions. |
| Spend | Report-only, no ceiling; per-wave tracking, cumulative line in the final report. |

## Scope

- **Outcome 1 `fleet-integrity-gates`** (from #337): #422, #424, #427, #428, #431, #457, #458.
  Waves: A = #422 #424 #431 · B = #427 #457 #458 · C = #428.
  Pruned (parked, NOT abandoned): #423, #425, #426, #430, #464, #465, #466; #429 pruned as
  already shipped. **Objective #337 stays open.**
- **Outcome 2 `intent-envelope-autonomy`** (from #332): #380, #373, #371, #450, #449, #372, #433.
  Waves: D = #380 #450 #372 · E = #373 #433 · F = #371 → #449.
  Closing parent #332 is ALWAYS_OPERATOR.

## Standing constraints

Commit-before-verify; verify panels run the `saga:readonly-verifier` profile in worktree
isolation; release-surface tri-lock in every shipping PR; engineering-journal capture in the same
commit; `advance --persist` per tick; board writes only through the reversibility certificate;
PR merge and parent-issue close per the table above — never silent.
