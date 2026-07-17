#!/usr/bin/env python3
"""Closed orphan evidence, bounded quarantine, and read-only projection (#355).

The lease broker remains the sole mutation authority. This module only preserves refused output and
derives operator candidates from immutable broker/audit facts. Nothing here can accept a live write,
close a lease, supersede a generation, or execute reclamation.
"""

from __future__ import annotations

import contextlib
import fcntl
import hashlib
import json
import os
import shutil
import stat
import time
import uuid
from collections.abc import Callable, Iterator, Mapping, Sequence
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Literal, cast

MAX_PAYLOAD_BYTES = 128 * 1024 * 1024
MAX_QUARANTINE_BYTES = 512 * 1024 * 1024
MAX_QUARANTINE_ITEMS = 256
MIN_RETENTION_SECONDS = 30 * 24 * 60 * 60
LIVE_RESERVATION_ALERT_SECONDS = 60 * 60

QUARANTINE = "quarantine"
STAGING = "quarantine-staging"
EVENTS = "orphan-events"
SEALS = "close-seals"
LOCK = "quarantine.lock"

Disposition = Literal[
    "ORPHAN_WRITE_BLOCKED",
    "EXPIRED_LEASE_QUARANTINED",
    "LATE_WRITE_AFTER_CLOSE",
    "EVIDENCE_INTEGRITY_ERROR",
]

_HEX = frozenset("0123456789abcdef")
_PRODUCERS = frozenset({"agy", "saga", "team-execution"})
_CLASSIFICATIONS = frozenset(
    {
        "expired-write-quarantined",
        "superseded-write-blocked",
        "late-write-after-close",
        "stalled",
        "empty-artifacts",
        "evidence-integrity-error",
    }
)
_OWNERS = {
    "agy": "agy-supervisor",
    "saga": "outcome",
    "team-execution": "team-execution",
}

SCHEMA_FIELDS: dict[str, tuple[frozenset[str], frozenset[str]]] = {
    "settlement_close.v1": (
        frozenset(
            {
                "schema",
                "resource_ref",
                "token",
                "lease_id",
                "settlement_id",
                "session_id",
                "policy_sha256",
                "generation",
                "phase",
                "producer",
                "run_id",
                "terminal",
                "evidence_refs",
                "expected_output_sha256",
                "protected_write_intent_sha256",
                "settlement_sha256",
                "receipt_sha256",
                "sha256",
            }
        ),
        frozenset(),
    ),
    "settlement_recovery_intent.v1": (
        frozenset(
            {
                "schema",
                "resource_ref",
                "token",
                "lease_id",
                "generation",
                "settlement_id",
                "session_id",
                "policy_sha256",
                "expected_phase",
                "protected_write_intent_sha256",
                "recovery_owner_id",
                "recovery_owner_pid",
                "recovery_owner_process_start",
                "recovery_owner_boot_id",
                "recovery_owner_effective_uid",
                "sha256",
            }
        ),
        frozenset(),
    ),
    "agy.expected-output-template.v1": (
        frozenset(
            {
                "schema",
                "trusted_source",
                "source_id",
                "required",
                "artifact_keys",
                "target_count",
                "expected_output_template_sha256",
                "sha256",
            }
        ),
        frozenset(),
    ),
    "expected_output.v1": (
        frozenset(
            {
                "schema",
                "expected_output_template_sha256",
                "resource_ref",
                "token",
                "lease_id",
                "generation",
                "producer",
                "run_id",
                "expected_output_sha256",
                "sha256",
            }
        ),
        frozenset(),
    ),
    "quarantine_manifest.v1": (
        frozenset(
            {
                "schema",
                "resource_ref",
                "token",
                "lease_id",
                "generation",
                "producer",
                "run_id",
                "reason",
                "payload_sha256",
                "payload_bytes",
                "observed_at",
                "expected_output_sha256",
                "evidence_refs",
                "sha256",
            }
        ),
        frozenset({"receipt_sha256"}),
    ),
    "orphan_event.v1": (
        frozenset(
            {
                "schema",
                "event_id",
                "resource_ref",
                "token",
                "lease_id",
                "generation",
                "producer",
                "run_id",
                "classification",
                "observed_at",
                "expected_output_sha256",
                "evidence_refs",
                "payload_refs",
                "sha256",
            }
        ),
        frozenset({"receipt_sha256"}),
    ),
    "orphan_candidate.v1": (
        frozenset(
            {
                "schema",
                "candidate_id",
                "classification",
                "producer",
                "run_id",
                "resource_ref",
                "token",
                "lease_id",
                "generation",
                "authoritative_terminal",
                "owner",
                "expected_output_sha256",
                "evidence_refs",
                "sha256",
            }
        ),
        frozenset({"receipt_sha256"}),
    ),
    "reservation.v1": (
        frozenset(
            {
                "schema",
                "reservation_id",
                "payload_sha256",
                "payload_bytes",
                "owner_pid",
                "owner_process_start",
                "boot_id",
                "created_at",
                "created_monotonic_ns",
                "state",
            }
        ),
        frozenset({"manifest_sha256"}),
    ),
    "agy.lease-admission.v1": (
        frozenset(
            {
                "schema",
                "session_id",
                "owner_id",
                "owner_pid",
                "owner_process_start",
                "policy_sha256",
                "session_limit",
                "aggregate_limit",
                "mutation",
                "ttl_seconds",
                "resource_ref",
                "repository_identity_sha256",
                "expected_output_template_sha256",
            }
        ),
        frozenset(),
    ),
}


class OrphanEvidenceError(ValueError):
    """An evidence record, binding, or quarantine operation failed closed."""


class _SupersededDuringPublicationError(RuntimeError):
    """The generation advanced before prepared quarantine bytes could be published."""


@dataclass(frozen=True)
class Providers:
    wall_now: Callable[[], datetime] = lambda: datetime.now(UTC)
    monotonic_ns: Callable[[], int] = time.monotonic_ns
    boot_id: Callable[[], str] = lambda: "unknown-boot"
    process_identity: Callable[[int], str | None] = lambda _pid: None
    process_exists: Callable[[int], bool] = lambda pid: _process_exists(pid)


def _process_exists(pid: int) -> bool:
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    except PermissionError:
        return True
    return True


def canonical_json(value: Mapping[str, Any]) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode(
        "ascii"
    )


def _digest(value: Mapping[str, Any], *excluded: str) -> str:
    return hashlib.sha256(
        canonical_json({key: item for key, item in value.items() if key not in excluded})
    ).hexdigest()


def _text(value: Any, name: str, *, maximum: int = 256) -> str:
    if not isinstance(value, str) or not value or len(value.encode("utf-8")) > maximum:
        raise OrphanEvidenceError(f"{name} must be a bounded non-empty string")
    if any(ord(char) < 32 for char in value):
        raise OrphanEvidenceError(f"{name} must not contain control characters")
    return value


def _sha(value: Any, name: str) -> str:
    text = _text(value, name, maximum=64)
    if len(text) != 64 or any(char not in _HEX for char in text):
        raise OrphanEvidenceError(f"{name} must be lowercase SHA-256")
    return text


