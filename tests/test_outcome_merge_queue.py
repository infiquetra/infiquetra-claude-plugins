"""Tests for the auto-merge queue + GitHub negative terminal states (U6) — #449 envelope-gated.

Pins R12 (serialized squash-merge, base-freshness rebase-then-reverify, expected-base-SHA guard,
base-churn cap, conflict->work+page), R32 (PR closed-unmerged / deleted branch -> rejected terminal,
out-of-band merge not duplicated), R22 (rejected cascades to its downstream subtree), and R34 (a gh
read failure degrades to a safe value — defers a merge, never performs a wrong one).

Since #449 every GitHub WRITE the queue can perform (rebase, squash) is gated on the merge
ceremony: committed ``ceremony_gates.merge: "auto"`` posture AND exactly one active envelope
token, re-checked fresh per write attempt. The pre-#449 tokenless auto-merge default is GONE —
pinned here by ``test_envelope_less_campaign_waits_operator_never_merges`` (with the authorized
control proving the queue can still go green). Read-only classification (conflict, blocked,
unknown) still runs for every campaign, authorized or not.
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


GH = _load("outcome_github")
SPEC = _load("outcome_spec")
STORE = _load("outcome_store")
ET = _load("envelope_token")
M = _load("outcome_merge")

# The committed run-start posture that permits autonomous merge (#449): merge=auto.
_ENV_AUTO: dict[str, Any] = {
    "schema_version": 1,
    "run_mode": "attended",
    "ceremony_gates": {"reviews_required": "gate", "merge": "auto", "deploy_nonprod": "gate"},
}
_ENV_GATE: dict[str, Any] = {
    "schema_version": 1,
    "run_mode": "attended",
    "ceremony_gates": {"reviews_required": "gate", "merge": "gate", "deploy_nonprod": "gate"},
}


def _store(tmp_path: Path):
    return STORE.Store(root=tmp_path / "store").ensure()


def _node(sid: str, **kw: Any):
    return SPEC.Node.from_dict({"subplot_id": sid, "title": sid, "kind": "code", **kw})


def _spec(nodes: list[dict[str, Any]], *, intent: dict[str, Any] | None = None):
    payload: dict[str, Any] = {"outcome_id": "o", "objective": "x", "nodes": nodes}
    if intent is not None:
        payload["intent"] = intent
    return SPEC.OutcomeSpec.from_dict(payload)


def _mint(store: Any, *, outcome_id: str = "o", token_id: str | None = None) -> Any:
    """Mint the single active merge token for the store's outcome (the #449 credential)."""
    return ET.mint_token(
        ET.tokens_dir(store.root),
        outcome_id=outcome_id,
        envelope=_ENV_AUTO,
        intent_revision=0,
        ttl_hours=24,
        issued_by="operator",
        token_id=token_id,
    )


def _authorized(tmp_path: Path) -> tuple[Any, Any]:
    """A real store + committed merge=auto envelope + one active token."""
    store = _store(tmp_path)
    spec = _spec([{"subplot_id": "seed", "title": "s", "kind": "code"}], intent=_ENV_AUTO)
    _mint(store)
    return spec, store


def _authorizer(spec: Any, store: Any, node: Any) -> Any:
    return M.make_merge_authorizer(spec, store, node)


def _seq(val: Any, default: Any) -> Any:
    """A scriptable adapter field: a list is consumed on successive calls, else a constant."""
    if isinstance(val, list):
        box = {"i": 0}

        def f(*_a: Any) -> Any:
            i = min(box["i"], len(val) - 1)
            box["i"] += 1
            return val[i]

        return f
    fixed = val if val is not None else default
    return lambda *_a: fixed


def _ops(
    *,
    pr_state: Any = "open",
    merge_state: Any = "clean",
    squash: Any = "merged",
    branch: bool = True,
    base_oids: Any = None,
    on_update: list[str] | None = None,
) -> Any:
    base = _seq(base_oids, "A") if base_oids is not None else _seq(None, "A")

    def update(r: str) -> bool:
        if on_update is not None:
            on_update.append(r)
        return True

    return M.MergeOps(
        pr_state=_seq(pr_state, "open"),
        base_oid=base,
        merge_state=_seq(merge_state, "clean"),
        update_branch=update,
        squash_merge=_seq(squash, "merged"),
        branch_exists=lambda _b: branch,
    )


# --------------------------------------------------------------------------- outcome_github write side


