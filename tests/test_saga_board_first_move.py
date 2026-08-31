"""#927 U4: the pins that stop the missing-caller defect coming back.

The defect these exist for is stated plainly in issue #927: since the 0.145.0 change, **Saga makes
none of the project-board moves.** The mechanism shipped -- ``flow set-field --correction`` with the
field name part of the operation, its authorization and its retry identity -- and the *caller* never
did. A suite that proves the mechanism works proves nothing about that; what has to be provable is
that a standalone run **makes a first move at each permitted boundary**.

**What counts as proving the real path, and why it is not a fixture.** The proof is the recorded
``sdlc_manager.py`` argv: build the writer with ``board_progression.default_board_writer`` and the
injected ``runner`` seam it already accepts, drive the boundary, and read the captured command. That
exercises the real composition, the real certificate gate and the real field identity, and stops at
the process boundary -- the function's own docstring calls this the house pattern. A stand-in for
the controller would sit *above* the seam being proven, so it would assert the fake and claim the
path. **No test here may mutate a real board.** The injected runner is the boundary; nothing crosses
it, and no ``gh`` child is ever spawned.

**The boundaries are read out of the skill files, not restated here.** Each fenced submission block
in ``skills/plan/SKILL.md`` and ``skills/work/SKILL.md`` is parsed for its ``--target-state`` and
``--payload`` and driven through the real writer. A restated table would go green while the skill
said something else; this cannot.

**Every assertion checks BOTH fields, and that is the whole point.** ``Ready for Active`` is a valid
live ``Status`` on its own, so a ``Status``-only submission writes a legal value, gets a clean
record, and leaves ``Stage`` where it was. A test that asserts one captured assignment passes on
exactly that half-write.
"""

from __future__ import annotations

import importlib.util
import json
import re
import subprocess
import sys
from pathlib import Path
from types import ModuleType
from typing import Any

import pytest

ROOT = Path(__file__).resolve().parent.parent
SAGA_SCRIPTS = ROOT / "plugins" / "saga" / "scripts"
PLAN_SKILL = ROOT / "plugins" / "saga" / "skills" / "plan" / "SKILL.md"
WORK_SKILL = ROOT / "plugins" / "saga" / "skills" / "work" / "SKILL.md"


def _load(name: str) -> ModuleType:
    if name in sys.modules:
        return sys.modules[name]
    if str(SAGA_SCRIPTS) not in sys.path:
        sys.path.insert(0, str(SAGA_SCRIPTS))
    spec = importlib.util.spec_from_file_location(name, SAGA_SCRIPTS / f"{name}.py")
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


BP = _load("board_progression")
CERT = _load("reversibility_certificate")
RC = _load("reconcile_controller")


# ----------------------------------------------------------------- reading the skills' own moves

_FENCE = re.compile(r"```[A-Za-z0-9_+.-]*\n(.*?)```", re.DOTALL)
_TARGET = re.compile(r'--target-state\s+"([^"]+)"')
_PAYLOAD = re.compile(r"--payload\s+'(\{.*?\})'")


def submissions(path: Path) -> list[tuple[str, dict[str, Any]]]:
    """Every ``(target_state, payload)`` a skill file's fenced submissions carry, in file order."""
    found: list[tuple[str, dict[str, Any]]] = []
    for block in _FENCE.findall(path.read_text(encoding="utf-8")):
        if "--op set-field-status" not in block:
            continue
        target = _TARGET.search(block)
        payload = _PAYLOAD.search(block)
        assert target is not None and payload is not None, (
            f"a submission block in {path.name} is not runnable as written:\n{block}"
        )
        found.append((target.group(1), json.loads(payload.group(1))))
    return found


def assignments_in(argv: list[str]) -> list[tuple[str, str]]:
    """The ``--field X --option Y`` assignments one captured ``sdlc_manager.py`` argv carries."""
    found: list[tuple[str, str]] = []
    index = 0
    while index < len(argv) - 3:
        if argv[index] == "--field" and argv[index + 2] == "--option":
            found.append((argv[index + 1], argv[index + 3]))
            index += 4
            continue
        index += 1
    return found


