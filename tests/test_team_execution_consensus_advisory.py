"""U7 contracts plus characterization checks for the quarantined legacy helper."""

from __future__ import annotations

import importlib.util
import json
import re
import sys
from pathlib import Path
from types import ModuleType
from typing import Any, cast

import pytest

ROOT = Path(__file__).parent.parent
HELPER = (
    ROOT
    / "plugins"
    / "team-execution"
    / "skills"
    / "team-execution"
    / "scripts"
    / "consensus_advisory.py"
)
ROSTER = ROOT / "plugins" / "saga" / "references" / "lens-roster.json"
SCORER = ROOT / "plugins" / "saga" / "scripts" / "review_consensus.py"
TEAM_SKILL_ROOT = ROOT / "plugins" / "team-execution" / "skills" / "team-execution"
REFERENCES = TEAM_SKILL_ROOT / "references"
REVIEWER_REGISTRY = REFERENCES / "reviewer-registry.md"
CONSENSUS_PROTOCOL = REFERENCES / "consensus-protocol.md"
REVIEW_CRITERIA = REFERENCES / "review-criteria.md"
ANDON_CORD = REFERENCES / "andon-cord.md"
VALIDATOR_ORDER = REFERENCES / "validator-execution-order.md"
TEAM_SKILL = TEAM_SKILL_ROOT / "SKILL.md"
README = ROOT / "plugins" / "team-execution" / "README.md"
TEAM_AGENTS = ROOT / "plugins" / "team-execution" / "agents"
SECURITY_REVIEWER = TEAM_AGENTS / "security-reviewer.md"
ARCHITECTURE_REVIEWER = TEAM_AGENTS / "architecture-reviewer.md"
DEVILS_ADVOCATE_REVIEWER = TEAM_AGENTS / "devils-advocate-reviewer.md"
CODE_REVIEW_SKILL = ROOT / "plugins" / "saga" / "skills" / "code-review" / "SKILL.md"
WORK_GATE_REFERENCE = (
    ROOT / "plugins" / "saga" / "skills" / "work" / "references" / "test-and-gates.md"
)

LIVE_POLICY_DOCS = (
    REVIEWER_REGISTRY,
    CONSENSUS_PROTOCOL,
    REVIEW_CRITERIA,
    ANDON_CORD,
    VALIDATOR_ORDER,
    TEAM_SKILL,
    README,
    *sorted(TEAM_AGENTS.glob("*.md")),
)
CYCLE_CAP_CONSUMERS = (
    CONSENSUS_PROTOCOL,
    REVIEW_CRITERIA,
    ANDON_CORD,
    VALIDATOR_ORDER,
    TEAM_SKILL,
)


def _load_helper() -> ModuleType:
    spec = importlib.util.spec_from_file_location("consensus_advisory", HELPER)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules["consensus_advisory"] = module
    spec.loader.exec_module(module)
    return module


def _load_scorer() -> ModuleType:
    spec = importlib.util.spec_from_file_location("review_consensus_for_team_execution", SCORER)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def _load_roster(path: Path = ROSTER) -> dict[str, Any]:
    return cast(dict[str, Any], json.loads(path.read_text(encoding="utf-8")))


def _selected_team_execution_assignments(
    roster: dict[str, Any], *, conditional_lenses: set[str] | None = None
) -> dict[str, str]:
    requested = conditional_lenses or set()
    return {
        lens["id"]: lens["implementations"]["team_execution"]["agent"]
        for lens in roster["lenses"]
        if lens["trigger"]["class"] == "always-on" or lens["id"] in requested
    }


C: Any = _load_helper()
SCORING: Any = _load_scorer()


def test_reviewer_selection_consumes_only_the_canonical_roster(tmp_path: Path) -> None:
    registry = REVIEWER_REGISTRY.read_text(encoding="utf-8")
    skill = TEAM_SKILL.read_text(encoding="utf-8")
    roster = _load_roster()

    assert "plugins/saga/references/lens-roster.json" in registry
    assert "implementations.team_execution" in registry
    assert "trigger.class" in registry
    assert "Base Reviewers" not in registry
    assert "Optional Reviewers" not in registry
    assert "base-reviewer list" in skill

    assignments = _selected_team_execution_assignments(roster)
    removed_lens = next(iter(assignments))
    changed = json.loads(json.dumps(roster))
    changed["lenses"] = [lens for lens in changed["lenses"] if lens["id"] != removed_lens]
    changed_path = tmp_path / "lens-roster.json"
    changed_path.write_text(json.dumps(changed), encoding="utf-8")

    assert removed_lens not in _selected_team_execution_assignments(_load_roster(changed_path))


