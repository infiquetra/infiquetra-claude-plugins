"""Tests for the OutcomeOrchestrator dispatcher seam (U4).

Pins R5 (single dispatcher seam, HALT-not-degrade receipt), R6 (team-execution is the first real
backend), and R23 (a backend that cannot run halts visibly, never a silent substitute) — plus the
team_emitter wiring (R5) and integration with the U3 reconcile loop.
"""

from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path
from types import ModuleType, SimpleNamespace
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


D = _load("outcome_dispatcher")
ES = _load("execution_spec")
OUTCOME = _load("outcome")
STORE = _load("outcome_store")


def _req(backend: str, *, outcome_id: str = "ship-x", subplot_id: str = "build") -> Any:
    return SimpleNamespace(
        outcome_id=outcome_id,
        subplot_id=subplot_id,
        title="Build the thing",
        backend=backend,
        repo_root=Path("."),
    )


# --------------------------------------------------------------------------- dispatch (R5/R6)


def test_dispatch_team_execution_mints_leaf_with_return_channel() -> None:
    out = D.dispatch(_req("team-execution"))
    assert out["status"] == "dispatched"
    assert out["backend"] == "team-execution"
    assert out["leaf_saga_id"] == "leaf-ship-x-build"
    assert out["return_channel"] == "/resume leaf-ship-x-build"  # R9 re-entry token out


def test_dispatch_inline_is_available() -> None:
    assert D.dispatch(_req("inline"))["status"] == "dispatched"


@pytest.mark.parametrize(
    # The host-dependent backends are unavailable under the conservative DEFAULT_AVAILABLE floor
    # (inline / team-execution / manual). `manual` is now always-available (U9), so it dispatches.
    "backend",
    ["fork", "subagent", "cc-workflows-ultracode", "goal"],
)
def test_dispatch_unavailable_backend_halts_not_substitutes(backend: str) -> None:
    # R5/R23: a chosen-but-unavailable backend HALTS with a visible receipt — never a silent inline.
    out = D.dispatch(_req(backend))
    assert out["status"] == "halt"
    receipt = out["receipt"]
    assert receipt["backend"] == backend
    assert receipt["kind"] == "halt"
    assert "HALT" in receipt["reason"] and "substitute" in receipt["reason"]
    assert receipt["available"] == list(D.DEFAULT_AVAILABLE)


def test_dispatch_unknown_backend_is_rejected() -> None:
    with pytest.raises(D.DispatcherError, match="executor menu"):
        D.dispatch(_req("magic-backend"))


def test_custom_available_set() -> None:
    # If team-execution is not in the available set, it too halts (the seam is data-driven).
    assert D.dispatch(_req("team-execution"), available=("inline",))["status"] == "halt"


# --------------------------------------------------------------------------- make_dispatcher adapter


def test_make_dispatcher_returns_leaf_id_on_dispatch() -> None:
    disp = D.make_dispatcher()
    assert disp(_req("team-execution")) == "leaf-ship-x-build"


def test_make_dispatcher_raises_halt_with_receipt() -> None:
    disp = D.make_dispatcher()
    with pytest.raises(D.BackendHaltError) as exc:
        disp(_req("fork"))
    assert exc.value.receipt.backend == "fork"
    assert exc.value.receipt.subplot_id == "build"


# --------------------------------------------------------------------------- team_emitter wiring (R5)


def _execution_spec_dict() -> dict[str, Any]:
    return {
        "name": "leaf-plan",
        "description": "a leaf plan",
        "repo": "/tmp/repo",
        "units": [
            {"unit_id": "U1", "label": "preflight", "tier": {"model": "haiku", "effort": "low"}},
            {
                "unit_id": "U2",
                "label": "build",
                "tier": {"model": "sonnet", "effort": "high"},
                "depends_on": ["U1"],
            },
        ],
    }


def test_team_execution_artifact_wires_team_emitter() -> None:
    spec = ES.ExecutionSpec.from_dict(_execution_spec_dict())
    art = D.team_execution_artifact(spec)
    assert "Team Structure" in art  # produced through recompile_for_tier's team_emitter leg (R5)
    assert "U1" in art and "U2" in art  # units preserved (by unit id)


# --------------------------------------------------------------------------- integration with advance


