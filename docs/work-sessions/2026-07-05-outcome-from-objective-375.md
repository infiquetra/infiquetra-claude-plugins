# Work session — /outcome start --from-objective (#375)

- **Date:** 2026-07-05
- **Issue:** #375 (Phase 0 item 7, execution-order row 7) — objective #332 (intent envelope)
- **Plan:** `docs/plans/2026-07-05-outcome-from-objective-375-plan.md`
- **Doc-review:** `docs/reviews/2026-07-05-outcome-from-objective-375-doc-review.md`
- **Code-review:** `docs/code-reviews/2026-07-05-outcome-from-objective-375-code-review.md`
- **Backend:** inline. **Driver:** autonomous Phase 0 (Opus/xhigh).

## What shipped

`/outcome start --from-objective <owner>/<repo>#<N>` seeds the DAG from a GitHub Objective's sub-issues.

- **U1** `discover_subissues.py` — query gains `stateReason` + `trackedIssues`; `normalize()` surfaces
  `state_reason` + `blocked_by`; new library `fetch_objective()`; `runner` seam for offline tests.
- **U2** `outcome_edges.py` (new) — pure cycle-safe `edges_from_relationships()` (drops+reports
  dangling/self/cyclic; always-acyclic output).
- **U3** `nodes_from_objective()` in `outcome.py` — kind-from-label, closed→terminal authored state,
  `github` provenance stamp, inferred `depends_on`.
- **U4** CLI `--from-objective` (+ optional `objective` defaulting to the parent title); reports dropped
  edges to stderr.
- **U5** release surfaces: saga 0.57.0 → **0.58.0**, marketplace regenerated, CHANGELOG, version literal.

## Scope decision (surfaced, not silent)

Narrowed U1's relationship source from the approved plan's `trackedIssues` + `timelineItems` to
**`trackedIssues` only**. The `timelineItems` cross-reference path needs inline-fragment GraphQL for
marginal edge yield, and KTD1 frames edge inference as best-effort/degrade-to-no-edges — so fewer
signals reduce auto-edge *yield*, never correctness. A clean follow-up if richer inference is wanted.

## Findings resolved mid-build (small, fixed inline — no filing)

1. **Doc-review P1 (GraphQL all-or-nothing):** a speculative `blockedBy` field would 400 the whole
   query; switched to stable `trackedIssues`/`stateReason` + isolated fetch → real degradation.
2. **Doc-review P2:** added the `runner` seam (conftest no-live-gh blocks, doesn't return fixtures);
   made `objective` optional, defaulting to the parent title.
3. **Impl (missing import):** `re` was not imported in `outcome.py` (my `_parse_objective_ref` was the
   first user) — added it.
4. **Impl (test input shape):** the edge-mapper unit tests initially passed raw GraphQL `trackedIssues`
   fixtures; the mapper consumes the *normalized* `blocked_by` shape — fixed the tests. Also moved the
   `start()` end-to-end assertions to `OutcomeSpec.from_dict` (offline) since `start()` needs a git repo.

## Gates

`pytest` 2020 passed (8 new); full-repo `ruff format --check .` + `ruff check .` clean; full-scope
`mypy` clean; release-surface parity + diff-guard green.
