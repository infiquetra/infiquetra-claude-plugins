"""Board submissions cross the real authorization, transport and durable-ledger boundaries."""

from __future__ import annotations

import hashlib
import importlib.util
import json
import subprocess
import sys
from pathlib import Path
from types import ModuleType, SimpleNamespace
from typing import Any

import pytest

ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "plugins" / "saga" / "scripts"
PAIR = [["Stage", "Active"], ["Status", "Implementing"]]


@pytest.fixture
def board(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> ModuleType:
    monkeypatch.syspath_prepend(str(SCRIPTS))
    monkeypatch.setenv("HOME", str(tmp_path / "home"))
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path / "config"))

    def deny_process(*args: Any, **kwargs: Any) -> None:
        raise AssertionError("uncontrolled external process in board boundary test")

    monkeypatch.setattr(subprocess, "run", deny_process)
    spec = importlib.util.spec_from_file_location(
        "_board_boundary_contract", SCRIPTS / "board_progression.py"
    )
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    module.__dict__["_production_resolver"] = module.resolve_mission_control_root
    monkeypatch.setattr(
        module, "resolve_mission_control_root", lambda: (tmp_path / "mission-control", 2)
    )
    return module


def transport(
    reply: str = "", code: int = 0, stderr: str = ""
) -> tuple[list[tuple[list[str], dict]], Any]:
    calls: list[tuple[list[str], dict]] = []

    def run(argv: list[str], **kwargs: Any) -> subprocess.CompletedProcess[str]:
        calls.append((argv, kwargs))
        return subprocess.CompletedProcess(argv, code, reply, stderr)

    return calls, run


@pytest.mark.parametrize(
    ("op", "payload", "tail"),
    [
        (
            "set-field-status",
            {"assignments": PAIR},
            [
                "flow",
                "set-field",
                "--project",
                "asgard",
                "--repo",
                "repo",
                "--number",
                "45",
                "--field",
                "Stage",
                "--option",
                "Active",
                "--field",
                "Status",
                "--option",
                "Implementing",
                "--correction",
            ],
        ),
        (
            "set-field-status",
            {"field": "Status", "target_state": "Ready to close"},
            [
                "flow",
                "set-field",
                "--project",
                "asgard",
                "--repo",
                "repo",
                "--number",
                "45",
                "--field",
                "Status",
                "--option",
                "Ready to close",
                "--correction",
            ],
        ),
        ("sub-issue-close", {}, ["issue", "close", "--repo", "repo", "--number", "45"]),
        ("sub-issue-reopen", {}, ["issue", "reopen", "--repo", "repo", "--number", "45"]),
        (
            "issue-progress-comment",
            {"body": "progress recorded"},
            ["issue", "comment", "--repo", "repo", "--number", "45", "--body", "progress recorded"],
        ),
        (
            "issue-label-add",
            {"label": "verified"},
            ["issue", "label-add", "--repo", "repo", "--number", "45", "--label", "verified"],
        ),
        (
            "issue-label-remove",
            {"label": "stale"},
            ["issue", "label-remove", "--repo", "repo", "--number", "45", "--label", "stale"],
        ),
    ],
)
def test_real_writer_preserves_outgoing_argv_and_timeout(
    board: ModuleType, tmp_path: Path, op: str, payload: dict, tail: list[str]
) -> None:
    calls, run = transport()
    plugin = tmp_path / "installed-plugin"
    writer = board.default_board_writer(mission_control_root=plugin, project="asgard", runner=run)
    writer(op_kind=op, repo="fixture/repo", number=45, payload=payload)
    assert len(calls) == 1
    argv, options = calls[0]
    assert argv == ["python3", str(plugin / "scripts/sdlc_manager.py"), *tail]
    assert options == {
        "capture_output": True,
        "text": True,
        "timeout": 120 if payload.get("assignments") else 60,
    }


@pytest.mark.parametrize(
    ("op", "payload", "message"),
    [
        ("unknown-write", {}, "no mission-control verb"),
        (
            "set-field-status",
            {"field": "Priority", "target_state": "High"},
            "rejects field 'Priority'",
        ),
    ],
)
def test_writer_refuses_unknown_operations_and_fields_before_transport(
    board: ModuleType, tmp_path: Path, op: str, payload: dict, message: str
) -> None:
    calls, run = transport()
    writer = board.default_board_writer(mission_control_root=tmp_path, runner=run)
    with pytest.raises(ValueError, match=message):
        writer(op_kind=op, repo="fixture/repo", number=45, payload=payload)
    assert calls == []


