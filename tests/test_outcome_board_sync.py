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
BP_MOD = _load("board_progression")
SYNC_MOD = _load("outcome_board_sync")


# ---------------------------------------------------------------------------
# Test helpers
# ---------------------------------------------------------------------------


def _live_bp() -> ModuleType:
    """The board_progression object ``reconcile_board`` imports at call time.

    ``reconcile_board`` does ``import board_progression as _bp`` (lazy, resolved through
    ``sys.modules``), and every ``_load`` in the suite reassigns that slot — so a collection-time
    handle goes stale in a full-suite run. Reading ``sys.modules`` at test-run time is
    order-independent and always names the object the code under test will actually use.
    """
    return sys.modules["board_progression"]


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
# AE1: ready state → set-field-status schema-resolved status written (#326, R5, R16, R19)
# ---------------------------------------------------------------------------


def test_ae1_ready_state_writes_set_field_status(tmp_path: Path) -> None:
    """AE1: a leaf in ready state on the default (operations) board resolves to "Ready" — the
    intent_flow schema value, NOT the campps-workflow "In Progress" literal (#326)."""
    store = _store(tmp_path)
    # No completion events and no deps → leaf1 is in the ready frontier.
    spec = _spec([_leaf("leaf1", "infiquetra/x#42")])
    writer = RecordingWriter()

    result = SYNC_MOD.reconcile_board(spec, store, board_writer=writer)

    sf_records = [r for r in result if r.get("op_kind") == "set-field-status"]
    assert sf_records, "expected a set-field-status record for a ready leaf"
    r = sf_records[0]
    assert r["status"] == "written", f"expected written, got {r['status']!r}"
    assert r["target_state"] == "Ready"
    assert r["repo"] == "infiquetra/x"
    assert r["number"] == 42

    sf_calls = writer.calls_for("set-field-status")
    assert len(sf_calls) == 1, "board_writer must be called exactly once for set-field-status"
    assert sf_calls[0]["repo"] == "infiquetra/x"
    assert sf_calls[0]["number"] == 42
    assert sf_calls[0]["payload"].get("target_state") == "Ready"


@pytest.mark.parametrize(
    ("project", "state", "expected"),
    [
        ("operations", "dispatched", "Active"),
        ("asgard", "dispatched", "Active"),
        ("campps", "dispatched", "In Progress"),
        ("asgard", "ready", "Ready"),
        ("campps", "ready", "Committed"),
    ],
)
def test_schema_resolved_status_per_project(
    tmp_path: Path, project: str, state: str, expected: str
) -> None:
    """#326 KTD1/KTD2: ready/dispatched resolve per-project from the real sdlc-schema.json — proves
    the fix is correct for every board, not just a literal Active swap for operations."""
    store = _store(tmp_path)
    spec = _spec([_leaf("leaf1", "infiquetra/x#42")])
    if state == "dispatched":
        # A settled (commit-phase) dispatch ledger record — the same shape derive_states()
        # requires (outcome.py:319) to surface LIVE_DISPATCHED instead of LIVE_READY.
        STORE_MOD.append_ledger(
            store,
            {
                "phase": "commit",
                "kind": "dispatch",
                "key": "d:leaf1",
                "subplot_id": "leaf1",
                "leaf_saga_id": "l-leaf1",
            },
        )
    writer = RecordingWriter()

    result = SYNC_MOD.reconcile_board(spec, store, board_writer=writer, project=project)

    sf_records = [r for r in result if r.get("op_kind") == "set-field-status"]
    assert sf_records and sf_records[0]["status"] == "written"
    assert sf_records[0]["target_state"] == expected


def test_candidate_ops_no_hardcoded_board_status_literal() -> None:
    """#326: no hardcoded ladder literal remains in the module source — schema-resolve only."""
    source = (SCRIPTS / "outcome_board_sync.py").read_text()
    assert '"In Progress"' not in source, (
        "outcome_board_sync.py must not contain a hardcoded board-status literal"
    )


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
    comment_body = writer1.calls_for("issue-progress-comment")[0]["payload"]["body"]
    assert "saga /outcome board-sync: leaf `leaf1` reached state `done`." in comment_body
    assert "<!-- saga-board-sync-idempotency:" in comment_body
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
    # _safe_ledger_name to handle the SHA-1 fallback for keys with unsafe characters.
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


