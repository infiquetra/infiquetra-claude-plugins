"""Replay-ledger + crash-recovery + cache-loss oracles for the outcome store (U2).

These pin R30 (crash/replay: append-only ledger + idempotent reconcile) and R27 (deleting the
git-common-dir cache loses NO canonical state — it is rebuilt from the committed spec + GitHub).
"""

from __future__ import annotations

import importlib.util
import shutil
import sys
from pathlib import Path
from types import ModuleType

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


OS_ = _load("outcome_spec")
M = _load("outcome_store")


def _store(tmp_path: Path):
    return M.Store(root=tmp_path / "store").ensure()


# --------------------------------------------------------------------------- ledger durability


def test_ledger_append_read_roundtrip(tmp_path: Path) -> None:
    store = _store(tmp_path)
    M.append_ledger(store, {"phase": "intent", "key": "k1"})
    M.append_ledger(store, {"phase": "commit", "key": "k1"})
    recs = M.read_ledger(store)
    assert [r["phase"] for r in recs] == ["intent", "commit"]


def test_torn_trailing_line_is_tolerated(tmp_path: Path) -> None:
    store = _store(tmp_path)
    M.append_ledger(store, {"phase": "intent", "key": "k1"})
    M.append_ledger(store, {"phase": "commit", "key": "k1"})
    # Simulate a crash mid-append: a truncated final line with no newline.
    with open(store.ledger_path, "a", encoding="utf-8") as fh:
        fh.write('{"phase": "intent", "key": "k2"')  # torn, unterminated
    recs = M.read_ledger(store)
    assert [r["key"] for r in recs] == ["k1", "k1"]  # torn trailing line dropped, rest intact


def test_mid_file_corruption_raises(tmp_path: Path) -> None:
    store = _store(tmp_path)
    # A malformed line that is NOT the trailing line is genuine corruption, not a torn tail.
    store.ledger_path.write_text(
        '{"phase": "intent", "key": "k1"}\nNOT JSON\n{"phase": "commit", "key": "k1"}\n',
        encoding="utf-8",
    )
    with pytest.raises(M.OutcomeStoreError, match="corrupt ledger line"):
        M.read_ledger(store)


def test_nondict_midfile_line_raises(tmp_path: Path) -> None:
    # A line that is VALID JSON but not an object (e.g. a bare scalar left by truncation) in a
    # non-trailing position is corruption too — it must raise, not be silently skipped.
    store = _store(tmp_path)
    store.ledger_path.write_text(
        '{"phase":"intent","key":"k1"}\n42\n{"phase":"commit","key":"k1"}\n', encoding="utf-8"
    )
    with pytest.raises(M.OutcomeStoreError, match="not a JSON object"):
        M.read_ledger(store)


def test_nondict_trailing_line_tolerated(tmp_path: Path) -> None:
    store = _store(tmp_path)
    store.ledger_path.write_text('{"phase":"intent","key":"k1"}\n42\n', encoding="utf-8")
    assert [r["key"] for r in M.read_ledger(store)] == ["k1"]  # trailing non-object tolerated


def test_ledger_self_heals_torn_tail_before_append(tmp_path: Path) -> None:
    # The crash R30 must survive: a torn (newline-less) tail, then RECOVERY APPENDS. Without
    # self-heal the first append merges into the torn line (lost) and the second bricks read_ledger.
    store = _store(tmp_path)
    M.append_ledger(store, {"phase": "intent", "key": "k1"})
    with open(store.ledger_path, "a", encoding="utf-8") as fh:
        fh.write('{"phase": "intent", "key": "k2"')  # crash: torn, unterminated fragment
    # recovery appends — must heal (truncate) the torn k2 fragment, not merge into it
    M.append_ledger(store, {"phase": "commit", "key": "k1"})
    M.append_ledger(store, {"phase": "intent", "key": "k3"})
    recs = M.read_ledger(store)  # must NOT raise
    assert [(r["phase"], r["key"]) for r in recs] == [
        ("intent", "k1"),
        ("commit", "k1"),
        ("intent", "k3"),
    ]
    # k1 committed; the torn k2 was dropped; k3 is the only genuine pending intent
    assert [p["key"] for p in M.replay_pending(store)] == ["k3"]


# --------------------------------------------------------------------------- replay (R30)


def test_replay_pending_returns_uncommitted_intents(tmp_path: Path) -> None:
    store = _store(tmp_path)
    M.append_ledger(store, {"phase": "intent", "key": "k1", "kind": "dispatch"})
    M.append_ledger(store, {"phase": "commit", "key": "k1"})
    M.append_ledger(store, {"phase": "intent", "key": "k2", "kind": "merge"})
    pending = M.replay_pending(store)
    assert [p["key"] for p in pending] == ["k2"]


