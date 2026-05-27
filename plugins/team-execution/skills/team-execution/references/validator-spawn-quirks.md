# Validator Spawn Quirks - team-execution

Validator agents are specialized evidence collectors. Spawn only selected validators.

---

## Context Package

Each validator receives:

- Plan summary and intended outcome.
- Relevant changed files or diff summary.
- Selected command/tool candidates.
- Required vs optional status.
- State file path.
- Blocking rules.
- Safety constraints.

Do not ask validators to rediscover the whole repo when Phase A already selected them for a
specific reason.

---

## Missing Tools

If a selected required validator needs a missing tool:

1. Mark status `blocked`.
2. State the missing command.
3. Provide setup guidance.
4. Do not silently substitute a weaker check unless the user explicitly approves.

Optional validators may report `warn` or `skipped-by-config` when their tools are absent.

---

## Avoid Duplicate Work

- Scanners run before CI/nonprod coordination.
- Testers run after a target exists.
- Monitors inspect external signals after CI or deployment starts.
- Re-run only validators affected by remediation.

---

## Automation Safety

Before any validator coordinates an external action, confirm:

- Remote is `github.com/infiquetra/*`.
- Action is nonprod or publish-nonprod.
- Reviewer, scanner, CI, and required tester gates have passed.
- No production, staging, force-push, branch deletion, or credential change is involved.

Ambiguity means blocked.
