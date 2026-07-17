#!/usr/bin/env python3
"""Typed, advisory-only second-opinion coordination for Saga review consumers."""

from __future__ import annotations

import fcntl
import hashlib
import json
import os
import re
import sys
import tempfile
from collections.abc import Callable, Iterable, Iterator, Mapping
from contextlib import contextmanager
from dataclasses import dataclass, replace
from pathlib import Path, PurePosixPath
from types import MappingProxyType
from typing import Any, Literal, cast

sys.path.insert(0, str(Path(__file__).resolve().parent))

import engine_dispatch  # noqa: E402
import engine_recommend  # noqa: E402
import engine_resolver  # noqa: E402
import reconcile  # noqa: E402
import run_ledger  # noqa: E402
from engine_registry import Registry  # noqa: E402

Severity = Literal["P0", "P1", "P2", "P3"]
RequestSource = Literal["human", "claude"]
OpinionState = Literal["recommended", "requested", "available", "unavailable", "declined"]
ClaimState = Literal["requested", "available", "unavailable"]

MAX_EXCERPTS = 16
MAX_EXCERPT_BYTES = 16 * 1024
MAX_CONTEXT_BYTES = 128 * 1024
MAX_REASON_BYTES = 4 * 1024
MAX_STATUS_NOTE_BYTES = 1024
CLAIM_SCHEMA = "saga.second-opinion-claims.v1"
WORK_STATE_SCHEMA = "saga.work-second-opinion.v1"
MAX_WORK_ATTEMPTS = 64
MAX_TARGETS_PER_ATTEMPT = 256
DEFAULT_SECOND_OPINION_TIER = {"model": "opus", "effort": "high"}
INTERRUPTED_DISPATCH_NOTE = (
    "prior dispatch outcome unknown; at-most-once replay guard refused redispatch"
)
UNUSABLE_DISPATCH_NOTE = "second-opinion dispatch produced unusable advisory evidence"
EMPTY_OPINION_NOTE = "second-opinion dispatch returned no typed findings"
_SEVERITIES: tuple[Severity, ...] = ("P0", "P1", "P2", "P3")
_STATUS_MAP = {
    "success": "ok",
    "no_output": "no-output",
    "no-output": "no-output",
    "clone_failed": "clone-failed",
    "clone-failed": "clone-failed",
    "failure": "error",
}
_SENSITIVE_CONTENT_PATTERNS = (
    re.compile(r"-----BEGIN [A-Z0-9 ]*PRIVATE KEY-----"),
    re.compile(r"\b(?:AKIA|ASIA)[A-Z0-9]{16}\b"),
    re.compile(r"\b(?:gh[pousr]_[A-Za-z0-9_]{20,}|github_pat_[A-Za-z0-9_]{20,})\b"),
    re.compile(r"\bsk-[A-Za-z0-9]{20,}\b"),
    re.compile(
        r"(?i)\b(?:api[_-]?key|secret|password|access[_-]?token|auth(?:orization)?)"
        r"\b\s*[:=]\s*[^\s<][^\s]*"
    ),
    re.compile(r"(?i)\bauthorization\s*:\s*bearer\s+\S+"),
    re.compile(r"(?i)\b(?:customer|tenant)[_-]?(?:id|email|name|data)\b\s*[:=]\s*\S+"),
    re.compile(r"(?i)\b(?:private|confidential)\s+(?:customer|tenant)\b"),
)


class SecondOpinionError(ValueError):
    """A second-opinion request, claim, or projection is invalid."""


class WorkSecondOpinionStateError(SecondOpinionError):
    """A versioned `/work` second-opinion sidecar is invalid or cannot advance safely."""


@dataclass(frozen=True)
class SourceExcerpt:
    """One bounded repo-grounded source excerpt in a second-opinion context."""

    path: str
    start_line: int
    end_line: int
    content: str

    def __post_init__(self) -> None:
        _repo_relative_path(self.path)
        _positive_line(self.start_line, "start_line")
        _positive_line(self.end_line, "end_line")
        if self.end_line < self.start_line:
            raise SecondOpinionError("excerpt end_line must be >= start_line")
        _nonempty_string(self.content, "excerpt content")

    def to_dict(self) -> dict[str, Any]:
        return {
            "path": self.path,
            "start_line": self.start_line,
            "end_line": self.end_line,
            "content": self.content,
        }


@dataclass(frozen=True)
class FindingSnapshot:
    """The selected source finding and the only repository content eligible for egress."""

    finding_id: str
    title: str
    severity: Severity
    why_it_matters: str
    evidence: tuple[str, ...]
    suggested_fix: str | None
    reviewed_revision: str
    excerpts: tuple[SourceExcerpt, ...]
    sensitive: bool = False

    def __post_init__(self) -> None:
        _bounded_id(self.finding_id, "finding_id")
        _nonempty_string(self.title, "title")
        if self.severity not in _SEVERITIES:
            raise SecondOpinionError(f"severity {self.severity!r} not in {_SEVERITIES}")
        _nonempty_string(self.why_it_matters, "why_it_matters")
        _bounded_id(self.reviewed_revision, "reviewed_revision")
        if not isinstance(self.evidence, tuple) or not self.evidence:
            raise SecondOpinionError("evidence must be a non-empty immutable tuple")
        if not all(isinstance(value, str) and value for value in self.evidence):
            raise SecondOpinionError("evidence entries must be non-empty strings")
        if self.suggested_fix is not None and not isinstance(self.suggested_fix, str):
            raise SecondOpinionError("suggested_fix must be a string or None")
        if not isinstance(self.excerpts, tuple) or not all(
            isinstance(item, SourceExcerpt) for item in self.excerpts
        ):
            raise SecondOpinionError("excerpts must be an immutable SourceExcerpt tuple")
        if not isinstance(self.sensitive, bool):
            raise SecondOpinionError("sensitive must be a boolean")

    def to_context_dict(self, *, reason: str) -> dict[str, Any]:
        return {
            "finding_id": self.finding_id,
            "title": self.title,
            "severity": self.severity,
            "why_it_matters": self.why_it_matters,
            "evidence": list(self.evidence),
            "suggested_fix": self.suggested_fix,
            "reviewed_revision": self.reviewed_revision,
            "reason": reason,
            "excerpts": [item.to_dict() for item in self.excerpts],
        }


@dataclass(frozen=True)
class PreparedSecondOpinion:
    """A fully bounded, resolved request ready for a pre-dispatch claim."""

    request_id: str
    request_digest: str
    execution_id: str
    reconciliation_id: str
    finding: FindingSnapshot
    requested_by: RequestSource
    reason: str
    chaperone_model: str
    chaperone_effort: str
    context: str
    context_digest: str
    token_estimate: int
    resolution: engine_resolver.Resolution | None
    egress_policy: str | None
    unavailable_reason: str | None

    @property
    def selected_identity(self) -> str | None:
        if self.resolution is None:
            return None
        return f"{self.resolution.engine_id}/{self.resolution.variant}"


