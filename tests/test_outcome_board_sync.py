"""Tests for outcome_board_sync — U4 autonomous board-sync consumer (#279).

Uses a REAL store under tmp_path and a fake recording board_writer; drives
``reconcile_board`` directly (no fabricated shape).

Requirement traceability: R1, R6, R9, R15–R19; KTD4, KTD6, KTD8.
AE coverage: AE1, AE2, AE4, AE5, AE8.

Security guard: conftest.py has an autouse fixture (_no_live_gh) scoped to this
module that RAISES on any unmocked ``gh`` subprocess call.  Board_writer here is
always a fake recording callable — no real ``gh`` ever fires.
"""

from __future__ import annotations

import importlib.util
import json
import os
import subprocess
import sys
from pathlib import Path
from types import ModuleType
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


# Load in dependency order (mirrors test_outcome_projection.py pattern).
SPEC_MOD = _load("outcome_spec")
STORE_MOD = _load("outcome_store")
_load("outcome_orchestrator")
DISP_MOD = _load("outcome_dispatcher")
_load("outcome_merge")
_load("outcome_worktrees")
DEC_MOD = _load("outcome_decompose")
ENG_MOD = _load("outcome")
_load("outcome_report")
_load("outcome_projection")
CERT_MOD = _load("reversibility_certificate")
SYNC_MOD = _load("outcome_board_sync")


# ---------------------------------------------------------------------------
# Test helpers
# ---------------------------------------------------------------------------


def _store(tmp_path: Path) -> Any:
    return STORE_MOD.Store(root=tmp_path / "store").ensure()


def _spec(nodes: list[dict[str, Any]]) -> Any:
    return SPEC_MOD.OutcomeSpec.from_dict(
        {"outcome_id": "o", "objective": "Ship it", "nodes": nodes}
    )


def _done(store: Any, sid: str, state: str = "done") -> None:
    STORE_MOD.write_completion_event(
        store,
        STORE_MOD.CompletionEvent(subplot_id=sid, state=state, idempotency_key=f"k:{sid}:{state}"),
    )


def _leaf(sid: str, issue: str = "infiquetra/x#42") -> dict[str, Any]:
    return {"subplot_id": sid, "title": sid, "kind": "code", "github": {"issue": issue}}


class RecordingWriter:
    """Fake board_writer: records calls, never touches GitHub."""

    def __init__(self) -> None:
        self.calls: list[dict[str, Any]] = []

    def __call__(self, *, op_kind: str, repo: str, number: int, payload: dict) -> None:
        self.calls.append({"op_kind": op_kind, "repo": repo, "number": number, "payload": payload})

    def calls_for(self, op_kind: str) -> list[dict[str, Any]]:
        return [c for c in self.calls if c["op_kind"] == op_kind]


# ---------------------------------------------------------------------------
# AE1: ready state → set-field-status "In Progress" written (R5, R16, R19)
# ---------------------------------------------------------------------------


def test_ae1_ready_state_writes_set_field_status(tmp_path: Path) -> None:
    """AE1: a leaf in ready state has board_writer called with set-field-status In Progress."""
    store = _store(tmp_path)
    # No completion events and no deps → leaf1 is in the ready frontier.
    spec = _spec([_leaf("leaf1", "infiquetra/x#42")])
    writer = RecordingWriter()

    result = SYNC_MOD.reconcile_board(spec, store, board_writer=writer)

    sf_records = [r for r in result if r.get("op_kind") == "set-field-status"]
    assert sf_records, "expected a set-field-status record for a ready leaf"
    r = sf_records[0]
    assert r["status"] == "written", f"expected written, got {r['status']!r}"
    assert r["target_state"] == "In Progress"
    assert r["repo"] == "infiquetra/x"
    assert r["number"] == 42

    sf_calls = writer.calls_for("set-field-status")
    assert len(sf_calls) == 1, "board_writer must be called exactly once for set-field-status"
    assert sf_calls[0]["repo"] == "infiquetra/x"
    assert sf_calls[0]["number"] == 42
    assert sf_calls[0]["payload"].get("target_state") == "In Progress"


# ---------------------------------------------------------------------------
# AE2: done state → sub-issue-close performed (R5, R15, R16)
# ---------------------------------------------------------------------------


