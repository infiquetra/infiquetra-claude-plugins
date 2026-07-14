#!/usr/bin/env python3
"""Closure gate: evidence-gated /outcome closure (#397).

`outcome_orchestrator.harvest()` materializes a leaf as `done` the moment `barrier_satisfied()`
reports the leaf's PR merged or its tracking issue closed — it never reads an evidence ledger,
never checks whether a required check's evidence was recorded against the SHA the outcome is
actually closing at, and never asks whether a FAIL result was later silently overwritten by a
PASS. This module is the consumer that closes that gap: it reads the evidence ledger (#398,
`evidence_ledger.py`) for a node's declared `required_checks` and derives a typed verdict —
`satisfied` or a named `halt_reason` — every reconcile tick, purely on read.

**Schema (`Node.evidence`, the existing open pass-through map):**

- `required_checks: list[str]` — `check_id` values (e.g. `["qa", "code-review"]`) this node must
  have satisfying evidence for before it can be harvested `done`. Absent or empty -> the gate is
  trivially satisfied (every existing outcome spec, none of which declares this key, is
  unaffected).
- `reviewed_sha: str` (optional) — an explicit close-SHA override. When absent, a `code` node
  derives its close SHA from `outcome_github.head_ref_oid(node.github["pr"])` (the PR's pre-merge
  head commit SHA — exactly the SHA `/qa` and `/code-review` reviewed against, never the
  post-squash merge-commit SHA on `main`, which would never match any evidence entry).

**HALT-reason vocabulary** (named, distinct from the generic barrier-unsatisfied path):

- `missing-evidence:<check_id>` — the check has zero evidence entries anywhere in the ledger.
- `stale-sha:<check_id>` — the check has evidence, but none at the resolved close SHA.
- `unresolved-fail:<check_id>` — the latest verdict at the close SHA is a failing verdict (`FAIL`,
  or a real shipped producer's failing string — `no-ship`, `blocked`).
- `unsuperseded-fail:<check_id>` — an earlier failing verdict at the close SHA was followed by a
  passing verdict with no `payload["supersession_reason"]` on that later entry (an unexplained
  PASS never silently clears a FAIL).
- `unrecognized-verdict:<check_id>` — the latest verdict at the close SHA is neither a known
  passing nor a known failing string (KTD7) — HALT rather than silently treat it as a pass.
- `unresolvable-close-sha` — `required_checks` is declared but no close SHA (or no `leaf_saga_id`)
  can be resolved for this node.
- `chain-tamper:<subplot_id>` — `evidence_ledger.verify_chain()` detected a broken/tampered chain.
- `invalid-identity:<subplot_id>` — a malformed `leaf_saga_id` or `check_id` (e.g. traversal-
  shaped) was rejected by `evidence_ledger`'s `_safe_name` guard — HALT rather than an uncaught
  exception crashing the reconcile loop.

Supersession is a `payload["supersession_reason"]` convention on the entry that follows a FAIL —
not a new ledger entry kind (evidence-ledger plan R10 reserves the open `payload` dict for exactly
this kind of downstream extension; no schema surgery on the already-merged, already-tested ledger).

**Verdict vocabulary (KTD7).** `evidence_ledger.latest()`'s own `superseded_fail` flag hardcodes a
literal `"FAIL"` sentinel — correct for a synthetic fixture, but blind to what the shipped
producers actually write: `/qa` records `ship` / `ship-with-deferred` / `no-ship`
(`qa/SKILL.md` Phase 4.2) and `/code-review` records `clean` / `blocked`
(`code-review/SKILL.md` Phase 5.3). This module classifies independently, off its own closed
vocabulary (`_FAIL_VERDICTS` / `_PASS_VERDICTS`), so a real `no-ship`/`blocked` verdict is
correctly treated as failing rather than silently satisfied.

CLI::

    python3 closure_gate.py evaluate --repo-root <path> --spec <outcome-spec.json> \\
        --subplot-id <id>
"""

from __future__ import annotations

import argparse
import json
import sys
from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parent))

import evidence_ledger  # noqa: E402  (after the sys.path shim, by design)
import outcome_github  # noqa: E402
import outcome_spec  # noqa: E402

REQUIRED_CHECKS_KEY = "required_checks"
REVIEWED_SHA_KEY = "reviewed_sha"
SUPERSESSION_REASON_KEY = "supersession_reason"

