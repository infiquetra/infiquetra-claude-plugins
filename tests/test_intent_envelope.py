"""Acceptance tests for the fleet IntentEnvelope (#380) — one committed run-start posture.

Covers every acceptance criterion on issue #380, keyed by the issue's own ``-k`` selectors:
``drift_guard``, ``round_trip_seeds_defaults``, ``spend_posture_unattended_silent``,
``spend_posture_attended_requires_token``, ``posture_prompt_shows_stakes``,
``recommend_tier_cheaper_unattended``, ``posture_error_without_token``,
``posture_unattended_silent_path``, ``issue_to_consumer_round_trip_no_reprompt``,
``ceremony_gates_default_to_gate``, ``outcome_start_skips_interview_when_envelope_present``,
``outcome_start_asks_when_envelope_absent``, ``manifest_is_typed_not_freeform``,
``unattended_run_self_selects_posture``.

The drift guard is the fleet-wide single-asker check (G-negative-space-1): no production
module or skill document outside the envelope registry defines a run-start posture
question. Its baseline controls prove the scanner could have failed (a green verdict
without a control proves nothing).
"""

from __future__ import annotations

import ast
import importlib.util
import json
import re
import sys
from pathlib import Path
from types import ModuleType
from typing import Any

import pytest

ROOT = Path(__file__).parent.parent
SAGA_SCRIPTS = ROOT / "plugins" / "saga" / "scripts"
CANONICAL_MODULE = (
    ROOT / "plugins" / "fleet-core" / "scripts" / "fleet_commons" / "intent_envelope.py"
)
SAGA_MODULE = SAGA_SCRIPTS / "intent_envelope.py"
POSTURE_CHECK = (
    ROOT
    / "plugins"
    / "team-execution"
    / "skills"
    / "team-execution"
    / "scripts"
    / "posture_check.py"
)
ENVELOPE_REFERENCE_DOC = ROOT / "plugins" / "saga" / "references" / "intent-envelope.md"

if str(SAGA_SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SAGA_SCRIPTS))

import intent_envelope as ie  # noqa: E402  (saga re-export of the canonical fleet module)


def _load_by_path(name: str, path: Path) -> ModuleType:
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


# ---------------------------------------------------------------------------
# Drift guard (G-negative-space-1): exactly one run-start posture interview.
# ---------------------------------------------------------------------------

# The registry and its documentation are the ONLY places allowed to define the
# run-mode posture vocabulary / posture questions.
_PY_ALLOWLIST = frozenset({CANONICAL_MODULE, SAGA_MODULE})
_MD_ALLOWLIST = frozenset({ENVELOPE_REFERENCE_DOC})

_ATTENDED_RE = re.compile(r"\battended\b", re.IGNORECASE)
_UNATTENDED_RE = re.compile(r"\bunattended\b", re.IGNORECASE)


def _module_defines_posture_vocab(source: str) -> bool:
    """True iff the module's string constants include BOTH run-mode words.

    Defining both "attended" and "unattended" as string values is the signature of a
    module declaring its own run-mode posture vocabulary/question instead of importing
    the envelope registry's. AST-based so comments and docstrings that merely discuss
    modes in prose do not count — only actual string constants do.
    """
    try:
        tree = ast.parse(source)
    except SyntaxError:
        return False  # not analyzable Python -> out of scope for the AST rule
    literals = {
        node.value
        for node in ast.walk(tree)
        if isinstance(node, ast.Constant) and isinstance(node.value, str)
    }
    return "attended" in literals and "unattended" in literals


def _markdown_posture_question_lines(text: str) -> list[int]:
    """Line numbers of prose posture questions: a '?' line naming BOTH run modes."""
    flagged = []
    for i, line in enumerate(text.splitlines(), start=1):
        if "?" in line and _ATTENDED_RE.search(line) and _UNATTENDED_RE.search(line):
            flagged.append(i)
    return flagged


def _production_py_files() -> list[Path]:
    files: list[Path] = []
    for base in ("plugins", "scripts", "tools"):
        for path in sorted((ROOT / base).rglob("*.py")):
            parts = set(path.parts)
            if "tests" in parts or "fixtures" in parts:
                continue
            files.append(path)
    return files


def _fleet_md_files() -> list[Path]:
    return sorted((ROOT / "plugins").rglob("*.md"))