@dataclass(frozen=True)
class ReconciledOpinion:
    """An externally produced opinion that Claude has fully accounted for."""

    prepared: PreparedSecondOpinion
    evidence: engine_dispatch.AdvisoryEvidence
    reconciliation: reconcile.ReconciliationResult


@dataclass(frozen=True)
class ClaudeAdjudication:
    """Claude's durable decision about the original review finding."""

    adjudicator_id: str
    decision: Literal["keep", "downgrade", "dismiss"]
    rationale: str
    final_severity: Severity
    final_status: Literal["active", "dismissed"]

    def __post_init__(self) -> None:
        _bounded_id(self.adjudicator_id, "adjudicator_id")
        if self.decision not in {"keep", "downgrade", "dismiss"}:
            raise SecondOpinionError(f"unsupported adjudication decision {self.decision!r}")
        _bounded_bytes(self.rationale, reconcile.MAX_RATIONALE_BYTES, "adjudication rationale")
        if self.final_severity not in _SEVERITIES:
            raise SecondOpinionError(f"final_severity {self.final_severity!r} not in {_SEVERITIES}")
        if self.final_status not in {"active", "dismissed"}:
            raise SecondOpinionError(f"unsupported final_status {self.final_status!r}")


@dataclass(frozen=True)
class RequestClaim:
    """Durable metadata-only reservation; raw opinion content never enters this store."""

    request_id: str
    request_digest: str
    execution_id: str
    reconciliation_id: str
    state: ClaimState
    status_note: str | None = None

    def to_dict(self) -> dict[str, str]:
        result = {
            "request_id": self.request_id,
            "request_digest": self.request_digest,
            "execution_id": self.execution_id,
            "reconciliation_id": self.reconciliation_id,
            "state": self.state,
        }
        if self.status_note is not None:
            result["status_note"] = self.status_note
        return result

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> RequestClaim:
        expected = {
            "request_id",
            "request_digest",
            "execution_id",
            "reconciliation_id",
            "state",
            "status_note",
        }
        if set(data) - expected:
            raise SecondOpinionError("second-opinion claim has unknown fields")
        values = {
            key: data.get(key)
            for key in (
                "request_id",
                "request_digest",
                "execution_id",
                "reconciliation_id",
                "state",
            )
        }
        if not all(isinstance(value, str) and value for value in values.values()):
            raise SecondOpinionError("second-opinion claim is missing required string fields")
        state = cast(str, values["state"])
        if state not in {"requested", "available", "unavailable"}:
            raise SecondOpinionError(f"second-opinion claim has invalid state {state!r}")
        note = data.get("status_note")
        if note is not None:
            _bounded_bytes(note, MAX_STATUS_NOTE_BYTES, "status_note")
        return cls(
            request_id=cast(str, values["request_id"]),
            request_digest=cast(str, values["request_digest"]),
            execution_id=cast(str, values["execution_id"]),
            reconciliation_id=cast(str, values["reconciliation_id"]),
            state=cast(ClaimState, state),
            status_note=cast(str | None, note),
        )


@dataclass(frozen=True)
class ClaimResult:
    acquired: bool
    claim: RequestClaim


@dataclass(frozen=True)
class WorkAttempt:
    """One applied fix followed by its test result; reruns reuse its immutable ID."""

    attempt_id: str
    change_ref: str
    result: Literal["pass", "fail"]
    failing_test_files: tuple[str, ...]

    def __post_init__(self) -> None:
        _bounded_id(self.attempt_id, "attempt_id")
        _bounded_bytes(self.change_ref, 4 * 1024, "change_ref")
        if self.result not in {"pass", "fail"}:
            raise WorkSecondOpinionStateError("work attempt result must be pass or fail")
        if not isinstance(self.failing_test_files, tuple):
            raise WorkSecondOpinionStateError("failing_test_files must be an immutable tuple")
        if len(self.failing_test_files) > MAX_TARGETS_PER_ATTEMPT:
            raise WorkSecondOpinionStateError(
                f"failing_test_files exceeds MAX_TARGETS_PER_ATTEMPT={MAX_TARGETS_PER_ATTEMPT}"
            )
        normalized = tuple(normalize_pytest_target(value) for value in self.failing_test_files)
        if len(set(normalized)) != len(normalized):
            raise WorkSecondOpinionStateError(
                "failing_test_files must not contain duplicate targets"
            )
        if self.result == "pass" and normalized:
            raise WorkSecondOpinionStateError(
                "a passing work attempt cannot have failing_test_files"
            )
        object.__setattr__(self, "failing_test_files", normalized)

    def to_dict(self) -> dict[str, Any]:
        return {
            "attempt_id": self.attempt_id,
            "change_ref": self.change_ref,
            "result": self.result,
            "failing_test_files": list(self.failing_test_files),
        }

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> WorkAttempt:
        expected = {"attempt_id", "change_ref", "result", "failing_test_files"}
        if set(data) != expected:
            raise WorkSecondOpinionStateError("work attempt fields do not match v1 schema")
        targets = data["failing_test_files"]
        if not isinstance(targets, list):
            raise WorkSecondOpinionStateError("failing_test_files must be an array")
        return cls(
            attempt_id=cast(str, data["attempt_id"]),
            change_ref=cast(str, data["change_ref"]),
            result=cast(Literal["pass", "fail"], data["result"]),
            failing_test_files=tuple(cast(str, target) for target in targets),
        )


