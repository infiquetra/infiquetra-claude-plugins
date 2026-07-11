# Work Session: Issue #559 GPT-5.6 Codex Routing

## Scope

Implement the supplied plan to register GPT-5.6 Sol, Terra, and Luna Codex variants and preserve
selected model/effort identity through Saga dispatch, the Codex bridge, receipts, evidence, and
release/operator documentation.

## Completed

- U1: Added six GPT-5.6 high/xhigh registry rows, retained GPT-5.5 legacy selectors, made Sol high
  the only Codex default, added release dates and provisional relative profiles, and required
  canonical `<model>-<effort>` identity plus explicit model/effort on Codex CLI rows.
- U2: Registry-backed `build_codex_invocation()` now forwards `model` and `effort` and fails closed
  before runner execution when either is missing. Direct synthetic/direct-delegate default behavior
  remains compatible.
- U3: Launched Codex receipts use `<model>-<effort>` when both values are explicit; result payloads
  and projections expose model and effort; evidence/manifest identity tests cover the same value.
- U4: Updated Saga, Codex, and team-execution docs, changelogs, manifests, marketplace metadata,
  engineering journal, and release-version contract tests.

## Checks

- Focused pytest: 346 passed with `--no-cov`.
- `git diff --check`: passed.

## Next step

Run the full registry, marketplace, pytest, Ruff, mypy, and Bandit gates, then inspect the final diff
and perform the code-review readiness gate.

## Residual risk

Terra/Luna capability ratings and relative cost-speed ranks are provisional metadata. Credit
accounting and spend-guard calibration remain intentionally unchanged and are not proven by this
change.
