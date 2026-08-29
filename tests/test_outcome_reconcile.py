"""Tests outcome_reconcile — board<->saga drift detection + HITL resolution (#295).

detect() is a pure classification over a REAL store's board-sync ledger (seeded with #279-shaped
records) plus injected fake board/issue readers — no live gh ever fires (conftest _no_live_gh guard).
Requirement traceability: R1-R9; KTD1-KTD7. Test names preserve issue #295's acceptance -k selectors.
"""

from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path
from types import ModuleType
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


# Load in dependency order (mirrors test_outcome_board_sync.py).
SPEC_MOD = _load("outcome_spec")
STORE_MOD = _load("outcome_store")
_load("outcome_orchestrator")
_load("outcome_dispatcher")
_load("outcome_merge")
_load("outcome_worktrees")
_load("outcome_decompose")
_load("outcome")
CERT_MOD = _load("reversibility_certificate")
SYNC_MOD = _load("outcome_board_sync")
RECON = _load("outcome_reconcile")


# ---------------------------------------------------------------------------
# Fixtures / helpers
# ---------------------------------------------------------------------------


def _store(tmp_path: Path) -> Any:
    return STORE_MOD.Store(root=tmp_path / "store").ensure()


def _spec(nodes: list[dict[str, Any]]) -> Any:
    return SPEC_MOD.OutcomeSpec.from_dict({"outcome_id": "o", "objective": "Ship", "nodes": nodes})


def _leaf(sid: str, issue: str = "infiquetra/x#42", kind: str = "non-code") -> dict[str, Any]:
    return {"subplot_id": sid, "title": sid, "kind": kind, "github": {"issue": issue}}


def _done(store: Any, sid: str) -> None:
    STORE_MOD.write_completion_event(
        store, STORE_MOD.CompletionEvent(subplot_id=sid, state="done", idempotency_key=f"k:{sid}")
    )


_SEED_COUNTER = [0]


def _seed(
    store: Any,
    *,
    op_kind: str,
    repo: str = "infiquetra/x",
    number: int = 42,
    target_state: str = "",
    ts: float = 1.0,
    override: bool = False,
    board_value: str | None = None,
) -> None:
    """Write one #279-shaped ledger record (write record by default; override when ``override``)."""
    d = Path(store.root) / "board-sync"
    d.mkdir(parents=True, exist_ok=True)
    rec: dict[str, Any] = {"op_kind": op_kind, "repo": repo, "number": number, "ts": ts}
    if override:
        rec["kind"] = "reconcile-override"
        rec["board_value"] = board_value if board_value is not None else target_state
        rec["resolution"] = "accept-board"
    else:
        rec["target_state"] = target_state
        rec["key"] = f"{op_kind}:{repo}#{number}:{target_state}"
    _SEED_COUNTER[0] += 1
    (d / f"rec_{_SEED_COUNTER[0]}.json").write_text(json.dumps(rec), encoding="utf-8")


def _readers(
    *,
    status: str = "",
    state: str = "open",
    reason: str = "unknown",
    closed_by: str = "",
    status_calls: list[str] | None = None,
    issue_calls: list[str] | None = None,
):
    def board_reader(ref: str) -> str:
        if status_calls is not None:
            status_calls.append(ref)
        return status

    def issue_reader(ref: str) -> dict[str, str]:
        if issue_calls is not None:
            issue_calls.append(ref)
        return {"state": state, "state_reason": reason, "closed_by": closed_by}

    return board_reader, issue_reader


# ---------------------------------------------------------------------------
# detect() — U3
# ---------------------------------------------------------------------------


def test_silent_when_match(tmp_path: Path) -> None:
    """Live board == asserted Status and issue open → empty list (silent, R4)."""
    store = _store(tmp_path)
    spec = _spec([_leaf("leaf1")])
    _seed(store, op_kind="set-field-status", target_state="Ready")
    board_reader, issue_reader = _readers(status="Ready", state="open")
    assert RECON.detect(spec, store, board_reader=board_reader, issue_reader=issue_reader) == []


def test_surfaces_divergence(tmp_path: Path) -> None:
    """Ledger asserts 'In Progress', live board reads 'Blocked' → one status-drift record (R5)."""
    store = _store(tmp_path)
    spec = _spec([_leaf("leaf1")])
    _seed(store, op_kind="set-field-status", target_state="In Progress")
    board_reader, issue_reader = _readers(status="Blocked", state="open")
    out = RECON.detect(spec, store, board_reader=board_reader, issue_reader=issue_reader)
    drift = [r for r in out if r["kind"] == "status-drift"]
    assert len(drift) == 1
    assert drift[0]["saga_value"] == "In Progress"
    assert drift[0]["board_value"] == "Blocked"
    assert drift[0]["repo"] == "infiquetra/x"
    assert drift[0]["number"] == 42
    assert drift[0]["drift_id"]  # deterministic reference id present


