---
title: Work session — tier floors & backend enforceability (#369)
issue: infiquetra/infiquetra-claude-plugins#369
plan: docs/plans/2026-07-06-tier-floors-enforceability-plan.md
branch: feat/369-tier-floors-enforceability
date: 2026-07-06
---

# Work session — tier floors & backend enforceability (#369)

**Built the two live mechanisms of #369 (scope B); mechanism 3 deferred.** All four units landed,
full repo gate green, three clean commits on `feat/369-tier-floors-enforceability`.

## What was built (by U-ID)

- **U1** — `TIER_ENFORCEABLE_BY_BACKEND` matrix + `unenforceable_tier()` helper in
  `execution_spec.py`, beside `SANDBOX_ENFORCEABLE_BY_BACKEND`. Model-axis; `team-execution` =
  `{opus, sonnet, haiku}`; unknown backend enforces nothing.
- **U2** — optional `Unit.min_tier` floor (mirrors the `sandbox`/`verify` optional-field pattern);
  `segment_units()` clamps the merged segment tier up via `tier_palette.strongest()`; absent field
  round-trips byte-identical.
- **U3** — `team_emitter.emit_team_structure()` raises `SpecError` when a unit's model is unreachable
  by `team-execution` (e.g. `fable`), beside the existing unenforceable-sandbox halt.
- **U4** — release surface: saga `0.64.0 → 0.65.0` (plugin.json + marketplace.json), CHANGELOG,
  DECISIONS `{#tier-floors-enforceability-369}`, drift-guard version pin.

## Key decisions

- Scope **B** (operator-confirmed): ship mechanisms 1 & 2; defer mechanism 3 (agent `tier-floor:`
  frontmatter) to a follow-up carrying its per-teammate override producer — avoids a field consumed
  only by its test.
- Enforceability matrix lives in `execution_spec.py` (backend-keyed), not the vocab palette (KTD1).
- Floor reuses the #370 palette ladder ops, honoring `{#tier-vocab-ordering}` (KTD4).

## Files modified

`plugins/saga/scripts/execution_spec.py`, `plugins/saga/scripts/team_emitter.py`,
`tests/test_saga_execution_spec.py`, `tests/test_team_emitter.py`, `tests/test_saga_plugin.py`,
`plugins/saga/.claude-plugin/plugin.json`, `plugins/saga/CHANGELOG.md`,
`.claude-plugin/marketplace.json`, `docs/engineering-journal/DECISIONS.md`.

## Checks run

Full repo gate green: `pytest` (2221 passed, 1 skipped), `ruff format --check`, `ruff check`,
`mypy plugins/ scripts/ tests/`, `bandit -r plugins/` (no new findings). 7 new tests + no regression
to the `segment_units()` golden suite.

## Next step

Code-review gate → open PR → merge on green → `/outcome advance` to harvest sub-369.
