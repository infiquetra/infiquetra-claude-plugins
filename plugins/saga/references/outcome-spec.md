# Outcome spec — the canonical outcome document (OutcomeOrchestrator U1)

`plugins/saga/scripts/outcome_spec.py` defines the spec at the root of the `OutcomeOrchestrator`
layer: a canonical JSON document describing a whole **outcome** as a DAG of subplots (leaf sagas).
It is a superset-in-pattern of `execution_spec.py` — the same pure-function,
`from_dict`/`to_dict`/`validate` house pattern — but models a *concurrent DAG of subplots* with an
operational state machine, not one linear unit list.

This is the structural source of truth (R26). GitHub sub-issues are **generated from** the spec, so
there is no node/edge drift. The committed spec is canonical for **structure + decision-trail +
cost**; GitHub is canonical for **completion**; the git-common-dir cache (U2) is performance-only.

## Placement (KTD1 / R26)

```
docs/outcomes/<outcome-id>/outcome-spec.json   # on branch outcome/<slug>
```

JSON (not Markdown front-matter, not SQLite) is canonical so the round-trip is deterministic and the
repo's JSON-parser tests apply. `OutcomeSpec.to_json()` is stable (fixed key order, trailing newline)
so a committed spec diffs cleanly.

## Top-level shape (`OutcomeSpec`)

| field | meaning |
|---|---|
| `schema_version` | on-disk schema version (`SCHEMA_VERSION`, currently `1`); bumped only on a breaking shape change |
| `outcome_id` | stable id; the child of a `child_spec_ref` is a *distinct* `outcome_id` |
| `spec_revision` | bumped on every **structural** change (edge redirect, add/prune, promote) so a stale reader/cache detects drift |
| `objective` | the human statement of the whole outcome |
| `nodes[]` | the subplot DAG (see below) |
| `decision_trail[]` | append-only "why" records (R26) — kept canonical so cold re-entry is non-lossy (KTD5/F5) |
| `cost_rollup` | the economics rollup (R24); empty renders as "no data yet" (U8), never a fabricated zero |
| `created_at` / `updated_at` | ISO timestamps (stamped by the writer, U3) |

## Node shape (`Node`, KTD2 — the operational state machine in data)

Each node carries the state machine **as data** so the reconcile loop (U3) is level-triggered and
holds no authoritative in-memory DAG (R29):

| field | meaning |
|---|---|
| `subplot_id` | unique within the spec |
| `title` | human label |
| `kind` | `code` (contract = merged PR, R11) or `non-code` (contract = durable tick + GitHub/spec marker, KTD4) |
| `state` | one of `NODE_STATES` (below) |
| `backend` | one of `NODE_BACKENDS` — the full executor menu (R6) |
| `gated` / `risky` / `destructive` | risk flags that gate the degrade decision (U9) |
| `guarantee_tags[]` / `degrade_policy` | the degrade contract (KTD9), enforced in the degrade path, **not** in `recompile_for_tier` |
| `timeout_seconds` / `heartbeat_seconds` | liveness budgets (R31); `null` = untimed (attended leaves) |
| `depends_on[]` | dependency barriers — the DAG edges |
| `leaf_saga_id` | the leaf saga this subplot dispatches to (set at dispatch) |
| `child_spec_ref` | typed parent→child link (KTD10): when set, the node **is** an outcome and reconcile recurses. Never overload saga's `orchestration_ref`. |
| `github` / `worktree` / `evidence` / `cost` | open pass-through maps; detailed schemas land in the consuming units (U5/U6/U7/U10) |

### Node state machine (`NODE_STATES`)

```
pending → ready → dispatched → running → done            (success, R11)
                                       ↘ failed           (terminal-retryable → leaf `work`, R12)
                                       ↘ rejected         (NEGATIVE terminal — PR closed, branch gone, R32)
                                       ↘ stalled          (NEGATIVE terminal — liveness timeout, R31)
   blocked  (upstream paused/failed — cascade, R22)
   merging  (code leaf in the auto-merge queue, U6)
   paused   (operator- or cascade-paused; not yet terminal)
```

`TERMINAL_STATES = {done, failed, rejected, stalled}`; `SUCCESS_STATES = {done}`. A code leaf unlocks
its dependents only from `done`; the negative terminals cascade.

## Type coercion at `from_dict` (fail-loud, before `validate`)

The constructors reject mistyped fields rather than silently coercing them — a typo must fail, not
flow corrupted data into the reconcile loop:

