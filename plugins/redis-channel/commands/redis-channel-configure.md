---
description: Add or update a redis-channel endpoint configuration.
argument-hint: "<endpoint-name>"
---

Interactively configure the `redis-channel` endpoint named `$1` (or prompt for a name if `$1` is empty). Walks through:

- Redis URL (e.g., `redis://olympus-bus.infiquetra.com:6379/0`)
- Password env-var name (no password value entered here — that lives in env)
- Display name for `list` output
- Persists to `~/.claude/channels/redis-channel/registry.json`

**Not implemented in Phase 0.** Lands in Phase 6 polish.
