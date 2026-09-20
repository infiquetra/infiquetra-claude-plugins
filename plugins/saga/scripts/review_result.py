#!/usr/bin/env python3
"""Write ``review_result.v2`` into the run record, and publish it as one comment.

WHAT THIS MODULE OWNS
=====================

Serialising a review result, giving every finding one stable identity, keeping one
review history per unit, preparing the residual defects when the repair allowance
runs out, and rendering the result as exactly one pull-request comment. Filing
those defects is mission-control's, not this module's: opening an issue is that
plugin's ownership lane. It owns no policy: what
a lens means, what threshold it must reach and what shape acceptance takes all come
from the roster :mod:`review_roster` resolved, and the verdict itself is computed
by :mod:`review_consensus`.

FINDING IDENTITY
================

The lifecycle repository's catalogue gives every finding one fingerprint — path,
line and category — that survives across cycles, so the same defect keeps one
identity however many lenses report it. Two reviewers reporting the same defect
produce **one** finding with the agreement recorded, not two. A duplicate is
recorded ``duplicate-of`` against the finding it repeats: not deleted, and not
counted twice. Similar wording is not evidence of the same defect, so wording is
not part of the fingerprint.

ONE HISTORY PER UNIT
====================

A unit has one review history for the life of the run. Starting a fresh one is
refused, because a fresh history resets the cycle counter and puts scores from two
different lens sets side by side as though they were comparable. That is the whole
of issue 946.

ONE COUNTER PER LOOP
====================

A run has two repair loops — the pre-merge code-review loop and the post-merge
repair loop — and each keeps its **own** allowance and its own count under the same
rules. Every entry therefore carries a ``loop`` field valued ``code_review`` or
``post_merge``, and the allowance check counts entries whose loop matches rather
than the array's length. Without the field a long testing phase would silently
spend the pre-merge budget.

READING AN OLDER RESULT
=======================

A ``review_result.v1`` entry already in a record is reported by name, preserved
unchanged, and counted toward no allowance: its cycle accounting used a different
acceptance rule and is not comparable to this one. Silently upgrading it would put
incomparable scores in one history, which is the thing above this one exists to
prevent.

PUBLICATION
===========

Exactly one pull-request comment, naming the reviewed revision as a full
forty-character commit identifier. **Never an approving review**, in any of its
forms. Publication commits nothing, pushes nothing, and does not advance ``HEAD`` —
issue 935 reports the opposite arrangement, where publishing the artifact moved the
branch and broke the caller's freshness check.

Publication lives in this module rather than a fourth script because issue 1001
names exactly three, and because binding the comment to the result it renders is
what makes it impossible to publish a comment naming a revision other than the one
the result records.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import subprocess  # nosec B404 — fixed argv, no shell
import sys
from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parent))

import run_record  # noqa: E402

RESULT_SCHEMA = "review_result.v2"
LEGACY_RESULT_SCHEMA = "review_result.v1"

#: The two repair loops, each with its own allowance and its own counter.
LOOP_CODE_REVIEW = "code_review"
LOOP_POST_MERGE = "post_merge"
LOOPS = (LOOP_CODE_REVIEW, LOOP_POST_MERGE)

#: The catalogue's status vocabulary. Eight values, and no others.
STATUS_VOCABULARY = (
    "open",
    "fixed-verified",
    "unresolved",
    "disputed",
    "out-of-scope",
    "evidence-gap",
    "withdrawn",
    "duplicate-of",
)

#: The catalogue's severity vocabulary.
SEVERITY_VOCABULARY = ("P0", "P1", "P2", "P3")

#: The catalogue's four persistent-finding classifications (operator decision C6).
CLASSIFICATION_VOCABULARY = (
    "out-of-scope",
    "repairable-first",
    "evidence-gap",
    "disputed",
)

#: A full commit identifier. An abbreviation or a symbolic ref stops meaning
#: anything once the branch moves, so neither is accepted as a reviewed revision.
FULL_SHA_RE = re.compile(r"^[0-9a-f]{40}$")

EXIT_OK = 0
EXIT_INTERNAL = 1
EXIT_REFUSED = 2
EXIT_UNKNOWN_VERSION = 3


class ReviewResultError(ValueError):
    """A refusal this module owns. The command line maps it to exit 2."""


class HistoryConflictError(ReviewResultError):
    """A second review history was requested for a unit that already has one."""


# ---------------------------------------------------------------------------
# Findings
# ---------------------------------------------------------------------------


def fingerprint(path: str, line: int | str, category: str) -> str:
    """The catalogue's finding identity: a fingerprint of path, line and category.

    Stable across cycles, so the same defect keeps one identity. Wording is
    deliberately excluded: two findings worded alike are not thereby the same
    defect, and folding them together on wording would merge two real problems
    into one repair.
    """
    canonical = f"{path}:{line}:{category}"
    return "fp:" + hashlib.sha256(canonical.encode("utf-8")).hexdigest()[:32]


@dataclass
class Finding:
    """One finding in the shared schema the lifecycle repository's catalogue defines."""

    path: str
    line: int | str
    category: str
    lens: str
    dimension: str
    severity: str
    evidence: str
    impact: str
    confidence: str = "medium"
    owner: str = "review-fixer"
    status: str = "open"
    first_seen_cycle: int = 1
    classification: str | None = None
    duplicate_of: str | None = None
    agreed_by: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        if self.severity not in SEVERITY_VOCABULARY:
            raise ReviewResultError(
                f"finding severity {self.severity!r} is not one of {list(SEVERITY_VOCABULARY)}"
            )
        if self.status not in STATUS_VOCABULARY:
            raise ReviewResultError(
                f"finding status {self.status!r} is not one of {list(STATUS_VOCABULARY)}"
            )
        if self.classification is not None and self.classification not in CLASSIFICATION_VOCABULARY:
            raise ReviewResultError(
                f"finding classification {self.classification!r} is not one of "
                f"{list(CLASSIFICATION_VOCABULARY)}"
            )
        if not str(self.evidence).strip():
            raise ReviewResultError(
                "a finding with no citation is an evidence gap, not a finding; evidence is "
                "required by the catalogue's own finding schema"
            )

    @property
    def id(self) -> str:
        return fingerprint(self.path, self.line, self.category)

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "lens": self.lens,
            "dimension": self.dimension,
            "severity": self.severity,
            "confidence": self.confidence,
            "evidence": self.evidence,
            "impact": self.impact,
            "owner": self.owner,
            "status": self.status,
            "first_seen_cycle": self.first_seen_cycle,
            "classification": self.classification,
            "duplicate_of": self.duplicate_of,
            "agreed_by": list(self.agreed_by),
            "path": self.path,
            "line": self.line,
            "category": self.category,
        }


