# Validator Registry - team-execution

Validators provide post-review evidence. Select them by context; do not spawn every
validator for every plan.

---

## Selection Inputs

Phase A considers:

- Repo type and language/tooling.
- Changed files and staged files.
- GitHub workflows.
- Contracts and schemas.
- Docs, runbooks, and scenario hints.
- Existing tests and quality commands.
- Optional `.team-execution.json`.

Supported `.team-execution.json` keys:

- `required_validators`
- `disabled_validators`
- `nonprod_workflows`
- `scenario_hints`
- `smoke_targets`

Required validators block completion if they cannot run. Disabled validators do not run unless
the user explicitly overrides.

---

## Scanners

| Agent | Select When | OSS/Free Tool Candidates |
|-------|-------------|--------------------------|
| `security-scanner` | App code, secrets, auth, input handling, or broad code changes | Semgrep, Bandit, Gitleaks, detect-secrets |
| `iac-cost-scanner` | CDK, CloudFormation, Terraform, Kubernetes, IAM, or cloud cost changes | Checkov, Trivy |
| `api-compat-scanner` | OpenAPI/AsyncAPI/protobuf/GraphQL contract or endpoint changes | oasdiff, Schemathesis |
| `dependency-scanner` | Dependency manifest, lockfile, base image, or package publishing changes | pip-audit, Trivy |

Scanner hard-fail findings block auto-merge, nonprod deploy, and completion.

---

## Testers

| Agent | Select When | OSS/Free Tool Candidates |
|-------|-------------|--------------------------|
| `smoke-tester` | Nonprod target, service entrypoint, CLI, health endpoint, or smoke target exists | curl/fetch, pytest, repo scripts |
| `scenario-tester` | `scenario_hints` exist or the plan changes user-visible flows | pytest, repo scripts |
| `api-contract-tester` | API contracts, schemas, or generated clients change | Schemathesis, oasdiff |
| `sdk-regression-tester` | SDK package, generated client, or compatibility fixture changes | repo tests, package manager scripts |
| `event-flow-tester` | Events, queues, webhooks, streams, or async workflows change | repo scripts, pytest |
| `ui-regression-tester` | Frontend screens, routing, components, or browser workflows change | Playwright |
| `performance-tester` | Latency, throughput, load, query, or runtime cost claims change | k6, repo benchmarks |
| `concurrency-tester` | Locks, queues, idempotency, retries, or parallel workers change | pytest, repo stress scripts |

Tester hard-fail findings block completion.

---

## Monitors

| Agent | Select When | Evidence |
|-------|-------------|----------|
| `github-actions-monitor` | Any PR, CI, merge, or workflow action is part of the plan | GitHub Actions run status and relevant logs |
| `runtime-monitor` | Nonprod deploy/publish or runtime health validation is part of the plan | CloudWatch, Prometheus/Grafana-style checks, app health endpoints |

---

## Operational

| Agent | Select When | Evidence |
|-------|-------------|----------|
| `deploy-watcher` | A nonprod or publish-nonprod workflow is eligible and selected | Workflow run, artifact, environment URL, rollback notes |

---

## Automation Eligibility

Automation may proceed only for `github.com/infiquetra/*`, only from the repo default branch
model, only after gates pass, and only for nonprod or publish-nonprod workflows.

Never automate production, staging, force-push, branch deletion, or credential changes.
