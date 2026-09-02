"""Contract tests for the portable agent-launcher plugin (#777)."""

from __future__ import annotations

import hashlib
import importlib.util
import inspect
import json
import os
import re
import shlex
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


def test_orchestrate_sorts_launcher_cache_versions_numerically() -> None:
    orch = _load(ORCHESTRATE, "_orchestrate_version_sort_proof")
    older = Path("/cache/agent-launcher/1.9.0/skills/agent-launcher/scripts/launcher.py")
    newer = Path("/cache/agent-launcher/1.10.0/skills/agent-launcher/scripts/launcher.py")
    assert orch._launcher_cache_version(newer) > orch._launcher_cache_version(older)


def test_orchestrate_rejects_a_launcher_below_its_declared_floor(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    orch = _load(ORCHESTRATE, "_orchestrate_version_floor_proof")
    declared_manifest = tmp_path / "orchestrate-plugin.json"
    declared_manifest.write_text(
        json.dumps(
            {
                "dependencies": [
                    {"name": "agent-launcher", "version": ">=9.8.7"},
                ]
            }
        ),
        encoding="utf-8",
    )
    assert orch._declared_agent_launcher_floor(declared_manifest) == (9, 8, 7)

    root = tmp_path / "agent-launcher" / "1.1.9"
    script = root / "skills" / "agent-launcher" / "scripts" / "launcher.py"
    script.parent.mkdir(parents=True)
    script.write_text("# old launcher\n", encoding="utf-8")
    manifest = root / ".claude-plugin" / "plugin.json"
    manifest.parent.mkdir(parents=True)
    manifest.write_text('{"version":"1.1.9"}', encoding="utf-8")
    monkeypatch.setattr(orch, "_declared_agent_launcher_floor", lambda: (9, 8, 7))
    with pytest.raises(SystemExit, match=r"requires >=9\.8\.7"):
        orch._validated_agent_launcher(script)


def test_ingested_launcher_resolves_composer_from_its_own_compile_path() -> None:
    """ARCH-12: the caller's compile filename is the loader's only authority for where the
    sibling composer.py lives. A placeholder produces the named stop naming the wrong
    directory; the real path loads the parser. Replaces the source-grep assertion."""
    source = LAUNCHER.read_text(encoding="utf-8")
    with pytest.raises(SystemExit) as exc_info:
        _exec_launcher_source(source, "wrong-dir/launcher.py")
    message = str(exc_info.value)
    assert "cannot load agent-launcher composer parser" in message
    assert "file is missing" in message
    assert "wrong-dir" in message
    namespace = _exec_launcher_source(source, str(LAUNCHER))
    assert namespace["COMPOSER_GLYPH_BY_VENDOR"]["claude"] == "❯"


def _exec_launcher_source(source: str, compile_filename: str) -> dict[str, Any]:
    """Exec launcher.py the way Orchestrate ingests it, into a sys.modules-registered module
    namespace whose dataclasses can resolve their module, and clean the registration up."""
    probe = ModuleType("_agent_launcher_compile_probe")
    sys.modules["_agent_launcher_compile_probe"] = probe
    try:
        exec(compile(source, compile_filename, "exec"), probe.__dict__)
    finally:
        sys.modules.pop("_agent_launcher_compile_probe", None)
    return probe.__dict__


def _composer_module_name_probe() -> str:
    """The composer module name one fresh process chose for this launcher's parser."""
    code = (
        "import importlib.util, sys\n"
        "spec = importlib.util.spec_from_file_location('probe_launcher', sys.argv[1])\n"
        "module = importlib.util.module_from_spec(spec)\n"
        "sys.modules['probe_launcher'] = module\n"
        "spec.loader.exec_module(module)\n"
        "print([n for n in sys.modules if n.startswith('_agent_launcher_composer')][0])\n"
    )
    proc = subprocess.run(
        [sys.executable, "-c", code, str(LAUNCHER)],
        capture_output=True,
        text=True,
        check=True,
    )
    return proc.stdout.strip()


def test_composer_module_name_is_a_stable_digest_of_the_resolved_path() -> None:
    """ARCH-09: the synthetic module name is the documented digest form of the resolved
    composer path -- identical in every process, where abs(hash(path)) was randomised per
    process. The digest assertion is the deterministic kill; the two-process equality is
    the same guarantee observed across a process boundary."""
    composer_path = (LAUNCHER.parent / "composer.py").resolve()
    expected = (
        "_agent_launcher_composer_" + hashlib.sha256(str(composer_path).encode()).hexdigest()[:16]
    )
    first = _composer_module_name_probe()
    second = _composer_module_name_probe()
    assert first == expected
    assert first == second


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


def test_pane_read_and_transcript_slack_bounds_are_pinned(launcher: ModuleType) -> None:
    assert 0 < launcher.PANE_INPUT_READ_SECONDS <= 10
    assert 0 <= launcher.TRANSCRIPT_MTIME_SLACK_SECONDS <= 2


def test_create_timeout_reconciles_one_new_target_workspace_tab(
    launcher: ModuleType, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(launcher, "list_tab_ids", lambda _workspace=None: frozenset({"w1:t-new"}))
    unit = launcher.LaunchRequest(name="timed", vendor="codex")
    detail = launcher._record_create_timeout(
        unit,
        preexisting=frozenset(),
        workspace_id="w1",
    )
    assert "w1:t-new" in detail
    assert unit.tab_id == "w1:t-new"
    assert unit.launch_receipt["create_timeout_new_tabs"] == ["w1:t-new"]
    assert unit.launch_receipt["owned"] is True


def test_genuine_wrapper_exit_124_preserves_its_receipt(
    launcher: ModuleType, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    receipt = {
        "tab_id": "tab-124",
        "agent_name": "worker-124",
        "pane_id": "pane-124",
        "reused": False,
    }
    wrapper = tmp_path / "agents"
    wrapper.write_text("#!/bin/sh\nprintf '%s\\n' '" + json.dumps(receipt) + "'\nexit 124\n")
    wrapper.chmod(0o755)
    monkeypatch.setenv("PATH", str(tmp_path), prepend=os.pathsep)
    unit = launcher.LaunchRequest(name="worker", vendor="codex", worktree=str(tmp_path))
    with pytest.raises(SystemExit, match=r"command failed \(124\)"):
        launcher.launch(unit)
    assert unit.tab_id == "tab-124"
    assert unit.launch_receipt["agent_name"] == "worker-124"


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


def test_ownership_snapshot_uses_the_unit_target_workspace(
    launcher: ModuleType, monkeypatch: pytest.MonkeyPatch
) -> None:
    listed: list[str | None] = []
    receipt = {
        "tab_id": "w9:t-new",
        "agent_name": "reviewer-2",
        "pane_id": "w9:p1",
        "reused": True,
    }
    monkeypatch.setattr(launcher, "workspace_id_for_name", lambda name: "w9")

    def list_target_tabs(workspace: str | None = None) -> frozenset[str]:
        listed.append(workspace)
        return frozenset({"w9:t-old"})

    monkeypatch.setattr(launcher, "list_tab_ids", list_target_tabs)
    monkeypatch.setattr(
        launcher,
        "run",
        lambda cmd, **kwargs: subprocess.CompletedProcess(cmd, 0, json.dumps(receipt), ""),
    )
    monkeypatch.setattr(launcher, "launcher", lambda: "agents")
    monkeypatch.setattr(launcher, "await_ready", lambda *_a, **_k: True)
    monkeypatch.setattr(
        launcher,
        "verify_unit_preflight",
        lambda *a, **k: (_ for _ in ()).throw(SystemExit("stop after snapshot")),
    )
    unit = launcher.LaunchRequest(
        name="reviewer", vendor="codex", workspace="target", worktree="/tmp/wt"
    )
    with pytest.raises(SystemExit, match="stop after snapshot"):
        launcher.launch(unit)
    assert listed == ["w9"]
    assert unit.owned is True


CODEX_PLACEHOLDER = "\x1b[38;2;153;153;153m› Ask Codex to do anything\x1b[0m"
STAGED_SLASH_COMMAND = "/saga:doc-review docs/plans/x.md"
CAPTURED_COMPOSERS = json.loads(
    (Path(__file__).parent / "fixtures" / "composer-panes.json").read_text(encoding="utf-8")
)
# The parser module loaded for its private glyph rosters only; every state assertion goes
# through the launcher fixture so class identity never crosses module boundaries.
COMPOSER_MODULE = _load(
    REPO / "plugins" / "agent-launcher" / "skills" / "agent-launcher" / "scripts" / "composer.py",
    "_agent_launcher_contract_composer",
)
# Full `herdr pane read --source visible --format ansi` dumps of two idle Claude sessions in
# workspace wEV (Herdr 0.8.2): the marker row sits between two horizontal-rule rows with three
# two-space-indented status rows below the lower rule. Captured 2026-09-02 from wEV:pG and
# wEV:pQ; the plan's 2026-09-01 captures came from wEV:pM and wEV:p6, which no longer exist.
LIVE_CLAUDE_IDLE_KEYS = (
    "claude_live_idle_2026-09-02_herdr0.8.2_wEV-pG",
    "claude_live_idle_2026-09-02_herdr0.8.2_wEV-pQ",
)
# The complete border rosters as the test's own pinned expectation: the parametrised cases
# must survive a shrunk roster, so they cannot be derived from the module under mutation.
LEADING_BORDER_ROSTER = "│┃┆┇┊┋╎╏▏▎▍▌▋▊▉█╭╰┌└"
TRAILING_BORDER_ROSTER = "│┃┆┇┊┋╎╏▏▎▍▌▋▊▉█╮╯┐┘"


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
    vendor: str = "claude",
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
    # verify_unit_preflight is deliberately NOT stubbed: it rebuilds unit.launch_receipt, and a
    # stub that skips the rebuild hid the rebuild discarding the guard's keys. Its own
    # collaborators (the herdr row read) are the seam; the function under guard must be real.
    monkeypatch.setattr(
        launcher,
        "agent_row",
        lambda unit, agents=None: {
            "pane_id": "w80:p9",
            "cwd": "/tmp/wt",
            "workspace_id": "w80",
            "interactive_ready": True,
            "agent": vendor,
        },
    )
    monkeypatch.setattr(launcher, "send", lambda *a, **k: sends.append(a))
    monkeypatch.setattr(launcher, "took_the_task", lambda *_a, **_k: True)
    unit = launcher.LaunchRequest(name="reviewer", vendor=vendor, worktree="/tmp/wt")
    return unit, recorded, sends


def test_a_closed_placeholder_reads_unreadable_not_empty(launcher: ModuleType) -> None:
    """A line fully styled with its span closing at end of line is byte-identical between a
    vendor placeholder and a draft, so it must never be claimed empty: the honest answer is
    unreadable, and the guard takes the unreadable branch rather than prompting on a claim."""
    captured = CAPTURED_COMPOSERS["codex_closed_placeholder"]
    assert launcher.composer_staged_text(captured, vendor="codex") is None


def test_composer_typed_text_is_staged(launcher: ModuleType) -> None:
    staged = launcher.composer_staged_text(f"❯ {STAGED_SLASH_COMMAND}", vendor="claude")
    assert staged == STAGED_SLASH_COMMAND


def test_composer_glyph_table_covers_the_launcher_vendor_roster(launcher: ModuleType) -> None:
    assert launcher.COMPOSER_GLYPH_BY_VENDOR == {
        "claude": "❯",
        "codex": "›",
        "grok": "❯",
        "agy": ">",
        "qwen": ">",
        "muse": None,
        "opencode": None,
    }
    assert set(launcher.COMPOSER_GLYPH_BY_VENDOR) == set(launcher.VENDOR_FLAGS)


def test_documented_input_box_receipt_schema_is_complete(launcher: ModuleType) -> None:
    """API-06: the value set is derived from ComposerState, never a pinned copy of it."""
    skill = SKILL_MD.read_text(encoding="utf-8")
    readme = LAUNCHER_README.read_text(encoding="utf-8")
    values = [member.value for member in launcher.ComposerState]
    for surface in (skill, readme):
        assert "input_box" in surface
        assert "input_box_text_chars" in surface
        assert all(f"`{value}`" in surface for value in values)


def test_input_box_text_chars_is_the_visible_length_of_the_absorbed_block(
    launcher: ModuleType, monkeypatch: pytest.MonkeyPatch
) -> None:
    """DOCC-01 / SEC-08: the count is the visible length of the whole absorbed block, bound
    through the real guard so the documented number cannot drift from the recorded one."""
    row_one = "Stop before running U5 with Grok and Agy blocked. Direct host verification"
    row_two = "found both real executables. Use the live roster."
    unit, _recorded, _sends = _prepare_guard_launch(
        launcher,
        monkeypatch,
        pane_dump=f"❯ {row_one}\n  {row_two}",
        receipt_tab="w80:t1",
        existing_tabs=("w80:t1",),
    )
    with pytest.raises(launcher.StagedInputError, match="already holds staged input"):
        launcher.launch(unit)
    assert unit.launch_receipt["input_box_text_chars"] == len(row_one + row_two)


def test_input_box_text_chars_counts_a_styled_remainder_not_only_the_unstyled_part(
    launcher: ModuleType, monkeypatch: pytest.MonkeyPatch
) -> None:
    """DOCC-01: the count is the visible length, never the count of positively recognized
    (unstyled) characters -- only `ok` is unstyled here, but the whole draft is withheld."""
    unstyled = "ok"
    styled = "the remainder of the draft is client-styled"
    visible = f"{unstyled} {styled}"
    dump = f"❯ {unstyled} \x1b[2m{styled}\x1b[0m"
    unit, _recorded, _sends = _prepare_guard_launch(
        launcher,
        monkeypatch,
        pane_dump=dump,
        receipt_tab="w80:t1",
        existing_tabs=("w80:t1",),
    )
    with pytest.raises(launcher.StagedInputError, match="already holds staged input"):
        launcher.launch(unit)
    assert unit.launch_receipt["input_box_text_chars"] == len(visible)
    assert unit.launch_receipt["input_box_text_chars"] > len(unstyled)


def test_documents_state_the_count_definition_and_the_owned_session_absence() -> None:
    """DOCC-01, DOCC-10, DOCC-11, DOCC-02: both surfaces carry the KTD3 count definition,
    the owned-session absence, and the accepted indented-row asymmetry. Prose is compared
    with whitespace flattened so line wrapping cannot mask a claim."""
    for path in (SKILL_MD, LAUNCHER_README):
        flat = " ".join(path.read_text(encoding="utf-8").split())
        assert "visible length of what the parser absorbed" in flat, path
        assert "one character short at each wrapped-row boundary" in flat, path
        assert "lower bound" in flat, path
        assert "carries no `input_box` key" in flat, path
        assert "read as input" in flat, path


def test_documented_opencode_permission_flag_matches_the_runtime_table(
    launcher: ModuleType,
) -> None:
    skill = SKILL_MD.read_text(encoding="utf-8")
    sentence = next(line for line in skill.splitlines() if "OpenCode's `auto` posture" in line)
    assert launcher.VENDOR_PERMISSION["opencode"]["auto"] == ["--auto"]
    assert "`--auto`" in sentence
    assert "`--dangerously-skip-permissions`" not in sentence


@pytest.mark.parametrize(
    ("vendor", "glyph"),
    [("claude", "❯"), ("codex", "›"), ("grok", "❯"), ("agy", ">"), ("qwen", ">")],
)
def test_every_characterised_vendor_stops_on_its_own_draft(
    launcher: ModuleType, vendor: str, glyph: str
) -> None:
    result = launcher.inspect_composer(f"{glyph} destructive draft", vendor=vendor)
    assert result.state is launcher.ComposerState.STAGED
    assert result.text == "destructive draft"


def test_bordered_composer_matches_after_the_border(launcher: ModuleType) -> None:
    result = launcher.inspect_composer("│ ❯ destructive draft", vendor="grok")
    assert result.state is launcher.ComposerState.STAGED


@pytest.mark.parametrize("line", ["│ ❯   │", "\x1b[2m│ ❯   │\x1b[0m"])
def test_paired_box_borders_are_structure_not_a_phantom_draft(
    launcher: ModuleType, line: str
) -> None:
    result = launcher.inspect_composer(line, vendor="claude")
    assert result.state is launcher.ComposerState.EMPTY
    assert result.text == ""


def test_composer_absent_reads_as_unreadable(launcher: ModuleType) -> None:
    dump = "some session output\na second line of plain output\n"
    assert launcher.composer_staged_text(dump, vendor="claude") is None


def test_codex_placeholder_is_distinct_from_no_composer(launcher: ModuleType) -> None:
    placeholder = launcher.inspect_composer(CODEX_PLACEHOLDER, vendor="codex")
    absent = launcher.inspect_composer("ordinary output", vendor="codex")
    assert placeholder.state is launcher.ComposerState.UNCLASSIFIABLE
    assert absent.state is launcher.ComposerState.NOT_FOUND


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


@pytest.mark.parametrize("reset_code", ["00", "22", "0;10"])
def test_reset_codes_after_a_styled_marker_return_the_staged_text(
    launcher: ModuleType, reset_code: str
) -> None:
    """Every style-off shape the terminal defines ends the styled span at the marker."""
    line = f"\x1b[2m❯\x1b[{reset_code}m /deploy prod --force"
    assert launcher.composer_staged_text(line, vendor="claude") == "/deploy prod --force"


def test_marker_styled_and_never_reset_is_unclassifiable(launcher: ModuleType) -> None:
    """A fully styled draft and a fully styled placeholder are byte-indistinguishable."""
    result = launcher.inspect_composer("\x1b[2m❯ /deploy prod --force", vendor="claude")
    assert result.state is launcher.ComposerState.UNCLASSIFIABLE


def test_a_bare_marker_row_below_staged_text_is_a_decoy(launcher: ModuleType) -> None:
    assert launcher.composer_staged_text("❯ rm -rf /important\n> ", vendor="claude") == (
        "rm -rf /important"
    )


def test_a_quoted_row_below_staged_text_is_not_the_composer(launcher: ModuleType) -> None:
    dump = "❯ rm -rf /important\n> quoted line"
    assert launcher.composer_staged_text(dump, vendor="claude") == "rm -rf /important"


def test_an_empty_live_box_below_an_echo_reads_empty(launcher: ModuleType) -> None:
    """B4: the box is decided positionally -- it is the last classified block of the pane's own
    glyph. A reused pane whose live box is empty below an earlier echoed prompt reads empty and
    does not stop: the echo is scrollback, not the box, and a working launch must not become a
    refusal."""
    dump = "❯ earlier submitted prompt\npane output line\n❯ "
    assert launcher.composer_staged_text(dump, vendor="claude") == ""


def test_adjacent_staged_and_empty_marker_rows_are_ambiguous(launcher: ModuleType) -> None:
    """The viewport cannot distinguish a new empty box from a glyph-led final draft row."""
    result = launcher.inspect_composer("❯ draft text\n❯ ", vendor="claude")
    assert result.state is launcher.ComposerState.UNCLASSIFIABLE


def test_escapes_inside_staged_text_are_stripped(launcher: ModuleType) -> None:
    assert launcher.composer_staged_text("❯ deploy the \x1b[Kfleet", vendor="claude") == (
        "deploy the fleet"
    )


def test_colour_reset_does_not_clear_dim_intensity(launcher: ModuleType) -> None:
    """Select Graphic Rendition code 39 resets foreground only, never intensity."""
    line = "\x1b[2;31m❯\x1b[39m fully styled draft"
    assert launcher.inspect_composer(line, vendor="claude").state is (
        launcher.ComposerState.UNCLASSIFIABLE
    )


def test_intensity_reset_exposes_plain_staged_text(launcher: ModuleType) -> None:
    line = "\x1b[2;31m❯\x1b[39;22m plain draft"
    result = launcher.inspect_composer(line, vendor="claude")
    assert result.state is launcher.ComposerState.STAGED
    assert result.text == "plain draft"


# The marker scan: the box is the last block of the pane's own glyph. Lines carrying another glyph
# are content, and an inconclusive live block never lets an earlier scrollback block decide.
def test_menu_rows_below_the_box_are_content_not_the_box(launcher: ModuleType) -> None:
    dump = "❯ deploy now\n> Option A\n> Option B"
    assert launcher.composer_staged_text(dump, vendor="claude") == "deploy now"


def test_cross_glyph_rows_are_content_not_the_box(launcher: ModuleType) -> None:
    assert launcher.composer_staged_text("❯ draft text\n› ", vendor="claude") == "draft text"


def test_a_weak_marker_under_a_decorated_box_is_content(launcher: ModuleType) -> None:
    assert launcher.composer_staged_text("❯ \n> draft text", vendor="claude") == ""


def test_a_plain_marker_vendor_reads_its_own_box(launcher: ModuleType) -> None:
    assert launcher.composer_staged_text("> draft text", vendor="agy") == "draft text"


def test_a_blank_marker_row_with_continuation_rows_is_one_block(launcher: ModuleType) -> None:
    """A wrapped draft continues on unmarked rows; reading only the marker row reports the
    first wrapped line and drops the rest."""
    dump = "❯\n  wrapped draft continuation"
    assert launcher.composer_staged_text(dump, vendor="claude") == "wrapped draft continuation"


def test_blank_then_indented_text_is_ambiguous_not_affirmatively_empty(
    launcher: ModuleType,
) -> None:
    """Indentation cannot distinguish multiline input from vendor status chrome."""
    dump = "❯\n\n  wrapped draft or status footer"
    result = launcher.inspect_composer(dump, vendor="claude")
    assert result.state is launcher.ComposerState.UNCLASSIFIABLE


def test_styled_wrapped_row_stays_in_a_proven_staged_block(launcher: ModuleType) -> None:
    dump = "│ ❯ deploy the │\n│   \x1b[31mfleet\x1b[0m │"
    assert launcher.composer_staged_text(dump, vendor="claude") == "deploy thefleet"


def test_status_footer_after_blank_is_not_counted_as_staged_input(
    launcher: ModuleType,
) -> None:
    result = launcher.inspect_composer("› ninechars\n\n  model footer status", vendor="codex")
    assert result.state is launcher.ComposerState.STAGED
    assert result.text == "ninechars"


def test_unstyled_status_footer_after_empty_box_cannot_create_a_false_stop(
    launcher: ModuleType,
) -> None:
    result = launcher.inspect_composer("› \n\n  model footer status", vendor="codex")
    assert result.state is launcher.ComposerState.UNCLASSIFIABLE


@pytest.mark.parametrize(
    ("vendor", "dump"),
    [
        ("codex", "› \n\n  model footer status"),
        ("claude", "❯ here is the failing session:\n   ran the suite\n❯ "),
    ],
)
def test_ambiguous_composer_geometry_never_records_affirmative_empty(
    launcher: ModuleType,
    monkeypatch: pytest.MonkeyPatch,
    vendor: str,
    dump: str,
) -> None:
    """Ambiguous geometry never claims `empty` -- and the `len(sends) == 1` assertion below is
    the fail-open pin the accepted ambiguity trade requires: an inconclusive inspection still
    prompts, because a styled operator draft is byte-identical to a styled placeholder."""
    unit, _recorded, sends = _prepare_guard_launch(
        launcher,
        monkeypatch,
        pane_dump=dump,
        receipt_tab="w80:t1",
        existing_tabs=("w80:t1",),
        vendor=vendor,
    )
    launcher.launch(unit)
    assert len(sends) == 1
    assert unit.launch_receipt["input_box"] == "unclassifiable"
    assert "input box unclassifiable" in unit.note


def test_first_noncontinuation_terminates_the_composer_block(launcher: ModuleType) -> None:
    dump = "❯ draft\nordinary output\n  unrelated indented output"
    assert launcher.composer_staged_text(dump, vendor="claude") == "draft"


def test_menu_marker_terminates_the_composer_block(launcher: ModuleType) -> None:
    dump = "❯ draft\n  continuation\n> menu choice\n  menu detail"
    assert launcher.composer_staged_text(dump, vendor="claude") == "draftcontinuation"


def test_marker_must_be_the_first_printable_character_after_a_border(
    launcher: ModuleType,
) -> None:
    dump = "❯ \nordinary output\n  footer hint contains ❯ but is not a composer"
    result = launcher.inspect_composer(dump, vendor="claude")
    assert result.state is launcher.ComposerState.EMPTY


def test_glyph_led_last_visual_row_never_turns_a_staged_draft_into_empty(
    launcher: ModuleType,
) -> None:
    dump = "❯ here is the failing session:\n   ran the suite\n❯ "
    result = launcher.inspect_composer(dump, vendor="claude")
    assert result.state is launcher.ComposerState.UNCLASSIFIABLE


def test_a_draft_above_a_closed_placeholder_row_is_unclassifiable(launcher: ModuleType) -> None:
    """The live closed-span box wins positionally over an earlier scrollback draft."""
    dump = '❯ deploy the prod key now\n\x1b[2m❯ Try "fix it"\x1b[0m'
    result = launcher.inspect_composer(dump, vendor="claude")
    assert result.state is launcher.ComposerState.UNCLASSIFIABLE


@pytest.mark.parametrize("prefix", ["\x1b[0m", "\x1b[m", "\x1b[39m"])
def test_open_fully_styled_content_is_unclassifiable(launcher: ModuleType, prefix: str) -> None:
    result = launcher.inspect_composer(f"{prefix}\x1b[2m❯ /deploy prod", vendor="claude")
    assert result.state is launcher.ComposerState.UNCLASSIFIABLE


def test_closed_hint_then_reopened_span_is_unclassifiable(launcher: ModuleType) -> None:
    result = launcher.inspect_composer("\x1b[2m❯ \x1b[0m\x1b[2mdeploy prod", vendor="claude")
    assert result.state is launcher.ComposerState.UNCLASSIFIABLE


# --- The row rule: one classification per physical row (issue 907 U1, CORR-01/02/04/05/06, SEC-04,
# --- TEST-01/02/07/08/09, ARCH-03/04/17). Every clause below names the clause it binds.


def _claude_marker_bytes() -> str:
    """The fixture's own Claude marker row, the bytes a live pane emits for an empty box."""
    return CAPTURED_COMPOSERS["claude_echo_above_empty"].splitlines()[-1]


def test_unbordered_two_row_claude_draft_is_absorbed_whole(launcher: ModuleType) -> None:
    """CORR-04: an unbordered wrapped draft is not truncated to its marker row."""
    row_one = "Stop before running U5 with Grok and Agy blocked. Direct host verification"
    row_two = "found both real executables. Use the live roster."
    dump = f"❯ {row_one}\n  {row_two}"
    assert launcher.composer_staged_text(dump, vendor="claude") == row_one + row_two


def test_unbordered_three_row_codex_draft_is_absorbed_whole(launcher: ModuleType) -> None:
    """TEST-07: the three-row Codex draft returns all three rows, not 22 of 41 characters."""
    dump = "› first row of the draft\n  second row\n  third row"
    assert launcher.composer_staged_text(dump, vendor="codex") == (
        "first row of the draftsecond rowthird row"
    )


def test_an_empty_marker_with_an_indented_request_row_is_staged(launcher: ModuleType) -> None:
    """CORR-02: the marker alone on row 1 with the request indented on row 2 is a draft."""
    dump = _claude_marker_bytes() + "\n  the actual request text the operator staged"
    result = launcher.inspect_composer(dump, vendor="claude")
    assert result.state is launcher.ComposerState.STAGED
    assert result.text == "the actual request text the operator staged"
    assert len(result.text) == 43


def test_a_styled_at_mention_with_an_indented_unstyled_row_is_staged(
    launcher: ModuleType,
) -> None:
    """CORR-01: a styled at-mention on the marker row plus unstyled indented text is a draft."""
    dump = (
        _claude_marker_bytes()
        + "\x1b[38;2;128;128;128m@plugins/agent-launcher/README.md\x1b[0m"
        + "\n  please review this and tell me what breaks"
    )
    result = launcher.inspect_composer(dump, vendor="claude")
    assert result.state is launcher.ComposerState.STAGED
    assert result.text == (
        "@plugins/agent-launcher/README.mdplease review this and tell me what breaks"
    )


def test_an_empty_marker_followed_by_two_blank_rows_is_empty(launcher: ModuleType) -> None:
    """Trailing blank rows alone read empty (C23: a blank is not by itself ambiguity)."""
    result = launcher.inspect_composer("❯ \n\n\n", vendor="claude")
    assert result.state is launcher.ComposerState.EMPTY
    assert result.text == ""


def test_an_echo_a_blank_row_and_an_empty_marker_read_empty(launcher: ModuleType) -> None:
    """CORR-05: a blank row separates, so the live empty box is not adjacent to the echo."""
    result = launcher.inspect_composer("❯ earlier submitted prompt\n\n❯ ", vendor="claude")
    assert result.state is launcher.ComposerState.EMPTY
    assert result.text == ""


def test_a_bordered_draft_ending_in_a_corner_glyph_keeps_it(launcher: ModuleType) -> None:
    """CORR-06: at most one trailing border glyph is structure; the draft's own corner stays."""
    result = launcher.inspect_composer("│ ❯ the tree ends with (╰╯ │", vendor="claude")
    assert result.state is launcher.ComposerState.STAGED
    assert result.text == "the tree ends with (╰╯"


def test_a_bordered_box_whose_only_content_is_a_border_glyph_is_staged(
    launcher: ModuleType,
) -> None:
    """SEC-04: one border-glyph character of content is a draft, not an empty box."""
    result = launcher.inspect_composer("│ ❯ █ │", vendor="claude")
    assert result.state is launcher.ComposerState.STAGED
    assert result.text == "█"


def test_a_bordered_row_flush_at_the_marker_column_continues(launcher: ModuleType) -> None:
    """SEC-04: containment, not a column comparison, proves a bordered continuation."""
    dump = "│ ❯ │\n│ y │"
    result = launcher.inspect_composer(dump, vendor="claude")
    assert result.state is launcher.ComposerState.STAGED
    assert result.text == "y"


def test_a_bordered_rule_row_ends_the_block_and_never_joins_the_draft(
    launcher: ModuleType,
) -> None:
    """C18: a bordered row whose content is only rule glyphs is a rule row, not a continuation."""
    dump = "│ ❯ x │\n│    ──── │\n│   y │"
    result = launcher.inspect_composer(dump, vendor="claude")
    assert result.state is launcher.ComposerState.STAGED
    assert result.text == "x"


def test_round_corner_borders_lead_and_trail_a_two_row_draft(launcher: ModuleType) -> None:
    """The corner glyphs are rosters on both sides: they lead row 1 and close row 2."""
    dump = "╭ ❯ draft ╮\n╰   more ╯"
    result = launcher.inspect_composer(dump, vendor="claude")
    assert result.state is launcher.ComposerState.STAGED
    assert result.text == "draftmore"


@pytest.mark.parametrize("glyph", sorted(LEADING_BORDER_ROSTER))
def test_every_leading_border_glyph_is_rostered(launcher: ModuleType, glyph: str) -> None:
    """TEST-08 / C21: removing any one leading glyph breaks this named case for that glyph."""
    result = launcher.inspect_composer(f"{glyph} ❯ draft text", vendor="claude")
    assert result.state is launcher.ComposerState.STAGED
    assert result.text == "draft text"


@pytest.mark.parametrize("glyph", sorted(TRAILING_BORDER_ROSTER))
def test_every_trailing_border_glyph_is_rostered(launcher: ModuleType, glyph: str) -> None:
    """TEST-08 / C22: removing any one trailing glyph breaks this named case for that glyph."""
    result = launcher.inspect_composer(f"│ ❯ hi {glyph}", vendor="claude")
    assert result.state is launcher.ComposerState.STAGED
    assert result.text == "hi"


def test_the_border_rosters_match_their_pinned_expectation() -> None:
    """Drift pin: a glyph added to or removed from either roster fails here, so the pinned
    parametrisation above cannot silently fall behind the module."""
    assert frozenset(LEADING_BORDER_ROSTER) == COMPOSER_MODULE._LEADING_BORDER_GLYPHS
    assert frozenset(TRAILING_BORDER_ROSTER) == COMPOSER_MODULE._TRAILING_BORDER_GLYPHS


def test_unstyled_text_joins_rows_without_a_separator() -> None:
    """CORR-10: the wrap boundary adds no character; the join is pinned directly."""
    assert COMPOSER_MODULE._unstyled_text(["❯ deploy the", "  fleet"], "❯") == "deploy thefleet"


@pytest.mark.parametrize("key", LIVE_CLAUDE_IDLE_KEYS)
def test_a_live_idle_claude_pane_is_prompted_through_the_real_guard(
    launcher: ModuleType, monkeypatch: pytest.MonkeyPatch, key: str
) -> None:
    """R3: the live captures are the horizontal-rule clause's real-pane regression fixtures."""
    unit, _recorded, sends = _prepare_guard_launch(
        launcher,
        monkeypatch,
        pane_dump=CAPTURED_COMPOSERS[key],
        receipt_tab="w80:t1",
        existing_tabs=("w80:t1",),
    )
    launcher.launch(unit)
    assert len(sends) == 1
    assert unit.launch_receipt["input_box"] == "empty"


def _corrp01_pane() -> str:
    """CORR-01: the fixture marker plus a styled at-file mention, then an indented request."""
    return (
        _claude_marker_bytes()
        + "\x1b[38;2;128;128;128m@plugins/agent-launcher/README.md\x1b[0m"
        + "\n  please review this and tell me what breaks"
    )


def _corrp02_pane() -> str:
    """CORR-02: the fixture marker alone, then the operator's request indented on row 2."""
    return _claude_marker_bytes() + "\n  the actual request text the operator staged"


@pytest.mark.parametrize("pane", [_corrp01_pane, _corrp02_pane], ids=["corrp01", "corrp02"])
def test_corrp01_and_corrp02_panes_stop_the_prompt_through_the_real_guard(
    launcher: ModuleType, monkeypatch: pytest.MonkeyPatch, pane: Any
) -> None:
    """CORR-01 and CORR-02 end to end: the guard refuses to write behind a real draft shape."""
    unit, _recorded, sends = _prepare_guard_launch(
        launcher,
        monkeypatch,
        pane_dump=pane(),
        receipt_tab="w80:t1",
        existing_tabs=("w80:t1",),
    )
    with pytest.raises(launcher.StagedInputError, match="already holds staged input"):
        launcher.launch(unit)
    assert sends == []
    assert unit.launch_receipt["input_box"] == "staged"


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
    # The real verify_unit_preflight must run: it rebuilds unit.launch_receipt, and stubbing it
    # once hid the rebuild discarding this very key. Only its row-read collaborator is stubbed.
    monkeypatch.setattr(
        launcher,
        "agent_row",
        lambda unit, agents=None: {
            "pane_id": "w80:p9",
            "cwd": "/tmp/wt",
            "workspace_id": "w80",
            "interactive_ready": True,
            "agent": "codex",
        },
    )
    monkeypatch.setattr(launcher, "send", lambda *a, **k: sends.append(a))
    monkeypatch.setattr(launcher, "took_the_task", lambda *_a, **_k: True)
    unit = launcher.LaunchRequest(name="reader", vendor="codex", worktree="/tmp/wt")
    launcher.launch(unit)
    assert unit.launch_receipt["input_box"] == "read_failed"
    assert "input box read_failed" in unit.note
    assert len(sends) == 1
    assert pane_read_timeouts == [launcher.PANE_INPUT_READ_SECONDS]


def test_pane_read_timeout_is_distinct_from_a_failed_read(
    launcher: ModuleType, monkeypatch: pytest.MonkeyPatch
) -> None:
    timed_out = launcher.TimedOutProcess(["herdr"], 124, "", "timed out")
    monkeypatch.setattr(launcher, "run", lambda *a, **k: timed_out)
    assert launcher.pane_input_inspection("w1:p1", vendor="claude").state is (
        launcher.ComposerState.READ_TIMEOUT
    )
    failed = subprocess.CompletedProcess(["herdr"], 124, "", "vendor returned 124")
    monkeypatch.setattr(launcher, "run", lambda *a, **k: failed)
    assert launcher.pane_input_inspection("w1:p1", vendor="claude").state is (
        launcher.ComposerState.READ_FAILED
    )


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
    """The input guard runs before the OpenCode picker writes into an unowned pane -- and
    the send carries its own adjacent inspection, so the unowned OpenCode path reads twice."""
    typed: list[list[str]] = []
    # An opencode pane's own glyph is ">": the menu rows and the staged draft all carry it, and
    # the last classified block is the box.
    dump = "Choose variant:\n> high\n> low\n" + f"> {STAGED_SLASH_COMMAND}"
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
    order: list[str] = []
    monkeypatch.setattr(
        launcher, "verify_unit_identity", lambda *a, **k: ([], [], "opencode", True)
    )
    monkeypatch.setattr(launcher, "guard_pane_before_write", lambda *a, **k: order.append("guard"))

    def select_variant(*_args: object, **_kwargs: object) -> tuple[str, bool]:
        order.append("picker")
        return "high", True

    monkeypatch.setattr(
        launcher,
        "drive_opencode_variant_selection",
        select_variant,
    )
    monkeypatch.setattr(launcher, "verify_unit_preflight", lambda *a, **k: {})
    monkeypatch.setattr(launcher, "send", lambda *a, **k: False)
    monkeypatch.setattr(launcher, "took_the_task", lambda *a, **k: True)
    unit = launcher.LaunchRequest(name="oc", vendor="opencode", worktree="/tmp/wt", effort="high")
    launcher.launch(unit)
    assert order == ["guard", "picker", "guard"]
    assert typed == []


def test_the_send_inspection_is_taken_after_the_preflight(
    launcher: ModuleType, monkeypatch: pytest.MonkeyPatch
) -> None:
    """REL-08: the read that authorises the send is taken immediately before the send, after
    the preflight, so a person typing during the preflight's declared bounds cannot defeat
    the guard. At the frozen revision the order is guard-then-preflight."""
    unit, _recorded, _sends = _prepare_guard_launch(
        launcher,
        monkeypatch,
        pane_dump=_claude_pane("❯ "),
        receipt_tab="w80:t1",
        existing_tabs=("w80:t1",),
    )
    order: list[str] = []
    real_guard = launcher.guard_pane_before_write
    real_preflight = launcher.verify_unit_preflight

    def recording_guard(unit: Any, pane_id: str) -> None:
        order.append("guard")
        real_guard(unit, pane_id)

    def recording_preflight(*args: object, **kwargs: object) -> dict[str, Any]:
        order.append("preflight")
        return real_preflight(*args, **kwargs)

    monkeypatch.setattr(launcher, "guard_pane_before_write", recording_guard)
    monkeypatch.setattr(launcher, "verify_unit_preflight", recording_preflight)
    launcher.launch(unit)
    assert order == ["preflight", "guard"]
    assert unit.launch_receipt["input_box"] == "empty"


def test_second_opencode_read_before_the_send_stops_a_late_staged_draft(
    launcher: ModuleType, monkeypatch: pytest.MonkeyPatch
) -> None:
    """REL-08: an unowned OpenCode launch reads twice -- once before the picker, once
    immediately before the send -- so a draft staged between them still stops the send.
    The classifier carries no OpenCode entry (the picker residual holds that custody), so
    the second read's stop is modelled at the guard boundary while the read sites are
    real: the run stub serves an empty composer to the first read and a staged draft to
    the second. At the frozen revision there is one read, it is empty, and the send is
    made."""
    dumps = iter([_claude_pane("❯ "), _claude_pane(f"❯ {STAGED_SLASH_COMMAND}")])
    ansi_reads: list[list[str]] = []
    sends: list[str] = []
    receipt = {"tab_id": "w80:t1", "agent_name": "oc-2", "pane_id": "w80:p9", "reused": False}

    def fake_run(cmd: list[str], **_k: object) -> subprocess.CompletedProcess[str]:
        if cmd[:3] == ["herdr", "pane", "read"] and "--format" in cmd:
            ansi_reads.append(cmd)
            return subprocess.CompletedProcess(cmd, 0, next(dumps), "")
        if cmd[:3] == ["herdr", "pane", "run"]:
            return subprocess.CompletedProcess(cmd, 0, "", "")
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
    monkeypatch.setattr(
        launcher, "verify_unit_identity", lambda *a, **k: ([], [], "opencode", True)
    )
    order: list[str] = []

    def guard(unit: Any, pane_id: str) -> None:
        order.append("guard")
        # Read through the real inspection so the stop is driven by what the pane returned,
        # not by the call count: the classifier has no OpenCode entry, so the read is
        # classified in the pane's vendor-neutral claude shape.
        inspection = launcher.pane_input_inspection(pane_id, vendor="claude")
        if inspection.state is launcher.ComposerState.STAGED:
            raise launcher.StagedInputError("second read found staged input")

    monkeypatch.setattr(launcher, "guard_pane_before_write", guard)

    def picker(*_args: object, **_kwargs: object) -> tuple[str, bool]:
        order.append("picker")
        return "high", True

    monkeypatch.setattr(launcher, "drive_opencode_variant_selection", picker)
    monkeypatch.setattr(launcher, "verify_unit_preflight", lambda *a, **k: {})
    monkeypatch.setattr(launcher, "send", lambda *a, **k: sends.append("send"))
    monkeypatch.setattr(launcher, "took_the_task", lambda *_a, **_k: True)
    unit = launcher.LaunchRequest(name="oc", vendor="opencode", worktree="/tmp/wt", effort="high")
    with pytest.raises(launcher.StagedInputError, match="second read"):
        launcher.launch(unit)
    assert len(ansi_reads) == 2
    assert sends == []
    assert order == ["guard", "picker", "guard"]


def test_a_reused_pane_with_an_empty_box_below_an_echo_is_not_stopped(
    launcher: ModuleType, monkeypatch: pytest.MonkeyPatch
) -> None:
    """B4 end to end: a reused pane whose live box is empty below an earlier prompt echo is a
    normal pane. The launch must prompt, not refuse, and the receipt must say empty."""
    unit, _recorded, sends = _prepare_guard_launch(
        launcher,
        monkeypatch,
        pane_dump="❯ earlier submitted prompt\npane output line\n❯ ",
        receipt_tab="w80:t1",
        existing_tabs=("w80:t1",),
    )
    launcher.launch(unit)
    assert len(sends) == 1
    assert unit.launch_receipt["input_box"] == "empty"


@pytest.mark.parametrize(("vendor", "glyph"), [("codex", "›"), ("grok", "❯"), ("agy", ">")])
def test_non_claude_guard_stops_on_the_vendor_composer_draft(
    launcher: ModuleType,
    monkeypatch: pytest.MonkeyPatch,
    vendor: str,
    glyph: str,
) -> None:
    unit, _recorded, sends = _prepare_guard_launch(
        launcher,
        monkeypatch,
        pane_dump=f"scrollback\n{glyph} destructive draft",
        receipt_tab="w80:t1",
        existing_tabs=("w80:t1",),
        vendor=vendor,
    )
    with pytest.raises(launcher.StagedInputError, match="already holds staged input"):
        launcher.launch(unit)
    assert sends == []
    assert unit.launch_receipt["input_box"] == "staged"


def test_echo_above_a_closed_span_placeholder_does_not_false_stop(
    launcher: ModuleType, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A closed-span live box wins over a classified scrollback echo positionally."""
    unit, _recorded, sends = _prepare_guard_launch(
        launcher,
        monkeypatch,
        pane_dump=CAPTURED_COMPOSERS["claude_echo_above_empty"],
        receipt_tab="w80:t1",
        existing_tabs=("w80:t1",),
    )
    launcher.launch(unit)
    assert len(sends) == 1
    assert unit.launch_receipt["input_box"] == "empty"


def test_echo_above_closed_span_hint_does_not_fall_back_to_the_echo(
    launcher: ModuleType, monkeypatch: pytest.MonkeyPatch
) -> None:
    unit, _recorded, sends = _prepare_guard_launch(
        launcher,
        monkeypatch,
        pane_dump='❯ earlier submitted prompt\noutput\n\x1b[2m❯ Try "fix it"\x1b[0m',
        receipt_tab="w80:t1",
        existing_tabs=("w80:t1",),
    )
    launcher.launch(unit)
    assert len(sends) == 1
    assert unit.launch_receipt["input_box"] == "unclassifiable"


def test_closed_styled_operator_draft_is_knowingly_unclassifiable_and_prompted(
    launcher: ModuleType, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Accepted trade: a fully styled operator draft is unclassifiable and prompts fail-open."""
    unit, _recorded, sends = _prepare_guard_launch(
        launcher,
        monkeypatch,
        pane_dump='❯ \x1b[2mTry "fix it"\x1b[0m',
        receipt_tab="w80:t1",
        existing_tabs=("w80:t1",),
    )
    launcher.launch(unit)
    assert len(sends) == 1
    assert unit.launch_receipt["input_box"] == "unclassifiable"


def _preflight_stubs(
    launcher: ModuleType, monkeypatch: pytest.MonkeyPatch, *, vendor: str = "claude"
) -> list[str]:
    closed: list[str] = []
    monkeypatch.setattr(
        launcher,
        "agent_row",
        lambda unit, agents=None: {
            "pane_id": "pane-1",
            "cwd": "/tmp/wt",
            "workspace_id": "w1",
            "interactive_ready": True,
            "agent": vendor,
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


@pytest.mark.parametrize("vendor", ["agy", "qwen"])
def test_empty_permission_token_list_never_claims_an_argv_confirmation(
    launcher: ModuleType, monkeypatch: pytest.MonkeyPatch, vendor: str
) -> None:
    _preflight_stubs(launcher, monkeypatch, vendor=vendor)
    unit = launcher.LaunchRequest(
        name="worker", vendor=vendor, worktree="/tmp/wt", pane_id="pane-1", tab_id="tab-1"
    )
    receipt = launcher.verify_unit_preflight(
        unit, "pane-1", ready=True, argv=[*LAUNCH_ARGV_HEAD, vendor]
    )
    assert receipt["permission_resolved"]["tokens"] == []
    assert receipt["permission_resolved"]["confirmed_from"] is None
    assert receipt["account_evidence"] == "none"


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


def test_vanished_transcript_between_glob_and_stat_is_skipped(
    launcher: ModuleType, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    vanished = tmp_path / "vanished.jsonl"
    monkeypatch.setattr(launcher, "claude_transcript_roots", lambda: (tmp_path, tmp_path))
    monkeypatch.setattr(launcher, "find_claude_transcripts", lambda *_a: [vanished])
    unit = launcher.LaunchRequest(name="acct", vendor="claude", worktree="/tmp/wt")
    assert launcher.transcript_account(unit, since=time.time()) is None


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
    assert "account" not in receipt["confirmed_against_herdr"]
    assert receipt["confirmed_outside_herdr"] == ["account"]


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
    assert isinstance(result, launcher.TimedOutProcess)
    assert result.returncode == 124
    assert "timed out after 0.1s" in result.stderr


def test_genuine_exit_124_is_not_a_synthesized_timeout(launcher: ModuleType) -> None:
    result = launcher.run(["sh", "-c", "exit 124"], check=False, timeout=2)
    assert result.returncode == 124
    assert not isinstance(result, launcher.TimedOutProcess)


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
    monkeypatch.setattr(launcher, "send", lambda *a, **k: None)
    monkeypatch.setattr(launcher, "took_the_task", lambda *_a, **_k: False)
    monkeypatch.setattr(
        launcher,
        "agent_row",
        lambda *_a, **_k: {
            "agent_status": "idle",
            "pane_id": "pane-1",
            "cwd": str(tmp_path),
            "interactive_ready": True,
            "agent": "codex",
        },
    )
    monkeypatch.setattr(launcher.time, "sleep", lambda *_a, **_k: None)
    unit = launcher.LaunchRequest(name="reviewer", vendor="codex", worktree=str(tmp_path))
    launcher.launch(unit)
    assert unit.status == launcher.PROMPT_UNDELIVERED
    assert launcher.DELIVERY_WARNING in unit.note
    assert unit.launch_receipt["prompt_delivered"] is False
    assert unit.launch_receipt["agent_name"] == "reviewer-2"
    assert unit.tab_id == "tab-1"


def test_pane_fallback_resend_rechecks_for_staged_input(
    launcher: ModuleType, monkeypatch: pytest.MonkeyPatch
) -> None:
    receipt = {
        "tab_id": "w1:t-new",
        "agent_name": "worker-2",
        "pane_id": "w1:p1",
        "reused": False,
    }
    monkeypatch.setattr(launcher, "list_tab_ids", lambda _workspace=None: frozenset({"w1:t-new"}))
    monkeypatch.setattr(
        launcher,
        "run",
        lambda cmd, **kwargs: subprocess.CompletedProcess(cmd, 0, json.dumps(receipt), ""),
    )
    monkeypatch.setattr(launcher, "launcher", lambda: "agents")
    monkeypatch.setattr(launcher, "await_ready", lambda *_a, **_k: True)
    monkeypatch.setattr(launcher, "verify_unit_preflight", lambda *a, **k: {})
    sends: list[str] = []

    def pane_send(*_args: object, **_kwargs: object) -> bool:
        sends.append("send")
        return True

    monkeypatch.setattr(launcher, "send", pane_send)
    monkeypatch.setattr(launcher, "took_the_task", lambda *_a, **_k: False)
    monkeypatch.setattr(
        launcher,
        "agent_row",
        lambda *_a, **_k: {
            "agent_status": "idle",
            "pane_id": "w1:p1",
            "cwd": "/tmp/wt",
            "workspace_id": "w1",
            "interactive_ready": True,
            "agent": "codex",
        },
    )

    inspections: list[str] = []

    def stop_resend(*_args: object, **_kwargs: object) -> None:
        inspections.append("guard")
        if len(inspections) > 1:
            raise launcher.StagedInputError("resend target now contains staged input")

    monkeypatch.setattr(launcher, "guard_pane_before_write", stop_resend)
    unit = launcher.LaunchRequest(name="worker", vendor="codex", worktree="/tmp/wt")
    with pytest.raises(launcher.StagedInputError, match="resend target"):
        launcher.launch(unit)
    assert sends == ["send"]
    assert inspections == ["guard", "guard"]


def test_agent_prompt_resend_rechecks_before_it_can_fall_back_to_the_pane(
    launcher: ModuleType, monkeypatch: pytest.MonkeyPatch
) -> None:
    unit, _recorded, _sends = _prepare_guard_launch(
        launcher,
        monkeypatch,
        pane_dump=_claude_pane("❯ "),
        receipt_tab="w80:t1",
        existing_tabs=("w80:t1",),
    )
    inspections: list[str] = []
    send_paths = iter([False, True])  # agent prompt first, pane fallback on the resend
    accepted = iter([False, True])
    monkeypatch.setattr(
        launcher,
        "guard_pane_before_write",
        lambda *_a, **_k: inspections.append("guard"),
    )
    monkeypatch.setattr(launcher, "send", lambda *_a, **_k: next(send_paths))
    monkeypatch.setattr(launcher, "took_the_task", lambda *_a, **_k: next(accepted))
    monkeypatch.setattr(
        launcher,
        "agent_row",
        lambda *_a, **_k: {
            "agent_status": "idle",
            "pane_id": "w80:p9",
            "cwd": "/tmp/wt",
            "workspace_id": "w80",
            "interactive_ready": True,
            "agent": "claude",
        },
    )

    launcher.launch(unit)

    assert inspections == ["guard", "guard"]
    assert unit.status == launcher.RUNNING


def _prepare_resend_launch(
    launcher: ModuleType,
    monkeypatch: pytest.MonkeyPatch,
    *,
    agent_prompt_ok: bool,
    pane_dump: str,
    preexisting_tabs: frozenset[str],
) -> tuple[Any, list[list[str]], list[str], list[str]]:
    """Drive the real send/say and the resend loop with only the Herdr boundary stubbed.

    Whether `herdr agent prompt` succeeds or is refused selects the two delivery doors: a
    refusal makes say() type into the pane, which is the used_pane half of the resend
    predicate. Returns the unit, every recorded command, the pane-typing writes, and the
    guard calls made by the counting wrapper around the real guard.
    """
    recorded: list[list[str]] = []
    pane_writes: list[str] = []
    guard_calls: list[str] = []
    receipt = {"tab_id": "w1:t-new", "agent_name": "worker-2", "pane_id": "w1:p1", "reused": False}

    def fake_run(cmd: list[str], **_k: object) -> subprocess.CompletedProcess[str]:
        recorded.append(cmd)
        if cmd[:3] == ["herdr", "agent", "prompt"]:
            rc = 0 if agent_prompt_ok else 1
            detail = "" if agent_prompt_ok else "not interactive ready"
            return subprocess.CompletedProcess(cmd, rc, "", detail)
        if cmd[:3] == ["herdr", "pane", "run"]:
            pane_writes.append(cmd[-1])
            return subprocess.CompletedProcess(cmd, 0, "", "")
        if cmd[:3] == ["herdr", "pane", "read"]:
            return subprocess.CompletedProcess(cmd, 0, pane_dump, "")
        return subprocess.CompletedProcess(cmd, 0, json.dumps(receipt), "")

    real_guard = launcher.guard_pane_before_write

    def counting_guard(unit: Any, pane_id: str) -> None:
        guard_calls.append(pane_id)
        real_guard(unit, pane_id)

    monkeypatch.setattr(launcher, "list_tab_ids", lambda _workspace=None: preexisting_tabs)
    monkeypatch.setattr(launcher, "run", fake_run)
    monkeypatch.setattr(launcher, "launcher", lambda: "agents")
    monkeypatch.setattr(launcher, "await_ready", lambda *_a, **_k: True)
    monkeypatch.setattr(launcher, "verify_unit_preflight", lambda *a, **k: {})
    monkeypatch.setattr(launcher, "guard_pane_before_write", counting_guard)
    monkeypatch.setattr(launcher, "took_the_task", lambda *_a, **_k: False)
    monkeypatch.setattr(
        launcher,
        "agent_row",
        lambda *_a, **_k: {
            "agent_status": "idle",
            "pane_id": "w1:p1",
            "cwd": "/tmp/wt",
            "workspace_id": "w1",
            "interactive_ready": True,
            "agent": "claude",
        },
    )
    unit = launcher.LaunchRequest(name="worker", vendor="claude", worktree="/tmp/wt")
    return unit, recorded, pane_writes, guard_calls


def test_pane_fallback_resend_into_an_owned_pane_rechecks_for_staged_input(
    launcher: ModuleType, monkeypatch: pytest.MonkeyPatch
) -> None:
    """SEC-01: an owned session whose first send typed into the pane is re-inspected on the
    resend. At the frozen revision this shape makes three pane writes and zero guard calls
    (DID NOT RAISE); the probe is rebuilt here from the artifact."""
    unit, _recorded, pane_writes, guard_calls = _prepare_resend_launch(
        launcher,
        monkeypatch,
        agent_prompt_ok=False,
        pane_dump=_claude_pane(f"❯ {STAGED_SLASH_COMMAND}"),
        preexisting_tabs=frozenset(),
    )
    with pytest.raises(launcher.StagedInputError, match="already holds staged input"):
        launcher.launch(unit)
    assert guard_calls == ["w1:p1"]
    assert len(pane_writes) == 1
    assert unit.tab_id == "w1:t-new"
    assert unit.pane_id == "w1:p1"
    assert unit.owned is True
    assert unit.launch_receipt["agent_name"] == "worker-2"
    assert unit.launch_receipt["input_box"] == "staged"


def test_agent_prompt_resend_into_an_owned_pane_is_never_inspected(
    launcher: ModuleType, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The direction not fixed: ownership is about who created the tab, never who last
    typed. An owned session delivered through `herdr agent prompt` has never been written
    by this launcher, so no resend inspects it -- zero guard calls in the whole launch."""
    unit, recorded, pane_writes, guard_calls = _prepare_resend_launch(
        launcher,
        monkeypatch,
        agent_prompt_ok=True,
        pane_dump=_claude_pane("❯ "),
        preexisting_tabs=frozenset(),
    )
    launcher.launch(unit)
    assert guard_calls == []
    assert pane_writes == []
    prompt_calls = [c for c in recorded if c[:3] == ["herdr", "agent", "prompt"]]
    assert len(prompt_calls) == 3
    assert unit.status == launcher.PROMPT_UNDELIVERED


def test_each_resend_after_a_pane_fallback_is_inspected_once(
    launcher: ModuleType, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The fixed side, counted: an owned pane-fallback launch makes zero guard calls before
    its first send and exactly one per resend while the session stays idle."""
    unit, _recorded, pane_writes, guard_calls = _prepare_resend_launch(
        launcher,
        monkeypatch,
        agent_prompt_ok=False,
        pane_dump=_claude_pane("❯ "),
        preexisting_tabs=frozenset(),
    )
    launcher.launch(unit)
    assert guard_calls == ["w1:p1", "w1:p1"]
    assert len(pane_writes) == 3
    assert unit.status == launcher.PROMPT_UNDELIVERED


def _prepare_redeliver(
    launcher: ModuleType,
    monkeypatch: pytest.MonkeyPatch,
    *,
    owned: bool,
    pane_dump: str,
) -> tuple[Any, list[list[str]], list[str]]:
    """A unit carrying a staged-input stop's identifiers, with only the Herdr boundary
    stubbed. Returns the unit, every recorded command, and the sends."""
    recorded: list[list[str]] = []
    sends: list[str] = []

    def fake_run(cmd: list[str], **_k: object) -> subprocess.CompletedProcess[str]:
        recorded.append(cmd)
        if cmd[:3] == ["herdr", "pane", "read"] and "--format" in cmd:
            return subprocess.CompletedProcess(cmd, 0, pane_dump, "")
        if cmd[:3] == ["herdr", "agent", "prompt"]:
            return subprocess.CompletedProcess(cmd, 0, "", "")
        return subprocess.CompletedProcess(cmd, 0, "", "")

    monkeypatch.setattr(launcher, "run", fake_run)
    monkeypatch.setattr(launcher, "launcher", lambda: "agents")
    monkeypatch.setattr(launcher, "await_ready", lambda *_a, **_k: True)
    monkeypatch.setattr(launcher, "verify_unit_preflight", lambda *a, **k: {})
    monkeypatch.setattr(launcher, "send", lambda *a, **k: sends.append("send"))
    monkeypatch.setattr(launcher, "took_the_task", lambda *_a, **_k: True)
    monkeypatch.setattr(
        launcher,
        "agent_row",
        lambda *_a, **_k: {
            "agent_status": "idle",
            "pane_id": "w1:p1",
            "workspace_id": "w1",
            "interactive_ready": True,
            "agent": "claude",
        },
    )
    unit = launcher.LaunchRequest(
        name="worker",
        vendor="claude",
        worktree="/tmp/wt",
        pane_id="w1:p1",
        tab_id="w1:t1",
        owned=owned,
        launch_receipt={
            "tab_id": "w1:t1",
            "pane": "w1:p1",
            "agent_name": "worker-2",
            "owned": owned,
            "input_box": "staged",
        },
    )
    return unit, recorded, sends


def test_redeliver_records_no_wrapper_create_and_keeps_the_tab(
    launcher: ModuleType, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The retry never runs the wrapper create: calling launch() again would create a second
    session and overwrite the first owned tab (the prior validation artifact's REL-03,
    rebuilt through the retry door)."""
    unit, recorded, sends = _prepare_redeliver(
        launcher, monkeypatch, owned=False, pane_dump=_claude_pane("❯ ")
    )
    launcher.redeliver(unit)
    assert not any(cmd[0] == "agents" for cmd in recorded)
    assert unit.tab_id == "w1:t1"
    assert unit.status == launcher.RUNNING
    assert unit.launch_receipt["prompt_delivered"] is True
    assert unit.launch_receipt["input_box"] == "empty"
    assert sends == ["send"]


def test_redeliver_inspects_before_the_first_write_on_an_owned_unit(
    launcher: ModuleType, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The used_pane half of the pre-send predicate, observable only here: a redelivery
    into a pane this launcher owns still inspects before its first write, because the stop
    that made the redelivery necessary was an inspection that found text. A still-staged
    pane raises with no send."""
    unit, _recorded, sends = _prepare_redeliver(
        launcher,
        monkeypatch,
        owned=True,
        pane_dump=_claude_pane(f"❯ {STAGED_SLASH_COMMAND}"),
    )
    with pytest.raises(launcher.StagedInputError, match="already holds staged input"):
        launcher.redeliver(unit)
    assert sends == []
    assert unit.launch_receipt["input_box"] == "staged"


def test_redeliver_without_a_pane_id_is_a_named_stop(launcher: ModuleType) -> None:
    """A unit that lost its pane id cannot be redelivered; the stop names the recovery."""
    unit = launcher.LaunchRequest(name="worker", vendor="claude", worktree="/tmp/wt")
    with pytest.raises(SystemExit, match="cannot redeliver"):
        launcher.redeliver(unit)


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


def test_already_absent_owned_tab_is_an_idempotent_success(
    launcher: ModuleType, monkeypatch: pytest.MonkeyPatch
) -> None:
    calls: list[tuple[list[str], dict[str, object]]] = []

    def fake_run(cmd: list[str], **kwargs: object) -> subprocess.CompletedProcess[str]:
        calls.append((cmd, kwargs))
        if cmd[:3] == ["herdr", "tab", "list"]:
            return subprocess.CompletedProcess(cmd, 0, '{"result":{"tabs":[]}}', "")
        return subprocess.CompletedProcess(cmd, 1, "", "tab not found")

    monkeypatch.setattr(launcher, "run", fake_run)
    unit = launcher.LaunchRequest(name="x", vendor="codex", tab_id="w1:t-gone", owned=True)
    result = launcher.close_run_session(unit)
    assert result is not None and result.returncode == 0
    assert unit.note == ""
    assert calls[0][1]["timeout"] == launcher.TAB_CLOSE_SECONDS


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


@pytest.mark.parametrize("contents", ["", '{"tab_id":'])
def test_malformed_receipt_file_has_a_named_recovery_stop(
    launcher: ModuleType, tmp_path: Path, contents: str
) -> None:
    path = tmp_path / "receipt.json"
    path.write_text(contents, encoding="utf-8")
    with pytest.raises(SystemExit) as exc_info:
        launcher._load_receipt(str(path))
    message = str(exc_info.value)
    assert str(path) in message
    assert "empty or unparseable JSON" in message
    assert "fresh receipt file" in message


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
    launcher_manifest = json.loads(
        (REPO / "plugins" / "agent-launcher" / ".claude-plugin" / "plugin.json").read_text(
            encoding="utf-8"
        )
    )
    assert floors.get("agent-launcher") == f">={launcher_manifest['version']}", declared


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


def test_the_documented_preflight_recipe_is_runnable(launcher: ModuleType) -> None:
    """The probe recipe must actually run: a prompt (and the account flag when an account is
    named) on the launch line, an exit-status statement, and a read-back that selects only keys
    the receipt can supply -- never the model, which is the request echoed back."""
    skill = (
        REPO / "plugins" / "agent-launcher" / "skills" / "agent-launcher" / "SKILL.md"
    ).read_text(encoding="utf-8")
    section = skill[skill.index("## The only real preflight") : skill.index("## Ordering")]
    launch_lines = [line for line in section.splitlines() if "launch --vendor" in line]
    assert launch_lines
    probe = launch_lines[-1]
    command = probe.removesuffix(" > receipt.json")
    tokens = shlex.split(command)
    assert tokens[:2] == ["python3", "$S"]
    replacements = {
        "<probe-name>": "probe",
        "$PWD": "/tmp/worktree",
        "<model>": "model",
        "<effort>": "high",
        "<selection>": "company",
        "<probe-task>": "verify readiness",
    }
    parsed = launcher._build_parser().parse_args(
        [replacements.get(token, token) for token in tokens[2:]]
    )
    assert parsed.cmd == "launch"
    assert parsed.vendor == "claude"
    assert parsed.prompt == "verify readiness"
    assert parsed.account == "company"
    assert "only when creation, identity, preflight, and delivery all succeed" in section
    jq_lines = [line for line in section.splitlines() if line.startswith("jq ")]
    assert jq_lines
    assert "model" not in jq_lines[-1]
    assert "confirmed_against_herdr" in jq_lines[-1]


def test_every_documented_launcher_fence_carries_a_prompt_and_nonzero_caveat() -> None:
    for path in (SKILL_MD, LAUNCHER_README):
        surface = path.read_text(encoding="utf-8")
        launch_lines = [line for line in surface.splitlines() if 'python3 "$S" launch' in line]
        assert launch_lines, path
        assert all("--prompt" in line for line in launch_lines), path
        assert "without one" in surface.lower(), path
        assert "exits nonzero" in surface.lower(), path


def test_launcher_failure_messages_do_not_interpolate_whole_argv() -> None:
    source = LAUNCHER.read_text(encoding="utf-8")
    assert "' '.join(cmd)" not in source
    assert '" ".join(cmd)' not in source
    assert "' '.join(argv)" not in source
    assert '" ".join(argv)' not in source


def test_release_and_journal_record_the_composer_contract() -> None:
    changelog = (REPO / "plugins" / "agent-launcher" / "CHANGELOG.md").read_text(encoding="utf-8")
    skill = SKILL_MD.read_text(encoding="utf-8")
    learnings = (REPO / "docs" / "engineering-journal" / "LEARNINGS.md").read_text(encoding="utf-8")
    decisions = (REPO / "docs" / "engineering-journal" / "DECISIONS.md").read_text(encoding="utf-8")
    assert "## [1.2.1] - 2026-08-31" in changelog
    assert "selects the last block positionally" in changelog
    assert "`unclassifiable`, `not_found`, `unsupported_vendor`, `read_failed`" in changelog
    normalized_changelog = " ".join(changelog.split())
    assert "distinguishes a client's own placeholder from staged text" not in normalized_changelog
    assert "Claude, Codex, Grok, Agy, and Qwen" in skill
    assert "#907-composer-position-before-classification" in learnings
    assert "#907-styled-composer-trade" in decisions
