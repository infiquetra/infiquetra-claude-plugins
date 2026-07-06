#!/usr/bin/env python3
"""Effort-escrow ledger — per-unit actual-vs-planned effort accounting (#366 U4).

The effort label carries no lifecycle accounting today: no unit records what it actually spent
against what it was allocated, a cheap unit cannot return unused budget, and a risky unit cannot
ask for more *before* it runs. This ledger closes that gap:

- ``allocate(unit_id, amount)`` declares a unit's planned budget (in the ordinal ``to_spend`` unit
  the cost-weight table produces, so escrow and the #366 spend budget speak one currency).
- ``record_actual(unit_id, amount)`` records what the unit actually spent; when it under-spends,
  the unused remainder is **refunded** to a run-level pool (policy-gated).
- ``request_escalation(unit_id, requested)`` surfaces an escalation-request **before** a unit
  executes when its requested spend would exceed its allocation — so the operator sees it ahead of
  the overspend, not after (mirrors the #364 between-rounds gate: surface, never silently proceed).

Policy lives in ``plugins/saga/references/effort-policy.yaml`` (loaded via PyYAML like
``engine_registry.py``); an absent file resolves to the documented safe default (refund unused,
surface escalations, never auto-approve). The ledger state persists as JSON under the git-ignored
``.claude/saga/`` so ``/plan`` (allocate) and ``/work`` (record / report) share one run's accounting
across invocations. The CLI verbs ``allocate`` / ``record`` / ``report`` are the surface those skills
call — a named mechanism, not intent-only prose.
"""

from __future__ import annotations

import argparse
import json
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml

# Policy file default: beside the other saga reference configs (engine-registry.yaml lives here too).
DEFAULT_POLICY_PATH = Path(__file__).resolve().parent.parent / "references" / "effort-policy.yaml"
# Ledger state default: git-ignored machine-local run accounting.
DEFAULT_LEDGER_PATH = Path(".claude/saga/effort-ledger.json")


class EffortLedgerError(ValueError):
    """Raised on an invalid ledger operation (unknown unit, malformed policy, bad amount)."""


@dataclass(frozen=True)
class EffortPolicy:
    """How the ledger refunds unused allocation and surfaces escalation-requests.

    The absent-file default is the *safe* side of every axis: refund unused budget, surface an
    escalation-request before execution, and never auto-approve one (the operator decides).
    """

    refund_unused: bool = True
    surface_escalation_before_execution: bool = True
    auto_approve_escalation: bool = False

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> EffortPolicy:
        return cls(
            refund_unused=bool(data.get("refund_unused", True)),
            surface_escalation_before_execution=bool(
                data.get("surface_escalation_before_execution", True)
            ),
            auto_approve_escalation=bool(data.get("auto_approve_escalation", False)),
        )


def load_policy(path: Path | None = None) -> EffortPolicy:
    """Load the effort policy, or the documented safe default when the file is absent."""
    policy_path = path if path is not None else DEFAULT_POLICY_PATH
    if not policy_path.is_file():
        return EffortPolicy()  # absent file => safe default (#366 R8)
    raw = yaml.safe_load(policy_path.read_text(encoding="utf-8"))
    if raw is None:
        return EffortPolicy()  # empty file => safe default
    if not isinstance(raw, dict):
        raise EffortLedgerError(
            f"{policy_path}: effort policy must be a YAML mapping, got {type(raw)}"
        )
    return EffortPolicy.from_dict(raw)


@dataclass(frozen=True)
class EscalationRequest:
    """A unit's request for more budget than it was allocated, surfaced before it executes."""

    unit_id: str
    allocated: int
    requested: int
    reason: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "unit_id": self.unit_id,
            "allocated": self.allocated,
            "requested": self.requested,
            "reason": self.reason,
        }


