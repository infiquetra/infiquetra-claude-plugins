"""Tests for the durable per-sub-outcome worktree lifecycle + the worktree-removed terminal (U7).

Pins R15 (one durable named+owned worktree per sub-outcome, reused across leaves not one-per-leaf;
cap-bounded; reaped on terminal; shared install ref), R32-worktree (a worktree removed out-of-band ->
a defined ``rejected`` terminal), R22 (the removed terminal cascades to its downstream subtree), and
R34 (a transient git failure degrades to present — never falsely terminates a live sub-outcome).
"""

from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path
from types import ModuleType, SimpleNamespace
from typing import Any

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


# Load in dependency order so every lazy `import outcome` / sibling import reuses these instances.
SPEC = _load("outcome_spec")
STORE = _load("outcome_store")
ORCH = _load("outcome_orchestrator")
_load("outcome_dispatcher")
_load("outcome_merge")
ENG = _load("outcome")
WT = _load("outcome_worktrees")


def _store(tmp_path: Path) -> Any:
    return STORE.Store(root=tmp_path / "store").ensure()


def _spec(nodes: list[dict[str, Any]]) -> Any:
    return SPEC.OutcomeSpec.from_dict({"outcome_id": "o", "objective": "x", "nodes": nodes})


def _sub(sid: str, **kw: Any) -> dict[str, Any]:
    """A sub-outcome node dict (child_spec_ref set so Node.is_outcome is True)."""
    return {"subplot_id": sid, "title": sid, "kind": "code", "child_spec_ref": f"child-{sid}", **kw}


class FakeWT:
    """A fake WorktreeOps backed by an in-memory set of live paths (git is simulated)."""

    def __init__(self, *, exists_override: Any = None) -> None:
        self.paths: set[str] = set()
        self.removed: list[str] = []
        self._exists_override = exists_override

    def _add(self, path: str, _branch: str) -> bool:
        self.paths.add(path)
        return True

    def _remove(self, path: str) -> bool:
        self.paths.discard(path)
        self.removed.append(path)
        return True

    def _exists(self, path: str) -> bool:
        if self._exists_override is not None:
            return bool(self._exists_override(path))
        return path in self.paths

    def ops(self) -> Any:
        return WT.WorktreeOps(
            add=self._add,
            remove=self._remove,
            exists=self._exists,
            list_paths=lambda: sorted(self.paths),
        )


# --------------------------------------------------------------------------- names / paths


def test_names_and_paths_are_deterministic_and_namespaced() -> None:
    assert WT.worktree_name("o", "s1") == "saga-outcome-o-s1"
    p = WT.worktree_path(Path("/repo"), "o", "s1")
    assert p == Path("/repo/.saga-worktrees/o/s1")
    # the shared install ref is one path per OUTCOME (reused by every sibling worktree, R15)
    assert WT.shared_install_ref(Path("/repo"), "o") == "/repo/.saga-worktrees/o/_shared-install"


# --------------------------------------------------------------------------- ensure (R15)


def test_plain_leaf_is_not_managed(tmp_path: Path) -> None:
    spec = _spec([{"subplot_id": "p", "title": "p", "kind": "code"}])  # no child_spec_ref
    out = WT.ensure_worktree(
        tmp_path, spec, _store(tmp_path), spec.nodes[0], FakeWT().ops(), owner="me"
    )
    assert out.state == "skipped-not-suboutcome"


def test_suboutcome_creates_once_then_reuses(tmp_path: Path) -> None:
    spec = _spec([_sub("s1")])
    store = _store(tmp_path)
    ops = FakeWT().ops()
    first = WT.ensure_worktree(tmp_path, spec, store, spec.nodes[0], ops, owner="me")
    assert first.state == "created"
    second = WT.ensure_worktree(tmp_path, spec, store, spec.nodes[0], ops, owner="me")
    assert second.state == "reused"  # one durable worktree, reused across the child's leaves (R15)
    assert second.path == first.path


