"""Tests for reconcile_controller — the ONE level-triggered board-reconcile controller (#450).

Offline: the reversibility certificate and board_progression write mechanism are the REAL production
modules (imported by path, not faked), the ``board_writer`` and ``live_reader`` are injected fakes,
and the ledger is a real on-disk dir under ``tmp_path`` — no live gh, no mission-control child.

Every green assertion carries a baseline control (a sibling run where the guarded mechanism is
absent) proving the check could have failed: the dedup, the crash-retry, the drift surfacing, and
the HALT are each shown to be load-bearing, not vacuously true. Since W7 (SDLC R30/R32) the
controller holds no autonomous lifecycle-field write authority — the auto-correct allowlist is
empty, every outside drift halts with a named reason, and ``/loop`` drives the read-only
``detect_op`` tick.
"""

from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path
from types import ModuleType
from typing import Any

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


CERT = _load("reversibility_certificate")
BP = _load("board_progression")
RC = _load("reconcile_controller")

# The three lifecycle commands that share this ONE controller (#450). Every consumer drives the same
# ``reconcile_op`` entry point, so a behavior asserted "for all three" is asserted by parametrizing
# the shared call over these labels — the labels vary; the mechanism does not.
CONSUMERS = ["outcome", "work", "loop"]


class RecordingWriter:
    """Fake board_writer: records every call, optionally failing the first ``fail_times`` attempts."""

    def __init__(self, *, fail_times: int = 0) -> None:
        self.calls: list[dict[str, Any]] = []
        self._fail_times = fail_times

    def __call__(self, *, op_kind: str, repo: str, number: int, payload: dict) -> None:
        self.calls.append({"op_kind": op_kind, "repo": repo, "number": number, "payload": payload})
        if len(self.calls) <= self._fail_times:
            raise RuntimeError("board write failed (injected)")


class LiveBoard:
    """Fake live_reader backing store: an outside actor can mutate a field between ticks."""

    def __init__(self) -> None:
        self.values: dict[tuple[str, str, int], str] = {}

    def set(self, op_kind: str, repo: str, number: int, value: str) -> None:
        self.values[(op_kind, repo, number)] = value

    def reader(self, op_kind: str, repo: str, number: int) -> str:
        return self.values.get((op_kind, repo, number), "")


def _ledger(tmp_path: Path, name: str = "ledger") -> Path:
    d = tmp_path / name
    d.mkdir(parents=True, exist_ok=True)
    return d


def _ledger_files(ledger_dir: Path) -> list[Path]:
    return list(ledger_dir.glob("*.json"))


# ---------------------------------------------------------------------------
# R4 / F1 — rapid double tick converges on exactly one write + one ledger entry
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("consumer", CONSUMERS)
def test_rapid_double_tick_single_write(tmp_path: Path, consumer: str) -> None:
    """Two ticks on the same (repo, issue, op, target_state) → exactly one applied write, one ledger
    entry, for all three of /outcome, /work, /loop (they share this controller)."""
    ledger = _ledger(tmp_path, f"{consumer}-shared")
    writer = RecordingWriter()
    live = LiveBoard()
    kw: dict[str, Any] = {
        "board_writer": writer,
        "ledger_dir": ledger,
        "live_reader": live.reader,
    }

    tick1 = RC.reconcile_op("set-field-status", "infiquetra/saga", 450, "Done", **kw)
    assert tick1["status"] == "written"
    # The first write lands; the outside board now holds what saga drove.
    live.set("set-field-status", "infiquetra/saga", 450, "Done")

    tick2 = RC.reconcile_op("set-field-status", "infiquetra/saga", 450, "Done", **kw)
    assert tick2["status"] == "skipped", (
        "second tick must observe the first's ledger entry and no-op"
    )

    assert len(writer.calls) == 1, "exactly one applied write across the double tick"
    assert len(_ledger_files(ledger)) == 1, "exactly one ledger entry across the double tick"