def _gh_runner(out: str = "", *, rc: int = 0, err: str = ""):
    return lambda args, **kw: SimpleNamespace(returncode=rc, stdout=out, stderr=err)


def test_base_ref_oid_and_merge_state_degrade_safe() -> None:
    assert GH.base_ref_oid("1", runner=_gh_runner(json.dumps({"baseRefOid": "abc"}))) == "abc"
    assert GH.base_ref_oid("1", runner=_gh_runner(rc=1)) == ""  # gh down -> empty (safe)
    assert (
        GH.merge_state("1", runner=_gh_runner(json.dumps({"mergeStateStatus": "BEHIND"})))
        == "behind"
    )
    assert GH.merge_state("1", runner=_gh_runner(rc=1)) == "unknown"  # safe degrade (R34)


def test_squash_merge_returns_error_not_conflict_on_failure() -> None:
    assert GH.squash_merge("1", runner=_gh_runner()) == "merged"
    # a non-zero exit is NOT necessarily a conflict (could be transient) -> "error" (caller defers)
    assert GH.squash_merge("1", runner=_gh_runner(rc=1)) == "error"


def test_branch_exists_only_a_definite_404_is_gone() -> None:
    assert GH.branch_exists("feat", runner=_gh_runner("refs/heads/feat")) is True
    assert GH.branch_exists("feat", runner=_gh_runner(rc=1, err="HTTP 404: Not Found")) is False
    # a transient gh error (NOT a 404) must NOT falsely declare a live branch gone (degrades present)
    assert GH.branch_exists("feat", runner=_gh_runner(rc=1, err="connection timed out")) is True


# --------------------------------------------------------------------------- auto_merge_one (R12 + #449)


def test_clean_squash_merges(tmp_path: Path) -> None:
    spec, store = _authorized(tmp_path)
    node = _node("build", github={"pr": "1"})
    out = M.auto_merge_one(node, _ops(), merge_authorizer=_authorizer(spec, store, node))
    assert out.state == "merged" and out.cycles == 0
    assert out.authorizing_envelope_id.startswith("sha256:")  # attributed (#449 R5)
    assert out.token_id.startswith("emt-")


def test_behind_base_rebases_then_squashes(tmp_path: Path) -> None:
    spec, store = _authorized(tmp_path)
    node = _node("build", github={"pr": "1"})
    updates: list[str] = []
    out = M.auto_merge_one(
        node,
        _ops(merge_state=["behind", "clean"], on_update=updates),
        merge_authorizer=_authorizer(spec, store, node),
    )
    assert out.state == "merged" and out.cycles == 1
    assert updates == ["1"]  # rebased (update-branch) before the squash (R12 base-freshness)


def test_conflict_fails_leaf_back_to_work() -> None:
    # read-only classification needs no merge authority (#449 gates writes, not reads)
    out = M.auto_merge_one(_node("build", github={"pr": "1"}), _ops(merge_state="dirty"))
    assert out.state == "conflict" and "work" in out.reason


def test_github_rejected_squash_reloops_then_merges(tmp_path: Path) -> None:
    # GitHub is the atomic guard: a stale-tree/head-moved squash is rejected ("error") -> reloop;
    # the next attempt (base now stable) succeeds. (--match-head-commit makes this GitHub-side.)
    spec, store = _authorized(tmp_path)
    node = _node("build", github={"pr": "1"})
    out = M.auto_merge_one(
        node, _ops(squash=["error", "merged"]), merge_authorizer=_authorizer(spec, store, node)
    )
    assert (
        out.state == "merged" and out.cycles == 1
    )  # relooped once on a rejected squash, then merged


def test_base_churn_caps_at_three_then_halts(tmp_path: Path) -> None:
    # GitHub rejects the squash on every attempt (head/base keeps moving) -> reloop -> capped, no spin.
    spec, store = _authorized(tmp_path)
    node = _node("build", github={"pr": "1"})
    out = M.auto_merge_one(
        node, _ops(squash="error"), merge_authorizer=_authorizer(spec, store, node)
    )
    assert out.state == "capped" and out.cycles == M.MERGE_CAP  # halt + page, no starvation spin


def test_unreadable_base_defers_never_merges() -> None:
    # base_oid unreadable (gh degraded) -> defer, never squash on an unguardable base (R34).
    out = M.auto_merge_one(_node("build", github={"pr": "1"}), _ops(base_oids=[""]))
    assert out.state == "not-ready"


