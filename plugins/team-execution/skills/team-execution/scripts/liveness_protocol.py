#!/usr/bin/env python3
"""Installed-plugin Team adapter for Saga's canonical liveness protocol (#357).

The adapter owns no scoring or ledger implementation.  It resolves the independently installed Saga
plugin, preflights the exact protocol, invokes its fixed CLI, and stages hash-only SendMessage
bindings for Saga's host hook.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import subprocess  # nosec B404 -- fixed Python/script argv, no shell
import sys
import tempfile
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import artifact_pointer
import fleet_commons_shim

SAGA_SCRIPT = Path("scripts") / "liveness_events.py"
PENDING_SCHEMA = "liveness.reping-pending.v1"
PENDING_SUBDIR = Path("saga-liveness") / "pending"
REQUIRED_ENGINE_PROTOCOL_VERSION = 1
REQUIRED_FLEET_CORE_VERSION = (0, 15, 0)
_HEX64 = re.compile(r"^[0-9a-f]{64}$")
_IDENTITY_REQUEST_KEYS = frozenset(
    {
        "subplot_id",
        "dispatch_id",
        "unit_id",
        "attempt",
        "resident_id",
        "agent_id",
        "manifest_sha256",
        "spawn_sha256",
    }
)
COORDINATOR_EVENTS = frozenset(
    {
        "heartbeat",
        "idle-ack",
        "reping-ack",
    }
)
RUNG_NAMES = {
    1: "SAGA_PLUGIN_ROOT",
    2: "source-checkout",
    3: "installed-plugins",
    4: "cache-sibling",
}


class LivenessProtocolError(ValueError):
    """The Saga dependency, protocol response, or host binding is invalid."""


@dataclass(frozen=True, slots=True)
class SagaResolution:
    root: Path
    rung: int

    @property
    def script(self) -> Path:
        return self.root / SAGA_SCRIPT


def _is_saga_root(root: Path) -> bool:
    return (root / SAGA_SCRIPT).is_file()


def _source_checkout_root(script_path: Path) -> Path | None:
    for ancestor in script_path.resolve().parents:
        candidate = ancestor / "plugins" / "saga"
        if (ancestor / ".claude-plugin" / "marketplace.json").is_file() and _is_saga_root(
            candidate
        ):
            return candidate
    return None


def _registry_root(registry_path: Path) -> Path | None:
    try:
        plugins = json.loads(registry_path.read_text(encoding="utf-8"))["plugins"]
        entries = plugins.items()
    except (OSError, ValueError, KeyError, TypeError, AttributeError):
        return None
    for name, records in entries:
        if (
            not isinstance(name, str)
            or not name.startswith("saga@")
            or not isinstance(records, list)
        ):
            continue
        for record in records:
            if not isinstance(record, Mapping):
                continue
            install_path = record.get("installPath")
            if isinstance(install_path, str) and _is_saga_root(Path(install_path)):
                return Path(install_path)
    return None


def _semver_key(value: str) -> tuple[int, ...] | None:
    try:
        return tuple(int(part) for part in value.split("."))
    except ValueError:
        return None


def _cache_sibling_root(plugin_root: str | None) -> Path | None:
    if not plugin_root:
        return None
    versions = Path(plugin_root).resolve().parent.parent / "saga"
    if not versions.is_dir():
        return None
    candidates = [
        (version, child)
        for child in versions.iterdir()
        if child.is_dir() and (version := _semver_key(child.name)) is not None
    ]
    for _, candidate in sorted(candidates, reverse=True):
        if _is_saga_root(candidate):
            return candidate
    return None


def resolve_saga_plugin(
    *,
    environ: Mapping[str, str] | None = None,
    registry_path: Path | None = None,
    script_path: Path | None = None,
) -> SagaResolution:
    environment = os.environ if environ is None else environ
    override = environment.get("SAGA_PLUGIN_ROOT")
    if override:
        root = Path(override)
        if not _is_saga_root(root):
            raise LivenessProtocolError(
                f"SAGA_PLUGIN_ROOT={override!r} is not a Saga liveness root "
                "(expected scripts/liveness_events.py)"
            )
        return SagaResolution(root=root, rung=1)
    checkout = _source_checkout_root(script_path or Path(__file__))
    if checkout is not None:
        return SagaResolution(root=checkout, rung=2)
    registry = registry_path or (Path.home() / ".claude" / "plugins" / "installed_plugins.json")
    installed = _registry_root(registry)
    if installed is not None:
        return SagaResolution(root=installed, rung=3)
    cached = _cache_sibling_root(environment.get("CLAUDE_PLUGIN_ROOT"))
    if cached is not None:
        return SagaResolution(root=cached, rung=4)
    raise LivenessProtocolError(
        "team-execution: Saga liveness is unavailable; install Saga with issue #357 support, set "
        "SAGA_PLUGIN_ROOT, or run from an Infiquetra source checkout. Preflight must pass before "
        "the first background Agent call."
    )


def _json_object(raw: str, label: str) -> dict[str, Any]:
    try:
        value = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise LivenessProtocolError(f"{label} is not valid JSON") from exc
    if not isinstance(value, dict):
        raise LivenessProtocolError(f"{label} must be a JSON object")
    return value


def _invoke(
    resolution: SagaResolution,
    repo_root: Path,
    argv: Sequence[str],
) -> dict[str, Any]:
    completed = subprocess.run(  # nosec B603 -- fixed interpreter and resolved script, no shell
        [sys.executable, str(resolution.script), "--repo-root", str(repo_root), *argv],
        capture_output=True,
        text=True,
    )
    if completed.returncode != 0:
        detail = completed.stderr.strip() or completed.stdout.strip() or "unknown Saga refusal"
        raise LivenessProtocolError(f"Saga liveness command failed: {detail}")
    return _json_object(completed.stdout, "Saga liveness response")


def preflight(
    *,
    repo_root: Path,
    resolution: SagaResolution | None = None,
) -> dict[str, Any]:
    selected = resolution or resolve_saga_plugin()
    result = _invoke(selected, repo_root, ["describe"])
    if (
        result.get("subject_schema") != "liveness.subject.v1"
        or result.get("decision_schema") != "liveness_decision.v1"
        or result.get("engine_protocol_version") != REQUIRED_ENGINE_PROTOCOL_VERSION
        or result.get("max_definitive_not_sent_retries_per_attempt") != 1
    ):
        raise LivenessProtocolError("installed Saga liveness contract is stale or incompatible")
    version = result.get("fleet_core_version")
    parsed_version = _semver_key(version) if isinstance(version, str) else None
    if parsed_version is None or parsed_version < REQUIRED_FLEET_CORE_VERSION:
        raise LivenessProtocolError(
            "installed fleet-core liveness is stale or incompatible "
            f"(requires >= {'.'.join(map(str, REQUIRED_FLEET_CORE_VERSION))}, found {version!r})"
        )
    if not isinstance(result.get("engine_sha256"), str) or not _HEX64.fullmatch(
        result["engine_sha256"]
    ):
        raise LivenessProtocolError("installed Saga did not attest the resolved liveness engine")
    return {
        **result,
        "resolution_rung": selected.rung,
        "resolution_name": RUNG_NAMES[selected.rung],
    }


def capture_spawn_baseline(
    paths: Sequence[str],
    *,
    repo_root: Path,
    observed_monotonic: float,
) -> dict[str, Any]:
    return artifact_pointer.capture_liveness_baseline(
        list(paths),
        repo_root=repo_root,
        observed_monotonic=observed_monotonic,
    )


def bind_identity(
    request: Mapping[str, Any],
    baseline: Mapping[str, Any],
    *,
    lease_broker: Any | None = None,
) -> dict[str, Any]:
    """Bind caller metadata to the broker-verified current agent lease.

    Resource, token, session, boot, TTL, and fencing values are derived from canonical fleet-core
    authority. The caller cannot choose their digests or generations.
    """

    if set(request) != _IDENTITY_REQUEST_KEYS:
        raise LivenessProtocolError(
            f"identity request fields are not closed (expected {sorted(_IDENTITY_REQUEST_KEYS)})"
        )
    agent_id = request.get("agent_id")
    if not isinstance(agent_id, str) or not agent_id:
        raise LivenessProtocolError("identity request requires agent_id")
    authority = fleet_commons_shim.load("lease_broker")
    selected = authority.LeaseBroker() if lease_broker is None else lease_broker
    try:
        lease = selected.verify_agent(agent_id)
        if lease.pool != "agent" or lease.agent_id != agent_id or lease.resource_ref is None:
            raise LivenessProtocolError("broker returned a non-agent or mismatched liveness lease")
        resource = authority.canonical_resource_ref("agent", lease.resource_ref)
    except authority.LeaseBrokerError as exc:
        raise LivenessProtocolError(f"cannot bind current liveness lease: {exc}") from exc
    if baseline.get("schema") != artifact_pointer.LIVENESS_BASELINE_SCHEMA:
        raise LivenessProtocolError("identity binding requires a liveness artifact baseline")
    for field in ("baseline_digest", "path_set_sha256"):
        if not isinstance(baseline.get(field), str) or not _HEX64.fullmatch(baseline[field]):
            raise LivenessProtocolError(f"identity baseline {field} is invalid")
    token = lease.token.to_dict()
    token_sha256 = hashlib.sha256(
        json.dumps(token, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()
    return {
        "session_id": lease.session_id,
        "subplot_id": request["subplot_id"],
        "dispatch_id": request["dispatch_id"],
        "unit_id": request["unit_id"],
        "attempt": request["attempt"],
        "resident_id": request["resident_id"],
        "agent_id": agent_id,
        "lease_id": lease.lease_id,
        "resource_sha256": authority.resource_sha256(resource),
        "broker_epoch": lease.broker_epoch,
        "fencing_sequence": lease.fencing_sequence,
        "boot_id": lease.boot_id,
        "manifest_sha256": request["manifest_sha256"],
        "spawn_sha256": request["spawn_sha256"],
        "token_sha256": token_sha256,
        "lease_ttl_seconds": lease.ttl_seconds,
        "baseline_sha256": baseline["baseline_digest"],
        "path_set_sha256": baseline["path_set_sha256"],
    }


def append_event(
    *,
    repo_root: Path,
    identity: Mapping[str, Any],
    event: str,
    event_id: str,
    at: str,
    payload: Mapping[str, Any],
    resolution: SagaResolution | None = None,
) -> dict[str, Any]:
    selected = resolution or resolve_saga_plugin()
    return _invoke(
        selected,
        repo_root,
        [
            "append",
            "--identity-json",
            json.dumps(dict(identity), sort_keys=True, separators=(",", ":")),
            "--event",
            event,
            "--event-id",
            event_id,
            "--at",
            at,
            "--payload-json",
            json.dumps(dict(payload), sort_keys=True, separators=(",", ":")),
        ],
    )


def record_coordinator_event(
    *,
    repo_root: Path,
    identity: Mapping[str, Any],
    event: str,
    event_id: str,
    at: str,
    payload: Mapping[str, Any],
    resolution: SagaResolution | None = None,
) -> dict[str, Any]:
    if event not in COORDINATOR_EVENTS:
        raise LivenessProtocolError(
            f"event {event!r} is not coordinator-owned; use the dedicated open/claim/hook path"
        )
    return append_event(
        repo_root=repo_root,
        identity=identity,
        event=event,
        event_id=event_id,
        at=at,
        payload=payload,
        resolution=resolution,
    )


def record_idle_notice(
    *,
    repo_root: Path,
    identity: Mapping[str, Any],
    event_id: str,
    at: str,
    signal_ref: str,
    signal_digest: str,
    observed_monotonic: float,
    host_notice_id: str | None = None,
    resolution: SagaResolution | None = None,
) -> dict[str, Any]:
    selected = resolution or resolve_saga_plugin()
    argv = [
        "idle-notice",
        "--identity-json",
        json.dumps(dict(identity), sort_keys=True, separators=(",", ":")),
        "--event-id",
        event_id,
        "--at",
        at,
        "--signal-ref",
        signal_ref,
        "--signal-digest",
        signal_digest,
        "--observed-monotonic",
        str(observed_monotonic),
    ]
    if host_notice_id is not None:
        argv.extend(["--host-notice-id", host_notice_id])
    return _invoke(selected, repo_root, argv)


def record_artifact_observation(
    *,
    repo_root: Path,
    identity: Mapping[str, Any],
    baseline: Mapping[str, Any],
    event_id: str,
    at: str,
    observed_monotonic: float,
    exclusive_provenance: Mapping[str, Any] | None = None,
    resolution: SagaResolution | None = None,
) -> dict[str, Any]:
    selected = resolution or resolve_saga_plugin()
    subject_id = _invoke(
        selected,
        repo_root,
        [
            "subject-id",
            "--identity-json",
            json.dumps(dict(identity), sort_keys=True, separators=(",", ":")),
        ],
    )["subject_id"]
    observation = artifact_pointer.observe_liveness_paths(
        baseline,
        repo_root=repo_root,
        observed_monotonic=observed_monotonic,
        exclusive_provenance=exclusive_provenance,
        subject_identity={"subject_id": subject_id, **dict(identity)},
    )
    event = observation.get("event")
    payload = observation.get("payload")
    if event is None:
        return {"observation": observation, "record": None}
    if event not in {"scoped-activity-unattributed", "artifact-progress"} or not isinstance(
        payload, Mapping
    ):
        raise LivenessProtocolError("artifact observation returned an unsupported event contract")
    record = append_event(
        repo_root=repo_root,
        identity=identity,
        event=event,
        event_id=event_id,
        at=at,
        payload=payload,
        resolution=selected,
    )
    return {"observation": observation, "record": record}


def open_subject(
    *,
    repo_root: Path,
    identity: Mapping[str, Any],
    event_id: str,
    at: str,
    observed_monotonic: float,
    source_ref: str,
    resolution: SagaResolution | None = None,
) -> dict[str, Any]:
    return append_event(
        repo_root=repo_root,
        identity=identity,
        event="subject-open",
        event_id=event_id,
        at=at,
        payload={"observed_monotonic": observed_monotonic, "source_ref": source_ref},
        resolution=resolution,
    )


def poll(
    *,
    repo_root: Path,
    subject_id: str,
    now: float,
    resolution: SagaResolution | None = None,
) -> dict[str, Any]:
    selected = resolution or resolve_saga_plugin()
    authority = fleet_commons_shim.load("lease_broker")
    current_boot_id = authority.Providers().boot_id()
    argv = [
        "poll",
        "--subject-id",
        subject_id,
        "--now",
        str(now),
        "--current-boot-id",
        current_boot_id,
    ]
    return _invoke(selected, repo_root, argv)


def claim_reping(
    *,
    repo_root: Path,
    identity: Mapping[str, Any],
    event_id: str,
    at: str,
    now: float,
    resolution: SagaResolution | None = None,
) -> dict[str, Any] | None:
    selected = resolution or resolve_saga_plugin()
    subject = _invoke(
        selected,
        repo_root,
        [
            "subject-id",
            "--identity-json",
            json.dumps(dict(identity), sort_keys=True, separators=(",", ":")),
        ],
    )["subject_id"]
    decision = poll(
        repo_root=repo_root,
        subject_id=subject,
        now=now,
        resolution=selected,
    )
    candidate = decision.get("reping")
    generation = decision.get("generation")
    if not isinstance(candidate, Mapping) or not isinstance(generation, Mapping):
        return None
    return append_event(
        repo_root=repo_root,
        identity=identity,
        event="reping-intent",
        event_id=event_id,
        at=at,
        payload={
            "generation_id": candidate["generation_id"],
            "cause": candidate["cause"],
            "anchor_ref": generation["anchor_ref"],
            "opened_monotonic": now,
            "liveness_attempt": candidate["liveness_attempt"],
            "retry_ordinal": candidate["retry_ordinal"],
            "predecessor_failure_ref": candidate["predecessor_failure_ref"],
            "claim_key": candidate["claim_key"],
        },
        resolution=selected,
    )


def request_digest(recipient: str, message: str) -> str:
    if not recipient:
        raise LivenessProtocolError("re-ping recipient is required")
    return hashlib.sha256(
        json.dumps(
            {"recipient": recipient, "message": message},
            sort_keys=True,
            separators=(",", ":"),
        ).encode()
    ).hexdigest()


def _git_common_dir(repo_root: Path) -> Path:
    completed = subprocess.run(  # nosec B603 B607 -- fixed Git argv, no shell
        ["git", "-C", str(repo_root), "rev-parse", "--git-common-dir"],
        capture_output=True,
        text=True,
    )
    if completed.returncode != 0:
        raise LivenessProtocolError(f"cannot resolve Git common dir: {completed.stderr.strip()}")
    common = Path(completed.stdout.strip())
    return common if common.is_absolute() else (repo_root / common).resolve()


def pending_dir(repo_root: Path) -> Path:
    return _git_common_dir(repo_root) / PENDING_SUBDIR


def stage_reping_send(
    *,
    repo_root: Path,
    identity: Mapping[str, Any],
    claim: Mapping[str, Any],
    recipient: str,
    request_sha256: str,
    staged_monotonic: float,
    response_window_seconds: float,
) -> Path:
    claim_key = claim.get("claim_key")
    if not isinstance(claim_key, str) or not _HEX64.fullmatch(claim_key):
        raise LivenessProtocolError("staged re-ping requires a canonical claim_key")
    if not isinstance(request_sha256, str) or not _HEX64.fullmatch(request_sha256):
        raise LivenessProtocolError("staged re-ping request digest is invalid")
    if not recipient:
        raise LivenessProtocolError("staged re-ping recipient is required")
    if staged_monotonic < 0 or response_window_seconds <= 0:
        raise LivenessProtocolError(
            "staged re-ping timing must be nonnegative with a positive window"
        )
    record = {
        "schema": PENDING_SCHEMA,
        "identity": dict(identity),
        "claim_key": claim_key,
        "claim_event_id": claim.get("event_id"),
        "recipient": recipient,
        "request_digest": request_sha256,
        "staged_monotonic": float(staged_monotonic),
        "response_window_seconds": float(response_window_seconds),
    }
    directory = pending_dir(repo_root)
    directory.mkdir(parents=True, exist_ok=True)
    path = directory / f"{claim_key}.json"
    fd, temporary = tempfile.mkstemp(dir=directory, prefix=f".{claim_key}-")
    try:
        os.fchmod(fd, 0o600)
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            json.dump(record, handle, sort_keys=True, separators=(",", ":"))
            handle.write("\n")
        os.replace(temporary, path)
    except Exception:
        if os.path.exists(temporary):
            os.unlink(temporary)
        raise
    return path


def _cmd_preflight(args: argparse.Namespace) -> int:
    print(json.dumps(preflight(repo_root=Path(args.repo_root).resolve()), sort_keys=True))
    return 0


def _cmd_baseline(args: argparse.Namespace) -> int:
    result = capture_spawn_baseline(
        args.path,
        repo_root=Path(args.repo_root).resolve(),
        observed_monotonic=args.observed_monotonic,
    )
    print(json.dumps(result, sort_keys=True, separators=(",", ":")))
    return 0


def _cmd_open(args: argparse.Namespace) -> int:
    identity = bind_identity(
        _json_object(args.identity_request_json, "identity-request-json"),
        _json_object(args.baseline_json, "baseline-json"),
    )
    result = open_subject(
        repo_root=Path(args.repo_root).resolve(),
        identity=identity,
        event_id=args.event_id,
        at=args.at,
        observed_monotonic=args.observed_monotonic,
        source_ref=args.source_ref,
    )
    print(
        json.dumps(
            {"subject_id": result["subject_id"], "identity": identity, "record": result},
            sort_keys=True,
            separators=(",", ":"),
        )
    )
    return 0


def _cmd_event(args: argparse.Namespace) -> int:
    result = record_coordinator_event(
        repo_root=Path(args.repo_root).resolve(),
        identity=_json_object(args.identity_json, "identity-json"),
        event=args.event,
        event_id=args.event_id,
        at=args.at,
        payload=_json_object(args.payload_json, "payload-json"),
    )
    print(json.dumps(result, sort_keys=True, separators=(",", ":")))
    return 0


def _cmd_idle_notice(args: argparse.Namespace) -> int:
    result = record_idle_notice(
        repo_root=Path(args.repo_root).resolve(),
        identity=_json_object(args.identity_json, "identity-json"),
        event_id=args.event_id,
        at=args.at,
        signal_ref=args.signal_ref,
        signal_digest=args.signal_digest,
        observed_monotonic=args.observed_monotonic,
        host_notice_id=args.host_notice_id,
    )
    print(json.dumps(result, sort_keys=True, separators=(",", ":")))
    return 0


def _cmd_artifact_observation(args: argparse.Namespace) -> int:
    result = record_artifact_observation(
        repo_root=Path(args.repo_root).resolve(),
        identity=_json_object(args.identity_json, "identity-json"),
        baseline=_json_object(args.baseline_json, "baseline-json"),
        event_id=args.event_id,
        at=args.at,
        observed_monotonic=args.observed_monotonic,
        exclusive_provenance=(
            None
            if args.exclusive_provenance_json is None
            else _json_object(args.exclusive_provenance_json, "exclusive-provenance-json")
        ),
    )
    print(json.dumps(result, sort_keys=True, separators=(",", ":")))
    return 0


def _cmd_poll(args: argparse.Namespace) -> int:
    result = poll(
        repo_root=Path(args.repo_root).resolve(),
        subject_id=args.subject_id,
        now=args.now,
    )
    print(json.dumps(result, sort_keys=True, separators=(",", ":")))
    return 0


def _cmd_claim(args: argparse.Namespace) -> int:
    result = claim_reping(
        repo_root=Path(args.repo_root).resolve(),
        identity=_json_object(args.identity_json, "identity-json"),
        event_id=args.event_id,
        at=args.at,
        now=args.now,
    )
    print(json.dumps(result, sort_keys=True, separators=(",", ":")))
    return 0


def _cmd_stage(args: argparse.Namespace) -> int:
    path = stage_reping_send(
        repo_root=Path(args.repo_root).resolve(),
        identity=_json_object(args.identity_json, "identity-json"),
        claim=_json_object(args.claim_json, "claim-json"),
        recipient=args.recipient,
        request_sha256=args.request_digest,
        staged_monotonic=args.staged_monotonic,
        response_window_seconds=args.response_window_seconds,
    )
    print(json.dumps({"pending_ref": path.name}, sort_keys=True))
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Team adapter for Saga liveness")
    commands = parser.add_subparsers(dest="command", required=True)
    preflight_parser = commands.add_parser("preflight")
    preflight_parser.add_argument("--repo-root", required=True)
    preflight_parser.set_defaults(func=_cmd_preflight)
    baseline_parser = commands.add_parser("baseline")
    baseline_parser.add_argument("--repo-root", required=True)
    baseline_parser.add_argument("--path", action="append", required=True)
    baseline_parser.add_argument("--observed-monotonic", type=float, required=True)
    baseline_parser.set_defaults(func=_cmd_baseline)
    open_parser = commands.add_parser("open")
    open_parser.add_argument("--repo-root", required=True)
    open_parser.add_argument("--identity-request-json", required=True)
    open_parser.add_argument("--baseline-json", required=True)
    open_parser.add_argument("--event-id", required=True)
    open_parser.add_argument("--at", required=True)
    open_parser.add_argument("--observed-monotonic", type=float, required=True)
    open_parser.add_argument("--source-ref", required=True)
    open_parser.set_defaults(func=_cmd_open)
    event_parser = commands.add_parser("record-event")
    event_parser.add_argument("--repo-root", required=True)
    event_parser.add_argument("--identity-json", required=True)
    event_parser.add_argument("--event", choices=sorted(COORDINATOR_EVENTS), required=True)
    event_parser.add_argument("--event-id", required=True)
    event_parser.add_argument("--at", required=True)
    event_parser.add_argument("--payload-json", required=True)
    event_parser.set_defaults(func=_cmd_event)
    notice_parser = commands.add_parser("record-idle-notice")
    notice_parser.add_argument("--repo-root", required=True)
    notice_parser.add_argument("--identity-json", required=True)
    notice_parser.add_argument("--event-id", required=True)
    notice_parser.add_argument("--at", required=True)
    notice_parser.add_argument("--host-notice-id")
    notice_parser.add_argument("--signal-ref", required=True)
    notice_parser.add_argument("--signal-digest", required=True)
    notice_parser.add_argument("--observed-monotonic", type=float, required=True)
    notice_parser.set_defaults(func=_cmd_idle_notice)
    observation_parser = commands.add_parser("record-artifact-observation")
    observation_parser.add_argument("--repo-root", required=True)
    observation_parser.add_argument("--identity-json", required=True)
    observation_parser.add_argument("--baseline-json", required=True)
    observation_parser.add_argument("--event-id", required=True)
    observation_parser.add_argument("--at", required=True)
    observation_parser.add_argument("--observed-monotonic", type=float, required=True)
    observation_parser.add_argument("--exclusive-provenance-json")
    observation_parser.set_defaults(func=_cmd_artifact_observation)
    poll_parser = commands.add_parser("poll")
    poll_parser.add_argument("--repo-root", required=True)
    poll_parser.add_argument("--subject-id", required=True)
    poll_parser.add_argument("--now", type=float, required=True)
    poll_parser.set_defaults(func=_cmd_poll)
    claim_parser = commands.add_parser("claim-reping")
    claim_parser.add_argument("--repo-root", required=True)
    claim_parser.add_argument("--identity-json", required=True)
    claim_parser.add_argument("--event-id", required=True)
    claim_parser.add_argument("--at", required=True)
    claim_parser.add_argument("--now", type=float, required=True)
    claim_parser.set_defaults(func=_cmd_claim)
    stage_parser = commands.add_parser("stage-send")
    stage_parser.add_argument("--repo-root", required=True)
    stage_parser.add_argument("--identity-json", required=True)
    stage_parser.add_argument("--claim-json", required=True)
    stage_parser.add_argument("--recipient", required=True)
    stage_parser.add_argument("--request-digest", required=True)
    stage_parser.add_argument("--staged-monotonic", type=float, required=True)
    stage_parser.add_argument("--response-window-seconds", type=float, required=True)
    stage_parser.set_defaults(func=_cmd_stage)
    args = parser.parse_args(argv)
    try:
        return int(args.func(args))
    except LivenessProtocolError as exc:
        print(str(exc), file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
