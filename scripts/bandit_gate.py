#!/usr/bin/env python3
"""Run the locked Bandit policy and reject incomplete or failed scanner evidence."""

from __future__ import annotations

import hashlib
import json
import os
import re
import subprocess
import sys
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any, NoReturn

ROOTS = ("plugins", "scripts", "tests", "tools")
REPORT = "bandit-report.json"
LOG = "bandit.log"
STATUS = "bandit-gate.json"
METRICS = {
    "loc",
    "nosec",
    "skipped_tests",
    *(
        f"{axis}.{level}"
        for axis in ("SEVERITY", "CONFIDENCE")
        for level in ("UNDEFINED", "LOW", "MEDIUM", "HIGH")
    ),
}


def _raise_walk_error(error: OSError) -> NoReturn:
    raise error


def input_inventory(root: Path) -> dict[str, str]:
    """Enumerate locked Bandit's *.py/*.pyw inputs; traversal failures are fatal."""
    inventory = {}
    for name in ROOTS:
        directory = root / name
        if not directory.is_dir():
            raise ValueError(f"missing scan root: {name}")
        for parent, _, filenames in os.walk(directory, onerror=_raise_walk_error):
            for filename in filenames:
                if filename.endswith((".py", ".pyw")):
                    path = Path(parent) / filename
                    inventory[path.relative_to(root).as_posix()] = hashlib.sha256(
                        path.read_bytes()
                    ).hexdigest()
    if not inventory:
        raise ValueError("empty scan inventory")
    return dict(sorted(inventory.items()))


def validate_report(
    report: Any, inventory: dict[str, str], started: datetime, ended: datetime
) -> None:
    if not isinstance(report, dict):
        raise ValueError("report must be an object")
    generated = datetime.strptime(report["generated_at"], "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=UTC)
    if not started.replace(microsecond=0) <= generated <= ended + timedelta(seconds=1):
        raise ValueError("stale or future report timestamp")
    if report["errors"] != []:
        raise ValueError("scanner reported errors")
    results, metrics = report["results"], report["metrics"]
    if not isinstance(results, list) or not isinstance(metrics, dict):
        raise ValueError("invalid results or metrics")
    if set(metrics) != {*inventory, "_totals"}:
        raise ValueError("report file inventory differs from all four scan roots")
    for name, values in metrics.items():
        if not isinstance(values, dict) or set(values) != METRICS:
            raise ValueError(f"incomplete metrics: {name}")
        if any(type(value) is not int or value < 0 for value in values.values()):
            raise ValueError(f"invalid metric values: {name}")
    for key in METRICS:
        if metrics["_totals"][key] != sum(metrics[name][key] for name in inventory):
            raise ValueError(f"inconsistent total: {key}")
    counts: dict[tuple[str, str], int] = {}
    for result in results:
        if not isinstance(result, dict):
            raise ValueError("invalid finding")
        name, severity = result["filename"], result["issue_severity"]
        if name not in inventory or severity not in {"MEDIUM", "HIGH"}:
            raise ValueError("unexpected finding path/severity")
        if result["issue_confidence"] not in {"LOW", "MEDIUM", "HIGH"}:
            raise ValueError("invalid finding confidence")
        if not re.fullmatch(r"B\d{3}", result["test_id"]):
            raise ValueError("invalid finding rule")
        if type(result["line_number"]) is not int or result["line_number"] < 1:
            raise ValueError("invalid finding location")
        counts[name, severity] = counts.get((name, severity), 0) + 1
    for name in inventory:
        for severity in ("MEDIUM", "HIGH"):
            if counts.get((name, severity), 0) != metrics[name][f"SEVERITY.{severity}"]:
                raise ValueError("incomplete policy findings")
    if results:
        raise ValueError(f"{len(results)} unresolved medium/high findings")


def run_scan(root: Path) -> int:
    report_path, log_path = root / REPORT, root / LOG
    started = datetime.now(UTC)
    status: dict[str, Any] = {"started": started.isoformat(), "roots": list(ROOTS), "ok": False}
    try:
        log_path.write_text("", encoding="utf-8")
        # A previous clean report must never qualify a failed or interrupted new scan.
        report_path.unlink(missing_ok=True)
        inventory = input_inventory(root)
        status["inputs"] = inventory
        command = [
            sys.executable,
            "-m",
            "bandit",
            "-r",
            *(f"{p}/" for p in ROOTS),
            "-ll",
            "-f",
            "json",
            "-o",
            REPORT,
        ]
        status["command"] = command
        with log_path.open("w", encoding="utf-8") as log:
            process = subprocess.run(
                command, cwd=root, stdout=log, stderr=subprocess.STDOUT, check=False
            )
        status["scanner_exit"] = process.returncode
        log_text = log_path.read_text(encoding="utf-8")
        if re.search(r"\b(?:ERROR|CRITICAL)\b|Traceback \(most recent call last\)", log_text):
            raise ValueError("scanner logged an internal error")
        if input_inventory(root) != inventory:
            raise ValueError("scan inputs changed during execution")
        report = json.loads(report_path.read_text(encoding="utf-8"))
        validate_report(report, inventory, started, datetime.now(UTC))
        if process.returncode != 0:
            raise ValueError(f"scanner execution failed: exit {process.returncode}")
        status["ok"] = True
    except (OSError, ValueError, KeyError, TypeError, OverflowError) as exc:
        status["error"] = str(exc)
        # Retain startup/inventory failures even when the scanner never made a log.
        with log_path.open("a", encoding="utf-8") as log:
            log.write(f"\nBandit gate failed: {exc}\n")
    finally:
        status["ended"] = datetime.now(UTC).isoformat()
        (root / STATUS).write_text(json.dumps(status, indent=2) + "\n", encoding="utf-8")
    print("Bandit gate passed" if status["ok"] else f"Bandit gate failed: {status.get('error')}")
    return 0 if status["ok"] else 1


if __name__ == "__main__":
    sys.exit(run_scan(Path.cwd()))