def test_ae2_done_state_writes_sub_issue_close(tmp_path: Path) -> None:
    """AE2: a leaf derived 'done' → board_writer called with sub-issue-close."""
    store = _store(tmp_path)
    spec = _spec([_leaf("leaf1", "infiquetra/x#42")])
    _done(store, "leaf1", "done")
    writer = RecordingWriter()

    result = SYNC_MOD.reconcile_board(spec, store, board_writer=writer)

    close_records = [r for r in result if r.get("op_kind") == "sub-issue-close"]
    assert close_records, "expected a sub-issue-close record for a done leaf"
    assert close_records[0]["status"] == "written"

    close_calls = writer.calls_for("sub-issue-close")
    assert len(close_calls) == 1, "board_writer must be called once for sub-issue-close"
    assert close_calls[0]["number"] == 42


# ---------------------------------------------------------------------------
# AE4: coalescing — progress comment written once, skipped on re-run (R6, R16)
# ---------------------------------------------------------------------------


def test_ae4_comment_coalescing_written_then_skipped(tmp_path: Path) -> None:
    """AE4: run twice for same done leaf → comment written first run, skipped second."""
    store = _store(tmp_path)
    spec = _spec([_leaf("leaf1", "infiquetra/x#42")])
    _done(store, "leaf1", "done")

    writer1 = RecordingWriter()
    result1 = SYNC_MOD.reconcile_board(spec, store, board_writer=writer1)

    writer2 = RecordingWriter()
    result2 = SYNC_MOD.reconcile_board(spec, store, board_writer=writer2)

    # First run: comment must be "written"
    comment_written = [
        r
        for r in result1
        if r.get("op_kind") == "issue-progress-comment" and r.get("status") == "written"
    ]
    assert comment_written, "issue-progress-comment should be 'written' on first run"

    # Second run: same key → must be "skipped"
    comment_skipped = [
        r
        for r in result2
        if r.get("op_kind") == "issue-progress-comment" and r.get("status") == "skipped"
    ]
    assert comment_skipped, "issue-progress-comment should be 'skipped' on second run (coalescing)"

    # board_writer called for comment exactly once total (across both runs)
    assert len(writer1.calls_for("issue-progress-comment")) == 1
    assert len(writer2.calls_for("issue-progress-comment")) == 0


# ---------------------------------------------------------------------------
# AE5: GATE → gated record, board_writer NOT called, no ledger file (R17)
# ---------------------------------------------------------------------------


def test_ae5_gate_surfaces_no_write_no_ledger(tmp_path: Path) -> None:
    """AE5: monkeypatched GATE → gated record, board_writer not called, no ledger file."""
    store = _store(tmp_path)
    spec = _spec([_leaf("leaf1", "infiquetra/x#42")])
    # leaf1 is "ready" (no deps, no completion)

    cert_mod: Any = sys.modules["reversibility_certificate"]
    original_authorize = cert_mod.authorize_write
    try:
        cert_mod.authorize_write = lambda _op: cert_mod.GATE

        writer = RecordingWriter()
        result = SYNC_MOD.reconcile_board(spec, store, board_writer=writer)
    finally:
        cert_mod.authorize_write = original_authorize

    gated = [r for r in result if r.get("status") == "gated"]
    assert gated, "expected at least one gated record when authorize_write returns GATE"
    assert all(r["verdict"] == "GATE" for r in gated)

    assert len(writer.calls) == 0, "board_writer must NOT be called for gated ops"

    # No ledger files created under board-sync
    ledger_dir = Path(store.root) / "board-sync"
    if ledger_dir.exists():
        assert not list(ledger_dir.glob("*.json")), "no ledger files for gated ops"


# ---------------------------------------------------------------------------
# AE8a: retry → eventually succeeds, one ledger key, no duplicate (R9, R18)
# ---------------------------------------------------------------------------


def test_ae8_retry_on_transient_failure_succeeds(tmp_path: Path) -> None:
    """AE8: board_writer raises on first call then succeeds → status 'written', one ledger key."""
    store = _store(tmp_path)
    spec = _spec([_leaf("leaf1", "infiquetra/x#42")])
    # leaf1 is "ready"

    call_count: dict[str, int] = {"n": 0}

    def flaky_writer(*, op_kind: str, repo: str, number: int, payload: dict) -> None:
        call_count["n"] += 1
        if call_count["n"] == 1 and op_kind == "set-field-status":
            raise RuntimeError("transient network error")

    result = SYNC_MOD.reconcile_board(spec, store, board_writer=flaky_writer, max_attempts=3)

    sf_records = [r for r in result if r.get("op_kind") == "set-field-status"]
    assert sf_records and sf_records[0]["status"] == "written", (
        f"expected written, got {sf_records}"
    )
    # Exactly one ledger file for the set-field-status op — use the module's own
    # _safe_ledger_name to handle the SHA-1 fallback for keys with spaces (e.g. "In Progress").
    ledger_dir = Path(store.root) / "board-sync"
    sf_key = sf_records[0]["key"]
    ledger_file = ledger_dir / SYNC_MOD._safe_ledger_name(sf_key)
    assert ledger_file.exists(), "ledger key must be written on success"


