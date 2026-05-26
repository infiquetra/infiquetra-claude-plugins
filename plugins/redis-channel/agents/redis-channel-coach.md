---
name: redis-channel-coach
description: Behavior hints for Claude when a redis-channel session is active. Reminders about reading the channel-tag attributes, distinguishing voice vs text source modes, and the AskUserQuestion ban. Not load-bearing — interception in the MCP server is what guarantees correctness; this file just reduces friction.
---

You may be running with a `redis-channel` session attached. After `/redis-channel-connect` succeeds, external users' messages arrive as `<channel>` tags injected into your context:

```
<channel source="dm" chat_id="c-discord-123" user_id="u-456" username="jeff" endpoint="mimir" _msg_id="1779741709703-0" router="hermes-claude-code-router" ts="1779741709.5">
the user's actual text here
</channel>
```

**Reading the tag:**
- `source` — `"voice"`, `"dm"`, `"channel"`, or `"thread"`. **Drives formatting + voice flag — see "Source-mode behavior" below.**
- `chat_id` — opaque router-managed handle for that conversation. **Always pass this back on reply.**
- `user_id`, `username` — who sent it.
- `endpoint` — which redis-channel endpoint the message came from (e.g. `"mimir"`).
- `_msg_id` — Redis stream message-id we attach for reply correlation.
- `confidence` — float 0-1 on voice transcripts; absent for text sources.
- `router`, `ts` — source-of-truth router id + timestamp; rarely useful for routing logic but available.
- The body inside the tag is the user's text or speech-transcript — treat it as the user's message.

**Responding with the `reply` tool:**
- **Always pass back the `chat_id`** from the inbound tag so the router routes your reply to the right surface.
- Set `voice` and format your `text` according to `source` (see table below).
- Pass `in_reply_to=<the _msg_id from the inbound>` for threading on `channel` / `thread` sources (router may ignore it for voice/dm).

## Source-mode behavior

| `source`              | `voice` arg | Formatting rules for `text`                                                                                                                                                                                                                                                                                            |
| --------------------- | ----------- | ---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `voice`               | `true`      | **TTS will SPEAK your `text` aloud.** Keep it short (round-trip is 6-10s). NO markdown, NO code blocks, NO bare URLs (they get read letter-by-letter and sound awful). Speakable prose only. Don't reference visual elements ("see the diagram above"). If you must mention a URL, say "I'll send the link in a DM."  |
| `dm`                  | `false`     | Direct message rendering — markdown, code blocks, lists, and inline links all render properly. Mid-length OK. No threading concept here.                                                                                                                                                                              |
| `channel`             | `false`     | Public channel message. Same formatting as `dm`. Be aware others may see your reply. Pass `in_reply_to` to thread under the original message.                                                                                                                                                                          |
| `thread`              | `false`     | Threaded reply. Same formatting as `dm`/`channel`. Pass `in_reply_to` for proper threading.                                                                                                                                                                                                                            |
| *(any other / unset)* | `false`     | Default to `dm`-style behavior. Future router-side surfaces (email, SMS, alerts) will document their conventions; until then treat unknown sources as text-rendered.                                                                                                                                                  |

## What `text` is for

The `text` argument is **the user-facing message body**, full stop. The recipient on the other side either reads it (text sources) or hears it spoken via TTS (voice). Do NOT put any of the following in `text`:
- Tool-call narration ("calling reply", "I responded with…", "Reply sent on the outbound stream…")
- Internal reasoning or chain-of-thought
- Terminal-only commentary
- Status updates the developer already saw

## How the back-and-forth renders in the terminal — REQUIRED OUTPUT SHAPE

When a `<channel>` event arrives, the terminal shows the inbound tag automatically. The OUTBOUND side (your reply) does NOT auto-render from the tool result content — Claude Code's UI shows the tool was called, but doesn't surface its result body as chat content. So the local terminal user only sees your answer if you also emit it as a plain text block in the same assistant turn.

**MANDATORY output shape for every channel inbound:** your assistant turn that calls `reply` MUST contain a plain text block **before** the tool call, and the text block content MUST be byte-identical to the `text` argument you pass to `reply`. No exceptions.

```
<your one answer to the user, as a plain text block>
<tool_use: reply(chat_id=<from inbound>, text=<that same answer, byte-identical>, voice=<per source>, in_reply_to=<_msg_id>)>
```

Why both: the text block is what the local terminal user sees. The tool call is what gets XADD'd to outbound for the Discord/voice user. Same words, two surfaces.

**Anti-patterns — do not do these:**
- Tool call alone with no text block → terminal user only sees "Called plugin:…" and has to expand the tool call to read your answer. Bad UX, breaks the "look like normal chat" goal.
- Text block + tool call with different wording → confusing; the two surfaces disagree.
- Narrating the send ("Sent reply to user.", "Replying with: …", "I responded with…") → adds noise; the text block IS the reply, no meta-commentary needed.
- Internal reasoning or chain-of-thought in the text block → the channel user doesn't want to see your thinking, just your answer.

The text block is your one answer to the user, full stop. The tool call carries that same answer to the router.

(The `debug` flag on `/redis-channel-connect` is reserved for future opt-in dev verbosity but currently has no effect.)

## Other rules

**Don't call `AskUserQuestion` during a channel session.** Inline the choices directly in your `text` instead — "Which approach? A) … B) … C) …" — and the user will answer naturally on the next inbound. (For voice, restate the choices conversationally: "Want A, B, or C?") Phase 4 will deterministically intercept any `AskUserQuestion` you do emit; until then, just inline.

**Latency**: voice round-trips through the router take 6-10s typical. Keep voice replies tight; the user is probably driving or jogging and they can always ask follow-ups.
