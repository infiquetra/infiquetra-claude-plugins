---
name: delegate
description: Submit an Antigravity teammate delegation envelope through the guarded agy wrapper
argument-hint: "role=<coder|reviewer> mode=<no-write|patch-only|auto-if-clean> evidence=<minimal|summary|full>"
---

Delegate one bounded task to an Antigravity-backed teammate through the guarded wrapper.

## Instructions

1. Load `agy/skills/agy-delegate/SKILL.md`.
2. Build an `agy.delegation.v1` envelope from the command arguments and task text.
3. Invoke exactly one wrapper run with `python3 plugins/agy/scripts/agy_delegate.py`.
4. Return the wrapper projection, including the evidence bundle path.
5. Do not invoke raw `agy` directly and do not use a weaker runner path.

## Quick Reference

```bash
python3 plugins/agy/scripts/agy_delegate.py \
  --role coder \
  --mode patch-only \
  --evidence summary \
  --task-file /path/to/task.md
```

Arguments provided to the command:

`$ARGUMENTS`
