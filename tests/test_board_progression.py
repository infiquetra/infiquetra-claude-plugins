"""Tests for board_progression — the plugin-agnostic certificate-gated board writer (#344 U1).

Offline: the certificate is real, the board_writer and write_once are injected fakes, and the CLI's
concrete writer is patched — no live gh, no mission-control child process.
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


CERT_MOD = _load("reversibility_certificate")
BP = _load("board_progression")


class RecordingWriter:
    """Fake board_writer: records calls, never touches GitHub."""

    def __init__(self, *, fail_times: int = 0) -> None:
        self.calls: list[dict[str, Any]] = []
        self._fail_times = fail_times

    def __call__(self, *, op_kind: str, repo: str, number: int, payload: dict) -> None:
        self.calls.append({"op_kind": op_kind, "repo": repo, "number": number, "payload": payload})
        if len(self.calls) <= self._fail_times:
            raise RuntimeError("board write failed (injected)")


def _ledger(tmp_path: Path) -> Path:
    d = tmp_path / "ledger"
    d.mkdir(parents=True, exist_ok=True)
    return d


# ---------------------------------------------------------------------------
# Core mechanism
# ---------------------------------------------------------------------------


def test_authorized_reversible_op_writes_and_records(tmp_path: Path) -> None:
    """AUTHORIZED reversible op, absent key → board_writer called once, 'written', ledger key written."""
    ld = _ledger(tmp_path)
    writer = RecordingWriter()
    rec = BP.authorize_and_write(
        "set-field-status", "infiquetra/x", 42, "Done", board_writer=writer, ledger_dir=ld
    )
    assert rec["status"] == "written"
    assert len(writer.calls) == 1
    assert writer.calls[0]["payload"]["target_state"] == "Done"
    assert list(ld.glob("*.json")), "a ledger key must be written on success"


def test_present_key_is_idempotent_skip(tmp_path: Path) -> None:
    """A present ledger key → 'skipped', board_writer NOT called (crash/retry safety)."""
    ld = _ledger(tmp_path)
    writer = RecordingWriter()
    first = BP.authorize_and_write(
        "set-field-status", "infiquetra/x", 42, "Done", board_writer=writer, ledger_dir=ld
    )
    assert first["status"] == "written"
    second = BP.authorize_and_write(
        "set-field-status", "infiquetra/x", 42, "Done", board_writer=writer, ledger_dir=ld
    )
    assert second["status"] == "skipped"
    assert len(writer.calls) == 1, "the second call must not re-drive the writer"


@pytest.mark.parametrize("op", ["merge-pr", "deploy", "parent-issue-close"])
def test_merge_deploy_and_always_operator_gate(tmp_path: Path, op: str) -> None:
    """R3/KTD2: merge/deploy (absent from registry) and ALWAYS_OPERATOR ops → 'gated', no write."""
    ld = _ledger(tmp_path)
    writer = RecordingWriter()
    rec = BP.authorize_and_write(op, "infiquetra/x", 42, "", board_writer=writer, ledger_dir=ld)
    assert rec["status"] == "gated"
    assert rec["verdict"] == "GATE"
    assert writer.calls == [], "a gated op must never call the board_writer"
    assert not list(ld.glob("*.json")), "a gated op must write no ledger key"


def test_all_attempts_fail_writes_no_key(tmp_path: Path) -> None:
    """R18: writer raises through all attempts → 'failed', NO ledger key (retryable next tick)."""
    ld = _ledger(tmp_path)
    writer = RecordingWriter(fail_times=99)
    rec = BP.authorize_and_write(
        "set-field-status",
        "infiquetra/x",
        42,
        "Done",
        board_writer=writer,
        ledger_dir=ld,
        max_attempts=3,
    )
    assert rec["status"] == "failed"
    assert rec["attempts"] == 3
    assert len(writer.calls) == 3
    assert not list(ld.glob("*.json")), "no ledger key may be written when the op fails"


def test_retry_then_succeed(tmp_path: Path) -> None:
    """Bounded retry: first attempt fails, second succeeds → 'written', one ledger key."""
    ld = _ledger(tmp_path)
    writer = RecordingWriter(fail_times=1)
    rec = BP.authorize_and_write(
        "set-field-status", "infiquetra/x", 42, "Done", board_writer=writer, ledger_dir=ld
    )
    assert rec["status"] == "written"
    assert rec["attempts"] == 2
    assert len(list(ld.glob("*.json"))) == 1


def test_ledger_fault_after_write_surfaces_error_not_raises(tmp_path: Path) -> None:
    """A ledger-write fault AFTER a committed board write → 'error' (may_reapply), must NOT raise."""
    ld = _ledger(tmp_path)
    writer = RecordingWriter()

    def _boom(_path: Path, _content: str) -> bool:
        raise OSError("disk full")

    rec = BP.authorize_and_write(
        "set-field-status",
        "infiquetra/x",
        42,
        "Done",
        board_writer=writer,
        ledger_dir=ld,
        write_once=_boom,
    )
    assert rec["status"] == "error"
    assert rec["may_reapply"] is True
    assert len(writer.calls) == 1, "the board write did commit before the ledger fault"


def test_extra_is_merged_into_record(tmp_path: Path) -> None:
    """extra={} is merged into every record — how /outcome keeps its subplot_id shape (R2)."""
    ld = _ledger(tmp_path)
    rec = BP.authorize_and_write(
        "set-field-status",
        "infiquetra/x",
        42,
        "Done",
        board_writer=RecordingWriter(),
        ledger_dir=ld,
        extra={"subplot_id": "leaf1"},
    )
    assert rec["subplot_id"] == "leaf1"
    assert rec["op_kind"] == "set-field-status"


def test_issue_progress_comment_payload_gets_idempotency_marker(tmp_path: Path) -> None:
    """A progress comment carries a hidden marker derived from the same key as the ledger file."""
    ld = _ledger(tmp_path)
    writer = RecordingWriter()
    payload = {"body": "visible progress"}

    rec = BP.authorize_and_write(
        "issue-progress-comment",
        "infiquetra/x",
        42,
        "done",
        board_writer=writer,
        ledger_dir=ld,
        payload=payload,
    )

    key = CERT_MOD.idempotency_key("issue-progress-comment", "infiquetra/x", 42, "done")
    marker = BP._comment_idempotency_marker(key)
    assert rec["status"] == "written"
    assert writer.calls[0]["payload"]["body"] == f"visible progress\n\n{marker}"
    assert payload == {"body": "visible progress"}, "caller payload must not be mutated"


def test_non_comment_payload_does_not_get_comment_marker(tmp_path: Path) -> None:
    """Only additive progress comments get the hidden comment marker."""
    ld = _ledger(tmp_path)
    writer = RecordingWriter()

    BP.authorize_and_write(
        "issue-label-add",
        "infiquetra/x",
        42,
        "blocked",
        board_writer=writer,
        ledger_dir=ld,
        payload={"label": "blocked"},
    )

    assert writer.calls[0]["payload"] == {"label": "blocked", "target_state": "blocked"}


def test_default_writer_skips_post_when_marked_comment_already_exists(tmp_path: Path) -> None:
    """Production writer preflights marked comments and treats an existing marker as success."""
    key = CERT_MOD.idempotency_key("issue-progress-comment", "infiquetra/x", 42, "done")
    marker = BP._comment_idempotency_marker(key)
    calls: list[list[str]] = []

    class _Ok:
        returncode = 0
        stderr = ""

        def __init__(self, stdout: str = "") -> None:
            self.stdout = stdout

    def fake_run(cmd: list[str], **_kw: Any) -> Any:
        calls.append(cmd)
        if cmd[:2] == ["gh", "api"]:
            return _Ok(json.dumps([{"body": f"already posted {marker}"}]))
        return _Ok()

    writer = BP.default_board_writer(tmp_path, runner=fake_run)
    writer(
        op_kind="issue-progress-comment",
        repo="infiquetra/x",
        number=42,
        payload={"body": f"visible progress\n\n{marker}"},
    )

    assert [c[:2] for c in calls] == [["gh", "api"]]
    assert "--method" in calls[0]
    assert "GET" in calls[0]
    assert calls[0][4] == "repos/infiquetra/x/issues/42/comments"
    assert not any(c[2:4] == ["issue", "comment"] for c in calls)


def test_comment_crash_replay_skips_remote_duplicate_and_writes_local_ledger(
    tmp_path: Path,
) -> None:
    """Remote marker present + missing local key → no duplicate POST, then ledger is restored."""
    ld = _ledger(tmp_path)
    key = CERT_MOD.idempotency_key("issue-progress-comment", "infiquetra/x", 42, "done")
    marker = BP._comment_idempotency_marker(key)
    calls: list[list[str]] = []

    class _Ok:
        returncode = 0
        stderr = ""

        def __init__(self, stdout: str = "") -> None:
            self.stdout = stdout

    def fake_run(cmd: list[str], **_kw: Any) -> Any:
        calls.append(cmd)
        if cmd[:2] == ["gh", "api"]:
            return _Ok(json.dumps([{"body": f"previous crash left {marker} remote"}]))
        return _Ok()

    rec = BP.authorize_and_write(
        "issue-progress-comment",
        "infiquetra/x",
        42,
        "done",
        board_writer=BP.default_board_writer(tmp_path, runner=fake_run),
        ledger_dir=ld,
        payload={"body": "visible progress"},
    )

    assert rec["status"] == "written"
    assert not any(c[2:4] == ["issue", "comment"] for c in calls)
    assert (ld / BP._safe_ledger_name(key)).exists()


# ---------------------------------------------------------------------------
# CLI (skill-invokable, #344 KTD6)
# ---------------------------------------------------------------------------


def test_cli_gated_op_prints_gated_exit_zero(tmp_path: Path, capsys: Any) -> None:
    """CLI: a merge-like op prints {"status":"gated"} and exits 0 (a gate is a normal outcome)."""
    rc = BP.main(
        [
            "write",
            "--op",
            "merge-pr",
            "--repo",
            "infiquetra/x",
            "--number",
            "42",
            "--ledger-dir",
            str(tmp_path),
        ]
    )
    out = json.loads(capsys.readouterr().out)
    assert out["status"] == "gated"
    assert rc == 0


def test_cli_authorized_op_written(tmp_path: Path, capsys: Any, monkeypatch: Any) -> None:
    """CLI: an authorized op prints {"status":"written"} — concrete writer patched (no live gh)."""
    calls: list[tuple[str, str, int]] = []

    def _fake_factory(repo_root: Path, *, project: str = "operations", runner: Any = None) -> Any:
        def _w(*, op_kind: str, repo: str, number: int, payload: dict) -> None:
            calls.append((op_kind, repo, number))

        return _w

    monkeypatch.setattr(BP, "default_board_writer", _fake_factory)
    rc = BP.main(
        [
            "write",
            "--op",
            "set-field-status",
            "--repo",
            "infiquetra/x",
            "--number",
            "42",
            "--target-state",
            "Done",
            "--ledger-dir",
            str(tmp_path),
        ]
    )
    out = json.loads(capsys.readouterr().out)
    assert out["status"] == "written"
    assert rc == 0
    assert calls == [("set-field-status", "infiquetra/x", 42)]
