# Work session — #314 leak-guard legacy parity + local mypy gate

**Date.** 2026-07-02
**Issue.** infiquetra/infiquetra-claude-plugins#314
**Plan.** `docs/plans/2026-07-02-leak-guard-parity-mypy-gate-plan.md`
**Doc-review.** `docs/reviews/2026-07-02-leak-guard-parity-mypy-gate-plan-readiness.md` (READY, 0 findings)
**Branch.** `fix/314-leak-guard-parity-mypy-gate`
**Destination.** merge · **Backend.** inline

## What shipped

### U1 — leak-guard legacy-branch parity + pure helper + proofs (`tests/test_saga_saga.py`)
- Added `_PREEXISTING_LEGACY_CHECKPOINTS` collection-time baseline mirroring `_PREEXISTING_SAGA_DIRS`.
- Extracted `_leaked_children(current, baseline) -> sorted[str]`; both guard branches now route
  through it, so the legacy-checkpoint branch gains the baseline diff (AC#4).
- Added 7 proof-tests: 3 helper-level (pure set logic) + 4 guard-wiring integration
  (`monkeypatch` `ROOT`/baseline → `tmp_path`, assert the guard *itself* raises on a new saga dir /
  new legacy checkpoint and passes on a pre-existing one) — literal AC#1 + false-positive proof.

### U2 — mypy step in the local pre-push gate (`tools/gate-manifest.json`, `tests/test_pre_push_gate.py`)
- Added a `mypy` step mirroring `.github/workflows/ci.yml:123` token-for-token, placed among the
  static checks before pytest.
- Drift-guard `test_manifest_contains_required_gate_steps` now requires `mypy`; "5→6 steps" docstrings updated.

## Verification

Full pre-push gate run green (all 6 steps):

| Step | Result |
|---|---|
| ruff format --check . | 181 files already formatted |
| ruff check . | All checks passed |
| mypy plugins/ scripts/ tests/ --ignore-missing-imports | Success: no issues found in 113 source files |
| validate_plugins.py | exit 0 |
| marketplace validate.py | All validations passed |
| pytest | 1706 passed in ~34s |

**Live proof:** the leak-guard ran inside the full suite with real in-flight sagas present
(`issue-287/318/285/314` under `.claude/saga/sagas/`) and passed — the #281 false-positive scenario,
now green. The 4 new guard-wiring tests wrote only under `tmp_path`, so they did not pollute the real
tree (the guard would have caught them if they had).

**Acceptance criteria:** AC#1 (proof-test) ✓ · AC#2/AC#3 (already shipped in #317, re-confirmed live) ✓ ·
AC#4 (legacy parity) ✓ · mypy-gate comment scope ✓.

## Next step

Pre-PR code-review gate, then open PR → merge (destination=merge) under operator confirmation. On
merge, close #314 noting AC#2/AC#3 were pre-satisfied by #317 and this PR completed AC#1 + AC#4 +
the mypy-gate comment scope.