class RecordingRunner:
    """The injected ``runner`` seam: records every argv, returns scripted results, spawns nothing."""

    def __init__(self, results: list[tuple[int, str, str]] | None = None) -> None:
        self.calls: list[list[str]] = []
        self._results = list(results or [])

    def __call__(self, cmd: Any, **kwargs: Any) -> subprocess.CompletedProcess[Any]:
        self.calls.append([str(part) for part in cmd])
        returncode, stdout, stderr = self._results.pop(0) if self._results else (0, "", "")
        return subprocess.CompletedProcess(cmd, returncode, stdout=stdout, stderr=stderr)


def _drive(
    tmp_path: Path,
    target_state: str,
    payload: dict[str, Any],
    *,
    label: str,
    results: list[tuple[int, str, str]] | None = None,
    max_attempts: int = 3,
) -> tuple[dict[str, Any], RecordingRunner]:
    """Drive ONE boundary through the real writer and hand back its record and the recorded argv."""
    runner = RecordingRunner(results)
    writer = BP.default_board_writer(
        mission_control_root=tmp_path / "mission-control", runner=runner
    )
    ledger = tmp_path / f"ledger-{label}"
    ledger.mkdir(parents=True, exist_ok=True)
    record = BP.authorize_and_write(
        "set-field-status",
        "infiquetra/infiquetra-claude-plugins",
        927,
        target_state,
        board_writer=writer,
        ledger_dir=ledger,
        payload=payload,
        max_attempts=max_attempts,
    )
    return record, runner


# ----------------------------------------------------------------- the first-move positive proof


def test_a_standalone_run_makes_a_first_move_at_every_permitted_boundary(tmp_path: Path) -> None:
    """The defect's direct disproof: each skill boundary composes a real submission argv.

    This is the most important test in the unit. It fails the moment a boundary's submission is
    deleted from the skill file, which is exactly the state the tree was in before #927.
    """
    boundaries = [
        (skill, index, target, payload)
        for skill in (PLAN_SKILL, WORK_SKILL)
        for index, (target, payload) in enumerate(submissions(skill))
    ]
    assert len(boundaries) == 5, f"five permitted boundaries, found {len(boundaries)}"

    for skill, index, target_state, payload in boundaries:
        label = f"{skill.parent.name}-{index}"
        record, runner = _drive(tmp_path, target_state, payload, label=label)
        assert record["status"] == "written", f"{label}: {record}"
        assert len(runner.calls) == 1, f"{label}: one boundary is one invocation"
        argv = runner.calls[0]
        assert argv[2:4] == ["flow", "set-field"], f"{label}: {argv}"
        assert "--correction" in argv, f"{label}: the submission must be marked a correction"
        assignments = assignments_in(argv)
        assert len(assignments) == 2, (
            f"{label}: the argv carries {len(assignments)} assignment(s), not the pair: {assignments}"
        )
        assert assignments == [tuple(pair) for pair in payload["assignments"]], (
            f"{label}: the argv does not carry the pair the skill submits: {assignments}"
        )
        assert [field for field, _ in assignments] == ["Stage", "Status"], f"{label}: {assignments}"


def test_every_submitted_pair_is_live_on_the_board() -> None:
    """R1: each boundary's pair is a member of the schema's own ``stage_statuses``."""
    schema = json.loads(
        (ROOT / "plugins" / "mission-control" / "config" / "sdlc-schema.json").read_text(
            encoding="utf-8"
        )
    )
    live = {
        (stage, status)
        for stage, options in schema["workflows"]["stage_flow"]["stage_statuses"].items()
        for status in options
    }
    for skill in (PLAN_SKILL, WORK_SKILL):
        for _target, payload in submissions(skill):
            stage, status = (pair[1] for pair in payload["assignments"])
            assert (stage, status) in live, f"{skill.name}: ({stage}, {status}) is not on the board"


# ----------------------------------------------------------------- the half-applied pair


def _half_applied_stdout() -> str:
    """Mission Control's own report for a pair whose second assignment failed.

    Shaped exactly as ``flow_set_fields_bulk`` builds it: ``identity`` is built from ``updated``
    only, so the unlanded assignment has no identity record -- stdout already distinguishes the
    landed half from the unlanded one.
    """
    return json.dumps(
        {
            "action": "set-field",
            "project": "operations",
            "repo": "infiquetra-claude-plugins",
            "assignments": [
                {"field": "Stage", "option": "Verify"},
                {"field": "Status", "option": "Awaiting verification"},
            ],
            "updated": [
                {
                    "repo": "infiquetra-claude-plugins",
                    "number": 927,
                    "field": "Stage",
                    "option": "Verify",
                }
            ],
            "failed": [
                {
                    "repo": "infiquetra-claude-plugins",
                    "number": 927,
                    "field": "Status",
                    "option": "Awaiting verification",
                    "error": "option 'Awaiting verification' is not valid for stage 'Shaping'",
                }
            ],
            "correction": True,
            "identity": [
                {
                    "field": "Stage",
                    "repo": "infiquetra-claude-plugins",
                    "number": 927,
                    "option": "Verify",
                }
            ],
        },
        indent=2,
    )


