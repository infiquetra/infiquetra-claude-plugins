# redis-channel

Claude Code channel plugin that bridges a session to external systems over **Redis Streams**. Router-agnostic by design: it speaks a documented protocol over Redis, and any router (web UI, mobile app, Discord bot, CLI test harness, ...) that speaks the same protocol can drive it.

One reference router is [`hermes-claude-code-router`](https://github.com/infiquetra/hermes-claude-code-router), which routes Discord voice/text into a connected Claude Code session for hands-free workflows. Other routers can be built against the same protocol.

## What this plugin does

- Connects to a Redis instance you configure (e.g., the one your router uses).
- Registers the live Claude Code session in a presence registry with auto-generated or user-set name.
- Consumes inbound messages from a Redis stream and emits them as `<channel>` events into the Claude session.
- Exposes a `reply` MCP tool: Claude calls it to send messages back via an outbound Redis stream.
- Relays tool-permission prompts over Redis so the user can approve them from outside the terminal.
- Intercepts `AskUserQuestion` calls and converts them to inline-choice replies (channel-protocol has no native structured-question facility).

It is **not** a Discord bot. It does not touch Discord, voice-channel audio, STT, or TTS. Those concerns live in the router (or wherever you want to consume the streams).

## Status

**CC-plugin side complete (foreground end-to-end verified).** Phases shipped:
- **P1** — presence registry + heartbeat (`/redis-channel-list`, 60s hb TTL).
- **P2** — inbound XREADGROUP → `notifications/claude/channel` → `reply` tool → outbound XADD round-trip.
- **P2.5** — env-var-driven auto-connect (`CLAUDE_CHANNEL_AUTO_CONNECT=1`), `claude-channel` wrapper, `/redis-channel-setup` first-run helper, `/redis-channel-status` probe, self-refreshing wrapper symlink on plugin updates.
- **P6** — `/redis-channel-configure` interactive endpoint setup, this README, [`ARCHITECTURE.md`](ARCHITECTURE.md).

**Router-side phases** (voice routing, permission relay, hybrid LLM tools, etc.) live in the router repo ([`hermes-claude-code-router`](https://github.com/infiquetra/hermes-claude-code-router)) — they don't change this plugin. The CC-plugin side is feature-complete for what a router needs to drive it.

**Known limitation** — `/redis-channel-connect` works in **foreground** claude sessions. Background-dispatched sessions (`claude --bg`, `/bg`) silently drop channel notifications because Claude Code's bg-carry-through flag set excludes `--dangerously-load-development-channels`. See [`docs/engineering-journal/LEARNINGS.md#cc-channels-bg-not-supported`](../../docs/engineering-journal/LEARNINGS.md#cc-channels-bg-not-supported) for the chase + the tmux-foreground workaround.

## Quickstart

1. **Install the plugin** via Claude Code's `/plugin` UI.
2. **Run `/redis-channel-setup`** in a Claude Code session. This symlinks `~/bin/claude-channel` to the cached wrapper (refreshes on each plugin update) and scaffolds `~/.claude/channels/redis-channel/source-env.sh` + `registry.json` from the bundled examples (only if those user files don't already exist).
3. **Edit `~/.claude/channels/redis-channel/source-env.sh`** to populate the env var named in your registry's `redis_password_env` field. Example for macOS keychain:
   ```sh
   export MY_REDIS_PASSWORD="$(security find-generic-password -s 'my-redis-keychain-item' -w)"
   ```
4. **Run `/redis-channel-configure`** to add your endpoint interactively (Redis URL, password env-var name, display name, set-as-default). Or edit `registry.json` directly.
5. **Connect.** From inside Claude Code: `/redis-channel-connect` (uses the registry's `default_endpoint`, or `/redis-channel-connect <endpoint-name>` for a specific one). The session registers under an auto-generated `<cwd-basename>-<8hex>` name; heartbeat starts.

   Or, for fresh sessions: launch via `claude-channel --session-name <name>` from a terminal. The wrapper sets `CLAUDE_CHANNEL_AUTO_CONNECT=1` so the plugin auto-connects at startup — no manual connect needed.
6. **Verify.** `/redis-channel-list` shows the registry. `/redis-channel-status` reports the current session's state.
7. **Disconnect.** `/redis-channel-disconnect` gracefully unregisters. Killing the process is also safe — the heartbeat key expires within 60s and other sessions GC the entry on the next `list`.

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

- [`hermes-claude-code-router`](https://github.com/infiquetra/hermes-claude-code-router) — one reference router implementation (Discord-via-Hermes).
- [Claude Code channels reference](https://code.claude.com/docs/en/channels-reference) — upstream channel protocol Claude Code itself speaks.
