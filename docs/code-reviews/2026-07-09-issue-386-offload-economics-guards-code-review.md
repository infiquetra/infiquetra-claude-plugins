---
target: work/386-offload-economics-guards
reviewed_revision: 3e83d76a91f08ca676c2023ae6548aa11077b32f
base_revision: 44a774e4489e32a4be38f022d11420a3060ea13b
linked_issue: https://github.com/infiquetra/infiquetra-claude-plugins/issues/386
plan: docs/plans/2026-07-09-issue-386-offload-economics-guards-plan.md
work_session: docs/work-sessions/2026-07-09-issue-386-offload-economics-guards.md
blocked: false
orchestration_mode: inline
---

# Code Review - Issue #386 Offload Economics Guards

## Verdict

Not blocked. No unresolved P0/P1/P2/P3 findings remain.

Scope Check: CLEAN.

Intent: Add dispatch-time offload economics guards, operator previews, and durable net-savings evidence.

Delivered: Registry cost-policy metadata, pure economics policy decisions, pre-adapter dispatch halts,
manifest/run-ledger economics records, offer previews, release surfaces, and focused/full validation.

## Review Team

- correctness - always-on; checked break-even, budget, free-class, missing-estimate, and status-sign paths.
- security - always-on; checked external-engine trust boundary and rejected gatekeeper authority remained intact.
- testing - always-on; checked guard, schema, CLI, manifest, ledger, and release-surface tests.
- maintainability/conventions - always-on; checked registry vocabulary, release surfaces, and docs parity.
- reliability - selected because dispatch halt/error paths changed.
- api-contract - selected because registry, manifest, ledger, and CLI schemas changed.
- adversarial/red-team - selected because the diff touches external-engine spend and integration boundaries.
- agent-native - selected because `engine_offer.py` exposes operator-facing preview behavior.

## Built vs Planned

| Unit | State | Evidence |
| --- | --- | --- |
| U1 Registry Cost Policy Fields | DONE | `engine_registry.py` parses `cost_class` and `budget_ceiling_usd`; registry/CLI/lint tests cover metered/free rows. |
| U2 Pure Offload Economics Helper | DONE | `chaperone_economics.py` adds `OffloadEconomicsInput`, `OffloadEconomicsDecision`, and `NetSavingsRecord`; `tests/test_chaperone_economics.py` covers proceed, free, break-even, ceiling, missing, negative, and stable preview paths. |
| U3 Dispatch-Time Halt Wiring | DONE | `engine_dispatch.dispatch()` evaluates economics before `_build_invocation()` and runner execution; dispatch tests assert halt paths do not invoke the runner. |
| U4 Manifest And Ledger Net-Savings Records | DONE | `provenance_manifest.py` adds typed `EconomicsRecord`; dispatch manifests and run-ledger engine facts carry net-savings fields; manifest matrix guard is updated. |
| U5 Operator Cost-Delta Preview And Release Surfaces | DONE | `engine_offer.py` adds advisory `cost_delta_preview`; Saga plugin version/changelog/marketplace parity checks pass. |

COMPLETION: 5/5 DONE, 0 PARTIAL, 0 NOT-DONE, 0 CHANGED, 0 UNVERIFIABLE.

## Findings

### Unresolved

| # | File | Issue | Reviewer | Confidence | Route |
| --- | --- | --- | --- | --- | --- |
| - | - | None | - | - | - |

### Resolved During Review

| # | File | Issue | Reviewer | Confidence | Route |
| --- | --- | --- | --- | --- | --- |
| 1 | `plugins/saga/scripts/provenance_manifest.py:366` | Manifest readback accepted mismatched `net_savings_tokens` sign and `net_savings_status` label, allowing persisted economics evidence to claim a positive result with a negative numeric value. Fixed in `3e83d76` by deriving the expected status from the signed token count and rejecting mismatches; covered by `tests/test_provenance_manifest.py:174`. | api-contract / adversarial | 75 | fixed |

## Coverage

Suppressed findings: 0.

Residual risks:

- Economics estimates remain caller-supplied. This PR enforces declared estimates; it does not add provider billing API integrations or live pricing fetches.
- `engine_offer.py` previews are advisory only by design. Dispatch remains the hard enforcement point.
- Provider budget ceilings are based on current run-ledger facts plus dispatch estimates, not a global provider account balance.

Testing gaps:

- No live provider billing integration was exercised; out of scope for #386.
- No deployment gate applies; this is repository-local Python/schema/docs work.

## Checks

- `uv run --with pytest --with pytest-cov python -m pytest tests/test_provenance_manifest.py tests/test_manifest_consumer_matrix.py -v` - passed, 19 tests.
- `uv run --with pytest --with pytest-cov --with fakeredis python -m pytest` - passed, 2768 tests, 1 skipped.
- `uv run ruff check .` - passed.
- `uv run ruff format --check .` - passed.
- `uv run mypy plugins/ scripts/ tests/ --ignore-missing-imports` - passed.
- `uv run python scripts/sync_marketplace.py --check` - passed.
- `uv run python scripts/check_release_surface_parity.py` - passed.
- `git diff --check origin/main...HEAD` - passed.

## Route

Proceed to PR prep, CI monitor, merge, issue close, board Done, and outcome harvest.
