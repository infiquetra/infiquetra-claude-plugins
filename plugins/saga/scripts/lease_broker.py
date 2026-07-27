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
from typing import Any, NoReturn, cast

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
REQUIRED_PROTOCOL_VERSION = 2
_ADMISSION_ENV = frozenset(
    {SESSION_LIMIT_ENV, AGGREGATE_LIMIT_ENV, POLICY_SHA256_ENV, MUTATION_ENV}
)


class HookInputError(ValueError):
    """A required trusted hook field is missing or malformed."""


def ensure_protocol() -> None:
    """Fail closed when the installed fleet-core predates this lease contract."""

    observed = getattr(authority, "PROTOCOL_VERSION", None)
    if observed != REQUIRED_PROTOCOL_VERSION:
        raise HookInputError(
            "fleet-core lease broker protocol "
            f"{REQUIRED_PROTOCOL_VERSION} required (found {observed!r}); install/update fleet-core"
        )


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


def _declared_isolation(payload: Mapping[str, Any]) -> str | None:
    """Extract the parent's declared spawn isolation from ``tool_input`` (#616 KTD1/KTD2).

    Only the exact string ``"worktree"`` is forwarded; any other declared value (e.g.
    ``"remote"``) or its absence normalizes to ``None`` here, before the broker boundary, so
    the adapter never forwards a speculative isolation value for fleet-core to reject.
    """

    tool_input = payload.get("tool_input")
    if isinstance(tool_input, dict) and tool_input.get("isolation") == "worktree":
        return "worktree"
    return None


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
    aggregate_limit = _positive_env(env, AGGREGATE_LIMIT_ENV, defaults.aggregate_max_concurrent)
    if session_limit > aggregate_limit:
        raise HookInputError(f"{SESSION_LIMIT_ENV} must not exceed {AGGREGATE_LIMIT_ENV}")
    mutation = env.get(MUTATION_ENV, "read-write")
    if mutation not in ("read-write", "none"):
        raise HookInputError(f"{MUTATION_ENV} must be read-write or none")
    policy_sha256 = env.get(POLICY_SHA256_ENV, defaults.policy_sha256())
    # Fleet-core performs the canonical SHA-256 shape check; keep this adapter thin.
    return policy_sha256, session_limit, aggregate_limit, mutation


def configure_session_admission(
    session_id: str,
    *,
    policy_sha256: str,
    session_limit: int,
    aggregate_limit: int,
    mutation: str,
    selected: Any | None = None,
) -> Any:
    """Pin one trusted, already-resolved Saga admission snapshot."""

    ensure_protocol()
    active = broker() if selected is None else selected
    return active.configure_session_admission(
        session_id,
        policy_sha256=policy_sha256,
        session_limit=session_limit,
        aggregate_limit=aggregate_limit,
        mutation=mutation,
    )


def session_admission_snapshot(
    session_id: str,
    environment: Mapping[str, str],
    *,
    selected: Any,
) -> tuple[str, int, int, str]:
    """Load the pinned snapshot, or arm it from a trusted environment or policy defaults."""

    configured = selected.get_session_admission(session_id)
    present = set(environment) & _ADMISSION_ENV
    explicit = set(environment) >= _ADMISSION_ENV
    # A partially-resolved environment means a preflight ran and did not finish. That is a
    # real fault whether or not a snapshot already exists, so it is checked BEFORE we trust
    # `configured` — gated on `configured is None` it would be skipped for exactly the
    # sessions that already have limits to ride on, letting a broken preflight proceed
    # under an earlier snapshot instead of halting (#662 review P1).
    if present and not explicit:
        missing = sorted(_ADMISSION_ENV - set(environment))
        raise HookInputError(
            "incomplete Saga admission environment "
            f"(missing {', '.join(missing)}); "
            "run the Saga or team-execution lease preflight before spawning"
        )
    if configured is None:
        # A session with no fleet environment at all was never Saga-managed, so it arms
        # from policy defaults rather than being refused a tool it never opted into
        # (#615 follow-up).
        values = admission_snapshot(environment)
        configure_session_admission(
            session_id,
            policy_sha256=values[0],
            session_limit=values[1],
            aggregate_limit=values[2],
            mutation=values[3],
            selected=selected,
        )
        return values
    values = (
        configured.policy_sha256,
        configured.session_limit,
        configured.aggregate_limit,
        configured.mutation,
    )
    if explicit and admission_snapshot(environment) != values:
        raise HookInputError(
            f"session {session_id!r} hook environment differs from its configured admission snapshot"
        )
    return values


def broker(environment: Mapping[str, str] | None = None) -> Any:
    """Resolve the one runtime-neutral authority selected by the current environment."""

    ensure_protocol()
    return authority.LeaseBroker(environment=os.environ if environment is None else environment)


