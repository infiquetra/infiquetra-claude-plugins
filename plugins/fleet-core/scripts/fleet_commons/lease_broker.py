#!/usr/bin/env python3
"""Lease-backed fleet admission and fencing authority.

The registry is a small, closed JSON document. Every mutation holds a stable sibling ``flock``
across read, validation, decision, and atomic replacement. Expiry is always derived from the
same-boot monotonic renewal timestamp; no mutable status or expiry bit is stored.
"""

from __future__ import annotations

import contextlib
import ctypes
import fcntl
import hashlib
import json
import os
import stat
import subprocess
import sys
import threading
import time
import uuid
from collections.abc import Callable, Iterator, Mapping, Sequence
from dataclasses import dataclass, replace
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any, Literal, cast

SCHEMA = "fleet_lease_registry.v1"
PROTOCOL_VERSION = 2
STATE_ENV = "INFIQUETRA_FLEET_STATE_DIR"
XDG_STATE_ENV = "XDG_STATE_HOME"
REGISTRY_NAME = "registry.json"
LOCK_NAME = "registry.lock"
CLOSED_FENCES_DIR = "closed-fences"
DEFAULT_TTL_SECONDS = 300
DEFAULT_WORKTREE_LIMIT = 4
DEFAULT_CLAIM_TTL_SECONDS = 30

Pool = Literal["agent", "worktree"]
MutationMode = Literal["read-write", "none"]
TokenState = Literal["current", "expired", "closed", "superseded"]
SettlementPhase = Literal["prepared", "committing", "ambiguous"]
ResourceRef = dict[str, str]

_TOP_KEYS = frozenset(
    {
        "schema",
        "broker_epoch",
        "recovery_capability_sha256",
        "next_fencing_sequence",
        "resource_fences",
        "leases",
        "session_admissions",
        "settlements",
        "closed_owner_admissions",
    }
)
_FENCE_KEYS = frozenset(
    {"resource_ref", "broker_epoch", "fencing_sequence", "lease_id", "close_receipt"}
)
_LEGACY_FENCE_KEYS = _FENCE_KEYS - {"close_receipt"}
_SETTLEMENT_KEYS = frozenset(
    {
        "settlement_id",
        "phase",
        "lease_id",
        "owner_id",
        "owner_pid",
        "owner_process_start",
        "session_id",
        "policy_sha256",
        "resource_ref",
        "token",
        "producer",
        "run_id",
        "expected_output_sha256",
        "protected_write_intent_sha256",
        "recovery_capability_sha256",
        "prepared_at",
        "updated_at",
    }
)
_SETTLEMENT_CLOSE_KEYS = frozenset(
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
)
_LEGACY_SETTLEMENT_CLOSE_KEYS = _SETTLEMENT_CLOSE_KEYS - {
    "settlement_id",
    "session_id",
    "policy_sha256",
    "protected_write_intent_sha256",
    "settlement_sha256",
}
_SETTLEMENT_RECOVERY_KEYS = frozenset(
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
)
_SESSION_ADMISSION_KEYS = frozenset(
    {
        "policy_sha256",
        "session_limit",
        "aggregate_limit",
        "mutation",
        "configured_monotonic_ns",
        "boot_id",
        "ttl_seconds",
    }
)
_LEASE_KEYS = frozenset(
    {
        "pool",
        "owner_id",
        "owner_pid",
        "owner_process_start",
        "session_id",
        "agent_id",
        "tool_use_id",
        "agent_type",
        "batch_id",
        "resource_ref",
        "policy_sha256",
        "session_limit",
        "aggregate_limit",
        "mutation",
        "boot_id",
        "acquired_at",
        "renewed_at",
        "renewed_monotonic_ns",
        "claimed_at",
        "child_terminal_at",
        "parent_completed_at",
        "ttl_seconds",
        "fencing_sequence",
    }
)
_AGENT_RESOURCE_KEYS = frozenset({"logical_unit_id", "worktree_root"})
_WORKTREE_RESOURCE_KEYS = frozenset({"repo_root", "outcome_id", "subplot_id"})
_NOFOLLOW = getattr(os, "O_NOFOLLOW", 0)
_DIRECTORY = getattr(os, "O_DIRECTORY", 0)
_MAX_ID = 256
_MAX_PATH = 4096
_MAX_SESSION_ADMISSIONS = 64
_MAX_CLOSED_FENCES = 128
_MAX_SETTLEMENTS = 128
_CLOSED_OWNER_ADMISSION_KEYS = frozenset({"closed_at", "boot_id", "close_generation"})
# Closed-owner records exist to fence spawn-versus-completion races during one run's teardown.
# On overflow the lowest-generation record is evicted, which REOPENS admission for the evicted
# owner until it is re-closed: the fence guarantee is scoped to record retention, not to
# unbounded history. Safety survives eviction because the teardown driver re-closes at pass
# start, snapshots AFTER that close (capturing any lease admitted in the evicted window), and
# refuses its receipt unless the pass-local generation is still the closed one. The bound is
# therefore a liveness ceiling: sustained churn past it costs retries, never a false receipt.
_MAX_CLOSED_OWNER_ADMISSIONS = 128
_BOOT_ID_LOCK = threading.Lock()


class LeaseBrokerError(RuntimeError):
    """Base class for typed broker refusals."""


class UnsafeAuthorityError(LeaseBrokerError):
    """The authority root, lock, or registry is unsafe to trust."""


class RegistryCorruptError(LeaseBrokerError):
    """The persisted registry is malformed or version-incompatible."""


class CapacityExhaustedError(LeaseBrokerError):
    """The requested reservation would exceed a live policy ceiling."""

    def __init__(self, message: str, *, earliest_expiry: str | None) -> None:
        super().__init__(message)
        self.earliest_expiry = earliest_expiry


class PolicyMismatchError(LeaseBrokerError):
    """A session attempted to mix admission snapshots while leases were live."""


class LeaseNotFoundError(LeaseBrokerError):
    """A required lease or reservation was not found."""


class LeaseOwnershipError(LeaseBrokerError):
    """The caller does not own the selected lease."""


class LeaseExpiredError(LeaseBrokerError):
    """The selected lease has expired and cannot be renewed or used."""


class LeaseClosedError(LeaseBrokerError):
    """The presented resource token has been released."""


class OwnerAdmissionClosedError(LeaseBrokerError):
    """Admission for this owner is monotonically closed; acquire/reserve/claim/retry refuse."""


class LeaseSupersededError(LeaseBrokerError):
    """The presented resource token is no longer the resource head."""


class MissingResourceError(LeaseBrokerError):
    """The fenced worktree or write target no longer exists."""


def _bounded(value: Any, name: str, *, maximum: int = _MAX_ID) -> str:
    if not isinstance(value, str) or not value or len(value) > maximum:
        raise RegistryCorruptError(f"{name} must be a non-empty string <= {maximum} characters")
    if any(ord(char) < 32 for char in value):
        raise RegistryCorruptError(f"{name} must not contain control characters")
    return cast(str, value)


def _optional_bounded(value: Any, name: str, *, maximum: int = _MAX_ID) -> str | None:
    if value is None:
        return None
    return _bounded(value, name, maximum=maximum)


