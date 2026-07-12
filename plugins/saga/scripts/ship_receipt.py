#!/usr/bin/env python3
"""ship_receipt.py — immutable ship receipt writer/reader (issue #347 U2).

Once ``ship_teardown.reconcile`` reports a zero closing count, the ceremony mints a
receipt that records what was opened and what was closed. The receipt is written
exactly once and is never mutated (R4, KTD5):

* ``mint`` refuses (``TeardownBlockedError``) if the report's closing count is
  non-zero — no file is created. On a zero count it writes
  ``.claude/saga/sagas/<saga_id>/ship_receipt.json`` via ``O_CREAT|O_EXCL`` (so a
  concurrent/second mint cannot silently clobber it) then ``chmod 0444`` (so an
  in-place edit attempt fails at the filesystem, not merely by convention). A second
  ``mint`` against the same saga raises ``ReceiptExistsError`` — the receipt is
  write-once, mechanically, not by promise.
* ``read`` parses and schema-validates the receipt and never writes. It re-probes
  reality via ``ship_teardown.reconcile`` and, if the freshly reconciled report
  disagrees with what the receipt recorded as closed, surfaces a named anomaly in
  the return value — it never edits the receipt to "fix" the discrepancy.

Storage: same per-saga sidecar directory as ``opened_resources.json``
(``.claude/saga/sagas/<saga_id>/``), same saga-id hardening as ``ship_teardown.py``.
"""

from __future__ import annotations

import argparse
import errno
import json
import os
import re
import stat
import sys
from collections.abc import Callable
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

SCRIPT_DIR = Path(__file__).resolve().parent

# Sibling-module import (issue #347, U2): ship_teardown.py's manifest reader +
# reconcile are called as a library, not shelled out to — mirrors the
# sys.path.insert + import pattern ship_ceremony.py uses for ceremony_hazards.py /
# merge_watcher.py / ship_undo.py.
sys.path.insert(0, str(SCRIPT_DIR))

import ship_teardown  # noqa: E402

SAGAS_DIR = ship_teardown.SAGAS_DIR
RECEIPT_NAME = "ship_receipt.json"

# Duplicated (not imported) from ship_teardown.py by house convention — each
# sidecar module stays dependency-free on the saga_id validation regex itself,
# even though it happens to share ship_teardown's helper here for DRYness of the
# storage location. The regex is intentionally the same value.
_SAGA_ID_RE = re.compile(r"[A-Za-z0-9][A-Za-z0-9._-]*")

_REQUIRED_TOP_KEYS = ("saga_id", "minted_at", "opened", "closed", "ceremony")


class ShipReceiptError(Exception):
    """Base error for ship_receipt.py — always caught at the CLI boundary and
    reported as a message, never an uncaught traceback."""


class TeardownBlockedError(ShipReceiptError):
    """``mint`` was called against a report whose closing count is non-zero.
    Raised BEFORE any file is created — a blocked mint leaves no receipt on disk
    (R4). Names every blocking entry so the operator knows what to close."""

    def __init__(self, saga_id: str, report: ship_teardown.ReconcileReport) -> None:
        self.saga_id = saga_id
        self.report = report
        self.remedy = (
            "close every entry named below (ship_teardown.py close --id ... "
            "--evidence ...) or resolve the discrepancy, then re-run teardown"
        )
        blockers = "; ".join(report.lines()) or "(no entries — closing_count > 0 is a bug)"
        super().__init__(
            f"ship_receipt refuses to mint for saga {saga_id!r}: closing count is "
            f"{report.closing_count}, not 0 — {blockers}; {self.remedy}"
        )


class ReceiptExistsError(ShipReceiptError):
    """A receipt already exists for this saga_id — mint is write-once (KTD5).
    The existing receipt is left untouched; re-mint is never a silent overwrite."""

    def __init__(self, saga_id: str, path: Path) -> None:
        self.saga_id = saga_id
        self.path = path
        super().__init__(
            f"ship_receipt already minted for saga {saga_id!r} at {path} — receipts "
            "are write-once; use read() to inspect it, never mint() to overwrite it"
        )


class ReceiptNotMintedError(ShipReceiptError):
    """``read()`` was called for a saga_id with no receipt on disk yet — distinct
    from a corrupt/invalid receipt so callers can tell "not shipped yet" apart from
    "shipped but the receipt is broken"."""

    def __init__(self, saga_id: str, path: Path) -> None:
        self.saga_id = saga_id
        self.path = path
        super().__init__(f"no ship_receipt.json minted yet for saga {saga_id!r} (looked at {path})")


class InvalidReceiptError(ShipReceiptError):
    """The on-disk receipt is not valid JSON or is missing required schema keys —
    always wrapped, never a bare ``JSONDecodeError``/``KeyError`` escaping."""


def _validate_saga_id(saga_id: str) -> str:
    if not _SAGA_ID_RE.fullmatch(saga_id):
        raise ShipReceiptError(
            f"invalid saga_id {saga_id!r}: must be a single path-safe segment "
            "matching [A-Za-z0-9][A-Za-z0-9._-]* (e.g. issue-347)"
        )
    return saga_id


def receipt_path(repo_root: Path, saga_id: str) -> Path:
    return repo_root / SAGAS_DIR / _validate_saga_id(saga_id) / RECEIPT_NAME


