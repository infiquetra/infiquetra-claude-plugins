# Work Session — Fleet-Commons Distribution Mechanism (#463)

- **Plan:** `docs/plans/2026-07-04-fleet-commons-mechanism-plan.md`
- **Doc review:** `docs/reviews/2026-07-04-fleet-commons-mechanism-plan-review.md` (not blocked,
  zero findings remaining after the operator-requested fix pass)
- **Saga:** `issue-463`
- **Branch:** `feat/pf-fleet-commons-463`
- **Destination:** merge
- **Backend:** inline (operator-confirmed at plan time; `recommend_execution_backend()` said
  team-execution on size thresholds — recommended-vs-chosen recorded on the saga tick)

## Units completed

- **U1** — New scripts-only `plugins/fleet-core/` (0.1.0): manifest, README (what belongs in
  commons and what does not), CHANGELOG, and `scripts/fleet_commons/tier_palette.py` — palette
  constants verbatim from `execution_spec.py`, `_CHEAP_MODELS` made public `CHEAP_MODELS`,
  `model_rank()`/`effort_rank()` helpers, ordering contract in the docstring.
  `claude plugin validate plugins/fleet-core` → "Validation passed". Commit `713a870`.
- **U2** — Canonical `scripts/fleet_commons_shim.py` (five-rung ladder with rung provenance,
  `FLEET_COMMONS_DEBUG=1` stderr line, fail-loud) + byte-identical vendored copies in saga and
  mission-control + `tests/test_fleet_commons_resolution.py` (17 tests: per-rung, fail-loud,
  malformed-registry fallthrough, highest-semver, drift guard, palette regression). Commit
  `713a870`. Live-verified detail baked in: `installed_plugins.json` values are *lists* of
  install records.
- **U3** — `execution_spec.py` re-exports the palette through the vendored shim; `PASS_RULES`
  stays saga-local. Identity test proves `execution_spec.MODELS is` the shim-loaded object.
  Existing saga suite passed unchanged (238 tests in the regression net). Commit `131ef49`.
- **U4** — `plugins/mission-control/scripts/executor_profile_lint.py` + 9 tests: profile-block
  parse, palette membership, above-sonnet-requires-justification via palette ordering, exit
  codes 0/1/2, shim provenance under `FLEET_COMMONS_ROOT`. Validated end to end against the
  real issue #463 body (exit 0). Commit `da8a07e`.
- **U5** — `tests/test_fleet_commons_install_time.py`: fake install root (bare cache copies +
  registry fixture), lint run in a subprocess with `HOME` redirected, cwd outside the repo,
  scrubbed `PYTHONPATH`; asserts rung-3 stderr provenance (not rung 2), fail-loud negative
  case, and registry-pin-beats-newer-cache-decoy skew case. Commit `803be61`.
- **U6** — DECISIONS `{#fleet-commons-mechanism-463}` + LEARNINGS
  `{#marketplace-install-layout-no-import-path}` + QUEUED `{#fleet-commons-dependents}` census
  table; marketplace gains fleet-core 0.1.0; saga 0.53.0 / mission-control 2.5.0 bumps +
  CHANGELOGs + drift-guard literals; execution-order Phase 0 row 3 ticked. Commit `7eadf3d`.

## Census (AC5, operator-acknowledged adaptation)

The recorded deterministic query (keyword regex over `survivors/*.json` `title`+`idea`,
`seeds.json` excluded → 22 ids; ∪ the 7 issue-named ids, 6 new) enumerates **28 survivor ids** —
the count coincides with the issue's original "at least 28" figure, which was itself not
reproducible from any artifact. The enumerated list in QUEUED is now the canonical census.

## Checks run

`uv run pytest` → **1924 passed** (includes 29 new tests). `uv run ruff format --check .` and
`uv run ruff check .` clean. `uv run mypy plugins/ scripts/ tests/ --ignore-missing-imports`
clean. `uv run bandit` quiet-clean on the new surfaces. One pre-existing drift guard tripped as
designed by the version bump (`test_prompt_alignment.py` pinned 2.4.0) and was updated.

## Notes

- The scaffold script (`tools/create-plugin.sh`) generates a legacy `src/main.py` layout with an
  `"id"`-keyed manifest that contradicts the repo CLAUDE.md and every shipped plugin; fleet-core
  was authored directly to the live convention instead (adaptation noted per U1).
- `.serena/project.yml` remains a pre-existing unrelated local modification, excluded throughout.

## Next step

PR-ready. Open PR from `feat/pf-fleet-commons-463` → `main`, destination merge under operator
confirmation. Follow-ups that now build against the settled mechanism: #348 (429 retry
primitive), #401 (run-fact ledger), #341 (single-source vocabulary).