def test_rapid_double_tick_control_without_shared_ledger(tmp_path: Path) -> None:
    """BASELINE CONTROL: without a shared ledger (each tick keyed into its own dir) the same double
    tick applies TWO writes — proving the shared idempotency ledger is what collapses it to one."""
    writer = RecordingWriter()
    live = LiveBoard()
    for i in range(2):
        RC.reconcile_op(
            "set-field-status",
            "infiquetra/saga",
            450,
            "Done",
            board_writer=writer,
            ledger_dir=_ledger(tmp_path, f"isolated-{i}"),
            live_reader=live.reader,
        )
    assert len(writer.calls) == 2, "no shared ledger → the dedup cannot fire → two writes"


# ---------------------------------------------------------------------------
# F3 — crash between expected-state compute and ledger write is retried, not skipped
# ---------------------------------------------------------------------------


def test_crash_safe_resume(tmp_path: Path) -> None:
    """A crash after the board write but before the ledger key lands leaves the key absent; the next
    tick recomputes, finds no key, and re-drives the (idempotent) write — never a permanent skip."""
    ledger = _ledger(tmp_path)
    writer = RecordingWriter()
    live = LiveBoard()

    def crashing_write_once(path: Path, content: str) -> bool:
        raise OSError("ledger fsync crashed after the board write committed")

    crashed = RC.reconcile_op(
        "set-field-status",
        "infiquetra/saga",
        450,
        "Done",
        board_writer=writer,
        ledger_dir=ledger,
        live_reader=live.reader,
        write_once=crashing_write_once,
    )
    assert crashed["status"] == "error" and crashed.get("may_reapply") is True
    assert len(_ledger_files(ledger)) == 0, "the crash left NO ledger key"
    assert len(writer.calls) == 1

    # Next tick — real write_once. Key still absent → re-drive, then record.
    resumed = RC.reconcile_op(
        "set-field-status",
        "infiquetra/saga",
        450,
        "Done",
        board_writer=writer,
        ledger_dir=ledger,
        live_reader=live.reader,
    )
    assert resumed["status"] == "written", "the lost write is retried, not skipped"
    assert len(writer.calls) == 2, "the board write was re-driven on resume"
    assert len(_ledger_files(ledger)) == 1


def test_crash_safe_resume_control_clean_write_is_not_retried(tmp_path: Path) -> None:
    """BASELINE CONTROL: when the FIRST tick records its ledger key cleanly, the next tick skips —
    proving the resume-retry above happens only because the crash left the key absent."""
    ledger = _ledger(tmp_path)
    writer = RecordingWriter()
    live = LiveBoard()
    first = RC.reconcile_op(
        "set-field-status",
        "infiquetra/saga",
        450,
        "Done",
        board_writer=writer,
        ledger_dir=ledger,
        live_reader=live.reader,
    )
    assert first["status"] == "written"
    live.set("set-field-status", "infiquetra/saga", 450, "Done")
    second = RC.reconcile_op(
        "set-field-status",
        "infiquetra/saga",
        450,
        "Done",
        board_writer=writer,
        ledger_dir=ledger,
        live_reader=live.reader,
    )
    assert second["status"] == "skipped"
    assert len(writer.calls) == 1, "a cleanly-recorded write is never re-driven"


# ---------------------------------------------------------------------------
# R5 / F2 — outside field change while /work is at rest is re-detected + corrected
# ---------------------------------------------------------------------------


def _seed_asserted_status(ledger: Path, writer: RecordingWriter, live: LiveBoard) -> None:
    """Drive one clean status write so saga has asserted `Done`, then mirror it on the live board."""
    rec = RC.reconcile_op(
        "set-field-status",
        "infiquetra/saga",
        450,
        "Done",
        board_writer=writer,
        ledger_dir=ledger,
        live_reader=live.reader,
    )
    assert rec["status"] == "written"
    live.set("set-field-status", "infiquetra/saga", 450, "Done")


