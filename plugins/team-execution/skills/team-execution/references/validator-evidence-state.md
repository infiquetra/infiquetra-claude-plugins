# Validator Evidence and State - team-execution

Validator evidence is stored as JSON state plus referenced artifacts.

---

## State Location

Default repo-local state:

```text
.claude/team-execution/validators/
```

This location is valid only when `.claude/` is ignored by the target repository.

If `.claude/` is not ignored, instruct the user to add an ignore rule or use:

```text
~/.claude/team-execution/state/<repo>/
```

---

## State File Shape

Use one JSON file per validator run:

```json
{
  "validator": "security-scanner",
  "group": "scanner",
  "required": true,
  "selection_reason": "Python API code and dependency lockfile changed",
  "tools": [
    {
      "name": "bandit",
      "command": "uv run bandit -r plugins/",
      "available": true,
      "setup": "uv add --dev bandit"
    }
  ],
  "inputs": ["plugins/example", "pyproject.toml"],
  "evidence": ["logs/security-scanner-2026-05-27.txt"],
  "findings": [],
  "status": "pass",
  "remediation_loop": 0
}
```

---

## Evidence Rules

- Keep evidence paths relative when they are inside the repo.
- Do not store secrets, tokens, production identifiers, or sensitive payloads.
- Prefer summaries plus artifact paths over large pasted logs.
- Include exact command, exit code, and relevant stdout/stderr summary.
- Include timestamps for remote CI and runtime checks.

---

## Completion Summary

Final reports include:

- Selected validators and why.
- Skipped validators and why.
- Gate result for each validator.
- State directory.
- Evidence paths.
- Remaining warnings or blocked signals.
