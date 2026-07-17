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
background or detached path, and do not solve the delegated task locally as a fallback.
Direct Read/Edit/Write solving is a contract breach.

## Required Inputs

- `role`: `coder` or `reviewer`.
- `mode`: `no-write`, `patch-only`, or `auto-if-clean`.
- `task`: bounded task text or a task file path.
- `evidence`: `minimal`, `summary`, or `full`.
- `write_set`: explicit paths when mutation may be imported.
- `verification`: orchestrator-supplied commands when checks are required.
- `lease_resource_key_file`: owner-private `0600` regular file containing the trusted outer
  resource identity required for launched `auto-if-clean`.

## Shared Envelope Gate

- Coder delegations default to `mode=patch-only` and `apply_policy=preserve-patch`.
- Coder delegations may use `mode=auto-if-clean` only with an explicit repo-relative write-set,
  `apply_policy=apply-if-clean`, required verification commands, and a trusted
  `--lease-resource-key-file`. The wrapper reads the raw key only from that owner-private file,
  immediately retains only a repository-scoped digest, and never accepts the raw key on argv or
  through the envelope, environment, prompt, or bundle.
- Reviewer delegations default to `role=reviewer`, `mode=no-write`, and
  `review_lens=adversarial`.
- Supported reviewer lenses are `adversarial`, `quality`, `scope-gap`, and `security-ops`; route
  lens variants through the envelope instead of creating more agents.
- Verification commands are supplied by the orchestrator or operator. The delegated teammate must
  not invent the gate it will be judged by.
- The wrapper owns evidence capture, provenance classification, changed-path checks, and live-tree
  apply decisions.

## Delegation Flow

1. Read `agy/skills/agy-delegate/references/delegation-contract.md`.
2. Normalize the requested role, mode, lens, write-set, evidence level, timeout, and verification
   policy into the `agy.delegation.v1` contract.
3. Write the task to a temporary task file when needed.
4. Invoke exactly one wrapper run through `plugins/agy/scripts/agy_delegate.py`. For launched
   `auto-if-clean`, put the caller's trusted key in an owner-private `0600` regular file and pass
   `--lease-resource-key-file <path>` on the wrapper CLI.
5. Report only the wrapper projection and evidence bundle path.

Each follow-up delegation is a fresh wrapper invocation unless a later wrapper version explicitly
adds stateful conversation support.