def test_work_outside_drift_halts_with_named_reason_not_rewrite(tmp_path: Path) -> None:
    """/work at rest, an operator/CI moves the saga-owned Status field away from `Done`; the next
    /work reconcile tick re-detects the drift and HALTs with a named reason — since W7 the
    controller holds no autonomous lifecycle-field write authority, so a drift is surfaced for the
    operator (M7), never auto-corrected into a second routine write."""
    ledger = _ledger(tmp_path)
    writer = RecordingWriter()
    live = LiveBoard()
    _seed_asserted_status(ledger, writer, live)

    # Outside edit while /work is at rest.
    live.set("set-field-status", "infiquetra/saga", 450, "In-Progress")
    writes_before_tick = len(writer.calls)

    halted = RC.reconcile_op(
        "set-field-status",
        "infiquetra/saga",
        450,
        "Done",
        board_writer=writer,
        ledger_dir=ledger,
        live_reader=live.reader,
    )
    assert halted["status"] == "halt" and halted["halt"] is True
    assert halted["halt_reason"] == "status-drift:In-Progress", (
        "the surfaced reason names the drift kind and the live value"
    )
    assert len(writer.calls) == writes_before_tick, (
        "a reversible board-field drift is surfaced, never auto-rewritten (W7/R30)"
    )


def test_work_outside_drift_control_no_drift_no_write(tmp_path: Path) -> None:
    """BASELINE CONTROL: with the live board still matching the asserted value, the same tick skips
    and drives NO write — proving the correction fires only on a genuine outside drift."""
    ledger = _ledger(tmp_path)
    writer = RecordingWriter()
    live = LiveBoard()
    _seed_asserted_status(ledger, writer, live)  # live stays "Done"

    rec = RC.reconcile_op(
        "set-field-status",
        "infiquetra/saga",
        450,
        "Done",
        board_writer=writer,
        ledger_dir=ledger,
        live_reader=live.reader,
    )
    assert rec["status"] == "skipped"
    assert len(writer.calls) == 1, "no drift → no corrective write"


def test_loop_detect_tick_surfaces_drift_without_write(tmp_path: Path) -> None:
    """/loop at rest (route-and-sequence), an outside edit moves the Status field; /loop's post-W7
    tick is the READ-ONLY ``detect_op`` — it reports the drift with the prepared saga value and
    drives no write of any kind (R33: /loop detects and submits, never writes)."""
    ledger = _ledger(tmp_path)
    writer = RecordingWriter()
    live = LiveBoard()
    _seed_asserted_status(ledger, writer, live)

    live.set("set-field-status", "infiquetra/saga", 450, "Backlog")  # outside move
    writes_before_tick = len(writer.calls)

    detected = RC.detect_op(
        "set-field-status",
        "infiquetra/saga",
        450,
        "Done",
        live_reader=live.reader,
    )
    assert detected["status"] == "drift"
    assert detected["drift_kind"] == "status-drift"
    assert detected["board_value"] == "Backlog"
    assert detected["saga_value"] == "Done", "the prepared correction is the asserted value"
    assert len(writer.calls) == writes_before_tick, "a detect tick can never drive a write"
    assert len(_ledger_files(ledger)) == 1, "detect mints no ledger key — it is not a write"


def test_loop_outside_drift_control_unreadable_live_skips(tmp_path: Path) -> None:
    """BASELINE CONTROL: an unreadable live field ("") is treated as unreadable, never as drift —
    so /loop's tick skips rather than overwriting on a transient read failure."""
    ledger = _ledger(tmp_path)
    writer = RecordingWriter()
    live = LiveBoard()
    _seed_asserted_status(ledger, writer, live)
    live.set("set-field-status", "infiquetra/saga", 450, "")  # unreadable this tick

    rec = RC.reconcile_op(
        "set-field-status",
        "infiquetra/saga",
        450,
        "Done",
        board_writer=writer,
        ledger_dir=ledger,
        live_reader=live.reader,
    )
    assert rec["status"] == "skipped"
    assert len(writer.calls) == 1, "unreadable live is not drift → no corrective write"


