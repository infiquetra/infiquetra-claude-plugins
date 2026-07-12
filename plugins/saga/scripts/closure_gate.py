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
- `unresolved-fail:<check_id>` — the latest verdict at the close SHA is still `FAIL`.
- `unsuperseded-fail:<check_id>` — an earlier `FAIL` at the close SHA was followed by a non-FAIL
  verdict with no `payload["supersession_reason"]` on that later entry (an unexplained PASS never
  silently clears a FAIL).
- `unresolvable-close-sha` — `required_checks` is declared but no close SHA (or no `leaf_saga_id`)
  can be resolved for this node.
- `chain-tamper:<subplot_id>` — `evidence_ledger.verify_chain()` detected a broken/tampered chain.

Supersession is a `payload["supersession_reason"]` convention on the entry that follows a FAIL —
not a new ledger entry kind (evidence-ledger plan R10 reserves the open `payload` dict for exactly
this kind of downstream extension; no schema surgery on the already-merged, already-tested ledger).

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

FAIL_VERDICT = "FAIL"


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
    """Classify one required check: missing / stale / unresolved-fail / unsuperseded-fail / ok."""
    history_entries = evidence_ledger.history(store, check_id=check_id)
    if not history_entries:
        return CheckResult(check_id, False, f"missing-evidence:{check_id}", None, None, False)

    at_close_sha = [e for e in history_entries if e.get("reviewed_sha") == close_sha]
    if not at_close_sha:
        return CheckResult(check_id, False, f"stale-sha:{check_id}", None, None, False)

    latest_result = evidence_ledger.latest(store, check_id=check_id, reviewed_sha=close_sha)
    verdict = latest_result.verdict
    attempt = latest_result.attempt

    if verdict == FAIL_VERDICT:
        return CheckResult(check_id, False, f"unresolved-fail:{check_id}", verdict, attempt, False)

    if latest_result.superseded_fail:
        latest_entry = latest_result.history[-1]
        reason = latest_entry.get("payload", {}).get(SUPERSESSION_REASON_KEY)
        if not (isinstance(reason, str) and reason.strip()):
            return CheckResult(
                check_id, False, f"unsuperseded-fail:{check_id}", verdict, attempt, True
            )

    return CheckResult(check_id, True, None, verdict, attempt, latest_result.superseded_fail)


def evaluate(
    node: Any,
    *,
    repo_root: Path,
    github_runner: Callable[..., Any] | None = None,
) -> GateVerdict:
    """The closure gate's verdict for one outcome-spec node.

    Pure read-time derivation (R9): no new committed or cached closure-status field, no writes.
    A node with no `required_checks` declared is trivially satisfied (R8) — every existing outcome
    spec, none of which declares this key today, keeps its current harvest behavior unchanged.
    """
    sid = node.subplot_id
    required = node.evidence.get(REQUIRED_CHECKS_KEY) or []
    if not required:
        return GateVerdict(sid, True, None, "no required checks declared", [])

    saga_id = node.leaf_saga_id
    if not saga_id:
        return GateVerdict(
            sid,
            False,
            "unresolvable-close-sha",
            "node declares required_checks but has no leaf_saga_id to resolve the evidence store",
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

    store = evidence_ledger.Store.for_saga(saga_id, repo_root)
    try:
        evidence_ledger.verify_chain(store)
    except evidence_ledger.EvidenceLedgerError as exc:
        return GateVerdict(sid, False, f"chain-tamper:{sid}", str(exc), [])

    checks = [_evaluate_check(store, check_id=check_id, close_sha=close_sha) for check_id in required]
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