# ---------------------------------------------------------------------------
# AE8b: always fails → 'failed' surfaced, re-run re-attempts (R9, R18)
# ---------------------------------------------------------------------------


def test_ae8_always_fails_surfaced_and_retryable(tmp_path: Path) -> None:
    """AE8: always-raising writer → 'failed' record; re-run re-attempts (no ledger on fail)."""
    store = _store(tmp_path)
    spec = _spec([_leaf("leaf1", "infiquetra/x#42")])

    def always_fail(*, op_kind: str, repo: str, number: int, payload: dict) -> None:
        raise RuntimeError("always fails")

    result1 = SYNC_MOD.reconcile_board(spec, store, board_writer=always_fail, max_attempts=3)

    failed = [
        r for r in result1 if r.get("op_kind") == "set-field-status" and r["status"] == "failed"
    ]
    assert failed, "expected 'failed' record for set-field-status after max_attempts exhausted"
    assert failed[0]["attempts"] == 3

    # Ledger NOT written on failure → next tick can re-attempt
    ledger_dir = Path(store.root) / "board-sync"
    if ledger_dir.exists():
        ledger_files = list(ledger_dir.glob("*.json"))
        # No set-field-status ledger key was written
        sf_ledger = [
            f for f in ledger_files if "set_field_status" in f.name or "set-field-status" in f.name
        ]
        assert not sf_ledger, "ledger key must NOT be written when the op fails"

    # Re-run succeeds with a writer that works
    good_calls: list[str] = []

    def good_writer(*, op_kind: str, repo: str, number: int, payload: dict) -> None:
        good_calls.append(op_kind)

    result2 = SYNC_MOD.reconcile_board(spec, store, board_writer=good_writer, max_attempts=3)
    sf_written = [
        r for r in result2 if r.get("op_kind") == "set-field-status" and r["status"] == "written"
    ]
    assert sf_written, (
        "re-run must attempt set-field-status again (ledger not written on first fail)"
    )
    assert "set-field-status" in good_calls


# ---------------------------------------------------------------------------
# R1: authorize_write is invoked for the verdict (never re-derived)
# ---------------------------------------------------------------------------


def test_r1_authorize_write_invoked(tmp_path: Path) -> None:
    """R1: reconcile_board MUST invoke reversibility_certificate.authorize_write."""
    store = _store(tmp_path)
    spec = _spec([_leaf("leaf1", "infiquetra/x#42")])

    cert_mod: Any = sys.modules["reversibility_certificate"]
    original = cert_mod.authorize_write
    invocations: list[Any] = []

    def spy(op_kind: Any) -> Any:
        invocations.append(op_kind)
        return original(op_kind)

    try:
        cert_mod.authorize_write = spy
        writer = RecordingWriter()
        SYNC_MOD.reconcile_board(spec, store, board_writer=writer)
    finally:
        cert_mod.authorize_write = original

    assert invocations, (
        "authorize_write must be called at least once per candidate op — "
        "a consumer that re-derives its own verdict violates R1"
    )


# ---------------------------------------------------------------------------
# Ledger isolation: board-op keys in board-sync, NOT in events_dir (KTD4, R9)
# ---------------------------------------------------------------------------


