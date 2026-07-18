#!/usr/bin/env python3
"""Team-execution lifecycle wrapper for fleet-core's lease authority (#356)."""

from __future__ import annotations

import argparse
import json
import sys
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any, NoReturn

_SCRIPTS_DIR = Path(__file__).resolve().parent
if str(_SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS_DIR))

import fleet_commons_shim  # noqa: E402

authority = fleet_commons_shim.load("lease_broker")
concurrency_policy = fleet_commons_shim.load("concurrency_policy")
REQUIRED_PROTOCOL_VERSION = 2


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


def preflight(session_id: str, *, selected: Any | None = None) -> dict[str, Any]:
    """Prove installation and pin team-execution's closed default admission snapshot."""

    ensure_protocol()
    selected = broker() if selected is None else selected
    limits = concurrency_policy.AdmissionLimits()
    selected.configure_session_admission(
        session_id,
        policy_sha256=limits.policy_sha256(),
        session_limit=limits.max_concurrent,
        aggregate_limit=limits.aggregate_max_concurrent,
        mutation="read-write",
    )
    return {
        "protocol": "team-execution-lease.v1",
        "status": "ready",
        "session_id": session_id,
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
    try:
        released = selected.release_session_if_terminal(
            session_id,
            terminal_agent_ids=terminal_agent_ids,
        )
    except authority.LeaseBrokerError as exc:
        raise LeaseProtocolError(str(exc)) from exc
    swept = selected.sweep()
    return {
        "protocol": "team-execution-lease.v1",
        "status": "released",
        "session_id": session_id,
        "released_lease_ids": list(released),
        "sweep": swept.to_dict(),
        "root_sha256": selected.root_sha256,
    }


_TEARDOWN_SCRIPT = Path("scripts") / "team_teardown.py"
# The teardown CLI's closed verb/flag surface (#358 R11): fixed argv, no shell, no extras.
_TEARDOWN_VERBS = {
    "open-run": ("--session-id", "--team-run-id"),
    "status": ("--team-run-id",),
    "request": ("--session-id", "--reason", "--team-run-id"),
    "reclaim-all": ("--team-run-id", "--reason", "--max-actions", "--dry-run"),
    "recover": ("--expired-only", "--max-actions"),
}


def teardown_run(
    verb: str,
    arguments: Mapping[str, Any],
    *,
    repo_root: Path | None = None,
) -> dict[str, Any]:
    """Invoke Saga's canonical team_teardown CLI (#358) through the installed resolution.

    Local checkouts and installed plugin layouts resolve the same script; an absent or
    pre-#358 Saga is a loud typed failure, never a silent no-op (armed B8 requires it).
    """

    import subprocess  # noqa: PLC0415  # nosec B404 -- fixed Python/script argv, no shell

    import liveness_protocol

    allowed = _TEARDOWN_VERBS.get(verb)
    if allowed is None:
        raise LeaseProtocolError(f"unknown teardown verb {verb!r}")
    resolution = liveness_protocol.resolve_saga_plugin()
    script = resolution.root / _TEARDOWN_SCRIPT
    if not script.is_file():
        raise LeaseProtocolError(
            f"resolved Saga plugin at {resolution.root} lacks {_TEARDOWN_SCRIPT}; "
            "install/update Saga with issue #358 support before arming Step B8"
        )
    argv = [sys.executable, str(script)]
    if repo_root is not None:
        argv.extend(["--repo-root", str(repo_root)])
    argv.append(verb)
    for flag in allowed:
        key = flag.lstrip("-").replace("-", "_")
        value = arguments.get(key)
        if value is None or value is False:
            continue
        if value is True:
            argv.append(flag)
        else:
            argv.extend([flag, str(value)])
    completed = subprocess.run(  # nosec B603 -- fixed interpreter + resolved script path
        argv, capture_output=True, text=True, timeout=60
    )
    if completed.returncode != 0:
        raise LeaseProtocolError(
            f"team_teardown {verb} failed (rc={completed.returncode}): "
            f"{completed.stderr.strip() or completed.stdout.strip()}"
        )
    try:
        parsed = json.loads(completed.stdout)
    except json.JSONDecodeError as exc:
        raise LeaseProtocolError(f"team_teardown {verb} returned non-JSON output") from exc
    if not isinstance(parsed, dict):
        raise LeaseProtocolError(f"team_teardown {verb} returned a non-object payload")
    return parsed


def _print(value: dict[str, Any]) -> None:
    print(json.dumps(value, indent=2, sort_keys=True))


def _die(message: str) -> NoReturn:
    print(json.dumps({"error": "lease-protocol", "reason": message}), file=sys.stderr)
    raise SystemExit(2)


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    preflight_parser = commands.add_parser("preflight")
    preflight_parser.add_argument("--session-id", required=True)

    renew_parser = commands.add_parser("renew")
    renew_parser.add_argument("--session-id", required=True)

    teardown_parser = commands.add_parser("teardown")
    teardown_parser.add_argument("--session-id", required=True)
    teardown_parser.add_argument("--terminal-agent-id", action="append", default=[])

    for verb in sorted(_TEARDOWN_VERBS):
        verb_parser = commands.add_parser(verb)
        verb_parser.add_argument("--repo-root", default=".")
        for flag in _TEARDOWN_VERBS[verb]:
            if flag == "--dry-run" or flag == "--expired-only":
                verb_parser.add_argument(flag, action="store_true")
            else:
                verb_parser.add_argument(flag, default=None)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    try:
        if args.command == "preflight":
            result = preflight(args.session_id)
        elif args.command == "renew":
            result = renew(args.session_id)
        elif args.command == "teardown":
            result = teardown(args.session_id, terminal_agent_ids=args.terminal_agent_id)
        else:
            result = teardown_run(
                args.command,
                {
                    key.replace("-", "_"): value
                    for key, value in vars(args).items()
                    if key not in ("command", "repo_root")
                },
                repo_root=Path(args.repo_root).resolve(),
            )
    except (LeaseProtocolError, authority.LeaseBrokerError) as exc:
        _die(str(exc))
    _print(result)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
