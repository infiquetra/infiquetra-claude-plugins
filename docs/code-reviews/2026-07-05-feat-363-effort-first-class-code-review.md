# Code Review — Effort becomes a first-class validated field (#363)

**Target:** diff `feat/363-effort-first-class` vs `main` (merge-base `1c455f0`)
**Reviewed revision:** `706cd6a` (code logic lens-reviewed at `6957427` and byte-unchanged since; the
three commits after are the fixes for the two findings below, each re-verified by the full CI gate)
**Mode:** programmatic (in-loop `/work` gate)
**Blocked:** **NO** — both P1 findings fixed in place; no unresolved P0/P1.
**Linked:** plan `docs/plans/2026-07-05-effort-first-class-plan.md` · spec `…-spec.json` · saga `issue-363` ·
issue #363 · outcome leaf `sub-363` · work-session `docs/work-sessions/2026-07-05-effort-first-class.md`

## Verdict

Clean to merge. A serialized 6-unit ultracode build (U1–U6) landed the feature; three judgment-selected
lenses (correctness, testing, maintainability) ran as `saga:readonly-verifier` in worktree isolation.
Two P1 findings surfaced — both cross-cutting consequences no single unit owned — and both are fixed and
re-verified. The reviewed code logic (`team_emitter` cascade, `effort_rider` seam, reconcile, tests) is
unchanged since the lens pass.

## Scope check: CLEAN

- **Intent:** make `effort` a first-class validated value fleet-wide, honored by the real knob where the
  dispatch path has one (Workflow/external-engine) and a labeled `EFFORT_RIDER` proxy only on the native
  Agent-tool path, behind one `inject_effort()` seam (KTD1).
- **Delivered:** matches. One intended cross-plugin touch (validated `effort:` on one agy + one deploy
  agent) is required by R8 ("prove the convention fleet-wide"), not scope creep.

## Plan-completion audit

| Unit | Deliverable | Status | Evidence |
|------|-------------|--------|----------|
| U1 | `effort:` vocab + glob/membership CI lint | **DONE** | `tests/test_agent_tier_lint.py` (34 files parametrized), `scripts/lint_agent_tiers.py`; live-mutation confirmed a seeded `effort: extreme` fails |
| U2 | `EFFORT_RIDER` + `inject_effort()` in fleet_commons | **DONE** | `plugins/fleet-core/scripts/fleet_commons/effort_rider.py`; pass-through vs prepend vs raise all tested |
| U3 | A7 validation + 3-layer cascade + chaperone exclusion | **DONE** | `team_emitter.py` `resolve_teammate_effort`/`_is_chaperone`; `resolve()` contract (role_kind=None, override short-circuit) verified against `tier_resolver.py` |
| U4 | wire seam + convention doc + agy/deploy agents | **DONE** | `SKILL.md:336`, `references/effort-convention.md`, `agy-coder.md` (`effort: medium`), `release-orchestrator.md` (`effort: high`) |
| U5 | post-run tiering-drift reconciliation | **DONE** (placement deviation, accepted) | `reconcile_effort` co-located in `effort_rider.py` (plan named `team_emitter.py`); honest-per-path, tested match/mismatch on both paths |
| U6 | release surfaces | **DONE** (after fixes) | saga 0.63.0 / team-execution 2.11.0 / fleet-core 0.4.0 + KTD1–KTD7 in DECISIONS; QUEUED heading corrected; agy/deploy added to the release set |

## Findings (both fixed)

| # | Pri | Lens | Finding | Status |
|---|-----|------|---------|--------|
| 1 | P1 | maintainability | `QUEUED.md:457` heading read `— SHIPPED (#363)` while its body concedes only the `EFFORT_RIDER` proxy was built (native knob is tracked residual) — an honesty overclaim the plan's U6 explicitly forbade | **Fixed** `fc8eff2` — heading now `— RESOLVED via inject_effort() seam (#363)` |
| 2 | P1 | release-guard | U4 added `effort:` frontmatter to agy + deploy agents but U6 bumped only saga/team-execution/fleet-core → `release_surface_diff_guard` red (CI-blocking) | **Fixed** `c260d8c` + `706cd6a` — agy 0.1.1 / deploy 0.1.4 (plugin.json + marketplace + CHANGELOG + drift-guard pins) |

**Below-anchor (not surfaced as blocking), noted for the record:**
- U5 file-placement deviation (reconcile in `effort_rider.py` vs planned `team_emitter.py`) — the
  maintainability lens judged it a defensible co-location beside the sibling `inject_effort()`, wired via
  SKILL prose and covered by real tests; below anchor-75.
- `_MODEL_TO_WORK_SHAPE` base layer is "never the cascade winner in practice" (plan-unit tier always
  present) — the correctness lens confirmed this is the documented KTD4 behavior, not dead code; the
  agent-frontmatter branch is still exercised by a dedicated test.

## Lens coverage & verification

- **Correctness** — clean. Traced `resolve()`: `role_kind=None` accepted, `operator_override={"effort":X}`
  returns `resolution.effort==X`, work-shape keys exist; ran the 3 target test files (99 passed).
- **Testing** — clean. **Live mutation**: flipped `effort: medium→extreme` on `agy-coder.md`, confirmed
  the lint fails, reverted clean. AC1/AC5/AC6/cascade-layers/U5 all have behavior-asserting tests.
- **Maintainability** — 1 P1 (finding 1) + release-surface audit that seeded finding 2. Shim pattern
  consistent with #463; convention doc present; agy/deploy `effort:` valid.

## Gate evidence (final HEAD `706cd6a`)

pytest **2185 passed, 1 skipped** · ruff check clean · ruff format clean · mypy success (141 files) ·
marketplace validator 0 errors · `validate_plugins` exit 0 · `release_surface_diff_guard` all bumped.

## Residual risk

Low. The one irreducible caveat is stated honestly in KTD1/KTD7 and the convention doc: the `EFFORT_RIDER`
proxy on the Agent-tool path is a prose directive, not a real reasoning-budget knob. The `inject_effort()`
seam is structured so the `agent` branch swaps rider→native-knob in one function when the harness ships it,
with nothing upstream (authoring, lint, cascade, provenance, reconcile) changing. Tracked as a residual
follow-up in `QUEUED.md`.

**Route:** clean gate → PR-ready. Destination `merge` (operator-confirmed at plan time). Next gate is `/qa`
(advisory) after merge.
