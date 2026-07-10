# Code Review — Issue #394 Second-Opinion Triggers

## Verdict

> **CLEAN — not blocked.** No unresolved P0 or P1 findings. The reviewed diff keeps external opinions
> advisory-only, bounds and validates all new egress/output paths, and preserves Claude-owned verdict inputs.

| Field | Value |
|---|---|
| Target | `work/394-second-opinion-triggers` against `origin/main` |
| Reviewed revision | `68432ea` |
| Plan | `docs/plans/2026-07-10-issue-394-second-opinion-triggers-plan.md` |
| Work sessions | `docs/work-sessions/2026-07-10-issue-394-second-opinion-u1.md`; `docs/work-sessions/2026-07-10-issue-394-second-opinion-triggers.md` |
| Scope check | CLEAN |
| Blocked | false |

## Scope Check

Intent: add operator-confirmed, advisory-only external-engine second opinions to `/work`, `/code-review`,
and `/doc-review` without a new transport or gate authority.

Delivered: a typed coordinator and replay guard, bounded work-sidecar trigger, native review-point-out
contracts, trust-boundary/role propagation, release surfaces, and focused/full regression coverage. The
22-file diff is within the approved indivisible one-plugin plan; no unrelated product or transport work was
introduced.

## Plan Completion

| Unit | Status | Evidence |
|---|---|---|
| U1 — shared coordinator and role contract | DONE | `plugins/saga/scripts/second_opinion.py`; `engine_dispatch.py`; dispatch/trust-boundary tests |
| U2 — `/work` failure trigger | DONE | `WorkSecondOpinionState` sidecar and `tests/test_work_second_opinion.py` |
| U3 — `/code-review` point-out | DONE | `skills/code-review/SKILL.md`; `references/findings-schema.md`; contract tests |
| U4 — `/doc-review` point-out | DONE | `skills/doc-review/SKILL.md`; shared contract tests |
| U5 — release closure | DONE | Saga `0.75.22` manifest, marketplace, changelog, journal, and release checks |

COMPLETION: 5/5 DONE.

## Findings

No P0, P1, P2, or P3 findings remain. Fresh-context U1 and U2–U4 reviews previously identified and
verified fixes for secret egress, at-most-once completion, malformed output, stale offers, unavailable
sidecar state, and state-specific projection identity leakage.

## Coverage And Residual Risk

- Focused coordinator/work/review/documentation matrix: 99 passed.
- Full repository suite: 3,080 tests collected and passed, with one existing skip.
- Ruff check/format, mypy over `plugins/`, scoped Bandit, marketplace sync/parity, diff-aware release guard,
  and marketplace validation passed. Marketplace validation retains its existing recommended-field warnings.
- No live provider call was made. The real registry currently has no local-only second-opinion route, so
  sensitive input correctly follows the tested unavailable path; a future local-only provider needs an
  integration test before it can carry sensitive content.

## Route

`/work` is PR-ready. Opening a PR and requesting review remain explicit operator-confirmed GitHub actions.