def deduplicate(findings: list[Finding]) -> tuple[list[Finding], list[Finding]]:
    """Merge findings sharing one fingerprint; return (surviving, duplicates).

    The first finding for a fingerprint survives and records every later lens that
    agreed with it. Each later one is kept, marked ``duplicate-of`` the survivor —
    visible, and counted once.
    """
    survivors: dict[str, Finding] = {}
    duplicates: list[Finding] = []
    for finding in findings:
        key = finding.id
        existing = survivors.get(key)
        if existing is None:
            survivors[key] = finding
            continue
        if finding.lens not in existing.agreed_by and finding.lens != existing.lens:
            existing.agreed_by = (*existing.agreed_by, finding.lens)
        finding.status = "duplicate-of"
        finding.duplicate_of = key
        duplicates.append(finding)
    return list(survivors.values()), duplicates


# ---------------------------------------------------------------------------
# Lens results
# ---------------------------------------------------------------------------


@dataclass
class LensResult:
    """One lens's reading of one revision, with the provenance that makes it evidence."""

    lens: str
    strictness: str
    scorable: bool
    dimension_scores: dict[str, int] = field(default_factory=dict)
    non_applicable: dict[str, str] = field(default_factory=dict)
    executed: bool = True
    executor: dict[str, Any] = field(default_factory=dict)
    verification_reference: dict[str, Any] | None = None
    hosting: dict[str, Any] = field(default_factory=dict)
    checks_executed: list[dict[str, Any]] = field(default_factory=list)
    threshold: dict[str, Any] = field(default_factory=dict)
    scored: bool = True

    def derived_overall(self) -> float | None:
        """The weighted mean of applicable dimension scores, to one decimal place.

        Rounded half away from zero, which is the catalogue's stated rule and not
        Python's default banker's rounding.
        """
        if not self.dimension_scores:
            return None
        total = sum(self.dimension_scores.values())
        count = len(self.dimension_scores)
        raw = total / count
        return float(int(raw * 10 + (0.5 if raw >= 0 else -0.5)) / 10)

    def to_dict(self) -> dict[str, Any]:
        return {
            "lens": self.lens,
            "strictness": self.strictness,
            "scorable": self.scorable,
            "scored": self.scored,
            "executed": self.executed,
            "dimension_scores": dict(self.dimension_scores),
            "non_applicable_dimensions": dict(self.non_applicable),
            "derived_overall": self.derived_overall(),
            "threshold": dict(self.threshold),
            "executor": dict(self.executor),
            "verification_reference": self.verification_reference,
            "hosting": dict(self.hosting),
            "checks_executed": list(self.checks_executed),
        }


