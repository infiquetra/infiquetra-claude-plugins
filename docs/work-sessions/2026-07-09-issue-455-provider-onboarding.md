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

## Checks Run

- U1 focused suites: `177 passed`.
- `uv run pytest tests/test_engine_onboarding.py -q`: `15 passed`.
- `uv run pytest tests/test_engine_promotion.py -q`: `19 passed`.
- Combined U1-U4 focused gate: `216 passed`.
- Focused Ruff format/check passed for onboarding, conformance, promotion, and their tests.
- Isolated mypy passed for onboarding/promotion and their tests with `--follow-imports=skip`.
- The planned transitive mypy command reached pre-existing errors in `engine_overlay.py`,
  `fleet_commons_shim.py`, and `engine_dispatch.py`; no unrelated baseline fix was made.

## Review State

- Doc review resolved all two P1, two P2, and one P3 findings before implementation.
- Team Execution serial reviewers, validators, and the code-review gate remain pending.

## Next Step

Run Team Execution serial reviewer consensus and required validators, then the Saga code-review gate.
