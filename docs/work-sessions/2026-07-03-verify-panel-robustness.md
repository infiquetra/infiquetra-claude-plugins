---
issue: infiquetra/infiquetra-claude-plugins#293
plan: docs/plans/2026-07-03-verify-panel-robustness-plan.md
branch: fix/293-verify-panel-robustness
status: PR-ready
---

# Verify-panel robustness — non-applicable vs. failed panel members

## What was built

- **U1** — Consolidated the three hand-maintained verify-panel reconciliation emissions
  (`_emit_thunk`, `_emit_verify_loop_singleton`, `_emit_verify_panel` in
  `plugins/saga/scripts/execution_spec.py`) into one shared `_emit_panel_reconciliation`
  helper, mirroring the `_verifier_agent_opts` single-source precedent. Behavior-preserving:
  all 57 `tests/test_workflow_emitter.py` assertions passed with zero edits. Commit `177ca21`.
- **U2 (Layer A, the core fix)** — The helper now records which verifiers reported vs. went
  runtime-missing (`null` verdict) and recomputes the pass-rule threshold over the reporters
  instead of the declared panel size — `max(1, ⌈k/2⌉)` majority / `max(1, k)` unanimous — with
  a baked `⌈n/2⌉` quorum floor that marks under-strength results without suppressing a
  refutation. Updated the three fixed-threshold assertions this necessarily broke
  (`tests/test_workflow_emitter.py:780,797,844`) to the recomputed expressions, and added 7 new
  tests covering missing-verifier logging, floor scaling (n=3/7/1), the n=1 all-missing edge
  case, unanimous recompute, and an integration test hitting all three reconciliation sites in
  one spec. Commit `195ce44`.
- **U3** — Extended `plugins/saga/references/execution-spec.md`'s `Unit.verify` section with
  the `iterate_to_consensus`/`max_iterations` fields, the throw consumer, and a new "Missing
  verdicts" subsection covering the recompute rule, the floor, the two-kinds boundary, and the
  KTD2 no-timeout residue. New KTD citations continue the doc's own pre-existing KTD1–KTD6
  sequence as KTD7–KTD10 (a numbering collision with the plan's own KTDs was caught and fixed
  during authoring — the doc has an independent KTD namespace from any one plan). Commit
  `fc55c2d`.
- **U4 (Layer B, independent of U1–U3)** — `plugins/team-execution/agents/architecture-reviewer.md`
  no longer scores a non-applicable dimension as a fabricated N/A→8.0 default; it excludes the
  dimension from the averaging denominator with a logged `static-non-applicable` cause.
  `consensus-protocol.md` defines the matching applicable-dimensions denominator for the gate
  and the re-review path. New `tests/test_team_execution_consensus.py` (4 drift-guard tests)
  pins the contract text. Commit `ec402a7`.
- **U5** — saga `0.49.2` → `0.50.0`, team-execution `2.8.0` → `2.9.0` (minor bumps, KTD8);
  `marketplace.json`, both `CHANGELOG.md`s, both version drift-guard test pins
  (`tests/test_saga_plugin.py:48`, `tests/test_team_execution_plugin.py:64`), and a
  `LEARNINGS.md` entry on the shared uphold-bias mechanism. Commit `3a6dd21`.
- Plan, readiness review, and the pre-existing `DECISIONS.md` KTD record from the planning pass
  shipped alongside (commit `03e56b0`).

## Key decisions

Full rationale is in `docs/plans/2026-07-03-verify-panel-robustness-plan.md` (KTD1–KTD8) and
`docs/engineering-journal/DECISIONS.md#verify-panel-missing-member-ktds-293`. The two load
bearing ones for review:

- **Skeptical asymmetry (KTD4)** — a refutation over reporters always acts (throws/retries),
  even under-strength; the quorum floor only annotates the accept path. Suppressing a small
  quorum's refutation would reintroduce the exact uphold bias this fix removes.
- **No behavior change in the all-report case (R10)** — the recomputed expressions are
  arithmetically identical to today's fixed threshold when every verifier reports
  (`max(1, ⌈n/2⌉) ≡ (n+1)//2`; `max(1, n) ≡ n`).

## Files modified

- `plugins/saga/scripts/execution_spec.py`
- `plugins/saga/references/execution-spec.md`
- `plugins/team-execution/agents/architecture-reviewer.md`
- `plugins/team-execution/skills/team-execution/references/consensus-protocol.md`
- `tests/test_workflow_emitter.py`
- `tests/test_team_execution_consensus.py` (new)
- `plugins/saga/.claude-plugin/plugin.json`, `plugins/team-execution/.claude-plugin/plugin.json`
- `.claude-plugin/marketplace.json`
- `plugins/saga/CHANGELOG.md`, `plugins/team-execution/CHANGELOG.md`
- `tests/test_saga_plugin.py`, `tests/test_team_execution_plugin.py`
- `docs/engineering-journal/LEARNINGS.md`, `docs/engineering-journal/DECISIONS.md`
- `docs/plans/2026-07-03-verify-panel-robustness-plan.md`,
  `docs/reviews/2026-07-03-verify-panel-robustness-plan-readiness.md` (new)

## Checks run

- `uv run pytest -q` — 1832 passed
- `uv run ruff check .` — all checks passed
- `uv run mypy plugins/ scripts/ tests/ --ignore-missing-imports` — no issues, 118 source files
- `uv run bandit -r plugins/saga plugins/team-execution` — 1 pre-existing High finding in
  `outcome_board_sync.py` (unrelated file, not touched by this change)
- JSON validity check on `marketplace.json` and both bumped `plugin.json`s
- `grep -r "0.49.2\|2.8.0"` — no stale pins outside changelogs/historical docs
- Manual emit-and-read of a 3-panel unit's generated reconciliation, confirmed byte-for-byte
  against the plan's High-Level Technical Design block

## Next step

Run the code-review gate, then offer PR-open against `main`.
