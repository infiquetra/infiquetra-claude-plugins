#!/usr/bin/env python3
"""The reversible-mutation undo ledger: act-log-inverse-notify, not pause-by-default (#372).

The load-bearing default that keeps plan-declared pause points *additive* rather than making
every run pause-heavy: **reversible mutations do not pause**. Instead of gating an operator
before a cheap, reversible action, the run performs it, writes a proven inverse to this
ledger, and notifies the operator post-hoc. Pauses are then reserved for *irreversibles* —
operations with no registered inverse, which fall back to the existing gated-pause behavior.

Registered reversible operations (the v1 set per R10 — the fleet is NOT backfilled):

* ``board_move``   — mission-control board status move (inverse: move back)
* ``label_change`` — mission-control label set (inverse: restore prior labels)
* ``issue_edit``   — mission-control issue field edit (inverse: restore prior value)
* ``saga_branch``  — a created git branch (inverse: delete it)
* ``saga_pr``      — an opened PR (inverse: close it)

Each registered op has a **proven round-trip inverse**: :func:`record` computes the inverse
action, and applying the forward action then the inverse via :func:`apply_action` returns the
projected state to its pre-op value (:func:`round_trip_ok` proves this per op, the control
that makes R6's "only irreversibles pause by default" claim true rather than aspirational).

Ownership-lane note: this module is **gh-free**. It never calls ``gh issue``/``gh project``
directly (that write-ownership lane belongs to mission-control). It computes inverses and
records them; the owning subsystem supplies an ``apply_action`` callback (or uses the pure
in-memory model here) to replay them. That keeps ``scripts/check_ownership_lanes.py`` green.

Threat model / self-attestation
-------------------------------
The ledger is a self-attested act-log written by the run's own leaves. It records *what the
leaf claims it did* (before/after per target); the inverse is derived from that claim. A leaf
that mis-reports its ``before`` state would record a wrong inverse — the ledger authenticates
the *op type is reversible*, not that the reported before/after are the true world state.
An op type with no registered inverse is refused (:class:`NoInverseError`) so it can never be
recorded as "reversible"; the caller must fall back to a gated pause (R11).
"""

from __future__ import annotations

import argparse
import json
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import Any

LEDGER_VERSION = 1


class UndoLedgerError(ValueError):
    """A malformed ledger record or replay failure."""


class NoInverseError(UndoLedgerError):
    """The op type has no registered inverse — it is NOT reversible and must pause (R11)."""


@dataclass(frozen=True)
class OpRecord:
    """One recorded reversible mutation and its computed inverse action."""

    op_type: str
    target: str
    before: Any
    after: Any
    inverse: dict[str, Any]
    reason: str = ""
    at: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "op_type": self.op_type,
            "target": self.target,
            "before": self.before,
            "after": self.after,
            "inverse": self.inverse,
            "reason": self.reason,
            "at": self.at,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> OpRecord:
        try:
            return cls(
                op_type=data["op_type"],
                target=data["target"],
                before=data["before"],
                after=data["after"],
                inverse=data["inverse"],
                reason=data.get("reason", ""),
                at=data.get("at", ""),
            )
        except KeyError as exc:
            raise UndoLedgerError(f"ledger record missing field {exc}") from exc


# --------------------------------------------------------------------------------------------
# The inverse registry. Each inverter maps (before, after) -> an inverse ACTION dict that,
# applied by ``apply_action``, restores the projected state. The registry keys are exactly
# the reversible op types (R10); a type absent here has no inverse (R11).
# --------------------------------------------------------------------------------------------

Inverter = Callable[[Any, Any], dict[str, Any]]


def _inv_board_move(before: Any, after: Any) -> dict[str, Any]:
    # forward: move status -> after. inverse: move status back to before.
    return {"kind": "move", "to": before}


def _inv_label_change(before: Any, after: Any) -> dict[str, Any]:
    # forward: set labels -> after (a list). inverse: restore the prior label list.
    return {"kind": "set_labels", "labels": list(before) if before is not None else []}


def _inv_issue_edit(before: Any, after: Any) -> dict[str, Any]:
    # forward: set a field -> after. inverse: restore the prior field value.
    return {"kind": "set_field", "value": before}


