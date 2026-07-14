#!/usr/bin/env python3
"""Envelope tokens — the revocable merge-authorization credential for #449.

The #380 ``IntentEnvelope`` records the operator's run-start posture but **authorizes
nothing by itself** (its own threat model says so). This module is the credential layer
that #449 adds on top: a durable, expiring, immediately-revocable **token** that binds
one outcome's committed envelope content to a merge-only authorization scope. The
reversibility certificate's ``AUTONOMOUS_UNDER_ENVELOPE`` write class
(``reversibility_certificate.authorize_write_under_envelope``) is inert unless a token
from this store checks out — fresh, on disk, at authorization time.

Store layout (one lane per outcome store, git-ignored, machine-local):

    <store.root>/envelope-tokens/<token_id>.json          — the token (write-once)
    <store.root>/envelope-tokens/<token_id>.revoked.json  — revocation marker (write-once)

Status is **derived on every read** (active / expired / revoked / malformed) — nothing
caches an "authorized" verdict. ``check_token`` re-reads both files per call, so a
revocation is effective on the very next authorization attempt (R4: no grace window,
no cached-authorized state).

Token binding (all must match at check time, every check):

* ``outcome_id`` — the outcome whose store this lane belongs to.
* ``envelope_id`` — ``sha256:<hex>`` content fingerprint of the committed envelope. Any
  posture renegotiation (a #433 ``repost``) changes the committed content, so tokens
  minted under the previous posture stop matching — even an A->B->A round trip is a new
  era because ``intent_revision`` is also bound (below).
* ``intent_revision`` — the #433 revision the token was minted under. Bound in addition
  to the fingerprint because the ``save_spec`` check-then-write residual (documented at
  ``outcome.save_spec``) means a revision number alone can be minted twice; content +
  revision together are strictly narrower than either alone.
* ``scope`` — exactly ``"merge"`` in v1. Deploy is out of scope (#449 non-goal); a
  ``"deploy"``-scoped token fails validation at mint AND at check.
* ``expires_at`` — a token at or past its expiry no longer authorizes (at-expiry
  exhausts, mirroring ``authorize_spend``'s at-ceiling rule).

Threat model — read before trusting a token:

* **Minting is self-attested.** ``issued_by`` is a label; nothing here verifies a human
  operator ran the mint CLI. The trust boundary is the local filesystem — the same
  boundary as every other ``.saga``/store artifact (gate records, approvals, ledgers).
  What the token adds over the self-attested posture record: an expiry, an immediate
  revocation verb, binding to one exact envelope content + revision + outcome, and a
  per-merge attribution trail. What it cannot prove: the biological identity of the
  minter. Anyone with write access to the store can mint or revoke; this module is not
  a defense against a hostile local writer.
* **Fail closed, never enumerate.** An unknown key, a missing key, a wrong value type,
  a naive (timezone-less) timestamp, or an unreadable file is an *invalid token*, never
  a shrug. ``resolve_merge_token`` fails the WHOLE lane closed when any file in it is
  malformed — a corrupt artifact in the authorization lane means the lane is not
  trustworthy — and GATEs on ambiguity (more than one active matching token) rather
  than picking one.
* Gate records (#371) are **not consulted** in v1: this token is CLI-minted, not
  minted from an operator's gate answer. A future attended flow that mints tokens from
  a live gate-record answer must classify with ``gate_record.is_operator_answerer``
  (carried-forward/absence provenance never mints) — that flow is the issuance
  companion issue, not this module.

House pattern: pure functions over explicit values, lazy sibling imports, no I/O at
import. Requirement traceability: #449 R1–R4 (with ``reversibility_certificate``).
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import secrets
import sys
from collections.abc import Mapping
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parent))

SCHEMA_VERSION = 1

SCOPE_MERGE = "merge"
TOKEN_SCOPES = (SCOPE_MERGE,)  # closed vocabulary — v1 is merge-only (#449 non-goal: deploy)

TOKENS_LANE = "envelope-tokens"

_TOKEN_KEYS = frozenset(
    {
        "schema_version",
        "token_id",
        "envelope_id",
        "outcome_id",
        "intent_revision",
        "scope",
        "issued_at",
        "expires_at",
        "issued_by",
    }
)

_REVOCATION_KEYS = frozenset({"token_id", "revoked_at", "reason", "revoked_by"})

_TOKEN_ID_RE = re.compile(r"^[A-Za-z0-9._-]{1,100}$")
_FINGERPRINT_RE = re.compile(r"^sha256:[0-9a-f]{64}$")


class EnvelopeTokenError(ValueError):
    """Raised for a malformed token, marker, or mint/revoke misuse (fail closed)."""


def _intent_envelope():  # lazy: pulls the fleet_commons shim (file I/O) on first use
    import intent_envelope as _m  # noqa: PLC0415

    return _m


def tokens_dir(store_root: Path | str) -> Path:
    """The token lane under one outcome store's root (created on demand by writers)."""
    return Path(store_root) / TOKENS_LANE


