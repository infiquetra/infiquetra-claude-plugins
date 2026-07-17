#!/usr/bin/env python3
"""Lease-backed fleet admission and fencing authority.

The registry is a small, closed JSON document. Every mutation holds a stable sibling ``flock``
across read, validation, decision, and atomic replacement. Expiry is always derived from the
same-boot monotonic renewal timestamp; no mutable status or expiry bit is stored.
"""

from __future__ import annotations

import contextlib
import fcntl
import hashlib
import json
import os
import stat
import subprocess
import threading
import time
import uuid
from collections.abc import Callable, Iterator, Mapping, Sequence
from dataclasses import dataclass, replace
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any, Literal, cast

SCHEMA = "fleet_lease_registry.v1"
PROTOCOL_VERSION = 1
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
ResourceRef = dict[str, str]

_TOP_KEYS = frozenset(
    {
        "schema",
        "broker_epoch",
        "next_fencing_sequence",
        "resource_fences",
        "leases",
        "session_admissions",
    }
)
_FENCE_KEYS = frozenset({"resource_ref", "broker_epoch", "fencing_sequence", "lease_id"})
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
_MAX_ID = 256
_MAX_PATH = 4096
_MAX_SESSION_ADMISSIONS = 64
_MAX_CLOSED_FENCES = 128
_MAX_COLD_CLOSED_FENCES = 128
_MAX_CLOSED_FENCE_DISPOSITION_BYTES = 1024 * 1024
_MAX_CLOSED_FENCE_FILE_BYTES = 16 * 1024


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


