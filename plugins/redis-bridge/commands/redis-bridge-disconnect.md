---
description: Cleanly disconnect this Claude Code session from its redis-bridge endpoint.
---

Disconnect the current session from its `redis-bridge` endpoint:
- Stops inbound consumer.
- Deletes the heartbeat key.
- Removes session from the presence registry.
- Publishes an `unregistered{reason:"graceful"}` lifecycle event.

The router observes the disconnect and reverts any routing targets pointing at this session.

**Not implemented in Phase 0.** Lands in Phase 1.
