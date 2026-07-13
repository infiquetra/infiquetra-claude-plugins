#!/usr/bin/env python3
"""Evidence ledger: content-addressed, append-only custody log for verification evidence (#398).

`/qa` and `/code-review` write their durable ship verdicts as plain markdown files with no
clobber-guard today — a grounded, previously observed failure (a probe script overwrote a FAIL
evidence artifact with a later PASS,
``docs/plans/2026-07-03-plugin-fleet-grounding-brief.md:150-151``). This module is the mechanism
fix: every verdict artifact is content-addressed (sha256), written once, and recorded in a
hash-chained JSONL custody log so a later PASS can never silently overwrite an earlier FAIL, a
tamper is detectable, and a producer can never certify its own evidence.

Ledger home is **committed, per-saga**: ``docs/evidence/<saga-id>/`` (not the git-common-dir
cache ``outcome_store.py``/``manifest_store.py`` use) — a fresh clone must be able to verify the
custody chain, and custody belongs in PR history (KTD1, ``docs/plans/2026-07-12-evidence-ledger-
plan.md``). Identity is ``(check_id, reviewed_sha, attempt)`` (KTD2): a retry is a new attempt
that appends, never mutates; the reader flags a FAIL-then-PASS transition as a supersession
rather than a silent green. Each entry chains to the previous via a ``prev`` hash over the
previous entry's canonical JSON (KTD3), so tampering with the log itself — not just an artifact —
is detectable (git history alone is not sufficient: a local edit or force-push rewrites both).

This module reuses ``outcome_store``'s ``_write_once`` / ``_atomic_write`` / ``_safe_name``
(mirroring the ``manifest_store`` precedent) rather than modifying or duplicating them; the one
genuinely new primitive is the fsynced O_APPEND JSONL append below. Unlike ``outcome_store``'s
disposable local cache ledger (which heals a torn trailing line because a crash there is
recoverable from the spec), this ledger IS the committed evidence — a torn or malformed line
HALTs verification with the offending line number rather than being healed and silently
continued.

CLI::

    python3 evidence_ledger.py --repo-root <path> --saga-id <id> write \\
        --check-id <id> --reviewed-sha <40-char-sha> --producer <role> --verdict <verdict> \\
        --artifact-file <path> [--attempt N] [--payload <path-to-json>]
    python3 evidence_ledger.py --repo-root <path> --saga-id <id> freeze-criteria \\
        --check-id <id> --reviewed-sha <sha> --criteria-file <path>
    python3 evidence_ledger.py --repo-root <path> --saga-id <id> latest \\
        --check-id <id> --reviewed-sha <sha>
    python3 evidence_ledger.py --repo-root <path> --saga-id <id> verify-chain
    python3 evidence_ledger.py --repo-root <path> --saga-id <id> close \\
        --check-id <id> --reviewed-sha <sha> --verifier <role>
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import sys
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, cast

sys.path.insert(0, str(Path(__file__).resolve().parent))

import outcome_store  # noqa: E402

_SHA_LEN = 40
_HEX_DIGITS = set("0123456789abcdef")


class EvidenceLedgerError(ValueError):
    """An evidence-ledger operation was rejected (clobber, chain break, tamper, self-certify)."""


def _safe_name(name: str, *, what: str = "id") -> str:
    """Reject a name that would escape the store directory (parity with ``outcome_store``)."""
    try:
        return cast(str, outcome_store._safe_name(name, what=what))
    except outcome_store.OutcomeStoreError as exc:
        raise EvidenceLedgerError(str(exc)) from exc


def _validate_sha(sha: str) -> str:
    """A full 40-char hex SHA only — no short-SHA ambiguity in an integrity artifact."""
    lowered = sha.lower()
    if len(lowered) != _SHA_LEN or not set(lowered) <= _HEX_DIGITS:
        raise EvidenceLedgerError(
            f"reviewed_sha must be a full {_SHA_LEN}-char hex SHA, got {sha!r}"
        )
    return lowered


def _now() -> str:
    return datetime.now(UTC).isoformat()


def _sha256_hex(content: bytes) -> str:
    return hashlib.sha256(content).hexdigest()


def _canonical_json(obj: dict[str, Any]) -> str:
    return json.dumps(obj, sort_keys=True, separators=(",", ":"))


def _entry_hash(entry: dict[str, Any]) -> str:
    return _sha256_hex(_canonical_json(entry).encode("utf-8"))


@dataclass(frozen=True)
class Store:
    """A handle to one saga's committed evidence directory (``docs/evidence/<saga-id>/``)."""

    root: Path

    @classmethod
    def for_saga(cls, saga_id: str, repo_root: Path) -> Store:
        safe = _safe_name(saga_id, what="saga_id")
        return cls(root=repo_root / "docs" / "evidence" / safe)

    def ensure(self) -> Store:
        self.artifacts_dir.mkdir(parents=True, exist_ok=True)
        return self

    @property
    def ledger_path(self) -> Path:
        return self.root / "ledger.jsonl"

    @property
    def head_path(self) -> Path:
        return self.root / "ledger.head"

    @property
    def artifacts_dir(self) -> Path:
        return self.root / "artifacts"

    def criteria_path(self, check_id: str, reviewed_sha: str) -> Path:
        safe_check = _safe_name(check_id, what="check_id")
        safe_sha = _validate_sha(reviewed_sha)
        return self.root / f"criteria-{safe_check}-{safe_sha}.json"

    def artifact_path(self, content_hash: str) -> Path:
        return self.artifacts_dir / f"{content_hash}.md"


