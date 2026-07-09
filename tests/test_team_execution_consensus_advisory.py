"""Executable checks for the external advisory consensus seat."""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path
from types import ModuleType
from typing import Any

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


def _load_helper() -> ModuleType:
    spec = importlib.util.spec_from_file_location("consensus_advisory", HELPER)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules["consensus_advisory"] = module
    spec.loader.exec_module(module)
    return module


C: Any = _load_helper()


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