def test_scope_excludes_operator_field(tmp_path: Path) -> None:
    """An issue with no ledger record is never read → no false positive (scope discipline, KTD6)."""
    store = _store(tmp_path)
    spec = _spec([_leaf("leaf1", "infiquetra/x#42"), _leaf("leaf2", "infiquetra/x#99")])
    _seed(store, op_kind="set-field-status", number=42, target_state="Ready")
    status_calls: list[str] = []
    board_reader, issue_reader = _readers(status="Ready", state="open", status_calls=status_calls)
    out = RECON.detect(spec, store, board_reader=board_reader, issue_reader=issue_reader)
    assert out == []
    # leaf2 (#99) has no ledger record → board never probed for it.
    assert all("#99" not in ref for ref in status_calls)
    assert any("#42" in ref for ref in status_calls)


def test_w7_lost_status_key_is_neither_drift_nor_recovered(tmp_path: Path) -> None:
    """W7: a landed-but-unrecorded STATUS write is neither recovered nor flagged. The pre-W7
    recover arm rewrote a lost ledger key from the schema-recomputed expected Status; since
    ``/outcome`` composes no lifecycle-field write (SDLC R30/R34), there is no expected value to
    recompute and no key of ours to heal — the ledger-asserted view (empty for status) is silent."""
    store = _store(tmp_path)
    spec = _spec([_leaf("leaf1")])  # no deps, no completion → the leaf is in the ready frontier
    # In-scope via a coalesced comment record, but (hypothetically, pre-W7) the set-field-status
    # key was lost to a crash.
    _seed(store, op_kind="issue-progress-comment", target_state="ready")
    board_reader, issue_reader = _readers(status="Ready", state="open")
    out = RECON.detect(spec, store, board_reader=board_reader, issue_reader=issue_reader)
    assert not [r for r in out if r["kind"] == "recovered"], (
        "the recover arm for lifecycle-field writes is gone with W7"
    )
    assert not [r for r in out if r["kind"] in RECON.DRIFT_KINDS], (
        "no status assertion exists in the ledger, so a matching live value is not drift"
    )
    assert RECON.detect(spec, store, board_reader=board_reader, issue_reader=issue_reader) == []


def test_w7_detection_never_resolves_the_schema_for_status(
    tmp_path: Path, monkeypatch: Any
) -> None:
    """W7: drift detection never resolves the SDLC schema (the pre-W7 expected-Status recomputation
    seam, #620 KTD5/S4, is retired with the status writes it fed) — a broken resolver cannot break
    detection."""
    import board_progression as _bp

    def must_not_resolve() -> tuple[Path, int]:
        raise AssertionError("detect must not resolve the SDLC schema after W7")

    monkeypatch.setattr(_bp, "resolve_mission_control_root", must_not_resolve)

    store = _store(tmp_path)
    spec = _spec([_leaf("leaf1")])
    _seed(store, op_kind="issue-progress-comment", target_state="ready")
    board_reader, issue_reader = _readers(status="Ready", state="open")
    out = RECON.detect(spec, store, board_reader=board_reader, issue_reader=issue_reader)
    assert out == [], "a comment-only ledger with a matching live board stays silent"


def test_external_close_surfaced(tmp_path: Path) -> None:
    """A not_planned external close is surfaced with its author — never silently adopted (R6, AE1)."""
    store = _store(tmp_path)
    spec = _spec([_leaf("leaf1", kind="non-code")])
    _seed(store, op_kind="set-field-status", target_state="Ready")  # in-scope; status matches below
    board_reader, issue_reader = _readers(
        status="Ready", state="closed", reason="not_planned", closed_by="operator"
    )
    out = RECON.detect(spec, store, board_reader=board_reader, issue_reader=issue_reader)
    close = [r for r in out if r["kind"] == "external-close"]
    assert len(close) == 1
    assert close[0]["board_value"] == "closed"
    assert close[0]["saga_value"] == "open"
    assert close[0]["author"] == "operator"


