"""Tests for the outcome store: cache layout, completion events, leases, offline queue (U2).

The store is the git-common-dir **cache** beside the canonical spec (U1) + GitHub. These oracles pin
the durability/coordination primitives KTD15 makes explicit:

* happy — events round-trip; two leaves write without contention; the store path is worktree-stable;
* edge — idempotency dedup vs a genuine new-attempt retry; same-holder lease refresh; lease reclaim;
* error — malformed files are quarantined not fatal; a non-terminal completion state is rejected;
* integration — the CLI ``paths``/``ledger`` entrypoints exercise the real resolve+read path.
"""

from __future__ import annotations

import importlib.util
import json
import sys
from collections.abc import Callable
from pathlib import Path
from types import ModuleType, SimpleNamespace
from typing import Any

import pytest

ROOT = Path(__file__).parent.parent
SCRIPTS = ROOT / "plugins" / "saga" / "scripts"
SCRIPT = SCRIPTS / "outcome_store.py"


def _load() -> ModuleType:
    # outcome_store imports its sibling outcome_spec; make the scripts dir importable first.
    if str(SCRIPTS) not in sys.path:
        sys.path.insert(0, str(SCRIPTS))
    spec = importlib.util.spec_from_file_location("outcome_store", SCRIPT)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules["outcome_store"] = module
    spec.loader.exec_module(module)
    return module


M = _load()


class Clock:
    """A deterministic, advanceable clock for lease tests."""

    def __init__(self, t: float = 1000.0) -> None:
        self.t = t

    def __call__(self) -> float:
        return self.t

    def advance(self, d: float) -> None:
        self.t += d


def _store(tmp_path: Path):
    return M.Store(root=tmp_path / "store").ensure()


def _runner_returning(common_dir: str, *, returncode: int = 0) -> Callable[..., Any]:
    def runner(args: list[str], **_kw: Any) -> SimpleNamespace:
        return SimpleNamespace(returncode=returncode, stdout=f"{common_dir}\n", stderr="boom")

    return runner


def _event(mod: ModuleType, sid: str, key: str, *, attempt: int = 1, state: str = "done"):
    return mod.CompletionEvent(subplot_id=sid, state=state, idempotency_key=key, attempt=attempt)


# --------------------------------------------------------------------------- store resolution (R27)


def test_store_path_identical_from_two_worktrees() -> None:
    # git rev-parse --git-common-dir returns the SAME absolute main .git from any worktree, so the
    # store root must be identical regardless of which worktree we resolve from.
    common = "/repo/.git"
    a = M.Store.for_outcome("ship-x", Path("/repo"), runner=_runner_returning(common))
    b = M.Store.for_outcome(
        "ship-x", Path("/repo/.git/worktrees/feature"), runner=_runner_returning(common)
    )
    assert a.root == b.root
    assert a.root == Path("/repo/.git/saga-outcomes/ship-x")


def test_relative_common_dir_resolves_against_repo_root(tmp_path: Path) -> None:
    store = M.Store.for_outcome("o", tmp_path, runner=_runner_returning(".git"))
    assert store.root == (tmp_path / ".git" / "saga-outcomes" / "o").resolve()


def test_git_failure_raises(tmp_path: Path) -> None:
    with pytest.raises(M.OutcomeStoreError, match="git rev-parse"):
        M.Store.for_outcome("o", tmp_path, runner=_runner_returning("", returncode=1))


def test_outcome_id_with_separator_is_rejected(tmp_path: Path) -> None:
    with pytest.raises(M.OutcomeStoreError, match="path separator"):
        M.Store.for_outcome("a/b", tmp_path, runner=_runner_returning("/repo/.git"))


# --------------------------------------------------------------------------- atomic / write-once


def test_atomic_write_leaves_no_tmp_and_overwrites(tmp_path: Path) -> None:
    p = tmp_path / "f.json"
    M._atomic_write(p, "one")
    M._atomic_write(p, "two")
    assert p.read_text() == "two"
    assert list(tmp_path.glob("*.tmp")) == []


