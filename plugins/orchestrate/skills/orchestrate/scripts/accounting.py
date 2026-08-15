#!/usr/bin/env python3
"""Spend ceiling from observed actuals.

``tokens_observed`` is produced here from a ``pane.output_matched`` line and
consumed by :func:`check_spend`. ``tokens_reserved`` is produced by admission
and consumed here when a vendor exposes no usage line: the declared worst case
is the actual, and the ceiling can fire.

``authorize_spend`` does not engage when actuals are ``None``. This module never
passes ``None`` to mean "the vendor is silent."
"""

from __future__ import annotations

import hashlib
import re
from collections.abc import Mapping
from pathlib import Path
from typing import Any

import fleet_commons_shim
import register as register_store

intent_envelope = fleet_commons_shim.load("intent_envelope")

# Vendors whose CLIs have no documented usage line on this host.
VENDORS_WITHOUT_USAGE = frozenset({"muse", "agy"})

# Closed needle the subscriber accepts as a usage ``pane.output_matched``
# substring. A match that does not contain this token is still a startup
# error unless it is a complete sentinel.
USAGE_SUBSTRING = "token"

_NOT_SPEND = re.compile(r"(?i)context\s+left|tokens?\s+remaining|tokens?/sec|tokens?\s+per\s")
_INPUT_OUTPUT = re.compile(
    r"(?i)\binput(?:\s+tokens?)?\s*[:=]?\s*(\d+)\s*,?\s*output(?:\s+tokens?)?\s*[:=]?\s*(\d+)"
)
_USED_TOTAL = re.compile(
    r"(?i)\b(?:tokens?\s*(?:used|usage)|total(?:\s+tokens?)?)\s*[:=]\s*(\d+)\b"
)


class AccountingError(Exception):
    """The spend gate refused the run, or telemetry is missing."""


def vendor_reports_usage(vendor: str) -> bool:
    return vendor not in VENDORS_WITHOUT_USAGE


def is_usage_match_value(value: str) -> bool:
    """True when a subscription substring is the closed usage needle."""
    return USAGE_SUBSTRING in value.lower()


def parse_usage_line(line: str) -> int | None:
    """Return a token count from one CLI usage line, or ``None`` if it is not one.

    ``None`` means this line is not usage (a sentinel, a log line). It is not
    "the vendor reports no usage."
    """
    if not line or _NOT_SPEND.search(line):
        return None
    paired = _INPUT_OUTPUT.search(line)
    if paired is not None:
        return int(paired.group(1)) + int(paired.group(2))
    used = _USED_TOTAL.search(line)
    if used is not None:
        return int(used.group(1))
    return None


def usage_fingerprint(line: str) -> str:
    return hashlib.sha256(line.encode("utf-8")).hexdigest()


def record_observed_tokens(
    root: Path,
    row_id: str,
    tokens: int,
    *,
    run_id: str,
    fingerprint: str | None = None,
) -> dict[str, Any]:
    """Producer of ``tokens_observed``. Adds under the generation lock.

    A repeated ``fingerprint`` is ignored so a redelivered line is not spend.
    """
    if tokens < 0:
        raise AccountingError("observed tokens cannot be negative")
    claimed = register_store.canonical_work_location(root)
    with register_store.generation_locked(run_id):
        doc = register_store._read_register_unlocked(run_id)
        existing = doc.get("rows", {}).get(row_id, {})
        if fingerprint and existing.get("usage_fingerprint") == fingerprint:
            return dict(existing)
        prior = existing.get("tokens_observed")
        total = tokens if not isinstance(prior, (int, float)) else int(prior) + tokens
        fields: dict[str, Any] = {"tokens_observed": total}
        if fingerprint:
            fields["usage_fingerprint"] = fingerprint
        merged = register_store._upsert_rows_unlocked(claimed, {row_id: fields}, run_id=run_id)
        return merged[row_id]


def apply_output_match(root: Path, row_id: str, line: str, *, run_id: str) -> int | None:
    """If ``line`` is a usage line, record it. Otherwise leave the row alone."""
    tokens = parse_usage_line(line)
    if tokens is None:
        return None
    record_observed_tokens(root, row_id, tokens, run_id=run_id, fingerprint=usage_fingerprint(line))
    return tokens


def _actual_for_row(row: Mapping[str, Any], *, vendor: str) -> float:
    observed = row.get("tokens_observed")
    declared = row.get("tokens_max", row.get("tokens_reserved"))
    if isinstance(observed, (int, float)) and not isinstance(observed, bool):
        return float(observed)
    if not vendor_reports_usage(vendor):
        if isinstance(declared, (int, float)) and not isinstance(declared, bool) and declared > 0:
            return float(declared)
        raise AccountingError(
            f"vendor {vendor!r} exposes no usage line and row {row.get('id')!r} "
            "has no declared tokens_max; fail closed"
        )
    raise AccountingError(
        f"vendor {vendor!r} reports usage but row {row.get('id')!r} has no "
        "tokens_observed; fail closed"
    )


def run_actual_tokens(root: Path, *, run_id: str) -> float:
    """Sum this run's actuals. Missing telemetry fails closed."""
    rows = register_store.read_rows(root, run_id=run_id)
    total = 0.0
    for row in rows.values():
        if row.get("agent") in {"subscriber", "mirror"}:
            continue
        vendor = str(row.get("vendor") or row.get("agent") or "")
        total += _actual_for_row(row, vendor=vendor)
    return total


def check_spend(
    root: Path,
    *,
    run_id: str,
    ceiling: float,
    vendor: str | None = None,
    row_id: str | None = None,
) -> None:
    """Refuse when observed actuals, or a silent vendor's declared maximum, meet the ceiling.

    A silent vendor is charged its ``tokens_max``, which is a declaration, not
    observed usage. Passes a real number to :func:`intent_envelope.authorize_spend`.
    """
    if row_id is not None:
        rows = register_store.read_rows(root, run_id=run_id)
        row = rows.get(row_id)
        if row is None:
            raise AccountingError(f"unknown child row {row_id!r}")
        chosen = vendor or str(row.get("vendor") or row.get("agent") or "")
        actual = _actual_for_row(row, vendor=chosen)
    else:
        actual = run_actual_tokens(root, run_id=run_id)
    spend = intent_envelope.SpendEnvelope(cost_ceiling_tokens=float(ceiling))
    decision = intent_envelope.authorize_spend(spend, actual_tokens=actual)
    if not decision.authorized:
        raise AccountingError(decision.reason)
