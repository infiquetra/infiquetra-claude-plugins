#!/usr/bin/env python3
"""Spend ceiling from observed actuals.

``tokens_observed`` is produced here from a ``pane.output_matched`` line and
consumed by :func:`check_spend`. ``tokens_reserved`` is produced by admission
and consumed here when a vendor exposes no usage line: the declared worst case
is the actual, and the ceiling can fire.

Usage-sample contract. Vendors in ``VENDORS_WITHOUT_USAGE`` emit no usage line;
their declared ``tokens_max`` is the charge once the child has launched, and an
observed value cannot lower it. No live transcript in this repository binds a
line format to claude, codex, grok, or qwen; any of those four may emit either
grammar. A line is classified only when exactly one grammar matches. A line
matching both is refused, not parsed by one grammar and labelled with the
other.

A ``tokens used`` / ``total tokens`` line is a cumulative total: store the
monotonic maximum. An ``input``/``output`` line is a delta: add it. Herdr's
``pane.output_matched`` envelope reports ``read.revision=0`` on every live
event, so there is no transport delivery identity. Content-hash deduplication
of deltas cannot be claimed: two genuine equal samples are ordinary, and
dropping one under-counts. When a replay cannot be distinguished from a
repeat, this module over-counts. Over-counting halts early, which an operator
can see. Under-counting authorizes spend past the ceiling, silently.

A line that matches the usage needle but neither closed grammar, after a
prior sample exists, marks telemetry unparseable. The spend gate then fails
closed instead of keeping the stale prior. That mark is not cleared by a
later parseable sample: a later line is a different sample, not evidence
that the earlier ambiguity was resolved.

A child whose phase is explicitly planned has spent zero. Queued is an
admission status, not a phase; a queued child is still planned. A missing
or unknown phase is not "not launched": it is unknown and fails closed.
A launched, active, or terminal metered child with no telemetry fails closed.

``authorize_spend`` does not engage when actuals are ``None``. This module never
passes ``None`` to mean "the vendor is silent."
"""

from __future__ import annotations

import hashlib
import re
from collections.abc import Collection, Mapping
from pathlib import Path
from typing import Any

import fleet_commons_shim
import register as register_store

intent_envelope = fleet_commons_shim.load("intent_envelope")

# Vendors whose CLIs have no documented usage line on this host.
VENDORS_WITHOUT_USAGE = frozenset({"muse", "agy"})
# Vendors that may emit a usage line. No transcript binds a grammar to one of them.
USAGE_REPORTING_VENDORS = frozenset({"claude", "codex", "grok", "qwen"})
USAGE_KIND_CUMULATIVE = "cumulative"
USAGE_KIND_DELTA = "delta"
USAGE_UNPARSEABLE_KEY = "usage_unparseable"
LAUNCHED_PHASES = frozenset({"launching", "launched", "ready", "working", "verified", "reaped"})

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


def classify_usage_line(line: str, *, vendor: str | None = None) -> tuple[str, int] | None:
    """Return ``(kind, tokens)`` for one closed usage line.

    ``None`` means the line is not usage. A line matching both grammars, or a
    silent vendor producing a usage-shaped line, raises.
    """
    if not line or _NOT_SPEND.search(line):
        return None
    paired = _INPUT_OUTPUT.search(line)
    used = _USED_TOTAL.search(line)
    if paired is not None and used is not None:
        raise AccountingError(
            f"usage line matches both the delta and cumulative grammars: {line!r}"
        )
    if vendor is not None and vendor in VENDORS_WITHOUT_USAGE and (paired or used):
        raise AccountingError(
            f"vendor {vendor!r} exposes no usage line; refusing to treat {line!r} as spend"
        )
    if paired is not None:
        return USAGE_KIND_DELTA, int(paired.group(1)) + int(paired.group(2))
    if used is not None:
        return USAGE_KIND_CUMULATIVE, int(used.group(1))
    return None


def parse_usage_line(line: str) -> int | None:
    """Return a token count from one CLI usage line, or ``None`` if it is not one.

    ``None`` means this line is not usage (a sentinel, a log line). It is not
    "the vendor reports no usage." Ambiguous lines raise.
    """
    classified = classify_usage_line(line)
    if classified is None:
        return None
    return classified[1]


def usage_fingerprint(line: str) -> str:
    return hashlib.sha256(line.encode("utf-8")).hexdigest()


def usage_sample_kind(line: str, *, vendor: str | None = None) -> str | None:
    """Whether this line is a cumulative total or a delta sample.

    ``None`` means the line is not usage. Ambiguous lines raise.
    """
    classified = classify_usage_line(line, vendor=vendor)
    if classified is None:
        return None
    return classified[0]


