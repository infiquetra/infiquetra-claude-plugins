"""Integration proof for the capability-scoped sandbox (#287 U6, R8/R9).

Three layers:

(a) mechanism -- a real disposable git worktree contains a ``git checkout`` clobber, so the
    primary tree's uncommitted work survives (the ``{#verify-agent-git-checkout-clobber}``
    incident that motivated this feature). A control case proves the clobber IS destructive when
    run in the primary tree, so the containment assertion is not vacuous.
(b) wiring -- the emitted verify-panel workflow script carries the readonly-verifier agentType +
    worktree isolation end-to-end from a spec fixture (the dead-wiring guard, R9).
(c) no-escalation -- applying a sandbox never grants a tool/mode/path the unsandboxed form lacked
    (R8): a read-only sandbox never expands agy's writes, and codex never gains write.
"""

from __future__ import annotations

import importlib.util
import subprocess
import sys
from pathlib import Path
from types import ModuleType

import pytest

ROOT = Path(__file__).parent.parent
SCRIPT_DIR = ROOT / "plugins" / "saga" / "scripts"


def _load(name: str) -> ModuleType:
    if str(SCRIPT_DIR) not in sys.path:
        sys.path.insert(0, str(SCRIPT_DIR))
    spec = importlib.util.spec_from_file_location(name, SCRIPT_DIR / f"{name}.py")
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


ES = _load("execution_spec")
ED = _load("engine_dispatch")
RES = _load("engine_resolver")


# --------------------------------------------------------------------------- git helpers


def _git(repo: Path, *args: str) -> str:
    result = subprocess.run(
        ["git", "-C", str(repo), *args], capture_output=True, text=True, check=True
    )
    return result.stdout


def _init_repo_with_tracked_file(root: Path) -> Path:
    repo = root / "primary"
    repo.mkdir()
    _git(repo, "init", "-q")
    _git(repo, "config", "user.email", "t@example.com")
    _git(repo, "config", "user.name", "Test")
    (repo / "tracked.txt").write_text("committed content\n", encoding="utf-8")
    _git(repo, "add", "tracked.txt")
    _git(repo, "commit", "-q", "-m", "initial")
    return repo


# --------------------------------------------------------------------- (a) mechanism


def test_clobber_contained_disposable_worktree_protects_primary_tree(tmp_path: Path) -> None:
    repo = _init_repo_with_tracked_file(tmp_path)
    tracked = repo / "tracked.txt"
    # Uncommitted edit in the PRIMARY working tree -- the work a verify agent must not destroy.
    tracked.write_text("PRECIOUS uncommitted work\n", encoding="utf-8")

    # Provision a disposable worktree (what isolation: 'worktree' does for a verifier).
    wt = tmp_path / "verifier-wt"
    _git(repo, "worktree", "add", "-q", "--detach", str(wt), "HEAD")

    # The clobber: `git checkout -- tracked.txt` run INSIDE the worktree. In the primary tree this
    # wipes the uncommitted edit; in the worktree it only resets the worktree's own copy.
    _git(wt, "checkout", "--", "tracked.txt")

    # Load-bearing assertion: the primary tree's uncommitted work is intact.
    assert tracked.read_text(encoding="utf-8") == "PRECIOUS uncommitted work\n"
    # The worktree's copy WAS reset to committed content (the checkout ran, just contained).
    assert (wt / "tracked.txt").read_text(encoding="utf-8") == "committed content\n"


def test_clobber_would_destroy_in_primary_tree_control(tmp_path: Path) -> None:
    # Control: the SAME checkout run in the primary tree DOES wipe uncommitted work -- proving the
    # worktree-contained assertion above is load-bearing, not vacuous.
    repo = _init_repo_with_tracked_file(tmp_path)
    tracked = repo / "tracked.txt"
    tracked.write_text("PRECIOUS uncommitted work\n", encoding="utf-8")
    _git(repo, "checkout", "--", "tracked.txt")  # run in the PRIMARY tree -> clobbers
    assert tracked.read_text(encoding="utf-8") == "committed content\n"  # the work is GONE