@pytest.fixture
def repo(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    common = tmp_path / ".git"
    common.mkdir()
    monkeypatch.setattr(
        OUTCOME.outcome_store.subprocess,
        "run",
        lambda args, **kw: SimpleNamespace(returncode=0, stdout=str(common) + "\n", stderr=""),
    )
    return tmp_path


def test_advance_dispatches_team_execution_node(repo: Path) -> None:
    OUTCOME.start(
        repo,
        "ship-x",
        "Ship X",
        nodes=[{"subplot_id": "build", "title": "Build", "backend": "team-execution"}],
    )
    result = OUTCOME.advance(repo, "ship-x", dispatcher=D.make_dispatcher())
    assert result.dispatched == ["build"]
    assert OUTCOME.attend(repo, "ship-x", "build") == "/resume leaf-ship-x-build"


def test_advance_halts_visibly_on_unavailable_backend_no_silent_substitute(repo: Path) -> None:
    OUTCOME.start(
        repo,
        "ship-x",
        "Ship X",
        nodes=[{"subplot_id": "build", "title": "Build", "backend": "fork"}],
    )
    # The reconcile loop catches the HALT per-leaf: surfaced in result.halted (visible), nothing
    # dispatched, nothing silently substituted to inline.
    result = OUTCOME.advance(repo, "ship-x", dispatcher=D.make_dispatcher())
    assert result.dispatched == []
    assert len(result.halted) == 1 and result.halted[0]["backend"] == "fork"
    store = STORE.Store.for_outcome("ship-x", repo)
    assert STORE.completed_subplots(store) == set()


def test_halt_does_not_leak_dispatch_lease_resurfaces_each_advance(repo: Path) -> None:
    # P1 regression: a HALT must release the per-subplot dispatch lock so the NEXT advance re-attempts
    # and re-surfaces the HALT, rather than the leaked lease silently masking it for the lease TTL.
    OUTCOME.start(
        repo,
        "ship-x",
        "Ship X",
        nodes=[{"subplot_id": "build", "title": "Build", "backend": "fork"}],
    )
    r1 = OUTCOME.advance(repo, "ship-x", dispatcher=D.make_dispatcher())
    r2 = OUTCOME.advance(repo, "ship-x", dispatcher=D.make_dispatcher())
    assert len(r1.halted) == 1 and len(r2.halted) == 1  # re-surfaced, not masked by a leaked lease


def test_halt_does_not_starve_other_runnable_leaves(repo: Path) -> None:
    # P2 regression: one HALT leaf must NOT abort the whole tick — independent runnable leaves still
    # dispatch in the same advance.
    OUTCOME.start(
        repo,
        "ship-x",
        "Ship X",
        nodes=[
            {"subplot_id": "a", "title": "A", "backend": "team-execution"},
            {"subplot_id": "b", "title": "B", "backend": "fork"},
        ],
    )
    result = OUTCOME.advance(repo, "ship-x", dispatcher=D.make_dispatcher())
    assert result.dispatched == ["a"]  # the runnable leaf dispatched despite b's HALT
    assert [h["subplot_id"] for h in result.halted] == ["b"]


def test_cli_advance_uses_the_real_backend_seam(
    repo: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    # R5: the production /outcome advance routes through the real seam, not the U3 record-only default.
    OUTCOME.start(
        repo,
        "ship-x",
        "Ship X",
        nodes=[{"subplot_id": "build", "title": "Build", "backend": "fork"}],
    )
    # R20 approval gate is upstream of the backend HALT — approve the frontier first so the leaf
    # actually reaches the dispatcher seam (an unapproved leaf is gated, never HALTed).
    assert OUTCOME.main(["--repo-root", str(repo), "approve", "ship-x"]) == 0
    capsys.readouterr()
    rc = OUTCOME.main(["--repo-root", str(repo), "advance", "ship-x"])
    assert rc == 0
    out = json.loads(capsys.readouterr().out)
    assert (
        out["dispatched"] == [] and len(out["halted"]) == 1
    )  # the seam HALTed fork, didn't dispatch


# --------------------------------------------------------------------------- CLI


def test_cli_dispatch_dry_run(capsys: pytest.CaptureFixture[str]) -> None:
    assert D.main(["ship-x", "build", "team-execution"]) == 0
    out = json.loads(capsys.readouterr().out)
    assert out["status"] == "dispatched" and out["return_channel"] == "/resume leaf-ship-x-build"
    assert D.main(["ship-x", "build", "fork"]) == 0
    halt = json.loads(capsys.readouterr().out)
    assert halt["status"] == "halt"
