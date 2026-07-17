#!/usr/bin/env python3
"""Driver-side Workflow lease reservation protocol (#356).

Generated JavaScript and children never receive registry access. The trusted root driver materializes
the metadata, reserves before ``Workflow(...)``, attests the full batch, renews at collection seams,
and releases only after authoritative return or cancellation.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any, NoReturn, cast

import lease_broker

SCHEMA = "workflow_lease_reservation.v1"
_KEYS = frozenset(
    {
        "schema",
        "batch_id",
        "owner_id",
        "invocation_id",
        "spec_sha256",
        "reservation_width",
        "session_limit",
        "aggregate_limit",
        "policy_sha256",
        "mutation",
        "claim_ttl_seconds",
        "execution_ttl_seconds",
        "slots",
        "workload_unit_ids",
        "requires_prelaunch_reservation",
        "generated_runtime_filesystem_access",
    }
)


class WorkflowLeaseContractError(ValueError):
    """Driver metadata is incomplete, malformed, or not launch-ready."""


def _text(value: Any, name: str) -> str:
    if not isinstance(value, str) or not value:
        raise WorkflowLeaseContractError(f"{name} must be a non-empty string")
    return value


def _positive(value: Any, name: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value < 1:
        raise WorkflowLeaseContractError(f"{name} must be a positive integer")
    return value


def validate_metadata(value: Mapping[str, Any], *, launch_ready: bool = True) -> dict[str, Any]:
    """Validate the closed metadata shape and return a plain canonical mapping."""

    data = dict(value)
    unknown = sorted(set(data) - _KEYS)
    missing = sorted(_KEYS - set(data))
    if unknown or missing:
        raise WorkflowLeaseContractError(
            f"workflow lease metadata is not closed; unknown={unknown}, missing={missing}"
        )
    if data["schema"] != SCHEMA:
        raise WorkflowLeaseContractError(f"schema must be {SCHEMA!r}")
    width = _positive(data["reservation_width"], "reservation_width")
    session_limit = _positive(data["session_limit"], "session_limit")
    aggregate_limit = _positive(data["aggregate_limit"], "aggregate_limit")
    if width != session_limit or width > aggregate_limit:
        raise WorkflowLeaseContractError(
            "reservation_width must equal session_limit and not exceed aggregate_limit"
        )
    slots = data["slots"]
    if not isinstance(slots, list) or slots != [
        f"slot-{index:03d}" for index in range(1, width + 1)
    ]:
        raise WorkflowLeaseContractError("slots must enumerate the exact reservation width")
    unit_ids = data["workload_unit_ids"]
    if (
        not isinstance(unit_ids, list)
        or not unit_ids
        or any(not isinstance(item, str) or not item for item in unit_ids)
    ):
        raise WorkflowLeaseContractError("workload_unit_ids must be a non-empty string list")
    if data["mutation"] not in ("read-write", "none"):
        raise WorkflowLeaseContractError("mutation must be read-write or none")
    _text(data["spec_sha256"], "spec_sha256")
    _text(data["policy_sha256"], "policy_sha256")
    _positive(data["claim_ttl_seconds"], "claim_ttl_seconds")
    _positive(data["execution_ttl_seconds"], "execution_ttl_seconds")
    if data["requires_prelaunch_reservation"] is not True:
        raise WorkflowLeaseContractError("requires_prelaunch_reservation must be true")
    if data["generated_runtime_filesystem_access"] is not False:
        raise WorkflowLeaseContractError("generated runtime filesystem access must be false")
    if launch_ready:
        _text(data["batch_id"], "batch_id")
        _text(data["owner_id"], "owner_id")
        _text(data["invocation_id"], "invocation_id")
    return data


def reserve(
    metadata: Mapping[str, Any],
    *,
    session_id: str,
    environment: Mapping[str, str] | None = None,
) -> dict[str, Any]:
    """Reserve the complete simultaneous wave or mutate nothing."""

    contract = validate_metadata(metadata)
    selected = lease_broker.broker(environment)
    leases = selected.reserve_batch(
        count=contract["reservation_width"],
        owner_id=contract["owner_id"],
        owner_pid=os.getppid(),
        session_id=_text(session_id, "session_id"),
        batch_id=contract["batch_id"],
        agent_type="*",
        policy_sha256=contract["policy_sha256"],
        session_limit=contract["session_limit"],
        aggregate_limit=contract["aggregate_limit"],
        mutation=contract["mutation"],
        ttl_seconds=contract["claim_ttl_seconds"],
    )
    return {
        "schema": "workflow_lease_receipt.v1",
        "batch_id": contract["batch_id"],
        "owner_id": contract["owner_id"],
        "session_id": session_id,
        "root_sha256": selected.root_sha256,
        "reservation_width": contract["reservation_width"],
        "lease_ids": [lease.lease_id for lease in leases],
    }


def attest(
    metadata: Mapping[str, Any],
    *,
    session_id: str,
    environment: Mapping[str, str] | None = None,
) -> dict[str, Any]:
    """Fail closed unless the exact unclaimed live batch exists before launch."""

    contract = validate_metadata(metadata)
    snapshot = lease_broker.broker(environment).inspect()
    leases = [
        lease
        for lease in snapshot.get("leases", [])
        if lease.get("batch_id") == contract["batch_id"]
    ]
    if len(leases) != contract["reservation_width"]:
        raise WorkflowLeaseContractError(
            f"batch {contract['batch_id']!r} has {len(leases)} of "
            f"{contract['reservation_width']} required slots"
        )
    for lease in leases:
        if (
            lease.get("derived_state") != "live"
            or lease.get("owner_id") != contract["owner_id"]
            or lease.get("session_id") != session_id
            or lease.get("agent_id") is not None
            or lease.get("tool_use_id") is not None
        ):
            raise WorkflowLeaseContractError(
                f"batch {contract['batch_id']!r} is not an unclaimed live prelaunch reservation"
            )
    return {
        "schema": "workflow_lease_attestation.v1",
        "batch_id": contract["batch_id"],
        "root_sha256": snapshot["root_sha256"],
        "reservation_width": len(leases),
        "launch_authorized": True,
    }


def renew(
    metadata: Mapping[str, Any], environment: Mapping[str, str] | None = None
) -> tuple[str, ...]:
    contract = validate_metadata(metadata)
    leases = lease_broker.broker(environment).renew_batch(
        contract["batch_id"], owner_id=contract["owner_id"]
    )
    return tuple(lease.lease_id for lease in leases)


def release(
    metadata: Mapping[str, Any],
    *,
    session_id: str,
    environment: Mapping[str, str] | None = None,
) -> tuple[str, ...]:
    contract = validate_metadata(metadata)
    return cast(
        tuple[str, ...],
        lease_broker.broker(environment).release_owner(
            contract["owner_id"], session_id=_text(session_id, "session_id")
        ),
    )


def _load(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise WorkflowLeaseContractError(f"cannot read lease metadata {path}: {exc}") from exc
    if not isinstance(value, dict):
        raise WorkflowLeaseContractError("lease metadata must contain a JSON object")
    return value


def _die(message: str) -> NoReturn:
    print(f"workflow-lease: HALT — {message}", file=sys.stderr)
    raise SystemExit(2)


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    for name in ("reserve", "attest", "release"):
        command = commands.add_parser(name)
        command.add_argument("metadata", type=Path)
        command.add_argument("--session-id", required=True)
    renew_command = commands.add_parser("renew")
    renew_command.add_argument("metadata", type=Path)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    try:
        metadata = _load(args.metadata)
        if args.command == "reserve":
            result: Any = reserve(metadata, session_id=args.session_id)
        elif args.command == "attest":
            result = attest(metadata, session_id=args.session_id)
        elif args.command == "renew":
            result = {"renewed_lease_ids": list(renew(metadata))}
        elif args.command == "release":
            result = {"released_lease_ids": list(release(metadata, session_id=args.session_id))}
        else:  # pragma: no cover - argparse closes the command set.
            raise AssertionError(args.command)
        print(json.dumps(result, indent=2, sort_keys=True))
        return 0
    except (
        WorkflowLeaseContractError,
        lease_broker.HookInputError,
        lease_broker.authority.LeaseBrokerError,
    ) as exc:
        _die(str(exc))


if __name__ == "__main__":
    raise SystemExit(main())