def test_live_team_execution_policy_is_only_a_pointer_to_roster_and_scorer() -> None:
    for path in LIVE_POLICY_DOCS:
        text = path.read_text(encoding="utf-8")
        assert "9.0" not in text, path
        assert "7.0" not in text, path
        assert "5.0" not in text, path

    criteria = REVIEW_CRITERIA.read_text(encoding="utf-8")
    protocol = CONSENSUS_PROTOCOL.read_text(encoding="utf-8")
    assert "score_lens_review" in criteria
    assert "score_lens_review" in protocol
    assert "evaluate_review_readiness" in protocol
    assert not re.search(r"\b(?:arithmetic\s+mean|average\s+of)\b", criteria, re.IGNORECASE)
    assert not re.search(r"\b(?:arithmetic\s+mean|average\s+of)\b", protocol, re.IGNORECASE)
    assert "| Score |" not in criteria

    roster = _load_roster()
    assert roster["acceptance"]["rules"]
    assert all(
        dimension["anchors"] for lens in roster["lenses"] for dimension in lens["dimensions"]
    )

    for reviewer in (
        SECURITY_REVIEWER,
        ARCHITECTURE_REVIEWER,
        DEVILS_ADVOCATE_REVIEWER,
    ):
        assert "plugins/saga/references/lens-roster.json" in reviewer.read_text(encoding="utf-8")

    security = SECURITY_REVIEWER.read_text(encoding="utf-8")
    assert "hard stop" not in security
    assert "do not wait for cycle end" not in security


def test_code_review_stage_c_scores_findings_and_evaluates_independent_gates() -> None:
    skill = CODE_REVIEW_SKILL.read_text(encoding="utf-8")
    stage_c = skill.split("### Stage C — score, repair, and terminate", 1)[1].split(
        "## Phase 5 — Report, route, and saga", 1
    )[0]

    assert "construct a `FindingEvidence` value" in stage_c
    assert "through the `findings` argument" in stage_c
    assert "`IndependentGateResult`" in stage_c
    assert "built-versus-planned" in stage_c
    assert "evaluate_review_readiness" in stage_c
    assert "A gate result never changes a dimension score" in stage_c


def test_work_gate_reference_uses_typed_outcome_and_keeps_freshness_separate() -> None:
    contract = WORK_GATE_REFERENCE.read_text(encoding="utf-8")

    for outcome in (
        "accepted",
        "repairs_requested",
        "cycle_cap_best_available",
        "review_incomplete",
    ):
        assert f"**`{outcome}`**" in contract
    assert "use `outcome` as the sole acceptance decision" in contract
    assert "finding Priority, confidence, or fix-request counts" in contract
    for obsolete in (r"\bP0\b", r"\bP1\b", r"Priority 0", r"Priority 1", r"P-level"):
        assert re.search(obsolete, contract, flags=re.IGNORECASE) is None
    assert "a blocking typed outcome or a stale review" in contract
    assert "git rev-list <REVIEWED_SHA>..HEAD --count" in contract


def test_static_non_applicable_vocabulary_pointer_resolves_to_its_source() -> None:
    protocol = CONSENSUS_PROTOCOL.read_text(encoding="utf-8")
    match = re.search(
        r"cause vocabulary from the\s+\[[^]]+\]\(([^)]+)\)",
        protocol,
    )

    assert match is not None
    target = (CONSENSUS_PROTOCOL.parent / match.group(1)).resolve()
    assert target.is_file()
    assert target == ARCHITECTURE_REVIEWER.resolve()
    assert "static-non-applicable: no architecture docs or observable patterns" in target.read_text(
        encoding="utf-8"
    )


def test_cycle_cap_termination_has_one_team_execution_statement() -> None:
    statements = [
        (path, line)
        for path in CYCLE_CAP_CONSUMERS
        for line in path.read_text(encoding="utf-8").splitlines()
        if "Cycle-cap termination:" in line
    ]

    assert statements == [
        (
            CONSENSUS_PROTOCOL,
            "**Cycle-cap termination:** when the transition engine returns "
            "`cycle_cap_best_available`, stop review",
        )
    ]


