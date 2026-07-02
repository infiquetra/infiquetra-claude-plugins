---
name: team-execution
description: |
  Two-phase structured plan execution with reviewer consensus, validator gates,
  and guarded nonprod automation for Infiquetra repositories.

  Phase A runs during planning: inspect the requested work, derive workers,
  reviewers, and selected validators, then embed the team plan into the user-approved
  plan artifact.

  Phase B runs after approval: workers complete changes, reviewers reach consensus,
  scanners run, PR/CI/nonprod coordination happens only after gates pass, and
  testers plus monitors validate the deployed nonprod result.
when_to_use: |
  Use this skill proactively when in plan mode and any of these are true:
  - The plan has 3+ steps, touches 3+ files, or involves docs/specs.
  - The plan involves multiple work streams, repositories, contracts, workflows, or deployments.
  - The user asks for agent teams, team-execution, validator gates, nonprod automation,
    review consensus, or automated checks.
  - The user asks for code review as part of a plan.

  Do not use when:
  - The plan already has a ## Team Structure section.
  - The change is trivially simple and the user declines team planning.
  - The user has already declined team planning for this plan in this session.
---

# Team Execution Skill

This skill has two phases:

- **Phase A** runs during planning. You inspect the plan and repository signals, derive
  workers, reviewers, selected validators, and automation eligibility, then embed the
  `## Team Structure` section into the plan before plan approval.
- **Phase B** is the orchestration protocol. It is followed directly by the main agent after
  the user approves the plan.

Validators are selected by task context. Do not spawn the full validator roster by default.

---

# Phase A: Team Planning

## Step A0: Environment Pre-flight

Run pre-flight checks silently. Show only actionable gaps.

### A0a. Handoff Rule

Check for the handoff rule:

```bash
grep -q "Team Execution Auto-Handoff" ~/.claude/CLAUDE.md 2>/dev/null && echo "FOUND" || echo "MISSING"
```

If missing, tell the user to add the rule manually. Do not block plan creation.

---

## Step A1: Plan and Repository Intake

Derive the plan from all available signals:

- User plan text and acceptance criteria.
- Repo type and language/tooling.
- Changed files, staged files, and branch state.
- GitHub workflows under `.github/workflows/`.
- API contracts such as OpenAPI, AsyncAPI, protobuf, GraphQL schemas, or SDK fixtures.
- Documentation, runbooks, architecture docs, and issue specs.
- Test suites and existing quality commands.
- Optional `.team-execution.json`.

The `.team-execution.json` file is optional. Absence means infer from the repo. Supported keys:

```json
{
  "required_validators": ["security-scanner", "smoke-tester"],
  "disabled_validators": ["performance-tester"],
  "nonprod_workflows": ["publish-nonprod.yml"],
  "scenario_hints": ["checkout flow", "webhook replay"],
  "smoke_targets": ["https://example-nonprod.internal/health"]
}
```

If present:

- `required_validators` must be selected unless explicitly impossible.
- `disabled_validators` must not run unless the user overrides.
- `nonprod_workflows` limits deployment/publish workflow candidates.
- `scenario_hints` inform scenario and event-flow testers.
- `smoke_targets` inform smoke tests.

---

## Step A2: Classify Work

Classify the plan:

| Type | Definition |
|------|------------|
| code | Primarily code changes, refactors, bug fixes, or infrastructure |
| docs/specs | Primarily documentation, issue specs, skill docs, or runbooks |
| mixed | Both code and documentation/spec content |

Also classify repository signals:

| Repo Signal | Examples |
|-------------|----------|
| Python service | `pyproject.toml`, `requirements.txt`, `pytest`, FastAPI, Lambda handlers |
| AWS/CDK service | `cdk.json`, `template.yaml`, CloudFormation, SAM, Lambda, IAM |
| API contract repo | OpenAPI, AsyncAPI, protobuf, GraphQL schema |
| SDK repo | `sdk`, generated clients, package publishing workflows |
| Frontend repo | React, Next.js, Vite, Playwright, browser smoke targets |
| Home-lab/observability | Ansible, Prometheus, Grafana, Docker Compose, local infra |

