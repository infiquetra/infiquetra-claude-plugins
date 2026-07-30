---
title: defect(saga): outcome advance and handoff settled-guard are blind to codex-native outcome.dispatch.v2 records — cross-runtime double dispatch
repo: infiquetra-claude-plugins
type: defect
team: asgard
project: operations
status: Shaping
labels: defect, hermes-task, needs-plan
risk: high
handoff_maturity: requirements-ready
---

# defect(saga): outcome advance and handoff settled-guard are blind to codex-native outcome.dispatch.v2 records — cross-runtime double dispatch

### Objective
# defect(saga): outcome advance and handoff settled-guard are blind to codex-native outcome.dispatch.v2 records — cross-runtime double dispatch

## Objective

Make the Claude runtime's local dispatch derivation aware of the codex-native
`outcome.dispatch.v2` ledger vocabulary so that a native intent blocks re-dispatch as in-flight
and a protected `ack_kind=launched` acknowledgement counts as settlement — restoring the
cross-runtime "exactly one dispatch side effect" invariant (R5/R6 of the cross-runtime
acceptance plan) on a shared clone.

## Where this comes from

U4 (`u4-race`) of the cross-runtime Outcome acceptance harness (#605, outcome
lease-safe-runtime-continuity), run against the pinned runtimes Claude `794b4da6` (saga
0.105.0) and Codex `f3e1af75` (saga 0.78.0+codex.20260720120109). Harness commit `24501ba` on
branch `work/605-cross-runtime-acceptance`; scenario facts are recorded in the acceptance
evidence bundle and `docs/work-sessions/2026-07-20-issue-605-acceptance-progress.md`.

Two scenarios fail against production truth:

- **race-codex-first**: codex `advance` writes its native v2 intent; the launched runner
  produces the write-once backend effect and a receipt-validated
  `reconcile-dispatch --ack-kind launched` (chain verified working end to end). A subsequent
  Claude `advance` on the same clone **re-dispatches the natively-settled leaf** — the ledger
  ends with `settled_chains: 2` (one codex launched ack + one Claude legacy commit) for one
  leaf, i.e. a second real backend effect.
- **race-simultaneous**: barrier-released two-OS-process race; when codex enters first, Claude
  dispatches anyway, leaving one settled legacy chain plus a dangling un-acked codex intent
  (a missing dispatch unit).

The claude-first ordering is safe: codex's reducer is both v2- and legacy-aware (PA-2 /
infiquetra-codex-plugins PR #44), so the blindness is a one-directional asymmetry. This is the
Claude-side mirror of the cross-runtime ledger-vocabulary defects discharged in #627.

## Mechanism

Claude at `794b4da6` carries zero `outcome.dispatch.v2` references in
`plugins/saga/scripts/outcome.py`, `outcome_store.py`, and `outcome_compat.py`:

- `_dispatch_records` (outcome.py) derives the settled set from
  `kind == "dispatch" and phase == "commit"` only — a codex launched ack never settles a leaf
  in Claude's eyes.
- `_reconcile_once` treats a leaf with only a foreign v2 intent as "failed dispatch, re-drive"
  (its own crash-after-intent semantics), so it re-dispatches a leaf that is in-flight under
  codex's "intent until acked" model.
- `_settled_lookup` (the `accept_handoff` already-settled guard) consults only the #351
  dispatch-settlement run ledger, which codex-native intents/acks do not write — so even the
  sanctioned protected-handoff path cannot refuse a handoff for a natively-settled leaf.

## Acceptance criteria

- [ ] Claude's settled derivation counts a codex-native launched acknowledgement as settled:
      records matching
      `{"kind": "outcome.dispatch.v2", "phase": "ack" | "authority-ack", "ack_kind": "launched"}`
      settle their `subplot_id` (carrying `leaf_saga_id`) exactly like a legacy
      `{"kind": "dispatch", "phase": "commit"}` record.
- [ ] A live v2 intent without an acknowledgement reads as IN-FLIGHT: `advance` does not
      re-dispatch the leaf, mirroring codex's `intent-created` semantics, with an explicit
      liveness/reclaim path for stale intents instead of silent re-drive.
- [ ] `_settled_lookup` (handoff acceptance) returns settled for natively-settled dispatches so
      `accept_handoff` refuses with `handoff-already-settled`.
- [ ] Reducer parity with the codex arms (codex `outcome_store.py` v2 intent/ack arms) or an
      equivalent shared derivation, so the two runtimes read one ledger identically.
- [ ] Regression tests cover: codex-first ordering (no re-dispatch after native ack),
      simultaneous race (no dangling unit), and the handoff already-settled refusal.

## Verification

```bash
uv run pytest tests/ -q
uv run python tools/run_cross_runtime_outcome_acceptance.py \
  --claude-repo <clean-claude-checkout-at-fixed-sha> --claude-sha <fixed-sha> \
  --claude-saga-version <bumped> --claude-fleet-core-version <current> \
  --codex-repo <clean-codex-checkout> --codex-sha f3e1af75d06ac4c64a499f05e99c54903d978f35 \
  --codex-saga-version 0.78.0+codex.20260720120109 \
  --codex-fleet-core-version 0.10.0+codex.20260720120109 \
  --units u4-race --output /tmp/xr-u4-verify.json
# race-codex-first and race-simultaneous must report verdict "pass"
```

## Files

