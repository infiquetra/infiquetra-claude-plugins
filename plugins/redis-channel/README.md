# redis-channel

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

**Phase 2 complete.** Presence + heartbeat (P1) plus inbound consumer + `reply` MCP tool (P2). Channel notifications surface as `notifications/claude/channel` events with the full Inbound payload; replies XADD onto the outbound stream with router-correlation IDs and an `in_reply_to` field for threading. Phase 3 (voice routing through Hermes TTS/STT) and Phase 4 (permission relay + AskUserQuestion interception) still to come — both gated on the matching router-side implementation in `hermes-claude-code-router`. Roadmap: `/Users/jefcox/.claude/plans/i-would-like-to-distributed-hanrahan.md`.

## Quickstart

1. **Configure an endpoint.** Copy `docs/registry.example.json` to `~/.claude/channels/redis-channel/registry.json` and edit. At minimum set `redis_url` and `redis_password_env` (the name of the env var containing your Redis password — never embed the password in the file).
2. **Make sure Python deps are available.** The plugin's MCP server (`python -m server`) needs `mcp` and `redis` on its Python path. `uv sync --extra dev` at the repo root covers it for development.
3. **Connect from inside Claude Code.** Run `/redis-channel-connect mimir` (or whatever endpoint name you configured). The session is registered with an auto-generated `<cwd-basename>-<8hex>` name, heartbeat starts.
4. **Verify.** Run `/redis-channel-list` to see the registry. Start another CC session in a different repo and `/redis-channel-connect` it too; the list shows both.
5. **Disconnect.** `/redis-channel-disconnect` gracefully unregisters. Killing the process is also safe — the heartbeat key expires within 60s and other sessions GC the entry the next time they `list`.

## Layout

```
plugins/redis-channel/
├── .claude-plugin/plugin.json     # Claude Code plugin manifest
├── .mcp.json                      # auto-launch the MCP server
├── PROTOCOL.md                    # canonical wire format
├── docs/
│   ├── STATE_MACHINE.md           # router-side routing state machine
│   └── registry.example.json      # sample endpoint config
├── agents/redis-channel-coach.md
├── skills/redis-channel/SKILL.md
├── commands/                      # slash commands (connect, disconnect, list, ...)
├── server/
│   ├── __init__.py
│   ├── __main__.py                # `python -m server` entry point
│   ├── channel.py                 # FastMCP server: connect/disconnect/list + reply tools
│   ├── presence.py                # registry HSET + heartbeat thread + lifecycle pubsub
│   ├── redis_client.py            # connection helper + password-env injection
│   ├── redis_consumer.py          # XREADGROUP loop, dispatches to notifier
│   ├── redis_producer.py          # XADD helper for outbound stream
│   ├── notifier.py                # thread → asyncio bridge for notifications/claude/channel
│   ├── registry.py                # local endpoint config loader
│   ├── session_id.py              # auto-name generator + override validation
│   └── protocol.py                # pydantic models matching PROTOCOL.md
└── (tests at repo-root tests/test_redis_channel_*.py)
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
uv run pytest tests/test_redis_channel_*.py -v
uv run ruff check plugins/redis-channel/
uv run mypy plugins/redis-channel/server/
```

## Related

- [`hermes-claude-code-router`](https://github.com/infiquetra/hermes-claude-code-router) — reference router implementation for Hermes.
- [`hermes-extensions`](https://github.com/infiquetra/hermes-extensions) — pattern this plugin's router was modeled on.
- [Claude Code channels reference](https://code.claude.com/docs/en/channels-reference) — upstream channel protocol Claude Code itself speaks.