def test_ledger_isolation_board_sync_separate_from_events_dir(tmp_path: Path) -> None:
    """KTD4: board-sync ledger is strictly separate from events_dir; derive_states unaffected."""
    store = _store(tmp_path)
    spec = _spec([_leaf("leaf1", "infiquetra/x#42")])
    writer = RecordingWriter()

    result = SYNC_MOD.reconcile_board(spec, store, board_writer=writer)

    written = [r for r in result if r.get("status") == "written"]
    assert written, "at least one op must be written to exercise the ledger"

    # Board-op keys live under board-sync, not events_dir
    ledger_dir = Path(store.root) / "board-sync"
    assert ledger_dir.exists(), "board-sync ledger dir must be created"
    ledger_files = list(ledger_dir.glob("*.json"))
    assert ledger_files, "board-sync ledger files must be created for written ops"

    # events_dir must NOT contain any board-op key content
    events_dir = Path(store.root) / "events"
    if events_dir.exists():
        for ef in events_dir.rglob("*.json"):
            content = ef.read_text()
            try:
                data = json.loads(content)
            except json.JSONDecodeError:
                continue
            # Board-op idempotency keys look like "set-field-status:#N:..." — confirm none present.
            # The events_dir holds CompletionEvent records; a board-op key fed here would crash
            # validate (non-terminal state) or pollute the leaf frontier (KTD4).
            ikey = data.get("idempotency_key", "")
            board_op_prefixes = ("set-field-status:", "sub-issue-close:", "issue-progress-comment:")
            assert not any(ikey.startswith(p) for p in board_op_prefixes), (
                f"board-op idempotency key found in events_dir: {ef} — KTD4 violation"
            )

    # derive_states is still correct — leaf1 is still "ready" (no completion event written)
    states = ENG_MOD.derive_states(spec, store)
    assert states["leaf1"] == "ready", (
        "derive_states must not be polluted by board-sync ledger writes"
    )

    # completed_subplots does not count leaf1 (board writes ≠ completion events)
    completed = STORE_MOD.completed_subplots(store)
    assert "leaf1" not in completed, "board-sync writes must not appear in completed_subplots"


# ---------------------------------------------------------------------------
# KTD8: drive the REAL advance() entrypoint (no-dead-wiring — U1 is live via U4)
# ---------------------------------------------------------------------------


def _git_repo(tmp_path: Path) -> Path:
    repo = tmp_path / "repo"
    repo.mkdir()
    env = {
        "GIT_AUTHOR_NAME": "t",
        "GIT_AUTHOR_EMAIL": "t@t",
        "GIT_COMMITTER_NAME": "t",
        "GIT_COMMITTER_EMAIL": "t@t",
        "PATH": os.environ.get("PATH", ""),
    }
    subprocess.run(["git", "init", "-q"], cwd=repo, check=True, env=env)
    return repo


def test_advance_autonomous_drives_board_sync(tmp_path: Path) -> None:
    """KTD8: the REAL advance(autonomous=True) entrypoint drives reconcile_board → the
    certificate → the injected board_writer, surfacing records in AdvanceResult.board_synced.

    Proves U1 is a live producer+consumer (not dead-wired). A 'done' leaf maps to sub-issue-close,
    so no dispatch/gh is needed — the autonomous board write is the only side effect (a fake writer)."""
    repo = _git_repo(tmp_path)
    ENG_MOD.start(repo, "o", "ship", nodes=[_leaf("leaf1", "infiquetra/x#42")])
    store = ENG_MOD._store(repo, "o")
    DEC_MOD.approve_frontier(store, ENG_MOD.load_spec(repo, "o"))
    _done(store, "leaf1", "done")  # derive_states -> "done" -> sub-issue-close

    writer = RecordingWriter()
    result = ENG_MOD.advance(repo, "o", autonomous=True, board_writer=writer, attending=False)

    assert any(
        r["op_kind"] == "sub-issue-close" and r["status"] == "written" for r in result.board_synced
    ), "advance(autonomous=True) must drive the board-sync close for a done leaf"
    assert writer.calls_for("sub-issue-close"), "the real advance() must call the injected writer"
    assert result.to_dict()["board_synced"], "board_synced surfaces in the AdvanceResult envelope"


def test_advance_without_autonomous_does_no_board_sync(tmp_path: Path) -> None:
    """The default path (autonomous=False) performs NO board writes — the capability is opt-in."""
    repo = _git_repo(tmp_path)
    ENG_MOD.start(repo, "o", "ship", nodes=[_leaf("leaf1", "infiquetra/x#42")])
    store = ENG_MOD._store(repo, "o")
    DEC_MOD.approve_frontier(store, ENG_MOD.load_spec(repo, "o"))
    _done(store, "leaf1", "done")

    writer = RecordingWriter()
    result = ENG_MOD.advance(
        repo, "o", board_writer=writer, attending=False
    )  # autonomous defaults False
    assert result.board_synced == [], "no board-sync unless autonomous=True"
    assert writer.calls == [], "the writer must not be called on the default path"