# Closed verdict vocabulary (KTD7): evidence_ledger.py's own `latest().superseded_fail` hardcodes
# a literal "FAIL" sentinel -- correct for the issue's own golden-fixture tests, but blind to the
# REAL verdict strings the shipped producers write: `/qa` (`ship` / `ship-with-deferred` /
# `no-ship`, qa/SKILL.md Phase 4.2) and `/code-review` (`clean` / `blocked`, code-review/SKILL.md
# Phase 5.3). Treating only a literal "FAIL" as failing would silently satisfy the gate on a real
# `no-ship`/`blocked` verdict -- exactly the silent-pass failure mode this issue exists to kill.
# closure_gate therefore classifies independently of evidence_ledger.latest()'s own flag (HALT on
# an unrecognized string, R9's HALT-not-degrade bias, rather than assuming it is a pass).
_FAIL_VERDICTS = frozenset({"FAIL", "no-ship", "blocked"})
_PASS_VERDICTS = frozenset({"PASS", "ship", "ship-with-deferred", "clean"})


def _classify_verdict(verdict: str) -> str:
    """`"fail"` / `"pass"` / `"unrecognized"` for one verdict string against the closed vocabulary."""
    if verdict in _FAIL_VERDICTS:
        return "fail"
    if verdict in _PASS_VERDICTS:
        return "pass"
    return "unrecognized"


@dataclass(frozen=True)
class CheckResult:
    """One required check's classification against the resolved close SHA."""

    check_id: str
    satisfied: bool
    halt_reason: str | None
    verdict: str | None
    attempt: int | None
    superseded_fail: bool

    def to_dict(self) -> dict[str, Any]:
        return {
            "check_id": self.check_id,
            "satisfied": self.satisfied,
            "halt_reason": self.halt_reason,
            "verdict": self.verdict,
            "attempt": self.attempt,
            "superseded_fail": self.superseded_fail,
        }


@dataclass(frozen=True)
class GateVerdict:
    """The closure gate's verdict for one outcome-spec node (R1-R6, R9)."""

    subplot_id: str
    satisfied: bool
    halt_reason: str | None
    reason: str
    checks: list[CheckResult] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "subplot_id": self.subplot_id,
            "satisfied": self.satisfied,
            "halt_reason": self.halt_reason,
            "reason": self.reason,
            "checks": [c.to_dict() for c in self.checks],
        }


def _resolve_close_sha(node: Any, *, github_runner: Callable[..., Any] | None = None) -> str:
    """Explicit `evidence.reviewed_sha` wins; else a `code` node derives from its PR head (KTD2)."""
    override = node.evidence.get(REVIEWED_SHA_KEY)
    if isinstance(override, str) and override.strip():
        return override.strip()
    if node.kind == "code":
        pr = str(node.github.get("pr", ""))
        if pr:
            return outcome_github.head_ref_oid(pr, runner=github_runner)
    return ""


def _evaluate_check(store: evidence_ledger.Store, *, check_id: str, close_sha: str) -> CheckResult:
    """Classify one required check: missing / stale / unresolved-fail / unsuperseded-fail / ok.

    Reads ``evidence_ledger.history()`` directly (not ``latest()``) so the fail/pass
    classification is closure_gate's own closed vocabulary (KTD7), independent of
    ``latest().superseded_fail``'s literal-"FAIL"-only computation.
    """
    history_entries = evidence_ledger.history(store, check_id=check_id)
    if not history_entries:
        return CheckResult(check_id, False, f"missing-evidence:{check_id}", None, None, False)

    at_close_sha = sorted(
        (e for e in history_entries if e.get("reviewed_sha") == close_sha),
        key=lambda e: e["attempt"],
    )
    if not at_close_sha:
        return CheckResult(check_id, False, f"stale-sha:{check_id}", None, None, False)

    latest_entry = at_close_sha[-1]
    verdict = latest_entry["verdict"]
    attempt = latest_entry["attempt"]
    classification = _classify_verdict(verdict)

    if classification == "unrecognized":
        return CheckResult(
            check_id, False, f"unrecognized-verdict:{check_id}", verdict, attempt, False
        )
    if classification == "fail":
        return CheckResult(check_id, False, f"unresolved-fail:{check_id}", verdict, attempt, False)

    had_earlier_fail = any(_classify_verdict(e["verdict"]) == "fail" for e in at_close_sha[:-1])
    if had_earlier_fail:
        reason = latest_entry.get("payload", {}).get(SUPERSESSION_REASON_KEY)
        if not (isinstance(reason, str) and reason.strip()):
            return CheckResult(
                check_id, False, f"unsuperseded-fail:{check_id}", verdict, attempt, True
            )

    return CheckResult(check_id, True, None, verdict, attempt, had_earlier_fail)