def test_write_once_refuses_to_clobber(tmp_path: Path) -> None:
    p = tmp_path / "once.json"
    assert M._write_once(p, "first") is True
    assert M._write_once(p, "second") is False
    assert p.read_text() == "first"  # immutable
    assert list(tmp_path.glob("*.tmp")) == []


def test_malformed_file_is_quarantined_not_fatal(tmp_path: Path) -> None:
    store = _store(tmp_path)
    bad = store.events_dir / "x.a1.json"
    bad.write_text("{not json", encoding="utf-8")
    out = M._read_json_or_quarantine(bad, quarantine_dir=store.quarantine_dir)
    assert out is None
    assert not bad.exists()  # moved out of the way
    assert any(store.quarantine_dir.iterdir())  # quarantined, logged-aside
    # and a higher-level read just skips it rather than raising
    assert M.read_completion_events(store, "x") == []


# --------------------------------------------------------------------------- completion events (R10)


def test_two_leaves_write_concurrently_no_contention(tmp_path: Path) -> None:
    store = _store(tmp_path)
    assert M.write_completion_event(store, _event(M, "a", "ka")) == "written"
    assert M.write_completion_event(store, _event(M, "b", "kb")) == "written"
    # distinct files, no shared log
    assert M.completed_subplots(store) == {"a", "b"}


def test_duplicate_idempotency_key_is_skipped(tmp_path: Path) -> None:
    store = _store(tmp_path)
    assert M.write_completion_event(store, _event(M, "x", "k1")) == "written"
    assert M.write_completion_event(store, _event(M, "x", "k1")) == "skipped"
    assert len(M.read_completion_events(store, "x")) == 1


def test_retry_with_new_attempt_proceeds(tmp_path: Path) -> None:
    store = _store(tmp_path)
    assert (
        M.write_completion_event(store, _event(M, "x", "k1", attempt=1, state="failed"))
        == "written"
    )
    assert (
        M.write_completion_event(store, _event(M, "x", "k2", attempt=2, state="done")) == "written"
    )
    events = M.read_completion_events(store, "x")
    assert [e.attempt for e in events] == [1, 2]
    # latest attempt is the success -> x counts as completed
    assert M.completed_subplots(store) == {"x"}


def test_failed_only_completion_not_counted_as_success(tmp_path: Path) -> None:
    store = _store(tmp_path)
    M.write_completion_event(store, _event(M, "x", "k1", state="failed"))
    assert M.completed_subplots(store) == set()  # successful_only default
    assert M.completed_subplots(store, successful_only=False) == {"x"}


def test_same_attempt_slot_conflicting_key_raises(tmp_path: Path) -> None:
    store = _store(tmp_path)
    M.write_completion_event(store, _event(M, "x", "k1", attempt=1))
    with pytest.raises(M.OutcomeStoreError, match="already holds a different event"):
        M.write_completion_event(store, _event(M, "x", "k2", attempt=1))