# --------------------------------------------------------------------------- negative states (R32)


def test_closed_unmerged_pr_is_rejected() -> None:
    out = M.auto_merge_one(_node("build", github={"pr": "1"}), _ops(pr_state="closed"))
    assert out.state == "rejected" and "closed" in out.reason


def test_out_of_band_merge_is_not_duplicated() -> None:
    out = M.auto_merge_one(_node("build", github={"pr": "1"}), _ops(pr_state="merged"))
    assert out.state == "already-merged"  # detected, never a second merge


def test_deleted_branch_is_rejected() -> None:
    out = M.auto_merge_one(_node("build", github={"pr": "1", "branch": "feat"}), _ops(branch=False))
    assert out.state == "rejected" and "branch deleted" in out.reason


def test_gated_risky_destructive_wait_for_operator(tmp_path: Path) -> None:
    spec, store = _authorized(tmp_path)
    for flag in ("gated", "risky", "destructive"):
        node = _node("build", github={"pr": "1"}, **{flag: True})
        # even a VALID envelope token never overrides a leaf's own gating flags (#449)
        out = M.auto_merge_one(node, _ops(), merge_authorizer=_authorizer(spec, store, node))
        assert out.state == "waits-operator"


def test_unknown_merge_state_defers_never_squashes() -> None:
    # merge readiness unknown (gh degraded) -> defer, never squash on an unknown readiness (R34).
    out = M.auto_merge_one(
        _node("build", github={"pr": "1"}), _ops(pr_state="unknown", merge_state="unknown")
    )
    assert out.state == "not-ready"


def test_gh_outage_via_real_adapter_defers_never_fails_leaf(tmp_path: Path) -> None:
    # P1 regression: a TOTAL gh outage through the REAL github_merge_ops must DEFER (not-ready), never
    # record a permanent `failed`/`rejected` terminal (the bug the fake squash='error' had masked).
    def gh_down(args: Any, **kw: Any) -> SimpleNamespace:
        raise OSError("gh unreachable")

    ops = M.github_merge_ops(runner=gh_down)
    spec, store = _authorized(tmp_path)
    node = _node("build", github={"pr": "1", "branch": "feat"})
    out = M.auto_merge_one(node, ops, merge_authorizer=_authorizer(spec, store, node))
    assert out.state == "not-ready"  # deferred, R34 — never a wrong action on an outage
    qspec = _spec(
        [{"subplot_id": "build", "title": "b", "kind": "code", "github": {"pr": "1"}}],
        intent=_ENV_AUTO,
    )
    M.process_merge_queue(qspec, store, ops)
    assert STORE.completed_subplots(store, successful_only=False) == set()  # NO terminal recorded


def test_conflict_then_fixed_leaf_is_retried_not_permanently_skipped(tmp_path: Path) -> None:
    # P2 regression: a conflict records a `failed` terminal, but once /work fixes it the leaf must
    # RE-ENTER the queue — `failed` is retryable, only `rejected`/`stalled` permanently skip.
    store = _store(tmp_path)
    _mint(store)
    spec = _spec(
        [{"subplot_id": "A", "title": "A", "kind": "code", "github": {"pr": "1"}}],
        intent=_ENV_AUTO,
    )
    M.process_merge_queue(spec, store, _ops(merge_state="dirty"))  # conflict -> failed
    assert any(e.state == "failed" for e in STORE.read_completion_events(store, "A"))
    # the conflict is fixed -> a fresh queue run must retry (not skip) and merge it
    result = M.process_merge_queue(spec, store, _ops(merge_state="clean", squash="merged"))
    assert any(o["state"] == "merged" for o in result["outcomes"])  # retried, not stranded


def test_no_pr_ref_not_ready() -> None:
    assert M.auto_merge_one(_node("build"), _ops()).state == "not-ready"


# --------------------------------------------------------------------------- #449 merge ceremony