def test_crash_after_effect_before_commit_replays_without_duplicate(tmp_path: Path) -> None:
    store = _store(tmp_path)
    # 1) record intent, 2) perform the side effect (write the completion event), 3) CRASH before
    # the commit line is appended.
    M.append_ledger(store, {"phase": "intent", "key": "k1", "subplot_id": "build"})
    assert (
        M.write_completion_event(
            store, M.CompletionEvent(subplot_id="build", state="done", idempotency_key="k1")
        )
        == "written"
    )
    # --- crash here: no commit record ---
    pending = M.replay_pending(store)
    assert [p["key"] for p in pending] == ["k1"]

    # Recovery re-drives the pending intent. The effect is idempotent on the same key, so it does
    # NOT duplicate — the second write is skipped and there is still exactly one event file.
    assert (
        M.write_completion_event(
            store, M.CompletionEvent(subplot_id="build", state="done", idempotency_key="k1")
        )
        == "skipped"
    )
    assert M.completed_subplots(store) == {"build"}
    assert len(M.read_completion_events(store, "build")) == 1

    # Now the commit is recorded -> nothing pending.
    M.append_ledger(store, {"phase": "commit", "key": "k1"})
    assert M.replay_pending(store) == []


# --------------------------------------------------------------------------- v2 vocabulary (#628)


def _native_intent(sid: str, *, outcome_id: str = "ship-x") -> dict:
    intent_id = f"dispatch-intent:{outcome_id}:{sid}"
    return {
        "phase": "intent",
        "kind": "outcome.dispatch.v2",
        "key": intent_id,
        "dispatch_intent_id": intent_id,
        "subplot_id": sid,
        "backend": "claude-direct",
        "run_identity": "outcome-run-0f3a9c",
        "at": 1000.0,
    }


def _native_ack(
    sid: str,
    *,
    ack_kind: str = "launched",
    receipt_authority: str = "owner-user-state-v1",
    leaf: str = "issue-42",
    outcome_id: str = "ship-x",
) -> dict:
    intent_id = f"dispatch-intent:{outcome_id}:{sid}"
    record = {
        "phase": "ack",
        "kind": "outcome.dispatch.v2",
        "key": intent_id,
        "dispatch_intent_id": intent_id,
        "subplot_id": sid,
        "backend": "claude-direct",
        "ack_kind": ack_kind,
        "dispatch_ack_ref": "launch-receipt:abc",
        "receipt_authority": receipt_authority,
        "run_identity": "outcome-run-0f3a9c",
        "at": 1001.0,
    }
    if leaf:
        record["leaf_saga_id"] = leaf
    return record


def test_reduce_dispatch_ledger_native_arms(tmp_path: Path) -> None:
    """The shared v1/v2 reduction reads each vocabulary arm exactly like the codex runtime."""
    store = _store(tmp_path)
    # legacy commit -> settled, legacy-unverified
    M.append_ledger(
        store, {"phase": "commit", "kind": "dispatch", "key": "dispatch:a", "subplot_id": "a"}
    )
    # live native intent, no ack -> in flight, NOT settled
    M.append_ledger(store, _native_intent("b"))
    # native intent + authoritative launched ack -> dispatched, settled
    M.append_ledger(store, _native_intent("c"))
    M.append_ledger(store, _native_ack("c"))
    # native intent + operator handed-off ack -> handed-off, settled (no leaf id claimed)
    M.append_ledger(store, _native_intent("d"))
    M.append_ledger(
        store,
        _native_ack("d", ack_kind="handed-off", receipt_authority="operator-confirmed-v1", leaf=""),
    )
    # an ack WITHOUT receipt authority still concludes conservatively (settled, unverified)
    M.append_ledger(store, _native_intent("e"))
    M.append_ledger(store, _native_ack("e", receipt_authority=""))
    reduced = M.reduce_dispatch_ledger(store)
    assert (reduced["a"]["state"], reduced["a"]["settled"]) == ("legacy-unverified", True)
    assert (reduced["b"]["state"], reduced["b"]["settled"]) == ("intent-created", False)
    assert (reduced["c"]["state"], reduced["c"]["settled"]) == ("dispatched", True)
    assert reduced["c"]["record"]["leaf_saga_id"] == "issue-42"
    assert (reduced["d"]["state"], reduced["d"]["settled"]) == ("handed-off", True)
    assert (reduced["e"]["state"], reduced["e"]["settled"]) == ("legacy-unverified", True)


def test_reduce_halt_preserves_settlement(tmp_path: Path) -> None:
    store = _store(tmp_path)
    M.append_ledger(
        store, {"phase": "commit", "kind": "dispatch", "key": "dispatch:a", "subplot_id": "a"}
    )
    M.append_ledger(
        store, {"phase": "halt", "kind": "dispatch", "key": "spend:a", "subplot_id": "a"}
    )
    reduced = M.reduce_dispatch_ledger(store)
    assert reduced["a"]["settled"] is True  # a later halt never un-settles a concluded dispatch
    assert reduced["a"]["halted"] is True