def test_team_execution_contract_invokes_the_u5_scorer() -> None:
    policy = SCORING.load_scoring_policy(ROSTER)
    lens_id = next(iter(policy.lens_dimensions))
    dimensions = policy.dimensions_for(lens_id)
    score = SCORING.score_lens_review(
        lens_id,
        dict.fromkeys(dimensions, policy.maximum_score),
        policy=policy,
    )
    readiness = SCORING.evaluate_review_readiness([score])

    assert score.accepted is True
    assert readiness.review_accepted is True
    assert readiness.can_proceed is True


def test_legacy_consensus_helper_is_quarantined_without_a_production_caller() -> None:
    assert C.QUARANTINED is True

    caller = re.compile(
        r"(?:python\S*\s+[^\n]*consensus_advisory\.py|"
        r"(?:from|import)\s+[\w.]*consensus_advisory)"
    )
    references = []
    for path in (ROOT / "plugins").rglob("*"):
        if path == HELPER or path.suffix not in {".py", ".md"}:
            continue
        if caller.search(path.read_text(encoding="utf-8")):
            references.append(path)

    assert references == []


def test_external_advisory_seat_exclusion_comes_from_the_roster() -> None:
    seat = _load_roster()["participant_defaults"]["external_advisory_seat"]

    assert seat["scoring"] is False
    assert seat["consensus_denominator"] is False
    assert seat["applies_acceptance_rules"] == []
    assert "never passed to `score_lens_review`" in CONSENSUS_PROTOCOL.read_text(encoding="utf-8")


def test_external_seat_excluded_from_gate() -> None:
    result = C.calculate_consensus(
        [
            C.ReviewerResult("devils-advocate-reviewer", 9.1),
            C.ReviewerResult("security-reviewer", 9.4, dimension_scores={"OWASP": 9.4}),
            C.ReviewerResult("architecture-reviewer", 9.0),
            C.ReviewerResult(
                "external-advisory-reviewer",
                2.0,
                seat=C.ADVISORY_SEAT,
                dimension_scores={"independent synthesis": 1.0},
            ),
        ]
    )

    assert result.accepted is True
    assert result.gated_reviewers == (
        "devils-advocate-reviewer",
        "security-reviewer",
        "architecture-reviewer",
    )
    assert result.advisory_reviewers == ("external-advisory-reviewer",)
    assert result.blocking_reviewers == ()
    assert result.rerun_reviewers == ()


def test_external_seat_absence_is_noop() -> None:
    result = C.calculate_consensus(
        [
            C.ReviewerResult("devils-advocate-reviewer", 9.1),
            C.ReviewerResult("security-reviewer", 9.4),
            C.ReviewerResult(
                "external-advisory-reviewer",
                None,
                seat=C.ADVISORY_SEAT,
                status="halted",
            ),
        ]
    )

    assert result.accepted is True
    assert result.advisory_reviewers == ()
    assert result.absent_advisory_reviewers == ("external-advisory-reviewer",)


def test_convergence_diff_generated() -> None:
    report = C.build_convergence_report(
        [
            C.Finding("same", "bounds check missing", "P1", "add validation"),
            C.Finding("claude-only", "release surface missing", "P2", "bump metadata"),
            C.Finding("conflict", "tests are too narrow", "P2", "add failure path"),
        ],
        [
            C.Finding("same", "bounds check missing", "P1", "add validation"),
            C.Finding("external-only", "naming drift", "P3", "rename helper"),
            C.Finding("conflict", "tests cover enough", "P3", "no change"),
        ],
    )

    assert report.converged == ("same",)
    assert [finding.key for finding in report.claude_only] == ["claude-only"]
    assert [finding.key for finding in report.external_only] == ["external-only"]
    assert [conflict.key for conflict in report.conflicting] == ["conflict"]

    rendered = C.render_convergence_markdown(report)
    assert "Claude vs External Convergence" in rendered
    assert "`same`" in rendered
    assert "claude-only" in rendered
    assert "external-only" in rendered
    assert "Claude=tests are too narrow; external=tests cover enough" in rendered


def test_invalid_reviewer_seat_rejected() -> None:
    with pytest.raises(ValueError, match="unknown reviewer seat"):
        C.calculate_consensus([C.ReviewerResult("external", 10.0, seat="scoring-advisory")])


def test_invalid_reviewer_status_rejected() -> None:
    with pytest.raises(ValueError, match="unknown reviewer status"):
        C.calculate_consensus(
            [C.ReviewerResult("external", None, seat=C.ADVISORY_SEAT, status="maybe")]
        )
