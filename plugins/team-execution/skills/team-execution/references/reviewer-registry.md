# Reviewer Registry — team-execution

This file defines the base reviewers (always spawned) and optional reviewers (triggered by keyword
detection in the plan). Read this file during Phase A (Step A2) to determine which optional
reviewers to suggest.

---

## Base Reviewers (Always Spawned)

These three reviewers are spawned for every plan execution regardless of plan type or content.

| Agent | Color | Focus |
|-------|-------|-------|
| `devils-advocate-reviewer` | red | Assumptions, edge cases, failure modes, scope creep risk |
| `security-reviewer` | orange | OWASP Top 10, secrets, auth/authZ, PII, supply chain |
| `architecture-reviewer` | purple | Design patterns, separation of concerns, convention adherence |

---

## Optional Reviewers — Code/Implementation Plans

These reviewers are suggested when the listed keywords appear in the plan content.

| Keywords in Plan | Suggested Reviewer | Agent File |
|---|---|---|
| CDK, CloudFormation, Lambda, DynamoDB, S3, IAM, KMS, multi-region, infrastructure, AWS | `infra-reviewer` | `agents/infra-reviewer.md` |
| API, endpoint, REST, OpenAPI, versioning, deprecation, SDK, contract, breaking change | `api-reviewer` | `agents/api-reviewer.md` |
| pytest, test, coverage, integration test, mock, fixture, unit test, e2e, test suite | `testing-reviewer` | `agents/testing-reviewer.md` |
| refactor, lint, patterns, DRY, SOLID, complexity, code smell, technical debt, abstraction | `code-quality-reviewer` | `agents/code-quality-reviewer.md` |
| PII, GDPR, data classification, consent, retention, anonymize, personal data, privacy | `privacy-reviewer` | `agents/privacy-reviewer.md` |

---

## Optional Reviewers — Docs/Spec Plans

These reviewers are suggested when the plan involves documentation, specifications, or AI-consumed artifacts.

| Keywords in Plan | Suggested Reviewer | Agent File |
|---|---|---|
| docs, README, specification, guide, runbook, architecture doc, documentation | `clarity-reviewer` | `agents/clarity-reviewer.md` |
| issue template, GitHub issue, task description, acceptance criteria, AI prompt, SKILL.md, CLAUDE.md, spec | `ai-usefulness-reviewer` | `agents/ai-usefulness-reviewer.md` |

---

## Plan Type Classification

Classify the plan into one of three types before reviewer selection:

| Plan Type | Definition | Reviewer Sets |
|-----------|------------|---------------|
| **code** | Primarily code changes, implementations, refactors | Base + code optional reviewers |
| **docs/specs** | Primarily documentation, specs, issue templates, SKILL.md files | Base + doc optional reviewers |
| **mixed** | Both code changes AND documentation/spec content | Base + both code and doc optional reviewers |

**Important**: Docs-only plans do NOT qualify for the triage escape hatch. Documentation is specs
for code and deserves full review.

---

## Triage Escape Hatch — Qualifying Criteria

A plan qualifies for the triage escape hatch ONLY if ALL of the following are true:

1. Single config file change (e.g., updating a version number, adding an env var)
2. No security surface affected (no auth, secrets, permissions, PII)
3. Fewer than 3 files modified
4. No specification or documentation content

If ALL four criteria are met, offer:

- **A)** Skip review team (recommended for trivial changes only)
- **B)** Full review team anyway
- **C)** Devil's Advocate only (lightweight check)

If ANY criterion is not met — especially docs-only plans — proceed with the full review team.

---

## Custom Reviewers

Users can always add custom reviewers not in this list. When confirming the team lineup, prompt:

> "Would you like to add any custom reviewers not in the standard registry? If so, describe
> their focus area and I'll configure them."

Custom reviewers use the same frontmatter format as standard reviewers and are spawned in the
same review cycle.

---

## Adding a New Reviewer

To register a new optional reviewer:

1. Create the agent file at `agents/<name>-reviewer.md`
2. Add a row to this registry with keywords and agent file path
3. Update `CHANGELOG.md`
4. The new reviewer will be auto-suggested on plans matching the keywords
