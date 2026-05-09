"""Shared pytest fixtures for Infiquetra plugin tests."""

from unittest.mock import MagicMock

import pytest


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


# ===========================
# UniFi Fixtures
# ===========================


@pytest.fixture
def mock_unifi_device():
    """Mock UniFi network device response."""
    return {
        "_id": "64a1b2c3d4e5f6789012345",
        "mac": "aa:bb:cc:dd:ee:ff",
        "name": "U6-Pro-Office",
        "model": "U6-Pro",
        "type": "uap",
        "state": 1,
        "version": "6.6.55.15907",
        "ip": "10.220.1.20",
        "uptime": 86400,
    }


@pytest.fixture
def mock_unifi_client():
    """Mock UniFi wireless client response."""
    return {
        "_id": "64a1b2c3d4e5f678901234a",
        "mac": "11:22:33:44:55:66",
        "hostname": "my-laptop",
        "ip": "10.220.10.50",
        "network": "Main",
        "essid": "HomeNetwork",
        "signal": -55,
        "rx_bytes": 1024000,
        "tx_bytes": 512000,
    }


@pytest.fixture
def mock_unifi_network():
    """Mock UniFi network (VLAN) config response."""
    return {
        "_id": "64a1b2c3d4e5f678901234b",
        "name": "IoT",
        "purpose": "corporate",
        "vlan": 30,
        "ip_subnet": "10.220.30.1/24",
        "dhcpd_enabled": True,
    }


@pytest.fixture
def mock_unifi_firewall_rule():
    """Mock UniFi firewall rule response."""
    return {
        "_id": "64a1b2c3d4e5f678901234c",
        "name": "Block IoT to LAN",
        "action": "drop",
        "ruleset": "LAN_IN",
        "rule_index": 2000,
        "enabled": True,
        "src_networkconf_id": "64a1b2c3d4e5f678901234b",
    }


@pytest.fixture
def mock_unifi_camera():
    """Mock UniFi Protect camera response."""
    return {
        "id": "64a1b2c3d4e5f678901234d",
        "name": "Front Door",
        "type": "UVC-G4-Pro",
        "state": "CONNECTED",
        "mac": "aa:bb:cc:dd:ee:01",
        "host": "10.220.1.100",
        "channels": [
            {
                "id": "0",
                "name": "High",
                "isRtspEnabled": True,
                "rtspAlias": "front_door_high_quality",
                "width": 3840,
                "height": 2160,
            },
            {
                "id": "1",
                "name": "Medium",
                "isRtspEnabled": True,
                "rtspAlias": "front_door_medium_quality",
                "width": 1920,
                "height": 1080,
            },
        ],
        "ptzPresets": [
            {"id": "0", "name": "Front View"},
            {"id": "1", "name": "Side View"},
        ],
    }


@pytest.fixture
def mock_unifi_event():
    """Mock UniFi Protect event response."""
    return {
        "id": "64a1b2c3d4e5f678901234e",
        "type": "motion",
        "start": 1710000000000,
        "end": 1710000060000,
        "score": 85,
        "camera": "64a1b2c3d4e5f678901234d",
        "thumbnail": "e-64a1b2c3d4e5f678901234e",
    }


@pytest.fixture
def mock_unifi_nvr():
    """Mock UniFi Protect NVR info response."""
    return {
        "id": "64a1b2c3d4e5f678901234f",
        "name": "UniFi Dream Machine",
        "type": "UDMPRO",
        "version": "3.2.12",
        "firmwareVersion": "3.2.12.9351",
        "uptime": 7200000,
        "storageInfo": {
            "totalSize": 2000000000000,
            "usedSize": 500000000000,
        },
    }