# ---------------------------------------------------------------------------
# Custody log: read (HALT on damage) + append (fsynced, O_APPEND)
# ---------------------------------------------------------------------------


def _read_lines_or_halt(path: Path) -> list[dict[str, Any]]:
    """Read every JSONL entry, HALTing (typed error) on a torn or malformed line.

    Unlike ``outcome_store.append_ledger``'s disposable cache (which heals a torn tail — a crash
    there is recoverable from the spec), this ledger is committed evidence: a damaged line is an
    integrity event, not routine crash noise, so it halts naming the offending line rather than
    silently dropping it.
    """
    if not path.exists():
        return []
    text = path.read_text(encoding="utf-8")
    if text == "":
        return []
    lines = text.split("\n")
    if lines[-1] != "":
        raise EvidenceLedgerError(
            f"custody log {path} has a torn trailing line (no newline) at line {len(lines)}"
        )
    entries: list[dict[str, Any]] = []
    for i, line in enumerate(lines[:-1], start=1):
        if not line:
            raise EvidenceLedgerError(f"custody log {path} has a blank line at {i}")
        try:
            entries.append(json.loads(line))
        except json.JSONDecodeError as exc:
            raise EvidenceLedgerError(f"custody log {path} malformed at line {i}: {exc}") from exc
    return entries


def _append_entry(store: Store, entry: dict[str, Any]) -> None:
    """Append one JSON record as a single fsynced ``O_APPEND`` line, then advance the head pointer.

    Committed evidence warrants the fsync ``outcome_store``'s disposable cache append skips — the
    entry must be durable on disk the moment a caller's commit can pick it up. A single
    ``os.write`` under ``PIPE_BUF`` is atomic with ``O_APPEND``, so concurrent appenders never
    interleave a partial line.

    The hash chain alone cannot detect tampering with the LAST entry (there is no successor
    entry whose ``prev`` would fail to match) — a lone-tail edit is exactly the "probe script
    overwrote the evidence" failure mode this module exists to catch. ``ledger.head`` closes that
    gap: it atomically records the hash of the most recently appended entry, so
    ``verify_chain`` can detect a tampered tail by comparing the recomputed hash of the last entry
    on disk against this independently-stored pointer.
    """
    store.root.mkdir(parents=True, exist_ok=True)
    payload = (_canonical_json(entry) + "\n").encode("utf-8")
    fd = os.open(store.ledger_path, os.O_WRONLY | os.O_CREAT | os.O_APPEND, 0o644)
    try:
        view = memoryview(payload)
        while view:
            written = os.write(fd, view)
            view = view[written:]
        os.fsync(fd)
    finally:
        os.close(fd)
    outcome_store._atomic_write(store.head_path, _entry_hash(entry))


