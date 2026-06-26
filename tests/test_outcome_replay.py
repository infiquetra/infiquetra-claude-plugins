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
