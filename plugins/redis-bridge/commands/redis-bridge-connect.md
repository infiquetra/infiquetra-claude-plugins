---
description: Connect this Claude Code session to a redis-bridge endpoint (default: mimir). Registers session presence in Redis.
argument-hint: "[endpoint-name]"
---

Connect the current session to a configured `redis-bridge` endpoint. The endpoint must exist in `~/.claude/channels/redis-bridge/registry.json` (use `/redis-bridge list` to see configured endpoints, or `/redis-bridge configure <name>` to add one).

On success:
- Session is registered in the Redis presence registry under an auto-generated name (`<cwd-basename>-<short-hash>`) or the value of `$CLAUDE_SESSION_NAME` if set.
- Heartbeat starts (refresh every 10s, TTL 60s).
- Inbound stream consumer attaches.
- `reply` MCP tool becomes available for sending messages back to the router.

If `$1` is omitted, defaults to `mimir`.

**Not implemented in Phase 0.** Lands in Phase 1 (presence + slash list).
