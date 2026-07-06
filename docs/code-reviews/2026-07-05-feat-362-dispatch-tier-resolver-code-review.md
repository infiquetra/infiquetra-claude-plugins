# Code Review — Dispatch-time tier resolver (#362)

**Target:** `git diff` vs `origin/main` (merge-base `5498a3a`), branch `feat/362-dispatch-tier-resolver`, PR #493.
**Reviewed revision:** `9379a7f` (working tree == HEAD).
**Blocked:** **NO** — no P0/P1 findings.
**Linked:** issue #362 · plan `docs/plans/2026-07-05-dispatch-tier-resolver-plan.md` · work-session `docs/work-sessions/2026-07-05-dispatch-tier-resolver.md` · saga `issue-362`.

## Verdict

Clean to ship. Three independent read-only lenses (correctness, testing, maintainability, in disposable worktrees) plus a built-vs-planned audit found **no P0/P1**. The resolver is correct and behaviorally verified; the 25-agent migration is provably tier-preserving; the tests are genuine (independently anchored against pre-migration git history, not self-referential). Two P2 advisories remain — release-surface hygiene and a mislabelled test — neither blocks.

## Scope check: CLEAN (with one documented note)

Intent: build the dispatch-time tier resolver (#362, R1–R8). Delivered: exactly that. `render_tier_table.py` is a wired helper for U3 (not drift). One informational note: the diff includes the two `execution_spec.py` emitter fixes (+31) — beyond #362's tier-resolver scope but necessary to build it via cc-workflows-ultracode, documented in defect **#494**. Split-or-keep is the operator's call.

## Plan-completion audit (built-vs-planned)

| Req | Status | Evidence |
|---|---|---|
| R1 resolver | DONE | `tier_resolver.py:161-166` signature; CLI resolves live |
| R2 registry | DONE | `tier_policy.json` 6 keys, all values ∈ MODELS/EFFORTS |
| R3 cheaper_fallback | DONE | `:92-100` weaken-model-then-effort, floor no-op; verified opus→sonnet |
| R4 confirm-gate | DONE | `:159` fable/xhigh only; verified override→needs_confirm=True, opus/high→False |
| R5 role-tier migration | DONE | 25 agents, **tier-preserving** verified independently (10 opus / 8 sonnet / 7 haiku) against pre-migration history |
| R6 SKILL render + drift-guard | DONE | `render_tier_table.py` + `test_skill_registry_sync` |
| R7 effort emit + spawn-site guard | DONE | A7 table + `test_spawn_site_enumeration` parses the real sandbox-spawn-sites table |
| R8 release surfaces | PARTIAL | saga 0.62.0 + te 2.10.0 bumped & consistent; **fleet-core NOT bumped** (see P2 #1) |

## Findings

| # | Pri | Conf | File | Issue | Route |
|---|---|---|---|---|---|
| 1 | P2 | 85 | `plugins/fleet-core/.claude-plugin/plugin.json` | fleet-core gained the resolver/registry/render-table (370 new lines, a consumed cross-plugin API) but stayed at `0.2.0` — no version bump, no CHANGELOG entry, no marketplace change. CI won't catch it (drift-guard checks plugin.json↔marketplace *consistency*, which holds at 0.2.0). Repo rule: "don't treat as PR-ready until installed metadata tells the same story." R8 made this a conditional judgment call. | gated_auto |
| 2 | P2 | 80 | `tests/test_tier_resolver.py:464-486` | `test_model_fallback_when_registry_absent` tests a non-existent mechanism: there is no code path that catches a registry-load failure and substitutes `model:` (confirmed — no try/except in `tier_resolver.py`). KTD5's "model: kept as fallback" is really a *structural non-dependency* (Claude Code reads `model:` natively, independent of the resolver), not a resolver fallback. The test can't fail for any wrong impl because none exists. | manual (reframe docstring + KTD5 language) |

**Suppressed (below the anchor-75 gate):** P3 conf-60 — `test_skill_registry_sync_catches_seeded_divergence` (`:292-296`) seeds into a local string copy rather than mutating `SKILL.md`; a valid proxy given the sibling `test_skill_registry_sync` does the real comparison, but indirect. Informational only.

## Coverage / residual risk

- Lenses run: correctness, testing, maintainability (all clean of P0/P1). Suppressed: 1.
- Strongest tests (verified genuine): `test_role_tier_resolves_for_all_agents` (all 25, anchored to git history), `test_cheaper_fallback_one_rung_with_floor_no_op`, `test_expensive_tier_confirm_gate`, `test_envelope_ceiling_*`, `test_spawn_site_enumeration_routes_through_resolver`.
- Full suite green: 2113 passed; ruff + mypy clean.
- Cross-leaf: effort-honoring (#363) and vocab-source/ladder (#370) are deferred with concerns filed; not in scope here.

## Route

No P0/P1 → **`/qa`** is the next gate (ship-readiness). The two P2s are non-blocking but worth fixing before merge (repo release-surface rule for #1; accuracy for #2). Fixer dispatch is offered, not auto-run.