def test_envelope_less_campaign_waits_operator_never_merges(tmp_path: Path) -> None:
    """THE #449 default flip, pinned: with no committed envelope the queue performs NO
    GitHub write — no squash, no rebase — and the leaf waits for the operator with a
    reason naming the missing envelope. Control: the same store with a committed
    merge=auto envelope + one token DOES merge (the check can go red)."""
    store = _store(tmp_path)
    node_dict = {"subplot_id": "A", "title": "A", "kind": "code", "github": {"pr": "1"}}
    updates: list[str] = []
    squashes: list[str] = []

    def squash(r: str) -> str:
        squashes.append(r)
        return "merged"

    def update(r: str) -> bool:
        updates.append(r)
        return True

    ops = M.MergeOps(
        pr_state=lambda r: "open",
        base_oid=lambda r: "A",
        merge_state=lambda r: "clean",
        update_branch=update,
        squash_merge=squash,
        branch_exists=lambda b: True,
    )
    result = M.process_merge_queue(_spec([node_dict]), store, ops)
    (outcome,) = result["outcomes"]
    assert outcome["state"] == "waits-operator"
    assert "no committed intent envelope" in outcome["reason"]
    assert squashes == [] and updates == []  # zero GitHub writes without authority
    assert not (store.root / "board-sync").exists() or not list(
        (store.root / "board-sync").glob("*.json")
    )  # and zero attribution records

    # Baseline control: envelope + token -> the very same ops DO merge.
    _mint(store)
    result2 = M.process_merge_queue(_spec([node_dict], intent=_ENV_AUTO), store, ops)
    assert result2["outcomes"][0]["state"] == "merged"
    assert squashes == ["1"]


def test_merge_gate_posture_waits_operator(tmp_path: Path) -> None:
    store = _store(tmp_path)
    spec = _spec(
        [{"subplot_id": "A", "title": "A", "kind": "code", "github": {"pr": "1"}}],
        intent=_ENV_GATE,
    )
    result = M.process_merge_queue(spec, store, _ops())
    (outcome,) = result["outcomes"]
    assert outcome["state"] == "waits-operator"
    assert "does not permit autonomous merge" in outcome["reason"]


def test_merge_auto_posture_without_token_waits_operator(tmp_path: Path) -> None:
    """Posture is recorded intent, never a credential — merge=auto with no minted token
    still waits for the operator (#380 threat model / #449 R1)."""
    store = _store(tmp_path)
    spec = _spec(
        [{"subplot_id": "A", "title": "A", "kind": "code", "github": {"pr": "1"}}],
        intent=_ENV_AUTO,
    )
    result = M.process_merge_queue(spec, store, _ops())
    (outcome,) = result["outcomes"]
    assert outcome["state"] == "waits-operator"
    assert "merge ceremony gated" in outcome["reason"]


def test_behind_rebase_is_also_ceremony_gated(tmp_path: Path) -> None:
    """update_branch is a GitHub WRITE — an unauthorized campaign never rebases either."""
    store = _store(tmp_path)
    updates: list[str] = []
    spec = _spec(
        [{"subplot_id": "A", "title": "A", "kind": "code", "github": {"pr": "1"}}],
        intent=_ENV_AUTO,  # posture says auto, but NO token minted
    )
    result = M.process_merge_queue(spec, store, _ops(merge_state="behind", on_update=updates))
    assert result["outcomes"][0]["state"] == "waits-operator"
    assert updates == []


def test_revocation_between_two_leaves_stops_the_very_next_merge(tmp_path: Path) -> None:
    """R4 within ONE queue run: the token is re-checked fresh before EVERY squash, so a
    revocation landing after leaf A's merge stops leaf B in the same tick — no grace
    window, no cached-authorized state."""
    store = _store(tmp_path)
    token = _mint(store)
    spec = _spec(
        [
            {"subplot_id": "A", "title": "A", "kind": "code", "github": {"pr": "1"}},
            {"subplot_id": "B", "title": "B", "kind": "code", "github": {"pr": "2"}},
        ],
        intent=_ENV_AUTO,
    )

    def squash(r: str) -> str:
        if r == "1":  # the operator revokes immediately after A's squash lands
            ET.revoke_token(
                ET.tokens_dir(store.root), token["token_id"], reason="operator stop mid-tick"
            )
        return "merged"

    ops = M.MergeOps(
        pr_state=lambda r: "open",
        base_oid=lambda r: "A",
        merge_state=lambda r: "clean",
        update_branch=lambda r: True,
        squash_merge=squash,
        branch_exists=lambda b: True,
    )
    result = M.process_merge_queue(spec, store, ops)
    by_id = {o["subplot_id"]: o for o in result["outcomes"]}
    assert by_id["A"]["state"] == "merged"
    assert by_id["B"]["state"] == "waits-operator"
    assert "revoked" in by_id["B"]["reason"]


