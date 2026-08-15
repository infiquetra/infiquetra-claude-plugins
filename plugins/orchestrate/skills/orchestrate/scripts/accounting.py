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

_USAGE_PATTERNS = (
    re.compile(r"(?i)\btokens?(?:\s+used|\s+usage)?\s*[:=]\s*(\d+)\b"),
    re.compile(r"(?i)\b(\d+)\s+tokens?\b"),
    re.compile(r"(?i)\binput\s+(\d+)\s+output\s+(\d+)\b"),
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
    if not line:
        return None
    for pattern in _USAGE_PATTERNS:
        match = pattern.search(line)
        if match is None:
            continue
        numbers = [int(group) for group in match.groups() if group is not None]
        if numbers:
            return sum(numbers)
    return None


def record_observed_tokens(root: Path, row_id: str, tokens: int, *, run_id: str) -> dict[str, Any]:
    """Producer of ``tokens_observed``. Adds to any value already stored."""
    if tokens < 0:
        raise AccountingError("observed tokens cannot be negative")
    rows = register_store.read_rows(root, run_id=run_id)
    existing = rows.get(row_id, {}).get("tokens_observed")
    total = tokens if not isinstance(existing, (int, float)) else int(existing) + tokens
    return register_store.upsert_row(root, row_id, {"tokens_observed": total}, run_id=run_id)


def apply_output_match(root: Path, row_id: str, line: str, *, run_id: str) -> int | None:
    """If ``line`` is a usage line, record it. Otherwise leave the row alone."""
    tokens = parse_usage_line(line)
    if tokens is None:
        return None
    record_observed_tokens(root, row_id, tokens, run_id=run_id)
    return tokens


def _actual_for_row(row: Mapping[str, Any], *, vendor: str) -> float:
    observed = row.get("tokens_observed")
    reserved = row.get("tokens_reserved")
    if isinstance(observed, (int, float)) and not isinstance(observed, bool):
        return float(observed)
    if not vendor_reports_usage(vendor):
        if isinstance(reserved, (int, float)) and not isinstance(reserved, bool):
            return float(reserved)
        raise AccountingError(
            f"vendor {vendor!r} exposes no usage line and row {row.get('id')!r} "
            "has no tokens_reserved; fail closed"
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
        if row.get("tokens_reserved") is None and row.get("tokens_observed") is None:
            continue
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
    """Refuse when observed (or reserved-as-observed) actuals meet the ceiling.

    The consumer of both accounting columns. Passes a real number to
    :func:`intent_envelope.authorize_spend` so the cost gate can fire.
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