def test_replay_pending_native_intent_until_acked(tmp_path: Path) -> None:
    """A live native intent is pending; its authoritative ack retires it — never a legacy re-drive."""
    store = _store(tmp_path)
    M.append_ledger(store, _native_intent("race-leaf"))
    assert [p["subplot_id"] for p in M.replay_pending(store)] == ["race-leaf"]
    M.append_ledger(store, _native_ack("race-leaf"))
    assert M.replay_pending(store) == []


# --------------------------------------------------------------------------- cache loss (R27)


def _three_node_spec():
    return OS_.OutcomeSpec.from_dict(
        {
            "outcome_id": "ship-x",
            "objective": "ship feature x",
            "nodes": [
                {"subplot_id": "design", "title": "design"},
                {"subplot_id": "build", "title": "build", "depends_on": ["design"]},
                {"subplot_id": "docs", "title": "docs", "depends_on": ["build"]},
            ],
        }
    )


def test_deleting_cache_loses_no_canonical_state(tmp_path: Path) -> None:
    spec = _three_node_spec()
    store = _store(tmp_path)
    # The cache records design as done; the live frontier (from the cache) is therefore "build".
    M.write_completion_event(
        store, M.CompletionEvent(subplot_id="design", state="done", idempotency_key="kd")
    )
    assert OS_.ready_frontier(spec, completed=M.completed_subplots(store)) == ["build"]

    # Blow the entire cache away (e.g. `git worktree remove`, a wipe). It is PURE CACHE.
    shutil.rmtree(store.root)
    assert M.completed_subplots(M.Store(root=store.root)) == set()  # cache holds nothing now

    # This proves the CACHE holds no canonical state. The full R27 "reconstruct from GitHub" leg —
    # actually READING issue/PR completion from GitHub — is U5's outcome_github primitive (not in
    # this module), so here we stand in the canonical completion set GitHub would supply and confirm
    # the frontier is fully recomputable from (committed spec + that set), i.e. nothing was lost with
    # the cache.
    github_completed = {
        "design"
    }  # placeholder for U5's GitHub read — the canonical completion source
    assert OS_.ready_frontier(spec, completed=github_completed) == ["build"]


def test_reduce_same_subplot_cross_vocabulary_collision(tmp_path: Path) -> None:
    """#628 review P1: the literal defect shape — ONE subplot carrying records from BOTH
    vocabularies. The reduction must converge on the native settlement in either order; a later
    legacy commit must never clobber an already-settled native state (the ordering guard)."""
    # Order A: native intent + launched ack, THEN a legacy commit lands on the same subplot.
    store_a = M.Store(root=tmp_path / "store-a").ensure()
    M.append_ledger(store_a, _native_intent("race-leaf"))
    M.append_ledger(store_a, _native_ack("race-leaf"))
    M.append_ledger(
        store_a,
        {
            "phase": "commit",
            "kind": "dispatch",
            "key": "dispatch:race-leaf",
            "subplot_id": "race-leaf",
        },
    )
    reduced_a = M.reduce_dispatch_ledger(store_a)["race-leaf"]
    assert (reduced_a["state"], reduced_a["settled"]) == ("dispatched", True)
    assert reduced_a["record"]["leaf_saga_id"] == "issue-42"  # the ack won, not the late commit

    # Order B: legacy commit first, then the native intent + launched ack arrive.
    store_b = M.Store(root=tmp_path / "store-b").ensure()
    M.append_ledger(
        store_b,
        {
            "phase": "commit",
            "kind": "dispatch",
            "key": "dispatch:race-leaf",
            "subplot_id": "race-leaf",
        },
    )
    M.append_ledger(store_b, _native_intent("race-leaf"))
    M.append_ledger(store_b, _native_ack("race-leaf"))
    reduced_b = M.reduce_dispatch_ledger(store_b)["race-leaf"]
    assert (reduced_b["state"], reduced_b["settled"]) == ("dispatched", True)
    # settlement never lapsed mid-sequence: the interposed intent carried the commit's settled bit
    store_c = M.Store(root=tmp_path / "store-c").ensure()
    M.append_ledger(
        store_c,
        {
            "phase": "commit",
            "kind": "dispatch",
            "key": "dispatch:race-leaf",
            "subplot_id": "race-leaf",
        },
    )
    M.append_ledger(store_c, _native_intent("race-leaf"))
    mid = M.reduce_dispatch_ledger(store_c)["race-leaf"]
    assert mid["settled"] is True  # a legacy commit still prevents relaunch while awaiting the ack
