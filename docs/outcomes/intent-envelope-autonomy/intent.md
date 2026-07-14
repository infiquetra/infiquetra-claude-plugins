# Campaign intent envelope — intent-envelope-autonomy (outcome 2 of 2)

**Same operator envelope as outcome 1** (approved by Jeff 2026-07-14 up-front; full table in
`docs/outcomes/fleet-integrity-gates/intent.md` on `outcome/fleet-integrity-gates`). This outcome
runs under it unchanged: Workflows per wave (pool ≤ 3), mixed tiering with Fable xhigh on every
adversarial verify panel, serial auto-merge of green PRs, nonstop pacing, report-only spend.

## Scope (from objective #332)

Live leaves: #380, #373, #371, #450, #449, #372, #433.
Backfilled done (shipped before this outcome): #344 (PR #485), #375 (PR #486), #379 (PR #488).
Pruned (parked, NOT abandoned): #374, #376, #377, #378.

Edges: #380 → #373 → #371 → #449 (the envelope chain, ending at the risk apex
envelope-authorized merge); #372 → #433 (the mid-run adjustment pair); #450 independent.

Waves: **D** = #380 #450 #372 · **E** = #373 #433 · **F** = #371 then #449.
The #449 leaf (envelope-authorized merge) is the risk apex of the whole campaign: Fable panel
mandatory, page the operator on anything ambiguous there. **Closing parent #332 is
ALWAYS_OPERATOR — ask Jeff at campaign end.**

## Provenance

Outcome 1 (`fleet-integrity-gates`, 7/7 COMPLETE 2026-07-14) shipped the integrity gates this
outcome's autonomy features presuppose: agent-file lint, ownership lanes, pagination gates,
mutation canary, fake-adapter integrity, delegation-proof gate, e2e lifecycle harness.
