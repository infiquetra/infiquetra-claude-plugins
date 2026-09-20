"""U3 #930 — maintenance sweep prose contracts.

Pins that Work's post-merge ceremony names all five calls. The /loop claim and the
artifact-pointer path cases retired with the surfaces they guarded: issue #1030 removed the /loop
skill and archived the team-execution plugin that owned the pointer script.

The six stale sentences in #930 were re-resolved at preflight: three were
located and repaired (teardown, first-time move, artifact_pointer path, and
the Phase-4.4 gated/allowlist conflation plus the orphaned skip-silently line)
and three remain unlocated after a repository-wide search — the stale /qa
preamble, the stale certificate comment, and the command stub. The latter are
recorded as explicit non-findings in the work-session and the pull request
description rather than silent non-fixes, per OQ3. This test pins the four
provable prose contracts; the residue is documented as non-findings, not
closed on silent.
"""

from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
WORK_SKILL = ROOT / "plugins" / "saga" / "skills" / "work" / "SKILL.md"


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def test_section_54_carries_no_ship_ceremony_transition_and_keeps_the_confirmation() -> None:
    """The ceremony went; the confirmation stayed. Both halves, or the removal was wrong.

    This replaces the test that derived the five post-merge calls from the ship ceremony's own
    ``TRANSITIONS`` tuple and asserted each appeared in section 5.4. That module was deleted in
    issue #1027, so the derivation has no source any more -- but the property worth keeping is the
    other one it implied: section 5.4 is where the outward mutations are described, and every one
    of them must still be explicitly confirmed. Issue #1029 declared that as the preservation
    contract, and a removal that quietly took the confirmation with the ceremony would look
    identical in the diff to one that did not.
    """
    text = _read(WORK_SKILL)
    sec_start = text.find("### 5.4")
    sec_end = text.find("### 5.5", sec_start)
    assert sec_start >= 0 and sec_end >= 0
    sec = text[sec_start:sec_end]

    # The mechanism is gone: no ceremony, no transition names, no reversibility tier.
    assert "ship_ceremony" not in sec
    for transition in ("checkout_main", "branch_delete", "CeremonyTier"):
        assert transition not in sec, (
            f"section 5.4 still names the ceremony transition {transition!r}"
        )

    # The confirmation is not gone.
    collapsed = " ".join(sec.split())
    assert "explicitly confirmed" in collapsed, (
        "section 5.4 must still say the pull-request open, review request and merge are "
        "explicitly confirmed -- issue #1029's preservation contract"
    )


def test_phase44_gated_and_allowlist_are_not_conflated() -> None:
    # Phase 4.4 must distinguish gated (certificate) from allowlist (halt).
    text = _read(WORK_SKILL)
    sec_start = text.find("### 4.4")
    sec_end = text.find("## Phase 5", sec_start)
    assert sec_start >= 0 and sec_end >= 0
    sec = text[sec_start:sec_end]
    # Each of these had a dead disjunct: `"halt" in sec.lower()` subsumes both quoted forms and is
    # true of almost any prose about this controller, and `"certificate" in sec.lower()` subsumes
    # the module name beside it. A disjunction is only as strong as its weakest operand, so both
    # assertions were passing on the loosest possible reading of the section.
    assert '"halt"' in sec, 'the halt status must appear as the literal record value "halt"'
    assert "certificate" in sec.lower(), "gated must be described as a certificate verdict"
    # The old conflated sentence "gated.*allowlist returns" with gated for allowlist must be gone.
    assert not re.search(r'"gated".*allowlist returns', sec, flags=re.DOTALL | re.IGNORECASE)


def test_the_gated_and_halt_distinction_is_stated_not_merely_mentioned() -> None:
    """Both words appearing is not the contract; saying they are different decisions is.

    A caller that treats them alike offers a retry for a certificate refusal, which reproduces the
    identical answer."""
    text = _read(WORK_SKILL)
    sec_start = text.find("### 4.4")
    sec = text[sec_start : text.find("## Phase 5", sec_start)]
    collapsed = " ".join(sec.split())
    assert re.search(
        r"`gated`\s+and\s+`halt`\s+are\s+the\s+two\s+withholding\s+outcomes\s+and\s+they\s+"
        r"are\s+\*\*not\s+the\s+same\s+decision\*\*",
        collapsed,
    ), "section 4.4 must state that gated and halt are different decisions"
    assert "neither is cleared by re-running the same call" in collapsed


def test_skip_silently_line_is_not_orphaned() -> None:
    text = _read(WORK_SKILL)
    # The old orphaned "Skip silently when there is no issue" must be replaced.
    assert "Skip silently when there is no issue" not in text
    # New wording is explicit: no board move is submitted when no issue.
    assert (
        "no board move is submitted" in text.lower() or "no lifecycle field to move" in text.lower()
    )
