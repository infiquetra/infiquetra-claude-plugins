"""Shared pytest fixtures for Infiquetra plugin tests."""

import sys
from pathlib import Path
from unittest.mock import MagicMock

import pytest

# Make `plugins/redis-channel/server/*` importable without installing.
# The plugin dir contains a hyphen so it isn't a valid Python package name —
# we put the *plugin* dir on sys.path so `from server.foo import ...` works.
_REDIS_BRIDGE_ROOT = Path(__file__).parent.parent / "plugins" / "redis-channel"
if str(_REDIS_BRIDGE_ROOT) not in sys.path:
    sys.path.insert(0, str(_REDIS_BRIDGE_ROOT))


@pytest.fixture(autouse=True)
def _clear_ambient_saga_concurrency_override(monkeypatch: pytest.MonkeyPatch) -> None:
    """Keep ordinary emitter tests independent of the operator's shell concurrency override."""

    monkeypatch.delenv("SAGA_MAX_CONCURRENT", raising=False)


# Same concern as above, for the fleet-lease admission surface. An operator who arms these
# in their shell (or in ~/.claude/settings.json `env`) makes `session_admission_snapshot`
# take its explicit-environment branch, which then disagrees with any snapshot a test
# pinned itself — so admission tests would pass or fail based on the operator's own
# machine. Tests that need these set them explicitly after this fixture runs.
_FLEET_ADMISSION_ENV = (
    "INFIQUETRA_FLEET_SESSION_LIMIT",
    "INFIQUETRA_FLEET_AGGREGATE_LIMIT",
    "INFIQUETRA_FLEET_POLICY_SHA256",
    "INFIQUETRA_FLEET_MUTATION",
)


@pytest.fixture(autouse=True)
def _clear_ambient_fleet_admission_env(monkeypatch: pytest.MonkeyPatch) -> None:
    """Keep lease-admission tests independent of the operator's armed fleet environment."""

    for var in _FLEET_ADMISSION_ENV:
        monkeypatch.delenv(var, raising=False)


# --- #279 hard floor: GitHub-write test modules can never touch the live operations board ---
_GH_WRITE_TEST_MODULES = {"test_mission_control", "test_outcome_board_sync", "test_ship_ceremony"}


@pytest.fixture(autouse=True)
def _no_live_gh(request, monkeypatch):
    """Deny-by-default guard for the GitHub-mutating test modules (#279 doc-review hard floor).

    Mission-control's issue verbs and the ``/outcome`` board-sync consumer mutate GitHub through
    ``gh`` (``sdlc_manager._gh`` builds ``["gh", *args]``). For the modules that exercise those
    verbs this autouse fixture (a) strips every GitHub credential from the env and (b) replaces
    ``subprocess.run`` with a wrapper that RAISES on any unmocked ``gh`` invocation. A test that
    legitimately drives a verb injects its own fake runner
    (``monkeypatch.setattr("subprocess.run", ...)``), which overrides this guard for that test — so a
    *forgotten* mock fails loudly instead of hitting the real board. Unlike the opt-in
    ``mock_subprocess_run`` fixture this denies by default; it is the concrete tripwire behind the
    external-agent "escalate off agy on a real-gh call" rule.
    """
    if request.module.__name__.rsplit(".", 1)[-1] not in _GH_WRITE_TEST_MODULES:
        return
    # Strip env creds AND point gh's file-based auth at a nonexistent config dir — gh authenticates
    # from ~/.config/gh/hosts.yml too, so env-strip alone is not a real backstop on a logged-in box.
    for var in ("GH_TOKEN", "GITHUB_TOKEN", "GH_HOST", "GH_ENTERPRISE_TOKEN"):
        monkeypatch.delenv(var, raising=False)
    monkeypatch.setenv("GH_CONFIG_DIR", "/nonexistent-no-live-gh-guard-279")

    import subprocess as _sp

    real_run = _sp.run

    def _guard(cmd, *args, **kwargs):
        argv = cmd if isinstance(cmd, (list, tuple)) else str(cmd).split()
        parts = [str(a) for a in argv]
        first = parts[0] if parts else ""
        # Block a direct `gh` call AND the nested production path (`python3 …/sdlc_manager.py …`),
        # whose gh runs one process deeper where this in-process wrapper cannot see it.
        is_gh = first == "gh" or first.endswith("/gh")
        invokes_sdlc = any("sdlc_manager.py" in p for p in parts)
        if is_gh or invokes_sdlc:
            raise RuntimeError(
                "no-live-gh guard (#279): an unmocked GitHub-mutating call escaped a GitHub-write "
                "test module (direct `gh` or a nested sdlc_manager.py subprocess); inject a fake "
                f"runner instead of touching the live board. cmd={parts!r}"
            )
        return real_run(cmd, *args, **kwargs)

    monkeypatch.setattr(_sp, "run", _guard)


# --- #458 T11-F4-7: boundary-crossing test convention ---
# The generalizable rule from LEARNINGS {#test-shape-masks-dead-wiring-291}: "A round-trip test only
# proves the round-trip if the consumer reads from the boundary it claims to validate." This helper
# makes that read explicit — see docs/testing/boundary-crossing-convention.md.


def _assert_reads_from_boundary(reader, expected, *, boundary, description="value"):
    """Assert ``reader()`` == ``expected`` AND that the value genuinely crossed a persistence boundary.

    ``boundary`` is a path (or iterable of paths) — the on-disk artifact the producer must have
    written (a saga tick, a persisted JSON row). Both invariants are checked BEFORE comparing values:
    the boundary artifact must exist and be non-empty. So a test that merely reads an in-memory shared
    variable cannot masquerade as a round-trip, and stubbing out the persistence write makes this fail
    at the boundary-existence check rather than passing on a stale in-memory value. ``reader`` MUST
    re-read from the boundary (e.g. ``restore(...)``), never return a producer-side variable.
    """
    boundaries = [boundary] if isinstance(boundary, (str, Path)) else list(boundary)
    for b in boundaries:
        bp = Path(b)
        assert bp.exists(), (
            f"boundary artifact {bp} was never written — nothing crossed the persistence boundary "
            "(a stubbed/absent write, or the assertion is reading an in-memory value, not disk)"
        )
        assert bp.stat().st_size > 0, (
            f"boundary artifact {bp} is empty — the producer persisted nothing"
        )
    actual = reader()
    assert actual == expected, (
        f"{description}: value re-read from the boundary {actual!r} != expected {expected!r}"
    )
    return actual


@pytest.fixture
def assert_reads_from_boundary():
    """The shared boundary-crossing assertion helper (#458 T11-F4-7)."""
    return _assert_reads_from_boundary


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
