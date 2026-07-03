"""Drift-guard tests for the Layer B consensus contract (#293 U4).

architecture-reviewer.md and consensus-protocol.md are the executable spec the reviewer
agent follows (KTD7) -- there is no scoring engine to unit-test, so these assert the contract
text itself: the fabricated N/A->8.0 default is gone, the applicable-dimensions denominator is
defined, and a static exclusion is never a failure signal.
"""

import re
from pathlib import Path

ROOT = Path(__file__).parent.parent
PLUGIN_ROOT = ROOT / "plugins" / "team-execution"
ARCHITECTURE_REVIEWER = PLUGIN_ROOT / "agents" / "architecture-reviewer.md"
CONSENSUS_PROTOCOL = (
    PLUGIN_ROOT / "skills" / "team-execution" / "references" / "consensus-protocol.md"
)


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def test_dimension_exclusion_replaces_fabricated_default() -> None:
    """R7: architecture-reviewer.md no longer fabricates a default score for a non-applicable
    dimension -- it excludes the dimension and names the applicable-dimensions denominator."""
    doc = _read(ARCHITECTURE_REVIEWER)

    assert "8.0 default" not in doc
    assert "N/A (8.0" not in doc
    # Broader than the two literal strings above: catches a differently-worded reintroduction
    # of a fabricated numeric default (e.g. "N/A (7.5 default)"), not just the exact old value.
    assert not re.search(r"N/A\s*\(\d", doc)
    assert "EXCLUDE" in doc
    assert "static-non-applicable" in doc
    assert "avg of 4 applicable" in doc


def test_consensus_gate_evaluates_applicable_dimensions() -> None:
    """R7/R8: consensus-protocol.md defines the applicable-dimensions denominator for the
    >=9.0 / no-dimension-<7.0 gate, and the whole-lens exclusion rule."""
    doc = _read(CONSENSUS_PROTOCOL)

    assert "average of applicable dimensions" in doc
    # Line-wrapped in the source doc, so pinned as two adjacent contiguous fragments rather
    # than one substring or fully-independent tokens.
    assert "no individual" in doc
    assert "applicable* dimension < 7.0" in doc
    assert "excluded WHOLE from the consensus denominator" in doc


def test_static_skip_no_floor() -> None:
    """AE3 boundary: both docs state a precondition exclusion is recorded with cause
    static-non-applicable and is never a failure -- it never enters re-review or escalation,
    and the exclusion vocabulary is shared with the Layer A execution-spec.md contract."""
    reviewer_doc = _read(ARCHITECTURE_REVIEWER)
    protocol_doc = _read(CONSENSUS_PROTOCOL)

    assert "static-non-applicable" in reviewer_doc
    assert "static-non-applicable" in protocol_doc
    # Shared vocabulary with the Layer A contract (execution-spec.md), named explicitly so a
    # reader can trace both surfaces to the same two-kinds concept.
    assert "execution-spec.md" in protocol_doc

    # Never a NEEDS REVISION / re-review trigger on its own.
    assert "never itself" in reviewer_doc or "never a NEEDS REVISION" in reviewer_doc
    assert "never a failure signal" in protocol_doc
    assert "does not trigger the re-review" in protocol_doc
    assert "is never re-run on that basis" in protocol_doc


def test_dimension_granular_exclusion_still_scores_remaining_dimensions() -> None:
    """Edge case: exclusion is dimension-granular -- the reviewer doc still requires scoring
    the four precondition-independent dimensions when only ADR-coverage is excluded."""
    doc = _read(ARCHITECTURE_REVIEWER)

    assert "Score the remaining\nfour dimensions normally" in doc or (
        "remaining" in doc and "four dimensions" in doc
    )
    # The other four dimensions have no repo-state precondition -- they are never excludable.
    for dimension in (
        "Pattern Consistency",
        "Separation of Concerns",
        "Dependency Direction",
        "Convention Adherence",
    ):
        assert dimension in doc