# ---------------------------------------------------------------------------
# R5 (HALT arm) — irreversible-transition outside drift HALTs, never overwrites
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("consumer", CONSUMERS)
def test_halt_on_irreversible_drift_issue_state(tmp_path: Path, consumer: str) -> None:
    """An outside actor reopens an issue saga had closed. Reversing that would destroy a human/CI
    lifecycle decision, so the controller HALTs with a named reason — for all three consumers."""
    ledger = _ledger(tmp_path, f"{consumer}-halt")
    writer = RecordingWriter()
    live = LiveBoard()

    seed = RC.reconcile_op(
        "sub-issue-close",
        "infiquetra/saga",
        450,
        "",
        board_writer=writer,
        ledger_dir=ledger,
        live_reader=live.reader,
    )
    assert seed["status"] == "written"
    live.set("sub-issue-close", "infiquetra/saga", 450, "closed")
    writes_after_seed = len(writer.calls)

    # Outside reopen while at rest.
    live.set("sub-issue-close", "infiquetra/saga", 450, "open")

    halted = RC.reconcile_op(
        "sub-issue-close",
        "infiquetra/saga",
        450,
        "",
        board_writer=writer,
        ledger_dir=ledger,
        live_reader=live.reader,
    )
    assert halted["status"] == "halt" and halted["halt"] is True
    assert halted["halt_reason"] == "external-reopen:open"
    assert len(writer.calls) == writes_after_seed, "a HALT never drives a corrective write"


@pytest.mark.parametrize("consumer", CONSUMERS)
def test_halt_on_certificate_gated_op(tmp_path: Path, consumer: str) -> None:
    """A certificate-GATE op (parent-issue-close is ALWAYS_OPERATOR) HALTs before any read or write —
    the fail-closed default for anything not in the reversibility allowlist, for all three consumers."""
    ledger = _ledger(tmp_path, f"{consumer}-gate")
    writer = RecordingWriter()
    live = LiveBoard()
    rec = RC.reconcile_op(
        "parent-issue-close",
        "infiquetra/saga",
        450,
        "",
        board_writer=writer,
        ledger_dir=ledger,
        live_reader=live.reader,
    )
    assert rec["status"] == "gated" and rec["halt"] is True
    assert rec["halt_reason"] == "certificate-gate:parent-issue-close"
    assert len(writer.calls) == 0 and _ledger_files(ledger) == []


def test_detect_distinguishes_reversible_drift_from_irreversible_halt(tmp_path: Path) -> None:
    """BASELINE CONTROL (post-W7): the unified halt in ``reconcile_op`` is not a loss of
    classification — the read-only ``detect_op`` still DISTINGUISHES the two drift classes. A
    reversible Status edit is surfaced as ``drift`` with a prepared correction; an irreversible
    open/closed change stays ``halt`` with its named reason. The operator sees which is which (R5).
    """
    ledger = _ledger(tmp_path)
    writer = RecordingWriter()
    live = LiveBoard()

    # Reversible class: a Status-field edit.
    _seed_asserted_status(ledger, writer, live)
    live.set("set-field-status", "infiquetra/saga", 450, "In-Progress")
    reversible = RC.detect_op(
        "set-field-status",
        "infiquetra/saga",
        450,
        "Done",
        live_reader=live.reader,
    )
    assert reversible["status"] == "drift" and reversible["drift_kind"] == "status-drift"

    # Irreversible class: an outside reopen. Seed a clean close, then flip it.
    close_writer = RecordingWriter()
    close_live = LiveBoard()
    close_ledger = _ledger(tmp_path, "halt-side")
    seeded = RC.reconcile_op(
        "sub-issue-close",
        "infiquetra/saga",
        450,
        "",
        board_writer=close_writer,
        ledger_dir=close_ledger,
        live_reader=close_live.reader,
    )
    assert seeded["status"] == "written"
    close_live.set("sub-issue-close", "infiquetra/saga", 450, "open")
    irreversible = RC.detect_op(
        "sub-issue-close",
        "infiquetra/saga",
        450,
        "",
        live_reader=close_live.reader,
    )
    assert irreversible["status"] == "halt" and irreversible["halt"] is True
    assert irreversible["halt_reason"] == "external-reopen:open"
    assert len(writer.calls) + len(close_writer.calls) == 2, (
        "neither class drives a corrective write in detect (W7)"
    )


