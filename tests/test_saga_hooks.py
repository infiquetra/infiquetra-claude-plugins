"""Lease lifecycle and mutation-hook contracts for Saga (#356, U2)."""

from __future__ import annotations

import importlib.util
import json
import os
import subprocess
import sys
from pathlib import Path
from types import ModuleType
from typing import Any, cast

import pytest

ROOT = Path(__file__).parent.parent
SAGA = ROOT / "plugins" / "saga"
LIFECYCLE_HOOK = SAGA / "hooks" / "lease_lifecycle_hook.py"
MUTATION_HOOK = SAGA / "hooks" / "lease_mutation_hook.py"
BROKER_PATH = (
    ROOT / "plugins" / "fleet-core" / "scripts" / "fleet_commons" / "lease_broker.py"
)
POLICY_PATH = (
    ROOT / "plugins" / "fleet-core" / "scripts" / "fleet_commons" / "concurrency_policy.py"
)
HOOKS_JSON = SAGA / "hooks" / "hooks.json"


def _load(path: Path, name: str) -> ModuleType:
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


B = _load(BROKER_PATH, "saga_hook_broker_under_test")
P = _load(POLICY_PATH, "saga_hook_policy_under_test")


def _environment(authority: Path, **overrides: str) -> dict[str, str]:
    result = dict(os.environ)
    result.update(
        {
            "INFIQUETRA_FLEET_STATE_DIR": str(authority),
            "INFIQUETRA_FLEET_SESSION_LIMIT": "3",
            "INFIQUETRA_FLEET_AGGREGATE_LIMIT": "7",
            "INFIQUETRA_FLEET_CLAIM_TTL_SECONDS": "30",
            "INFIQUETRA_FLEET_TTL_SECONDS": "300",
        }
    )
    result.update(overrides)
    return result


def _run_hook(
    path: Path,
    payload: dict[str, Any] | bytes,
    *,
    cwd: Path,
    environment: dict[str, str],
) -> subprocess.CompletedProcess[str]:
    encoded = payload if isinstance(payload, bytes) else json.dumps(payload).encode()
    return _run_hook_text(path, encoded, cwd=cwd, environment=environment)


def _run_hook_text(
    path: Path, payload: bytes, *, cwd: Path, environment: dict[str, str]
) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(path)],
        cwd=cwd,
        env=environment,
        input=payload.decode("utf-8", errors="replace"),
        capture_output=True,
        check=False,
        text=True,
    )


def _spawn_payload(cwd: Path, tool: str, *, session: str = "session") -> dict[str, Any]:
    return {
        "hook_event_name": "PreToolUse",
        "session_id": session,
        "cwd": str(cwd),
        "tool_name": "Agent",
        "tool_use_id": tool,
        "tool_input": {"subagent_type": "worker"},
    }


def _start_payload(cwd: Path, child: str, *, session: str = "session") -> dict[str, Any]:
    return {
        "hook_event_name": "SubagentStart",
        "session_id": session,
        "cwd": str(cwd),
        "agent_id": child,
        "agent_type": "worker",
    }


def _parent_payload(cwd: Path, tool: str, *, failure: bool = False) -> dict[str, Any]:
    return {
        "hook_event_name": "PostToolUseFailure" if failure else "PostToolUse",
        "session_id": "session",
        "cwd": str(cwd),
        "tool_name": "Agent",
        "tool_use_id": tool,
        "tool_input": {"subagent_type": "worker"},
    }


def _stop_payload(cwd: Path, child: str) -> dict[str, Any]:
    return {
        "hook_event_name": "SubagentStop",
        "session_id": "session",
        "cwd": str(cwd),
        "agent_id": child,
        "agent_type": "worker",
    }


def _mutation_payload(cwd: Path, *, child: str | None, tool: str = "Edit") -> dict[str, Any]:
    payload: dict[str, Any] = {
        "hook_event_name": "PreToolUse",
        "session_id": "session",
        "cwd": str(cwd),
        "tool_name": tool,
        "tool_input": (
            {"command": "git status --short"}
            if tool == "Bash"
            else {"file_path": str(cwd / "example.txt")}
        ),
    }
    if child is not None:
        payload["agent_id"] = child
    return payload


def _broker(authority: Path) -> Any:
    return B.LeaseBroker(authority)


def _leases(authority: Path) -> list[dict[str, Any]]:
    return cast(list[dict[str, Any]], _broker(authority).inspect()["leases"])