def evaluate(
    node: Any,
    *,
    repo_root: Path,
    github_runner: Callable[..., Any] | None = None,
    implied_checks: tuple[str, ...] = (),
) -> GateVerdict:
    """The closure gate's verdict for one outcome-spec node.

    Pure read-time derivation (R9): no new committed or cached closure-status field, no writes.
    A node with no `required_checks` declared is trivially satisfied (R8) — every existing outcome
    spec, none of which declares this key today, keeps its current harvest behavior unchanged.

    ``implied_checks`` (#380) are spec-level checks the caller derives from the committed
    intent envelope (``ceremony_gates.reviews_required == "gate"`` implies ``code-review``
    on code leaves); they merge with the node's declared ``required_checks`` (declared order
    first, no duplicates) and are evaluated identically. Empty (every caller today that
    passes nothing) leaves behavior byte-identical.
    """
    sid = node.subplot_id
    declared = node.evidence.get(REQUIRED_CHECKS_KEY) or []
    required = list(declared) + [c for c in implied_checks if c not in declared]
    if not required:
        return GateVerdict(sid, True, None, "no required checks declared", [])

    saga_id = node.leaf_saga_id
    if not saga_id:
        return GateVerdict(
            sid,
            False,
            "unresolvable-close-sha",
            "node requires closure checks but has no leaf_saga_id to resolve the evidence store",
            [],
        )

    close_sha = _resolve_close_sha(node, github_runner=github_runner)
    if not close_sha:
        return GateVerdict(
            sid,
            False,
            "unresolvable-close-sha",
            "no reviewed_sha override and no derivable close SHA for this node's kind",
            [],
        )

    # A malformed leaf_saga_id or check_id (e.g. a traversal-shaped string) raises
    # EvidenceLedgerError from `_safe_name` — `OutcomeSpec.validate()` never catches this, since
    # `evidence` is an open pass-through map it deliberately does not schema-check. HALT rather
    # than let an uncaught exception crash the reconcile loop (R9's HALT-not-degrade — a mid-loop
    # crash is the opposite of a clean, named HALT).
    try:
        store = evidence_ledger.Store.for_saga(saga_id, repo_root)
    except evidence_ledger.EvidenceLedgerError as exc:
        return GateVerdict(sid, False, f"invalid-identity:{sid}", str(exc), [])

    try:
        evidence_ledger.verify_chain(store)
    except evidence_ledger.EvidenceLedgerError as exc:
        return GateVerdict(sid, False, f"chain-tamper:{sid}", str(exc), [])

    try:
        checks = [
            _evaluate_check(store, check_id=check_id, close_sha=close_sha) for check_id in required
        ]
    except evidence_ledger.EvidenceLedgerError as exc:
        return GateVerdict(sid, False, f"invalid-identity:{sid}", str(exc), [])

    first_failure = next((c for c in checks if not c.satisfied), None)
    if first_failure is not None:
        return GateVerdict(
            sid,
            False,
            first_failure.halt_reason,
            f"required check {first_failure.check_id!r} not satisfied at close SHA {close_sha}",
            checks,
        )
    return GateVerdict(sid, True, None, "all required checks satisfied", checks)


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Closure gate: evidence-gated /outcome closure CLI (#397)."
    )
    parser.add_argument("--repo-root", default=".", help="Repo root (default cwd).")
    sub = parser.add_subparsers(dest="command", required=True)

    p_eval = sub.add_parser(
        "evaluate", help="Evaluate the closure gate for one subplot in an outcome spec."
    )
    p_eval.add_argument("--spec", required=True, help="Path to an outcome-spec.json")
    p_eval.add_argument("--subplot-id", required=True)

    args = parser.parse_args(argv)
    repo_root = Path(args.repo_root)

    if args.command == "evaluate":
        spec = outcome_spec.OutcomeSpec.from_json(Path(args.spec).read_text(encoding="utf-8"))
        node = next((n for n in spec.nodes if n.subplot_id == args.subplot_id), None)
        if node is None:
            print(f"unknown subplot_id {args.subplot_id!r} in {args.spec}", file=sys.stderr)
            return 1
        verdict = evaluate(node, repo_root=repo_root)
        print(json.dumps(verdict.to_dict(), indent=2, sort_keys=True))
        return 0 if verdict.satisfied else 1

    parser.error(f"unknown command {args.command!r}")
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
