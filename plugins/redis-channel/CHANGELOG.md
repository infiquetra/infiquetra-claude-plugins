# Changelog

All notable changes to the `redis-channel` plugin will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/) and
the project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Changed — `.mcp.json` runs server under `uv run` + auto-sources password (v0.4.1)

Two reliability fixes to the shipped `.mcp.json` so the MCP server boots correctly out of the box:

**1. Use `uv run` with inline deps instead of bare `python`.** The previous `command: python` failed in Claude Code's MCP-spawn shell because `python` is rarely on the minimal default PATH on macOS (only `python3` is, via homebrew). Even when `python3` resolves, system Python doesn't have `mcp`/`redis`/`pydantic` installed. The new command is:

```
uv run --quiet --with "mcp>=1.0" --with "redis>=5.0" --with "pydantic>=2.5" python3 -m server
```

`uv` is reliably on PATH (homebrew default), it manages a per-spec cached env, and the `--with` flags ensure deps resolve at first launch — no pre-`pip install` step required. Subsequent launches use the cached env (~50ms cold-start overhead acceptable for a long-lived MCP server).

**2. Auto-source HERMES_REDIS_PASSWORD from the keychain helper.** The wrapper script now does:

1. If `HERMES_REDIS_PASSWORD` is already in env (you launched claude with it set) → use that value, helper not invoked.
2. Otherwise, if `~/.claude/channels/redis-channel/get-redis-password.sh` exists and is executable → source the value from it.
3. Otherwise (no env, no helper) → falls through to `uv run python3 -m server`, and the existing structured "endpoint X requires password env var Y but it is unset or empty" error fires at connect time with a clear message.

**Together, these mean** `/reload-plugins` is now the only thing needed to get a freshly-installed plugin connected to Redis, instead of "exit claude, set env, run pip install, relaunch claude".

**Requirements** on the host: `uv` installed (homebrew or astral installer) + the keychain helper script in place (which the user creates once as part of capturing the Redis password — see README).

### Added — same-cwd disambiguation + git_branch auto-detection

- `presence.detect_git_branch(cwd)`: runs `git rev-parse --abbrev-ref HEAD` with a 1s subprocess timeout. Returns `None` for non-git dirs / missing cwds / detached HEAD / git not installed / any subprocess failure. `build_metadata` calls it automatically when `git_branch` is unset, so live session metadata in `cc-sessions:registry` now carries the branch — useful for natural-language session routing later.
- `presence.disambiguate_if_collision(client, base_name, host, pid)`: prevents two CC sessions in the same cwd (which auto-name identically because the name's hash is `sha256(cwd + host)[:8]`) from clobbering each other in Redis. On collision with a live presence owned by a different PID on the same host, appends `-<pid_hex_4>` to the auto-name. Same-PID collision (reconnect) keeps the base name. Stale-entry (hb expired) and corrupt-entry cases pass through cleanly. Only applies when no explicit session_name was passed — user-supplied names are honored as intent and use regular replace semantics.
- `channel.py:connect` wires disambiguation into the auto-name path.
- Tests: 8 new presence cases (no-collision, same-PID, different-PID, different-host, short-PID zero-padding, stale, half-state, corrupt) + 2 channel cases (auto-name disambiguates on collision; explicit name does NOT).

### Added — Phase 2 (text bridge: inbound consumer + reply tool)

- `server/redis_consumer.py`: XREADGROUP consumer thread for `cc-sessions:<name>:inbound`. Creates the consumer group on first connect (idempotent on BUSYGROUP). Each decoded payload is handed to a caller-supplied `on_message` callback. Acks after the callback returns; a raising callback leaves the message in the pending entries list for re-delivery. Drops + acks structurally bad payloads (missing `payload` field, undecodable JSON, non-object body) so the consumer never loops on garbage. The original Redis message-id is attached as `_msg_id` for reply correlation.
- `server/redis_producer.py`: `publish_outbound()` XADDs a sorted-key JSON-encoded payload onto `cc-sessions:<name>:outbound` with `MAXLEN ~ 10_000` to bound stream growth.
- `server/notifier.py`: bridges the consumer thread → async `session.send_notification`. `AsyncNotifier` captures the asyncio loop + ServerSession at connect time; `emit()` (called from the consumer thread) builds a `Notification[dict, str](method="notifications/claude/channel", params=payload)` and schedules `send_notification` via `asyncio.run_coroutine_threadsafe`. Cleanly drops payloads if the loop is closed (no coroutine leak). `RecordingNotifier` + `NoopNotifier` are the test/no-op seams.
- `server/channel.py`: connect now also starts the consumer with the wired notifier; disconnect stops the consumer first (so it doesn't try to ack on a stale client). New `reply(chat_id, text, voice=False, in_reply_to=None)` MCP tool that XADDs an Outbound payload. Server-side guards: `chat_id` and `text` must be non-empty/non-whitespace.
- Tests: 30 new unit tests across `test_redis_channel_consumer.py` (11), `test_redis_channel_producer.py` (4), `test_redis_channel_notifier.py` (6), plus 9 additional `test_redis_channel_channel.py` cases covering consumer attachment, second-connect replaces consumer, reply XADD + voice/in_reply_to propagation, reply-when-disconnected, and empty-text/empty-chat_id rejection.

### Added — Phase 1 (presence + heartbeat + slash list)

- `server/session_id.py`: auto-generate session names from cwd + host hash (`<slug>-<8hex>`), with `CLAUDE_SESSION_NAME` env override and slug validation.
- `server/registry.py`: loads endpoint config from `~/.claude/channels/redis-channel/registry.json`; clean error types for missing/parse/unknown-endpoint cases.
- `server/redis_client.py`: Redis connection helper with password-env injection that fails loud if the configured env var is unset.
- `server/presence.py`: registry HSET + 10s heartbeat thread (TTL 60s by default) + lifecycle pub/sub events (`registered`, `unregistered`); supports context-manager use; tolerates transient errors without exiting the thread; lazy stale-entry GC on `list_live_sessions`.
- `server/channel.py`: FastMCP stdio server exposing `redis_channel_connect`, `redis_channel_disconnect`, `redis_channel_list` tools. Single-active-session state with lock; second connect replaces first; atexit + SIGTERM/SIGINT cleanup.
- `.mcp.json` manifest so Claude Code auto-launches the server.
- `docs/registry.example.json` reference config.
- Slash commands `connect`/`disconnect`/`list` rewritten to instruct Claude to invoke the matching MCP tools and interpret results.
- Tests: 57 new unit tests across `test_redis_channel_session_id.py` (12), `test_redis_channel_registry.py` (9), `test_redis_channel_presence.py` (16), `test_redis_channel_channel.py` (15). fakeredis-backed; heartbeat refresh verified with sub-TTL beat.

### Added — Phase 0 (scaffold)

- Directory layout, plugin manifest, README, CHANGELOG.
- `PROTOCOL.md` canonical wire-format spec for redis-channel ↔ router.
- `docs/STATE_MACHINE.md` routing-target state machine spec (router-side).
- `server/protocol.py` pydantic models + `is_destructive` classifier.
- `tests/test_protocol.py` covering all protocol models.
- Agent coach `agents/redis-channel-coach.md`, skill `skills/redis-channel/SKILL.md`, slash command stubs.

### Not implemented yet (planned for later phases)

- Voice routing (Phase 3).
- Permission relay + AskUserQuestion interception + audit logging (Phase 4).
- Hybrid intelligence — LLM tools for session-routing fallback (Phase 5; router-side).