def test_a_half_applied_pair_fails_and_names_which_half_landed(tmp_path: Path) -> None:
    """One argv is one returncode, so the split is visible in stdout, never in the exit code.

    A test written as "the runner succeeds on Stage and fails on Status" is unimplementable against
    a one-invocation writer, and a worker who made it pass would have silently restored the
    two-invocation path. ``max_attempts=1`` pins the single call.
    """
    stdout = _half_applied_stdout()
    stderr = "RuntimeError: flow set-field failed for 1 of 2 field update(s); see results above"
    record, runner = _drive(
        tmp_path,
        "Awaiting verification",
        {"assignments": [["Stage", "Verify"], ["Status", "Awaiting verification"]]},
        label="half-applied",
        results=[(1, stdout, stderr)],
        max_attempts=1,
    )

    assert len(runner.calls) == 1, "one argv, one returncode -- never two runner calls"
    assert record["status"] == "failed", f"a half-applied pair must not report success: {record}"
    assert record["status"] not in ("written", "skipped")
    assert "landed: Stage=Verify" in record["error"], record["error"]
    assert "NOT landed: Status=Awaiting verification" in record["error"], record["error"]
    # No ledger key on failure, so the next tick retries rather than skipping a move that never
    # fully happened.
    assert list((tmp_path / "ledger-half-applied").iterdir()) == []


def test_the_default_retry_re_submits_the_whole_pair_and_still_names_both_halves(
    tmp_path: Path,
) -> None:
    """The half-applied path under the DEFAULT three attempts, not just the pinned single one.

    ``authorize_and_write`` retries a raising writer, so a genuinely half-applied pair is
    re-submitted whole: the landed half is rewritten to the value it already holds (a board no-op)
    and the unlanded half is retried. What must hold is that every attempt carries BOTH assignments
    — a retry that dropped the landed half would be the two-invocation path by another route — and
    that the surfaced error still names which half landed.
    """
    stdout = _half_applied_stdout()
    stderr = "RuntimeError: flow set-field failed for 1 of 2 field update(s); see results above"
    record, runner = _drive(
        tmp_path,
        "Awaiting verification",
        {"assignments": [["Stage", "Verify"], ["Status", "Awaiting verification"]]},
        label="half-applied-retried",
        results=[(1, stdout, stderr)] * 3,
    )
    assert record["status"] == "failed"
    assert record["attempts"] == 3
    assert len(runner.calls) == 3, "the default bounded retry must actually retry"
    for argv in runner.calls:
        assert assignments_in(argv) == [
            ("Stage", "Verify"),
            ("Status", "Awaiting verification"),
        ], "a retry must re-submit the whole pair, never just the half that failed"
    assert "landed: Stage=Verify" in record["error"]
    assert "NOT landed: Status=Awaiting verification" in record["error"]
    assert list((tmp_path / "ledger-half-applied-retried").iterdir()) == []


def test_a_one_element_assignments_list_is_refused(tmp_path: Path) -> None:
    """A boundary that opts into the pair API and then drops half its move submits nothing.

    The asymmetry with the legacy ``field``/``target_state`` form is deliberate: that form is what a
    genuine single-field write uses, and it stays legal so no pre-#927 caller changes. An
    ``assignments`` list carrying one entry is a lifecycle boundary that lost a half — the exact
    "wrong card with a clean record" failure, since the Status half alone is a legal write.
    """
    ledger = tmp_path / "half-submission"
    ledger.mkdir()
    runner = RecordingRunner()
    writer = BP.default_board_writer(
        mission_control_root=tmp_path / "mission-control", runner=runner
    )
    record = BP.authorize_and_write(
        "set-field-status",
        "o/r",
        927,
        "Implementing",
        board_writer=writer,
        ledger_dir=ledger,
        payload={"assignments": [["Status", "Implementing"]]},
    )
    assert record["status"] == "gated", record
    assert "carries 1 field(s)" in record["error"]
    assert "must carry both halves" in record["error"] or "exactly 2" in record["error"]
    assert runner.calls == [], "a refused submission reaches no writer at all"
    assert list(ledger.iterdir()) == [], "and leaves no ledger key behind"

    # The controller refuses it at its own seam too, not only downstream.
    controller_record = RC.reconcile_op(
        "set-field-status",
        "o/r",
        927,
        "Implementing",
        board_writer=writer,
        ledger_dir=ledger,
        payload={"assignments": [["Status", "Implementing"]]},
    )
    assert controller_record["status"] == "gated"
    assert controller_record["halt"] is True
    assert "malformed-assignments" in controller_record["halt_reason"]