@dataclass(frozen=True)
class WorkOffer:
    """One debounced `/work` offer, keyed by target and its current streak epoch."""

    offer_id: str
    target: str
    streak_epoch_attempt_id: str
    disposition: Literal["offered", "accepted", "declined", "unattended", "unavailable"]
    tier: Mapping[str, str]
    engine: str | None = None
    request_id: str | None = None
    request_digest: str | None = None
    execution_id: str | None = None

    def __post_init__(self) -> None:
        _bounded_id(self.offer_id, "offer_id")
        object.__setattr__(self, "target", normalize_pytest_target(self.target))
        _bounded_id(self.streak_epoch_attempt_id, "streak_epoch_attempt_id")
        if self.disposition not in {
            "offered",
            "accepted",
            "declined",
            "unattended",
            "unavailable",
        }:
            raise WorkSecondOpinionStateError("work offer has an invalid disposition")
        if set(self.tier) != {"model", "effort"} or not all(
            isinstance(value, str) and value for value in self.tier.values()
        ):
            raise WorkSecondOpinionStateError(
                "work offer tier must have non-empty model and effort"
            )
        object.__setattr__(self, "tier", MappingProxyType(dict(self.tier)))
        for field, value in (
            ("engine", self.engine),
            ("request_id", self.request_id),
            ("request_digest", self.request_digest),
            ("execution_id", self.execution_id),
        ):
            if value is not None:
                _bounded_bytes(value, reconcile.MAX_ID_BYTES, field)

    def to_dict(self) -> dict[str, Any]:
        result: dict[str, Any] = {
            "offer_id": self.offer_id,
            "target": self.target,
            "streak_epoch_attempt_id": self.streak_epoch_attempt_id,
            "disposition": self.disposition,
            "tier": dict(self.tier),
        }
        for field in ("engine", "request_id", "request_digest", "execution_id"):
            value = getattr(self, field)
            if value is not None:
                result[field] = value
        return result

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> WorkOffer:
        required = {"offer_id", "target", "streak_epoch_attempt_id", "disposition", "tier"}
        optional = {"engine", "request_id", "request_digest", "execution_id"}
        if not required <= set(data) or set(data) - required - optional:
            raise WorkSecondOpinionStateError("work offer fields do not match v1 schema")
        tier = data["tier"]
        if not isinstance(tier, dict):
            raise WorkSecondOpinionStateError("work offer tier must be an object")
        return cls(
            offer_id=cast(str, data["offer_id"]),
            target=cast(str, data["target"]),
            streak_epoch_attempt_id=cast(str, data["streak_epoch_attempt_id"]),
            disposition=cast(
                Literal["offered", "accepted", "declined", "unattended", "unavailable"],
                data["disposition"],
            ),
            tier={cast(str, key): cast(str, value) for key, value in tier.items()},
            engine=cast(str | None, data.get("engine")),
            request_id=cast(str | None, data.get("request_id")),
            request_digest=cast(str | None, data.get("request_digest")),
            execution_id=cast(str | None, data.get("execution_id")),
        )


@dataclass(frozen=True)
class WorkSecondOpinionState:
    """Bounded, versioned sidecar state for `/work` stuck-trigger debounce."""

    round: int
    attempts: tuple[WorkAttempt, ...] = ()
    offers: tuple[WorkOffer, ...] = ()

    def __post_init__(self) -> None:
        if isinstance(self.round, bool) or not isinstance(self.round, int) or self.round < 0:
            raise WorkSecondOpinionStateError(
                "work second-opinion round must be a non-negative integer"
            )
        if not isinstance(self.attempts, tuple) or not all(
            isinstance(item, WorkAttempt) for item in self.attempts
        ):
            raise WorkSecondOpinionStateError(
                "work attempts must be an immutable WorkAttempt tuple"
            )
        if len(self.attempts) > MAX_WORK_ATTEMPTS:
            raise WorkSecondOpinionStateError(
                f"work attempts exceeds MAX_WORK_ATTEMPTS={MAX_WORK_ATTEMPTS}"
            )
        if len({item.attempt_id for item in self.attempts}) != len(self.attempts):
            raise WorkSecondOpinionStateError("work attempts must have unique attempt_id values")
        if not isinstance(self.offers, tuple) or not all(
            isinstance(item, WorkOffer) for item in self.offers
        ):
            raise WorkSecondOpinionStateError("work offers must be an immutable WorkOffer tuple")
        if len(self.offers) > MAX_WORK_ATTEMPTS:
            raise WorkSecondOpinionStateError(
                f"work offers exceeds MAX_WORK_ATTEMPTS={MAX_WORK_ATTEMPTS}"
            )
        if len({item.offer_id for item in self.offers}) != len(self.offers):
            raise WorkSecondOpinionStateError("work offers must have unique offer_id values")
        attempt_ids = {item.attempt_id for item in self.attempts}
        keys = {(item.target, item.streak_epoch_attempt_id) for item in self.offers}
        if len(keys) != len(self.offers):
            raise WorkSecondOpinionStateError("work offers must have unique target/epoch keys")
        if any(item.streak_epoch_attempt_id not in attempt_ids for item in self.offers):
            raise WorkSecondOpinionStateError("work offer epoch must name a retained attempt")

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema": WORK_STATE_SCHEMA,
            "round": self.round,
            "attempts": [item.to_dict() for item in self.attempts],
            "offers": [item.to_dict() for item in self.offers],
        }

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> WorkSecondOpinionState:
        expected = {"schema", "round", "attempts", "offers"}
        if set(data) != expected or data.get("schema") != WORK_STATE_SCHEMA:
            raise WorkSecondOpinionStateError(f"work state must match {WORK_STATE_SCHEMA}")
        attempts = data["attempts"]
        offers = data["offers"]
        if not isinstance(attempts, list) or not isinstance(offers, list):
            raise WorkSecondOpinionStateError("work state attempts and offers must be arrays")
        if not all(isinstance(value, dict) for value in attempts + offers):
            raise WorkSecondOpinionStateError("work state array entries must be objects")
        return cls(
            round=cast(int, data["round"]),
            attempts=tuple(WorkAttempt.from_dict(value) for value in attempts),
            offers=tuple(WorkOffer.from_dict(value) for value in offers),
        )


@dataclass(frozen=True)
class WorkAttemptRecord:
    """The updated sidecar plus the one new operator-visible offer, if any."""

    state: WorkSecondOpinionState
    offer: WorkOffer | None

    @property
    def offer_line(self) -> str | None:
        if self.offer is None:
            return None
        return render_work_offer_line(self.offer.target)