def test_drift_guard_no_posture_question_outside_registry() -> None:
    """The single-asker rule: no production module defines the run-mode posture vocabulary
    and no skill document asks the posture question in prose — outside the registry."""
    py_offenders = [
        str(path.relative_to(ROOT))
        for path in _production_py_files()
        if path not in _PY_ALLOWLIST
        and _module_defines_posture_vocab(path.read_text(encoding="utf-8"))
    ]
    assert py_offenders == [], (
        f"modules defining a posture vocabulary outside intent_envelope.py: {py_offenders} — "
        "import the envelope registry instead of declaring run modes"
    )

    md_offenders = [
        f"{path.relative_to(ROOT)}:{line}"
        for path in _fleet_md_files()
        if path not in _MD_ALLOWLIST
        for line in _markdown_posture_question_lines(path.read_text(encoding="utf-8"))
    ]
    assert md_offenders == [], (
        f"posture questions asked in prose outside the envelope registry: {md_offenders} — "
        "route the ask through the intent_envelope interview"
    )


def test_drift_guard_reds_on_reintroduced_posture_question(tmp_path: Path) -> None:
    """Baseline control: the scanner catches a reintroduced posture question (it has teeth)."""
    rogue_py = 'RUN_MODES = ("attended", "unattended")\nQ = "which mode?"\n'
    assert _module_defines_posture_vocab(rogue_py)

    rogue_md = "# Skill\n\nRun attended or unattended for this run?\n"
    assert _markdown_posture_question_lines(rogue_md) == [3]

    # And through the same file-walk plumbing the fleet scan uses:
    (tmp_path / "rogue.py").write_text(rogue_py, encoding="utf-8")
    assert _module_defines_posture_vocab((tmp_path / "rogue.py").read_text(encoding="utf-8"))


def test_drift_guard_ignores_single_mode_mentions() -> None:
    """Control: one mode's word alone (second_opinion.py's disposition vocab) never flags."""
    assert not _module_defines_posture_vocab('DISPOSITIONS = ("declined", "unattended")\n')
    assert _markdown_posture_question_lines("Is this run unattended?\n") == []


def test_drift_guard_registry_is_the_single_asker() -> None:
    """The canonical registry exists, is closed, and the saga path re-exports it (not a copy)."""
    assert CANONICAL_MODULE.is_file() and SAGA_MODULE.is_file()
    assert ie.INTERVIEW is not None and len(ie.INTERVIEW) == 4
    qids = [q.qid for q in ie.INTERVIEW]
    assert qids == ["run_mode", "reviews_required", "merge", "deploy_nonprod"]
    # The saga module must not re-declare the schema — its INTERVIEW is the same object
    # loaded from the canonical fleet-commons home.
    saga_source = SAGA_MODULE.read_text(encoding="utf-8")
    assert 'fleet_commons_shim.load("intent_envelope")' in saga_source


# ---------------------------------------------------------------------------
# T12-F1-2: round-trip + per-unit tier seeding on ExecutionSpec.
# ---------------------------------------------------------------------------


def _minimal_exec_spec(intent: dict[str, Any] | None) -> dict[str, Any]:
    data: dict[str, Any] = {
        "name": "spec-380",
        "description": "seeding fixture",
        "units": [
            {
                "unit_id": "u1",
                "label": "one unit",
                "tier": {"model": "sonnet", "effort": "medium"},
                "prompt": "do the thing",
            }
        ],
    }
    if intent is not None:
        data["intent"] = intent
    return data


def test_round_trip_seeds_defaults() -> None:
    """T12-F1-2: the posture field round-trips through ExecutionSpec and seeds per-unit
    tier defaults through the one mode-keyed matrix (asked once, never per unit)."""
    import execution_spec

    unattended = ie.apply_answers({"run_mode": "unattended"}).to_dict()
    spec = execution_spec.ExecutionSpec.from_dict(_minimal_exec_spec(unattended))
    spec.validate()
    rebuilt = execution_spec.ExecutionSpec.from_dict(spec.to_dict())
    rebuilt.validate()
    assert rebuilt.intent == unattended

    attended_spec = execution_spec.ExecutionSpec.from_dict(
        _minimal_exec_spec(ie.apply_answers({"run_mode": "attended"}).to_dict())
    )
    seeded_unattended = ie.seeded_tier(rebuilt, "judgment")
    seeded_attended = ie.seeded_tier(attended_spec, "judgment")
    assert (seeded_attended.model, seeded_attended.effort) == ("opus", "high")
    # The unattended posture seeds a strictly cheaper default for the same work shape.
    assert (seeded_unattended.model, seeded_unattended.effort) == ("sonnet", "high")

    # A spec with NO committed intent seeds the attended default — today's behavior.
    bare = execution_spec.ExecutionSpec.from_dict(_minimal_exec_spec(None))
    assert "intent" not in bare.to_dict()
    seeded_bare = ie.seeded_tier(bare, "judgment")
    assert (seeded_bare.model, seeded_bare.effort) == (
        seeded_attended.model,
        seeded_attended.effort,
    )


