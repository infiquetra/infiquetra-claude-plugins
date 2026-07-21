---
title: Doc review — issue #627 lease-seam and guard-scope plan
target: docs/plans/2026-07-20-issue-627-lease-seam-guard-scope-plan.md
reviewed_revision: working tree at origin/main 83a170ff (plan uncommitted)
date: 2026-07-20
blocked: false
linked_issue: https://github.com/infiquetra/infiquetra-claude-plugins/issues/627
linked_spec: docs/plans/2026-07-20-issue-627-lease-seam-guard-scope-spec.json
---

# Doc review — issue #627 lease-seam and guard-scope plan

**Verdict: READY.** No P0/P1 findings remain; two evidence-backed safe fixes applied in place.
The plan can drive implementation without the executing agent inventing decisions.

## Review method

Classification: plan (path `docs/plans/`, `origin:`/Implementation Units/KTD shape). Readiness-
skeptic pass with a full independent anchor audit — every cited line number, symbol, test name,
and mechanism claim re-verified against the tree at `83a170ff` via batched grep/sed probes.
External-engine offer: stored preference, no prompt required, no panel dispatched (advisory
helper returned `intent: none`).

## Anchor audit results (all verified exact unless noted)

- Halt-append collision sites `outcome.py:1314`/`:1383`/`:1552` — confirmed live: literal
  `"kind": "dispatch"` first, `**receipt` spread last, so the receipt's `halt`/`spend-halt`
  kind wins. Matches KTD4's fix direction (spread-first, literal-last).
- Arms `outcome.py:1519` (`BackendRateLimitError`) / `:1547` (`BackendHaltError`) exact;
  `DispatcherError` caught nowhere in `outcome.py`. Sibling release call
  `outcome_store.release_lease(store, f"dispatch-{sid}", holder)` matches U2's constraint;
  `release_lease` signature confirmed at `outcome_store.py:670`.
- Intent append at `outcome.py:1447` (`append_ledger` call), `phase: intent` + `key` in body.
- `LEDGER_CLASSIFICATIONS` closed vocabulary at `dispatch_settlement.py:38`; `SILENT_NOOP`
  member confirmed; frontier dispatch-id derivation at `dispatch_settlement.py:1525` verbatim.
- `DispatchRequest.dispatch_id`/`attempt` at `outcome.py:109-110`; single `make_dispatcher`
  site `:2515-2518`; second `default_lease_authority` consumer `:2571` (out of scope, correct).
- Broker: `_drop_superseded_resource_lease` `lease_broker.py:2116` with settlement-retained and
  canonically-closed arms above the pop (plan's precedence constraint correct); `_expired`
  predicate `:1804`; `LeaseOwnershipError` `:220`; `acquire_agent` `:2197`.
- Dispatcher: `DispatcherError` class `:62`, admission raise `:276`, renew raises `:282`/`:286`;
  `HaltReceipt` kind `"halt"` `:99`; `SpendHaltReceipt` kind `"spend-halt"` `:648`;
  self-acknowledgment docstring (~`:630-634`) confirmed.
- Guards: `_refuse_unsafe_handoff_ancestors` `outcome_compat.py:1154`;
  `_refuse_unsafe_ancestors` `audit_store.py:147`; `S_ISVTX` occurs nowhere in `plugins/`
  (defect confirmed); group-writable twin absent from the compat suite (R6 gap confirmed).
- Tests: `test_retry_supersedes_at_full_capacity` `tests/test_fleet_lease_broker.py:734`;
  `_halt` fixture `tests/test_outcome_report.py:74`;
  `test_halt_then_recovered_is_not_a_sticky_ambiguity` `:167`;
  `test_live_native_intent_reads_in_flight_not_redriven` `tests/test_outcome_command.py:761`;
  `test_ensure_private_dir_exempts_paths_outside_home` `tests/test_audit_store.py:204` and the
  group-writable acceptance `:230`. `scripts/check_release_surface_parity.py` exists.

## Applied fixes

| # | Fix | Evidence |
|---|-----|----------|
| F1 | R7 + Verification grep gate scoped to `--include='*.py'`; historical fleet-core `CHANGELOG.md:19` occurrence declared exempt; U5 gains the constraint that the new CHANGELOG entry corrects the 0.16.x-era claim | `grep -rn 'covers every caller' plugins/` returns TWO sites — `audit_store.py:157` (source, U4 deletes) and `fleet-core/CHANGELOG.md:19` (historical release note; retro-editing history would misrepresent what 0.16.x shipped). As written the gate could never pass. |
| F2 | Stale anchor `outcome_dispatcher.py:256-258` → `:216-220` for the `getattr` fallback | grep: the `dispatch_id`/`attempt`/`idempotency_key` getattrs sit at `:218-220` with the comment at `:216`; nothing at `:256-258`. |

## Remaining findings

| ID | Priority | Status | Finding |
|----|----------|--------|---------|
| — | — | — | None. |

## Residual risk from limited evidence

The `BackendHaltError` arm's settlement classification (U2's `SILENT_NOOP` precedent) was
verified pre-compaction but not re-probed this pass; the arm body's settle call was confirmed
present at `:1552-1560`. The acceptance-harness `contract_digests` halt behavior (KTD5's
`port-digest` window) is asserted from the prior grounding session, not re-run — it is a
documented-boundary claim, not an implementation input.
