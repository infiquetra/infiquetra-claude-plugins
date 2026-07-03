# Work session — board↔saga reconciliation on resume (#295)

**Date:** 2026-07-03
**Branch:** `feat/295-board-saga-reconciliation`
**Plan:** `docs/plans/2026-07-03-board-saga-reconciliation-plan.md`
**Doc-review:** `docs/reviews/2026-07-03-board-saga-reconciliation-plan-readiness.md` (READY, no P0/P1)
**Destination:** merge · **Backend:** inline

## What was built (by U-ID)

- **U1 — `outcome_github.board_status(issue_ref, *, project)`**: live board Status via `gh issue view --json projectItems`, title↔slug matched case-insensitively, degrade-safe to `""`. No GraphQL, no mission-control surface (revised KTD7).
- **U2 — `outcome_github.issue_close_info(issue_ref)`**: `{state, state_reason, closed_by}`. State+reason from `gh issue view --json state,stateReason`; close author best-effort from the REST events endpoint (`--paginate`, last closed event). `issue_state` left untouched so the harvester barrier keeps its exact semantics.
- **U3 — `outcome_reconcile.detect()`**: pure classification over baseline (latest of {ledger write record, reconcile-override} per op family) + recomputed expected Status vs injected live reads. Emits `status-drift` / `external-close` / `external-reopen` drift records, `recovered` records (rewrites a landed-but-unrecorded key), and `unreadable` notes. Scope is ledger-bearing issues only (KTD6). Contract-aware + stateReason close semantics (KTD4).
- **U4 — `decide()` / `apply_resolution()`**: HITL behind a `policy` seam (R8); accept-board / re-assert / hold recorded as append-only `reconcile-override` records. re-assert `authorize_write`s first, then re-drives through the injected `board_writer` (never a direct gh call, R9).
- **U5 — wiring**: `advance --autonomous` runs `detect` BEFORE `reconcile_board`, threads drifted issues into `hold_issues` (drift-hold, KTD3), and carries records on `AdvanceResult.drift`. New `outcome reconcile <id> [--resolve <drift-id> --action …]` CLI verb (read-only, no lease). `reconcile_board` gained the `hold_issues` param.
- **U6 — docs + release**: `/outcome` SKILL.md (verb row + Reconcile-on-wake subsection), `outcome-spec.md` reconcile contract, saga `0.50.0 → 0.51.0` (plugin.json, marketplace.json, CHANGELOG, version guard), DECISIONS entry flipped to Shipped.

## Key decisions carried from the plan

KTD1 reconstruct-intent-not-persist (recompute expected values, no intent ledger); KTD2 `/outcome`-boundary trigger (not `/resume`/hooks); KTD3 drift-hold not gate-all; KTD4 contract-aware + stateReason closes; KTD5 append-only override baseline; KTD6 ledger-bearing scope; KTD7 (revised) board Status via `gh projectItems`, no mission-control verb.

## Files modified

`plugins/saga/scripts/outcome_reconcile.py` (new), `outcome_github.py`, `outcome.py`, `outcome_board_sync.py`; `plugins/saga/skills/outcome/SKILL.md`; `plugins/saga/references/outcome-spec.md`; `plugins/saga/CHANGELOG.md`; `plugins/saga/.claude-plugin/plugin.json`; `.claude-plugin/marketplace.json`; `docs/engineering-journal/DECISIONS.md`; tests: `test_outcome_reconcile.py` (new), `test_outcome_completion.py`, `test_outcome_command.py`, `test_outcome_board_sync.py`, `test_saga_plugin.py`.

## Checks run

- Full suite: **1871 passed** (`uv run pytest`).
- `ruff check .` clean; `ruff format --check .` clean; `mypy plugins/ scripts/ tests/` clean (0 errors, CI scope); bandit clean (only expected `nosec` acknowledgements).
- New tests: 20 reconcile (U3/U4), 10 completion (U1/U2), 6 command+board_sync (U5); release-surface drift guards green.

## Next step

Code-review gate (adversarial read-only verifier in flight), then offer PR-open under confirmation.