def test_clobber_contained_worktree_is_discardable(tmp_path: Path) -> None:
    repo = _init_repo_with_tracked_file(tmp_path)
    wt = tmp_path / "verifier-wt"
    _git(repo, "worktree", "add", "-q", "--detach", str(wt), "HEAD")
    _git(repo, "worktree", "remove", "--force", str(wt))
    assert not wt.exists()
    # Discarding the disposable worktree leaves the primary tree fully intact.
    assert (repo / "tracked.txt").read_text(encoding="utf-8") == "committed content\n"


# --------------------------------------------------------------------- (b) wiring


def _emit(units: list[dict[str, object]]) -> str:
    spec = ES.ExecutionSpec.from_dict(
        {"name": "u6", "description": "d", "repo": "/tmp/r", "units": units}
    )
    spec.validate()
    return ES.emit_workflow_script(spec)


def test_verify_panel_wiring_end_to_end_carries_isolation_and_agenttype() -> None:
    script = _emit(
        [
            {
                "unit_id": "u",
                "label": "u",
                "tier": {"model": "opus", "effort": "high"},
                "prompt": "p",
                "returns": ["r"],
                "verify": {"n": 2, "pass_rule": "majority"},
            }
        ]
    )
    assert 'agentType: "saga:readonly-verifier"' in script
    assert 'isolation: "worktree"' in script


def test_capability_axes_profile_composition() -> None:
    ro = ES.Sandbox.from_dict("read-only-verify", "w")
    sm = ES.Sandbox.from_dict("sandboxed-mutate", "w")
    assert (ro.mutation_policy, ro.workspace_isolation) == ("read-only", "disposable-worktree")
    assert (sm.mutation_policy, sm.workspace_isolation) == ("read-write", "owned-worktree")
    assert ro.is_restrictive and sm.is_restrictive
    default = ES.Sandbox(mutation_policy="read-write", workspace_isolation="ambient")
    assert not default.is_restrictive


# --------------------------------------------------------------------- (c) no-escalation (R8)


def _res(engine: str) -> object:
    return RES.Resolution(
        engine_id=engine,
        variant="v",
        effort="high",
        recipe="r",
        protocol=["P"],
        payload="task",
        write_capable=True,
        fallback=None,
        halt=None,
    )


def test_no_escalation_read_only_sandbox_grants_no_agy_writes() -> None:
    # A read-only sandbox never expands agy's write posture beyond the unsandboxed default.
    baseline = ED.build_agy_envelope(_res("agy"), model="opus")
    ro = ES.Sandbox.from_dict("read-only-verify", "w")
    sandboxed = ED.build_agy_envelope(_res("agy"), model="opus", sandbox=ro, write_set=["a.py"])
    assert sandboxed["mode"] == baseline["mode"] == "no-write"
    assert sandboxed["write_set"] == baseline["write_set"] == []


def test_no_escalation_codex_never_gains_write_under_any_profile() -> None:
    read_only = ES.Sandbox.from_dict("read-only-verify", "w")
    assert ED.build_codex_invocation(_res("codex"), sandbox=read_only)["sandbox"] == "read-only"
    write_mode = ES.Sandbox.from_dict("sandboxed-mutate", "w")
    with pytest.raises(ED.DispatchError):
        ED.build_codex_invocation(_res("codex"), sandbox=write_mode)


def test_agy_write_set_is_passed_through_verbatim_not_expanded() -> None:
    # The builder passes write_set through exactly as given -- it never ADDS paths. Clamping the
    # write_set to the unit's DECLARED files is the CALLER's contract (the chaperone passes
    # unit.files as write_set); the builder receives no unit.files and does not itself clamp.
    sm = ES.Sandbox.from_dict("sandboxed-mutate", "w")
    env = ED.build_agy_envelope(_res("agy"), model="opus", sandbox=sm, write_set=["only.py"])
    assert env["write_set"] == ["only.py"]