# ---------------------------------------------------------------------------
# The result
# ---------------------------------------------------------------------------


@dataclass
class ReviewResult:
    """One cycle's ``review_result.v2``."""

    revision: str
    roster_hash: str
    outcome: str
    cycle: int
    loop: str
    unit: str
    lens_results: list[LensResult] = field(default_factory=list)
    findings: list[Finding] = field(default_factory=list)
    duplicates: list[Finding] = field(default_factory=list)
    advisory_findings: list[Finding] = field(default_factory=list)
    repair_accounting: dict[str, Any] = field(default_factory=dict)
    residual_issues: list[int] = field(default_factory=list)
    provenance: dict[str, Any] = field(default_factory=dict)
    checks_and_coverage_gaps: dict[str, Any] = field(default_factory=dict)
    reason: str = ""

    def __post_init__(self) -> None:
        if not FULL_SHA_RE.match(self.revision):
            raise ReviewResultError(
                f"reviewed revision {self.revision!r} is not a full forty-character commit "
                "identifier; an abbreviation or a symbolic reference stops meaning anything "
                "once the branch moves"
            )
        if self.loop not in LOOPS:
            raise ReviewResultError(f"loop {self.loop!r} is not one of {list(LOOPS)}")

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema": RESULT_SCHEMA,
            "cycle": self.cycle,
            "loop": self.loop,
            "unit": self.unit,
            "revision": self.revision,
            "roster_hash": self.roster_hash,
            "outcome": self.outcome,
            "reason": self.reason,
            "per_lens_results": [row.to_dict() for row in self.lens_results],
            "findings": [row.to_dict() for row in self.findings],
            "duplicate_findings": [row.to_dict() for row in self.duplicates],
            "advisory_findings": [row.to_dict() for row in self.advisory_findings],
            "repair_accounting": dict(self.repair_accounting),
            "residual_issues": list(self.residual_issues),
            "checks_and_coverage_gaps": dict(self.checks_and_coverage_gaps),
            "provenance": dict(self.provenance),
        }


# ---------------------------------------------------------------------------
# The run record's review history
# ---------------------------------------------------------------------------


def legacy_entries(record: run_record.RunRecord) -> list[dict[str, Any]]:
    """Entries in the record written against the older result schema."""
    return [
        entry
        for entry in record.review_cycles
        if isinstance(entry, dict) and entry.get("schema") == LEGACY_RESULT_SCHEMA
    ]


