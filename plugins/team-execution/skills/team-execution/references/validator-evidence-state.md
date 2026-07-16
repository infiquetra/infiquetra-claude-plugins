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

## Dispatch settlement boundary

The selected validator roster is a `site=team-execution` dispatch. Before any validator Agent call,
the coordinator writes the complete manifest through
`plugins/saga/scripts/dispatch_settlement.py manifest`; immediately before each call it appends that
unit's `spawn`. The state file above is the validator's trusted expected deliverable and its digest is
the settlement evidence passed through `settle --evidence-json`; callers never select a terminal
classification directly. A required validator with no state file, an empty state file, or incomplete
required evidence settles `silent-no-op` even if its agent returned success prose. Run `report` before
the gate; a casualty threshold breach halts. `dlq` and `claim-retry` derive bounded at-least-once
retry from the ledger and preserve the original idempotency key.

---

## Completion Summary

Final reports include:

- Selected validators and why.
- Skipped validators and why.
- Gate result for each validator.
- State directory.
- Evidence paths.
- Remaining warnings or blocked signals.

A **required, non-skipped** validator whose evidence record is absent at completion is a
`missing-output` omission, not a silent pass — see `validator-execution-order.md`
(Required-Evidence Absence). A `skipped-by-config` validator's absent evidence is expected.

The `external-second-opinion` validator (Advisory, `validator-registry.md`) is exempt from
Required-Evidence Absence even when opted in: it is never `required` in the gate sense (R13/R15,
it cannot block), so an absent or failed dispatch is expected evidence-state, recorded via its
downgrade note (R24) rather than treated as a `missing-output` omission.