def worktree_resource(repo_root: Path | str, outcome_id: str, subplot_id: str) -> dict[str, str]:
    """Build the canonical closed resource identity for an outcome-owned worktree."""

    ensure_protocol()
    root = Path(repo_root).resolve()
    return cast(
        dict[str, str],
        authority.canonical_resource_ref(
            "worktree",
            {
                "repo_root": str(root),
                "outcome_id": outcome_id,
                "subplot_id": subplot_id,
            },
        ),
    )


def acquire_outcome_worktree(
    *,
    repo_root: Path | str,
    outcome_id: str,
    subplot_id: str,
    owner_id: str,
    session_id: str,
    selected: Any | None = None,
    ttl_seconds: int = authority.DEFAULT_TTL_SECONDS,
) -> Any:
    """Acquire one worktree-pool lease through the canonical broker."""

    ensure_protocol()
    active = broker() if selected is None else selected
    return active.acquire_worktree(
        owner_id=owner_id,
        owner_pid=os.getpid(),
        session_id=session_id,
        resource_ref=worktree_resource(repo_root, outcome_id, subplot_id),
        ttl_seconds=ttl_seconds,
    )


def worktree_lease_receipt(lease: Any, selected: Any) -> dict[str, Any]:
    """Persist the minimum exact-token binding; never expose the authority path."""

    return {
        "lease_id": lease.lease_id,
        "token": lease.token.to_dict(),
        "root_sha256": selected.root_sha256,
    }


def parse_worktree_lease_receipt(value: Any, selected: Any) -> tuple[str, Any]:
    """Validate a closed registry receipt and return its exact lease id/token."""

    ensure_protocol()
    if not isinstance(value, dict) or set(value) != {"lease_id", "token", "root_sha256"}:
        raise HookInputError(
            "worktree lease receipt requires exactly lease_id, token, and root_sha256"
        )
    if value["root_sha256"] != selected.root_sha256:
        raise HookInputError("worktree lease receipt names a different authority root")
    lease_id = value["lease_id"]
    if not isinstance(lease_id, str) or not lease_id:
        raise HookInputError("worktree lease receipt requires a non-empty lease_id")
    try:
        token = authority.FencingToken.from_dict(value["token"])
    except authority.LeaseBrokerError as exc:
        raise HookInputError(f"worktree lease receipt token is invalid: {exc}") from exc
    return lease_id, token


def active_batch_id(
    payload: Mapping[str, Any], environment: Mapping[str, str] | None = None
) -> str | None:
    """Resolve the one live batch for this Claude session when no explicit override persists."""

    env = os.environ if environment is None else environment
    explicit = env.get(BATCH_ID_ENV)
    if explicit:
        return explicit
    session_id = _required_text(payload, "session_id")
    snapshot = broker(env).inspect()
    batches = {
        lease["batch_id"]
        for lease in snapshot.get("leases", [])
        if lease.get("session_id") == session_id
        and lease.get("derived_state") == "live"
        and isinstance(lease.get("batch_id"), str)
        and lease["batch_id"]
    }
    if len(batches) > 1:
        raise HookInputError(
            f"session {session_id!r} has multiple live Workflow batches; release or cancel one"
        )
    return next(iter(batches), None)


def reserve_hook_agent(
    payload: Mapping[str, Any], environment: Mapping[str, str] | None = None
) -> Any | None:
    """Reserve before an ``Agent|Task`` tool call; a named batch is already reserved."""

    env = os.environ if environment is None else environment
    if payload.get("tool_name") not in ("Agent", "Task"):
        raise HookInputError("lease reservation requires Agent or Task tool_name")
    session_id = _required_text(payload, "session_id")
    tool_use_id = _required_text(payload, "tool_use_id")
    parent_agent = _optional_text(payload, "agent_id")
    claim_ttl = _positive_env(env, CLAIM_TTL_SECONDS_ENV, authority.DEFAULT_CLAIM_TTL_SECONDS)
    selected = broker(env)
    batch_id = active_batch_id(payload, env)
    try:
        if batch_id:
            return selected.prepare_batch_call(
                session_id=session_id,
                batch_id=batch_id,
                agent_type=_agent_type(payload),
                tool_use_id=tool_use_id,
                claim_ttl_seconds=claim_ttl,
                parent_agent_id=parent_agent,
                isolation=_declared_isolation(payload),
            )
        policy_sha256, session_limit, aggregate_limit, mutation = session_admission_snapshot(
            session_id,
            env,
            selected=selected,
        )
        return selected.acquire_agent(
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
            parent_agent_id=parent_agent,
            isolation=_declared_isolation(payload),
        )
    except (authority.LeaseNotFoundError, authority.LeaseOwnershipError) as exc:
        if parent_agent is None:
            raise
        raise HookInputError(
            f"delegated parent {parent_agent!r} has no current spawn authority: {exc}"
        ) from exc


