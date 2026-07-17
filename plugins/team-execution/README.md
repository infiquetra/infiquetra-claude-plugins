# team-execution

Two-phase plan execution with reviewer consensus, validator gates, and guarded nonprod
automation for Infiquetra repositories.

**Phase A** runs during planning. It reads the requested work, inspects repository signals,
classifies the repo and risk profile, derives workers, reviewers, and selected validators, and
embeds a `## Team Structure` plus validator plan into the approved plan.

**Phase B** runs after plan approval. Workers complete the change, reviewers reach consensus,
scanners validate the local result, CI and optional nonprod automation are coordinated, and
testers/monitors validate the deployed nonprod result. The coordinator records every expected
reviewer and validator, persists a spawn immediately before its host call, and derives settlement
from returned structured evidence before opening the next gate. Casualties and open positions halt
progression and remain visible through the derived dead-letter view until explicitly retried.

Validators are available as a roster. They are selected by task context; they are not spawned
all at once.

---

## Quick Start

```
/team-execute
```

Or provide an existing plan:

```
/team-execute [paste plan here or provide file path]
```

---

## What You Get

### Base Reviewers

Always included:

| Reviewer | Focus |
|----------|-------|
| `devils-advocate-reviewer` | Assumptions, edge cases, failure modes, scope creep |
| `security-reviewer` | OWASP Top 10, secrets, auth/authZ, PII, supply chain |
| `architecture-reviewer` | Design patterns, separation of concerns, convention adherence |

Optional reviewers are still available for infrastructure, API, testing, code quality,
privacy, clarity, and AI-usefulness review.

### Validators

Validators run after worker completion and reviewer consensus. They are grouped by the signal
they provide:

| Group | Agents |
|-------|--------|
| Scanners | `security-scanner`, `iac-cost-scanner`, `api-compat-scanner`, `dependency-scanner` |
| Testers | `smoke-tester`, `scenario-tester`, `api-contract-tester`, `sdk-regression-tester`, `event-flow-tester`, `ui-regression-tester`, `performance-tester`, `concurrency-tester` |
| Monitors | `github-actions-monitor`, `runtime-monitor` |
| Operational | `deploy-watcher` |

Selected validators use OSS/free tools when applicable: Semgrep, Bandit, pip-audit, Trivy,
Gitleaks, detect-secrets, Checkov, oasdiff, Schemathesis, Playwright, and k6. Missing selected
tools fail loud with setup guidance.

---

## Optional Configuration

Target repositories may define `.team-execution.json`. Absence is valid; the skill infers from
changed files, workflows, contracts, docs, tests, and repository layout.

```json
{
  "required_validators": ["security-scanner", "smoke-tester"],
  "disabled_validators": ["performance-tester"],
  "nonprod_workflows": ["publish-nonprod.yml"],
  "scenario_hints": ["checkout flow", "webhook replay"],
  "smoke_targets": ["https://example-nonprod.internal/health"]
}
```

The config may require or disable validators, name nonprod workflows, and provide scenario or
smoke-test hints. Required validators that cannot run block automation and completion until the
missing setup is resolved or the user explicitly changes the plan.

---

## Phase B Order

1. Workers complete approved implementation tasks.
2. Reviewers run the consensus protocol.
3. Reviewer non-consensus blocks validators unless the user explicitly overrides.
4. Scanners run against the local result.
5. PR, CI, merge, and nonprod deployment are coordinated only after gates pass.
6. Testers validate the deployed nonprod result.
7. Monitors verify GitHub Actions and runtime signals.
8. Completion reports evidence, state paths, residual risks, and blocked automation.

Hard-fail scanner or tester findings block auto-merge, nonprod deployment, and completion.
The orchestrator may run a maximum of 3 remediation loops before escalating to the user.

---

## Automation Guardrails

Automation is allowed only when all of these are true:

- Repository remote matches `github.com/infiquetra/*`.
- The work follows the repo default branch model.
- Reviewer, scanner, CI, and required tester gates passed.
- The workflow is explicitly nonprod or publish-nonprod.
- No production, staging, force-push, branch deletion, or credential-changing action is involved.

Any ambiguous signal blocks automation.

---

## Validator State

Validator run state is JSON under ignored repo-local:

```
.claude/team-execution/validators/
```

If `.claude/` is not ignored in the target repository, the skill instructs the user to add an
ignore rule or use a user-local fallback:

```
~/.claude/team-execution/state/<repo>/
```

State files record selected validators, commands, tool availability, evidence paths, findings,
remediation loops, and final gate status.

---

## Reference Files

- `team-execution/skills/team-execution/references/reviewer-registry.md`
- `team-execution/skills/team-execution/references/review-criteria.md`
- `team-execution/skills/team-execution/references/consensus-protocol.md`
- `team-execution/skills/team-execution/references/validator-registry.md`
- `team-execution/skills/team-execution/references/validator-criteria.md`
- `team-execution/skills/team-execution/references/validator-execution-order.md`
- `team-execution/skills/team-execution/references/validator-evidence-state.md`
- `team-execution/skills/team-execution/references/validator-spawn-quirks.md`
- `team-execution/skills/team-execution/references/external-engine-workers.md`
- `team-execution/skills/team-execution/references/lease-protocol.md`
- `team-execution/skills/team-execution/references/artifact-pointers.md`
- `team-execution/skills/team-execution/references/andon-cord.md`

---

## Plugin Structure

```
team-execution/
├── .claude-plugin/plugin.json
├── skills/
│   ├── appsec-audit/
│   │   └── SKILL.md
│   └── team-execution/
│       ├── SKILL.md
│       ├── scripts/
│       │   └── dispatch_settlement_adapter.py
│       └── references/
│           ├── consensus-protocol.md
│           ├── review-criteria.md
│           ├── reviewer-registry.md
│           ├── validator-criteria.md
│           ├── validator-evidence-state.md
│           ├── validator-execution-order.md
│           ├── validator-registry.md
│           ├── validator-spawn-quirks.md
│           ├── external-engine-workers.md
│           ├── lease-protocol.md
│           └── artifact-pointers.md
├── agents/
│   ├── devils-advocate-reviewer.md
│   ├── security-reviewer.md
│   ├── architecture-reviewer.md
│   ├── security-scanner.md
│   ├── smoke-tester.md
│   ├── github-actions-monitor.md
│   └── ... validator and optional reviewer agents
├── commands/
│   └── team-execute.md
├── README.md
└── CHANGELOG.md
```