# ---------------------------------------------------------------------------
# write() — content-addressed evidence entries (R1/R2/KTD2)
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class WriteResult:
    content_hash: str
    attempt: int
    artifact_path: Path
    entry: dict[str, Any]


def write(
    store: Store,
    *,
    check_id: str,
    reviewed_sha: str,
    producer: str,
    verdict: str,
    content: str,
    attempt: int | None = None,
    payload: dict[str, Any] | None = None,
) -> WriteResult:
    """Content-address ``content`` and append one custody entry.

    Identity is ``(check_id, reviewed_sha, attempt)``. Omitting ``attempt`` auto-assigns the next
    attempt number for this ``(check_id, reviewed_sha)`` group — a retry, never a mutation of a
    prior attempt. An explicit ``attempt`` colliding with an existing one is a no-op when the
    content is byte-identical (an idempotent replay) and rejected otherwise — the clobber R1
    forbids.
    """
    check_id = _safe_name(check_id, what="check_id")
    reviewed_sha = _validate_sha(reviewed_sha)
    store.ensure()
    entries = _read_lines_or_halt(store.ledger_path)
    same_identity = [
        e
        for e in entries
        if e.get("kind") == "evidence"
        and e.get("check_id") == check_id
        and e.get("reviewed_sha") == reviewed_sha
    ]
    content_hash = _sha256_hex(content.encode("utf-8"))

    if attempt is None:
        attempt = max((e["attempt"] for e in same_identity), default=0) + 1
    else:
        collision = next((e for e in same_identity if e["attempt"] == attempt), None)
        if collision is not None:
            if collision["hash"] == content_hash:
                return WriteResult(
                    content_hash=content_hash,
                    attempt=attempt,
                    artifact_path=store.artifact_path(content_hash),
                    entry=collision,
                )
            raise EvidenceLedgerError(
                f"attempt {attempt} for ({check_id}, {reviewed_sha}) is already recorded with a "
                f"different artifact (hash {collision['hash']} != {content_hash}) — refusing to "
                "clobber"
            )

    artifact_path = store.artifact_path(content_hash)
    outcome_store._write_once(artifact_path, content)

    prev_hash = _entry_hash(entries[-1]) if entries else None
    entry = {
        "seq": len(entries) + 1,
        "kind": "evidence",
        "prev": prev_hash,
        "check_id": check_id,
        "reviewed_sha": reviewed_sha,
        "attempt": attempt,
        "producer": producer,
        "verdict": verdict,
        "hash": content_hash,
        "artifact_path": str(artifact_path),
        "timestamp": _now(),
        "payload": payload or {},
    }
    _append_entry(store, entry)
    return WriteResult(
        content_hash=content_hash, attempt=attempt, artifact_path=artifact_path, entry=entry
    )


# ---------------------------------------------------------------------------
# freeze_criteria() — pre-registered, write-once pass/fail criteria (R4)
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class FreezeResult:
    content_hash: str
    criteria_path: Path
    entry: dict[str, Any]


def freeze_criteria(
    store: Store,
    *,
    check_id: str,
    reviewed_sha: str,
    criteria: dict[str, Any],
) -> FreezeResult:
    """Write-once the pass/fail criteria block for ``(check_id, reviewed_sha)``.

    Freezing is an intent-capture EVENT, not a value cache: a second freeze for the same identity
    is always rejected, even with identical content. Immutability across attempts then falls out
    structurally — the criteria file itself is written with ``outcome_store._write_once``, so
    nothing can edit it in place after the freeze.
    """
    check_id = _safe_name(check_id, what="check_id")
    reviewed_sha = _validate_sha(reviewed_sha)
    store.ensure()
    entries = _read_lines_or_halt(store.ledger_path)
    already_frozen = any(
        e.get("kind") == "criteria"
        and e.get("check_id") == check_id
        and e.get("reviewed_sha") == reviewed_sha
        for e in entries
    )
    if already_frozen:
        raise EvidenceLedgerError(
            f"criteria already frozen for ({check_id}, {reviewed_sha}) — freeze is one-time"
        )

    criteria_path = store.criteria_path(check_id, reviewed_sha)
    content = _canonical_json(criteria) + "\n"
    created = outcome_store._write_once(criteria_path, content)
    if not created:
        raise EvidenceLedgerError(f"criteria file {criteria_path} already exists on disk")

    content_hash = _sha256_hex(content.encode("utf-8"))
    prev_hash = _entry_hash(entries[-1]) if entries else None
    entry = {
        "seq": len(entries) + 1,
        "kind": "criteria",
        "prev": prev_hash,
        "check_id": check_id,
        "reviewed_sha": reviewed_sha,
        "hash": content_hash,
        "criteria_path": str(criteria_path),
        "timestamp": _now(),
    }
    _append_entry(store, entry)
    return FreezeResult(content_hash=content_hash, criteria_path=criteria_path, entry=entry)