def test_round_trip_seeds_defaults_rejects_invalid_intent() -> None:
    import execution_spec

    spec = execution_spec.ExecutionSpec.from_dict(_minimal_exec_spec({"run_mode": "nope"}))
    with pytest.raises(execution_spec.SpecError, match="invalid intent envelope"):
        spec.validate()


# ---------------------------------------------------------------------------
# T12-F3-7: mode-keyed spend posture is machinery, not prose.
# ---------------------------------------------------------------------------


def test_spend_posture_unattended_silent() -> None:
    assert ie.spend_posture("unattended") == ("cache-tight", "silent")
    decision = ie.resolve_spend_action("unattended", spend_increase=False)
    assert decision.silent is True and decision.action == "proceed-default"


def test_spend_posture_attended_requires_token() -> None:
    assert ie.spend_posture("attended") == ("interactive", "ask-on-spend-increase")
    with pytest.raises(ie.PostureError, match="approval token"):
        ie.resolve_spend_action("attended", spend_increase=True)
    approved = ie.resolve_spend_action("attended", spend_increase=True, approval_token="jeff-ok-1")
    assert approved.action == "proceed-increase" and approved.silent is False


def test_spend_posture_rejects_unknown_mode() -> None:
    with pytest.raises(ie.IntentEnvelopeError, match="run_mode"):
        ie.spend_posture("hybrid")


# ---------------------------------------------------------------------------
# T4-F4-2: the interview prompt shows computed stakes, not guesswork.
# ---------------------------------------------------------------------------


def _outcome_spec_module() -> ModuleType:
    import outcome_spec

    module: ModuleType = outcome_spec
    return module


def _dag(edges: dict[str, list[str]]) -> Any:
    outcome_spec = _outcome_spec_module()
    nodes = [
        {"subplot_id": sid, "title": sid.upper(), "kind": "code", "depends_on": deps}
        for sid, deps in edges.items()
    ]
    spec = outcome_spec.OutcomeSpec.from_dict(
        {"outcome_id": "oc-stakes", "objective": "stakes fixture", "nodes": nodes}
    )
    spec.validate()
    return spec


def test_posture_prompt_shows_stakes() -> None:
    """The known independent-vs-chained fixture: both computed numbers appear in the prompt."""
    independent = _dag({"a": [], "b": [], "c": []})
    chained = _dag({"a": [], "b": ["a"], "c": ["b"]})

    ind = ie.compute_stakes(independent)
    assert (ind.parallel_width, ind.critical_path_estimate) == (3, 1.0)
    chn = ie.compute_stakes(chained)
    assert (chn.parallel_width, chn.critical_path_estimate) == (1, 3.0)

    ind_prompt = ie.render_interview(ind)
    assert "parallel_width: 3" in ind_prompt
    assert "critical_path_estimate: 1" in ind_prompt
    chn_prompt = ie.render_interview(chn)
    assert "parallel_width: 1" in chn_prompt
    assert "critical_path_estimate: 3" in chn_prompt
    # The manifest carries the same numbers machine-readably.
    manifest = ie.interview_manifest(chn)
    assert manifest["stakes"] == {"parallel_width": 1, "critical_path_estimate": 3.0}


def test_posture_prompt_stakes_reuse_critical_path_wall() -> None:
    """compute_stakes reuses outcome_costs.critical_path_wall — never a re-derivation."""
    import outcome_costs

    chained = _dag({"a": [], "b": ["a"], "c": ["b"]})
    walls = {n.subplot_id: 1.0 for n in chained.nodes}
    assert ie.compute_stakes(chained).critical_path_estimate == outcome_costs.critical_path_wall(
        chained, walls
    )


# ---------------------------------------------------------------------------
# T12-F6-7: mode-aware tier recommendation.
# ---------------------------------------------------------------------------