def test_sanctioned_completed_close_is_silent(tmp_path: Path) -> None:
    """A completed close that satisfies a non-code leaf's contract stays the harvester's silent path."""
    store = _store(tmp_path)
    spec = _spec([_leaf("leaf1", kind="non-code")])
    _seed(store, op_kind="set-field-status", target_state="Ready")
    board_reader, issue_reader = _readers(
        status="Ready", state="closed", reason="completed", closed_by="operator"
    )
    assert RECON.detect(spec, store, board_reader=board_reader, issue_reader=issue_reader) == []


def test_contract_unsatisfied_close_is_drift(tmp_path: Path) -> None:
    """A completed close on a CODE leaf (contract = PR-merged) is drift, not sanctioned (KTD4)."""
    store = _store(tmp_path)
    spec = _spec([_leaf("leaf1", kind="code")])
    _seed(store, op_kind="set-field-status", target_state="Ready")
    board_reader, issue_reader = _readers(status="Ready", state="closed", reason="completed")
    out = RECON.detect(spec, store, board_reader=board_reader, issue_reader=issue_reader)
    assert [r["kind"] for r in out if r["kind"] in RECON.DRIFT_KINDS] == ["external-close"]


def test_unreadable_statereason_degrades_to_contract_only(tmp_path: Path) -> None:
    """Unknown stateReason → contract-only: silent for a satisfying leaf, drift for a non-satisfying one."""
    # Non-code leaf, contract satisfied → silent.
    store_a = _store(tmp_path / "a")
    spec_a = _spec([_leaf("leaf1", kind="non-code")])
    _seed(store_a, op_kind="set-field-status", target_state="Ready")
    br_a, ir_a = _readers(status="Ready", state="closed", reason="unknown")
    assert RECON.detect(spec_a, store_a, board_reader=br_a, issue_reader=ir_a) == []
    # Code leaf, contract NOT satisfied → drift.
    store_b = _store(tmp_path / "b")
    spec_b = _spec([_leaf("leaf1", kind="code")])
    _seed(store_b, op_kind="set-field-status", target_state="Ready")
    br_b, ir_b = _readers(status="Ready", state="closed", reason="unknown")
    out_b = RECON.detect(spec_b, store_b, board_reader=br_b, issue_reader=ir_b)
    assert [r["kind"] for r in out_b if r["kind"] in RECON.DRIFT_KINDS] == ["external-close"]


def test_external_reopen_is_drift(tmp_path: Path) -> None:
    """A recorded sub-issue-close whose issue now reads open → external-reopen drift (AE, R6)."""
    store = _store(tmp_path)
    spec = _spec([_leaf("leaf1")])
    _done(store, "leaf1")  # done → expected Status is "" so the status branch stays quiet
    _seed(store, op_kind="sub-issue-close", target_state="")
    board_reader, issue_reader = _readers(status="Done", state="open")
    out = RECON.detect(spec, store, board_reader=board_reader, issue_reader=issue_reader)
    reopen = [r for r in out if r["kind"] == "external-reopen"]
    assert len(reopen) == 1
    assert reopen[0]["saga_value"] == "closed"
    assert reopen[0]["board_value"] == "open"


def test_override_as_baseline_silences_status_and_close(tmp_path: Path) -> None:
    """An accept-board override becomes the baseline: the accepted value never re-flags (KTD5)."""
    # Status: a later override for 'Blocked' supersedes the earlier 'In Progress' write.
    store_a = _store(tmp_path / "a")
    spec_a = _spec([_leaf("leaf1")])
    _seed(store_a, op_kind="set-field-status", target_state="In Progress", ts=1.0)
    _seed(store_a, op_kind="set-field-status", override=True, board_value="Blocked", ts=2.0)
    br_a, ir_a = _readers(status="Blocked", state="open")
    assert RECON.detect(spec_a, store_a, board_reader=br_a, issue_reader=ir_a) == []
    # Accepted external close: override board_value 'closed' → the close stays closed, no re-ask.
    store_b = _store(tmp_path / "b")
    spec_b = _spec([_leaf("leaf1", kind="non-code")])
    _done(store_b, "leaf1")
    _seed(store_b, op_kind="sub-issue-close", override=True, board_value="closed", ts=2.0)
    br_b, ir_b = _readers(status="Done", state="closed", reason="not_planned")
    assert RECON.detect(spec_b, store_b, board_reader=br_b, issue_reader=ir_b) == []


def test_unreadable_board_emits_note_not_drift(tmp_path: Path) -> None:
    """A "" board read (gh degraded) on an asserted issue is an unreadable note, never a status drift."""
    store = _store(tmp_path)
    spec = _spec([_leaf("leaf1")])
    _seed(store, op_kind="set-field-status", target_state="Ready")
    board_reader, issue_reader = _readers(status="", state="open")
    out = RECON.detect(spec, store, board_reader=board_reader, issue_reader=issue_reader)
    assert [r["kind"] for r in out if r["kind"] in RECON.DRIFT_KINDS] == []
    assert any(r["kind"] == "unreadable" and r.get("field") == "status" for r in out)