def test_advance_threads_project_to_reconcile_board_for_nondefault_project(tmp_path: Path) -> None:
    """#326 R4: advance(project=...) threads the SAME project value into reconcile_board's schema
    resolution — proven through the REAL advance() entrypoint, not just a direct reconcile_board
    call, for both asgard and campps (not just the default operations).

    A leaf starting "ready" is dispatched within the SAME advance() tick (dispatch runs before
    board-sync each tick), so by the time board-sync observes it the derived state is
    "dispatched" — this test proves threading through that real, naturally-reached path."""
    for project, expected_dispatched in (("asgard", "Active"), ("campps", "In Progress")):
        project_root = tmp_path / project
        project_root.mkdir()
        repo = _git_repo(project_root)
        ENG_MOD.start(repo, "o", "ship", nodes=[_leaf("leaf1", "infiquetra/x#42")])
        store = ENG_MOD._store(repo, "o")
        DEC_MOD.approve_frontier(store, ENG_MOD.load_spec(repo, "o"))
        # No completion event → leaf1 starts "ready"; advance() dispatches it this same tick.

        writer = RecordingWriter()
        result = ENG_MOD.advance(
            repo, "o", autonomous=True, board_writer=writer, project=project, attending=False
        )

        sf_records = [r for r in result.board_synced if r.get("op_kind") == "set-field-status"]
        assert sf_records and sf_records[0]["status"] == "written", (
            f"{project}: expected a written set-field-status record, got {sf_records}"
        )
        assert sf_records[0]["target_state"] == expected_dispatched, (
            f"{project}: advance() did not thread its project into reconcile_board's resolution"
        )
        assert (
            writer.calls_for("set-field-status")[0]["payload"]["target_state"]
            == expected_dispatched
        )


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
    assert "--correction" in calls[0]
    assert calls[1][2:4] == ["issue", "close"] and "42" in calls[1]
    assert calls[2][2:4] == ["issue", "comment"] and "hi" in calls[2]
    assert calls[3][2:4] == ["issue", "label-add"] and "blocked" in calls[3]
    assert calls[4][2:4] == ["issue", "label-remove"] and "blocked" in calls[4]


def test_default_board_writer_respects_nondefault_project(tmp_path: Path) -> None:
    """#326: _default_board_writer's --project flag reflects a NON-default project (not just the
    "operations" default every other command-construction test exercises)."""
    calls: list[list[str]] = []

    class _Ok:
        returncode = 0
        stderr = ""

    def fake_run(cmd: list[str], **kw: Any) -> Any:
        calls.append(cmd)
        return _Ok()

    writer = ENG_MOD._default_board_writer(tmp_path, project="asgard", runner=fake_run)
    writer(
        op_kind="set-field-status",
        repo="infiquetra/x",
        number=42,
        payload={"target_state": "Active"},
    )

    assert calls[0][2:6] == ["flow", "set-field", "--project", "asgard"]


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
# #620: mission-control resolution — consumer-repo success, unavailable cohort,
# stale-fleet-core degrade (KTD6/R11), provenance stamping (R7).
# ---------------------------------------------------------------------------


def _make_schema_root(base: Path) -> Path:
    """A minimal resolved mission-control root carrying a real phase_board_map schema."""
    (base / "config").mkdir(parents=True, exist_ok=True)
    (base / "scripts").mkdir(parents=True, exist_ok=True)
    (base / "scripts" / "sdlc_manager.py").write_text("# stub\n")
    (base / "config" / "sdlc-schema.json").write_text(
        json.dumps(
            {
                "saga_lifecycle": {
                    "phase_board_map": {
                        "review": {"operations": ["Ready"]},
                        "work": {"operations": ["Active"]},
                    }
                }
            }
        )
    )
    return base