def claim_hook_agent(
    payload: Mapping[str, Any], environment: Mapping[str, str] | None = None
) -> Any:
    """Bind trusted SubagentStart identity and canonical actual cwd."""

    env = os.environ if environment is None else environment
    ttl = _positive_env(env, TTL_SECONDS_ENV, authority.DEFAULT_TTL_SECONDS)
    selected = broker(env)
    return selected.claim(
        session_id=_required_text(payload, "session_id"),
        agent_type=_agent_type(payload),
        agent_id=_required_text(payload, "agent_id"),
        worktree_root=_canonical_cwd(payload),
        batch_id=active_batch_id(payload, env),
        execution_ttl_seconds=ttl,
    )


def record_hook_terminal(
    payload: Mapping[str, Any], environment: Mapping[str, str] | None = None
) -> bool:
    selected = broker(environment)
    return bool(selected.record_child_terminal(_required_text(payload, "agent_id")))


def record_hook_parent(
    payload: Mapping[str, Any], environment: Mapping[str, str] | None = None
) -> tuple[str, ...]:
    if payload.get("tool_name") not in ("Agent", "Task"):
        raise HookInputError("parent completion requires Agent or Task tool_name")
    env = os.environ if environment is None else environment
    selected = broker(env)
    spawn_failed = payload.get("hook_event_name") == "PostToolUseFailure"
    released = selected.record_parent_completed(
        _required_text(payload, "session_id"),
        _required_text(payload, "tool_use_id"),
        spawn_failed=spawn_failed,
    )
    batch_id = active_batch_id(payload, env)
    if batch_id:
        # PostToolUse is the existing collection seam. Renew the whole batch without a daemon.
        selected.renew_batch(batch_id)
    return cast(tuple[str, ...], released)


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
    renew.add_argument("--broker-epoch", required=True)
    renew.add_argument("--fencing-sequence", type=int, required=True)

    release = subparsers.add_parser("release")
    release.add_argument("lease_id")
    release.add_argument("--owner-id")
    release.add_argument("--broker-epoch", required=True)
    release.add_argument("--fencing-sequence", type=int, required=True)

    release_owner = subparsers.add_parser("release-owner")
    release_owner.add_argument("owner_id")
    release_owner.add_argument("--session-id", required=True)

    configure = subparsers.add_parser("configure-session")
    configure.add_argument("--session-id", required=True)
    configure.add_argument("--policy-sha256", required=True)
    configure.add_argument("--session-limit", type=int, required=True)
    configure.add_argument("--aggregate-limit", type=int, required=True)
    configure.add_argument("--mutation", choices=("read-write", "none"), required=True)

    clear = subparsers.add_parser("clear-session")
    clear.add_argument("--session-id", required=True)

    sweep = subparsers.add_parser("sweep")
    sweep.add_argument("--terminal-lease-id", action="append", default=[])

    # #617 KTD4: doctor is read-only; repair performs no default action and requires the explicit
    # ``--strip-unknown`` flag so a rollback down-migration on shared fenced state is never implicit.
    subparsers.add_parser("doctor")

    repair = subparsers.add_parser("repair")
    repair.add_argument("--strip-unknown", action="store_true")

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
            token = authority.FencingToken(args.broker_epoch, args.fencing_sequence)
            _json_print(
                _lease_payload(selected.renew(args.lease_id, owner_id=args.owner_id, token=token))
            )
        elif args.command == "release":
            token = authority.FencingToken(args.broker_epoch, args.fencing_sequence)
            _json_print(
                {"released": selected.release(args.lease_id, owner_id=args.owner_id, token=token)}
            )
        elif args.command == "release-owner":
            released = selected.release_owner(
                args.owner_id,
                session_id=args.session_id,
            )
            _json_print({"released_lease_ids": list(released)})
        elif args.command == "configure-session":
            configured = configure_session_admission(
                args.session_id,
                policy_sha256=args.policy_sha256,
                session_limit=args.session_limit,
                aggregate_limit=args.aggregate_limit,
                mutation=args.mutation,
                selected=selected,
            )
            _json_print(
                {
                    "session_id": args.session_id,
                    "policy_sha256": configured.policy_sha256,
                    "session_limit": configured.session_limit,
                    "aggregate_limit": configured.aggregate_limit,
                    "mutation": configured.mutation,
                    "root_sha256": selected.root_sha256,
                }
            )
        elif args.command == "doctor":
            report = selected.doctor()
            _json_print(report)
            # Distinct exit codes for the operator/automation seam (#617 R7): 0 clean,
            # 3 tolerated-unknowns present, 4 corrupt. doctor never raises for a corrupt document.
            # An unmapped future status fails closed to the corrupt code — a diagnostic verb must
            # never report clean for a state it does not recognize.
            return {"valid": 0, "tolerated-unknowns": 3, "corrupt": 4}.get(report["status"], 4)
        elif args.command == "repair":
            if not args.strip_unknown:
                _die(
                    "repair requires the explicit --strip-unknown flag; it performs no default "
                    "action (#617 R8/KTD4)"
                )
            _json_print(selected.repair())
        elif args.command == "clear-session":
            _json_print({"cleared": selected.clear_session_admission(args.session_id)})
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