def _inv_saga_branch(before: Any, after: Any) -> dict[str, Any]:
    # forward: CREATE branch named ``after``. inverse: DELETE it (distinct op kind).
    return {"kind": "delete_branch", "branch": after}


def _inv_saga_pr(before: Any, after: Any) -> dict[str, Any]:
    # forward: OPEN pr ``after``. inverse: CLOSE it (distinct op kind).
    return {"kind": "close_pr", "pr": after}


_REGISTRY: dict[str, Inverter] = {
    "board_move": _inv_board_move,
    "label_change": _inv_label_change,
    "issue_edit": _inv_issue_edit,
    "saga_branch": _inv_saga_branch,
    "saga_pr": _inv_saga_pr,
}

REVERSIBLE_OPS = frozenset(_REGISTRY)


def has_inverse(op_type: str) -> bool:
    """True iff ``op_type`` is a registered reversible operation (has a proven inverse)."""
    return op_type in _REGISTRY


def mutation_disposition(op_type: str) -> str:
    """Route a mutation: ``"proceed-with-undo"`` if reversible, else ``"pause"`` (R11).

    This is the decision R6/R10 hinge on: a reversible mutation proceeds under
    act-log-inverse-notify; an operation with no registered inverse is definitionally
    irreversible and falls back to the existing gated-pause behavior — never proceeds
    unpaused.
    """
    return "proceed-with-undo" if has_inverse(op_type) else "pause"


def build_inverse(op_type: str, before: Any, after: Any) -> dict[str, Any]:
    """Compute the inverse action for a mutation. Raises :class:`NoInverseError` if not reversible."""
    inverter = _REGISTRY.get(op_type)
    if inverter is None:
        raise NoInverseError(op_type)
    return inverter(before, after)


def apply_action(state: dict[str, Any], action: dict[str, Any], target: str) -> dict[str, Any]:
    """Apply one forward-or-inverse action to the projected mutation state (pure).

    The projected state is a small dict the owning subsystem models (a board is
    ``{ref: status}``; branches are ``{"branches": [...]}``; PRs are ``{ref: "open"/"closed"}``).
    This is the deterministic replay engine the ``/undo`` command drives; the real subsystem
    may instead supply its own applier over the live world. Returns a NEW state (no mutation).
    """
    kind = action.get("kind")
    new = dict(state)
    if kind == "move":
        new[target] = action["to"]
    elif kind == "set_labels":
        new[target] = list(action["labels"])
    elif kind == "set_field":
        new[target] = action["value"]
    elif kind == "create_branch":
        branches = list(new.get("branches", []))
        if action["branch"] not in branches:
            branches.append(action["branch"])
        new["branches"] = branches
    elif kind == "delete_branch":
        branches = [b for b in new.get("branches", []) if b != action["branch"]]
        new["branches"] = branches
    elif kind == "open_pr":
        new[target] = "open"
    elif kind == "close_pr":
        new[target] = "closed"
    else:
        raise UndoLedgerError(f"unknown replay action kind: {kind!r}")
    return new


def forward_action(op_type: str, before: Any, after: Any, target: str) -> dict[str, Any]:
    """The FORWARD action for a mutation — the mirror of :func:`build_inverse`, for round-trip proof."""
    if op_type == "board_move":
        return {"kind": "move", "to": after}
    if op_type == "label_change":
        return {"kind": "set_labels", "labels": list(after) if after is not None else []}
    if op_type == "issue_edit":
        return {"kind": "set_field", "value": after}
    if op_type == "saga_branch":
        return {"kind": "create_branch", "branch": after}
    if op_type == "saga_pr":
        return {"kind": "open_pr", "pr": after}
    raise NoInverseError(op_type)


def round_trip_ok(op_type: str, before: Any, after: Any, target: str) -> bool:
    """Prove the registered op's inverse round-trips: forward then inverse restores state (R11)."""
    original = _projected_before(op_type, before, target)
    forward = apply_action(original, forward_action(op_type, before, after, target), target)
    inverse = build_inverse(op_type, before, after)
    restored = apply_action(forward, inverse, target)
    return restored == original


