# Code Review — Single-source tier palette (#370)

**Target:** `feat/370-tier-vocab-single-source` · merge-base `main` · reviewed at `1e34fae`, fixes at `6315564`
**Mode:** programmatic (`/work` pre-PR gate) · two adversarial `saga:readonly-verifier` lenses (read-only, worktree-isolated)
**Blocked:** **NO** — 0 P0/P1 unresolved. Correctness lens found no bugs; efficacy lens found 3 guard defects, all fixed + regression-tested.
**Linked:** plan `docs/plans/2026-07-06-tier-vocab-single-source-plan.md` · work-session `docs/work-sessions/2026-07-06-tier-vocab-single-source.md`

## Verdict summary

The correctness verifier ran an **exhaustive equivalence check** — old `min(MODELS.index)`/`max(EFFORTS.index)`
vs the new `strongest()` across the full 1/2/3-unit combinatorial tier space — and found **0 mismatches**,
plus verified the HALT/exclusion logic and that `segment_units` cannot structurally produce an unsupported
combo from valid inputs. The efficacy verifier hunted for trivially-green guards and found three real ones,
all now closed.

## Findings and resolutions

| # | Pri | Finding | Verdict | Resolution |
|---|---|---|---|---|
| A8 | P1→fixed | AC8 tier-token regex requires *unspaced* `opus/high`; the `/plan` table is *spaced* (`opus / high`) → guard vacuously green for `/plan` | CONFIRMED (injected `opus / superhigh`, guard still passed) | Scoped the token guard to the team-execution table (unspaced, its purpose); added `test_plan_table_render_synced` proving the `/plan` table is guarded by render-equality (`render_block() in plan_text`) — reds on drift or removal (`6315564`) |
| A1 | P2→fixed | `_vocabulary_redefinitions` missed `tuple([...])`-wrapped redefinition | CONFIRMED (appended `_X = tuple([...])`, guard passed) | Guard now also inspects `tuple`/`list`/`set`/`frozenset` calls wrapping a vocab literal; forcing test asserts the call-wrapped case reds (`6315564`) |
| esc | P3→fixed | `escalate(ceiling=weaker)` could push *down*, contradicting "no-op" | note, unreachable today | Made `escalate`/`downgrade` monotonic (outer `max`/`min` keeps the result on the intended side); test added — matters for #364's runtime ladder climbing which calls `escalate` (`6315564`) |
| A9 | P3 | AC9's literal grep (`^MODELS = `) matches the re-export alias; untested | PLAUSIBLE | Intent (no inline tuple) satisfied and **covered** by U4's vocab-redefinition scan of `execution_spec.py`; documented as doc-review finding H. No code change. |

## Confirmed solid (not trivially green)

- U3 HALT wiring is genuine production code (`Tier.validate`/`Unit.validate`), exercised through the real
  `SpecError` path; `test_segment_tier_merge_prefers_fable_and_xhigh` still green against the refactor.
- Registry-rank guards exercise `_derive_ordered` against live + scratch data.
- Release surfaces: `release_surface_diff_guard --base-ref main` OK; `sync_marketplace --check` matches;
  fleet-core 0.5.0 / saga 0.64.0 agree across plugin.json / marketplace / CHANGELOG / the saga version pin;
  team-execution correctly unbumped (its SKILL.md is read, not written).

## Gates (final, at `6315564`)

`uv run pytest` → 2214 passed, 1 skipped · `ruff format --check` + `ruff check` clean · `mypy` clean ·
`release_surface_diff_guard --base-ref main` → all changed plugins bumped.
