---
description: List configured redis-bridge endpoints and their connection status.
---

Print the configured endpoints from `~/.claude/channels/redis-bridge/registry.json`. For each:
- Endpoint name + display name + Redis URL (password redacted).
- Current connection status (this session connected? other session connected? unreachable?).
- For connected endpoints, show all live registered sessions (this session highlighted).

**Not implemented in Phase 0.** Lands in Phase 1.
