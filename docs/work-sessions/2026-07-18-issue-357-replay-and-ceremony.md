# Work session — issue #357 replay and cc-workflow ceremony (2026-07-18)

## What was built

- **Replay (U1–U6 as preserved bytes).** The preserved r2 implementation (31 paths, base
  `c9cdc992`, preservation manifest digest `e15b1b57…`) was replayed onto current main
  `a1dc0c2a` on branch `work/357-shared-liveness-engine`. Every replayed file landed
  byte-identical to the preserved tree; commit `0bc594b2`.
- **Baseline truth.** Live git contradicted the coordination-side assumption: `c9cdc992` is a
  *descendant* of current main (main + two docs-only plan-refresh commits), not a divergent
  base. The version bumps carried by the preserved bytes (fleet-core 0.14.0, saga 0.101.0,
  team-execution 2.20.0) are exactly one rung above live main — no R13 correction was needed.
  Release-triad parity (plugin.json / marketplace.json / CHANGELOG) verified for all three.
- **Plan custody merge.** The plan on the outcome branch was the 2026-07-15 deepening; the
  implementation was built against the 2026-07-17 Codex baseline refresh. Merged: refreshed
  body + operator-approved cc-workflow ceremony sections, with the anchored bytes verified
  unchanged (`453fa2d1…`). Committed to both the work branch (`c45ee832`) and the outcome
  branch (`d04f8e9e`). The KTD2/KTD3 attribution refresh in DECISIONS.md and both review
  artifacts ship with the work branch.

## Key decisions

- Kept the replayed one-rung version bumps instead of the stale plan-recorded targets; live
  git is authoritative over coordination-side notes.
- Full repository gate run *before* lens dispatch (beyond the contract's focused-suites
  minimum) — it caught two gaps the preserved r2 focused validation never exercised.

## Checks run

- Focused suites: 213 passed (`test_liveness_engine`, `test_liveness_events`,
  `test_liveness_consumer_conformance`, `test_liveness_reping_hook`, `test_outcome_liveness`,
  `test_outcome_integration`, `test_run_ledger`, `test_team_execution_pointers`,
  `test_team_execution_liveness`, `test_saga_plugin`, `test_team_execution_plugin`).
- Full gate at `8d3dbbe8`: pytest 4857 passed / 1 skipped, ruff check clean, ruff format
  clean, mypy clean, bandit clean on all changed plugin files.
- Two gate fixes (commit `8d3dbbe8`): pulse-telemetry `FACT_KINDS` pin extended with the new
  `liveness` kind; typed `cast` on the dynamically-loaded liveness_events test helper.

## Ceremony

Six-lens Workflow run `wf_152ed78e-331` dispatched at HEAD `8d3dbbe8` under the
operator-approved ceremony (anchor `453fa2d1…`): devils-advocate / security / architecture /
testing as opus-high `saga:readonly-verifier` agents, event-flow / scenario as sonnet-medium,
each in a disposable worktree, bounded pool of 3. Session lease admission pinned
(session 3 / aggregate 7, policy `b985631b…`).

## Ceremony harvest (round 1)

All six lenses returned (0 errors): devils-advocate 8, security 8.5, architecture 9,
testing 8.5, event-flow 9, scenario 9. Seven findings — one P2, six P3, no P0/P1.

- **P2 devils-advocate** (fixed): the engine never compared `now` to `dispatched_at`; a
  far-future dispatch with no post-now beats read `healthy`, violating R4/R12. The guarding
  clock-rollback test passed only incidentally through the heartbeat future-skew raise. Fix:
  dispatch-side future-skew guard in `phi_score` + sparse-history regression asserting the
  `invalid-observation` reason code; LEARNINGS entry `{#wrong-guard-fail-closed-357}`.
- **P3 security** (fixed): one corrupt/foreign file in the shared pending directory made the
  re-ping hook halt every SendMessage repo-wide. Fix: per-file read failures are skipped with
  a stderr warning; the poisoned claim alone degrades to `reping-send-unresolved`. New hook
  test proves unrelated traffic passes and a staged claim still binds beside the poison.
- **P3 architecture** (no change needed): claimed the plan still says team-execution
  2.18.0→2.19.0 at line 181 — that is **main's** copy; the branch plan at review HEAD reads
  2.19.0→2.20.0 at every site (`git show 8d3dbbe8:docs/plans/...` lines 32/83–84/226/596–597).
  Stale-read artifact of the lens worktree, disposed with git evidence.
- **P3 testing ×4** (fixed): phi-threshold boundary now pinned as inclusive at 8.0
  (75.6→healthy, 75.7→suspect, and phi==threshold→suspect via a pinned policy); golden phi
  value 4.499334907556478 pins the normal-tail formula; lease-TTL cold-start boundary pinned
  strict (elapsed==ttl healthy, +0.5s suspect); new integration test drives the real
  `production_liveness_processor` through `advance()` with the harvester withheld and asserts
  the adaptive projection survives into the tick's `liveness` record.

Post-fix gates: focused liveness suites 82 passed; full pytest 4862 passed / 1 skipped; ruff
check + format clean; mypy clean; bandit clean on both changed plugin files.

## Next step

Fresh re-runs of the three affected lenses (devils-advocate, security, testing) at the fix
HEAD, then `/code-review` and `/qa` at the close SHA.