- `depends_on` / `guarantee_tags` must be **lists**. A bare string (`"depends_on": "a"`) is rejected,
  not silently character-iterated into single-character edges (`"ab"` → `["a", "b"]`).
- `timeout_seconds` / `heartbeat_seconds` must be an **int or null**. A JSON `true` (would coerce to a
  silent 1-second budget) and a float (`1.9` would truncate to `1`) are both rejected.
- `spec_revision` / `schema_version` must be **integers ≥ 1** — they are monotonic drift-detectors
  (R26), so a negative or zero seed fails here.

## Validation invariants (`validate`, fail BEFORE any dispatch — R20 / R31)

`validate` enforces only the **hard, dispatch-blocking** invariants, in order:

1. non-empty `outcome_id` and `objective`; at least one node;
2. unique `subplot_id` (**duplicate id** fails);
3. per-node: closed vocabularies (`kind` / `state` / `backend` / `degrade_policy`), positive-or-null
   liveness budgets, **self-dependency** fails, local `child_spec_ref` constraints (a child may not be
   the parent `outcome_id` — **self-recursion** — nor the node's own `subplot_id`);
4. no `child_spec_ref` **collides with a declared sibling `subplot_id`** (a child outcome must be a
   distinct outcome, a purely local fact);
5. every `depends_on` resolves to a declared node (**missing dep** fails);
6. the graph is acyclic — Kahn `dependency_layers` (**cycle** fails).

### Disconnection is advisory, not a hard failure

An earlier design hard-failed a degree-0 "orphan" node. That was both **too strict** (it rejected a
legitimate pipeline + one independent `update-the-changelog` subplot) and **too loose** (it silently
passed a disconnected *multi-node* island — the exact "forgot to wire it in" error it claimed to
catch). Independent workstreams under one objective are first-class in this model, so disconnection is
**not** dispatch-blocking.

Instead, `structural_warnings(spec)` returns a **non-fatal advisory** when the graph splits into more
than one weakly-connected component — consistently for a lone isolate *and* a multi-node island. The
CLI `validate` surfaces it under a `"warnings"` key; `/outcome` shows it without blocking. The
state-aware half of R33 — *which edits are legal once a leaf is dispatched*, and dynamic orphan
**reconciliation** (close the sub-issue, reap the worktree, reconcile cost when an edit strands a
node) — needs node-state + ancestor context and lands with the decompose/promote flow (U7).

`validate` is intentionally **dispatch-state-blind** in U1: it never reads `Node.state`. Mutations are
checked only for structural validity (acyclic, connected-enough, vocab) here; legality-after-dispatch
is U7.

## Frontier helpers

- `dependency_layers(spec)` — Kahn topological layers of `subplot_id`s, keyed on `Node`. This is a
  **parallel reimplementation** of the same Kahn algorithm as `execution_spec.dependency_layers`, not
  a reuse of it: `execution_spec` adds an implicit `pilot` barrier edge (an execution-session concept
  the outcome layer has no notion of), so the two **deliberately diverge** and must not be assumed to
  agree. Raises on a cycle or an unresolved dep.
- `ready_frontier(spec, completed)` — the live frontier: not-yet-completed subplots whose deps are all
  in `completed`. This is the level-triggered read the reconcile loop performs each tick (R29).
- `structural_warnings(spec)` — advisory (non-fatal) structural smells; today, disconnected components.

## Structural mutation bumps the revision (atomically)

- `bump_revision(reason=, at=)` — increments `spec_revision` and appends a `decision_trail` entry.
- `redirect_dependency(subplot_id, old_dep, new_dep)` — redirects one edge. **Atomic**: the redirect
  is applied to a snapshot and `validate`d *before* the revision is bumped, so a rejected redirect
  (cycle/self-dep/undeclared target) leaves `depends_on`, `spec_revision`, and the append-only
  `decision_trail` completely untouched — the canonical artifact never carries a bumped revision with
  a trail entry that lies about a change that was rejected (R26 fidelity). In U1 this is the only
  structural mutation; add/prune/promote land in U7 and bump through `bump_revision` too.

## CLI

```bash
python3 plugins/saga/scripts/outcome_spec.py validate docs/outcomes/<id>/outcome-spec.json
python3 plugins/saga/scripts/outcome_spec.py layers   docs/outcomes/<id>/outcome-spec.json
```

`validate` exits non-zero with a JSON `{"valid": false, "error": ...}` on a malformed spec; `layers`
prints the topological layers. No I/O happens at import (pure functions), so the module is unit-testable
offline — see `tests/test_outcome_spec.py`.
