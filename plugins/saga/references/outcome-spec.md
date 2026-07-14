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
| `intent` | the committed run-start intent envelope (#380): `run_mode` + `ceremony_gates`; absent key = never captured |
| `intent_revision` | the `spec_revision` at which posture was last (re)negotiated (#433 R4); absent key = the revision-1 run-start baseline is still in force |
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
| `tier` | optional declared execution tier (#373) — a model name validated against the fleet ladder; read by the spend gate's tier-ceiling check (an escalating leaf HALTs for step-up); absent emits no key |
| `timeout_seconds` / `heartbeat_seconds` | liveness budgets (R31); `null` = untimed (attended leaves) |
| `depends_on[]` | dependency barriers — the DAG edges |
| `leaf_saga_id` | the leaf saga this subplot dispatches to (set at dispatch) |
| `child_spec_ref` | typed parent→child link (KTD10): when set, the node **is** an outcome and reconcile recurses. Never overload saga's `orchestration_ref`. |
| `github` / `worktree` / `evidence` / `cost` | open pass-through maps; detailed schemas land in the consuming units (U5/U6/U7/U10) |

### `evidence` schema — the closure gate's declared contract (#397)

The closure gate (`plugins/saga/scripts/closure_gate.py`) is the first consumer to give `evidence`
a concrete shape:

| key | meaning |
|---|---|
| `required_checks` | `list[str]` of `check_id` values (e.g. `["qa", "code-review"]`) this node must have satisfying evidence for before it can be harvested `done`. Absent or empty -> the gate is trivially satisfied; every outcome spec that does not declare this key (every spec that exists today) is unaffected. |
| `reviewed_sha` | optional explicit close-SHA override. When absent, a `code` node derives its close SHA from `outcome_github.head_ref_oid(node.github["pr"])` — the PR's pre-merge head commit SHA, not the post-squash merge-commit SHA on `main` (which would never match any evidence entry). A `non-code` node has no PR to derive from, so it needs this override to use evidence gating at all. |

The gate reads the evidence ledger (`docs/evidence/<node.leaf_saga_id>/`, #398) for each declared
check at the resolved close SHA and derives one of these named HALT reasons (never a silent close):

| HALT reason | meaning |
|---|---|
| `missing-evidence:<check_id>` | the check has zero evidence entries anywhere in the ledger |
| `stale-sha:<check_id>` | the check has evidence, but none recorded at the resolved close SHA |
| `unresolved-fail:<check_id>` | the latest verdict at the close SHA is a failing verdict (`FAIL`, or a real producer's failing string — `no-ship`, `blocked`) |
| `unsuperseded-fail:<check_id>` | an earlier failing verdict at the close SHA was followed by a passing verdict with no `payload["supersession_reason"]` on that later entry — an unexplained PASS never silently clears a FAIL |
| `unrecognized-verdict:<check_id>` | the latest verdict at the close SHA is neither a known passing nor a known failing string — HALT rather than silently treat it as a pass |
| `unresolvable-close-sha` | `required_checks` is declared but no close SHA (or no `leaf_saga_id`) can be resolved |
| `chain-tamper:<subplot_id>` | `evidence_ledger.verify_chain()` detected a broken or tampered custody chain |
| `invalid-identity:<subplot_id>` | a malformed `leaf_saga_id` or `check_id` (e.g. traversal-shaped) was rejected by `evidence_ledger`'s `_safe_name` guard — a clean HALT instead of an uncaught exception crashing the reconcile loop |

`outcome_orchestrator.harvest()` runs this gate as a second, additive check after the GitHub-only
barrier above is satisfied — a node is never harvested `done` while the gate HALTs.
`barrier_report()` surfaces the same verdict under each node's `closure_gate` key so an operator
sees the named reason even when the GitHub barrier alone already reads satisfied.

**Verdict vocabulary (KTD7).** The gate classifies each check's latest verdict against its own
closed vocabulary, independent of `evidence_ledger.latest()`'s own `superseded_fail` flag (which
hardcodes a literal `"FAIL"` sentinel). Known-failing: `FAIL`, `no-ship` (`/qa`), `blocked`
(`/code-review`). Known-passing: `PASS`, `ship`, `ship-with-deferred` (`/qa`), `clean`
(`/code-review`). Anything else HALTs `unrecognized-verdict:<check_id>` rather than being
silently treated as a pass.

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

## Mid-run posture renegotiation — `repost`/`set_intent` (#433)

`outcome.py repost` (`plugins/saga/scripts/outcome_intent.py`) is the ONE verb that changes a
live campaign's posture mid-run — the renegotiation form of `set-intent`, which itself only
*attaches* a first envelope and refuses overwrite. It reuses the existing vocabularies, never a
parallel one: campaign posture is the #380 intent envelope (`run_mode`, `ceremony_gates.
reviews_required/merge/deploy_nonprod`); node posture is the existing `degrade_policy`/`sandbox`
fields. It never touches DAG structure (node/edge edits stay `redirect_dependency`/decompose).

```bash
# campaign scope (envelope fields)
python3 plugins/saga/scripts/outcome.py repost <id> --set run_mode=unattended --reason "..."
# node scope (one leaf's degrade policy / sandbox) — the R8 scoped-repose form
python3 plugins/saga/scripts/outcome.py repost <id> --scope <subplot> \
  --set degrade_policy=operator_away_one_rung --reason "..."
```

**Atomic (R1/R2).** Same shape as every structural edit: the change set is applied to a deep-
copied snapshot and validated first; only then is the real spec mutated, `spec_revision` bumped
(one counter), and ONE structured `decision_trail` entry appended (`kind: "repost"`, the
classified deltas, the new `intent_revision`). A rejected repost — unknown field, off-vocabulary
value, wrong value type, a no-op value, a monotonic violation, a strand — leaves
`spec_revision`, `decision_trail`, and every posture field byte-identical.

**Overlap contract (R4/R5) — dispatch-time posture.** Each accepted repost tags the spec with
`intent_revision` (= the revision it introduced). Every leaf dispatch record captures the
`intent_revision` + posture snapshot active at its dispatch (`outcome._reconcile_once` writes
`intent_revision` and `posture` — including the campaign envelope as `posture.intent`, where
`null` explicitly means "dispatched with no committed envelope" — on the `commit` record;
`DispatchRequest.intent_revision` carries it to the backend). An in-flight leaf finishes under
its dispatch-time posture at BOTH ends of its flight: dispatch (backend/sandbox) and completion
— `outcome_orchestrator.harvest` and `barrier_report` evaluate an in-flight leaf's
intent-implied closure checks (e.g. `code-review` under `reviews_required: "gate"`) against its
dispatch-era envelope, so a loosening repost never retroactively releases an in-flight leaf's
completion gate and a tightening one never retroactively imposes new checks. A pending leaf
picks the new posture up at its next dispatch. A running `advance` detects a mid-run repost:
the on-disk `spec_revision` is re-checked at every tick boundary AND per leaf after the
dispatch lock (before the intent record) — a moved revision stops the pass, reloads, and
re-ticks (`AdvanceResult.spec_reloads` says it happened), so a tick never knowingly dispatches
under a revoked posture.

**Strand HALT (R6).** A repost scoped to a `destructive` leaf that is IN FLIGHT (a dispatch
record in EITHER phase — `commit`, or the fail-closed mid-dispatch `intent` window — with no
terminal completion) and that TIGHTENS that leaf's sandbox would revoke irreversible-op
authorization the leaf already carries and cannot be re-issued mid-op. The campaign HALTs
instead of resolving silently in either direction: the amendment is rejected (spec untouched),
ONE `coordinator` `andon_halt` lands in the #372 adjustment envelope append-once on
`(writer, scope)` (the next tick stops dispatching; in-flight leaves drain under dispatch-time
posture), and ONE durable `{"phase": "halt", "kind": "repost"}` ledger record — append-once on
`(phase, key)`, the same parity as the reconcile halt path — names the stranded leaf; a
repeated stranded repost re-raises every time but never duplicates either record.
Campaign-scoped fields and `degrade_policy` govern *future* dispatch and completion decisions
(through the dispatch-era capture above), not authorization already in the leaf's hands, so
they never strand — R5 covers them.

**Remaining overlap window (R6, documented precisely).** The staleness check and the strand
check close the two demonstrated races (a stale tick dispatching after a repost commits; a
repost applying against a leaf whose dispatch intent is already declared), but one sub-window
remains: a tick that has passed its per-leaf revision check but not yet written the dispatch
`intent` record, interleaved with a repost whose ledger read happened before that write and
whose spec save lands after the tick's check. Both then proceed — the leaf launches under the
old (wider) posture and the tightening applies. The window is the intersection of two
milliseconds-scale intervals inside single dispatch iterations, requires the repost to be
scoped to exactly that destructive leaf, and self-heals for every non-destructive axis (R5
dispatch-time semantics make "launched under the old posture" the *defined* behavior); for the
destructive/strand class it means a strand can, in that sub-window, resolve as
"dispatch-time posture finishes the flight" instead of a HALT. Closing it entirely would
require the repost to take the per-subplot dispatch lease; deliberately not done in this
change (blast radius), recorded here instead of claimed away.

**Persistence guard — a committed repost survives a concurrent tick.** `save_spec` is
compare-and-swap on the revision the spec was loaded at (`OutcomeSpec.loaded_revision`,
runtime-only, never serialized): a save built on a spec another writer has since superseded
raises `StaleSpecError` instead of silently reverting the newer revision's posture, bump, and
trail entry. The one spec-persisting seam inside the advance path — the production cost
processor's rollup save — catches it, reloads the newer spec, re-derives the rollup from the
same ledger, and re-applies on top, reporting `reapplied_over_stale_revision` in the tick's
cost record. A mid-tick repost therefore cannot be destroyed by a production advance tick.

**Monotonic merge/deploy gating (R7).** `ceremony_gates.merge` / `deploy_nonprod` (the issue's
`merge_gate`/`deploy_gate`) move only toward MORE gating: `auto -> gate` is accepted; `gate ->
auto` is rejected outright — including against a campaign with NO committed envelope, whose
effective gates default to `gate`, and equally through the sibling `set-intent` verb: once a
campaign is LIVE (any dispatch record, either phase), a first envelope attach carrying
`merge`/`deploy_nonprod: "auto"` is rejected by the same validation
(`outcome_intent.validate_live_attach`), and every accepted attach writes a `set-intent`
decision-trail entry with its classified deltas — one rule, one trail, no second-verb side
door (AC5). A PRE-dispatch attach may carry any posture (the #380 interview-fallback
contract). One-directional by design: loosening merge/deploy posture back to autonomous takes
a new campaign, not a repost. **Consumer honesty:** today the engine consumes
`reviews_required` (implied closure checks) and the #373 dispatch-seam fields;
`ceremony_gates.merge` / `deploy_nonprod` are *recorded posture with no engine consumer yet* —
the auto-merge queue keys off node-level flags and nothing reads these two gates. R7 protects
the recorded value's integrity so the consumer that #449 lands (the token-checked
merge/deploy write class) inherits a trustworthy field, not so it changes behavior today.

**Approval interplay (R3).** Every repost bumps `spec_revision` and the R20 approval gate is
revision-keyed, so the frontier approval is consumed automatically. A repost whose deltas ONLY
tighten carries an existing approval forward (a new `r<rev>.json` approval record with
`answerer: "carried-forward:tightening-repost:r<old>"` provenance — self-attested, like all
approval provenance); any loosening delta leaves the new revision unapproved, and gated leaves
do not dispatch until the operator re-approves.

**Direction vocabulary** (closed; per axis, toward "more gated" = tighten): `run_mode`
`unattended < attended`; every ceremony gate `auto < gate`; `degrade_policy` `none <
operator_away_one_rung < halt`; `sandbox.mutation_policy` `read-write < read-only`;
`sandbox.workspace_isolation` `ambient` is strictly loosest, and the two isolated values
(`disposable-worktree`/`owned-worktree`) are mutually incomparable — a move between them
classifies **loosen** conservatively (costs at most one extra re-approval, never skips one).

**HALT as a renegotiation point (R8/R9).** A leaf HALT carries a `scoped_repose` option on its
`HaltReceipt` ONLY where the offered verb can actually resolve the halt: the guarantee class
when the guarantee is borne by the leaf's own `degrade_policy: "halt"` (no `guarantee_tags`) —
a scoped `repost --set degrade_policy=operator_away_one_rung` lifts exactly that guarantee and
the unchanged degrade machinery takes over. Every other halt class is honestly offer-less: an
ATTENDING halt fires before `degrade_policy` is consulted (the operator is present — R23 pages
them directly; no repost value changes `attending`); a `guarantee_tags`-borne guarantee is
spec-authored (repost's node axes are `degrade_policy`/`sandbox` only); a
side-effected/destructive halt is HALT-not-degrade by design; a captured #373 envelope
`degrade_policy` that forbids degrade is not a repost axis; an availability halt (no lower
rung) is not posture at all. The option is an offer, not a mechanism that acts: the leaf stays
halted — re-derived every tick — until the operator explicitly reposts (and re-approves, when
loosening) or leaves it halted. There is no default and no timeout; silence is never consent.
This composes with, never overrides, HALT-not-degrade: a scoped repose is a *path out of* an
existing HALT, not a new degrade mode.

## Board↔saga reconciliation (`outcome_reconcile`, #295)

Autonomous board-sync (`advance --autonomous`, #279) *writes* the board but never re-reads it. An outside
writer who changes a saga-owned field while saga is at rest is therefore invisible — and because a recorded
idempotency key makes the next tick **skip** the op, the drift would persist silently. `outcome_reconcile`
is the resume-time detector that closes that loop. It adds **no writer and no new persistence**: it reads
#279's board-sync ledger and re-drives any resolution through #279's existing writer.

**Trigger.** `detect` runs at the top of every `advance --autonomous` tick *before* any board write, and on
demand via `outcome reconcile <id>` (read-only; no coordinator lease). Silent unless something diverged.

**Three per-issue views** (`detect`):

- **asserted** — the latest of {ledger write record, `reconcile-override` record} per op family, by `ts`.
  What saga last drove or the operator last accepted.
- **expected** — recomputed from `derive_states` → `outcome_board_sync._candidate_ops` → the schema status
  map. Because idempotency keys and target values are pure functions of observable state, a
  landed-but-unrecorded write (a ledger key lost to a crash) is reconciled by *recomputation* — no intent
  ledger, zero change to #279's scope-locked writer.
- **live** — `outcome_github.board_status` (board Status) + `outcome_github.issue_close_info` (open/closed +
  stateReason + best-effort close author).

**Saga-owned field class.** Exactly what the writer writes: board **Status** and issue **open/closed**.
**Scope** is ledger-bearing issues only — an issue with no recorded write is never read, so a field saga
never owned (a hand-added label) can never be a false positive.

**Close semantics (contract-aware + stateReason).** A `completed` close that satisfies a leaf's completion
contract (a non-code leaf's contract *is* the closed issue) is the harvester's sanctioned silent path; a
`not_planned` close, or a close on a code leaf (contract = merged PR), is drift. An unreadable stateReason
degrades to contract-only — today's behavior.

**Records.** `detect` returns a list of dicts: `status-drift` / `external-close` / `external-reopen` drift
records (each with `{kind, repo, number, subplot_id, op_kind, saga_value, board_value, author, drift_id}`),
`recovered` records (a rewritten missing ledger key — informational, never a drift), and `unreadable` notes
(a field that could not be read this tick — never fatal). A drift drift-holds only its own issue's board ops
(`reconcile_board(hold_issues=…)` → `{status: drift-hold}`); other leaves proceed.

**Resolution** (`decide` / `apply_resolution`). HITL behind a single replaceable policy seam
(`decide(drift, policy=None)` → `None` = ask). `accept-board` / `re-assert` / `hold` are recorded as
append-only `reconcile-override` records in the board-sync ledger namespace; `re-assert` calls
`reversibility_certificate.authorize_write` first, then re-drives through the injected `board_writer` — never
a direct gh call. PR-merge and deploy autonomy stay permanently HITL (#279 R20).

```bash
python3 plugins/saga/scripts/outcome.py reconcile <id>                 # detect (silent unless drift)
python3 plugins/saga/scripts/outcome.py reconcile <id> \
  --resolve <drift-id> --action accept-board|re-assert|hold            # apply an operator decision
```
