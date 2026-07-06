# Work session — Effort becomes a first-class field (#363)

**Date:** 2026-07-05 · **Branch:** `feat/363-effort-first-class` · **Saga:** `issue-363` ·
**Destination:** merge · **Backend:** cc-workflows-ultracode (serialized, max concurrency 1)
**Status:** PR-ready — gate clean, awaiting PR-open confirmation.

## What was built (by U-ID)

Serialized ultracode Workflow `wf_dfbc6fcb-657` (6 agents, 0 errors, ~491K subagent tokens):

- **U1** `sonnet·medium` — `effort:` recognized as a validated agent-frontmatter field sourced from
  `tier_palette.EFFORTS`; glob+membership CI lint as a pytest (`tests/test_agent_tier_lint.py`, 34 agent
  files) in the existing CI step + optional `scripts/lint_agent_tiers.py` wrapper; `tiering_exempt` escape.
- **U2** `opus·high` — `EFFORT_RIDER` dict + `inject_effort(prompt, effort, spawn_kind)` in
  `plugins/fleet-core/scripts/fleet_commons/effort_rider.py`: pass-through for workflow/external-engine
  (no double-inject), rider-prepend for agent, raise on unknown kind.
- **U3** `opus·high` — `team_emitter.py`: A7 Tier effort validated against `EFFORTS` (R4); three-layer
  cascade wrapping `tier_resolver.resolve()` (plan-unit > team-default > agent base, KTD4); per-teammate
  provenance line; chaperone (offload/second-opinion) exclusion preserving intent default (R6/KTD5).
- **U4** `sonnet·medium` — wired `inject_effort(...,'agent')` into team-execution dispatch (SKILL.md);
  single fleet `effort-convention.md` reference doc; validated `effort:` on `agy-coder` + `release-orchestrator`.
- **U5** `sonnet·medium` — `reconcile_effort()`: post-run resolved-vs-manifest tiering-drift, honest per
  path (KTD7). Co-located in `effort_rider.py` beside `inject_effort` (deviation from plan's `team_emitter.py`
  target — accepted in review as defensible symmetry).
- **U6** `sonnet·medium` — release surfaces: saga 0.63.0 / team-execution 2.11.0 / fleet-core 0.4.0;
  KTD1–KTD7 in DECISIONS; QUEUED entry resolved-via-seam.

## Key decisions

- **KTD1 (Option C):** honor the real knob where the path has one (Workflow/external-engine already pass
  `agent({effort})` / `effort=resolution.effort`); labeled `EFFORT_RIDER` proxy only on the native
  Agent-tool path; all behind one swappable `inject_effort()` seam. Effort is first-class as a **value**;
  "how it's honored" lives in exactly one function.
- Backend cc-workflows-ultracode, **serialized** (concurrency 1) — for API rate-limit safety and to avoid
  concurrent edits to the shared test files (`test_team_emitter.py`, `test_effort_rider.py`).

## Code-review gate (Phase 5)

3 lenses (correctness / testing / maintainability) as `saga:readonly-verifier` in worktree isolation.
Two P1 findings, both cross-cutting consequences no single build unit owned — both fixed:

1. `QUEUED.md` heading overclaimed "SHIPPED" vs its honest body → corrected to resolved-via-seam (`fc8eff2`).
2. agy/deploy got `effort:` frontmatter (U4) with no release-surface bump → bumped agy 0.1.1 / deploy 0.1.4
   + drift-guard pins (`c260d8c`, `706cd6a`). The staleness re-run caught the guard-pin regression the
   version bump introduced — fixed in the same loop.

Artifact: `docs/code-reviews/2026-07-05-feat-363-effort-first-class-code-review.md` (blocked=NO).

## Checks run (final HEAD `706cd6a`)

pytest **2185 passed, 1 skipped** · ruff check · ruff format · mypy (141 files) · marketplace validator
(0 errors) · `validate_plugins` · `release_surface_diff_guard` (all 5 changed plugins bumped).

## Files modified

`team_emitter.py`, `effort_rider.py` (new), `lint_agent_tiers.py` (new), `test_agent_tier_lint.py` (new),
`test_effort_rider.py` (new), `test_team_emitter.py`, `SKILL.md`, `effort-convention.md` (new),
`agy-coder.md`, `release-orchestrator.md`, 5× `plugin.json` + `marketplace.json`, 5× `CHANGELOG.md`,
`QUEUED.md`, `DECISIONS.md`, `test_saga_plugin.py`, `test_team_execution_plugin.py`, `test_agy_plugin.py`,
`test_deploy_plugin.py`.

## Next step

Await operator confirmation to open the PR (destination merge). On merge: route to `/qa` advisorily, and
**attach the merged-PR URL to outcome node `sub-363`** before `/outcome advance` can harvest it (defect
#495 recurs — code leaves need their merged-PR ref written to the node).