# ---------------------------------------------------------------------------
# Time — timezone-aware ISO-8601 only (a naive timestamp is an error)
# ---------------------------------------------------------------------------


def _parse_ts(value: Any, where: str) -> datetime:
    if not isinstance(value, str) or not value:
        raise EnvelopeTokenError(f"{where} must be a non-empty ISO-8601 string, got {value!r}")
    try:
        parsed = datetime.fromisoformat(value)
    except ValueError as exc:
        raise EnvelopeTokenError(f"{where} is not ISO-8601: {value!r}") from exc
    if parsed.tzinfo is None:
        raise EnvelopeTokenError(
            f"{where} must be timezone-aware ({value!r} is naive) — fail closed, never guess a zone"
        )
    return parsed


def _now_dt(now: str | None) -> datetime:
    if now is None:
        return datetime.now(UTC)
    return _parse_ts(now, "now")


# ---------------------------------------------------------------------------
# Envelope fingerprint — content-addressed identity for a committed envelope
# ---------------------------------------------------------------------------


def envelope_fingerprint(intent: Mapping[str, Any]) -> str:
    """``sha256:<hex>`` of the canonical JSON of a schema-VALID committed envelope.

    The dict is round-tripped through the canonical ``IntentEnvelope`` schema first, so
    an invalid envelope raises (fail closed) and key order / formatting can never fork
    the identity of the same posture.
    """
    envelope_mod = _intent_envelope()
    envelope = envelope_mod.IntentEnvelope.from_dict(dict(intent))
    canonical = json.dumps(envelope.to_dict(), sort_keys=True, separators=(",", ":"))
    return "sha256:" + hashlib.sha256(canonical.encode("utf-8")).hexdigest()


# ---------------------------------------------------------------------------
# Strict validation — closed schemas, exact keys, exact types
# ---------------------------------------------------------------------------


def _require_str(value: Any, where: str, *, allow_empty: bool = False) -> str:
    if not isinstance(value, str) or (not allow_empty and not value):
        raise EnvelopeTokenError(f"{where} must be a non-empty string, got {value!r}")
    return value


