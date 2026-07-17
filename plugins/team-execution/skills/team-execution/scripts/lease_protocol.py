#!/usr/bin/env python3
"""Team-execution lifecycle wrapper for fleet-core's lease authority (#356)."""

from __future__ import annotations

import argparse
import json
import sys
from collections.abc import Sequence
from pathlib import Path
from typing import Any, NoReturn

_SCRIPTS_DIR = Path(__file__).resolve().parent
if str(_SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS_DIR))

import fleet_commons_shim  # noqa: E402

authority = fleet_commons_shim.load("lease_broker")
concurrency_policy = fleet_commons_shim.load("concurrency_policy")
REQUIRED_PROTOCOL_VERSION = 1


class LeaseProtocolError(RuntimeError):
    """A team wave cannot safely renew or tear down its lease authority."""


def ensure_protocol() -> None:
    observed = getattr(authority, "PROTOCOL_VERSION", None)
    if observed != REQUIRED_PROTOCOL_VERSION:
        raise LeaseProtocolError(
            "fleet-core lease broker protocol "
            f"{REQUIRED_PROTOCOL_VERSION} required (found {observed!r}); install/update fleet-core"
        )


def broker() -> Any:
    ensure_protocol()
    return authority.LeaseBroker()


def preflight(*, selected: Any | None = None) -> dict[str, Any]:
    """Prove that the canonical broker and default closed admission policy are installed."""

    ensure_protocol()
    selected = broker() if selected is None else selected
    limits = concurrency_policy.AdmissionLimits()
    return {
        "protocol": "team-execution-lease.v1",
        "status": "ready",
        "root_sha256": selected.root_sha256,
        "policy_sha256": limits.policy_sha256(),
        "limits": limits.to_dict(),
    }


def renew(session_id: str, *, selected: Any | None = None) -> dict[str, Any]:
    """Renew one team session at a cooperative wave or collection boundary."""

    ensure_protocol()
    selected = broker() if selected is None else selected
    leases = selected.renew_session(session_id)
    return {
        "protocol": "team-execution-lease.v1",
        "status": "renewed",
        "session_id": session_id,
        "lease_ids": [lease.lease_id for lease in leases],
        "root_sha256": selected.root_sha256,
    }


def teardown(
    session_id: str,
    *,
    terminal_agent_ids: Sequence[str],
    selected: Any | None = None,
) -> dict[str, Any]:
    """Release a session only after every bound child is authoritatively terminal."""

    ensure_protocol()
    selected = broker() if selected is None else selected
    snapshot = selected.inspect()
    session_leases = [
        lease
        for lease in snapshot.get("leases", [])
        if lease.get("pool") == "agent" and lease.get("session_id") == session_id
    ]
    asserted = set(terminal_agent_ids)
    unresolved: list[str] = []
    for lease in session_leases:
        agent_id = lease.get("agent_id")
        if not isinstance(agent_id, str) or not agent_id:
            unresolved.append(f"{lease['lease_id']}:unclaimed")
        elif lease.get("child_terminal_at") is None and agent_id not in asserted:
            unresolved.append(f"{lease['lease_id']}:{agent_id}")
    if unresolved:
        raise LeaseProtocolError(
            "refusing teardown until every child is terminal: " + ", ".join(sorted(unresolved))
        )

    released = selected.release_session(session_id)
    swept = selected.sweep()
    return {
        "protocol": "team-execution-lease.v1",
        "status": "released",
        "session_id": session_id,
        "released_lease_ids": list(released),
        "sweep": swept.to_dict(),
        "root_sha256": selected.root_sha256,
    }


def _print(value: dict[str, Any]) -> None:
    print(json.dumps(value, indent=2, sort_keys=True))


def _die(message: str) -> NoReturn:
    print(json.dumps({"error": "lease-protocol", "reason": message}), file=sys.stderr)
    raise SystemExit(2)


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    commands.add_parser("preflight")

    renew_parser = commands.add_parser("renew")
    renew_parser.add_argument("--session-id", required=True)

    teardown_parser = commands.add_parser("teardown")
    teardown_parser.add_argument("--session-id", required=True)
    teardown_parser.add_argument("--terminal-agent-id", action="append", default=[])
    return parser


def main(argv: list[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    try:
        if args.command == "preflight":
            result = preflight()
        elif args.command == "renew":
            result = renew(args.session_id)
        else:
            result = teardown(args.session_id, terminal_agent_ids=args.terminal_agent_id)
    except (LeaseProtocolError, authority.LeaseBrokerError) as exc:
        _die(str(exc))
    _print(result)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
