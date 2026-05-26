---
name: redis-channel-coach
description: Behavior hints for Claude when a redis-channel session is active. Reminders about reading the channel-tag attributes, voice-mode reply defaults, and the AskUserQuestion ban. Not load-bearing — interception in the MCP server is what guarantees correctness; this file just reduces friction.
---

You may be running with a `redis-channel` session attached. After `/redis-channel-connect` succeeds, external users' messages arrive as `<channel>` tags injected into your context:

```
<channel source="dm" chat_id="c-discord-123" user_id="u-456" username="jeff" endpoint="mimir" _msg_id="1779741709703-0" router="hermes-claude-code-router" ts="1779741709.5">
the user's actual text here
</channel>
```

**Reading the tag:**
- `source` — `"voice"`, `"dm"`, `"channel"`, or `"thread"` (where the user is reaching you from).
- `chat_id` — opaque router-managed handle for that conversation. **Always pass this back on reply.**
- `user_id`, `username` — who sent it.
- `endpoint` — which redis-channel endpoint the message came from (e.g. `"mimir"`).
- `_msg_id` — Redis stream message-id we attach for reply correlation.
- `confidence` — float 0-1 on voice transcripts; absent for text.
- `router`, `ts` — source-of-truth router id + timestamp; rarely useful for routing logic but available.
- The body inside the tag is the user's text/transcript — treat it as the user's message.

**Responding with the `reply` tool:**
- **Always pass back the `chat_id`** from the inbound tag so the router routes your reply to the right surface.
- If `source` was `"voice"`, set `voice=true` so the router synthesizes audio for that voice channel.
- If `source` was `"dm"`, `"channel"`, or `"thread"`, leave `voice` at the default (false).
- Pass `in_reply_to=<the _msg_id from the inbound>` when you want the router to thread the reply (useful in channel/thread surfaces; the router may ignore it for voice).

**Don't call `AskUserQuestion` during a channel session.** Inline the choices directly in your reply text instead ("Which approach? A) … B) … C) …"). A user on the other side will answer naturally and you'll get the response on the next inbound `<channel>` event. (Phase 4 will deterministically intercept any `AskUserQuestion` you do emit; until then, just inline.)

**Verbosity (driven by the `debug` flag on `/redis-channel-connect`):**

- The connect tool's response includes a `debug: bool` field. Honor it for the lifetime of this connection:
- **`debug=false` (default)** — quiet mode. After calling the `reply` tool for a channel event, **do not narrate the reply in the local terminal**. The recipient is on the channel side (Discord/voice/etc.); your terminal narration is invisible to them and noisy for whoever is watching the terminal. Just call the tool — the tool's structured result is the only confirmation needed.
- **`debug=true`** — verbose mode. After replying, print a one-line confirmation in the terminal (e.g. `→ replied to <chat_id> · msg_id=<x>`). This mode is for developers running live integration tests from the terminal.

If you don't remember the debug flag from connect (e.g. session was resumed), default to quiet.

Latency: voice round-trips through the router take 6-10s typical. Keep replies tight when the user is hands-free; they can ask follow-ups.
