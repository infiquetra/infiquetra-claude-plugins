# Concurrency and lease spawn-site inventory (#350, #356)

This is the canonical machine-readable inventory of production Saga fan-out and resource-spawn
seams. Every row records both the concurrency governor and the complete lease lifecycle. The
conformance test discovers executable Workflow, external-runner, outcome-dispatch, and worktree-add
calls; validates the installed Agent/Task hook metadata; and fails when a discovered seam is absent
or any lifecycle cell is empty.

Panels use `concurrency_governor.ordered_chunks`; mixed worker layers use `concurrency_chunks`,
which delegates to `concurrency_governor.ordered_policy_chunks`. Both public paths delegate to the
single `_bounded_ordered_chunks` ordering primitive. One private `_emit_parallel_wave` helper owns
the executable `parallel([` opener and `])` closer, snapshots the supplied bounded member sequence,
and invokes the caller's renderer once per snapshot entry. The structural guard requires exactly
the two inventoried Workflow call sites, a direct governor assignment, iteration of the governed
collection, and the unchanged direct chunk target as `bounded_members`. Literal or obscured opener
and closer emissions outside the helper fail closed.

`not-applicable:in-process-adapter` means the launch API returns synchronously without a provider-
assigned child identity; the exact acquired token is already bound to that call. `expiry-fence:no-
cooperative-boundary` means a foreground Agent/Task has no safe boundary while the provider call is
running: it may outlive its TTL, but later delegated mutation is rejected instead of silently
renewed. These are explicit lifecycle postures, not blank exemptions.

| Source | Function or seam | Spawn form | Governor entry point | Lease pool | Acquire or reserve seam | Bind seam | Renewal seam | Release seam |
|---|---|---|---|---|---|---|---|---|
| `plugins/saga/scripts/execution_spec.py` | `_emit_panel_reconciliation` | verify-panel verdict agents | `concurrency_governor.ordered_chunks` | `agent` | `workflow_emitter.reserve` | `lease_broker.claim_hook_agent` | `workflow_emitter.renew` | `workflow_emitter.release` |
| `plugins/saga/scripts/execution_spec.py` | `emit_workflow_script` | dependency-layer worker agents | `concurrency_chunks` | `agent` | `workflow_emitter.reserve` | `lease_broker.claim_hook_agent` | `workflow_emitter.renew` | `workflow_emitter.release` |
| `plugins/saga/hooks/hooks.json` | `Agent|Task` | normal Saga Agent and Task calls | `concurrency_policy.AdmissionLimits` | `agent` | `lease_broker.reserve_hook_agent` | `lease_broker.claim_hook_agent` | `expiry-fence:no-cooperative-boundary` | `lease_broker.record_hook_terminal+record_hook_parent` |
| `plugins/team-execution/skills/team-execution/scripts/lease_protocol.py` | `team-execution-fan-out` | worker reviewer and validator waves | `concurrency_policy.AdmissionLimits` | `agent` | `lease_broker.reserve_hook_agent` | `lease_broker.claim_hook_agent` | `lease_protocol.renew` | `lease_protocol.teardown` |
| `plugins/saga/scripts/engine_dispatch.py` | `_dispatch_once` | registered external-engine runner | `concurrency_policy.AdmissionLimits` | `agent` | `engine_dispatch.dispatch` | `not-applicable:in-process-adapter` | `LeaseBroker.renew` | `LeaseBroker.release` |
| `plugins/saga/scripts/outcome.py` | `_reconcile_once` | outcome backend dispatch | `concurrency_policy.AdmissionLimits` | `agent` | `outcome_dispatcher.make_dispatcher` | `not-applicable:in-process-adapter` | `LeaseBroker.renew` | `LeaseBroker.release` |
| `plugins/saga/scripts/outcome_worktrees.py` | `ensure_worktree` | outcome-owned git worktree | `WORKTREE_CAP` | `worktree` | `_arm_worktree` | `worktree_lease_receipt` | `reconcile_worktree_leases` | `reap_worktree` |

[`sandbox-spawn-sites.md`](sandbox-spawn-sites.md) separately inventories containment requirements.
The inventories cross-link because verify-panel and external-engine rows are both concurrency-
governed and sandbox-sensitive, but the lease table must not absorb sandbox policy columns.

## Operator inspection and recovery

Use the read-only broker view first; it redacts fencing tokens and the authority path:

```bash
python3 plugins/saga/scripts/lease_broker.py inspect
```

For crashed owners, stop any surviving child first and then let the canonical sweeper derive expiry
and process death:

```bash
python3 plugins/saga/scripts/lease_broker.py sweep
```

Do not edit `registry.json`, copy a token from a receipt, or fabricate a release call. A live owner,
an ambiguous child, a mismatched worktree registry, or a failed reap stays retained for the owning
coordinator to resolve. Version or installation diagnostics are recovered by installing the required
fleet-core release and rerunning the original preflight; bypassing hooks is outside the supported
runtime contract.