# ---------------------------------------------------------------------------
# Production _default_board_writer: op_kind -> mission-control CLI command construction
# ---------------------------------------------------------------------------


def test_default_board_writer_builds_correct_commands(tmp_path: Path) -> None:
    """Each OpKind maps to the right sdlc_manager.py subcommand (construction-only, fake runner)."""
    calls: list[list[str]] = []

    class _Ok:
        returncode = 0
        stderr = ""

    def fake_run(cmd: list[str], **kw: Any) -> Any:
        calls.append(cmd)
        return _Ok()

    writer = ENG_MOD._default_board_writer(tmp_path, project="operations", runner=fake_run)
    # Pass the OWNER-QUALIFIED repo (as the consumer does) — the writer must strip the owner so the
    # mc verbs (which prepend ORG) build a valid path, not repos/infiquetra/infiquetra/x/...
    writer(
        op_kind="set-field-status",
        repo="infiquetra/x",
        number=42,
        payload={"target_state": "In Progress"},
    )
    writer(op_kind="sub-issue-close", repo="infiquetra/x", number=42, payload={})
    writer(op_kind="issue-progress-comment", repo="infiquetra/x", number=42, payload={"body": "hi"})
    writer(op_kind="issue-label-add", repo="infiquetra/x", number=42, payload={"label": "blocked"})
    writer(
        op_kind="issue-label-remove", repo="infiquetra/x", number=42, payload={"label": "blocked"}
    )

    assert all("sdlc_manager.py" in c[1] for c in calls)
    # Owner stripped to the bare repo name on every command (no owner-qualified repo leaks through).
    for c in calls:
        assert "x" in c and "infiquetra/x" not in c
    assert calls[0][2:6] == ["flow", "set-field", "--project", "operations"]
    assert "Status" in calls[0] and "In Progress" in calls[0]
    assert calls[1][2:4] == ["issue", "close"] and "42" in calls[1]
    assert calls[2][2:4] == ["issue", "comment"] and "hi" in calls[2]
    assert calls[3][2:4] == ["issue", "label-add"] and "blocked" in calls[3]
    assert calls[4][2:4] == ["issue", "label-remove"] and "blocked" in calls[4]


def test_default_board_writer_raises_on_nonzero_exit(tmp_path: Path) -> None:
    """A non-zero exit raises so the consumer's bounded-retry / fail-loud path engages."""

    class _Fail:
        returncode = 1
        stderr = "boom"

    writer = ENG_MOD._default_board_writer(tmp_path, runner=lambda *a, **k: _Fail())
    with pytest.raises(RuntimeError, match="board write"):
        writer(op_kind="sub-issue-close", repo="x", number=1, payload={})


def test_default_board_writer_rejects_unknown_op_kind(tmp_path: Path) -> None:
    """An op_kind with no verb mapping fails loudly (defensive — the map is the whole envelope)."""
    writer = ENG_MOD._default_board_writer(tmp_path, runner=lambda *a, **k: None)
    with pytest.raises(ValueError, match="no mission-control verb mapping"):
        writer(op_kind="merge", repo="x", number=1, payload={})


# ---------------------------------------------------------------------------
# Adversarial-verify regressions (two P2 holes found by the U4 refute panel)
# ---------------------------------------------------------------------------


def test_cross_repo_same_issue_number_does_not_collide(tmp_path: Path) -> None:
    """P2 regression: two ready leaves with the SAME issue number in DIFFERENT repos must EACH get
    their board write — the repo-qualified idempotency key prevents one silently skipping the other."""
    store = _store(tmp_path)
    spec = _spec(
        [
            {
                "subplot_id": "a",
                "title": "a",
                "kind": "code",
                "github": {"issue": "infiquetra/saga#5"},
            },
            {
                "subplot_id": "b",
                "title": "b",
                "kind": "code",
                "github": {"issue": "infiquetra/mission-control#5"},
            },
        ]
    )
    writer = RecordingWriter()
    result = SYNC_MOD.reconcile_board(spec, store, board_writer=writer)

    repos = {c["repo"] for c in writer.calls_for("set-field-status")}
    assert repos == {"infiquetra/saga", "infiquetra/mission-control"}, (
        f"both repos' #5 must be written, not collide on one ledger key; got {repos}"
    )
    written = [r for r in result if r["op_kind"] == "set-field-status" and r["status"] == "written"]
    assert len(written) == 2, "neither same-number cross-repo write may be silently skipped"