def test_a_failure_with_no_parseable_report_still_surfaces_stderr(tmp_path: Path) -> None:
    """Degrade to exactly what the error said before, never to an invented claim about the board."""
    record, _runner = _drive(
        tmp_path,
        "Awaiting verification",
        {"assignments": [["Stage", "Verify"], ["Status", "Awaiting verification"]]},
        label="opaque",
        results=[(1, "not json at all", "gh: connection reset")],
        max_attempts=1,
    )
    assert record["status"] == "failed"
    assert "connection reset" in record["error"]
    assert "landed:" not in record["error"]


# ----------------------------------------------------------------- the replay identity


def test_the_pair_key_never_collides_with_a_status_only_write() -> None:
    """Without this the second of the two operations is ``skipped`` as already-applied.

    A pair whose ``Stage`` half never landed would then carry a success-shaped record for a move
    that did not happen -- no error, no drift record. That is the property closed issue #812's
    named-field identity exists to protect.
    """
    pair_field, pair_state = BP.assignment_identity(
        [("Stage", "Verify"), ("Status", "Awaiting verification")]
    )
    only_field, only_state = BP.assignment_identity([("Status", "Awaiting verification")])
    pair_key = CERT.idempotency_key("set-field-status", "o/r", 927, pair_state, field=pair_field)
    only_key = CERT.idempotency_key("set-field-status", "o/r", 927, only_state, field=only_field)
    assert pair_key != only_key
    # The single-field recipe is byte-identical to the pre-#927 one, so no existing ledger key is
    # orphaned by the widening.
    assert only_key == "set-field-status:o/r#927:Status:Awaiting verification"


def test_both_key_minting_sites_agree(tmp_path: Path) -> None:
    """``authorize_and_write`` and the reconcile controller mint one identity for one pair.

    Proven by making the controller MEET the key the writer left: it re-derives the key itself on
    the ledger-present branch, so a disagreement shows up as a second write (``written``) instead of
    the converged ``skipped``.
    """
    ledger = tmp_path / "shared-ledger"
    ledger.mkdir()
    payload = {"assignments": [["Stage", "Verify"], ["Status", "Awaiting verification"]]}
    runner = RecordingRunner()
    writer = BP.default_board_writer(
        mission_control_root=tmp_path / "mission-control", runner=runner
    )
    written = BP.authorize_and_write(
        "set-field-status",
        "o/r",
        927,
        "Awaiting verification",
        board_writer=writer,
        ledger_dir=ledger,
        payload=payload,
    )
    assert written["status"] == "written"

    met = RC.reconcile_op(
        "set-field-status",
        "o/r",
        927,
        "Awaiting verification",
        board_writer=writer,
        ledger_dir=ledger,
        payload=payload,
    )
    assert met["status"] == "skipped", f"the controller minted a different identity: {met}"
    assert met["key"] == written["key"]
    assert met["key"] == "set-field-status:o/r#927:Stage+Status:Verify+Awaiting verification"
    assert len(runner.calls) == 1, "the second tick must not re-drive a landed write"


def test_a_single_assignment_keeps_its_pre_pair_identity(tmp_path: Path) -> None:
    """Every pre-#927 caller is byte-unchanged: same argv, same key, same payload."""
    ledger = tmp_path / "single"
    ledger.mkdir()
    runner = RecordingRunner()
    writer = BP.default_board_writer(
        mission_control_root=tmp_path / "mission-control", runner=runner
    )
    record = BP.authorize_and_write(
        "set-field-status",
        "o/r",
        927,
        "Implementing",
        board_writer=writer,
        ledger_dir=ledger,
    )
    assert record["key"] == "set-field-status:o/r#927:Status:Implementing"
    assert assignments_in(runner.calls[0]) == [("Status", "Implementing")]