@pytest.mark.parametrize(
    ("reply", "code", "message"),
    [
        ("", 1, "preflight failed"),
        ("not-json", 0, "invalid JSON"),
        ('{"body": "wrong shape"}', 0, "non-list JSON"),
    ],
)
def test_comment_preflight_failure_never_posts(
    board: ModuleType, tmp_path: Path, reply: str, code: int, message: str
) -> None:
    calls, run = transport(reply, code, "denied")
    writer = board.default_board_writer(mission_control_root=tmp_path, runner=run)
    body = "progress\n<!-- saga-board-sync-idempotency:" + "a" * 64 + " -->"
    with pytest.raises(RuntimeError, match=message):
        writer(
            op_kind="issue-progress-comment", repo="fixture/repo", number=45, payload={"body": body}
        )
    assert calls == [
        (
            [
                "gh",
                "api",
                "--method",
                "GET",
                "repos/infiquetra/repo/issues/45/comments",
                "--paginate",
                "-F",
                "per_page=100",
            ],
            {"capture_output": True, "text": True, "timeout": 60},
        )
    ]


@pytest.mark.parametrize("already_posted", [False, True])
def test_remote_comment_marker_suppresses_only_the_matching_retry(
    board: ModuleType, tmp_path: Path, already_posted: bool
) -> None:
    marker = "<!-- saga-board-sync-idempotency:" + "b" * 64 + " -->"
    body = "progress\n" + marker
    calls, run = transport(
        json.dumps([None, {"body": marker if already_posted else "other progress"}])
    )
    writer = board.default_board_writer(mission_control_root=tmp_path, runner=run)
    writer(op_kind="issue-progress-comment", repo="fixture/repo", number=45, payload={"body": body})
    assert len(calls) == (1 if already_posted else 2)
    if not already_posted:
        assert calls[1][0][-2:] == ["--body", body]


@pytest.mark.parametrize(
    ("stdout", "fragments"),
    [
        (
            'progress\n{bad json}\n{"updated": [{"field":"Stage","option":"Active"}], "failed":[{"field":"Status","option":"Implementing"}]}',
            ["landed: Stage=Active", "NOT landed: Status=Implementing"],
        ),
        (
            '{"updated": [], "failed": []}\n{"updated":[{"field":"Status","option":"Implementing"}],"failed":[]}',
            ["landed: Status=Implementing", "NOT landed: none"],
        ),
        (
            '{"updated": null, "failed": [null, {}, {"field":"Status","option":"Implementing"}]}',
            ["landed: none", "NOT landed: Status=Implementing"],
        ),
        (
            "no report was emitted",
            [
                "which halves landed is UNKNOWN",
                "Stage=Active",
                "Status=Implementing",
                "check every field",
            ],
        ),
    ],
)
def test_partial_board_failures_retain_landed_evidence_and_stderr(
    board: ModuleType, tmp_path: Path, stdout: str, fragments: list[str]
) -> None:
    calls, run = transport(stdout, 1, "transport refusal")
    writer = board.default_board_writer(mission_control_root=tmp_path, runner=run)
    with pytest.raises(RuntimeError) as error:
        writer(
            op_kind="set-field-status",
            repo="fixture/repo",
            number=45,
            payload={"assignments": PAIR},
        )
    text = str(error.value)
    assert "transport refusal" in text and "repo#45" in text
    for fragment in fragments:
        assert fragment in text
    assert calls[0][1]["timeout"] == 120


def test_single_field_failure_does_not_invent_a_half_written_pair(
    board: ModuleType, tmp_path: Path
) -> None:
    _, run = transport("no report", 1, "refused")
    writer = board.default_board_writer(mission_control_root=tmp_path, runner=run)
    with pytest.raises(RuntimeError) as error:
        writer(
            op_kind="set-field-status",
            repo="fixture/repo",
            number=45,
            payload={"target_state": "Active"},
        )
    assert "whether the write landed is UNKNOWN" in str(error.value)
    assert "which halves" not in str(error.value)


