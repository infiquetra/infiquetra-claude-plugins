"""Contract checks for the Verify entry (W8, SDLC issue #89, R69/R71/R70).

Work and QA are Markdown skills, so these tests read the shipped skill text directly (the
house pattern, as in ``test_work_review_contract.py``). They assert the Active/Verify
boundary that the ``verify_entry`` block of ``config/sdlc-schema.json`` in
``infiquetra-sdlc`` encodes: no pre-merge Verify write survives, and the post-merge path
names the real conditions.

Deliberate failure direction: the region assertions anchor on the ``### 5.3`` / ``### 5.4``
phase headings; if a restructure removes those anchors the helper asserts loudly rather
than passing vacuously.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

ROOT = Path(__file__).parent.parent
WORK_SKILL = ROOT / "plugins" / "saga" / "skills" / "work" / "SKILL.md"
QA_SKILL = ROOT / "plugins" / "saga" / "skills" / "qa" / "SKILL.md"


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def _region(text: str, start_heading: str, end_heading: str, source: Path) -> str:
    """Text between two level-3 phase headings, or an assertion failure naming
    the missing anchor."""
    start = text.find(start_heading)
    end = text.find(end_heading, start + len(start_heading))
    assert start >= 0, f"anchor heading missing in {source}: {start_heading!r}"
    assert end >= 0, f"anchor heading missing in {source}: {end_heading!r}"
    return text[start:end]


def _pr_ready_region() -> str:
    return _region(_read(WORK_SKILL), "### 5.3 ", "### 5.4 ", WORK_SKILL)


def _post_merge_region() -> str:
    return _region(_read(WORK_SKILL), "### 4.4 ", "## Phase 5 ", WORK_SKILL)


def _collapse(text: str) -> str:
    return " ".join(text.split())


# --- R3: the pre-merge Verify write is gone, not renamed ----------------------


def test_no_move_the_card_to_verify_heading_survives() -> None:
    text = _read(WORK_SKILL)
    assert not re.search(r"^#{2,6}\s.*Move the card to Verify\s*$", text, re.MULTILINE)


def test_no_target_state_verify_inside_the_pr_ready_region() -> None:
    # Whether the string appears at all is W7/4.4's business; only its PLACE in the
    # PR-ready region is policed here.
    assert "--target-state Verify" not in _pr_ready_region()


# --- R1/R69: the post-merge path states the real condition --------------------


def test_post_merge_region_names_merge_and_succeeded_nonprod_deployment() -> None:
    collapsed = _collapse(_post_merge_region())
    assert "**merged**" in collapsed
    assert "non-production deployment has **succeeded**" in collapsed
    assert "PR-ready" in collapsed and "never move the card to Verify" in collapsed


def test_post_merge_region_names_the_no_deployable_software_route_and_forbids_fabrication() -> None:
    collapsed = _collapse(_post_merge_region())
    assert "no deployable software" in collapsed
    assert "real form and consumption context" in collapsed
    assert "non-applicability" in collapsed and "with a reason" in collapsed
    assert "no environment or deployment record fabricated" in collapsed
    # The schema block is named as the single authority this prose only restates.
    assert "verify_entry" in collapsed
    assert "verify_entry.py" in collapsed


# --- P16/Q6: /qa is the activity Verify holds ---------------------------------


def test_qa_skill_names_the_post_merge_verify_relationship() -> None:
    collapsed = _collapse(_read(QA_SKILL))
    assert "Verify" in collapsed
    assert "merged plus a succeeded non-production deployment" in collapsed
    assert "PR-ready never moves a card to `Verify`" in collapsed
    assert "verify_entry" in collapsed