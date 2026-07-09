# Issue #382 Consensus Advisory Seat Code Review

The code is ready for PR.

## Review Result

| Field | Value |
| --- | --- |
| Target | merge-base diff against `origin/main`, including untracked #382 artifacts |
| Reviewed revision | working tree at `16d3334` plus local #382 changes |
| Linked issue | `infiquetra/infiquetra-claude-plugins#382` |
| Linked plan | `docs/plans/2026-07-09-issue-382-consensus-advisory-seat-plan.md` |
| Linked work session | `docs/work-sessions/2026-07-09-issue-382-consensus-advisory-seat.md` |
| Blocked | no |

## Built Vs Planned

| Unit | Status | Evidence |
| --- | --- | --- |
| U1 Add Consensus Advisory Helper | done | `consensus_advisory.py` models gated/advisory seats and convergence buckets; `test_team_execution_consensus_advisory.py` covers exclusion, absence, convergence, and invalid vocabulary. |
| U2 Add Advisory-Reviewer Gate Refusal | done | `AdvisoryEvidence.role_kind` defaults to `worker`; `satisfy_gate()` rejects `advisory-reviewer`/`panel`; dispatch tests cover verified advisory refusal. |
| U3 Update Team Execution Protocol Docs | done | Consensus, registry, and external-engine worker references document the non-scoring advisory seat and convergence report; drift guards pin the contract. |
| U4 Update Release Surfaces And Journal | done | Team Execution is `2.14.0`; marketplace, changelog, tests, and DECISIONS are aligned. |

## Findings

| Priority | Status | Finding | Resolution |
| --- | --- | --- | --- |
| P2 | fixed | Advisory result status accepted arbitrary strings, so a typo such as `halt` could be treated as a participating advisory reviewer instead of an absence/error. | Added a closed `STATUSES` vocabulary and a regression test. |

No unresolved P0/P1/P2/P3 findings remain.

## Scope Check

Clean. The diff stays on #382: a small helper, Saga gate-role refusal, Team Execution docs/tests, release surfaces, and durable lifecycle artifacts.

## Checks

- `COVERAGE_FILE=/tmp/cov-382-full-final uv run pytest -q --ignore=tests/test_redis_channel_channel.py --ignore=tests/test_redis_channel_notifier.py` — passed, 2601 passed, 1 skipped.
- `uv run ruff check .` — passed.
- `uv run ruff format --check .` — passed.
- `uv run mypy plugins/ scripts/ tests/ --ignore-missing-imports` — passed.
- `uv run python marketplace/validator/validate.py` — passed with existing recommended-field warnings.
- `uv run python scripts/sync_marketplace.py --check` — passed.
- `uv run python scripts/check_release_surface_parity.py` — passed.
- `python3 tools/release_surface_diff_guard.py --base-ref origin/main` — passed.
- `git diff --check` — passed.
- `uv run bandit plugins/team-execution/skills/team-execution/scripts/consensus_advisory.py plugins/saga/scripts/engine_dispatch.py` — passed.

## Residual Risk

Full `uv run bandit -r plugins/` still reports pre-existing repo-wide findings outside the changed files. This review used scoped Bandit for changed Python files plus the existing repo gates.
