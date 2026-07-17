#!/usr/bin/env python3
"""Trusted in-process lease admission for direct agy live apply (#355)."""

from __future__ import annotations

import contextlib
import hashlib
import os
import subprocess
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import fleet_commons_shim

_broker_module = fleet_commons_shim.load("lease_broker")
_policy_module = fleet_commons_shim.load("concurrency_policy")
_evidence_module = fleet_commons_shim.load("orphan_evidence")

REQUIRED_LEASE_PROTOCOL_VERSION = 2
if getattr(_broker_module, "PROTOCOL_VERSION", None) != REQUIRED_LEASE_PROTOCOL_VERSION:
    raise RuntimeError(
        "agy live apply requires fleet-core lease protocol "
        f"{REQUIRED_LEASE_PROTOCOL_VERSION} "
        f"(found {getattr(_broker_module, 'PROTOCOL_VERSION', None)!r}); "
        "install/update fleet-core"
    )

MAX_RESOURCE_KEY_BYTES = 128


class AgyLeaseAdmissionError(ValueError):
    """Direct agy admission could not be derived from trusted local state."""


def _closed_resource_head(broker: Any, resource_ref: dict[str, str]) -> tuple[Any, str] | None:
    """Return the exact canonical closed predecessor, if one is still the resource head.

    ``acquire_successor`` repeats this comparison under the broker lock.  This read only
    selects which acquisition API to call; it is deliberately not relied on for authority.
    """

    canonical = _broker_module.canonical_resource_ref("agent", resource_ref)
    head = broker.inspect_resource_head(canonical)
    if not isinstance(head, Mapping) or head.get("resource_ref") != canonical:
        return None
    close = head.get("close_receipt")
    if not isinstance(close, Mapping):
        return None
    try:
        token = _broker_module.FencingToken.from_dict(close["token"])
        receipt_sha256 = close["receipt_sha256"]
        if not isinstance(receipt_sha256, str):
            raise ValueError("receipt_sha256 is not a string")
        _broker_module.validate_settlement_close(close)
    except (KeyError, TypeError, ValueError, _broker_module.LeaseBrokerError) as exc:
        raise AgyLeaseAdmissionError(
            "canonical resource head has an invalid close receipt"
        ) from exc
    return token, receipt_sha256


def _bounded(value: str, name: str, *, maximum: int = 128) -> str:
    if not isinstance(value, str) or not value or len(value.encode("utf-8")) > maximum:
        raise AgyLeaseAdmissionError(f"{name} must be a bounded non-empty string")
    if any(ord(char) < 32 for char in value):
        raise AgyLeaseAdmissionError(f"{name} must not contain control characters")
    return value


def _canonical_repository(repo_root: Path) -> tuple[Path, str]:
    resolved = repo_root.expanduser().resolve(strict=True)
    completed = subprocess.run(
        ["git", "-C", str(resolved), "rev-parse", "--show-toplevel", "--git-common-dir"],
        check=False,
        capture_output=True,
        text=True,
        timeout=10,
    )
    lines = completed.stdout.splitlines()
    if completed.returncode != 0 or len(lines) != 2:
        raise AgyLeaseAdmissionError("repo_root must be a readable Git worktree root")
    top = Path(lines[0]).resolve(strict=True)
    if top != resolved:
        raise AgyLeaseAdmissionError("repo_root must equal Git's canonical worktree root")
    common = Path(lines[1])
    if not common.is_absolute():
        common = (resolved / common).resolve(strict=True)
    identity = hashlib.sha256(f"{top}\0{common}".encode()).hexdigest()
    return top, identity


