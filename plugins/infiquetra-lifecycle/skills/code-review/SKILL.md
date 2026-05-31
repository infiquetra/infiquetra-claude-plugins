---
name: code-review
description: Structured Infiquetra code review for diffs, PRs, and pre-shipping gates.
---

# Code Review

Use this for review requests or before PR and shipping gates.

## Review Order

1. Correctness and behavioral regressions.
2. Security, secrets, trust boundaries, and authorization.
3. Operational risk, migrations, deployments, and rollback.
4. Missing tests or weak verification.
5. Maintainability, readability, and local conventions.

Findings lead. Include file and line references. If no issues are found, say so plainly and call
out residual test or operational risk. Offer `team-execution` when the review needs multiple
reviewer lenses or validators.
