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

**#677/U3 re-key:** the fleet broker's retirement strips the lease lifecycle from the
`engine_dispatch.py`, `outcome.py`, and `outcome_worktrees.py` rows. `retired:broker-free-(#677/U3)`
marks a cell whose broker seam is deleted with an accepted loss attached: dispatch admission and
cross-run worktree sweep are gone (two concurrent dispatches both proceed; abandoned outcome
worktrees are reclaimed through the operator path in
[`worktree-reclamation.md`](worktree-reclamation.md)). The external-engine settlement record is now
the self-authenticating `saga.close-receipt.v1` mint, and the outcome worktree's ownership record
is its registry entry — `reap_worktree` removes and deregisters authority-free. The hooks and
team-execution rows keep their broker lifecycle until their own retirement units land.

**#677/U4 re-key:** the batch lease concept retires, and the two `execution_spec.py` rows lose
their reserve/renew/release cells to `retired:broker-free-(#677/U4)`: `workflow_emitter.py`
validates the frozen reservation contract and reports the retired, broker-free outcome — no batch
lease is reserved, renewed, or settled (plan #677 KTD4: no batch lease exists to renew). The bind
cell keeps `lease_broker.claim_hook_agent` until U5 deletes the hook: with no live batch,
`reserve_hook_agent` falls back to the pre-#356 per-spawn `acquire_agent` admission, so spawned
children are still claimed through the hook until the wrapper goes.

| Source | Function or seam | Spawn form | Governor entry point | Lease pool | Acquire or reserve seam | Bind seam | Renewal seam | Release seam |
|---|---|---|---|---|---|---|---|---|
| `plugins/saga/scripts/execution_spec.py` | `_emit_panel_reconciliation` | verify-panel verdict agents | `concurrency_governor.ordered_chunks` | `agent` | `retired:broker-free-(#677/U4)` | `lease_broker.claim_hook_agent` | `retired:broker-free-(#677/U4)` | `retired:broker-free-(#677/U4)` |
| `plugins/saga/scripts/execution_spec.py` | `emit_workflow_script` | dependency-layer worker agents | `concurrency_chunks` | `agent` | `retired:broker-free-(#677/U4)` | `lease_broker.claim_hook_agent` | `retired:broker-free-(#677/U4)` | `retired:broker-free-(#677/U4)` |
| `plugins/saga/hooks/hooks.json` | `Agent|Task` | normal Saga Agent and Task calls | `concurrency_policy.AdmissionLimits` | `agent` | `lease_broker.reserve_hook_agent` | `lease_broker.claim_hook_agent` | `expiry-fence:no-cooperative-boundary` | `lease_broker.record_hook_terminal+record_hook_parent` |
| `plugins/team-execution/skills/team-execution/scripts/lease_protocol.py` | `team-execution-fan-out` | worker reviewer and validator waves | `concurrency_policy.AdmissionLimits` | `agent` | `lease_broker.reserve_hook_agent` | `lease_broker.claim_hook_agent` | `lease_protocol.renew` | `lease_protocol.teardown` |
| `plugins/saga/scripts/engine_dispatch.py` | `_dispatch_once` | registered external-engine runner | `retired:broker-free-(#677/U3)` | `agent` | `retired:broker-free-(#677/U3)` | `not-applicable:in-process-adapter` | `retired:broker-free-(#677/U3)` | `saga.close-receipt.v1:mint` |
| `plugins/saga/scripts/outcome.py` | `_reconcile_once` | outcome backend dispatch | `retired:broker-free-(#677/U3)` | `agent` | `retired:broker-free-(#677/U3)` | `not-applicable:in-process-adapter` | `retired:broker-free-(#677/U3)` | `retired:broker-free-(#677/U3)` |
| `plugins/saga/scripts/outcome_worktrees.py` | `ensure_worktree` | outcome-owned git worktree | `WORKTREE_CAP` | `worktree` | `registry.register` | `not-applicable:registry-entry` | `retired:broker-free-(#677/U3)` | `reap_worktree.deregister` |

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