def test_production_path_resolves_once_and_threads_root_to_schema_and_writer(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """R2/R3/R4: with board_writer=None (production), reconcile_board resolves the mission-control
    root ONCE and uses it for BOTH the schema read and the writer — proven by driving a ready leaf
    whose status comes from the resolved root's schema, from a simulated non-monorepo layout."""
    mc_root = _make_schema_root(
        tmp_path / "cache" / "infiquetra-plugins" / "mission-control" / "2.10.1"
    )
    calls: list[dict[str, Any]] = []
    resolve_count = {"n": 0}

    def fake_resolve() -> tuple[Path, int]:
        resolve_count["n"] += 1  # R4: prove the tick resolves at most ONCE, not per-op/per-consumer
        return (mc_root, 3)  # rung 3 = installed-plugins, the consumer-repo governing rung

    def fake_writer_factory(
        *, mission_control_root: Path, project: str = "operations", runner: Any = None
    ):
        assert mission_control_root == mc_root  # the resolved root reaches the writer (R4)

        def _w(*, op_kind: str, repo: str, number: int, payload: dict) -> None:
            calls.append({"op_kind": op_kind, "number": number, "payload": payload})

        return _w

    monkeypatch.setattr(_live_bp(), "resolve_mission_control_root", fake_resolve)
    monkeypatch.setattr(_live_bp(), "default_board_writer", fake_writer_factory)

    store = _store(tmp_path)
    spec = _spec([_leaf("leaf1", "infiquetra/x#42")])
    result = SYNC_MOD.reconcile_board(spec, store, board_writer=None)  # production entry

    # R4: exactly one resolution for the whole tick — a double-resolving implementation fails here.
    assert resolve_count["n"] == 1

    sf = [r for r in result if r.get("op_kind") == "set-field-status"]
    assert sf and sf[0]["status"] == "written"
    assert (
        sf[0]["target_state"] == "Ready"
    )  # resolved from mc_root's schema, not a hardcoded literal
    assert any(c["op_kind"] == "set-field-status" for c in calls)
    # R7: provenance on the returned record, from the SAME resolution that fed the schema.
    assert sf[0]["board_sync_root"] == str(mc_root)
    assert sf[0]["board_sync_rung"] == 3

    # R7 (F3): provenance is PERSISTED to the durable board-sync ledger, not just the return value —
    # so a stale resolution is diagnosable by reading the ledger later, never re-derived.
    ledger_files = list((Path(store.root) / "board-sync").glob("*.json"))
    persisted = [json.loads(p.read_text()) for p in ledger_files]
    sf_persisted = [rec for rec in persisted if rec.get("op_kind") == "set-field-status"]
    assert sf_persisted, "expected a persisted set-field-status ledger record"
    assert sf_persisted[0]["board_sync_root"] == str(mc_root)
    assert sf_persisted[0]["board_sync_rung"] == 3


def test_unresolvable_root_withholds_the_whole_cohort_with_one_record(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """R5/R6/KTD3: when mission-control cannot be resolved, a multi-leaf multi-op tick yields
    EXACTLY ONE 'unavailable' record and drives nothing — not N ops × max_attempts retries."""

    def boom() -> tuple[Path, int]:
        raise RuntimeError("plugin-resolution: could not resolve a 'mission-control' root")

    monkeypatch.setattr(_live_bp(), "resolve_mission_control_root", boom)

    store = _store(tmp_path)
    # Three ready leaves → six candidate ops pre-fix (status + comment each). Must collapse to one.
    spec = _spec(
        [
            _leaf("leaf1", "infiquetra/x#1"),
            _leaf("leaf2", "infiquetra/x#2"),
            _leaf("leaf3", "infiquetra/x#3"),
        ]
    )
    result = SYNC_MOD.reconcile_board(spec, store, board_writer=None)

    assert len(result) == 1
    assert result[0]["status"] == "unavailable"
    assert "could not resolve" in result[0]["reason"]


def test_stale_fleet_core_missing_plugin_resolution_degrades_not_crashes(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """R11/KTD6: a fleet-core too old to carry plugin_resolution (the #642-stale-registry case)
    surfaces as a RuntimeError naming #642 — NOT an uncaught ImportError that kills the tick."""
    import fleet_commons_shim

    def raise_missing(module: str) -> Any:
        # The real shim's message names the resolved fleet-core root AND version; the wrapper must
        # preserve them via its `({exc})` interpolation (R11 — the reason must stay actionable).
        raise RuntimeError(
            f"fleet-commons: module {module!r} not found at /cache/fleet-core/0.22.0 "
            "(fleet-core resolved to /cache/fleet-core/0.22.0, version 0.22.0)."
        )

    monkeypatch.setattr(fleet_commons_shim, "load", raise_missing)
    with pytest.raises(RuntimeError) as excinfo:
        _live_bp().resolve_mission_control_root()
    message = str(excinfo.value)
    assert "plugin_resolution" in message
    assert "#642" in message
    # R11: the wrapped reason still names the resolved fleet-core root + version, so a stale-registry
    # operator knows exactly which install to hand-repair — not just that "something" is missing.
    assert "0.22.0" in message
    assert "/cache/fleet-core/0.22.0" in message


def test_reconcile_board_routes_stale_fleet_core_into_the_unavailable_record(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """R11 end-to-end: the KTD6 RuntimeError becomes the single unavailable cohort record, so board
    sync degrades instead of the whole advance tick dying on an import error."""

    def boom() -> tuple[Path, int]:
        raise RuntimeError(
            "board-sync: the resolved fleet-core cannot provide plugin_resolution ... (see #642)."
        )

    monkeypatch.setattr(_live_bp(), "resolve_mission_control_root", boom)
    store = _store(tmp_path)
    spec = _spec([_leaf("leaf1", "infiquetra/x#42")])
    result = SYNC_MOD.reconcile_board(spec, store, board_writer=None)
    assert len(result) == 1
    assert result[0]["status"] == "unavailable"
    assert "#642" in result[0]["reason"]


def test_injected_writer_never_triggers_root_resolution(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The test seam is preserved: an injected board_writer means the resolver is never called for
    the writer, so a broken resolver cannot break a writer-injected (test) reconcile."""

    def must_not_run() -> tuple[Path, int]:
        raise AssertionError(
            "resolve_mission_control_root must not be called when a writer is injected"
        )

    monkeypatch.setattr(_live_bp(), "resolve_mission_control_root", must_not_run)
    store = _store(tmp_path)
    spec = _spec([_leaf("leaf1", "infiquetra/x#42")])
    writer = RecordingWriter()
    # schema_path supplied so the ready leaf's status resolves without touching the resolver either.
    schema = _make_schema_root(tmp_path / "mc") / "config" / "sdlc-schema.json"
    result = SYNC_MOD.reconcile_board(spec, store, board_writer=writer, schema_path=schema)
    assert any(r.get("op_kind") == "set-field-status" for r in result)


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
    status_map = {"ready": "Ready", "dispatched": "Active"}
    for dead in ("failed", "rejected", "stalled", "blocked"):
        assert SYNC_MOD._candidate_ops(dead, status_map) == [], f"{dead} must yield no board op"
    # positive control — live states DO emit ops (so the test isn't vacuously asserting [])
    assert SYNC_MOD._candidate_ops("ready", status_map)
    assert SYNC_MOD._candidate_ops("done", status_map)


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


# ---------------------------------------------------------------------------
# #326 R5/KTD4: schema resolution failure is per-op fail-loud + retryable, never tick-fatal
# ---------------------------------------------------------------------------


def test_schema_resolution_missing_file_fails_status_op_but_comment_still_posts(
    tmp_path: Path,
) -> None:
    """A missing schema file: set-field-status records 'failed' with no ledger key (retryable);
    the coalesced issue-progress-comment for the same leaf still proceeds and is written."""
    store = _store(tmp_path)
    spec = _spec([_leaf("leaf1", "infiquetra/x#42")])
    writer = RecordingWriter()

    result = SYNC_MOD.reconcile_board(
        spec, store, board_writer=writer, schema_path=tmp_path / "nonexistent-schema.json"
    )

    sf_records = [r for r in result if r.get("op_kind") == "set-field-status"]
    assert sf_records and sf_records[0]["status"] == "failed"
    assert "error" in sf_records[0]

    comment_records = [r for r in result if r.get("op_kind") == "issue-progress-comment"]
    assert comment_records and comment_records[0]["status"] == "written"
    assert writer.calls_for("issue-progress-comment"), "comment write must still fire"
    assert not writer.calls_for("set-field-status"), (
        "no board_writer attempt without a resolved status"
    )

    ledger_dir = Path(store.root) / "board-sync"
    ledger_files = list(ledger_dir.glob("*.json")) if ledger_dir.exists() else []
    assert len(ledger_files) == 1, "only the comment's ledger key is written, not a status key"


def test_schema_resolution_missing_project_fails_status_op_retryably(tmp_path: Path) -> None:
    """A project absent from phase_board_map: same failed/retryable semantics as a missing file —
    including no board_writer attempt, no ledger key, and the comment still posting."""
    store = _store(tmp_path)
    spec = _spec([_leaf("leaf1", "infiquetra/x#42")])
    writer = RecordingWriter()

    result = SYNC_MOD.reconcile_board(spec, store, board_writer=writer, project="no-such-project")

    sf_records = [r for r in result if r.get("op_kind") == "set-field-status"]
    assert sf_records and sf_records[0]["status"] == "failed"
    assert "error" in sf_records[0]
    assert not writer.calls_for("set-field-status"), (
        "no board_writer attempt without a resolved status"
    )

    comment_records = [r for r in result if r.get("op_kind") == "issue-progress-comment"]
    assert comment_records and comment_records[0]["status"] == "written"
    assert writer.calls_for("issue-progress-comment"), "comment write must still fire"

    ledger_dir = Path(store.root) / "board-sync"
    ledger_files = list(ledger_dir.glob("*.json")) if ledger_dir.exists() else []
    assert len(ledger_files) == 1, "only the comment's ledger key is written, not a status key"


@pytest.mark.parametrize(
    "corrupt_schema",
    [
        "not valid json {{{",
        json.dumps({"no_saga_lifecycle_key": True}),
        json.dumps({"saga_lifecycle": {"phase_board_map": {}}}),  # missing review/work rows
        json.dumps(
            {
                "saga_lifecycle": {
                    "phase_board_map": {
                        "review": {"operations": []},
                        "work": {"operations": ["Active"]},
                    }
                }
            }
        ),  # noqa: E501
    ],
    ids=["malformed-json", "missing-saga-lifecycle", "missing-phase-rows", "empty-status-list"],
)
def test_schema_resolution_corrupt_schema_fails_status_op(
    tmp_path: Path, corrupt_schema: str
) -> None:
    """#326: every corrupt-schema shape (malformed JSON, missing keys, empty status list) hits the
    same fail-loud/retryable path as a missing file — never a raw exception escaping reconcile_board."""
    bad_schema = tmp_path / "bad-schema.json"
    bad_schema.write_text(corrupt_schema)
    store = _store(tmp_path)
    spec = _spec([_leaf("leaf1", "infiquetra/x#42")])
    writer = RecordingWriter()

    result = SYNC_MOD.reconcile_board(spec, store, board_writer=writer, schema_path=bad_schema)

    sf_records = [r for r in result if r.get("op_kind") == "set-field-status"]
    assert sf_records and sf_records[0]["status"] == "failed"
    assert "error" in sf_records[0]


def test_schema_resolution_retries_successfully_on_next_call(tmp_path: Path) -> None:
    """After a failed resolution (no ledger key written), a subsequent call with a valid schema
    path succeeds — proving the failure is genuinely retryable, not permanently stuck."""
    store = _store(tmp_path)
    spec = _spec([_leaf("leaf1", "infiquetra/x#42")])

    bad_writer = RecordingWriter()
    SYNC_MOD.reconcile_board(
        spec, store, board_writer=bad_writer, schema_path=tmp_path / "nonexistent-schema.json"
    )

    good_writer = RecordingWriter()
    result2 = SYNC_MOD.reconcile_board(spec, store, board_writer=good_writer)

    sf_records = [r for r in result2 if r.get("op_kind") == "set-field-status"]
    assert sf_records and sf_records[0]["status"] == "written"
    assert sf_records[0]["target_state"] == "Ready"


def test_done_leaf_never_touches_schema_file(tmp_path: Path) -> None:
    """A done-only leaf never needs a status resolution — a missing/bogus schema_path must not
    affect it (the lazy-resolution guarantee KTD3 depends on)."""
    store = _store(tmp_path)
    spec = _spec([_leaf("leaf1", "infiquetra/x#42")])
    _done(store, "leaf1", "done")
    writer = RecordingWriter()

    result = SYNC_MOD.reconcile_board(
        spec, store, board_writer=writer, schema_path=tmp_path / "nonexistent-schema.json"
    )

    close_records = [r for r in result if r.get("op_kind") == "sub-issue-close"]
    assert close_records and close_records[0]["status"] == "written"


# ---------------------------------------------------------------------------
# hold_issues — #295 U5/KTD3 drift-hold: withhold ONLY the drifted issue's ops
# ---------------------------------------------------------------------------


def test_hold_issues_withholds_only_that_issues_ops(tmp_path: Path) -> None:
    """A held issue's candidate ops become drift-hold records; other leaves are written normally."""
    store = _store(tmp_path)
    spec = _spec([_leaf("l1", "infiquetra/x#42"), _leaf("l2", "infiquetra/x#99")])
    writer = RecordingWriter()
    result = SYNC_MOD.reconcile_board(
        spec, store, board_writer=writer, hold_issues={("infiquetra/x", 42)}
    )
    held = [r for r in result if r.get("status") == "drift-hold"]
    assert held, "expected drift-hold records for the held issue"
    assert all(r["number"] == 42 for r in held)  # only #42 withheld
    # #42's board ops were NOT driven; #99's were.
    driven_numbers = {c["number"] for c in writer.calls}
    assert 42 not in driven_numbers
    assert 99 in driven_numbers


def test_hold_issues_none_is_byte_identical_to_today(tmp_path: Path) -> None:
    """With no hold set, board-sync behavior is unchanged (regression guard for the new param)."""
    store_a = _store(tmp_path / "a")
    store_b = _store(tmp_path / "b")
    spec_a = _spec([_leaf("l1", "infiquetra/x#42")])
    spec_b = _spec([_leaf("l1", "infiquetra/x#42")])
    r_default = SYNC_MOD.reconcile_board(spec_a, store_a, board_writer=RecordingWriter())
    r_none = SYNC_MOD.reconcile_board(
        spec_b, store_b, board_writer=RecordingWriter(), hold_issues=None
    )
    assert [r["status"] for r in r_default] == [r["status"] for r in r_none]
    assert not [r for r in r_none if r.get("status") == "drift-hold"]


# ---------------------------------------------------------------------------
# #449 R5/AC4 — the board-sync ledger's authorizing_envelope_id extension
# (merge-class records ONLY; every non-merge record is untouched)
# ---------------------------------------------------------------------------

BP_MOD = _load("board_progression")

_FP = "sha256:" + "a" * 64


def _merge_record(store: Any, **kw: Any) -> Any:
    defaults: dict[str, Any] = {
        "phase": "authorized",
        "outcome_id": "o",
        "subplot_id": "build",
        "pr": "7",
        "authorizing_envelope_id": _FP,
        "token_id": "emt-1",
    }
    defaults.update(kw)
    return BP_MOD.record_envelope_authorized_merge(SYNC_MOD._board_sync_dir(store), **defaults)


def test_authorizing_envelope_id_on_merge_ledger_record(tmp_path: Path) -> None:
    """AC4: the ledger JSON written for an envelope-authorized merge carries the correct
    authorizing_envelope_id (and token_id), in BOTH phases, under the board-sync dir."""
    store = _store(tmp_path)
    for phase in ("authorized", "merged"):
        result = _merge_record(store, phase=phase)
        assert result["status"] == "written"
    ledger_dir = SYNC_MOD._board_sync_dir(store)
    records = [json.loads(p.read_text(encoding="utf-8")) for p in sorted(ledger_dir.glob("*.json"))]
    assert len(records) == 2
    for record in records:
        assert record["authorizing_envelope_id"] == _FP
        assert record["token_id"] == "emt-1"
        assert record["op_kind"] == "merge-under-envelope"
        assert record["phase"] in ("authorized", "merged")
        assert "ts" in record


def test_authorizing_envelope_merge_record_is_write_once(tmp_path: Path) -> None:
    store = _store(tmp_path)
    assert _merge_record(store)["status"] == "written"
    assert _merge_record(store)["status"] == "skipped"  # idempotent under the same key


def test_authorizing_envelope_merge_record_refuses_missing_attribution(tmp_path: Path) -> None:
    """An unattributed merge record must be impossible to write (fail closed)."""
    store = _store(tmp_path)
    with pytest.raises(ValueError, match="unattributed"):
        _merge_record(store, authorizing_envelope_id="")
    with pytest.raises(ValueError, match="unattributed"):
        _merge_record(store, token_id="")
    with pytest.raises(ValueError, match="closed vocabulary"):
        _merge_record(store, phase="pending")  # off-vocabulary phase


def test_authorizing_envelope_merge_record_write_fault_is_surfaced(tmp_path: Path) -> None:
    """A ledger fault comes back as a status:error record — never an escaping exception
    (the merged-phase caller's squash has already committed)."""
    store = _store(tmp_path)

    def broken_write_once(path: Path, content: str) -> bool:
        raise OSError("disk full")

    result = BP_MOD.record_envelope_authorized_merge(
        SYNC_MOD._board_sync_dir(store),
        phase="merged",
        outcome_id="o",
        subplot_id="build",
        pr="7",
        authorizing_envelope_id=_FP,
        token_id="emt-1",
        write_once=broken_write_once,
    )
    assert result["status"] == "error" and "disk full" in result["error"]


def test_non_merge_ledger_records_carry_no_authorizing_envelope_id(tmp_path: Path) -> None:
    """R5 boundary control: the schema extension is merge-record-specific — a normal
    board-sync write's ledger record gains NO authorizing_envelope_id key."""
    store = _store(tmp_path)
    spec = _spec([_leaf("l1", "infiquetra/x#42")])
    _done(store, "l1")
    SYNC_MOD.reconcile_board(spec, store, board_writer=RecordingWriter())
    ledger_dir = SYNC_MOD._board_sync_dir(store)
    records = [json.loads(p.read_text(encoding="utf-8")) for p in ledger_dir.glob("*.json")]
    assert records, "expected at least one non-merge ledger record"
    for record in records:
        assert "authorizing_envelope_id" not in record
        assert "token_id" not in record


def test_cross_era_merge_records_do_not_collide(tmp_path: Path) -> None:
    """#449 panel hand-finish (P2): the record key carries the token era — a second
    authorization of the SAME merge (same outcome/subplot/pr/phase) under a NEW token
    writes its own record instead of write-once-deduping against the dead era's, while
    repeats within one era still dedup."""
    store = _store(tmp_path)
    assert _merge_record(store, token_id="emt-era-a")["status"] == "written"
    assert _merge_record(store, token_id="emt-era-b")["status"] == "written"
    assert _merge_record(store, token_id="emt-era-b")["status"] == "skipped"