def history_for(record: run_record.RunRecord, unit: str, loop: str) -> list[dict[str, Any]]:
    """This unit's entries in this loop, oldest first. Legacy entries are excluded."""
    return [
        entry
        for entry in record.review_cycles
        if isinstance(entry, dict)
        and entry.get("schema") == RESULT_SCHEMA
        and entry.get("unit") == unit
        and entry.get("loop") == loop
    ]


def cycles_used(record: run_record.RunRecord, unit: str, loop: str) -> int:
    """How many cycles this unit has spent in this loop.

    Counted per loop, never across the whole record: the two loops keep separate
    allowances, and counting the array's length would let a long testing phase
    spend the pre-merge budget.
    """
    return len(history_for(record, unit, loop))


def next_cycle(record: run_record.RunRecord, unit: str, loop: str) -> int:
    """The cycle number this unit's next result in this loop takes."""
    return cycles_used(record, unit, loop) + 1


def refuse_second_history(record: run_record.RunRecord, unit: str, loop: str) -> None:
    """Refuse a request to start a fresh history for a unit that already has one.

    Issue 946: a fresh history resets the cycle counter and shows incomparable
    scores. The refusal names the existing history's cycle count so the caller can
    see what it would have discarded.
    """
    existing = history_for(record, unit, loop)
    if existing:
        raise HistoryConflictError(
            f"review_result: unit {unit!r} already has a review history in the {loop} loop with "
            f"{len(existing)} cycle(s), the latest at revision "
            f"{existing[-1].get('revision', 'UNKNOWN')}; a fresh history would reset the cycle "
            "counter and place incomparable scores side by side, so it is refused. Append the "
            "next cycle to the existing history instead."
        )


def comparable_lens_set(
    record: run_record.RunRecord, unit: str, loop: str, lenses: list[str]
) -> None:
    """Refuse a result whose lens set differs from the history it joins.

    Scores are compared only within the declared lens set. The roster is frozen
    for the whole run, so a differing set means the roster changed underneath the
    history — which the lifecycle repository permits only through a recorded,
    operator-approved amendment.
    """
    existing = history_for(record, unit, loop)
    if not existing:
        return
    previous = [row.get("lens") for row in existing[-1].get("per_lens_results", [])]
    if sorted(filter(None, previous)) != sorted(lenses):
        raise ReviewResultError(
            f"review_result: unit {unit!r} has a history scored against lenses "
            f"{sorted(filter(None, previous))} and this result names {sorted(lenses)}; the "
            "roster is frozen for the whole run, and scores are compared only within one "
            "declared lens set"
        )


def append_result(
    record: run_record.RunRecord,
    result: ReviewResult,
) -> run_record.RunRecord:
    """Append *result* to the record's review history.

    Legacy entries are left exactly as they are. A missing key is not a refusal.
    """
    cycles = list(record.review_cycles)
    cycles.append(result.to_dict())
    return run_record.RunRecord(**{**record.__dict__, "review_cycles": cycles})


# ---------------------------------------------------------------------------
# Residual issues at the cycle cap
# ---------------------------------------------------------------------------


def residual_issue_payloads(result: ReviewResult, *, parent_issue: int) -> list[dict[str, str]]:
    """One linked defect per still-unresolved finding, for the capped run.

    Prepared rather than filed here: filing is a network write, and a module that
    both decides and files gives a test no seam to stand in. The caller passes
    these to mission-control, which owns issue creation, and records the numbers
    it returns on the result.
    """
    payloads: list[dict[str, str]] = []
    for finding in result.findings:
        if finding.status in ("fixed-verified", "withdrawn", "duplicate-of"):
            continue
        payloads.append(
            {
                "title": f"Residual review finding: {finding.category} at {finding.path}",
                "body": (
                    f"Carried out of the review of issue #{parent_issue} at revision "
                    f"`{result.revision}` when the repair allowance was exhausted.\n\n"
                    f"**Lens.** {finding.lens} / {finding.dimension}\n"
                    f"**Severity.** {finding.severity}\n"
                    f"**Evidence.** {finding.evidence}\n"
                    f"**Impact.** {finding.impact}\n"
                    f"**Finding id.** `{finding.id}`\n\n"
                    "The run proceeded with `cycle_cap_best_available`. Follow-up on this issue "
                    "is not automatic and does not establish consensus."
                ),
            }
        )
    return payloads


