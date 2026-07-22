"""Lease lifecycle and mutation-hook contracts for Saga (#356, U2)."""

from __future__ import annotations

import importlib.util
import json
import os
import subprocess
import sys
import threading
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from types import ModuleType
from typing import Any, cast

import pytest

ROOT = Path(__file__).parent.parent
SAGA = ROOT / "plugins" / "saga"
LIFECYCLE_HOOK = SAGA / "hooks" / "lease_lifecycle_hook.py"
MUTATION_HOOK = SAGA / "hooks" / "lease_mutation_hook.py"
BROKER_PATH = ROOT / "plugins" / "fleet-core" / "scripts" / "fleet_commons" / "lease_broker.py"
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
            "INFIQUETRA_FLEET_POLICY_SHA256": P.AdmissionLimits().policy_sha256(),
            "INFIQUETRA_FLEET_MUTATION": "read-write",
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
    first = _run_hook(
        LIFECYCLE_HOOK, _spawn_payload(tmp_path, "tool-1"), cwd=tmp_path, environment=env
    )
    second = _run_hook(
        LIFECYCLE_HOOK, _spawn_payload(tmp_path, "tool-2"), cwd=tmp_path, environment=env
    )
    assert first.returncode == second.returncode == 0
    assert {lease["tool_use_id"] for lease in _leases(authority)} == {"tool-1", "tool-2"}

    # SubagentStart has no parent tool id. Serialized oldest-compatible claims are safe.
    start_b = _run_hook(
        LIFECYCLE_HOOK, _start_payload(tmp_path, "child-b"), cwd=tmp_path, environment=env
    )
    start_a = _run_hook(
        LIFECYCLE_HOOK, _start_payload(tmp_path, "child-a"), cwd=tmp_path, environment=env
    )
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


def test_delegated_parent_must_hold_current_same_session_authority(tmp_path: Path) -> None:
    authority = tmp_path / "authority"
    env = _environment(authority)
    _run_hook(
        LIFECYCLE_HOOK, _spawn_payload(tmp_path, "parent-tool"), cwd=tmp_path, environment=env
    )
    _run_hook(LIFECYCLE_HOOK, _start_payload(tmp_path, "parent"), cwd=tmp_path, environment=env)

    nested = _spawn_payload(tmp_path, "nested-tool")
    nested["agent_id"] = "parent"
    assert _run_hook(LIFECYCLE_HOOK, nested, cwd=tmp_path, environment=env).returncode == 0

    wrong_session = _spawn_payload(tmp_path, "wrong-session", session="other")
    wrong_session["agent_id"] = "parent"
    refused = _run_hook(LIFECYCLE_HOOK, wrong_session, cwd=tmp_path, environment=env)
    assert refused.returncode == 2
    assert "different session" in refused.stderr

    raw = json.loads((authority / B.REGISTRY_NAME).read_text(encoding="utf-8"))
    parent = next(lease for lease in raw["leases"].values() if lease["agent_id"] == "parent")
    parent["renewed_monotonic_ns"] = 0
    (authority / B.REGISTRY_NAME).write_text(json.dumps(raw), encoding="utf-8")
    os.chmod(authority / B.REGISTRY_NAME, 0o600)
    expired = _spawn_payload(tmp_path, "expired-parent")
    expired["agent_id"] = "parent"
    blocked = _run_hook(LIFECYCLE_HOOK, expired, cwd=tmp_path, environment=env)
    assert blocked.returncode == 2
    assert "no current spawn authority" in blocked.stderr


