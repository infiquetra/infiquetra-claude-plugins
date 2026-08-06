"""Tests for the durable per-sub-outcome worktree lifecycle + the worktree-removed terminal (U7).

Pins R15 (one durable named+owned worktree per sub-outcome, reused across leaves not one-per-leaf;
cap-bounded; reaped on terminal; shared install ref), R32-worktree (a worktree removed out-of-band ->
a defined ``rejected`` terminal), R22 (the removed terminal cascades to its downstream subtree), and
R34 (a transient git failure degrades to present — never falsely terminates a live sub-outcome).

Broker-free since #677/U3: the registry entry IS the reap authority, single-writer safety comes from
caller discipline (one ``advance`` tick per outcome), and abandoned worktrees are reclaimed by the
operator through the manual path in ``plugins/saga/references/worktree-reclamation.md`` — pinned here
by the ``reclaim_candidates`` inventory tests and the end-to-end manual reclamation test.
"""

from __future__ import annotations

import importlib.util
import json
import os
import subprocess
import sys
from pathlib import Path
from types import ModuleType, SimpleNamespace
from typing import Any, cast

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


def _dispatched(store: Any, sid: str) -> None:
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


def test_stale_worktree_debits_are_read_only(tmp_path: Path) -> None:
    store = _store(tmp_path)
    WT.register(
        store,
        "s1",
        {"path": str(WT.worktree_path(tmp_path, "o", "s1")), "branch": "branch-s1"},
    )
    registry_before = WT._registry_path(store).read_bytes()
    debits = WT.stale_worktree_debits(store, FakeWT().ops(), outcome_id="o")
    assert debits == [
        {
            "dispatch_id": "outcome:o:worktrees",
            "unit_id": "s1",
            "attempt": 1,
            "worktree": str(WT.worktree_path(tmp_path, "o", "s1")),
        }
    ]
    assert WT._registry_path(store).read_bytes() == registry_before


def test_stale_worktree_debits_leave_malformed_registry_untouched(tmp_path: Path) -> None:
    store = _store(tmp_path)
    registry = WT._registry_path(store)
    registry.write_text("{broken\n", encoding="utf-8")

    with pytest.raises(WT.WorktreeError, match="without repair"):
        WT.stale_worktree_debits(store, FakeWT().ops(), outcome_id="o")

    assert registry.read_text(encoding="utf-8") == "{broken\n"
    assert list(store.quarantine_dir.iterdir()) == []