def test_cap_defers_never_overshoots(tmp_path: Path) -> None:
    spec = _spec([_sub("s1"), _sub("s2")])
    store = _store(tmp_path)
    ops = FakeWT().ops()
    assert (
        WT.ensure_worktree(tmp_path, spec, store, spec.nodes[0], ops, owner="me", cap=1).state
        == "created"
    )
    capped = WT.ensure_worktree(tmp_path, spec, store, spec.nodes[1], ops, owner="me", cap=1)
    assert capped.state == "capped"  # past the cap -> defer + page, never an (N+1)th worktree
    assert (
        WT.ensure_worktree(tmp_path, spec, store, spec.nodes[1], ops, owner="me", cap=2).state
        == "created"
    )


def test_siblings_share_one_install_ref_and_are_owner_tagged(tmp_path: Path) -> None:
    spec = _spec([_sub("s1"), _sub("s2")])
    store = _store(tmp_path)
    ops = FakeWT().ops()
    WT.ensure_worktree(tmp_path, spec, store, spec.nodes[0], ops, owner="alice", cap=4)
    WT.ensure_worktree(tmp_path, spec, store, spec.nodes[1], ops, owner="alice", cap=4)
    reg = WT.read_registry(store)
    assert (
        reg["s1"]["shared_install_ref"] == reg["s2"]["shared_install_ref"]
    )  # shared installs (R15)
    assert reg["s1"]["owner"] == reg["s2"]["owner"] == "alice"  # named + owner-tagged
    assert reg["s1"]["branch"] == "saga-outcome-o-s1"


def test_stale_registry_entry_is_dropped_then_recreated(tmp_path: Path) -> None:
    spec = _spec([_sub("s1")])
    store = _store(tmp_path)
    fw = FakeWT()
    ops = fw.ops()
    WT.ensure_worktree(tmp_path, spec, store, spec.nodes[0], ops, owner="me")
    # simulate the worktree vanishing out-of-band, then a re-ensure: stale entry dropped, recreated
    fw.paths.clear()
    again = WT.ensure_worktree(tmp_path, spec, store, spec.nodes[0], ops, owner="me")
    assert again.state == "created"  # not wedged on the stale record


# --------------------------------------------------------------------------- reap (R15)


def test_reap_removes_and_deregisters_idempotently(tmp_path: Path) -> None:
    spec = _spec([_sub("s1")])
    store = _store(tmp_path)
    fw = FakeWT()
    ops = fw.ops()
    WT.ensure_worktree(tmp_path, spec, store, spec.nodes[0], ops, owner="me")
    assert WT.reap_worktree(store, "s1", ops) is True
    assert "s1" not in WT.read_registry(store)
    assert WT.reap_worktree(store, "s1", ops) is False  # idempotent — nothing left to reap


def _ops_remove_fails() -> Any:
    """An ops whose remove always fails (a stuck/locked worktree that survives --force)."""
    return WT.WorktreeOps(
        add=lambda _p, _b: True,
        remove=lambda _p: False,
        exists=lambda _p: True,
        list_paths=list,
    )


def test_reap_keeps_the_entry_when_removal_fails(tmp_path: Path) -> None:
    # P2 regression: a failed ops.remove() must NOT deregister — that would silently leak the worktree
    # (drop it from the registry/cap accounting while it survives on disk).
    store = _store(tmp_path)
    WT.register(store, "s1", {"path": str(WT.worktree_path(tmp_path, "o", "s1")), "branch": "x"})
    assert WT.reap_worktree(store, "s1", _ops_remove_fails()) is False
    assert "s1" in WT.read_registry(
        store
    )  # entry retained so a later pass retries (no silent leak)


# --------------------------------------------------------------------------- harvest (R15 reap + R32 + R22)


def _completed(store: Any, sid: str, state: str = "done") -> None:
    STORE.write_completion_event(
        store,
        STORE.CompletionEvent(subplot_id=sid, state=state, idempotency_key=f"k:{sid}:{state}"),
    )


def test_harvest_reaps_terminal_suboutcome_worktrees(tmp_path: Path) -> None:
    spec = _spec([_sub("s1")])
    store = _store(tmp_path)
    fw = FakeWT()
    ops = fw.ops()
    WT.ensure_worktree(tmp_path, spec, store, spec.nodes[0], ops, owner="me")
    _completed(store, "s1", "done")  # s1 reaches a terminal -> its worktree is reaped
    res = WT.harvest_worktrees(spec, store, ops)
    assert res["reaped"] == ["s1"] and "s1" not in WT.read_registry(store)