# ---------------------------------------------------------------------------
# decide() + apply_resolution() — U4 (resolutions + the precedence seam)
# ---------------------------------------------------------------------------


class _RecordingWriter:
    """A fake board_writer that records calls and never touches gh (proves R9: no direct write)."""

    def __init__(self, *, fail: bool = False) -> None:
        self.calls: list[dict[str, Any]] = []
        self.fail = fail

    def __call__(self, *, op_kind: str, repo: str, number: int, payload: dict[str, Any]) -> None:
        self.calls.append({"op_kind": op_kind, "repo": repo, "number": number, "payload": payload})
        if self.fail:
            raise RuntimeError("board write failed")


def _status_drift() -> dict[str, Any]:
    return {
        "kind": "status-drift",
        "repo": "infiquetra/x",
        "number": 42,
        "subplot_id": "leaf1",
        "op_kind": "set-field-status",
        "saga_value": "In Progress",
        "board_value": "Blocked",
        "author": "",
        "drift_id": RECON._drift_id("status-drift", "infiquetra/x", 42, "In Progress", "Blocked"),
    }


def test_decide_is_hitl_without_policy() -> None:
    """decide() returns None (defer to operator) when no policy is supplied — the R8 default."""
    assert RECON.decide(_status_drift()) is None


def test_decide_delegates_to_policy_seam() -> None:
    """A policy short-circuits the ask — proving the precedence seam is load-bearing (R8)."""
    seen: list[str] = []

    def policy(drift: dict[str, Any]) -> str:
        seen.append(drift["drift_id"])
        return "accept-board"

    assert RECON.decide(_status_drift(), policy=policy) == "accept-board"
    assert len(seen) == 1


def test_accept_board_writes_one_idempotent_override(tmp_path: Path) -> None:
    """accept-board appends exactly one override record; replaying it is a no-op (idempotent name)."""
    store = _store(tmp_path)
    writer = _RecordingWriter()
    r1 = RECON.apply_resolution(_status_drift(), "accept-board", store=store, board_writer=writer)
    assert r1["status"] == "accepted" and r1["recorded"] is True
    r2 = RECON.apply_resolution(_status_drift(), "accept-board", store=store, board_writer=writer)
    assert r2["recorded"] is False  # idempotent — same drift_id, no second file
    overrides = list((Path(store.root) / "board-sync").glob("override-accept-board-*.json"))
    assert len(overrides) == 1
    assert writer.calls == []  # accept-board never drives the board


def test_reassert_via_authorize_write(tmp_path: Path) -> None:
    """re-assert calls the injected board_writer (never a direct gh path) and records the baseline (R9)."""
    store = _store(tmp_path)
    writer = _RecordingWriter()
    out = RECON.apply_resolution(_status_drift(), "re-assert", store=store, board_writer=writer)
    assert out["status"] == "reasserted"
    assert len(writer.calls) == 1
    assert writer.calls[0]["op_kind"] == "set-field-status"
    assert writer.calls[0]["payload"] == {"target_state": "In Progress"}  # re-drives saga's value
    # An override record fixes the re-asserted value as the new baseline.
    overrides = list((Path(store.root) / "board-sync").glob("override-re-assert-*.json"))
    assert len(overrides) == 1


def test_no_new_writer(tmp_path: Path) -> None:
    """outcome_reconcile introduces no direct gh/subprocess writer — writes go only via the seam."""
    src = (SCRIPTS / "outcome_reconcile.py").read_text(encoding="utf-8")
    assert "subprocess" not in src
    assert "import outcome_github" not in src  # reconcile never reaches gh itself
    # The only board mutation path is the injected board_writer (asserted behaviorally above).


def test_reassert_gated_op_refuses(tmp_path: Path) -> None:
    """A GATE verdict refuses the re-assert — no write, no record (certificate is never bypassed)."""
    store = _store(tmp_path)
    writer = _RecordingWriter()
    gated = dict(_status_drift())
    gated["op_kind"] = "parent-issue-close"  # ALWAYS_OPERATOR → GATE
    out = RECON.apply_resolution(gated, "re-assert", store=store, board_writer=writer)
    assert out["status"] == "gated"
    assert writer.calls == []
    assert not list((Path(store.root) / "board-sync").glob("override-*.json"))