def _positive(value: Any, name: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value < 1:
        raise RegistryCorruptError(f"{name} must be a positive integer")
    return cast(int, value)


def _nonnegative(value: Any, name: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        raise RegistryCorruptError(f"{name} must be a nonnegative integer")
    return cast(int, value)


def _sha256(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def _canonical_json(value: Mapping[str, Any]) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True)


def _utc_text(value: datetime) -> str:
    normalized = value.astimezone(UTC).replace(microsecond=value.microsecond)
    return normalized.isoformat().replace("+00:00", "Z")


def _parse_utc(value: Any, name: str) -> str:
    text = _bounded(value, name)
    try:
        parsed = datetime.fromisoformat(text.replace("Z", "+00:00"))
    except ValueError as exc:
        raise RegistryCorruptError(f"{name} must be an ISO-8601 timestamp") from exc
    if parsed.tzinfo is None:
        raise RegistryCorruptError(f"{name} must include a UTC offset")
    return text


def _optional_utc(value: Any, name: str) -> str | None:
    if value is None:
        return None
    return _parse_utc(value, name)


def _uuid_text(value: Any, name: str) -> str:
    text = _bounded(value, name)
    try:
        parsed = uuid.UUID(text)
    except ValueError as exc:
        raise RegistryCorruptError(f"{name} must be a UUID") from exc
    if str(parsed) != text:
        raise RegistryCorruptError(f"{name} must be a canonical lowercase UUID")
    return text


def _sha256_text(value: Any, name: str) -> str:
    text = _bounded(value, name, maximum=64)
    if len(text) != 64 or any(char not in "0123456789abcdef" for char in text):
        raise RegistryCorruptError(f"{name} must be a lowercase SHA-256 digest")
    return text


def _safe_absolute_path(value: Any, name: str) -> str:
    text = _bounded(value, name, maximum=_MAX_PATH)
    path = Path(text)
    if not path.is_absolute() or ".." in path.parts or str(path) != os.path.normpath(text):
        raise RegistryCorruptError(f"{name} must be a normalized absolute path")
    return text


def _closed_mapping(value: Any, keys: frozenset[str], name: str) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise RegistryCorruptError(f"{name} must be an object")
    unknown = sorted(set(value) - keys)
    missing = sorted(keys - set(value))
    if unknown or missing:
        details: list[str] = []
        if unknown:
            details.append(f"unknown field(s): {', '.join(unknown)}")
        if missing:
            details.append(f"missing field(s): {', '.join(missing)}")
        raise RegistryCorruptError(f"{name}: {'; '.join(details)}")
    return value


def canonical_resource_ref(pool: Pool, value: Mapping[str, Any]) -> ResourceRef:
    """Validate and normalize one closed pool-specific resource reference."""

    if not isinstance(value, Mapping):
        raise RegistryCorruptError("resource_ref must be an object")
    data = dict(value)
    if pool == "agent":
        unknown = sorted(set(data) - _AGENT_RESOURCE_KEYS)
        if unknown or "logical_unit_id" not in data:
            raise RegistryCorruptError(
                "agent resource_ref requires logical_unit_id and permits only worktree_root"
            )
        result = {"logical_unit_id": _bounded(data["logical_unit_id"], "logical_unit_id")}
        if "worktree_root" in data:
            result["worktree_root"] = _safe_absolute_path(data["worktree_root"], "worktree_root")
        return result
    _closed_mapping(data, _WORKTREE_RESOURCE_KEYS, "worktree resource_ref")
    return {
        "repo_root": _safe_absolute_path(data["repo_root"], "repo_root"),
        "outcome_id": _bounded(data["outcome_id"], "outcome_id"),
        "subplot_id": _bounded(data["subplot_id"], "subplot_id"),
    }


def resource_sha256(resource_ref: Mapping[str, Any]) -> str:
    """Digest a canonical resource object without disclosing its paths."""

    return _sha256(_canonical_json(resource_ref))


def _safe_configured_root(value: str, name: str) -> Path:
    try:
        normalized = _safe_absolute_path(value, name)
    except RegistryCorruptError as exc:
        raise UnsafeAuthorityError(str(exc)) from exc
    return Path(normalized)


def resolve_state_root(
    environment: Mapping[str, str] | None = None,
    *,
    home: Path | None = None,
) -> Path:
    """Resolve the runtime-neutral broker root without touching the filesystem."""

    env = os.environ if environment is None else environment
    if STATE_ENV in env:
        return _safe_configured_root(env[STATE_ENV], STATE_ENV)
    if XDG_STATE_ENV in env:
        return (
            _safe_configured_root(env[XDG_STATE_ENV], XDG_STATE_ENV) / "infiquetra" / "fleet-leases"
        )
    effective_home = Path.home() if home is None else home
    if not effective_home.is_absolute():
        raise UnsafeAuthorityError("home must be absolute when resolving fleet lease state")
    return effective_home / ".local" / "state" / "infiquetra" / "fleet-leases"


def root_identity_sha256(root: Path | str) -> str:
    path = Path(root)
    if not path.is_absolute():
        raise UnsafeAuthorityError("fleet lease state root must be absolute")
    return _sha256(os.path.normpath(str(path)))


def _darwin_utmpx_boot_id() -> str | None:
    """Read Darwin's current boot record without relying on sandboxed sysctl access."""

    class Timeval(ctypes.Structure):
        _fields_ = [("tv_sec", ctypes.c_long), ("tv_usec", ctypes.c_int)]

    class Utmpx(ctypes.Structure):
        _fields_ = [
            ("ut_user", ctypes.c_char * 256),
            ("ut_id", ctypes.c_char * 4),
            ("ut_line", ctypes.c_char * 32),
            ("ut_pid", ctypes.c_int),
            ("ut_type", ctypes.c_short),
            ("ut_tv", Timeval),
            ("ut_host", ctypes.c_char * 256),
            ("ut_pad", ctypes.c_uint32 * 16),
        ]

    try:
        libc = ctypes.CDLL(None)
        libc.getutxent.restype = ctypes.POINTER(Utmpx)
    except (AttributeError, OSError):
        return None
    current: tuple[int, int] | None = None
    with _BOOT_ID_LOCK:
        try:
            libc.setutxent()
            while entry := libc.getutxent():
                record = entry.contents
                if record.ut_type != 2:  # Darwin BOOT_TIME from <utmpx.h>.
                    continue
                candidate = (int(record.ut_tv.tv_sec), int(record.ut_tv.tv_usec))
                if candidate[0] > 0 and 0 <= candidate[1] < 1_000_000:
                    current = candidate if current is None else max(current, candidate)
        except (AttributeError, OSError, ValueError):
            return None
        finally:
            with contextlib.suppress(AttributeError):
                libc.endutxent()
    if current is None:
        return None
    return f"darwin-utmpx:{current[0]}:{current[1]}"


def _default_boot_id() -> str:
    linux = Path("/proc/sys/kernel/random/boot_id")
    try:
        value = linux.read_text(encoding="utf-8").strip()
        if value:
            return f"linux:{value}"
    except OSError:
        pass
    try:
        result = subprocess.run(
            ["sysctl", "-n", "kern.boottime"],
            check=True,
            capture_output=True,
            text=True,
            timeout=2,
        )
        value = result.stdout.strip()
        if value:
            return f"darwin:{_sha256(value)}"
    except (OSError, subprocess.SubprocessError):
        pass
    if sys.platform == "darwin":
        boot_id = _darwin_utmpx_boot_id()
        if boot_id is not None:
            return boot_id
    raise UnsafeAuthorityError(
        "operating system boot identity is unavailable; refusing lease authority"
    )


def _default_process_identity(pid: int) -> str | None:
    try:
        result = subprocess.run(
            ["ps", "-o", "lstart=", "-p", str(pid)],
            check=False,
            capture_output=True,
            text=True,
            timeout=2,
        )
    except (OSError, subprocess.SubprocessError):
        result = None
    value = "" if result is None else result.stdout.strip()
    if value:
        return value
    return _darwin_process_identity(pid) if sys.platform == "darwin" else None


def _darwin_process_identity(pid: int) -> str | None:
    """Read a PID's kernel start time without shelling out to sandbox-blocked ``ps``."""

    class ProcBsdInfo(ctypes.Structure):
        _fields_ = [
            ("flags", ctypes.c_uint32),
            ("status", ctypes.c_uint32),
            ("xstatus", ctypes.c_uint32),
            ("pid", ctypes.c_uint32),
            ("ppid", ctypes.c_uint32),
            ("uid", ctypes.c_uint32),
            ("gid", ctypes.c_uint32),
            ("ruid", ctypes.c_uint32),
            ("rgid", ctypes.c_uint32),
            ("svuid", ctypes.c_uint32),
            ("svgid", ctypes.c_uint32),
            ("comm", ctypes.c_char * 16),
            ("name", ctypes.c_char * 32),
            ("nfiles", ctypes.c_uint32),
            ("pgid", ctypes.c_uint32),
            ("pjobc", ctypes.c_uint32),
            ("e_tdev", ctypes.c_uint32),
            ("e_tpgid", ctypes.c_uint32),
            ("nice", ctypes.c_int32),
            ("start_tvsec", ctypes.c_uint64),
            ("start_tvusec", ctypes.c_uint64),
        ]

    try:
        library = ctypes.CDLL("/usr/lib/libproc.dylib", use_errno=True)
        function = library.proc_pidinfo
        function.argtypes = [
            ctypes.c_int,
            ctypes.c_int,
            ctypes.c_uint64,
            ctypes.c_void_p,
            ctypes.c_int,
        ]
        function.restype = ctypes.c_int
        info = ProcBsdInfo()
        written = function(pid, 3, 0, ctypes.byref(info), ctypes.sizeof(info))
    except (AttributeError, OSError, TypeError, ValueError):
        return None
    if written != ctypes.sizeof(info) or info.start_tvsec < 1:
        return None
    return f"darwin-start:{info.start_tvsec}:{info.start_tvusec}"


@dataclass(frozen=True)
class Providers:
    """Injectable sources for deterministic time, identity, and liveness tests."""

    wall_now: Callable[[], datetime] = lambda: datetime.now(UTC)
    monotonic_ns: Callable[[], int] = time.monotonic_ns
    boot_id: Callable[[], str] = _default_boot_id
    uuid4: Callable[[], uuid.UUID] = uuid.uuid4
    process_identity: Callable[[int], str | None] = _default_process_identity
    process_exists: Callable[[int], bool] = lambda pid: _process_exists(pid)


def _process_exists(pid: int) -> bool:
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    except PermissionError:
        return True
    return True


@dataclass(frozen=True)
class FencingToken:
    broker_epoch: str
    fencing_sequence: int

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> FencingToken:
        return cls(
            broker_epoch=_uuid_text(data.get("broker_epoch"), "token.broker_epoch"),
            fencing_sequence=_positive(data.get("fencing_sequence"), "token.fencing_sequence"),
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "broker_epoch": self.broker_epoch,
            "fencing_sequence": self.fencing_sequence,
        }


def token_generation(token: FencingToken) -> str:
    """Return the canonical generation name shared by broker and forensic records."""

    return f"{token.broker_epoch}:{token.fencing_sequence}"


def _record_sha256(value: Mapping[str, Any], *excluded: str) -> str:
    payload = {key: item for key, item in value.items() if key not in excluded}
    return hashlib.sha256(_canonical_json(payload).encode("ascii")).hexdigest()


def validate_settlement_close(value: Mapping[str, Any]) -> dict[str, Any]:
    """Validate the exact broker-owned ``settlement_close.v1`` record."""

    parsed = _closed_mapping(dict(value), _SETTLEMENT_CLOSE_KEYS, "settlement close")
    if parsed["schema"] != "settlement_close.v1":
        raise RegistryCorruptError("settlement close schema must be settlement_close.v1")
    resource = canonical_resource_ref("agent", parsed["resource_ref"])
    token_raw = parsed["token"]
    if not isinstance(token_raw, Mapping) or set(token_raw) != {
        "broker_epoch",
        "fencing_sequence",
    }:
        raise RegistryCorruptError("settlement close token must use the closed token shape")
    token = FencingToken.from_dict(token_raw)
    lease_id = _uuid_text(parsed["lease_id"], "settlement close lease_id")
    settlement_id = _uuid_text(parsed["settlement_id"], "settlement close settlement_id")
    session_id = _bounded(parsed["session_id"], "settlement close session_id", maximum=128)
    policy_sha256 = _sha256_text(parsed["policy_sha256"], "settlement close policy_sha256")
    generation = _bounded(parsed["generation"], "settlement close generation")
    if generation != token_generation(token):
        raise RegistryCorruptError("settlement close generation does not match its token")
    if parsed["phase"] != "closed" or parsed["terminal"] is not True:
        raise RegistryCorruptError("settlement close must be terminal and closed")
    producer = parsed["producer"]
    if producer not in {"agy", "saga", "team-execution"}:
        raise RegistryCorruptError("settlement close producer is invalid")
    run_id = _bounded(parsed["run_id"], "settlement close run_id", maximum=128)
    refs = parsed["evidence_refs"]
    if (
        not isinstance(refs, list)
        or len(refs) > 256
        or refs != sorted(refs)
        or len(refs) != len(set(refs))
    ):
        raise RegistryCorruptError("settlement close evidence_refs must be sorted and unique")
    for ref in refs:
        _bounded(ref, "settlement close evidence_ref")
    expected_output = _sha256_text(
        parsed["expected_output_sha256"], "settlement close expected_output_sha256"
    )
    protected_write_intent = _sha256_text(
        parsed["protected_write_intent_sha256"],
        "settlement close protected_write_intent_sha256",
    )
    settlement_sha256 = _sha256_text(
        parsed["settlement_sha256"], "settlement close settlement_sha256"
    )
    receipt_sha256 = _sha256_text(parsed["receipt_sha256"], "settlement close receipt_sha256")
    record_sha256 = _sha256_text(parsed["sha256"], "settlement close sha256")
    normalized = {
        "schema": "settlement_close.v1",
        "resource_ref": resource,
        "token": token.to_dict(),
        "lease_id": lease_id,
        "settlement_id": settlement_id,
        "session_id": session_id,
        "policy_sha256": policy_sha256,
        "generation": generation,
        "phase": "closed",
        "producer": producer,
        "run_id": run_id,
        "terminal": True,
        "evidence_refs": refs,
        "expected_output_sha256": expected_output,
        "protected_write_intent_sha256": protected_write_intent,
        "settlement_sha256": settlement_sha256,
        "receipt_sha256": receipt_sha256,
        "sha256": record_sha256,
    }
    if receipt_sha256 != _record_sha256(normalized, "receipt_sha256", "sha256"):
        raise RegistryCorruptError("settlement close receipt_sha256 does not match its content")
    if record_sha256 != _record_sha256(normalized, "sha256"):
        raise RegistryCorruptError("settlement close sha256 does not match its content")
    return normalized


def _validate_legacy_settlement_close(value: Mapping[str, Any]) -> dict[str, Any]:
    """Read an exact pre-binding close receipt without promoting it to current proof.

    These records remain useful for classifying an already-closed resource head. They deliberately
    retain their old shape so recovery and manifest gates, which call ``validate_settlement_close``
    and require the new binding fields, cannot mistake them for current settlement authority.
    """

    parsed = _closed_mapping(dict(value), _LEGACY_SETTLEMENT_CLOSE_KEYS, "legacy settlement close")
    if parsed["schema"] != "settlement_close.v1":
        raise RegistryCorruptError("legacy settlement close schema must be settlement_close.v1")
    resource = canonical_resource_ref("agent", parsed["resource_ref"])
    token_raw = parsed["token"]
    if not isinstance(token_raw, Mapping) or set(token_raw) != {
        "broker_epoch",
        "fencing_sequence",
    }:
        raise RegistryCorruptError("legacy settlement close token must use the closed token shape")
    token = FencingToken.from_dict(token_raw)
    lease_id = _uuid_text(parsed["lease_id"], "legacy settlement close lease_id")
    generation = _bounded(parsed["generation"], "legacy settlement close generation")
    if generation != token_generation(token):
        raise RegistryCorruptError("legacy settlement close generation does not match its token")
    if parsed["phase"] != "closed" or parsed["terminal"] is not True:
        raise RegistryCorruptError("legacy settlement close must be terminal and closed")
    producer = parsed["producer"]
    if producer not in {"agy", "saga", "team-execution"}:
        raise RegistryCorruptError("legacy settlement close producer is invalid")
    run_id = _bounded(parsed["run_id"], "legacy settlement close run_id", maximum=128)
    refs = parsed["evidence_refs"]
    if (
        not isinstance(refs, list)
        or len(refs) > 256
        or refs != sorted(refs)
        or len(refs) != len(set(refs))
    ):
        raise RegistryCorruptError(
            "legacy settlement close evidence_refs must be sorted and unique"
        )
    for ref in refs:
        _bounded(ref, "legacy settlement close evidence_ref")
    expected_output = _sha256_text(
        parsed["expected_output_sha256"],
        "legacy settlement close expected_output_sha256",
    )
    receipt_sha256 = _sha256_text(
        parsed["receipt_sha256"], "legacy settlement close receipt_sha256"
    )
    record_sha256 = _sha256_text(parsed["sha256"], "legacy settlement close sha256")
    normalized = {
        "schema": "settlement_close.v1",
        "resource_ref": resource,
        "token": token.to_dict(),
        "lease_id": lease_id,
        "generation": generation,
        "phase": "closed",
        "producer": producer,
        "run_id": run_id,
        "terminal": True,
        "evidence_refs": refs,
        "expected_output_sha256": expected_output,
        "receipt_sha256": receipt_sha256,
        "sha256": record_sha256,
    }
    if receipt_sha256 != _record_sha256(normalized, "receipt_sha256", "sha256"):
        raise RegistryCorruptError(
            "legacy settlement close receipt_sha256 does not match its content"
        )
    if record_sha256 != _record_sha256(normalized, "sha256"):
        raise RegistryCorruptError("legacy settlement close sha256 does not match its content")
    return normalized


def build_settlement_close(
    *,
    resource_ref: Mapping[str, Any],
    token: FencingToken,
    lease_id: str,
    producer: str,
    run_id: str,
    evidence_refs: Sequence[str],
    expected_output_sha256: str,
    settlement_id: str,
    session_id: str,
    policy_sha256: str,
    protected_write_intent_sha256: str,
    settlement_sha256: str,
) -> dict[str, Any]:
    """Build the canonical close record; callers cannot supply either digest."""

    payload: dict[str, Any] = {
        "schema": "settlement_close.v1",
        "resource_ref": canonical_resource_ref("agent", resource_ref),
        "token": token.to_dict(),
        "lease_id": _uuid_text(lease_id, "settlement close lease_id"),
        "settlement_id": _uuid_text(settlement_id, "settlement close settlement_id"),
        "session_id": _bounded(session_id, "settlement close session_id", maximum=128),
        "policy_sha256": _sha256_text(policy_sha256, "settlement close policy_sha256"),
        "generation": token_generation(token),
        "phase": "closed",
        "producer": producer,
        "run_id": _bounded(run_id, "settlement close run_id", maximum=128),
        "terminal": True,
        "evidence_refs": sorted(
            {_bounded(item, "settlement close evidence_ref") for item in evidence_refs}
        ),
        "expected_output_sha256": _sha256_text(
            expected_output_sha256, "settlement close expected_output_sha256"
        ),
        "protected_write_intent_sha256": _sha256_text(
            protected_write_intent_sha256,
            "settlement close protected_write_intent_sha256",
        ),
        "settlement_sha256": _sha256_text(settlement_sha256, "settlement close settlement_sha256"),
    }
    payload["receipt_sha256"] = _record_sha256(payload)
    payload["sha256"] = _record_sha256(payload)
    return validate_settlement_close(payload)


@dataclass(frozen=True)
class Lease:
    lease_id: str
    pool: Pool
    owner_id: str
    owner_pid: int | None
    owner_process_start: str | None
    session_id: str
    agent_id: str | None
    tool_use_id: str | None
    agent_type: str | None
    batch_id: str | None
    resource_ref: ResourceRef | None
    policy_sha256: str | None
    session_limit: int | None
    aggregate_limit: int | None
    mutation: MutationMode | None
    boot_id: str
    acquired_at: str
    renewed_at: str
    renewed_monotonic_ns: int
    claimed_at: str | None
    child_terminal_at: str | None
    parent_completed_at: str | None
    ttl_seconds: int
    broker_epoch: str
    fencing_sequence: int

    @property
    def token(self) -> FencingToken:
        return FencingToken(self.broker_epoch, self.fencing_sequence)

    @classmethod
    def from_dict(cls, lease_id: str, data: Mapping[str, Any], broker_epoch: str) -> Lease:
        parsed = _closed_mapping(dict(data), _LEASE_KEYS, f"leases.{lease_id}")
        pool = parsed["pool"]
        if pool not in ("agent", "worktree"):
            raise RegistryCorruptError(f"leases.{lease_id}.pool must be agent or worktree")
        resource_raw = parsed["resource_ref"]
        resource = None if resource_raw is None else canonical_resource_ref(pool, resource_raw)
        owner_pid_raw = parsed["owner_pid"]
        owner_pid = None if owner_pid_raw is None else _positive(owner_pid_raw, "owner_pid")
        policy_raw = parsed["policy_sha256"]
        session_limit_raw = parsed["session_limit"]
        aggregate_limit_raw = parsed["aggregate_limit"]
        mutation_raw = parsed["mutation"]
        if pool == "agent":
            policy = _sha256_text(policy_raw, "policy_sha256")
            session_limit = _positive(session_limit_raw, "session_limit")
            aggregate_limit = _positive(aggregate_limit_raw, "aggregate_limit")
            if session_limit > aggregate_limit:
                raise RegistryCorruptError("session_limit must not exceed aggregate_limit")
            if mutation_raw not in ("read-write", "none"):
                raise RegistryCorruptError("agent mutation must be read-write or none")
            mutation = cast(MutationMode, mutation_raw)
        else:
            if any(
                item is not None
                for item in (policy_raw, session_limit_raw, aggregate_limit_raw, mutation_raw)
            ):
                raise RegistryCorruptError("worktree admission fields must be null")
            if resource is None:
                raise RegistryCorruptError("worktree resource_ref must not be null")
            policy = None
            session_limit = None
            aggregate_limit = None
            mutation = None
        agent_id = _optional_bounded(parsed["agent_id"], "agent_id")
        claimed_at = _optional_utc(parsed["claimed_at"], "claimed_at")
        if agent_id is None and claimed_at is not None:
            raise RegistryCorruptError("claimed_at requires agent_id")
        if agent_id is not None and (claimed_at is None or resource is None):
            raise RegistryCorruptError("claimed agent leases require claimed_at and resource_ref")
        return cls(
            lease_id=_bounded(lease_id, "lease_id"),
            pool=cast(Pool, pool),
            owner_id=_bounded(parsed["owner_id"], "owner_id"),
            owner_pid=owner_pid,
            owner_process_start=_optional_bounded(
                parsed["owner_process_start"], "owner_process_start"
            ),
            session_id=_bounded(parsed["session_id"], "session_id"),
            agent_id=agent_id,
            tool_use_id=_optional_bounded(parsed["tool_use_id"], "tool_use_id"),
            agent_type=_optional_bounded(parsed["agent_type"], "agent_type"),
            batch_id=_optional_bounded(parsed["batch_id"], "batch_id"),
            resource_ref=resource,
            policy_sha256=policy,
            session_limit=session_limit,
            aggregate_limit=aggregate_limit,
            mutation=mutation,
            boot_id=_bounded(parsed["boot_id"], "boot_id"),
            acquired_at=_parse_utc(parsed["acquired_at"], "acquired_at"),
            renewed_at=_parse_utc(parsed["renewed_at"], "renewed_at"),
            renewed_monotonic_ns=_nonnegative(
                parsed["renewed_monotonic_ns"], "renewed_monotonic_ns"
            ),
            claimed_at=claimed_at,
            child_terminal_at=_optional_utc(parsed["child_terminal_at"], "child_terminal_at"),
            parent_completed_at=_optional_utc(parsed["parent_completed_at"], "parent_completed_at"),
            ttl_seconds=_positive(parsed["ttl_seconds"], "ttl_seconds"),
            broker_epoch=broker_epoch,
            fencing_sequence=_positive(parsed["fencing_sequence"], "fencing_sequence"),
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "pool": self.pool,
            "owner_id": self.owner_id,
            "owner_pid": self.owner_pid,
            "owner_process_start": self.owner_process_start,
            "session_id": self.session_id,
            "agent_id": self.agent_id,
            "tool_use_id": self.tool_use_id,
            "agent_type": self.agent_type,
            "batch_id": self.batch_id,
            "resource_ref": self.resource_ref,
            "policy_sha256": self.policy_sha256,
            "session_limit": self.session_limit,
            "aggregate_limit": self.aggregate_limit,
            "mutation": self.mutation,
            "boot_id": self.boot_id,
            "acquired_at": self.acquired_at,
            "renewed_at": self.renewed_at,
            "renewed_monotonic_ns": self.renewed_monotonic_ns,
            "claimed_at": self.claimed_at,
            "child_terminal_at": self.child_terminal_at,
            "parent_completed_at": self.parent_completed_at,
            "ttl_seconds": self.ttl_seconds,
            "fencing_sequence": self.fencing_sequence,
        }


@dataclass(frozen=True)
class SettlementRecord:
    settlement_id: str
    phase: SettlementPhase
    lease_id: str
    owner_id: str
    owner_pid: int | None
    owner_process_start: str | None
    session_id: str
    policy_sha256: str
    resource_ref: ResourceRef
    token: FencingToken
    producer: str
    run_id: str
    expected_output_sha256: str
    protected_write_intent_sha256: str
    recovery_capability_sha256: str | None
    prepared_at: str
    updated_at: str

    @classmethod
    def from_dict(cls, digest: str, data: Mapping[str, Any]) -> SettlementRecord:
        _sha256_text(digest, "settlements key")
        raw = dict(data)
        if set(raw) == _SETTLEMENT_KEYS - {"recovery_capability_sha256"}:
            raw["recovery_capability_sha256"] = None
        parsed = _closed_mapping(raw, _SETTLEMENT_KEYS, f"settlements.{digest}")
        resource = canonical_resource_ref("agent", parsed["resource_ref"])
        if resource_sha256(resource) != digest:
            raise RegistryCorruptError("settlement digest does not match resource_ref")
        token_raw = parsed["token"]
        if not isinstance(token_raw, Mapping) or set(token_raw) != {
            "broker_epoch",
            "fencing_sequence",
        }:
            raise RegistryCorruptError("settlement token must use the closed token shape")
        token = FencingToken.from_dict(token_raw)
        phase = parsed["phase"]
        if phase not in {"prepared", "committing", "ambiguous"}:
            raise RegistryCorruptError("settlement phase is invalid")
        owner_pid_raw = parsed["owner_pid"]
        owner_pid = None if owner_pid_raw is None else _positive(owner_pid_raw, "owner_pid")
        producer = parsed["producer"]
        if producer not in {"agy", "saga", "team-execution"}:
            raise RegistryCorruptError("settlement producer is invalid")
        return cls(
            settlement_id=_uuid_text(parsed["settlement_id"], "settlement_id"),
            phase=cast(SettlementPhase, phase),
            lease_id=_uuid_text(parsed["lease_id"], "settlement lease_id"),
            owner_id=_bounded(parsed["owner_id"], "settlement owner_id", maximum=128),
            owner_pid=owner_pid,
            owner_process_start=_optional_bounded(
                parsed["owner_process_start"], "settlement owner_process_start"
            ),
            session_id=_bounded(parsed["session_id"], "settlement session_id", maximum=128),
            policy_sha256=_sha256_text(parsed["policy_sha256"], "settlement policy_sha256"),
            resource_ref=resource,
            token=token,
            producer=cast(str, producer),
            run_id=_bounded(parsed["run_id"], "settlement run_id", maximum=128),
            expected_output_sha256=_sha256_text(
                parsed["expected_output_sha256"], "settlement expected_output_sha256"
            ),
            protected_write_intent_sha256=_sha256_text(
                parsed["protected_write_intent_sha256"],
                "settlement protected_write_intent_sha256",
            ),
            recovery_capability_sha256=(
                None
                if parsed["recovery_capability_sha256"] is None
                else _sha256_text(
                    parsed["recovery_capability_sha256"],
                    "settlement recovery_capability_sha256",
                )
            ),
            prepared_at=_parse_utc(parsed["prepared_at"], "settlement prepared_at"),
            updated_at=_parse_utc(parsed["updated_at"], "settlement updated_at"),
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "settlement_id": self.settlement_id,
            "phase": self.phase,
            "lease_id": self.lease_id,
            "owner_id": self.owner_id,
            "owner_pid": self.owner_pid,
            "owner_process_start": self.owner_process_start,
            "session_id": self.session_id,
            "policy_sha256": self.policy_sha256,
            "resource_ref": self.resource_ref,
            "token": self.token.to_dict(),
            "producer": self.producer,
            "run_id": self.run_id,
            "expected_output_sha256": self.expected_output_sha256,
            "protected_write_intent_sha256": self.protected_write_intent_sha256,
            "recovery_capability_sha256": self.recovery_capability_sha256,
            "prepared_at": self.prepared_at,
            "updated_at": self.updated_at,
        }

    @property
    def settlement_sha256(self) -> str:
        """Bind the complete original prepared settlement, excluding later phase transitions."""

        original = self.to_dict()
        original["phase"] = "prepared"
        original["updated_at"] = self.prepared_at
        return _record_sha256(original)


@dataclass(frozen=True)
class ResourceFence:
    resource_ref: ResourceRef
    broker_epoch: str
    fencing_sequence: int
    lease_id: str
    close_receipt: dict[str, Any] | None = None

    @classmethod
    def from_dict(cls, digest: str, data: Mapping[str, Any]) -> ResourceFence:
        _sha256_text(digest, "resource_fences key")
        raw = dict(data)
        if set(raw) == _LEGACY_FENCE_KEYS:
            raw["close_receipt"] = None
        parsed = _closed_mapping(raw, _FENCE_KEYS, f"resource_fences.{digest}")
        resource_raw = parsed["resource_ref"]
        if not isinstance(resource_raw, dict):
            raise RegistryCorruptError("resource fence resource_ref must be an object")
        # Shape identifies its pool; both are closed and cannot overlap.
        pool: Pool = "worktree" if set(resource_raw) == _WORKTREE_RESOURCE_KEYS else "agent"
        resource = canonical_resource_ref(pool, resource_raw)
        if resource_sha256(resource) != digest:
            raise RegistryCorruptError("resource fence digest does not match resource_ref")
        close_raw = parsed["close_receipt"]
        close = None
        if close_raw is not None:
            if not isinstance(close_raw, Mapping):
                raise RegistryCorruptError("resource fence close_receipt must be an object or null")
            close = (
                _validate_legacy_settlement_close(close_raw)
                if set(close_raw) == _LEGACY_SETTLEMENT_CLOSE_KEYS
                else validate_settlement_close(close_raw)
            )
            if (
                close["resource_ref"] != resource
                or close["token"]["broker_epoch"] != parsed["broker_epoch"]
                or close["token"]["fencing_sequence"] != parsed["fencing_sequence"]
                or close["lease_id"] != parsed["lease_id"]
            ):
                raise RegistryCorruptError("resource fence close_receipt binding does not match")
        return cls(
            resource_ref=resource,
            broker_epoch=_uuid_text(parsed["broker_epoch"], "fence.broker_epoch"),
            fencing_sequence=_positive(parsed["fencing_sequence"], "fence.fencing_sequence"),
            lease_id=_bounded(parsed["lease_id"], "fence.lease_id"),
            close_receipt=close,
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "resource_ref": self.resource_ref,
            "broker_epoch": self.broker_epoch,
            "fencing_sequence": self.fencing_sequence,
            "lease_id": self.lease_id,
            "close_receipt": self.close_receipt,
        }


@dataclass(frozen=True)
class SessionAdmission:
    """The resolved admission policy pinned to a coordinator session."""

    policy_sha256: str
    session_limit: int
    aggregate_limit: int
    mutation: MutationMode
    configured_monotonic_ns: int
    boot_id: str
    ttl_seconds: int

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> SessionAdmission:
        raw = dict(data)
        legacy_keys = {
            "policy_sha256",
            "session_limit",
            "aggregate_limit",
            "mutation",
        }
        if set(raw) == legacy_keys:
            # Pre-TTL v1 pins remain valid while a lease is live and otherwise expire immediately.
            raw.update(
                configured_monotonic_ns=0,
                boot_id="legacy-session-admission",
                ttl_seconds=1,
            )
        parsed = _closed_mapping(raw, _SESSION_ADMISSION_KEYS, "session_admission")
        session_limit = _positive(parsed["session_limit"], "session_limit")
        aggregate_limit = _positive(parsed["aggregate_limit"], "aggregate_limit")
        if session_limit > aggregate_limit:
            raise RegistryCorruptError("session_limit must not exceed aggregate_limit")
        mutation = parsed["mutation"]
        if mutation not in ("read-write", "none"):
            raise RegistryCorruptError("session admission mutation must be read-write or none")
        return cls(
            policy_sha256=_sha256_text(parsed["policy_sha256"], "policy_sha256"),
            session_limit=session_limit,
            aggregate_limit=aggregate_limit,
            mutation=cast(MutationMode, mutation),
            configured_monotonic_ns=_nonnegative(
                parsed["configured_monotonic_ns"], "configured_monotonic_ns"
            ),
            boot_id=_bounded(parsed["boot_id"], "session admission boot_id"),
            ttl_seconds=_positive(parsed["ttl_seconds"], "session admission ttl_seconds"),
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "policy_sha256": self.policy_sha256,
            "session_limit": self.session_limit,
            "aggregate_limit": self.aggregate_limit,
            "mutation": self.mutation,
            "configured_monotonic_ns": self.configured_monotonic_ns,
            "boot_id": self.boot_id,
            "ttl_seconds": self.ttl_seconds,
        }

    @property
    def contract(self) -> tuple[str, int, int, MutationMode]:
        return (
            self.policy_sha256,
            self.session_limit,
            self.aggregate_limit,
            self.mutation,
        )


@dataclass(frozen=True)
class OwnerAdmissionClose:
    """One monotonic owner-admission close.

    There is no reopen *operation*; the closed map is bounded, so on overflow the
    lowest-generation record is evicted and admission for that owner lapses back open.
    A driver that needs the fence across eviction re-closes at pass start (minting a
    fresh, higher generation) and re-verifies the generation before its receipt.
    """

    closed_at: str
    boot_id: str
    close_generation: int

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> OwnerAdmissionClose:
        parsed = _closed_mapping(dict(data), _CLOSED_OWNER_ADMISSION_KEYS, "closed_owner_admission")
        return cls(
            closed_at=_parse_utc(parsed["closed_at"], "closed_owner_admission closed_at"),
            boot_id=_bounded(parsed["boot_id"], "closed_owner_admission boot_id"),
            close_generation=_positive(
                parsed["close_generation"], "closed_owner_admission close_generation"
            ),
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "closed_at": self.closed_at,
            "boot_id": self.boot_id,
            "close_generation": self.close_generation,
        }


@dataclass
class Registry:
    broker_epoch: str
    recovery_capability_sha256: str | None
    next_fencing_sequence: int
    resource_fences: dict[str, ResourceFence]
    leases: dict[str, Lease]
    session_admissions: dict[str, SessionAdmission]
    settlements: dict[str, SettlementRecord]
    closed_owner_admissions: dict[str, OwnerAdmissionClose]

    @classmethod
    def fresh(cls, providers: Providers) -> Registry:
        return cls(str(providers.uuid4()), None, 1, {}, {}, {}, {}, {})

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> Registry:
        raw = dict(data)
        if "closed_owner_admissions" not in raw and set(raw).issubset(
            _TOP_KEYS - {"closed_owner_admissions"}
        ):
            # Pre-#358 authorities have no owner-admission fence records; the only safe
            # migration is the empty map (no owner was ever closed under the old shape).
            raw["closed_owner_admissions"] = {}
        if "recovery_capability_sha256" not in raw and set(raw).issubset(
            _TOP_KEYS - {"recovery_capability_sha256"}
        ):
            raw["recovery_capability_sha256"] = None
        legacy_keys = _TOP_KEYS - {"session_admissions", "settlements"}
        if set(raw) == legacy_keys and raw.get("schema") == SCHEMA:
            # ``session_admissions`` was added to the v1 registry as bounded coordination metadata.
            # Older v1 authorities have no such pins, so the only safe migration is the exact old
            # closed shape to an empty map.  Unknown or any other missing fields still fail closed.
            raw["session_admissions"] = {}
            raw["settlements"] = {}
        elif set(raw) == _TOP_KEYS - {"settlements"} and raw.get("schema") == SCHEMA:
            raw["settlements"] = {}
        elif set(raw) == _TOP_KEYS - {"session_admissions"} and raw.get("schema") == SCHEMA:
            raw["session_admissions"] = {}
        parsed = _closed_mapping(raw, _TOP_KEYS, "registry")
        if parsed["schema"] != SCHEMA:
            raise RegistryCorruptError(
                f"registry.schema must be {SCHEMA!r}; found {parsed['schema']!r}"
            )
        epoch = _uuid_text(parsed["broker_epoch"], "broker_epoch")
        recovery_capability = (
            None
            if parsed["recovery_capability_sha256"] is None
            else _sha256_text(parsed["recovery_capability_sha256"], "recovery_capability_sha256")
        )
        next_sequence = _positive(parsed["next_fencing_sequence"], "next_fencing_sequence")
        fences_raw = parsed["resource_fences"]
        leases_raw = parsed["leases"]
        admissions_raw = parsed["session_admissions"]
        settlements_raw = parsed["settlements"]
        closed_owners_raw = parsed["closed_owner_admissions"]
        if not isinstance(fences_raw, dict) or not isinstance(leases_raw, dict):
            raise RegistryCorruptError("resource_fences and leases must be objects")
        if not isinstance(admissions_raw, dict):
            raise RegistryCorruptError("session_admissions must be an object")
        if not isinstance(settlements_raw, dict):
            raise RegistryCorruptError("settlements must be an object")
        if not isinstance(closed_owners_raw, dict):
            raise RegistryCorruptError("closed_owner_admissions must be an object")
        if len(admissions_raw) > _MAX_SESSION_ADMISSIONS:
            raise RegistryCorruptError("session_admissions exceeds its bounded capacity")
        if len(settlements_raw) > _MAX_SETTLEMENTS:
            raise RegistryCorruptError("settlements exceeds its bounded capacity")
        if len(closed_owners_raw) > _MAX_CLOSED_OWNER_ADMISSIONS:
            raise RegistryCorruptError("closed_owner_admissions exceeds its bounded capacity")
        fences = {
            digest: ResourceFence.from_dict(digest, fence) for digest, fence in fences_raw.items()
        }
        leases = {
            lease_id: Lease.from_dict(lease_id, lease, epoch)
            for lease_id, lease in leases_raw.items()
        }
        admissions = {
            _bounded(session_id, "session_admissions key"): SessionAdmission.from_dict(admission)
            for session_id, admission in admissions_raw.items()
        }
        settlements = {
            digest: SettlementRecord.from_dict(digest, settlement)
            for digest, settlement in settlements_raw.items()
        }
        closed_owners = {
            _bounded(owner_id, "closed_owner_admissions key"): OwnerAdmissionClose.from_dict(close)
            for owner_id, close in closed_owners_raw.items()
        }
        sequences = [lease.fencing_sequence for lease in leases.values()]
        sequences.extend(fence.fencing_sequence for fence in fences.values())
        sequences.extend(close.close_generation for close in closed_owners.values())
        if any(fence.broker_epoch != epoch for fence in fences.values()):
            raise RegistryCorruptError("resource fence broker_epoch must match registry epoch")
        if sequences and next_sequence <= max(sequences):
            raise RegistryCorruptError("next_fencing_sequence must exceed every issued sequence")
        for digest, settlement in settlements.items():
            fence = fences.get(digest)
            lease = leases.get(settlement.lease_id)
            if (
                fence is None
                or lease is None
                or fence.close_receipt is not None
                or fence.lease_id != settlement.lease_id
                or lease.resource_ref != settlement.resource_ref
                or lease.token != settlement.token
                or fence.broker_epoch != settlement.token.broker_epoch
                or fence.fencing_sequence != settlement.token.fencing_sequence
            ):
                raise RegistryCorruptError(
                    "settlement does not bind the current live resource head"
                )
        return cls(
            epoch,
            recovery_capability,
            next_sequence,
            fences,
            leases,
            admissions,
            settlements,
            closed_owners,
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema": SCHEMA,
            "broker_epoch": self.broker_epoch,
            "recovery_capability_sha256": self.recovery_capability_sha256,
            "next_fencing_sequence": self.next_fencing_sequence,
            "resource_fences": {
                key: value.to_dict() for key, value in sorted(self.resource_fences.items())
            },
            "leases": {key: value.to_dict() for key, value in sorted(self.leases.items())},
            "session_admissions": {
                key: value.to_dict() for key, value in sorted(self.session_admissions.items())
            },
            "settlements": {
                key: value.to_dict() for key, value in sorted(self.settlements.items())
            },
            "closed_owner_admissions": {
                key: value.to_dict() for key, value in sorted(self.closed_owner_admissions.items())
            },
        }

    def issue_sequence(self) -> int:
        sequence = self.next_fencing_sequence
        self.next_fencing_sequence += 1
        return sequence


@dataclass(frozen=True)
class SweepResult:
    released_agent_leases: tuple[str, ...]
    reaped_worktree_leases: tuple[str, ...]
    retained: Mapping[str, str]

    def to_dict(self) -> dict[str, Any]:
        return {
            "released_agent_leases": list(self.released_agent_leases),
            "reaped_worktree_leases": list(self.reaped_worktree_leases),
            "retained": dict(self.retained),
        }


@dataclass(frozen=True)
class SettlementRecoveryHandler:
    """One exact retained settlement and its root-adapter replay operation."""

    settlement: SettlementRecord
    write: Callable[[Lease, SettlementRecord], SettlementReplayResult]


@dataclass(frozen=True)
class SettlementReplayResult:
    """Evidence that a replay honored the retained write and output contract."""

    evidence_refs: Sequence[str]
    protected_write_intent_sha256: str
    output_sha256: str


class LeaseBroker:
    """One file-backed broker handle. Construction and inspection are side-effect free."""

    def __init__(
        self,
        root: Path | str | None = None,
        *,
        providers: Providers | None = None,
        worktree_limit: int = DEFAULT_WORKTREE_LIMIT,
        environment: Mapping[str, str] | None = None,
        home: Path | None = None,
    ) -> None:
        resolved = resolve_state_root(environment, home=home) if root is None else Path(root)
        if not resolved.is_absolute() or ".." in resolved.parts:
            raise UnsafeAuthorityError("fleet lease state root must be a normalized absolute path")
        self.root = Path(os.path.normpath(str(resolved)))
        self.registry_path = self.root / REGISTRY_NAME
        self.lock_path = self.root / LOCK_NAME
        self.closed_fences_dir = self.root / CLOSED_FENCES_DIR
        self.providers = Providers() if providers is None else providers
        self._authority_fd: int | None = None
        self._authority_fd_pid: int | None = None
        self._authority_fd_lock = threading.Lock()
        if isinstance(worktree_limit, bool) or worktree_limit < 1:
            raise ValueError("worktree_limit must be a positive integer")
        self.worktree_limit = worktree_limit

    @property
    def root_sha256(self) -> str:
        return root_identity_sha256(self.root)

    def _validate_node(self, path: Path, *, mode: int, kind: str) -> os.stat_result:
        try:
            result = path.lstat()
        except FileNotFoundError:
            raise
        if stat.S_ISLNK(result.st_mode):
            raise UnsafeAuthorityError(f"fleet lease {kind} must not be a symlink: {path}")
        expected_type = stat.S_ISDIR if kind == "root" else stat.S_ISREG
        if not expected_type(result.st_mode):
            raise UnsafeAuthorityError(f"fleet lease {kind} has the wrong file type: {path}")
        if result.st_uid != os.geteuid():
            raise UnsafeAuthorityError(f"fleet lease {kind} is not owned by the effective user")
        actual_mode = stat.S_IMODE(result.st_mode)
        if actual_mode != mode:
            raise UnsafeAuthorityError(
                f"fleet lease {kind} mode must be {mode:04o}; found {actual_mode:04o}"
            )
        return result

    @staticmethod
    def _validate_opened_node(
        result: os.stat_result, *, mode: int, kind: str, directory: bool = False
    ) -> None:
        expected = stat.S_ISDIR if directory else stat.S_ISREG
        if not expected(result.st_mode):
            raise UnsafeAuthorityError(f"fleet lease {kind} has the wrong file type")
        if result.st_uid != os.geteuid():
            raise UnsafeAuthorityError(f"fleet lease {kind} is not owned by the effective user")
        actual_mode = stat.S_IMODE(result.st_mode)
        if actual_mode != mode:
            raise UnsafeAuthorityError(
                f"fleet lease {kind} mode must be {mode:04o}; found {actual_mode:04o}"
            )

    @staticmethod
    def _same_node(before: os.stat_result, opened: os.stat_result, *, kind: str) -> None:
        if (before.st_dev, before.st_ino) != (opened.st_dev, opened.st_ino):
            raise UnsafeAuthorityError(f"fleet lease {kind} changed identity while opening")

    def _ensure_root(self) -> None:
        if self.root.exists() or self.root.is_symlink():
            self._validate_node(self.root, mode=0o700, kind="root")
            return
        try:
            self.root.mkdir(mode=0o700, parents=True, exist_ok=False)
            os.chmod(self.root, 0o700, follow_symlinks=False)
        except FileExistsError:
            # Another broker may have won first creation; validate its result below.
            pass
        self._validate_node(self.root, mode=0o700, kind="root")
        self._fsync_directory(self.root.parent)

    def _open_authority(self, *, create: bool) -> int | None:
        """Retain the opened authority directory so path swaps cannot redirect later I/O."""

        pid = os.getpid()
        with self._authority_fd_lock:
            if self._authority_fd is not None and self._authority_fd_pid == pid:
                opened = os.fstat(self._authority_fd)
                self._validate_opened_node(opened, mode=0o700, kind="root", directory=True)
                try:
                    current = self._validate_node(self.root, mode=0o700, kind="root")
                except FileNotFoundError as exc:
                    raise UnsafeAuthorityError(
                        "fleet lease root path no longer identifies the opened authority"
                    ) from exc
                self._same_node(current, opened, kind="root")
                return self._authority_fd
            if self._authority_fd is not None:
                os.close(self._authority_fd)
                self._authority_fd = None
                self._authority_fd_pid = None
            if create:
                self._ensure_root()
            elif not self.root.exists() and not self.root.is_symlink():
                return None
            try:
                before = self._validate_node(self.root, mode=0o700, kind="root")
                fd = os.open(self.root, os.O_RDONLY | _DIRECTORY | _NOFOLLOW)
            except FileNotFoundError as exc:
                if not create:
                    return None
                raise UnsafeAuthorityError("fleet lease root disappeared while opening") from exc
            except OSError as exc:
                raise UnsafeAuthorityError(f"cannot open fleet lease root safely: {exc}") from exc
            try:
                opened = os.fstat(fd)
                self._validate_opened_node(opened, mode=0o700, kind="root", directory=True)
                self._same_node(before, opened, kind="root")
            except BaseException:
                os.close(fd)
                raise
            self._authority_fd = fd
            self._authority_fd_pid = pid
            return fd

    @staticmethod
    def _stat_at(directory_fd: int, name: str, *, mode: int, kind: str) -> os.stat_result:
        try:
            result = os.stat(name, dir_fd=directory_fd, follow_symlinks=False)
        except FileNotFoundError:
            raise
        if stat.S_ISLNK(result.st_mode):
            raise UnsafeAuthorityError(f"fleet lease {kind} must not be a symlink")
        LeaseBroker._validate_opened_node(result, mode=mode, kind=kind)
        return result

    @staticmethod
    def _open_existing_at(directory_fd: int, name: str, flags: int, *, mode: int, kind: str) -> int:
        before = LeaseBroker._stat_at(directory_fd, name, mode=mode, kind=kind)
        try:
            fd = os.open(name, flags | _NOFOLLOW, dir_fd=directory_fd)
        except OSError as exc:
            raise UnsafeAuthorityError(f"cannot open fleet lease {kind} safely: {exc}") from exc
        try:
            opened = os.fstat(fd)
            LeaseBroker._validate_opened_node(opened, mode=mode, kind=kind)
            LeaseBroker._same_node(before, opened, kind=kind)
        except BaseException:
            os.close(fd)
            raise
        return fd

    @staticmethod
    def _fsync_directory(path: Path) -> None:
        fd = os.open(path, os.O_RDONLY)
        try:
            os.fsync(fd)
        finally:
            os.close(fd)

    @contextlib.contextmanager
    def _locked(self) -> Iterator[None]:
        authority_fd = cast(int, self._open_authority(create=True))
        created = False
        try:
            fd = os.open(
                LOCK_NAME,
                os.O_CREAT | os.O_EXCL | os.O_RDWR | _NOFOLLOW,
                0o600,
                dir_fd=authority_fd,
            )
            created = True
        except FileExistsError:
            fd = self._open_existing_at(authority_fd, LOCK_NAME, os.O_RDWR, mode=0o600, kind="lock")
        except OSError as exc:
            raise UnsafeAuthorityError(f"cannot open fleet lease lock safely: {exc}") from exc
        try:
            opened = os.fstat(fd)
            self._validate_opened_node(opened, mode=0o600, kind="lock")
            if created:
                os.fsync(authority_fd)
            fcntl.flock(fd, fcntl.LOCK_EX)
            try:
                self._open_authority(create=False)
                yield
            finally:
                self._open_authority(create=False)
                fcntl.flock(fd, fcntl.LOCK_UN)
        finally:
            os.close(fd)

    def _read_registry(self, *, create: bool) -> Registry | None:
        authority_fd = self._open_authority(create=create)
        if authority_fd is None:
            return Registry.fresh(self.providers) if create else None
        try:
            fd = self._open_existing_at(
                authority_fd, REGISTRY_NAME, os.O_RDONLY, mode=0o600, kind="registry"
            )
        except FileNotFoundError:
            return Registry.fresh(self.providers) if create else None
        try:
            chunks: list[bytes] = []
            while chunk := os.read(fd, 65536):
                chunks.append(chunk)
        finally:
            os.close(fd)
        try:
            payload = json.loads(b"".join(chunks).decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise RegistryCorruptError(
                f"fleet lease registry is not valid UTF-8 JSON: {exc}"
            ) from exc
        if not isinstance(payload, dict):
            raise RegistryCorruptError("fleet lease registry must contain an object")
        return Registry.from_dict(payload)

    def _write_registry(self, registry: Registry) -> None:
        authority_fd = cast(int, self._open_authority(create=True))
        # Validate the complete authority before archive sidecars are changed.
        Registry.from_dict(registry.to_dict())
        self._compact_closed_fences(registry)
        # Round-trip validation before authority replacement catches programmer errors fail-closed.
        payload = registry.to_dict()
        Registry.from_dict(payload)
        with contextlib.suppress(FileNotFoundError):
            self._stat_at(authority_fd, REGISTRY_NAME, mode=0o600, kind="registry")
        temp = (
            f".{REGISTRY_NAME}.{os.getpid()}.{threading.get_ident()}."
            f"{self.providers.monotonic_ns()}.tmp"
        )
        flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL | _NOFOLLOW
        encoded = (json.dumps(payload, indent=2, sort_keys=True) + "\n").encode("utf-8")
        try:
            fd = os.open(temp, flags, 0o600, dir_fd=authority_fd)
            try:
                os.fchmod(fd, 0o600)
                remaining = memoryview(encoded)
                while remaining:
                    written = os.write(fd, remaining)
                    remaining = remaining[written:]
                os.fsync(fd)
            finally:
                os.close(fd)
            os.replace(temp, REGISTRY_NAME, src_dir_fd=authority_fd, dst_dir_fd=authority_fd)
            os.fsync(authority_fd)
        finally:
            with contextlib.suppress(FileNotFoundError):
                os.unlink(temp, dir_fd=authority_fd)

    def _open_closed_fences_dir(self, *, create: bool) -> int | None:
        authority_fd = self._open_authority(create=create)
        if authority_fd is None:
            return None
        if create:
            try:
                os.mkdir(CLOSED_FENCES_DIR, mode=0o700, dir_fd=authority_fd)
                os.fsync(authority_fd)
            except FileExistsError:
                pass
        try:
            before = os.stat(CLOSED_FENCES_DIR, dir_fd=authority_fd, follow_symlinks=False)
        except FileNotFoundError:
            return None
        if stat.S_ISLNK(before.st_mode):
            raise UnsafeAuthorityError("fleet lease closed fences directory must not be a symlink")
        self._validate_opened_node(
            before, mode=0o700, kind="closed fences directory", directory=True
        )
        try:
            fd = os.open(
                CLOSED_FENCES_DIR,
                os.O_RDONLY | _DIRECTORY | _NOFOLLOW,
                dir_fd=authority_fd,
            )
        except OSError as exc:
            raise UnsafeAuthorityError(
                f"cannot open closed fences directory safely: {exc}"
            ) from exc
        try:
            opened = os.fstat(fd)
            self._validate_opened_node(
                opened, mode=0o700, kind="closed fences directory", directory=True
            )
            self._same_node(before, opened, kind="closed fences directory")
        except BaseException:
            os.close(fd)
            raise
        return fd

    def _archived_fence_path(self, digest: str) -> Path:
        _sha256_text(digest, "closed fence digest")
        return self.closed_fences_dir / f"{digest}.json"

    def _archive_closed_fence(self, digest: str, fence: ResourceFence) -> None:
        """Move one exact closed head out of the hot registry without losing disposition history."""

        if resource_sha256(fence.resource_ref) != digest:
            raise RegistryCorruptError("closed fence digest does not match its resource")
        archive_fd = cast(int, self._open_closed_fences_dir(create=True))
        destination = f"{digest}.json"
        with contextlib.suppress(FileNotFoundError):
            self._stat_at(archive_fd, destination, mode=0o600, kind="closed fence")
        temp = (
            f".{digest}.{os.getpid()}.{threading.get_ident()}.{self.providers.monotonic_ns()}.tmp"
        )
        encoded = (json.dumps(fence.to_dict(), indent=2, sort_keys=True) + "\n").encode()
        try:
            fd = os.open(
                temp,
                os.O_WRONLY | os.O_CREAT | os.O_EXCL | _NOFOLLOW,
                0o600,
                dir_fd=archive_fd,
            )
            try:
                os.fchmod(fd, 0o600)
                remaining = memoryview(encoded)
                while remaining:
                    remaining = remaining[os.write(fd, remaining) :]
                os.fsync(fd)
            finally:
                os.close(fd)
            os.replace(temp, destination, src_dir_fd=archive_fd, dst_dir_fd=archive_fd)
            os.fsync(archive_fd)
        finally:
            with contextlib.suppress(FileNotFoundError):
                os.unlink(temp, dir_fd=archive_fd)
            os.close(archive_fd)

    def _read_archived_fence(self, digest: str) -> ResourceFence | None:
        _sha256_text(digest, "closed fence digest")
        archive_fd = self._open_closed_fences_dir(create=False)
        if archive_fd is None:
            return None
        try:
            fd = self._open_existing_at(
                archive_fd,
                f"{digest}.json",
                os.O_RDONLY,
                mode=0o600,
                kind="closed fence",
            )
        except FileNotFoundError:
            os.close(archive_fd)
            return None
        try:
            payload = json.loads(os.read(fd, 65536).decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise RegistryCorruptError(f"closed fence is not valid UTF-8 JSON: {exc}") from exc
        finally:
            os.close(fd)
            os.close(archive_fd)
        if not isinstance(payload, dict):
            raise RegistryCorruptError("closed fence must contain an object")
        return ResourceFence.from_dict(digest, payload)

    def _inspect_archived_fences(self, *, exclude: set[str]) -> dict[str, dict[str, Any]]:
        """Return at most the newest bounded set of validated archived authority heads."""

        archive_fd = self._open_closed_fences_dir(create=False)
        if archive_fd is None:
            return {}
        newest: list[tuple[int, str, ResourceFence]] = []
        try:
            names = os.listdir(archive_fd)
            for name in names:
                if name.startswith("."):
                    continue
                if len(name) != 69 or not name.endswith(".json"):
                    raise RegistryCorruptError("closed fences directory contains an unknown entry")
                digest = name[:-5]
                _sha256_text(digest, "closed fence digest")
                if digest in exclude:
                    continue
                fd = self._open_existing_at(
                    archive_fd, name, os.O_RDONLY, mode=0o600, kind="closed fence"
                )
                try:
                    chunks: list[bytes] = []
                    while chunk := os.read(fd, 65536):
                        chunks.append(chunk)
                    payload = json.loads(b"".join(chunks).decode("utf-8"))
                except (UnicodeDecodeError, json.JSONDecodeError) as exc:
                    raise RegistryCorruptError(
                        f"closed fence is not valid UTF-8 JSON: {exc}"
                    ) from exc
                finally:
                    os.close(fd)
                if not isinstance(payload, dict):
                    raise RegistryCorruptError("closed fence must contain an object")
                fence = ResourceFence.from_dict(digest, payload)
                newest.append((fence.fencing_sequence, digest, fence))
            newest.sort(reverse=True)
            return {
                digest: fence.to_dict()
                for _sequence, digest, fence in sorted(newest[:_MAX_CLOSED_FENCES])
            }
        finally:
            os.close(archive_fd)

    def _compact_closed_fences(self, registry: Registry) -> None:
        """Bound hot closed heads while preserving exact closed/superseded classification."""

        closed = sorted(
            (
                (digest, fence)
                for digest, fence in registry.resource_fences.items()
                if fence.lease_id not in registry.leases
            ),
            key=lambda item: item[1].fencing_sequence,
        )
        for digest, fence in closed[:-_MAX_CLOSED_FENCES]:
            self._archive_closed_fence(digest, fence)
            del registry.resource_fences[digest]

    def _now(self) -> tuple[datetime, str, int, str]:
        wall = self.providers.wall_now()
        if wall.tzinfo is None:
            raise LeaseBrokerError("wall clock provider must return a timezone-aware datetime")
        monotonic = self.providers.monotonic_ns()
        if monotonic < 0:
            raise LeaseBrokerError("monotonic clock provider returned a negative value")
        boot_id = _bounded(self.providers.boot_id(), "boot_id")
        return wall, _utc_text(wall), monotonic, boot_id

    def _expired(self, lease: Lease, *, monotonic: int, boot_id: str) -> bool:
        if lease.boot_id != boot_id:
            return True
        return monotonic >= lease.renewed_monotonic_ns + lease.ttl_seconds * 1_000_000_000

    def _live(self, registry: Registry, *, monotonic: int, boot_id: str) -> list[Lease]:
        retained_ids = {item.lease_id for item in registry.settlements.values()}
        return [
            lease
            for lease in registry.leases.values()
            if lease.lease_id in retained_ids
            or not self._expired(lease, monotonic=monotonic, boot_id=boot_id)
        ]

    def _earliest_expiry(
        self,
        leases: Sequence[Lease],
        *,
        wall: datetime,
        monotonic: int,
        boot_id: str,
    ) -> str | None:
        if not leases:
            return None
        seconds: list[float] = []
        for lease in leases:
            if lease.boot_id != boot_id:
                seconds.append(0)
            else:
                deadline = lease.renewed_monotonic_ns + lease.ttl_seconds * 1_000_000_000
                seconds.append(max(0, deadline - monotonic) / 1_000_000_000)
        return _utc_text(wall + timedelta(seconds=min(seconds)))

    def _admit_agent(
        self,
        registry: Registry,
        *,
        session_id: str,
        policy_sha256: str,
        session_limit: int,
        aggregate_limit: int,
        mutation: MutationMode,
        count: int,
        wall: datetime,
        monotonic: int,
        boot_id: str,
    ) -> None:
        self._purge_orphan_admissions(registry, monotonic=monotonic, boot_id=boot_id)
        live = [
            lease
            for lease in self._live(registry, monotonic=monotonic, boot_id=boot_id)
            if lease.pool == "agent"
        ]
        same_session = [lease for lease in live if lease.session_id == session_id]
        expected = (policy_sha256, session_limit, aggregate_limit, mutation)
        configured = registry.session_admissions.get(session_id)
        if configured is not None and configured.contract != expected:
            raise PolicyMismatchError(
                f"session {session_id!r} admission snapshot does not match its configured policy"
            )
        snapshots = {
            (lease.policy_sha256, lease.session_limit, lease.aggregate_limit, lease.mutation)
            for lease in same_session
        }
        candidate = (policy_sha256, session_limit, aggregate_limit, mutation)
        if snapshots and snapshots != {candidate}:
            raise PolicyMismatchError(
                f"session {session_id!r} already has live leases under a different admission snapshot"
            )
        if len(same_session) + count > session_limit:
            raise CapacityExhaustedError(
                f"session {session_id!r} would exceed session_limit={session_limit}",
                earliest_expiry=self._earliest_expiry(
                    same_session, wall=wall, monotonic=monotonic, boot_id=boot_id
                ),
            )
        live_limits = [
            cast(int, lease.aggregate_limit) for lease in live if lease.aggregate_limit is not None
        ]
        effective_aggregate = min([aggregate_limit, *live_limits])
        if len(live) + count > effective_aggregate:
            raise CapacityExhaustedError(
                f"fleet would exceed effective aggregate_limit={effective_aggregate}",
                earliest_expiry=self._earliest_expiry(
                    live, wall=wall, monotonic=monotonic, boot_id=boot_id
                ),
            )

    def _admit_worktree(
        self, registry: Registry, *, count: int, monotonic: int, boot_id: str, wall: datetime
    ) -> None:
        live = [
            lease
            for lease in self._live(registry, monotonic=monotonic, boot_id=boot_id)
            if lease.pool == "worktree"
        ]
        if len(live) + count > self.worktree_limit:
            raise CapacityExhaustedError(
                f"worktree pool would exceed limit={self.worktree_limit}",
                earliest_expiry=self._earliest_expiry(
                    live, wall=wall, monotonic=monotonic, boot_id=boot_id
                ),
            )

    @staticmethod
    def _session_has_live_agents(
        registry: Registry, session_id: str, *, monotonic: int, boot_id: str
    ) -> bool:
        retained_ids = {item.lease_id for item in registry.settlements.values()}
        return any(
            lease.pool == "agent"
            and lease.session_id == session_id
            and (
                lease.lease_id in retained_ids
                or not LeaseBroker._expired_static(lease, monotonic=monotonic, boot_id=boot_id)
            )
            for lease in registry.leases.values()
        )

    @staticmethod
    def _admission_expired(admission: SessionAdmission, *, monotonic: int, boot_id: str) -> bool:
        return admission.boot_id != boot_id or monotonic >= (
            admission.configured_monotonic_ns + admission.ttl_seconds * 1_000_000_000
        )

    def _purge_orphan_admissions(
        self, registry: Registry, *, monotonic: int, boot_id: str
    ) -> tuple[str, ...]:
        purged = sorted(
            session
            for session, admission in registry.session_admissions.items()
            if self._admission_expired(admission, monotonic=monotonic, boot_id=boot_id)
            and not self._session_has_live_agents(
                registry, session, monotonic=monotonic, boot_id=boot_id
            )
        )
        for session in purged:
            del registry.session_admissions[session]
        return tuple(purged)

    @staticmethod
    def _expired_static(lease: Lease, *, monotonic: int, boot_id: str) -> bool:
        return lease.boot_id != boot_id or monotonic >= (
            lease.renewed_monotonic_ns + lease.ttl_seconds * 1_000_000_000
        )

    def configure_session_admission(
        self,
        session_id: str,
        *,
        policy_sha256: str,
        session_limit: int,
        aggregate_limit: int,
        mutation: MutationMode,
    ) -> SessionAdmission:
        """Pin a resolved policy through live leases or a bounded pre-spawn claim window."""

        session = _bounded(session_id, "session_id")
        contract = (
            _sha256_text(policy_sha256, "policy_sha256"),
            _positive(session_limit, "session_limit"),
            _positive(aggregate_limit, "aggregate_limit"),
            mutation,
        )
        if contract[1] > contract[2]:
            raise LeaseBrokerError("session_limit must not exceed aggregate_limit")
        if mutation not in ("read-write", "none"):
            raise LeaseBrokerError("mutation must be read-write or none")
        with self._locked():
            registry = cast(Registry, self._read_registry(create=True))
            _wall, _now_text, monotonic, boot_id = self._now()
            self._purge_orphan_admissions(registry, monotonic=monotonic, boot_id=boot_id)
            existing = registry.session_admissions.get(session)
            if existing is not None:
                live = self._session_has_live_agents(
                    registry, session, monotonic=monotonic, boot_id=boot_id
                )
                if existing.contract != contract and live:
                    raise PolicyMismatchError(
                        f"session {session!r} cannot replace its live admission snapshot"
                    )
                if existing.contract == contract and live:
                    return existing
            elif len(registry.session_admissions) >= _MAX_SESSION_ADMISSIONS:
                raise CapacityExhaustedError(
                    "session admission registry is full",
                    earliest_expiry=None,
                )
            admission = SessionAdmission(
                contract[0],
                contract[1],
                contract[2],
                cast(MutationMode, contract[3]),
                monotonic,
                boot_id,
                DEFAULT_TTL_SECONDS,
            )
            registry.session_admissions[session] = admission
            self._write_registry(registry)
            return admission

    def get_session_admission(self, session_id: str) -> SessionAdmission | None:
        """Read a pinned resolved policy without creating or modifying authority."""

        session = _bounded(session_id, "session_id")
        registry = self._read_registry(create=False)
        if registry is None:
            return None
        admission = registry.session_admissions.get(session)
        if admission is None:
            return None
        _wall, _now_text, monotonic, boot_id = self._now()
        if self._admission_expired(admission, monotonic=monotonic, boot_id=boot_id) and not (
            self._session_has_live_agents(registry, session, monotonic=monotonic, boot_id=boot_id)
        ):
            return None
        return admission

    def clear_session_admission(self, session_id: str) -> bool:
        """Forget a policy pin only after every live agent lease for that session has drained."""

        session = _bounded(session_id, "session_id")
        with self._locked():
            registry = cast(Registry, self._read_registry(create=True))
            _wall, _now_text, monotonic, boot_id = self._now()
            if self._session_has_live_agents(
                registry, session, monotonic=monotonic, boot_id=boot_id
            ):
                raise LeaseOwnershipError(
                    f"session {session!r} still has live agent leases; admission cannot be cleared"
                )
            if session not in registry.session_admissions:
                return False
            del registry.session_admissions[session]
            self._write_registry(registry)
            return True

    def _new_lease(
        self,
        registry: Registry,
        *,
        pool: Pool,
        owner_id: str,
        owner_pid: int | None,
        owner_process_start: str | None,
        session_id: str,
        agent_id: str | None,
        tool_use_id: str | None,
        agent_type: str | None,
        batch_id: str | None,
        resource_ref: ResourceRef | None,
        policy_sha256: str | None,
        session_limit: int | None,
        aggregate_limit: int | None,
        mutation: MutationMode | None,
        ttl_seconds: int,
        now_text: str,
        monotonic: int,
        boot_id: str,
    ) -> Lease:
        lease_id = str(self.providers.uuid4())
        sequence = registry.issue_sequence()
        lease = Lease(
            lease_id=lease_id,
            pool=pool,
            owner_id=owner_id,
            owner_pid=owner_pid,
            owner_process_start=owner_process_start,
            session_id=session_id,
            agent_id=agent_id,
            tool_use_id=tool_use_id,
            agent_type=agent_type,
            batch_id=batch_id,
            resource_ref=resource_ref,
            policy_sha256=policy_sha256,
            session_limit=session_limit,
            aggregate_limit=aggregate_limit,
            mutation=mutation,
            boot_id=boot_id,
            acquired_at=now_text,
            renewed_at=now_text,
            renewed_monotonic_ns=monotonic,
            claimed_at=now_text if agent_id is not None else None,
            child_terminal_at=None,
            parent_completed_at=None,
            ttl_seconds=ttl_seconds,
            broker_epoch=registry.broker_epoch,
            fencing_sequence=sequence,
        )
        registry.leases[lease_id] = lease
        if resource_ref is not None:
            self._make_resource_current(registry, lease)
        return lease

    def _make_resource_current(self, registry: Registry, lease: Lease) -> None:
        if lease.resource_ref is None:
            raise LeaseBrokerError("cannot fence a lease without a resource_ref")
        digest = resource_sha256(lease.resource_ref)
        if digest in registry.settlements:
            raise LeaseOwnershipError(
                "resource has retained settlement authority and cannot be superseded"
            )
        prior = registry.resource_fences.get(digest)
        if prior is not None and prior.lease_id != lease.lease_id:
            registry.leases.pop(prior.lease_id, None)
        registry.resource_fences[digest] = ResourceFence(
            resource_ref=lease.resource_ref,
            broker_epoch=registry.broker_epoch,
            fencing_sequence=lease.fencing_sequence,
            lease_id=lease.lease_id,
        )

    def _drop_superseded_resource_lease(
        self, registry: Registry, resource_ref: Mapping[str, Any]
    ) -> None:
        """Remove prior authority before applying capacity to an atomic retry grant."""

        digest = resource_sha256(resource_ref)
        if digest in registry.settlements:
            raise LeaseOwnershipError(
                "resource has retained settlement authority and cannot be superseded"
            )
        prior = registry.resource_fences.get(digest) or self._read_archived_fence(digest)
        if (
            prior is not None
            and prior.close_receipt is not None
            and prior.lease_id not in registry.leases
        ):
            raise LeaseOwnershipError(
                "canonically closed resource requires acquire_successor with predecessor receipt"
            )
        if prior is not None:
            registry.leases.pop(prior.lease_id, None)

    @staticmethod
    def _require_no_retained_settlements(
        registry: Registry, leases: Sequence[Lease], *, operation: str
    ) -> None:
        retained = {
            settlement.lease_id: settlement.phase for settlement in registry.settlements.values()
        }
        blocked = [
            f"{lease.lease_id}:{retained[lease.lease_id]}"
            for lease in leases
            if lease.lease_id in retained
        ]
        if blocked:
            raise LeaseOwnershipError(
                f"{operation} cannot retire retained settlement authority: {', '.join(blocked)}"
            )

    @staticmethod
    def _require_owner_admission_open(registry: Registry, owner_id: str) -> None:
        """Refuse admission-shaped operations for a monotonically closed owner (#358 R2)."""

        close = registry.closed_owner_admissions.get(owner_id)
        if close is not None:
            raise OwnerAdmissionClosedError(
                f"owner admission for {owner_id!r} closed at {close.closed_at} "
                f"(generation {close.close_generation}); acquire/reserve/claim/retry are refused"
            )

    def _require_current_parent(
        self,
        registry: Registry,
        parent_agent_id: str | None,
        session_id: str,
        *,
        monotonic: int,
        boot_id: str,
    ) -> None:
        """Validate nested delegation in the same lock transaction that grants its child."""

        if parent_agent_id is None:
            return
        matches = [lease for lease in registry.leases.values() if lease.agent_id == parent_agent_id]
        if len(matches) != 1:
            raise LeaseNotFoundError(
                f"expected one current parent lease for agent {parent_agent_id!r}"
            )
        parent = matches[0]
        if parent.session_id != session_id or parent.resource_ref is None:
            raise LeaseOwnershipError("delegated parent belongs to a different session")
        state, current = self._current_state(
            registry,
            parent.resource_ref,
            parent.token,
            monotonic=monotonic,
            boot_id=boot_id,
        )
        if state != "current" or current is None or current.lease_id != parent.lease_id:
            raise LeaseOwnershipError("delegated parent has no current spawn authority")

    def acquire_agent(
        self,
        *,
        owner_id: str,
        session_id: str,
        policy_sha256: str,
        session_limit: int,
        aggregate_limit: int,
        mutation: MutationMode,
        ttl_seconds: int = DEFAULT_TTL_SECONDS,
        resource_ref: Mapping[str, Any] | None = None,
        owner_pid: int | None = None,
        owner_process_start: str | None = None,
        agent_id: str | None = None,
        tool_use_id: str | None = None,
        agent_type: str | None = None,
        batch_id: str | None = None,
        parent_agent_id: str | None = None,
    ) -> Lease:
        """Atomically reserve one agent slot, provisional when ``resource_ref`` is absent."""

        owner = _bounded(owner_id, "owner_id")
        session = _bounded(session_id, "session_id")
        digest = _sha256_text(policy_sha256, "policy_sha256")
        session_cap = _positive(session_limit, "session_limit")
        aggregate_cap = _positive(aggregate_limit, "aggregate_limit")
        if session_cap > aggregate_cap:
            raise LeaseBrokerError("session_limit must not exceed aggregate_limit")
        if mutation not in ("read-write", "none"):
            raise LeaseBrokerError("mutation must be read-write or none")
        ttl = _positive(ttl_seconds, "ttl_seconds")
        resource = None if resource_ref is None else canonical_resource_ref("agent", resource_ref)
        parsed_agent = _optional_bounded(agent_id, "agent_id")
        if parsed_agent is not None and resource is None:
            raise LeaseBrokerError("a bound agent lease requires resource_ref")
        pid = None if owner_pid is None else _positive(owner_pid, "owner_pid")
        process_start = _optional_bounded(owner_process_start, "owner_process_start")
        parent = _optional_bounded(parent_agent_id, "parent_agent_id")
        if pid is not None and process_start is None:
            process_start = self.providers.process_identity(pid)
        with self._locked():
            registry = cast(Registry, self._read_registry(create=True))
            self._require_owner_admission_open(registry, owner)
            wall, now_text, monotonic, boot_id = self._now()
            self._require_current_parent(
                registry, parent, session, monotonic=monotonic, boot_id=boot_id
            )
            parsed_tool = _optional_bounded(tool_use_id, "tool_use_id")
            if parsed_tool is not None:
                existing = [
                    lease
                    for lease in registry.leases.values()
                    if lease.pool == "agent"
                    and lease.session_id == session
                    and lease.tool_use_id == parsed_tool
                    and lease.agent_id is None
                    and not self._expired(lease, monotonic=monotonic, boot_id=boot_id)
                ]
                if len(existing) > 1:
                    raise RegistryCorruptError(
                        f"multiple provisional leases use tool_use_id {parsed_tool!r}"
                    )
                if existing:
                    lease = existing[0]
                    if (
                        lease.owner_id != owner
                        or lease.agent_type != _optional_bounded(agent_type, "agent_type")
                        or lease.policy_sha256 != digest
                        or lease.session_limit != session_cap
                        or lease.aggregate_limit != aggregate_cap
                        or lease.mutation != mutation
                    ):
                        raise LeaseOwnershipError(
                            f"tool_use_id {parsed_tool!r} already identifies a different reservation"
                        )
                    return lease
            if resource is not None:
                self._drop_superseded_resource_lease(registry, resource)
            self._admit_agent(
                registry,
                session_id=session,
                policy_sha256=digest,
                session_limit=session_cap,
                aggregate_limit=aggregate_cap,
                mutation=mutation,
                count=1,
                wall=wall,
                monotonic=monotonic,
                boot_id=boot_id,
            )
            lease = self._new_lease(
                registry,
                pool="agent",
                owner_id=owner,
                owner_pid=pid,
                owner_process_start=process_start,
                session_id=session,
                agent_id=parsed_agent,
                tool_use_id=parsed_tool,
                agent_type=_optional_bounded(agent_type, "agent_type"),
                batch_id=_optional_bounded(batch_id, "batch_id"),
                resource_ref=resource,
                policy_sha256=digest,
                session_limit=session_cap,
                aggregate_limit=aggregate_cap,
                mutation=mutation,
                ttl_seconds=ttl,
                now_text=now_text,
                monotonic=monotonic,
                boot_id=boot_id,
            )
            self._write_registry(registry)
            return lease

    def acquire_successor(
        self,
        *,
        owner_id: str,
        session_id: str,
        policy_sha256: str,
        session_limit: int,
        aggregate_limit: int,
        mutation: MutationMode,
        resource_ref: Mapping[str, Any],
        predecessor_token: FencingToken,
        predecessor_receipt_sha256: str,
        ttl_seconds: int = DEFAULT_TTL_SECONDS,
        owner_pid: int | None = None,
        owner_process_start: str | None = None,
        agent_id: str | None = None,
        tool_use_id: str | None = None,
        agent_type: str | None = None,
    ) -> Lease:
        """Acquire only from the exact canonically closed predecessor resource head."""

        owner = _bounded(owner_id, "owner_id")
        session = _bounded(session_id, "session_id")
        policy = _sha256_text(policy_sha256, "policy_sha256")
        session_cap = _positive(session_limit, "session_limit")
        aggregate_cap = _positive(aggregate_limit, "aggregate_limit")
        if session_cap > aggregate_cap:
            raise LeaseBrokerError("session_limit must not exceed aggregate_limit")
        if mutation not in {"read-write", "none"}:
            raise LeaseBrokerError("mutation must be read-write or none")
        resource = canonical_resource_ref("agent", resource_ref)
        receipt_digest = _sha256_text(predecessor_receipt_sha256, "predecessor_receipt_sha256")
        ttl = _positive(ttl_seconds, "ttl_seconds")
        pid = None if owner_pid is None else _positive(owner_pid, "owner_pid")
        process_start = _optional_bounded(owner_process_start, "owner_process_start")
        if pid is not None and process_start is None:
            process_start = self.providers.process_identity(pid)
        parsed_agent = _optional_bounded(agent_id, "agent_id")
        parsed_tool = _optional_bounded(tool_use_id, "tool_use_id")
        parsed_type = _optional_bounded(agent_type, "agent_type")
        with self._locked():
            registry = cast(Registry, self._read_registry(create=True))
            self._require_owner_admission_open(registry, owner)
            wall, now_text, monotonic, boot_id = self._now()
            digest = resource_sha256(resource)
            if digest in registry.settlements:
                raise LeaseOwnershipError(
                    "resource has retained settlement authority and cannot admit a successor"
                )
            head = registry.resource_fences.get(digest) or self._read_archived_fence(digest)
            if head is None or head.resource_ref != resource:
                raise LeaseNotFoundError("successor predecessor resource head does not exist")
            if registry.leases.get(head.lease_id) is not None:
                raise LeaseOwnershipError("successor requires a canonically closed predecessor")
            close = head.close_receipt
            if (
                close is None
                or predecessor_token.broker_epoch != head.broker_epoch
                or predecessor_token.fencing_sequence != head.fencing_sequence
                or close["receipt_sha256"] != receipt_digest
            ):
                raise LeaseOwnershipError(
                    "successor predecessor token or receipt CAS does not match"
                )
            self._admit_agent(
                registry,
                session_id=session,
                policy_sha256=policy,
                session_limit=session_cap,
                aggregate_limit=aggregate_cap,
                mutation=mutation,
                count=1,
                wall=wall,
                monotonic=monotonic,
                boot_id=boot_id,
            )
            lease = self._new_lease(
                registry,
                pool="agent",
                owner_id=owner,
                owner_pid=pid,
                owner_process_start=process_start,
                session_id=session,
                agent_id=parsed_agent,
                tool_use_id=parsed_tool,
                agent_type=parsed_type,
                batch_id=None,
                resource_ref=resource,
                policy_sha256=policy,
                session_limit=session_cap,
                aggregate_limit=aggregate_cap,
                mutation=cast(MutationMode, mutation),
                ttl_seconds=ttl,
                now_text=now_text,
                monotonic=monotonic,
                boot_id=boot_id,
            )
            self._write_registry(registry)
            return lease

    def reserve_batch(
        self,
        *,
        count: int,
        owner_id: str,
        session_id: str,
        batch_id: str,
        agent_type: str,
        policy_sha256: str,
        session_limit: int,
        aggregate_limit: int,
        mutation: MutationMode,
        ttl_seconds: int = DEFAULT_CLAIM_TTL_SECONDS,
        owner_pid: int | None = None,
        owner_process_start: str | None = None,
    ) -> tuple[Lease, ...]:
        """Reserve an all-or-nothing named workflow batch."""

        amount = _positive(count, "count")
        owner = _bounded(owner_id, "owner_id")
        session = _bounded(session_id, "session_id")
        batch = _bounded(batch_id, "batch_id")
        kind = _bounded(agent_type, "agent_type")
        digest = _sha256_text(policy_sha256, "policy_sha256")
        session_cap = _positive(session_limit, "session_limit")
        aggregate_cap = _positive(aggregate_limit, "aggregate_limit")
        if session_cap > aggregate_cap:
            raise LeaseBrokerError("session_limit must not exceed aggregate_limit")
        if mutation not in ("read-write", "none"):
            raise LeaseBrokerError("mutation must be read-write or none")
        ttl = _positive(ttl_seconds, "ttl_seconds")
        pid = None if owner_pid is None else _positive(owner_pid, "owner_pid")
        process_start = _optional_bounded(owner_process_start, "owner_process_start")
        if pid is not None and process_start is None:
            process_start = self.providers.process_identity(pid)
        with self._locked():
            registry = cast(Registry, self._read_registry(create=True))
            self._require_owner_admission_open(registry, owner)
            wall, now_text, monotonic, boot_id = self._now()
            existing = sorted(
                (
                    lease
                    for lease in registry.leases.values()
                    if lease.pool == "agent"
                    and lease.batch_id == batch
                    and not self._expired(lease, monotonic=monotonic, boot_id=boot_id)
                ),
                key=lambda lease: lease.fencing_sequence,
            )
            if existing:
                if len(existing) != amount or any(
                    lease.owner_id != owner
                    or lease.session_id != session
                    or lease.agent_type != kind
                    or lease.policy_sha256 != digest
                    or lease.session_limit != session_cap
                    or lease.aggregate_limit != aggregate_cap
                    or lease.mutation != mutation
                    for lease in existing
                ):
                    raise LeaseOwnershipError(
                        f"workflow batch {batch!r} already exists under a different contract"
                    )
                return tuple(existing)
            self._admit_agent(
                registry,
                session_id=session,
                policy_sha256=digest,
                session_limit=session_cap,
                aggregate_limit=aggregate_cap,
                mutation=mutation,
                count=amount,
                wall=wall,
                monotonic=monotonic,
                boot_id=boot_id,
            )
            leases = tuple(
                self._new_lease(
                    registry,
                    pool="agent",
                    owner_id=owner,
                    owner_pid=pid,
                    owner_process_start=process_start,
                    session_id=session,
                    agent_id=None,
                    tool_use_id=None,
                    agent_type=kind,
                    batch_id=batch,
                    resource_ref=None,
                    policy_sha256=digest,
                    session_limit=session_cap,
                    aggregate_limit=aggregate_cap,
                    mutation=mutation,
                    ttl_seconds=ttl,
                    now_text=now_text,
                    monotonic=monotonic,
                    boot_id=boot_id,
                )
                for _ in range(amount)
            )
            self._write_registry(registry)
            return leases

    def claim(
        self,
        *,
        session_id: str,
        agent_type: str,
        agent_id: str,
        resource_ref: Mapping[str, Any] | None = None,
        worktree_root: Path | str | None = None,
        batch_id: str | None = None,
        execution_ttl_seconds: int = DEFAULT_TTL_SECONDS,
    ) -> Lease:
        """Bind the oldest compatible provisional reservation exactly once."""

        session = _bounded(session_id, "session_id")
        kind = _bounded(agent_type, "agent_type")
        child = _bounded(agent_id, "agent_id")
        batch = _optional_bounded(batch_id, "batch_id")
        resource = None if resource_ref is None else canonical_resource_ref("agent", resource_ref)
        canonical_worktree = (
            None
            if worktree_root is None
            else _safe_absolute_path(str(worktree_root), "worktree_root")
        )
        ttl = _positive(execution_ttl_seconds, "execution_ttl_seconds")
        with self._locked():
            registry = cast(Registry, self._read_registry(create=True))
            wall, now_text, monotonic, boot_id = self._now()
            bound = [
                lease
                for lease in registry.leases.values()
                if lease.pool == "agent"
                and lease.session_id == session
                and lease.agent_type in (kind, "*")
                and lease.batch_id == batch
                and lease.agent_id == child
                and not self._expired(lease, monotonic=monotonic, boot_id=boot_id)
            ]
            if len(bound) > 1:
                raise RegistryCorruptError(f"multiple leases are bound to agent {child!r}")
            if bound:
                existing = bound[0]
                if resource is not None and existing.resource_ref != resource:
                    raise LeaseOwnershipError(
                        f"agent {child!r} is already bound to a different resource"
                    )
                return existing
            candidates = [
                lease
                for lease in registry.leases.values()
                if lease.pool == "agent"
                and lease.session_id == session
                and lease.agent_type in (kind, "*")
                and lease.batch_id == batch
                and lease.agent_id is None
                and (batch is None or lease.tool_use_id is not None)
                and not self._expired(lease, monotonic=monotonic, boot_id=boot_id)
            ]
            if not candidates:
                raise LeaseNotFoundError(
                    f"no live provisional reservation for session={session!r}, "
                    f"agent_type={kind!r}, batch_id={batch!r}"
                )
            selected = min(candidates, key=lambda lease: (lease.fencing_sequence, lease.lease_id))
            self._require_owner_admission_open(registry, selected.owner_id)
            if resource is None:
                logical_unit_id = selected.tool_use_id or f"{session}:{kind}:{child}"
                derived: dict[str, str] = {"logical_unit_id": logical_unit_id}
                if canonical_worktree is not None:
                    derived["worktree_root"] = canonical_worktree
                resource = canonical_resource_ref("agent", derived)
            sequence = registry.issue_sequence()
            claimed = replace(
                selected,
                agent_id=child,
                resource_ref=resource,
                claimed_at=now_text,
                renewed_at=now_text,
                renewed_monotonic_ns=monotonic,
                boot_id=boot_id,
                ttl_seconds=ttl,
                fencing_sequence=sequence,
            )
            registry.leases[selected.lease_id] = claimed
            self._make_resource_current(registry, claimed)
            self._write_registry(registry)
            return claimed

    def prepare_batch_call(
        self,
        *,
        session_id: str,
        batch_id: str,
        agent_type: str,
        tool_use_id: str,
        claim_ttl_seconds: int = DEFAULT_CLAIM_TTL_SECONDS,
        parent_agent_id: str | None = None,
    ) -> Lease:
        """Assign one reusable batch slot to a concrete pre-spawn Agent tool call."""

        session = _bounded(session_id, "session_id")
        batch = _bounded(batch_id, "batch_id")
        kind = _bounded(agent_type, "agent_type")
        tool = _bounded(tool_use_id, "tool_use_id")
        parent = _optional_bounded(parent_agent_id, "parent_agent_id")
        ttl = _positive(claim_ttl_seconds, "claim_ttl_seconds")
        with self._locked():
            registry = cast(Registry, self._read_registry(create=True))
            wall, now_text, monotonic, boot_id = self._now()
            self._require_current_parent(
                registry, parent, session, monotonic=monotonic, boot_id=boot_id
            )
            replay = [
                lease
                for lease in registry.leases.values()
                if lease.pool == "agent"
                and lease.session_id == session
                and lease.batch_id == batch
                and lease.tool_use_id == tool
                and lease.agent_id is None
                and not self._expired(lease, monotonic=monotonic, boot_id=boot_id)
            ]
            if len(replay) > 1:
                raise RegistryCorruptError(f"multiple batch slots use tool_use_id {tool!r}")
            if replay:
                return replay[0]
            candidates = [
                lease
                for lease in registry.leases.values()
                if lease.pool == "agent"
                and lease.session_id == session
                and lease.batch_id == batch
                and lease.agent_id is None
                and lease.tool_use_id is None
                and lease.agent_type == "*"
                and not self._expired(lease, monotonic=monotonic, boot_id=boot_id)
            ]
            if not candidates:
                raise CapacityExhaustedError(
                    f"workflow batch {batch!r} has no available reserved slot",
                    earliest_expiry=self._earliest_expiry(
                        [lease for lease in registry.leases.values() if lease.batch_id == batch],
                        wall=wall,
                        monotonic=monotonic,
                        boot_id=boot_id,
                    ),
                )
            selected = min(candidates, key=lambda lease: (lease.fencing_sequence, lease.lease_id))
            self._require_owner_admission_open(registry, selected.owner_id)
            prepared = replace(
                selected,
                agent_type=kind,
                tool_use_id=tool,
                renewed_at=now_text,
                renewed_monotonic_ns=monotonic,
                boot_id=boot_id,
                ttl_seconds=ttl,
            )
            registry.leases[selected.lease_id] = prepared
            self._write_registry(registry)
            return prepared

    def acquire_worktree(
        self,
        *,
        owner_id: str,
        session_id: str,
        resource_ref: Mapping[str, Any],
        ttl_seconds: int = DEFAULT_TTL_SECONDS,
        owner_pid: int | None = None,
        owner_process_start: str | None = None,
    ) -> Lease:
        owner = _bounded(owner_id, "owner_id")
        session = _bounded(session_id, "session_id")
        resource = canonical_resource_ref("worktree", resource_ref)
        ttl = _positive(ttl_seconds, "ttl_seconds")
        pid = None if owner_pid is None else _positive(owner_pid, "owner_pid")
        process_start = _optional_bounded(owner_process_start, "owner_process_start")
        if pid is not None and process_start is None:
            process_start = self.providers.process_identity(pid)
        with self._locked():
            registry = cast(Registry, self._read_registry(create=True))
            self._require_owner_admission_open(registry, owner)
            wall, now_text, monotonic, boot_id = self._now()
            head = registry.resource_fences.get(resource_sha256(resource))
            if head is not None:
                existing = registry.leases.get(head.lease_id)
                if existing is not None:
                    exact_owner = (
                        existing.pool == "worktree"
                        and existing.owner_id == owner
                        and existing.session_id == session
                        and existing.owner_pid == pid
                        and existing.owner_process_start == process_start
                    )
                    if exact_owner and not self._expired(
                        existing, monotonic=monotonic, boot_id=boot_id
                    ):
                        return existing
                    if self._expired(existing, monotonic=monotonic, boot_id=boot_id):
                        raise LeaseExpiredError(
                            "expired worktree ownership must be released or reaped before reacquisition"
                        )
                    raise LeaseOwnershipError(
                        "worktree is already owned by a live coordinator; release or reap it first"
                    )
            self._admit_worktree(registry, count=1, monotonic=monotonic, boot_id=boot_id, wall=wall)
            lease = self._new_lease(
                registry,
                pool="worktree",
                owner_id=owner,
                owner_pid=pid,
                owner_process_start=process_start,
                session_id=session,
                agent_id=None,
                tool_use_id=None,
                agent_type=None,
                batch_id=None,
                resource_ref=resource,
                policy_sha256=None,
                session_limit=None,
                aggregate_limit=None,
                mutation=None,
                ttl_seconds=ttl,
                now_text=now_text,
                monotonic=monotonic,
                boot_id=boot_id,
            )
            self._write_registry(registry)
            return lease

    def transfer_worktree(
        self,
        lease_id: str,
        *,
        token: FencingToken,
        owner_id: str,
        owner_pid: int | None = None,
        owner_process_start: str | None = None,
    ) -> Lease:
        """Atomically bind the current coordinator and renew an exact worktree token.

        The exact current token is the transfer authority, so an expired-but-current lease can be
        recovered by the coordinator that retained it.  A superseded or released token cannot move
        ownership.
        """

        selected_id = _bounded(lease_id, "lease_id")
        owner = _bounded(owner_id, "owner_id")
        pid = None if owner_pid is None else _positive(owner_pid, "owner_pid")
        process_start = _optional_bounded(owner_process_start, "owner_process_start")
        if pid is not None and process_start is None:
            process_start = self.providers.process_identity(pid)
        with self._locked():
            registry = cast(Registry, self._read_registry(create=True))
            self._require_owner_admission_open(registry, owner)
            lease = registry.leases.get(selected_id)
            if lease is None or lease.pool != "worktree" or lease.resource_ref is None:
                raise LeaseNotFoundError(f"worktree lease {selected_id!r} does not exist")
            _wall, now_text, monotonic, boot_id = self._now()
            state, current = self._current_state(
                registry, lease.resource_ref, token, monotonic=monotonic, boot_id=boot_id
            )
            if state == "superseded":
                raise LeaseSupersededError("worktree transfer token has been superseded")
            if state == "closed" or current is None or current.lease_id != selected_id:
                raise LeaseClosedError("worktree transfer token has been released")
            if token != lease.token:
                raise LeaseOwnershipError("worktree transfer token does not match lease")
            transferred = replace(
                lease,
                owner_id=owner,
                owner_pid=pid,
                owner_process_start=process_start,
                renewed_at=now_text,
                renewed_monotonic_ns=monotonic,
                boot_id=boot_id,
            )
            registry.leases[selected_id] = transferred
            self._write_registry(registry)
            return transferred

    def _current_state(
        self,
        registry: Registry,
        resource_ref: Mapping[str, Any],
        token: FencingToken,
        *,
        monotonic: int,
        boot_id: str,
    ) -> tuple[TokenState, Lease | None]:
        digest = resource_sha256(resource_ref)
        head = registry.resource_fences.get(digest)
        if head is None:
            archived = self._read_archived_fence(digest)
            if (
                archived is not None
                and archived.resource_ref == dict(resource_ref)
                and token.broker_epoch == registry.broker_epoch
                and token.broker_epoch == archived.broker_epoch
                and token.fencing_sequence == archived.fencing_sequence
            ):
                return ("closed" if archived.close_receipt is not None else "expired"), None
            return "superseded", None
        if (
            token.broker_epoch != registry.broker_epoch
            or token.broker_epoch != head.broker_epoch
            or token.fencing_sequence != head.fencing_sequence
        ):
            return "superseded", None
        lease = registry.leases.get(head.lease_id)
        if lease is None:
            return ("closed" if head.close_receipt is not None else "expired"), None
        if (
            lease.resource_ref != dict(resource_ref)
            or lease.fencing_sequence != head.fencing_sequence
        ):
            raise RegistryCorruptError("resource head does not bind its referenced live lease")
        retained = registry.settlements.get(digest)
        if retained is not None:
            if retained.lease_id != lease.lease_id or retained.token != token:
                raise RegistryCorruptError("retained settlement does not match its resource head")
            return "current", lease
        if self._expired(lease, monotonic=monotonic, boot_id=boot_id):
            return "expired", lease
        return "current", lease

    def classify_token(
        self, resource_ref: Mapping[str, Any], token: FencingToken, *, pool: Pool = "agent"
    ) -> TokenState:
        resource = canonical_resource_ref(pool, resource_ref)
        registry = self._read_registry(create=False)
        if registry is None:
            return "superseded"
        _wall, _now_text, monotonic, boot_id = self._now()
        return self._current_state(registry, resource, token, monotonic=monotonic, boot_id=boot_id)[
            0
        ]

    def publish_if_token_state(
        self,
        resource_ref: Mapping[str, Any],
        token: FencingToken,
        *,
        expected_state: Literal["expired", "closed"],
        publish: Callable[[], None],
        pool: Pool = "agent",
    ) -> bool:
        """Run one bounded forensic publication only while the token state still matches.

        Payload preparation happens before this call. The callback may perform only the final
        staging rename and commit-marker write, keeping large byte copies outside the broker lock.
        A successor cannot interleave between the state check and that publication.
        """

        resource = canonical_resource_ref(pool, resource_ref)
        if expected_state not in {"expired", "closed"}:
            raise LeaseBrokerError("forensic publication requires expired or closed authority")
        with self._locked():
            registry = cast(Registry, self._read_registry(create=True))
            _wall, _now_text, monotonic, boot_id = self._now()
            state, _lease = self._current_state(
                registry,
                resource,
                token,
                monotonic=monotonic,
                boot_id=boot_id,
            )
            if state != expected_state:
                return False
            publish()
            return True

    def verify(
        self,
        resource_ref: Mapping[str, Any],
        token: FencingToken,
        *,
        pool: Pool = "agent",
        agent_id: str | None = None,
        owner_id: str | None = None,
    ) -> Lease:
        resource = canonical_resource_ref(pool, resource_ref)
        registry = self._read_registry(create=False)
        if registry is None:
            raise LeaseSupersededError("fleet lease authority does not contain this resource token")
        _wall, _now_text, monotonic, boot_id = self._now()
        state, lease = self._current_state(
            registry, resource, token, monotonic=monotonic, boot_id=boot_id
        )
        if state == "superseded":
            raise LeaseSupersededError("resource token has been superseded")
        if state == "closed":
            raise LeaseClosedError("resource token has been released")
        if state == "expired":
            raise LeaseExpiredError("resource token has expired")
        if lease is None:
            raise LeaseNotFoundError("current resource token has no live lease")
        if agent_id is not None and lease.agent_id != _bounded(agent_id, "agent_id"):
            raise LeaseOwnershipError("resource token is not bound to this agent")
        if owner_id is not None and lease.owner_id != _bounded(owner_id, "owner_id"):
            raise LeaseOwnershipError("resource token is not owned by this caller")
        return lease

    def verify_agent(self, agent_id: str) -> Lease:
        """Resolve and verify the current lease bound to trusted hook ``agent_id``."""

        child = _bounded(agent_id, "agent_id")
        registry = self._read_registry(create=False)
        if registry is None:
            raise LeaseNotFoundError(f"no fleet lease is bound to agent {child!r}")
        matches = [lease for lease in registry.leases.values() if lease.agent_id == child]
        if len(matches) != 1:
            raise LeaseNotFoundError(
                f"expected exactly one fleet lease bound to agent {child!r}; found {len(matches)}"
            )
        lease = matches[0]
        if lease.resource_ref is None:
            raise RegistryCorruptError("bound agent lease lacks resource_ref")
        return self.verify(lease.resource_ref, lease.token, agent_id=child)

    def assert_write_target(self, agent_id: str, target: Path | str | None = None) -> Lease:
        """Fence a delegated mutation and optionally validate its worktree target."""

        lease = self.verify_agent(agent_id)
        if lease.mutation != "read-write":
            raise LeaseOwnershipError("agent lease does not authorize mutation")
        worktree_raw = (
            None if lease.resource_ref is None else lease.resource_ref.get("worktree_root")
        )
        if worktree_raw is None:
            return lease
        worktree = Path(worktree_raw)
        if not worktree.is_dir():
            raise MissingResourceError(f"leased worktree is missing: {worktree}")
        try:
            resolved_worktree = worktree.resolve(strict=True)
        except OSError as exc:
            raise MissingResourceError(f"leased worktree cannot be resolved: {worktree}") from exc
        if target is not None:
            candidate = Path(target)
            if not candidate.is_absolute():
                candidate = worktree / candidate
            normalized = Path(os.path.abspath(candidate))
            parent = normalized
            while not parent.exists() and parent != parent.parent:
                parent = parent.parent
            try:
                resolved_parent = parent.resolve(strict=True)
            except OSError as exc:
                raise MissingResourceError(
                    f"write target parent cannot be resolved: {parent}"
                ) from exc
            resolved = resolved_parent.joinpath(*normalized.relative_to(parent).parts)
            try:
                resolved.relative_to(resolved_worktree)
            except ValueError as exc:
                raise MissingResourceError(
                    f"write target {normalized} is outside leased worktree {worktree} through a symlink"
                ) from exc
        return lease

    def renew(
        self,
        lease_id: str,
        *,
        token: FencingToken,
        owner_id: str | None = None,
    ) -> Lease:
        selected_id = _bounded(lease_id, "lease_id")
        with self._locked():
            registry = cast(Registry, self._read_registry(create=True))
            lease = registry.leases.get(selected_id)
            if lease is None:
                raise LeaseNotFoundError(f"lease {selected_id!r} does not exist")
            if owner_id is not None and lease.owner_id != _bounded(owner_id, "owner_id"):
                raise LeaseOwnershipError("lease is not owned by this caller")
            _wall, now_text, monotonic, boot_id = self._now()
            if self._expired(lease, monotonic=monotonic, boot_id=boot_id):
                raise LeaseExpiredError(f"lease {selected_id!r} has expired")
            if token != lease.token:
                raise LeaseOwnershipError("renew token does not match lease")
            if lease.resource_ref is not None:
                state, _ = self._current_state(
                    registry,
                    lease.resource_ref,
                    lease.token,
                    monotonic=monotonic,
                    boot_id=boot_id,
                )
                if state != "current":
                    raise LeaseSupersededError(f"lease {selected_id!r} is no longer current")
            renewed = replace(
                lease,
                renewed_at=now_text,
                renewed_monotonic_ns=monotonic,
                boot_id=boot_id,
            )
            registry.leases[selected_id] = renewed
            self._write_registry(registry)
            return renewed

    def release(
        self,
        lease_id: str,
        *,
        token: FencingToken,
        owner_id: str | None = None,
    ) -> bool:
        selected_id = _bounded(lease_id, "lease_id")
        with self._locked():
            registry = cast(Registry, self._read_registry(create=True))
            lease = registry.leases.get(selected_id)
            if lease is None:
                return False
            if owner_id is not None and lease.owner_id != _bounded(owner_id, "owner_id"):
                raise LeaseOwnershipError("lease is not owned by this caller")
            if token != lease.token:
                raise LeaseOwnershipError("release token does not match lease")
            if (
                lease.resource_ref is not None
                and resource_sha256(lease.resource_ref) in registry.settlements
            ):
                raise LeaseOwnershipError(
                    "lease has retained settlement authority; use abort or recovery"
                )
            del registry.leases[selected_id]
            if lease.pool == "agent":
                _wall, _now_text, monotonic, boot_id = self._now()
                if not self._session_has_live_agents(
                    registry, lease.session_id, monotonic=monotonic, boot_id=boot_id
                ):
                    registry.session_admissions.pop(lease.session_id, None)
            self._write_registry(registry)
            return True

    @staticmethod
    def _settlement_by_id(registry: Registry, settlement_id: str) -> SettlementRecord:
        selected = _uuid_text(settlement_id, "settlement_id")
        matches = [item for item in registry.settlements.values() if item.settlement_id == selected]
        if len(matches) != 1:
            raise LeaseNotFoundError(f"settlement {selected!r} does not exist")
        return matches[0]

    def prepare_agent_settlement(
        self,
        lease_id: str,
        *,
        token: FencingToken,
        owner_id: str,
        producer: str,
        run_id: str,
        expected_output_sha256: str,
        protected_write_intent_sha256: str,
    ) -> SettlementRecord:
        """Persist retained authority before any protected writer may run."""

        selected_id = _uuid_text(lease_id, "lease_id")
        owner = _bounded(owner_id, "owner_id", maximum=128)
        if producer not in {"agy", "saga", "team-execution"}:
            raise LeaseBrokerError("settlement producer is invalid")
        run = _bounded(run_id, "run_id", maximum=128)
        expected = _sha256_text(expected_output_sha256, "expected_output_sha256")
        write_intent = _sha256_text(protected_write_intent_sha256, "protected_write_intent_sha256")
        with self._locked():
            registry = cast(Registry, self._read_registry(create=True))
            lease = registry.leases.get(selected_id)
            if lease is None or lease.pool != "agent" or lease.resource_ref is None:
                raise LeaseNotFoundError(f"agent lease {selected_id!r} does not exist")
            if lease.owner_id != owner or lease.token != token:
                raise LeaseOwnershipError("agent settlement owner or token does not match")
            if lease.policy_sha256 is None:
                raise RegistryCorruptError("agent settlement lease lacks policy_sha256")
            digest = resource_sha256(lease.resource_ref)
            existing = registry.settlements.get(digest)
            if existing is not None:
                if (
                    existing.lease_id == selected_id
                    and existing.owner_id == owner
                    and existing.token == token
                    and existing.producer == producer
                    and existing.run_id == run
                    and existing.expected_output_sha256 == expected
                    and existing.protected_write_intent_sha256 == write_intent
                ):
                    return existing
                raise LeaseOwnershipError("resource already has a different retained settlement")
            if len(registry.settlements) >= _MAX_SETTLEMENTS:
                raise CapacityExhaustedError(
                    "retained settlement registry is full", earliest_expiry=None
                )
            _wall, now_text, monotonic, boot_id = self._now()
            state, current = self._current_state(
                registry,
                lease.resource_ref,
                token,
                monotonic=monotonic,
                boot_id=boot_id,
            )
            if state == "expired":
                raise LeaseExpiredError(f"agent lease {selected_id!r} expired before settlement")
            if state != "current" or current is None or current.lease_id != selected_id:
                raise LeaseSupersededError(
                    f"agent lease {selected_id!r} is not current at settlement"
                )
            renewed = replace(
                lease,
                renewed_at=now_text,
                renewed_monotonic_ns=monotonic,
                boot_id=boot_id,
            )
            registry.leases[selected_id] = renewed
            settlement = SettlementRecord(
                settlement_id=str(self.providers.uuid4()),
                phase="prepared",
                lease_id=selected_id,
                owner_id=owner,
                owner_pid=lease.owner_pid,
                owner_process_start=lease.owner_process_start,
                session_id=lease.session_id,
                policy_sha256=lease.policy_sha256,
                resource_ref=lease.resource_ref,
                token=token,
                producer=producer,
                run_id=run,
                expected_output_sha256=expected,
                protected_write_intent_sha256=write_intent,
                recovery_capability_sha256=registry.recovery_capability_sha256,
                prepared_at=now_text,
                updated_at=now_text,
            )
            registry.settlements[digest] = settlement
            self._write_registry(registry)
            return settlement

    def _commit_settlement_locked(
        self,
        registry: Registry,
        settlement: SettlementRecord,
        *,
        write: Callable[[Lease], Sequence[str]] | None,
        replay_handler: SettlementRecoveryHandler | None = None,
        allow_retained_replay: bool,
    ) -> dict[str, Any]:
        digest = resource_sha256(settlement.resource_ref)
        lease = registry.leases.get(settlement.lease_id)
        if (
            lease is None
            or lease.token != settlement.token
            or lease.resource_ref != settlement.resource_ref
        ):
            raise LeaseOwnershipError("settlement lease is no longer the exact resource authority")
        allowed: set[str] = {"prepared"}
        if allow_retained_replay:
            allowed.update({"committing", "ambiguous"})
        if settlement.phase not in allowed:
            raise LeaseOwnershipError(
                f"settlement phase {settlement.phase!r} is not eligible for this commit"
            )
        _wall, now_text, monotonic, boot_id = self._now()
        committing = replace(settlement, phase="committing", updated_at=now_text)
        registry.settlements[digest] = committing
        registry.leases[lease.lease_id] = replace(
            lease,
            renewed_at=now_text,
            renewed_monotonic_ns=monotonic,
            boot_id=boot_id,
        )
        try:
            self._write_registry(registry)
        except BaseException as exc:
            # A failed replacement occurs before the protected callback is reachable. Reload the
            # durable authority rather than mutating this failed in-memory transaction, then
            # retire only its exact lease and settlement so retry admission is not wedged.
            try:
                self._abort_unstarted_settlement_after_commit_persistence_failure(settlement)
            except BaseException as cleanup_exc:
                exc.add_note(
                    "could not abort unstarted settlement after commit persistence failure: "
                    f"{cleanup_exc}"
                )
            raise
        try:
            renewed = registry.leases[lease.lease_id]
            if replay_handler is None:
                if write is None:
                    raise LeaseBrokerError("settlement commit lacks a protected writer")
                evidence_refs = write(renewed)
            else:
                result = replay_handler.write(renewed, settlement)
                if not isinstance(result, SettlementReplayResult):
                    raise LeaseBrokerError("recovery replay must return SettlementReplayResult")
                if (
                    _sha256_text(
                        result.protected_write_intent_sha256,
                        "recovery replay protected_write_intent_sha256",
                    )
                    != settlement.protected_write_intent_sha256
                    or _sha256_text(result.output_sha256, "recovery replay output_sha256")
                    != settlement.expected_output_sha256
                ):
                    raise LeaseOwnershipError(
                        "recovery replay result does not match retained write/output semantics"
                    )
                evidence_refs = result.evidence_refs
            if isinstance(evidence_refs, (str, bytes)) or not isinstance(evidence_refs, Sequence):
                raise LeaseBrokerError("protected writer must return a sequence of evidence refs")
            close = build_settlement_close(
                resource_ref=settlement.resource_ref,
                token=settlement.token,
                lease_id=settlement.lease_id,
                producer=settlement.producer,
                run_id=settlement.run_id,
                evidence_refs=list(evidence_refs),
                expected_output_sha256=settlement.expected_output_sha256,
                settlement_id=settlement.settlement_id,
                session_id=settlement.session_id,
                policy_sha256=settlement.policy_sha256,
                protected_write_intent_sha256=settlement.protected_write_intent_sha256,
                settlement_sha256=settlement.settlement_sha256,
            )
        except BaseException as exc:
            _failure_wall, failed_at, _failure_monotonic, _failure_boot = self._now()
            registry.settlements[digest] = replace(
                committing, phase="ambiguous", updated_at=failed_at
            )
            try:
                self._write_registry(registry)
            except Exception as audit_exc:
                exc.add_note(f"could not persist ambiguous settlement state: {audit_exc}")
            raise
        head = registry.resource_fences.get(digest)
        if (
            head is None
            or head.lease_id != settlement.lease_id
            or head.broker_epoch != settlement.token.broker_epoch
            or head.fencing_sequence != settlement.token.fencing_sequence
            or head.close_receipt is not None
        ):
            raise LeaseSupersededError("settlement close lost its exact resource-head CAS")
        registry.resource_fences[digest] = ResourceFence(
            resource_ref=settlement.resource_ref,
            broker_epoch=settlement.token.broker_epoch,
            fencing_sequence=settlement.token.fencing_sequence,
            lease_id=settlement.lease_id,
            close_receipt=close,
        )
        registry.leases.pop(settlement.lease_id, None)
        registry.settlements.pop(digest, None)
        _final_wall, _final_text, final_monotonic, final_boot_id = self._now()
        if not self._session_has_live_agents(
            registry,
            settlement.session_id,
            monotonic=final_monotonic,
            boot_id=final_boot_id,
        ):
            registry.session_admissions.pop(settlement.session_id, None)
        # This replacement is the only accepted-write linearization point. If it fails, the
        # durable registry remains in its previously persisted committing phase.
        self._write_registry(registry)
        return close

    def _abort_unstarted_settlement_after_commit_persistence_failure(
        self, settlement: SettlementRecord
    ) -> None:
        """Retire the durable prepared authority when committing-state persistence never began.

        This method is called only while the broker lock is held and before a protected callback.
        Exact matching prevents a stale failed caller from retiring any later authority. A write
        implementation can report failure after replacement, so this accepts the same original
        settlement in either prepared or committing phase while the caller still proves that no
        protected callback was reached.
        """

        registry = cast(Registry, self._read_registry(create=True))
        digest = resource_sha256(settlement.resource_ref)
        persisted = registry.settlements.get(digest)
        lease = registry.leases.get(settlement.lease_id)
        if (
            settlement.phase != "prepared"
            or persisted is None
            or persisted.settlement_sha256 != settlement.settlement_sha256
            or persisted.phase not in {"prepared", "committing"}
            or lease is None
            or lease.token != settlement.token
            or lease.resource_ref != settlement.resource_ref
        ):
            raise LeaseOwnershipError(
                "unstarted settlement no longer has exact prepared authority for rollback"
            )
        registry.settlements.pop(digest, None)
        registry.leases.pop(settlement.lease_id, None)
        _wall, _now_text, monotonic, boot_id = self._now()
        if not self._session_has_live_agents(
            registry,
            settlement.session_id,
            monotonic=monotonic,
            boot_id=boot_id,
        ):
            registry.session_admissions.pop(settlement.session_id, None)
        self._write_registry(registry)

    def commit_agent_settlement(
        self,
        settlement_id: str,
        *,
        owner_id: str,
        token: FencingToken,
        write: Callable[[Lease], Sequence[str]],
    ) -> dict[str, Any]:
        """Run protected writers and atomically publish the canonical closed receipt."""

        owner = _bounded(owner_id, "owner_id", maximum=128)
        with self._locked():
            registry = cast(Registry, self._read_registry(create=True))
            settlement = self._settlement_by_id(registry, settlement_id)
            if settlement.owner_id != owner or settlement.token != token:
                raise LeaseOwnershipError("settlement commit owner or token does not match")
            return self._commit_settlement_locked(
                registry,
                settlement,
                write=write,
                replay_handler=None,
                allow_retained_replay=False,
            )

    def abort_agent_settlement(
        self,
        settlement_id: str,
        *,
        owner_id: str,
        token: FencingToken,
    ) -> bool:
        """Release an exact settlement only while no protected writer may have run."""

        owner = _bounded(owner_id, "owner_id", maximum=128)
        with self._locked():
            registry = cast(Registry, self._read_registry(create=True))
            settlement = self._settlement_by_id(registry, settlement_id)
            if settlement.owner_id != owner or settlement.token != token:
                raise LeaseOwnershipError("settlement abort owner or token does not match")
            if settlement.phase != "prepared":
                raise LeaseOwnershipError("only a prepared settlement can be aborted")
            digest = resource_sha256(settlement.resource_ref)
            registry.settlements.pop(digest, None)
            registry.leases.pop(settlement.lease_id, None)
            _wall, _now_text, monotonic, boot_id = self._now()
            if not self._session_has_live_agents(
                registry,
                settlement.session_id,
                monotonic=monotonic,
                boot_id=boot_id,
            ):
                registry.session_admissions.pop(settlement.session_id, None)
            self._write_registry(registry)
            return True

    @contextlib.contextmanager
    def agent_settlement(
        self,
        lease_id: str,
        *,
        token: FencingToken,
        owner_id: str,
    ) -> Iterator[Lease]:
        """Reject the legacy mutation-capable context manager.

        It cannot express the protected intent, expected output, or close receipt required by the
        failure-atomic protocol. Callers must use prepare_agent_settlement followed by
        commit_agent_settlement (or abort before any protected write).
        """

        del lease_id, token, owner_id
        raise LeaseBrokerError(
            "legacy agent_settlement is disabled; use prepare_agent_settlement and "
            "commit_agent_settlement"
        )
        yield  # pragma: no cover - keeps the contextmanager protocol type without enabling writes.

    def close_owner_admission(self, *, owner_id: str) -> dict[str, Any]:
        """Monotonically close admission for ``owner_id`` under the broker lock (#358 R2).

        After the commit, every acquire, reserve, claim, or retry for this exact owner is
        refused with :class:`OwnerAdmissionClosedError` while existing leases remain
        inspectable and releasable. Repeating close is idempotent (the original record is
        returned) and there is no reopen operation — but the closed map is bounded
        (``_MAX_CLOSED_OWNER_ADMISSIONS``), and overflow evicts the lowest-generation
        record, lapsing that owner's admission back open until a re-close mints a fresh
        generation. The returned ``close_generation`` is issued from the registry's one
        fencing sequence, so a teardown driver can re-verify the still-closed generation
        before emitting its completion receipt (and must re-close at pass start to hold
        the fence across a possible eviction).
        """

        owner = _bounded(owner_id, "owner_id")
        with self._locked():
            registry = cast(Registry, self._read_registry(create=True))
            existing = registry.closed_owner_admissions.get(owner)
            if existing is not None:
                return {"owner_id": owner, **existing.to_dict()}
            if len(registry.closed_owner_admissions) >= _MAX_CLOSED_OWNER_ADMISSIONS:
                oldest = min(
                    registry.closed_owner_admissions,
                    key=lambda key: registry.closed_owner_admissions[key].close_generation,
                )
                del registry.closed_owner_admissions[oldest]
            _wall, now_text, _monotonic, boot_id = self._now()
            close = OwnerAdmissionClose(
                closed_at=now_text,
                boot_id=_bounded(boot_id, "boot_id"),
                close_generation=registry.issue_sequence(),
            )
            registry.closed_owner_admissions[owner] = close
            self._write_registry(registry)
            return {"owner_id": owner, **close.to_dict()}

    def inspect_owner_admission(self, owner_id: str) -> dict[str, Any] | None:
        """Return the exact close record for ``owner_id``, or None while admission is open."""

        owner = _bounded(owner_id, "owner_id")
        with self._locked():
            registry = self._read_registry(create=False)
            if registry is None:
                return None
            close = registry.closed_owner_admissions.get(owner)
            return None if close is None else {"owner_id": owner, **close.to_dict()}

    def release_owner(
        self,
        owner_id: str,
        *,
        session_id: str,
    ) -> tuple[str, ...]:
        """Release one owner's session only after broker-recorded terminal evidence exists."""

        owner = _bounded(owner_id, "owner_id")
        session = _bounded(session_id, "session_id")
        with self._locked():
            registry = cast(Registry, self._read_registry(create=True))
            selected = sorted(
                (
                    lease
                    for lease in registry.leases.values()
                    if lease.owner_id == owner
                    and lease.batch_id is None
                    and lease.session_id == session
                ),
                key=lambda lease: lease.lease_id,
            )
            unsafe = [
                lease.lease_id
                for lease in selected
                if lease.agent_id is None or lease.child_terminal_at is None
            ]
            if unsafe:
                raise LeaseOwnershipError(
                    f"owner {owner!r} has non-terminal leases: {', '.join(unsafe)}"
                )
            self._require_no_retained_settlements(registry, selected, operation="owner release")
            selected_ids = tuple(lease.lease_id for lease in selected)
            for lease_id in selected_ids:
                del registry.leases[lease_id]
            if selected_ids:
                _wall, _now_text, monotonic, boot_id = self._now()
                if not self._session_has_live_agents(
                    registry, session, monotonic=monotonic, boot_id=boot_id
                ):
                    registry.session_admissions.pop(session, None)
                self._write_registry(registry)
            return selected_ids

    def renew_session(self, session_id: str) -> tuple[Lease, ...]:
        """Atomically renew every live agent lease owned by one runtime session."""

        session = _bounded(session_id, "session_id")
        with self._locked():
            registry = cast(Registry, self._read_registry(create=True))
            selected = sorted(
                (
                    lease
                    for lease in registry.leases.values()
                    if lease.pool == "agent" and lease.session_id == session
                ),
                key=lambda lease: lease.lease_id,
            )
            if not selected:
                raise LeaseNotFoundError(f"session {session!r} has no agent leases")
            _wall, now_text, monotonic, boot_id = self._now()
            for lease in selected:
                if self._expired(lease, monotonic=monotonic, boot_id=boot_id):
                    raise LeaseExpiredError(
                        f"session {session!r} contains expired lease {lease.lease_id!r}"
                    )
                if lease.resource_ref is not None:
                    state, _ = self._current_state(
                        registry,
                        lease.resource_ref,
                        lease.token,
                        monotonic=monotonic,
                        boot_id=boot_id,
                    )
                    if state != "current":
                        raise LeaseSupersededError(
                            f"session {session!r} contains non-current lease {lease.lease_id!r}"
                        )
            renewed = tuple(
                replace(
                    lease,
                    renewed_at=now_text,
                    renewed_monotonic_ns=monotonic,
                    boot_id=boot_id,
                )
                for lease in selected
            )
            for lease in renewed:
                registry.leases[lease.lease_id] = lease
            self._write_registry(registry)
            return renewed

    def release_session(self, session_id: str) -> tuple[str, ...]:
        """Release all agent leases for a terminal runtime session under one lock."""

        session = _bounded(session_id, "session_id")
        with self._locked():
            registry = cast(Registry, self._read_registry(create=True))
            selected = sorted(
                (
                    lease
                    for lease in registry.leases.values()
                    if lease.pool == "agent" and lease.session_id == session
                ),
                key=lambda lease: lease.lease_id,
            )
            self._require_no_retained_settlements(registry, selected, operation="session release")
            for lease in selected:
                del registry.leases[lease.lease_id]
            if selected:
                _wall, _now_text, monotonic, boot_id = self._now()
                if not self._session_has_live_agents(
                    registry, session, monotonic=monotonic, boot_id=boot_id
                ):
                    registry.session_admissions.pop(session, None)
                self._write_registry(registry)
            return tuple(lease.lease_id for lease in selected)

    def release_session_if_terminal(
        self, session_id: str, *, terminal_agent_ids: Sequence[str]
    ) -> tuple[str, ...]:
        """Validate coordinator terminal evidence and release a session in one lock transaction."""

        session = _bounded(session_id, "session_id")
        terminal = {_bounded(agent_id, "terminal_agent_id") for agent_id in terminal_agent_ids}
        with self._locked():
            registry = cast(Registry, self._read_registry(create=True))
            selected = sorted(
                (
                    lease
                    for lease in registry.leases.values()
                    if lease.pool == "agent" and lease.session_id == session
                ),
                key=lambda lease: lease.lease_id,
            )
            unsafe = [
                lease.lease_id
                for lease in selected
                if (
                    lease.agent_id is not None
                    and lease.child_terminal_at is None
                    and lease.agent_id not in terminal
                )
                or (lease.agent_id is None and lease.tool_use_id is not None)
            ]
            if unsafe:
                raise LeaseOwnershipError(
                    f"session {session!r} has non-terminal agent leases: {', '.join(unsafe)}"
                )
            self._require_no_retained_settlements(
                registry, selected, operation="terminal session release"
            )
            for lease in selected:
                del registry.leases[lease.lease_id]
            if selected or session in registry.session_admissions:
                registry.session_admissions.pop(session, None)
                self._write_registry(registry)
            return tuple(lease.lease_id for lease in selected)

    def settle_batch(self, batch_id: str, *, owner_id: str, session_id: str) -> tuple[str, ...]:
        """Release only unused or fully two-signal-terminal Workflow slots atomically."""

        batch = _bounded(batch_id, "batch_id")
        owner = _bounded(owner_id, "owner_id")
        session = _bounded(session_id, "session_id")
        with self._locked():
            registry = cast(Registry, self._read_registry(create=True))
            selected = [
                lease
                for lease in registry.leases.values()
                if lease.pool == "agent" and lease.batch_id == batch
            ]
            if not selected:
                return ()
            if any(lease.owner_id != owner or lease.session_id != session for lease in selected):
                raise LeaseOwnershipError("workflow batch is not owned by this session")
            self._require_no_retained_settlements(registry, selected, operation="batch settlement")
            released = sorted(
                lease.lease_id
                for lease in selected
                if (lease.agent_id is None and lease.tool_use_id is None)
                or (
                    lease.agent_id is not None
                    and lease.child_terminal_at is not None
                    and lease.parent_completed_at is not None
                )
            )
            for lease_id in released:
                del registry.leases[lease_id]
            if released:
                _wall, _now_text, monotonic, boot_id = self._now()
                if not self._session_has_live_agents(
                    registry, session, monotonic=monotonic, boot_id=boot_id
                ):
                    registry.session_admissions.pop(session, None)
                self._write_registry(registry)
            return tuple(released)

    def renew_batch(self, batch_id: str, *, owner_id: str | None = None) -> tuple[Lease, ...]:
        """Renew every live slot in one named Workflow batch under one lock."""

        batch = _bounded(batch_id, "batch_id")
        owner = None if owner_id is None else _bounded(owner_id, "owner_id")
        with self._locked():
            registry = cast(Registry, self._read_registry(create=True))
            selected = sorted(
                (lease for lease in registry.leases.values() if lease.batch_id == batch),
                key=lambda lease: lease.lease_id,
            )
            if not selected:
                raise LeaseNotFoundError(f"workflow batch {batch!r} has no leases")
            _wall, now_text, monotonic, boot_id = self._now()
            renewed: list[Lease] = []
            for lease in selected:
                if owner is not None and lease.owner_id != owner:
                    raise LeaseOwnershipError("workflow batch is not owned by this caller")
                if self._expired(lease, monotonic=monotonic, boot_id=boot_id):
                    raise LeaseExpiredError(
                        f"workflow batch {batch!r} contains expired lease {lease.lease_id!r}"
                    )
                updated = replace(
                    lease,
                    renewed_at=now_text,
                    renewed_monotonic_ns=monotonic,
                    boot_id=boot_id,
                )
                registry.leases[lease.lease_id] = updated
                renewed.append(updated)
            self._write_registry(registry)
            return tuple(renewed)

    def record_child_terminal(self, agent_id: str) -> bool:
        child = _bounded(agent_id, "agent_id")
        with self._locked():
            registry = cast(Registry, self._read_registry(create=True))
            matches = [lease for lease in registry.leases.values() if lease.agent_id == child]
            if not matches:
                return False
            if len(matches) != 1:
                raise RegistryCorruptError(f"multiple leases are bound to agent {child!r}")
            lease = matches[0]
            _wall, now_text, monotonic, boot_id = self._now()
            updated = replace(lease, child_terminal_at=lease.child_terminal_at or now_text)
            if updated.parent_completed_at is not None:
                self._complete_foreground_lease(
                    registry, updated, now_text=now_text, monotonic=monotonic, boot_id=boot_id
                )
            else:
                registry.leases[lease.lease_id] = updated
            if not self._session_has_live_agents(
                registry, lease.session_id, monotonic=monotonic, boot_id=boot_id
            ):
                registry.session_admissions.pop(lease.session_id, None)
            self._write_registry(registry)
            return True

    def record_parent_completed(self, session_id: str, tool_use_id: str) -> tuple[str, ...]:
        """Record a trusted parent result for exactly one runtime session and tool call."""

        session = _bounded(session_id, "session_id")
        tool = _bounded(tool_use_id, "tool_use_id")
        with self._locked():
            registry = cast(Registry, self._read_registry(create=True))
            matches = [
                lease
                for lease in registry.leases.values()
                if lease.session_id == session and lease.tool_use_id == tool
            ]
            if not matches:
                return ()
            _wall, now_text, monotonic, boot_id = self._now()
            removed: list[str] = []
            for lease in matches:
                updated = replace(lease, parent_completed_at=lease.parent_completed_at or now_text)
                if updated.agent_id is None or updated.child_terminal_at is not None:
                    self._complete_foreground_lease(
                        registry,
                        updated,
                        now_text=now_text,
                        monotonic=monotonic,
                        boot_id=boot_id,
                    )
                    removed.append(lease.lease_id)
                else:
                    registry.leases[lease.lease_id] = updated
                if not self._session_has_live_agents(
                    registry, lease.session_id, monotonic=monotonic, boot_id=boot_id
                ):
                    registry.session_admissions.pop(lease.session_id, None)
            self._write_registry(registry)
            return tuple(sorted(removed))

    def _complete_foreground_lease(
        self,
        registry: Registry,
        lease: Lease,
        *,
        now_text: str,
        monotonic: int,
        boot_id: str,
    ) -> None:
        """Remove a normal grant or recycle a driver-owned Workflow batch slot."""

        self._require_no_retained_settlements(registry, [lease], operation="foreground completion")

        if lease.batch_id is None:
            registry.leases.pop(lease.lease_id, None)
            return
        registry.leases[lease.lease_id] = replace(
            lease,
            agent_id=None,
            tool_use_id=None,
            agent_type="*",
            resource_ref=None,
            claimed_at=None,
            child_terminal_at=None,
            parent_completed_at=None,
            renewed_at=now_text,
            renewed_monotonic_ns=monotonic,
            boot_id=boot_id,
            ttl_seconds=DEFAULT_CLAIM_TTL_SECONDS,
        )

    def inspect(self) -> dict[str, Any]:
        """Return persisted authority plus derived state without creating any file."""

        if self._open_authority(create=False) is None:
            return {
                "exists": False,
                "root_sha256": self.root_sha256,
                "leases": [],
                "archived_resource_fences": {},
            }
        registry = self._read_registry(create=False)
        if registry is None:
            return {
                "exists": False,
                "root_sha256": self.root_sha256,
                "leases": [],
                "archived_resource_fences": {},
            }
        _wall, _now_text, monotonic, boot_id = self._now()
        leases = []
        for lease in sorted(registry.leases.values(), key=lambda item: item.lease_id):
            item = {"lease_id": lease.lease_id, **lease.to_dict()}
            item["derived_state"] = (
                "expired" if self._expired(lease, monotonic=monotonic, boot_id=boot_id) else "live"
            )
            leases.append(item)
        admissions: dict[str, Any] = {}
        for session, admission in sorted(registry.session_admissions.items()):
            item = admission.to_dict()
            live = self._session_has_live_agents(
                registry, session, monotonic=monotonic, boot_id=boot_id
            )
            item["derived_state"] = (
                "live"
                if live
                else (
                    "expired"
                    if self._admission_expired(admission, monotonic=monotonic, boot_id=boot_id)
                    else "armed"
                )
            )
            admissions[session] = item
        return {
            "exists": True,
            "root_sha256": self.root_sha256,
            "schema": SCHEMA,
            "broker_epoch": registry.broker_epoch,
            "next_fencing_sequence": registry.next_fencing_sequence,
            "leases": leases,
            "session_admissions": admissions,
            "resource_fences": {
                key: value.to_dict() for key, value in sorted(registry.resource_fences.items())
            },
            "archived_resource_fences": self._inspect_archived_fences(
                exclude=set(registry.resource_fences)
            ),
            "settlements": {
                key: value.to_dict() for key, value in sorted(registry.settlements.items())
            },
        }

    def inspect_resource_head(
        self, resource_ref: Mapping[str, Any], *, pool: Pool = "agent"
    ) -> dict[str, Any] | None:
        """Return one exact hot or archived resource head without the bounded projection."""

        resource = canonical_resource_ref(pool, resource_ref)
        digest = resource_sha256(resource)
        with self._locked():
            registry = self._read_registry(create=False)
            if registry is None:
                return None
            head = registry.resource_fences.get(digest) or self._read_archived_fence(digest)
            if head is None:
                return None
            if head.resource_ref != resource:
                raise RegistryCorruptError("resource head digest does not match its resource")
            return head.to_dict()

    def _owner_state(self, lease: Lease) -> Literal["dead", "live", "unknown"]:
        if lease.boot_id != _bounded(self.providers.boot_id(), "boot_id"):
            return "dead"
        if lease.owner_pid is None:
            return "unknown"
        if not self.providers.process_exists(lease.owner_pid):
            return "dead"
        current = self.providers.process_identity(lease.owner_pid)
        if current is None or lease.owner_process_start is None:
            return "unknown"
        return "live" if current == lease.owner_process_start else "dead"

    def sweep(
        self,
        *,
        worktree_reaper: Callable[[ResourceRef], bool] | None = None,
        terminal_lease_ids: Sequence[str] = (),
    ) -> SweepResult:
        """Release expired agents and reap provably-dead worktrees under the authority lock.

        ``worktree_reaper`` runs while this broker's global flock is held.  It must not call this
        broker (or another handle rooted at the same authority), acquire a competing lease, or wait
        for code that does.  That intentionally non-reentrant callback contract prevents a fresh
        acquisition or ownership transfer from racing destructive reclamation.
        """

        terminal = {_bounded(item, "terminal_lease_id") for item in terminal_lease_ids}
        retained: dict[str, str] = {}
        released_agents: list[str] = []
        reaped: list[str] = []
        with self._locked():
            registry = cast(Registry, self._read_registry(create=True))
            _wall, _now_text, monotonic, boot_id = self._now()
            purged_admissions = self._purge_orphan_admissions(
                registry, monotonic=monotonic, boot_id=boot_id
            )
            released_sessions: set[str] = set()
            for lease in list(registry.leases.values()):
                retained_settlement = next(
                    (
                        item
                        for item in registry.settlements.values()
                        if item.lease_id == lease.lease_id
                    ),
                    None,
                )
                if retained_settlement is not None:
                    retained[lease.lease_id] = f"settlement-{retained_settlement.phase}"
                    continue
                if not self._expired(lease, monotonic=monotonic, boot_id=boot_id):
                    continue
                if lease.pool == "agent":
                    del registry.leases[lease.lease_id]
                    released_agents.append(lease.lease_id)
                    released_sessions.add(lease.session_id)
                    continue
                owner_state = "dead" if lease.lease_id in terminal else self._owner_state(lease)
                if owner_state == "live":
                    retained[lease.lease_id] = "expired-live-owner"
                elif owner_state == "unknown":
                    retained[lease.lease_id] = "expired-owner-unknown"
                else:
                    if worktree_reaper is None:
                        retained[lease.lease_id] = "expired-no-reaper"
                    elif lease.resource_ref is None:
                        retained[lease.lease_id] = "expired-resource-missing"
                    else:
                        try:
                            successful = bool(worktree_reaper(lease.resource_ref))
                        except Exception:  # noqa: BLE001 - retain authority for an operator retry.
                            successful = False
                        if successful:
                            del registry.leases[lease.lease_id]
                            reaped.append(lease.lease_id)
                        else:
                            retained[lease.lease_id] = "reap-failed"
            if released_agents or reaped or purged_admissions:
                for session in released_sessions:
                    if not self._session_has_live_agents(
                        registry, session, monotonic=monotonic, boot_id=boot_id
                    ):
                        registry.session_admissions.pop(session, None)
                self._write_registry(registry)
        return SweepResult(
            released_agent_leases=tuple(sorted(released_agents)),
            reaped_worktree_leases=tuple(sorted(reaped)),
            retained=dict(sorted(retained.items())),
        )


_RECOVERY_COORDINATOR_CAPABILITY = object()


class SettlementRecoveryCoordinator:
    """Low-level, process-bound seam for retained settlement recovery experiments.

    Ordinary ``LeaseBroker`` handles intentionally have no recovery configuration or method. The
    owner-local plugin does not wire this seam into normal producer startup. Ambiguous authority is
    retained for inspection until #358 supplies lifecycle recovery. Tests may create a coordinator
    through the bounded module factory and register one exact handler per settlement.
    """

    def __init__(
        self,
        capability: object,
        broker: LeaseBroker,
        *,
        recovery_owner_id: str,
        recovery_handlers: Mapping[str, SettlementRecoveryHandler],
        recovery_capability: bytes,
    ) -> None:
        if capability is not _RECOVERY_COORDINATOR_CAPABILITY:
            raise LeaseOwnershipError("settlement recovery coordinator is root-adapter-owned")
        self._broker = broker
        self._owner_id = _bounded(recovery_owner_id, "recovery_owner_id", maximum=128)
        self._pid = os.getpid()
        self._process_start = broker.providers.process_identity(self._pid)
        if self._process_start is None:
            raise UnsafeAuthorityError("root recovery adapter requires a stable process identity")
        self._boot_id = _bounded(broker.providers.boot_id(), "recovery_owner_boot_id")
        self._effective_uid = os.geteuid()
        if len(recovery_capability) != 32:
            raise ValueError("recovery capability must contain 256 random bits")
        self._recovery_capability = recovery_capability
        self._recovery_capability_sha256 = hashlib.sha256(recovery_capability).hexdigest()
        handlers = dict(recovery_handlers)
        if len(handlers) > _MAX_SETTLEMENTS:
            raise ValueError("recovery handlers exceed the retained settlement bound")
        for settlement_id, handler in handlers.items():
            selected = _uuid_text(settlement_id, "recovery handler settlement_id")
            if selected != handler.settlement.settlement_id:
                raise ValueError("recovery handler key does not match its exact settlement")
        self._handlers = handlers
        # Establish and retain the exact authority directory identity before any child can run.
        broker._open_authority(create=True)
        with broker._locked():
            registry = cast(Registry, broker._read_registry(create=True))
            if registry.recovery_capability_sha256 is None:
                registry.recovery_capability_sha256 = self._recovery_capability_sha256
                broker._write_registry(registry)
            elif registry.recovery_capability_sha256 != self._recovery_capability_sha256:
                raise LeaseOwnershipError(
                    "authority is already bound to a different root recovery capability"
                )

    def register_recovery_handler(self, handler: SettlementRecoveryHandler) -> None:
        """Register one exact settlement after the root adapter observes its preparation."""

        if os.getpid() != self._pid:
            raise LeaseOwnershipError("recovery coordinator cannot be inherited by a child")
        settlement_id = handler.settlement.settlement_id
        if len(self._handlers) >= _MAX_SETTLEMENTS and settlement_id not in self._handlers:
            raise CapacityExhaustedError("recovery handler registry is full", earliest_expiry=None)
        if handler.settlement.recovery_capability_sha256 != self._recovery_capability_sha256:
            raise LeaseOwnershipError(
                "recovery handler settlement lacks this root capability binding"
            )
        existing = self._handlers.get(settlement_id)
        if existing is not None and existing != handler:
            raise LeaseOwnershipError("settlement already has a different recovery handler")
        self._handlers[settlement_id] = handler

    def _parse_intent(
        self, recovery_intent: Mapping[str, Any]
    ) -> tuple[dict[str, Any], ResourceRef, FencingToken]:
        parsed = _closed_mapping(
            dict(recovery_intent), _SETTLEMENT_RECOVERY_KEYS, "settlement recovery intent"
        )
        if parsed["schema"] != "settlement_recovery_intent.v1":
            raise LeaseBrokerError("recovery intent schema is invalid")
        supplied_sha = _sha256_text(parsed["sha256"], "recovery intent sha256")
        if supplied_sha != _record_sha256(parsed, "sha256"):
            raise LeaseBrokerError("recovery intent sha256 does not match its content")
        resource = canonical_resource_ref("agent", parsed["resource_ref"])
        token_raw = parsed["token"]
        if not isinstance(token_raw, Mapping) or set(token_raw) != {
            "broker_epoch",
            "fencing_sequence",
        }:
            raise LeaseBrokerError("recovery intent token shape is invalid")
        token = FencingToken.from_dict(token_raw)
        if parsed["generation"] != token_generation(token):
            raise LeaseBrokerError("recovery intent generation does not match token")
        return parsed, resource, token

    def _authorize_caller(self, parsed: Mapping[str, Any]) -> None:
        if os.getpid() != self._pid:
            raise LeaseOwnershipError("recovery coordinator cannot be inherited by a child")
        if (
            parsed["recovery_owner_id"] != self._owner_id
            or _positive(parsed["recovery_owner_pid"], "recovery_owner_pid") != self._pid
            or _bounded(parsed["recovery_owner_process_start"], "recovery_owner_process_start")
            != self._process_start
            or _bounded(parsed["recovery_owner_boot_id"], "recovery_owner_boot_id") != self._boot_id
            or _nonnegative(parsed["recovery_owner_effective_uid"], "recovery_owner_effective_uid")
            != self._effective_uid
            or self._broker.providers.process_identity(self._pid) != self._process_start
            or self._broker.providers.boot_id() != self._boot_id
        ):
            raise LeaseOwnershipError(
                "recovery caller identity does not match the retained root adapter"
            )

    @staticmethod
    def _intent_matches_settlement(
        parsed: Mapping[str, Any],
        resource: ResourceRef,
        token: FencingToken,
        settlement: SettlementRecord,
    ) -> bool:
        return (
            settlement.phase == parsed["expected_phase"]
            and settlement.resource_ref == resource
            and settlement.token == token
            and settlement.lease_id == parsed["lease_id"]
            and settlement.settlement_id == parsed["settlement_id"]
            and settlement.session_id == parsed["session_id"]
            and settlement.policy_sha256 == parsed["policy_sha256"]
            and settlement.protected_write_intent_sha256 == parsed["protected_write_intent_sha256"]
        )

    @staticmethod
    def _close_matches_intent(
        close: Mapping[str, Any],
        parsed: Mapping[str, Any],
        handler: SettlementRecoveryHandler | None,
    ) -> bool:
        if (
            close["resource_ref"] != parsed["resource_ref"]
            or close["token"] != parsed["token"]
            or close["lease_id"] != parsed["lease_id"]
            or close["settlement_id"] != parsed["settlement_id"]
            or close["session_id"] != parsed["session_id"]
            or close["policy_sha256"] != parsed["policy_sha256"]
            or close["protected_write_intent_sha256"] != parsed["protected_write_intent_sha256"]
        ):
            return False
        if handler is None:
            return False
        settlement = handler.settlement
        return bool(
            close["settlement_sha256"] == settlement.settlement_sha256
            and close["producer"] == settlement.producer
            and close["run_id"] == settlement.run_id
            and close["expected_output_sha256"] == settlement.expected_output_sha256
        )

    def recover_agent_settlement(
        self,
        recovery_intent: Mapping[str, Any],
        *,
        action: Literal["abort", "commit"],
    ) -> dict[str, Any] | None:
        """Recover or idempotently converge one exact retained settlement."""

        parsed, resource, token = self._parse_intent(recovery_intent)
        self._authorize_caller(parsed)
        expected_phase = parsed["expected_phase"]
        if expected_phase not in {"prepared", "committing", "ambiguous"}:
            raise LeaseBrokerError("recovery expected_phase is invalid")
        with self._broker._locked():
            registry = cast(Registry, self._broker._read_registry(create=True))
            proven_capability_sha256 = hashlib.sha256(self._recovery_capability).hexdigest()
            if (
                proven_capability_sha256 != self._recovery_capability_sha256
                or registry.recovery_capability_sha256 != proven_capability_sha256
            ):
                raise LeaseOwnershipError("recovery capability no longer matches authority")
            digest = resource_sha256(resource)
            settlement = registry.settlements.get(digest)
            handler = self._handlers.get(parsed["settlement_id"])
            if settlement is None:
                head = registry.resource_fences.get(digest) or self._broker._read_archived_fence(
                    digest
                )
                if (
                    head is None
                    or head.resource_ref != resource
                    or head.broker_epoch != token.broker_epoch
                    or head.fencing_sequence != token.fencing_sequence
                    or head.lease_id != parsed["lease_id"]
                ):
                    raise LeaseNotFoundError(
                        f"settlement {parsed['settlement_id']!r} does not exist"
                    )
                if action == "abort" and head.close_receipt is None:
                    return None
                if action == "commit" and head.close_receipt is not None:
                    close = validate_settlement_close(head.close_receipt)
                    if self._close_matches_intent(close, parsed, handler):
                        return close
                raise LeaseOwnershipError(
                    "recovery retry does not match the canonical settlement disposition"
                )
            if not self._intent_matches_settlement(parsed, resource, token, settlement):
                raise LeaseOwnershipError("recovery intent does not match retained authority")
            if settlement.recovery_capability_sha256 != self._recovery_capability_sha256:
                raise LeaseOwnershipError(
                    "settlement is not bound to this root recovery capability"
                )
            lease = registry.leases.get(settlement.lease_id)
            if lease is None or self._broker._owner_state(lease) != "dead":
                raise LeaseOwnershipError("recovery requires a provably dead original owner")
            if action == "abort":
                if settlement.phase != "prepared":
                    raise LeaseOwnershipError("committing or ambiguous authority cannot be aborted")
                registry.settlements.pop(digest, None)
                registry.leases.pop(settlement.lease_id, None)
                self._broker._write_registry(registry)
                return None
            if action != "commit":
                raise LeaseBrokerError("recovery action is invalid")
            if handler is None or (
                handler.settlement.settlement_sha256 != settlement.settlement_sha256
            ):
                raise LeaseOwnershipError(
                    "recovery handler does not match the full retained settlement"
                )
            return self._broker._commit_settlement_locked(
                registry,
                settlement,
                write=None,
                replay_handler=handler,
                allow_retained_replay=True,
            )


def _open_settlement_recovery_coordinator(
    broker: LeaseBroker,
    *,
    recovery_owner_id: str,
    recovery_handlers: Mapping[str, SettlementRecoveryHandler] | None = None,
) -> SettlementRecoveryCoordinator:
    """Bounded production seam reserved for the non-child root adapter."""

    return SettlementRecoveryCoordinator(
        _RECOVERY_COORDINATOR_CAPABILITY,
        broker,
        recovery_owner_id=recovery_owner_id,
        recovery_handlers={} if recovery_handlers is None else recovery_handlers,
        recovery_capability=os.urandom(32),
    )