def test_parallel_claims_bind_each_reservation_once(tmp_path: Path) -> None:
    authority = tmp_path / "authority"
    env = _environment(authority)
    for tool in ("tool-1", "tool-2"):
        assert (
            _run_hook(
                LIFECYCLE_HOOK, _spawn_payload(tmp_path, tool), cwd=tmp_path, environment=env
            ).returncode
            == 0
        )

    barrier = threading.Barrier(2)

    def start(child: str) -> subprocess.CompletedProcess[str]:
        barrier.wait()
        return _run_hook(
            LIFECYCLE_HOOK, _start_payload(tmp_path, child), cwd=tmp_path, environment=env
        )

    with ThreadPoolExecutor(max_workers=2) as executor:
        results = list(executor.map(start, ("child-1", "child-2")))
    assert all(result.returncode == 0 for result in results)
    leases = _leases(authority)
    assert {lease["agent_id"] for lease in leases} == {"child-1", "child-2"}
    assert {lease["tool_use_id"] for lease in leases} == {"tool-1", "tool-2"}


def test_capacity_refusal_blocks_agent_tool_before_spawn(tmp_path: Path) -> None:
    authority = tmp_path / "authority"
    env = _environment(
        authority,
        INFIQUETRA_FLEET_SESSION_LIMIT="1",
        INFIQUETRA_FLEET_AGGREGATE_LIMIT="1",
    )
    first = _run_hook(
        LIFECYCLE_HOOK, _spawn_payload(tmp_path, "tool-1"), cwd=tmp_path, environment=env
    )
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


def test_normal_agent_requires_pinned_resolved_session_admission(tmp_path: Path) -> None:
    authority = tmp_path / "authority"
    env = dict(os.environ)
    env["INFIQUETRA_FLEET_STATE_DIR"] = str(authority)
    missing = _run_hook(
        LIFECYCLE_HOOK,
        _spawn_payload(tmp_path, "tool-missing"),
        cwd=tmp_path,
        environment=env,
    )
    assert missing.returncode == 2
    assert "configured resolved session snapshot" in missing.stderr

    limits = P.AdmissionLimits()
    _broker(authority).configure_session_admission(
        "session",
        policy_sha256=limits.policy_sha256(),
        session_limit=1,
        aggregate_limit=limits.aggregate_max_concurrent,
        mutation="read-write",
    )
    admitted = _run_hook(
        LIFECYCLE_HOOK,
        _spawn_payload(tmp_path, "tool-pinned"),
        cwd=tmp_path,
        environment=env,
    )
    assert admitted.returncode == 0
    assert _leases(authority)[0]["session_limit"] == 1


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


@pytest.mark.parametrize("tool", ["Edit", "Bash"])
def test_removed_bound_worktree_blocks_subsequent_mutation(tmp_path: Path, tool: str) -> None:
    authority = tmp_path / "authority"
    env = _environment(authority)
    worktree = tmp_path / "leased-worktree"
    worktree.mkdir()
    _run_hook(LIFECYCLE_HOOK, _spawn_payload(worktree, "tool"), cwd=tmp_path, environment=env)
    started = _run_hook(
        LIFECYCLE_HOOK, _start_payload(worktree, "child"), cwd=tmp_path, environment=env
    )
    assert started.returncode == 0
    worktree.rmdir()

    blocked = _run_hook(
        MUTATION_HOOK,
        _mutation_payload(worktree, child="child", tool=tool),
        cwd=tmp_path,
        environment=env,
    )
    assert blocked.returncode == 2
    assert "leased worktree is missing" in blocked.stderr


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
    first = (
        _parent_payload(tmp_path, "tool")
        if first_signal == "parent"
        else _stop_payload(tmp_path, "child")
    )
    second = (
        _stop_payload(tmp_path, "child")
        if first_signal == "parent"
        else _parent_payload(tmp_path, "tool")
    )
    assert _run_hook(LIFECYCLE_HOOK, first, cwd=tmp_path, environment=env).returncode == 0
    assert len(_leases(authority)) == 1
    assert _run_hook(LIFECYCLE_HOOK, second, cwd=tmp_path, environment=env).returncode == 0
    assert _leases(authority) == []