def test_recommend_tier_cheaper_unattended() -> None:
    """For the same work shape, unattended recommends a strictly cheaper default tier."""
    import fleet_commons_shim

    palette = fleet_commons_shim.load("tier_palette")
    attended = ie.recommend_tier("judgment", "attended")
    unattended = ie.recommend_tier("judgment", "unattended")
    model_cheaper = palette.model_rank(unattended.model) > palette.model_rank(attended.model)
    effort_cheaper = palette.effort_rank(unattended.effort) < palette.effort_rank(attended.effort)
    assert model_cheaper or effort_cheaper, (
        f"unattended {unattended.model}/{unattended.effort} is not cheaper than "
        f"attended {attended.model}/{attended.effort}"
    )
    # Exactly one rung down the ordered ladder ({#tier-vocab-ordering}), never a jump.
    resolver = fleet_commons_shim.load("tier_resolver")
    assert (unattended.model, unattended.effort) == resolver.cheaper_fallback(
        attended.model, attended.effort
    )


def test_recommend_tier_floor_is_a_no_op() -> None:
    """At the ladder floor the unattended fallback equals the default — never an error."""
    attended = ie.recommend_tier("purely-mechanical", "attended")
    unattended = ie.recommend_tier("purely-mechanical", "unattended")
    assert (attended.model, attended.effort) == ("haiku", "low")
    assert (unattended.model, unattended.effort) == ("haiku", "low")


def test_recommend_tier_rejects_unknown_inputs() -> None:
    with pytest.raises(ie.IntentEnvelopeError, match="run_mode"):
        ie.recommend_tier("judgment", "sometimes")
    with pytest.raises(Exception, match="work_shape"):
        ie.recommend_tier("interpretive-dance", "attended")


# ---------------------------------------------------------------------------
# T4-F4-1: shared posture primitive with a real wired consumer (Step B1).
# ---------------------------------------------------------------------------

PC = _load_by_path("te_posture_check", POSTURE_CHECK)


def _envelope_dict(run_mode: str) -> dict[str, Any]:
    data: dict[str, Any] = ie.apply_answers({"run_mode": run_mode}).to_dict()
    return data


def test_posture_error_without_token() -> None:
    """The wired team-execution Step B1 consumer: attended + spend increase + no token
    raises PostureError through the shared resolver (structural refusal, not prose)."""
    with pytest.raises(PC.PostureError, match="approval token"):
        PC.check(_envelope_dict("attended"), spend_increase=True)
    # The CLI surfaces the same refusal as a distinct exit code (2).
    approved = PC.check(_envelope_dict("attended"), spend_increase=True, approval_token="tok-1")
    assert approved["action"] == "proceed-increase" and approved["step"] == "B1"


def test_posture_unattended_silent_path() -> None:
    """The unattended path returns cache-tight silently through the same wired consumer."""
    result = PC.check(_envelope_dict("unattended"))
    assert result["posture"] == "cache-tight"
    assert result["silent"] is True
    assert result["action"] == "proceed-default"
    held = PC.check(_envelope_dict("unattended"), spend_increase=True)
    assert held["action"] == "hold-at-default" and held["silent"] is True