@pytest.mark.parametrize(
    ("assignments", "reason"),
    [
        ([], "present but empty"),
        ("Stage=Active", "must be a list"),
        ([["Stage"]], "not a .* pair"),
        ([["Stage", "A", "extra"]], "not a .* pair"),
        (["Stage"], "not a .* pair"),
        ([["Stage", "A+B"], ["Status", "Implementing"]], "separator"),
        ([["Stage+Other", "Active"], ["Status", "Implementing"]], "separator"),
        ([["Status", "Active"], ["Status", "Done"]], "more than once"),
        ([["Status", "Active"]], "exactly 2"),
        ([["Stage", "Active"], ["Status", "Implementing"], ["Priority", "High"]], "exactly 2"),
    ],
)
def test_malformed_pair_is_gated_before_any_write(
    board: ModuleType, tmp_path: Path, assignments: Any, reason: str
) -> None:
    calls, run = transport()
    record = board.authorize_and_write(
        "set-field-status",
        "fixture/repo",
        45,
        "Implementing",
        board_writer=run,
        ledger_dir=tmp_path / "ledger",
        payload={"assignments": assignments},
    )
    assert record["status"] == "gated" and record["verdict"] == "GATE"
    import re

    assert re.search(reason, record["error"])
    assert calls == [] and not (tmp_path / "ledger").exists()


@pytest.mark.parametrize(
    "assignments",
    [
        [["Stage", "Active"], ["Priority", "High"]],
        [["Stage", "Active"], ["Status", "Done"]],
    ],
)
def test_unauthorized_name_or_value_never_creates_success_ledger(
    board: ModuleType, tmp_path: Path, assignments: list
) -> None:
    calls, run = transport()
    result = board.authorize_and_write(
        "set-field-status",
        "fixture/repo",
        45,
        "Done",
        board_writer=run,
        ledger_dir=tmp_path / "ledger",
        payload={"assignments": assignments},
    )
    assert result["status"] == "gated" and calls == []
    assert not (tmp_path / "ledger").exists()
    if assignments[1][0] == "Priority":
        assert result["field"] == "Priority"
    else:
        assert "not one the lifecycle repository allows" in result["error"]


def test_pair_reordering_is_one_durable_move_with_full_attribution(
    board: ModuleType, tmp_path: Path
) -> None:
    writes: list[dict] = []

    def writer(**kwargs: Any) -> None:
        writes.append(kwargs)

    first = board.authorize_and_write(
        "set-field-status",
        "fixture/repo",
        45,
        "Implementing",
        board_writer=writer,
        ledger_dir=tmp_path,
        payload={"assignments": PAIR},
        provenance={"resolution_root": "private-install", "resolution_rung": 2},
        now=lambda: 123,
    )
    repeated = board.authorize_and_write(
        "set-field-status",
        "fixture/repo",
        45,
        "Implementing",
        board_writer=writer,
        ledger_dir=tmp_path,
        payload={"assignments": list(reversed(PAIR))},
    )
    assert first["status"] == "written" and repeated["status"] == "skipped"
    assert repeated["key"] == first["key"] and len(writes) == 1
    assert writes[0]["payload"]["assignments"] == PAIR
    ledger = json.loads(next(tmp_path.glob("*.json")).read_text())
    assert ledger == {
        "key": first["key"],
        "op_kind": "set-field-status",
        "repo": "fixture/repo",
        "number": 45,
        "target_state": "Implementing",
        "field": "Stage+Status",
        "assignments": PAIR,
        "ts": 123,
        "resolution_root": "private-install",
        "resolution_rung": 2,
    }


@pytest.mark.parametrize("recover", [False, True])
def test_bounded_retry_records_only_a_committed_write(
    board: ModuleType, tmp_path: Path, recover: bool
) -> None:
    attempts: list[dict] = []

    def flaky(**kwargs: Any) -> None:
        attempts.append(kwargs)
        if not recover or len(attempts) < 2:
            raise OSError("controlled transport failure")

    record = board.authorize_and_write(
        "issue-label-add",
        "fixture/repo",
        45,
        "",
        board_writer=flaky,
        ledger_dir=tmp_path,
        payload={"label": "verified"},
        max_attempts=2,
    )
    assert len(attempts) == 2
    assert record["status"] == ("written" if recover else "failed")
    assert record["attempts"] == 2
    assert bool(list(tmp_path.glob("*.json"))) is recover
    if not recover:
        assert record["error"] == "controlled transport failure"


