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
assigned child identity; the exact acquired token is already bound to that call. This is an
explicit lifecycle posture, not a blank exemption. (The `expiry-fence:no-cooperative-boundary`
posture retired with the last cell that used it, #677/U5.)

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
cell kept the lease hook's claim seam at that point; U5 retired it with the hook itself.

**#677/U5 re-key:** the lease lifecycle hook and the saga broker wrapper are deleted whole, and
their manifest registrations are removed in the same commit. Every remaining lease cell in this
table — the bind cell of the two `execution_spec.py` rows and all four lease cells of the
`hooks.json` row (its admission governor included) — becomes `retired:broker-free-(#677/U5)`. Normal
Agent/Task spawns carry no lease admission at all now. **#677/U6 re-key:** the team-execution lease
protocol is deleted whole — the `lease_protocol.py` row is removed; no team-execution file is
spawned through the broker. Normal team-execution waves are file-disjoint and carry no renewal or
teardown lease lifecycle. The emergency kill switch retires with the hook: the doc review
of #677 measured exactly one reader, and the `INFIQUETRA_FLEET_LEASE_ENFORCEMENT` variable now
has none in this repository.

| Source | Function or seam | Spawn form | Governor entry point | Lease pool | Acquire or reserve seam | Bind seam | Renewal seam | Release seam |
|---|---|---|---|---|---|---|---|---|
| `plugins/saga/scripts/execution_spec.py` | `_emit_panel_reconciliation` | verify-panel verdict agents | `concurrency_governor.ordered_chunks` | `agent` | `retired:broker-free-(#677/U4)` | `retired:broker-free-(#677/U5)` | `retired:broker-free-(#677/U4)` | `retired:broker-free-(#677/U4)` |
| `plugins/saga/scripts/execution_spec.py` | `emit_workflow_script` | dependency-layer worker agents | `concurrency_chunks` | `agent` | `retired:broker-free-(#677/U4)` | `retired:broker-free-(#677/U5)` | `retired:broker-free-(#677/U4)` | `retired:broker-free-(#677/U4)` |
| `plugins/saga/hooks/hooks.json` | `Agent|Task` | normal Saga Agent and Task calls | `retired:broker-free-(#677/U5)` | `agent` | `retired:broker-free-(#677/U5)` | `retired:broker-free-(#677/U5)` | `retired:broker-free-(#677/U5)` | `retired:broker-free-(#677/U5)` |
| `plugins/saga/scripts/engine_dispatch.py` | `_dispatch_once` | registered external-engine runner | `retired:broker-free-(#677/U3)` | `agent` | `retired:broker-free-(#677/U3)` | `not-applicable:in-process-adapter` | `retired:broker-free-(#677/U3)` | `saga.close-receipt.v1:mint` |
| `plugins/saga/scripts/outcome.py` | `_reconcile_once` | outcome backend dispatch | `retired:broker-free-(#677/U3)` | `agent` | `retired:broker-free-(#677/U3)` | `not-applicable:in-process-adapter` | `retired:broker-free-(#677/U3)` | `retired:broker-free-(#677/U3)` |
| `plugins/saga/scripts/outcome_worktrees.py` | `ensure_worktree` | outcome-owned git worktree | `WORKTREE_CAP` | `worktree` | `registry.register` | `not-applicable:registry-entry` | `retired:broker-free-(#677/U3)` | `reap_worktree.deregister` |

[`sandbox-spawn-sites.md`](sandbox-spawn-sites.md) separately inventories containment requirements.
The inventories cross-link because verify-panel and external-engine rows are both concurrency-
governed and sandbox-sensitive, but the lease table must not absorb sandbox policy columns.

## Operator inspection and recovery

Retired with the saga broker wrapper (#677/U5): no saga seam binds fleet leases any more, so there
is no lease registry for saga to inspect or recover. The wrapper's read-only `inspect` view and its
`sweep` command are deleted with it, and no successor mechanism replaces them — lease admission,
claim, and recovery are gone, not rehomed. Outcome-worktree recovery remains the report-only
operator path in [`worktree-reclamation.md`](worktree-reclamation.md). The fleet-core broker and
its registry stay dead weight nothing reads until campaign #677 unit U7 deletes them.