def test_an_unauthorized_field_in_the_pair_gates_the_whole_submission(tmp_path: Path) -> None:
    """A pair whose second half names an unauthorized field must gate whole, never half-write."""
    ledger = tmp_path / "gated"
    ledger.mkdir()
    runner = RecordingRunner()
    writer = BP.default_board_writer(
        mission_control_root=tmp_path / "mission-control", runner=runner
    )
    record = BP.authorize_and_write(
        "set-field-status",
        "o/r",
        927,
        "whatever",
        board_writer=writer,
        ledger_dir=ledger,
        payload={"assignments": [["Stage", "Verify"], ["Initiative", "platform-quality"]]},
    )
    assert record["status"] == "gated"
    assert record["field"] == "Initiative"
    assert runner.calls == [], "a gated submission reaches no writer at all"


# ----------------------------------------------------------------- what must not come back


def test_no_pre_merge_path_submits_verify() -> None:
    """R5/W-D2: the Verify submission lives after merge, and the rule that says so is intact."""
    text = WORK_SKILL.read_text(encoding="utf-8")
    heading = "### 4.4 Post-merge board actions"
    assert heading in text
    pre_merge = text[: text.index(heading)]
    assert "Awaiting verification" not in pre_merge, (
        "a Verify submission appears before the post-merge boundary"
    )
    assert '["Stage", "Verify"]' not in pre_merge
    assert (
        "PR-ready, green checks, code review, and merge readiness never move the\ncard to Verify"
        in text
    ), "W-D2's pre-merge rule must survive verbatim"
    assert "a non-production deployment has **succeeded**, in that order" in text


def test_the_auto_correct_allowlist_is_still_empty() -> None:
    """R7: no second routine writer, and no silent overwrite of an outside edit."""
    assert frozenset() == RC.AUTO_CORRECT_OP_KINDS


def test_no_new_op_kind_was_invented_for_the_pair() -> None:
    """The existing op-kind's payload carries the shape; a ``set-field-pair`` would be dead API
    surface needing its own certificate registry entry, reversibility tier and inverse descriptor —
    the same reasoning that already rejected ``set-field-stage``."""
    names = {kind.value for kind in CERT.OpKind}
    assert "set-field-status" in names
    assert not [
        name for name in names if name.startswith("set-field-") and name != "set-field-status"
    ]


# ----------------------------------------------------------------- cycle-2 review repairs


def _seed_ledger(tmp_path: Path, payload: dict[str, Any], target_state: str) -> Path:
    """Drive one successful submission so its ledger key is present for the next tick."""
    ledger = tmp_path / "drift-ledger"
    ledger.mkdir(exist_ok=True)
    runner = RecordingRunner()
    writer = BP.default_board_writer(
        mission_control_root=tmp_path / "mission-control", runner=runner
    )
    record = BP.authorize_and_write(
        "set-field-status",
        "o/r",
        927,
        target_state,
        board_writer=writer,
        ledger_dir=ledger,
        payload=payload,
    )
    assert record["status"] == "written"
    return ledger


def test_a_pair_keeps_its_live_drift_check(tmp_path: Path) -> None:
    """The level-triggered convergence loop must stay ON for a pair submission.

    The guard that skips a field this controller cannot read back compared the submission's LEDGER
    IDENTITY against the one readable field. A pair mints the composite `Stage+Status`, which can
    never equal `Status`, so from the second tick every pair returned `skipped` without calling
    `live_reader` at all -- the single property this module exists to provide, off for every
    lifecycle write Plan, Work and Orchestrate make. The question is whether the submission
    CONTAINS the readable field, not whether its identity equals it.
    """
    payload = {"assignments": [["Stage", "Active"], ["Status", "Implementing"]]}
    ledger = _seed_ledger(tmp_path, payload, "Implementing")
    reads: list[tuple[str, str, int]] = []

    def drifted(op_kind: str, repo: str, number: int) -> str:
        reads.append((op_kind, repo, number))
        return "Repairing"

    record = RC.reconcile_op(
        "set-field-status",
        "o/r",
        927,
        "Implementing",
        board_writer=lambda **_kwargs: None,
        ledger_dir=ledger,
        live_reader=drifted,
        payload=payload,
    )
    assert reads, "the drift check must actually read the live board for a pair"
    assert record["status"] == "halt", record
    assert record["halt_reason"] == "status-drift:Repairing"
    assert record["board_value"] == "Repairing"


