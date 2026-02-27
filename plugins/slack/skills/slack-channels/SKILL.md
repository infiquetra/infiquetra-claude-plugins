---
name: slack-channels
description: Manage channels, view history, create/archive channels
when_to_use: |
  Use this skill when the user wants to:
  - List channels
  - View channel history
  - Create new channels
  - Archive old channels
  - Get channel information
---

# Slack Channels

Manage Slack channels and view conversation history.

## Operations

```bash
# List channels
python slack_client.py channels list

# Get channel info
python slack_client.py channels info --channel "C123ABC"

# View history
python slack_client.py channels history --channel "C123ABC" --limit 50

# Create channel
python slack_client.py channels create --name "incident-response"

# Archive channel
python slack_client.py channels archive --channel "C123ABC"
```

## Natural Language

**"List all Infiquetra channels"**
→ Filter channels by name pattern

**"Show recent messages in #team"**
→ Get channel history

**"Create incident war room"**
→ Create new channel for incident
