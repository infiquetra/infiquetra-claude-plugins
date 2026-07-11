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
- Final Codex contract pytest: 34 passed, including all six GPT-5.6 model/effort pairs against a
  fake Codex executable.
- Full pytest: 3,094 passed, 0 failed, 1 skipped.
- Registry validator and conformance: 13 rows passed.
- Marketplace sync check, release-surface parity, Ruff, mypy, changed-file Bandit, and
  `git diff --check`: passed.
- Full recursive Bandit retains pre-existing repository and nested-environment findings; changed
  Saga/Codex files have zero medium/high findings.
- Code review: `docs/code-reviews/2026-07-10-issue-559-gpt-56-codex-routing-code-review.md`, clean and
  not blocked.
- Commit: `6d49c75` (`feat(codex): route current models through saga dispatch`).

## Next step

Push/open the PR and run the external CI, merge, issue, and board closeout sequence after operator
confirmation.

## Residual risk

Terra/Luna capability ratings and relative cost-speed ranks are provisional metadata. Credit
accounting and spend-guard calibration remain intentionally unchanged and are not proven by this
change.