# Filing the prepared residuals is deliberately NOT here. Opening an issue is
# mission-control's ownership lane, and a saga script that shelled out to the
# issue-creating command itself would cross it —
# `tests/test_check_ownership_lanes.py` fails on exactly that. The caller hands
# these payloads to mission-control, which files them and returns the numbers
# recorded on `ReviewResult.residual_issues`.


# ---------------------------------------------------------------------------
# Publication
# ---------------------------------------------------------------------------


def render_comment(result: ReviewResult) -> str:
    """Render the result as the body of one pull-request comment."""
    lines: list[str] = []
    lines.append(f"## Code review — `{result.outcome}`")
    lines.append("")
    lines.append(f"**Reviewed revision.** `{result.revision}`")
    lines.append(f"**Roster.** `{result.roster_hash}`")
    lines.append(f"**Cycle.** {result.cycle} of the {result.loop.replace('_', ' ')} loop")
    lines.append("")
    if result.reason:
        lines.append(result.reason)
        lines.append("")

    lines.append("### Lenses")
    lines.append("")
    lines.append("| Lens | Strictness | Derived overall | Threshold | Scored |")
    lines.append("|---|---|---|---|---|")
    for row in result.lens_results:
        overall = row.derived_overall()
        minimum = row.threshold.get("derived_overall_minimum", "—")
        lines.append(
            f"| {row.lens} | {row.strictness} | {overall if overall is not None else '—'} "
            f"| {minimum} | {'yes' if row.scored else 'no'} |"
        )
    lines.append("")

    if result.findings:
        lines.append("### Findings")
        lines.append("")
        lines.append("| Severity | Lens | Location | Status | Impact |")
        lines.append("|---|---|---|---|---|")
        for finding in sorted(result.findings, key=lambda f: f.severity):
            lines.append(
                f"| {finding.severity} | {finding.lens} | `{finding.path}:{finding.line}` "
                f"| {finding.status} | {finding.impact} |"
            )
        lines.append("")
    else:
        lines.append("No findings were reported against this revision.")
        lines.append("")

    if result.residual_issues:
        numbers = ", ".join(f"#{number}" for number in result.residual_issues)
        lines.append(f"**Residuals filed at the cycle cap.** {numbers}")
        lines.append("")

    lines.append(
        "This is a comment, not a review approval. A later commit carries no outcome from this one."
    )
    return "\n".join(lines)


def publish(
    result: ReviewResult,
    *,
    pull_request: str,
    repo: str,
    runner: Callable[..., Any] = subprocess.run,
) -> dict[str, Any]:
    """Post the result as exactly one pull-request comment.

    One ``gh pr comment``. Never ``gh pr review`` in any form: an approving review
    on a pull request would carry an outcome forward onto commits this review never
    read. Nothing is committed and nothing is pushed, so ``HEAD`` does not move and
    a caller's freshness check stays valid.
    """
    body = render_comment(result)
    argv = ["gh", "pr", "comment", pull_request, "--repo", repo, "--body", body]
    completed = runner(argv, capture_output=True, text=True, check=False)  # nosec B603
    if completed.returncode != 0:
        raise ReviewResultError(
            f"review_result: could not publish the review comment: {completed.stderr.strip()[:300]}"
        )
    return {
        "published": True,
        "comments": 1,
        "reviews": 0,
        "revision": result.revision,
        "argv": argv,
        "url": completed.stdout.strip(),
    }