def test_posture_check_cli_round_trip(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    envelope_path = tmp_path / "envelope.json"
    envelope_path.write_text(json.dumps(_envelope_dict("unattended")), encoding="utf-8")
    assert PC.main(["--envelope-file", str(envelope_path)]) == 0
    out = json.loads(capsys.readouterr().out)
    assert out["posture"] == "cache-tight"

    attended_path = tmp_path / "attended.json"
    attended_path.write_text(json.dumps(_envelope_dict("attended")), encoding="utf-8")
    assert PC.main(["--envelope-file", str(attended_path), "--spend-increase"]) == 2
    err = json.loads(capsys.readouterr().err)
    assert err["error"] == "posture-error"


def test_posture_check_rejects_malformed_envelope(tmp_path: Path) -> None:
    """Fail closed: a wave never spawns under an envelope nobody can strictly understand."""
    with pytest.raises(PC.IntentEnvelopeError):
        PC.check({"run_mode": "attended", "surprise": 1})
    bad = tmp_path / "bad.json"
    bad.write_text("{not json", encoding="utf-8")
    assert PC.main(["--envelope-file", str(bad)]) == 1


# ---------------------------------------------------------------------------
# G-hybrids-4 / H-F2-9 / S-22: issue -> envelope -> consumer, no re-prompt.
# ---------------------------------------------------------------------------


def _sdlc_manager() -> ModuleType:
    mc_scripts = ROOT / "plugins" / "mission-control" / "scripts"
    if str(mc_scripts) not in sys.path:
        sys.path.insert(0, str(mc_scripts))
    import sdlc_manager

    module: ModuleType = sdlc_manager
    return module


def test_issue_to_consumer_round_trip_no_reprompt(capsys: pytest.CaptureFixture[str]) -> None:
    """A ship-policy envelope authored at mission-control issue capture survives to the
    saga consumer unchanged, and no consumer has a question left to re-ask."""
    sdlc_manager = _sdlc_manager()
    block = sdlc_manager.issue_render_intent_envelope(
        "unattended", merge="auto", authored_by="jeff"
    )
    capsys.readouterr()  # the CLI print is not under test here
    issue_body = f"## Problem\n\nSome capability.\n\n{block}\n### Verification\n\ngreen.\n"

    # Capture-side schema validation (the mission-control readiness gate) passes...
    assert sdlc_manager._intent_envelope_readiness_error(issue_body) is None
    # ...and a corrupted block is a BLOCKING capture error (fail closed at authoring).
    broken = issue_body.replace('"unattended"', '"sideways"')
    error = sdlc_manager._intent_envelope_readiness_error(broken)
    assert error is not None and "Invalid intent envelope" in error

    # The saga consumer reads the SAME envelope, unchanged.
    decision = ie.outcome_start_decision(issue_body)
    assert decision.interview_required is False
    assert decision.envelope is not None
    assert decision.envelope.run_mode == "unattended"
    assert decision.envelope.ceremony_gates.merge == "auto"
    assert decision.envelope.authored_by == "jeff"
    assert decision.envelope.source == "issue-capture"

    # No-reprompt contract: every interview question is already answered by the envelope.
    assert ie.unanswered_questions(decision.envelope) == ()
    # And with no envelope, the interview is still owed in full (the guard could fail).
    assert ie.unanswered_questions(None) == tuple(q.qid for q in ie.INTERVIEW)


def test_issue_round_trip_rejects_two_blocks() -> None:
    envelope = ie.apply_answers({"run_mode": "attended"})
    body = ie.render_issue_block(envelope) + "\n" + ie.render_issue_block(envelope)
    with pytest.raises(ie.IntentEnvelopeError, match="exactly one"):
        ie.envelope_from_issue_body(body)


# ---------------------------------------------------------------------------
# T7-F3-2: ceremony gates are pre-declared fields defaulting to gate.
# ---------------------------------------------------------------------------


def test_ceremony_gates_default_to_gate(tmp_path: Path) -> None:
    """An unset ceremony gate defaults to gate, and the block round-trips through save/load."""
    envelope = ie.IntentEnvelope.from_dict({"run_mode": "attended"})
    gates = envelope.ceremony_gates
    assert (gates.reviews_required, gates.merge, gates.deploy_nonprod) == ("gate", "gate", "gate")

    # Save/load round trip (the committed-artifact path): every gate survives explicitly.
    path = tmp_path / "envelope.json"
    path.write_text(envelope.to_json(), encoding="utf-8")
    reloaded = ie.IntentEnvelope.from_dict(json.loads(path.read_text(encoding="utf-8")))
    assert reloaded == envelope
    assert reloaded.to_dict()["ceremony_gates"] == {
        "reviews_required": "gate",
        "merge": "gate",
        "deploy_nonprod": "gate",
    }


def test_ceremony_gates_reject_unknown_field_and_value() -> None:
    with pytest.raises(ie.IntentEnvelopeError, match="unknown field"):
        ie.CeremonyGates.from_dict({"deploy_prod": "auto"})
    with pytest.raises(ie.IntentEnvelopeError, match="not in"):
        ie.CeremonyGates.from_dict({"merge": "yolo"})


# ---------------------------------------------------------------------------
# S-22 / T7-F6-7 / H-F2-9: /outcome start skips or asks — the production path.
# ---------------------------------------------------------------------------


def _outcome_module() -> ModuleType:
    import outcome

    module: ModuleType = outcome
    return module


def test_outcome_start_skips_interview_when_envelope_present(tmp_path: Path) -> None:
    """`/outcome start` commits the issue-authored envelope onto the spec and skips the
    interview — exercised through the production start() + resolve_start_intent path."""
    outcome = _outcome_module()
    envelope = ie.apply_answers({"run_mode": "unattended"}, authored_by="jeff")
    issue_body = "## Objective\n\nShip it.\n\n" + ie.render_issue_block(envelope)

    resolution = outcome.resolve_start_intent(issue_body, None)
    assert resolution["interview_required"] is False
    assert resolution["intent_source"] == "issue"

    repo_root = tmp_path / "repo"
    (repo_root / ".git").mkdir(parents=True)

    def _git_common_dir_runner(cmd: list[str], **_kwargs: Any) -> Any:
        class _Result:
            returncode = 0
            stderr = ""
            stdout = str(repo_root / ".git") + "\n"

        return _Result()

    spec = outcome.start(
        repo_root,
        "oc-envelope",
        "ship it",
        intent=resolution["intent"],
        runner=_git_common_dir_runner,
    )
    assert spec.intent == envelope.to_dict()
    # The committed artifact carries the envelope (the durable ask-once record).
    on_disk = json.loads(outcome.spec_path(repo_root, "oc-envelope").read_text(encoding="utf-8"))
    assert on_disk["intent"] == envelope.to_dict()


def test_outcome_start_asks_when_envelope_absent(tmp_path: Path) -> None:
    """Absent or invalid envelopes fall back to the interview — never silently adopted."""
    outcome = _outcome_module()

    absent = outcome.resolve_start_intent("## Objective\n\nno envelope here", None)
    assert absent["interview_required"] is True
    assert absent["intent"] is None and absent["intent_source"] is None

    invalid_body = '```intent-envelope\n{"run_mode": "sideways"}\n```\n'
    invalid = outcome.resolve_start_intent(invalid_body, None)
    assert invalid["interview_required"] is True
    assert invalid["intent"] is None
    assert "invalid" in invalid["interview_reason"]

    # An explicit --intent-file wins and skips the interview (the interview-capture path).
    envelope_path = tmp_path / "envelope.json"
    envelope_path.write_text(ie.apply_answers({"run_mode": "attended"}).to_json(), encoding="utf-8")
    from_file = outcome.resolve_start_intent(None, envelope_path)
    assert from_file["interview_required"] is False
    assert from_file["intent_source"] == "file"

    # But an INVALID --intent-file is direct operator input -> a loud error, not a fallback.
    bad_path = tmp_path / "bad.json"
    bad_path.write_text('{"run_mode": "sideways"}', encoding="utf-8")
    with pytest.raises(outcome.OutcomeError, match="intent-file"):
        outcome.resolve_start_intent(None, bad_path)


# ---------------------------------------------------------------------------
# T1-F5-8: the interview is a typed challenge-response manifest.
# ---------------------------------------------------------------------------


def test_manifest_is_typed_not_freeform() -> None:
    """Fixed question set, closed options, typed answers — free-form prose is rejected."""
    manifest = ie.interview_manifest()
    assert manifest["kind"] == "run-start-posture-interview"
    assert [q["qid"] for q in manifest["questions"]] == [q.qid for q in ie.INTERVIEW]
    for question in manifest["questions"]:
        assert question["options"], f"{question['qid']} has no closed option set"
        assert question["required"] or question["default"] in question["options"]

    # Free-form prose answers fail closed.
    with pytest.raises(ie.IntentEnvelopeError, match="typed answers only"):
        ie.apply_answers({"run_mode": "mostly attended I think"})
    # Unknown qids fail closed (the manifest is fixed, not extensible per consumer).
    with pytest.raises(ie.IntentEnvelopeError, match="unknown qid"):
        ie.apply_answers({"run_mode": "attended", "vibes": "good"})
    # Missing required answers fail closed.
    with pytest.raises(ie.IntentEnvelopeError, match="required qid"):
        ie.apply_answers({"merge": "auto"})
    # Non-string answers fail closed (typed end to end).
    with pytest.raises(ie.IntentEnvelopeError, match="must be a string"):
        ie.apply_answers({"run_mode": True})


# ---------------------------------------------------------------------------
# T1-F6-8: mode→intent default matrix — unattended runs pick their own posture.
# ---------------------------------------------------------------------------


def test_unattended_run_self_selects_posture() -> None:
    """An unattended run selects posture defaults from the same (work_shape, run_mode)
    matrix recommend_tier uses, with no interactive answer required."""
    selected = ie.self_select_posture("judgment")
    envelope = selected.envelope
    assert envelope.run_mode == "unattended"
    assert envelope.source == "defaults:unattended"
    envelope.validate()  # a fully valid envelope with zero answers supplied
    gates = envelope.ceremony_gates
    assert (gates.reviews_required, gates.merge, gates.deploy_nonprod) == ("gate", "gate", "gate")

    # SAME matrix: the tier equals recommend_tier(work_shape, "unattended") exactly.
    expected = ie.recommend_tier("judgment", "unattended")
    assert selected.tier == expected
    # And nothing is left to ask.
    assert ie.unanswered_questions(envelope) == ()
