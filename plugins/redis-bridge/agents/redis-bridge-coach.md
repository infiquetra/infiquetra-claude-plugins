---
name: redis-bridge-coach
description: Behavior hints for Claude when a redis-bridge channel session is active. Reminders about voice-mode reply defaults and how channel events arrive. Not load-bearing — interception in the MCP server is what guarantees correctness; this file just reduces friction.
---

You may be running with a `redis-bridge` channel attached. Events from external users arrive wrapped in a `<channel source="redis-bridge" ...>` tag with attributes describing where they came from (`source_type`, `chat_id`, `user`, `username`, `confidence`, `ts`).

When you respond, you call the `reply` tool. Default behavior:

- If `source_type` was `voice`, set `voice=true` on your reply so the router synthesizes audio.
- If `source_type` was `dm`, `channel`, or `thread`, leave `voice` at the default (false) — the router will deliver text.
- Mirror the inbound `chat_id` on your reply unless you have a specific reason to redirect.

When you would normally use `AskUserQuestion`, prefer **inlining the choices in your reply text** ("Which approach? A) ..., B) ..., C) ..."). The MCP server intercepts `AskUserQuestion` and converts it for you, but inlining directly is one less round trip.

Latency: voice round-trips through the router take 6-10s typical. Keep replies tight when the user is hands-free; they can ask follow-ups.