# ---------------------------------------------------------------------------
# Command line
# ---------------------------------------------------------------------------


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Write review_result.v2 into the run record and render its comment."
    )
    parser.add_argument("--result", type=Path, required=True, help="A review_result.v2 file.")
    parser.add_argument("--issue", type=int, help="Append the result to this issue's record.")
    parser.add_argument("--store-root", type=Path, default=None, help="Run-record store override.")
    parser.add_argument(
        "--render-comment",
        type=Path,
        default=None,
        help="Write the comment body here instead of posting it.",
    )
    return parser


def _result_from_dict(payload: dict[str, Any]) -> ReviewResult:
    if payload.get("schema") != RESULT_SCHEMA:
        raise ReviewResultError(
            f"review_result: unknown result schema {payload.get('schema')!r}; this saga writes "
            f"{RESULT_SCHEMA}"
        )
    findings = [
        Finding(
            path=row["path"],
            line=row["line"],
            category=row["category"],
            lens=row["lens"],
            dimension=row.get("dimension", ""),
            severity=row.get("severity", "P3"),
            evidence=row.get("evidence", ""),
            impact=row.get("impact", ""),
            confidence=row.get("confidence", "medium"),
            status=row.get("status", "open"),
            first_seen_cycle=row.get("first_seen_cycle", 1),
        )
        for row in payload.get("findings", [])
    ]
    lens_results = [
        LensResult(
            lens=row["lens"],
            strictness=row.get("strictness", "standard"),
            scorable=bool(row.get("scorable", False)),
            dimension_scores=row.get("dimension_scores", {}),
            non_applicable=row.get("non_applicable_dimensions", {}),
            executed=bool(row.get("executed", True)),
            scored=bool(row.get("scored", True)),
            threshold=row.get("threshold", {}),
            executor=row.get("executor", {}),
            verification_reference=row.get("verification_reference"),
            hosting=row.get("hosting", {}),
        )
        for row in payload.get("per_lens_results", [])
    ]
    return ReviewResult(
        revision=payload["revision"],
        roster_hash=payload.get("roster_hash", "UNKNOWN"),
        outcome=payload.get("outcome", "review_incomplete"),
        cycle=int(payload.get("cycle", 1)),
        loop=payload.get("loop", LOOP_CODE_REVIEW),
        unit=payload.get("unit", "UNKNOWN"),
        lens_results=lens_results,
        findings=findings,
        reason=payload.get("reason", ""),
        residual_issues=list(payload.get("residual_issues", [])),
        provenance=payload.get("provenance", {}),
    )


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        payload = json.loads(args.result.read_text(encoding="utf-8"))
        result = _result_from_dict(payload)
        if args.render_comment is not None:
            args.render_comment.write_text(render_comment(result), encoding="utf-8")
            print(f"wrote {args.render_comment}")
        if args.issue is not None:
            store_root = (
                Path(args.store_root).resolve()
                if args.store_root
                else run_record.resolve_store_root()
            )
            record = run_record.load(store_root, args.issue, warn=None)
            if record is None:
                raise ReviewResultError(
                    f"review_result: no run record for issue {args.issue} under {store_root}"
                )
            for entry in legacy_entries(record):
                print(
                    f"review_result: entry for cycle {entry.get('cycle')} declares "
                    f"{LEGACY_RESULT_SCHEMA}; preserved unchanged and counted toward no "
                    f"allowance (this saga writes {RESULT_SCHEMA})",
                    file=sys.stderr,
                )
            updated = append_result(record, result)
            path = run_record.save(store_root, updated)
            print(f"appended cycle {result.cycle} ({result.outcome}) to {path}")
    except run_record.UnknownRecordVersionError as exc:
        print(str(exc), file=sys.stderr)
        return EXIT_UNKNOWN_VERSION
    except ReviewResultError as exc:
        print(str(exc), file=sys.stderr)
        return EXIT_REFUSED
    except (OSError, KeyError, json.JSONDecodeError) as exc:
        print(f"review_result: {exc}", file=sys.stderr)
        return EXIT_REFUSED
    return EXIT_OK


if __name__ == "__main__":
    raise SystemExit(main())
