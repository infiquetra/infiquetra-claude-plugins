# Validator Criteria - team-execution

Validators report evidence and gate status. They do not replace reviewer judgment.

---

## Gate Status

| Status | Meaning | Effect |
|--------|---------|--------|
| pass | Required checks ran and found no blocking issue | Gate passes |
| warn | Non-blocking issue or optional missing signal | Report and continue |
| hard-fail | Blocking scanner/tester finding | Blocks auto-merge, nonprod deploy, and completion |
| skipped-by-config | Disabled by `.team-execution.json` or explicit user choice | Report as skipped |
| blocked | Required tool, target, credential, or signal is missing | Blocks required gate until resolved |

---

## Scanners

Scanners must:

- State selected tools and exact commands.
- Fail loud when a selected required tool is missing.
- Include setup guidance for missing tools.
- Report findings with severity, file/path, evidence, and remediation.
- Distinguish hard-fail from warn.

Recommended hard-fail examples:

- Secret-like value in tracked files.
- High-confidence SSRF, command injection, SQL/NoSQL injection, or auth bypass risk.
- Critical dependency or container vulnerability in a reachable path.
- IaC rule that opens public access or grants broad IAM without justification.
- Breaking API contract change without explicit versioning or migration.

---

## Testers

Testers must:

- Define target, command, and expected outcome before running.
- Capture logs, exit codes, URLs, screenshots, or artifacts when applicable.
- Fail loud when required targets or tools are missing.
- Treat hard assertion failures as blocking.
- Treat unreachable optional targets as warn unless marked required.

---

## Monitors

Monitors must:

- Identify the system being observed.
- Record the time window inspected.
- Capture current status and relevant failures.
- Distinguish "healthy", "degraded", "missing signal", and "not applicable".

---

## Operational Agents

Operational agents may coordinate only allowed nonprod automation. They must not perform
production, staging, force-push, branch deletion, or credential-changing actions.

Any ambiguous workflow name, environment, remote, branch model, or credential action is a
blocked gate.