- plugins/saga/scripts/outcome.py
- plugins/saga/scripts/outcome_store.py
- tests/test_outcome_command.py
- tests/test_outcome_cross_runtime_contract.py

## Notes

Blocks #605 (the cross-runtime acceptance cannot go green at the current pins) and therefore
the lease-safe-runtime-continuity outcome close. Fix belongs in its own production PR — the
acceptance PR carries no production changes by design (KTD4).

### Intent
Restore the cross-runtime "exactly one dispatch side effect" invariant (R5/R6): a codex-native
`outcome.dispatch.v2` intent must read as in-flight and a protected launched acknowledgement as
settlement in the Claude runtime's advance dedup and handoff already-settled guard.

### Out-of-scope / non-goals
- No changes to the codex runtime (already v2- and legacy-aware after PA-2 / codex PR #44).
- No changes to the acceptance harness (it correctly reports this defect; KTD4 keeps the
  acceptance PR production-free).
- Not a redesign of the v2 ack/receipt protocol — consume the existing vocabulary only.
- The #627 findings (halt-record kinds, DispatcherError arm, guard scopes) stay in #627.

### Inputs inventory
- Codex reducer arms as the parity reference: infiquetra-codex-plugins
  `plugins/saga/scripts/outcome_store.py` (v2 intent/ack arms, `ack_kind` launched/handed-off)
  at `f3e1af75`.
- U4 evidence: `u4-race` scenarios `race-codex-first` / `race-simultaneous` in
  `tools/run_cross_runtime_outcome_acceptance.py` (branch `work/605-cross-runtime-acceptance`,
  commit `24501ba`) and `docs/work-sessions/2026-07-20-issue-605-acceptance-progress.md`.
- Claude sites: `outcome.py` `_dispatch_records`, `_reconcile_once` dispatch loop,
  `_settled_lookup`; `outcome_store.py` ledger reduction.

### Files expected to change
- plugins/saga/scripts/outcome.py
- plugins/saga/scripts/outcome_store.py
- tests/test_outcome_command.py
- tests/test_outcome_cross_runtime_contract.py
- plugins/saga/CHANGELOG.md
- plugins/saga/.claude-plugin/plugin.json
- .claude-plugin/marketplace.json

### Tests to add or update
- Settled derivation counts `{kind: outcome.dispatch.v2, phase: ack|authority-ack,
  ack_kind: launched}` as settled with its `leaf_saga_id`.
- A live v2 intent (no ack) is skipped by `advance` as in-flight (no re-dispatch), and a stale
  intent has an explicit reclaim path.
- `_settled_lookup` returns settled for a natively-settled dispatch so `accept_handoff`
  refuses `handoff-already-settled`.
- Ledger fixture mixing legacy and v2 chains reduces identically to the codex arms.

### Failure modes / pre-mortem
- Treating a bare v2 intent as settled would wedge a leaf whose codex launcher crashed —
  in-flight and settled must stay distinct states with a reclaim path for stale intents.
- Counting `ack_kind=handed-off` as launched settlement would fake a leaf id; only `launched`
  carries one.
- Divergence between this derivation and the codex arms re-opens the asymmetry — pin parity
  with a fixture shared across both vocabularies.

### Stop conditions
- If honoring v2 intents requires changing the v2 record schema itself, stop and coordinate a
  cross-repo contract change instead of a one-sided fix.
- If the fix would need to land inside the acceptance PR, stop (KTD4 — separate production PR).

### Context library links
- source_context: docs/work-sessions/2026-07-20-issue-605-acceptance-progress.md (U4 findings)

### Acceptance criteria
- [ ] `race-codex-first` and `race-simultaneous` in the #605 acceptance harness report
      verdict `pass` against a Claude pin carrying this fix.
- [ ] A codex-native launched ack settles its leaf in Claude's advance dedup and in
      `_settled_lookup`.
- [ ] A live v2 intent is in-flight (no re-dispatch), with an explicit stale-intent reclaim.
- [ ] Regression tests for all three behaviors are green in the full battery.

### Verification
```bash
uv run pytest tests/ -q
uv run python tools/run_cross_runtime_outcome_acceptance.py \
  --claude-repo <clean-checkout-at-fix-sha> --claude-sha <fix-sha> \
  --claude-saga-version <bumped> --claude-fleet-core-version <current> \
  --codex-repo <clean-codex-checkout> --codex-sha f3e1af75d06ac4c64a499f05e99c54903d978f35 \
  --codex-saga-version 0.78.0+codex.20260720120109 \
  --codex-fleet-core-version 0.10.0+codex.20260720120109 \
  --units u4-race --output /tmp/xr-u4-verify.json
```

### Handoff maturity
requirements-ready

### Suggested next action
Use `/plan <issue>` to create an implementation plan.

### Source context
- Source: /private/tmp/claude-501/-Users-jefcox-workspace-infiquetra-infiquetra-claude-plugins/a2c17e16-6a69-4ff8-a9f6-dc347823861a/scratchpad/v2-blindness-defect.md
- Source type: local-file
- Source title: defect(saga): outcome advance and handoff settled-guard are blind to codex-native outcome.dispatch.v2 records — cross-runtime double dispatch

### Recommended Tier Band
opus/high

## Created Issue

- URL: https://github.com/infiquetra/infiquetra-claude-plugins/issues/628
- Number: 628
- Created at: 2026-07-20T15:29:20.846369+00:00

