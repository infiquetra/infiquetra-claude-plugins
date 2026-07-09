# Issue #385 Engine Output Trust Boundary Work Session

Date: 2026-07-09
Branch: `work/385-engine-output-trust-boundary`
Plan: `docs/plans/2026-07-09-issue-385-engine-output-trust-boundary-plan.md`
Review: `docs/reviews/2026-07-09-issue-385-engine-output-trust-boundary-plan-review.md`

## Summary

Implemented the external-engine output trust boundary for advisory text crossing into Saga and Team
Execution gated flows. Advisory evidence and validator finding prose are now documented as untrusted
opaque data; regression tests guard current Python consuming paths from shell, eval, path, and gate-token
sinks while preserving existing `satisfy_gate` semantics.

## Implementation Units

- U1: Added `plugins/saga/references/engine-output-trust-boundary.md` defining in-scope advisory text
  fields, allowed opaque-data handling, forbidden executable and gate-decision sinks, and review rules.
- U2: Added `tests/test_engine_output_trust_boundary.py` with a narrow AST guard over current Python
  call sites plus seeded unsafe fixtures proving f-string subprocess use, gate-token comparison, and
  opaque rendering behavior are detected correctly.
- U3: Added an adversarial `AdvisoryEvidence.evidence` fixture containing shell metacharacters, path
  traversal text, and spoofed gate tokens. The fixture remains inert through `satisfy_gate`; unverified
  evidence still fails and observer-corroborated evidence still passes only through existing provenance
  rules.
- U4: Cross-referenced the Saga trust-boundary contract from Team Execution validator references and
  bumped release surfaces for Saga `0.75.9` and Team Execution `2.14.1`, including changelogs,
  marketplace metadata, and version assertions.

## Temporary-Red Proof

The regression proof uses seeded unsafe fixtures in `tests/test_engine_output_trust_boundary.py` rather
than a throwaway production-code mutation. These fixtures deliberately model the failure classes from
the plan and assert the guard catches them, giving a durable equivalent of the temporary-red check for
future maintainers.

## Modified Files

- `.claude-plugin/marketplace.json`
- `plugins/saga/.claude-plugin/plugin.json`
- `plugins/saga/CHANGELOG.md`
- `plugins/saga/references/engine-output-trust-boundary.md`
- `plugins/team-execution/.claude-plugin/plugin.json`
- `plugins/team-execution/CHANGELOG.md`
- `plugins/team-execution/skills/team-execution/references/validator-criteria.md`
- `plugins/team-execution/skills/team-execution/references/validator-registry.md`
- `tests/test_engine_output_trust_boundary.py`
- `tests/test_saga_plugin.py`
- `tests/test_team_execution_plugin.py`

## Checks

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

## Residual Risk

The AST guard is intentionally scoped to current Python call sites. Future advisory-text-bearing fields
or new consumers must update the contract and `PYTHON_CALL_SITES` list in the same PR.

## Next Step

Run the pre-PR code-review gate, commit the review artifact, then open the PR.
