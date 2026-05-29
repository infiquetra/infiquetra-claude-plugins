---
name: qa
description: Run risk-based Infiquetra QA gates for code, docs, browser behavior, deployment, and acceptance evidence.
---

# QA

Use this before PR readiness, merge readiness, nonprod deployment evidence, or completion.

## Workflow

1. Identify the risk class: behavior, security, infra, API, deployment, data, docs, config, or
   trivial.
2. Derive checks from repository tooling and the plan's verification section.
3. Run narrow checks first, then broader checks when risk justifies them.
4. Store durable QA notes under `docs/qa/` when the work is non-trivial.
5. Update issue progress with checks run and remaining risk.

Skipping tests requires a clear rationale and is only acceptable for docs, config, or trivial work.