def test_expired_token_waits_operator(tmp_path: Path) -> None:
    store = _store(tmp_path)
    ET.mint_token(
        ET.tokens_dir(store.root),
        outcome_id="o",
        envelope=_ENV_AUTO,
        intent_revision=0,
        ttl_hours=1,
        now="2026-07-14T00:00:00+00:00",
    )
    spec = _spec(
        [{"subplot_id": "A", "title": "A", "kind": "code", "github": {"pr": "1"}}],
        intent=_ENV_AUTO,
    )
    # the queue's clock is injected: two hours later the token is expired -> GATE
    late = lambda: 1784167200.0  # noqa: E731  — 2026-07-15T02:00:00Z epoch, past expiry
    result = M.process_merge_queue(spec, store, _ops(), now=late)
    (outcome,) = result["outcomes"]
    assert outcome["state"] == "waits-operator"
    assert "expired" in outcome["reason"]


def test_renegotiated_posture_read_fresh_from_disk_gates_the_merge(tmp_path: Path) -> None:
    """The production intent_reader seam: a repost that tightened merge->gate ON DISK
    gates the merge even though the tick's in-memory spec still says auto (#433 era
    honesty at the merge seam)."""
    store = _store(tmp_path)
    _mint(store)
    spec = _spec(
        [{"subplot_id": "A", "title": "A", "kind": "code", "github": {"pr": "1"}}],
        intent=_ENV_AUTO,  # the stale in-memory posture
    )
    tightened = {
        **_ENV_AUTO,
        "ceremony_gates": {**_ENV_AUTO["ceremony_gates"], "merge": "gate"},
    }
    result = M.process_merge_queue(spec, store, _ops(), intent_reader=lambda: (tightened, 1))
    (outcome,) = result["outcomes"]
    assert outcome["state"] == "waits-operator"
    assert "does not permit autonomous merge" in outcome["reason"]

    # Control: an intent_reader agreeing with the mint era merges (the seam can go green).
    result2 = M.process_merge_queue(spec, store, _ops(), intent_reader=lambda: (_ENV_AUTO, 0))
    assert result2["outcomes"][0]["state"] == "merged"


def test_ambiguous_multiple_tokens_gate(tmp_path: Path) -> None:
    store = _store(tmp_path)
    _mint(store, token_id="emt-a")
    _mint(store, token_id="emt-b")
    spec = _spec(
        [{"subplot_id": "A", "title": "A", "kind": "code", "github": {"pr": "1"}}],
        intent=_ENV_AUTO,
    )
    result = M.process_merge_queue(spec, store, _ops())
    (outcome,) = result["outcomes"]
    assert outcome["state"] == "waits-operator"
    assert "ambiguous" in outcome["reason"]


def test_authorized_merge_writes_both_attribution_records(tmp_path: Path) -> None:
    """#449 R5/AC4 at the queue level: an envelope-authorized merge writes the
    pre-squash `authorized` record AND the post-squash `merged` record into the
    board-sync ledger, both carrying the authorizing envelope id + token id."""
    store = _store(tmp_path)
    token = _mint(store)
    spec = _spec(
        [{"subplot_id": "A", "title": "A", "kind": "code", "github": {"pr": "1"}}],
        intent=_ENV_AUTO,
    )
    result = M.process_merge_queue(spec, store, _ops())
    (outcome,) = result["outcomes"]
    assert outcome["state"] == "merged"
    assert outcome["authorizing_envelope_id"] == token["envelope_id"]
    assert outcome["attribution"]["status"] == "written"
    records = [
        json.loads(p.read_text(encoding="utf-8"))
        for p in sorted((store.root / "board-sync").glob("*.json"))
    ]
    phases = {r["phase"]: r for r in records}
    assert set(phases) == {"authorized", "merged"}
    for record in phases.values():
        assert record["authorizing_envelope_id"] == token["envelope_id"]
        assert record["token_id"] == token["token_id"]
        assert record["op_kind"] == "merge-under-envelope"
        assert record["subplot_id"] == "A" and record["pr"] == "1"


