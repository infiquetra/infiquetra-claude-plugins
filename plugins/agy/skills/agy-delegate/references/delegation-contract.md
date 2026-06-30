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

Field rules:

- `schema` must be `agy.delegation.v1`.
- `role` must be `coder` or `reviewer`.
- `mode` must be `no-write`, `patch-only`, or `auto-if-clean`.
- `task` and `model` must be non-empty strings.
- `review_lens` may be `null`, `adversarial`, `quality`, `scope-gap`, or `security-ops`.
- `write_set` must contain repo-relative paths only. Absolute paths and `..` are invalid.
- `apply_policy` must be `preserve-patch` or `apply-if-clean`.
- `evidence` must be `minimal`, `summary`, or `full`.
- `verification.commands` must be a list of non-empty strings supplied by the orchestrator or
  operator, not by the delegate. When `verification.required` is `true`, at least one command is
  required. `verification.run_scope` must be `clone`, `live`, or `none`.
- `timeout_seconds` and `no_output_seconds` must be positive integers, and `no_output_seconds`
  must not exceed `timeout_seconds`.
- `provenance_required` must be a boolean.

## Modes

- `no-write`: review or analysis only. No live-tree mutation is allowed.
- `patch-only`: preserve a derived patch in the evidence bundle without applying it.
- `auto-if-clean`: apply only when the wrapper proves a clean compatible tree, explicit write-set,
  in-scope changes, orchestrator-supplied verification success, and real Antigravity provenance.

Reviewer delegation defaults to `no-write`. Coder delegation defaults to `patch-only` unless the
caller supplies an explicit write-set and requests `auto-if-clean`.

`auto-if-clean` with an empty `write_set` is rejected before any subprocess launch or bundle
creation.

## Evidence

Every wrapper run writes a local bundle under:

```text
.claude/agy/runs/<run-id>/
```

The projection returned to Claude Code must include the bundle path. If the wrapper cannot write
the bundle, the run fails.

Validation-only wrapper runs write this minimum bundle:

```text
.claude/agy/runs/<run-id>/
  envelope.json
  prompt.txt
  command.json
  run-lease.json
  result.json
  projection.md
```

Launched wrapper runs execute `agy` inside a disposable clone and add write-policy evidence:

```text
.claude/agy/runs/<run-id>/
  worktree/
  stdout.log
  stderr.log
  agy.log
  diff.patch
  changed-paths.json
  checks.json
  git-proof.json
```

`projection.md` is emitted to stdout. `diff.patch`, `changed-paths.json`, and `git-proof.json`
are derived from the disposable clone relative to the recorded base SHA. The clone remotes are
removed before `agy` runs.

## Status Enum

Wrapper result statuses are snake_case:

- `success`
- `patch_ready`
- `applied`
- `plan_gap`
- `test_conflict`
- `path_missing`
- `timeout`
- `no_output`
- `fallback_suspected`
- `out_of_scope_mutation`
- `checks_failed`
- `shutdown_incomplete`
- `bundle_failed`
- `error`

## Prompt Surface Rule

Packaged commands and bridge agents invoke:

```bash
python3 plugins/agy/scripts/agy_delegate.py
```

They do not expose raw `agy`, background execution, direct file editing, or a second execution path.
