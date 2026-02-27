"""Unit tests for splunk_client.py."""

import pytest
import json
import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

sys.path.insert(0, str(Path(__file__).parent.parent / "plugins" / "splunk" / "skills" / "splunk-search" / "scripts"))

from splunk_client import SplunkClient


class TestSplunkClient:
    """Test SplunkClient class."""

    def test_init_missing_token(self, monkeypatch, capsys):
        """Test initialization fails when token missing."""
        monkeypatch.delenv("SPLUNK_TOKEN", raising=False)
        monkeypatch.delenv("SPLUNK_HOST", raising=False)

        with pytest.raises(SystemExit):
            SplunkClient()

    def test_init_success(self, monkeypatch):
        """Test successful initialization."""
        monkeypatch.setenv("SPLUNK_TOKEN", "test-token")
        monkeypatch.setenv("SPLUNK_HOST", "splunk.example.com")

        client = SplunkClient()
        assert client.token == "test-token"
        assert "splunk.example.com" in client.base_url

    @patch("splunk_client.requests.request")
    def test_search_submit(self, mock_request, monkeypatch, capsys):
        """Test search job submission."""
        monkeypatch.setenv("SPLUNK_TOKEN", "test-token")
        monkeypatch.setenv("SPLUNK_HOST", "splunk.example.com")

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"sid": "1234567890.12345"}
        mock_request.return_value = mock_response

        client = SplunkClient()
        client.search_submit("index=main error")

        captured = capsys.readouterr()
        output = json.loads(captured.out)
        assert output["success"] is True
        assert output["data"]["sid"] == "1234567890.12345"

    @patch("splunk_client.requests.request")
    def test_search_execute(self, mock_request, monkeypatch, capsys):
        """Test search execute convenience method."""
        monkeypatch.setenv("SPLUNK_TOKEN", "test-token")
        monkeypatch.setenv("SPLUNK_HOST", "splunk.example.com")

        # Mock submit response
        submit_response = MagicMock()
        submit_response.status_code = 200
        submit_response.json.return_value = {"sid": "1234567890.12345"}

        # Mock status response (done)
        status_response = MagicMock()
        status_response.status_code = 200
        status_response.json.return_value = {
            "entry": [{"content": {"isDone": True}}]
        }

        # Mock results response
        results_response = MagicMock()
        results_response.status_code = 200
        results_response.json.return_value = {
            "results": [{"_time": "2026-02-26", "level": "ERROR"}]
        }

        mock_request.side_effect = [submit_response, status_response, results_response]

        client = SplunkClient()
        client.search_execute("index=main error", timeout=5)

        captured = capsys.readouterr()
        output = json.loads(captured.out)
        assert output["success"] is True
        assert len(output["data"]) == 1