class SecondOpinionClaimStore:
    """Atomic request reservations for one durable review or work consumer record."""

    def __init__(self, path: Path | str) -> None:
        self.path = Path(path)

    def claim(self, prepared: PreparedSecondOpinion) -> ClaimResult:
        with self._locked():
            claims = self._read_claims()
            existing = claims.get(prepared.request_id)
            if existing is not None:
                if existing.request_digest != prepared.request_digest:
                    raise SecondOpinionError(
                        f"request_id {prepared.request_id!r} already names another request digest"
                    )
                _assert_claim_matches_prepared(existing, prepared)
                return ClaimResult(acquired=False, claim=existing)
            claim = RequestClaim(
                request_id=prepared.request_id,
                request_digest=prepared.request_digest,
                execution_id=prepared.execution_id,
                reconciliation_id=prepared.reconciliation_id,
                state="requested",
            )
            claims[claim.request_id] = claim
            self._write_claims(claims)
            return ClaimResult(acquired=True, claim=claim)

    def recover_unresolved(self, prepared: PreparedSecondOpinion) -> RequestClaim:
        """Turn a pre-existing requested reservation into visible unavailable state on resume."""
        return self.mark_unavailable(prepared, note=INTERRUPTED_DISPATCH_NOTE)

    def mark_unavailable(self, prepared: PreparedSecondOpinion, *, note: str) -> RequestClaim:
        """Record a terminal advisory failure without permitting a wrapper replay."""
        return self._transition(prepared, expected="requested", target="unavailable", note=note)

    def mark_available(self, prepared: PreparedSecondOpinion) -> RequestClaim:
        return self._transition(prepared, expected="requested", target="available", note=None)

    def read(self, request_id: str) -> RequestClaim | None:
        with self._read_locked():
            return self._read_claims().get(request_id)

    def _transition(
        self,
        prepared: PreparedSecondOpinion,
        *,
        expected: ClaimState,
        target: ClaimState,
        note: str | None,
    ) -> RequestClaim:
        if note is not None:
            _bounded_bytes(note, MAX_STATUS_NOTE_BYTES, "status_note")
        with self._locked():
            claims = self._read_claims()
            existing = claims.get(prepared.request_id)
            if existing is None:
                raise SecondOpinionError(f"request {prepared.request_id!r} has not been claimed")
            _assert_claim_matches_prepared(existing, prepared)
            if existing.state == target:
                return existing
            if existing.state != expected:
                raise SecondOpinionError(
                    f"request {prepared.request_id!r} cannot transition {existing.state!r} to {target!r}"
                )
            updated = RequestClaim(
                request_id=existing.request_id,
                request_digest=existing.request_digest,
                execution_id=existing.execution_id,
                reconciliation_id=existing.reconciliation_id,
                state=target,
                status_note=note,
            )
            claims[updated.request_id] = updated
            self._write_claims(claims)
            return updated

    @contextmanager
    def _locked(self) -> Iterator[None]:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        lock_path = self.path.with_suffix(self.path.suffix + ".lock")
        fd = os.open(lock_path, os.O_RDWR | os.O_CREAT, 0o600)
        os.fchmod(fd, 0o600)
        try:
            fcntl.flock(fd, fcntl.LOCK_EX)
            yield
        finally:
            fcntl.flock(fd, fcntl.LOCK_UN)
            os.close(fd)

    @contextmanager
    def _read_locked(self) -> Iterator[None]:
        lock_path = self.path.with_suffix(self.path.suffix + ".lock")
        try:
            fd = os.open(lock_path, os.O_RDONLY)
        except FileNotFoundError:
            yield
            return
        try:
            fcntl.flock(fd, fcntl.LOCK_SH)
            yield
        finally:
            fcntl.flock(fd, fcntl.LOCK_UN)
            os.close(fd)

    def _read_claims(self) -> dict[str, RequestClaim]:
        try:
            raw = json.loads(self.path.read_text(encoding="utf-8"))
        except FileNotFoundError:
            return {}
        except (OSError, json.JSONDecodeError) as exc:
            raise SecondOpinionError(
                f"cannot read second-opinion claim store {self.path}: {exc}"
            ) from exc
        if not isinstance(raw, dict) or raw.get("schema") != CLAIM_SCHEMA:
            raise SecondOpinionError("second-opinion claim store has an invalid schema")
        items = raw.get("claims")
        if not isinstance(items, dict):
            raise SecondOpinionError("second-opinion claim store claims must be an object")
        claims: dict[str, RequestClaim] = {}
        for request_id, value in items.items():
            if not isinstance(request_id, str) or not isinstance(value, dict):
                raise SecondOpinionError("second-opinion claim store entry is malformed")
            claim = RequestClaim.from_dict(value)
            if claim.request_id != request_id:
                raise SecondOpinionError("second-opinion claim key and request_id disagree")
            claims[request_id] = claim
        return claims

    def _write_claims(self, claims: Mapping[str, RequestClaim]) -> None:
        payload = {
            "schema": CLAIM_SCHEMA,
            "claims": {request_id: claim.to_dict() for request_id, claim in sorted(claims.items())},
        }
        encoded = json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
        fd, temp_name = tempfile.mkstemp(
            prefix=f".{self.path.name}.", suffix=".tmp", dir=self.path.parent
        )
        temp_path = Path(temp_name)
        try:
            os.fchmod(fd, 0o600)
            with os.fdopen(fd, "w", encoding="utf-8") as handle:
                handle.write(encoded)
                handle.write("\n")
                handle.flush()
                os.fsync(handle.fileno())
            os.replace(temp_path, self.path)
        finally:
            if temp_path.exists():
                temp_path.unlink()


def work_second_opinion_sidecar(work_session_path: Path | str) -> Path:
    """Return the adjacent v1 state sidecar for a durable Markdown work-session record."""
    path = Path(work_session_path)
    if path.suffix != ".md":
        raise WorkSecondOpinionStateError("work-session path must be a Markdown file")
    return path.with_name(f"{path.stem}-second-opinion.json")


