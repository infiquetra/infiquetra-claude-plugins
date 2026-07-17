---
name: delegate
description: Submit an Antigravity teammate delegation envelope through the guarded agy wrapper
argument-hint: "role=<coder|reviewer> mode=<no-write|patch-only|auto-if-clean> evidence=<minimal|summary|full> write-set=<path> lease-resource-key-file=<path> verification=<command>"
---

Delegate one bounded task to an Antigravity-backed teammate through the guarded wrapper.

## Instructions

1. Load `agy/skills/agy-delegate/SKILL.md`.
2. Build an `agy.delegation.v1` envelope from the command arguments and task text.
3. Invoke exactly one wrapper run with `python3 plugins/agy/scripts/agy_delegate.py`.
4. Return the wrapper projection, including the evidence bundle path.
5. Do not invoke raw `agy` directly, do not use background or detached execution, and do not use a
   weaker runner path.
6. Do not use direct Claude repo file tools to solve the delegated task locally.

## Argument Syntax

- `role=<coder|reviewer>` selects the envelope role. Reviewer defaults are `mode=no-write` and
  `review_lens=adversarial`.
- `mode=<no-write|patch-only|auto-if-clean>` selects the write gate. Coder defaults to
  `patch-only`.
- `evidence=<minimal|summary|full>` selects the evidence bundle detail level.
- `review_lens=<adversarial|quality|scope-gap|security-ops>` selects one reviewer lens without
  creating another agent.
- `write-set=<repo-relative-path>` may be repeated. It is required when mutation may be imported,
  and `auto-if-clean` requires at least one explicit write-set path.
- `lease-resource-key-file=<path>` is required for launched `auto-if-clean`. The file must be an
  owner-private `0600` regular file. Pass only its path as wrapper CLI
  `--lease-resource-key-file`; do not put the raw key on argv or copy it into the envelope,
  environment, task text, or evidence bundle.
- `verification=<command>` may be repeated. Required verification commands must be supplied by the
  operator or orchestrator, not invented by the delegate.
- `verification-required=<true|false>` declares whether the wrapper must see successful checks.
- `verification-run-scope=clone` is required for `auto-if-clean`; other scopes are accepted only for
  non-applying evidence paths.

## Quick Reference

```bash
python3 plugins/agy/scripts/agy_delegate.py \
  --role coder \
  --mode patch-only \
  --evidence summary \
  --write-set plugins/example/file.py \
  --verification-command "PYTHONPATH=. python3 -m pytest -q tests/test_example.py" \
  --verification-required \
  --task-file /path/to/task.md
```

Arguments provided to the command:

`$ARGUMENTS`