def test_a_converged_pair_is_a_skip_not_a_halt(tmp_path: Path) -> None:
    """And the same read, when the board agrees, converges rather than manufacturing drift."""
    payload = {"assignments": [["Stage", "Active"], ["Status", "Implementing"]]}
    ledger = _seed_ledger(tmp_path, payload, "Implementing")
    record = RC.reconcile_op(
        "set-field-status",
        "o/r",
        927,
        "Implementing",
        board_writer=lambda **_kwargs: None,
        ledger_dir=ledger,
        live_reader=lambda *_a: "Implementing",
        payload=payload,
    )
    assert record["status"] == "skipped"
    assert "note" not in record, "a converged read is not an unreadable-field skip"


def test_a_stage_only_submission_still_refuses_to_judge(tmp_path: Path) -> None:
    """The guard's real purpose survives: no readable half means no verdict, as before."""
    payload = {"assignments": [["Stage", "Active"], ["Stage", "Verify"]]}
    ledger = tmp_path / "stage-only"
    ledger.mkdir()
    record = RC.reconcile_op(
        "set-field-status",
        "o/r",
        927,
        "Active",
        board_writer=lambda **_kwargs: None,
        ledger_dir=ledger,
        live_reader=lambda *_a: "Implementing",
        payload=payload,
    )
    # Refused before it can even mint a key: two assignments to one field is not a pair.
    assert record["status"] == "gated"
    assert "more than once" in record["halt_reason"]


def test_a_submission_without_the_readable_field_refuses_to_judge_drift() -> None:
    """The drift guard's real purpose: no readable half means no verdict, exactly as before.

    Driven through `_expected_live` rather than a whole submission, because `normalize_assignments`
    now refuses a `Stage`-only list outright and the two guards are independent -- the drift check
    must still decline to judge a submission that reaches it without a `Status` half, whatever the
    normalizer would have said about it.
    """
    assert RC._expected_live("set-field-status", "Active", [("Stage", "Active")]) == ""
    assert (
        RC._expected_live("set-field-status", "Active", [("Stage", "Active"), ("Status", "Impl")])
        == "Impl"
    )
    # A non-lifecycle op is unaffected either way.
    assert RC._expected_live("issue-progress-comment", "d", None) == ""


def test_two_assignments_to_one_field_are_not_a_pair(tmp_path: Path) -> None:
    """Counting ELEMENTS accepts a half-move wearing a pair's shape."""
    ledger = tmp_path / "same-field"
    ledger.mkdir()
    record = BP.authorize_and_write(
        "set-field-status",
        "o/r",
        927,
        "Implementing",
        board_writer=lambda **_kwargs: None,
        ledger_dir=ledger,
        payload={"assignments": [["Status", "Implementing"], ["Status", "Integrating"]]},
    )
    assert record["status"] == "gated"
    assert "Status more than once" in record["error"]


def test_the_identity_separator_is_refused_inside_a_value(tmp_path: Path) -> None:
    """Unreachable against today's board, and refused rather than left to become reachable."""
    ledger = tmp_path / "separator"
    ledger.mkdir()
    record = BP.authorize_and_write(
        "set-field-status",
        "o/r",
        927,
        "x",
        board_writer=lambda **_kwargs: None,
        ledger_dir=ledger,
        payload={"assignments": [["Stage", "Ac+tive"], ["Status", "Implementing"]]},
    )
    assert record["status"] == "gated"
    assert "separator" in record["error"]


def test_the_replay_identity_does_not_depend_on_assignment_order() -> None:
    """Submission order is a property of the write, not of the logical move."""
    forward = BP.assignment_identity([("Stage", "Active"), ("Status", "Implementing")])
    reverse = BP.assignment_identity([("Status", "Implementing"), ("Stage", "Active")])
    assert forward == reverse == ("Stage+Status", "Active+Implementing")


