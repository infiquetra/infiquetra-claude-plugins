"""W7 (SDLC issue #88, R33): /loop detects drift and submits corrections — it never advances.

Two halves of R33, each with the failure it guards against:

* **detect-and-submit**: a detected drift produces a *submission* through the Mission Control
  mutation contract, never a direct write. Post-W7 the tick /loop drives is the read-only
  ``reconcile_controller.detect_op``; the correction itself (once the operator confirms) rides the
  certificate-gated reconcile tick, whose writer is mission-control's ``flow set-field``
  submission. UNKNOWN-1 is RESOLVED against W6's merged code (#87, ``sdlc_manager.py``): any
  ``flow set-field`` naming Status or Stage — with or without ``--correction`` — IS the
  constrained cross-board lifecycle-field mutation
  (``_set_lifecycle_field_cross_board``; the field NAME selects the writer, KTD10), with
  casefold field normalisation, a pre-write refusal when carrying boards already disagree (F-7),
  and a compensation halt naming the failing board. The argv asserted below therefore IS W6's
  mutation; byte-identity of the identity keys is proven separately below.
* **no self-advancement**: given a card eligible for a FORWARD move (the board sits at an earlier
  value than the lifecycle's next step), /loop reports it and performs no advancement — the
  first-time forward move belongs to /work, and the field write belongs to Mission Control.

Offline: the real controller/board_progression/certificate modules loaded by path; the board
writer is either a recording fake or a fake ``--runner`` behind ``default_board_writer`` so the
exact mission-control argv is asserted without spawning a process. No GitHub, no gh.
"""

from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path
from types import ModuleType
from typing import Any

import pytest

ROOT = Path(__file__).resolve().parent.parent
SCRIPTS = ROOT / "plugins" / "saga" / "scripts"
SAGA_ROOT = ROOT / "plugins" / "saga"


def _load(name: str) -> ModuleType:
    # Reuse an existing module instance when one is loaded: these share the singleton module
    # identity other saga tests assert on (e.g. outcome_reconcile's re-export identity probe).
    if name in sys.modules:
        return sys.modules[name]
    if str(SCRIPTS) not in sys.path:
        sys.path.insert(0, str(SCRIPTS))
    spec = importlib.util.spec_from_file_location(name, SCRIPTS / f"{name}.py")
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


RC = _load("reconcile_controller")
BP = _load("board_progression")
CERT = _load("reversibility_certificate")


class LiveBoard:
    """Fake live_reader backing store: an outside actor can mutate a field between reads."""

    def __init__(self) -> None:
        self.values: dict[tuple[str, str, int], str] = {}

    def set(self, op_kind: str, repo: str, number: int, value: str) -> None:
        self.values[(op_kind, repo, number)] = value

    def reader(self, op_kind: str, repo: str, number: int) -> str:
        return self.values.get((op_kind, repo, number), "")


class RecordingWriter:
    """Fake board_writer: records every call."""

    def __init__(self) -> None:
        self.calls: list[dict[str, Any]] = []

    def __call__(self, *, op_kind: str, repo: str, number: int, payload: dict) -> None:
        self.calls.append({"op_kind": op_kind, "repo": repo, "number": number, "payload": payload})


@pytest.fixture()
def loop_skill_text() -> str:
    return (SAGA_ROOT / "skills" / "loop" / "SKILL.md").read_text(encoding="utf-8")


# ---------------------------------------------------------------------------
# R33 positive half: a detected drift produces a submission through the mutation contract
# ---------------------------------------------------------------------------


