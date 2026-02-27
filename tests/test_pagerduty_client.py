"""Unit tests for pagerduty_client.py."""

import pytest
import json
import sys
from pathlib import Path
from unittest.mock import MagicMock, patch, call

# Add plugin skills directory to path
sys.path.insert(
    0,
    str(
        Path(__file__).parent.parent
        / "plugins"
        / "pagerduty"
        / "skills"
        / "pagerduty-incidents"
        / "scripts"
    ),
)

from pagerduty_client import PagerDutyClient


class TestPagerDutyClient:
    """Test PagerDutyClient class."""

    def test_init_missing_api_key(self, monkeypatch, capsys):
        """Test initialization fails when API key missing."""
        monkeypatch.delenv("PAGERDUTY_API_KEY", raising=False)

        with pytest.raises(SystemExit) as exc_info:
            PagerDutyClient()

        assert exc_info.value.code == 1
        captured = capsys.readouterr()
        output = json.loads(captured.out)
        assert output["error"] is True
        assert "PAGERDUTY_API_KEY" in output["message"]

    def test_init_success(self, monkeypatch):
        """Test successful initialization."""
        monkeypatch.setenv("PAGERDUTY_API_KEY", "test-token-12345")

        client = PagerDutyClient()

        assert client.token == "test-token-12345"
        assert client.base_url == "https://api.pagerduty.com"
        assert "Authorization" in client.headers
        assert client.headers["Authorization"] == "Token token=test-token-12345"

    @patch("pagerduty_client.requests.request")
    def test_request_success(self, mock_request, monkeypatch):
        """Test successful API request."""
        monkeypatch.setenv("PAGERDUTY_API_KEY", "test-token")

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"incidents": []}
        mock_request.return_value = mock_response

        client = PagerDutyClient()
        result = client._request("GET", "/incidents")

        assert result == {"incidents": []}
        mock_request.assert_called_once()

    @patch("pagerduty_client.requests.request")
    def test_request_rate_limit(self, mock_request, monkeypatch, capsys):
        """Test rate limit handling."""
        monkeypatch.setenv("PAGERDUTY_API_KEY", "test-token")

        mock_response = MagicMock()
        mock_response.status_code = 429
        mock_response.headers = {"Retry-After": "60"}
        mock_request.return_value = mock_response

        client = PagerDutyClient()

        with pytest.raises(SystemExit) as exc_info:
            client._request("GET", "/incidents")

        assert exc_info.value.code == 1
        captured = capsys.readouterr()
        output = json.loads(captured.out)
        assert output["error"] is True
        assert "Rate limit exceeded" in output["message"]
        assert output["status_code"] == 429

    @patch("pagerduty_client.requests.request")
    def test_request_404_error(self, mock_request, monkeypatch, capsys):
        """Test 404 error handling."""
        monkeypatch.setenv("PAGERDUTY_API_KEY", "test-token")

        mock_response = MagicMock()
        mock_response.status_code = 404
        mock_response.json.return_value = {
            "error": {"message": "Incident not found", "code": 2003}
        }
        mock_request.return_value = mock_response

        client = PagerDutyClient()

        with pytest.raises(SystemExit) as exc_info:
            client._request("GET", "/incidents/INVALID")

        assert exc_info.value.code == 1
        captured = capsys.readouterr()
        output = json.loads(captured.out)
        assert output["error"] is True
        assert "Incident not found" in output["message"]

    @patch("pagerduty_client.requests.request")
    def test_paginate(self, mock_request, monkeypatch):
        """Test pagination handling."""
        monkeypatch.setenv("PAGERDUTY_API_KEY", "test-token")

        # First page
        mock_response_1 = MagicMock()
        mock_response_1.status_code = 200
        mock_response_1.json.return_value = {
            "incidents": [{"id": "P1"}, {"id": "P2"}],
            "more": True,
        }

        # Second page
        mock_response_2 = MagicMock()
        mock_response_2.status_code = 200
        mock_response_2.json.return_value = {
            "incidents": [{"id": "P3"}],
            "more": False,
        }

        mock_request.side_effect = [mock_response_1, mock_response_2]

        client = PagerDutyClient()
        results = client._paginate("/incidents", key="incidents")

        assert len(results) == 3
        assert results[0]["id"] == "P1"
        assert results[2]["id"] == "P3"
        assert mock_request.call_count == 2

    @patch("pagerduty_client.requests.request")
    def test_incidents_list(self, mock_request, monkeypatch, capsys):
        """Test listing incidents."""
        monkeypatch.setenv("PAGERDUTY_API_KEY", "test-token")

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "incidents": [
                {
                    "id": "PXXXXX",
                    "status": "triggered",
                    "urgency": "high",
                    "service": {"id": "SXXXXX", "summary": "wallet-service"},
                }
            ],
            "more": False,
        }
        mock_request.return_value = mock_response

        client = PagerDutyClient()
        client.incidents_list(status="triggered", urgency="high")

        captured = capsys.readouterr()
        output = json.loads(captured.out)
        assert output["success"] is True
        assert len(output["data"]) == 1
        assert output["data"][0]["id"] == "PXXXXX"

    @patch("pagerduty_client.requests.request")
    def test_incidents_get(self, mock_request, monkeypatch, capsys):
        """Test getting incident details."""
        monkeypatch.setenv("PAGERDUTY_API_KEY", "test-token")

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "incident": {
                "id": "PXXXXX",
                "status": "triggered",
                "title": "Database timeout",
            }
        }
        mock_request.return_value = mock_response

        client = PagerDutyClient()
        client.incidents_get("PXXXXX")

        captured = capsys.readouterr()
        output = json.loads(captured.out)
        assert output["success"] is True
        assert output["data"]["id"] == "PXXXXX"

    @patch("pagerduty_client.requests.request")
    def test_incidents_acknowledge(self, mock_request, monkeypatch, capsys):
        """Test acknowledging incident."""
        monkeypatch.setenv("PAGERDUTY_API_KEY", "test-token")

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "incident": {"id": "PXXXXX", "status": "acknowledged"}
        }
        mock_request.return_value = mock_response

        client = PagerDutyClient()
        client.incidents_acknowledge("PXXXXX")

        captured = capsys.readouterr()
        output = json.loads(captured.out)
        assert output["success"] is True
        assert output["message"] == "Incident acknowledged"
        assert output["data"]["status"] == "acknowledged"

    @patch("pagerduty_client.requests.request")
    def test_incidents_resolve(self, mock_request, monkeypatch, capsys):
        """Test resolving incident."""
        monkeypatch.setenv("PAGERDUTY_API_KEY", "test-token")

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "incident": {"id": "PXXXXX", "status": "resolved"}
        }
        mock_request.return_value = mock_response

        client = PagerDutyClient()
        client.incidents_resolve("PXXXXX")

        captured = capsys.readouterr()
        output = json.loads(captured.out)
        assert output["success"] is True
        assert output["message"] == "Incident resolved"

    @patch("pagerduty_client.requests.request")
    def test_incidents_add_note(self, mock_request, monkeypatch, capsys):
        """Test adding note to incident."""
        monkeypatch.setenv("PAGERDUTY_API_KEY", "test-token")

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "note": {"id": "NXXXXX", "content": "Investigating issue"}
        }
        mock_request.return_value = mock_response

        client = PagerDutyClient()
        client.incidents_add_note("PXXXXX", "Investigating issue")

        captured = capsys.readouterr()
        output = json.loads(captured.out)
        assert output["success"] is True
        assert output["message"] == "Note added to incident"

    @patch("pagerduty_client.requests.request")
    def test_incidents_reassign(self, mock_request, monkeypatch, capsys):
        """Test reassigning incident."""
        monkeypatch.setenv("PAGERDUTY_API_KEY", "test-token")

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"incident": {"id": "PXXXXX"}}
        mock_request.return_value = mock_response

        client = PagerDutyClient()
        client.incidents_reassign("PXXXXX", "UYYYYY")

        captured = capsys.readouterr()
        output = json.loads(captured.out)
        assert output["success"] is True
        assert "reassigned" in output["message"].lower()

    @patch("pagerduty_client.requests.request")
    def test_services_list(self, mock_request, monkeypatch, capsys):
        """Test listing services."""
        monkeypatch.setenv("PAGERDUTY_API_KEY", "test-token")

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "services": [
                {"id": "SXXXXX", "name": "wallet-service", "status": "active"}
            ],
            "more": False,
        }
        mock_request.return_value = mock_response

        client = PagerDutyClient()
        client.services_list()

        captured = capsys.readouterr()
        output = json.loads(captured.out)
        assert output["success"] is True
        assert len(output["data"]) == 1
        assert output["data"][0]["name"] == "wallet-service"

    @patch("pagerduty_client.requests.request")
    def test_services_create(self, mock_request, monkeypatch, capsys):
        """Test creating service."""
        monkeypatch.setenv("PAGERDUTY_API_KEY", "test-token")

        mock_response = MagicMock()
        mock_response.status_code = 201
        mock_response.json.return_value = {
            "service": {
                "id": "SXXXXX",
                "name": "new-service",
                "description": "Test service",
            }
        }
        mock_request.return_value = mock_response

        client = PagerDutyClient()
        client.services_create("new-service", "Test service")

        captured = capsys.readouterr()
        output = json.loads(captured.out)
        assert output["success"] is True
        assert "created" in output["message"].lower()

    @patch("pagerduty_client.requests.request")
    def test_services_update(self, mock_request, monkeypatch, capsys):
        """Test updating service."""
        monkeypatch.setenv("PAGERDUTY_API_KEY", "test-token")

        # Mock GET request for current service
        mock_get_response = MagicMock()
        mock_get_response.status_code = 200
        mock_get_response.json.return_value = {
            "service": {
                "id": "SXXXXX",
                "name": "wallet-service",
                "description": "Old description",
            }
        }

        # Mock PUT request for update
        mock_put_response = MagicMock()
        mock_put_response.status_code = 200
        mock_put_response.json.return_value = {
            "service": {
                "id": "SXXXXX",
                "name": "wallet-service",
                "description": "New description",
            }
        }

        mock_request.side_effect = [mock_get_response, mock_put_response]

        client = PagerDutyClient()
        client.services_update("SXXXXX", description="New description")

        captured = capsys.readouterr()
        output = json.loads(captured.out)
        assert output["success"] is True
        assert "updated" in output["message"].lower()

    @patch("pagerduty_client.requests.request")
    def test_services_delete(self, mock_request, monkeypatch, capsys):
        """Test deleting service."""
        monkeypatch.setenv("PAGERDUTY_API_KEY", "test-token")

        mock_response = MagicMock()
        mock_response.status_code = 204
        mock_response.json.return_value = {}
        mock_request.return_value = mock_response

        client = PagerDutyClient()
        client.services_delete("SXXXXX")

        captured = capsys.readouterr()
        output = json.loads(captured.out)
        assert output["success"] is True
        assert "deleted" in output["message"].lower()

    @patch("pagerduty_client.requests.request")
    def test_teams_list(self, mock_request, monkeypatch, capsys):
        """Test listing teams."""
        monkeypatch.setenv("PAGERDUTY_API_KEY", "test-token")

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "teams": [{"id": "PIZE7QW", "name": "Infiquetra", "description": "Infiquetra team"}],
            "more": False,
        }
        mock_request.return_value = mock_response

        client = PagerDutyClient()
        client.teams_list()

        captured = capsys.readouterr()
        output = json.loads(captured.out)
        assert output["success"] is True
        assert len(output["data"]) == 1
        assert output["data"][0]["id"] == "PIZE7QW"

    @patch("pagerduty_client.requests.request")
    def test_teams_create(self, mock_request, monkeypatch, capsys):
        """Test creating team."""
        monkeypatch.setenv("PAGERDUTY_API_KEY", "test-token")

        mock_response = MagicMock()
        mock_response.status_code = 201
        mock_response.json.return_value = {
            "team": {"id": "TXXXXX", "name": "New Team", "description": "New team"}
        }
        mock_request.return_value = mock_response

        client = PagerDutyClient()
        client.teams_create("New Team", "New team")

        captured = capsys.readouterr()
        output = json.loads(captured.out)
        assert output["success"] is True
        assert "created" in output["message"].lower()

    @patch("pagerduty_client.requests.request")
    def test_teams_members_add(self, mock_request, monkeypatch, capsys):
        """Test adding team member."""
        monkeypatch.setenv("PAGERDUTY_API_KEY", "test-token")

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"success": True}
        mock_request.return_value = mock_response

        client = PagerDutyClient()
        client.teams_members_add("PIZE7QW", "UXXXXX", role="responder")

        captured = capsys.readouterr()
        output = json.loads(captured.out)
        assert output["success"] is True
        assert "added to team" in output["message"].lower()

    @patch("pagerduty_client.requests.request")
    def test_policies_list(self, mock_request, monkeypatch, capsys):
        """Test listing escalation policies."""
        monkeypatch.setenv("PAGERDUTY_API_KEY", "test-token")

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "escalation_policies": [
                {"id": "P0G40L2", "name": "Infiquetra Production", "escalation_rules": []}
            ],
            "more": False,
        }
        mock_request.return_value = mock_response

        client = PagerDutyClient()
        client.policies_list()

        captured = capsys.readouterr()
        output = json.loads(captured.out)
        assert output["success"] is True
        assert len(output["data"]) == 1
        assert output["data"][0]["id"] == "P0G40L2"

    @patch("pagerduty_client.requests.request")
    def test_oncall_list(self, mock_request, monkeypatch, capsys):
        """Test listing on-call users."""
        monkeypatch.setenv("PAGERDUTY_API_KEY", "test-token")

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "oncalls": [
                {
                    "user": {"id": "UXXXXX", "summary": "Jeff Cox"},
                    "escalation_level": 1,
                }
            ],
            "more": False,
        }
        mock_request.return_value = mock_response

        client = PagerDutyClient()
        client.oncall_list()

        captured = capsys.readouterr()
        output = json.loads(captured.out)
        assert output["success"] is True
        assert len(output["data"]) == 1
        assert output["data"][0]["escalation_level"] == 1

    @patch("pagerduty_client.requests.request")
    def test_users_list(self, mock_request, monkeypatch, capsys):
        """Test listing users."""
        monkeypatch.setenv("PAGERDUTY_API_KEY", "test-token")

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "users": [
                {
                    "id": "UXXXXX",
                    "name": "Jeff Cox",
                    "email": "jeff.user@example.com",
                }
            ],
            "more": False,
        }
        mock_request.return_value = mock_response

        client = PagerDutyClient()
        client.users_list()

        captured = capsys.readouterr()
        output = json.loads(captured.out)
        assert output["success"] is True
        assert len(output["data"]) == 1
        assert output["data"][0]["name"] == "Jeff Cox"

    @patch("pagerduty_client.requests.request")
    def test_vecu_defaults(self, mock_request, monkeypatch, capsys):
        """Test Infiquetra default team ID is used when not specified."""
        monkeypatch.setenv("PAGERDUTY_API_KEY", "test-token")

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"incidents": [], "more": False}
        mock_request.return_value = mock_response

        client = PagerDutyClient()
        assert client.DEFAULT_TEAM_ID == "PIZE7QW"
        assert client.DEFAULT_ESCALATION_POLICY_ID == "P0G40L2"

        # Call incidents_list without team_id - should use default
        client.incidents_list()

        # Verify the request was made with the default team ID
        call_args = mock_request.call_args
        assert "team_ids[]" in call_args[1]["params"]


@pytest.fixture
def mock_subprocess_run():
    """Mock subprocess.run for git operations."""
    with patch("subprocess.run") as mock:
        mock_result = MagicMock()
        mock_result.returncode = 0
        mock_result.stdout = ""
        mock.return_value = mock_result
        yield mock
