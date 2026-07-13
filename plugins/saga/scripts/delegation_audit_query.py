#!/usr/bin/env python3
"""`/delegation-audit` CLI: reconcile the durable delegation audit store (#396, U5).

Reads the durable delegation audit store (`~/.claude/delegation-audit` by default — see
`fleet_commons/audit_store.py`) and reports every run's reconciled verdict: a delegation whose
disposition claims real execution but whose receipt does not back that claim is flagged as a
no-op (`fleet_commons/delegation_audit.py`'s `reconcile_store`). Read-only, advisory, on-demand —
never a gate, never a background job.

CLI::

    python3 delegation_audit_query.py [--audit-store <path>] [--run-id <id> ...]
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parent))

import fleet_commons_shim  # noqa: E402

_audit_store = fleet_commons_shim.load("audit_store")
_delegation_audit = fleet_commons_shim.load("delegation_audit")


def build_report(store: Any, run_ids: list[str] | None = None) -> dict[str, Any]:
    """Reconcile every run (or the given ``run_ids``) and shape the JSON report.

    Never raises on an empty or missing store — an absent ``runs/`` directory reconciles to zero
    entries, which is a clean (not erroring) report.
    """
    entries = _delegation_audit.reconcile_store(store, run_ids=run_ids)
    flagged = [entry.to_jsonable() for entry in entries if entry.flagged]
    clean = [entry.to_jsonable() for entry in entries if not entry.flagged]
    return {
        "audit_store_root": str(store.root),
        "run_count": len(entries),
        "flagged_count": len(flagged),
        "flagged": flagged,
        "clean": clean,
    }


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Reconcile the durable delegation audit store: flag any delegation whose "
            "disposition claims real execution but whose receipt does not back that claim."
        )
    )
    parser.add_argument(
        "--audit-store",
        default=None,
        help=f"Audit-store root (default: {_audit_store.DEFAULT_AUDIT_STORE_ROOT})",
    )
    parser.add_argument(
        "--run-id",
        action="append",
        default=None,
        dest="run_ids",
        help="Reconcile only this run id (repeatable). Default: every run in the store.",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    store = _audit_store.Store.for_root(args.audit_store)
    report = build_report(store, run_ids=args.run_ids)
    print(json.dumps(report, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