---

## Step A3: Reviewer Selection

Read:

- `team-execution/skills/team-execution/references/reviewer-registry.md`
- `team-execution/skills/team-execution/references/review-criteria.md`
- `team-execution/skills/team-execution/references/consensus-protocol.md`

Base reviewers always included:

- `devils-advocate-reviewer`
- `security-reviewer`
- `architecture-reviewer`

Optional reviewers are suggested from plan and repo signals.

Reviewer non-consensus blocks validators unless the user explicitly overrides.

---

## Step A4: Validator Selection

Read:

- `team-execution/skills/team-execution/references/validator-registry.md`
- `team-execution/skills/team-execution/references/validator-criteria.md`
- `team-execution/skills/team-execution/references/validator-execution-order.md`
- `team-execution/skills/team-execution/references/validator-evidence-state.md`
- `team-execution/skills/team-execution/references/validator-spawn-quirks.md`

Select validators by context:

| Group | Agents |
|-------|--------|
| Scanners | `security-scanner`, `iac-cost-scanner`, `api-compat-scanner`, `dependency-scanner` |
| Testers | `smoke-tester`, `scenario-tester`, `api-contract-tester`, `sdk-regression-tester`, `event-flow-tester`, `ui-regression-tester`, `performance-tester`, `concurrency-tester` |
| Monitors | `github-actions-monitor`, `runtime-monitor` |
| Operational | `deploy-watcher` |

Tool candidates are OSS/free where available:

- Semgrep
- Bandit
- pip-audit
- Trivy
- Gitleaks
- detect-secrets
- Checkov
- oasdiff
- Schemathesis
- Playwright
- k6

If a selected validator requires a missing tool, fail loud with setup guidance. Do not silently
skip required validators.

---

## Step A5: State and Evidence Plan

Validator run state is JSON under:

```text
.claude/team-execution/validators/
```

Before planning validator state, check whether `.claude/` is ignored in the target repo. If it is
not ignored, instruct the user to add an ignore rule or use the user-local fallback:

```text
~/.claude/team-execution/state/<repo>/
```

Each validator state record includes:

- Validator name and group.
- Selection reason.
- Required tool commands and availability.
- Inputs inspected.
- Evidence paths.
- Findings and severity.
- Gate result: pass, warn, hard-fail, skipped-by-config, or blocked.
- Remediation loop count.

---

## Step A6: Automation Eligibility

Automation is allowed only when all conditions are true:

- Remote matches `github.com/infiquetra/*`.
- The plan follows the repo default branch model.
- Reviewers, selected scanners, CI, and required testers pass.
- Workflow is explicitly nonprod or publish-nonprod.
- The action does not touch production, staging, force-push, branch deletion, or credentials.

Any ambiguous or missing signal blocks automation.

---

## Step A7: Embed Team Structure

Append a plan section like this:

```markdown
## Team Structure

### Workers
| Agent | Units | Tier | Mode | Depends-on | Engine | Intent |
|-------|-------|------|------|------------|--------|--------|
| `worker-<plugin>` | U1, U2 | opus/high | bypassPermissions | — | — | — |
| `worker-<engine>` | U3 | sonnet/medium | bypassPermissions | `worker-<plugin>` | `<engine-key>` | offload |

`Engine` and `Intent` are `—` for Claude workers. An engine-owned worker (KTD3, U12) renders
`Engine` as `<engine-key>` for an explicit selector or `cap:<capability-key>` for a capability
route, and `Intent` as `offload` or `second-opinion` — see
`team-execution/skills/team-execution/references/external-engine-workers.md`.

### Reviewers
| Agent | Role | Required | Selection Reason |
|-------|------|----------|------------------|
| `devils-advocate-reviewer` | Devil's Advocate Reviewer | yes | Base reviewer |
| `security-reviewer` | Security Reviewer | yes | Base reviewer |
| `architecture-reviewer` | Architecture Reviewer | yes | Base reviewer |

### Validators
| Agent | Group | Required | Selection Reason | Blocking |
|-------|-------|----------|------------------|----------|
| `security-scanner` | Scanner | yes/no | [Why selected] | hard-fail blocks automation |

### Execution Gates
- Reviewer consensus threshold: >= 9.0/10 from every reviewer.
- Reviewer non-consensus blocks validators unless the user explicitly overrides.
- Scanners run before PR/CI/merge/nonprod coordination.
- Tester hard-fail blocks completion.
- Maximum 3 remediation loops before escalation.

### Reference Files
- `team-execution/skills/team-execution/references/reviewer-registry.md`
- `team-execution/skills/team-execution/references/review-criteria.md`
- `team-execution/skills/team-execution/references/consensus-protocol.md`
- `team-execution/skills/team-execution/references/validator-registry.md`
- `team-execution/skills/team-execution/references/validator-criteria.md`
- `team-execution/skills/team-execution/references/validator-execution-order.md`
- `team-execution/skills/team-execution/references/validator-evidence-state.md`
- `team-execution/skills/team-execution/references/validator-spawn-quirks.md`
- `team-execution/skills/team-execution/references/worker-manifest.md`
- `team-execution/skills/team-execution/references/external-engine-workers.md`
```

Then submit the plan for approval. Do not start implementation during Phase A.

---

# Phase B: Orchestration Protocol

Phase B starts only after plan approval.

## Step B0: Parse the Approved Team Plan

Read the approved `## Team Structure`, selected validators, reference files, automation
eligibility, and state location.

If the plan has no `## Team Structure`, stop and tell the user to run `/team-execute`.

---

## Step B0a: Validator-State Preflight

Before any worker runs (pre-execution, so the safety check survives without `/team-setup`), re-verify
the validator-state location is safe — the same `.claude/`-ignored check from Step A5, now enforced at
execution time:

```text
.claude/team-execution/validators/   (valid only when .claude/ is git-ignored in the target repo)
```

If `.claude/` is NOT ignored in the target repo, do not write run-state there — fail loud and either
have the user add an ignore rule or fall back to `~/.claude/team-execution/state/<repo>/`. This guards
against committing validator run-state into the repo and runs in BOTH Phase A planning (Step A5) and
here in Phase B preflight.

---

## Step B1: Workers Complete Changes

Workers execute approved tasks. Coordinate dependencies, keep work scoped to the plan, and run execution waves using the resident-worker residency protocol:

- **Wave Scheduling & Reactive Unblocking (R8, R10):** A resident worker with unmet segment-level `Depends-on` must not be spawned (avoiding premature creation costs) until its upstream segments complete. Segments with no dependencies can start in parallel. This within-run segment frontier is strictly subordinate to saga's coordinator-level `ready_frontier`.
- **Persistent Resident Workers (R3):** Spawn exactly one named, persistent teammate per resident worker (segment) using an Agent with a specific `name` (the resident id) and `run_in_background` enabled, rather than spawning anonymous workers per unit.
- **Worker Reuse (R3):** Reuse the resident worker across all units in its segment via `SendMessage`. Never re-spawn the worker per unit; reusing the persistent teammate preserves its warm context/cache across all units it owns.
- **Cross-Segment Summary-Handoff (R4):** When a dependent segment requires the result of a prior segment, seed the dependent segment's fresh worker with a short summary of the upstream segment's output via `SendMessage` instead of forwarding the upstream worker's entire context.
- **Context Shedding (R11):** Shed a resident worker at its segment boundary, or when a block of time is expected to exceed the prompt cache TTL horizon (~5 minutes). Teammate reuse is for temporally-tight loops, not indefinite warmth.
- **Chaperone Dispatch (KTD1, U12):** A resident worker whose `### Workers` row carries a non-`—`
  `Engine` cell is a chaperone: it resolves, dispatches through the existing containment wrappers,
  verifies the returned evidence, applies the patch as sole-committer, runs its unit's tests, and
  writes the worker-exit manifest — the engine itself never joins wave scheduling or touches the
  working tree. Full protocol in
  `team-execution/skills/team-execution/references/external-engine-workers.md`.

