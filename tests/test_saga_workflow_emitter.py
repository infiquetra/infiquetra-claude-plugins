"""Driver-owned Workflow batch admission contracts (#356, U3)."""

from __future__ import annotations

import importlib.util
import json
import os
import sys
from pathlib import Path
from types import ModuleType
from typing import Any, cast

import pytest

ROOT = Path(__file__).parent.parent
SCRIPTS = ROOT / "plugins" / "saga" / "scripts"
sys.path.insert(0, str(SCRIPTS))


def _load(path: Path, name: str) -> ModuleType:
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


ES = _load(SCRIPTS / "execution_spec.py", "workflow_execution_spec_under_test")
W = _load(SCRIPTS / "workflow_emitter.py", "workflow_emitter_under_test")
A = W.lease_broker
B = A.authority
P = A.concurrency_policy


def _spec() -> Any:
    return ES.ExecutionSpec.from_dict(
        {
            "name": "batch-demo",
            "description": "two workers with verifier panels",
            "units": [
                {
                    "unit_id": "U1",
                    "label": "first",
                    "tier": {"model": "sonnet", "effort": "high"},
                    "prompt": "implement first",
                    "verify": {"n": 2, "pass_rule": "majority"},
                },
                {
                    "unit_id": "U2",
                    "label": "second",
                    "tier": {"model": "sonnet", "effort": "high"},
                    "prompt": "implement second",
                    "verify": {"n": 2, "pass_rule": "majority"},
                },
            ],
        }
    )


def _metadata(invocation: str = "invocation-1") -> dict[str, Any]:
    return cast(
        dict[str, Any],
        ES.workflow_lease_metadata(_spec(), invocation_id=invocation, environment={}),
    )


def _environment(authority: Path, metadata: dict[str, Any]) -> dict[str, str]:
    result = dict(os.environ)
    result.update(
        {
            A.STATE_ENV: str(authority),
            A.SESSION_LIMIT_ENV: str(metadata["session_limit"]),
            A.AGGREGATE_LIMIT_ENV: str(metadata["aggregate_limit"]),
            A.POLICY_SHA256_ENV: str(metadata["policy_sha256"]),
            A.MUTATION_ENV: str(metadata["mutation"]),
            A.CLAIM_TTL_SECONDS_ENV: str(metadata["claim_ttl_seconds"]),
            A.TTL_SECONDS_ENV: str(metadata["execution_ttl_seconds"]),
            A.BATCH_ID_ENV: str(metadata["batch_id"]),
        }
    )
    return result


def _spawn(cwd: Path, tool: str) -> dict[str, Any]:
    return {
        "hook_event_name": "PreToolUse",
        "session_id": "session",
        "cwd": str(cwd),
        "tool_name": "Agent",
        "tool_use_id": tool,
        "tool_input": {"subagent_type": "reviewer"},
    }


def _start(cwd: Path, child: str) -> dict[str, Any]:
    return {
        "hook_event_name": "SubagentStart",
        "session_id": "session",
        "cwd": str(cwd),
        "agent_id": child,
        "agent_type": "reviewer",
    }


def test_exact_maximum_wave_width_and_stable_identity() -> None:
    first = _metadata("same-run")
    replay = _metadata("same-run")
    later = _metadata("later-run")
    assert first == replay
    assert first["reservation_width"] == 4  # two workers x two simultaneous verifiers
    assert first["session_limit"] == 4
    assert first["aggregate_limit"] == 7
    assert first["slots"] == ["slot-001", "slot-002", "slot-003", "slot-004"]
    assert first["workload_unit_ids"] == ["U1", "U2"]
    assert first["batch_id"] != later["batch_id"]
    assert first["policy_sha256"] == P.AdmissionLimits().policy_sha256()


def test_emitted_script_exports_template_but_gets_no_filesystem_authority() -> None:
    spec = _spec()
    script = ES.emit_workflow_script(spec, environment={})
    template = ES.workflow_lease_metadata(spec, environment={})
    assert (
        "export const lease = " + json.dumps(template, sort_keys=True, separators=(",", ":"))
        in script
    )
    assert template["batch_id"] is None
    assert template["generated_runtime_filesystem_access"] is False
    assert "lease_broker.py" not in script
    assert "workflow_emitter.py" not in script
    assert "registry.json" not in script


