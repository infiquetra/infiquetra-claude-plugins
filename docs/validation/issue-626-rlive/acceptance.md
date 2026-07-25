# R-live acceptance — #626 settlement auto-settle for externally-executed leaves

**Date:** 2026-07-24 · **Verdict: PASS** · **Repo state:** `main` at `f26f4d1c`
(`test(saga): lock settlement auto-settle for externally-executed leaves (#626) (#653)`)

R-live is the operator-gated acceptance leg the #626 plan stakes the close on, following the
#615 R9 / #620 R10 pattern. The plan's wording:

> Prove the auto-settle chain end-to-end against a **real externally-executed leaf**: run the
> harvester over its ledger + store, observe the `DELIVERED` settle fact land, and confirm the
> frontier advances. Operator names the subject; no live campaign card is mutated to satisfy an
> acceptance criterion.

## Why a purpose-built subject

Three candidate subjects existed in `campps-context-library`, and none could serve:

| Outcome | Backends | Settlement cohorts | Why not |
|---|---|---|---|
| `l2-consent-registration` | 17 × `cc-workflows-ultracode` | 4 (one `halt_required=True`) | Correct shape, but all five dispatched leaves' GitHub issues are still OPEN — nothing harvestable — and it is live in another session, so advancing it risks the #628 cross-runtime double dispatch |
| `tenant-bts-metering` | 13 × `inline` | 0 | All-inline leaves self-settle in-process; cannot exercise the external path |
| `campps-e2e-outcome-close-registry` | 9 × `team-execution`, 1 × `manual` | 0 | No external leaf |

Both completed outcomes return **zero settlement cohorts** — they predate the ledger (its earliest
fact is `2026-07-17`; those specs were last committed `2026-07-10` and `2026-06-29`), so they never
held a dispatch position at all.

A purpose-built subject was therefore constructed. This is an honest limitation and is recorded as
such: the subject was **authored rather than found in the wild**. What it is *not* is a fixture or a
simulation — every component below the spec is production: the real `outcome.py advance` CLI, the
real `make_dispatcher` backend seam, the real `production_harvester`, the real `gh` issue read, and
the real settlement ledger at `.git/saga-run-facts/run-facts.jsonl`. Per the plan's constraint, **no
live campaign card was mutated**.

## Subject

Outcome `rlive-626-external-settlement`, three nodes:

| Node | Kind | Backend | Depends on | Role |
|---|---|---|---|---|
| `external-leaf` | non-code | `cc-workflows-ultracode` | — | The externally-executed leaf under test; bound to issue #655 |
| `dependent-frontier` | non-code | `manual` | `external-leaf` | Proves completion propagates along a dependency edge |
| `independent-control` | non-code | `manual` | — | **Negative control** — ready from tick 1, so it can only be blocked by the settlement halt |

Every node carries `degrade_policy: "halt"`. This is load-bearing for integrity: had the Workflow
backend been unavailable, the leaf would HALT loudly rather than silently degrade to
`team-execution`/`inline` — and a degraded leaf is an *inline* leaf, which would have faked a pass
for the exact path under test. The guard fired on the first attempt (see Tick 0).

The `independent-control` node is what makes this more than a dependency-satisfaction test. With
only the dependent edge, its unblocking would be ambiguous — a skeptic could say the edge was met and
the settlement path was never load-bearing. An independent ready node has no such explanation
available: per `outcome.py:1198-1216`, any ready unit lacking a settlement binding is a `new_unit`,
and a single `halt_required` cohort blocks *all* of them.

Issue **#655** (`R-live probe fixture: external-leaf settlement auto-settle (#626)`) is the
GitHub-canonical completion marker. It is required because `outcome_orchestrator.barrier_satisfied`
(`outcome_orchestrator.py:157-166`) resolves a non-code leaf by reading `gh issue view --json state`
and is satisfied only on `closed` — GitHub is the engine's *only* channel for learning that an
out-of-process leaf finished, so closing a real issue is the faithful stand-in for the external
executor completing, not a shortcut around one.

## Timeline

