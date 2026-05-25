---
description: Connect this Claude Code session to a redis-channel endpoint (default: mimir). Registers session presence in Redis.
argument-hint: "[endpoint-name] [--session-name <name>]"
---

Connect the current session to a configured `redis-channel` endpoint.

**Action:** Call the `redis_channel_connect` MCP tool with `endpoint` set to `$1` (or `"mimir"` if no argument). If the user supplied `--session-name <name>`, pass that as `session_name`; otherwise omit it and let the server auto-generate `<cwd-basename>-<short-hash>`.

After the tool returns:
- On `{"ok": true}` — report the resolved `session_name`, the endpoint, and the heartbeat interval. Briefly note that the session is now visible to the router and the heartbeat refreshes every 10s.
- On `{"ok": false, "error": "registry not configured"}` — show the `hint` from the response and stop. The user needs to run `/redis-channel-configure` first.
- On `{"ok": false, "error": "endpoint not found"}` — show the `detail` (which lists available endpoints) and stop.
- On any other `{"ok": false}` — show `error` + `detail` and stop.

Endpoints live in `~/.claude/channels/redis-channel/registry.json`. A second connect call automatically disconnects the previous session first.
