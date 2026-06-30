---
name: agy-delegate
description: |
  Build a versioned Antigravity teammate delegation envelope and route it through the guarded
  agy wrapper.
when_to_use: |
  Use when the operator calls /agy:delegate or when agy-coder / agy-reviewer need to delegate a
  bounded coding or review task to Antigravity.
---

# Agy Delegate

This skill is the routing contract for the dormant `agy` plugin scaffold. It prepares one
`agy.delegation.v1` envelope and invokes the shared wrapper:

```bash
python3 plugins/agy/scripts/agy_delegate.py
```

The wrapper is the only supported execution path. Do not call raw `agy` directly, do not run a
background path, and do not solve the delegated task locally as a fallback.

## Required Inputs

- `role`: `coder` or `reviewer`.
- `mode`: `no-write`, `patch-only`, or `auto-if-clean`.
- `task`: bounded task text or a task file path.
- `evidence`: `minimal`, `summary`, or `full`.
- `write_set`: explicit paths when mutation may be imported.
- `verification`: orchestrator-supplied commands when checks are required.

## Delegation Flow

1. Read `agy/skills/agy-delegate/references/delegation-contract.md`.
2. Normalize the requested role, mode, lens, write-set, evidence level, timeout, and verification
   policy into the `agy.delegation.v1` contract.
3. Write the task to a temporary task file when needed.
4. Invoke exactly one wrapper run through `plugins/agy/scripts/agy_delegate.py`.
5. Report only the wrapper projection and evidence bundle path.

Each follow-up delegation is a fresh wrapper invocation unless a later wrapper version explicitly
adds stateful conversation support.
