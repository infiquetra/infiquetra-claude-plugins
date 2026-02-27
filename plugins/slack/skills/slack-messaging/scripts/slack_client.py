#!/usr/bin/env python3
"""
Slack CLI - Command-line interface for Slack Web API operations.

This script provides messaging and channel management for Slack.
All output is JSON for Claude Code to parse.

Environment Variables:
    SLACK_BOT_TOKEN or SLACK_TOKEN: Bot token for posting messages (required)
    SLACK_USER_TOKEN: User token for searching (optional, needed for search)

Usage:
    python slack_client.py messages send --channel "#team" --text "Hello team"
    python slack_client.py channels list
    python slack_client.py users lookup --email "jeff.user@example.com"
"""

import argparse
import json
import os
import sys
from typing import Any

try:
    import requests
except ImportError:
    print(json.dumps({"error": "requests library not installed"}))
    sys.exit(1)


class SlackClient:
    """Wrapper for Slack Web API operations with JSON output."""

    def __init__(self, bot_token: str | None = None, user_token: str | None = None):
        """Initialize the Slack client."""
        self.bot_token = bot_token or os.getenv("SLACK_BOT_TOKEN") or os.getenv("SLACK_TOKEN")
        self.user_token = user_token or os.getenv("SLACK_USER_TOKEN")

        if not self.bot_token:
            self._error("SLACK_BOT_TOKEN or SLACK_TOKEN environment variable not set")
            sys.exit(1)

        self.base_url = "https://slack.com/api"

    def _error(self, message: str, **kwargs) -> None:
        """Output error in JSON format."""
        error_data = {"error": True, "message": message}
        error_data.update(kwargs)
        print(json.dumps(error_data, indent=2))

    def _success(self, data: Any, **kwargs) -> None:
        """Output success data in JSON format."""
        output = {"success": True, "data": data}
        output.update(kwargs)
        print(json.dumps(output, indent=2, default=str))

    def _request(self, method: str, token: str | None = None, **kwargs) -> dict[str, Any]:
        """Make request to Slack API."""
        url = f"{self.base_url}/{method}"
        headers = {"Authorization": f"Bearer {token or self.bot_token}"}

        try:
            response = requests.post(url, headers=headers, json=kwargs, timeout=30)
            data = response.json()

            if not data.get("ok"):
                error_msg = data.get("error", "Unknown error")
                self._error(f"Slack API error: {error_msg}")
                sys.exit(1)

            return data

        except Exception as e:
            self._error(f"Request error: {str(e)}")
            sys.exit(1)

    # ===========================
    # MESSAGES
    # ===========================

    def messages_send(self, channel: str, text: str, thread_ts: str | None = None) -> None:
        """Send message to channel."""
        data = {"channel": channel, "text": text}
        if thread_ts:
            data["thread_ts"] = thread_ts

        response = self._request("chat.postMessage", **data)
        self._success({"ts": response.get("ts"), "channel": response.get("channel")})

    def messages_search(self, query: str, count: int = 20) -> None:
        """Search messages (requires user token)."""
        if not self.user_token:
            self._error("SLACK_USER_TOKEN required for search")
            sys.exit(1)

        response = self._request("search.messages", self.user_token, query=query, count=count)
        messages = response.get("messages", {}).get("matches", [])
        self._success(messages, count=len(messages))

    def messages_thread(self, channel: str, thread_ts: str) -> None:
        """Get thread replies."""
        response = self._request("conversations.replies", channel=channel, ts=thread_ts)
        messages = response.get("messages", [])
        self._success(messages, count=len(messages))

    def messages_react(self, channel: str, timestamp: str, emoji: str) -> None:
        """Add reaction to message."""
        self._request("reactions.add", channel=channel, timestamp=timestamp, name=emoji)
        self._success({}, message=f"Added :{emoji}: reaction")

    # ===========================
    # CHANNELS
    # ===========================

    def channels_list(self, types: str = "public_channel,private_channel") -> None:
        """List channels."""
        response = self._request("conversations.list", types=types, limit=200)
        channels = response.get("channels", [])
        self._success(channels, count=len(channels))

    def channels_info(self, channel: str) -> None:
        """Get channel info."""
        response = self._request("conversations.info", channel=channel)
        self._success(response.get("channel", {}))

    def channels_history(self, channel: str, limit: int = 100) -> None:
        """Get channel history."""
        response = self._request("conversations.history", channel=channel, limit=limit)
        messages = response.get("messages", [])
        self._success(messages, count=len(messages))

    def channels_create(self, name: str, is_private: bool = False) -> None:
        """Create channel."""
        response = self._request("conversations.create", name=name, is_private=is_private)
        self._success(response.get("channel", {}))

    def channels_archive(self, channel: str) -> None:
        """Archive channel."""
        self._request("conversations.archive", channel=channel)
        self._success({}, message=f"Channel {channel} archived")

    # ===========================
    # USERS
    # ===========================

    def users_lookup(self, email: str) -> None:
        """Lookup user by email."""
        response = self._request("users.lookupByEmail", email=email)
        self._success(response.get("user", {}))

    def users_info(self, user_id: str) -> None:
        """Get user info."""
        response = self._request("users.info", user=user_id)
        self._success(response.get("user", {}))

    def users_list(self) -> None:
        """List users."""
        response = self._request("users.list", limit=200)
        users = response.get("members", [])
        self._success(users, count=len(users))