def test_provisioning_persists_registry_before_physical_add(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    # The registry record is the ONLY ownership record left (#677/U3) — it must be written before
    # the physical add so a crash after ``ops.add`` cannot strand an unregistered worktree.
    spec = _spec([_sub("s1")])
    store = _store(tmp_path)
    fw = FakeWT()

    def fail_register(*_args: Any, **_kwargs: Any) -> None:
        raise OSError("registry unavailable")

    monkeypatch.setattr(WT, "register", fail_register)
    with pytest.raises(OSError, match="registry unavailable"):
        WT.ensure_worktree(tmp_path, spec, store, spec.nodes[0], fw.ops(), owner="coordinator")
    assert fw.paths == set()


def test_uncertain_add_failure_retains_registry_for_retry(tmp_path: Path) -> None:
    spec = _spec([_sub("s1")])
    store = _store(tmp_path)
    uncertain = WT.WorktreeOps(
        add=lambda _path, _branch: False,
        remove=lambda _path: False,
        exists=lambda _path: True,
        list_paths=list,
    )

    with pytest.raises(WT.WorktreeError, match="registry entry retained"):
        WT.ensure_worktree(tmp_path, spec, store, spec.nodes[0], uncertain, owner="coordinator")
    assert "s1" in WT.read_registry(store)  # retained so a later pass retries (no silent leak)
    assert WT.reap_worktree(store, "s1", FakeWT().ops()) is True
    assert WT.read_registry(store) == {}


# --------------------------------------------------------------------------- registered_entry_strict (#677/U3 reap preflight)


def test_registered_entry_strict_absent_is_none(tmp_path: Path) -> None:
    assert WT.registered_entry_strict(_store(tmp_path), "nope") is None


def test_registered_entry_strict_returns_entry_and_binds_outcome(tmp_path: Path) -> None:
    store = _store(tmp_path)
    entry = {
        "path": str(WT.worktree_path(tmp_path, "o", "s1")),
        "branch": "branch-s1",
        "outcome_id": "o",
    }
    WT.register(store, "s1", entry)
    assert WT.registered_entry_strict(store, "s1") == entry
    assert WT.registered_entry_strict(store, "s1", expected_outcome_id="o") == entry


def test_registered_entry_strict_refuses_an_outcome_mismatch(tmp_path: Path) -> None:
    store = _store(tmp_path)
    WT.register(
        store,
        "s1",
        {"path": str(WT.worktree_path(tmp_path, "o", "s1")), "outcome_id": "other-outcome"},
    )
    with pytest.raises(WT.WorktreeError, match="does not match"):
        WT.registered_entry_strict(store, "s1", expected_outcome_id="o")


def test_registered_entry_strict_refuses_a_missing_outcome_id(tmp_path: Path) -> None:
    store = _store(tmp_path)
    WT.register(store, "s1", {"path": str(WT.worktree_path(tmp_path, "o", "s1"))})
    with pytest.raises(WT.WorktreeError, match="lacks outcome_id"):
        WT.registered_entry_strict(store, "s1", expected_outcome_id="o")


def test_registered_entry_strict_surfaces_corruption_without_repair(tmp_path: Path) -> None:
    store = _store(tmp_path)
    registry = WT._registry_path(store)
    registry.write_text("{broken\n", encoding="utf-8")
    with pytest.raises(WT.WorktreeError, match="without repair"):
        WT.registered_entry_strict(store, "s1")
    assert registry.read_text(encoding="utf-8") == "{broken\n"  # surfaced, never repaired
    assert list(store.quarantine_dir.iterdir()) == []


def test_vestigial_lease_field_is_inert_data(tmp_path: Path) -> None:
    # A pre-retirement registry entry may still carry a ``lease`` receipt (#677/U3): it is never
    # read and never a reap blocker — the registry entry IS the reap authority now.
    store = _store(tmp_path)
    WT.register(
        store,
        "s1",
        {
            "path": str(WT.worktree_path(tmp_path, "o", "s1")),
            "branch": "branch-s1",
            "lease": {"lease_id": "lease-1", "token": "tok-1"},
        },
    )
    assert WT.reap_worktree(store, "s1", FakeWT().ops()) is True
    assert WT.read_registry(store) == {}


# --------------------------------------------------------------------------- reap (R15)


def test_reap_unknown_subplot_is_false(tmp_path: Path) -> None:
    assert WT.reap_worktree(_store(tmp_path), "nope", FakeWT().ops()) is False


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


def test_harvest_reap_failure_retries_next_pass(tmp_path: Path) -> None:
    # The broker-free replacement for the lease-reconcile retry loop: a failed removal keeps the
    # entry (reap_failed), and the NEXT pass reaps it once the removal succeeds.
    spec = _spec([_sub("s1")])
    store = _store(tmp_path)
    fw = FakeWT()
    WT.ensure_worktree(tmp_path, spec, store, spec.nodes[0], fw.ops(), owner="me")
    _completed(store, "s1", "done")
    first = WT.harvest_worktrees(spec, store, _ops_remove_fails())
    assert first["reap_failed"] == ["s1"] and first["reaped"] == []
    assert "s1" in WT.read_registry(store)  # retained, not silently leaked
    second = WT.harvest_worktrees(spec, store, fw.ops())
    assert second["reaped"] == ["s1"] and WT.read_registry(store) == {}


# --------------------------------------------------------------------------- provision_pending (R15)


def test_provision_only_dispatched_suboutcomes(tmp_path: Path) -> None:
    spec = _spec([_sub("s1"), _sub("s2")])
    store = _store(tmp_path)
    ops = FakeWT().ops()
    _dispatched(store, "s1")  # s1 dispatched; s2 stays ready (undispatched)
    res = WT.provision_pending(tmp_path, spec, store, ops, owner="me", cap=4)
    assert res["provisioned"] == ["s1"] and res["deferred"] == []  # only the dispatched one
    assert "s2" not in WT.read_registry(store)


def test_provision_defers_past_cap(tmp_path: Path) -> None:
    spec = _spec([_sub("s1"), _sub("s2")])
    store = _store(tmp_path)
    ops = FakeWT().ops()
    for sid in ("s1", "s2"):
        _dispatched(store, sid)
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


def _init_git_repo(tmp_path: Path) -> Path:
    repo = tmp_path / "repo"
    repo.mkdir()
    subprocess.run(["git", "init", "-q"], cwd=repo, check=True)
    env = {
        "GIT_AUTHOR_NAME": "t",
        "GIT_AUTHOR_EMAIL": "t@t",
        "GIT_COMMITTER_NAME": "t",
        "GIT_COMMITTER_EMAIL": "t@t",
        "PATH": os.environ["PATH"],
    }
    subprocess.run(
        ["git", "commit", "-q", "--allow-empty", "-m", "init"], cwd=repo, check=True, env=env
    )
    return repo


def test_real_git_adapter_sees_a_live_worktree_under_a_symlinked_root(tmp_path: Path) -> None:
    # P0 regression: with the REAL `git worktree` against a symlinked/relative repo_root, a LIVE
    # on-disk worktree must read as PRESENT — a verbatim string compare read it ABSENT, silently
    # breaking the R15 cap (unbounded fan-out) AND R34 (live sub-outcomes falsely terminated).
    repo = _init_git_repo(tmp_path)
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


def test_real_git_dead_worktree_reap_retries_without_losing_authority(tmp_path: Path) -> None:
    # Broker-free retry semantics (#677/U3): with REAL git, a harvest whose removal flakes keeps the
    # entry (no deregister, no lost authority), and the next pass completes the reap.
    repo = _init_git_repo(tmp_path)
    spec = _spec([_sub("s1"), _sub("s2")])
    store = _store(tmp_path)
    real_ops = WT.git_worktree_ops(repo)
    for node in spec.nodes:
        WT.ensure_worktree(repo, spec, store, node, real_ops, owner="coordinator", cap=2)
    for sid in ("s1", "s2"):
        _completed(store, sid, "done")
    paths = {sid: WT.read_registry(store)[sid]["path"] for sid in ("s1", "s2")}
    first_failure = True

    def flaky_remove(path: str) -> bool:
        nonlocal first_failure
        if path == paths["s1"] and first_failure:
            first_failure = False
            return False
        return cast(bool, real_ops.remove(path))

    flaky_ops = WT.WorktreeOps(
        add=real_ops.add,
        remove=flaky_remove,
        exists=real_ops.exists,
        list_paths=real_ops.list_paths,
    )
    first = WT.harvest_worktrees(spec, store, flaky_ops)
    assert sorted(first["reaped"]) == ["s2"]
    assert first["reap_failed"] == ["s1"]
    assert real_ops.exists(paths["s1"]) is True
    assert real_ops.exists(paths["s2"]) is False

    second = WT.harvest_worktrees(spec, store, real_ops)
    assert second["reaped"] == ["s1"]
    assert WT.read_registry(store) == {}
    assert not any(path in real_ops.list_paths() for path in paths.values())


# --------------------------------------------------------------------------- operator reclamation (#677/U3)


def _reclaim_runner(repo: Path, common: Path, listed: set[str]) -> Any:
    """A fake git runner for reclaim_candidates: rev-parse + worktree list only."""

    def runner(args: list[str], **_kw: Any) -> Any:
        if args[1:3] == ["rev-parse", "--git-common-dir"]:  # argv is ["git", ...]
            return SimpleNamespace(returncode=0, stdout=str(common), stderr="")
        if args[1:3] == ["worktree", "list"]:
            out = "".join(f"worktree {p}\n" for p in sorted(listed))
            return SimpleNamespace(returncode=0, stdout=out, stderr="")
        return SimpleNamespace(returncode=1, stdout="", stderr="unsupported")

    return runner


def test_reclaim_candidates_reports_all_three_states(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    repo.mkdir()
    common = repo / ".git"
    registry_dir = common / "saga-outcomes" / "o"
    registry_dir.mkdir(parents=True)
    live_path = str(WT.worktree_path(repo, "o", "live"))
    absent_path = str(WT.worktree_path(repo, "o", "ghost"))
    (registry_dir / "worktrees.json").write_text(
        json.dumps(
            {
                "worktrees": {
                    "live": {"outcome_id": "o", "path": live_path},
                    "ghost": {"outcome_id": "o", "path": absent_path},
                }
            }
        ),
        encoding="utf-8",
    )
    # an unregistered leftover on disk (and the shared-install ref, which must be skipped)
    stray = WT.worktrees_root(repo) / "o" / "stray"
    stray.mkdir(parents=True)
    (WT.worktrees_root(repo) / "o" / "_shared-install").mkdir()

    candidates = WT.reclaim_candidates(repo, runner=_reclaim_runner(repo, common, {live_path}))
    by_sid = {(c["subplot_id"], c["state"]): c for c in candidates}
    assert set(by_sid) == {("live", "live"), ("ghost", "path-absent"), ("stray", "unregistered")}
    assert by_sid[("stray", "unregistered")]["registry"] == ""  # claimed by no registry
    assert by_sid[("live", "live")]["registry"] == str(registry_dir / "worktrees.json")
    assert all(c["outcome_id"] == "o" for c in candidates)
    assert all(c["subplot_id"] != "_shared-install" for c in candidates)


def test_reclaim_list_cli_is_report_only(tmp_path: Path, capsys: Any) -> None:
    repo = tmp_path / "repo"
    repo.mkdir()
    assert WT.main(["--reclaim-list", "--repo-root", str(repo)]) == 0
    out = json.loads(capsys.readouterr().out)
    assert out == {"candidates": []}  # nothing under a bare repo — and nothing was removed


def test_manual_reclamation_procedure_end_to_end(tmp_path: Path) -> None:
    # The documented operator path (references/worktree-reclamation.md), exercised end to end with
    # REAL git: inventory reports the abandoned worktree live, the operator removes it by hand, and
    # the next harvest pass settles the sub-outcome onto the R32 rejected terminal.
    repo = _init_git_repo(tmp_path)
    spec = _spec([_sub("s1")])
    # The store must live where reclaim_candidates takes its census: <git-common-dir>/saga-outcomes.
    raw_common = Path(
        subprocess.run(
            ["git", "rev-parse", "--git-common-dir"],
            cwd=repo,
            capture_output=True,
            text=True,
            check=True,
        ).stdout.strip()
    )
    common = raw_common if raw_common.is_absolute() else (repo / raw_common).resolve()
    store_root = common / "saga-outcomes" / "o-store"
    store = STORE.Store(root=store_root).ensure()
    real_ops = WT.git_worktree_ops(repo)
    _dispatched(store, "s1")
    created = WT.ensure_worktree(repo, spec, store, spec.nodes[0], real_ops, owner="me")
    assert created.state == "created"
    path = WT.read_registry(store)["s1"]["path"]

    # Step 1 — the report-only inventory sees it LIVE.
    candidates = WT.reclaim_candidates(repo)
    assert [(c["subplot_id"], c["state"]) for c in candidates] == [("s1", "live")]

    # Step 2 — the operator removes it exactly as documented.
    subprocess.run(["git", "worktree", "remove", "--force", path], cwd=repo, check=True)
    subprocess.run(["git", "worktree", "prune"], cwd=repo, check=True)
    assert real_ops.exists(path) is False
    assert [(c["subplot_id"], c["state"]) for c in WT.reclaim_candidates(repo)] == [
        ("s1", "path-absent")
    ]

    # Consequence — the next harvest settles the entry; the sub-outcome reaches the R32 terminal.
    res = WT.harvest_worktrees(spec, store, real_ops)
    assert res["removed"] == ["s1"] and WT.read_registry(store) == {}
    assert ENG.derive_states(spec, store)["s1"] == WT.WORKTREE_REMOVED_STATE


# --------------------------------------------------------------------------- CLI


def test_cli_describes_policy(capsys: Any) -> None:
    assert WT.main(["--cap", "7"]) == 0
    out = json.loads(capsys.readouterr().out)
    assert out["worktree_cap"] == 7 and out["removed_terminal"] == "rejected"
    assert "worktree-reclamation.md" in out["policy"]  # the documented manual path is named