# ---------------------------------------------------------------------------
# latest() — supersession reader (R3)
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class LatestResult:
    check_id: str
    reviewed_sha: str
    verdict: str | None
    attempt: int | None
    superseded_fail: bool
    history: list[dict[str, Any]]


def latest(store: Store, *, check_id: str, reviewed_sha: str) -> LatestResult:
    """Return the latest verdict for ``(check_id, reviewed_sha)`` plus its full attempt history.

    ``superseded_fail`` is True exactly when an earlier attempt FAILed and the latest attempt did
    not — surfacing the transition instead of returning only a silent green.
    """
    check_id = _safe_name(check_id, what="check_id")
    reviewed_sha = _validate_sha(reviewed_sha)
    entries = _read_lines_or_halt(store.ledger_path)
    history = sorted(
        (
            e
            for e in entries
            if e.get("kind") == "evidence"
            and e.get("check_id") == check_id
            and e.get("reviewed_sha") == reviewed_sha
        ),
        key=lambda e: cast(int, e["attempt"]),
    )
    if not history:
        return LatestResult(
            check_id=check_id,
            reviewed_sha=reviewed_sha,
            verdict=None,
            attempt=None,
            superseded_fail=False,
            history=[],
        )
    latest_entry = history[-1]
    had_earlier_fail = any(e["verdict"] == "FAIL" for e in history[:-1])
    superseded = had_earlier_fail and latest_entry["verdict"] != "FAIL"
    return LatestResult(
        check_id=check_id,
        reviewed_sha=reviewed_sha,
        verdict=latest_entry["verdict"],
        attempt=latest_entry["attempt"],
        superseded_fail=superseded,
        history=history,
    )


def history(store: Store, *, check_id: str) -> list[dict[str, Any]]:
    """Every evidence entry for ``check_id`` across every ``reviewed_sha``, oldest -> newest (#397).

    ``latest()`` is already scoped to one exact ``(check_id, reviewed_sha)`` pair, so it alone
    cannot distinguish "this check never ran" from "this check ran, but only at a different SHA" —
    the closure gate (sub-397) needs exactly that distinction to tell ``missing-evidence`` apart
    from ``stale-sha``. Additive only: no change to any existing signature or storage format
    (evidence-ledger plan R10 reserves this module's read surface for sub-397 to extend).
    """
    check_id = _safe_name(check_id, what="check_id")
    entries = _read_lines_or_halt(store.ledger_path)
    return [e for e in entries if e.get("kind") == "evidence" and e.get("check_id") == check_id]


# ---------------------------------------------------------------------------
# verify_chain() — linkage + artifact re-hash (R2, KTD3)
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class ChainReport:
    entry_count: int
    verified_artifacts: int
    verified_criteria: int


