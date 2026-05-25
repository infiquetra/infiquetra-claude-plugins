---
name: redis-bridge
description: Operator-facing guide for the redis-bridge Claude Code channel plugin. Use when the user wants to connect a Claude Code session to an external router over Redis Streams (e.g., for Discord/voice via Hermes), list registered sessions, change endpoints, or troubleshoot the bridge.
---

# redis-bridge — operator guide

## What it is

`redis-bridge` is a Claude Code channel that runs as an MCP subprocess of your session. It speaks a Redis-streams protocol (see `PROTOCOL.md`) and bridges to any consumer on the other side. The reference consumer is `hermes-claude-code-router` for Discord/voice via Hermes.

## Slash commands

| Command | Effect |
|---|---|
| `/redis-bridge connect [<endpoint>]` | Register session presence with the named Redis endpoint (default: `mimir`). |
| `/redis-bridge disconnect` | Cleanly remove session from registry; stop consuming streams. |
| `/redis-bridge list` | Show configured endpoints + current connection status. |
| `/redis-bridge rename <name>` | Change the session's name in the registry (must be unique). |
| `/redis-bridge configure <endpoint>` | Add or update an endpoint in the local registry. |
| `/redis-bridge mode <auto\|always_route\|never_route>` | Override the router-side routing default for this session. |

## Configuration

`~/.claude/channels/redis-bridge/registry.json` lists known endpoints. Example:

```json
{
  "endpoints": {
    "mimir": {
      "redis_url": "redis://olympus-bus.infiquetra.com:6379/0",
      "redis_password_env": "HERMES_REDIS_PASSWORD",
      "display_name": "Mimir (Hermes profile)"
    }
  },
  "defaults": {
    "session_name_override_env": "CLAUDE_SESSION_NAME",
    "heartbeat_seconds": 10,
    "registry_ttl_seconds": 60,
    "destructive_confirm_seconds": 3,
    "permission_window_seconds": 30,
    "consumer_block_ms": 1000
  }
}
```

The password lives in an env var (referenced by name); never commit secrets to disk.

## Troubleshooting

| Symptom | Likely cause | Fix |
|---|---|---|
| `connect` fails: `NOAUTH` | `HERMES_REDIS_PASSWORD` env var unset | export the var or change the `redis_password_env` reference |
| `connect` fails: `Connection refused` | Redis unreachable or wrong URL | verify with `redis-cli -h <host> -p <port> ping` |
| Session not appearing in router's `list sessions` | Heartbeat key missing | check CC plugin process is running; `cc-sessions:hb:<name>` exists in Redis |
| Replies don't reach Discord/etc | Router not consuming outbound | check router-side consumer-group status: `XINFO GROUPS cc-sessions:<name>:outbound` |
| Permission prompt fires but no reply heard back | Voice STT didn't match "yes/no <id>" | check router-side audit log; verify confidence threshold |

## See also

- `PROTOCOL.md` — wire format (CC ↔ router)
- `docs/STATE_MACHINE.md` — routing-target state machine (router-side)
- `agents/redis-bridge-coach.md` — Claude behavior hints when this channel is active