def test_reserve_before_call_and_cross_ordered_same_type_claims(tmp_path: Path) -> None:
    authority = tmp_path / "authority"
    env = _environment(authority)
    first = _run_hook(LIFECYCLE_HOOK, _spawn_payload(tmp_path, "tool-1"), cwd=tmp_path, environment=env)
    second = _run_hook(LIFECYCLE_HOOK, _spawn_payload(tmp_path, "tool-2"), cwd=tmp_path, environment=env)
    assert first.returncode == second.returncode == 0
    assert {lease["tool_use_id"] for lease in _leases(authority)} == {"tool-1", "tool-2"}

    # SubagentStart has no parent tool id. Serialized oldest-compatible claims are safe.
    start_b = _run_hook(LIFECYCLE_HOOK, _start_payload(tmp_path, "child-b"), cwd=tmp_path, environment=env)
    start_a = _run_hook(LIFECYCLE_HOOK, _start_payload(tmp_path, "child-a"), cwd=tmp_path, environment=env)
    assert start_b.returncode == start_a.returncode == 0
    by_child = {lease["agent_id"]: lease for lease in _leases(authority)}
    assert by_child["child-b"]["tool_use_id"] == "tool-1"
    assert by_child["child-a"]["tool_use_id"] == "tool-2"
    assert by_child["child-b"]["resource_ref"]["worktree_root"] == str(tmp_path.resolve())


def test_replayed_pretool_and_start_are_idempotent(tmp_path: Path) -> None:
    authority = tmp_path / "authority"
    env = _environment(authority)
    spawn = _spawn_payload(tmp_path, "tool-1")
    assert _run_hook(LIFECYCLE_HOOK, spawn, cwd=tmp_path, environment=env).returncode == 0
    assert _run_hook(LIFECYCLE_HOOK, spawn, cwd=tmp_path, environment=env).returncode == 0
    assert len(_leases(authority)) == 1
    start = _start_payload(tmp_path, "child")
    assert _run_hook(LIFECYCLE_HOOK, start, cwd=tmp_path, environment=env).returncode == 0
    assert _run_hook(LIFECYCLE_HOOK, start, cwd=tmp_path, environment=env).returncode == 0
    assert len(_leases(authority)) == 1


def test_capacity_refusal_blocks_agent_tool_before_spawn(tmp_path: Path) -> None:
    authority = tmp_path / "authority"
    env = _environment(
        authority,
        INFIQUETRA_FLEET_SESSION_LIMIT="1",
        INFIQUETRA_FLEET_AGGREGATE_LIMIT="1",
    )
    first = _run_hook(LIFECYCLE_HOOK, _spawn_payload(tmp_path, "tool-1"), cwd=tmp_path, environment=env)
    refused = _run_hook(
        LIFECYCLE_HOOK,
        _spawn_payload(tmp_path, "tool-2", session="other"),
        cwd=tmp_path,
        environment=env,
    )
    assert first.returncode == 0
    assert refused.returncode == 2
    assert "reservation refused before spawn" in refused.stderr
    assert len(_leases(authority)) == 1


def test_missing_reservation_at_subagent_start_arms_no_implicit_grant(tmp_path: Path) -> None:
    authority = tmp_path / "authority"
    result = _run_hook(
        LIFECYCLE_HOOK,
        _start_payload(tmp_path, "orphan"),
        cwd=tmp_path,
        environment=_environment(authority),
    )
    assert result.returncode == 0  # SubagentStart cannot block after creation.
    assert "No live fleet lease was bound" in result.stdout
    assert _leases(authority) == []


@pytest.mark.parametrize("tool", ["Edit", "Bash", "Write", "MultiEdit", "NotebookEdit"])
def test_bound_child_mutation_passes_and_root_is_unchanged(tmp_path: Path, tool: str) -> None:
    authority = tmp_path / "authority"
    env = _environment(authority)
    root_authority = tmp_path / "root-unused"
    root_result = _run_hook(
        MUTATION_HOOK,
        _mutation_payload(tmp_path, child=None, tool=tool),
        cwd=tmp_path,
        environment=_environment(root_authority),
    )
    assert root_result.returncode == 0
    assert not root_authority.exists()

    _run_hook(LIFECYCLE_HOOK, _spawn_payload(tmp_path, "tool"), cwd=tmp_path, environment=env)
    _run_hook(LIFECYCLE_HOOK, _start_payload(tmp_path, "child"), cwd=tmp_path, environment=env)
    child_result = _run_hook(
        MUTATION_HOOK,
        _mutation_payload(tmp_path, child="child", tool=tool),
        cwd=tmp_path,
        environment=env,
    )
    assert child_result.returncode == 0, child_result.stderr


