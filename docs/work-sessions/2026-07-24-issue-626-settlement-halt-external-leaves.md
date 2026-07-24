# Work session — #626 outcome settlement-halt for externally-executed leaves

- **Issue:** infiquetra/infiquetra-claude-plugins#626 (leaf `sub-626` of outcome
  `governed-execution-integrity`, Objective #639). Closing it unblocks `infiquetra-codex-plugins#45`
  (codex sub-45) — the campaign critical path.
- **Plan:** `docs/plans/2026-07-24-issue-626-outcome-settlement-halt-externally-executed-leaves-plan.md`
- **Doc-review:** `docs/reviews/doc-review-issue-626-2026-07-24.md` (verdict READY, no P0/P1; 1 P2 = D1, 1 P3)
- **Branch:** `work/626-settlement-halt-external-leaves` (base `main` `03c2640c`)
- **Saga:** `issue-626`, `lifecycle_phase=work`
- **Backend:** `inline` (recommended = chosen; ~1 test + docs, zero production code — no fan-out warranted)

## Shape: verify-and-close, zero production code

#626 named two defects; verified live at `03c2640c` that ~1.5 of 2 were already shipped and the residual
was already wired, so the deliverable is characterization tests + docs + an operator-gated live proof:

| #626 element | Status at `03c2640c` | #626 action |
|---|---|---|
| Defect 1 — board-sync `--autonomous` in consumer repos | Shipped by #620 (R10 PASS) | **Verify** (U2) |
| Defect 2b — operator settle/waive verb | Shipped by #618 (`dispatch-waiver`, R9) | Out of scope |
| Defect 2a — auto-settle a harvested Workflow completion | Already wired, backend-agnostic + idempotent | **Characterize + R-live** (U1) |
| Defect 2c — `casualty_threshold_percent=0` default | Decision: Option A, leave 0 (operator 2026-07-24) | **Document** (U3) |

The auto-settle chain (`outcome.py:2100-2209` `production_harvester` → `outcome.py:2148-2206` reconcile
loop over `outcome_dispatch_bindings`, **no `site`/`backend` filter**) closes an externally-executed
leaf's `open` position on the tick that materializes its GitHub-canonical completion. `settle_attempt`
(`dispatch_settlement.py:1545-1643`) is write-once per `(dispatch_id, unit_id, attempt)`, so the
every-tick harvester re-settle is a genuine no-op.

## What was built (by U-ID)

- **U1 — one net-new characterization test.**
  `tests/test_outcome_dispatcher.py::test_workflow_executed_leaf_auto_settles_on_harvest_and_unblocks_frontier`.
  Dispatches a `cc-workflows-ultracode` (out-of-process Workflow) leaf → open position (never
  self-settles) with a dependent blocked behind it; harvest materializes its completion → the
  site-agnostic reconcile loop auto-settles it `DELIVERED` → the dependent dispatches the same tick; a
  repeat tick appends no second settle fact (write-once). Passes green against current code (KTD3
  characterization, not red-first). **This is the only net-new test** — it pins the `cc-workflows-ultracode`
  site + dependent-unblock combination that no existing test covers; its value is prospective (fails the
  day a site filter re-strands Workflow leaves).
- **U2 — adjudicated to a reference, no net-new test.** R1 (Defect-1 board-sync from a non-monorepo cwd,
  resolved-root + rung on the record) is already covered at parity by #620's suite:
  `test_outcome_board_sync.py::test_production_path_resolves_once_and_threads_root_to_schema_and_writer`
  (production entry, simulated cache layout, R7 provenance on record **and** persisted ledger) and
  `::test_advance_autonomous_drives_board_sync`. Duplicating it is the churn the plan warns against.
- **U3 — docs.** DECISIONS `{#outcome-settlement-halt-externally-executed-626}` (KTD1 Option A, KTD2
  verify-and-close, KTD3 characterization, the test adjudication, and the D1 decision); this work-session.
- **U4 — no release surface (D1 = #605-style no-bump).** The diff is repo-root `tests/` + `docs/` only —
  nothing under `plugins/saga/`, no plugin behavior/schema/command/prompt/user-facing-guidance change,
  drift pins key on `plugin.json` (untouched). A needless bump re-invites the same-version sibling
  collision. Recorded in DECISIONS D1.

## Coverage already present (referenced, not re-asserted — R3/R4)

- R3 idempotency: `test_outcome_harvest_reconciles_prior_completion_when_nothing_is_new`,
  `test_late_delivery_requires_non_delivered_settle_and_is_write_once`.
- R4 coherence: `test_three_spawn_two_reap_one_open` (still-running stays open),
  `test_outcome_harvest_negative_terminal_settles_fail_closed_and_enters_dlq` (SILENT_NOOP fail-closed),
  `test_waived_halt_dispatches_new_cohort_with_receipt` (#618 waive advances a genuine casualty).

## Checks run

- `tests/test_outcome_dispatcher.py -k workflow_executed_leaf_auto_settles` → 1 passed.
- Relevant regression surface (dispatcher + dispatch_settlement + completion + board_sync + command) →
  269 passed. `ruff check` + `ruff format --check` on the edited test file → clean.
- Full suite + mypy + bandit + `check_release_surface_parity`: pending the Phase 3 / code-review gate.

## Next step

Run the full test gate, then the programmatic `/code-review` gate; on a clean gate, present the PR-open
offer (gated on Jeff's go). **R-live** is the post-merge, operator-gated leg (KTD4): it needs an
operator-named externally-executed subject (`sub-626` runs inline and cannot exercise the external-leaf
path), following the #615 R9 / #620 R10 pattern — Jeff names the subject before that run.
