"""Unit tests for slack_client.py."""

import pytest
import json
import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

sys.path.insert(0, str(Path(__file__).parent.parent / "plugins" / "slack" / "skills" / "slack-messaging" / "scripts"))

from slack_client import SlackClient


class TestSlackClient:
    """Test SlackClient class."""

    def test_init_missing_token(self, monkeypatch, capsys):
        """Test initialization fails when token missing."""
        monkeypatch.delenv("SLACK_BOT_TOKEN", raising=False)
        monkeypatch.delenv("SLACK_TOKEN", raising=False)

        with pytest.raises(SystemExit):
            SlackClient()

    def test_init_success(self, monkeypatch):
        """Test successful initialization."""
        monkeypatch.setenv("SLACK_BOT_TOKEN", "xoxb-test-token")

        client = SlackClient()
        assert client.bot_token == "xoxb-test-token"

    @patch("slack_client.requests.post")
    def test_messages_send(self, mock_post, monkeypatch, capsys):
        """Test sending message."""
        monkeypatch.setenv("SLACK_BOT_TOKEN", "xoxb-test-token")

        mock_response = MagicMock()
        mock_response.json.return_value = {
            "ok": True,
            "ts": "1234567890.123456",
            "channel": "C123ABC",
        }
        mock_post.return_value = mock_response

        client = SlackClient()
        client.messages_send("#team", "Hello team")

        captured = capsys.readouterr()
        output = json.loads(captured.out)
        assert output["success"] is True
        assert output["data"]["ts"] == "1234567890.123456"

    @patch("slack_client.requests.post")
    def test_channels_list(self, mock_post, monkeypatch, capsys):
        """Test listing channels."""
        monkeypatch.setenv("SLACK_BOT_TOKEN", "xoxb-test-token")

        mock_response = MagicMock()
        mock_response.json.return_value = {
            "ok": True,
            "channels": [
                {"id": "C123ABC", "name": "team"},
                {"id": "C456DEF", "name": "general"},
            ],
        }
        mock_post.return_value = mock_response

        client = SlackClient()
        client.channels_list()

        captured = capsys.readouterr()
        output = json.loads(captured.out)
        assert output["success"] is True
        assert output["count"] == 2