@dataclass(frozen=True)
class AgyLeaseAdmission:
    """Immutable trusted record carried directly from resolver through exact close."""

    session_id: str
    owner_id: str
    owner_pid: int
    owner_process_start: str
    policy_sha256: str
    session_limit: int
    aggregate_limit: int
    mutation: str
    ttl_seconds: int
    resource_ref: dict[str, str]
    repository_identity_sha256: str
    expected_output_template_sha256: str
    lease: Any
    expected_output_template: dict[str, Any]
    expected_output: dict[str, Any]
    broker: Any

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema": "agy.lease-admission.v1",
            "session_id": self.session_id,
            "owner_id": self.owner_id,
            "owner_pid": self.owner_pid,
            "owner_process_start": self.owner_process_start,
            "policy_sha256": self.policy_sha256,
            "session_limit": self.session_limit,
            "aggregate_limit": self.aggregate_limit,
            "mutation": self.mutation,
            "ttl_seconds": self.ttl_seconds,
            "resource_ref": self.resource_ref,
            "repository_identity_sha256": self.repository_identity_sha256,
            "expected_output_template_sha256": self.expected_output_template_sha256,
        }


def cleanup_unsettled_admission(admission: AgyLeaseAdmission) -> None:
    """Release one pre-settlement grant and its admission pin, or fail loudly.

    A failed release is not harmless: only an independently observed closed or superseded token
    proves this process no longer retains authority.  The broker's release path is exact-token
    checked and normally removes the session admission itself; the explicit clear below catches
    any pin left behind by a partial failure.
    """

    try:
        released = admission.broker.release(
            admission.lease.lease_id,
            owner_id=admission.owner_id,
            token=admission.lease.token,
        )
    except Exception as exc:  # noqa: BLE001 - broker failures are containment failures.
        state = admission.broker.classify_token(admission.resource_ref, admission.lease.token)
        if state not in {"closed", "superseded"}:
            raise AgyLeaseAdmissionError(
                f"could not exact-release pre-settlement lease; authority remains {state}: {exc}"
            ) from exc
    else:
        if not released:
            state = admission.broker.classify_token(admission.resource_ref, admission.lease.token)
            if state not in {"closed", "superseded"}:
                raise AgyLeaseAdmissionError(
                    f"exact-release reported no lease while authority remains {state}"
                )
    try:
        admission.broker.clear_session_admission(admission.session_id)
    except Exception as exc:  # noqa: BLE001 - a pinned admission is durable authority state.
        raise AgyLeaseAdmissionError(
            f"could not clear pre-settlement session admission: {exc}"
        ) from exc