def test_parallel_terminal_and_parent_signals_release_exactly_once(tmp_path: Path) -> None:
    authority = tmp_path / "authority"
    env = _environment(authority)
    _run_hook(LIFECYCLE_HOOK, _spawn_payload(tmp_path, "tool"), cwd=tmp_path, environment=env)
    _run_hook(LIFECYCLE_HOOK, _start_payload(tmp_path, "child"), cwd=tmp_path, environment=env)
    barrier = threading.Barrier(2)

    def signal(payload: dict[str, Any]) -> subprocess.CompletedProcess[str]:
        barrier.wait()
        return _run_hook(LIFECYCLE_HOOK, payload, cwd=tmp_path, environment=env)

    with ThreadPoolExecutor(max_workers=2) as executor:
        futures = [
            executor.submit(signal, _parent_payload(tmp_path, "tool")),
            executor.submit(signal, _stop_payload(tmp_path, "child")),
        ]
        results = [future.result() for future in futures]
    assert all(result.returncode == 0 for result in results)
    assert _leases(authority) == []
    json.loads((authority / B.REGISTRY_NAME).read_text(encoding="utf-8"))


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
    assert any(
        "lease_lifecycle_hook.py" in command for command in _commands(events["SubagentStart"])
    )
    assert any(
        "lease_lifecycle_hook.py" in command for command in _commands(events["SubagentStop"])
    )
    assert any(
        "lease_lifecycle_hook.py" in command
        for command in _commands(events["PostToolUse"], "Agent|Task")
    )
    assert any(
        "lease_lifecycle_hook.py" in command
        for command in _commands(events["PostToolUseFailure"], "Agent|Task")
    )


@pytest.mark.parametrize("version", [1, 99])
def test_saga_adapter_rejects_lease_protocol_skew(
    monkeypatch: pytest.MonkeyPatch, version: int
) -> None:
    scripts = SAGA / "scripts"
    if str(scripts) not in sys.path:
        sys.path.insert(0, str(scripts))
    adapter = _load(scripts / "lease_broker.py", "saga_lease_adapter_skew_test")
    monkeypatch.setattr(adapter.authority, "PROTOCOL_VERSION", version)

    with pytest.raises(adapter.HookInputError, match="install/update fleet-core"):
        adapter.ensure_protocol()


def test_saga_lease_cli_requires_exact_token_and_session_scoped_owner_release() -> None:
    scripts = SAGA / "scripts"
    if str(scripts) not in sys.path:
        sys.path.insert(0, str(scripts))
    adapter = _load(scripts / "lease_broker.py", "saga_lease_adapter_cli_contract_test")
    parser = adapter._build_parser()

    for argv in (
        ["renew", "lease-id"],
        ["release", "lease-id"],
        ["release-owner", "owner-id"],
    ):
        with pytest.raises(SystemExit) as caught:
            parser.parse_args(argv)
        assert caught.value.code == 2

    renewed = parser.parse_args(
        [
            "renew",
            "lease-id",
            "--broker-epoch",
            "00000000-0000-0000-0000-000000000001",
            "--fencing-sequence",
            "7",
        ]
    )
    assert renewed.fencing_sequence == 7
    released_owner = parser.parse_args(["release-owner", "owner-id", "--session-id", "session-id"])
    assert released_owner.session_id == "session-id"


# --------------------------------------------------------------- team teardown hook (#358)

TEAM_TEARDOWN_HOOK = SAGA / "hooks" / "team_teardown_hook.py"


def _teardown_modules() -> tuple[ModuleType, ModuleType]:
    scripts = SAGA / "scripts"
    if str(scripts) not in sys.path:
        sys.path.insert(0, str(scripts))
    ledger_module = _load(scripts / "run_ledger.py", "run_ledger_for_teardown_hook_tests")
    teardown_module = _load(scripts / "team_teardown.py", "team_teardown_for_hook_tests")
    return ledger_module, teardown_module


def _git_repo(tmp_path: Path) -> Path:
    repo = tmp_path / "repo"
    repo.mkdir()
    subprocess.run(
        ["git", "init", "--quiet", str(repo)], check=True, capture_output=True, timeout=30
    )
    return repo


