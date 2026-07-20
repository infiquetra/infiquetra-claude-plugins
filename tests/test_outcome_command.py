"""Tests for the /outcome reconcile engine (U3).

Pins the U3 plan scenarios and the two load-bearing invariants:

* R3 — the coordinator DISPATCHES but never runs a leaf's work in the advance process;
* R17/R29 — status is derived on read (never a stored field) and reconstructs from the canonical
  spec even with the cache deleted; the reconcile loop is level-triggered + idempotent.

The store resolves under a (monkeypatched) git common dir so the whole engine is exercised offline
with no real git repo; repo_root is a tmp dir that holds the branch-local spec.
"""

from __future__ import annotations

import importlib.util
import json
import shutil
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


M = _load("outcome")
SPEC = _load("outcome_spec")
STORE = _load("outcome_store")


@pytest.fixture
def repo(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """A tmp repo_root whose git common dir resolves to tmp_path/.git (monkeypatched, no real git)."""
    common = tmp_path / ".git"
    common.mkdir()

    def fake_run(args: list[str], **_kw: Any) -> SimpleNamespace:
        return SimpleNamespace(returncode=0, stdout=str(common) + "\n", stderr="")

    monkeypatch.setattr(M.outcome_store.subprocess, "run", fake_run)
    return tmp_path


def _recorder():
    calls: list[str] = []

    def dispatcher(req: Any) -> str:
        calls.append(req.subplot_id)
        return f"leaf-{req.subplot_id}"

    return dispatcher, calls


# --------------------------------------------------------------------------- start / status


def test_start_creates_branch_local_spec_and_two_node_dag(repo: Path) -> None:
    spec = M.start(repo, "ship-x", "Ship feature X")
    path = M.spec_path(repo, "ship-x")
    assert path.exists()
    assert [n.subplot_id for n in spec.nodes] == ["design", "build"]
    # the branch-local spec round-trips and is canonical structure
    on_disk = SPEC.OutcomeSpec.from_json(path.read_text())
    assert on_disk.outcome_id == "ship-x"


def test_start_twice_is_rejected(repo: Path) -> None:
    M.start(repo, "ship-x", "Ship feature X")
    with pytest.raises(M.OutcomeError, match="already started"):
        M.start(repo, "ship-x", "Ship feature X")


def test_status_is_derived_not_stored(repo: Path) -> None:
    M.start(repo, "ship-x", "Ship feature X")
    # nothing done yet -> design is the frontier, build is blocked
    st = M.status(repo, "ship-x")
    assert st["states"] == {"design": "ready", "build": "blocked"}
    assert st["frontier"] == ["design"]
    # the canonical spec has NO stored status field — status is computed from spec + store
    assert (
        "status"
        not in SPEC.OutcomeSpec.from_dict(
            {"outcome_id": "o", "objective": "x", "nodes": [{"subplot_id": "a", "title": "a"}]}
        ).to_dict()
    )
    # writing a completion event (no advance, no status write) flips the derived state
    store = STORE.Store.for_outcome("ship-x", repo)
    STORE.write_completion_event(
        store, STORE.CompletionEvent(subplot_id="design", state="done", idempotency_key="kd")
    )
    st2 = M.status(repo, "ship-x")
    assert st2["states"]["design"] == "done" and st2["states"]["build"] == "ready"


# --------------------------------------------------------------------------- advance (R3 + idempotency)


def test_advance_dispatches_frontier_but_never_runs_leaf_work(repo: Path) -> None:
    M.start(repo, "ship-x", "Ship feature X")
    dispatcher, calls = _recorder()
    result = M.advance(repo, "ship-x", dispatcher=dispatcher)
    # the coordinator DISPATCHED design (the frontier)...
    assert result.dispatched == ["design"]
    assert calls == ["design"]  # dispatcher called exactly once, for the frontier leaf
    # ...but did NOT run/complete it: design is 'dispatched', not 'done', and there is NO
    # completion event (the coordinator never fabricates a leaf's completion — R3).
    st = M.status(repo, "ship-x")
    assert st["states"]["design"] == "dispatched"
    assert st["states"]["build"] == "blocked"
    store = STORE.Store.for_outcome("ship-x", repo)
    assert STORE.completed_subplots(store) == set()  # no leaf body ran -> nothing completed


def test_advance_is_idempotent_no_duplicate_dispatch(repo: Path) -> None:
    M.start(repo, "ship-x", "Ship feature X")
    dispatcher, calls = _recorder()
    first = M.advance(repo, "ship-x", dispatcher=dispatcher)
    second = M.advance(repo, "ship-x", dispatcher=dispatcher)
    assert first.dispatched == ["design"]
    assert second.dispatched == []  # already dispatched -> no re-dispatch
    assert calls == ["design"]  # dispatcher NOT called again
    store = STORE.Store.for_outcome("ship-x", repo)
    # one settled dispatch (commit) for design, never two
    commits = [
        r
        for r in STORE.read_ledger(store)
        if r.get("kind") == "dispatch" and r.get("phase") == "commit"
    ]
    assert len(commits) == 1


def test_concurrent_reentrant_advance_does_not_double_dispatch(repo: Path) -> None:
    # Model a second concurrent tick by re-entering advance() from inside the dispatcher. With a
    # per-invocation unique holder, the nested advance is a DIFFERENT holder -> it no-ops on the
    # held coordinator lease, so design is dispatched exactly ONCE (not twice).
    M.start(repo, "ship-x", "Ship feature X")
    calls: list[str] = []

    def reentrant(req: Any) -> str:
        calls.append(req.subplot_id)
        if len(calls) == 1:  # re-enter once, mid-dispatch, as a "concurrent" tick
            M.advance(repo, "ship-x", dispatcher=reentrant)
        return f"leaf-{req.subplot_id}"

    M.advance(repo, "ship-x", dispatcher=reentrant)
    assert calls == ["design"]  # the nested advance no-op'd on the held lease -> single dispatch
    store = STORE.Store.for_outcome("ship-x", repo)
    commits = [
        r
        for r in STORE.read_ledger(store)
        if r.get("kind") == "dispatch" and r.get("phase") == "commit"
    ]
    assert len(commits) == 1


def test_negative_terminal_leaf_shows_failed_not_dispatched(repo: Path) -> None:
    # A dispatched leaf that reaches a NEGATIVE terminal must render as its actual terminal state,
    # not stay masked as "dispatched" (a dead leaf must not look in-flight).
    M.start(repo, "ship-x", "Ship feature X")
    M.advance(repo, "ship-x")  # dispatch design
    store = STORE.Store.for_outcome("ship-x", repo)
    STORE.write_completion_event(
        store, STORE.CompletionEvent(subplot_id="design", state="failed", idempotency_key="kf")
    )
    st = M.status(repo, "ship-x")
    assert st["states"]["design"] == "failed"  # surfaced, not "dispatched"


def test_advance_unlocks_next_layer_after_completion(repo: Path) -> None:
    M.start(repo, "ship-x", "Ship feature X")
    M.advance(repo, "ship-x")  # dispatch design
    store = STORE.Store.for_outcome("ship-x", repo)
    STORE.write_completion_event(
        store, STORE.CompletionEvent(subplot_id="design", state="done", idempotency_key="kd")
    )
    result = M.advance(repo, "ship-x")  # now build is ready
    assert result.dispatched == ["build"]


def test_advance_loop_runs_until_quiescent(repo: Path) -> None:
    # With a dispatcher that immediately records completion, --loop should dispatch the whole chain.
    M.start(repo, "ship-x", "Ship feature X")
    store = STORE.Store.for_outcome("ship-x", repo).ensure()

    def auto_complete(req: Any) -> str:
        leaf = f"leaf-{req.subplot_id}"
        STORE.write_completion_event(
            store,
            STORE.CompletionEvent(subplot_id=req.subplot_id, state="done", idempotency_key=leaf),
        )
        return leaf

    result = M.advance(repo, "ship-x", loop=True, dispatcher=auto_complete)
    assert sorted(result.dispatched) == ["build", "design"]
    assert result.status["complete"] is True


def test_second_concurrent_advance_noops_on_held_lease(repo: Path) -> None:
    M.start(repo, "ship-x", "Ship feature X")
    store = STORE.Store.for_outcome("ship-x", repo).ensure()
    # an external holder grabs the coordinator lease with a long TTL
    assert STORE.acquire_coordinator(store, "other", ttl_seconds=10_000) is True
    result = M.advance(repo, "ship-x")
    assert result.skipped_busy is True and result.dispatched == []


# --------------------------------------------------------------------------- attend (R16 handoff)


def test_attend_prints_native_resume_handoff(repo: Path) -> None:
    M.start(repo, "ship-x", "Ship feature X")
    M.advance(repo, "ship-x", dispatcher=lambda req: f"leaf-saga-{req.subplot_id}")
    assert M.attend(repo, "ship-x", "design") == "/resume leaf-saga-design"


def test_attend_undispatched_leaf_errors(repo: Path) -> None:
    M.start(repo, "ship-x", "Ship feature X")
    with pytest.raises(M.OutcomeError, match="not dispatched"):
        M.attend(repo, "ship-x", "design")


# --------------------------------------------------------------------------- resume / cache loss


def test_resume_reconstructs_with_cache_deleted(repo: Path) -> None:
    M.start(repo, "ship-x", "Ship feature X")
    M.advance(repo, "ship-x")  # dispatch design (record lives in the cache)
    store = STORE.Store.for_outcome("ship-x", repo)
    shutil.rmtree(store.root)  # wipe the cache (e.g. `git worktree remove`)
    # the canonical spec on the branch survives -> resume reconstructs structure with no crash;
    # the cache-resident dispatch record is gone, so design is back on the frontier (recomputed).
    st = M.resume(repo, "ship-x")
    assert st["outcome_id"] == "ship-x"
    assert st["states"] == {"design": "ready", "build": "blocked"}
    assert st["frontier"] == ["design"]


# --------------------------------------------------------------------------- export / import (R14)


def test_legacy_bundle_import_is_refused_with_zero_writes(
    repo: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """R10 (#604): outcome-bundle/1 is retired as an authority-transfer path.

    A copied bundle must not write a spec, replay completion events, or replay dispatch
    records into another repository — the refusal names the discover/attach migration.
    """
    M.start(repo, "ship-x", "Ship feature X")
    bundle = {
        "schema": "outcome-bundle/1",
        "spec": {"outcome_id": "ship-x"},
        "completion_events": [{"subplot_id": "design", "state": "done"}],
        "dispatch_ledger": [{"phase": "commit", "key": "dispatch:build"}],
    }
    dest = tmp_path / "dest"
    dest.mkdir()
    common2 = dest / ".git"
    common2.mkdir()
    monkeypatch.setattr(
        M.outcome_store.subprocess,
        "run",
        lambda args, **kw: SimpleNamespace(returncode=0, stdout=str(common2) + "\n", stderr=""),
    )
    with pytest.raises(M.OutcomeError) as exc:
        M.import_bundle(dest, bundle)
    message = str(exc.value)
    assert "retired" in message and "discover" in message and "attach" in message
    assert not (dest / "docs").exists()  # no spec write
    assert not (common2 / "saga-outcomes").exists()  # no store/ledger write


# --------------------------------------------------------------------------- graph + CLI


def test_graph_mermaid_renders_nodes_edges_states(repo: Path) -> None:
    M.start(repo, "ship-x", "Ship feature X")
    g = M.graph_mermaid(repo, "ship-x")
    assert g.startswith("flowchart TD")
    assert "design --> build" in g
    assert "design: ready" in g


def test_cli_start_advance_status(repo: Path, capsys: pytest.CaptureFixture[str]) -> None:
    assert M.main(["--repo-root", str(repo), "start", "ship-x", "Ship feature X"]) == 0
    capsys.readouterr()
    # R20: nothing dispatches before the operator approves the current frontier.
    assert M.main(["--repo-root", str(repo), "advance", "ship-x"]) == 0
    gated = json.loads(capsys.readouterr().out)
    assert gated["dispatched"] == [] and gated["gated"] == ["design"]
    # approve, then advance -> the frontier dispatches.
    assert M.main(["--repo-root", str(repo), "approve", "ship-x"]) == 0
    capsys.readouterr()
    assert M.main(["--repo-root", str(repo), "advance", "ship-x"]) == 0
    out = json.loads(capsys.readouterr().out)
    assert out["dispatched"] == ["design"]
    assert M.main(["--repo-root", str(repo), "status", "ship-x"]) == 0
    st = json.loads(capsys.readouterr().out)
    assert st["states"]["design"] == "dispatched"


def test_cli_missing_outcome_errors(repo: Path, capsys: pytest.CaptureFixture[str]) -> None:
    rc = M.main(["--repo-root", str(repo), "status", "nope"])
    assert rc == 1
    err = json.loads(capsys.readouterr().err)
    assert err["ok"] is False


def test_cli_help_pins_retired_bundle_semantics(capsys: pytest.CaptureFixture[str]) -> None:
    """PA-1 (#624): top-level help no longer advertises the retired outcome-bundle/1 flow."""
    with pytest.raises(SystemExit) as exc:
        M.main(["--help"])
    assert exc.value.code == 0
    normalized = " ".join(capsys.readouterr().out.split())
    assert "deprecated read-only alias of `discover`" in normalized
    assert "always refuses with discover/attach migration guidance" in normalized
    assert "portable bundle" not in normalized
    assert "reconstruct an outcome" not in normalized


def test_cli_import_refuses_with_receipt_and_no_success_print(
    repo: Path, tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """The import arm has no success path — the refusal receipt is the only output.

    A forward contract guard, not a change detector: the refusal has held since #604 R10
    retired ``import_bundle``, so this passes before and after PA-1 (#624), which only deleted
    the already-unreachable success print. It pins the CLI shape the deletion assumed.
    """
    bundle_path = tmp_path / "bundle.json"
    bundle_path.write_text(
        json.dumps({"schema": "outcome-bundle/1", "spec": {"outcome_id": "ship-x"}}),
        encoding="utf-8",
    )
    rc = M.main(["--repo-root", str(repo), "import", str(bundle_path)])
    assert rc == 1
    captured = capsys.readouterr()
    assert captured.out == ""
    err = json.loads(captured.err)
    assert err["ok"] is False
    for token in ("retired", "discover", "attach"):
        assert token in err["error"]


@pytest.mark.parametrize("body", [None, "{not valid json"])
def test_cli_import_refuses_before_reading_the_bundle(
    repo: Path, tmp_path: Path, capsys: pytest.CaptureFixture[str], body: str | None
) -> None:
    """PA-1 (#624): a missing or malformed bundle still yields the migration receipt.

    The arm refuses without touching the path, so an unreadable file cannot pre-empt the
    guidance with a traceback (missing) or a JSON parse error (malformed).
    """
    bundle_path = tmp_path / "bundle.json"
    if body is not None:
        bundle_path.write_text(body, encoding="utf-8")

    rc = M.main(["--repo-root", str(repo), "import", str(bundle_path)])

    assert rc == 1
    captured = capsys.readouterr()
    assert captured.out == ""
    err = json.loads(captured.err)
    assert err["ok"] is False
    for token in ("retired", "discover", "attach"):
        assert token in err["error"]


# --------------------------------------------------------------------------- reconcile (#295 U5)


class _RecWriter:
    """A fake board_writer that records calls and never touches gh."""

    def __init__(self) -> None:
        self.calls: list[dict[str, Any]] = []

    def __call__(self, *, op_kind: str, repo: str, number: int, payload: dict[str, Any]) -> None:
        self.calls.append({"op_kind": op_kind, "repo": repo, "number": number, "payload": payload})


def _seed_ledger(store: Any, *, op_kind: str, repo: str, number: int, target_state: str) -> None:
    d = Path(store.root) / "board-sync"
    d.mkdir(parents=True, exist_ok=True)
    rec = {
        "op_kind": op_kind,
        "repo": repo,
        "number": number,
        "target_state": target_state,
        "ts": 1.0,
    }
    (d / f"seed_{op_kind}_{number}.json").write_text(json.dumps(rec), encoding="utf-8")


def _issue_leaves() -> list[dict[str, Any]]:
    return [
        {
            "subplot_id": "a",
            "title": "A",
            "kind": "non-code",
            "github": {"issue": "infiquetra/x#42"},
        },
        {
            "subplot_id": "b",
            "title": "B",
            "kind": "non-code",
            "github": {"issue": "infiquetra/x#99"},
        },
    ]


def test_advance_autonomous_drift_holds_only_drifted_issue(repo: Path) -> None:
    """advance --autonomous detects drift BEFORE writing: the drifted issue is held, others proceed."""
    M.start(repo, "o", "obj", nodes=_issue_leaves())
    store = STORE.Store.for_outcome("o", repo)
    _seed_ledger(
        store,
        op_kind="set-field-status",
        repo="infiquetra/x",
        number=42,
        target_state="In Progress",
    )
    _seed_ledger(
        store, op_kind="set-field-status", repo="infiquetra/x", number=99, target_state="Ready"
    )

    def board_reader(ref: str) -> str:
        return "Blocked" if "#42" in ref else "Ready"  # #42 drifted, #99 matches

    def issue_reader(ref: str) -> dict[str, str]:
        return {"state": "open", "state_reason": "unknown", "closed_by": ""}

    writer = _RecWriter()
    dispatcher, _ = _recorder()
    result = M.advance(
        repo,
        "o",
        dispatcher=dispatcher,
        autonomous=True,
        board_reader=board_reader,
        issue_reader=issue_reader,
        board_writer=writer,
    )
    # drift surfaced for #42, on the AdvanceResult
    assert any(d["kind"] == "status-drift" and d["number"] == 42 for d in result.drift)
    # #42's ops were drift-held (never driven); #99's were written
    held = [r for r in result.board_synced if r.get("status") == "drift-hold"]
    assert held and all(r["number"] == 42 for r in held)
    driven = {c["number"] for c in writer.calls}
    assert 42 not in driven and 99 in driven


def test_advance_non_autonomous_never_detects(repo: Path) -> None:
    """The default (non-autonomous) advance performs no drift detection — no board/issue reads."""
    M.start(repo, "o", "obj", nodes=_issue_leaves())
    store = STORE.Store.for_outcome("o", repo)
    _seed_ledger(
        store,
        op_kind="set-field-status",
        repo="infiquetra/x",
        number=42,
        target_state="In Progress",
    )
    reads: list[str] = []

    def board_reader(ref: str) -> str:
        reads.append(ref)
        return "Blocked"

    dispatcher, _ = _recorder()
    result = M.advance(repo, "o", dispatcher=dispatcher, board_reader=board_reader)
    assert reads == []  # detection never ran on the non-autonomous path
    assert result.drift == []


def test_reconcile_cli_empty_when_no_ledger(repo: Path, capsys: pytest.CaptureFixture[str]) -> None:
    """`outcome reconcile <id>` on an outcome that never board-synced prints an empty drift list."""
    M.start(repo, "o", "obj", nodes=_issue_leaves())
    rc = M.main(["--repo-root", str(repo), "reconcile", "o"])
    assert rc == 0
    out = json.loads(capsys.readouterr().out.strip().splitlines()[-1])
    assert out == {"drift": []}


def test_reconcile_cli_resolve_requires_action(repo: Path) -> None:
    """`--resolve` without `--action` is rejected (no silent guess at the operator's decision)."""
    M.start(repo, "o", "obj", nodes=_issue_leaves())
    rc = M.main(["--repo-root", str(repo), "reconcile", "o", "--resolve", "abc123"])
    assert rc != 0  # OutcomeError surfaced as a non-zero exit


# --------------------------------------------------------------------------- link-pr (#495 U2)

_PR = "https://github.com/infiquetra/infiquetra-claude-plugins/pull/500"


def _code_nodes() -> list[dict[str, Any]]:
    return [
        {"subplot_id": "build", "title": "B", "kind": "code", "github": {"issue": "o/r#7"}},
        {"subplot_id": "docs", "title": "D", "kind": "non-code", "github": {"issue": "o/r#8"}},
    ]


def test_link_pr_writes_ref_and_leaves_others_untouched(repo: Path) -> None:
    M.start(repo, "o", "obj", nodes=_code_nodes())
    res = M.link_pr(repo, "o", "build", _PR)
    assert res["pr"] == _PR and res["changed"] is True
    spec = M.load_spec(repo, "o")
    assert spec.node_by_id("build").github["pr"] == _PR
    assert "pr" not in spec.node_by_id("docs").github  # only the target node mutated


def test_link_pr_is_idempotent(repo: Path) -> None:
    M.start(repo, "o", "obj", nodes=_code_nodes())
    M.link_pr(repo, "o", "build", _PR)
    again = M.link_pr(repo, "o", "build", _PR)
    assert again["changed"] is False  # re-linking the same URL is a no-op flag
    assert M.load_spec(repo, "o").node_by_id("build").github["pr"] == _PR


def test_link_pr_unknown_subplot_errors(repo: Path) -> None:
    M.start(repo, "o", "obj", nodes=_code_nodes())
    with pytest.raises(M.OutcomeError, match="no subplot"):
        M.link_pr(repo, "o", "nope", _PR)


def test_link_pr_rejects_non_code_node(repo: Path) -> None:
    M.start(repo, "o", "obj", nodes=_code_nodes())
    with pytest.raises(M.OutcomeError, match="not 'code'"):
        M.link_pr(repo, "o", "docs", _PR)


def test_link_pr_rejects_non_pr_url(repo: Path) -> None:
    M.start(repo, "o", "obj", nodes=_code_nodes())
    with pytest.raises(M.OutcomeError, match="pull-request URL"):
        M.link_pr(repo, "o", "build", "o/r#500")  # a bare ref is NOT accepted — URL required


def test_cli_link_pr_happy_path(repo: Path, capsys: pytest.CaptureFixture[str]) -> None:
    M.start(repo, "o", "obj", nodes=_code_nodes())
    assert M.main(["--repo-root", str(repo), "link-pr", "o", "build", _PR]) == 0
    out = json.loads(capsys.readouterr().out)
    assert out["subplot_id"] == "build" and out["pr"] == _PR and out["changed"] is True


def test_cli_link_pr_bad_url_nonzero(repo: Path, capsys: pytest.CaptureFixture[str]) -> None:
    M.start(repo, "o", "obj", nodes=_code_nodes())
    rc = M.main(["--repo-root", str(repo), "link-pr", "o", "build", "not-a-url"])
    assert rc == 1
    err = json.loads(capsys.readouterr().err)
    assert err["ok"] is False


# --------------------------------------------------------------------------- attend handoff (#491 U1)


def _node(**github: Any) -> Any:
    return SPEC.Node(subplot_id="x", title="X", github=github)


def test_leaf_handoff_id_resolves_issue_backed() -> None:
    assert M._leaf_handoff_id(_node(sub_issue=491), "leaf-o-x") == "issue-491"
    assert M._leaf_handoff_id(_node(sub_issue="491"), "leaf-o-x") == "issue-491"
    assert M._leaf_handoff_id(_node(issue="infiquetra/plugins#362"), "leaf-o-x") == "issue-362"


def test_leaf_handoff_id_falls_back_when_no_issue() -> None:
    assert M._leaf_handoff_id(_node(pr="https://github.com/o/r/pull/1"), "leaf-o-x") == "leaf-o-x"
    assert M._leaf_handoff_id(_node(), "leaf-o-x") == "leaf-o-x"
    assert M._leaf_handoff_id(None, "leaf-o-x") == "leaf-o-x"  # node miss -> raw id


def test_leaf_handoff_id_hardening_non_positive_and_non_dict() -> None:
    # #491 adversarial-gate hardening: a non-positive/garbage issue number is a DEAD pointer -> fall back
    # to the raw id (never emit issue-0 / issue--5); a corrupt non-dict github must not raise (R3).
    assert M._leaf_handoff_id(_node(sub_issue=0), "leaf-o-x") == "leaf-o-x"
    assert M._leaf_handoff_id(_node(sub_issue=-5), "leaf-o-x") == "leaf-o-x"
    assert (
        M._leaf_handoff_id(_node(sub_issue=True), "leaf-o-x") == "leaf-o-x"
    )  # bool is not an issue no.
    assert M._leaf_handoff_id(_node(issue="o/r#0"), "leaf-o-x") == "leaf-o-x"
    corrupt = SPEC.Node(subplot_id="x", title="X")
    corrupt.github = ["not", "a", "dict"]  # type: ignore[assignment]
    assert M._leaf_handoff_id(corrupt, "leaf-o-x") == "leaf-o-x"


def _dispatch_one(repo: Path, sid: str, **github: Any) -> None:
    M.start(
        repo,
        "o",
        "obj",
        nodes=[{"subplot_id": sid, "title": "B", "kind": "code", "github": github}],
    )
    dispatcher, _ = _recorder()
    M.advance(repo, "o", dispatcher=dispatcher)


def test_attend_emits_issue_backed_saga_id_from_sub_issue(repo: Path) -> None:
    _dispatch_one(repo, "build", sub_issue=491)
    assert M.attend(repo, "o", "build") == "/resume issue-491"


def test_attend_emits_issue_saga_from_owner_repo_num(repo: Path) -> None:
    _dispatch_one(repo, "build", issue="infiquetra/infiquetra-claude-plugins#362")
    assert M.attend(repo, "o", "build") == "/resume issue-362"


def test_attend_falls_back_to_raw_leaf_when_no_issue(repo: Path) -> None:
    _dispatch_one(repo, "build")  # a task/ad-hoc leaf with no issue on its node
    assert M.attend(repo, "o", "build") == "/resume leaf-build"


def test_attend_not_dispatched_still_raises(repo: Path) -> None:
    M.start(repo, "o", "obj", nodes=[{"subplot_id": "build", "title": "B", "kind": "code"}])
    with pytest.raises(M.OutcomeError, match="not dispatched"):
        M.attend(repo, "o", "build")


# ---------------------------------------------------------------------------
# set-intent (#380 hand-finish): the landing place for a post-start interview capture.
# ---------------------------------------------------------------------------


def _envelope_file(tmp_path: Path, run_mode: str = "attended") -> Path:
    import intent_envelope as ie

    path = tmp_path / "envelope.json"
    path.write_text(ie.apply_answers({"run_mode": run_mode}).to_json(), encoding="utf-8")
    return path


def test_set_intent_attaches_envelope_to_started_outcome(repo: Path, tmp_path: Path) -> None:
    started = M.start(repo, "ship-x", "Ship feature X")
    spec = M.set_intent(repo, "ship-x", _envelope_file(tmp_path))
    assert spec.intent is not None and spec.intent["run_mode"] == "attended"
    assert spec.spec_revision == started.spec_revision + 1  # structural edit -> re-approve
    on_disk = SPEC.OutcomeSpec.from_json(M.spec_path(repo, "ship-x").read_text())
    assert on_disk.intent == spec.intent


def test_set_intent_refuses_to_overwrite_committed_envelope(repo: Path, tmp_path: Path) -> None:
    M.start(repo, "ship-x", "Ship feature X")
    env = _envelope_file(tmp_path)
    M.set_intent(repo, "ship-x", env)
    with pytest.raises(M.OutcomeError, match="already carries"):
        M.set_intent(repo, "ship-x", env)


def test_set_intent_invalid_file_is_loud_and_never_lands(repo: Path, tmp_path: Path) -> None:
    M.start(repo, "ship-y", "Ship feature Y")
    bad = tmp_path / "bad.json"
    bad.write_text('{"run_mode": "sideways"}', encoding="utf-8")
    with pytest.raises(M.OutcomeError):
        M.set_intent(repo, "ship-y", bad)
    on_disk = SPEC.OutcomeSpec.from_json(M.spec_path(repo, "ship-y").read_text())
    assert on_disk.intent is None


def test_set_intent_attach_records_decision_trail_entry(repo: Path, tmp_path: Path) -> None:
    """#433 AC5 hand-finish: an accepted attach is a posture change — one verb, one revision
    counter, ONE trail entry (never a bare revision bump with no audit record)."""
    M.start(repo, "ship-x", "Ship feature X")
    spec = M.set_intent(repo, "ship-x", _envelope_file(tmp_path))
    entry = spec.decision_trail[-1]
    assert entry["kind"] == "set-intent"
    assert entry["revision"] == spec.spec_revision == 2
    assert entry["live"] is False  # pre-dispatch: run-start posture, any gate values allowed
    assert entry["intent_revision"] == spec.intent_revision == 2


def test_set_intent_on_live_campaign_rejects_merge_auto_via_cli(repo: Path, tmp_path: Path) -> None:
    """#433 AC5: once ANY dispatch exists, a first attach carrying merge/deploy_nonprod=auto is
    rejected outright by the SAME monotonic rule repost enforces — no second-verb side door.
    CLI parity: non-zero exit, on-disk spec byte-identical."""
    import intent_envelope as ie

    M.start(repo, "live-x", "Ship X", nodes=[{"subplot_id": "a", "title": "A", "kind": "code"}])
    dispatcher, _calls = _recorder()
    assert M.advance(repo, "live-x", dispatcher=dispatcher).dispatched == ["a"]

    auto_env = tmp_path / "auto-envelope.json"
    auto_env.write_text(
        json.dumps(
            {"schema_version": 1, "run_mode": "attended", "ceremony_gates": {"merge": "auto"}}
        ),
        encoding="utf-8",
    )
    file_before = M.spec_path(repo, "live-x").read_text(encoding="utf-8")
    rc = M.main(["--repo-root", str(repo), "set-intent", "live-x", "--intent-file", str(auto_env)])
    assert rc == 1
    assert M.spec_path(repo, "live-x").read_text(encoding="utf-8") == file_before

    # Control (the #380 interview-fallback flow preserved): the SAME envelope attaches cleanly
    # BEFORE any dispatch — run-start posture may carry any gate values.
    M.start(repo, "fresh-x", "Ship X", nodes=[{"subplot_id": "a", "title": "A", "kind": "code"}])
    spec = M.set_intent(repo, "fresh-x", auto_env)
    assert ie.IntentEnvelope.from_dict(spec.intent).ceremony_gates.merge == "auto"


# --------------------------------------------------------------------------- native v2 vocabulary (#628)


def _native_v2(sid: str, phase: str, *, outcome_id: str = "ship-x", **extra: Any) -> dict[str, Any]:
    """A codex-native ``outcome.dispatch.v2`` ledger record, shaped like the codex writer's."""
    intent_id = f"dispatch-intent:{outcome_id}:{sid}"
    return {
        "phase": phase,
        "kind": "outcome.dispatch.v2",
        "key": intent_id,
        "dispatch_intent_id": intent_id,
        "subplot_id": sid,
        "backend": "claude-direct",
        "run_identity": "outcome-run-0f3a9c",
        "at": 1000.0,
        **extra,
    }


def _native_launched_ack(sid: str, leaf: str = "issue-42") -> dict[str, Any]:
    return _native_v2(
        sid,
        "ack",
        ack_kind="launched",
        dispatch_ack_ref="launch-receipt:abc",
        receipt_authority="owner-user-state-v1",
        leaf_saga_id=leaf,
    )


def test_native_launched_ack_settles_leaf_no_redispatch(repo: Path) -> None:
    """#628 codex-first ordering: a receipt-authoritative native ack settles the leaf exactly like
    a legacy commit — a later advance on the same clone must NOT re-dispatch it (R5/R6)."""
    M.start(repo, "ship-x", "Ship feature X")
    store = STORE.Store.for_outcome("ship-x", repo).ensure()
    STORE.append_ledger(store, _native_v2("design", "intent"))
    STORE.append_ledger(store, _native_launched_ack("design"))
    dispatcher, calls = _recorder()
    result = M.advance(repo, "ship-x", dispatcher=dispatcher)
    assert result.dispatched == []
    assert calls == []  # the natively-settled leaf never reaches the backend again
    # exactly one settled chain: the native ack — no legacy dispatch records were ever written
    legacy = [r for r in STORE.read_ledger(store) if r.get("kind") == "dispatch"]
    assert legacy == []
    assert M.status(repo, "ship-x")["states"]["design"] == "dispatched"


def test_live_native_intent_reads_in_flight_not_redriven(repo: Path) -> None:
    """#628: a native intent WITHOUT an acknowledgement is IN FLIGHT — advance refuses loudly
    (visible receipt) instead of re-dispatching under legacy crash-recovery semantics."""
    M.start(repo, "ship-x", "Ship feature X")
    store = STORE.Store.for_outcome("ship-x", repo).ensure()
    STORE.append_ledger(store, _native_v2("design", "intent"))
    dispatcher, calls = _recorder()
    result = M.advance(repo, "ship-x", dispatcher=dispatcher)
    assert result.dispatched == []
    assert calls == []
    reasons = [h.get("reason", "") for h in result.halted]
    assert any("without an acknowledgement" in reason for reason in reasons)
    # the refusal wrote nothing: the live intent stays the only dispatch-chain record
    assert [r for r in STORE.read_ledger(store) if r.get("kind") == "dispatch"] == []
    # the cockpit surfaces in-flight, never "ready" (which would invite a double dispatch)
    assert M.status(repo, "ship-x")["states"]["design"] == "intent-created"


def test_settled_lookup_sees_native_settlement(repo: Path) -> None:
    """#628: the handoff already-settled guard consults the shared reduction, so a natively
    concluded dispatch refuses re-admission even though #351 settlement never saw it."""
    M.start(repo, "ship-x", "Ship feature X")
    store = STORE.Store.for_outcome("ship-x", repo).ensure()
    STORE.append_ledger(store, _native_v2("design", "intent"))
    lookup = M._settled_lookup(repo, "ship-x")
    assert lookup("dispatch-intent:ship-x:design", "design", 1) is False  # live, not settled
    STORE.append_ledger(store, _native_launched_ack("design"))
    assert lookup("dispatch-intent:ship-x:design", "design", 1) is True
    assert lookup("dispatch-intent:ship-x:build", "build", 1) is False  # untouched leaf stays open