def test_removed_worktree_becomes_rejected_terminal_and_cascades(tmp_path: Path) -> None:
    # R32 (the terminal U6 deferred) + R22: a vanished worktree -> rejected; its downstream cascades.
    spec = _spec(
        [
            _sub("s1"),
            {"subplot_id": "dep", "title": "dep", "kind": "code", "depends_on": ["s1"]},
            {"subplot_id": "indep", "title": "indep", "kind": "code"},  # not downstream of s1
        ]
    )
    store = _store(tmp_path)
    fw = FakeWT()
    ops = fw.ops()
    WT.ensure_worktree(tmp_path, spec, store, spec.nodes[0], ops, owner="me")
    fw.paths.clear()  # worktree removed out-of-band (git no longer lists it)
    res = WT.harvest_worktrees(spec, store, ops)
    assert res["removed"] == ["s1"]
    assert res["cascade_paused"] == [
        "dep"
    ]  # only s1's downstream pauses; indep keeps running (R22)
    assert ENG.derive_states(spec, store)["s1"] == "rejected"  # the defined terminal (R32)


def test_transient_git_failure_does_not_terminate_a_live_suboutcome(tmp_path: Path) -> None:
    # R34: ops.exists degraded to True (a flake) must NOT fire the removed terminal.
    spec = _spec([_sub("s1")])
    store = _store(tmp_path)
    fw = FakeWT(exists_override=lambda _p: True)  # git "always present" (flake degrades to present)
    ops = fw.ops()
    WT.ensure_worktree(tmp_path, spec, store, spec.nodes[0], ops, owner="me")
    res = WT.harvest_worktrees(spec, store, ops)
    assert res["removed"] == []  # never falsely terminated
    assert "rejected" not in {e.state for e in STORE.read_completion_events(store, "s1")}


def test_removed_terminal_is_idempotent(tmp_path: Path) -> None:
    spec = _spec([_sub("s1")])
    store = _store(tmp_path)
    fw = FakeWT()
    ops = fw.ops()
    WT.ensure_worktree(tmp_path, spec, store, spec.nodes[0], ops, owner="me")
    fw.paths.clear()
    WT.harvest_worktrees(spec, store, ops)
    WT.harvest_worktrees(spec, store, ops)  # re-run
    assert sum(e.state == "rejected" for e in STORE.read_completion_events(store, "s1")) == 1


def test_harvest_reaps_a_node_gone_orphan(tmp_path: Path) -> None:
    # P2 regression: a registry entry whose node left the spec (pruned away another path) must be
    # reaped + deregistered, not skipped forever holding a cap slot.
    spec = _spec([_sub("s1")])
    store = _store(tmp_path)
    fw = FakeWT()
    ops = fw.ops()
    WT.ensure_worktree(tmp_path, spec, store, spec.nodes[0], ops, owner="me")
    # s1 is gone from the spec, but its worktree is still registered
    gone_spec = _spec([{"subplot_id": "other", "title": "other", "kind": "code"}])
    res = WT.harvest_worktrees(gone_spec, store, ops)
    assert res["orphaned"] == ["s1"] and "s1" not in WT.read_registry(store)


# --------------------------------------------------------------------------- provision_pending (R15)


def test_provision_only_dispatched_suboutcomes(tmp_path: Path) -> None:
    spec = _spec([_sub("s1"), _sub("s2")])
    store = _store(tmp_path)
    ops = FakeWT().ops()
    # mark s1 dispatched via a commit ledger record; s2 stays ready (undispatched)
    STORE.append_ledger(
        store,
        {
            "phase": "commit",
            "kind": "dispatch",
            "key": "dispatch:s1",
            "subplot_id": "s1",
            "leaf_saga_id": "leaf-s1",
        },
    )
    res = WT.provision_pending(tmp_path, spec, store, ops, owner="me", cap=4)
    assert res["provisioned"] == ["s1"] and res["deferred"] == []  # only the dispatched one
    assert "s2" not in WT.read_registry(store)


def test_provision_defers_past_cap(tmp_path: Path) -> None:
    spec = _spec([_sub("s1"), _sub("s2")])
    store = _store(tmp_path)
    ops = FakeWT().ops()
    for sid in ("s1", "s2"):
        STORE.append_ledger(
            store,
            {
                "phase": "commit",
                "kind": "dispatch",
                "key": f"dispatch:{sid}",
                "subplot_id": sid,
                "leaf_saga_id": f"leaf-{sid}",
            },
        )
    res = WT.provision_pending(tmp_path, spec, store, ops, owner="me", cap=1)
    assert res["provisioned"] == ["s1"] and res["deferred"] == [
        "s2"
    ]  # cap bounds it, the rest defers