def load_work_second_opinion_state(
    path: Path | str,
    *,
    round: int,
) -> WorkSecondOpinionState:
    """Load one sidecar; an absent file is an empty round, while malformed state fails closed."""
    if isinstance(round, bool) or not isinstance(round, int) or round < 0:
        raise WorkSecondOpinionStateError(
            "work second-opinion round must be a non-negative integer"
        )
    state_path = Path(path)
    try:
        raw = json.loads(state_path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        return WorkSecondOpinionState(round=round)
    except (OSError, json.JSONDecodeError) as exc:
        raise WorkSecondOpinionStateError(
            f"cannot read work second-opinion state {state_path}: {exc}"
        ) from exc
    if not isinstance(raw, dict):
        raise WorkSecondOpinionStateError("work second-opinion state must be an object")
    state = WorkSecondOpinionState.from_dict(raw)
    if state.round != round:
        raise WorkSecondOpinionStateError(
            f"work second-opinion state round {state.round} does not match current round {round}"
        )
    return state


def save_work_second_opinion_state(path: Path | str, state: WorkSecondOpinionState) -> None:
    """Atomically replace a validated v1 sidecar using private file permissions."""
    state_path = Path(path)
    encoded = json.dumps(state.to_dict(), sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    state_path.parent.mkdir(parents=True, exist_ok=True)
    fd, temp_name = tempfile.mkstemp(
        prefix=f".{state_path.name}.", suffix=".tmp", dir=state_path.parent
    )
    temp_path = Path(temp_name)
    try:
        os.fchmod(fd, 0o600)
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            handle.write(encoded)
            handle.write("\n")
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temp_path, state_path)
    finally:
        if temp_path.exists():
            temp_path.unlink()


def record_work_attempt(
    state: WorkSecondOpinionState,
    attempt: WorkAttempt,
    *,
    preference_intent: str | None = None,
) -> WorkAttemptRecord:
    """Record one completed fix/test attempt and emit at most one debounced offer.

    A repeated identical attempt ID is a no-op. A changed payload using the same ID is an error because a
    rerun without a new applied fix must not advance the three-failure signal.
    """
    existing = next(
        (item for item in state.attempts if item.attempt_id == attempt.attempt_id), None
    )
    if existing is not None:
        if existing != attempt:
            raise WorkSecondOpinionStateError(
                "attempt_id already names a different completed attempt"
            )
        return WorkAttemptRecord(state=state, offer=None)
    if len(state.attempts) >= MAX_WORK_ATTEMPTS:
        raise WorkSecondOpinionStateError(
            f"work attempts exceeds MAX_WORK_ATTEMPTS={MAX_WORK_ATTEMPTS}"
        )
    if preference_intent not in {None, "none", "offload", "second-opinion"}:
        raise WorkSecondOpinionStateError(
            "work trigger preference must be none, offload, or second-opinion"
        )

    updated = _expire_reset_work_offers(
        replace(state, attempts=(*state.attempts, attempt)),
        attempt,
    )
    if attempt.result == "pass" or preference_intent == "none":
        return WorkAttemptRecord(state=updated, offer=None)

    candidates: list[tuple[str, str]] = []
    existing_keys = {(offer.target, offer.streak_epoch_attempt_id) for offer in updated.offers}
    for target in attempt.failing_test_files:
        streak, epoch = _target_failure_streak(updated.attempts, target)
        if streak == 3 and (target, epoch) not in existing_keys:
            candidates.append((target, epoch))
    if not candidates:
        return WorkAttemptRecord(state=updated, offer=None)

    target, epoch = min(candidates)
    offer = WorkOffer(
        offer_id=_work_offer_id(updated.round, target, epoch),
        target=target,
        streak_epoch_attempt_id=epoch,
        disposition="offered",
        tier=dict(DEFAULT_SECOND_OPINION_TIER),
    )
    return WorkAttemptRecord(state=replace(updated, offers=(*updated.offers, offer)), offer=offer)


def set_work_offer_disposition(
    state: WorkSecondOpinionState,
    *,
    offer_id: str,
    disposition: Literal["declined", "unattended"],
) -> WorkSecondOpinionState:
    """Record a non-dispatch operator outcome without changing the stage preference."""
    if disposition not in {"declined", "unattended"}:
        raise WorkSecondOpinionStateError("work offer disposition must be declined or unattended")
    offer = _work_offer_by_id(state, offer_id)
    if offer.disposition == disposition:
        return state
    if offer.disposition != "offered":
        raise WorkSecondOpinionStateError("only an offered work second opinion may be resolved")
    return _replace_work_offer(state, replace(offer, disposition=disposition))


def accept_work_offer(
    state: WorkSecondOpinionState,
    *,
    offer_id: str,
    prepared: PreparedSecondOpinion,
) -> WorkSecondOpinionState:
    """Persist the accepted request identity before the stage invokes U1's runner path."""
    offer = _work_offer_by_id(state, offer_id)
    if offer.disposition not in {"offered", "accepted"}:
        raise WorkSecondOpinionStateError("work offer no longer has an active failure streak")
    if offer.disposition == "offered":
        _require_active_work_offer_streak(state, offer)
    disposition: Literal["accepted", "unavailable"] = (
        "unavailable" if prepared.unavailable_reason is not None else "accepted"
    )
    replacement = replace(
        offer,
        disposition=disposition,
        tier={"model": prepared.chaperone_model, "effort": prepared.chaperone_effort},
        engine=prepared.selected_identity,
        request_id=prepared.request_id,
        request_digest=prepared.request_digest,
        execution_id=prepared.execution_id,
    )
    if offer.disposition == "offered":
        return _replace_work_offer(state, replacement)
    if offer == replacement:
        return state
    raise WorkSecondOpinionStateError("work offer already has a conflicting terminal disposition")


def record_work_dispatch_outcome(
    state: WorkSecondOpinionState,
    *,
    offer_id: str,
    evidence: engine_dispatch.AdvisoryEvidence,
) -> WorkSecondOpinionState:
    """Make a terminal U1 unavailable outcome visible in the durable `/work` sidecar."""
    offer = _work_offer_by_id(state, offer_id)
    if offer.disposition == "unavailable":
        return state
    if offer.disposition != "accepted":
        raise WorkSecondOpinionStateError(
            "only an accepted work offer can receive a dispatch outcome"
        )
    if evidence.execution_id != offer.execution_id:
        raise WorkSecondOpinionStateError("work offer and dispatch evidence execution_id disagree")
    if evidence.halt is None:
        return state
    return _replace_work_offer(state, replace(offer, disposition="unavailable"))


def render_work_offer_line(target: str) -> str:
    """Render the fixed, one-line operator prompt required by KTD3."""
    return (
        f"Second opinion available: {normalize_pytest_target(target)} failed after 3 fix attempts; "
        "dispatch an advisory second opinion?"
    )


def prepare_second_opinion(
    finding: FindingSnapshot,
    *,
    registry: Registry,
    requested_by: RequestSource,
    reason: str,
    selected_engine: str | None = None,
    repo_root: Path | str | None = None,
    memo: engine_resolver.RunMemo | None = None,
    chaperone_model: str = "opus",
    chaperone_effort: str = "high",
) -> PreparedSecondOpinion:
    """Build a bounded second-opinion request without invoking any wrapper."""
    if requested_by not in {"human", "claude"}:
        raise SecondOpinionError(f"requested_by {requested_by!r} must be human or claude")
    _bounded_bytes(reason, MAX_REASON_BYTES, "reason")
    _nonempty_string(chaperone_model, "chaperone_model")
    _nonempty_string(chaperone_effort, "chaperone_effort")
    context = _render_context(finding, reason)
    context_bytes = len(context.encode("utf-8"))
    if context_bytes > MAX_CONTEXT_BYTES:
        raise SecondOpinionError(
            f"second-opinion context exceeds MAX_CONTEXT_BYTES={MAX_CONTEXT_BYTES}"
        )
    context_digest = _sha256(context)
    task_context = {
        "context": context,
        "token_estimate": context_bytes,
        "unit_id": finding.finding_id,
    }
    resolution: engine_resolver.Resolution | None = None
    egress_policy: str | None = None
    unavailable_reason: str | None = None

    sensitive = finding.sensitive or _contains_sensitive_content(finding, reason)
    if sensitive:
        recommendation = engine_recommend.recommend(
            engine_recommend.RecommendationTask(
                capability="second-opinion",
                policy="cheapest-viable",
                sensitive=True,
                token_estimate=context_bytes,
                min_rating="MODERATE",
            ),
            registry=registry,
        )
        candidate = recommendation.recommended
        if candidate is None:
            unavailable_reason = (
                recommendation.reason or "no local-only second-opinion route is available"
            )
        else:
            egress_policy = candidate.egress_policy
            resolution = engine_resolver.resolve(
                {
                    "engine": candidate.key,
                    "role_kind": "advisory-reviewer",
                    "task_context": task_context,
                },
                mode="dispatch",
                registry=registry,
                memo=memo,
                repo_root=repo_root,
            )
    else:
        request: dict[str, Any] = {
            "role_kind": "advisory-reviewer",
            "task_context": task_context,
        }
        if selected_engine is None:
            request["capability"] = "second-opinion"
        else:
            request["engine"] = selected_engine
        resolution = engine_resolver.resolve(
            request,
            mode="dispatch",
            registry=registry,
            memo=memo,
            repo_root=repo_root,
        )
        egress_policy = registry.by_key(
            f"{resolution.engine_id}/{resolution.variant}"
        ).egress_policy

    if resolution is not None and resolution.halt is not None:
        unavailable_reason = resolution.halt
    route = (
        f"{resolution.engine_id}/{resolution.variant}" if resolution is not None else "unavailable"
    )
    request_digest = _sha256(
        _canonical_json(
            {
                "context_digest": context_digest,
                "requested_by": requested_by,
                "chaperone_tier": {"model": chaperone_model, "effort": chaperone_effort},
                "route": route,
            }
        )
    )
    return PreparedSecondOpinion(
        request_id=f"second-opinion:{request_digest}",
        request_digest=request_digest,
        execution_id=f"second-opinion-exec:{request_digest}",
        reconciliation_id=f"second-opinion-reconcile:{request_digest}",
        finding=finding,
        requested_by=requested_by,
        reason=reason,
        chaperone_model=chaperone_model,
        chaperone_effort=chaperone_effort,
        context=context,
        context_digest=context_digest,
        token_estimate=context_bytes,
        resolution=resolution,
        egress_policy=egress_policy,
        unavailable_reason=unavailable_reason,
    )


def dispatch_second_opinion(
    prepared: PreparedSecondOpinion,
    *,
    runner: engine_dispatch.Runner,
    claim_store: SecondOpinionClaimStore,
    ledger: run_ledger.RunLedger | None = None,
    subplot_id: str = "",
    at: str = "",
    recover_pending: bool = False,
) -> engine_dispatch.AdvisoryEvidence:
    """Claim then dispatch once; a resumed uncertain claim never replays the wrapper."""
    if prepared.unavailable_reason is not None or prepared.resolution is None:
        return _unavailable_evidence(prepared, prepared.unavailable_reason or "route unavailable")
    claim = claim_store.claim(prepared)
    if not claim.acquired:
        if claim.claim.state == "requested" and recover_pending:
            claim = ClaimResult(acquired=False, claim=claim_store.recover_unresolved(prepared))
        if claim.claim.state == "available":
            return _unavailable_evidence(
                prepared,
                "second-opinion result is already durable; load the consumer artifact instead of redispatching",
            )
        return _unavailable_evidence(prepared, claim.claim.status_note or INTERRUPTED_DISPATCH_NOTE)

    try:
        dispatched = engine_dispatch.dispatch(
            prepared.resolution,
            runner=_normalized_runner(runner),
            ledger=ledger,
            subplot_id=subplot_id,
            at=at,
            gated=False,
            session_id=prepared.execution_id,
            execution_id=prepared.execution_id,
            intent="second-opinion",
            role_kind="advisory-reviewer",
        )
    except Exception:  # noqa: BLE001 - external runner failures must remain nonblocking advisory data.
        return _mark_unavailable_evidence(
            prepared,
            claim_store=claim_store,
            note=UNUSABLE_DISPATCH_NOTE,
        )
    if isinstance(dispatched, engine_dispatch.RequeueDisposition):
        return _mark_unavailable_evidence(
            prepared,
            claim_store=claim_store,
            note=UNUSABLE_DISPATCH_NOTE,
        )
    if dispatched.halt is not None:
        return _mark_unavailable_evidence(
            prepared,
            claim_store=claim_store,
            note=_terminal_dispatch_note(dispatched),
        )
    if not dispatched.source_findings:
        return _mark_unavailable_evidence(
            prepared,
            claim_store=claim_store,
            note=EMPTY_OPINION_NOTE,
        )
    return dispatched


def reconcile_second_opinion(
    prepared: PreparedSecondOpinion,
    evidence: engine_dispatch.AdvisoryEvidence,
    *,
    adjudicator_id: str,
    items: Iterable[reconcile.ReconciliationItem],
) -> ReconciledOpinion:
    """Bind Claude's typed reconciliation to the exact advisory dispatch."""
    if evidence.intent != "second-opinion" or evidence.role_kind != "advisory-reviewer":
        raise SecondOpinionError(
            "second-opinion reconciliation requires advisory-reviewer evidence"
        )
    if evidence.execution_id != prepared.execution_id:
        raise SecondOpinionError("second-opinion evidence execution_id disagrees with request")
    if evidence.halt is not None:
        raise SecondOpinionError("halted second-opinion evidence cannot be reconciled")
    if not evidence.source_findings:
        raise SecondOpinionError(
            "empty second-opinion findings are unavailable, not reconcilable opinion"
        )
    result = reconcile.build_result(
        reconciliation_id=prepared.reconciliation_id,
        execution_id=prepared.execution_id,
        intent="second-opinion",
        adjudicator_id=adjudicator_id,
        evidence_digest=evidence.evidence_digest,
        source_finding_ids=evidence.source_finding_ids,
        items=tuple(items),
    )
    result.require_ready()
    if result.evidence_digest != evidence.evidence_digest:
        raise SecondOpinionError(
            "reconciliation evidence digest disagrees with dispatched evidence"
        )
    return ReconciledOpinion(
        prepared=prepared,
        evidence=replace(evidence, verified_by_claude=True),
        reconciliation=result,
    )


def adjudicate_finding(
    reconciled: ReconciledOpinion,
    *,
    adjudicator_id: str,
    decision: Literal["keep", "downgrade", "dismiss"],
    rationale: str,
    final_severity: Severity,
) -> ClaudeAdjudication:
    """Validate the closed keep/downgrade/dismiss contract for the source finding."""
    original = reconciled.prepared.finding.severity
    if decision == "keep":
        if final_severity != original:
            raise SecondOpinionError("keep must preserve the original severity")
        status: Literal["active", "dismissed"] = "active"
    elif decision == "downgrade":
        if original == "P3" or _SEVERITIES.index(final_severity) <= _SEVERITIES.index(original):
            raise SecondOpinionError("downgrade requires a strictly lower active severity")
        status = "active"
    elif decision == "dismiss":
        if final_severity != original:
            raise SecondOpinionError("dismiss must preserve original severity for audit")
        status = "dismissed"
    else:
        raise SecondOpinionError(f"unsupported adjudication decision {decision!r}")
    return ClaudeAdjudication(
        adjudicator_id=adjudicator_id,
        decision=decision,
        rationale=rationale,
        final_severity=final_severity,
        final_status=status,
    )


def external_opinion_projection(
    prepared: PreparedSecondOpinion,
    *,
    state: OpinionState,
    reconciled: ReconciledOpinion | None = None,
    status_note: str | None = None,
    request_claimed: bool = False,
) -> dict[str, Any]:
    """Serialize the closed optional review projection with opaque finding content."""
    if state not in {"recommended", "requested", "available", "unavailable", "declined"}:
        raise SecondOpinionError(f"unsupported external opinion state {state!r}")
    if status_note is not None:
        _bounded_bytes(status_note, MAX_STATUS_NOTE_BYTES, "status_note")
    if state == "available" and reconciled is None:
        raise SecondOpinionError("available second opinion requires reconciled evidence")
    if state != "available" and reconciled is not None:
        raise SecondOpinionError("only available second opinion may carry reconciled evidence")
    if state in {"requested", "available"} and not request_claimed:
        raise SecondOpinionError(f"{state} second opinion requires a durable request claim")
    if state in {"recommended", "declined"} and request_claimed:
        raise SecondOpinionError(f"{state} second opinion cannot carry a request claim")
    projection: dict[str, Any] = {
        "state": state,
        "intent": "second-opinion",
        "role_kind": "advisory-reviewer",
        "requested_by": prepared.requested_by,
        "reason": prepared.reason,
    }
    if request_claimed:
        projection["chaperone_tier"] = {
            "model": prepared.chaperone_model,
            "effort": prepared.chaperone_effort,
        }
        projection["request_id"] = prepared.request_id
        projection["request_digest"] = prepared.request_digest
        projection["execution_id"] = prepared.execution_id
        projection["reconciliation_id"] = prepared.reconciliation_id
        if prepared.resolution is not None:
            projection["engine_id"] = prepared.resolution.engine_id
            projection["variant"] = prepared.resolution.variant
        if prepared.egress_policy is not None:
            projection["egress_policy"] = prepared.egress_policy
    if status_note is not None:
        projection["status_note"] = status_note
    if reconciled is not None:
        projection["evidence_digest"] = reconciled.evidence.evidence_digest
        projection["findings"] = [
            {
                "source_finding_id": item.source_finding_id,
                "digest": item.digest,
                "content": item.content,
            }
            for item in reconciled.evidence.source_findings
        ]
        projection["verified_by_claude"] = reconciled.evidence.verified_by_claude
    return projection


def claude_adjudication_projection(value: ClaudeAdjudication) -> dict[str, str]:
    return {
        "adjudicator_id": value.adjudicator_id,
        "decision": value.decision,
        "rationale": value.rationale,
        "final_severity": value.final_severity,
        "final_status": value.final_status,
    }


def is_blocking_finding(*, severity: str, status: str, pre_existing: bool) -> bool:
    """Return the existing verdict input without consulting external-opinion metadata."""
    return not pre_existing and status == "active" and severity in {"P0", "P1"}


def append_reconciliation_once(
    ledger: run_ledger.RunLedger,
    result: reconcile.ReconciliationResult,
    *,
    action: reconcile.ReconciliationAction | str,
    subplot_id: str,
    at: str,
) -> dict[str, Any]:
    """Append one recovery-safe reconciliation transition, reusing an exact existing transition."""
    typed_action = reconcile.ReconciliationAction(action)
    expected_hash = reconcile.canonical_result_hash(result)
    existing = [
        item
        for item in reconcile.read_reconciliation_facts(ledger)
        if item["reconciliation_id"] == result.reconciliation_id
    ]
    if existing:
        if any(item["result_hash"] != expected_hash for item in existing):
            raise SecondOpinionError("reconciliation identity already names a conflicting result")
        matching = [item for item in existing if item["action"] == typed_action.value]
        if matching:
            return matching[0]
    try:
        return reconcile.append_reconciliation_fact(
            ledger,
            result,
            action=typed_action,
            subplot_id=subplot_id,
            at=at,
        )
    except reconcile.ReconciliationError as exc:
        raise SecondOpinionError(str(exc)) from exc


def complete_second_opinion(
    reconciled: ReconciledOpinion,
    *,
    claim_store: SecondOpinionClaimStore,
    ledger: run_ledger.RunLedger,
    subplot_id: str,
    at: str,
    persist_available_artifact: Callable[[], None],
) -> tuple[dict[str, Any], dict[str, Any]]:
    """Durably complete reconcile -> artifact -> available -> apply without replaying a runner.

    ``persist_available_artifact`` belongs to the consuming review/work stage and must atomically
    write the enriched artifact carrying the raw opinion. A retry with that durable result may call
    this helper again: existing facts and an ``available`` claim are reused, while a missing final
    transition is appended exactly once.
    """
    reconcile_fact = append_reconciliation_once(
        ledger,
        reconciled.reconciliation,
        action="reconcile",
        subplot_id=subplot_id,
        at=at,
    )
    claim = claim_store.read(reconciled.prepared.request_id)
    if claim is None:
        raise SecondOpinionError("second-opinion completion requires a pre-dispatch claim")
    _assert_claim_matches_prepared(claim, reconciled.prepared)
    if claim.state == "requested":
        persist_available_artifact()
        claim_store.mark_available(reconciled.prepared)
    elif claim.state != "available":
        raise SecondOpinionError("unavailable second-opinion request cannot be completed")
    apply_fact = append_reconciliation_once(
        ledger,
        reconciled.reconciliation,
        action="apply",
        subplot_id=subplot_id,
        at=at,
    )
    return reconcile_fact, apply_fact


def _normalized_runner(runner: engine_dispatch.Runner) -> engine_dispatch.Runner:
    def invoke(invocation: dict[str, Any]) -> dict[str, Any]:
        result = runner(invocation)
        if not isinstance(result, dict):
            raise engine_dispatch.DispatchError("second-opinion runner must return an object")
        normalized = dict(result)
        status = normalized.get("status")
        if isinstance(status, str):
            normalized["status"] = _STATUS_MAP.get(status, status)
        return normalized

    return invoke


def _mark_unavailable_evidence(
    prepared: PreparedSecondOpinion,
    *,
    claim_store: SecondOpinionClaimStore,
    note: str,
) -> engine_dispatch.AdvisoryEvidence:
    claim_store.mark_unavailable(prepared, note=note)
    return _unavailable_evidence(prepared, note)


def _terminal_dispatch_note(evidence: engine_dispatch.AdvisoryEvidence) -> str:
    """Project terminal runner state into bounded metadata without retaining runner text."""
    status = evidence.provenance.get("status")
    if isinstance(status, str) and status in engine_dispatch.FAILURE_STATUSES:
        return f"second-opinion dispatch {status}"
    return UNUSABLE_DISPATCH_NOTE


def _unavailable_evidence(
    prepared: PreparedSecondOpinion,
    reason: str,
) -> engine_dispatch.AdvisoryEvidence:
    _bounded_bytes(reason, MAX_STATUS_NOTE_BYTES, "unavailable reason")
    engine_id = prepared.resolution.engine_id if prepared.resolution is not None else "unavailable"
    variant = prepared.resolution.variant if prepared.resolution is not None else "unavailable"
    return engine_dispatch.AdvisoryEvidence(
        engine_id=engine_id,
        variant=variant,
        evidence="",
        provenance={
            "engine": engine_id,
            "variant": variant,
            "status": "unavailable",
            "note": reason,
        },
        execution_id=prepared.execution_id,
        intent="second-opinion",
        role_kind="advisory-reviewer",
        halt=reason,
    )


def _render_context(finding: FindingSnapshot, reason: str) -> str:
    if len(finding.excerpts) > MAX_EXCERPTS:
        raise SecondOpinionError(f"second-opinion context exceeds MAX_EXCERPTS={MAX_EXCERPTS}")
    for excerpt in finding.excerpts:
        if len(excerpt.content.encode("utf-8")) > MAX_EXCERPT_BYTES:
            raise SecondOpinionError(
                f"excerpt {excerpt.path!r} exceeds MAX_EXCERPT_BYTES={MAX_EXCERPT_BYTES}"
            )
    return _canonical_json(finding.to_context_dict(reason=reason))


def _contains_sensitive_content(finding: FindingSnapshot, reason: str) -> bool:
    """Fail closed for clear credentials and tenant/customer markers in egressable text."""
    values = (
        finding.title,
        finding.why_it_matters,
        *finding.evidence,
        finding.suggested_fix or "",
        reason,
        *(excerpt.content for excerpt in finding.excerpts),
    )
    return any(
        pattern.search(value) is not None
        for value in values
        for pattern in _SENSITIVE_CONTENT_PATTERNS
    )


def _target_failure_streak(attempts: tuple[WorkAttempt, ...], target: str) -> tuple[int, str]:
    """Return a target's consecutive failure count and the epoch-start attempt ID."""
    normalized = normalize_pytest_target(target)
    streak: list[WorkAttempt] = []
    for attempt in reversed(attempts):
        if attempt.result != "fail" or normalized not in attempt.failing_test_files:
            break
        streak.append(attempt)
    if not streak:
        raise WorkSecondOpinionStateError(
            "target streak requires a current matching failed attempt"
        )
    return len(streak), streak[-1].attempt_id


def _work_offer_id(round: int, target: str, epoch_attempt_id: str) -> str:
    digest = _sha256(
        _canonical_json(
            {
                "round": round,
                "target": normalize_pytest_target(target),
                "streak_epoch_attempt_id": epoch_attempt_id,
            }
        )
    )
    return f"work-second-opinion:{digest}"


def _work_offer_by_id(state: WorkSecondOpinionState, offer_id: str) -> WorkOffer:
    _bounded_id(offer_id, "offer_id")
    for offer in state.offers:
        if offer.offer_id == offer_id:
            return offer
    raise WorkSecondOpinionStateError(f"unknown work second-opinion offer {offer_id!r}")


def _replace_work_offer(
    state: WorkSecondOpinionState, replacement: WorkOffer
) -> WorkSecondOpinionState:
    return replace(
        state,
        offers=tuple(
            replacement if offer.offer_id == replacement.offer_id else offer
            for offer in state.offers
        ),
    )


def _expire_reset_work_offers(
    state: WorkSecondOpinionState,
    attempt: WorkAttempt,
) -> WorkSecondOpinionState:
    """Close only unresolved offers whose target's streak has just reset."""
    active_targets = set(attempt.failing_test_files) if attempt.result == "fail" else set()
    offers = tuple(
        replace(offer, disposition="unavailable")
        if offer.disposition == "offered" and offer.target not in active_targets
        else offer
        for offer in state.offers
    )
    return replace(state, offers=offers)


def _require_active_work_offer_streak(state: WorkSecondOpinionState, offer: WorkOffer) -> None:
    """Fail closed if a loaded older sidecar still exposes an offer after a reset boundary."""
    if offer.disposition != "offered":
        return
    if not state.attempts:
        raise WorkSecondOpinionStateError("work offer no longer has an active failure streak")
    latest = state.attempts[-1]
    if latest.result != "fail" or offer.target not in latest.failing_test_files:
        raise WorkSecondOpinionStateError("work offer no longer has an active failure streak")
    streak, epoch = _target_failure_streak(state.attempts, offer.target)
    if streak < 3 or epoch != offer.streak_epoch_attempt_id:
        raise WorkSecondOpinionStateError("work offer no longer has an active failure streak")


def _assert_claim_matches_prepared(claim: RequestClaim, prepared: PreparedSecondOpinion) -> None:
    if (
        claim.request_digest != prepared.request_digest
        or claim.execution_id != prepared.execution_id
        or claim.reconciliation_id != prepared.reconciliation_id
    ):
        raise SecondOpinionError("claim identity disagrees with prepared second-opinion request")


def _bounded_id(value: Any, field: str) -> str:
    result = _nonempty_string(value, field)
    if len(result.encode("utf-8")) > reconcile.MAX_ID_BYTES:
        raise SecondOpinionError(f"{field} exceeds {reconcile.MAX_ID_BYTES} bytes")
    return result


def _bounded_bytes(value: Any, limit: int, field: str) -> str:
    result = _nonempty_string(value, field)
    if len(result.encode("utf-8")) > limit:
        raise SecondOpinionError(f"{field} exceeds {limit} bytes")
    return result


def _nonempty_string(value: Any, field: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise SecondOpinionError(f"{field} must be a non-empty string")
    if any(ord(char) < 32 and char not in {"\n", "\t"} for char in value):
        raise SecondOpinionError(f"{field} contains a control character")
    return value


def _repo_relative_path(value: Any) -> str:
    path = _nonempty_string(value, "excerpt path")
    if "\\" in path:
        raise SecondOpinionError("excerpt path must use POSIX separators")
    parsed = PurePosixPath(path)
    if parsed.is_absolute() or ".." in parsed.parts:
        raise SecondOpinionError("excerpt path must be repository-relative without traversal")
    return path


def _positive_line(value: Any, field: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value <= 0:
        raise SecondOpinionError(f"{field} must be a positive integer")
    return cast(int, value)


def normalize_pytest_target(value: Any) -> str:
    """Normalize a repo-relative pytest node ID to its test-file target, rejecting traversal."""
    raw = _nonempty_string(value, "pytest target")
    path = raw.split("::", 1)[0].replace("\\", "/")
    while path.startswith("./"):
        path = path[2:]
    if not path or ":" in path:
        raise WorkSecondOpinionStateError(
            "pytest target must contain a repository-relative file path"
        )
    parsed = PurePosixPath(path)
    if parsed.is_absolute() or ".." in parsed.parts or parsed.name in {"", ".", ".."}:
        raise WorkSecondOpinionStateError(
            "pytest target must be repository-relative without traversal"
        )
    if parsed.suffix != ".py":
        raise WorkSecondOpinionStateError("pytest target must name a Python test file")
    return parsed.as_posix()


def _canonical_json(value: Mapping[str, Any]) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def _sha256(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()
