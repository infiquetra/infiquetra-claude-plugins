"""Issue #923 (plan U2): surfaced plan-save failures and the finished-plan routing contract.

Two defects, two repairs, both pinned here:

* **Save failures name the stranded plan document** (plan KTD2: a named failure, not a
  transaction). A filesystem failure while writing the tick already exits non-zero, but a
  bare traceback never names the plan document now left on disk with NO saga state
  referencing it. The CLI save path catches the ``OSError`` and names the ``--plan-path``
  document. The negative test engineers a REAL filesystem failure — the saga directory
  exists as a regular file, so ``mkdir`` inside ``save()`` raises — and asserts the raised
  failure and the non-zero exit, not a log line.
* **A finished plan routes onward, never back into /plan** (plan KTD1: the producer
  changes, the router does not). Phase 5.3 writes ``--phase-status complete`` on every
  save variant; the ``/loop`` dispatch table routes ``plan`` / ``complete`` onward to
  ``/doc-review``. The three contract surfaces are pinned equal so they cannot drift apart
  again, and Phase 5.3's exit-status instruction is pinned present.
"""

from __future__ import annotations

import importlib.util
import json
import re
import sys
from collections.abc import Callable
from pathlib import Path
from types import ModuleType, SimpleNamespace
from typing import Any

import pytest

ROOT = Path(__file__).parent.parent
PLUGIN_ROOT = ROOT / "plugins" / "saga"
SCRIPTS_DIR = PLUGIN_ROOT / "scripts"
PLAN_SKILL = PLUGIN_ROOT / "skills" / "plan" / "SKILL.md"
SAGA_SPEC = PLUGIN_ROOT / "references" / "saga-spec.md"
DISPATCH_TABLE = PLUGIN_ROOT / "skills" / "loop" / "references" / "dispatch-table.md"


def _load_module(script_name: str) -> ModuleType:
    """Load a script module by file path, registered in ``sys.modules``.

    Registration matters: ``saga.py`` defines a frozen ``@dataclass`` and (on Python
    3.12+) dataclass processing looks the class's ``__module__`` up in ``sys.modules``
    while building it. Registering under the bare name also lets this file share the same
    engine instance the other saga test modules load.
    """
    name = script_name.removesuffix(".py")
    path = SCRIPTS_DIR / script_name
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


@pytest.fixture
def saga() -> ModuleType:
    """The loaded ``saga`` engine module."""
    return _load_module("saga.py")


def _run_main(
    module: ModuleType,
    argv: list[str],
    capsys: pytest.CaptureFixture[str],
    monkeypatch: pytest.MonkeyPatch,
) -> tuple[int, dict[str, Any]]:
    """Invoke a script's ``main()`` with a faked argv; return (rc, parsed JSON)."""
    monkeypatch.setattr("sys.argv", ["script", *argv])
    rc = module.main()
    out = capsys.readouterr().out
    return rc, json.loads(out)


def _set_runner(
    saga: ModuleType, monkeypatch: pytest.MonkeyPatch, runner: Callable[..., Any]
) -> None:
    """Install ``runner`` as the subprocess seam everywhere the engine uses it.

    Patches both ``saga.subprocess.run`` and each function's captured keyword-only
    ``runner`` default (defaults bind at definition time, so the attribute patch alone
    never reaches a call that omits ``runner=``). Tests never shell out to git/gh.
    """
    monkeypatch.setattr(saga.subprocess, "run", runner)
    for fn_name in ("save", "current_git_state", "aggregate_context", "prior_prs"):
        fn = getattr(saga, fn_name)
        new_kwdefaults = dict(fn.__kwdefaults__ or {})
        new_kwdefaults["runner"] = runner
        monkeypatch.setattr(fn, "__kwdefaults__", new_kwdefaults)


def _stub_no_git(saga: ModuleType, monkeypatch: pytest.MonkeyPatch) -> None:
    """Make the engine's subprocess seam a no-op (empty git/gh output)."""

    def fake_run(*_args: Any, **_kwargs: Any) -> SimpleNamespace:
        return SimpleNamespace(returncode=1, stdout="", stderr="")

    _set_runner(saga, monkeypatch, fake_run)


# ---------------------------------------------------------------------------
# Save half: a failing save surfaces an error that names the stranded document
# ---------------------------------------------------------------------------