def main():
    """Main CLI entry point."""
    parser = argparse.ArgumentParser(description="Slack CLI for messaging and channel management")
    subparsers = parser.add_subparsers(dest="resource", help="Resource type")

    # MESSAGES
    messages_parser = subparsers.add_parser("messages", help="Manage messages")
    messages_subparsers = messages_parser.add_subparsers(dest="action")

    send_parser = messages_subparsers.add_parser("send", help="Send message")
    send_parser.add_argument("--channel", required=True, help="Channel ID or name")
    send_parser.add_argument("--text", required=True, help="Message text")
    send_parser.add_argument("--thread-ts", help="Thread timestamp (for replies)")

    search_parser = messages_subparsers.add_parser("search", help="Search messages")
    search_parser.add_argument("--query", required=True, help="Search query")
    search_parser.add_argument("--count", type=int, default=20, help="Result count")

    thread_parser = messages_subparsers.add_parser("thread", help="Get thread")
    thread_parser.add_argument("--channel", required=True, help="Channel ID")
    thread_parser.add_argument("--thread-ts", required=True, help="Thread timestamp")

    react_parser = messages_subparsers.add_parser("react", help="Add reaction")
    react_parser.add_argument("--channel", required=True, help="Channel ID")
    react_parser.add_argument("--timestamp", required=True, help="Message timestamp")
    react_parser.add_argument("--emoji", required=True, help="Emoji name (without colons)")

    # CHANNELS
    channels_parser = subparsers.add_parser("channels", help="Manage channels")
    channels_subparsers = channels_parser.add_subparsers(dest="action")

    list_parser = channels_subparsers.add_parser("list", help="List channels")
    list_parser.add_argument("--types", default="public_channel,private_channel", help="Channel types")

    info_parser = channels_subparsers.add_parser("info", help="Get channel info")
    info_parser.add_argument("--channel", required=True, help="Channel ID")

    history_parser = channels_subparsers.add_parser("history", help="Get channel history")
    history_parser.add_argument("--channel", required=True, help="Channel ID")
    history_parser.add_argument("--limit", type=int, default=100, help="Message limit")

    create_parser = channels_subparsers.add_parser("create", help="Create channel")
    create_parser.add_argument("--name", required=True, help="Channel name")
    create_parser.add_argument("--private", action="store_true", help="Create private channel")

    archive_parser = channels_subparsers.add_parser("archive", help="Archive channel")
    archive_parser.add_argument("--channel", required=True, help="Channel ID")

    # USERS
    users_parser = subparsers.add_parser("users", help="Manage users")
    users_subparsers = users_parser.add_subparsers(dest="action")

    lookup_parser = users_subparsers.add_parser("lookup", help="Lookup user by email")
    lookup_parser.add_argument("--email", required=True, help="User email")

    users_info_parser = users_subparsers.add_parser("info", help="Get user info")
    users_info_parser.add_argument("--user-id", required=True, help="User ID")

    users_subparsers.add_parser("list", help="List users")

    args = parser.parse_args()

    if not args.resource:
        parser.print_help()
        sys.exit(1)

    client = SlackClient()

    if args.resource == "messages":
        if not args.action:
            messages_parser.print_help()
            sys.exit(1)

        if args.action == "send":
            client.messages_send(args.channel, args.text, args.thread_ts)
        elif args.action == "search":
            client.messages_search(args.query, args.count)
        elif args.action == "thread":
            client.messages_thread(args.channel, args.thread_ts)
        elif args.action == "react":
            client.messages_react(args.channel, args.timestamp, args.emoji)

    elif args.resource == "channels":
        if not args.action:
            channels_parser.print_help()
            sys.exit(1)

        if args.action == "list":
            client.channels_list(args.types)
        elif args.action == "info":
            client.channels_info(args.channel)
        elif args.action == "history":
            client.channels_history(args.channel, args.limit)
        elif args.action == "create":
            client.channels_create(args.name, args.private)
        elif args.action == "archive":
            client.channels_archive(args.channel)

    elif args.resource == "users":
        if not args.action:
            users_parser.print_help()
            sys.exit(1)

        if args.action == "lookup":
            client.users_lookup(args.email)
        elif args.action == "info":
            client.users_info(args.user_id)
        elif args.action == "list":
            client.users_list()


if __name__ == "__main__":
    main()