def test_concurrent_identical_key_link_loser_dedups(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    # The race: a second identical-key delivery whose dedup pre-scan MISSED the file (a sibling
    # linked between our scan and our link). Force the pre-scan to return [] so we reach the
    # write-once link-loser branch — it must converge to "skipped", NOT raise a "key K != K" error.
    store = _store(tmp_path)
    assert M.write_completion_event(store, _event(M, "x", "k1")) == "written"
    monkeypatch.setattr(M, "read_completion_events", lambda *a, **k: [])
    assert M.write_completion_event(store, _event(M, "x", "k1")) == "skipped"


def test_completed_subplots_success_is_sticky(tmp_path: Path) -> None:
    # done@attempt1 then a later failed@attempt2 must NOT un-complete a leaf that already succeeded
    # (latest-attempt-wins would have erased the success and re-locked the frontier).
    store = _store(tmp_path)
    M.write_completion_event(store, _event(M, "x", "k1", attempt=1, state="done"))
    M.write_completion_event(store, _event(M, "x", "k2", attempt=2, state="failed"))
    assert M.completed_subplots(store) == {"x"}


@pytest.mark.parametrize(
    "kwargs,match",
    [
        ({"state": "running"}, "not terminal"),
        ({"idempotency_key": ""}, "idempotency_key"),
        ({"attempt": 0}, "attempt must be"),
        ({"attempt": True}, "attempt must be"),
    ],
)
def test_completion_event_validation(tmp_path: Path, kwargs: dict, match: str) -> None:
    store = _store(tmp_path)
    base = {"subplot_id": "x", "state": "done", "idempotency_key": "k", "attempt": 1}
    base.update(kwargs)
    with pytest.raises(M.OutcomeStoreError, match=match):
        M.write_completion_event(store, M.CompletionEvent(**base))


# --------------------------------------------------------------------------- leases (R13)


def test_coordinator_lease_held_then_reclaim_stale(tmp_path: Path) -> None:
    store = _store(tmp_path)
    clock = Clock()
    assert M.acquire_coordinator(store, "A", ttl_seconds=100, now=clock) is True
    # a second advance (another tick / machine) no-ops on the held, unexpired lease
    assert M.acquire_coordinator(store, "B", ttl_seconds=100, now=clock) is False
    clock.advance(101)  # lease expires
    assert M.acquire_coordinator(store, "B", ttl_seconds=100, now=clock) is True
    assert M.read_lease(store, M.COORDINATOR_LOCK).holder == "B"


def test_same_holder_refreshes_lease(tmp_path: Path) -> None:
    store = _store(tmp_path)
    clock = Clock()
    assert M.acquire_coordinator(store, "A", ttl_seconds=100, now=clock) is True
    assert M.acquire_coordinator(store, "A", ttl_seconds=100, now=clock) is True


def test_release_lease_frees_it(tmp_path: Path) -> None:
    store = _store(tmp_path)
    clock = Clock()
    M.acquire_coordinator(store, "A", ttl_seconds=100, now=clock)
    assert M.release_lease(store, M.COORDINATOR_LOCK, "B") is False  # not the holder
    assert M.release_lease(store, M.COORDINATOR_LOCK, "A") is True
    assert M.acquire_coordinator(store, "B", ttl_seconds=100, now=clock) is True


def test_dispatch_lock_prevents_duplicate_dispatch(tmp_path: Path) -> None:
    store = _store(tmp_path)
    clock = Clock()
    assert M.acquire_dispatch(store, "build", "A", ttl_seconds=100, now=clock) is True
    assert M.acquire_dispatch(store, "build", "B", ttl_seconds=100, now=clock) is False
    # a different subplot is independent
    assert M.acquire_dispatch(store, "docs", "B", ttl_seconds=100, now=clock) is True


def test_zero_ttl_rejected(tmp_path: Path) -> None:
    store = _store(tmp_path)
    with pytest.raises(M.OutcomeStoreError, match="ttl_seconds"):
        M.acquire_coordinator(store, "A", ttl_seconds=0)


# --------------------------------------------------------------------------- offline queue (R34)


def test_offline_drain_sends_and_removes(tmp_path: Path) -> None:
    store = _store(tmp_path)
    M.enqueue_offline(store, {"key": "k1", "op": "close-issue"})
    M.enqueue_offline(store, {"key": "k2", "op": "merge"})
    res = M.drain_offline(store, sender=lambda _m: True)
    assert sorted(res.sent) == ["k1", "k2"]
    assert list(store.offline_dir.glob("*.json")) == []


def test_offline_drain_drops_superseded(tmp_path: Path) -> None:
    # GitHub wins for completion: a queued write the server already obsoleted is dropped, not sent.
    store = _store(tmp_path)
    M.enqueue_offline(store, {"key": "k1", "op": "mark-done"})
    sent: list[dict] = []

    def _record_and_succeed(mutation: dict) -> bool:
        sent.append(mutation)
        return True

    res = M.drain_offline(store, sender=_record_and_succeed, is_superseded=lambda _m: True)
    assert res.dropped == ["k1"] and res.sent == []
    assert sent == []  # sender never called for a superseded write
    assert list(store.offline_dir.glob("*.json")) == []


def test_offline_drain_pages_on_retry_exhaustion(tmp_path: Path) -> None:
    store = _store(tmp_path)
    M.enqueue_offline(store, {"key": "k1", "op": "merge"}, max_attempts=1)
    res = M.drain_offline(store, sender=lambda _m: False)  # always fails -> attempts 1 >= max 1
    assert res.paged == ["k1"]
    assert list(store.offline_dir.glob("*.json")) == []  # moved out of the live queue
    assert any(store.quarantine_dir.iterdir())


def test_offline_drain_retries_within_budget(tmp_path: Path) -> None:
    store = _store(tmp_path)
    M.enqueue_offline(store, {"key": "k1", "op": "merge"}, max_attempts=3)
    res = M.drain_offline(store, sender=lambda _m: False)
    assert res.paged == [] and res.sent == [] and res.dropped == []
    # still queued, attempts incremented
    [queued] = list(store.offline_dir.glob("*.json"))
    assert json.loads(queued.read_text())["attempts"] == 1


def test_offline_exponential_backoff_defers_then_retries(tmp_path: Path) -> None:
    # R34 "exponential backoff, cap N" — a failed delivery schedules next_retry_at; a drain inside
    # that window defers (sender not called); after it elapses, the retry proceeds.
    store = _store(tmp_path)
    M.enqueue_offline(store, {"key": "k1", "op": "merge"}, max_attempts=5)
    clock = Clock(t=1000.0)
    M.drain_offline(store, sender=lambda _m: False, now=clock, backoff_base=2.0)
    rec = json.loads(next(store.offline_dir.glob("*.json")).read_text())
    assert rec["attempts"] == 1 and rec["next_retry_at"] == 1002.0  # 1000 + 2*2^0

    calls: list[dict] = []

    def _record_fail(mutation: dict) -> bool:
        calls.append(mutation)
        return False

    deferred = M.drain_offline(store, sender=_record_fail, now=lambda: 1001.0, backoff_base=2.0)
    assert deferred.deferred == ["k1"] and calls == []  # still inside the backoff window

    after = M.drain_offline(store, sender=lambda _m: False, now=lambda: 1002.0, backoff_base=2.0)
    assert after.deferred == []  # window elapsed -> retried
    rec2 = json.loads(next(store.offline_dir.glob("*.json")).read_text())
    assert rec2["attempts"] == 2


def test_enqueue_requires_key(tmp_path: Path) -> None:
    store = _store(tmp_path)
    with pytest.raises(M.OutcomeStoreError, match="non-empty 'key'"):
        M.enqueue_offline(store, {"op": "merge"})


# --------------------------------------------------------------------------- integration (CLI)


def test_cli_paths(
    tmp_path: Path, capsys: pytest.CaptureFixture[str], monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(M.subprocess, "run", _runner_returning(str(tmp_path / ".git")))
    rc = M.main(["paths", "ship-x", "--repo-root", str(tmp_path)])
    assert rc == 0
    out = json.loads(capsys.readouterr().out)
    assert out["root"].endswith("saga-outcomes/ship-x")
    assert out["events"].endswith("saga-outcomes/ship-x/events")


def test_cli_ledger(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    store = _store(tmp_path)
    M.append_ledger(store, {"phase": "intent", "key": "k1", "kind": "dispatch"})
    rc = M.main(["ledger", str(store.root)])
    assert rc == 0
    out = json.loads(capsys.readouterr().out)
    assert out["records"][0]["key"] == "k1"