def test_reassert_all_attempts_fail_no_record(tmp_path: Path) -> None:
    """When board_writer fails every attempt → failed result, no override record (retryable next tick)."""
    store = _store(tmp_path)
    writer = _RecordingWriter(fail=True)
    out = RECON.apply_resolution(
        _status_drift(), "re-assert", store=store, board_writer=writer, max_attempts=3
    )
    assert out["status"] == "failed"
    assert out["attempts"] == 3
    assert len(writer.calls) == 3
    assert not list((Path(store.root) / "board-sync").glob("override-*.json"))


def test_hold_records_nothing_and_drift_resurfaces(tmp_path: Path) -> None:
    """hold writes no ledger change, so a follow-up detect still reports the same drift (KTD5)."""
    store = _store(tmp_path)
    spec = _spec([_leaf("leaf1")])
    _seed(store, op_kind="set-field-status", target_state="In Progress")
    writer = _RecordingWriter()
    out = RECON.apply_resolution(_status_drift(), "hold", store=store, board_writer=writer)
    assert out["status"] == "held"
    assert not list((Path(store.root) / "board-sync").glob("override-*.json"))
    board_reader, issue_reader = _readers(status="Blocked", state="open")
    again = RECON.detect(spec, store, board_reader=board_reader, issue_reader=issue_reader)
    assert [r["kind"] for r in again if r["kind"] in RECON.DRIFT_KINDS] == ["status-drift"]


def test_accept_external_close_carries_prune_advisory(tmp_path: Path) -> None:
    """Accepting a not_planned external close records it but advises /outcome prune (no completion mint)."""
    store = _store(tmp_path)
    writer = _RecordingWriter()
    close_drift = {
        "kind": "external-close",
        "repo": "infiquetra/x",
        "number": 42,
        "subplot_id": "leaf1",
        "op_kind": "sub-issue-close",
        "saga_value": "open",
        "board_value": "closed",
        "author": "operator",
        "drift_id": "abc123",
    }
    out = RECON.apply_resolution(close_drift, "accept-board", store=store, board_writer=writer)
    assert out["status"] == "accepted"
    assert "prune" in out["advisory"]
    assert writer.calls == []


# ---------------------------------------------------------------------------
# ts-tie robustness — the _asserted_value / _asserted_at_max_ts fix (adversarial P2)
# ---------------------------------------------------------------------------


def test_equal_ts_write_tie_no_false_drift_when_live_matches(tmp_path: Path) -> None:
    """Two status writes at the SAME ts: live matching either one is consistent (no false drift)."""
    store = _store(tmp_path)
    spec = _spec([_leaf("leaf1")])
    # Same ts, different target states — a frozen-clock artifact; production ts are distinct.
    _seed(store, op_kind="set-field-status", target_state="In Progress", ts=5.0)
    _seed(store, op_kind="set-field-status", target_state="Blocked", ts=5.0)
    # Live board reads one of the tied assertions → must NOT report drift (was a false positive).
    for live in ("In Progress", "Blocked"):
        br, ir = _readers(status=live, state="open")
        out = RECON.detect(spec, store, board_reader=br, issue_reader=ir)
        assert [r["kind"] for r in out if r["kind"] in RECON.DRIFT_KINDS] == [], (
            f"false drift for {live!r}"
        )
    # Live matching NEITHER tied value is still a real drift.
    br, ir = _readers(status="Done", state="open")
    out = RECON.detect(spec, store, board_reader=br, issue_reader=ir)
    assert [r["kind"] for r in out if r["kind"] in RECON.DRIFT_KINDS] == ["status-drift"]


def test_override_beats_write_on_equal_ts(tmp_path: Path) -> None:
    """On an equal-ts tie an override wins (it is causally later than the write it supersedes)."""
    store = _store(tmp_path)
    spec = _spec([_leaf("leaf1")])
    _seed(store, op_kind="set-field-status", target_state="In Progress", ts=7.0)
    _seed(store, op_kind="set-field-status", override=True, board_value="Blocked", ts=7.0)
    # The override (accept "Blocked") is the baseline → live "Blocked" is silent...
    br, ir = _readers(status="Blocked", state="open")
    assert RECON.detect(spec, store, board_reader=br, issue_reader=ir) == []
    # ...and the drift record (if live differs) names the override's value as saga_value.
    br2, ir2 = _readers(status="Done", state="open")
    out = RECON.detect(spec, store, board_reader=br2, issue_reader=ir2)
    drift = [r for r in out if r["kind"] == "status-drift"]
    assert len(drift) == 1 and drift[0]["saga_value"] == "Blocked"
