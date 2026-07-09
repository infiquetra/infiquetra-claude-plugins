# Issue #455 Provider Onboarding Work Session

Date: 2026-07-09
Issue: https://github.com/infiquetra/infiquetra-claude-plugins/issues/455
Plan: docs/plans/2026-07-09-issue-455-provider-onboarding-plan.md
Plan review: docs/reviews/2026-07-09-issue-455-provider-onboarding-plan-review.md
Branch: `work/455-provider-onboarding`

## Built

- U1: Added required `probation|advisory` trust standing, migrated incumbents to advisory, exposed
  standing through `/engines`, and made worker/generator versus advisory resolution role-aware.
- U2: Added an offline conformance checker and named CI gate for exact-key, capability-candidate,
  dispatch-invocation, and receipt-emitter reachability.
- U3: Added a strict JSON provider-spec parser, generic HTTP row scaffolder, dry-run/apply CLI,
  parser-anchored insertion, concurrent-edit guard, and atomic shell entrypoint.
- U4: Added read-only exact-variant promotion assessment over a stable, hash-chain-verified run-fact
  snapshot, including distinct bridge-run proof and precise ineligibility reasons.
- U5: Added the provider operator guide, dispatch and `/engines` guidance, journal status, and Saga
  0.75.16 release parity.

## Key Decisions

- Provider onboarding targets the existing `engine-bridge-http` / `http-bridge` path; it never
  generates provider-specific HTTP bridge code.
- V1 accepts OpenAI-compatible Chat Completions providers. CLI providers require a real wrapper.
- New rows start at `trust_tier: probation`; promotion remains an explicit reviewed registry edit.
- Five most recent exact-variant facts must be successful, proof-integrity valid, and keyed to five
  distinct bridge runs. Sibling variants and older facts do not affect the current window.

## Commits

- `6be4606` - trust-tier schema and resolver enforcement.
- `406352c` - offline engine-registry conformance gate.
- `53fae75` - provider onboarding scaffolder and atomic apply.
- `0d57320` - run-ledger promotion assessment.
- `0dccb26` - reject embedding claims from the Chat Completions scaffolder.
- `afb5b1e` - harden provider/evidence inputs from Team Execution review.
- `37c2ef4` - close final Saga code-review gaps.

## Checks Run

- U1 focused suites: `177 passed`.
- `uv run pytest tests/test_engine_onboarding.py -q`: `18 passed`.
- `uv run pytest tests/test_engine_promotion.py -q`: `20 passed`.
- Combined U1-U4 focused gate: `216 passed`.
- Post-remediation behavior and package gate: `260 passed`.
- New-module coverage: onboarding `86%`, promotion `98%`, conformance `91%`.
- Broad repository suite: `2,806 passed, 1 skipped` with the two redis-channel tests excluded because
  the optional `mcp` package is absent locally.
- Focused Ruff format/check passed for onboarding, conformance, promotion, and their tests.
- Isolated mypy passed for onboarding/promotion and their tests with `--follow-imports=skip`.
- Repository-wide Ruff format/check and the canonical full mypy command passed.
- Registry lint, conformance CLI, marketplace sync, release parity, and release diff guard passed.
- Unfiltered pytest collection stops on the two redis-channel imports when `mcp` is absent; no #455
  test or changed path is involved.

## Review State

- Doc review resolved all two P1, two P2, and one P3 findings before implementation.
- Team Execution serial consensus reached in cycle 2: Devil's Advocate `9.4`, Security `9.6`,
  Architecture `9.8`, Testing `9.4`, and Clarity `9.6`. Serial mode is explicitly not independent
  delegated review.
- Security scanner: pass on changed scope. The broad scan's unchanged `board_progression.py` SHA-1
  filename-key finding remains a baseline warning.
- Scenario tester: pass with `260 passed` plus registry and release checks.
- Evidence root: `~/.codex/team-execution/state/infiquetra-claude-plugins/issue-455/`.
- Saga code review: pass with no unresolved P0-P3 findings; artifact at
  `docs/code-reviews/2026-07-09-issue-455-provider-onboarding-code-review.md`.
- GitHub Actions monitor remains pending.

## Next Step

Push the branch, open the PR, and monitor required GitHub Actions checks.
