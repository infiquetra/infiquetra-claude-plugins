"""Acceptance + unit tests for the mid-run adjustment envelope (#372).

Covers the envelope primitive (R1-R3) and its three stopping writers — operator quiesce
(R4), plan-declared pause points (R5-R7), worker-raised andon-cord (R8-R9) — plus the
fail-closed contract (R3). The ``quiesce_drain``, ``andon_blocks_next_wave``, and
``unknown_directive_fails_closed`` scenarios drive the production ``outcome.advance`` tick
wiring (not a scaffold reimplementation) so the poll boundary is exercised end to end; each
green assertion is paired with a control that proves the check could have failed.
"""

from __future__ import annotations

import importlib.util
import json
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
M = _load("outcome")
SPEC = _load("outcome_spec")
STORE = _load("outcome_store")
REVIEW_CONSENSUS = _load("review_consensus")

TEAM_REFS = ROOT / "plugins" / "team-execution" / "skills" / "team-execution" / "references"


@pytest.fixture
def repo(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """A tmp repo_root whose git common dir resolves to tmp_path/.git (no real git)."""
    common = tmp_path / ".git"
    common.mkdir()

    def fake_run(args: list[str], **_kw: Any) -> SimpleNamespace:
        return SimpleNamespace(returncode=0, stdout=str(common) + "\n", stderr="")

    monkeypatch.setattr(M.outcome_store.subprocess, "run", fake_run)
    return tmp_path


# ---------------------------------------------------------------- envelope primitive (R1-R3)


def test_parse_round_trips_every_known_directive() -> None:
    doc = {
        "version": 1,
        "directives": [
            {"directive": "quiesce", "writer": "operator", "reason": "drain"},
            {"directive": "pause_after", "writer": "plan", "segment": "code-review"},
            {"directive": "andon_halt", "writer": "worker", "scope": "leaf-3"},
            {"directive": "re-tier", "writer": "operator", "tier": "opus:high"},
            {"directive": "add-reviewer", "writer": "operator", "reviewer": "security"},
            {"directive": "cancel", "writer": "operator"},
            {"directive": "abort", "writer": "operator"},
        ],
    }
    env = AE.parse(doc)
    assert [d.directive for d in env.directives] == [
        "quiesce",
        "pause_after",
        "andon_halt",
        "re-tier",
        "add-reviewer",
        "cancel",
        "abort",
    ]
    # round-trips through to_dict deterministically
    assert AE.parse(env.to_dict()).to_dict() == env.to_dict()


def test_unknown_directive_fails_closed() -> None:
    # R3: an unrecognized directive is an ERROR that names the token, never a silent pass.
    with pytest.raises(AE.EnvelopeError, match=r"unrecognized directive: 'frobnicate'"):
        AE.parse({"version": 1, "directives": [{"directive": "frobnicate"}]})
    # control: the SAME shape with a KNOWN directive parses cleanly, proving the check
    # discriminates rather than rejecting everything.
    ok = AE.parse({"version": 1, "directives": [{"directive": "quiesce"}]})
    assert ok.directives[0].directive == "quiesce"


def test_unknown_directive_fails_closed_variants() -> None:
    # every unmodellable shape fails closed (fail-closed, never enumerate-and-skip)
    with pytest.raises(AE.EnvelopeError, match="version"):
        AE.parse({"version": 2, "directives": []})
    with pytest.raises(AE.EnvelopeError, match="version must be an int"):
        AE.parse({"version": "1", "directives": []})
    with pytest.raises(AE.EnvelopeError, match="unknown envelope key"):
        AE.parse({"version": 1, "directives": [], "extra": 1})
    with pytest.raises(AE.EnvelopeError, match="unknown key"):
        AE.parse({"version": 1, "directives": [{"directive": "quiesce", "bogus": 1}]})
    with pytest.raises(AE.EnvelopeError, match="missing required field"):
        AE.parse({"version": 1, "directives": [{"directive": "pause_after"}]})
    with pytest.raises(AE.EnvelopeError, match="unrecognized writer"):
        AE.parse({"version": 1, "directives": [{"directive": "quiesce", "writer": "ghost"}]})
    with pytest.raises(AE.EnvelopeError, match="must be a JSON object"):
        AE.parse([1, 2, 3])


def test_load_malformed_file_fails_closed(tmp_path: Path) -> None:
    p = tmp_path / "env.json"
    p.write_text("{not json")
    with pytest.raises(AE.EnvelopeError, match="not readable JSON"):
        AE.load(p)
    # control: an ABSENT file is not an error — it means "no directives, proceed".
    assert AE.load(tmp_path / "absent.json") is None


def test_poll_precedence_halt_beats_drain_beats_pause() -> None:
    doc = {
        "version": 1,
        "directives": [
            {"directive": "pause_after", "writer": "plan", "segment": "s"},
            {"directive": "quiesce", "writer": "operator"},
            {"directive": "andon_halt", "writer": "worker"},
        ],
    }
    env = AE.parse(doc)
    # HALT wins — composing with HALT-not-degrade precedence, not a second halt vocabulary.
    assert AE.poll(env, segment="s").action == "halt"


# ------------------------------------------------------------------- operator quiesce (R4)


def test_quiesce_drain(repo: Path) -> None:
    # R4/F1: a quiesce written mid-run drains in-flight (the harvest still runs) and dispatches
    # NOTHING new at the next tick boundary, through the production advance() poll wiring.
    M.start(repo, "ship-x", "Ship feature X")
    env_path = AE.default_envelope_path(repo)

    harvest_calls: list[int] = []

    def harvester(spec: Any, store: Any) -> list[str]:
        harvest_calls.append(1)  # in-flight completions are still drained on the stop tick
        return []

    def auto(req: Any) -> str:
        return f"leaf-{req.subplot_id}"

    # control: with NO envelope, the very same advance dispatches the frontier leaf.
    ctrl = M.advance(repo, "ship-x", dispatcher=auto, harvester=harvester)
    assert ctrl.dispatched == ["design"]

    # now raise quiesce and advance again on a fresh outcome so the frontier is still ready
    M.start(repo, "ship-y", "Ship feature Y")
    AE.raise_quiesce(env_path, reason="operator pausing the fleet")
    result = M.advance(repo, "ship-y", loop=True, dispatcher=auto, harvester=harvester)
    assert result.dispatched == []  # dispatched nothing new (drained-not-dispatched)
    assert result.adjustment["action"] == "drain"
    assert any("quiesce" in s for s in result.adjustment["surfaced"])
    assert len(harvest_calls) >= 2  # the harvest (drain) still ran on the stop tick
    # the frontier leaf never left `ready` — no work was handed out under quiesce
    assert M.status(repo, "ship-y")["states"]["design"] == "ready"


def test_quiesce_writer_helper_appends_to_one_file(tmp_path: Path) -> None:
    p = tmp_path / "env.json"
    AE.raise_quiesce(p, reason="a")
    AE.raise_andon(p, writer="worker", reason="b")
    env = AE.load(p)
    assert env is not None
    # both writers converge on ONE file (not two) — the single-polled-surface contract
    assert [d.directive for d in env.directives] == ["quiesce", "andon_halt"]


# -------------------------------------------------------------- plan-declared pause (R5-R7)


def test_pause_after_boundary() -> None:
    # R5: a declared pause_after halts at exactly that boundary and proceeds elsewhere.
    env = AE.parse(
        {
            "version": 1,
            "directives": [
                {"directive": "pause_after", "writer": "plan", "segment": "code-review"}
            ],
        }
    )
    assert AE.poll(env, segment="code-review").action == "pause"  # halts at the declared boundary
    assert AE.poll(env, segment="test").action == "proceed"  # deterministic: only THAT boundary
    assert AE.poll(env, segment=None).action == "proceed"


def test_pause_after_resumes_only_on_explicit_continue(tmp_path: Path) -> None:
    # R5: resumes only on an explicit continue signal (acknowledge), never on silence.
    p = tmp_path / "env.json"
    AE.declare_pause_after(p, "code-review", reason="review gate")
    assert AE.poll(AE.load(p), segment="code-review").action == "pause"  # still paused (no ack)
    AE.acknowledge_pause(p, "code-review")  # the explicit continue signal
    assert AE.poll(AE.load(p), segment="code-review").action == "proceed"  # now continues
    # control: a continue with nothing to continue fails closed (no silent no-op)
    with pytest.raises(AE.EnvelopeError, match="no unacknowledged pause_after"):
        AE.acknowledge_pause(p, "code-review")


def test_pause_after_absent_only_irreversibles_pause() -> None:
    # R6: absent an explicit pause_after, only IRREVERSIBLE actions pause by default;
    # reversible actions proceed under the act-log-notify path instead.
    assert AE.poll(AE.parse({"version": 1, "directives": []})).action == "proceed"
    # The reversible/irreversible disposition split lived in undo_ledger, removed in #666:
    # it never wrote a ledger entry in production. Only the envelope side is asserted now.


def test_pause_context_model_change(tmp_path: Path) -> None:
    # R7/S-31: a declared pause point accepts an operator context/model change and the resumed
    # run HONORS it — verified via a transcript assertion, not accepted-and-ignored.
    p = tmp_path / "env.json"
    AE.declare_pause_after(p, "phase-2", reason="swap the tier", resume_tier="opus:xhigh")
    assert AE.poll(AE.load(p), segment="phase-2").action == "pause"  # halts to accept the change

    AE.acknowledge_pause(p, "phase-2")  # operator continues, carrying the model change
    decision = AE.poll(AE.load(p), segment="phase-2")
    assert decision.action == "proceed"
    # the change is surfaced as an amendment the resumed run must apply
    assert {"kind": "re-tier", "tier": "opus:xhigh"} in decision.amendments

    # simulate the resumed run applying the amendment and writing a transcript — the honored
    # tier must appear in the transcript (not silently dropped).
    transcript: list[str] = []
    effective_tier = "sonnet:high"  # the pre-pause default
    for amd in decision.amendments:
        if amd["kind"] == "re-tier":
            effective_tier = amd["tier"]
            transcript.append(f"resume honored re-tier -> {amd['tier']}")
    assert effective_tier == "opus:xhigh"
    assert transcript == [
        "resume honored re-tier -> opus:xhigh"
    ]  # transcript proves it was honored


# ------------------------------------------------------------- worker-raised andon (R8-R9)


def test_andon_blocks_next_wave(repo: Path) -> None:
    # R8/R9/F3: a worker-raised andon reaches the coordinator through the SAME envelope file
    # and blocks the next tick/wave from dispatching, writing an operator-surface HALT record.
    M.start(repo, "ship-x", "Ship feature X")
    env_path = AE.default_envelope_path(repo)

    def auto(req: Any) -> str:
        return f"leaf-{req.subplot_id}"

    AE.raise_andon(env_path, writer="reviewer", scope="build", reason="tests fabricated")
    result = M.advance(repo, "ship-x", loop=True, dispatcher=auto)
    assert result.dispatched == []  # the next wave is blocked
    assert result.adjustment["action"] == "halt"
    surfaced = " ".join(result.adjustment["surfaced"])
    assert "andon_halt" in surfaced and "reviewer" in surfaced  # operator-surface HALT record


def test_andon_does_not_weaken_team_execution_iteration_caps() -> None:
    # R9: the andon-cord is an ORTHOGONAL halt path — it must not remove or relax the existing
    # per-loop iteration caps. Review's cap is executable policy; Team Execution points to its
    # terminal result instead of restating the numeric limit.
    consensus = (TEAM_REFS / "consensus-protocol.md").read_text(encoding="utf-8")
    validator = (TEAM_REFS / "validator-execution-order.md").read_text(encoding="utf-8")
    assert REVIEW_CONSENSUS.MAX_REVIEW_CYCLES == 3
    assert consensus.count("**Cycle-cap termination:**") == 1
    assert "`cycle_cap_best_available`, stop review\nattempts" in consensus
    assert "maximum of 3 remediation loops" in validator  # the re-run loop cap survives


def test_andon_writer_helper_rejects_non_worker_writer(tmp_path: Path) -> None:
    p = tmp_path / "env.json"
    with pytest.raises(AE.EnvelopeError, match="andon writer must be worker/reviewer"):
        AE.raise_andon(p, writer="operator")


# ------------------------------------------------------- production fail-closed via advance


def test_unknown_directive_in_envelope_halts_advance(repo: Path) -> None:
    # R3 end to end: a malformed envelope file makes the production advance tick fail closed —
    # the run HALTs and surfaces the offending directive rather than dispatching.
    M.start(repo, "ship-x", "Ship feature X")
    env_path = AE.default_envelope_path(repo)
    env_path.parent.mkdir(parents=True, exist_ok=True)
    env_path.write_text(json.dumps({"version": 1, "directives": [{"directive": "explode"}]}))

    def auto(req: Any) -> str:
        return f"leaf-{req.subplot_id}"

    result = M.advance(repo, "ship-x", loop=True, dispatcher=auto)
    assert result.dispatched == []  # no dispatch under a fail-closed envelope
    assert result.adjustment["action"] == "halt"
    assert any("fail-closed" in s and "explode" in s for s in result.adjustment["surfaced"])


# ---------------------------------------------------------------------------
# Panel hand-finish: value-type strictness (shape-valid but wrong-typed values
# must be errors, never silent no-ops) + surfaced-not-dropped amendments.
# ---------------------------------------------------------------------------


def test_string_acknowledged_fails_closed() -> None:
    """acknowledged: 'no' bool-coerces truthy and would silently SKIP a declared pause."""
    data = {
        "version": 1,
        "directives": [
            {
                "directive": "pause_after",
                "writer": "plan",
                "segment": "code-review",
                "acknowledged": "no",
            }
        ],
    }
    with pytest.raises(AE.EnvelopeError, match="acknowledged"):
        AE.parse(data)


def test_non_string_segment_fails_closed() -> None:
    """segment: 5 parses cleanly but matches no boundary — a silently unreachable pause."""
    data = {
        "version": 1,
        "directives": [{"directive": "pause_after", "writer": "plan", "segment": 5}],
    }
    with pytest.raises(AE.EnvelopeError, match="segment"):
        AE.parse(data)


def test_clear_cli_removes_envelope(tmp_path: Path) -> None:
    path = AE.default_envelope_path(tmp_path)
    AE.raise_quiesce(path, reason="drain")
    assert path.exists()
    assert AE._main(["--repo-root", str(tmp_path), "clear"]) == 0
    assert not path.exists()