def test_lease_cli_exports_launch_ready_metadata(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    spec_path = tmp_path / "spec.json"
    spec_path.write_text(json.dumps(_spec().to_dict()), encoding="utf-8")
    assert (
        ES.main(
            [
                "lease",
                str(spec_path),
                "--invocation-id",
                "cli-run",
            ]
        )
        == 0
    )
    metadata = json.loads(capsys.readouterr().out)
    assert W.validate_metadata(metadata)["batch_id"].startswith("workflow:")


def test_reserve_attest_replay_and_release_are_driver_owned(tmp_path: Path) -> None:
    metadata = _metadata()
    authority = tmp_path / "authority"
    env = _environment(authority, metadata)
    first = W.reserve(metadata, session_id="session", environment=env)
    replay = W.reserve(metadata, session_id="session", environment=env)
    assert replay == first
    assert len(first["lease_ids"]) == metadata["reservation_width"]
    assert first["root_sha256"] == B.LeaseBroker(authority).root_sha256
    attestation = W.attest(metadata, session_id="session", environment=env)
    assert attestation["launch_authorized"] is True
    assert attestation["reservation_width"] == 4
    assert W.release(metadata, session_id="session", environment=env) == tuple(
        sorted(first["lease_ids"])
    )
    assert B.LeaseBroker(authority).inspect()["leases"] == []


def test_attestation_rejects_launch_without_full_reservation(tmp_path: Path) -> None:
    metadata = _metadata()
    env = _environment(tmp_path / "authority", metadata)
    with pytest.raises(W.WorkflowLeaseContractError, match="0 of 4 required slots"):
        W.attest(metadata, session_id="session", environment=env)


def test_batch_reservation_is_all_or_none_against_live_fleet_capacity(tmp_path: Path) -> None:
    metadata = _metadata()
    authority = tmp_path / "authority"
    env = _environment(authority, metadata)
    broker = B.LeaseBroker(authority)
    limits = P.AdmissionLimits()
    for index in range(4):
        broker.acquire_agent(
            owner_id=f"existing-{index}",
            session_id=f"other-{index}",
            policy_sha256=limits.policy_sha256(),
            session_limit=3,
            aggregate_limit=7,
            mutation="read-write",
        )
    with pytest.raises(B.CapacityExhaustedError):
        W.reserve(metadata, session_id="session", environment=env)
    snapshot = broker.inspect()["leases"]
    assert len(snapshot) == 4
    assert all(lease["batch_id"] is None for lease in snapshot)


def test_pretool_claim_collection_recycles_slot_and_renews_batch(tmp_path: Path) -> None:
    metadata = _metadata()
    authority = tmp_path / "authority"
    env = _environment(authority, metadata)
    W.reserve(metadata, session_id="session", environment=env)
    hook_env = {key: value for key, value in env.items() if key != A.BATCH_ID_ENV}
    prepared = A.reserve_hook_agent(_spawn(tmp_path, "tool-1"), hook_env)
    assert prepared.batch_id == metadata["batch_id"]
    claimed = A.claim_hook_agent(_start(tmp_path, "child-1"), hook_env)
    assert claimed.lease_id == prepared.lease_id
    assert claimed.agent_id == "child-1"
    assert claimed.resource_ref["logical_unit_id"] == "tool-1"

    # SubagentStop alone retains the bound slot. Parent collection recycles it and renews all slots.
    assert A.record_hook_terminal(_start(tmp_path, "child-1"), hook_env) is True
    before = B.LeaseBroker(authority).inspect()["leases"]
    assert any(lease["agent_id"] == "child-1" for lease in before)
    A.record_hook_parent(
        _spawn(tmp_path, "tool-1") | {"hook_event_name": "PostToolUse"}, hook_env
    )
    after = B.LeaseBroker(authority).inspect()["leases"]
    assert len(after) == metadata["reservation_width"]
    assert all(lease["derived_state"] == "live" for lease in after)
    assert all(lease["agent_id"] is None for lease in after)
    assert all(lease["tool_use_id"] is None for lease in after)

    # The recycled slot can authorize a later wave, but only after another PreToolUse assignment.
    second = A.reserve_hook_agent(_spawn(tmp_path, "tool-2"), hook_env)
    assert second is not None
    assert A.claim_hook_agent(_start(tmp_path, "child-2"), hook_env).agent_id == "child-2"


def test_unused_reservations_and_confirmed_children_release_after_return(tmp_path: Path) -> None:
    metadata = _metadata()
    authority = tmp_path / "authority"
    env = _environment(authority, metadata)
    receipt = W.reserve(metadata, session_id="session", environment=env)
    A.reserve_hook_agent(_spawn(tmp_path, "tool"), env)
    A.claim_hook_agent(_start(tmp_path, "child"), env)
    released = W.release(metadata, session_id="session", environment=env)
    assert set(released) == set(receipt["lease_ids"])
    assert B.LeaseBroker(authority).inspect()["leases"] == []


def test_contract_is_closed_and_rejects_filesystem_grant() -> None:
    metadata = _metadata()
    with pytest.raises(W.WorkflowLeaseContractError, match="not closed"):
        W.validate_metadata({**metadata, "registry_path": "/tmp/authority"})
    with pytest.raises(W.WorkflowLeaseContractError, match="filesystem access must be false"):
        W.validate_metadata({**metadata, "generated_runtime_filesystem_access": True})