def test_session_end_records_request_only_for_this_sessions_open_runs(tmp_path: Path) -> None:
    ledger_module, teardown_module = _teardown_modules()
    authority = tmp_path / "authority"
    repo = _git_repo(tmp_path)
    broker = B.LeaseBroker(authority)
    ledger = ledger_module.RunLedger.resolve(repo)
    teardown_module.open_run(
        ledger,
        broker,
        subplot_id="hook-test",
        session_id="session-mine",
        at="2026-07-18T14:00:00Z",
        team_run_id="team-run-mine",
    )
    teardown_module.open_run(
        ledger,
        broker,
        subplot_id="hook-test",
        session_id="session-other",
        at="2026-07-18T14:00:00Z",
        team_run_id="team-run-other",
    )

    result = _run_hook(
        TEAM_TEARDOWN_HOOK,
        {"hook_event_name": "SessionEnd", "session_id": "session-mine", "cwd": str(repo)},
        cwd=repo,
        environment=_environment(authority),
    )
    assert result.returncode == 0
    assert "request evidence only" in result.stderr
    facts = ledger_module.read_facts(ledger)
    intents = {f["team_run_id"] for f in facts if f.get("event") == "teardown-intent"}
    assert intents == {"team-run-mine"}
    assert broker.inspect_owner_admission("team-run-mine") is not None
    assert broker.inspect_owner_admission("team-run-other") is None


def test_session_start_recovers_expired_dead_owner_run(tmp_path: Path) -> None:
    import time as _time

    ledger_module, teardown_module = _teardown_modules()
    authority = tmp_path / "authority"
    repo = _git_repo(tmp_path)
    broker = B.LeaseBroker(authority)
    ledger = ledger_module.RunLedger.resolve(repo)
    teardown_module.open_run(
        ledger,
        broker,
        subplot_id="hook-test",
        session_id="session-crashed",
        at="2026-07-18T14:00:00Z",
        team_run_id="team-run-crashed",
    )
    limits = P.AdmissionLimits()
    broker.acquire_agent(
        owner_id="team-run-crashed",
        session_id="session-crashed",
        policy_sha256=limits.policy_sha256(),
        session_limit=limits.max_concurrent,
        aggregate_limit=limits.aggregate_max_concurrent,
        mutation="read-write",
        ttl_seconds=1,
        resource_ref={"logical_unit_id": "crashed-unit"},
        agent_type="worker",
    )
    _time.sleep(1.2)  # the crashed coordinator's lease derives expired

    result = _run_hook(
        TEAM_TEARDOWN_HOOK,
        {
            "hook_event_name": "SessionStart",
            "source": "startup",
            "session_id": "session-new",
            "cwd": str(repo),
        },
        cwd=repo,
        environment=_environment(authority),
    )
    assert result.returncode == 0
    facts = ledger_module.read_facts(ledger)
    events = {f["event"] for f in facts if f.get("team_run_id") == "team-run-crashed"}
    assert "teardown-complete" in events
    assert "recovery-observation" in events
    remaining = [
        item for item in broker.inspect()["leases"] if item["owner_id"] == "team-run-crashed"
    ]
    assert remaining == []


def test_session_start_retains_live_owner_runs(tmp_path: Path) -> None:
    ledger_module, teardown_module = _teardown_modules()
    authority = tmp_path / "authority"
    repo = _git_repo(tmp_path)
    broker = B.LeaseBroker(authority)
    ledger = ledger_module.RunLedger.resolve(repo)
    teardown_module.open_run(
        ledger,
        broker,
        subplot_id="hook-test",
        session_id="session-live",
        at="2026-07-18T14:00:00Z",
        team_run_id="team-run-live",
    )
    limits = P.AdmissionLimits()
    lease = broker.acquire_agent(
        owner_id="team-run-live",
        session_id="session-live",
        policy_sha256=limits.policy_sha256(),
        session_limit=limits.max_concurrent,
        aggregate_limit=limits.aggregate_max_concurrent,
        mutation="read-write",
        ttl_seconds=600,
        resource_ref={"logical_unit_id": "live-unit"},
        agent_type="worker",
    )

    result = _run_hook(
        TEAM_TEARDOWN_HOOK,
        {
            "hook_event_name": "SessionStart",
            "source": "resume",
            "session_id": "session-new",
            "cwd": str(repo),
        },
        cwd=repo,
        environment=_environment(authority),
    )
    assert result.returncode == 0
    facts = ledger_module.read_facts(ledger)
    events = {f["event"] for f in facts if f.get("team_run_id") == "team-run-live"}
    assert "teardown-complete" not in events
    assert "recovery-observation" in events  # honesty: observed, nothing safe to reclaim
    assert any(item["lease_id"] == lease.lease_id for item in broker.inspect()["leases"])


