# Delegation Contract

`agy` delegation is centered on the `agy.delegation.v1` envelope. The command and agents construct
that envelope; `plugins/agy/scripts/agy_delegate.py` validates it, runs Antigravity, records
evidence, and decides whether a patch may be preserved or imported.

## Envelope Fields

```json
{
  "schema": "agy.delegation.v1",
  "role": "coder",
  "mode": "patch-only",
  "task": "Implement the requested bounded change.",
  "model": "flash",
  "review_lens": null,
  "write_set": ["plugins/agy/scripts/agy_delegate.py"],
  "apply_policy": "preserve-patch",
  "evidence": "summary",
  "verification": {
    "commands": ["PYTHONPATH=. python3 -m pytest -q tests/test_agy_delegate_contract.py"],
    "required": true,
    "run_scope": "clone"
  },
  "timeout_seconds": 900,
  "no_output_seconds": 180,
  "provenance_required": true
}
```

## Modes

- `no-write`: review or analysis only. No live-tree mutation is allowed.
- `patch-only`: preserve a derived patch in the evidence bundle without applying it.
- `auto-if-clean`: apply only when the wrapper proves a clean compatible tree, explicit write-set,
  in-scope changes, orchestrator-supplied verification success, and real Antigravity provenance.

Reviewer delegation defaults to `no-write`. Coder delegation defaults to `patch-only` unless the
caller supplies an explicit write-set and requests `auto-if-clean`.

## Evidence

Every wrapper run writes a local bundle under:

```text
.claude/agy/runs/<run-id>/
```

The projection returned to Claude Code must include the bundle path. If the wrapper cannot write
the bundle, the run fails.

## Prompt Surface Rule

Packaged commands and bridge agents invoke:

```bash
python3 plugins/agy/scripts/agy_delegate.py
```

They do not expose raw `agy`, background execution, direct file editing, or a second execution path.