def test_a_failure_with_no_report_names_what_was_submitted(tmp_path: Path) -> None:
    """An absent report is NOT proof that nothing landed.

    `_out` runs before the `failed` raise, so no report means the run died before it -- a
    `LifecycleMutationHaltError` out of the SECOND assignment is exactly that shape, and it leaves
    the FIRST one written. Reporting a bare stderr there described a total failure for a board that
    may be half-moved.
    """
    record, _runner = _drive(
        tmp_path,
        "Awaiting verification",
        {"assignments": [["Stage", "Verify"], ["Status", "Awaiting verification"]]},
        label="halted",
        results=[(1, "", "LifecycleMutationHaltError: board 'Asgard' disagrees")],
        max_attempts=1,
    )
    assert record["status"] == "failed"
    assert "UNKNOWN" in record["error"]
    assert "Stage=Verify" in record["error"]
    assert "Status=Awaiting verification" in record["error"]
    assert "check every field" in record["error"]


def test_the_call_budget_scales_with_the_assignment_count(tmp_path: Path) -> None:
    """A pair is two cross-board passes inside mission-control, not one."""
    timeouts: list[int] = []

    def _recording(cmd: Any, **kwargs: Any) -> subprocess.CompletedProcess[Any]:
        timeouts.append(int(kwargs.get("timeout", 0)))
        return subprocess.CompletedProcess(cmd, 0, stdout="", stderr="")

    writer = BP.default_board_writer(
        mission_control_root=tmp_path / "mission-control", runner=_recording
    )
    writer(
        op_kind="set-field-status",
        repo="o/r",
        number=927,
        payload={
            "assignments": [["Stage", "Verify"], ["Status", "Awaiting verification"]],
            "target_state": "Awaiting verification",
        },
    )
    writer(
        op_kind="set-field-status",
        repo="o/r",
        number=927,
        payload={"field": "Status", "target_state": "Implementing"},
    )
    assert timeouts[0] == 2 * timeouts[1], (
        f"the pair must not silently halve its budget: {timeouts}"
    )


# ------------------------------------------------- the pair's own bounds, key and reporting


def test_the_pair_ledger_key_stays_readable_rather_than_hashing() -> None:
    """`+` was not in the safe-character set, so EVERY pair key took the SHA-1 fallback.

    The ledger is meant to be inspectable by filename -- that is what "did this move already
    land?" is answered with by hand -- and the writes it hid behind a digest were exactly the
    lifecycle pairs. The fallback itself must survive: a genuinely hostile key still hashes.
    """
    pair = BP._safe_ledger_name("set-field-status:o/r#927:Stage+Status:Active+Implementing")
    assert pair == "set-field-status_o_r_927_Stage+Status_Active+Implementing.json"
    assert not re.fullmatch(r"[0-9a-f]{40}\.json", pair)
    # Control: the SHA-1 fallback is still reached for a key the filesystem cannot take.
    assert re.fullmatch(r"[0-9a-f]{40}\.json", BP._safe_ledger_name("a key with spaces"))
    assert re.fullmatch(r"[0-9a-f]{40}\.json", BP._safe_ledger_name("x" * 400))


def test_an_empty_assignments_list_is_not_a_single_field_write(tmp_path: Path) -> None:
    """ABSENT is the single-field fallback; EMPTY is a pair payload with nothing in it."""
    with pytest.raises(ValueError, match="present but empty"):
        BP.normalize_assignments({"assignments": []}, "Implementing")
    # Control: absent still falls back, byte-for-byte as before the pair existed.
    assert BP.normalize_assignments({}, "Implementing") == [("Status", "Implementing")]
    assert BP.normalize_assignments(None, "Implementing") == [("Status", "Implementing")]
    assert BP.normalize_assignments({"field": "Stage"}, "Active") == [("Stage", "Active")]


def test_the_pair_guard_bounds_the_submission_from_both_ends(tmp_path: Path) -> None:
    """The floor caught the half-move and left the other end open.

    A three-field submission is not a lifecycle boundary, and authorizing it here would put an
    unreviewed field on the same certificate as the pair."""
    with pytest.raises(ValueError, match="carries 3 field"):
        BP.normalize_assignments(
            {
                "assignments": [
                    ["Stage", "Active"],
                    ["Status", "Implementing"],
                    ["Priority", "P0"],
                ]
            },
            "Implementing",
        )
    with pytest.raises(ValueError, match="more than once"):
        BP.normalize_assignments(
            {"assignments": [["Stage", "Active"], ["Stage", "Verify"], ["Status", "Impl"]]},
            "Impl",
        )
    # Control: the pair itself passes, in either order.
    assert len(
        BP.normalize_assignments(
            {"assignments": [["Status", "Implementing"], ["Stage", "Active"]]}, "Implementing"
        )
    ) == len(BP.EXPECTED_ASSIGNMENT_FIELDS)