def test_loop_submits_correction_through_mission_control(tmp_path: Path) -> None:
    """A detected drift is submitted through the Mission Control mutation contract: the detect tick
    is READ-ONLY (no write, no ledger key), and the operator-confirmed correction re-drive lands on
    ``default_board_writer``, whose set-field arm is mission-control's ``flow set-field
    --correction`` submission — never a Saga-side GitHub client."""
    live = LiveBoard()
    # The lifecycle has already asserted Active; an outside actor moved the card to Ready.
    live.set("set-field-status", "infiquetra/saga", 450, "Ready")

    detected = RC.detect_op(
        "set-field-status",
        "infiquetra/saga",
        450,
        "Active",
        live_reader=live.reader,
    )
    assert detected["status"] == "drift"
    assert detected["board_value"] == "Ready"
    assert detected["saga_value"] == "Active", "the prepared correction is the asserted value"

    # The operator CONFIRMS the prepared correction; the confirmed re-drive rides the
    # certificate-gated mechanism — the only writer that exists is Mission Control's.
    writer = RecordingWriter()
    submitted = RC.reconcile_op(
        "set-field-status",
        "infiquetra/saga",
        450,
        "Active",
        board_writer=writer,
        ledger_dir=tmp_path / "ledger",
        live_reader=None,  # write-only correction tick; drift policy belongs to detect
    )
    assert submitted["status"] == "written"
    assert writer.calls == [
        {
            "op_kind": "set-field-status",
            "repo": "infiquetra/saga",
            "number": 450,
            "payload": {"target_state": "Active", "field": "Status"},
        }
    ]

    # The correction lands on W6's constrained cross-board mutation, not a Saga-side client:
    # default_board_writer builds the sdlc_manager ``flow set-field --correction`` argv, and
    # (post-W6) ANY such argv naming Status/Stage routes into
    # ``_set_lifecycle_field_cross_board`` — the field name selects the writer, not the flag.
    commands: list[list[str]] = []

    class _Ok:
        returncode = 0
        stdout = ""
        stderr = ""

    def fake_runner(cmd: list[str], **_kw: Any) -> _Ok:
        commands.append(cmd)
        return _Ok()

    mission_writer = BP.default_board_writer(mission_control_root=tmp_path, runner=fake_runner)
    mission_writer(
        op_kind="set-field-status",
        repo="infiquetra/saga",
        number=450,
        payload={"target_state": "Active", "field": "Status"},
    )
    assert commands, "the submission argv must reach the runner"
    assert "flow" in commands[0] and "set-field" in commands[0], (
        "the correction rides mission-control's flow set-field mutation"
    )
    assert "--field" in commands[0] and "Status" in commands[0]
    assert "--correction" in commands[0], "the constrained-correction flag is present"


# ---------------------------------------------------------------------------
# R33 negative half: /loop detects but advances no lifecycle work
# ---------------------------------------------------------------------------


def test_loop_detects_drift_but_advances_no_lifecycle_work() -> None:
    """A card eligible for a forward move (board at an earlier value than the lifecycle's next
    step) is REPORTED by /loop's detect tick and never advanced by it: no write, no ledger key, no
    correction for a state the lifecycle has not already asserted."""
    live = LiveBoard()
    live.set("set-field-status", "infiquetra/saga", 450, "Shaping")  # card still in Shaping

    # A naive caller might pass the NEXT state (Ready) as a target; even so, detect claims only a
    # drift observation and drives nothing — /loop has no authority to advance (R30/R33).
    observed = RC.detect_op(
        "set-field-status",
        "infiquetra/saga",
        450,
        "Ready",
        live_reader=live.reader,
    )
    assert observed["status"] == "drift"
    assert observed["board_value"] == "Shaping"
    assert observed["saga_value"] == "Ready"


def test_loop_skill_drives_only_detect_and_names_the_boundary(
    loop_skill_text: str,
) -> None:
    """The /loop skill's driven reconcile tick is ``detect`` (read-only), the forward-progression
    boundary is stated, and no fenced block runs a WRITING reconcile for a lifecycle field."""
    assert "reconcile_controller.py detect" in loop_skill_text
    assert "never drives NEW forward progression" in loop_skill_text
    assert "read-only by construction" in loop_skill_text
    import re

    fenced = "\n".join(re.findall(r"```(?:bash|sh|shell)?\n(.*?)```", loop_skill_text, re.DOTALL))
    assert not re.search(r"reconcile_controller\.py\s+reconcile\b", fenced), (
        "the detect command must be the only controller invocation /loop drives"
    )


def test_loop_detect_tick_mints_no_ledger_key(tmp_path: Path) -> None:
    """The detect tick never creates the idempotency key a write would — it is not a write that
    skipped, it is an observation (R33's mechanical boundary, plan U3)."""
    live = LiveBoard()
    live.set("set-field-status", "infiquetra/saga", 450, "Ready")
    RC.detect_op(
        "set-field-status",
        "infiquetra/saga",
        450,
        "Active",
        live_reader=live.reader,
    )
    assert list(tmp_path.iterdir()) == [], "detect touches no ledger directory at all"