def _closed_fence_bytes(fence: ResourceFence) -> bytes:
    return (json.dumps(fence.to_dict(), indent=2, sort_keys=True) + "\n").encode("utf-8")


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
    # Stable for one process and fail-safe across a restart: a changed value only expires authority.
    return f"process:{os.getpid()}:{time.monotonic_ns()}"


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
        return None
    value = result.stdout.strip()
    return value or None


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
class ResourceFence:
    resource_ref: ResourceRef
    broker_epoch: str
    fencing_sequence: int
    lease_id: str

    @classmethod
    def from_dict(cls, digest: str, data: Mapping[str, Any]) -> ResourceFence:
        _sha256_text(digest, "resource_fences key")
        parsed = _closed_mapping(dict(data), _FENCE_KEYS, f"resource_fences.{digest}")
        resource_raw = parsed["resource_ref"]
        if not isinstance(resource_raw, dict):
            raise RegistryCorruptError("resource fence resource_ref must be an object")
        # Shape identifies its pool; both are closed and cannot overlap.
        pool: Pool = "worktree" if set(resource_raw) == _WORKTREE_RESOURCE_KEYS else "agent"
        resource = canonical_resource_ref(pool, resource_raw)
        if resource_sha256(resource) != digest:
            raise RegistryCorruptError("resource fence digest does not match resource_ref")
        return cls(
            resource_ref=resource,
            broker_epoch=_uuid_text(parsed["broker_epoch"], "fence.broker_epoch"),
            fencing_sequence=_positive(parsed["fencing_sequence"], "fence.fencing_sequence"),
            lease_id=_bounded(parsed["lease_id"], "fence.lease_id"),
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "resource_ref": self.resource_ref,
            "broker_epoch": self.broker_epoch,
            "fencing_sequence": self.fencing_sequence,
            "lease_id": self.lease_id,
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


@dataclass
class Registry:
    broker_epoch: str
    next_fencing_sequence: int
    resource_fences: dict[str, ResourceFence]
    leases: dict[str, Lease]
    session_admissions: dict[str, SessionAdmission]

    @classmethod
    def fresh(cls, providers: Providers) -> Registry:
        return cls(str(providers.uuid4()), 1, {}, {}, {})

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> Registry:
        raw = dict(data)
        legacy_keys = _TOP_KEYS - {"session_admissions"}
        if set(raw) == legacy_keys and raw.get("schema") == SCHEMA:
            # ``session_admissions`` was added to the v1 registry as bounded coordination metadata.
            # Older v1 authorities have no such pins, so the only safe migration is the exact old
            # closed shape to an empty map.  Unknown or any other missing fields still fail closed.
            raw["session_admissions"] = {}
        parsed = _closed_mapping(raw, _TOP_KEYS, "registry")
        if parsed["schema"] != SCHEMA:
            raise RegistryCorruptError(
                f"registry.schema must be {SCHEMA!r}; found {parsed['schema']!r}"
            )
        epoch = _uuid_text(parsed["broker_epoch"], "broker_epoch")
        next_sequence = _positive(parsed["next_fencing_sequence"], "next_fencing_sequence")
        fences_raw = parsed["resource_fences"]
        leases_raw = parsed["leases"]
        admissions_raw = parsed["session_admissions"]
        if not isinstance(fences_raw, dict) or not isinstance(leases_raw, dict):
            raise RegistryCorruptError("resource_fences and leases must be objects")
        if not isinstance(admissions_raw, dict):
            raise RegistryCorruptError("session_admissions must be an object")
        if len(admissions_raw) > _MAX_SESSION_ADMISSIONS:
            raise RegistryCorruptError("session_admissions exceeds its bounded capacity")
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
        sequences = [lease.fencing_sequence for lease in leases.values()]
        sequences.extend(fence.fencing_sequence for fence in fences.values())
        if any(fence.broker_epoch != epoch for fence in fences.values()):
            raise RegistryCorruptError("resource fence broker_epoch must match registry epoch")
        if sequences and next_sequence <= max(sequences):
            raise RegistryCorruptError("next_fencing_sequence must exceed every issued sequence")
        return cls(epoch, next_sequence, fences, leases, admissions)

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema": SCHEMA,
            "broker_epoch": self.broker_epoch,
            "next_fencing_sequence": self.next_fencing_sequence,
            "resource_fences": {
                key: value.to_dict() for key, value in sorted(self.resource_fences.items())
            },
            "leases": {key: value.to_dict() for key, value in sorted(self.leases.items())},
            "session_admissions": {
                key: value.to_dict() for key, value in sorted(self.session_admissions.items())
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

    @staticmethod
    def _fsync_directory(path: Path) -> None:
        fd = os.open(path, os.O_RDONLY)
        try:
            os.fsync(fd)
        finally:
            os.close(fd)

    @contextlib.contextmanager
    def _locked(self) -> Iterator[None]:
        self._ensure_root()
        existed = self.lock_path.exists() or self.lock_path.is_symlink()
        if existed:
            self._validate_node(self.lock_path, mode=0o600, kind="lock")
        flags = os.O_CREAT | os.O_RDWR | _NOFOLLOW
        try:
            fd = os.open(self.lock_path, flags, 0o600)
        except OSError as exc:
            raise UnsafeAuthorityError(f"cannot open fleet lease lock safely: {exc}") from exc
        try:
            os.fchmod(fd, 0o600)
            opened = os.fstat(fd)
            if not stat.S_ISREG(opened.st_mode) or opened.st_uid != os.geteuid():
                raise UnsafeAuthorityError("fleet lease lock changed identity while opening")
            if not existed:
                self._fsync_directory(self.root)
            fcntl.flock(fd, fcntl.LOCK_EX)
            try:
                yield
            finally:
                fcntl.flock(fd, fcntl.LOCK_UN)
        finally:
            os.close(fd)

    def _read_registry(self, *, create: bool) -> Registry | None:
        try:
            self._validate_node(self.registry_path, mode=0o600, kind="registry")
        except FileNotFoundError:
            return Registry.fresh(self.providers) if create else None
        try:
            fd = os.open(self.registry_path, os.O_RDONLY | _NOFOLLOW)
        except OSError as exc:
            raise UnsafeAuthorityError(f"cannot open fleet lease registry safely: {exc}") from exc
        try:
            opened = os.fstat(fd)
            if not stat.S_ISREG(opened.st_mode) or opened.st_uid != os.geteuid():
                raise UnsafeAuthorityError("fleet lease registry changed identity while opening")
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
        # Validate the complete authority before archive sidecars are changed.
        Registry.from_dict(registry.to_dict())
        self._compact_closed_fences(registry)
        # Round-trip validation before authority replacement catches programmer errors fail-closed.
        payload = registry.to_dict()
        Registry.from_dict(payload)
        if self.registry_path.exists() or self.registry_path.is_symlink():
            self._validate_node(self.registry_path, mode=0o600, kind="registry")
        temp = self.root / (
            f".{REGISTRY_NAME}.{os.getpid()}.{threading.get_ident()}."
            f"{self.providers.monotonic_ns()}.tmp"
        )
        flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL | _NOFOLLOW
        encoded = (json.dumps(payload, indent=2, sort_keys=True) + "\n").encode("utf-8")
        try:
            fd = os.open(temp, flags, 0o600)
            try:
                os.fchmod(fd, 0o600)
                remaining = memoryview(encoded)
                while remaining:
                    written = os.write(fd, remaining)
                    remaining = remaining[written:]
                os.fsync(fd)
            finally:
                os.close(fd)
            os.replace(temp, self.registry_path)
            self._fsync_directory(self.root)
        finally:
            with contextlib.suppress(FileNotFoundError):
                temp.unlink()

    def _ensure_closed_fences_dir(self) -> None:
        path = self.closed_fences_dir
        if path.exists() or path.is_symlink():
            self._validate_node(path, mode=0o700, kind="root")
            return
        try:
            path.mkdir(mode=0o700, exist_ok=False)
            os.chmod(path, 0o700, follow_symlinks=False)
        except FileExistsError:
            pass
        self._validate_node(path, mode=0o700, kind="root")
        self._fsync_directory(self.root)

    def _archived_fence_path(self, digest: str) -> Path:
        _sha256_text(digest, "closed fence digest")
        return self.closed_fences_dir / f"{digest}.json"

    def _archive_closed_fence(self, digest: str, fence: ResourceFence) -> None:
        """Move one exact closed head out of the hot registry without losing disposition history."""

        if resource_sha256(fence.resource_ref) != digest:
            raise RegistryCorruptError("closed fence digest does not match its resource")
        self._ensure_closed_fences_dir()
        destination = self._archived_fence_path(digest)
        if destination.exists() or destination.is_symlink():
            self._validate_node(destination, mode=0o600, kind="closed fence")
        temp = self.closed_fences_dir / (
            f".{digest}.{os.getpid()}.{threading.get_ident()}.{self.providers.monotonic_ns()}.tmp"
        )
        encoded = _closed_fence_bytes(fence)
        if len(encoded) > _MAX_CLOSED_FENCE_FILE_BYTES:
            raise RegistryCorruptError("closed fence exceeds the per-record byte limit")
        try:
            fd = os.open(temp, os.O_WRONLY | os.O_CREAT | os.O_EXCL | _NOFOLLOW, 0o600)
            try:
                os.fchmod(fd, 0o600)
                remaining = memoryview(encoded)
                while remaining:
                    remaining = remaining[os.write(fd, remaining) :]
                os.fsync(fd)
            finally:
                os.close(fd)
            os.replace(temp, destination)
            self._fsync_directory(self.closed_fences_dir)
        finally:
            with contextlib.suppress(FileNotFoundError):
                temp.unlink()

    def _read_archived_fence(self, digest: str) -> ResourceFence | None:
        path = self._archived_fence_path(digest)
        try:
            self._validate_node(self.closed_fences_dir, mode=0o700, kind="root")
            self._validate_node(path, mode=0o600, kind="closed fence")
        except FileNotFoundError:
            return None
        try:
            fd = os.open(path, os.O_RDONLY | _NOFOLLOW)
        except OSError as exc:
            raise UnsafeAuthorityError(f"cannot open closed fence safely: {exc}") from exc
        try:
            opened = os.fstat(fd)
            if (
                not stat.S_ISREG(opened.st_mode)
                or opened.st_uid != os.geteuid()
                or stat.S_IMODE(opened.st_mode) != 0o600
            ):
                raise UnsafeAuthorityError("closed fence changed identity while opening")
            if opened.st_size > _MAX_CLOSED_FENCE_FILE_BYTES:
                raise RegistryCorruptError("closed fence exceeds the per-record byte limit")
            payload = json.loads(os.read(fd, _MAX_CLOSED_FENCE_FILE_BYTES + 1).decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise RegistryCorruptError(f"closed fence is not valid UTF-8 JSON: {exc}") from exc
        finally:
            os.close(fd)
        if not isinstance(payload, dict):
            raise RegistryCorruptError("closed fence must contain an object")
        return ResourceFence.from_dict(digest, payload)

    def _archived_fences(self) -> dict[str, ResourceFence]:
        """Return every cold disposition after validating the closed authority directory."""

        if not self.closed_fences_dir.exists() and not self.closed_fences_dir.is_symlink():
            return {}
        self._validate_node(self.closed_fences_dir, mode=0o700, kind="root")
        archived: dict[str, ResourceFence] = {}
        for path in sorted(self.closed_fences_dir.iterdir(), key=lambda item: item.name):
            if path.suffix != ".json":
                raise UnsafeAuthorityError(
                    f"closed fence directory contains unsupported entry {path.name!r}"
                )
            digest = path.stem
            _sha256_text(digest, "closed fence digest")
            fence = self._read_archived_fence(digest)
            if fence is None:
                raise RegistryCorruptError(f"closed fence {digest!r} disappeared during validation")
            if resource_sha256(fence.resource_ref) != digest:
                raise RegistryCorruptError("closed fence filename does not match its resource")
            archived[digest] = fence
        return archived

    def _remove_archived_fence(self, digest: str) -> None:
        path = self._archived_fence_path(digest)
        self._validate_node(path, mode=0o600, kind="closed fence")
        path.unlink()

    def _compact_closed_fences(self, registry: Registry) -> None:
        """Bound hot and cold closed dispositions, retaining the newest exact history."""

        archived = self._archived_fences()
        current_closed = {
            digest: fence
            for digest, fence in registry.resource_fences.items()
            if fence.lease_id not in registry.leases
        }
        # A current resource head supersedes any older cold record with the same digest.
        candidates = {
            digest: fence
            for digest, fence in archived.items()
            if digest not in registry.resource_fences
        }
        candidates.update(current_closed)
        newest = sorted(
            candidates.items(),
            key=lambda item: item[1].fencing_sequence,
            reverse=True,
        )
        max_total = _MAX_CLOSED_FENCES + _MAX_COLD_CLOSED_FENCES
        retained: list[tuple[str, ResourceFence]] = []
        retained_bytes = 0
        for digest, fence in newest:
            encoded_size = len(_closed_fence_bytes(fence))
            if encoded_size > _MAX_CLOSED_FENCE_FILE_BYTES:
                raise RegistryCorruptError("closed fence exceeds the per-record byte limit")
            if len(retained) >= max_total:
                break
            if retained_bytes + encoded_size > _MAX_CLOSED_FENCE_DISPOSITION_BYTES:
                break
            retained.append((digest, fence))
            retained_bytes += encoded_size

        retained_map = dict(retained)
        desired_hot = {
            digest
            for digest, _fence in sorted(
                (item for item in current_closed.items() if item[0] in retained_map),
                key=lambda item: item[1].fencing_sequence,
                reverse=True,
            )[:_MAX_CLOSED_FENCES]
        }
        cold_candidates = [item for item in retained if item[0] not in desired_hot]
        desired_cold = dict(cold_candidates[:_MAX_COLD_CLOSED_FENCES])

        removed_archive = False
        for digest in archived:
            if digest not in desired_cold:
                self._remove_archived_fence(digest)
                removed_archive = True
        if removed_archive:
            self._fsync_directory(self.closed_fences_dir)
        # Evict before archiving newly cold heads so even a process crash never exceeds the cap.
        for digest, fence in desired_cold.items():
            if archived.get(digest) != fence:
                self._archive_closed_fence(digest, fence)
        for digest in tuple(current_closed):
            if digest not in desired_hot:
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
        return [
            lease
            for lease in registry.leases.values()
            if not self._expired(lease, monotonic=monotonic, boot_id=boot_id)
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
        return any(
            lease.pool == "agent"
            and lease.session_id == session_id
            and not LeaseBroker._expired_static(lease, monotonic=monotonic, boot_id=boot_id)
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
        prior = registry.resource_fences.get(digest)
        if prior is not None and prior.lease_id != lease.lease_id:
            registry.leases.pop(prior.lease_id, None)
        registry.resource_fences[digest] = ResourceFence(
            resource_ref=lease.resource_ref,
            broker_epoch=registry.broker_epoch,
            fencing_sequence=lease.fencing_sequence,
            lease_id=lease.lease_id,
        )

    @staticmethod
    def _drop_superseded_resource_lease(
        registry: Registry, resource_ref: Mapping[str, Any]
    ) -> None:
        """Remove prior authority before applying capacity to an atomic retry grant."""

        prior = registry.resource_fences.get(resource_sha256(resource_ref))
        if prior is not None:
            registry.leases.pop(prior.lease_id, None)

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
                return "closed", None
            return "superseded", None
        if (
            token.broker_epoch != registry.broker_epoch
            or token.broker_epoch != head.broker_epoch
            or token.fencing_sequence != head.fencing_sequence
        ):
            return "superseded", None
        lease = registry.leases.get(head.lease_id)
        if lease is None:
            return "closed", None
        if (
            lease.resource_ref != dict(resource_ref)
            or lease.fencing_sequence != head.fencing_sequence
        ):
            return "closed", None
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
            del registry.leases[selected_id]
            if lease.pool == "agent":
                _wall, _now_text, monotonic, boot_id = self._now()
                if not self._session_has_live_agents(
                    registry, lease.session_id, monotonic=monotonic, boot_id=boot_id
                ):
                    registry.session_admissions.pop(lease.session_id, None)
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
        """Fence post-run durable writes and exact lease release under one broker lock.

        The guarded code must not mutate this broker or another handle at the same authority root.
        It may write the external result ledger: competing retries cannot supersede the token until
        those writes finish and this context atomically removes the lease.
        """

        selected_id = _bounded(lease_id, "lease_id")
        owner = _bounded(owner_id, "owner_id")
        primary_error: BaseException | None = None
        with self._locked():
            registry = cast(Registry, self._read_registry(create=True))
            lease = registry.leases.get(selected_id)
            if lease is None or lease.pool != "agent" or lease.resource_ref is None:
                raise LeaseNotFoundError(f"agent lease {selected_id!r} does not exist")
            if lease.owner_id != owner or lease.token != token:
                raise LeaseOwnershipError("agent settlement owner or token does not match")
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
            settled = replace(
                lease,
                renewed_at=now_text,
                renewed_monotonic_ns=monotonic,
                boot_id=boot_id,
            )
            registry.leases[selected_id] = settled
            # Persist the renewed settlement window before an external result write. A process
            # crash in the guarded body must not expose the stale pre-run deadline to a retry.
            self._write_registry(registry)
            try:
                yield settled
            except BaseException as exc:
                primary_error = exc
                raise
            finally:
                registry.leases.pop(selected_id, None)
                _wall, _now_text, final_monotonic, final_boot_id = self._now()
                if not self._session_has_live_agents(
                    registry,
                    lease.session_id,
                    monotonic=final_monotonic,
                    boot_id=final_boot_id,
                ):
                    registry.session_admissions.pop(lease.session_id, None)
                try:
                    self._write_registry(registry)
                except Exception as cleanup_exc:
                    if primary_error is not None:
                        primary_error.add_note(
                            f"secondary agent settlement cleanup failure: {cleanup_exc}"
                        )
                    else:
                        raise

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
                lease_id
                for lease_id, lease in registry.leases.items()
                if lease.pool == "agent" and lease.session_id == session
            )
            for lease_id in selected:
                del registry.leases[lease_id]
            if selected:
                _wall, _now_text, monotonic, boot_id = self._now()
                if not self._session_has_live_agents(
                    registry, session, monotonic=monotonic, boot_id=boot_id
                ):
                    registry.session_admissions.pop(session, None)
                self._write_registry(registry)
            return tuple(selected)

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

        if not self.root.exists() and not self.root.is_symlink():
            return {"exists": False, "root_sha256": self.root_sha256, "leases": []}
        self._validate_node(self.root, mode=0o700, kind="root")
        registry = self._read_registry(create=False)
        if registry is None:
            return {"exists": False, "root_sha256": self.root_sha256, "leases": []}
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
        archived = self._archived_fences()
        hot_closed = {
            digest: fence
            for digest, fence in registry.resource_fences.items()
            if fence.lease_id not in registry.leases
        }
        archive_bytes = sum(len(_closed_fence_bytes(fence)) for fence in archived.values())
        disposition_bytes = archive_bytes + sum(
            len(_closed_fence_bytes(fence)) for fence in hot_closed.values()
        )
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
            "closed_fence_retention": {
                "hot_records": len(hot_closed),
                "archive_files": len(archived),
                "archive_bytes": archive_bytes,
                "disposition_bytes": disposition_bytes,
                "max_hot_records": _MAX_CLOSED_FENCES,
                "max_archive_files": _MAX_COLD_CLOSED_FENCES,
                "max_disposition_bytes": _MAX_CLOSED_FENCE_DISPOSITION_BYTES,
            },
        }

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