Dispatch cohort digest `cb4b9e5376396022a6ad116cbe8685d6`.

### Tick 0 — the integrity guard fires

`advance --workflow-available` HALTED:

```
"reason": "cc-workflows-ultracode unavailable and the operator is attending -> HALT + page (R23)",
"available": ["inline", "team-execution", "manual"]
```

Cause: `outcome_dispatcher.py:451` reads `if host_capable and workflow_available:` — the Workflow
backend requires **both** flags. `--workflow-available` alone is a silent no-op, and the CLI help
text for it (`this host can run cc-workflows-ultracode (the Workflow tool is present)`) reads as
standalone and never mentions the coupling. Filed below as a follow-up observation.

This is the `degrade_policy: "halt"` guard working: the run stopped visibly instead of quietly
producing an inline leaf that would have passed the test for the wrong reason.

### Tick 1 — dispatch, position opens

`advance --host-capable --workflow-available` → `dispatched: ["external-leaf"]`, recorded
`backend='cc-workflows-ultracode'` (verified from the dispatch commit record — no degrade).

Ledger state — the #626 defect reproduced live:

```
outcome:cb4b9e53...:frontier:25a79a67...  site=outcome  halt_required=True
    external-leaf            open  attempt=1
```

Facts: `manifest`, `spawn`. **No settle fact.** Structurally identical to the campps
`…cb70ed4d7b02` cohort named in the issue.

### Tick 1a — negative control captured

A structural edit added `independent-control` (spec revision 1 → 2). `advance` returned:

```
"kind": "settlement-halt",
"subplot_id": "independent-control",
"reason": "prior dispatch cohort has missing evidence or exceeds its casualty threshold:
           outcome:cb4b9e53...:frontier:25a79a67..."
```

A unit with **zero dependency** on the external leaf, blocked purely because that leaf's dispatch
position is `open`. This is the campaign-killing symptom #626 describes, observed directly.

### Tick 1b — approval eliminated as a confound

`approve` (revision 2) then `advance`: **still settlement-halted**, identical receipt. So the R20
approval gate is not what later releases the frontier.

### Tick 2 — the decisive tick

Issue #655 closed (standing in for the external executor completing). Then `advance`:

```json
{"dispatched": ["dependent-frontier", "independent-control"],
 "harvested": ["external-leaf"], "halted": [], "gated": [], "degraded": []}
```

Ledger after:

```
outcome:cb4b9e53...:frontier:25a79a67...  site=outcome  halt_required=False
    external-leaf            delivered  attempt=1
```

The durable fact, with reason text from the reconcile loop:

```
settle  unit=external-leaf  cls=delivered  attempt=1
        "outcome parent harvested durable successful completion evidence"
```

All three facts share a timestamp — `settle`, `spawn dependent-frontier`, and
`spawn independent-control` all at `2026-07-24T20:18:59Z`. Same tick, as R2 requires.

### Tick 3-5 — write-once idempotency

Three further `advance` ticks: ledger line count **86 → 86, delta 0**; settle facts for
`external-leaf` = **1**. R3 satisfied.

## Neuter probe (KTD3)

The plan requires proving the characterization test can fail, since it passes against current code
by construction. A scratch edit inserted `continue` before the `settle_attempt` call in the
`production_harvester` reconcile loop (`outcome.py:2160-2206`):

```
tests/test_outcome_dispatcher.py:1059: assert tick2.dispatched == ["ship"]
E   AssertionError: assert [] == ['ship']
→ 0 passed, 1 failed
```

`git checkout -- plugins/saga/scripts/outcome.py` restored the file (`git status` clean,
`git diff HEAD` empty); the suite re-ran **69 passed**. The reconcile loop is confirmed load-bearing
— the frontier release is caused by that settle call and nothing else.

## Criteria

