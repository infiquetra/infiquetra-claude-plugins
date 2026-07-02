# Doc-review readiness — leak-guard parity + mypy gate plan

**Verdict: READY to drive implementation.** No blocking findings. The plan's load-bearing claims
were independently re-verified against the working tree; the two units are implementable as written,
touch disjoint file pairs, and carry no runtime blast radius.

## Review-result contract

- **Target:** `docs/plans/2026-07-02-leak-guard-parity-mypy-gate-plan.md`
- **Reviewed revision:** working tree @ `main` (2026-07-02)
- **Blocked:** no
- **Findings:** 0 × P0, 0 × P1, 0 × P2, 2 × P3 — **both P3s resolved on operator request (2026-07-02)**
- **Applied fixes:** 3 (mypy-clean precondition; guard-wiring integration tests; failure_hint alignment)
- **Linked issue:** infiquetra/infiquetra-claude-plugins#314
- **Linked saga:** `.claude/saga/sagas/issue-314/` (git-ignored, not durable output)
- **Review artifact:** `docs/reviews/2026-07-02-leak-guard-parity-mypy-gate-plan-readiness.md`

## Applied fixes

| Fix | Location | Evidence |
|---|---|---|
| Added a "Precondition (verified 2026-07-02)" line stating the tree is mypy-clean so the new gate step lands green | Plan U2 | `uv run python -m mypy plugins/ scripts/ tests/ --ignore-missing-imports` → "Success: no issues found in 113 source files" |
| Added two guard-wiring integration tests (`monkeypatch` `ROOT`+baseline → `tmp_path`, assert the guard raises on a new dir / passes on a pre-existing one) to U1 — resolves P3 #1, literal AC#1 proof at the guard level | Plan U1 | operator-authorized 2026-07-02; safe because state lives under `tmp_path`, honoring KTD1 no-pollution |
| Aligned U2 `failure_hint` to the `uv run python -m mypy …` form, matching its own `command` array and the existing ruff steps' hint style — resolves P3 #2 | Plan U2 | `tools/gate-manifest.json:8` (ruff hint uses `uv run python -m ruff …`) |

## Independent verification

Every claim that would cause wrong execution if false was re-checked against the live tree:

| Plan claim | Verified | Evidence |
|---|---|---|
| Sagas branch already baselined in #317; issue body is stale | Yes | `tests/test_saga_saga.py:1346-1364` |
| Legacy branch still absolute `== []`, no baseline | Yes | `tests/test_saga_saga.py:1366-1369` |
| No dedicated proof-test for the guard logic (AC#1 gap) | Yes | grep: `_PREEXISTING_SAGA_DIRS` referenced only inside the guard |
| CI mypy invocation to mirror | Yes | `.github/workflows/ci.yml:123` = `uv run python -m mypy plugins/ scripts/ tests/ --ignore-missing-imports` |
| Local gate omits mypy | Yes | `tools/gate-manifest.json` steps: ruff-format, ruff-lint, validate-plugins, validate-marketplace, pytest |
| No hidden exact step-count assertion U2 would break | Yes | `tests/test_pre_push_gate.py:69` uses `len(steps) > 0`; only `== 0/2` are hook exit-code tests |
| `frozenset[str]` helper annotation is valid | Yes | `tests/test_saga_saga.py:27` `from __future__ import annotations`; frozenset already used at `:1347` |
| New gate step won't red-block on landing | Yes | tree mypy-clean (113 files) |

## Remaining findings

| # | Priority | Finding | Status |
|---|---|---|---|
| 1 | P3 | AC#1's proof was helper-level only. **Resolved** — U1 now adds two `monkeypatch`-to-`tmp_path` guard-wiring integration tests that assert the guard itself raises on a new dir and passes on a pre-existing one (legacy branch mirrored), giving a literal AC#1 proof without repo pollution. | resolved (2026-07-02) |
| 2 | P3 | U2's `failure_hint` used `uv run mypy …` vs the `command` array's `python -m` form. **Resolved** — U1/U2 hint aligned to `uv run python -m mypy …`, matching the command array and the existing ruff-step hints. | resolved (2026-07-02) |

## Readiness summary

The plan is smaller than issue #314 reads because #317 silently closed AC#2/AC#3 (the sagas-branch
false-positive) — the plan's drift-audit captures this accurately, so an implementer won't re-do
shipped work. What remains is genuine and well-scoped: legacy-branch baseline parity + a
filesystem-free proof-test (U1), and the mypy gate step with its drift-guard update (U2). Both
requirements-to-unit mappings are complete (R1/R2→U1, R3/R4→U2), and the verified mypy-clean state
removes the one precondition that could have made U2 land red.

## Residual risk

Low. The only residual is that the legacy-checkpoint branch is dormant on both CI (fresh checkout)
and this dev machine (`.claude/saga/checkpoints/` absent), so U1's legacy-branch change is exercised
only by the synthetic helper tests, not by a live pre-existing checkpoint. That is acceptable — the
helper tests cover the diff semantics directly, and the branch is defensive parity, not a hot path.
