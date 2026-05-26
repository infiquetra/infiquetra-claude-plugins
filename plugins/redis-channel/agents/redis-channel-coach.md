---
name: redis-channel-coach
description: Reference doc for redis-channel session behavior. The load-bearing runtime guidance lives in the MCP server's `instructions=` field (see server/channel.py build_app) so Claude reads it on every turn including notification-triggered ones. This file is a human-readable pointer; subagent invocations not expected.
---

The runtime behavior coaching for redis-channel sessions is delivered through the MCP server's `instructions` field — see `server/channel.py::build_app` and the corresponding "MCP Server Instructions" section that Claude Code injects into the system prompt at session start.

Why not here? Files in `agents/` define Claude Code subagents — they're invoked via the Agent tool, not automatically loaded into Claude's active context. For a plugin like this one where behavior coaching must apply during notification-triggered turns (where no Agent invocation happens), the coaching needs to live somewhere that loads with the MCP server itself.

If you need to adjust the coaching, edit the `instructions=` string in `server/channel.py`. Bump the plugin version + add a CHANGELOG entry as usual.

Open questions worth exploring later:
- Should `agents/` get a different file that DOES make sense as a subagent (e.g., a "redis-channel-debugger" agent invoked when troubleshooting connection issues)?
- Are there any redis-channel behaviors that fit the subagent invocation pattern (Agent-tool-triggered, not always-on)?