def test_unattributable_merge_is_not_performed(tmp_path: Path) -> None:
    """Audit-first fail-closed: if the pre-squash `authorized` record cannot be written,
    the squash does NOT happen."""
    store = _store(tmp_path)
    _mint(store)
    # poison the ledger dir: a FILE where the board-sync directory must be
    (store.root / "board-sync").write_text("not a dir", encoding="utf-8")
    squashes: list[str] = []

    def squash(r: str) -> str:
        squashes.append(r)
        return "merged"

    ops = M.MergeOps(
        pr_state=lambda r: "open",
        base_oid=lambda r: "A",
        merge_state=lambda r: "clean",
        update_branch=lambda r: True,
        squash_merge=squash,
        branch_exists=lambda b: True,
    )
    spec = _spec(
        [{"subplot_id": "A", "title": "A", "kind": "code", "github": {"pr": "1"}}],
        intent=_ENV_AUTO,
    )
    result = M.process_merge_queue(spec, store, ops)
    (outcome,) = result["outcomes"]
    assert outcome["state"] == "waits-operator"
    assert squashes == []  # the merge was NOT performed


# --------------------------------------------------------------------------- queue + cascade (R22/R32)


def test_process_queue_rejects_and_cascades_downstream(tmp_path: Path) -> None:
    store = _store(tmp_path)
    _mint(store)
    spec = _spec(
        [
            {"subplot_id": "A", "title": "A", "kind": "code", "github": {"pr": "1"}},
            {
                "subplot_id": "B",
                "title": "B",
                "kind": "code",
                "github": {"pr": "2"},
                "depends_on": ["A"],
            },
            {"subplot_id": "C", "title": "C", "kind": "code", "github": {"pr": "3"}},  # independent
        ],
        intent=_ENV_AUTO,
    )

    # A's PR is closed-unmerged -> rejected; C is clean -> merged. B (downstream of A) cascades.
    pr_states = {"1": "closed", "2": "open", "3": "open"}
    ops = M.MergeOps(
        pr_state=lambda r: pr_states.get(r, "open"),
        base_oid=lambda r: "A",
        merge_state=lambda r: "clean",
        update_branch=lambda r: True,
        squash_merge=lambda r: "merged",
        branch_exists=lambda b: True,
    )
    result = M.process_merge_queue(spec, store, ops)
    assert "A" in result["rejected"]
    assert result["cascade_paused"] == [
        "B"
    ]  # only A's downstream pauses; C is independent + merged
    assert any(o["subplot_id"] == "C" and o["state"] == "merged" for o in result["outcomes"])
    # A's rejected terminal is recorded (negative terminal, R32)
    assert any(e.state == "rejected" for e in STORE.read_completion_events(store, "A"))
    # re-processing is idempotent (no duplicate rejected event)
    M.process_merge_queue(spec, store, ops)
    assert sum(e.state == "rejected" for e in STORE.read_completion_events(store, "A")) == 1


def test_process_queue_records_conflict_as_failed(tmp_path: Path) -> None:
    # conflict classification is read-only — recorded even for an UNAUTHORIZED campaign
    # (#449 gates writes, never the conflict->work re-engagement loop).
    store = _store(tmp_path)
    spec = _spec([{"subplot_id": "A", "title": "A", "kind": "code", "github": {"pr": "1"}}])
    ops = _ops(merge_state="dirty")
    M.process_merge_queue(spec, store, ops)
    # a conflict fails the leaf back to work — a NON-success terminal (does not unlock dependents)
    events = STORE.read_completion_events(store, "A")
    assert any(e.state == "failed" for e in events)
    assert STORE.completed_subplots(store, successful_only=True) == set()  # not a success


def test_a_code_leaf_with_an_incomplete_upstream_is_not_merged(tmp_path: Path) -> None:
    # U11 regression: a coincidentally-clean PR must NOT squash while its declared upstream is incomplete
    # (GitHub does not model the DAG — especially a non-code upstream produces no base-blocking merge).
    store = _store(tmp_path)
    _mint(store)
    spec = _spec(
        [
            {
                "subplot_id": "design",
                "title": "design",
                "kind": "non-code",
                "github": {"issue": "9"},
            },
            {
                "subplot_id": "build",
                "title": "build",
                "kind": "code",
                "github": {"pr": "1"},
                "depends_on": ["design"],
            },
        ],
        intent=_ENV_AUTO,
    )
    # build's PR is perfectly clean, but design (its upstream) is not done -> build must NOT merge.
    result = M.process_merge_queue(spec, store, _ops(merge_state="clean", squash="merged"))
    assert all(o["state"] != "merged" for o in result["outcomes"])  # nothing merged out of order
    # once design completes, build is eligible and merges.
    STORE.write_completion_event(
        store, STORE.CompletionEvent(subplot_id="design", state="done", idempotency_key="k:design")
    )
    result2 = M.process_merge_queue(spec, store, _ops(merge_state="clean", squash="merged"))
    assert any(o["subplot_id"] == "build" and o["state"] == "merged" for o in result2["outcomes"])