def _projected_before(op_type: str, before: Any, target: str) -> dict[str, Any]:
    """The projected state slice BEFORE the forward op, per op type."""
    if op_type == "saga_branch":
        return {"branches": list(before) if before else []}
    if op_type == "saga_pr":
        return {target: "closed"}  # not-yet-open
    return {target: before}


# --------------------------------------------------------------------------------------------
# Ledger I/O (append-only JSONL) + the /undo replay path.
# --------------------------------------------------------------------------------------------


def record(
    ledger_path: Path,
    op_type: str,
    *,
    target: str,
    before: Any,
    after: Any,
    reason: str = "",
    at: str = "",
) -> dict[str, Any]:
    """Record a reversible mutation's inverse and return an operator notification.

    Raises :class:`NoInverseError` if ``op_type`` has no registered inverse — the caller must
    then fall back to a gated pause (R11), never record an irreversible op as reversible.
    """
    inverse = build_inverse(op_type, before, after)  # raises NoInverseError if not reversible
    rec = OpRecord(
        op_type=op_type,
        target=target,
        before=before,
        after=after,
        inverse=inverse,
        reason=reason,
        at=at,
    )
    ledger_path.parent.mkdir(parents=True, exist_ok=True)
    with ledger_path.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(rec.to_dict()) + "\n")
    return {
        "notified": True,
        "op_type": op_type,
        "target": target,
        "message": f"reversible {op_type} on {target} proceeded; inverse recorded to undo ledger",
    }


def read_ledger(ledger_path: Path) -> list[OpRecord]:
    """Read all ledger records oldest-first. Fails closed on a malformed line."""
    if not ledger_path.exists():
        return []
    records: list[OpRecord] = []
    for lineno, line in enumerate(ledger_path.read_text(encoding="utf-8").splitlines(), start=1):
        line = line.strip()
        if not line:
            continue
        try:
            data = json.loads(line)
        except json.JSONDecodeError as exc:
            raise UndoLedgerError(f"ledger line {lineno} is not valid JSON: {exc}") from exc
        records.append(OpRecord.from_dict(data))
    return records


def undo(
    ledger_path: Path,
    state: dict[str, Any],
    *,
    count: int = 1,
    applier: Callable[[dict[str, Any], dict[str, Any], str], dict[str, Any]] = apply_action,
) -> tuple[dict[str, Any], list[OpRecord]]:
    """Replay the inverse of the last ``count`` recorded ops (LIFO), returning (new_state, undone).

    Pops the applied records off the ledger tail (the ledger stays truthful — an undone op is
    no longer pending-undo) and applies each inverse via ``applier`` (default: the pure
    in-memory model). This is the ``/undo`` replay path. Raises :class:`UndoLedgerError` if
    there is nothing to undo.
    """
    records = read_ledger(ledger_path)
    if not records:
        raise UndoLedgerError("undo ledger is empty — nothing to replay")
    n = min(count, len(records))
    undone: list[OpRecord] = []
    new_state = state
    for rec in reversed(records[len(records) - n :]):
        new_state = applier(new_state, rec.inverse, rec.target)
        undone.append(rec)
    remaining = records[: len(records) - n]
    _rewrite(ledger_path, remaining)
    return new_state, undone


def _rewrite(ledger_path: Path, records: list[OpRecord]) -> None:
    if not records:
        ledger_path.write_text("", encoding="utf-8")
        return
    ledger_path.write_text(
        "".join(json.dumps(r.to_dict()) + "\n" for r in records), encoding="utf-8"
    )


def default_ledger_path(repo_root: Path) -> Path:
    """Canonical per-run undo-ledger location: the run's private ``.saga/`` state (git-ignored)."""
    return repo_root / ".saga" / "undo-ledger.jsonl"


def _main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Inspect / replay the reversible-op undo ledger")
    parser.add_argument("--repo-root", type=Path, default=Path.cwd())
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("show", help="list pending-undo records (oldest first)")
    sub.add_parser("ops", help="list the registered reversible op types")

    args = parser.parse_args(argv)
    path = default_ledger_path(args.repo_root)
    if args.command == "show":
        for rec in read_ledger(path):
            print(json.dumps(rec.to_dict()))
        return 0
    if args.command == "ops":
        for op in sorted(REVERSIBLE_OPS):
            print(op)
        return 0
    return 1


if __name__ == "__main__":
    raise SystemExit(_main())
