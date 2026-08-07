"""Driver-owned Workflow contract after the lease broker's retirement (#356, #677/U4).

The broker-lifecycle suite that lived here retired with its mechanisms (#677/U4): the
replay/release driver-ownership test re-keyed onto the retired emission, and
``test_attestation_rejects_launch_without_full_reservation``,
``test_batch_reservation_is_all_or_none_against_live_fleet_capacity``,
``test_pretool_claim_collection_recycles_slot_and_renews_batch``,
``test_prepare_batch_call_route_forwards_declared_isolation``,
``test_unused_reservations_and_confirmed_children_release_after_return``, and
``test_workflow_child_binds_without_pretool_stamp_and_waves_recycle`` extinct — admission,
capacity, claim/recycle/renew, and hook binding were broker concepts with no broker-free
successor (plan #677 KTD4: no batch lease exists to renew). The surviving pins hold the
frozen contract shape, the emitted script's broker isolation, and the retired CLI behavior.
"""

from __future__ import annotations

import importlib.util
import json
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
    # The policy-digest equality pin retired with broker admission (#677/U4): it asserted the
    # metadata against the broker-era AdmissionLimits; the closed-shape test below still
    # requires the field.


def test_emitted_script_carries_no_lease_contract_and_no_filesystem_authority() -> None:
    """#671: the reservation contract is driver-owned, so none of it is baked into the script.

    It never could have been acted on -- a workflow script has no filesystem or Node API access,
    so the generated code cannot reach the broker. The contract itself is unchanged and still
    reaches ``/work`` through ``workflow_lease_metadata`` and the ``lease`` CLI.
    """

    spec = _spec()
    script = ES.emit_workflow_script(spec, environment={})
    assert "const lease" not in script
    assert "lease_broker.py" not in script
    assert "workflow_emitter.py" not in script
    assert "registry.json" not in script

    template = ES.workflow_lease_metadata(spec, environment={})
    assert template["batch_id"] is None
    assert template["generated_runtime_filesystem_access"] is False


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


def test_reserve_attest_release_complete_with_no_batch_lease() -> None:
    """#677/U4: the commands complete with no batch lease — admission retired, not rebuilt."""

    metadata = _metadata()
    receipt = W.reserve(metadata, session_id="session")
    assert receipt == W.reserve(metadata, session_id="session")  # retired replay is deterministic
    assert receipt["schema"] == "workflow_lease_receipt.v1"
    assert receipt["batch_id"] == metadata["batch_id"]
    assert receipt["owner_id"] == metadata["owner_id"]
    assert receipt["session_id"] == "session"
    assert receipt["reservation_width"] == metadata["reservation_width"]
    assert receipt["lease_ids"] == []
    assert "root_sha256" not in receipt  # no fleet root survives the retirement

    attestation = W.attest(metadata, session_id="session")
    assert attestation["schema"] == "workflow_lease_attestation.v1"
    assert attestation["batch_id"] == metadata["batch_id"]
    assert attestation["reservation_width"] == 0  # zero leases attested: nothing exists to attest
    assert attestation["launch_authorized"] is True

    assert W.renew(metadata) == ()  # no batch lease exists to renew (plan #677 KTD4)
    assert W.release(metadata, session_id="session") == ()


def test_contract_is_closed_and_rejects_filesystem_grant() -> None:
    metadata = _metadata()
    with pytest.raises(W.WorkflowLeaseContractError, match="not closed"):
        W.validate_metadata({**metadata, "registry_path": "/tmp/authority"})
    with pytest.raises(W.WorkflowLeaseContractError, match="filesystem access must be false"):
        W.validate_metadata({**metadata, "generated_runtime_filesystem_access": True})


def test_cli_reserve_completes_and_prints_the_retired_receipt(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    metadata_path = tmp_path / "metadata.json"
    metadata_path.write_text(json.dumps(_metadata()), encoding="utf-8")
    assert W.main(["reserve", str(metadata_path), "--session-id", "session"]) == 0
    printed = json.loads(capsys.readouterr().out)
    assert printed["schema"] == "workflow_lease_receipt.v1"
    assert printed["lease_ids"] == []


def test_cli_failure_still_halts_through_the_re_narrowed_handler(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """#677/U4: the lease exception types disappeared with the broker module, but a real failure
    still HALTs loudly — the re-narrowed handler catches the surviving
    ``WorkflowLeaseContractError``, is not bare, and was not deleted outright."""

    metadata_path = tmp_path / "metadata.json"
    metadata_path.write_text(
        json.dumps({**_metadata(), "registry_path": "/tmp/authority"}), encoding="utf-8"
    )
    with pytest.raises(SystemExit) as excinfo:
        W.main(["attest", str(metadata_path), "--session-id", "session"])
    assert excinfo.value.code == 2
    assert "HALT" in capsys.readouterr().err

    missing = tmp_path / "absent.json"
    with pytest.raises(SystemExit) as excinfo:
        W.main(["renew", str(missing)])
    assert excinfo.value.code == 2
    assert "HALT" in capsys.readouterr().err
