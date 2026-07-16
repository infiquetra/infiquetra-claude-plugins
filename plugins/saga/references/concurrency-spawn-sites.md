# Concurrency fan-out inventory (#350)

This is the canonical inventory of executable Saga workflow fan-out emitters. A row means the
named Python function emits a JavaScript `parallel([...])` call and must first partition its cohort
through the named governor entry point. Panels use `concurrency_governor.ordered_chunks`; mixed
worker layers use `concurrency_chunks`, which delegates to
`concurrency_governor.ordered_policy_chunks`. Both public paths delegate to the single
`_bounded_ordered_chunks` ordering primitive. One private `_emit_parallel_wave` helper owns the
executable `parallel([` opener and `])` closer, snapshots the supplied bounded member sequence, and
then invokes the caller's member renderer once per snapshot entry. The conformance test keeps this
boundary structural: it requires exactly one helper definition, exactly the two inventoried call
sites below, no indirect references to the helper, a direct governor assignment in the call site's
statement block, direct iteration of that governed collection, each helper call as a direct expression
in the governed loop body, and the unchanged direct loop chunk target as `bounded_members`. Literal
opener or closer output-sink emissions outside the helper fail closed across direct list calls,
assignments, augmented assignments, and constant concatenation. The guard intentionally does not
interpret general Python aliases or JavaScript lexical grammar; centralizing the emission boundary
makes those mini-analyzers unnecessary.

| Source | Function | Fan-out form | Governor entry point |
|---|---|---|---|
| `plugins/saga/scripts/execution_spec.py` | `_emit_panel_reconciliation` | verify-panel verdict agents | `concurrency_governor.ordered_chunks` |
| `plugins/saga/scripts/execution_spec.py` | `emit_workflow_script` | dependency-layer worker agents | `concurrency_chunks` |

`plugins/saga/references/sandbox-spawn-sites.md` separately inventories containment requirements.
The two inventories cross-link because a verify-panel agent is both concurrency-governed and
sandbox-sensitive, but they answer different questions and must not share machine rows.

Out of scope: `team_emitter.py` emits a markdown coordination protocol, not executable
`parallel([...])` runtime calls; `/optimize`, team-execution scheduling, external-engine chaperones,
and the 429 retry helper keep their existing admission behavior.