Each worker writes a provenance manifest at segment/unit exit — see
`team-execution/skills/team-execution/references/worker-manifest.md` (attribution + disposition +,
for contract-bearing units, output_completeness; evidence-only, grants no privilege). A chaperone
worker's manifest additionally carries `kind=external-engine` attribution and the honest
disposition (`ran-as-requested` / `fell-back-to-claude` / `substituted-engine`) per
`external-engine-workers.md`.

When all worker tasks are complete, capture changed files and a git diff summary for reviewers.

---

## Step B2: Reviewers Reach Consensus

Run reviewers according to `consensus-protocol.md`.

- All confirmed reviewers score the implementation.
- Consensus requires overall score >= 9.0/10 and no dimension < 7.0.
- Security/auth/secrets dimension < 5.0 is a blocking stop.
- Reviewer non-consensus blocks validators unless the user explicitly overrides.
- Maximum 3 review cycles.

---

## Step B3: Scanners Run

Run selected scanner validators only after reviewer consensus or explicit user override.

Scanners inspect local artifacts, code, dependency manifests, contracts, and infrastructure.
Hard-fail scanner findings block auto-merge, nonprod deploy, and completion.

Missing required scanner tools fail loud with setup guidance. Optional scanner tools may be
reported as skipped only if the validator is not required.

---

## Step B4: PR, CI, Merge, and Nonprod Coordination

Coordinate automation only if gates pass and automation is eligible:

1. Confirm remote matches `github.com/infiquetra/*`.
2. Confirm default branch model.
3. Confirm no production, staging, force-push, branch deletion, or credential-changing action.
4. Run or monitor allowed `nonprod` or `publish-nonprod` workflows only.

If any signal is ambiguous, stop automation and report what is missing.

---

## Step B5: Testers Validate Deployed Nonprod Result

Run selected tester validators after a deploy or publish target is available.

Testers validate smoke targets, scenarios, contracts, SDK compatibility, event flows, UI
regressions, performance thresholds, and concurrency behavior as applicable.

Hard-fail tester findings block completion. Run a maximum 3 remediation loops before escalating
to the user.

---

## Step B6: Monitors Verify Runtime Signals

Run monitor validators:

- `github-actions-monitor` checks workflow status and relevant logs.
- `runtime-monitor` checks repository-appropriate observability: CloudWatch for AWS repos,
  Prometheus/Grafana-style checks for home-lab/local-infra repos, and app health endpoints
  where configured.

If monitors cannot reach an expected signal, mark the gate blocked or warn based on whether
the signal was required.

---

## Step B7: Completion

Report:

- Worker changes.
- Reviewer scores.
- Scanner, tester, and monitor gate results.
- Validator state location.
- Evidence paths.
- Automation actions taken or blocked.
- Residual risks.

Do not claim completion while required validators are hard-failing or blocked unless the user
explicitly accepts the residual risk.

A required, non-skipped validator whose evidence record was **never written** is a `missing-output`
omission, not a silent pass — treat its absent evidence at process exit as a completion block,
exactly like a hard-fail. A `skipped-by-config` validator (recorded with a `selection_reason`) is
not a trip. See `references/validator-execution-order.md` (Required-Evidence Absence).

---

# Quick Reference: File Paths

```text
team-execution/
├── .claude-plugin/plugin.json
├── skills/
│   ├── appsec-audit/SKILL.md
│   └── team-execution/
│       ├── SKILL.md
│       └── references/
│           ├── consensus-protocol.md
│           ├── review-criteria.md
│           ├── reviewer-registry.md
│           ├── validator-criteria.md
│           ├── validator-evidence-state.md
│           ├── validator-execution-order.md
│           ├── validator-registry.md
│           ├── validator-spawn-quirks.md
│           ├── worker-manifest.md
│           └── external-engine-workers.md
├── agents/
│   ├── devils-advocate-reviewer.md
│   ├── security-reviewer.md
│   ├── architecture-reviewer.md
│   └── [reviewer and validator agents]
└── commands/
    ├── team-execute.md
```