# ---------------------------------------------------------------------------
# Shared-mechanism / delegation integrity
# ---------------------------------------------------------------------------


def test_outcome_reconcile_reexports_controller_vocabulary() -> None:
    """/outcome's resume-time detector single-sources its drift vocabulary from the controller — the
    same objects, not parallel copies (the #450 'one shared mechanism' claim, load-bearing)."""
    outcome_reconcile = _load("outcome_reconcile")
    assert outcome_reconcile.DRIFT_KINDS is RC.DRIFT_KINDS
    assert outcome_reconcile._drift_record is RC._drift_record
    assert outcome_reconcile._drift_id is RC._drift_id
    assert outcome_reconcile._close_satisfies_contract is RC._close_satisfies_contract


def test_reconcile_driver_maps_intents_to_records(tmp_path: Path) -> None:
    """The bulk driver returns one record per intent, preserving order and per-intent ``extra``."""
    ledger = _ledger(tmp_path)
    writer = RecordingWriter()
    live = LiveBoard()
    intents = [
        RC.ReconcileIntent(
            "set-field-status", "infiquetra/saga", 1, "Done", extra={"subplot_id": "a"}
        ),
        RC.ReconcileIntent(
            "parent-issue-close", "infiquetra/saga", 2, "", extra={"subplot_id": "b"}
        ),
    ]
    records = RC.reconcile(intents, board_writer=writer, ledger_dir=ledger, live_reader=live.reader)
    assert [r["subplot_id"] for r in records] == ["a", "b"]
    assert records[0]["status"] == "written"
    assert records[1]["status"] == "gated"


def test_cli_reconcile_emits_record_json(
    tmp_path: Path, capsys: pytest.CaptureFixture[str], monkeypatch: pytest.MonkeyPatch
) -> None:
    """The CLI /work and /loop invoke drives a real reconcile_op, printing the record JSON and
    exiting 0 on a healthy gate."""
    import sys

    monkeypatch.setattr(
        sys.modules["board_progression"], "resolve_mission_control_root", lambda: (tmp_path, 1)
    )
    rc = RC.main(
        [
            "reconcile",
            "--op",
            "parent-issue-close",  # GATE → reconcile_op withholds the write
            "--repo",
            "infiquetra/saga",
            "--number",
            "450",
            "--ledger-dir",
            str(_ledger(tmp_path)),
            "--no-drift-check",
        ]
    )
    assert rc == 0
    printed = json.loads(capsys.readouterr().out.strip())
    assert printed["status"] == "gated" and printed["halt"] is True


def test_cli_reconcile_gated_op_unresolvable_mission_control_still_gated_exit_zero(
    tmp_path: Path, capsys: pytest.CaptureFixture[str], monkeypatch: pytest.MonkeyPatch
) -> None:
    """#652: a gated op evaluates the certificate BEFORE resolving mission-control, returning
    {"status":"gated"} and exiting 0 even when mission-control cannot be resolved."""
    import sys

    def boom() -> tuple[Path, int]:
        raise RuntimeError("plugin-resolution: could not resolve a 'mission-control' root")

    monkeypatch.setattr(sys.modules["board_progression"], "resolve_mission_control_root", boom)
    ledger = _ledger(tmp_path)
    rc = RC.main(
        [
            "reconcile",
            "--op",
            "parent-issue-close",
            "--repo",
            "infiquetra/saga",
            "--number",
            "450",
            "--ledger-dir",
            str(ledger),
            "--no-drift-check",
        ]
    )
    assert rc == 0
    printed = json.loads(capsys.readouterr().out.strip())
    assert printed["status"] == "gated" and printed["halt"] is True
    # No ledger entry on a gated op, so a later tick in a healthy environment still writes.
    assert not list(ledger.glob("*.json"))