def record_observed_tokens(
    root: Path,
    row_id: str,
    tokens: int,
    *,
    run_id: str,
    event_id: str | None = None,
    kind: str = USAGE_KIND_DELTA,
) -> dict[str, Any]:
    """Producer of ``tokens_observed``. Updates under the generation lock.

    ``event_id`` is a transport delivery identity. Deltas are not suppressed by
    content. A missing transport identity means equal deltas are added: that is
    fail-closed. Cumulative samples keep a monotonic maximum. This function
    does not write ``usage_unparseable``: a later sample is not a recovery.
    """
    if tokens < 0:
        raise AccountingError("observed tokens cannot be negative")
    claimed = register_store.canonical_work_location(root)
    with register_store.generation_locked(run_id):
        doc = register_store._read_register_unlocked(run_id)
        existing = doc.get("rows", {}).get(row_id, {})
        seen_raw = existing.get("usage_events")
        seen = [str(item) for item in seen_raw] if isinstance(seen_raw, list) else []
        if event_id and event_id in seen:
            return dict(existing)
        prior = existing.get("tokens_observed")
        numeric = isinstance(prior, (int, float)) and not isinstance(prior, bool)
        prior_n = int(prior) if numeric else None
        if kind == USAGE_KIND_CUMULATIVE:
            total = tokens if prior_n is None else max(prior_n, tokens)
        else:
            total = tokens if prior_n is None else prior_n + tokens
        fields: dict[str, Any] = {"tokens_observed": total}
        if event_id:
            fields["usage_events"] = [*seen, event_id]
        merged = register_store._upsert_rows_unlocked(
            claimed,
            {row_id: fields},
            run_id=run_id,
            writer=register_store.TOKENS_OBSERVED_WRITER,
        )
        return merged[row_id]


def _mark_usage_unparseable(root: Path, row_id: str, *, run_id: str) -> None:
    """Sole writer of ``usage_unparseable``. Sets the mark; never clears it."""
    claimed = register_store.canonical_work_location(root)
    with register_store.generation_locked(run_id):
        register_store._upsert_rows_unlocked(
            claimed,
            {row_id: {USAGE_UNPARSEABLE_KEY: True}},
            run_id=run_id,
            writer=register_store.USAGE_UNPARSEABLE_WRITER,
        )


def apply_output_match(
    root: Path,
    row_id: str,
    line: str,
    *,
    run_id: str,
    vendor: str | None = None,
    event_id: str | None = None,
) -> int | None:
    """If ``line`` is a usage line, record it. Otherwise leave the row alone.

    A line matching the usage needle that is not a closed grammar, after a
    prior sample exists, marks telemetry unparseable. The observer records
    that fact and returns; the spend gate is what refuses. A later parseable
    sample does not clear the mark.
    """
    try:
        classified = classify_usage_line(line, vendor=vendor)
    except AccountingError:
        _mark_usage_unparseable(root, row_id, run_id=run_id)
        return None
    if classified is None:
        if USAGE_SUBSTRING in line.lower() and not _NOT_SPEND.search(line):
            existing = register_store.read_rows(root, run_id=run_id).get(row_id, {})
            if existing.get("tokens_observed") is not None:
                _mark_usage_unparseable(root, row_id, run_id=run_id)
        return None
    kind, tokens = classified
    record_observed_tokens(
        root,
        row_id,
        tokens,
        run_id=run_id,
        event_id=event_id,
        kind=kind,
    )
    return tokens


def _actual_for_row(row: Mapping[str, Any], *, vendor: str) -> float:
    if row.get(USAGE_UNPARSEABLE_KEY) is True:
        raise AccountingError(f"row {row.get('id')!r} has unparseable usage telemetry; fail closed")
    phase = row.get("phase")
    if phase == "planned":
        return 0.0
    if phase == "launching":
        raise AccountingError(
            f"row {row.get('id')!r} is launching; its live session presence must be resolved "
            "before accounting can include or exclude it"
        )
    if phase not in LAUNCHED_PHASES:
        raise AccountingError(f"row {row.get('id')!r} has unknown phase {phase!r}; fail closed")
    declared = row.get("tokens_max", row.get("tokens_reserved"))
    if not vendor_reports_usage(vendor):
        if isinstance(declared, (int, float)) and not isinstance(declared, bool) and declared > 0:
            return float(declared)
        raise AccountingError(
            f"vendor {vendor!r} exposes no usage line and row {row.get('id')!r} "
            "has no declared tokens_max; fail closed"
        )
    observed = row.get("tokens_observed")
    if isinstance(observed, (int, float)) and not isinstance(observed, bool):
        return float(observed)
    raise AccountingError(
        f"vendor {vendor!r} reports usage but row {row.get('id')!r} has no "
        "tokens_observed; fail closed"
    )


def run_actual_tokens(root: Path, *, run_id: str, exclude_row_ids: Collection[str] = ()) -> float:
    """Sum this run's actuals. Missing telemetry fails closed.

    ``exclude_row_ids`` names rows the caller has already decided not to count toward this total
    -- for instance a row a coordinator has explicitly stopped pursuing
    (``coordinator_disposition.state == "abandoned"``). Excluding is not charging zero: a row's
    true spend may be nonzero and genuinely unknown, and it is left out of the sum rather than
    guessed at. This module does not itself know what "abandoned" means -- that fact belongs to
    whichever module records it -- it only skips whichever row ids the caller names.
    """
    rows = register_store.read_rows(root, run_id=run_id)
    total = 0.0
    for row_id, row in rows.items():
        if register_store.is_supervisory_row(row) or row_id in exclude_row_ids:
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
    exclude_row_ids: Collection[str] = (),
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
        actual = run_actual_tokens(root, run_id=run_id, exclude_row_ids=exclude_row_ids)
    spend = intent_envelope.SpendEnvelope(cost_ceiling_tokens=float(ceiling))
    decision = intent_envelope.authorize_spend(spend, actual_tokens=actual)
    if not decision.authorized:
        raise AccountingError(decision.reason)
