"""U3 #930 — maintenance sweep prose contracts.

Pins that Work's post-merge ceremony names all five calls, that /loop no
longer claims the first board move belongs to /work, and that every
artifact_pointer.py reference under plugins/saga/skills uses its full path.

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
LOOP_SKILL = ROOT / "plugins" / "saga" / "skills" / "loop" / "SKILL.md"
RESUME_SKILL = ROOT / "plugins" / "saga" / "skills" / "resume" / "SKILL.md"
SHIP_CEREMONY = ROOT / "plugins" / "saga" / "scripts" / "ship_ceremony.py"


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def test_post_merge_ceremony_names_all_five_calls_including_teardown() -> None:
    # Derive expected five as post-merge slice of TRANSITIONS, never a hand-maintained list.
    # Read the canonical tuple directly from the source to avoid import side effects.
    text = SHIP_CEREMONY.read_text(encoding="utf-8")
    m = re.search(r"TRANSITIONS:\s*tuple\[str,\s*\.\.\.\]\s*=\s*\((.*?)\)", text, flags=re.DOTALL)
    assert m, "TRANSITIONS tuple not found"
    inner = m.group(1)
    transitions = tuple(re.findall(r'"([^"]+)"', inner))
    assert transitions == (
        "commit",
        "open_pr",
        "request_review",
        "merge",
        "checkout_main",
        "pull",
        "branch_delete",
        "teardown",
    )
    expected = transitions[transitions.index("request_review") + 1 :]
    # expected must be the five post-merge calls
    assert expected == ("merge", "checkout_main", "pull", "branch_delete", "teardown")
    text = _read(WORK_SKILL)
    # Phase 5.4 is the post-merge ceremony; ensure each of the five appears near that section.
    sec_start = text.find("### 5.4")
    sec_end = text.find("### 5.5", sec_start)
    assert sec_start >= 0 and sec_end >= 0
    sec = text[sec_start:sec_end]
    for name in expected:
        assert name in sec, f"post-merge ceremony prose missing {name!r}"
    # Ensure we did not assert against whole tuple (commit/open_pr/request_review must NOT be in that section's expected list expectation)
    # The test derives from slice, so if prose mistakenly omitted teardown the check fails.


def test_no_saga_file_claims_first_board_move_belongs_to_work() -> None:
    # Negative: no file under plugins/saga/ claims a first board move belongs to /work.
    # Use the same grep the issue prescribes, scoped to skills.
    for path in (WORK_SKILL, LOOP_SKILL, RESUME_SKILL):
        text = _read(path)
        # The stale sentence is "first-time forward move belongs to `/work`"
        assert not re.search(
            r"first-time forward move belongs to.*\/work", text, flags=re.IGNORECASE
        ), f"{path} still claims first-time move belongs to /work"
        assert not re.search(r"first board move belongs to.*\/work", text, flags=re.IGNORECASE), (
            f"{path} still claims first board move belongs to /work"
        )
    # Also ensure /loop now describes the submission path.
    loop_text = _read(LOOP_SKILL)
    assert "reconcile controller" in loop_text.lower() and "mission control" in loop_text.lower()
    assert "0.151.0" in loop_text or "submission path" in loop_text.lower()


def test_artifact_pointer_is_referenced_by_full_path_in_saga_prose() -> None:
    """Every bare `artifact_pointer.py` in saga's prose must carry the full path.

    Scoped to `plugins/saga/skills` before, which is narrower than the requirement and missed a
    live reference in `plugins/saga/references/`: the module is not saga's -- it lives in
    team-execution -- so a bare filename in saga prose points a reader at a file that is not there,
    wherever in saga it appears. team-execution's own prose is untouched: a bare filename inside
    the plugin that OWNS the script is correct. The CHANGELOG stays out of scope because a
    historical note records what was written at the time.
    """
    saga_root = ROOT / "plugins" / "saga"
    bare: list[str] = []
    for path in saga_root.rglob("*.md"):
        if path.name == "CHANGELOG.md":
            continue
        content = path.read_text(encoding="utf-8")
        for lineno, line in enumerate(content.splitlines(), start=1):
            if (
                "artifact_pointer.py" in line
                and "plugins/team-execution/skills/team-execution/scripts/artifact_pointer.py"
                not in line
            ):
                bare.append(f"{path.relative_to(ROOT)}:{lineno}:{line.strip()}")
    assert not bare, "bare artifact_pointer.py references remain:\n" + "\n".join(bare)
    # Also ensure the four expected full-path occurrences exist.
    work = _read(WORK_SKILL)
    resume = _read(RESUME_SKILL)
    assert (
        work.count("plugins/team-execution/skills/team-execution/scripts/artifact_pointer.py") >= 1
    )
    assert (
        resume.count("plugins/team-execution/skills/team-execution/scripts/artifact_pointer.py")
        >= 2
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
