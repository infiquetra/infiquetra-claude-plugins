# Code Review: Issue #455 Provider Onboarding

Date: 2026-07-09
Target: `work/455-provider-onboarding` against `origin/main`
Reviewed revision: `37c2ef4482e7facfe6101f366ab6e65a07ab6f3e`
Merge base: `644df63b1a38aa191d78ca127c3b4c088533fda7`
Issue: https://github.com/infiquetra/infiquetra-claude-plugins/issues/455
Plan: `docs/plans/2026-07-09-issue-455-provider-onboarding-plan.md`
Work session: `docs/work-sessions/2026-07-09-issue-455-provider-onboarding.md`
Backend: `team-execution` (`team-execution-serial` evidence)
Blocked: no

## Verdict

**PASS - no unresolved P0, P1, P2, or P3 findings.**

The review selected correctness, security, testing, maintainability/conventions, reliability, and
operator-documentation lenses. Team Execution reached serial reviewer consensus in cycle 2, and the
security scanner and scenario tester passed. Serial review is explicitly not independent delegated
review.

## Scope Check

**CLEAN**

Intent: add safe generic-HTTP provider onboarding, offline registry conformance, probationary trust
standing, and evidence-only promotion assessment.

Delivered: the diff implements those paths, their resolver and CI enforcement, operator docs, Saga
0.75.16 release surfaces, tests, and durable lifecycle evidence. The parser and CLI hardening added
during review is directly within the plan's fail-closed input and evidence requirements.

## Built vs Planned

| Unit | Status | Evidence |
| --- | --- | --- |
| U1 - Trust-tier schema and resolver enforcement | DONE | Required row field, incumbent migration, role-aware filtering/halts, memo isolation, `/engines` output, and role-matrix tests. |
| U2 - Offline registry conformance gate | DONE | Reusable checker, all-errors report, dead-wire and no-side-effect tests, and named CI step. |
| U3 - Provider scaffolder and atomic apply | DONE | Strict JSON parser, fixed generic bridge defaults, dry-run/apply, parser-anchored insertion, source-hash guard, atomic replace, shell wrapper, and negative-path coverage. |
| U4 - Telemetry-fed promotion assessment | DONE | Stable chain-verified snapshot, exact-variant latest-five window, distinct proof-valid bridge keys, deterministic CLI, and corruption/standing tests. |
| U5 - Documentation, release, and durable evidence | DONE | Provider guide, dispatch and `/engines` references, Saga 0.75.16 triad, journal status, work session, and package contract test. |

All requirements R1-R10 are represented by implementation and focused tests. Live provider
availability remains explicitly outside scope.

## Review Findings

No unresolved findings.

Resolved during review:

| Priority | Finding | Resolution |
| --- | --- | --- |
| P2 | Duplicate/non-finite JSON and malformed encoding/YAML did not consistently fail through clean CLI errors. | Fixed in `afb5b1e`; strict object parsing, finite-number checks, UTF-8 handling, and CLI regression tests added. |
| P2 | Installed-plugin references used repo-relative links to a root-level guide. | Fixed in `afb5b1e`; references now use the canonical GitHub URL. |
| P2 | Promotion default-ledger resolution could raise an uncaught git-common-dir `ValueError`. | Fixed in `37c2ef4`; CLI catches the shared value-error boundary and has regression coverage. |
| P3 | The plan-required conformance multi-error scenario lacked a regression test. | Fixed in `37c2ef4`; independent row failures are asserted in one report. |

## Verification Evidence

- Team Execution reviewer consensus: DA `9.4`, Security `9.6`, Architecture `9.8`, Testing `9.4`, Clarity `9.6`.
- Security scanner: changed-scope Bandit pass; unchanged broad-scan baseline warning recorded.
- Scenario tester: `260 passed` before the final two review regressions.
- Broad repository suite: `2,806 passed, 1 skipped` with the two redis-channel tests excluded because
  the optional `mcp` package is absent locally.
- New-module coverage at the consensus gate: onboarding `86%`, promotion `98%`, conformance `91%`.
- Registry lint, offline conformance, marketplace sync, release parity, and release diff guard passed.
- Repository-wide Ruff format/check and the canonical full mypy command passed.

## Coverage and Residual Risk

- Suppressed findings: 0.
- Pre-existing findings attributed to this diff: 0.
- Testing gap: no live provider credential or network smoke test; this is an intentional offline gate
  and provider-specific live smoke remains availability-gated follow-up work.
- Local environment gap: unfiltered pytest collection requires the optional `mcp` package for two
  redis-channel tests; the remaining full suite passes when those two tests are excluded.
- Baseline warning: broad Bandit reports unchanged SHA-1 filename-key use in
  `board_progression.py`; changed paths scan cleanly.

## Route

PR-ready. Required GitHub Actions monitoring remains pending until a PR exists.
