---
name: slack-messaging
description: Send messages, search conversations, manage threads and reactions
when_to_use: |
  Use this skill when the user wants to:
  - Send messages to channels or threads
  - Search message history
  - Post incident updates
  - React to messages
  - Send team notifications
---

# Slack Messaging

Send and manage Slack messages for team communication.

## Operations

```bash
# Send message
python slack_client.py messages send --channel "#team" --text "Deploy complete"

# Search messages (requires SLACK_USER_TOKEN)
python slack_client.py messages search --query "incident"

# Reply to thread
python slack_client.py messages send --channel "C123ABC" --text "Fixed" --thread-ts "1234567890.123456"

# Add reaction
python slack_client.py messages react --channel "C123ABC" --timestamp "1234567890.123456" --emoji "white_check_mark"
```

## Natural Language

**"Post to #team that deployment is complete"**
→ Send message with deployment status

**"Search for incident discussions"**
→ Search messages with query

**"React with checkmark to that message"**
→ Add ✅ reaction