def _positive(value: Any, name: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value < 1:
        raise OrphanEvidenceError(f"{name} must be a positive integer")
    return int(value)


def _nonnegative(value: Any, name: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        raise OrphanEvidenceError(f"{name} must be a non-negative integer")
    return int(value)


def _timestamp(value: Any, name: str) -> str:
    text = _text(value, name)
    if not text.endswith("Z"):
        raise OrphanEvidenceError(f"{name} must be RFC3339 UTC with Z")
    try:
        datetime.fromisoformat(text.replace("Z", "+00:00"))
    except ValueError as exc:
        raise OrphanEvidenceError(f"{name} must be RFC3339 UTC") from exc
    return text


def utc_text(value: datetime) -> str:
    if value.tzinfo is None:
        raise OrphanEvidenceError("wall clock must be timezone aware")
    return value.astimezone(UTC).isoformat().replace("+00:00", "Z")


def resource_ref(value: Any) -> dict[str, str]:
    if not isinstance(value, Mapping):
        raise OrphanEvidenceError("resource_ref must be an object")
    data = dict(value)
    if set(data) not in ({"logical_unit_id"}, {"logical_unit_id", "worktree_root"}):
        raise OrphanEvidenceError("agent resource_ref must contain exact canonical fields")
    logical = _text(data["logical_unit_id"], "logical_unit_id")
    if "worktree_root" not in data:
        return {"logical_unit_id": logical}
    root = _text(data["worktree_root"], "worktree_root", maximum=4096)
    path = Path(root)
    if not path.is_absolute() or ".." in path.parts or str(path) != os.path.normpath(root):
        raise OrphanEvidenceError("worktree_root must be a normalized absolute path")
    return {"logical_unit_id": logical, "worktree_root": root}


def token_dict(value: Any) -> dict[str, Any]:
    if hasattr(value, "to_dict"):
        value = value.to_dict()
    if not isinstance(value, Mapping) or set(value) != {"broker_epoch", "fencing_sequence"}:
        raise OrphanEvidenceError("token must use the exact closed shape")
    epoch = _text(value["broker_epoch"], "broker_epoch")
    try:
        parsed = uuid.UUID(epoch)
    except ValueError as exc:
        raise OrphanEvidenceError("broker_epoch must be a UUID") from exc
    if str(parsed) != epoch:
        raise OrphanEvidenceError("broker_epoch must be canonical lowercase UUID")
    return {
        "broker_epoch": epoch,
        "fencing_sequence": _positive(value["fencing_sequence"], "fencing_sequence"),
    }


def generation(token: Any) -> str:
    parsed = token_dict(token)
    return f"{parsed['broker_epoch']}:{parsed['fencing_sequence']}"


def resource_sha256(value: Mapping[str, Any]) -> str:
    return hashlib.sha256(canonical_json(resource_ref(value))).hexdigest()


def _refs(value: Any, name: str) -> list[str]:
    if not isinstance(value, list) or len(value) > 256 or value != sorted(value):
        raise OrphanEvidenceError(f"{name} must be a sorted bounded list")
    result = [_text(item, f"{name} item") for item in value]
    if len(result) != len(set(result)):
        raise OrphanEvidenceError(f"{name} must not contain duplicates")
    return result


def validate_record(value: Mapping[str, Any]) -> dict[str, Any]:
    data = dict(value)
    schema = data.get("schema")
    if schema not in SCHEMA_FIELDS:
        raise OrphanEvidenceError("record schema is unsupported")
    required, optional = SCHEMA_FIELDS[schema]
    if not required.issubset(data) or set(data) - required - optional:
        raise OrphanEvidenceError(f"{schema} has missing or unknown fields")
    if "sha256" in data and _sha(data["sha256"], "sha256") != _digest(data, "sha256"):
        raise OrphanEvidenceError(f"{schema} self digest does not match")
    if "resource_ref" in data:
        resource_ref(data["resource_ref"])
    if "token" in data:
        parsed_token = token_dict(data["token"])
        if data.get("generation") != generation(parsed_token):
            raise OrphanEvidenceError(f"{schema} generation does not match token")
    for name, item in data.items():
        if name.endswith("_sha256") or name == "sha256":
            _sha(item, name)
    for name in ("evidence_refs", "payload_refs", "artifact_keys"):
        if name in data:
            _refs(data[name], name)
    if "producer" in data and data["producer"] not in _PRODUCERS:
        raise OrphanEvidenceError(f"{schema} producer is invalid")
    if "classification" in data and data["classification"] not in _CLASSIFICATIONS:
        raise OrphanEvidenceError(f"{schema} classification is invalid")
    for name in (
        "lease_id",
        "run_id",
        "generation",
        "session_id",
        "settlement_id",
        "recovery_owner_id",
        "owner_id",
        "owner_process_start",
        "boot_id",
        "source_id",
        "event_id",
        "candidate_id",
        "owner",
    ):
        if name in data:
            _text(data[name], name, maximum=128)
    if schema == "agy.expected-output-template.v1":
        if data["trusted_source"] != "agy-admission":
            raise OrphanEvidenceError("agy template trusted_source is invalid")
        if not isinstance(data["required"], bool):
            raise OrphanEvidenceError("agy template required must be a boolean")
        _positive(data["target_count"], "target_count")
        if data["expected_output_template_sha256"] != _digest(
            data, "expected_output_template_sha256", "sha256"
        ):
            raise OrphanEvidenceError("agy template digest does not match")
    elif schema == "expected_output.v1":
        _text(data["lease_id"], "lease_id", maximum=128)
        _text(data["run_id"], "run_id", maximum=128)
        if data["expected_output_sha256"] != _digest(data, "expected_output_sha256", "sha256"):
            raise OrphanEvidenceError("expected output digest does not match")
    elif schema == "settlement_close.v1":
        if data["phase"] != "closed" or data["terminal"] is not True:
            raise OrphanEvidenceError("settlement close must be terminal and closed")
        if data["receipt_sha256"] != _digest(data, "receipt_sha256", "sha256"):
            raise OrphanEvidenceError("settlement close receipt digest does not match")
    elif schema == "settlement_recovery_intent.v1":
        if data["expected_phase"] not in {"prepared", "committing", "ambiguous"}:
            raise OrphanEvidenceError("settlement recovery phase is invalid")
        _positive(data["recovery_owner_pid"], "recovery_owner_pid")
        _nonnegative(data["recovery_owner_effective_uid"], "recovery_owner_effective_uid")
    elif schema == "quarantine_manifest.v1":
        if data["reason"] not in {"expired-lease", "late-after-close"}:
            raise OrphanEvidenceError("quarantine reason is invalid")
        size = _nonnegative(data["payload_bytes"], "payload_bytes")
        if size >= MAX_PAYLOAD_BYTES:
            raise OrphanEvidenceError("quarantine payload_bytes exceeds its strict item cap")
        _timestamp(data["observed_at"], "observed_at")
        if (data["reason"] == "expired-lease") == ("receipt_sha256" in data):
            raise OrphanEvidenceError("quarantine receipt binding does not match its reason")
    elif schema == "orphan_event.v1":
        _timestamp(data["observed_at"], "observed_at")
        if (data["classification"] == "late-write-after-close") != ("receipt_sha256" in data):
            raise OrphanEvidenceError("orphan event receipt binding does not match classification")
    elif schema == "orphan_candidate.v1":
        if data["authoritative_terminal"] is not True:
            raise OrphanEvidenceError("orphan candidate requires authoritative terminal evidence")
        if data["owner"] != _OWNERS[data["producer"]]:
            raise OrphanEvidenceError("orphan candidate owner does not match producer")
        has_receipt = "receipt_sha256" in data
        if data["classification"] == "late-write-after-close" and not has_receipt:
            raise OrphanEvidenceError(
                "orphan candidate receipt binding does not match classification"
            )
        if has_receipt and data["classification"] not in {
            "late-write-after-close",
            "stalled",
            "empty-artifacts",
        }:
            raise OrphanEvidenceError(
                "orphan candidate receipt binding does not match classification"
            )
    elif schema == "reservation.v1":
        if data["state"] not in {"reserved", "payload-written", "manifest-written"}:
            raise OrphanEvidenceError("reservation state is invalid")
        _positive(data["owner_pid"], "owner_pid")
        _positive(data["created_monotonic_ns"], "created_monotonic_ns")
        _timestamp(data["created_at"], "created_at")
        size = _nonnegative(data["payload_bytes"], "payload_bytes")
        if size >= MAX_PAYLOAD_BYTES:
            raise OrphanEvidenceError("reservation payload_bytes exceeds its strict item cap")
        if (data["state"] == "manifest-written") != ("manifest_sha256" in data):
            raise OrphanEvidenceError("reservation manifest digest does not match its state")
    elif schema == "agy.lease-admission.v1":
        if data["mutation"] != "read-write":
            raise OrphanEvidenceError("agy lease admission mutation must be read-write")
        _positive(data["owner_pid"], "owner_pid")
        _positive(data["session_limit"], "session_limit")
        _positive(data["aggregate_limit"], "aggregate_limit")
        _positive(data["ttl_seconds"], "ttl_seconds")
        if data["session_limit"] > data["aggregate_limit"]:
            raise OrphanEvidenceError("agy session_limit exceeds aggregate_limit")
    return data


def loads_record(raw: str | bytes) -> dict[str, Any]:
    def no_duplicates(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
        result: dict[str, Any] = {}
        for key, value in pairs:
            if key in result:
                raise OrphanEvidenceError(f"duplicate JSON key: {key}")
            result[key] = value
        return result

    try:
        data = json.loads(raw, object_pairs_hook=no_duplicates)
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise OrphanEvidenceError("record is not valid JSON") from exc
    if not isinstance(data, dict):
        raise OrphanEvidenceError("record must be an object")
    return validate_record(data)


def _finalize(value: dict[str, Any]) -> dict[str, Any]:
    value["sha256"] = _digest(value)
    return validate_record(value)


def build_expected_output_template(
    source_id: str,
    *,
    required: bool,
    artifact_keys: Sequence[str],
    target_count: int,
) -> dict[str, Any]:
    if not isinstance(required, bool):
        raise OrphanEvidenceError("required must be a boolean")
    template: dict[str, Any] = {
        "schema": "agy.expected-output-template.v1",
        "trusted_source": "agy-admission",
        "source_id": _text(source_id, "source_id", maximum=128),
        "required": required,
        "artifact_keys": sorted({_text(item, "artifact key") for item in artifact_keys}),
        "target_count": _positive(target_count, "target_count"),
    }
    template["expected_output_template_sha256"] = _digest(template)
    return _finalize(template)


def bind_expected_output(
    template: Mapping[str, Any],
    *,
    resource: Mapping[str, Any],
    token: Any,
    lease_id: str,
    producer: str,
    run_id: str,
) -> dict[str, Any]:
    trusted = validate_record(template)
    if trusted["schema"] != "agy.expected-output-template.v1":
        raise OrphanEvidenceError("expected output requires the trusted agy template")
    parsed_token = token_dict(token)
    record: dict[str, Any] = {
        "schema": "expected_output.v1",
        "expected_output_template_sha256": trusted["expected_output_template_sha256"],
        "resource_ref": resource_ref(resource),
        "token": parsed_token,
        "lease_id": _text(lease_id, "lease_id", maximum=128),
        "generation": generation(parsed_token),
        "producer": producer,
        "run_id": _text(run_id, "run_id", maximum=128),
    }
    record["expected_output_sha256"] = _digest(record)
    return _finalize(record)


def build_recovery_intent(
    settlement: Any,
    *,
    recovery_owner_id: str,
    recovery_owner_pid: int,
    recovery_owner_process_start: str,
    recovery_owner_boot_id: str,
    recovery_owner_effective_uid: int,
) -> dict[str, Any]:
    record: dict[str, Any] = {
        "schema": "settlement_recovery_intent.v1",
        "resource_ref": resource_ref(settlement.resource_ref),
        "token": token_dict(settlement.token),
        "lease_id": settlement.lease_id,
        "generation": generation(settlement.token),
        "settlement_id": settlement.settlement_id,
        "session_id": settlement.session_id,
        "policy_sha256": settlement.policy_sha256,
        "expected_phase": settlement.phase,
        "protected_write_intent_sha256": settlement.protected_write_intent_sha256,
        "recovery_owner_id": recovery_owner_id,
        "recovery_owner_pid": recovery_owner_pid,
        "recovery_owner_process_start": recovery_owner_process_start,
        "recovery_owner_boot_id": recovery_owner_boot_id,
        "recovery_owner_effective_uid": recovery_owner_effective_uid,
    }
    return _finalize(record)


def _safe_name(value: str, name: str) -> str:
    text = _text(value, name)
    if text in {".", ".."} or "/" in text or "\\" in text or "\x00" in text:
        raise OrphanEvidenceError(f"{name} is not a safe path component")
    return text


def _ensure_dir(path: Path) -> None:
    if path.exists() or path.is_symlink():
        metadata = path.lstat()
        if (
            not stat.S_ISDIR(metadata.st_mode)
            or stat.S_ISLNK(metadata.st_mode)
            or metadata.st_uid != os.geteuid()
            or stat.S_IMODE(metadata.st_mode) != 0o700
        ):
            raise OrphanEvidenceError(f"unsafe evidence directory: {path}")
        return
    missing: list[Path] = []
    current = path
    while not current.exists() and not current.is_symlink():
        missing.append(current)
        current = current.parent
    for directory in reversed(missing):
        directory.mkdir(mode=0o700)
        os.chmod(directory, 0o700, follow_symlinks=False)


def _atomic_write(path: Path, content: bytes) -> None:
    _ensure_dir(path.parent)
    temp = path.with_name(f".{path.name}.{os.getpid()}.{time.monotonic_ns()}.tmp")
    fd = os.open(temp, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    try:
        os.fchmod(fd, 0o600)
        remaining = memoryview(content)
        while remaining:
            remaining = remaining[os.write(fd, remaining) :]
        os.fsync(fd)
    finally:
        os.close(fd)
    os.replace(temp, path)
    directory_fd = os.open(path.parent, os.O_RDONLY)
    try:
        os.fsync(directory_fd)
    finally:
        os.close(directory_fd)


def _write_once(path: Path, content: bytes) -> bool:
    _ensure_dir(path.parent)
    temp = path.with_name(f".{path.name}.{os.getpid()}.{time.monotonic_ns()}.tmp")
    fd = os.open(temp, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    try:
        os.fchmod(fd, 0o600)
        os.write(fd, content)
        os.fsync(fd)
    finally:
        os.close(fd)
    try:
        os.link(temp, path)
        return True
    except FileExistsError:
        return False
    finally:
        with contextlib.suppress(FileNotFoundError):
            temp.unlink()


@dataclass(frozen=True)
class QuarantineStore:
    root: Path
    providers: Providers = Providers()

    @classmethod
    def for_root(cls, root: Path | str, providers: Providers | None = None) -> QuarantineStore:
        path = Path(os.path.abspath(Path(root).expanduser()))
        return cls(path, providers or Providers())

    def ensure(self) -> QuarantineStore:
        _ensure_dir(self.root)
        return self

    @contextlib.contextmanager
    def locked(self) -> Iterator[None]:
        self.ensure()
        lock_path = self.root / LOCK
        fd = os.open(lock_path, os.O_RDWR | os.O_CREAT | getattr(os, "O_NOFOLLOW", 0), 0o600)
        try:
            os.fchmod(fd, 0o600)
            opened = os.fstat(fd)
            if not stat.S_ISREG(opened.st_mode) or opened.st_uid != os.geteuid():
                raise OrphanEvidenceError("unsafe quarantine lock")
            fcntl.flock(fd, fcntl.LOCK_EX)
            yield
        finally:
            with contextlib.suppress(OSError):
                fcntl.flock(fd, fcntl.LOCK_UN)
            os.close(fd)

    def final_dir(self, resource: Mapping[str, Any], token: Any, payload_sha256: str) -> Path:
        return (
            self.root
            / QUARANTINE
            / resource_sha256(resource)
            / _safe_name(generation(token), "generation")
            / _sha(payload_sha256, "payload_sha256")
        )


def _read_json(path: Path) -> dict[str, Any] | None:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None
    return cast(dict[str, Any], value) if isinstance(value, dict) else None


def _occupancy(store: QuarantineStore) -> tuple[int, int]:
    count = 0
    total = 0
    committed_root = store.root / QUARANTINE
    if committed_root.is_dir():
        for manifest_path in committed_root.rglob("manifest.json"):
            if manifest_path.is_symlink():
                raise OrphanEvidenceError("quarantine contains a symlink")
            try:
                manifest = loads_record(manifest_path.read_bytes())
            except OSError as exc:
                raise OrphanEvidenceError(f"cannot inspect quarantine occupancy: {exc}") from exc
            if manifest["schema"] != "quarantine_manifest.v1":
                raise OrphanEvidenceError("quarantine occupancy contains a non-manifest record")
            count += 1
            total += manifest["payload_bytes"]
    staging_root = store.root / STAGING
    if staging_root.is_dir():
        for reservation_path in staging_root.rglob("reservation.json"):
            try:
                reservation = loads_record(reservation_path.read_bytes())
            except OSError as exc:
                raise OrphanEvidenceError(f"cannot inspect quarantine reservation: {exc}") from exc
            if reservation["schema"] != "reservation.v1":
                raise OrphanEvidenceError("quarantine staging contains a non-reservation record")
            count += 1
            total += reservation["payload_bytes"]
    return count, total


def _manifest(
    *,
    resource: Mapping[str, Any],
    token: Any,
    lease_id: str,
    producer: str,
    run_id: str,
    reason: str,
    payload_sha256: str,
    payload_bytes: int,
    observed_at: str,
    expected_output_sha256: str,
    evidence_refs: Sequence[str],
    receipt_sha256: str | None,
) -> dict[str, Any]:
    if reason not in {"expired-lease", "late-after-close"}:
        raise OrphanEvidenceError("quarantine reason is invalid")
    if (reason == "expired-lease") != (receipt_sha256 is None):
        raise OrphanEvidenceError("only late-after-close quarantine may carry a receipt")
    record: dict[str, Any] = {
        "schema": "quarantine_manifest.v1",
        "resource_ref": resource_ref(resource),
        "token": token_dict(token),
        "lease_id": _text(lease_id, "lease_id", maximum=128),
        "generation": generation(token),
        "producer": producer,
        "run_id": _text(run_id, "run_id", maximum=128),
        "reason": reason,
        "payload_sha256": _sha(payload_sha256, "payload_sha256"),
        "payload_bytes": payload_bytes,
        "observed_at": _timestamp(observed_at, "observed_at"),
        "expected_output_sha256": _sha(expected_output_sha256, "expected_output_sha256"),
        "evidence_refs": sorted({_text(item, "evidence_ref") for item in evidence_refs}),
    }
    if receipt_sha256 is not None:
        record["receipt_sha256"] = _sha(receipt_sha256, "receipt_sha256")
    return _finalize(record)


def quarantine_late_write(
    store: QuarantineStore,
    payload: bytes,
    *,
    resource: Mapping[str, Any],
    token: Any,
    lease_id: str,
    producer: str,
    run_id: str,
    reason: Literal["expired-lease", "late-after-close"],
    expected_output_sha256: str,
    evidence_refs: Sequence[str] = (),
    receipt_sha256: str | None = None,
    publish_guard: Callable[[Callable[[], None]], bool] | None = None,
) -> Path:
    if len(payload) >= MAX_PAYLOAD_BYTES:
        raise OrphanEvidenceError("quarantine payload must be smaller than 128 MiB")
    payload_digest = hashlib.sha256(payload).hexdigest()
    observed = utc_text(store.providers.wall_now())
    manifest = _manifest(
        resource=resource,
        token=token,
        lease_id=lease_id,
        producer=producer,
        run_id=run_id,
        reason=reason,
        payload_sha256=payload_digest,
        payload_bytes=len(payload),
        observed_at=observed,
        expected_output_sha256=expected_output_sha256,
        evidence_refs=evidence_refs,
        receipt_sha256=receipt_sha256,
    )
    destination = store.final_dir(resource, token, payload_digest)
    with store.locked():
        # A killed publisher may have reserved the last byte/item slot. Recovery and admission are
        # one serialized operation so abandoned reservations cannot permanently wedge capacity.
        recover_quarantine(store, _already_locked=True)
        if (destination / "committed").is_file():
            if publish_guard is not None and not publish_guard(lambda: None):
                raise _SupersededDuringPublicationError
            existing = read_quarantine(destination)
            stable_existing = {
                key: value
                for key, value in existing[1].items()
                if key not in {"observed_at", "sha256"}
            }
            stable_manifest = {
                key: value
                for key, value in manifest.items()
                if key not in {"observed_at", "sha256"}
            }
            if existing[0] != payload or stable_existing != stable_manifest:
                raise OrphanEvidenceError("conflicting quarantine publication")
            return destination
        count, total = _occupancy(store)
        if count >= MAX_QUARANTINE_ITEMS or total + len(payload) > MAX_QUARANTINE_BYTES:
            raise OrphanEvidenceError("quarantine capacity is exhausted; evidence was not evicted")
        reservation_id = str(uuid.uuid4())
        staging = store.root / STAGING / reservation_id
        _ensure_dir(staging)
        process_start = store.providers.process_identity(os.getpid())
        if not process_start:
            raise OrphanEvidenceError("owner process identity is unavailable")
        reservation: dict[str, Any] = {
            "schema": "reservation.v1",
            "reservation_id": reservation_id,
            "payload_sha256": payload_digest,
            "payload_bytes": len(payload),
            "owner_pid": os.getpid(),
            "owner_process_start": process_start,
            "boot_id": _text(store.providers.boot_id(), "boot_id", maximum=128),
            "created_at": observed,
            "created_monotonic_ns": _positive(
                store.providers.monotonic_ns(), "created_monotonic_ns"
            ),
            "state": "reserved",
        }
        _atomic_write(staging / "reservation.json", canonical_json(reservation) + b"\n")
        _atomic_write(staging / "payload.bin", payload)
        reservation["state"] = "payload-written"
        _atomic_write(staging / "reservation.json", canonical_json(reservation) + b"\n")
        manifest_bytes = canonical_json(manifest) + b"\n"
        _atomic_write(staging / "manifest.json", manifest_bytes)
        reservation["state"] = "manifest-written"
        reservation["manifest_sha256"] = hashlib.sha256(manifest_bytes).hexdigest()
        _atomic_write(staging / "reservation.json", canonical_json(reservation) + b"\n")
        _ensure_dir(destination.parent)

        def publish() -> None:
            os.replace(staging, destination)
            _write_once(destination / "committed", b"")

        if publish_guard is not None and not publish_guard(publish):
            _remove_rejected(staging)
            raise _SupersededDuringPublicationError
        if publish_guard is None:
            publish()
        return destination


def read_quarantine(directory: Path) -> tuple[bytes, dict[str, Any]]:
    if directory.is_symlink() or not directory.is_dir():
        raise OrphanEvidenceError("quarantine entry directory is unsafe")
    entries = {item.name: item for item in directory.iterdir()}
    if set(entries) != {"reservation.json", "payload.bin", "manifest.json", "committed"}:
        raise OrphanEvidenceError("quarantine entry has an invalid closed file set")
    if any(item.is_symlink() or not item.is_file() for item in entries.values()):
        raise OrphanEvidenceError("quarantine entry contains an unsafe file")
    if entries["committed"].read_bytes() != b"":
        raise OrphanEvidenceError("quarantine commit marker is invalid")
    if not entries["committed"].is_file():
        raise OrphanEvidenceError("quarantine entry is not committed")
    reservation = loads_record(entries["reservation.json"].read_bytes())
    if reservation["schema"] != "reservation.v1" or reservation["state"] != "manifest-written":
        raise OrphanEvidenceError("quarantine reservation is not publication-complete")
    payload = entries["payload.bin"].read_bytes()
    manifest_raw = entries["manifest.json"].read_bytes()
    manifest = loads_record(manifest_raw)
    if manifest["schema"] != "quarantine_manifest.v1":
        raise OrphanEvidenceError("quarantine manifest schema is invalid")
    if (
        len(payload) != manifest["payload_bytes"]
        or hashlib.sha256(payload).hexdigest() != manifest["payload_sha256"]
        or reservation["payload_bytes"] != manifest["payload_bytes"]
        or reservation["payload_sha256"] != manifest["payload_sha256"]
        or reservation.get("manifest_sha256") != hashlib.sha256(manifest_raw).hexdigest()
    ):
        raise OrphanEvidenceError("quarantine payload digest does not match")
    return payload, manifest


def _remove_rejected(path: Path) -> None:
    """Remove one rejected, never-committed item without following attacker-controlled links."""

    if path.is_symlink() or not path.is_dir():
        path.unlink(missing_ok=True)
    else:
        shutil.rmtree(path)


def _validate_staging_files(
    staging: Path, reservation: Mapping[str, Any]
) -> tuple[bytes | None, dict[str, Any] | None]:
    entries = {item.name: item for item in staging.iterdir()}
    if set(entries) - {"reservation.json", "payload.bin", "manifest.json"}:
        raise OrphanEvidenceError("quarantine staging contains unknown files")
    if any(item.is_symlink() or not item.is_file() for item in entries.values()):
        raise OrphanEvidenceError("quarantine staging contains an unsafe file")

    payload: bytes | None = None
    payload_path = entries.get("payload.bin")
    if payload_path is not None:
        payload = payload_path.read_bytes()
        if (
            len(payload) != reservation["payload_bytes"]
            or hashlib.sha256(payload).hexdigest() != reservation["payload_sha256"]
        ):
            raise OrphanEvidenceError("quarantine staging payload does not match reservation")
    if reservation["state"] in {"payload-written", "manifest-written"} and payload is None:
        raise OrphanEvidenceError("quarantine staging state requires payload bytes")

    manifest: dict[str, Any] | None = None
    manifest_path = entries.get("manifest.json")
    if manifest_path is not None:
        manifest_bytes = manifest_path.read_bytes()
        manifest = loads_record(manifest_bytes)
        if manifest["schema"] != "quarantine_manifest.v1":
            raise OrphanEvidenceError("quarantine staging manifest schema is invalid")
        if payload is None:
            raise OrphanEvidenceError("quarantine staging manifest lacks payload bytes")
        if (
            manifest["payload_sha256"] != reservation["payload_sha256"]
            or manifest["payload_bytes"] != reservation["payload_bytes"]
        ):
            raise OrphanEvidenceError("quarantine staging manifest contradicts reservation")
        if (
            reservation["state"] == "manifest-written"
            and reservation.get("manifest_sha256") != hashlib.sha256(manifest_bytes).hexdigest()
        ):
            raise OrphanEvidenceError("quarantine staging manifest digest does not match")
    if reservation["state"] == "manifest-written" and manifest is None:
        raise OrphanEvidenceError("quarantine staging state requires a manifest")
    return payload, manifest


def _reservation_owner_is_live(store: QuarantineStore, reservation: Mapping[str, Any]) -> bool:
    pid = reservation.get("owner_pid")
    return bool(
        isinstance(pid, int)
        and not isinstance(pid, bool)
        and reservation.get("boot_id") == store.providers.boot_id()
        and store.providers.process_exists(pid)
        and store.providers.process_identity(pid) == reservation.get("owner_process_start")
    )


def recover_quarantine(
    store: QuarantineStore, *, _already_locked: bool = False
) -> dict[str, list[str]]:
    result: dict[str, list[str]] = {
        "retained": [],
        "finalized": [],
        "discarded": [],
        "alerts": [],
    }
    lock = contextlib.nullcontext() if _already_locked else store.locked()
    with lock:
        staging_root = store.root / STAGING
        if staging_root.is_dir():
            for staging in sorted(staging_root.iterdir()):
                if staging.is_symlink() or not staging.is_dir():
                    _remove_rejected(staging)
                    result["discarded"].append(staging.name)
                    continue
                try:
                    reservation = loads_record((staging / "reservation.json").read_bytes())
                except (OSError, OrphanEvidenceError):
                    _remove_rejected(staging)
                    result["discarded"].append(staging.name)
                    continue
                if (
                    reservation["schema"] != "reservation.v1"
                    or reservation["reservation_id"] != staging.name
                ):
                    _remove_rejected(staging)
                    result["discarded"].append(staging.name)
                    continue
                try:
                    payload, manifest = _validate_staging_files(staging, reservation)
                except (OSError, OrphanEvidenceError, KeyError):
                    _remove_rejected(staging)
                    result["discarded"].append(staging.name)
                    continue
                live = _reservation_owner_is_live(store, reservation)
                age = (
                    max(
                        0,
                        store.providers.monotonic_ns()
                        - int(reservation.get("created_monotonic_ns", 0)),
                    )
                    / 1_000_000_000
                )
                if live:
                    result["retained"].append(staging.name)
                    if age >= LIVE_RESERVATION_ALERT_SECONDS:
                        result["alerts"].append(staging.name)
                    continue
                if (
                    reservation["state"] != "manifest-written"
                    or payload is None
                    or manifest is None
                ):
                    _remove_rejected(staging)
                    result["discarded"].append(staging.name)
                    continue
                destination = store.final_dir(
                    manifest["resource_ref"], manifest["token"], manifest["payload_sha256"]
                )
                if (destination / "committed").is_file():
                    existing_payload, existing_manifest = read_quarantine(destination)
                    if existing_payload != payload or existing_manifest != manifest:
                        raise OrphanEvidenceError("conflicting recovered quarantine publication")
                    _remove_rejected(staging)
                    result["finalized"].append(destination.as_posix())
                    continue
                _ensure_dir(destination.parent)
                os.replace(staging, destination)
                _write_once(destination / "committed", b"")
                result["finalized"].append(destination.as_posix())
        quarantine_root = store.root / QUARANTINE
        if quarantine_root.is_dir():
            for manifest_path in quarantine_root.rglob("manifest.json"):
                directory = manifest_path.parent
                if (directory / "committed").exists():
                    continue
                try:
                    if manifest_path.is_symlink() or directory.is_symlink():
                        raise OrphanEvidenceError("incomplete publication contains a symlink")
                    reservation = loads_record((directory / "reservation.json").read_bytes())
                    payload, manifest = _validate_staging_files(directory, reservation)
                    if payload is None or manifest is None:
                        raise OrphanEvidenceError("incomplete publication lacks durable evidence")
                    if _reservation_owner_is_live(store, reservation):
                        result["retained"].append(directory.as_posix())
                        continue
                    expected_directory = store.final_dir(
                        manifest["resource_ref"], manifest["token"], manifest["payload_sha256"]
                    )
                    if (
                        manifest["schema"] != "quarantine_manifest.v1"
                        or reservation["state"] != "manifest-written"
                        or directory != expected_directory
                        or {item.name for item in directory.iterdir()}
                        != {"reservation.json", "payload.bin", "manifest.json"}
                    ):
                        raise OrphanEvidenceError("incomplete publication is corrupt")
                except (OSError, OrphanEvidenceError, KeyError):
                    _remove_rejected(directory)
                    result["discarded"].append(directory.as_posix())
                    continue
                _write_once(directory / "committed", b"")
                result["finalized"].append(directory.as_posix())
    return result


def build_event(
    *,
    lease: Any,
    producer: str,
    run_id: str,
    classification: str,
    expected_output_sha256: str,
    evidence_refs: Sequence[str],
    payload_refs: Sequence[str],
    observed_at: str,
    receipt_sha256: str | None = None,
) -> dict[str, Any]:
    if classification not in _CLASSIFICATIONS:
        raise OrphanEvidenceError("event classification is invalid")
    event_seed = f"{run_id}:{generation(lease.token)}:{classification}"
    record: dict[str, Any] = {
        "schema": "orphan_event.v1",
        "event_id": hashlib.sha256(event_seed.encode()).hexdigest(),
        "resource_ref": resource_ref(lease.resource_ref),
        "token": token_dict(lease.token),
        "lease_id": lease.lease_id,
        "generation": generation(lease.token),
        "producer": producer,
        "run_id": run_id,
        "classification": classification,
        "observed_at": _timestamp(observed_at, "observed_at"),
        "expected_output_sha256": expected_output_sha256,
        "evidence_refs": sorted(set(evidence_refs)),
        "payload_refs": sorted(set(payload_refs)),
    }
    if receipt_sha256 is not None:
        record["receipt_sha256"] = receipt_sha256
    return _finalize(record)


def write_event(store: QuarantineStore, event: Mapping[str, Any]) -> Path:
    record = validate_record(event)
    if record["schema"] != "orphan_event.v1":
        raise OrphanEvidenceError("event publication requires orphan_event.v1")
    with store.locked():
        recover_quarantine(store, _already_locked=True)
        for ref in record["payload_refs"]:
            relative = Path(ref)
            if relative.is_absolute() or ".." in relative.parts:
                raise OrphanEvidenceError("orphan event payload_ref is not a safe relative path")
            directory = store.root / relative
            payload, manifest = read_quarantine(directory)
            del payload  # Reading and hashing it is the durable-evidence validation boundary.
            for field in (
                "resource_ref",
                "token",
                "lease_id",
                "generation",
                "producer",
                "run_id",
                "expected_output_sha256",
                "observed_at",
            ):
                if manifest[field] != record[field]:
                    raise OrphanEvidenceError(f"orphan event payload evidence contradicts {field}")
            if manifest.get("receipt_sha256") != record.get("receipt_sha256"):
                raise OrphanEvidenceError("orphan event payload receipt binding does not match")

        digest = resource_sha256(record["resource_ref"])
        path = store.root / EVENTS / digest / f"{_safe_name(record['event_id'], 'event_id')}.json"
        encoded = canonical_json(record) + b"\n"
        if not _write_once(path, encoded):
            existing = loads_record(path.read_bytes())
            stable_existing = {
                key: value
                for key, value in existing.items()
                if key not in {"observed_at", "sha256"}
            }
            stable_record = {
                key: value for key, value in record.items() if key not in {"observed_at", "sha256"}
            }
            if stable_existing != stable_record:
                raise OrphanEvidenceError("conflicting immutable orphan event")
        return path


def write_close_seal(store: QuarantineStore, receipt: Mapping[str, Any]) -> Path:
    record = validate_record(receipt)
    if record["schema"] != "settlement_close.v1":
        raise OrphanEvidenceError("close seal requires settlement_close.v1")
    digest = resource_sha256(record["resource_ref"])
    path = store.root / SEALS / digest / f"{_safe_name(record['generation'], 'generation')}.json"
    encoded = canonical_json(record) + b"\n"
    if not _write_once(path, encoded) and path.read_bytes() != encoded:
        raise OrphanEvidenceError("conflicting immutable close seal")
    return path


def contain_refused_write(
    broker: Any,
    store: QuarantineStore,
    lease: Any,
    payload: bytes,
    *,
    producer: str,
    run_id: str,
    expected_output_sha256: str,
    evidence_refs: Sequence[str] = (),
) -> tuple[Disposition, dict[str, Any], Path | None]:
    if lease.resource_ref is None:
        raise OrphanEvidenceError("refused write lease lacks a canonical resource")
    observed = utc_text(store.providers.wall_now())
    try:
        state = broker.classify_token(lease.resource_ref, lease.token)
    except Exception as exc:  # noqa: BLE001 - corrupt authority must not be guessed.
        raise OrphanEvidenceError(f"AUTHORITY_INVALID: {exc}") from exc
    payload_ref: Path | None = None
    receipt_sha256: str | None = None
    if state == "superseded":
        disposition: Disposition = "ORPHAN_WRITE_BLOCKED"
        classification = "superseded-write-blocked"
    elif state == "expired":
        disposition = "EXPIRED_LEASE_QUARANTINED"
        classification = "expired-write-quarantined"
        try:
            payload_ref = quarantine_late_write(
                store,
                payload,
                resource=lease.resource_ref,
                token=lease.token,
                lease_id=lease.lease_id,
                producer=producer,
                run_id=run_id,
                reason="expired-lease",
                expected_output_sha256=expected_output_sha256,
                evidence_refs=evidence_refs,
                publish_guard=lambda publish: broker.publish_if_token_state(
                    lease.resource_ref,
                    lease.token,
                    expected_state="expired",
                    publish=publish,
                ),
            )
        except _SupersededDuringPublicationError:
            disposition = "ORPHAN_WRITE_BLOCKED"
            classification = "superseded-write-blocked"
        else:
            observed = read_quarantine(payload_ref)[1]["observed_at"]
    elif state == "closed":
        head = broker.inspect_resource_head(lease.resource_ref)
        close = head.get("close_receipt") if isinstance(head, dict) else None
        if (
            not isinstance(close, dict)
            or close.get("token") != token_dict(lease.token)
            or close.get("lease_id") != lease.lease_id
        ):
            # ``classify_token`` is a snapshot. A successor can replace a closed head before
            # this forensic projection reads it. Confirm the original state under the broker lock
            # before calling that mismatch corrupt authority; a false result is a stale write and
            # deliberately has no payload publication.
            still_closed = broker.publish_if_token_state(
                lease.resource_ref,
                lease.token,
                expected_state="closed",
                publish=lambda: None,
            )
            if not still_closed:
                disposition = "ORPHAN_WRITE_BLOCKED"
                classification = "superseded-write-blocked"
            else:
                disposition = "EVIDENCE_INTEGRITY_ERROR"
                classification = "evidence-integrity-error"
        else:
            receipt_sha256 = _sha(close.get("receipt_sha256"), "receipt_sha256")
            disposition = "LATE_WRITE_AFTER_CLOSE"
            classification = "late-write-after-close"
            try:
                payload_ref = quarantine_late_write(
                    store,
                    payload,
                    resource=lease.resource_ref,
                    token=lease.token,
                    lease_id=lease.lease_id,
                    producer=producer,
                    run_id=run_id,
                    reason="late-after-close",
                    expected_output_sha256=expected_output_sha256,
                    evidence_refs=evidence_refs,
                    receipt_sha256=receipt_sha256,
                    publish_guard=lambda publish: broker.publish_if_token_state(
                        lease.resource_ref,
                        lease.token,
                        expected_state="closed",
                        publish=publish,
                    ),
                )
            except _SupersededDuringPublicationError:
                disposition = "ORPHAN_WRITE_BLOCKED"
                classification = "superseded-write-blocked"
                receipt_sha256 = None
            else:
                observed = read_quarantine(payload_ref)[1]["observed_at"]
    else:
        raise OrphanEvidenceError(
            "current authority must commit through the broker, not quarantine"
        )
    event = build_event(
        lease=lease,
        producer=producer,
        run_id=run_id,
        classification=classification,
        expected_output_sha256=expected_output_sha256,
        evidence_refs=evidence_refs,
        payload_refs=(
            [] if payload_ref is None else [payload_ref.relative_to(store.root).as_posix()]
        ),
        observed_at=observed,
        receipt_sha256=receipt_sha256,
    )
    write_event(store, event)
    return disposition, event, payload_ref


def _head_token(head: Mapping[str, Any]) -> dict[str, Any]:
    if set(head) != {
        "resource_ref",
        "broker_epoch",
        "fencing_sequence",
        "lease_id",
        "close_receipt",
    }:
        raise OrphanEvidenceError("broker projection head has an invalid closed shape")
    return token_dict(
        {
            "broker_epoch": head["broker_epoch"],
            "fencing_sequence": head["fencing_sequence"],
        }
    )


def _validated_head(head: Mapping[str, Any]) -> tuple[dict[str, Any], dict[str, Any] | None]:
    parsed_token = _head_token(head)
    close_raw = head.get("close_receipt")
    if close_raw is None:
        return parsed_token, None
    if not isinstance(close_raw, Mapping):
        raise OrphanEvidenceError("broker projection close receipt is invalid")
    close = validate_record(close_raw)
    if close["schema"] != "settlement_close.v1":
        raise OrphanEvidenceError("broker projection close receipt schema is invalid")
    if (
        close["resource_ref"] != resource_ref(head["resource_ref"])
        or close["token"] != parsed_token
        or close["lease_id"] != head["lease_id"]
    ):
        raise OrphanEvidenceError("broker projection close receipt contradicts its resource head")
    return parsed_token, close


def _candidate(
    *,
    classification: str,
    producer: str,
    run_id: str,
    resource: Mapping[str, Any],
    token: Any,
    lease_id: str,
    expected_output_sha256: str,
    evidence_refs: Sequence[str],
    receipt_sha256: str | None = None,
) -> dict[str, Any]:
    parsed_token = token_dict(token)
    seed = f"{producer}:{run_id}:{generation(parsed_token)}:{classification}"
    record: dict[str, Any] = {
        "schema": "orphan_candidate.v1",
        "candidate_id": hashlib.sha256(seed.encode()).hexdigest(),
        "classification": classification,
        "producer": producer,
        "run_id": _text(run_id, "run_id", maximum=128),
        "resource_ref": resource_ref(resource),
        "token": parsed_token,
        "lease_id": _text(lease_id, "lease_id", maximum=128),
        "generation": generation(parsed_token),
        "authoritative_terminal": True,
        "owner": _OWNERS[producer],
        "expected_output_sha256": _sha(expected_output_sha256, "expected_output_sha256"),
        "evidence_refs": sorted({_text(item, "evidence_ref") for item in evidence_refs}),
    }
    if receipt_sha256 is not None:
        record["receipt_sha256"] = _sha(receipt_sha256, "receipt_sha256")
    return _finalize(record)


def project_candidates(snapshot: Mapping[str, Any]) -> list[dict[str, Any]]:
    """Derive candidates only from broker authority plus immutable refusal-event identities.

    Event ``classification`` is never consulted when selecting a candidate disposition. Hot or
    bounded archived broker heads, canonical close receipts, and broker-derived lease state are the
    only classification authority.
    """

    if set(snapshot) != {
        "schema",
        "broker_heads",
        "archived_broker_heads",
        "broker_leases",
        "sources",
    }:
        raise OrphanEvidenceError("projection snapshot must use the exact closed shape")
    if snapshot["schema"] != "orphan-projection-snapshot.v1":
        raise OrphanEvidenceError("projection snapshot schema is invalid")
    heads_raw = snapshot["broker_heads"]
    archived_raw = snapshot["archived_broker_heads"]
    leases_raw = snapshot["broker_leases"]
    sources = snapshot["sources"]
    if (
        not isinstance(heads_raw, Mapping)
        or not isinstance(archived_raw, Mapping)
        or not isinstance(leases_raw, list)
        or not isinstance(sources, list)
    ):
        raise OrphanEvidenceError("projection snapshot heads or sources are invalid")
    if len(archived_raw) > 128:
        raise OrphanEvidenceError("projection archived broker heads exceed the bounded inspection")
    heads: dict[str, tuple[Mapping[str, Any], dict[str, Any], dict[str, Any] | None]] = {}
    for head_kind, collection in (("archived", archived_raw), ("hot", heads_raw)):
        for digest, value in collection.items():
            if not isinstance(digest, str) or not isinstance(value, Mapping):
                raise OrphanEvidenceError(f"projection {head_kind} broker head entry is invalid")
            head_resource = resource_ref(value.get("resource_ref"))
            if digest != resource_sha256(head_resource):
                raise OrphanEvidenceError("projection broker head digest does not match resource")
            parsed_token, close = _validated_head(value)
            # A hot successor is current authority; an older same-resource archive is historical.
            heads[digest] = (value, parsed_token, close)

    leases: dict[tuple[str, str, str], str] = {}
    for raw_lease in leases_raw:
        if not isinstance(raw_lease, Mapping) or set(raw_lease) != {
            "lease_id",
            "resource_ref",
            "broker_epoch",
            "fencing_sequence",
            "derived_state",
        }:
            raise OrphanEvidenceError("projection broker lease has an invalid closed shape")
        lease_resource = resource_ref(raw_lease["resource_ref"])
        lease_token = token_dict(
            {
                "broker_epoch": raw_lease["broker_epoch"],
                "fencing_sequence": raw_lease["fencing_sequence"],
            }
        )
        lease_id = _text(raw_lease["lease_id"], "lease_id", maximum=128)
        derived_state = raw_lease["derived_state"]
        if derived_state not in {"live", "expired"}:
            raise OrphanEvidenceError("projection broker lease derived_state is invalid")
        key = (resource_sha256(lease_resource), generation(lease_token), lease_id)
        if key in leases:
            raise OrphanEvidenceError("projection contains a duplicate broker lease identity")
        leases[key] = derived_state

    candidates: list[dict[str, Any]] = []
    for raw in sources:
        if not isinstance(raw, Mapping):
            raise OrphanEvidenceError("projection source must be an object")
        if raw.get("schema") == "orphan_projection_fact.v1":
            expected_fields = {
                "schema",
                "classification",
                "producer",
                "run_id",
                "resource_ref",
                "token",
                "lease_id",
                "expected_output_sha256",
                "receipt_sha256",
                "evidence_refs",
                "authoritative_terminal",
            }
            if set(raw) != expected_fields:
                raise OrphanEvidenceError("projection fact has an invalid closed shape")
            classification = raw["classification"]
            if classification not in {
                "stalled",
                "empty-artifacts",
                "evidence-integrity-error",
            }:
                raise OrphanEvidenceError("projection fact classification is invalid")
            producer = raw["producer"]
            if producer not in _PRODUCERS:
                raise OrphanEvidenceError("projection fact producer is invalid")
            resource = resource_ref(raw["resource_ref"])
            digest = resource_sha256(resource)
            selected = heads.get(digest)
            if selected is None:
                raise OrphanEvidenceError("projection fact lacks its canonical broker head")
            head, head_token, close = selected
            fact_token = token_dict(raw["token"])
            if (
                close is None
                or raw["authoritative_terminal"] is not True
                or fact_token != head_token
                or raw["lease_id"] != head["lease_id"]
                or raw["receipt_sha256"] != close["receipt_sha256"]
                or producer != close["producer"]
                or raw["run_id"] != close["run_id"]
                or raw["expected_output_sha256"] != close["expected_output_sha256"]
            ):
                raise OrphanEvidenceError(
                    "projection fact contradicts its canonical terminal receipt"
                )
            evidence_refs = raw["evidence_refs"]
            if not isinstance(evidence_refs, list) or evidence_refs != sorted(set(evidence_refs)):
                raise OrphanEvidenceError("projection fact evidence_refs are invalid")
            candidates.append(
                _candidate(
                    classification=classification,
                    producer=producer,
                    run_id=raw["run_id"],
                    resource=resource,
                    token=fact_token,
                    lease_id=raw["lease_id"],
                    expected_output_sha256=raw["expected_output_sha256"],
                    evidence_refs=evidence_refs,
                    receipt_sha256=(
                        raw["receipt_sha256"]
                        if classification in {"stalled", "empty-artifacts"}
                        else None
                    ),
                )
            )
            continue
        event = validate_record(raw)
        if event["schema"] != "orphan_event.v1":
            raise OrphanEvidenceError("projection sources must be canonical orphan events")
        digest = resource_sha256(event["resource_ref"])
        selected = heads.get(digest)
        if selected is None:
            raise OrphanEvidenceError("orphan event lacks its canonical broker head")
        head, head_token, close = selected
        event_token = token_dict(event["token"])
        if event_token != head_token or event["lease_id"] != head["lease_id"]:
            if (
                event_token["broker_epoch"] == head_token["broker_epoch"]
                and event_token["fencing_sequence"] < head_token["fencing_sequence"]
            ):
                classification = "superseded-write-blocked"
            else:
                raise OrphanEvidenceError("orphan event does not precede its canonical broker head")
            producer = event["producer"]
            run_id = event["run_id"]
            expected_output_sha256 = event["expected_output_sha256"]
            evidence_refs = event["evidence_refs"]
            receipt_sha256 = None
        elif close is not None:
            classification = "late-write-after-close"
            producer = close["producer"]
            run_id = close["run_id"]
            expected_output_sha256 = close["expected_output_sha256"]
            evidence_refs = close["evidence_refs"]
            receipt_sha256 = close["receipt_sha256"]
        else:
            lease_state = leases.get((digest, event["generation"], event["lease_id"]))
            if lease_state == "expired":
                classification = "expired-write-quarantined"
            else:
                # A live lease or a receipt-less released head cannot prove the event's assertion.
                classification = "evidence-integrity-error"
            producer = event["producer"]
            run_id = event["run_id"]
            expected_output_sha256 = event["expected_output_sha256"]
            evidence_refs = event["evidence_refs"]
            receipt_sha256 = None
        candidates.append(
            _candidate(
                classification=classification,
                producer=producer,
                run_id=run_id,
                resource=event["resource_ref"],
                token=event_token,
                lease_id=event["lease_id"],
                expected_output_sha256=expected_output_sha256,
                evidence_refs=[*evidence_refs, f"orphan-event:{event['sha256']}"],
                receipt_sha256=receipt_sha256,
            )
        )
    return sorted(candidates, key=lambda item: item["candidate_id"])