def test_a_single_field_write_is_not_told_it_has_halves() -> None:
    """`outcome_reconcile.py` still drives single-field `set-field-status`, so this is live.

    Telling that caller that "which halves landed is UNKNOWN" and to "check every field" describes
    a submission it did not make -- it invents a half-written board out of a write that could only
    ever land or not."""
    single = BP._set_field_landed_detail("no json here", [("Status", "Implementing")])
    assert "whether the write landed is UNKNOWN" in single
    assert "halves" not in single
    assert "check the field on the board" in single
    # Control: a genuine pair still says halves, because it has them.
    pair = BP._set_field_landed_detail(
        "no json here", [("Stage", "Active"), ("Status", "Implementing")]
    )
    assert "which halves landed is UNKNOWN" in pair
    assert "check every field" in pair


def test_the_stdout_report_parser_survives_a_progress_prefixed_stream() -> None:
    """The parser is what turns a half-applied pair into "which half landed", and nothing drove it.

    `_out` pretty-prints, so the report's brace starts a line; any progress line printed before it
    defeats a plain `json.loads`, which is the case this scan exists for."""
    report = json.dumps(
        {"updated": [{"field": "Stage"}], "failed": [{"field": "Status"}]}, indent=2
    )
    assignments = [("Stage", "Active"), ("Status", "Implementing")]
    for stream in (report, "resolving project...\n" + report, "noise\n" + report + "\ntrailing"):
        detail = BP._set_field_landed_detail(stream, assignments)
        assert "Stage" in detail.split("NOT landed")[0], stream[:20]
        assert "Status" in detail.split("NOT landed")[1], stream[:20]
    # The LAST report wins: the result is printed after any interim one.
    first = json.dumps({"updated": [{"field": "Stage"}], "failed": []}, indent=2)
    both = BP._set_field_landed_detail(first + "\n" + report, assignments)
    assert "NOT landed" in both and "Status" in both.split("NOT landed")[1]
    # Control: unparseable stdout is still the UNKNOWN branch, not a fabricated verdict.
    assert "UNKNOWN" in BP._set_field_landed_detail("{not json", assignments)


def test_every_field_of_a_pair_is_authorized_at_BOTH_layers(tmp_path: Path) -> None:
    """Two independent certificate checks guard a pair, and only one of them had a test.

    `authorize_and_write` checks the submission's identity field before it mints a key, and
    `default_board_writer` checks EVERY assignment again before it builds the argv. The second is
    the one a pair actually needs -- the first sees the composite identity, so an unauthorized
    SECOND field reaches the writer with nothing having looked at it yet. Mutating that loop to
    read `assignments[0]` alone left the suite green.
    """
    runner = RecordingRunner()
    writer = BP.default_board_writer(
        mission_control_root=tmp_path / "mission-control", runner=runner
    )

    # Layer 2, the writer's own per-assignment loop, driven directly. An unauthorized field in
    # EITHER position must be refused, which is what a first-element-only check gets wrong.
    for assignments in (
        [["Priority", "P0"], ["Status", "Implementing"]],
        [["Stage", "Active"], ["Priority", "P0"]],
    ):
        with pytest.raises(ValueError, match="rejects field 'Priority'"):
            writer(
                op_kind="set-field-status",
                repo="infiquetra/orch",
                number=927,
                payload={"assignments": assignments, "target_state": "Implementing"},
            )
    assert runner.calls == [], "an unauthorized field must reach no argv at all"

    # Control: the authorized pair passes the same loop and does build an argv.
    writer(
        op_kind="set-field-status",
        repo="infiquetra/orch",
        number=927,
        payload={
            "assignments": [["Stage", "Active"], ["Status", "Implementing"]],
            "target_state": "Implementing",
        },
    )
    assert len(runner.calls) == 1
    argv = runner.calls[0]
    assert argv.count("--field") == 2

    # Layer 1, at the key-minting site, reached through the whole path.
    ledger = tmp_path / "auth-layer-1"
    ledger.mkdir()
    record = BP.authorize_and_write(
        "set-field-status",
        "o/r",
        927,
        "P0",
        board_writer=lambda **_kwargs: None,
        ledger_dir=ledger,
        payload={"field": "Priority"},
    )
    assert record["status"] == "gated", record
    assert list(ledger.iterdir()) == [], "a gated submission leaves no replay key"