def resolve_direct_agy_admission(
    repo_root: Path,
    resource_key: str,
    run_id: str,
    providers: Any | None = None,
    *,
    broker: Any | None = None,
) -> AgyLeaseAdmission:
    """Resolve, configure, acquire, and bind one direct live-apply lease before subprocess launch."""

    root, repository_identity = _canonical_repository(repo_root)
    key = _bounded(resource_key, "lease_resource_key", maximum=MAX_RESOURCE_KEY_BYTES)
    if key in {".", ".."} or "/" in key or "\\" in key:
        raise AgyLeaseAdmissionError("lease_resource_key must be one opaque path-free key")
    # The caller-provided key is an in-memory capability input, not evidence. Persisting it in the
    # broker's resource_ref (and therefore registry, close receipts, quarantine, and audit output)
    # leaks it across every durable containment surface. Derive one repository-scoped opaque id and
    # discard the raw value before constructing any record.
    resource_key_sha256 = hashlib.sha256(
        f"agy-resource-key\0{repository_identity}\0{key}".encode()
    ).hexdigest()
    run = _bounded(run_id, "run_id")
    selected_providers = providers or _broker_module.Providers()
    selected_broker = broker or _broker_module.LeaseBroker(providers=selected_providers)
    limits = _policy_module.AdmissionLimits()
    limits.validate("agy-direct")
    policy_sha256 = limits.policy_sha256()
    session_id = f"agy:{hashlib.sha256(f'{repository_identity}:{run}'.encode()).hexdigest()}"
    owner_id = f"agy-direct:{os.geteuid()}"
    owner_pid = os.getpid()
    owner_process_start = selected_providers.process_identity(owner_pid)
    if not owner_process_start:
        raise AgyLeaseAdmissionError("current process identity is unavailable")
    resource_ref = {
        "logical_unit_id": f"agy:{repository_identity}:{resource_key_sha256}",
        "worktree_root": str(root),
    }
    template = _evidence_module.build_expected_output_template(
        f"{run}:{resource_key_sha256}",
        required=True,
        artifact_keys=("diff.patch",),
        target_count=1,
    )
    selected_broker.configure_session_admission(
        session_id,
        policy_sha256=policy_sha256,
        session_limit=limits.max_concurrent,
        aggregate_limit=limits.aggregate_max_concurrent,
        mutation="read-write",
    )
    try:
        predecessor = _closed_resource_head(selected_broker, resource_ref)
        acquisition = {
            "owner_id": owner_id,
            "owner_pid": owner_pid,
            "owner_process_start": owner_process_start,
            "session_id": session_id,
            "policy_sha256": policy_sha256,
            "session_limit": limits.max_concurrent,
            "aggregate_limit": limits.aggregate_max_concurrent,
            "mutation": "read-write",
            "ttl_seconds": _broker_module.DEFAULT_TTL_SECONDS,
            "resource_ref": resource_ref,
            "agent_type": "agy-direct",
        }
        if predecessor is None:
            lease = selected_broker.acquire_agent(**acquisition)
        else:
            predecessor_token, predecessor_receipt_sha256 = predecessor
            lease = selected_broker.acquire_successor(
                **acquisition,
                predecessor_token=predecessor_token,
                predecessor_receipt_sha256=predecessor_receipt_sha256,
            )
    except Exception:
        with contextlib.suppress(Exception):
            selected_broker.clear_session_admission(session_id)
        raise
    try:
        expected_output = _evidence_module.bind_expected_output(
            template,
            resource=resource_ref,
            token=lease.token,
            lease_id=lease.lease_id,
            producer="agy",
            run_id=run,
        )
        admission = AgyLeaseAdmission(
            session_id=session_id,
            owner_id=owner_id,
            owner_pid=owner_pid,
            owner_process_start=owner_process_start,
            policy_sha256=policy_sha256,
            session_limit=limits.max_concurrent,
            aggregate_limit=limits.aggregate_max_concurrent,
            mutation="read-write",
            ttl_seconds=_broker_module.DEFAULT_TTL_SECONDS,
            resource_ref=resource_ref,
            repository_identity_sha256=repository_identity,
            expected_output_template_sha256=template["expected_output_template_sha256"],
            lease=lease,
            expected_output_template=template,
            expected_output=expected_output,
            broker=selected_broker,
        )
        _evidence_module.validate_record(admission.to_dict())
        return admission
    except Exception as exc:  # noqa: BLE001 - post-acquisition failures must drain authority.
        failed_admission = AgyLeaseAdmission(
            session_id=session_id,
            owner_id=owner_id,
            owner_pid=owner_pid,
            owner_process_start=owner_process_start,
            policy_sha256=policy_sha256,
            session_limit=limits.max_concurrent,
            aggregate_limit=limits.aggregate_max_concurrent,
            mutation="read-write",
            ttl_seconds=_broker_module.DEFAULT_TTL_SECONDS,
            resource_ref=resource_ref,
            repository_identity_sha256=repository_identity,
            expected_output_template_sha256=template["expected_output_template_sha256"],
            lease=lease,
            expected_output_template=template,
            expected_output={},
            broker=selected_broker,
        )
        try:
            cleanup_unsettled_admission(failed_admission)
        except AgyLeaseAdmissionError as cleanup_exc:
            raise AgyLeaseAdmissionError(
                f"post-acquisition binding failed ({exc}); cleanup also failed: {cleanup_exc}"
            ) from exc
        raise
