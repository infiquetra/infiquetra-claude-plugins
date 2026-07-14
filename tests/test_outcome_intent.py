"""Acceptance + unit tests for mid-run posture renegotiation — repost/set_intent (#433).

Covers the four contract facets against the PRODUCTION engine (outcome_intent.repost driving
outcome.advance / outcome_store / outcome_decompose — never a scaffold reimplementation):

* atomic repost — a rejected repost leaves the spec byte-identical (R1/R2);
* R20 interplay — a loosening repost re-closes the frontier approval, a pure-tightening one
  carries it forward (R3);
* overlap safety — dispatch-time posture: in-flight leaves finish under the posture captured at
  their dispatch, pending leaves pick up the amendment (R4/R5), and an amendment that would
  strand an in-flight irreversible-op authorization HALTs the campaign (R6);
* monotonic merge/deploy gating (R7) and the scoped-repose HALT resolution path (R8/R9).

Every green assertion is paired with a baseline control proving the check could have failed.
"""

from __future__ import annotations

import importlib.util
import json
import re
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


AE = _load("adjustment_envelope")
OI = _load("outcome_intent")
M = _load("outcome")
SPEC = _load("outcome_spec")
STORE = _load("outcome_store")
DEC = _load("outcome_decompose")
DISPATCHER = _load("outcome_dispatcher")
ORCH = _load("outcome_orchestrator")
LEDGER = _load("evidence_ledger")
COSTS = _load("outcome_costs")