def _require_int(value: Any, where: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        raise EnvelopeTokenError(f"{where} must be an integer, got {value!r}")
    return value


def validate_token(data: Any, *, where: str = "envelope token") -> dict[str, Any]:
    """Strictly validate one token document. Exact keys, exact types — anything else raises."""
    if not isinstance(data, Mapping):
        raise EnvelopeTokenError(f"{where} must be a JSON object, got {type(data).__name__}")
    unknown = sorted(set(data) - _TOKEN_KEYS)
    missing = sorted(_TOKEN_KEYS - set(data))
    if unknown or missing:
        raise EnvelopeTokenError(
            f"{where}: schema v{SCHEMA_VERSION} is closed and exact — "
            f"unknown keys {unknown}, missing keys {missing}"
        )
    if _require_int(data["schema_version"], f"{where}.schema_version") != SCHEMA_VERSION:
        raise EnvelopeTokenError(
            f"{where}.schema_version {data['schema_version']!r} is not the supported "
            f"{SCHEMA_VERSION} — migrate the token, do not guess"
        )
    token_id = _require_str(data["token_id"], f"{where}.token_id")
    if not _TOKEN_ID_RE.fullmatch(token_id):
        raise EnvelopeTokenError(
            f"{where}.token_id {token_id!r} must match {_TOKEN_ID_RE.pattern} (filename-safe)"
        )
    envelope_id = _require_str(data["envelope_id"], f"{where}.envelope_id")
    if not _FINGERPRINT_RE.fullmatch(envelope_id):
        raise EnvelopeTokenError(
            f"{where}.envelope_id {envelope_id!r} must be a sha256:<64-hex> fingerprint"
        )
    _require_str(data["outcome_id"], f"{where}.outcome_id")
    revision = _require_int(data["intent_revision"], f"{where}.intent_revision")
    if revision < 0:
        raise EnvelopeTokenError(f"{where}.intent_revision must be >= 0, got {revision}")
    scope = _require_str(data["scope"], f"{where}.scope")
    if scope not in TOKEN_SCOPES:
        raise EnvelopeTokenError(
            f"{where}.scope {scope!r} not in {TOKEN_SCOPES} — v1 is merge-only (#449 non-goal)"
        )
    issued = _parse_ts(data["issued_at"], f"{where}.issued_at")
    expires = _parse_ts(data["expires_at"], f"{where}.expires_at")
    if expires <= issued:
        raise EnvelopeTokenError(
            f"{where}: expires_at {data['expires_at']!r} must be strictly after "
            f"issued_at {data['issued_at']!r}"
        )
    _require_str(data["issued_by"], f"{where}.issued_by", allow_empty=True)
    return dict(data)


def _validate_revocation(data: Any, *, where: str) -> dict[str, Any]:
    if not isinstance(data, Mapping):
        raise EnvelopeTokenError(f"{where} must be a JSON object, got {type(data).__name__}")
    unknown = sorted(set(data) - _REVOCATION_KEYS)
    missing = sorted(_REVOCATION_KEYS - set(data))
    if unknown or missing:
        raise EnvelopeTokenError(
            f"{where}: revocation marker is closed and exact — "
            f"unknown keys {unknown}, missing keys {missing}"
        )
    _require_str(data["token_id"], f"{where}.token_id")
    _parse_ts(data["revoked_at"], f"{where}.revoked_at")
    _require_str(data["reason"], f"{where}.reason")
    _require_str(data["revoked_by"], f"{where}.revoked_by", allow_empty=True)
    return dict(data)


# ---------------------------------------------------------------------------
# Write-once store primitives (mirrors board_progression._write_once)
# ---------------------------------------------------------------------------


def _write_once(path: Path, content: str) -> bool:
    import contextlib  # noqa: PLC0415
    import os  # noqa: PLC0415

    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(f"{path.name}.tmp.{os.getpid()}")
    tmp.write_text(content, encoding="utf-8")
    try:
        os.link(tmp, path)  # atomic create; raises FileExistsError if path is taken
        return True
    except FileExistsError:
        return False
    finally:
        with contextlib.suppress(FileNotFoundError):
            tmp.unlink()


def _token_path(lane: Path, token_id: str) -> Path:
    if not _TOKEN_ID_RE.fullmatch(token_id):
        raise EnvelopeTokenError(f"token_id {token_id!r} must match {_TOKEN_ID_RE.pattern}")
    return lane / f"{token_id}.json"


def _revocation_path(lane: Path, token_id: str) -> Path:
    return _token_path(lane, token_id).with_name(f"{token_id}.revoked.json")


# ---------------------------------------------------------------------------
# Mint / revoke — the operator verbs (both seams validate; lesson 10)
# ---------------------------------------------------------------------------


def mint_token(
    lane: Path,
    *,
    outcome_id: str,
    envelope: Mapping[str, Any] | None,
    intent_revision: int,
    ttl_hours: float | None = None,
    expires_at: str | None = None,
    issued_by: str = "",
    token_id: str | None = None,
    now: str | None = None,
) -> dict[str, Any]:
    """Mint one merge-scope token bound to a committed envelope (write-once).

    Fail-closed authoring rules:
    * the spec must carry a committed envelope (``envelope`` is its ``intent`` dict) —
      an envelope-less outcome has nothing to authorize against;
    * the envelope's ``ceremony_gates.merge`` must be ``"auto"`` — minting a merge
      token against a gate posture is an authoring error, refused at the mint seam
      exactly as ``check_token`` refuses it at the read seam;
    * exactly one of ``ttl_hours`` / ``expires_at``, strictly in the future.
    """
    if envelope is None:
        raise EnvelopeTokenError(
            f"outcome {outcome_id!r} has no committed intent envelope — capture one "
            "(outcome set-intent / start --intent-file) before minting a merge token"
        )
    envelope_mod = _intent_envelope()
    parsed = envelope_mod.IntentEnvelope.from_dict(dict(envelope))
    if parsed.ceremony_gates.merge != envelope_mod.AUTO:
        raise EnvelopeTokenError(
            f"envelope ceremony_gates.merge is {parsed.ceremony_gates.merge!r} — a merge "
            'token may only be minted against a committed merge: "auto" posture'
        )
    now_dt = _now_dt(now)
    if (ttl_hours is None) == (expires_at is None):
        raise EnvelopeTokenError("mint_token needs exactly one of ttl_hours / expires_at")
    if ttl_hours is not None:
        if isinstance(ttl_hours, bool) or not isinstance(ttl_hours, (int, float)) or ttl_hours <= 0:
            raise EnvelopeTokenError(f"ttl_hours must be a number > 0, got {ttl_hours!r}")
        expires_dt = now_dt + timedelta(hours=float(ttl_hours))
    else:
        expires_dt = _parse_ts(expires_at, "expires_at")
    if expires_dt <= now_dt:
        raise EnvelopeTokenError(
            f"expires_at {expires_dt.isoformat()} is not in the future (now {now_dt.isoformat()})"
        )
    token = validate_token(
        {
            "schema_version": SCHEMA_VERSION,
            "token_id": token_id if token_id is not None else f"emt-{secrets.token_hex(8)}",
            "envelope_id": envelope_fingerprint(envelope),
            "outcome_id": outcome_id,
            "intent_revision": intent_revision,
            "scope": SCOPE_MERGE,
            "issued_at": now_dt.isoformat(),
            "expires_at": expires_dt.isoformat(),
            "issued_by": issued_by,
        }
    )
    path = _token_path(lane, str(token["token_id"]))
    if not _write_once(path, json.dumps(token, indent=2, sort_keys=False) + "\n"):
        raise EnvelopeTokenError(f"token {token['token_id']!r} already exists at {path}")
    return token


def revoke_token(
    lane: Path,
    token_id: str,
    *,
    reason: str,
    revoked_by: str = "",
    now: str | None = None,
) -> dict[str, Any]:
    """Revoke one token — effective on the very next check (R4), write-once, monotonic.

    Revoking a token that does not exist is an error (fail closed — a typo must not
    read as a successful revocation). Revoking an already-revoked token returns the
    ORIGINAL marker with ``already_revoked: true`` — repeat revocation never fails and
    never rewrites history.
    """
    if not _token_path(lane, token_id).exists():
        raise EnvelopeTokenError(f"cannot revoke unknown token {token_id!r} (no file in {lane})")
    marker_path = _revocation_path(lane, token_id)
    marker = _validate_revocation(
        {
            "token_id": token_id,
            "revoked_at": _now_dt(now).isoformat(),
            "reason": _require_str(reason, "reason"),
            "revoked_by": revoked_by,
        },
        where="revocation",
    )
    if _write_once(marker_path, json.dumps(marker, indent=2, sort_keys=False) + "\n"):
        return {**marker, "already_revoked": False}
    existing = _validate_revocation(
        json.loads(marker_path.read_text(encoding="utf-8")),
        where=f"revocation marker {marker_path.name}",
    )
    return {**existing, "already_revoked": True}


# ---------------------------------------------------------------------------
# Check / resolve — the read seam (fresh disk reads on EVERY call; R3/R4)
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class TokenCheck:
    """One derived-on-read token verdict. ``malformed`` marks a token document that
    could not be strictly understood (vs. a well-formed token that merely fails a
    validity condition) — ``resolve_merge_token`` fails the whole lane closed on it."""

    valid: bool
    reason: str
    token_id: str = ""
    envelope_id: str = ""
    outcome_id: str = ""
    intent_revision: int | None = None
    expires_at: str = ""
    revoked: bool = False
    malformed: bool = False

    def to_dict(self) -> dict[str, Any]:
        return {
            "valid": self.valid,
            "reason": self.reason,
            "token_id": self.token_id,
            "envelope_id": self.envelope_id,
            "outcome_id": self.outcome_id,
            "intent_revision": self.intent_revision,
            "expires_at": self.expires_at,
            "revoked": self.revoked,
            "malformed": self.malformed,
        }


def check_token(
    lane: Path,
    token_id: str,
    *,
    expected_outcome_id: str,
    expected_envelope: Mapping[str, Any] | None,
    expected_intent_revision: int,
    now: str | None = None,
) -> TokenCheck:
    """Re-derive one token's validity from disk — nothing is cached (R3/R4).

    Every failure is a precise, operator-actionable reason. The expected values come
    from the CALLER's current view of the spec (its committed ``intent`` and
    ``intent_revision``); a token minted under any other envelope content, revision,
    or outcome does not authorize.
    """
    try:
        path = _token_path(lane, token_id)
    except EnvelopeTokenError as exc:
        return TokenCheck(False, str(exc), token_id=token_id, malformed=True)
    if not path.exists():
        return TokenCheck(False, f"no token {token_id!r} in {lane}", token_id=token_id)
    try:
        token = validate_token(
            json.loads(path.read_text(encoding="utf-8")), where=f"token {path.name}"
        )
    except (OSError, ValueError) as exc:  # ValueError covers JSONDecodeError + schema errors
        return TokenCheck(
            False,
            f"token {token_id!r} could not be strictly understood — failing closed: {exc}",
            token_id=token_id,
            malformed=True,
        )
    if token["token_id"] != token_id:
        return TokenCheck(
            False,
            f"token file {path.name} carries token_id {token['token_id']!r} — identity "
            "mismatch, failing closed",
            token_id=token_id,
            malformed=True,
        )
    base = {
        "token_id": str(token["token_id"]),
        "envelope_id": str(token["envelope_id"]),
        "outcome_id": str(token["outcome_id"]),
        "intent_revision": int(token["intent_revision"]),
        "expires_at": str(token["expires_at"]),
    }
    # Revocation FIRST (R4): a revoked token is dead regardless of any other condition.
    marker_path = _revocation_path(lane, token_id)
    if marker_path.exists():
        try:
            marker = _validate_revocation(
                json.loads(marker_path.read_text(encoding="utf-8")),
                where=f"revocation marker {marker_path.name}",
            )
        except (OSError, ValueError) as exc:
            return TokenCheck(
                False,
                f"token {token_id!r} has an unreadable revocation marker — failing "
                f"closed as revoked: {exc}",
                revoked=True,
                malformed=True,
                **base,  # type: ignore[arg-type]
            )
        return TokenCheck(
            False,
            f"token {token_id!r} revoked at {marker['revoked_at']}: {marker['reason']}",
            revoked=True,
            **base,  # type: ignore[arg-type]
        )
    now_dt = _now_dt(now)
    expires_dt = _parse_ts(token["expires_at"], "expires_at")
    if now_dt >= expires_dt:
        return TokenCheck(
            False,
            f"token {token_id!r} expired at {token['expires_at']} (now {now_dt.isoformat()})",
            **base,  # type: ignore[arg-type]
        )
    if token["outcome_id"] != expected_outcome_id:
        return TokenCheck(
            False,
            f"token {token_id!r} was issued for outcome {token['outcome_id']!r}, not "
            f"{expected_outcome_id!r}",
            **base,  # type: ignore[arg-type]
        )
    if expected_envelope is None:
        return TokenCheck(
            False,
            f"outcome {expected_outcome_id!r} has no committed intent envelope — nothing "
            "to authorize against",
            **base,  # type: ignore[arg-type]
        )
    envelope_mod = _intent_envelope()
    try:
        parsed = envelope_mod.IntentEnvelope.from_dict(dict(expected_envelope))
    except envelope_mod.IntentEnvelopeError as exc:
        return TokenCheck(
            False,
            f"the committed intent envelope is invalid — failing closed: {exc}",
            **base,  # type: ignore[arg-type]
        )
    if parsed.ceremony_gates.merge != envelope_mod.AUTO:
        return TokenCheck(
            False,
            f"committed ceremony_gates.merge is {parsed.ceremony_gates.merge!r} — the "
            "current posture does not permit autonomous merge",
            **base,  # type: ignore[arg-type]
        )
    if token["envelope_id"] != envelope_fingerprint(expected_envelope):
        return TokenCheck(
            False,
            f"token {token_id!r} was minted under a different envelope content "
            "(fingerprint mismatch) — the posture was renegotiated since; mint a fresh token",
            **base,  # type: ignore[arg-type]
        )
    if token["intent_revision"] != expected_intent_revision:
        return TokenCheck(
            False,
            f"token {token_id!r} was minted under intent_revision "
            f"{token['intent_revision']}, the spec is now at {expected_intent_revision} — "
            "mint a fresh token for the current era",
            **base,  # type: ignore[arg-type]
        )
    return TokenCheck(True, "active merge token", **base)  # type: ignore[arg-type]


def resolve_merge_token(
    lane: Path,
    *,
    outcome_id: str,
    envelope: Mapping[str, Any] | None,
    intent_revision: int,
    now: str | None = None,
) -> TokenCheck:
    """Resolve THE single active merge token for an outcome, or a fail-closed reason.

    * a malformed document anywhere in the lane fails the WHOLE lane closed;
    * zero valid tokens -> invalid, with each candidate's precise reason;
    * more than one valid token -> ambiguous -> invalid (never pick one; revoke extras).
    """
    if not lane.is_dir():
        return TokenCheck(False, f"no envelope-token lane at {lane} — no token ever minted")
    checks: list[TokenCheck] = []
    for path in sorted(lane.glob("*.json")):
        if path.name.endswith(".revoked.json"):
            continue
        check = check_token(
            lane,
            path.name[: -len(".json")],
            expected_outcome_id=outcome_id,
            expected_envelope=envelope,
            expected_intent_revision=intent_revision,
            now=now,
        )
        if check.malformed:
            return TokenCheck(
                False,
                f"envelope-token lane {lane} contains a document that cannot be strictly "
                f"understood — failing the whole lane closed: {check.reason}",
                token_id=check.token_id,
                malformed=True,
            )
        checks.append(check)
    valid = [c for c in checks if c.valid]
    if len(valid) == 1:
        return valid[0]
    if not checks:
        return TokenCheck(False, f"no tokens minted in {lane}")
    if not valid:
        reasons = "; ".join(f"{c.token_id}: {c.reason}" for c in checks)
        return TokenCheck(False, f"no active merge token ({len(checks)} present): {reasons}")
    ids = ", ".join(sorted(c.token_id for c in valid))
    return TokenCheck(
        False,
        f"ambiguous: {len(valid)} active merge tokens ({ids}) — refusing to pick one; "
        "revoke the extras",
    )


def authorize_merge_under_envelope(
    lane: Path,
    *,
    outcome_id: str,
    envelope: Mapping[str, Any] | None,
    intent_revision: int,
    other_gates_green: bool,
    token_id: str | None = None,
    now: str | None = None,
) -> Any:
    """The composed one-call authorization: fresh token check -> certificate verdict.

    This is the surface consumers call once per merge-class write attempt: the token is
    re-read from disk HERE, at authorization time (R3/R4), then handed to the pure
    ``reversibility_certificate.authorize_write_under_envelope`` together with the
    caller's other-gates fact. Returns the certificate's ``EnvelopeAuthorization``.
    """
    import reversibility_certificate as cert  # noqa: PLC0415

    if token_id is not None:
        check = check_token(
            lane,
            token_id,
            expected_outcome_id=outcome_id,
            expected_envelope=envelope,
            expected_intent_revision=intent_revision,
            now=now,
        )
    else:
        check = resolve_merge_token(
            lane,
            outcome_id=outcome_id,
            envelope=envelope,
            intent_revision=intent_revision,
            now=now,
        )
    return cert.authorize_write_under_envelope(
        cert.OpKind.MERGE_UNDER_ENVELOPE, check, other_gates_green=other_gates_green
    )


# ---------------------------------------------------------------------------
# Derived lane listing (operator audit)
# ---------------------------------------------------------------------------


def list_tokens(lane: Path, *, now: str | None = None) -> list[dict[str, Any]]:
    """Every token in the lane with its derived status (active/expired/revoked/malformed).

    Listing derives per-document status only (no envelope/outcome binding check — that
    needs a spec; use ``check``). Malformed documents are LISTED as malformed, not
    skipped, so an operator audit sees exactly what a resolver would fail closed on.
    """
    if not lane.is_dir():
        return []
    now_dt = _now_dt(now)
    rows: list[dict[str, Any]] = []
    for path in sorted(lane.glob("*.json")):
        if path.name.endswith(".revoked.json"):
            continue
        token_id = path.name[: -len(".json")]
        try:
            token = validate_token(
                json.loads(path.read_text(encoding="utf-8")), where=f"token {path.name}"
            )
        except (OSError, ValueError) as exc:
            rows.append({"token_id": token_id, "status": "malformed", "reason": str(exc)})
            continue
        if _revocation_path(lane, token_id).exists():
            status = "revoked"
        elif now_dt >= _parse_ts(token["expires_at"], "expires_at"):
            status = "expired"
        else:
            status = "active"
        rows.append({**token, "status": status})
    return rows


# ---------------------------------------------------------------------------
# CLI — the operator mint/revoke/check/list surface (no gh calls; store-local)
# ---------------------------------------------------------------------------


def _lane_from_args(args: argparse.Namespace) -> Path:
    if args.store_root:
        return tokens_dir(Path(args.store_root))
    import outcome_store  # noqa: PLC0415

    store = outcome_store.Store.for_outcome(args.outcome_id, Path(args.repo_root))
    return tokens_dir(store.root)


def _spec_values(spec_path: str) -> tuple[str, dict[str, Any] | None, int]:
    import outcome_spec  # noqa: PLC0415

    spec = outcome_spec.OutcomeSpec.from_json(Path(spec_path).read_text(encoding="utf-8"))
    spec.validate()
    return (spec.outcome_id, spec.intent, spec.intent_revision or 0)


def _cli_mint(args: argparse.Namespace) -> int:
    outcome_id, envelope, revision = _spec_values(args.outcome_spec)
    token = mint_token(
        _lane_from_args(args),
        outcome_id=outcome_id,
        envelope=envelope,
        intent_revision=revision,
        ttl_hours=args.ttl_hours,
        expires_at=args.expires_at,
        issued_by=args.issued_by,
        token_id=args.token_id,
        now=args.now,
    )
    print(json.dumps(token, indent=2))
    return 0


def _cli_revoke(args: argparse.Namespace) -> int:
    marker = revoke_token(
        _lane_from_args(args),
        args.token_id,
        reason=args.reason,
        revoked_by=args.revoked_by,
        now=args.now,
    )
    print(json.dumps(marker, indent=2))
    return 0


def _cli_check(args: argparse.Namespace) -> int:
    outcome_id, envelope, revision = _spec_values(args.outcome_spec)
    lane = _lane_from_args(args)
    if args.token_id:
        check = check_token(
            lane,
            args.token_id,
            expected_outcome_id=outcome_id,
            expected_envelope=envelope,
            expected_intent_revision=revision,
            now=args.now,
        )
    else:
        check = resolve_merge_token(
            lane,
            outcome_id=outcome_id,
            envelope=envelope,
            intent_revision=revision,
            now=args.now,
        )
    print(json.dumps(check.to_dict(), indent=2))
    return 0 if check.valid else 1


def _cli_list(args: argparse.Namespace) -> int:
    print(json.dumps(list_tokens(_lane_from_args(args), now=args.now), indent=2))
    return 0


def _add_lane_args(parser: argparse.ArgumentParser) -> None:
    parser.add_argument(
        "--store-root", default="", help="explicit outcome-store root (overrides --outcome-id)"
    )
    parser.add_argument(
        "--outcome-id", default="", help="outcome id (lane derived via the outcome store)"
    )
    parser.add_argument("--repo-root", default=".", help="repo root for store resolution")
    parser.add_argument("--now", default=None, help="ISO-8601 override of the clock (tests)")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="envelope_token",
        description="Mint / revoke / check the #449 envelope merge-authorization tokens.",
    )
    sub = parser.add_subparsers(dest="command", required=True)

    p_mint = sub.add_parser("mint", help="mint a merge token bound to a spec's committed envelope")
    _add_lane_args(p_mint)
    p_mint.add_argument("--outcome-spec", required=True, help="path to outcome-spec.json")
    p_mint.add_argument("--ttl-hours", type=float, default=None)
    p_mint.add_argument("--expires-at", default=None, help="ISO-8601 expiry (alt. to --ttl-hours)")
    p_mint.add_argument("--issued-by", default="")
    p_mint.add_argument("--token-id", default=None)
    p_mint.set_defaults(func=_cli_mint)

    p_revoke = sub.add_parser("revoke", help="revoke a token — effective on the next check (R4)")
    _add_lane_args(p_revoke)
    p_revoke.add_argument("token_id")
    p_revoke.add_argument("--reason", required=True)
    p_revoke.add_argument("--revoked-by", default="")
    p_revoke.set_defaults(func=_cli_revoke)

    p_check = sub.add_parser("check", help="derive a token's validity against a spec, fresh")
    _add_lane_args(p_check)
    p_check.add_argument("--outcome-spec", required=True, help="path to outcome-spec.json")
    p_check.add_argument("--token-id", default="", help="omit to resolve the single active token")
    p_check.set_defaults(func=_cli_check)

    p_list = sub.add_parser("list", help="list tokens with derived status (operator audit)")
    _add_lane_args(p_list)
    p_list.set_defaults(func=_cli_list)

    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    if not args.store_root and not args.outcome_id:
        print("error: one of --store-root / --outcome-id is required", file=sys.stderr)
        return 2
    try:
        return int(args.func(args))
    except (EnvelopeTokenError, OSError, ValueError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
