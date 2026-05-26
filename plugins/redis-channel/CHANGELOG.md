# Changelog

All notable changes to the `redis-channel` plugin will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/) and
the project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Changed — coach reframes channel as two-user conversation, drops anti-narration list (v0.4.9)

Cheap diagnostic confirmed the previous theory: Claude itself self-reported `"no text block, only tool call"` when asked to repeat its prior turn's assistant text. The "Yes — text block is back" outbound text from v0.4.8 testing was Claude pattern-matching the question, not reporting actual output. Streaming-write debug log activity (1929 writes during a 1.4s window) was just terminal overhead — cursor, scroll, "Brewed for Xs" line — not real content.

This is a **model emission problem, not a UI rendering problem**. No amount of UI investigation helps. Coaching is the only lever.

Jeff caught the actual confound: the v0.4.7 coach had a "what `text` is for" anti-list explicitly banning "tool-call narration", "terminal-only commentary", "status updates the developer already saw" in the `text` arg. Claude appears to be over-generalizing those bans to the text_block too, since the MANDATORY rule required byte-identical content. Result: Claude's "don't narrate tool calls" prior wins, no text_block emitted.

v0.4.9 reframes the model:

- Removed the "what `text` is for" anti-narration list entirely.
- Removed the MANDATORY skeleton + anti-pattern list.
- Replaced with a "two users in this conversation" framing: a local terminal user (sees assistant text) and a channel user (sees `reply()`'s text arg). Two separate audiences, neither sees the other's surface. Writing assistant text is NOT narration — it's the answer for one audience; the reply tool is the answer for the other.

The hypothesis is that "I have two real users to serve, each with their own surface" overrides the "don't narrate" pattern more cleanly than MANDATORY framing. Whether it works empirically is the open question.

If v0.4.9 still doesn't produce reliable text_block emission, the conclusion is: Claude's training pattern around tool calls in MCP contexts is too strong to override via coaching, and the UX gap is structural. We accept and move to Phase 3.

### Changed — `reply` tool success result drops the TextContent echo (v0.4.8)

v0.4.7's coach tightening did not improve text_block emission alongside the `reply` tool call. Round-2 testing isolated that even when `reply` schema is already loaded (no ToolSearch in the assistant turn), Claude still drops the text_block. So deferred-vs-eager isn't the cause.

New working hypothesis: the v0.4.4 echo (returning `CallToolResult(content=[TextContent(text=text)], ...)`) signals to Claude that "the text was delivered as user-visible content from the tool" — making a redundant text_block feel wrong from Claude's POV. Even though Claude Code's renderer doesn't actually show MCP `TextContent` (`[ERROR] Tool ... not found in render-time tools`), Claude's training pattern of "tool result containing the answer means no text_block needed" appears to win.

Investigation via the claude-code-guide subagent confirmed: MCP spec is silent on rendering semantics ("implementations are free to expose tools through any interface pattern that suits their needs"), and Claude Code changelog has zero mentions of MCP result content rendering in 2025-2026. There is no documented mechanism to force text_block emission alongside a tool_use.

This release removes the TextContent echo from the success path:

```python
# before (v0.4.4 - v0.4.7):
return CallToolResult(content=[TextContent(text=text)], structuredContent=result)

# after (v0.4.8):
return CallToolResult(content=[], structuredContent=result)
```

Error path keeps TextContent (Claude must be able to read why the tool failed). Programmatic clients (integ_test.py + Hermes router) read `structuredContent.msg_id` and `structuredContent.ok` — both unaffected. No tests assert on the echo so no test changes needed.

If this still doesn't restore text_block emission reliably, the conclusion is: Claude Code's design intentionally skips MCP result rendering, the gap is structural, and best-effort coaching is the only available lever. We document the limitation and stop fighting it — for Phase 3 (voice routing) this UX gap is moot because TTS speaks the answer to the channel-side user.

### Changed — coach upgrades the two-places rule from soft guidance to mandatory output shape (v0.4.7)

v0.4.5 introduced the "write the same answer in two places" coaching, but live testing of v0.4.6 caught Claude occasionally emitting just the `reply` tool call with no preceding text block. The terminal then shows only `Called plugin:redis-channel:redis-channel` — the human has to expand the tool call or scroll back through `/resume` history to read what was sent. The functional pipeline (Hermes/Discord/voice) is unaffected because the outbound stream still gets the correct `text` argument, but the local-terminal UX takes a hit.

The protocol limitation is real: Claude Code's render pipeline does not surface MCP tool result content as chat (`Tool … not found in render-time tools`), and there is no notification channel that renders outbound replies. The only mechanism that puts text on the local terminal is a text block in the assistant turn — and whether Claude emits that text block alongside the tool call is inference-variant.

Coach is tightened from "write the same answer in two places" (soft) to a MANDATORY output shape with a concrete skeleton:

```
<your one answer to the user, as a plain text block>
<tool_use: reply(chat_id=…, text=<that same answer, byte-identical>, …)>
```

Plus an explicit anti-pattern list: tool call alone, text+tool with different wording, narration ("Sent reply…"), and chain-of-thought in the text. This is best-effort — coaching reduces but does not eliminate inference variance. The deterministic fix (server-side echo notification) was considered and rejected: it would double-render every reply on the local terminal, costing tokens and confusing the merged-chat illusion. Document the imperfection; accept that hands-off review may occasionally require expanding a tool call.

Files: `agents/redis-channel-coach.md`. No code or test changes.

### Fixed — per-session stream cleanup on disconnect + lazy GC (v0.4.6)

Live audit of olympus-bus Redis caught that we were leaking stream keys: every disconnected session left `cc-sessions:<name>:inbound` and `cc-sessions:<name>:outbound` behind forever. Eight orphan stream keys accumulated in one afternoon of testing.

Fix in two layers:

1. **Graceful disconnect** (`Presence.stop`) now DELs the inbound + outbound stream keys alongside the existing `HDEL cc-sessions:registry` + `DEL cc-sessions:hb:<name>`. Reflects the "this session is done" intent. Stream history is not preserved across disconnects — if you need durable transcripts, the router should snapshot them.
2. **Lazy GC on stale entries** (`list_live_sessions(gc_stale=True)`) now extends its sweep to also DEL the streams of any registry entry whose hb key has expired. Catches ungraceful crash paths (process killed mid-session) that bypass graceful disconnect.

New helper `presence.session_stream_keys(session_name)` enumerates all per-session keys (inbound, outbound, hb) so both code paths share one source of truth for what belongs to a session.

Tests: 4 new (`test_presence_stop_drops_session_streams`, `test_session_stream_keys_layout`, `test_list_live_sessions_gc_drops_stale_streams`, `test_list_live_sessions_no_gc_when_disabled`). Repo total: 418 tests pass.

### Changed — coach asks Claude to write the reply text twice: terminal + tool (v0.4.5)

Live testing of v0.4.4 surfaced that **Claude Code does not render MCP tool result text content as visible chat output** — even when the tool returns `CallToolResult(content=[TextContent(text="…")])`. The debug log confirms:
```
[ERROR] Tool mcp__plugin_redis-channel_redis-channel__reply not found in render-time tools
```
This is internal to Claude Code's render pipeline, not something we can change from the plugin side. The v0.4.4 tool-echo approach still works for programmatic clients (the integration test still parses the structured result correctly), but it doesn't surface anything to the human reading the terminal.

So the coach is updated to ask Claude to write the reply text **in two places**:

1. As the natural conversational response in the terminal turn — this is what the local user sees as the chat history.
2. As the `text` argument to the `reply` tool — this is what the channel-side user reads (or hears via TTS).

Both contain the **same words**. Composed once, rendered in both surfaces. No "I responded with…" wrappers, no double-typing of the same content in different forms. Just compose your answer naturally; output it as your turn text; call `reply` with that text.

This is the closest channels can get to Remote-Control-style chat-merging without the framework's render-time pipeline doing more for us.

The v0.4.4 `CallToolResult` machinery stays in place — useful for programmatic clients and harmless when Claude Code chooses not to render it.

### Changed — `reply` tool echoes sent text as natural MCP result content (v0.4.4)

The reply tool's MCP wrapper now returns a `CallToolResult` with the sent `text` as the unstructured `content` element + the existing `{ok, session_name, chat_id, msg_id}` as `structuredContent`. The result: the terminal automatically renders the reply text as the tool's natural output — no model-side narration ("Reply sent on the outbound stream…", "I responded with…") needed to make the back-and-forth visible.

This closes the outbound-visibility gap toward the user's stated goal of "channels should feel like Remote Control" — both sides of the chat now render in terminal without meta-decoration.

The agent coach was rewritten with **per-source-mode formatting guidance**, because voice and text sources need fundamentally different reply shapes:

| `source`              | `voice` arg | Formatting rules for `text`                                                                                          |
| --------------------- | ----------- | -------------------------------------------------------------------------------------------------------------------- |
| `voice`               | `true`      | TTS will SPEAK aloud. Short. No markdown, no code blocks, no bare URLs. Speakable prose only. No visual references.  |
| `dm`                  | `false`     | Direct message. Full markdown, code blocks, lists, links all render properly.                                        |
| `channel`             | `false`     | Public channel. Same formatting as DM. Use `in_reply_to` to thread.                                                  |
| `thread`              | `false`     | Threaded reply. Same formatting as DM/channel.                                                                       |
| *(any other / unset)* | `false`     | Default to DM-style for forward-compatibility with future sources (email, SMS, alerts, etc.).                        |

Also:
- Removed the `debug=false/true` narration toggle (the tool's natural echo replaces it).
- Kept the TTS-safety reminder explicit: when `voice=true`, the `text` arg is what gets SPOKEN aloud — Claude must not put tool-call narration, reasoning, or terminal-only commentary into `text`.
- Added explicit "what `text` is for" section: it's the user-facing message body, full stop.
- The `debug` flag stays on the connect tool for future opt-in dev verbosity but currently has no effect.

`ServerState.reply` itself still returns a dict (unchanged) — only the MCP-tool-wrapper layer in `build_app()` was modified. Existing unit tests pass without changes.

### Added — `debug` flag on `/redis-channel-connect` controls reply narration (v0.4.3)

Live testing surfaced that Claude narrates "Reply sent on the outbound stream — msg_id=…" in the terminal after calling the `reply` tool. That's noise when the recipient is on the channel side (Discord/voice) and only the developer is watching the terminal.

`redis_channel_connect` now accepts a `debug: bool = False` arg. Honored as follows:
- **`debug=false` (default)**: quiet mode — coach + slash-command markdown tell Claude *not* to narrate replies in the terminal; the reply tool's structured result is the only confirmation.
- **`debug=true`**: verbose mode — Claude is invited to print a one-line `→ replied to <chat_id> · msg_id=<x>` after each `reply`. For developers running live integration tests.

CLI usage: `/redis-channel-connect mimir --debug` for verbose, plain `/redis-channel-connect mimir` for quiet.

The flag is stored on `ServerState`, returned in the connect response (so the coach can key off it), and reset to `false` on disconnect.

### Fixed — channel notifications now use the correct {content, meta} schema + declare `claude/channel` capability + cd to plugin root (v0.4.2)

Live install testing surfaced **three** issues that together prevented Claude Code from actually surfacing channel events end-to-end:

**1. MCP server didn't declare `claude/channel` capability.** Claude Code's launcher reads `initialize`'s `capabilities.experimental['claude/channel']` to decide whether to register a listener for channel notifications. FastMCP's `Server` doesn't expose a constructor knob for `experimental_capabilities`, so we monkey-patch `app._mcp_server.create_initialization_options` in `channel.py:_enable_channel_capability` to inject `{"claude/channel": {}}`. Without this, claude logs `"Channel notifications skipped: server did not declare claude/channel capability"` and silently drops every event.

**2. Notification params were the wrong shape.** Claude Code's [channels reference](https://code.claude.com/docs/en/channels-reference) requires `params: {content: str, meta: dict[str,str]}` — `content` becomes the body of a `<channel source="..." attr="val">…</channel>` tag in Claude's context, each `meta` key (identifiers only, no hyphens) becomes a tag attribute. We were passing the raw Inbound payload (`{v, router, source, chat_id, text, ...}`) as params, which Claude Code can't render. New `notifier.inbound_to_channel_params()` translates at the emission boundary: `content` = `text`, `meta` = the other fields stringified and filtered to identifier-safe keys. Wire format on Redis stays unchanged; only the in-process MCP frame is reshaped.

**3. `cwd: ${CLAUDE_PLUGIN_ROOT}` wasn't being honored by Claude Code's MCP launcher.** The wrapper inherited claude's cwd, so `python3 -m server` couldn't find the `server` package (error: `No module named server`). Fixed by adding `cd "$CLAUDE_PLUGIN_ROOT" || exit 1;` at the start of the shell wrapper.

**Agent coach rewrite.** `agents/redis-channel-coach.md` now describes the actual `<channel source="..." chat_id="..." …>body</channel>` tag format Claude sees in context, with concrete instructions for reading attributes and constructing replies.

**Tests:** 8 new tests in `test_redis_channel_notifier.py` covering the translation (text-only, full payload, None values dropped, nested values dropped, non-identifier keys dropped, numeric/bool stringification, missing-text fallback). Existing channel tests updated to assert the new shape. Repo total: 412 tests pass.

**Heads-up for users**: during the channels research preview, custom plugins like this one are NOT on Anthropic's approved channel allowlist. You must launch claude with `--dangerously-load-development-channels plugin:redis-channel@infiquetra-plugins` (and acknowledge the confirmation prompt) for the channel events to register. After v1 ships and Anthropic accepts the plugin onto the official allowlist, this flag becomes unnecessary.

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