def test_ledger_write_fault_surfaces_not_wedges(tmp_path: Path, monkeypatch: Any) -> None:
    """P2 regression: a ledger-write fault AFTER a successful board write must surface an 'error'
    record (may_reapply) and NOT escape/wedge the tick (which would discard records + orphan the
    side effect)."""
    store = _store(tmp_path)
    spec = _spec([_leaf("leaf1", "infiquetra/x#42")])
    _done(store, "leaf1", "done")  # -> sub-issue-close (+ coalesced comment)

    def _boom(*a: Any, **k: Any) -> bool:
        raise OSError("disk full")

    monkeypatch.setattr(sys.modules["outcome_store"], "_write_once", _boom)

    writer = RecordingWriter()
    result = SYNC_MOD.reconcile_board(spec, store, board_writer=writer)  # must NOT raise

    assert writer.calls_for("sub-issue-close"), "the board write should have been attempted"
    errors = [r for r in result if r["status"] == "error"]
    assert errors, "a ledger fault after a successful board write must surface an error record"
    assert all(r.get("may_reapply") for r in errors)


# ---------------------------------------------------------------------------
# Code-review regressions (negative-terminal boundary + parse/skip edges)
# ---------------------------------------------------------------------------


def test_candidate_ops_negative_terminals_and_blocked_emit_no_op() -> None:
    """P2 regression: a dead/blocked leaf must NOT get an autonomous board op (Scope Boundary).

    Mutation-proof at the boundary itself: a mutant emitting any op for failed/rejected/stalled/blocked
    autonomously advances/closes a dead leaf and this goes red."""
    for dead in ("failed", "rejected", "stalled", "blocked"):
        assert SYNC_MOD._candidate_ops(dead) == [], f"{dead} must yield no board op"
    # positive control — live states DO emit ops (so the test isn't vacuously asserting [])
    assert SYNC_MOD._candidate_ops("ready")
    assert SYNC_MOD._candidate_ops("done")


def test_failed_leaf_drives_no_board_write(tmp_path: Path) -> None:
    """P2 regression (integration): a leaf derived 'failed' → reconcile_board does nothing for it."""
    store = _store(tmp_path)
    spec = _spec([_leaf("leaf1", "infiquetra/x#42")])
    _done(store, "leaf1", "failed")  # negative terminal
    writer = RecordingWriter()
    result = SYNC_MOD.reconcile_board(spec, store, board_writer=writer)
    assert writer.calls == [], "no board write may fire for a failed leaf"
    assert all(r.get("status") not in ("written", "skipped") for r in result)


def test_leaf_without_github_ref_is_skipped(tmp_path: Path) -> None:
    """P3 regression: a ready leaf with no github issue ref is skipped — no record, no write."""
    store = _store(tmp_path)
    spec = _spec([{"subplot_id": "a", "title": "a", "kind": "code", "github": {}}])
    writer = RecordingWriter()
    result = SYNC_MOD.reconcile_board(spec, store, board_writer=writer)
    assert writer.calls == []
    assert result == [], "a leaf with no issue ref produces no board-sync record"


def test_unparseable_issue_ref_surfaces_note_not_crash(tmp_path: Path) -> None:
    """P3 regression: an unparseable issue ref yields a 'note' record and does NOT crash the tick."""
    store = _store(tmp_path)
    spec = _spec(
        [{"subplot_id": "a", "title": "a", "kind": "code", "github": {"issue": "!!garbage"}}]
    )
    writer = RecordingWriter()
    result = SYNC_MOD.reconcile_board(spec, store, board_writer=writer)  # must NOT raise
    assert writer.calls == []
    assert any(r.get("status") == "note" for r in result), "an unparseable ref must surface a note"


def test_parse_issue_ref_accepts_three_forms_and_rejects_garbage() -> None:
    """P3 regression: cover all _parse_issue_ref branches (bare / no-owner / owner-qualified / bad)."""
    assert SYNC_MOD._parse_issue_ref("5") == ("", 5)
    assert SYNC_MOD._parse_issue_ref("repo#5") == ("repo", 5)
    assert SYNC_MOD._parse_issue_ref("infiquetra/saga#5") == ("infiquetra/saga", 5)
    assert SYNC_MOD._parse_issue_ref("!!garbage") is None
    assert SYNC_MOD._parse_issue_ref("") is None