def test_failed_save_surfaces_error_naming_the_stranded_plan_document(
    saga: ModuleType,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """A filesystem failure writing the tick surfaces as a clean error naming the plan.

    The saga directory exists as a regular FILE, so ``mkdir(parents=True, exist_ok=True)``
    inside ``save()`` raises ``FileExistsError`` — a real filesystem failure, no mocked
    write path. Before the repair this escaped as a bare traceback that never named the
    plan document left on disk without a tick.
    """
    monkeypatch.chdir(tmp_path)
    _stub_no_git(saga, monkeypatch)
    saga_id = saga.derive_saga_id("issue", "923")
    blocker = tmp_path / saga.SAGAS_DIR / saga_id
    blocker.parent.mkdir(parents=True)
    blocker.write_text("not a directory", encoding="utf-8")
    plan_doc = "docs/plans/2026-08-30-state-correctness-plan.md"
    plan_file = tmp_path / plan_doc
    plan_file.parent.mkdir(parents=True)
    plan_file.write_text("# Plan\n", encoding="utf-8")

    monkeypatch.setattr(
        "sys.argv",
        [
            "script",
            "save",
            "--id",
            "923",
            "--lifecycle-phase",
            "plan",
            "--phase-status",
            "complete",
            "--plan-path",
            plan_doc,
        ],
    )
    rc = saga.main()
    err = capsys.readouterr().err

    assert rc == 2
    assert plan_doc in err, "the surfaced error must name the stranded plan document"
    assert "Traceback" not in err, "the failure must surface as a clean error, not a traceback"
    # Nothing half-written: no tick may exist for a save that failed before the write.
    assert saga.restore(tmp_path, saga_id) is None


def test_successful_plan_save_tick_resolves_to_the_written_document(
    saga: ModuleType,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """After a successful save carrying ``--plan-path``, ``restore`` resolves to that document."""
    monkeypatch.chdir(tmp_path)
    _stub_no_git(saga, monkeypatch)
    plan_doc = "docs/plans/2026-08-30-state-correctness-plan.md"
    plan_file = tmp_path / plan_doc
    plan_file.parent.mkdir(parents=True)
    plan_file.write_text("# Plan\n", encoding="utf-8")

    rc, _ = _run_main(
        saga,
        [
            "save",
            "--id",
            "923",
            "--lifecycle-phase",
            "plan",
            "--phase-status",
            "complete",
            "--plan-path",
            plan_doc,
        ],
        capsys,
        monkeypatch,
    )
    assert rc == 0

    saga_id = saga.derive_saga_id("issue", "923")
    restored = saga.restore(tmp_path, saga_id)
    assert restored is not None
    assert restored.plan_path == plan_doc
    assert (tmp_path / restored.plan_path).is_file()
    # The written tick carries the exact value the /loop dispatch row routes onward on.
    assert restored.phase_status == "complete"


# ---------------------------------------------------------------------------
# Routing half: the producer and the router agree on a finished plan phase
# ---------------------------------------------------------------------------


def _plan_phase_53() -> str:
    """Return the Phase 5.3 section of plan/SKILL.md (up to Phase 5.4)."""
    text = PLAN_SKILL.read_text(encoding="utf-8")
    start = text.index("### 5.3")
    end = text.index("### 5.4", start)
    return text[start:end]


def _dispatch_status_for_finished_plan() -> str:
    """Read the ``phase_status`` the dispatch table requires to route ``plan`` onward.

    Read-only on loop's dispatch table (correct as filed; this run never edits it):
    the single row whose lifecycle phase is ``plan`` and whose next command is
    ``/doc-review`` is the router's definition of a finished plan phase.
    """
    rows: list[list[str]] = []
    for line in DISPATCH_TABLE.read_text(encoding="utf-8").splitlines():
        stripped = line.strip()
        if not stripped.startswith("|"):
            continue
        cells = [cell.strip() for cell in stripped.split("|")[1:-1]]
        if all(set(cell) <= {"-", ":", " "} for cell in cells):
            continue  # separator row
        rows.append(cells)
    matches = [
        row
        for row in rows
        if len(row) >= 4 and row[0] == "`plan`" and row[3].startswith("`/doc-review`")
    ]
    assert len(matches) == 1, (
        f"expected exactly one dispatch row routing a finished plan onward to /doc-review, "
        f"found {len(matches)}"
    )
    return matches[0][1].strip("`").strip()


def _spec_plan_write_phase_status() -> str:
    """Read ``phase_status`` from the ``/plan`` writes column of saga-spec.md §11."""
    for line in SAGA_SPEC.read_text(encoding="utf-8").splitlines():
        if line.strip().startswith("| **/plan**"):
            match = re.search(r"phase_status=([a-z_]+)", line)
            assert match, "the saga-spec /plan writes column must name phase_status"
            return match.group(1)
    raise AssertionError("no /plan row found in the saga-spec.md consumer table")


def test_plan_phase_status_agrees_end_to_end() -> None:
    """The producer, the spec row, and the router agree on a finished plan phase.

    Mutation proof (KTD1): removing ``--phase-status complete`` from Phase 5.3 fails this
    test, and the dispatch row is the router's side of the same contract — so the two can
    never drift apart again in silence. Only the runnable command blocks are pinned: the
    prose around them stays free.
    """
    section = _plan_phase_53()
    blocks = re.findall(r"```[a-z]*\n(.*?)```", section, flags=re.DOTALL)
    save_blocks = [block for block in blocks if "saga.py save" in block]
    assert save_blocks, "Phase 5.3 must contain runnable saga save command block(s)"
    values = [
        value for block in save_blocks for value in re.findall(r"--phase-status[= ](\S+)", block)
    ]
    assert values, "Phase 5.3 must pass --phase-status on its save command(s)"
    assert len(values) == len(save_blocks), (
        f"every Phase 5.3 save variant must pass --phase-status; found {len(values)} "
        f"flag(s) across {len(save_blocks)} save command(s)"
    )
    dispatch = _dispatch_status_for_finished_plan()
    spec = _spec_plan_write_phase_status()
    assert set(values) == {dispatch} == {spec}, (
        f"the finished-plan phase_status disagrees: Phase 5.3 writes {sorted(set(values))}, "
        f"saga-spec /plan writes {spec!r}, the /loop dispatch row requires {dispatch!r}"
    )


def test_phase_53_checks_save_exit_status_before_routing_onward() -> None:
    """Phase 5.3 carries the exit-status instruction; deleting it fails this test.

    A failed save must stop the run before Phase 5.4 routes onward, so the operator sees
    the stranded-document error instead of a route decision built on a tick that never
    landed.
    """
    section = _plan_phase_53().lower()
    assert "exit status" in section, "Phase 5.3 must instruct checking the save's exit status"
    assert re.search(r"\bstop\b", section), "Phase 5.3 must say to STOP on a failed save"
    assert "5.4" in section, "Phase 5.3 must forbid continuing to Phase 5.4 on a failed save"