def verify_chain(store: Store) -> ChainReport:
    """Reconstruct and validate the full custody log: linkage, tail integrity, then every file.

    Raises ``EvidenceLedgerError`` (never returns a false-positive report) on the first
    divergence: a broken ``prev`` link (an interior entry was tampered with), a head-pointer
    mismatch (the tail entry was tampered with — see ``_append_entry``), or a hash mismatch
    between a recorded entry and the bytes currently on disk (an artifact or criteria file was
    tampered with after being written).
    """
    entries = _read_lines_or_halt(store.ledger_path)
    prev_hash: str | None = None
    verified_artifacts = 0
    verified_criteria = 0
    for entry in entries:
        if entry.get("prev") != prev_hash:
            raise EvidenceLedgerError(
                f"custody chain broken at seq={entry.get('seq')}: expected prev={prev_hash!r}, "
                f"found {entry.get('prev')!r}"
            )
        kind = entry.get("kind")
        if kind == "evidence":
            artifact_path = Path(entry["artifact_path"])
            if not artifact_path.exists():
                raise EvidenceLedgerError(
                    f"artifact missing on disk: {artifact_path} (seq={entry['seq']})"
                )
            on_disk_hash = _sha256_hex(artifact_path.read_bytes())
            if on_disk_hash != entry["hash"]:
                raise EvidenceLedgerError(
                    f"artifact tampered: {artifact_path} recorded hash {entry['hash']}, "
                    f"on-disk hash {on_disk_hash} (seq={entry['seq']})"
                )
            verified_artifacts += 1
        elif kind == "criteria":
            criteria_path = Path(entry["criteria_path"])
            if not criteria_path.exists():
                raise EvidenceLedgerError(
                    f"criteria file missing on disk: {criteria_path} (seq={entry['seq']})"
                )
            on_disk_hash = _sha256_hex(criteria_path.read_bytes())
            if on_disk_hash != entry["hash"]:
                raise EvidenceLedgerError(
                    f"criteria tampered: {criteria_path} recorded hash {entry['hash']}, "
                    f"on-disk hash {on_disk_hash} (seq={entry['seq']})"
                )
            verified_criteria += 1
        prev_hash = _entry_hash(entry)

    if entries:
        if not store.head_path.exists():
            raise EvidenceLedgerError(f"ledger head pointer missing: {store.head_path}")
        recorded_head = store.head_path.read_text(encoding="utf-8").strip()
        if recorded_head != prev_hash:
            raise EvidenceLedgerError(
                "custody chain tail tampered: the last entry's recomputed hash "
                f"({prev_hash}) does not match the recorded head pointer ({recorded_head})"
            )

    return ChainReport(
        entry_count=len(entries),
        verified_artifacts=verified_artifacts,
        verified_criteria=verified_criteria,
    )


# ---------------------------------------------------------------------------
# close_verify() — closure HALT-on-tamper + producer/verifier separation (R5/R6)
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class ClosureReport:
    certified_through_seq: int
    verifier: str
    chain: ChainReport