def test_ledger_failure_after_write_is_visible_and_may_reapply(
    board: ModuleType, tmp_path: Path
) -> None:
    writes: list[dict] = []

    def writer(**kwargs: Any) -> None:
        writes.append(kwargs)

    def disk_full(path: Path, content: str) -> bool:
        raise OSError("disk full")

    record = board.authorize_and_write(
        "issue-label-add",
        "fixture/repo",
        45,
        "",
        board_writer=writer,
        ledger_dir=tmp_path,
        write_once=disk_full,
    )
    assert len(writes) == 1 and record["status"] == "error" and record["may_reapply"] is True
    assert "disk full" in record["error"] and list(tmp_path.iterdir()) == []


@pytest.mark.parametrize("phase", ["authorized", "merged"])
def test_merge_attribution_deduplicates_one_era_but_not_a_new_token(
    board: ModuleType, tmp_path: Path, phase: str
) -> None:
    payload = {
        "phase": phase,
        "outcome_id": "outcome-1",
        "subplot_id": "unit-1",
        "pr": "repo#45",
        "authorizing_envelope_id": "envelope-1",
        "token_id": "era-1",
        "now": lambda: 7,
    }
    first = board.record_envelope_authorized_merge(tmp_path, **payload)
    again = board.record_envelope_authorized_merge(tmp_path, **payload)
    other = board.record_envelope_authorized_merge(tmp_path, **{**payload, "token_id": "era-2"})
    assert [first["status"], again["status"], other["status"]] == ["written", "skipped", "written"]
    assert first["key"] != other["key"]
    records = [json.loads(p.read_text()) for p in tmp_path.glob("*.json")]
    assert {r["token_id"] for r in records} == {"era-1", "era-2"}
    assert all(
        r["authorizing_envelope_id"] == "envelope-1" and r["phase"] == phase and r["ts"] == 7
        for r in records
    )


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("phase", "unknown"),
        ("outcome_id", ""),
        ("subplot_id", None),
        ("pr", 45),
        ("authorizing_envelope_id", ""),
        ("token_id", ""),
    ],
)
def test_merge_attribution_cannot_be_unidentified(
    board: ModuleType, tmp_path: Path, field: str, value: Any
) -> None:
    kwargs = {
        "phase": "merged",
        "outcome_id": "o",
        "subplot_id": "u",
        "pr": "repo#45",
        "authorizing_envelope_id": "e",
        "token_id": "t",
    }
    kwargs[field] = value
    with pytest.raises(ValueError):
        board.record_envelope_authorized_merge(tmp_path, **kwargs)
    assert list(tmp_path.iterdir()) == []


def test_merge_record_failure_is_returned_after_committed_side_effect(
    board: ModuleType, tmp_path: Path
) -> None:
    def broken(path: Path, content: str) -> bool:
        raise OSError("readonly attribution store")

    record = board.record_envelope_authorized_merge(
        tmp_path,
        phase="merged",
        outcome_id="o",
        subplot_id="u",
        pr="repo#45",
        authorizing_envelope_id="e",
        token_id="t",
        write_once=broken,
    )
    assert record["status"] == "error" and "readonly attribution store" in record["error"]
    raced = board.record_envelope_authorized_merge(
        tmp_path,
        phase="authorized",
        outcome_id="o",
        subplot_id="u",
        pr="repo#45",
        authorizing_envelope_id="e",
        token_id="t",
        write_once=lambda p, c: False,
    )
    assert raced["status"] == "skipped" and list(tmp_path.iterdir()) == []


def test_atomic_ledger_create_does_not_clobber_or_leave_scratch_files(
    board: ModuleType, tmp_path: Path
) -> None:
    path = tmp_path / "records/key.json"
    assert board._write_once(path, "first") is True
    assert board._write_once(path, "second") is False
    assert path.read_text() == "first" and list(path.parent.iterdir()) == [path]