@pytest.fixture
def repo(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """A tmp repo_root whose git common dir resolves to tmp_path/.git (no real git)."""
    common = tmp_path / ".git"
    common.mkdir()

    def fake_run(args: list[str], **_kw: Any) -> SimpleNamespace:
        return SimpleNamespace(returncode=0, stdout=str(common) + "\n", stderr="")

    monkeypatch.setattr(M.outcome_store.subprocess, "run", fake_run)
    return tmp_path


def _env_path(repo: Path) -> Path:
    path: Path = AE.default_envelope_path(repo)
    return path


def _start(repo: Path, outcome_id: str, nodes: list[dict[str, Any]]) -> Any:
    return M.start(repo, outcome_id, f"objective for {outcome_id}", nodes=nodes)


def _store(repo: Path, outcome_id: str) -> Any:
    return M._store(repo, outcome_id)


def _auto(req: Any) -> str:
    return f"leaf-{req.subplot_id}"


# ---------------------------------------------------------------------------
# AC1 — a rejected repost leaves the spec byte-identical (R1/R2)
# ---------------------------------------------------------------------------


def test_rejected_repost_untouched(repo: Path) -> None:
    spec = _start(
        repo,
        "camp",
        [
            {"subplot_id": "a", "title": "A", "kind": "code"},
            {"subplot_id": "b", "title": "B", "kind": "code", "degrade_policy": "halt"},
        ],
    )
    store = _store(repo, "camp")
    env = _env_path(repo)
    before = spec.to_json()
    file_before = M.spec_path(repo, "camp").read_text(encoding="utf-8")

    rejections: list[tuple[dict[str, Any], str, str]] = [
        # (changes, scope, expected error fragment)
        ({"frobnicate": "x"}, "", "unknown field"),  # unknown field: error, never a pass
        ({"degrade_policy": "warp"}, "b", "closed vocabulary"),  # off-vocabulary value
        ({"degrade_policy": "halt"}, "b", "already"),  # a no-op never fabricates a trail entry
        ({"merge": True}, "", "must be a non-empty string"),  # wrong value TYPE fails closed
        ({"merge": "auto"}, "", "MORE gating"),  # monotonic violation (R7)
        ({"degrade_policy": "none"}, "", "unknown field"),  # node field needs --scope
        ({"run_mode": "unattended"}, "b", "unknown field"),  # campaign field rejects a scope
        ({"degrade_policy": "none"}, "ghost", "no declared subplot"),  # unknown scope
        ({}, "", "non-empty"),  # empty change set
        ({"sandbox": "warp-core"}, "b", "neither a known profile"),  # unparseable sandbox
    ]
    for changes, scope, fragment in rejections:
        with pytest.raises(OI.RepostError, match=re.escape(fragment)):
            OI.repost(spec, store, changes=changes, scope=scope, reason="r", envelope_path=env)
        # No partial mutation: spec_revision, decision_trail, and every posture field are
        # byte-identical after EVERY rejection (R2 / the R26 invariant).
        assert spec.to_json() == before

    # An empty reason is itself a rejection — the trail entry must record a why (R1).
    with pytest.raises(OI.RepostError, match="reason"):
        OI.repost(spec, store, changes={"run_mode": "unattended"}, reason=" ", envelope_path=env)
    assert spec.to_json() == before

    # CLI parity: a rejected repost exits non-zero and the on-disk spec is byte-identical.
    rc = M.main(
        [
            "--repo-root",
            str(repo),
            "repost",
            "camp",
            "--set",
            "merge=auto",
            "--reason",
            "loosen it",
        ]
    )
    assert rc == 1
    assert M.spec_path(repo, "camp").read_text(encoding="utf-8") == file_before

    # Control — the SAME engine accepts a valid change (proving the rejections above
    # discriminate rather than rejecting everything), and the trail records it.
    result = OI.repost(
        spec, store, changes={"run_mode": "unattended"}, reason="going away", envelope_path=env
    )
    assert spec.to_json() != before
    assert spec.spec_revision == result.spec_revision == 2
    assert spec.intent_revision == 2
    entry = spec.decision_trail[-1]
    assert entry["kind"] == "repost" and entry["intent_revision"] == 2
    assert entry["deltas"] == [
        {
            "field": "run_mode",
            "scope": "",
            "old": "attended",
            "new": "unattended",
            "direction": "loosen",
        }
    ]


def test_duplicate_set_field_fails_closed() -> None:
    with pytest.raises(OI.RepostError, match="given twice"):
        OI.parse_set_args(["merge=gate", "merge=auto"])
    with pytest.raises(OI.RepostError, match="not FIELD=VALUE"):
        OI.parse_set_args(["merge"])
    # control: well-formed args parse
    assert OI.parse_set_args(["merge=gate", "run_mode=attended"]) == {
        "merge": "gate",
        "run_mode": "attended",
    }


# ---------------------------------------------------------------------------
# AC2 — a loosening repost re-closes the frontier approval (R3)
# ---------------------------------------------------------------------------


def test_loosening_repost_recloses_approval(repo: Path) -> None:
    spec = _start(
        repo,
        "camp",
        [{"subplot_id": "build", "title": "Build", "kind": "code", "degrade_policy": "halt"}],
    )
    store = _store(repo, "camp")
    env = _env_path(repo)
    DEC.approve_frontier(store, spec)
    assert DEC.frontier_approved(store, 1) is True

    # Loosening: degrade-policy drop away from halt. The revision-keyed gate re-closes.
    result = OI.repost(
        spec,
        store,
        changes={"degrade_policy": "none"},
        scope="build",
        reason="allow degrade",
        envelope_path=env,
    )
    M.save_spec(repo, spec)
    assert result.loosened is True
    assert result.approval_carried_forward is False
    assert result.reapproval_required is True
    assert DEC.frontier_approved(store, spec.spec_revision) is False

    # The affected leaf does NOT dispatch under the un-approved new revision...
    gate_factory = lambda s, st: DEC.make_dispatch_gate(st, s)  # noqa: E731
    held = M.advance(repo, "camp", dispatcher=_auto, gate_factory=gate_factory)
    assert held.dispatched == [] and held.gated == ["build"]

    # ...and dispatches only after the operator re-approves (the R20 gate reopened).
    DEC.approve_frontier(store, M.load_spec(repo, "camp"))
    released = M.advance(repo, "camp", dispatcher=_auto, gate_factory=gate_factory)
    assert released.dispatched == ["build"]


def test_tightening_repost_carries_approval_forward(repo: Path) -> None:
    # Baseline control for AC2: a PURE-tightening repost requires no re-approval — the prior
    # approval is carried forward with explicit provenance, and dispatch proceeds.
    spec = _start(
        repo,
        "camp",
        [{"subplot_id": "build", "title": "Build", "kind": "code", "degrade_policy": "none"}],
    )
    store = _store(repo, "camp")
    DEC.approve_frontier(store, spec)

    result = OI.repost(
        spec,
        store,
        changes={"degrade_policy": "halt"},
        scope="build",
        reason="guarantee it",
        envelope_path=_env_path(repo),
    )
    M.save_spec(repo, spec)
    assert result.loosened is False
    assert result.approval_carried_forward is True
    assert result.reapproval_required is False
    assert DEC.frontier_approved(store, spec.spec_revision) is True
    # provenance says carried-forward, naming the source revision
    record = json.loads(
        (store.root / "approvals" / f"r{spec.spec_revision}.json").read_text(encoding="utf-8")
    )
    assert record["answerer"] == "carried-forward:tightening-repost:r1"

    gate_factory = lambda s, st: DEC.make_dispatch_gate(st, s)  # noqa: E731
    released = M.advance(repo, "camp", dispatcher=_auto, gate_factory=gate_factory)
    assert released.dispatched == ["build"]

    # Control within the control: WITHOUT the carried approval the same advance would have
    # gated — prove it by consuming the approval with a further LOOSENING repost.
    spec2 = M.load_spec(repo, "camp")
    OI.repost(
        spec2,
        store,
        changes={"reviews_required": "auto"},
        reason="loosen reviews",
        envelope_path=_env_path(repo),
    )
    M.save_spec(repo, spec2)
    # build already dispatched; use a fresh leafless assertion: the new revision is unapproved.
    assert DEC.frontier_approved(store, spec2.spec_revision) is False


# ---------------------------------------------------------------------------
# AC3 — dispatch-time posture overlap (R4/R5)
# ---------------------------------------------------------------------------


def test_dispatch_time_posture_overlap(repo: Path) -> None:
    spec = _start(
        repo,
        "camp",
        [
            {"subplot_id": "a", "title": "A", "kind": "code"},
            {"subplot_id": "b", "title": "B", "kind": "code", "depends_on": ["a"]},
        ],
    )
    store = _store(repo, "camp")
    requests: list[Any] = []

    def capturing(req: Any) -> str:
        requests.append(req)
        return f"leaf-{req.subplot_id}"

    # Tick 1: leaf a dispatches under the run-start posture (intent_revision baseline 1).
    first = M.advance(repo, "camp", dispatcher=capturing)
    assert first.dispatched == ["a"]
    assert requests[0].intent_revision == 1 and requests[0].sandbox is None

    # The repost lands while a is in flight: tighten b's sandbox (pending leaf).
    spec = M.load_spec(repo, "camp")
    result = OI.repost(
        spec,
        store,
        changes={"sandbox": "read-only-verify"},
        scope="b",
        reason="contain b",
        envelope_path=_env_path(repo),
    )
    M.save_spec(repo, spec)
    new_rev = result.intent_revision
    assert new_rev == 2

    # Leaf a completes AFTER the repost — under its dispatch-time posture, never re-evaluated
    # against the new one (no re-dispatch, its commit record still reads the old era).
    STORE.write_completion_event(
        store, STORE.CompletionEvent(subplot_id="a", state="done", idempotency_key="k:a")
    )
    second = M.advance(repo, "camp", dispatcher=capturing)
    assert second.dispatched == ["b"]  # the pending leaf picks up the new posture...
    assert requests[1].intent_revision == new_rev  # ...tagged with the amendment's revision
    assert requests[1].sandbox is not None
    assert requests[1].sandbox.mutation_policy == "read-only"  # the NEW posture, at dispatch

    records = {
        r["subplot_id"]: r
        for r in STORE.read_ledger(store)
        if r.get("kind") == "dispatch" and r.get("phase") == "commit"
    }
    # a's record is the dispatch-time capture: old era, old (wide default) posture — and it was
    # written BEFORE the repost, proving capture happens at dispatch, not read-back later.
    assert records["a"]["intent_revision"] == 1
    assert records["a"]["posture"]["mutation_policy"] == "read-write"
    # b's record carries the amended era + posture (the control proving the field can differ).
    assert records["b"]["intent_revision"] == new_rev
    assert records["b"]["posture"]["mutation_policy"] == "read-only"
    # a was dispatched exactly once (one intent + one commit) — never re-dispatched or
    # re-evaluated under the new posture.
    a_records = [r for r in STORE.read_ledger(store) if r.get("key") == "dispatch:a"]
    assert [r["phase"] for r in a_records] == ["intent", "commit"]
    assert M.status(repo, "camp")["states"]["a"] == "done"


# ---------------------------------------------------------------------------
# AC4 — an amendment that strands an authorized irreversible op HALTs (R6)
# ---------------------------------------------------------------------------


def test_amendment_strands_irreversible_op_halts(repo: Path) -> None:
    spec = _start(
        repo,
        "camp",
        [
            {"subplot_id": "deploy", "title": "Deploy", "kind": "code", "destructive": True},
            {"subplot_id": "docs", "title": "Docs", "kind": "non-code", "depends_on": ["deploy"]},
        ],
    )
    store = _store(repo, "camp")
    env = _env_path(repo)

    # The destructive leaf goes in flight (dispatched, no terminal completion).
    first = M.advance(repo, "camp", dispatcher=_auto)
    assert first.dispatched == ["deploy"]

    spec = M.load_spec(repo, "camp")
    before = spec.to_json()

    # The amendment would revoke the in-flight destructive leaf's mutation authorization.
    with pytest.raises(OI.RepostStrandedError, match="strand"):
        OI.repost(
            spec,
            store,
            changes={"sandbox": "read-only-verify"},
            scope="deploy",
            reason="contain it",
            envelope_path=env,
        )
    # Neither silent direction: the amendment was NOT applied (spec untouched)...
    assert spec.to_json() == before
    # ...and the campaign HALTs — a coordinator andon lands in the polled envelope.
    envelope = AE.load(env)
    assert envelope is not None
    andons = [d for d in envelope.directives if d.directive == "andon_halt"]
    assert len(andons) == 1
    assert andons[0].writer == "coordinator" and andons[0].extra["scope"] == "deploy"
    # A leaf that becomes READY while the strand halt stands does NOT dispatch: the in-flight
    # leaf drains (its completion is harvested), but the coordinator hands out nothing new.
    STORE.write_completion_event(
        store, STORE.CompletionEvent(subplot_id="deploy", state="done", idempotency_key="k:dep")
    )
    halted = M.advance(repo, "camp", dispatcher=_auto)
    assert halted.dispatched == [] and halted.adjustment["action"] == "halt"
    assert M.status(repo, "camp")["states"]["docs"] == "ready"  # ready, yet held back
    # ...with a durable ledger record naming the stranded leaf.
    strand_records = [
        r
        for r in STORE.read_ledger(store)
        if r.get("kind") == "repost" and r.get("phase") == "halt"
    ]
    assert len(strand_records) == 1 and strand_records[0]["subplot_id"] == "deploy"
    assert strand_records[0]["dispatch_posture"]["mutation_policy"] == "read-write"

    # Baseline control: clearing the halt (the operator's explicit resolution) releases the
    # ready leaf — proving it was the strand halt, not something else, holding dispatch.
    AE.clear(env)
    released = M.advance(repo, "camp", dispatcher=_auto)
    assert released.dispatched == ["docs"]

    # Control 1: the SAME amendment against a NON-destructive in-flight leaf applies cleanly —
    # no irreversible authorization to strand; R5's dispatch-time posture covers the flight.
    spec = M.load_spec(repo, "camp")
    ok = OI.repost(
        spec,
        store,
        changes={"sandbox": "read-only-verify"},
        scope="docs",
        reason="contain docs",
        envelope_path=env,
    )
    assert any(d.field == "sandbox.mutation_policy" for d in ok.deltas)
    assert AE.load(env) is None  # no halt raised

    # Control 2: the SAME amendment against a destructive leaf that is NOT in flight applies —
    # a pending leaf simply picks up the new posture at its next dispatch (R5).
    spec2 = _start(
        repo,
        "camp2",
        [{"subplot_id": "deploy", "title": "Deploy", "kind": "code", "destructive": True}],
    )
    store2 = _store(repo, "camp2")
    ok2 = OI.repost(
        spec2,
        store2,
        changes={"sandbox": "read-only-verify"},
        scope="deploy",
        reason="contain pre-dispatch",
        envelope_path=env,
    )
    assert ok2.spec_revision == 2 and AE.load(env) is None


def test_strand_check_ignores_terminal_flights(repo: Path) -> None:
    # A destructive leaf whose flight already reached a terminal state has no live
    # authorization left to strand — the repost applies.
    spec = _start(
        repo,
        "camp",
        [{"subplot_id": "deploy", "title": "Deploy", "kind": "code", "destructive": True}],
    )
    store = _store(repo, "camp")
    M.advance(repo, "camp", dispatcher=_auto)
    STORE.write_completion_event(
        store, STORE.CompletionEvent(subplot_id="deploy", state="done", idempotency_key="k:d")
    )
    spec = M.load_spec(repo, "camp")
    ok = OI.repost(
        spec,
        store,
        changes={"sandbox": "read-only-verify"},
        scope="deploy",
        reason="tighten post-flight",
        envelope_path=_env_path(repo),
    )
    assert ok.spec_revision == 2


# ---------------------------------------------------------------------------
# AC5 — merge/deploy gates are monotonic toward MORE gating (R7)
# ---------------------------------------------------------------------------


def test_merge_deploy_gate_monotonic(repo: Path) -> None:
    # A campaign whose committed envelope has merge/deploy at AUTO may tighten to GATE...
    intent = {
        "schema_version": 1,
        "run_mode": "attended",
        "ceremony_gates": {"reviews_required": "gate", "merge": "auto", "deploy_nonprod": "auto"},
    }
    spec = M.start(
        repo,
        "camp",
        "obj",
        nodes=[{"subplot_id": "a", "title": "A", "kind": "code"}],
        intent=intent,
    )
    store = _store(repo, "camp")
    env = _env_path(repo)
    result = OI.repost(
        spec,
        store,
        changes={"merge": "gate", "deploy_nonprod": "gate"},
        reason="tighten ceremonies",
        envelope_path=env,
    )
    assert {(d.field, d.direction) for d in result.deltas} == {
        ("merge", "tighten"),
        ("deploy_nonprod", "tighten"),
    }

    # ...but can NEVER move back toward autonomous: rejected outright, posture unchanged.
    before = spec.to_json()
    for field in ("merge", "deploy_nonprod"):
        with pytest.raises(OI.RepostError, match="MORE gating"):
            OI.repost(spec, store, changes={field: "auto"}, reason="loosen", envelope_path=env)
        assert spec.to_json() == before  # the campaign posture is unchanged

    # A mixed change set containing ONE monotonic violation is rejected whole (atomic).
    with pytest.raises(OI.RepostError, match="MORE gating"):
        OI.repost(
            spec,
            store,
            changes={"run_mode": "unattended", "merge": "auto"},
            reason="mixed",
            envelope_path=env,
        )
    assert spec.to_json() == before

    # No-envelope campaign: effective gates default to GATE, so merge=auto is a loosening from
    # gated and is rejected — the monotonic rule cannot be dodged by never committing an
    # envelope.
    bare = _start(repo, "bare", [{"subplot_id": "a", "title": "A", "kind": "code"}])
    bare_before = bare.to_json()
    with pytest.raises(OI.RepostError, match="MORE gating"):
        OI.repost(
            bare,
            _store(repo, "bare"),
            changes={"merge": "auto"},
            reason="loosen",
            envelope_path=env,
        )
    assert bare.to_json() == bare_before


# ---------------------------------------------------------------------------
# AC6 — a posture-caused HALT offers scoped repose; no default/timeout proceed (R8/R9)
# ---------------------------------------------------------------------------


def test_scoped_repose_no_timeout_default(repo: Path) -> None:
    spec = _start(
        repo,
        "camp",
        [
            {
                "subplot_id": "guard",
                "title": "Guaranteed leaf",
                "kind": "code",
                "backend": "cc-workflows-ultracode",
                "degrade_policy": "halt",  # guarantee-bearing: HALT-not-degrade
            }
        ],
    )
    store = _store(repo, "camp")
    env = _env_path(repo)
    gate_factory = lambda s, st: DEC.make_dispatch_gate(st, s)  # noqa: E731
    DEC.approve_frontier(store, spec)

    kwargs: dict[str, Any] = {
        "dispatcher": M.outcome_dispatcher.make_dispatcher(available=SPEC.NODE_BACKENDS),
        "gate_factory": gate_factory,
        "available": DISPATCHER.ALWAYS_AVAILABLE,  # ultracode NOT available on this host
        "attending": False,  # operator away — only the guarantee forces the halt
    }
    first = M.advance(repo, "camp", **kwargs)
    assert first.dispatched == [] and len(first.halted) == 1
    receipt = first.halted[0]
    # The posture-caused HALT surfaces the scoped-repose option targeting ONLY this leaf.
    assert receipt["scoped_repose"]["scope"] == "guard"
    assert receipt["scoped_repose"]["resolution"] == "explicit-operator-selection"
    assert "repost" in receipt["scoped_repose"]["hint"] and "--scope guard" in str(
        receipt["scoped_repose"]["hint"]
    )

    # R9: no default and no timeout — arbitrarily much later, with no operator selection, the
    # leaf is still halted and still not dispatched.
    much_later = M.advance(repo, "camp", now=lambda: 4_102_444_800.0, **kwargs)
    assert much_later.dispatched == [] and len(much_later.halted) == 1

    # The explicit operator selection: a SCOPED repost loosening this one leaf's degrade
    # policy. Loosening re-closes the frontier (R3) — still no dispatch until re-approval...
    spec = M.load_spec(repo, "camp")
    result = OI.repost(
        spec,
        store,
        changes={"degrade_policy": "operator_away_one_rung"},
        scope="guard",
        reason="allow one-rung degrade for this leaf only",
        envelope_path=env,
    )
    M.save_spec(repo, spec)
    assert result.loosened is True and result.reapproval_required is True
    still_gated = M.advance(repo, "camp", **kwargs)
    assert still_gated.dispatched == [] and still_gated.gated == ["guard"]

    # ...and after the second explicit selection (re-approve), the leaf degrades one rung and
    # dispatches — the HALT was a renegotiation point, not a dead stop.
    DEC.approve_frontier(store, M.load_spec(repo, "camp"))
    resolved = M.advance(repo, "camp", **kwargs)
    assert resolved.dispatched == ["guard"]
    assert len(resolved.degraded) == 1
    assert resolved.degraded[0]["to_backend"] == "team-execution"


def test_availability_halt_carries_no_scoped_repose(repo: Path) -> None:
    # Control for R8: a halt that posture CANNOT resolve (backend off the degrade ladder,
    # operator away, no guarantee, no side effect) carries NO scoped-repose option — proving
    # the option discriminates posture-caused halts rather than decorating every halt.
    _start(
        repo,
        "camp",
        [{"subplot_id": "forked", "title": "F", "kind": "code", "backend": "fork"}],
    )
    result = M.advance(
        repo,
        "camp",
        dispatcher=M.outcome_dispatcher.make_dispatcher(available=SPEC.NODE_BACKENDS),
        available=DISPATCHER.ALWAYS_AVAILABLE,
        attending=False,
    )
    assert len(result.halted) == 1
    assert "scoped_repose" not in result.halted[0]
    assert "no lower rung" in result.halted[0]["reason"]


# ---------------------------------------------------------------------------
# intent_revision plumbing (R4) — spec round-trip + set-intent tagging
# ---------------------------------------------------------------------------


def test_intent_revision_round_trip_and_fail_closed() -> None:
    # Absent stays absent: a never-renegotiated spec round-trips byte-identical (no key).
    spec = SPEC.OutcomeSpec.from_dict(
        {"outcome_id": "x", "objective": "o", "nodes": [{"subplot_id": "a", "title": "A"}]}
    )
    assert "intent_revision" not in spec.to_dict()
    assert SPEC.OutcomeSpec.from_json(spec.to_json()).to_json() == spec.to_json()

    # Present round-trips; garbage fails closed (bool / zero / non-int).
    spec.spec_revision = 3
    spec.intent_revision = 3
    again = SPEC.OutcomeSpec.from_json(spec.to_json())
    assert again.intent_revision == 3
    for bad in (True, 0, "two"):
        with pytest.raises(SPEC.OutcomeSpecError, match="intent_revision"):
            SPEC.OutcomeSpec.from_dict(
                {
                    "outcome_id": "x",
                    "objective": "o",
                    "nodes": [{"subplot_id": "a", "title": "A"}],
                    "intent_revision": bad,
                }
            )
    # A posture tag pointing past the current revision is a corrupted spec — validate fails.
    spec.intent_revision = 99
    with pytest.raises(SPEC.OutcomeSpecError, match="exceeds"):
        spec.validate()


def test_set_intent_first_attach_tags_intent_revision(repo: Path, tmp_path: Path) -> None:
    _start(repo, "camp", [{"subplot_id": "a", "title": "A", "kind": "code"}])
    envelope_file = tmp_path / "envelope.json"
    envelope_file.write_text(
        json.dumps({"schema_version": 1, "run_mode": "attended", "ceremony_gates": {}})
    )
    spec = M.set_intent(repo, "camp", envelope_file)
    assert spec.intent_revision == spec.spec_revision == 2


# ---------------------------------------------------------------------------
# AC5 parity for the sibling verb — a LIVE first-attach set-intent passes the SAME
# monotonic validation as repost (no second-verb side door), and any accepted attach
# writes a decision-trail entry (one verb, one revision counter, one trail).
# ---------------------------------------------------------------------------


def test_live_set_intent_attach_passes_monotonic_validation(repo: Path, tmp_path: Path) -> None:
    # The panel repro: live campaign (leaf dispatched), NO committed envelope. Both verbs must
    # reach the SAME verdict on the same semantic transition at the same moment.
    _start(repo, "camp", [{"subplot_id": "a", "title": "A", "kind": "code"}])
    store = _store(repo, "camp")
    assert M.advance(repo, "camp", dispatcher=_auto).dispatched == ["a"]

    auto_env = tmp_path / "auto.json"
    auto_env.write_text(
        json.dumps(
            {"schema_version": 1, "run_mode": "attended", "ceremony_gates": {"merge": "auto"}}
        ),
        encoding="utf-8",
    )
    file_before = M.spec_path(repo, "camp").read_text(encoding="utf-8")

    # repost merge=auto: rejected (R7)...
    with pytest.raises(OI.RepostError, match="MORE gating"):
        OI.repost(
            M.load_spec(repo, "camp"),
            store,
            changes={"merge": "auto"},
            reason="loosen",
            envelope_path=_env_path(repo),
        )
    # ...AND set-intent with an envelope carrying merge=auto: rejected by the SAME rule.
    with pytest.raises(OI.RepostError, match="LIVE campaign"):
        M.set_intent(repo, "camp", auto_env)
    assert M.spec_path(repo, "camp").read_text(encoding="utf-8") == file_before

    # deploy_nonprod=auto is rejected identically.
    deploy_env = tmp_path / "deploy.json"
    deploy_env.write_text(
        json.dumps(
            {
                "schema_version": 1,
                "run_mode": "attended",
                "ceremony_gates": {"deploy_nonprod": "auto"},
            }
        ),
        encoding="utf-8",
    )
    with pytest.raises(OI.RepostError, match="LIVE campaign"):
        M.set_intent(repo, "camp", deploy_env)
    assert M.spec_path(repo, "camp").read_text(encoding="utf-8") == file_before

    # An all-gated envelope attaches cleanly on the SAME live campaign (the rejections above
    # discriminate), and the attach records a structured decision-trail entry with its deltas.
    gated_env = tmp_path / "gated.json"
    gated_env.write_text(
        json.dumps({"schema_version": 1, "run_mode": "unattended", "ceremony_gates": {}}),
        encoding="utf-8",
    )
    spec = M.set_intent(repo, "camp", gated_env)
    assert spec.intent_revision == spec.spec_revision == 2
    entry = spec.decision_trail[-1]
    assert entry["kind"] == "set-intent" and entry["live"] is True
    assert {(d["field"], d["direction"]) for d in entry["deltas"]} == {("run_mode", "loosen")}

    # Pre-dispatch control (the #380 interview-fallback contract preserved): the REJECTED
    # merge=auto envelope attaches cleanly on a campaign with no dispatch record.
    _start(repo, "fresh", [{"subplot_id": "a", "title": "A", "kind": "code"}])
    fresh = M.set_intent(repo, "fresh", auto_env)
    assert fresh.intent["ceremony_gates"]["merge"] == "auto"
    assert fresh.decision_trail[-1]["kind"] == "set-intent"
    assert fresh.decision_trail[-1]["live"] is False


def test_mid_dispatch_intent_record_counts_as_live(repo: Path, tmp_path: Path) -> None:
    # A bare intent-phase dispatch record (the mid-dispatch window) already makes the
    # campaign LIVE for the attach rule — fail closed, same as the strand check.
    _start(repo, "camp", [{"subplot_id": "a", "title": "A", "kind": "code"}])
    store = _store(repo, "camp")
    STORE.append_ledger(
        store, {"phase": "intent", "kind": "dispatch", "key": "dispatch:a", "subplot_id": "a"}
    )
    auto_env = tmp_path / "auto.json"
    auto_env.write_text(
        json.dumps(
            {"schema_version": 1, "run_mode": "attended", "ceremony_gates": {"merge": "auto"}}
        ),
        encoding="utf-8",
    )
    with pytest.raises(OI.RepostError, match="LIVE campaign"):
        M.set_intent(repo, "camp", auto_env)


# ---------------------------------------------------------------------------
# Overlap safety at the persistence seam — a committed repost survives a concurrent
# production advance tick (the cost processor's spec save can never clobber it).
# ---------------------------------------------------------------------------


def test_save_spec_refuses_to_clobber_newer_revision(repo: Path) -> None:
    # Baseline control for the mid-tick test below: this exact save was the silent-revert
    # seam — a spec loaded at revision 1, saved after a repost committed revision 2, used to
    # overwrite the repost wholesale. The guard makes it loud.
    _start(repo, "camp", [{"subplot_id": "a", "title": "A", "kind": "code"}])
    store = _store(repo, "camp")
    stale = M.load_spec(repo, "camp")  # loaded at revision 1 (the tick's in-memory spec)

    fresh = M.load_spec(repo, "camp")
    OI.repost(
        fresh,
        store,
        changes={"run_mode": "unattended"},
        reason="operator repost",
        envelope_path=_env_path(repo),
    )
    M.save_spec(repo, fresh)  # revision 2 (intent + trail) on disk

    stale.cost_rollup = {"tokens": 1.0}
    with pytest.raises(M.StaleSpecError, match="superseded"):
        M.save_spec(repo, stale)
    # The newer revision survives byte-for-byte semantics: posture, revision, trail.
    on_disk = M.load_spec(repo, "camp")
    assert on_disk.spec_revision == 2
    assert on_disk.intent is not None and on_disk.intent["run_mode"] == "unattended"
    assert on_disk.decision_trail[-1]["kind"] == "repost"

    # Control: the same-object save at the CURRENT revision still works (the guard
    # discriminates staleness, not all saves).
    fresh.cost_rollup = {"tokens": 2.0}
    M.save_spec(repo, fresh)
    assert M.load_spec(repo, "camp").cost_rollup == {"tokens": 2.0}


def test_midtick_repost_survives_cost_processor_save(repo: Path) -> None:
    # The panel sequence, on the production cost processor: a leaf completes with a cost
    # fact; a repost commits to disk while the tick is mid-flight (spec_revision bumped,
    # intent updated, trail written); the tick's cost processor then persists. The repost
    # must SURVIVE and the tick's record must say what happened — never a silent revert.
    _start(repo, "camp", [{"subplot_id": "a", "title": "A", "kind": "code"}])
    store = _store(repo, "camp")
    assert M.advance(repo, "camp", dispatcher=_auto).dispatched == ["a"]
    COSTS.record_cost(store, "a", tokens=1234.0)
    STORE.write_completion_event(
        store, STORE.CompletionEvent(subplot_id="a", state="done", idempotency_key="k:a")
    )

    def midtick_repost(_spec: Any, _store: Any) -> list[str]:
        # Runs INSIDE the advance tick (the harvester seam), after the tick loaded its spec:
        # an operator repost commits run_mode=unattended to disk mid-flight.
        s2 = M.load_spec(repo, "camp")
        OI.repost(
            s2,
            store,
            changes={"run_mode": "unattended"},
            reason="mid-tick repost",
            envelope_path=_env_path(repo),
        )
        M.save_spec(repo, s2)
        return []

    result = M.advance(
        repo,
        "camp",
        dispatcher=_auto,
        harvester=midtick_repost,
        cost_processor=M.production_cost_processor(repo),
    )
    # The repost SURVIVED on disk: revision bump, envelope, decision-trail entry all intact.
    on_disk = M.load_spec(repo, "camp")
    assert on_disk.spec_revision == 2
    assert on_disk.intent is not None and on_disk.intent["run_mode"] == "unattended"
    assert on_disk.decision_trail[-1]["kind"] == "repost"
    # ...AND the cost rollup was re-applied on top of the newer revision, loudly.
    assert on_disk.cost_rollup.get("tokens") == 1234.0
    cost_run = result.costs[0]
    assert cost_run["reapplied_over_stale_revision"] == 1
    assert cost_run["spec_revision"] == 2
    assert cost_run["changed"] is True


def test_stale_spec_mid_pass_stops_dispatch_under_revoked_posture(repo: Path) -> None:
    # A repost that lands MID-pass (while the tick is dispatching) stops the pass: the next
    # leaf is never handed out under the revoked posture; the loop reloads and re-ticks, and
    # the leaf dispatches under the NEW posture era.
    _start(
        repo,
        "camp",
        [
            {"subplot_id": "a", "title": "A", "kind": "code"},
            {"subplot_id": "b", "title": "B", "kind": "code"},
        ],
    )
    store = _store(repo, "camp")
    requests: list[Any] = []

    def reposting_dispatcher(req: Any) -> str:
        requests.append(req)
        if len(requests) == 1:
            # While leaf a's dispatch is in the backend's hands, a repost tightens b.
            s2 = M.load_spec(repo, "camp")
            OI.repost(
                s2,
                store,
                changes={"sandbox": "read-only-verify"},
                scope="b",
                reason="tighten b mid-pass",
                envelope_path=_env_path(repo),
            )
            M.save_spec(repo, s2)
        return f"leaf-{req.subplot_id}"

    result = M.advance(repo, "camp", dispatcher=reposting_dispatcher, loop=True)
    # b was NOT dispatched in the stale pass — it went out on the re-tick, under the NEW era.
    assert result.dispatched == ["a", "b"]
    assert result.spec_reloads >= 1
    assert requests[0].intent_revision == 1 and requests[0].sandbox is None
    assert requests[1].intent_revision == 2
    assert requests[1].sandbox is not None
    assert requests[1].sandbox.mutation_policy == "read-only"


# ---------------------------------------------------------------------------
# R6 TOCTOU — a bare intent-phase dispatch record (mid-dispatch window) counts as
# in flight for the strand check; repeats never duplicate the halt records.
# ---------------------------------------------------------------------------


def test_strand_check_sees_mid_dispatch_intent_record(repo: Path) -> None:
    spec = _start(
        repo,
        "camp",
        [{"subplot_id": "deploy", "title": "Deploy", "kind": "code", "destructive": True}],
    )
    store = _store(repo, "camp")
    # The mid-dispatch window: the tick has written the dispatch INTENT, not yet the commit.
    STORE.append_ledger(
        store,
        {"phase": "intent", "kind": "dispatch", "key": "dispatch:deploy", "subplot_id": "deploy"},
    )
    before = spec.to_json()
    with pytest.raises(OI.RepostStrandedError, match="strand"):
        OI.repost(
            spec,
            store,
            changes={"sandbox": "read-only-verify"},
            scope="deploy",
            reason="tighten mid-dispatch",
            envelope_path=_env_path(repo),
        )
    assert spec.to_json() == before
    # (The pre-dispatch control — NO dispatch record at all applies cleanly — is
    # test_amendment_strands_irreversible_op_halts Control 2.)


def test_repeated_stranded_repost_appends_once(repo: Path) -> None:
    _start(
        repo,
        "camp",
        [{"subplot_id": "deploy", "title": "Deploy", "kind": "code", "destructive": True}],
    )
    store = _store(repo, "camp")
    env = _env_path(repo)
    assert M.advance(repo, "camp", dispatcher=_auto).dispatched == ["deploy"]

    for _ in range(3):
        spec = M.load_spec(repo, "camp")
        with pytest.raises(OI.RepostStrandedError):  # every repeat still raises...
            OI.repost(
                spec,
                store,
                changes={"sandbox": "read-only-verify"},
                scope="deploy",
                reason="tighten it",
                envelope_path=env,
            )
    # ...but the coordinator andon directive and the halt ledger record appear ONCE.
    envelope = AE.load(env)
    assert envelope is not None
    andons = [
        d for d in envelope.directives if d.directive == "andon_halt" and d.writer == "coordinator"
    ]
    assert len(andons) == 1
    strand_records = [
        r
        for r in STORE.read_ledger(store)
        if r.get("phase") == "halt" and r.get("kind") == "repost"
    ]
    assert len(strand_records) == 1
    # Control: the dedup discriminates by scope — a strand halt for a DIFFERENT leaf appends.
    AE.raise_strand_halt(env, scope="other-leaf", reason="different strand")
    envelope2 = AE.load(env)
    assert envelope2 is not None
    assert len([d for d in envelope2.directives if d.directive == "andon_halt"]) == 2


# ---------------------------------------------------------------------------
# R8 honesty — the scoped-repose offer appears ONLY on halts the hint can resolve
# (a degrade_policy-borne guarantee); attending / guarantee-tag halts carry none.
# ---------------------------------------------------------------------------


def test_attending_halt_carries_no_scoped_repose(repo: Path) -> None:
    # An ATTENDING halt fires before degrade_policy is consulted — no scoped repost value can
    # clear it (the operator is present and decides directly), so offering the hint would be
    # a false affordance.
    _start(
        repo,
        "camp",
        [
            {
                "subplot_id": "guard",
                "title": "G",
                "kind": "code",
                "backend": "cc-workflows-ultracode",
                "degrade_policy": "halt",
            }
        ],
    )
    result = M.advance(
        repo,
        "camp",
        dispatcher=M.outcome_dispatcher.make_dispatcher(available=SPEC.NODE_BACKENDS),
        available=DISPATCHER.ALWAYS_AVAILABLE,
        attending=True,
    )
    assert len(result.halted) == 1
    assert "attending" in result.halted[0]["reason"]
    assert "scoped_repose" not in result.halted[0]


def test_guarantee_tag_halt_carries_no_scoped_repose(repo: Path) -> None:
    # A guarantee borne by spec-authored guarantee_tags cannot be lifted by a repost
    # (degrade_policy/sandbox are the only node axes) — honestly offer-less.
    _start(
        repo,
        "camp",
        [
            {
                "subplot_id": "tagged",
                "title": "T",
                "kind": "code",
                "backend": "cc-workflows-ultracode",
                "guarantee_tags": ["deploy-window"],
            }
        ],
    )
    result = M.advance(
        repo,
        "camp",
        dispatcher=M.outcome_dispatcher.make_dispatcher(available=SPEC.NODE_BACKENDS),
        available=DISPATCHER.ALWAYS_AVAILABLE,
        attending=False,
    )
    assert len(result.halted) == 1
    assert "guarantee" in result.halted[0]["reason"]
    assert "scoped_repose" not in result.halted[0]


# ---------------------------------------------------------------------------
# R5 completion-time overlap — an in-flight leaf's implied closure checks come from its
# DISPATCH-ERA envelope; a loosening repost never retroactively releases its gate.
# ---------------------------------------------------------------------------

_SHA_A = "a" * 40
_SHA_B = "b" * 40


def _gh_runner(
    pr_state: dict[str, str] | None = None, head_ref_oid: dict[str, str] | None = None
) -> Any:
    """A fake `gh` runner answering both `pr_state()` and `head_ref_oid()` for the same ref."""
    pr_state = pr_state or {}
    head_ref_oid = head_ref_oid or {}

    def runner(args: list[str], **_kw: Any) -> SimpleNamespace:
        ref = args[3]
        st = pr_state.get(ref, "OPEN")
        body = {
            "state": st,
            "mergedAt": "2026-07-14T00:00:00Z" if st == "MERGED" else None,
            "headRefOid": head_ref_oid.get(ref, ""),
        }
        return SimpleNamespace(returncode=0, stdout=json.dumps(body), stderr="")

    return runner


def test_reviews_required_overlap_gates_in_flight_completion(repo: Path) -> None:
    intent = {
        "schema_version": 1,
        "run_mode": "attended",
        "ceremony_gates": {"reviews_required": "gate"},
    }
    M.start(
        repo,
        "camp",
        "obj",
        nodes=[
            {
                "subplot_id": "a",
                "title": "A",
                "kind": "code",
                "github": {"pr": "1"},
                "leaf_saga_id": "leaf-camp-a",
            },
            {
                "subplot_id": "b",
                "title": "B",
                "kind": "code",
                "github": {"pr": "2"},
                "leaf_saga_id": "leaf-camp-b",
                "depends_on": ["a"],
            },
        ],
        intent=intent,
    )
    store = _store(repo, "camp")
    assert M.advance(repo, "camp", dispatcher=_auto).dispatched == ["a"]  # a in flight, gated era

    # The loosening repost lands while a is in flight.
    spec = M.load_spec(repo, "camp")
    OI.repost(
        spec,
        store,
        changes={"reviews_required": "auto"},
        reason="loosen reviews",
        envelope_path=_env_path(repo),
    )
    M.save_spec(repo, spec)

    # b's PR stays OPEN until b actually runs (the realistic sequence); flipped below.
    pr_state = {"1": "MERGED", "2": "OPEN"}
    runner = _gh_runner(pr_state=pr_state, head_ref_oid={"1": _SHA_A, "2": _SHA_B})
    # The in-flight leaf is NOT released by the loosening: its dispatch-era posture
    # (reviews_required=gate) still requires code-review evidence at harvest.
    assert (
        ORCH.harvest(M.load_spec(repo, "camp"), store=store, github_runner=runner, repo_root=repo)
        == []
    )
    # barrier_report mirrors harvest — the operator-facing verdict tells the SAME
    # dispatch-era story (never "released" while the done transition is still gated).
    report = ORCH.barrier_report(
        M.load_spec(repo, "camp"), store=store, github_runner=runner, repo_root=repo
    )
    assert report["a"]["satisfied"] is True  # the GitHub-only barrier IS satisfied
    assert report["a"]["closure_gate"]["satisfied"] is False
    assert report["a"]["closure_gate"]["halt_reason"] == "missing-evidence:code-review"

    # Green through the intended door: the dispatch-era gate is satisfiable — recording the
    # code-review evidence releases the leaf (the gate discriminates, it doesn't just block).
    lstore = LEDGER.Store.for_saga("leaf-camp-a", repo)
    LEDGER.write(
        lstore,
        check_id="code-review",
        reviewed_sha=_SHA_A,
        producer="code-review",
        verdict="clean",
        content="ok",
    )
    assert ORCH.harvest(
        M.load_spec(repo, "camp"), store=store, github_runner=runner, repo_root=repo
    ) == ["a"]

    # Red counterpart: b dispatches AFTER the repost -> the NEW era (reviews_required=auto)
    # governs it, so it completes WITHOUT review evidence. Same campaign, same machinery —
    # the only difference is the dispatch era, proving the gate binds to dispatch time.
    assert M.advance(repo, "camp", dispatcher=_auto).dispatched == ["b"]
    pr_state["2"] = "MERGED"  # b's PR merges after its flight
    assert ORCH.harvest(
        M.load_spec(repo, "camp"), store=store, github_runner=runner, repo_root=repo
    ) == ["b"]


def test_tightening_repost_never_retroactively_imposes_checks(repo: Path) -> None:
    # The mirror-image control: a leaf dispatched under NO committed envelope ("intent": null
    # captured at dispatch) is not retroactively gated by a later live attach/tightening —
    # dispatch-time posture cuts both ways.
    M.start(
        repo,
        "camp",
        "obj",
        nodes=[
            {
                "subplot_id": "a",
                "title": "A",
                "kind": "code",
                "github": {"pr": "1"},
                "leaf_saga_id": "leaf-camp-a",
            }
        ],
    )
    store = _store(repo, "camp")
    assert M.advance(repo, "camp", dispatcher=_auto).dispatched == ["a"]  # envelope-less era

    # An all-gated envelope attaches mid-run (tightening — passes the live monotonic rule).
    spec = M.load_spec(repo, "camp")
    spec.intent = {
        "schema_version": 1,
        "run_mode": "attended",
        "ceremony_gates": {"reviews_required": "gate"},
    }
    spec.bump_revision(reason="test: attach gated envelope mid-run")
    spec.intent_revision = spec.spec_revision
    M.save_spec(repo, spec)

    runner = _gh_runner(pr_state={"1": "MERGED"}, head_ref_oid={"1": _SHA_A})
    # a completes under its dispatch-era (no-envelope) posture: no implied checks.
    assert ORCH.harvest(
        M.load_spec(repo, "camp"), store=store, github_runner=runner, repo_root=repo
    ) == ["a"]


def _crash_after_intent(req: Any) -> str:
    """Production dispatcher that HALTs after the intent record is written — the crash window.

    ``outcome._reconcile_once`` appends the ``intent`` dispatch record, THEN calls the
    dispatcher; a ``BackendHaltError`` here leaves the dangling intent record with no commit
    record — exactly the crash-after-backend-effect state the era capture must survive.

    Raised from ``M.outcome_dispatcher`` (the module instance the engine imported), not this
    file's ``DISPATCHER`` load — ``_load`` creates a separate module object, and the engine's
    per-leaf ``except`` only catches ITS class.
    """
    engine_dispatcher = M.outcome_dispatcher
    raise engine_dispatcher.BackendHaltError(
        engine_dispatcher.HaltReceipt(
            outcome_id="camp",
            subplot_id=req.subplot_id,
            backend=req.backend,
            reason="test: backend died after the intent record",
            available=(),
        )
    )


def _crash_window_ledger_phases(store: Any, sid: str) -> list[str]:
    return [
        str(r.get("phase"))
        for r in STORE.read_ledger(store)
        if r.get("kind") == "dispatch"
        and r.get("subplot_id") == sid
        and r.get("phase") in ("intent", "commit")
    ]


def test_loosening_repost_cannot_release_crash_window_leaf(repo: Path) -> None:
    # Re-panel P1: a leaf stranded in the intent-only dispatch window (backend HALTed after
    # the intent record, before the commit record) is in flight for EVERY consumer — a
    # loosening repost landing in that window must not retroactively release its completion
    # gate at harvest. Before the fix, the era map read only commit records and this leaf
    # fell back to the CURRENT (loosened) intent.
    intent = {
        "schema_version": 1,
        "run_mode": "attended",
        "ceremony_gates": {"reviews_required": "gate"},
    }
    M.start(
        repo,
        "camp",
        "obj",
        nodes=[
            {
                "subplot_id": "a",
                "title": "A",
                "kind": "code",
                "github": {"pr": "1"},
                "leaf_saga_id": "leaf-camp-a",
            }
        ],
        intent=intent,
    )
    store = _store(repo, "camp")
    result = M.advance(repo, "camp", dispatcher=_crash_after_intent)
    assert result.dispatched == []  # the dispatch HALTed mid-flight
    # Pin the window this test exercises: the intent record dangles, no commit record.
    assert _crash_window_ledger_phases(store, "a") == ["intent"]

    # The loosening repost lands inside the window (the campaign IS live — the intent
    # record counts).
    spec = M.load_spec(repo, "camp")
    OI.repost(
        spec,
        store,
        changes={"reviews_required": "auto"},
        reason="loosen mid-window",
        envelope_path=_env_path(repo),
    )
    M.save_spec(repo, spec)

    runner = _gh_runner(pr_state={"1": "MERGED"}, head_ref_oid={"1": _SHA_A})
    # NOT released without evidence: the intent record's captured era still gates it.
    assert (
        ORCH.harvest(M.load_spec(repo, "camp"), store=store, github_runner=runner, repo_root=repo)
        == []
    )
    report = ORCH.barrier_report(
        M.load_spec(repo, "camp"), store=store, github_runner=runner, repo_root=repo
    )
    assert report["a"]["closure_gate"]["satisfied"] is False
    assert report["a"]["closure_gate"]["halt_reason"] == "missing-evidence:code-review"

    # Baseline control (green through the intended door): the dispatch-era gate is
    # satisfiable — recording the evidence releases the leaf, proving the gate
    # discriminates rather than just blocking.
    lstore = LEDGER.Store.for_saga("leaf-camp-a", repo)
    LEDGER.write(
        lstore,
        check_id="code-review",
        reviewed_sha=_SHA_A,
        producer="code-review",
        verdict="clean",
        content="ok",
    )
    assert ORCH.harvest(
        M.load_spec(repo, "camp"), store=store, github_runner=runner, repo_root=repo
    ) == ["a"]


def test_tightening_attach_cannot_gate_crash_window_leaf(repo: Path) -> None:
    # Mirror control: a crash-window leaf of an ENVELOPE-LESS campaign captured
    # "intent": null on its intent record — a later tightening attach must not
    # retroactively impose checks on it (dispatch-time posture cuts both ways inside
    # the window, same as it does for settled records).
    M.start(
        repo,
        "camp",
        "obj",
        nodes=[
            {
                "subplot_id": "a",
                "title": "A",
                "kind": "code",
                "github": {"pr": "1"},
                "leaf_saga_id": "leaf-camp-a",
            }
        ],
    )
    store = _store(repo, "camp")
    assert M.advance(repo, "camp", dispatcher=_crash_after_intent).dispatched == []
    assert _crash_window_ledger_phases(store, "a") == ["intent"]

    # An all-gated envelope attaches mid-run (tightening — passes the live monotonic rule).
    spec = M.load_spec(repo, "camp")
    spec.intent = {
        "schema_version": 1,
        "run_mode": "attended",
        "ceremony_gates": {"reviews_required": "gate"},
    }
    spec.bump_revision(reason="test: attach gated envelope mid-window")
    spec.intent_revision = spec.spec_revision
    M.save_spec(repo, spec)

    runner = _gh_runner(pr_state={"1": "MERGED"}, head_ref_oid={"1": _SHA_A})
    # a completes under its captured null era: no implied checks, no evidence needed.
    assert ORCH.harvest(
        M.load_spec(repo, "camp"), store=store, github_runner=runner, repo_root=repo
    ) == ["a"]


# ---------------------------------------------------------------------------
# Release-surface drift guard (CLAUDE.md step 6): installed-plugin metadata must tell the
# same story as this diff — the verb exists AND the release surfaces mention it.
# ---------------------------------------------------------------------------


def test_release_surfaces_tell_the_repost_story() -> None:
    plugin = json.loads(
        (ROOT / "plugins" / "saga" / ".claude-plugin" / "plugin.json").read_text(encoding="utf-8")
    )
    changelog = (ROOT / "plugins" / "saga" / "CHANGELOG.md").read_text(encoding="utf-8")
    top_heading = next(line for line in changelog.splitlines() if line.startswith("## ["))
    top_version = top_heading.split("[", 1)[1].split("]", 1)[0]
    # The CHANGELOG's newest entry and plugin.json agree on the version...
    assert top_version == plugin["version"]
    # ...and the newest entry actually documents the new verb (metadata == diff story).
    newest_entry = changelog.split("## [", 2)[1]
    assert "repost" in newest_entry and "#433" in newest_entry
    # The operator-facing surfaces document the verb too.
    skill = (ROOT / "plugins" / "saga" / "skills" / "outcome" / "SKILL.md").read_text(
        encoding="utf-8"
    )
    reference = (ROOT / "plugins" / "saga" / "references" / "outcome-spec.md").read_text(
        encoding="utf-8"
    )
    assert "repost" in skill and "repost" in reference and "intent_revision" in reference
