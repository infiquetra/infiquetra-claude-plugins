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
STATE_ENV = "INFIQUETRA_FLEET_STATE_DIR"
XDG_STATE_ENV = "XDG_STATE_HOME"
REGISTRY_NAME = "registry.json"
LOCK_NAME = "registry.lock"
DEFAULT_TTL_SECONDS = 300
DEFAULT_WORKTREE_LIMIT = 4
DEFAULT_CLAIM_TTL_SECONDS = 30

Pool = Literal["agent", "worktree"]
MutationMode = Literal["read-write", "none"]
TokenState = Literal["current", "expired", "closed", "superseded"]
ResourceRef = dict[str, str]

_TOP_KEYS = frozenset(
    {"schema", "broker_epoch", "next_fencing_sequence", "resource_fences", "leases"}
)
_FENCE_KEYS = frozenset(
    {"resource_ref", "broker_epoch", "fencing_sequence", "lease_id"}
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
    return value


def _optional_bounded(value: Any, name: str, *, maximum: int = _MAX_ID) -> str | None:
    if value is None:
        return None
    return _bounded(value, name, maximum=maximum)


def _positive(value: Any, name: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value < 1:
        raise RegistryCorruptError(f"{name} must be a positive integer")
    return value


def _nonnegative(value: Any, name: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        raise RegistryCorruptError(f"{name} must be a nonnegative integer")
    return value


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
            result["worktree_root"] = _safe_absolute_path(
                data["worktree_root"], "worktree_root"
            )
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
        return _safe_configured_root(env[XDG_STATE_ENV], XDG_STATE_ENV) / "infiquetra" / "fleet-leases"
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
            fencing_sequence=_positive(
                data.get("fencing_sequence"), "token.fencing_sequence"
            ),
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
            parent_completed_at=_optional_utc(
                parsed["parent_completed_at"], "parent_completed_at"
            ),
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


@dataclass
class Registry:
    broker_epoch: str
    next_fencing_sequence: int
    resource_fences: dict[str, ResourceFence]
    leases: dict[str, Lease]

    @classmethod
    def fresh(cls, providers: Providers) -> Registry:
        return cls(str(providers.uuid4()), 1, {}, {})

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> Registry:
        parsed = _closed_mapping(dict(data), _TOP_KEYS, "registry")
        if parsed["schema"] != SCHEMA:
            raise RegistryCorruptError(
                f"registry.schema must be {SCHEMA!r}; found {parsed['schema']!r}"
            )
        epoch = _uuid_text(parsed["broker_epoch"], "broker_epoch")
        next_sequence = _positive(parsed["next_fencing_sequence"], "next_fencing_sequence")
        fences_raw = parsed["resource_fences"]
        leases_raw = parsed["leases"]
        if not isinstance(fences_raw, dict) or not isinstance(leases_raw, dict):
            raise RegistryCorruptError("resource_fences and leases must be objects")
        fences = {
            digest: ResourceFence.from_dict(digest, fence)
            for digest, fence in fences_raw.items()
        }
        leases = {
            lease_id: Lease.from_dict(lease_id, lease, epoch)
            for lease_id, lease in leases_raw.items()
        }
        sequences = [lease.fencing_sequence for lease in leases.values()]
        sequences.extend(fence.fencing_sequence for fence in fences.values())
        if any(fence.broker_epoch != epoch for fence in fences.values()):
            raise RegistryCorruptError("resource fence broker_epoch must match registry epoch")
        if sequences and next_sequence <= max(sequences):
            raise RegistryCorruptError("next_fencing_sequence must exceed every issued sequence")
        return cls(epoch, next_sequence, fences, leases)

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema": SCHEMA,
            "broker_epoch": self.broker_epoch,
            "next_fencing_sequence": self.next_fencing_sequence,
            "resource_fences": {
                key: value.to_dict() for key, value in sorted(self.resource_fences.items())
            },
            "leases": {key: value.to_dict() for key, value in sorted(self.leases.items())},
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
            raise RegistryCorruptError(f"fleet lease registry is not valid UTF-8 JSON: {exc}") from exc
        if not isinstance(payload, dict):
            raise RegistryCorruptError("fleet lease registry must contain an object")
        return Registry.from_dict(payload)

    def _write_registry(self, registry: Registry) -> None:
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
        count: int,
        wall: datetime,
        monotonic: int,
        boot_id: str,
    ) -> None:
        live = [
            lease
            for lease in self._live(registry, monotonic=monotonic, boot_id=boot_id)
            if lease.pool == "agent"
        ]
        same_session = [lease for lease in live if lease.session_id == session_id]
        digests = {lease.policy_sha256 for lease in same_session}
        if digests and digests != {policy_sha256}:
            raise PolicyMismatchError(
                f"session {session_id!r} already has live leases under a different policy digest"
            )
        if len(same_session) + count > session_limit:
            raise CapacityExhaustedError(
                f"session {session_id!r} would exceed session_limit={session_limit}",
                earliest_expiry=self._earliest_expiry(
                    same_session, wall=wall, monotonic=monotonic, boot_id=boot_id
                ),
            )
        live_limits = [
            cast(int, lease.aggregate_limit)
            for lease in live
            if lease.aggregate_limit is not None
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
        if pid is not None and process_start is None:
            process_start = self.providers.process_identity(pid)
        with self._locked():
            registry = cast(Registry, self._read_registry(create=True))
            wall, now_text, monotonic, boot_id = self._now()
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
            self._admit_agent(
                registry,
                session_id=session,
                policy_sha256=digest,
                session_limit=session_cap,
                aggregate_limit=aggregate_cap,
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
        resource = (
            None if resource_ref is None else canonical_resource_ref("agent", resource_ref)
        )
        canonical_worktree = (
            None
            if worktree_root is None
            else _safe_absolute_path(str(worktree_root), "worktree_root")
        )
        ttl = _positive(execution_ttl_seconds, "execution_ttl_seconds")
        with self._locked():
            registry = cast(Registry, self._read_registry(create=True))
            _wall, now_text, monotonic, boot_id = self._now()
            bound = [
                lease
                for lease in registry.leases.values()
                if lease.pool == "agent"
                and lease.session_id == session
                and lease.agent_type == kind
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
                and lease.agent_type == kind
                and lease.batch_id == batch
                and lease.agent_id is None
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
            self._drop_superseded_resource_lease(registry, resource)
            self._admit_worktree(
                registry, count=1, monotonic=monotonic, boot_id=boot_id, wall=wall
            )
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

    def _current_state(
        self,
        registry: Registry,
        resource_ref: Mapping[str, Any],
        token: FencingToken,
        *,
        monotonic: int,
        boot_id: str,
    ) -> tuple[TokenState, Lease | None]:
        head = registry.resource_fences.get(resource_sha256(resource_ref))
        if (
            head is None
            or token.broker_epoch != registry.broker_epoch
            or token.broker_epoch != head.broker_epoch
            or token.fencing_sequence != head.fencing_sequence
        ):
            return "superseded", None
        lease = registry.leases.get(head.lease_id)
        if lease is None:
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
        return self._current_state(
            registry, resource, token, monotonic=monotonic, boot_id=boot_id
        )[0]

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
        assert lease is not None
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
        worktree_raw = None if lease.resource_ref is None else lease.resource_ref.get("worktree_root")
        if worktree_raw is None:
            return lease
        worktree = Path(worktree_raw)
        if not worktree.is_dir():
            raise MissingResourceError(f"leased worktree is missing: {worktree}")
        if target is not None:
            candidate = Path(target)
            if not candidate.is_absolute():
                candidate = worktree / candidate
            normalized = Path(os.path.abspath(candidate))
            try:
                normalized.relative_to(worktree)
            except ValueError as exc:
                raise MissingResourceError(
                    f"write target {normalized} is outside leased worktree {worktree}"
                ) from exc
        return lease

    def renew(
        self,
        lease_id: str,
        *,
        owner_id: str | None = None,
        token: FencingToken | None = None,
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
            if token is not None and token != lease.token:
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
        owner_id: str | None = None,
        token: FencingToken | None = None,
    ) -> bool:
        selected_id = _bounded(lease_id, "lease_id")
        with self._locked():
            registry = cast(Registry, self._read_registry(create=True))
            lease = registry.leases.get(selected_id)
            if lease is None:
                return False
            if owner_id is not None and lease.owner_id != _bounded(owner_id, "owner_id"):
                raise LeaseOwnershipError("lease is not owned by this caller")
            if token is not None and token != lease.token:
                raise LeaseOwnershipError("release token does not match lease")
            del registry.leases[selected_id]
            self._write_registry(registry)
            return True

    def release_owner(self, owner_id: str, *, session_id: str | None = None) -> tuple[str, ...]:
        owner = _bounded(owner_id, "owner_id")
        session = None if session_id is None else _bounded(session_id, "session_id")
        with self._locked():
            registry = cast(Registry, self._read_registry(create=True))
            selected = sorted(
                lease_id
                for lease_id, lease in registry.leases.items()
                if lease.owner_id == owner and (session is None or lease.session_id == session)
            )
            for lease_id in selected:
                del registry.leases[lease_id]
            if selected:
                self._write_registry(registry)
            return tuple(selected)

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
            _wall, now_text, _monotonic, _boot_id = self._now()
            updated = replace(lease, child_terminal_at=lease.child_terminal_at or now_text)
            if updated.parent_completed_at is not None:
                del registry.leases[lease.lease_id]
            else:
                registry.leases[lease.lease_id] = updated
            self._write_registry(registry)
            return True

    def record_parent_completed(self, tool_use_id: str) -> tuple[str, ...]:
        tool = _bounded(tool_use_id, "tool_use_id")
        with self._locked():
            registry = cast(Registry, self._read_registry(create=True))
            matches = [lease for lease in registry.leases.values() if lease.tool_use_id == tool]
            if not matches:
                return ()
            _wall, now_text, _monotonic, _boot_id = self._now()
            removed: list[str] = []
            for lease in matches:
                updated = replace(lease, parent_completed_at=lease.parent_completed_at or now_text)
                if updated.agent_id is None or updated.child_terminal_at is not None:
                    del registry.leases[lease.lease_id]
                    removed.append(lease.lease_id)
                else:
                    registry.leases[lease.lease_id] = updated
            self._write_registry(registry)
            return tuple(sorted(removed))

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
                "expired"
                if self._expired(lease, monotonic=monotonic, boot_id=boot_id)
                else "live"
            )
            leases.append(item)
        return {
            "exists": True,
            "root_sha256": self.root_sha256,
            "schema": SCHEMA,
            "broker_epoch": registry.broker_epoch,
            "next_fencing_sequence": registry.next_fencing_sequence,
            "leases": leases,
            "resource_fences": {
                key: value.to_dict() for key, value in sorted(registry.resource_fences.items())
            },
        }

    def _owner_state(self, lease: Lease) -> Literal["dead", "live", "unknown"]:
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
        """Release expired agent leases and safely reap provably-dead worktree leases."""

        terminal = {_bounded(item, "terminal_lease_id") for item in terminal_lease_ids}
        candidates: list[Lease] = []
        retained: dict[str, str] = {}
        released_agents: list[str] = []
        with self._locked():
            registry = cast(Registry, self._read_registry(create=True))
            _wall, _now_text, monotonic, boot_id = self._now()
            for lease in list(registry.leases.values()):
                if not self._expired(lease, monotonic=monotonic, boot_id=boot_id):
                    continue
                if lease.pool == "agent":
                    del registry.leases[lease.lease_id]
                    released_agents.append(lease.lease_id)
                    continue
                owner_state = "dead" if lease.lease_id in terminal else self._owner_state(lease)
                if owner_state == "live":
                    retained[lease.lease_id] = "expired-live-owner"
                elif owner_state == "unknown":
                    retained[lease.lease_id] = "expired-owner-unknown"
                else:
                    candidates.append(lease)
            if released_agents:
                self._write_registry(registry)

        reaped: list[str] = []
        for candidate in candidates:
            if worktree_reaper is None:
                retained[candidate.lease_id] = "expired-no-reaper"
                continue
            assert candidate.resource_ref is not None
            try:
                successful = bool(worktree_reaper(candidate.resource_ref))
            except Exception:  # noqa: BLE001 - preserve authority for an operator-visible retry.
                successful = False
            if not successful:
                retained[candidate.lease_id] = "reap-failed"
                continue
            with self._locked():
                registry = cast(Registry, self._read_registry(create=True))
                current = registry.leases.get(candidate.lease_id)
                if current is None:
                    continue
                _wall, _now_text, monotonic, boot_id = self._now()
                if current.token != candidate.token or not self._expired(
                    current, monotonic=monotonic, boot_id=boot_id
                ):
                    retained[candidate.lease_id] = "changed-during-reap"
                    continue
                del registry.leases[candidate.lease_id]
                self._write_registry(registry)
                reaped.append(candidate.lease_id)
        return SweepResult(
            released_agent_leases=tuple(sorted(released_agents)),
            reaped_worktree_leases=tuple(sorted(reaped)),
            retained=dict(sorted(retained.items())),
        )