def test_cli_describes_policy(capsys: Any) -> None:
    assert M.main(["--cap", "5"]) == 0
    out = json.loads(capsys.readouterr().out)
    assert out["merge_cap"] == 5 and "squash" in out["policy"] and "envelope" in out["policy"]


def test_cross_era_attribution_never_reuses_a_stale_authorized_record(tmp_path: Path) -> None:
    """#449 panel hand-finish (P2, found by two verifiers): an `authorized` record written
    under envelope era A by an attempt that never squashed must not stand as — or
    write-once-suppress — the pre-attribution of the merge actually performed under era B.
    The record key carries the token era, so the era-B ceremony writes its OWN record and
    both phases of the real merge name the same (current) token."""
    store = _store(tmp_path)
    _mint(store, token_id="emt-era-a")
    spec = _spec(
        [{"subplot_id": "A", "title": "A", "kind": "code", "github": {"pr": "1"}}],
        intent=_ENV_AUTO,
    )
    # Tick 1 under era A: base churns every cycle -> capped. The rebase ceremony ran, so
    # the era-A `authorized` record is durably on disk — but nothing squashed.
    result1 = M.process_merge_queue(spec, store, _ops(merge_state="behind"))
    assert result1["outcomes"][0]["state"] == "capped"
    # The era ends: revoke A; the operator re-mints for the renegotiated era (revision 1).
    ET.revoke_token(ET.tokens_dir(store.root), "emt-era-a", reason="renegotiated")
    ET.mint_token(
        ET.tokens_dir(store.root),
        outcome_id="o",
        envelope=_ENV_AUTO,
        intent_revision=1,
        ttl_hours=24,
        issued_by="operator",
        token_id="emt-era-b",
    )
    # Tick 2 under era B merges cleanly (the on-disk posture reader agrees with the mint).
    result2 = M.process_merge_queue(spec, store, _ops(), intent_reader=lambda: (_ENV_AUTO, 1))
    (outcome,) = result2["outcomes"]
    assert outcome["state"] == "merged"
    records = [
        json.loads(p.read_text(encoding="utf-8"))
        for p in sorted((store.root / "board-sync").glob("*.json"))
    ]
    by_phase_token = {(r["phase"], r["token_id"]) for r in records}
    assert ("authorized", "emt-era-b") in by_phase_token  # the real merge's own pre-attribution
    assert ("merged", "emt-era-b") in by_phase_token
    assert ("authorized", "emt-era-a") in by_phase_token  # history kept — never rewritten
    assert ("merged", "emt-era-a") not in by_phase_token  # era A never merged anything


def test_record_write_fault_gates_the_squash(tmp_path: Path) -> None:
    """#449 panel hand-finish (P2): the authorizer's record-status-error conversion — an
    `authorized` attribution record that cannot be WRITTEN (ledger dir resolves but is
    unwritable) converts AUTHORIZED into GATE before any squash. Distinct from
    test_unattributable_merge_is_not_performed, which poisons the ledger DIR resolution
    and trips the earlier unavailable-guard: this pins the later branch, which survived
    mutation testing uncovered before this test."""
    store = _store(tmp_path)
    _mint(store)
    spec = _spec(
        [{"subplot_id": "A", "title": "A", "kind": "code", "github": {"pr": "1"}}],
        intent=_ENV_AUTO,
    )
    squashes: list[str] = []

    def squash(r: str) -> str:
        squashes.append(r)
        return "merged"

    ops = M.MergeOps(
        pr_state=lambda r: "open",
        base_oid=lambda r: "A",
        merge_state=lambda r: "clean",
        update_branch=lambda r: True,
        squash_merge=squash,
        branch_exists=lambda b: True,
    )
    ledger = store.root / "board-sync"
    ledger.mkdir(parents=True, exist_ok=True)
    ledger.chmod(0o555)  # the dir resolves fine; the record write itself faults
    try:
        result = M.process_merge_queue(spec, store, ops)
    finally:
        ledger.chmod(0o755)
    (outcome,) = result["outcomes"]
    assert outcome["state"] == "waits-operator"
    assert "attribution record could not be written" in outcome["reason"]
    assert squashes == []  # fail closed: no unattributable squash