def test_missing_expired_and_superseded_child_authority_block_mutation(tmp_path: Path) -> None:
    authority = tmp_path / "authority"
    env = _environment(authority)
    missing = _run_hook(
        MUTATION_HOOK,
        _mutation_payload(tmp_path, child="missing"),
        cwd=tmp_path,
        environment=env,
    )
    assert missing.returncode == 2
    assert "no fleet lease is bound" in missing.stderr

    _run_hook(LIFECYCLE_HOOK, _spawn_payload(tmp_path, "tool"), cwd=tmp_path, environment=env)
    _run_hook(LIFECYCLE_HOOK, _start_payload(tmp_path, "child"), cwd=tmp_path, environment=env)
    raw = json.loads((authority / B.REGISTRY_NAME).read_text(encoding="utf-8"))
    only = next(iter(raw["leases"].values()))
    only["renewed_monotonic_ns"] = 0
    (authority / B.REGISTRY_NAME).write_text(json.dumps(raw), encoding="utf-8")
    os.chmod(authority / B.REGISTRY_NAME, 0o600)
    expired = _run_hook(
        MUTATION_HOOK,
        _mutation_payload(tmp_path, child="child", tool="Bash"),
        cwd=tmp_path,
        environment=env,
    )
    assert expired.returncode == 2
    assert "expired" in expired.stderr

    # A fresh retry for the exact logical resource becomes the durable head.
    existing = _broker(authority).inspect()["leases"][0]
    limits = P.AdmissionLimits()
    retry = _broker(authority).acquire_agent(
        owner_id="retry-owner",
        session_id="retry-session",
        policy_sha256=limits.policy_sha256(),
        session_limit=limits.max_concurrent,
        aggregate_limit=limits.aggregate_max_concurrent,
        mutation="read-write",
        resource_ref=existing["resource_ref"],
        agent_id="fresh-child",
    )
    stale = _run_hook(
        MUTATION_HOOK,
        _mutation_payload(tmp_path, child="child"),
        cwd=tmp_path,
        environment=env,
    )
    fresh = _run_hook(
        MUTATION_HOOK,
        _mutation_payload(tmp_path, child="fresh-child"),
        cwd=tmp_path,
        environment=env,
    )
    assert stale.returncode == 2
    assert fresh.returncode == 0
    assert _broker(authority).verify(retry.resource_ref, retry.token).agent_id == "fresh-child"


@pytest.mark.parametrize("first_signal", ["parent", "child"])
def test_both_lifecycle_signals_are_required_in_either_order(
    tmp_path: Path, first_signal: str
) -> None:
    authority = tmp_path / "authority"
    env = _environment(authority)
    _run_hook(LIFECYCLE_HOOK, _spawn_payload(tmp_path, "tool"), cwd=tmp_path, environment=env)
    _run_hook(LIFECYCLE_HOOK, _start_payload(tmp_path, "child"), cwd=tmp_path, environment=env)
    first = _parent_payload(tmp_path, "tool") if first_signal == "parent" else _stop_payload(tmp_path, "child")
    second = _stop_payload(tmp_path, "child") if first_signal == "parent" else _parent_payload(tmp_path, "tool")
    assert _run_hook(LIFECYCLE_HOOK, first, cwd=tmp_path, environment=env).returncode == 0
    assert len(_leases(authority)) == 1
    assert _run_hook(LIFECYCLE_HOOK, second, cwd=tmp_path, environment=env).returncode == 0
    assert _leases(authority) == []


def test_unclaimed_posttool_failure_releases_provisional_slot(tmp_path: Path) -> None:
    authority = tmp_path / "authority"
    env = _environment(authority)
    _run_hook(LIFECYCLE_HOOK, _spawn_payload(tmp_path, "tool"), cwd=tmp_path, environment=env)
    result = _run_hook(
        LIFECYCLE_HOOK,
        _parent_payload(tmp_path, "tool", failure=True),
        cwd=tmp_path,
        environment=env,
    )
    assert result.returncode == 0
    assert _leases(authority) == []


def _commands(entries: list[dict[str, Any]], matcher: str | None = None) -> list[str]:
    result: list[str] = []
    for entry in entries:
        if matcher is not None and entry.get("matcher") != matcher:
            continue
        result.extend(hook["command"] for hook in entry.get("hooks", []))
    return result


def test_hooks_json_arms_every_required_lifecycle_seam() -> None:
    events = json.loads(HOOKS_JSON.read_text(encoding="utf-8"))["hooks"]
    assert any(
        "lease_lifecycle_hook.py" in command
        for command in _commands(events["PreToolUse"], "Agent|Task")
    )
    assert any(
        "lease_mutation_hook.py" in command
        for command in _commands(events["PreToolUse"], "Bash|Write|Edit|MultiEdit|NotebookEdit")
    )
    assert any("lease_lifecycle_hook.py" in command for command in _commands(events["SubagentStart"]))
    assert any("lease_lifecycle_hook.py" in command for command in _commands(events["SubagentStop"]))
    assert any(
        "lease_lifecycle_hook.py" in command
        for command in _commands(events["PostToolUse"], "Agent|Task")
    )
    assert any(
        "lease_lifecycle_hook.py" in command
        for command in _commands(events["PostToolUseFailure"], "Agent|Task")
    )
