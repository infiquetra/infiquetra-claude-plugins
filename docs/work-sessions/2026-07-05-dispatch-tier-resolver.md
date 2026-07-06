# Work session — Dispatch-time tier resolver (#362)

**Plan:** `docs/plans/2026-07-05-dispatch-tier-resolver-plan.md` · **Spec:** `…-spec.json` · **Branch:** `feat/362-dispatch-tier-resolver` · **PR:** #493 (draft) · **Backend:** cc-workflows-ultracode (6 units, serial)

## What was built (by U-ID)

- **U1** — `plugins/fleet-core/scripts/fleet_commons/tier_policy.json`: work-shape→tier registry (6 keys incl. the `mechanical`/`purely-mechanical` split).
- **U2** — `plugins/fleet-core/scripts/fleet_commons/tier_resolver.py`: `resolve(work_shape, role_kind, envelope_ceiling, operator_override) → {model, effort, because, cheaper_fallback, needs_confirm}`, importing `MODELS`/`EFFORTS`/`model_rank`/`effort_rank` from `tier_palette`. CLI verified: `judgment`→opus/high, `purely-mechanical`→haiku/low.
- **U3** — `/plan` Step-1 table renders from the registry (`render_tier_table.py` helper) + `skill_registry_sync` drift-guard.
- **U4** — all 25 `team-execution` agents migrated `model:`→`role-tier:`, **tier-preserving** (reviewers→adversarial-review→opus, testers→contract-test→sonnet, scanners/monitors→mechanical-scan→haiku); `model:` kept as fallback.
- **U5** — per-teammate effort **emitted** into the `/plan` unit table + A7 worker table (honoring deferred to #363); spawn-site routing drift-guard; `sandbox-spawn-sites.md` updated.
- **U6** — release surfaces: `saga` + `team-execution` `plugin.json` bumps, `marketplace.json`, both CHANGELOGs, `DECISIONS.md` (KTD1–KTD7), metadata drift-guard tests.

## Key decisions / events

- Scope stayed a parallel frontier root: effort-*honoring* → **#363**, vocab-source/ladder/repo-guard → **#370** (concerns filed on both).
- **Two saga-emitter defects found + fixed mid-build** (defect #494): the cc-workflows-ultracode return contract was haiku-only (`af74eb7`), and the gate demanded JSON-only so a sonnet prose preamble broke it (`f9573d5` — the gate now extracts embedded JSON). Both durable, benefit every future ultracode build.

## Checks run

- `uv run pytest` → **2113 passed** (baseline 2079). `ruff format --check` clean. `ruff check` clean. `mypy plugins/ scripts/ tests/` → **Success, 0 issues** (fixed one `no-any-return` in the test fixture).
- Resolver CLI smoke-tested against the plan's expected outputs.

## Next step

`/code-review` (pre-PR-ready gate), then flip PR #493 draft→ready. Merge stays operator-confirmed.