def mint(
    repo_root: Path,
    saga_id: str,
    report: ship_teardown.ReconcileReport,
    ceremony_summary: dict[str, Any],
    *,
    now: str | None = None,
) -> Path:
    """Mint the immutable receipt from a zero-count reconcile report (R4, KTD5).

    Refuses with ``TeardownBlockedError`` (no file created) if ``report.closing_count``
    is non-zero. Raises ``ReceiptExistsError`` if a receipt already exists — mint is
    write-once, enforced by ``O_CREAT|O_EXCL`` at the filesystem level, not merely by
    an existence check racing the write (the exclusive-create IS the guard; the
    existence check below only produces a friendlier error on the common path).
    """
    _validate_saga_id(saga_id)
    if report.closing_count != 0:
        raise TeardownBlockedError(saga_id, report)

    manifest = ship_teardown.read_manifest(repo_root, saga_id)
    path = receipt_path(repo_root, saga_id)
    path.parent.mkdir(parents=True, exist_ok=True)

    payload = {
        "saga_id": saga_id,
        "minted_at": now or datetime.now(UTC).isoformat(),
        "opened": manifest,
        "closed": report.to_dict(),
        "ceremony": dict(ceremony_summary),
    }
    body = json.dumps(payload, indent=2, sort_keys=True) + "\n"

    try:
        fd = os.open(str(path), os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o644)
    except FileExistsError as exc:
        raise ReceiptExistsError(saga_id, path) from exc
    except OSError as exc:
        if exc.errno == errno.EEXIST:
            raise ReceiptExistsError(saga_id, path) from exc
        raise
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            handle.write(body)
    finally:
        # Read-only after the write completes (KTD5) — an in-place mutation via any
        # writer API (including a second mint()) now fails at the filesystem, not
        # merely by convention.
        os.chmod(path, stat.S_IRUSR | stat.S_IRGRP | stat.S_IROTH)  # 0444
    return path


def _read_raw(path: Path) -> dict[str, Any]:
    with open(path, encoding="utf-8") as handle:
        try:
            data = json.load(handle)
        except json.JSONDecodeError as exc:
            raise InvalidReceiptError(
                f"ship_receipt.json at {path} is not valid JSON: {exc}"
            ) from exc
    if not isinstance(data, dict):
        raise InvalidReceiptError(f"ship_receipt.json at {path} is not a JSON object")
    missing = [key for key in _REQUIRED_TOP_KEYS if key not in data]
    if missing:
        raise InvalidReceiptError(
            f"ship_receipt.json at {path} is missing required keys: {missing}"
        )
    return data


def read(
    repo_root: Path,
    saga_id: str,
    *,
    runner: Callable[..., Any] | None = None,
    reprobe: bool = True,
) -> dict[str, Any]:
    """Read + schema-validate the receipt. Never writes (R4).

    When ``reprobe`` is true (the default), re-runs ``ship_teardown.reconcile``
    against current reality and folds any disagreement with what the receipt
    recorded as closed into an ``anomalies`` list on the returned dict — a
    contradiction between the recorded receipt and fresh reality is surfaced as a
    named anomaly, never silently trusted and never edited back into the receipt
    file (KTD5/R4).
    """
    _validate_saga_id(saga_id)
    path = receipt_path(repo_root, saga_id)
    if not path.exists():
        raise ReceiptNotMintedError(saga_id, path)
    data = _read_raw(path)

    anomalies: list[str] = []
    if reprobe:
        fresh = ship_teardown.reconcile(repo_root, saga_id, runner=runner)
        fresh_by_id = {e.resource_id: e for e in fresh.entries}
        recorded_entries = data.get("closed", {}).get("entries", [])
        for recorded in recorded_entries:
            resource_id = recorded.get("resource_id")
            recorded_status = recorded.get("status")
            fresh_entry = fresh_by_id.get(resource_id)
            if fresh_entry is None:
                anomalies.append(
                    f"{resource_id}: recorded in receipt but no longer present in the "
                    "manifest at all"
                )
                continue
            if (
                recorded_status == ship_teardown.STATUS_CLOSED_VERIFIED
                and fresh_entry.status != ship_teardown.STATUS_CLOSED_VERIFIED
            ):
                anomalies.append(
                    f"{resource_id}: receipt recorded {recorded_status!r} but a fresh "
                    f"probe now reports {fresh_entry.status!r} ({fresh_entry.note})"
                )

    result = dict(data)
    result["anomalies"] = anomalies
    return result


# --------------------------------------------------------------------------- #
# CLI
# --------------------------------------------------------------------------- #


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument(
        "--repo-root", type=Path, default=Path.cwd(), help="repo root (default: cwd)"
    )
    sub = parser.add_subparsers(dest="command", required=True)

    p_read = sub.add_parser("read", help="read + validate the receipt (never writes)")
    p_read.add_argument("--saga-id", required=True)
    p_read.add_argument(
        "--no-reprobe",
        action="store_true",
        help="skip the fresh reality reconcile pass (schema-only read)",
    )

    return parser


def main(argv: list[str] | None = None) -> int:
    parser = _build_parser()
    args = parser.parse_args(argv)
    repo_root: Path = args.repo_root

    try:
        if args.command == "read":
            result = read(repo_root, args.saga_id, reprobe=not args.no_reprobe)
            print(json.dumps(result, indent=2, sort_keys=True))
            if result.get("anomalies"):
                return 1
        else:  # pragma: no cover - argparse enforces valid choices
            parser.error(f"unknown command {args.command!r}")
            return 2
    except ShipReceiptError as exc:
        print(f"ship_receipt: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