# --------------------------------------------------------------------------- real git adapter (degrade-safe)


def _git_runner(out: str = "", *, rc: int = 0, err: str = "") -> Any:
    return lambda args, **kw: SimpleNamespace(returncode=rc, stdout=out, stderr=err)


def test_real_exists_degrades_to_present_on_git_failure(tmp_path: Path) -> None:
    # git unreadable -> exists() degrades to True (never falsely terminate a live sub-outcome, R34).
    ops = WT.git_worktree_ops(tmp_path, runner=_git_runner(rc=1, err="fatal: not a git repo"))
    assert ops.exists("/anything") is True


def test_real_exists_true_only_when_git_lists_the_path(tmp_path: Path) -> None:
    listing = "worktree /repo/.saga-worktrees/o/s1\nbranch refs/heads/saga-outcome-o-s1\n"
    ops = WT.git_worktree_ops(tmp_path, runner=_git_runner(listing))
    assert ops.exists("/repo/.saga-worktrees/o/s1") is True
    assert ops.exists("/repo/.saga-worktrees/o/missing") is False  # definite absence


def test_real_remove_is_idempotent_when_path_already_gone(tmp_path: Path) -> None:
    # a non-zero `git worktree remove` on an already-absent path is still success (idempotent reaping).
    ops = WT.git_worktree_ops(tmp_path, runner=_git_runner(rc=1, err="is not a working tree"))
    assert ops.remove(str(tmp_path / "definitely-absent")) is True


def test_real_git_adapter_sees_a_live_worktree_under_a_symlinked_root(tmp_path: Path) -> None:
    # P0 regression: with the REAL `git worktree` against a symlinked/relative repo_root, a LIVE
    # on-disk worktree must read as PRESENT — a verbatim string compare read it ABSENT, silently
    # breaking the R15 cap (unbounded fan-out) AND R34 (live sub-outcomes falsely terminated).
    import subprocess

    repo = tmp_path / "repo"
    repo.mkdir()
    subprocess.run(["git", "init", "-q"], cwd=repo, check=True)
    env = {
        "GIT_AUTHOR_NAME": "t",
        "GIT_AUTHOR_EMAIL": "t@t",
        "GIT_COMMITTER_NAME": "t",
        "GIT_COMMITTER_EMAIL": "t@t",
        "PATH": __import__("os").environ["PATH"],
    }
    subprocess.run(
        ["git", "commit", "-q", "--allow-empty", "-m", "init"], cwd=repo, check=True, env=env
    )
    # a symlink to the repo forces the path divergence the P0 was about (link != realpath)
    link = tmp_path / "link"
    link.symlink_to(repo)
    ops = WT.git_worktree_ops(link)
    store = _store(tmp_path)

    spec = _spec([_sub("s1")])
    created = WT.ensure_worktree(link, spec, store, spec.nodes[0], ops, owner="me")
    assert created.state == "created"
    reg = WT.read_registry(store)
    # the live worktree reads PRESENT despite the symlinked/relative registry path (the P0 fix)
    assert ops.exists(reg["s1"]["path"]) is True
    assert WT.live_worktrees(store, ops) == {"s1"}
    # harvest does NOT falsely terminate the live sub-outcome (R34) and does not reap it (non-terminal)
    res = WT.harvest_worktrees(spec, store, ops)
    assert res["removed"] == [] and res["reaped"] == []
    assert ENG.derive_states(spec, store)["s1"] != "rejected"
    # and the cap is now actually enforceable (it counts the live worktree)
    spec2 = _spec([_sub("s1"), _sub("s2")])
    capped = WT.ensure_worktree(link, spec2, store, spec2.nodes[1], ops, owner="me", cap=1)
    assert capped.state == "capped"  # not an unbounded (N+1)th worktree


def test_cli_describes_policy(capsys: Any) -> None:
    assert WT.main(["--cap", "7"]) == 0
    out = json.loads(capsys.readouterr().out)
    assert out["worktree_cap"] == 7 and out["removed_terminal"] == "rejected"
