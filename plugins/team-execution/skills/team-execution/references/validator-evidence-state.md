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
the coordinator runs the packaged adapter's `preflight`, then writes the complete manifest through
`dispatch_settlement_adapter.py manifest`; immediately before each call it appends that unit's `spawn`
through `dispatch_settlement_adapter.py saga -- ... spawn`. The state file above is the validator's
expected source evidence, but it is not itself a caller-trusted receipt. The coordinator validates it,
including that every `evidence[]` path exists within the repo, and materializes `dispatch.artifact.v1`
before settlement. Callers never select a terminal classification, digest, trusted flag, or outputs.

```bash
TEAM_SETTLEMENT="${CLAUDE_PLUGIN_ROOT:-plugins/team-execution}/skills/team-execution/scripts/dispatch_settlement_adapter.py"
python3 "$TEAM_SETTLEMENT" preflight
python3 "$TEAM_SETTLEMENT" manifest --kind validator --repo-root "$REPO_ROOT" --subplot-id "$SAGA_ID" \
  --dispatch-id "$DISPATCH_ID" --roster-json "$VALIDATOR_ROSTER_JSON" --at "$NOW"
python3 "$TEAM_SETTLEMENT" saga -- --repo-root "$REPO_ROOT" --subplot-id "$SAGA_ID" spawn \
  --dispatch-id "$DISPATCH_ID" --unit-id "$VALIDATOR" --attempt "$ATTEMPT" \
  --idempotency-key "team-execution:validator:$VALIDATOR" --at "$NOW"
python3 "$TEAM_SETTLEMENT" settle --kind validator --repo-root "$REPO_ROOT" --subplot-id "$SAGA_ID" \
  --dispatch-id "$DISPATCH_ID" --unit-id "$VALIDATOR" --attempt "$ATTEMPT" --at "$NOW" \
  --source-json ".claude/team-execution/validators/$VALIDATOR.json" \
  --receipt-path ".claude/team-execution/settlement/$DISPATCH_ID-$VALIDATOR.json"
python3 "$TEAM_SETTLEMENT" saga -- --repo-root "$REPO_ROOT" --subplot-id "$SAGA_ID" report \
  --dispatch-id "$DISPATCH_ID"
```

A required validator with no state file, an empty state file, incomplete required evidence, a missing
referenced file, success prose, or an artifact pointer settles `silent-no-op`. Run the canonical Saga
`report` before the gate; a casualty threshold breach halts. `dlq` and `claim-retry` derive bounded
at-least-once retry from the ledger and preserve the original idempotency key.

The command above stores state inside the repository. For state under
`~/.claude/team-execution/state/<repo>`, add that directory as `--evidence-root` and make
`--source-json` and `--receipt-path` relative to it. Validator `evidence[]` paths still resolve under
`--repo-root`; they cannot escape into the coordinator state directory.

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
