"""Contract tests for team-execution's lease lifecycle wrapper (#356)."""

from __future__ import annotations

import importlib.util
import sys
from dataclasses import dataclass
from pathlib import Path
from types import ModuleType, SimpleNamespace

import pytest

ROOT = Path(__file__).parent.parent
SCRIPT = (
    ROOT
    / "plugins"
    / "team-execution"
    / "skills"
    / "team-execution"
    / "scripts"
    / "lease_protocol.py"
)


def _load() -> ModuleType:
    spec = importlib.util.spec_from_file_location("team_execution_lease_protocol", SCRIPT)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


PROTOCOL = _load()


@dataclass
class FakeSweep:
    def to_dict(self) -> dict[str, object]:
        return {
            "released_agent_leases": [],
            "reaped_worktree_leases": [],
            "retained": {},
        }


class FakeBroker:
    root_sha256 = "a" * 64

    def __init__(self, leases: list[dict[str, object]]) -> None:
        self.leases = leases
        self.released: list[str] = []
        self.swept = False

    def inspect(self) -> dict[str, object]:
        return {"leases": list(self.leases)}

    def configure_session_admission(self, session_id: str, **kwargs: object) -> None:
        assert session_id == "session-1"
        assert kwargs["mutation"] == "read-write"

    def renew_session(self, session_id: str) -> tuple[SimpleNamespace, ...]:
        assert session_id == "session-1"
        return (SimpleNamespace(lease_id="lease-1"),)

    def release_session(self, session_id: str) -> tuple[str, ...]:
        assert session_id == "session-1"
        self.released.append(session_id)
        return tuple(str(lease["lease_id"]) for lease in self.leases)

    def release_session_if_terminal(
        self, session_id: str, *, terminal_agent_ids: tuple[str, ...]
    ) -> tuple[str, ...]:
        assert session_id == "session-1"
        asserted = set(terminal_agent_ids)
        unresolved = [
            str(lease["lease_id"])
            for lease in self.leases
            if lease["agent_id"] is None
            or (lease["child_terminal_at"] is None and lease["agent_id"] not in asserted)
        ]
        if unresolved:
            raise PROTOCOL.authority.LeaseOwnershipError(
                "refusing teardown until every child is terminal: " + ", ".join(unresolved)
            )
        return self.release_session(session_id)

    def sweep(self) -> FakeSweep:
        self.swept = True
        return FakeSweep()


def _lease(*, agent_id: str | None, child_terminal_at: str | None = None) -> dict[str, object]:
    return {
        "lease_id": "lease-1",
        "pool": "agent",
        "session_id": "session-1",
        "agent_id": agent_id,
        "child_terminal_at": child_terminal_at,
    }


def test_preflight_and_renew_expose_no_authority_path() -> None:
    selected = FakeBroker([])
    ready = PROTOCOL.preflight("session-1", selected=selected)
    assert ready["status"] == "ready"
    assert ready["root_sha256"] == "a" * 64
    assert "root" not in ready

    renewed = PROTOCOL.renew("session-1", selected=selected)
    assert renewed["lease_ids"] == ["lease-1"]
    assert "root" not in renewed


@pytest.mark.parametrize("version", [1, 99])
def test_preflight_rejects_lease_protocol_skew(
    monkeypatch: pytest.MonkeyPatch, version: int
) -> None:
    monkeypatch.setattr(PROTOCOL.authority, "PROTOCOL_VERSION", version)

    with pytest.raises(PROTOCOL.LeaseProtocolError, match="install/update fleet-core"):
        PROTOCOL.preflight("session-1", selected=FakeBroker([]))


def test_teardown_refuses_unclaimed_or_unconfirmed_child_without_releasing() -> None:
    for lease in (_lease(agent_id=None), _lease(agent_id="child-1")):
        selected = FakeBroker([lease])
        with pytest.raises(PROTOCOL.LeaseProtocolError, match="refusing teardown"):
            PROTOCOL.teardown("session-1", terminal_agent_ids=(), selected=selected)
        assert selected.released == []
        assert selected.swept is False


def test_teardown_accepts_persisted_or_explicit_terminal_evidence_then_sweeps() -> None:
    for lease, asserted in (
        (_lease(agent_id="child-1", child_terminal_at="2026-07-16T12:00:00Z"), ()),
        (_lease(agent_id="child-1"), ("child-1",)),
    ):
        selected = FakeBroker([lease])
        result = PROTOCOL.teardown("session-1", terminal_agent_ids=asserted, selected=selected)
        assert result["status"] == "released"
        assert result["released_lease_ids"] == ["lease-1"]
        assert selected.released == ["session-1"]
        assert selected.swept is True