def test_teardown_hook_is_visible_and_nonblocking_on_bad_input(tmp_path: Path) -> None:
    repo = _git_repo(tmp_path)
    malformed = _run_hook_text(
        TEAM_TEARDOWN_HOOK,
        b"not json at all",
        cwd=repo,
        environment=_environment(tmp_path / "authority"),
    )
    assert malformed.returncode == 0
    assert "malformed hook payload" in malformed.stderr

    plain_dir = tmp_path / "not-a-repo"
    plain_dir.mkdir()
    non_git = _run_hook(
        TEAM_TEARDOWN_HOOK,
        {"hook_event_name": "SessionEnd", "session_id": "s", "cwd": str(plain_dir)},
        cwd=plain_dir,
        environment=_environment(tmp_path / "authority"),
    )
    assert non_git.returncode == 0
    assert "teardown-complete" not in non_git.stdout


def test_hooks_json_arms_bounded_teardown_recovery_seams() -> None:
    events = json.loads(HOOKS_JSON.read_text(encoding="utf-8"))["hooks"]
    session_end = [
        hook
        for group in events["SessionEnd"]
        for hook in group["hooks"]
        if "team_teardown_hook.py" in hook["command"]
    ]
    assert session_end and session_end[0]["timeout"] == 5
    session_start = [
        hook
        for group in events["SessionStart"]
        if group.get("matcher") == "startup|resume"
        for hook in group["hooks"]
        if "team_teardown_hook.py" in hook["command"]
    ]
    assert session_start and session_start[0]["timeout"] == 15


def test_kill_switch_off_bypasses_both_hooks_and_touches_no_state(tmp_path: Path) -> None:
    """#615 R7: the exact value "off" disarms both hooks loudly and reads no broker state."""

    authority = tmp_path / "state"
    env = _environment(authority, INFIQUETRA_FLEET_LEASE_ENFORCEMENT="off")
    mutation = _run_hook(
        MUTATION_HOOK, _mutation_payload(tmp_path, child="ghost"), cwd=tmp_path, environment=env
    )
    assert mutation.returncode == 0
    assert "INFIQUETRA_FLEET_LEASE_ENFORCEMENT=off" in mutation.stderr
    assert "DISABLED" in mutation.stderr
    lifecycle = _run_hook(
        LIFECYCLE_HOOK, _spawn_payload(tmp_path, "tool-1"), cwd=tmp_path, environment=env
    )
    assert lifecycle.returncode == 0
    assert "DISABLED" in lifecycle.stderr
    assert not authority.exists()


@pytest.mark.parametrize("value", ["", "On", "false", "OFF", "disable"])
def test_kill_switch_unrecognized_values_stay_armed(tmp_path: Path, value: str) -> None:
    """#615 R7 fail-safe direction: anything but the exact string "off" keeps enforcement."""

    authority = tmp_path / "state"
    env = _environment(authority, INFIQUETRA_FLEET_LEASE_ENFORCEMENT=value)
    result = _run_hook(
        MUTATION_HOOK, _mutation_payload(tmp_path, child="ghost"), cwd=tmp_path, environment=env
    )
    assert result.returncode == 2
    assert "HALT" in result.stderr
