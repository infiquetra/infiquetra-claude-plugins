#!/usr/bin/env python3
"""Thin Saga adapter and operator CLI for fleet-core's lease broker (#356).

All state transitions remain in fleet-core. This module translates Saga/Claude hook inputs,
resolved admission environment, and CLI JSON into that canonical authority.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any, NoReturn

import fleet_commons_shim

authority = fleet_commons_shim.load("lease_broker")
concurrency_policy = fleet_commons_shim.load("concurrency_policy")

STATE_ENV = authority.STATE_ENV
SESSION_LIMIT_ENV = "INFIQUETRA_FLEET_SESSION_LIMIT"
AGGREGATE_LIMIT_ENV = "INFIQUETRA_FLEET_AGGREGATE_LIMIT"
POLICY_SHA256_ENV = "INFIQUETRA_FLEET_POLICY_SHA256"
MUTATION_ENV = "INFIQUETRA_FLEET_MUTATION"
TTL_SECONDS_ENV = "INFIQUETRA_FLEET_TTL_SECONDS"
CLAIM_TTL_SECONDS_ENV = "INFIQUETRA_FLEET_CLAIM_TTL_SECONDS"
BATCH_ID_ENV = "INFIQUETRA_FLEET_BATCH_ID"


class HookInputError(ValueError):
    """A required trusted hook field is missing or malformed."""


def _positive_env(environment: Mapping[str, str], name: str, default: int) -> int:
    raw = environment.get(name)
    if raw is None:
        return default
    if not raw.isascii() or not raw.isdecimal() or raw.startswith("0"):
        raise HookInputError(f"{name} must be a canonical positive integer")
    parsed = int(raw)
    if parsed < 1:
        raise HookInputError(f"{name} must be a canonical positive integer")
    return parsed


def _required_text(payload: Mapping[str, Any], name: str) -> str:
    value = payload.get(name)
    if not isinstance(value, str) or not value:
        raise HookInputError(f"hook input requires non-empty {name}")
    return value


def _optional_text(payload: Mapping[str, Any], name: str) -> str | None:
    value = payload.get(name)
    if value is None:
        return None
    if not isinstance(value, str) or not value:
        raise HookInputError(f"hook input {name} must be a non-empty string when present")
    return value


def _agent_type(payload: Mapping[str, Any]) -> str:
    direct = payload.get("agent_type")
    if isinstance(direct, str) and direct:
        return direct
    tool_input = payload.get("tool_input")
    if isinstance(tool_input, dict):
        for key in ("subagent_type", "agent_type"):
            value = tool_input.get(key)
            if isinstance(value, str) and value:
                return value
    return "general-purpose"


def _canonical_cwd(payload: Mapping[str, Any]) -> Path:
    raw = _required_text(payload, "cwd")
    path = Path(raw)
    if not path.is_absolute():
        raise HookInputError("hook input cwd must be absolute")
    try:
        return path.resolve(strict=True)
    except OSError as exc:
        raise HookInputError(f"hook input cwd is not a live directory: {path}") from exc


def admission_snapshot(
    environment: Mapping[str, str] | None = None,
) -> tuple[str, int, int, str]:
    """Resolve an already-normalized runtime snapshot; never re-run Saga policy precedence."""

    env = os.environ if environment is None else environment
    defaults = concurrency_policy.AdmissionLimits()
    session_limit = _positive_env(env, SESSION_LIMIT_ENV, defaults.max_concurrent)
    aggregate_limit = _positive_env(
        env, AGGREGATE_LIMIT_ENV, defaults.aggregate_max_concurrent
    )
    if session_limit > aggregate_limit:
        raise HookInputError(f"{SESSION_LIMIT_ENV} must not exceed {AGGREGATE_LIMIT_ENV}")
    mutation = env.get(MUTATION_ENV, "read-write")
    if mutation not in ("read-write", "none"):
        raise HookInputError(f"{MUTATION_ENV} must be read-write or none")
    policy_sha256 = env.get(POLICY_SHA256_ENV, defaults.policy_sha256())
    # Fleet-core performs the canonical SHA-256 shape check; keep this adapter thin.
    return policy_sha256, session_limit, aggregate_limit, mutation


def broker(environment: Mapping[str, str] | None = None) -> Any:
    """Resolve the one runtime-neutral authority selected by the current environment."""

    return authority.LeaseBroker(environment=os.environ if environment is None else environment)


def reserve_hook_agent(
    payload: Mapping[str, Any], environment: Mapping[str, str] | None = None
) -> Any | None:
    """Reserve before an ``Agent|Task`` tool call; a named batch is already reserved."""

    env = os.environ if environment is None else environment
    if env.get(BATCH_ID_ENV):
        return None
    if payload.get("tool_name") not in ("Agent", "Task"):
        raise HookInputError("lease reservation requires Agent or Task tool_name")
    session_id = _required_text(payload, "session_id")
    tool_use_id = _required_text(payload, "tool_use_id")
    parent_agent = _optional_text(payload, "agent_id")
    policy_sha256, session_limit, aggregate_limit, mutation = admission_snapshot(env)
    claim_ttl = _positive_env(
        env, CLAIM_TTL_SECONDS_ENV, authority.DEFAULT_CLAIM_TTL_SECONDS
    )
    return broker(env).acquire_agent(
        owner_id=parent_agent or f"session:{session_id}",
        owner_pid=os.getppid(),
        session_id=session_id,
        policy_sha256=policy_sha256,
        session_limit=session_limit,
        aggregate_limit=aggregate_limit,
        mutation=mutation,
        ttl_seconds=claim_ttl,
        tool_use_id=tool_use_id,
        agent_type=_agent_type(payload),
    )


def claim_hook_agent(
    payload: Mapping[str, Any], environment: Mapping[str, str] | None = None
) -> Any:
    """Bind trusted SubagentStart identity and canonical actual cwd."""

    env = os.environ if environment is None else environment
    ttl = _positive_env(env, TTL_SECONDS_ENV, authority.DEFAULT_TTL_SECONDS)
    return broker(env).claim(
        session_id=_required_text(payload, "session_id"),
        agent_type=_agent_type(payload),
        agent_id=_required_text(payload, "agent_id"),
        worktree_root=_canonical_cwd(payload),
        batch_id=env.get(BATCH_ID_ENV),
        execution_ttl_seconds=ttl,
    )


def record_hook_terminal(
    payload: Mapping[str, Any], environment: Mapping[str, str] | None = None
) -> bool:
    return broker(environment).record_child_terminal(_required_text(payload, "agent_id"))


def record_hook_parent(
    payload: Mapping[str, Any], environment: Mapping[str, str] | None = None
) -> tuple[str, ...]:
    if payload.get("tool_name") not in ("Agent", "Task"):
        raise HookInputError("parent completion requires Agent or Task tool_name")
    return broker(environment).record_parent_completed(_required_text(payload, "tool_use_id"))


def verify_hook_mutation(
    payload: Mapping[str, Any], environment: Mapping[str, str] | None = None
) -> Any | None:
    """Verify delegated mutation; root calls without trusted ``agent_id`` are unchanged."""

    agent_id = _optional_text(payload, "agent_id")
    if agent_id is None:
        return None
    target: str | None = None
    tool_input = payload.get("tool_input")
    if isinstance(tool_input, dict):
        for key in ("file_path", "notebook_path", "path"):
            value = tool_input.get(key)
            if isinstance(value, str) and value:
                target = value
                break
    return broker(environment).assert_write_target(agent_id, target)


def _lease_payload(lease: Any) -> dict[str, Any]:
    return {
        "lease_id": lease.lease_id,
        "pool": lease.pool,
        "owner_id": lease.owner_id,
        "session_id": lease.session_id,
        "agent_id": lease.agent_id,
        "resource_ref": lease.resource_ref,
        "ttl_seconds": lease.ttl_seconds,
        "token": lease.token.to_dict(),
    }


def _json_print(value: Any) -> None:
    print(json.dumps(value, indent=2, sort_keys=True))


def _die(message: str) -> NoReturn:
    print(f"lease-broker: {message}", file=sys.stderr)
    raise SystemExit(2)


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="command", required=True)
    subparsers.add_parser("inspect")

    renew = subparsers.add_parser("renew")
    renew.add_argument("lease_id")
    renew.add_argument("--owner-id")

    release = subparsers.add_parser("release")
    release.add_argument("lease_id")
    release.add_argument("--owner-id")

    release_owner = subparsers.add_parser("release-owner")
    release_owner.add_argument("owner_id")
    release_owner.add_argument("--session-id")

    sweep = subparsers.add_parser("sweep")
    sweep.add_argument("--terminal-lease-id", action="append", default=[])

    reserve = subparsers.add_parser("reserve-batch")
    reserve.add_argument("--count", type=int, required=True)
    reserve.add_argument("--owner-id", required=True)
    reserve.add_argument("--session-id", required=True)
    reserve.add_argument("--batch-id", required=True)
    reserve.add_argument("--agent-type", required=True)
    reserve.add_argument("--ttl-seconds", type=int, default=authority.DEFAULT_CLAIM_TTL_SECONDS)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = _build_parser().parse_args(argv)
    try:
        selected = broker()
        if args.command == "inspect":
            _json_print(selected.inspect())
        elif args.command == "renew":
            _json_print(_lease_payload(selected.renew(args.lease_id, owner_id=args.owner_id)))
        elif args.command == "release":
            _json_print({"released": selected.release(args.lease_id, owner_id=args.owner_id)})
        elif args.command == "release-owner":
            released = selected.release_owner(args.owner_id, session_id=args.session_id)
            _json_print({"released_lease_ids": list(released)})
        elif args.command == "sweep":
            result = selected.sweep(terminal_lease_ids=args.terminal_lease_id)
            _json_print(
                {
                    "released_agent_leases": list(result.released_agent_leases),
                    "reaped_worktree_leases": list(result.reaped_worktree_leases),
                    "retained": result.retained,
                }
            )
        elif args.command == "reserve-batch":
            policy_sha256, session_limit, aggregate_limit, mutation = admission_snapshot()
            leases = selected.reserve_batch(
                count=args.count,
                owner_id=args.owner_id,
                owner_pid=os.getppid(),
                session_id=args.session_id,
                batch_id=args.batch_id,
                agent_type=args.agent_type,
                policy_sha256=policy_sha256,
                session_limit=session_limit,
                aggregate_limit=aggregate_limit,
                mutation=mutation,
                ttl_seconds=args.ttl_seconds,
            )
            _json_print({"leases": [_lease_payload(lease) for lease in leases]})
        else:  # pragma: no cover - argparse owns command closure.
            raise AssertionError(args.command)
    except (authority.LeaseBrokerError, HookInputError, ValueError) as exc:
        _die(str(exc))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
