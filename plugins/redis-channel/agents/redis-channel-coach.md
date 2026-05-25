---
name: redis-channel-coach
description: Behavior hints for Claude when a redis-channel channel session is active. Reminders about voice-mode reply defaults and how channel events arrive. Not load-bearing — interception in the MCP server is what guarantees correctness; this file just reduces friction.
---

You may be running with a `redis-channel` channel attached. After `/redis-channel-connect` succeeds, external users' messages arrive as `notifications/claude/channel` events. The notification params carry the full Inbound payload:

- `source` — `"voice"`, `"dm"`, `"channel"`, or `"thread"` (where the user is on the other side).
- `chat_id` — opaque router-managed handle for that conversation.
- `user_id`, `username` — who sent it.
- `text` — what they said (or the STT transcript).
- `confidence` — float 0-1 for voice transcripts; absent for text.
- `endpoint` — which endpoint the message came from (e.g. `"mimir"`).
- `_msg_id` — Redis stream message-id we attach for reply correlation.

To respond, call the `reply` tool:

- **Always pass back the `chat_id`** from the inbound event so the router routes your reply to the right surface.
- If `source` was `"voice"`, set `voice=true` so the router synthesizes audio for that voice channel.
- If `source` was `"dm"`, `"channel"`, or `"thread"`, leave `voice` at the default (false).
- Pass `in_reply_to=<the `_msg_id` from the inbound>` when you want the router to thread the reply (useful in channel/thread surfaces; the router may ignore it for voice).

**Don't call `AskUserQuestion` during a channel session.** Inline the choices directly in your reply text instead ("Which approach? A) … B) … C) …"). A user on the other side will answer naturally and you'll get the response on the next inbound event. (Phase 4 will deterministically intercept any `AskUserQuestion` you do emit; until then, just inline.)

Latency: voice round-trips through the router take 6-10s typical. Keep replies tight when the user is hands-free; they can ask follow-ups.
