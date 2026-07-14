# Code Review — Issue #557 (Mission Control assign-to-Mimir)

One-line verdict: **PASS** — one correctness finding found during merge-base review and fixed in-branch; no open findings.

## Review result

- Target: `feat/557-assign-mimir`, diff `1457aed..0f67735`
- Reviewed SHA: `0f67735`
- Lenses: correctness, authorization/security, idempotency, failure handling, tests, release parity
- Linked: issue #557; plan `docs/plans/2026-07-14-ws1-assign-mimir-claude-plan.md`

## Finding

| # | Severity | Finding | Resolution |
|---|---|---|---|
| 1 | P2 | The first implementation preferred GitHub's `role_name` over standardized `permission`. A custom repository role can carry effective `write` permission under a nonstandard role name, causing a valid operator to be rejected. | Fixed in `0f67735`: prefer effective `permission`, fall back to `role_name`, and cover the custom-role case with a regression test. |

## Evidence

- Exact live coverage is fetched through the existing authenticated `gh api` rail; schema, policy version, fail-closed default, exact repository uniqueness, active state, `issues` event, and route are checked before mutation.
- Open-issue identity, current principal, effective triage-or-higher authority, and the repository-owned trigger label are all checked before the single label POST.
- Already-triggered issues perform no mutation or comment. A new trigger is accepted only after issue-label readback; Objective values come only from live project fields.
- Negative tests cover uncovered, inactive, malformed, closed, unauthenticated, unauthorized, missing-label, mutation-failure, and failed-readback paths.
- Focused suite: 18 passed. Mission Control suite before the review fix: 271 passed. Final repository suite after the fix: 3,988 passed and 1 skipped; Ruff, format, mypy, strict plugin/marketplace validation, release parity, and the high-severity Bandit gate passed.

Residual risk: the Objective query reads at most 100 project memberships and 100 field values per membership. GitHub issues in this environment have far fewer, and the command fails rather than inventing Objective data if the query itself cannot be read. No additional dependency or credential path was introduced.
