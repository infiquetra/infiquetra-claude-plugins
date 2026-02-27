"""Shared pytest fixtures for Infiquetra plugin tests."""

import pytest
from pathlib import Path
from unittest.mock import Mock, MagicMock


@pytest.fixture
def mock_aws_client():
    """Mock boto3 AWS client."""
    client = MagicMock()
    client.get_caller_identity.return_value = {
        "Account": "123456789012",
        "UserId": "AIDAI1234567890",
        "Arn": "arn:aws:iam::123456789012:user/test",
    }
    return client


@pytest.fixture
def temp_project_dir(tmp_path):
    """Create temporary project directory structure."""
    project_dir = tmp_path / "test_project"
    project_dir.mkdir()

    src_dir = project_dir / "src"
    src_dir.mkdir()

    tests_dir = project_dir / "tests"
    tests_dir.mkdir()

    pyproject = project_dir / "pyproject.toml"
    pyproject.write_text(
        """
[project]
name = "test-project"
version = "0.1.0"

[tool.pytest.ini_options]
testpaths = ["tests"]
"""
    )

    return project_dir


@pytest.fixture
def mock_github_cli():
    """Mock GitHub CLI responses."""
    mock = MagicMock()
    mock.returncode = 0
    mock.stdout = '{"name": "COMPONENT_ID", "value": "CI2408999"}'
    return mock


@pytest.fixture
def mock_subprocess_run(monkeypatch):
    """Mock subprocess.run for command execution."""
    mock = MagicMock()
    mock.return_value.returncode = 0
    mock.return_value.stdout = "Success"
    mock.return_value.stderr = ""
    monkeypatch.setattr("subprocess.run", mock)
    return mock


# ===========================
# PagerDuty Fixtures
# ===========================

@pytest.fixture
def mock_pagerduty_incident():
    """Mock PagerDuty incident response."""
    return {
        "id": "PXXXXX",
        "incident_number": 1234,
        "title": "Database connection timeout",
        "status": "triggered",
        "urgency": "high",
        "service": {"id": "SXXXXX", "summary": "my-service"},
    }


@pytest.fixture
def mock_pagerduty_service():
    """Mock PagerDuty service response."""
    return {
        "id": "SXXXXX",
        "name": "my-service",
        "status": "active",
        "escalation_policy": {"id": "YOUR_POLICY_ID", "summary": "Production Policy"},
    }


# ===========================
# Splunk Fixtures
# ===========================

@pytest.fixture
def mock_splunk_search_job():
    """Mock Splunk search job response."""
    return {"sid": "1234567890.12345"}


@pytest.fixture
def mock_splunk_results():
    """Mock Splunk search results."""
    return {
        "results": [
            {"_time": "2026-02-26T14:30:00Z", "level": "ERROR", "message": "Database timeout"},
            {"_time": "2026-02-26T14:31:00Z", "level": "ERROR", "message": "Connection failed"},
        ]
    }


# ===========================
# Slack Fixtures
# ===========================

@pytest.fixture
def mock_slack_message():
    """Mock Slack message response."""
    return {
        "ok": True,
        "ts": "1234567890.123456",
        "channel": "C123ABC",
        "message": {"text": "Hello team"},
    }


@pytest.fixture
def mock_slack_channel():
    """Mock Slack channel response."""
    return {
        "id": "C123ABC",
        "name": "team",
        "is_private": False,
        "num_members": 12,
    }