def test_schema_resolution_falls_back_past_bad_data_and_keeps_valid_pairs(
    board: ModuleType, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    paths = [
        tmp_path / name for name in ("missing.json", "broken.json", "empty.json", "schema.json")
    ]
    paths[1].write_text("{")
    paths[2].write_text('{"lifecycle_field_mutation":{"allowed_submissions":[null,{}]}}')
    paths[3].write_text(
        json.dumps(
            {
                "lifecycle_field_mutation": {
                    "allowed_submissions": [None, {}, {"stage": "Planning", "status": "Designing"}]
                }
            }
        )
    )
    monkeypatch.setattr(board, "_vendored_schema_paths", lambda: paths)
    assert board.allowed_submissions() == (("Planning", "Designing"),)
    assert (
        board.allowed_submission_refusal([("Stage", "Planning"), ("Status", "Designing")]) is None
    )
    assert "Planning / Designing" in board.allowed_submission_refusal(
        [("Stage", "Active"), ("Status", "Done")]
    )
    paths[3].unlink()
    assert board.allowed_submissions() == board.ALLOWED_SUBMISSIONS


def test_resolution_error_names_repair_and_actual_ladder_contract(
    board: ModuleType, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    import fleet_commons_shim

    # Keep process/HOME guards active while substituting only the install-ladder boundary.
    actual = board
    monkeypatch.setattr(board, "resolve_mission_control_root", board._production_resolver)
    calls = []

    def resolve(name: str, **kwargs: Any) -> tuple[Path, int]:
        calls.append((name, kwargs))
        return tmp_path, 3

    monkeypatch.setattr(
        fleet_commons_shim, "load", lambda name: SimpleNamespace(resolve_plugin_root=resolve)
    )
    assert actual.resolve_mission_control_root() == (tmp_path, 3)
    assert calls == [
        (
            "mission-control",
            {
                "markers": ("scripts/sdlc_manager.py", "config/sdlc-schema.json"),
                "env_var": "MISSION_CONTROL_ROOT",
            },
        )
    ]

    def unavailable(name: str) -> Any:
        raise RuntimeError("no compatible fleet core")

    monkeypatch.setattr(fleet_commons_shim, "load", unavailable)
    with pytest.raises(RuntimeError, match="board-sync:.*Fix: update the fleet-core"):
        actual.resolve_mission_control_root()


@pytest.mark.parametrize(
    ("contents", "error"),
    [
        ("[]", "does not hold a JSON object"),
        ('{"schema":"future.v99","repo":"fixture/repo","issue":45}', "declares schema"),
        ("{", "Expecting"),
    ],
)
def test_boundary_cli_refuses_invalid_record_without_transport(
    board: ModuleType, tmp_path: Path, capsys: pytest.CaptureFixture[str], contents: str, error: str
) -> None:
    record = tmp_path / "run.json"
    record.write_text(contents)
    assert board.main(["--boundary", "build-start", "--record", str(record)]) == 2
    assert error in json.loads(capsys.readouterr().err)["error"]


def test_boundary_cli_dry_run_and_no_submission_do_not_resolve_transport(
    board: ModuleType,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    record = tmp_path / "run.json"
    record.write_text(
        json.dumps(
            {
                "schema": "run_record.v1",
                "repo": "fixture/repo",
                "issue": 45,
                "retro": {"trigger_fired": True},
            }
        )
    )

    def forbidden() -> Any:
        raise AssertionError("read-only boundary resolved a live transport")

    monkeypatch.setattr(board, "resolve_mission_control_root", forbidden)
    assert board.main(["--boundary", "close", "--record", str(record), "--dry-run"]) == 0
    result = json.loads(capsys.readouterr().out)
    assert result["stage"] == "Retro" and result["dry_run"] is True
    assert result["payload"] == {"assignments": [["Stage", "Retro"], ["Status", "Ready to close"]]}
    assert board.main(["--boundary", "review-accepted", "--record", str(record)]) == 0
    result = json.loads(capsys.readouterr().out)
    assert (
        result["submits"] is False
        and result["number"] == 45
        and "no allowed submission" in result["note"]
    )


@pytest.mark.parametrize(
    ("args", "error"),
    [
        (["--boundary", "build-start"], "needs --record"),
        (["--boundary", "unknown"], "unknown boundary"),
    ],
)
def test_boundary_cli_missing_or_unknown_input(
    board: ModuleType,
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
    args: list[str],
    error: str,
) -> None:
    if "unknown" in args:
        record = tmp_path / "run.json"
        record.write_text('{"repo":"fixture/repo","issue":45}')
        args += ["--record", str(record)]
    assert board.main(args) == 2
    assert error in json.loads(capsys.readouterr().err)["error"]


@pytest.mark.parametrize("boundary", [False, True])
@pytest.mark.parametrize("succeeds", [False, True])
def test_actual_cli_reports_outgoing_submission_and_durable_result(
    board: ModuleType,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
    boundary: bool,
    succeeds: bool,
) -> None:
    calls, run = transport("", 0 if succeeds else 1, "controlled refusal")
    monkeypatch.setattr(subprocess, "run", run)
    ledger = tmp_path / "ledger"
    shared = ["--repo-root", str(tmp_path), "--ledger-dir", str(ledger), "--project", "asgard"]
    if boundary:
        record = tmp_path / "run.json"
        record.write_text('{"schema":"run_record.v1","repo":"fixture/repo","issue":45}')
        argv = ["--boundary", "build-start", "--record", str(record), *shared]
    else:
        argv = [
            "write",
            "--op",
            "issue-label-add",
            "--repo",
            "fixture/repo",
            "--number",
            "45",
            "--payload",
            '{"label":"verified"}',
            *shared,
        ]
    assert board.main(argv) == (0 if succeeds else 1)
    result = json.loads(capsys.readouterr().out)
    assert result["status"] == ("written" if succeeds else "failed")
    assert result["repo"] == "fixture/repo" and result["number"] == 45
    assert len(calls) == (1 if succeeds else 3)
    assert bool(list(ledger.glob("*.json"))) is succeeds
    if boundary:
        assert result["stage"] == "Active" and result["boundary"] == "build-start"
        assert calls[0][0][-9:] == [
            "--field",
            "Stage",
            "--option",
            "Active",
            "--field",
            "Status",
            "--option",
            "Implementing",
            "--correction",
        ]


@pytest.mark.parametrize("boundary", [False, True])
def test_cli_resolution_failure_is_structured_and_no_ledger_is_created(
    board: ModuleType,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
    boundary: bool,
) -> None:
    def unavailable() -> Any:
        raise RuntimeError("controlled missing install")

    monkeypatch.setattr(board, "resolve_mission_control_root", unavailable)
    ledger = tmp_path / "ledger"
    shared = ["--repo-root", str(tmp_path), "--ledger-dir", str(ledger)]
    if boundary:
        record = tmp_path / "run.json"
        record.write_text('{"repo":"fixture/repo","issue":45}')
        argv = ["--boundary", "build-start", "--record", str(record), *shared]
    else:
        argv = [
            "write",
            "--op",
            "issue-label-add",
            "--repo",
            "fixture/repo",
            "--number",
            "45",
            *shared,
        ]
    assert board.main(argv) == 1
    assert json.loads(capsys.readouterr().err) == {
        "ok": False,
        "error": "controlled missing install",
    }
    assert not ledger.exists()


def test_gated_cli_needs_no_install_and_defaults_ledger_to_private_repo(
    board: ModuleType,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    assert board._repo_root_default() == ROOT
    monkeypatch.setattr(board, "_repo_root_default", lambda: tmp_path)
    assert (
        board.main(
            ["write", "--op", "parent-issue-close", "--repo", "fixture/repo", "--number", "45"]
        )
        == 0
    )
    assert json.loads(capsys.readouterr().out)["status"] == "gated"
    assert not (tmp_path / ".claude").exists()
    assert board._default_ledger_dir(tmp_path) == tmp_path / ".claude/saga/board-progression"
    with pytest.raises(AssertionError, match="certificate-gated"):
        board._gated_writer()


def test_cli_requires_a_boundary_or_write_verb(
    board: ModuleType, capsys: pytest.CaptureFixture[str]
) -> None:
    with pytest.raises(SystemExit) as error:
        board.main([])
    assert error.value.code == 2 and "name a --boundary" in capsys.readouterr().err


def test_progress_retry_keeps_one_marker_through_actual_writer_and_ledger(
    board: ModuleType, tmp_path: Path
) -> None:
    key = "issue-progress-comment:fixture/repo#45:work-tick-1"
    marker = "<!-- saga-board-sync-idempotency:" + hashlib.sha256(key.encode()).hexdigest() + " -->"
    body = "verified build progress\n" + marker
    calls, run = transport("[]")
    writer = board.default_board_writer(mission_control_root=tmp_path, runner=run)
    record = board.authorize_and_write(
        "issue-progress-comment",
        "fixture/repo",
        45,
        "work-tick-1",
        board_writer=writer,
        ledger_dir=tmp_path / "ledger",
        payload={"body": body},
    )
    assert record["status"] == "written" and record["key"] == key
    assert len(calls) == 2 and calls[1][0][-2:] == ["--body", body]
    assert calls[1][0][-1].count(marker) == 1
    assert json.loads(next((tmp_path / "ledger").glob("*.json")).read_text())["key"] == key
