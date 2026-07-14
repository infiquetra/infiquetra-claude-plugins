"""Acceptance + unit tests for the reversible-mutation undo ledger (#372).

Covers R10 (reversible mutations proceed under act-log-inverse-notify instead of pausing) and
R11 (each registered reversible operation has a PROVEN round-trip inverse; an operation with
no registered inverse falls back to the gated pause). ``round_trip_inverse`` proves the
inverse for *every* registered op (the control that makes "only irreversibles pause" true
rather than aspirational); ``no_inverse_falls_back_to_pause`` proves the fallback and pairs it
with a control showing a registered op does NOT pause.
"""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path
from types import ModuleType

import pytest

ROOT = Path(__file__).parent.parent
SCRIPTS = ROOT / "plugins" / "saga" / "scripts"


def _load(name: str) -> ModuleType:
    if str(SCRIPTS) not in sys.path:
        sys.path.insert(0, str(SCRIPTS))
    spec = importlib.util.spec_from_file_location(name, SCRIPTS / f"{name}.py")
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


UL = _load("undo_ledger")

# The v1 registered reversible-op set (R10) with a representative before/after per op. Each
# tuple: (op_type, before, after, target). These are the ONLY ops with a registered inverse.
_REGISTERED_CASES = [
    ("board_move", "Todo", "Active", "infiquetra#1"),
    ("label_change", ["bug"], ["bug", "priority-1"], "infiquetra#1"),
    ("issue_edit", "old title", "new title", "infiquetra#1"),
    ("saga_branch", [], "feat/work-372", "branch"),
    ("saga_pr", None, "PR#42", "pr"),
]


def test_registered_case_table_matches_the_registry() -> None:
    # guard: the case table below stays in lockstep with the actual registry (no op untested)
    assert {c[0] for c in _REGISTERED_CASES} == set(UL.REVERSIBLE_OPS)


@pytest.mark.parametrize("op_type,before,after,target", _REGISTERED_CASES)
def test_round_trip_inverse(op_type: str, before: object, after: object, target: str) -> None:
    # R11: applying the forward op then its recorded inverse returns the projected state to
    # its pre-op value — proven for EVERY registered reversible operation.
    assert UL.round_trip_ok(op_type, before, after, target) is True


def test_round_trip_inverse_via_ledger_record_and_undo(tmp_path: Path) -> None:
    # The full /undo replay path: record a reversible board move, then undo() replays the
    # inverse and restores the projected board state exactly.
    ledger = UL.default_ledger_path(tmp_path)
    board = {"infiquetra#1": "Todo"}
    # leaf performs the forward mutation (proceeds, does NOT pause) and logs the inverse
    board = UL.apply_action(board, {"kind": "move", "to": "Active"}, "infiquetra#1")
    note = UL.record(ledger, "board_move", target="infiquetra#1", before="Todo", after="Active")
    assert note["notified"] is True and "undo ledger" in note["message"]
    assert board == {"infiquetra#1": "Active"}
    # /undo replays the inverse -> the board is back to its pre-op status
    restored, undone = UL.undo(ledger, board)
    assert restored == {"infiquetra#1": "Todo"}  # proven round trip
    assert [r.op_type for r in undone] == ["board_move"]
    # the ledger is now empty (the undone op is no longer pending-undo)
    assert UL.read_ledger(ledger) == []


def test_undo_is_lifo_across_multiple_ops(tmp_path: Path) -> None:
    ledger = UL.default_ledger_path(tmp_path)
    state = {"i#1": "Todo"}
    state = UL.apply_action(state, {"kind": "move", "to": "Active"}, "i#1")
    UL.record(ledger, "board_move", target="i#1", before="Todo", after="Active")
    state = UL.apply_action(state, {"kind": "move", "to": "Done"}, "i#1")
    UL.record(ledger, "board_move", target="i#1", before="Active", after="Done")
    # undo once -> back to Active (LIFO: the most recent op is inverted first)
    state, undone = UL.undo(ledger, state)
    assert state == {"i#1": "Active"} and len(undone) == 1
    # undo again -> back to Todo
    state, _ = UL.undo(ledger, state)
    assert state == {"i#1": "Todo"}


def test_no_inverse_falls_back_to_pause(tmp_path: Path) -> None:
    # R11: an unregistered / no-inverse mutation must NOT proceed unpaused — it falls back to
    # the existing gated-pause behavior, and cannot be recorded as reversible.
    assert UL.has_inverse("force_push_main") is False
    assert UL.mutation_disposition("force_push_main") == "pause"
    with pytest.raises(UL.NoInverseError):
        UL.record(
            UL.default_ledger_path(tmp_path),
            "force_push_main",
            target="main",
            before="a",
            after="b",
        )
    with pytest.raises(UL.NoInverseError):
        UL.build_inverse("force_push_main", "a", "b")
    # control: a REGISTERED op proceeds-with-undo (does NOT pause) — proving the disposition
    # check discriminates rather than pausing everything.
    assert UL.mutation_disposition("board_move") == "proceed-with-undo"


def test_undo_empty_ledger_fails_closed(tmp_path: Path) -> None:
    with pytest.raises(UL.UndoLedgerError, match="nothing to replay"):
        UL.undo(UL.default_ledger_path(tmp_path), {})


def test_read_ledger_malformed_line_fails_closed(tmp_path: Path) -> None:
    ledger = UL.default_ledger_path(tmp_path)
    ledger.parent.mkdir(parents=True, exist_ok=True)
    ledger.write_text("{not json\n")
    with pytest.raises(UL.UndoLedgerError, match="not valid JSON"):
        UL.read_ledger(ledger)


def test_saga_branch_and_pr_inverses_are_distinct_op_kinds() -> None:
    # the branch/PR inverses are genuinely different OP KINDS (create->delete, open->close),
    # not a uniform "set back" — the inverter must know the semantic pairing.
    assert UL.build_inverse("saga_branch", [], "feat/x")["kind"] == "delete_branch"
    assert UL.build_inverse("saga_pr", None, "PR#9")["kind"] == "close_pr"
