# Code review — #314 leak-guard parity + mypy gate

**Verdict: CLEAN — safe to merge. Not blocked.**

## Review-result contract

- **Target:** branch `fix/314-leak-guard-parity-mypy-gate`, diff `697fff1...HEAD`
- **Reviewed SHA:** `b727a20af1690ca34b64923951439f8694654982`
- **Mode:** programmatic (pre-PR gate, called by `/work`)
- **Blocked:** no
- **Findings:** 0 × P0, 0 × P1, 0 × P2, 1 × P3 (advisory)
- **Scope check:** CLEAN
- **Linked issue:** infiquetra/infiquetra-claude-plugins#314
- **Plan:** `docs/plans/2026-07-02-leak-guard-parity-mypy-gate-plan.md`
- **Work session:** `docs/work-sessions/2026-07-02-leak-guard-parity-mypy-gate.md`

## Plan-completion audit

| Unit | Verdict | Evidence |
|---|---|---|
| U1 — legacy baseline + `_leaked_children` helper + proofs | DONE | `tests/test_saga_saga.py`: helper + `_PREEXISTING_LEGACY_CHECKPOINTS`; both guard branches routed through the helper; 3 helper-level + 4 guard-wiring tests |
| U2 — mypy gate step + drift-guard | DONE | `tools/gate-manifest.json` mypy step mirrors `.github/workflows/ci.yml:123` token-for-token; `test_pre_push_gate.py` `required` set + docstrings updated 5→6 |

## Lens findings

Lenses run: correctness, security, testing, maintainability/conventions (always-on) + build/tooling-verification (gate-manifest change).

- **Correctness:** `_leaked_children` = `sorted(current - baseline)`; sagas branch behavior unchanged, legacy branch correctly gains the baseline diff (AC#4). All 4 guard-wiring tests traced: `monkeypatch` auto-restores, writes confined to `tmp_path`, branch-not-under-test skipped via `.exists()`. No issues.
- **Security:** no secrets/auth/injection surface (test-infra). No issues.
- **Testing:** covers happy (baseline ignores pre-existing), leak-detection (new entry caught), coexistence (#281 case), and both guard branches end-to-end. Strong.
- **Maintainability:** naming consistent with `_PREEXISTING_*`; `sys.modules[__name__]` pattern commented; ruff-formatted.
- **Build/tooling:** mypy command array matches CI token-for-token; placement (after ruff-lint, before pytest) per KTD3; `failure_hint` consistent with house style.

## Findings

| # | Priority | File | Issue | Route |
|---|---|---|---|---|
| 1 | P3 | tests/test_saga_saga.py | Legacy guard-wiring tests skip the saga branch implicitly (via sagas-dir nonexistence under `tmp_path`) rather than patching `_PREEXISTING_SAGA_DIRS` explicitly. Correct as written; explicit patch would future-proof intent. | advisory |

## Coverage

- Suppressed (below anchor 75): 0.
- Residual risk: legacy-checkpoint branch is dormant on real machines (`.claude/saga/checkpoints/` absent on CI and dev), so live exercise is synthetic-only — acceptable defensive parity.
- Verification: full pre-push gate green (ruff, mypy 113 files, validators, pytest 1706 passed); leak-guard passed live with real in-flight sagas present.