def close_verify(store: Store, *, check_id: str, reviewed_sha: str, verifier: str) -> ClosureReport:
    """Verify the full chain, reject self-certification, then append a closure entry.

    HALTs (raises) on any chain-verify failure — a tamper is never silently treated as valid.
    Also HALTs when ``verifier`` equals the ``producer`` role of ``(check_id, reviewed_sha)``'s
    evidence entries: a producer can never be its own verifier (R6 — reject, never merely flag,
    matching this repo's HALT-not-degrade bias).
    """
    check_id = _safe_name(check_id, what="check_id")
    reviewed_sha = _validate_sha(reviewed_sha)
    entries = _read_lines_or_halt(store.ledger_path)
    producer_roles = {
        e["producer"]
        for e in entries
        if e.get("kind") == "evidence"
        and e.get("check_id") == check_id
        and e.get("reviewed_sha") == reviewed_sha
    }
    if verifier in producer_roles:
        raise EvidenceLedgerError(
            f"verifier {verifier!r} matches the producer role for ({check_id}, {reviewed_sha}) — "
            "a producer cannot self-certify its own evidence"
        )
    chain = verify_chain(store)  # raises on any tamper — propagates as a HALT

    prev_hash = _entry_hash(entries[-1]) if entries else None
    entry = {
        "seq": len(entries) + 1,
        "kind": "closure",
        "prev": prev_hash,
        "check_id": check_id,
        "reviewed_sha": reviewed_sha,
        "verifier": verifier,
        "certified_through_seq": len(entries),
        "timestamp": _now(),
    }
    _append_entry(store, entry)
    return ClosureReport(certified_through_seq=len(entries), verifier=verifier, chain=chain)


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def _load_json_object(path: str) -> dict[str, Any]:
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise EvidenceLedgerError(f"{path} must contain a JSON object")
    return data


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Evidence ledger: content-addressed, append-only custody CLI (#398)."
    )
    parser.add_argument("--repo-root", default=".", help="Repo root (default cwd).")
    parser.add_argument("--saga-id", required=True, help="Saga id this evidence belongs to.")
    sub = parser.add_subparsers(dest="command", required=True)

    p_write = sub.add_parser("write", help="Content-address and append a verification artifact.")
    p_write.add_argument("--check-id", required=True)
    p_write.add_argument("--reviewed-sha", required=True)
    p_write.add_argument("--producer", required=True)
    p_write.add_argument("--verdict", required=True)
    p_write.add_argument("--artifact-file", required=True, help="Path to the artifact content.")
    p_write.add_argument("--attempt", type=int, default=None)
    p_write.add_argument("--payload", default=None, help="Path to a JSON object.")

    p_freeze = sub.add_parser("freeze-criteria", help="Write-once the pass/fail criteria block.")
    p_freeze.add_argument("--check-id", required=True)
    p_freeze.add_argument("--reviewed-sha", required=True)
    p_freeze.add_argument("--criteria-file", required=True, help="Path to a JSON criteria object.")

    p_latest = sub.add_parser("latest", help="Print the latest verdict + supersession flag.")
    p_latest.add_argument("--check-id", required=True)
    p_latest.add_argument("--reviewed-sha", required=True)

    sub.add_parser("verify-chain", help="Validate the full custody chain.")

    p_close = sub.add_parser("close", help="Verify the chain then append a closure entry.")
    p_close.add_argument("--check-id", required=True)
    p_close.add_argument("--reviewed-sha", required=True)
    p_close.add_argument("--verifier", required=True)

    args = parser.parse_args(argv)
    repo_root = Path(args.repo_root)
    store = Store.for_saga(args.saga_id, repo_root).ensure()

    try:
        if args.command == "write":
            content = Path(args.artifact_file).read_text(encoding="utf-8")
            payload = _load_json_object(args.payload) if args.payload else None
            write_result = write(
                store,
                check_id=args.check_id,
                reviewed_sha=args.reviewed_sha,
                producer=args.producer,
                verdict=args.verdict,
                content=content,
                attempt=args.attempt,
                payload=payload,
            )
            print(
                json.dumps(
                    {
                        "content_hash": write_result.content_hash,
                        "attempt": write_result.attempt,
                        "artifact_path": str(write_result.artifact_path),
                    },
                    indent=2,
                    sort_keys=True,
                )
            )
            return 0

        if args.command == "freeze-criteria":
            criteria = _load_json_object(args.criteria_file)
            freeze_result = freeze_criteria(
                store,
                check_id=args.check_id,
                reviewed_sha=args.reviewed_sha,
                criteria=criteria,
            )
            print(
                json.dumps(
                    {
                        "content_hash": freeze_result.content_hash,
                        "criteria_path": str(freeze_result.criteria_path),
                    },
                    indent=2,
                    sort_keys=True,
                )
            )
            return 0

        if args.command == "latest":
            latest_result = latest(store, check_id=args.check_id, reviewed_sha=args.reviewed_sha)
            print(
                json.dumps(
                    {
                        "verdict": latest_result.verdict,
                        "attempt": latest_result.attempt,
                        "superseded_fail": latest_result.superseded_fail,
                        "history_count": len(latest_result.history),
                    },
                    indent=2,
                    sort_keys=True,
                )
            )
            return 0

        if args.command == "verify-chain":
            chain_report = verify_chain(store)
            print(
                json.dumps(
                    {
                        "entry_count": chain_report.entry_count,
                        "verified_artifacts": chain_report.verified_artifacts,
                        "verified_criteria": chain_report.verified_criteria,
                    },
                    indent=2,
                    sort_keys=True,
                )
            )
            return 0

        if args.command == "close":
            closure_report = close_verify(
                store,
                check_id=args.check_id,
                reviewed_sha=args.reviewed_sha,
                verifier=args.verifier,
            )
            print(
                json.dumps(
                    {
                        "certified_through_seq": closure_report.certified_through_seq,
                        "verifier": closure_report.verifier,
                        "entry_count": closure_report.chain.entry_count,
                    },
                    indent=2,
                    sort_keys=True,
                )
            )
            return 0
    except EvidenceLedgerError as exc:
        print(f"HALT: {exc}", file=sys.stderr)
        return 1

    parser.error(f"unknown command {args.command!r}")
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
