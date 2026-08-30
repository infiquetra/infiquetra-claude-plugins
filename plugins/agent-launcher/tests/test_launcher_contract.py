"""Contract tests for the portable agent-launcher plugin (#777)."""

from __future__ import annotations

import importlib.util
import inspect
import json
import os
import re
import subprocess
import sys
import time
from collections.abc import Callable
from pathlib import Path
from types import ModuleType
from typing import Any

import pytest

REPO = Path(__file__).resolve().parents[3]
LAUNCHER = (
    REPO / "plugins" / "agent-launcher" / "skills" / "agent-launcher" / "scripts" / "launcher.py"
)
ORCHESTRATE = (
    REPO / "plugins" / "orchestrate" / "skills" / "orchestrate" / "scripts" / "orchestrate.py"
)

BACKGROUND_FLAGS = ("--no-focus", "--current", "--herdr", "--herdr-control-only")


def _load(path: Path, name: str) -> ModuleType:
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


@pytest.fixture(scope="module")
def launcher() -> ModuleType:
    return _load(LAUNCHER, "_agent_launcher_contract")


@pytest.fixture
def launcher_on_path(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    binary = tmp_path / "agents"
    binary.write_text("#!/bin/sh\n")
    binary.chmod(0o755)
    monkeypatch.setenv("PATH", str(tmp_path), prepend=os.pathsep)
    monkeypatch.delenv("ORCHESTRATE_AGENT_LAUNCHER", raising=False)
    return binary


def test_orchestrate_has_no_private_launcher_copy() -> None:
    text = ORCHESTRATE.read_text(encoding="utf-8")
    assert "def agent_argv(" not in text
    assert "def launcher(" not in text
    assert "VENDOR_FLAGS:" not in text
    assert "def verify_unit_preflight(" not in text
    assert "def close_run_session(" not in text
    assert "_ingest_agent_launcher" in text
    assert "agent-launcher" in text
    assert 'run(["herdr", "tab", "close"' not in text
    assert "close_run_session(unit)" in text


def test_degraded_path_binds_settle_and_review_names() -> None:
    text = ORCHESTRATE.read_text(encoding="utf-8")
    block = text.split("if not _ingest_agent_launcher():", 1)[1].split("def repo_root", 1)[0]
    for name in (
        "append_unit_note",
        "VENDOR_FLAGS",
        "say",
        "has_delivery_warning",
        "VENDOR_PERMISSION",
        "VENDOR_NOTES",
        "models",
        "favourites",
        "clear_delivery_warning",
        "AccountMismatchError",
    ):
        assert name in block, name


def test_orchestrate_subprocess_cli_is_not_the_launcher_cli() -> None:
    """Ingest must not run launcher.py's __main__ when orchestrate.py is argv[0]."""
    proc = subprocess.run(
        [sys.executable, str(ORCHESTRATE), "--help"],
        check=False,
        capture_output=True,
        text=True,
    )
    assert proc.returncode == 0, proc.stderr
    assert "wait" in proc.stdout
    assert "clean" in proc.stdout
    assert "{argv,preview,launch,close,roster}" not in proc.stdout


def test_orchestrate_ingests_this_script() -> None:
    orch = _load(ORCHESTRATE, "_orchestrate_ingest_proof")
    assert Path(orch.agent_argv.__code__.co_filename).resolve() == LAUNCHER.resolve()
    assert Path(orch.launch.__code__.co_filename).resolve() == LAUNCHER.resolve()
    assert orch.agent_argv is not None


@pytest.mark.usefixtures("launcher_on_path")
@pytest.mark.parametrize("vendor", ["claude", "codex", "grok", "muse", "agy", "qwen", "opencode"])
def test_argv_locks_background_flags_before_vendor(launcher: ModuleType, vendor: str) -> None:
    unit = launcher.LaunchRequest(name="reviewer", vendor=vendor, worktree="/tmp/wt")
    argv = launcher.agent_argv(unit)
    vendor_idx = argv.index(vendor)
    for flag in BACKGROUND_FLAGS:
        assert flag in argv
        assert argv.index(flag) < vendor_idx
    assert argv[argv.index("--cwd") + 1] == "/tmp/wt"
    assert argv[argv.index("--task") + 1] == "reviewer"


@pytest.mark.usefixtures("launcher_on_path")
def test_preview_argv_puts_dry_run_in_launcher_position(launcher: ModuleType) -> None:
    unit = launcher.LaunchRequest(
        name="reviewer",
        vendor="codex",
        worktree="/tmp/wt",
        model="gpt-5.4",
        effort="xhigh",
        permission="auto",
    )
    argv = launcher.preview_argv(unit)
    assert argv[1] == "--dry-run"
    assert argv.index("--dry-run") < argv.index("codex")
    assert "--no-focus" in argv
    vendor_tail = argv[argv.index("codex") :]
    assert vendor_tail[:1] == ["codex"]
    assert "--model" in vendor_tail
    assert "gpt-5.4" in vendor_tail
    assert any(
        part.startswith("model_reasoning_effort=") or part == "xhigh" for part in vendor_tail
    )


@pytest.mark.usefixtures("launcher_on_path")
def test_cli_argv_does_not_import_orchestrate(launcher_on_path: Path) -> None:
    proc = subprocess.run(
        [
            sys.executable,
            str(LAUNCHER),
            "argv",
            "--vendor",
            "codex",
            "--task",
            "plain-session",
            "--cwd",
            "/tmp/plain",
            "--model",
            "gpt-5.4",
            "--effort",
            "xhigh",
        ],
        check=False,
        capture_output=True,
        text=True,
        env={
            **os.environ,
            "PATH": str(launcher_on_path.parent) + os.pathsep + os.environ.get("PATH", ""),
        },
    )
    assert proc.returncode == 0, proc.stderr
    argv = proc.stdout.strip().split()
    assert "codex" in argv
    assert "--no-focus" in argv
    assert "--herdr-control-only" in argv
    assert argv[argv.index("--cwd") + 1] == str(Path("/tmp/plain").resolve())


def test_cli_refuses_skip_preview(launcher_on_path: Path) -> None:
    proc = subprocess.run(
        [
            sys.executable,
            str(LAUNCHER),
            "launch",
            "--vendor",
            "codex",
            "--task",
            "x",
            "--skip-preview",
        ],
        check=False,
        capture_output=True,
        text=True,
        env={
            **os.environ,
            "PATH": str(launcher_on_path.parent) + os.pathsep + os.environ.get("PATH", ""),
        },
    )
    assert proc.returncode != 0
    assert "preview" in (proc.stderr + proc.stdout).lower()


def test_malformed_receipt_stops_launch(
    launcher: ModuleType, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    wrapper = tmp_path / "agents"
    wrapper.write_text("#!/bin/sh\necho not-json\n")
    wrapper.chmod(0o755)
    monkeypatch.setenv("PATH", str(tmp_path), prepend=os.pathsep)
    monkeypatch.setattr(launcher, "await_ready", lambda *_a, **_k: True)
    unit = launcher.LaunchRequest(name="broken", vendor="codex", worktree=str(tmp_path))
    with pytest.raises(SystemExit, match="JSON"):
        launcher.launch(unit)


def test_nonzero_wrapper_exit_stops_launch(
    launcher: ModuleType, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    wrapper = tmp_path / "agents"
    wrapper.write_text("#!/bin/sh\necho fail >&2\nexit 3\n")
    wrapper.chmod(0o755)
    monkeypatch.setenv("PATH", str(tmp_path), prepend=os.pathsep)
    unit = launcher.LaunchRequest(name="failing", vendor="codex", worktree=str(tmp_path))
    with pytest.raises(SystemExit, match="command failed"):
        launcher.launch(unit)


def test_hanging_create_stops_at_the_deadline(
    launcher: ModuleType, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    receipt = {
        "tab_id": "tab-1",
        "agent_name": "hangs-2",
        "pane_id": "pane-1",
        "reused": False,
    }
    wrapper = tmp_path / "agents"
    wrapper.write_text("#!/bin/sh\nsleep 5\ncat <<'EOF'\n" + json.dumps(receipt) + "\nEOF\n")
    wrapper.chmod(0o755)
    monkeypatch.setenv("PATH", str(tmp_path), prepend=os.pathsep)
    monkeypatch.setattr(launcher, "LAUNCH_CREATE_SECONDS", 0.5)
    # Stub the post-create stages so that, with the timeout removed, the launch proceeds past the
    # create into a differently-worded stop instead of blocking the test out on a real one.
    monkeypatch.setattr(launcher, "await_ready", lambda *_a, **_k: True)
    monkeypatch.setattr(
        launcher,
        "verify_unit_preflight",
        lambda *a, **k: (_ for _ in ()).throw(SystemExit("stop after identity")),
    )
    unit = launcher.LaunchRequest(name="hangs", vendor="codex", worktree=str(tmp_path))
    start = time.monotonic()
    with pytest.raises(SystemExit, match="timed out after"):
        launcher.launch(unit)
    elapsed = time.monotonic() - start
    assert elapsed < 3.0, f"the create took {elapsed:.1f}s; the deadline did not stop it"


def test_launch_create_deadline_is_a_named_constant(launcher: ModuleType) -> None:
    assert "LAUNCH_CREATE_SECONDS" in inspect.getsource(launcher.launch)
    assert isinstance(launcher.LAUNCH_CREATE_SECONDS, float)
    assert 0 < launcher.LAUNCH_CREATE_SECONDS <= 300


def test_create_within_the_deadline_is_unaffected(
    launcher: ModuleType, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    receipt = {
        "tab_id": "tab-1",
        "agent_name": "reviewer-2",
        "pane_id": "pane-1",
        "reused": False,
    }
    wrapper = tmp_path / "agents"
    wrapper.write_text("#!/bin/sh\ncat <<'EOF'\n" + json.dumps(receipt) + "\nEOF\n")
    wrapper.chmod(0o755)
    monkeypatch.setenv("PATH", str(tmp_path), prepend=os.pathsep)
    monkeypatch.setattr(launcher, "await_ready", lambda *_a, **_k: True)
    monkeypatch.setattr(
        launcher,
        "verify_unit_preflight",
        lambda *a, **k: (_ for _ in ()).throw(SystemExit("stop after identity")),
    )
    unit = launcher.LaunchRequest(name="reviewer", vendor="codex", worktree=str(tmp_path))
    with pytest.raises(SystemExit, match="stop after identity"):
        launcher.launch(unit)
    assert unit.tab_id == "tab-1"


CODEX_PLACEHOLDER = "\x1b[38;2;153;153;153m› Ask Codex to do anything\x1b[0m"
STAGED_SLASH_COMMAND = "/saga:doc-review docs/plans/x.md"


def _claude_pane(composer_line: str) -> str:
    rule = "\x1b[2m──────────────────────────────\x1b[0m"
    return f"{rule}\n{composer_line}\n{rule}\n"


def _make_fake_run(
    recorded: list[list[str]],
    *,
    pane_dump: str,
    existing_tabs: tuple[str, ...],
    receipt: dict[str, object],
) -> Callable[..., subprocess.CompletedProcess[str]]:
    def fake_run(cmd: list[str], **_k: object) -> subprocess.CompletedProcess[str]:
        recorded.append(cmd)
        if cmd[:3] == ["herdr", "tab", "list"]:
            tabs = {"result": {"tabs": [{"tab_id": t, "label": t} for t in existing_tabs]}}
            return subprocess.CompletedProcess(cmd, 0, json.dumps(tabs), "")
        if cmd[:3] == ["herdr", "pane", "current"]:
            pane = {"result": {"pane": {"workspace_id": "w80"}}}
            return subprocess.CompletedProcess(cmd, 0, json.dumps(pane), "")
        if cmd[:3] == ["herdr", "pane", "read"]:
            return subprocess.CompletedProcess(cmd, 0, pane_dump, "")
        return subprocess.CompletedProcess(cmd, 0, json.dumps(receipt), "")

    return fake_run


def _prepare_guard_launch(
    launcher: ModuleType,
    monkeypatch: pytest.MonkeyPatch,
    *,
    pane_dump: str,
    receipt_tab: str,
    existing_tabs: tuple[str, ...],
) -> tuple[Any, list[list[str]], list[tuple[Any, ...]]]:
    recorded: list[list[str]] = []
    sends: list[tuple[Any, ...]] = []
    receipt = {
        "tab_id": receipt_tab,
        "agent_name": "reviewer-2",
        "pane_id": "w80:p9",
        "reused": True,
    }
    monkeypatch.setattr(
        launcher,
        "run",
        _make_fake_run(recorded, pane_dump=pane_dump, existing_tabs=existing_tabs, receipt=receipt),
    )
    # launch() resolves the wrapper in agent_argv before run(); stubbing run is not enough.
    monkeypatch.setattr(launcher, "launcher", lambda: "agents")
    monkeypatch.setattr(launcher, "await_ready", lambda *_a, **_k: True)
    monkeypatch.setattr(launcher, "verify_unit_preflight", lambda *a, **k: {})
    monkeypatch.setattr(launcher, "send", lambda *a, **k: sends.append(a))
    monkeypatch.setattr(launcher, "took_the_task", lambda *_a, **_k: True)
    unit = launcher.LaunchRequest(name="reviewer", vendor="codex", worktree="/tmp/wt")
    return unit, recorded, sends


def test_composer_placeholder_is_not_staged_text(launcher: ModuleType) -> None:
    assert launcher.composer_staged_text(CODEX_PLACEHOLDER) == ""


def test_composer_typed_text_is_staged(launcher: ModuleType) -> None:
    staged = launcher.composer_staged_text(f"❯ {STAGED_SLASH_COMMAND}")
    assert staged == STAGED_SLASH_COMMAND


def test_composer_absent_reads_as_unreadable(launcher: ModuleType) -> None:
    dump = "some session output\na second line of plain output\n"
    assert launcher.composer_staged_text(dump) is None


def test_reused_pane_holding_a_slash_command_is_not_prompted(
    launcher: ModuleType, monkeypatch: pytest.MonkeyPatch
) -> None:
    unit, _recorded, sends = _prepare_guard_launch(
        launcher,
        monkeypatch,
        pane_dump=_claude_pane(f"❯ {STAGED_SLASH_COMMAND}"),
        receipt_tab="w80:t1",
        existing_tabs=("w80:t1",),
    )
    with pytest.raises(SystemExit, match="already holds staged input"):
        launcher.launch(unit)
    assert sends == []
    assert unit.launch_receipt["input_box"] == "staged"
    assert STAGED_SLASH_COMMAND not in str(unit.launch_receipt)


def test_staged_text_is_recorded_not_discarded(
    launcher: ModuleType, monkeypatch: pytest.MonkeyPatch
) -> None:
    unit, _recorded, sends = _prepare_guard_launch(
        launcher,
        monkeypatch,
        pane_dump=_claude_pane(f"❯ {STAGED_SLASH_COMMAND}"),
        receipt_tab="w80:t1",
        existing_tabs=("w80:t1",),
    )
    with pytest.raises(SystemExit, match="already holds staged input"):
        launcher.launch(unit)
    assert sends == []
    assert unit.launch_receipt["input_box"] == "staged"
    assert unit.launch_receipt["input_box_text_chars"] == len(STAGED_SLASH_COMMAND)
    assert STAGED_SLASH_COMMAND not in json.dumps(unit.launch_receipt)
    assert STAGED_SLASH_COMMAND not in unit.note


def test_empty_reused_box_is_prompted_exactly_as_today(
    launcher: ModuleType, monkeypatch: pytest.MonkeyPatch
) -> None:
    unit, recorded, sends = _prepare_guard_launch(
        launcher,
        monkeypatch,
        pane_dump=_claude_pane("❯ "),
        receipt_tab="w80:t1",
        existing_tabs=("w80:t1",),
    )
    launcher.launch(unit)
    assert len(sends) == 1
    ansi_reads = [c for c in recorded if c[:3] == ["herdr", "pane", "read"] and "--format" in c]
    assert len(ansi_reads) == 1
    assert unit.launch_receipt["input_box"] == "empty"


def test_freshly_created_pane_takes_no_inspection_path(
    launcher: ModuleType, monkeypatch: pytest.MonkeyPatch
) -> None:
    unit, recorded, sends = _prepare_guard_launch(
        launcher,
        monkeypatch,
        pane_dump=_claude_pane(f"❯ {STAGED_SLASH_COMMAND}"),
        receipt_tab="w80:t9",
        existing_tabs=("w80:t1",),
    )
    launcher.launch(unit)
    assert len(sends) == 1
    ansi_reads = [c for c in recorded if c[:3] == ["herdr", "pane", "read"] and "--format" in c]
    assert ansi_reads == []


@pytest.mark.parametrize("reset_code", ["00", "39", "22", "0;10"])
def test_reset_codes_after_a_styled_marker_return_the_staged_text(
    launcher: ModuleType, reset_code: str
) -> None:
    """Every style-off shape the terminal defines ends the styled span at the marker."""
    line = f"\x1b[2m❯\x1b[{reset_code}m /deploy prod --force"
    assert launcher.composer_staged_text(line) == "/deploy prod --force"


def test_marker_styled_and_never_reset_counts_as_staged(launcher: ModuleType) -> None:
    """Styling that spans the whole line and never ends cannot be a placeholder signal."""
    assert launcher.composer_staged_text("\x1b[2m❯ /deploy prod --force") == "/deploy prod --force"


def test_a_bare_marker_row_below_staged_text_is_a_decoy(launcher: ModuleType) -> None:
    assert launcher.composer_staged_text("❯ rm -rf /important\n> ") == "rm -rf /important"


def test_a_quoted_row_below_staged_text_is_not_the_composer(launcher: ModuleType) -> None:
    dump = "❯ rm -rf /important\n> quoted line"
    assert launcher.composer_staged_text(dump) == "rm -rf /important"


def test_menu_rows_below_staged_text_are_not_the_composer(launcher: ModuleType) -> None:
    dump = "❯ deploy now\n> Option A\n> Option B"
    assert launcher.composer_staged_text(dump) == "deploy now"


def test_a_scrollback_echo_is_not_the_composer(launcher: ModuleType) -> None:
    dump = "❯ earlier submitted prompt\npane output line\n❯ "
    assert launcher.composer_staged_text(dump) == ""


def test_escapes_inside_staged_text_are_stripped(launcher: ModuleType) -> None:
    assert launcher.composer_staged_text("❯ deploy the \x1b[Kfleet") == "deploy the fleet"


def test_unreadable_box_is_marked_and_the_prompt_still_goes(
    launcher: ModuleType, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A genuine nonzero pane read drives the guard's failure branch: the box is marked
    unreadable, noted, and the launch still prompts. The fake captures the timeout keyword
    because the read it bounds must actually carry one."""
    recorded: list[list[str]] = []
    pane_read_timeouts: list[object] = []
    sends: list[tuple[Any, ...]] = []
    receipt = {
        "tab_id": "w80:t1",
        "agent_name": "reader-2",
        "pane_id": "w80:p9",
        "reused": False,
    }

    def fake_run(cmd: list[str], **kwargs: object) -> subprocess.CompletedProcess[str]:
        recorded.append(cmd)
        if cmd[:3] == ["herdr", "pane", "read"]:
            pane_read_timeouts.append(kwargs.get("timeout"))
            return subprocess.CompletedProcess(cmd, 1, "", "no such pane")
        if cmd[:3] == ["herdr", "tab", "list"]:
            tabs = {"result": {"tabs": [{"tab_id": "w80:t1", "label": "t"}]}}
            return subprocess.CompletedProcess(cmd, 0, json.dumps(tabs), "")
        if cmd[:3] == ["herdr", "pane", "current"]:
            pane = {"result": {"pane": {"workspace_id": "w80"}}}
            return subprocess.CompletedProcess(cmd, 0, json.dumps(pane), "")
        return subprocess.CompletedProcess(cmd, 0, json.dumps(receipt), "")

    monkeypatch.setattr(launcher, "run", fake_run)
    monkeypatch.setattr(launcher, "launcher", lambda: "agents")
    monkeypatch.setattr(launcher, "await_ready", lambda *_a, **_k: True)
    monkeypatch.setattr(launcher, "verify_unit_preflight", lambda *a, **k: {})
    monkeypatch.setattr(launcher, "send", lambda *a, **k: sends.append(a))
    monkeypatch.setattr(launcher, "took_the_task", lambda *_a, **_k: True)
    unit = launcher.LaunchRequest(name="reader", vendor="codex", worktree="/tmp/wt")
    launcher.launch(unit)
    assert unit.launch_receipt["input_box"] == "unreadable"
    assert "input box not readable" in unit.note
    assert len(sends) == 1
    assert pane_read_timeouts == [launcher.PANE_INPUT_READ_SECONDS]


def test_staged_text_reaches_no_sink_verbatim(
    launcher: ModuleType, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The operator's draft reaches none of the durable sinks: not the receipt, not the unit
    note, not the stop message -- and therefore not the run record the note and message feed.
    The stop proves the box was not empty with a length and says the text was withheld."""
    unit, _recorded, _sends = _prepare_guard_launch(
        launcher,
        monkeypatch,
        pane_dump=_claude_pane(f"❯ {STAGED_SLASH_COMMAND}"),
        receipt_tab="w80:t1",
        existing_tabs=("w80:t1",),
    )
    with pytest.raises(SystemExit) as exc_info:
        launcher.launch(unit)
    message = str(exc_info.value)
    assert STAGED_SLASH_COMMAND not in message
    assert "withheld" in message
    assert STAGED_SLASH_COMMAND not in unit.note
    assert STAGED_SLASH_COMMAND not in json.dumps(unit.launch_receipt)
    assert unit.launch_receipt["input_box_text_chars"] == len(STAGED_SLASH_COMMAND)


def test_opencode_guard_reads_before_the_picker_types(
    launcher: ModuleType, monkeypatch: pytest.MonkeyPatch
) -> None:
    """An unowned OpenCode pane holding staged text: the guard must stop the launch before the
    variant picker has typed anything into the pane through the same door prompts use."""
    typed: list[list[str]] = []
    dump = "Choose variant:\n> high\n> low\n" + _claude_pane(f"❯ {STAGED_SLASH_COMMAND}")
    receipt = {
        "tab_id": "w80:t1",
        "agent_name": "oc-2",
        "pane_id": "w80:p9",
        "reused": False,
    }

    def fake_run(cmd: list[str], **_k: object) -> subprocess.CompletedProcess[str]:
        if cmd[:3] == ["herdr", "pane", "run"]:
            typed.append(cmd)
            return subprocess.CompletedProcess(cmd, 0, "", "")
        if cmd[:3] == ["herdr", "pane", "read"]:
            return subprocess.CompletedProcess(cmd, 0, dump, "")
        if cmd[:3] == ["herdr", "tab", "list"]:
            tabs = {"result": {"tabs": [{"tab_id": "w80:t1", "label": "t"}]}}
            return subprocess.CompletedProcess(cmd, 0, json.dumps(tabs), "")
        if cmd[:3] == ["herdr", "pane", "current"]:
            pane = {"result": {"pane": {"workspace_id": "w80"}}}
            return subprocess.CompletedProcess(cmd, 0, json.dumps(pane), "")
        return subprocess.CompletedProcess(cmd, 0, json.dumps(receipt), "")

    monkeypatch.setattr(launcher, "run", fake_run)
    monkeypatch.setattr(launcher, "launcher", lambda: "agents")
    monkeypatch.setattr(launcher, "await_ready", lambda *_a, **_k: True)
    monkeypatch.setattr(launcher, "verify_unit_preflight", lambda *a, **k: {})
    unit = launcher.LaunchRequest(name="oc", vendor="opencode", worktree="/tmp/wt", effort="high")
    with pytest.raises(SystemExit, match="already holds staged input"):
        launcher.launch(unit)
    assert typed == []


def _preflight_stubs(launcher: ModuleType, monkeypatch: pytest.MonkeyPatch) -> list[str]:
    closed: list[str] = []
    monkeypatch.setattr(
        launcher,
        "agent_row",
        lambda unit, agents=None: {
            "pane_id": "pane-1",
            "cwd": "/tmp/wt",
            "workspace_id": "w1",
            "interactive_ready": True,
            "agent": "claude",
        },
    )
    monkeypatch.setattr(launcher, "workspace_id_for_name", lambda name: None)
    monkeypatch.setattr(launcher, "verify_unit_account", lambda *a, **k: (None, "none"))
    monkeypatch.setattr(
        launcher, "close_run_session", lambda unit: closed.append(unit.tab_id or "")
    )
    return closed


def _bypass_unit(launcher: ModuleType) -> Any:
    return launcher.LaunchRequest(
        name="reviewer",
        vendor="claude",
        worktree="/tmp/wt",
        permission="bypass",
        pane_id="pane-1",
        tab_id="tab-1",
    )


LAUNCH_ARGV_HEAD = [
    "agents",
    "--no-focus",
    "--current",
    "--task",
    "reviewer",
    "--cwd",
    "/tmp/wt",
]


def test_declared_bypass_missing_from_argv_is_a_named_stop(
    launcher: ModuleType, monkeypatch: pytest.MonkeyPatch
) -> None:
    closed = _preflight_stubs(launcher, monkeypatch)
    unit = _bypass_unit(launcher)
    argv = [*LAUNCH_ARGV_HEAD, "claude"]
    with pytest.raises(SystemExit) as exc_info:
        launcher.verify_unit_preflight(unit, "pane-1", ready=True, argv=argv)
    message = str(exc_info.value)
    assert "reviewer" in message
    assert "'bypass'" in message
    assert "'--permission-mode', 'bypassPermissions'" in message
    assert closed == ["tab-1"]


def test_receipt_records_resolved_posture_distinctly(
    launcher: ModuleType, monkeypatch: pytest.MonkeyPatch
) -> None:
    _preflight_stubs(launcher, monkeypatch)
    unit = _bypass_unit(launcher)
    argv = [*LAUNCH_ARGV_HEAD, "claude", "--permission-mode", "bypassPermissions"]
    receipt = launcher.verify_unit_preflight(unit, "pane-1", ready=True, argv=argv)
    assert receipt["permission"] == "bypass"
    assert receipt["permission_resolved"]["mode"] == "bypass"
    assert receipt["permission_resolved"]["tokens"] == [
        "--permission-mode",
        "bypassPermissions",
    ]
    assert receipt["permission_resolved"]["confirmed_from"] == "launch_argv"
    assert "permission" in receipt["requested_only"]
    assert "permission" not in receipt["confirmed_against_herdr"]


def test_no_argv_leaves_permission_unconfirmed(
    launcher: ModuleType, monkeypatch: pytest.MonkeyPatch
) -> None:
    _preflight_stubs(launcher, monkeypatch)
    unit = _bypass_unit(launcher)
    receipt = launcher.verify_unit_preflight(unit, "pane-1", ready=True)
    assert receipt["permission_resolved"]["confirmed_from"] is None
    assert "permission" in receipt["requested_only"]


def test_skill_no_longer_calls_permission_herdr_requested_only() -> None:
    skill = (
        REPO / "plugins" / "agent-launcher" / "skills" / "agent-launcher" / "SKILL.md"
    ).read_text(encoding="utf-8")
    assert "model and permission stay `requested_only`" not in skill
    assert "permission_resolved" in skill


def _plant_transcript(
    launcher: ModuleType,
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    worktree: str,
    *,
    label: str,
    mtime: float,
) -> Path:
    personal = tmp_path / "personal-projects"
    company = tmp_path / "company-projects"
    monkeypatch.setattr(launcher, "claude_transcript_roots", lambda: (personal, company))
    root = company if label == "company" else personal
    slug = str(launcher.claude_project_slug(worktree))
    path = root / slug / "session.jsonl"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text('{"type":"session"}\n', encoding="utf-8")
    os.utime(path, (mtime, mtime))
    return path


def _account_preflight_stubs(
    launcher: ModuleType, monkeypatch: pytest.MonkeyPatch, worktree: str
) -> None:
    monkeypatch.setattr(
        launcher,
        "agent_row",
        lambda unit, agents=None: {
            "pane_id": "pane-1",
            "cwd": worktree,
            "workspace_id": "w1",
            "interactive_ready": True,
            "agent": "claude",
        },
    )
    monkeypatch.setattr(launcher, "workspace_id_for_name", lambda name: None)
    monkeypatch.setattr(launcher, "close_run_session", lambda unit: None)


def _account_unit(launcher: ModuleType, worktree: str) -> Any:
    return launcher.LaunchRequest(
        name="acct",
        vendor="claude",
        account="company",
        worktree=worktree,
        pane_id="pane-1",
        tab_id="tab-1",
    )


def test_stale_transcript_does_not_confirm_a_silent_statusline(
    launcher: ModuleType, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    worktree = tmp_path / "wt"
    worktree.mkdir()
    since = time.time()
    _plant_transcript(
        launcher, monkeypatch, tmp_path, str(worktree), label="company", mtime=since - 60
    )
    monkeypatch.setattr(launcher, "pane_account_label", lambda pane_id: None)
    unit = _account_unit(launcher, str(worktree))
    assert launcher.observed_account(unit, "pane-1", 0, since=since) == (None, "none")
    confirmed, error = launcher.check_unit_account(unit, "pane-1", seconds=0, since=since)
    assert confirmed is False
    assert error is not None and "unverified" in error


def test_fresh_transcript_confirms_when_recency_is_provable(
    launcher: ModuleType, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    worktree = tmp_path / "wt"
    worktree.mkdir()
    since = time.time()
    _plant_transcript(
        launcher, monkeypatch, tmp_path, str(worktree), label="company", mtime=since + 5
    )
    monkeypatch.setattr(launcher, "pane_account_label", lambda pane_id: None)
    _account_preflight_stubs(launcher, monkeypatch, str(worktree))
    unit = _account_unit(launcher, str(worktree))
    assert launcher.observed_account(unit, "pane-1", 0, since=since) == ("company", "transcript")
    receipt = launcher.verify_unit_preflight(unit, "pane-1", ready=True, since=since)
    assert receipt["account_evidence"] == "transcript"
    assert "account" in receipt["confirmed_against_herdr"]


def test_transcript_written_during_the_create_still_confirms(
    launcher: ModuleType, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    worktree = tmp_path / "wt"
    worktree.mkdir()
    since = time.time()
    # The same-instant write the cmd_go account test produces: the wrapper plants the transcript
    # during the create, and filesystems quantise mtimes, so what lands can sit below the captured
    # launch instant. This file sits exactly on the slack boundary, where both a dropped slack and
    # a strict comparison fail while the shipped >= with one second of slack accepts it.
    _plant_transcript(
        launcher, monkeypatch, tmp_path, str(worktree), label="company", mtime=since - 1.0
    )
    monkeypatch.setattr(launcher, "pane_account_label", lambda pane_id: None)
    unit = _account_unit(launcher, str(worktree))
    assert launcher.observed_account(unit, "pane-1", 0, since=since) == ("company", "transcript")


def test_statusline_evidence_still_confirms_exactly_as_today(
    launcher: ModuleType, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    worktree = tmp_path / "wt"
    worktree.mkdir()
    # A contradicting transcript the statusline must outrank: a proof chain reordered to consult
    # transcripts first would mismatch this launch instead of confirming it.
    _plant_transcript(
        launcher, monkeypatch, tmp_path, str(worktree), label="personal", mtime=time.time()
    )
    monkeypatch.setattr(launcher, "pane_account_label", lambda pane_id: "company")
    _account_preflight_stubs(launcher, monkeypatch, str(worktree))
    unit = _account_unit(launcher, str(worktree))
    assert launcher.check_unit_account(unit, "pane-1", seconds=0) == (True, None)
    receipt = launcher.verify_unit_preflight(unit, "pane-1", ready=True)
    assert receipt["account_evidence"] == "statusline"


def test_omitted_since_keeps_the_existing_fallback(
    launcher: ModuleType, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    worktree = tmp_path / "wt"
    worktree.mkdir()
    # Deliberately old: with no floor the fallback behaves exactly as it did before the floor
    # existed. That is the compatibility decision, recorded here so it cannot be tightened by
    # accident.
    _plant_transcript(
        launcher, monkeypatch, tmp_path, str(worktree), label="company", mtime=time.time() - 500
    )
    monkeypatch.setattr(launcher, "pane_account_label", lambda pane_id: None)
    _account_preflight_stubs(launcher, monkeypatch, str(worktree))
    unit = _account_unit(launcher, str(worktree))
    assert launcher.observed_account(unit, "pane-1", 0) == ("company", "transcript")
    assert launcher.check_unit_account(unit, "pane-1", seconds=0) == (True, None)
    receipt = launcher.verify_unit_preflight(unit, "pane-1", ready=True)
    assert receipt["account_evidence"] == "transcript"


def test_launch_passes_a_recency_floor(
    launcher: ModuleType, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    worktree = tmp_path / "wt"
    worktree.mkdir()
    _plant_transcript(
        launcher, monkeypatch, tmp_path, str(worktree), label="company", mtime=time.time() - 3600
    )
    monkeypatch.setattr(launcher, "pane_account_label", lambda pane_id: None)
    sends: list[tuple[Any, ...]] = []
    receipt = {"tab_id": "w80:t9", "agent_name": "acct-2", "pane_id": "w80:p9", "reused": False}

    def fake_run(cmd: list[str], **_k: object) -> subprocess.CompletedProcess[str]:
        if cmd[:3] == ["herdr", "tab", "list"]:
            tabs = {"result": {"tabs": [{"tab_id": "w80:t1", "label": "old"}]}}
            return subprocess.CompletedProcess(cmd, 0, json.dumps(tabs), "")
        if cmd[:3] == ["herdr", "pane", "current"]:
            pane = {"result": {"pane": {"workspace_id": "w80"}}}
            return subprocess.CompletedProcess(cmd, 0, json.dumps(pane), "")
        return subprocess.CompletedProcess(cmd, 0, json.dumps(receipt), "")

    monkeypatch.setattr(launcher, "run", fake_run)
    monkeypatch.setattr(launcher, "launcher", lambda: "agents")
    monkeypatch.setattr(launcher, "await_ready", lambda *_a, **_k: True)
    monkeypatch.setattr(launcher, "send", lambda *a, **k: sends.append(a))
    monkeypatch.setattr(
        launcher,
        "agent_row",
        lambda unit, agents=None: {
            "pane_id": "w80:p9",
            "cwd": str(worktree),
            "workspace_id": "w80",
            "interactive_ready": True,
            "agent": "claude",
        },
    )
    # Spend the account-settle window without wall-clock delay. time.time() stays real: the floor
    # under test is a wall-clock instant compared against the planted file's mtime.
    clock = [time.monotonic()]

    def fast_monotonic() -> float:
        clock[0] += 2.0
        return clock[0]

    monkeypatch.setattr(launcher.time, "monotonic", fast_monotonic)
    monkeypatch.setattr(launcher.time, "sleep", lambda *_a, **_k: None)
    unit = _account_unit(launcher, str(worktree))
    with pytest.raises(launcher.AccountMismatchError, match="account unverified"):
        launcher.launch(unit)
    assert sends == []


def test_account_mismatch_still_raises_unchanged(
    launcher: ModuleType, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    worktree = tmp_path / "wt"
    worktree.mkdir()
    monkeypatch.setattr(launcher, "pane_account_label", lambda pane_id: "personal")
    monkeypatch.setattr(launcher, "close_run_session", lambda unit: None)
    unit = _account_unit(launcher, str(worktree))
    with pytest.raises(launcher.AccountMismatchError) as exc_info:
        launcher.verify_unit_account(unit, "pane-1")
    assert str(exc_info.value) == (
        "acct: account mismatch: worker is on the personal account when company was required"
    )


def test_startup_timeout_is_a_result_not_a_crash(launcher: ModuleType) -> None:
    result = launcher.run(["sleep", "2"], check=False, timeout=0.1)
    assert result.returncode == 124
    assert result.stderr == "timed out"


def test_prompt_delivery_failure_records_undelivered(
    launcher: ModuleType, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    wrapper = tmp_path / "agents"
    receipt = {
        "tab_id": "tab-1",
        "agent_name": "reviewer-2",
        "pane_id": "pane-1",
        "reused": False,
    }
    wrapper.write_text("#!/bin/sh\ncat <<'EOF'\n" + json.dumps(receipt) + "\nEOF\n")
    wrapper.chmod(0o755)
    monkeypatch.setenv("PATH", str(tmp_path), prepend=os.pathsep)
    monkeypatch.setattr(launcher, "await_ready", lambda *_a, **_k: True)
    monkeypatch.setattr(launcher, "verify_unit_preflight", lambda *a, **k: {})
    monkeypatch.setattr(launcher, "send", lambda *a, **k: None)
    monkeypatch.setattr(launcher, "took_the_task", lambda *_a, **_k: False)
    monkeypatch.setattr(launcher, "agent_row", lambda *_a, **_k: {"agent_status": "idle"})
    monkeypatch.setattr(launcher.time, "sleep", lambda *_a, **_k: None)
    unit = launcher.LaunchRequest(name="reviewer", vendor="codex", worktree=str(tmp_path))
    launcher.launch(unit)
    assert unit.status == launcher.PROMPT_UNDELIVERED
    assert launcher.DELIVERY_WARNING in unit.note
    assert unit.launch_receipt["prompt_delivered"] is False
    assert unit.launch_receipt["agent_name"] == "reviewer-2"
    assert unit.tab_id == "tab-1"


def test_close_without_receipt_tab_id_stops(launcher: ModuleType) -> None:
    unit = launcher.LaunchRequest(name="x", vendor="codex", tab_id="tab-1")
    with pytest.raises(SystemExit, match="ownership"):
        launcher.close_owned_session(unit, receipt={})


def test_close_mismatched_receipt_stops(
    launcher: ModuleType, monkeypatch: pytest.MonkeyPatch
) -> None:
    closed: list[str] = []

    def fake_run(cmd: list[str], **_k: object) -> subprocess.CompletedProcess[str]:
        closed.append(cmd[-1])
        return subprocess.CompletedProcess(cmd, 0, "", "")

    monkeypatch.setattr(launcher, "run", fake_run)
    unit = launcher.LaunchRequest(name="x", vendor="codex", tab_id="tab-1")
    with pytest.raises(SystemExit, match="does not match"):
        launcher.close_owned_session(unit, receipt={"tab_id": "tab-other", "owned": True})
    assert closed == []


def test_close_owned_session_closes_only_receipt_tab(
    launcher: ModuleType, monkeypatch: pytest.MonkeyPatch
) -> None:
    closed: list[list[str]] = []

    def fake_run(cmd: list[str], **_k: object) -> subprocess.CompletedProcess[str]:
        closed.append(cmd)
        return subprocess.CompletedProcess(cmd, 0, "", "")

    monkeypatch.setattr(launcher, "run", fake_run)
    unit = launcher.LaunchRequest(name="x", vendor="codex", tab_id="tab-owned")
    launcher.close_owned_session(unit, receipt={"tab_id": "tab-owned", "owned": True})
    assert closed == [["herdr", "tab", "close", "tab-owned"]]


def test_failing_tab_close_is_recorded_on_the_unit(
    launcher: ModuleType, monkeypatch: pytest.MonkeyPatch
) -> None:
    def fake_run(cmd: list[str], **_k: object) -> subprocess.CompletedProcess[str]:
        return subprocess.CompletedProcess(cmd, 1, "", "no such tab")

    monkeypatch.setattr(launcher, "run", fake_run)
    unit = launcher.LaunchRequest(name="x", vendor="codex", tab_id="tab-owned", owned=True)
    launcher.close_run_session(unit)
    assert "tab close failed" in unit.note
    assert "tab-owned" in unit.note
    assert "no such tab" in unit.note


def test_failing_tab_close_exits_nonzero_through_the_cli_variant(
    launcher: ModuleType, monkeypatch: pytest.MonkeyPatch
) -> None:
    def fake_run(cmd: list[str], **_k: object) -> subprocess.CompletedProcess[str]:
        return subprocess.CompletedProcess(cmd, 1, "", "no such tab")

    monkeypatch.setattr(launcher, "run", fake_run)
    unit = launcher.LaunchRequest(name="x", vendor="codex", tab_id="tab-owned")
    with pytest.raises(SystemExit, match="tab close failed"):
        launcher.close_owned_session(unit, receipt={"tab_id": "tab-owned", "owned": True})


def test_successful_close_adds_no_note(
    launcher: ModuleType, monkeypatch: pytest.MonkeyPatch
) -> None:
    closed: list[list[str]] = []

    def fake_run(cmd: list[str], **_k: object) -> subprocess.CompletedProcess[str]:
        closed.append(cmd)
        return subprocess.CompletedProcess(cmd, 0, "", "")

    monkeypatch.setattr(launcher, "run", fake_run)
    unit = launcher.LaunchRequest(name="x", vendor="codex", tab_id="tab-owned", owned=True)
    launcher.close_run_session(unit)
    assert closed == [["herdr", "tab", "close", "tab-owned"]]
    assert unit.note == ""


def test_unowned_session_closes_nothing_and_reports_nothing(
    launcher: ModuleType, monkeypatch: pytest.MonkeyPatch
) -> None:
    closed: list[list[str]] = []

    def fake_run(cmd: list[str], **_k: object) -> subprocess.CompletedProcess[str]:
        closed.append(cmd)
        return subprocess.CompletedProcess(cmd, 1, "", "no such tab")

    monkeypatch.setattr(launcher, "run", fake_run)
    unit = launcher.LaunchRequest(name="x", vendor="codex", tab_id="tab-old", owned=False)
    launcher.close_run_session(unit)
    assert closed == []
    assert unit.note == ""


def test_missing_receipt_path_names_the_path_and_the_recovery(launcher: ModuleType) -> None:
    with pytest.raises(SystemExit) as exc_info:
        launcher._load_receipt("/no/such/receipt.json")
    message = str(exc_info.value)
    assert "/no/such/receipt.json" in message
    assert "> receipt.json" in message


def test_missing_receipt_path_through_the_cli_exits_without_a_traceback() -> None:
    proc = subprocess.run(
        [sys.executable, str(LAUNCHER), "close", "--receipt-json", "/no/such/receipt.json"],
        check=False,
        capture_output=True,
        text=True,
    )
    assert proc.returncode != 0
    assert "Traceback" not in proc.stderr


def test_inline_malformed_json_keeps_its_existing_stop_shape(launcher: ModuleType) -> None:
    with pytest.raises(json.JSONDecodeError):
        launcher._load_receipt('{"a":')


def test_valid_receipt_file_is_unchanged(launcher: ModuleType, tmp_path: Path) -> None:
    receipt = {"tab_id": "t1", "owned": True}
    path = tmp_path / "receipt.json"
    path.write_text(json.dumps(receipt), encoding="utf-8")
    assert launcher._load_receipt(str(path)) == receipt


def test_valid_inline_json_is_unchanged(launcher: ModuleType) -> None:
    assert launcher._load_receipt('{"tab_id": "t1", "owned": true}') == {
        "tab_id": "t1",
        "owned": True,
    }


def test_non_object_json_keeps_its_message(launcher: ModuleType) -> None:
    with pytest.raises(SystemExit, match="must be a JSON object"):
        launcher._load_receipt("[1, 2]")


def test_confirm_preview_stops_on_cwd_mismatch(launcher: ModuleType) -> None:
    with pytest.raises(SystemExit, match="cwd"):
        launcher.confirm_preview(
            {"cwd": "/tmp/other", "herdr_workspace": "<current-terminal:w1>"},
            "/tmp/expected",
            "w1",
        )


def test_confirm_preview_stops_on_workspace_mismatch(launcher: ModuleType, tmp_path: Path) -> None:
    with pytest.raises(SystemExit, match="workspace"):
        launcher.confirm_preview(
            {"cwd": str(tmp_path), "herdr_workspace": "<current-terminal:w9>"},
            str(tmp_path),
            "w1",
        )


def test_herdr_readback_receipt_separates_confirmed_from_requested(
    launcher: ModuleType, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(
        launcher,
        "agent_row",
        lambda unit, agents=None: {
            "pane_id": "pane-1",
            "cwd": "/tmp/wt",
            "workspace_id": "w1",
            "interactive_ready": True,
            "agent": "codex",
        },
    )
    monkeypatch.setattr(launcher, "workspace_id_for_name", lambda name: "w1" if name else None)
    monkeypatch.setattr(launcher, "verify_unit_account", lambda *a, **k: (None, "none"))
    unit = launcher.LaunchRequest(
        name="reviewer",
        vendor="codex",
        worktree="/tmp/wt",
        workspace="review",
        model="gpt-5.4",
        effort="xhigh",
        pane_id="pane-1",
        tab_id="tab-1",
    )
    receipt = launcher.verify_unit_preflight(unit, "pane-1", ready=True)
    assert "pane" in receipt["confirmed_against_herdr"]
    assert "kind" in receipt["confirmed_against_herdr"]
    assert "working_directory" in receipt["confirmed_against_herdr"]
    assert "workspace" in receipt["confirmed_against_herdr"]
    assert "readiness" in receipt["confirmed_against_herdr"]
    assert "model" in receipt["requested_only"]
    assert "permission" in receipt["requested_only"]
    assert "permission" not in receipt["confirmed_against_herdr"]
    assert receipt["agent_name"] is None or "agent_name" in receipt
    assert receipt["permission"] == "auto"
    assert receipt["kind"] == "codex"
    assert receipt["verified"] is True


def test_herdr_cwd_mismatch_closes_owned_session(
    launcher: ModuleType, monkeypatch: pytest.MonkeyPatch
) -> None:
    closed: list[str] = []
    monkeypatch.setattr(
        launcher,
        "agent_row",
        lambda unit, agents=None: {
            "pane_id": "pane-1",
            "cwd": "/tmp/other",
            "interactive_ready": True,
            "agent": "codex",
        },
    )
    monkeypatch.setattr(
        launcher, "close_run_session", lambda unit: closed.append(unit.tab_id or "")
    )
    unit = launcher.LaunchRequest(
        name="reviewer", vendor="codex", worktree="/tmp/wt", pane_id="pane-1", tab_id="tab-1"
    )
    with pytest.raises(SystemExit, match="working directory"):
        launcher.verify_unit_preflight(unit, "pane-1", ready=True)
    assert closed == ["tab-1"]


def test_task_name_with_separator_is_refused_before_any_write(launcher: ModuleType) -> None:
    with pytest.raises(SystemExit, match="path separator"):
        launcher.assert_safe_path_component("../victim/CLAUDE", "task name")
    with pytest.raises(SystemExit, match="path separator"):
        launcher._request_from_args(
            type(
                "NS",
                (),
                {
                    "task": "feature/auth-review",
                    "cwd": "/tmp",
                    "vendor": "codex",
                    "prompt": "x",
                    "model": None,
                    "effort": None,
                    "account": None,
                    "permission": "auto",
                    "launch_arg": [],
                    "workspace": None,
                    "variant": None,
                },
            )()
        )


def test_pane_text_refuses_traversal_name(launcher: ModuleType, tmp_path: Path) -> None:
    unit = launcher.LaunchRequest(name="../victim", vendor="codex", worktree=str(tmp_path))
    long_text = "x" * (launcher.PANE_TYPING_LIMIT + 1)
    with pytest.raises(SystemExit, match="path"):
        launcher.pane_text(unit, long_text)


def test_preexisting_tab_is_not_owned(
    launcher: ModuleType, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Ownership is launcher-side: tab_id present in the pre-launch snapshot is not owned."""
    closed: list[list[str]] = []

    def fake_run(cmd: list[str], **_k: object) -> subprocess.CompletedProcess[str]:
        closed.append(cmd)
        return subprocess.CompletedProcess(cmd, 0, "", "")

    monkeypatch.setattr(launcher, "run", fake_run)
    preexisting = frozenset({"w80:t4", "w80:t1"})
    assert launcher.tab_was_created("w80:t4", preexisting) is False
    assert launcher.tab_was_created("w80:t9", preexisting) is True
    unit = launcher.LaunchRequest(name="u-777", vendor="codex", tab_id="w80:t4", owned=False)
    receipt = {"tab_id": "w80:t4", "owned": False}
    launcher.close_run_session(unit)
    assert closed == []
    with pytest.raises(SystemExit, match="existed before this launch"):
        launcher.close_owned_session(unit, receipt=receipt)
    assert closed == []


def test_cwd_mismatch_on_preexisting_tab_does_not_close(
    launcher: ModuleType, monkeypatch: pytest.MonkeyPatch
) -> None:
    closed: list[list[str]] = []

    def fake_run(cmd: list[str], **_k: object) -> subprocess.CompletedProcess[str]:
        if cmd[:3] == ["herdr", "tab", "close"]:
            closed.append(cmd)
        return subprocess.CompletedProcess(cmd, 0, "", "")

    monkeypatch.setattr(launcher, "run", fake_run)
    monkeypatch.setattr(
        launcher,
        "agent_row",
        lambda unit, agents=None: {
            "pane_id": "pane-1",
            "cwd": "/tmp/other",
            "interactive_ready": True,
            "agent": "codex",
        },
    )
    unit = launcher.LaunchRequest(
        name="reviewer",
        vendor="codex",
        worktree="/tmp/wt",
        pane_id="pane-1",
        tab_id="tab-1",
        owned=False,
        launch_receipt={"tab_id": "tab-1", "owned": False},
    )
    with pytest.raises(SystemExit, match="working directory"):
        launcher.verify_unit_preflight(unit, "pane-1", ready=True)
    assert closed == []


def test_ownership_is_tab_id_not_in_prelaunch_snapshot(
    launcher: ModuleType, monkeypatch: pytest.MonkeyPatch
) -> None:
    listed: list[str] = []

    def fake_run(cmd: list[str], **_k: object) -> subprocess.CompletedProcess[str]:
        listed.append(" ".join(cmd))
        if cmd[:3] == ["herdr", "tab", "list"]:
            return subprocess.CompletedProcess(
                cmd,
                0,
                json.dumps(
                    {
                        "result": {
                            "tabs": [
                                {"tab_id": "w80:t1", "label": "old"},
                                {"tab_id": "w80:t4", "label": "u-777"},
                            ]
                        }
                    }
                ),
                "",
            )
        if cmd[:3] == ["herdr", "pane", "current"]:
            return subprocess.CompletedProcess(
                cmd,
                0,
                json.dumps({"result": {"pane": {"workspace_id": "w80"}}}),
                "",
            )
        return subprocess.CompletedProcess(
            cmd,
            0,
            json.dumps(
                {
                    "tab_id": "w80:t9",
                    "agent_name": "smoke",
                    "pane_id": "w80:p9",
                    "reused": True,
                }
            ),
            "",
        )

    monkeypatch.setattr(launcher, "run", fake_run)
    # launch() resolves the wrapper in agent_argv before run(); stubbing run is not enough.
    monkeypatch.setattr(launcher, "launcher", lambda: "agents")
    monkeypatch.setattr(launcher, "await_ready", lambda *_a, **_k: True)
    monkeypatch.setattr(
        launcher,
        "verify_unit_preflight",
        lambda *a, **k: (_ for _ in ()).throw(SystemExit("stop after identity")),
    )
    unit = launcher.LaunchRequest(name="smoke", vendor="codex", worktree="/tmp/wt")
    with pytest.raises(SystemExit, match="stop after identity"):
        launcher.launch(unit)
    assert unit.tab_id == "w80:t9"
    assert unit.owned is True
    assert unit.launch_receipt["owned"] is True
    assert unit.launch_receipt["reused"] is True
    assert any("tab list" in c for c in listed)


def test_kind_mismatch_stops_before_prompt(
    launcher: ModuleType, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(
        launcher,
        "agent_row",
        lambda unit, agents=None: {
            "pane_id": "pane-1",
            "cwd": "/tmp/wt",
            "interactive_ready": True,
            "agent": "claude",
        },
    )
    unit = launcher.LaunchRequest(
        name="reviewer", vendor="codex", worktree="/tmp/wt", pane_id="pane-1", tab_id="tab-1"
    )
    with pytest.raises(SystemExit, match="herdr reports agent 'claude'"):
        launcher.verify_unit_preflight(unit, "pane-1", ready=True)


def test_failed_launch_persists_tab_id_for_close(
    launcher: ModuleType, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    wrapper = tmp_path / "agents"
    wrapper.write_text(
        "#!/bin/sh\n"
        + "cat <<'EOF'\n"
        + json.dumps(
            {
                "tab_id": "tab-recover",
                "agent_name": "reviewer-2",
                "pane_id": "pane-1",
                "reused": False,
            }
        )
        + "\nEOF\n"
    )
    wrapper.chmod(0o755)
    monkeypatch.setenv("PATH", str(tmp_path), prepend=os.pathsep)
    monkeypatch.setattr(launcher, "await_ready", lambda *_a, **_k: True)
    monkeypatch.setattr(
        launcher,
        "verify_unit_preflight",
        lambda *a, **k: (_ for _ in ()).throw(SystemExit("preflight failed")),
    )
    unit = launcher.LaunchRequest(name="reviewer", vendor="codex", worktree=str(tmp_path))
    with pytest.raises(SystemExit, match="preflight failed"):
        launcher.launch(unit)
    assert unit.tab_id == "tab-recover"
    assert unit.launch_receipt["tab_id"] == "tab-recover"
    assert unit.launch_receipt["agent_name"] == "reviewer-2"
    assert unit.launch_receipt["reused"] is False


def test_cli_undelivered_prompt_exits_nonzero(
    launcher: ModuleType, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    wrapper = tmp_path / "agents"
    wrapper.write_text("#!/bin/sh\necho dry\n")
    wrapper.chmod(0o755)
    monkeypatch.setenv("PATH", str(tmp_path), prepend=os.pathsep)
    unit = launcher.LaunchRequest(
        name="reviewer",
        vendor="codex",
        worktree=str(tmp_path),
        status=launcher.PROMPT_UNDELIVERED,
        launch_receipt={"tab_id": "t", "prompt_delivered": False, "reused": False},
    )
    monkeypatch.setattr(launcher, "preview_argv", lambda *_a, **_k: ["agents", "--dry-run"])
    monkeypatch.setattr(
        launcher,
        "run",
        lambda *_a, **_k: subprocess.CompletedProcess(["agents"], 0, "cwd=x\n", ""),
    )
    monkeypatch.setattr(
        launcher,
        "parse_dry_run",
        lambda _s: {"cwd": str(tmp_path), "herdr_workspace": "<current-terminal:w1>"},
    )
    monkeypatch.setattr(launcher, "confirm_preview", lambda *_a, **_k: None)
    monkeypatch.setattr(launcher, "current_herdr_workspace_id", lambda: "w1")
    monkeypatch.setattr(launcher, "launch", lambda *_a, **_k: None)
    monkeypatch.setattr(
        launcher,
        "_request_from_args",
        lambda _args: unit,
    )
    rc = launcher.cli_main(
        [
            "launch",
            "--vendor",
            "codex",
            "--task",
            "reviewer",
            "--cwd",
            str(tmp_path),
        ]
    )
    assert rc == 1


def test_orchestrate_declares_agent_launcher_dependency_and_breaking_version() -> None:
    plugin = json.loads(
        (REPO / "plugins" / "orchestrate" / ".claude-plugin" / "plugin.json").read_text()
    )
    marketplace = json.loads((REPO / ".claude-plugin" / "marketplace.json").read_text())
    entry = next(p for p in marketplace["plugins"] if p["name"] == "orchestrate")
    assert plugin["version"] >= "3.0.0"
    assert entry["version"] == plugin["version"]
    # The loader requires an array; the object form made the plugin unloadable (#871).
    declared = plugin["dependencies"]
    assert isinstance(declared, list), (
        f"dependencies must be an array, got {type(declared).__name__}"
    )
    floors = {entry["name"]: entry.get("version") for entry in declared if isinstance(entry, dict)}
    assert floors.get("agent-launcher") == ">=1.1.0", declared


def test_skill_cleanup_example_redirects_receipt() -> None:
    skill = (
        REPO / "plugins" / "agent-launcher" / "skills" / "agent-launcher" / "SKILL.md"
    ).read_text(encoding="utf-8")
    assert "> receipt.json" in skill
    assert "close --receipt-json receipt.json" in skill
    assert "close --tab-id <tab_id> --receipt-json <receipt.json>" not in skill
    assert "owned" in skill
    assert "workspace" in skill.lower()
    assert "tab set snapshotted immediately before" in skill or "pre-launch" in skill


def test_skill_declares_herdr_dependency_and_no_duplicate_herdr_skill() -> None:
    skill = (
        REPO / "plugins" / "agent-launcher" / "skills" / "agent-launcher" / "SKILL.md"
    ).read_text(encoding="utf-8")
    assert "canonical `herdr` skill" in skill
    assert "does not ship a copy" in skill
    herdr_skill = REPO / "plugins" / "agent-launcher" / "skills" / "herdr"
    assert not herdr_skill.exists()


SKILL_MD = REPO / "plugins" / "agent-launcher" / "skills" / "agent-launcher" / "SKILL.md"
LAUNCHER_README = REPO / "plugins" / "agent-launcher" / "README.md"
BINARY_AUTHORITY_HEADING = "## The binary is the authority"
PREFLIGHT_HEADING = "## The only real preflight is a bounded live launch with a read-back"
ORDERING_HEADING = "## Ordering — the most common mistake"
CREDENTIAL_WORDS = ("key", "token", "secret", "password", "credential")
ALLOWLIST_ENTRIES = (
    "model",
    "reasoning effort",
    "permission posture",
    "account or route",
    "working directory",
    "workspace",
)


def _skill_section(skill: str, heading: str, stop: str) -> str:
    start = skill.index(heading)
    end = skill.index(stop)
    assert start < end
    return skill[start:end]


def _code_fences(text: str) -> list[str]:
    return re.findall(r"```[^\n]*\n(.*?)```", text, flags=re.DOTALL)


def _environment_dump_violations(text: str) -> list[str]:
    violations: list[str] = []
    for pattern in (r"\benv\b", r"\bprintenv\b", r"os\.environ", r"\bdiff\b[^\n]*\benv"):
        violations.extend(re.findall(pattern, text))
    return violations


def _value_persist_violations(text: str) -> list[str]:
    violations: list[str] = []
    for pattern in (r"\bsha256\w*", r"\bmd5\w*", r"\bbase64\b", r"cut -c", r"head -c"):
        violations.extend(re.findall(pattern, text))
    for line in text.splitlines():
        if ">" in line and any(word in line.lower() for word in CREDENTIAL_WORDS):
            violations.append(line)
    return violations


def _downstream_redaction_violations(text: str) -> list[str]:
    violations: list[str] = []
    for line in text.splitlines():
        segments = line.split("|")
        if len(segments) > 1 and any(
            re.search(r"\b(sed|awk|grep|tr)\b", segment) for segment in segments[1:]
        ):
            violations.append(line)
    return violations


def _guidance_fences() -> list[str]:
    skill = SKILL_MD.read_text(encoding="utf-8")
    guidance = _skill_section(skill, BINARY_AUTHORITY_HEADING, ORDERING_HEADING)
    readme = LAUNCHER_README.read_text(encoding="utf-8")
    return _code_fences(guidance) + _code_fences(readme)


def test_dry_run_guidance_names_what_it_does_not_validate() -> None:
    skill = SKILL_MD.read_text(encoding="utf-8")
    section = _skill_section(skill, BINARY_AUTHORITY_HEADING, PREFLIGHT_HEADING)
    assert "does not validate the model" in section
    assert "reasoning effort" in section
    assert "account" in section


def test_dry_run_is_not_described_as_sufficient_preflight() -> None:
    skill = SKILL_MD.read_text(encoding="utf-8")
    assert "Use it before every creation command." not in skill
    assert PREFLIGHT_HEADING in skill


def test_readme_and_skill_agree_on_dry_run() -> None:
    skill = SKILL_MD.read_text(encoding="utf-8").lower()
    readme = LAUNCHER_README.read_text(encoding="utf-8").lower()
    for surface in (skill, readme):
        assert "does not confirm model, effort, or account" in surface


def test_guidance_names_an_allowlist_with_no_credential_entry() -> None:
    skill = SKILL_MD.read_text(encoding="utf-8")
    section = _skill_section(skill, PREFLIGHT_HEADING, ORDERING_HEADING)
    marker = "allowlist of launch arguments when reading a session back:"
    start = section.index(marker) + len(marker)
    entries = section[start : section.index("Never inspect argv wholesale", start)]
    for entry in ALLOWLIST_ENTRIES:
        assert entry in entries
    for word in CREDENTIAL_WORDS:
        assert word not in entries


def test_guidance_states_the_ordering_rule() -> None:
    skill = SKILL_MD.read_text(encoding="utf-8")
    section = _skill_section(skill, PREFLIGHT_HEADING, ORDERING_HEADING)
    identify = section.index("Identify the selected client auth mechanism")
    oauth = section.index("For an OAuth session")
    declared = section.index("Only when a declared run contract")
    assert identify < oauth < declared


def test_oauth_path_is_the_default_and_touches_no_environment() -> None:
    skill = SKILL_MD.read_text(encoding="utf-8")
    section = _skill_section(skill, PREFLIGHT_HEADING, ORDERING_HEADING)
    start = section.index("For an OAuth session")
    end = section.index("Only when a declared run contract")
    assert start < end
    passage = section[start:end]
    assert "documented default" in passage
    for pattern in (r"\benv\b", r"\bprintenv\b", r"os\.environ", r"\$[A-Z][A-Z0-9_]*"):
        assert re.search(pattern, passage) is None


def test_environment_access_is_gated_on_a_declared_contract() -> None:
    skill = SKILL_MD.read_text(encoding="utf-8")
    dry_run = _skill_section(skill, BINARY_AUTHORITY_HEADING, PREFLIGHT_HEADING)
    preflight = _skill_section(skill, PREFLIGHT_HEADING, ORDERING_HEADING)
    assert "environment" not in dry_run
    assert "declared run contract" in preflight


def test_environment_check_asserts_presence_of_a_name_only() -> None:
    skill = SKILL_MD.read_text(encoding="utf-8")
    preflight = _skill_section(skill, PREFLIGHT_HEADING, ORDERING_HEADING)
    assert "presence of the required variable name" in preflight
    assert "never its value" in preflight
    for fence in _code_fences(preflight):
        assert "==" not in fence and "!=" not in fence
        assert "echo $" not in fence


def test_no_specific_credential_variable_is_named() -> None:
    skill = SKILL_MD.read_text(encoding="utf-8")
    readme = LAUNCHER_README.read_text(encoding="utf-8")
    pattern = r"[A-Z][A-Z0-9_]{3,}_(KEY|TOKEN|SECRET|PASSWORD)"
    assert re.search(pattern, skill) is None
    assert re.search(pattern, readme) is None


def test_no_example_dumps_diffs_or_serialises_an_environment() -> None:
    for fence in _guidance_fences():
        assert _environment_dump_violations(fence) == []


def test_no_example_hashes_truncates_or_persists_a_value() -> None:
    for fence in _guidance_fences():
        assert _value_persist_violations(fence) == []


def test_redaction_appears_inside_the_producing_command() -> None:
    skill = SKILL_MD.read_text(encoding="utf-8")
    preflight = _skill_section(skill, PREFLIGHT_HEADING, ORDERING_HEADING)
    assert "Redact inside the producing command" in preflight
    for fence in _guidance_fences():
        assert _downstream_redaction_violations(fence) == []


def test_no_credential_shaped_literal_appears() -> None:
    for surface in (
        SKILL_MD.read_text(encoding="utf-8"),
        LAUNCHER_README.read_text(encoding="utf-8"),
    ):
        for run in re.findall(r"[A-Za-z0-9_-]{20,}", surface):
            uppercase = sum(1 for ch in run if ch.isupper())
            assert uppercase < 3, f"credential-shaped literal {run!r}"


def test_environment_dump_example_would_fail_its_guard() -> None:
    fixture = "some-command && printenv"
    assert _environment_dump_violations(fixture) != []


def test_hashing_example_would_fail_its_guard() -> None:
    fixture = "sha256sum ./receipt.json"
    assert _value_persist_violations(fixture) != []


def test_downstream_only_redaction_would_fail_its_guard() -> None:
    fixture = "launch | sed 's/.*/REDACTED/'"
    assert _downstream_redaction_violations(fixture) != []
