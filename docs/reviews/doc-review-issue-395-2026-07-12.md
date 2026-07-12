# Doc Review — issue #395 deploy-handoff-ack plan (2026-07-12)

One-line verdict: **READY** — three findings, all safely fixed in place from repo evidence; one
P3 residual note remains open. No P0/P1 outstanding; `/work` is unblocked.

## Review-result contract

- **Target:** `docs/plans/2026-07-12-issue-395-deploy-handoff-ack-plan.md` (+ the paired spec
  `docs/plans/2026-07-12-issue-395-deploy-handoff-ack-spec.json`, edited in lockstep)
- **Reviewed revision:** working tree (pre-commit; plan and spec not yet committed)
- **Blocked:** no
- **Linked:** issue #395; plan saga `issue-395` (destination merge,
  orchestration cc-workflows-ultracode); outcome ship-ceremony-hardening sub-395
- **Method:** readiness-skeptic pass with security/deploy lenses triggered (the document touches
  authorization and deployment); factual claims verified against live repo reads
  (`handoff_envelope.py:57`, `lifecycle_state.py:39-42`, `deploy-state/SKILL.md` scratch
  sanction, version pins `test_saga_plugin.py:49` / `test_deploy_plugin.py:42`,
  `state.json.sagas[*]` field inventory, marketplace entries, DECISIONS anchors).

## Findings

| # | Pri | Finding | Status |
|---|---|---|---|
| F1 | P1 | U1/U2 sequencing gap: plan U1 said "derive payload per KTD3" but the saga-field read is U2's deliverable — a literal U1 implementer would invent the read or stall | **fixed** in place: U1 payload defaults `gate`; U2 owns the saga-record wiring (plan U1 scope + spec U1 prompt) |
| F2 | P2 | The saga-record read mechanism was unnamed — divergent implementations likely (import saga.py vs read state.json) | **fixed** in place: named `read_state(root)["sagas"][saga_id]` per `handoff_envelope.py:57` precedent; `deploy_autonomy`/`pr_refs` sourced from that record, absent -> `gate`/empty (plan U2 files + spec U2 prompt) |
| F3 | P3 | U3 exit-code convention unstated ("distinguishes clean from unacknowledged" could collide with error exits) | **fixed** in place: follows `ship_receipt.py read` precedent — 0 clean/no-handoff, 1 unacknowledged or error (plan U3 + spec U3 prompt) |
| D1 | P3 | `acknowledged_by` is asserted identity, not authenticated — an ack's author is whoever ran the CLI | **open** (accepted): consistent with the fleet's machine-local single-operator trust model; the sidecar is git-ignored local state, same posture as `ship_receipt.json` |

## Applied fixes

Three in-place edits to the plan and three matching spec-prompt edits (kept in lockstep so the
emitted workflow tells the same story); spec re-validated with `--require-receipts` (exit 0) and
the `.workflow.js` re-emitted after the edits.

## Residual risk from limited evidence

- `state.json.sagas[*].pr_refs` was absent from the sampled records (only set when `/work` writes
  it) — the fix already pins the empty-list degrade, so this is informational.
- The plan defers cockpit/`status_card` integration of the dropped-baton read to follow-up; AC5
  is satisfied by the module's own `reconcile` verb, which matches the issue's F2 wording
  ("a status/reconciliation read"), but an operator who only ever looks at the outcome cockpit
  will not see unacknowledged handoffs until that follow-up lands.