| Criterion | Verdict | Evidence |
|---|---|---|
| **R2** — external leaf's harvested completion auto-settles `DELIVERED`; frontier dispatches | **PASS** | Tick 2; cohort `halt_required` True→False; settle fact `delivered`; all three facts at `20:18:59` |
| **R3** — repeated ticks append nothing | **PASS** | Ticks 3-5, ledger delta 0, one settle fact |
| **R-live** — end-to-end against a real externally-executed leaf, no live campaign card mutated | **PASS** | Production CLI + dispatcher + harvester + `gh` + ledger; purpose-built subject, campps untouched |
| **KTD3** — the lock is able to fail | **PASS** | Neuter probe red, restore green (69 passed) |
| **No silent degrade** | **PASS** | Dispatch record `backend='cc-workflows-ultracode'`; Tick 0 halted rather than degrading |

R1 (Defect 1, board-sync) was discharged against #620's shipped coverage; R4/R5 are code-read and
decision criteria discharged in the plan and DECISIONS `{#outcome-settlement-halt-externally-executed-626}`.

## Follow-up observed during this run

`--workflow-available` is a silent no-op without `--host-capable` (`outcome_dispatcher.py:451`),
while its CLI help presents it as standalone. The coupling may be deliberate — the docstring says
`workflow_available` "**additionally** enables" the backend — but the help text does not say so, and
the failure mode is an operator passing the documented flag and getting an unexplained availability
HALT. Not fixed here; #626 ships no production code.

## Artifacts

- Issue **#655** — the probe fixture, closed as step 2 of the experiment. Not an SDLC card:
  no labels, no board (verified inert at creation).
- Settlement ledger: `.git/saga-run-facts/run-facts.jsonl`, dispatch digest
  `cb4b9e5376396022a6ad116cbe8685d6` (6 facts).
- Outcome store: `.git/saga-outcomes/rlive-626-external-settlement/`.

The probe's spec directory was **not** committed — `docs/outcomes/` holds real campaigns, and a
retired acceptance fixture does not belong beside them. It is reproduced in full below instead.

The two `manual` leaves (`dependent-frontier`, `independent-control`) remain `open` in cohort
`…7ebd0a07…` and that cohort still reads `halt_required=True`. This is deliberate and harmless:
nobody completed them, so an honest ledger says so. Settling them would mean manufacturing facts for
a retired probe. The halt cannot leak — `outcome.py:1201` scopes `outcome_reports` by `outcome_id`,
so it constrains only this retired outcome and never `governed-execution-integrity`.

### Appendix — the probe spec

```json
{
  "schema_version": 1,
  "outcome_id": "rlive-626-external-settlement",
  "spec_revision": 2,
  "objective": "R-live acceptance probe for #626: prove a cc-workflows-ultracode leaf's open dispatch position auto-settles delivered on harvest of its GitHub completion.",
  "nodes": [
    {
      "subplot_id": "external-leaf",
      "title": "Externally-executed leaf (cc-workflows-ultracode)",
      "kind": "non-code",
      "state": "pending",
      "backend": "cc-workflows-ultracode",
      "degrade_policy": "halt",
      "depends_on": [],
      "github": { "issue": "infiquetra/infiquetra-claude-plugins#655" }
    },
    {
      "subplot_id": "dependent-frontier",
      "title": "Dependent frontier unit (blocked until the external leaf settles)",
      "kind": "non-code",
      "state": "pending",
      "backend": "manual",
      "degrade_policy": "halt",
      "depends_on": ["external-leaf"],
      "github": {}
    },
    {
      "subplot_id": "independent-control",
      "title": "Independent control unit (no dependency; blocked only by the settlement halt)",
      "kind": "non-code",
      "state": "pending",
      "backend": "manual",
      "degrade_policy": "halt",
      "depends_on": [],
      "github": {}
    }
  ]
}
```

Empty structural fields (`worktree`, `evidence`, `cost`, `guarantee_tags`, `leaf_saga_id`,
`child_spec_ref`, `timeout_seconds`, `heartbeat_seconds`, `gated`, `risky`, `destructive`) are
elided; `outcome.start()` populates them at their documented defaults.

Reproduce with `outcome.start(repo_root, "<id>", "<objective>", nodes=[...])`, then
`approve` → `advance --host-capable --workflow-available`.