def test_cli_reconcile_unresolvable_mission_control_exits_nonzero(
    tmp_path: Path, capsys: pytest.CaptureFixture[str], monkeypatch: pytest.MonkeyPatch
) -> None:
    """#620/#652: when mission-control cannot be resolved (a consumer repo with a stale/absent install),
    an authorized op fails loud — one error JSON on stderr and a non-zero exit — rather than
    crashing on an uncaught exception or silently proceeding with a bad path."""
    import sys

    def boom() -> tuple[Path, int]:
        raise RuntimeError("plugin-resolution: could not resolve a 'mission-control' root")

    monkeypatch.setattr(sys.modules["board_progression"], "resolve_mission_control_root", boom)
    rc = RC.main(
        [
            "reconcile",
            "--op",
            "set-field-status",
            "--repo",
            "infiquetra/saga",
            "--number",
            "450",
            "--target-state",
            "Done",
            "--ledger-dir",
            str(_ledger(tmp_path)),
            "--no-drift-check",
        ]
    )
    assert rc == 1
    err = json.loads(capsys.readouterr().err.strip())
    assert err["ok"] is False
    assert "could not resolve" in err["error"]


# ---------------------------------------------------------------------------
# #812 repair — the drift half fails closed on a field it cannot read back
# ---------------------------------------------------------------------------


def test_present_key_skips_drift_check_for_a_field_the_live_reader_cannot_read(
    tmp_path: Path,
) -> None:
    """A ``Stage`` correction is never drift-judged against the live ``Status`` value.

    ``default_live_reader`` maps ``set-field-status`` to ``outcome_github.board_status``,
    which has no field parameter, and ``_expected_live`` takes no field either. Since #812
    admits ``Stage`` to the correction allowlist by name, a present-key tick for ``Stage``
    would otherwise compare the live *Status* against the Stage target and manufacture a
    false drift record — a correction request driven by a reading that was never about
    this field.
    """
    ledger = _ledger(tmp_path)
    writer = RecordingWriter()
    live = LiveBoard()
    kw: dict[str, Any] = {
        "board_writer": writer,
        "ledger_dir": ledger,
        "live_reader": live.reader,
    }

    first = RC.reconcile_op(
        "set-field-status", "infiquetra/saga", 450, "Done", payload={"field": "Stage"}, **kw
    )
    assert first["status"] == "written"
    assert first["field"] == "Stage"
    writes_after_seed = len(writer.calls)

    # The live *Status* now reads something else entirely. That is not Stage drift.
    live.set("set-field-status", "infiquetra/saga", 450, "In-Progress")

    second = RC.reconcile_op(
        "set-field-status", "infiquetra/saga", 450, "Done", payload={"field": "Stage"}, **kw
    )
    assert second["status"] == "skipped", "a field-blind reading must never drive a write"
    assert "Status" in second["note"] and "Stage" in second["note"]
    assert len(writer.calls) == writes_after_seed, "no write from an uninterpretable reading"


def test_present_key_drift_on_the_readable_status_field_surfaces_never_corrects(
    tmp_path: Path,
) -> None:
    """CONTROL: the #812 fail-closed skip for unreadable fields is not a special-casing of Status —
    drift on the fully readable Status field is surfaced with the same halt, never auto-corrected
    (W7: the controller holds no autonomous lifecycle-field write authority)."""
    ledger = _ledger(tmp_path)
    writer = RecordingWriter()
    live = LiveBoard()
    kw: dict[str, Any] = {
        "board_writer": writer,
        "ledger_dir": ledger,
        "live_reader": live.reader,
    }

    RC.reconcile_op(
        "set-field-status", "infiquetra/saga", 450, "Done", payload={"field": "Status"}, **kw
    )
    live.set("set-field-status", "infiquetra/saga", 450, "In-Progress")
    writes_before_tick = len(writer.calls)

    record = RC.reconcile_op(
        "set-field-status", "infiquetra/saga", 450, "Done", payload={"field": "Status"}, **kw
    )
    assert record["status"] == "halt" and record["halt"] is True
    assert record["halt_reason"] == "status-drift:In-Progress"
    assert record["board_value"] == "In-Progress"
    assert len(writer.calls) == writes_before_tick
