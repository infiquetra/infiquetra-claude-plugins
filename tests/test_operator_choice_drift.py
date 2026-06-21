"""Drift guard: every execution-backend offer surface must stay a SUPERSET of the
`operator-choice.md` §3.2 dynamic-workflow purpose list.

The §3.2 contract names TWO first-class purposes for `cc-workflows-ultracode`
("dynamic workflows"):

  1. **Breadth / scale** — broad independent fan-out / probe-all sweep.
  2. **Adversarial confidence** — judge-panel / refute-N / perspective-diverse verification.

A future SKILL rebuild must not silently drop a purpose back to "fan-out only", and
must keep framing the team<->workflow fork on the GOVERNANCE axis (does the verdict
need to stick?), not on "review depth" (which both backends have). This test fails if
any offer surface omits a §3.2 purpose or reintroduces the "review depth" framing of
the fork.

The assertions anchor on STABLE content markers (bolded purpose names + their defining
keyword sets), never on line numbers, so benign reformatting does not break the guard.
"""

from __future__ import annotations

import re
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
SAGA_ROOT = REPO_ROOT / "plugins" / "saga"
OPERATOR_CHOICE = SAGA_ROOT / "references" / "operator-choice.md"

# Offer surfaces that must each name BOTH §3.2 purposes (R5).
OFFER_SURFACES = {
    "plan": SAGA_ROOT / "skills" / "plan" / "SKILL.md",
    "code-review": SAGA_ROOT / "skills" / "code-review" / "SKILL.md",
}

# The two §3.2 purposes, each identified by a stable bold marker and a set of
# defining keywords. The marker proves the purpose is NAMED; the keywords prove it
# carries its semantics, not just a label. Surfaces must be a SUPERSET of this set.
CANONICAL_PURPOSES = {
    "breadth": {
        "marker": "breadth",
        "keywords": ["fan-out", "target"],
    },
    "adversarial-confidence": {
        "marker": "adversarial confidence",
        "keywords": ["judge panel", "confidence"],
    },
}


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def _section_3_2(text: str) -> str:
    """Slice §3.2 from operator-choice.md, anchored on its heading markers."""
    start = re.search(r"^###\s*3\.2\b.*$", text, re.MULTILINE)
    assert start is not None, "operator-choice.md §3.2 heading not found"
    after = text[start.end() :]
    nxt = re.search(r"^###\s", after, re.MULTILINE)
    return after[: nxt.start()] if nxt else after


def test_operator_choice_3_2_names_both_purposes() -> None:
    """Sanity-anchor the source of truth: §3.2 itself names both purposes."""
    section = _section_3_2(_read(OPERATOR_CHOICE)).lower()
    for key, spec in CANONICAL_PURPOSES.items():
        assert spec["marker"] in section, f"§3.2 lost the '{key}' purpose marker"


def test_every_offer_surface_is_superset_of_3_2_purposes() -> None:
    """R5: each offer surface names BOTH §3.2 purposes with their defining keywords."""
    for name, path in OFFER_SURFACES.items():
        body = _read(path).lower()
        for key, spec in CANONICAL_PURPOSES.items():
            assert spec["marker"] in body, (
                f"{name} offer dropped the §3.2 '{key}' purpose (marker {spec['marker']!r} absent)"
            )
            for kw in spec["keywords"]:
                assert kw in body, (
                    f"{name} offer names '{key}' but is missing its defining "
                    f"keyword {kw!r} — purpose underspecified vs §3.2"
                )


def test_every_offer_frames_fork_on_governance_not_review_depth() -> None:
    """R6: the team<->workflow fork is framed on GOVERNANCE (does the verdict stick?),
    not on "review depth" (which both backends have)."""
    for name, path in OFFER_SURFACES.items():
        body = _read(path).lower()
        assert "governance" in body, (
            f"{name} offer does not frame the team<->workflow fork on the governance axis (R6)"
        )
        # The fork must be posed as the verdict-persistence question, not depth.
        assert any(
            phrase in body
            for phrase in ("verdict need to stick", "blocks a merge", "block a merge")
        ), (
            f"{name} offer does not name the 'does the verdict need to stick' "
            f"governance question (R6)"
        )


def test_no_offer_undersells_workflows_as_fan_out_only() -> None:
    """Regression: the pre-rewrite prose sold dynamic workflows as fan-out ONLY.
    If a surface names breadth/fan-out it must also name adversarial confidence."""
    for name, path in OFFER_SURFACES.items():
        body = _read(path).lower()
        names_breadth = "fan-out" in body
        names_confidence = "adversarial confidence" in body
        if names_breadth:
            assert names_confidence, (
                f"{name} offer names fan-out but not adversarial confidence — "
                f"undersells dynamic workflows as fan-out only (R5 regression)"
            )
