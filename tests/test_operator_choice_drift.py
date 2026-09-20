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
from typing import TypedDict

REPO_ROOT = Path(__file__).resolve().parent.parent
SAGA_ROOT = REPO_ROOT / "plugins" / "saga"
OPERATOR_CHOICE = SAGA_ROOT / "references" / "operator-choice.md"

# Offer surfaces that must each name BOTH §3.2 purposes (R5).
#
# Issue 1026 moved /plan's backend-offer section out of skills/plan/SKILL.md and into
# references/workflow-backend.md. The offer itself is unchanged, so this guard follows it to the
# file that now carries it rather than being deleted with the section: the two purposes and the
# governance framing are the contract, and where they live is not.
OFFER_SURFACES = {
    "plan": SAGA_ROOT / "references" / "workflow-backend.md",
    "code-review": SAGA_ROOT / "skills" / "code-review" / "SKILL.md",
}


class PurposeSpec(TypedDict):
    marker: str
    keywords: list[str]


# The two §3.2 purposes, each identified by a stable bold marker and a set of
# defining keywords. The marker proves the purpose is NAMED; the keywords prove it
# carries its semantics, not just a label. Surfaces must be a SUPERSET of this set.
CANONICAL_PURPOSES: dict[str, PurposeSpec] = {
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