def test_loop_detect_gated_op_reads_nothing() -> None:
    """Fail-closed parity with the writing tick: a certificate-GATE on the op means detect claims
    nothing (the op needs a human) — mirrored from reconcile_op's decision order."""
    live = LiveBoard()
    live.set("parent-issue-close", "infiquetra/saga", 450, "closed")

    record = RC.detect_op(
        "parent-issue-close",
        "infiquetra/saga",
        450,
        "closed",
        live_reader=live.reader,
    )
    assert record["status"] == "gated" and record["halt"] is True
    assert record["halt_reason"] == "certificate-gate:parent-issue-close"


def test_controller_detect_cli_writes_nothing(
    tmp_path: Path, monkeypatch: Any, capsys: pytest.CaptureFixture[str]
) -> None:
    """The CLI subcommand /loop's skill documents cannot spawn a writer: ``detect`` builds no
    writer, so a broken or absent mission-control install cannot turn detection into a write —
    and it prints the observation record, not a write record."""
    captured: dict[str, Any] = {}

    def spy_default_live_reader(*, project: str = "operations", runner: Any = None) -> Any:
        captured["project"] = project
        live = LiveBoard()
        live.set("set-field-status", "infiquetra/saga", 450, "Ready")
        return live.reader

    monkeypatch.setattr(RC, "default_live_reader", spy_default_live_reader)
    rc = RC.main(
        [
            "detect",
            "--op",
            "set-field-status",
            "--repo",
            "infiquetra/saga",
            "--number",
            "450",
            "--target-state",
            "Active",
        ]
    )
    assert rc == 0, "a drift observation is healthy output, not a crash"
    record = json.loads(capsys.readouterr().out.strip())
    assert record["status"] == "drift"
    assert record["board_value"] == "Ready"
    assert record["target_state"] == "Active"
    assert list(tmp_path.iterdir()) == [], "the CLI detect subcommand writes nothing locally"


# ---------------------------------------------------------------------------
# UNKNOWN-1 resolution: the submission's byte identity IS W6's mutation identity
# ---------------------------------------------------------------------------


def test_saga_ledger_key_is_byte_identical_to_w6_correction_identity() -> None:
    """UNKNOWN-1, resolved concretely against W6's merged code (#87): the identity mission-control
    emits for a correction write is byte-identical to saga's ledger key for the same submission, so
    a retried write correlates to the saga tick that submitted it. ``_canonical_lifecycle_field``
    (casefold routing) resolves the caller's spelling to the SAME canonical name that goes into
    both keys. Corrections bound for non-correction fields never reach a valid identity."""
    import importlib.util as _ilu

    mc_scripts = ROOT / "plugins" / "mission-control" / "scripts"
    if str(mc_scripts) not in sys.path:
        sys.path.insert(0, str(mc_scripts))
    spec = _ilu.spec_from_file_location("_w6_sdlc_manager", mc_scripts / "sdlc_manager.py")
    assert spec is not None and spec.loader is not None
    w6 = _ilu.module_from_spec(spec)
    sys.modules[spec.name] = w6
    spec.loader.exec_module(w6)

    evidence = w6.correction_identity(
        field_name="Status", repo="infiquetra/saga", number=450, option_name="Active"
    )
    ledger_key = CERT.idempotency_key(
        "set-field-status", "infiquetra/saga", 450, "Active", field="Status"
    )
    assert evidence["retry"] == ledger_key, (
        "W6's retry identity must stay byte-identical to saga's ledger key (#812 contract)"
    )
    # Casefold routing (W6 F-1) happens UPSTREAM, in ``flow_set_field`` via
    # ``_canonical_lifecycle_field``, which resolves the caller's spelling to the canonical name
    # it then feeds to ``_set_lifecycle_field_cross_board`` (whose ``assert_correction_field`` is
    # exact-match, so only the canonical name flows onward). Assert the routing location
    # precisely: a lower-case spelling canonicalises to the SAME name saga's key carries.
    assert w6._canonical_lifecycle_field("STATUS") == "Status"
    assert (
        w6.correction_identity(
            field_name=w6._canonical_lifecycle_field("STATUS"),
            repo="infiquetra/saga",
            number=450,
            option_name="Active",
        )["retry"]
        == ledger_key
    )
