# Issue #385 Engine Output Trust Boundary Code Review

Date: 2026-07-09
Target: branch `work/385-engine-output-trust-boundary`
Base: `origin/main` at `926f965787d27b93519c45df202b516c34e0a0ab`
Reviewed revision: `b07210b5cd023adaa36a50b8ff4b9737df7be4e1`
Issue: `infiquetra/infiquetra-claude-plugins#385`
Plan: `docs/plans/2026-07-09-issue-385-engine-output-trust-boundary-plan.md`
Work session: `docs/work-sessions/2026-07-09-issue-385-engine-output-trust-boundary.md`
Reviewer backend: `inline`
Verdict: PASS

## Scope Check

Scope Check: CLEAN
Intent: Document and test the external-engine advisory-text trust boundary before advisory prose crosses
into gated Saga and Team Execution flows.
Delivered: branch adds the Saga trust-boundary contract, AST-based guard tests, adversarial
`AdvisoryEvidence.evidence` fixture, Team Execution cross-references, work-session evidence, and release
surface bumps.

## Review Team

- correctness: always-on; checked plan units, guard precision, release metadata, and unchanged
  `satisfy_gate` behavior.
- security: always-on; checked advisory text is treated as untrusted input and forbidden sink coverage
  includes shell, eval/exec, file paths, and gate-token status derivation.
- testing: always-on; checked contract anchors, seeded unsafe fixtures, clean-call-site scan, adversarial
  evidence behavior, and broad local check evidence.
- maintainability/conventions: always-on; checked version/CHANGELOG/marketplace consistency and narrow
  call-site scope is documented.
- adversarial/red-team: selected because the diff formalizes an external-engine output trust boundary.

## Plan Completion

COMPLETION: 4/4 DONE, 0 PARTIAL, 0 NOT-DONE, 0 CHANGED, 0 UNVERIFIABLE

- U1 DONE: `plugins/saga/references/engine-output-trust-boundary.md:3` states external-engine output is
  untrusted and not a command, file path, gate token, or verifier decision. The same file enumerates
  in-scope fields at `plugins/saga/references/engine-output-trust-boundary.md:10` and
  `plugins/saga/references/engine-output-trust-boundary.md:11`, forbidden sinks at
  `plugins/saga/references/engine-output-trust-boundary.md:17`, and typed gate-status handling at
  `plugins/saga/references/engine-output-trust-boundary.md:27`.
- U2 DONE: `tests/test_engine_output_trust_boundary.py:40` scopes current Python call sites,
  `tests/test_engine_output_trust_boundary.py:102` implements the AST visitor, and
  `tests/test_engine_output_trust_boundary.py:188` asserts current call sites produce no violations.
  Seeded unsafe fixtures prove f-string subprocess use and gate-token comparison are caught at
  `tests/test_engine_output_trust_boundary.py:197` and
  `tests/test_engine_output_trust_boundary.py:211`.
- U3 DONE: `tests/test_engine_output_trust_boundary.py:233` builds the adversarial fixture;
  `tests/test_engine_output_trust_boundary.py:252` proves unverified payloads fail; and
  `tests/test_engine_output_trust_boundary.py:267` proves observer-corroborated, Claude-verified payloads
  pass without executing subprocess or writing files at `tests/test_engine_output_trust_boundary.py:269`.
  `plugins/saga/scripts/engine_dispatch.py` is unchanged in this branch, and existing gate logic remains
  provenance-based at `plugins/saga/scripts/engine_dispatch.py:640`.
- U4 DONE: Team Execution references the contract at
  `plugins/team-execution/skills/team-execution/references/validator-criteria.md:5` and
  `plugins/team-execution/skills/team-execution/references/validator-registry.md:103`. Saga is bumped to
  `0.75.9` at `plugins/saga/.claude-plugin/plugin.json:3` and asserted at
  `tests/test_saga_plugin.py:48`; Team Execution is bumped to `2.14.1` at
  `plugins/team-execution/.claude-plugin/plugin.json:3` and asserted at
  `tests/test_team_execution_plugin.py:64`.

## Findings

No P0/P1/P2/P3 findings.

## Coverage

Suppressed count: 0

Residual risks:

- The guard intentionally scans only current Python call sites. Future advisory text fields or consumers
  must update `plugins/saga/references/engine-output-trust-boundary.md` and
  `tests/test_engine_output_trust_boundary.py:40` in the same PR.
- The review covers local diff behavior and release metadata, not a live external-engine dispatch run.

Testing gaps:

- No remaining blocker. Full repo pytest passed with the existing Redis-channel exclusions used by the
  outcome's prior leaves.

## Checks Reviewed

- `uv run pytest tests/test_engine_output_trust_boundary.py -v`
- `uv run ruff check tests/test_engine_output_trust_boundary.py`
- `uv run ruff format tests/test_engine_output_trust_boundary.py`
- `uv run pytest tests/test_engine_output_trust_boundary.py tests/test_saga_engine_dispatch.py -k satisfy_gate -v`
- `uv run pytest tests/test_saga_plugin.py tests/test_team_execution_plugin.py -q`
- `uv run ruff check .`
- `uv run ruff format --check .`
- `uv run mypy plugins/ scripts/ tests/ --ignore-missing-imports`
- `uv run python scripts/check_release_surface_parity.py`
- `uv run python scripts/sync_marketplace.py --check`
- `uv run python marketplace/validator/validate.py`
- `python3 tools/release_surface_diff_guard.py --base-ref origin/main`
- `git diff --check`
- `COVERAGE_FILE=/tmp/cov-385-full uv run pytest -q --ignore=tests/test_redis_channel_channel.py --ignore=tests/test_redis_channel_notifier.py`

## Route

PR-ready. Commit this review artifact, open PR, monitor CI, and merge when checks stay green.