@dataclass
class EffortLedger:
    """Per-unit escrow accounting for one run (allocations, actuals, refund pool, escalations)."""

    policy: EffortPolicy = field(default_factory=EffortPolicy)
    allocations: dict[str, int] = field(default_factory=dict)
    actuals: dict[str, int] = field(default_factory=dict)
    pool: int = 0
    escalations: list[EscalationRequest] = field(default_factory=list)

    def allocate(self, unit_id: str, amount: int) -> None:
        """Declare a unit's planned budget (ordinal to_spend units). Non-negative, re-allocatable."""
        if amount < 0:
            raise EffortLedgerError(f"allocation for {unit_id!r} must be >= 0, got {amount}")
        self.allocations[unit_id] = amount

    def record_actual(self, unit_id: str, amount: int) -> int:
        """Record a unit's actual spend; refund unused allocation to the pool. Returns the refund.

        Recording an actual for a unit that was never allocated is an error -- the allocation is the
        planned baseline the refund is computed against.
        """
        if amount < 0:
            raise EffortLedgerError(f"actual for {unit_id!r} must be >= 0, got {amount}")
        if unit_id not in self.allocations:
            raise EffortLedgerError(
                f"cannot record actual for un-allocated unit {unit_id!r} -- allocate() it first"
            )
        self.actuals[unit_id] = amount
        allocated = self.allocations[unit_id]
        refund = 0
        if amount < allocated and self.policy.refund_unused:
            refund = allocated - amount
            self.pool += refund
        return refund

    def request_escalation(
        self, unit_id: str, requested: int, reason: str = ""
    ) -> EscalationRequest | None:
        """Surface an escalation-request BEFORE the unit executes when it would exceed its allocation.

        Returns the request (and records it, when policy surfaces before execution) if ``requested``
        exceeds the unit's allocation; returns ``None`` when the request fits within allocation.
        Deliberately does not touch ``actuals`` -- the request is raised ahead of execution, not
        after an overspend.
        """
        if requested < 0:
            raise EffortLedgerError(f"requested for {unit_id!r} must be >= 0, got {requested}")
        allocated = self.allocations.get(unit_id, 0)
        if requested <= allocated:
            return None
        request = EscalationRequest(
            unit_id=unit_id, allocated=allocated, requested=requested, reason=reason
        )
        if self.policy.surface_escalation_before_execution:
            self.escalations.append(request)
        return request

    def to_dict(self) -> dict[str, Any]:
        return {
            "allocations": dict(self.allocations),
            "actuals": dict(self.actuals),
            "pool": self.pool,
            "escalations": [e.to_dict() for e in self.escalations],
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any], policy: EffortPolicy | None = None) -> EffortLedger:
        return cls(
            policy=policy if policy is not None else EffortPolicy(),
            allocations={str(k): int(v) for k, v in data.get("allocations", {}).items()},
            actuals={str(k): int(v) for k, v in data.get("actuals", {}).items()},
            pool=int(data.get("pool", 0)),
            escalations=[
                EscalationRequest(
                    unit_id=str(e["unit_id"]),
                    allocated=int(e["allocated"]),
                    requested=int(e["requested"]),
                    reason=str(e.get("reason", "")),
                )
                for e in data.get("escalations", [])
            ],
        )

    def save(self, path: Path) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(self.to_dict(), indent=2) + "\n", encoding="utf-8")

    @classmethod
    def load(cls, path: Path, policy: EffortPolicy | None = None) -> EffortLedger:
        if not path.is_file():
            return cls(policy=policy if policy is not None else EffortPolicy())
        return cls.from_dict(json.loads(path.read_text(encoding="utf-8")), policy=policy)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Effort-escrow ledger (#366).")
    parser.add_argument(
        "--ledger", type=Path, default=DEFAULT_LEDGER_PATH, help="ledger state JSON path"
    )
    parser.add_argument(
        "--policy", type=Path, default=None, help="effort-policy.yaml override path"
    )
    sub = parser.add_subparsers(dest="cmd", required=True)

    p_alloc = sub.add_parser("allocate", help="declare a unit's planned budget (/plan)")
    p_alloc.add_argument("--unit", required=True)
    p_alloc.add_argument("--amount", required=True, type=int)

    p_rec = sub.add_parser("record", help="record a unit's actual spend + refund unused (/work)")
    p_rec.add_argument("--unit", required=True)
    p_rec.add_argument("--actual", required=True, type=int)

    p_esc = sub.add_parser(
        "escalate", help="surface an escalation-request before a unit executes (/work)"
    )
    p_esc.add_argument("--unit", required=True)
    p_esc.add_argument("--requested", required=True, type=int)
    p_esc.add_argument("--reason", default="")

    sub.add_parser("report", help="print the current ledger (pool, allocations, escalations)")

    args = parser.parse_args(argv)
    try:
        policy = load_policy(args.policy)
        ledger = EffortLedger.load(args.ledger, policy=policy)
        if args.cmd == "allocate":
            ledger.allocate(args.unit, args.amount)
            ledger.save(args.ledger)
            print(f"allocated {args.amount} to {args.unit}")
            return 0
        if args.cmd == "record":
            refund = ledger.record_actual(args.unit, args.actual)
            ledger.save(args.ledger)
            print(
                f"recorded actual {args.actual} for {args.unit}; refunded {refund} (pool {ledger.pool})"
            )
            return 0
        if args.cmd == "escalate":
            request = ledger.request_escalation(args.unit, args.requested, args.reason)
            ledger.save(args.ledger)
            if request is None:
                print(
                    f"{args.unit}: requested {args.requested} fits within allocation -- no escalation"
                )
            else:
                print(
                    f"ESCALATION (before execution): {args.unit} requests {request.requested} "
                    f"vs allocation {request.allocated}"
                    + (f" -- {request.reason}" if request.reason else "")
                )
            return 0
        if args.cmd == "report":
            print(json.dumps(ledger.to_dict(), indent=2))
            return 0
    except EffortLedgerError as exc:
        print(f"EFFORT LEDGER ERROR: {exc}", file=sys.stderr)
        return 2
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
