# redis-bridge

Claude Code channel plugin that bridges a session to external systems over **Redis Streams**. Hermes-agnostic by design: it speaks a documented protocol over Redis, and any router that speaks the same protocol can drive it.

The reference router is [`hermes-claude-code-router`](https://github.com/infiquetra/hermes-claude-code-router), which routes Discord voice/text through Hermes/Mimir into a connected Claude Code session for hands-free workflows.

## What this plugin does

- Connects to a Redis instance you configure (e.g., the one your router uses).
- Registers the live Claude Code session in a presence registry with auto-generated or user-set name.
- Consumes inbound messages from a Redis stream and emits them as `<channel>` events into the Claude session.
- Exposes a `reply` MCP tool: Claude calls it to send messages back via an outbound Redis stream.
- Relays tool-permission prompts over Redis so the user can approve them from outside the terminal.
- Intercepts `AskUserQuestion` calls and converts them to inline-choice replies (channel-protocol has no native structured-question facility).

It is **not** a Discord bot. It does not touch Discord, voice-channel audio, STT, or TTS. Those concerns live in the router (or wherever you want to consume the streams).

## Status

**Phase 0 scaffold.** Protocol + state-machine specs are nailed down; pydantic models pin the wire format; tests cover the type surface. The MCP server loop, Redis I/O, slash commands, and permission relay land in later phases. See `/Users/jefcox/.claude/plans/i-would-like-to-distributed-hanrahan.md` for the full roadmap.

## Layout

```
plugins/redis-bridge/
├── .claude-plugin/plugin.json     # Claude Code plugin manifest
├── PROTOCOL.md                    # canonical wire format
├── docs/STATE_MACHINE.md          # router-side routing state machine
├── agents/redis-bridge-coach.md   # behavioral hints for Claude when this channel is active
├── skills/redis-bridge/SKILL.md   # skill metadata
├── commands/                      # slash commands (connect, disconnect, list, etc.)
├── server/
│   ├── __init__.py
│   ├── __main__.py                # `python -m server` entry point
│   └── protocol.py                # pydantic models matching PROTOCOL.md
└── (tests at repo-root tests/test_redis_bridge_protocol.py, per repo convention)
```

## Protocol overview

See `PROTOCOL.md` for the full spec. Quick summary:

- Redis 6+ Streams + pub/sub. All keys namespaced under `cc-sessions:`.
- Presence: `HSET cc-sessions:registry` for static metadata + `SET cc-sessions:hb:<name> EX 60` heartbeat.
- Inbound: router XADDs JSON to `cc-sessions:<name>:inbound`; CC consumes via consumer group.
- Outbound: CC XADDs JSON to `cc-sessions:<name>:outbound`; router consumes.
- Permission relay: parallel streams for request/verdict, 5-char `request_id`, 30s window.
- Lifecycle events: pub/sub on `cc-sessions:events:<name>`.

## Routing state machine

See `docs/STATE_MACHINE.md`. The CC plugin is stateless about routing; the router owns the state machine. State key is `(user_id, endpoint, chat_id)`. Targets transition on slash commands, regex matches, or router-LLM tool calls. Race conditions (permission_request mid-stream, target lost, etc.) are spelled out explicitly.

## Development

Tests live at the repo root (per this repo's CLI-plugin convention), with the plugin source on `sys.path` via the test file itself.

```bash
# From repo root:
uv run pytest tests/test_redis_bridge_protocol.py -v
uv run ruff check plugins/redis-bridge/
uv run mypy plugins/redis-bridge/server/
```

## Related

- [`hermes-claude-code-router`](https://github.com/infiquetra/hermes-claude-code-router) — reference router implementation for Hermes.
- [`hermes-extensions`](https://github.com/infiquetra/hermes-extensions) — pattern this plugin's router was modeled on.
- [Claude Code channels reference](https://code.claude.com/docs/en/channels-reference) — upstream channel protocol Claude Code itself speaks.
