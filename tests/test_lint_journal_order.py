"""Tests for the engineering-journal ordering lint (#659).

The lint exists because both journals had silently drifted ~10% of their content below the
oldest date heading. Two classes of check, tested in both directions — a clean file must pass,
and each specific drift shape must be caught by name.
"""

from __future__ import annotations

import importlib.util
import subprocess
import sys
from pathlib import Path
from types import ModuleType

import pytest

REPO = Path(__file__).resolve().parent.parent
SCRIPT = REPO / "scripts" / "lint_journal_order.py"

LEARNINGS = "docs/engineering-journal/LEARNINGS.md"
DECISIONS = "docs/engineering-journal/DECISIONS.md"

CLEAN = """# Learnings

## 2026-07-27

### Newest thing  {#newest}

body

## 2026-07-20

### Older thing  {#older}

body
"""


@pytest.fixture(scope="module")
def lint() -> ModuleType:
    spec = importlib.util.spec_from_file_location("lint_journal_order", SCRIPT)
    assert spec and spec.loader
    mod = importlib.util.module_from_spec(spec)
    sys.modules["lint_journal_order"] = mod
    spec.loader.exec_module(mod)
    return mod


def _journal(root: Path, rel: str, text: str) -> Path:
    path = root / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")
    return path


# --- structural checks -------------------------------------------------------


def test_clean_journal_passes(lint: ModuleType) -> None:
    assert lint.check_structure(LEARNINGS, CLEAN) == []


def test_ascending_headings_are_caught(lint: ModuleType) -> None:
    text = CLEAN.replace("## 2026-07-20", "## 2026-07-28")
    problems = lint.check_structure(LEARNINGS, text)
    assert any("newest-first" in p for p in problems), problems


def test_duplicate_date_heading_is_caught(lint: ModuleType) -> None:
    text = CLEAN.replace("## 2026-07-20", "## 2026-07-27")
    problems = lint.check_structure(LEARNINGS, text)
    assert any("duplicate" in p and "merge the two sections" in p for p in problems), problems


def test_entry_written_at_h2_is_caught(lint: ModuleType) -> None:
    """The exact shape found in DECISIONS.md: an entry authored as `##` with an anchor."""
    text = CLEAN + "\n## A decision written at the wrong level {#wrong-level}\n\nbody\n"
    problems = lint.check_structure(DECISIONS, text)
    assert any("entries are `###`" in p for p in problems), problems


def test_bare_h2_without_an_anchor_is_not_flagged(lint: ModuleType) -> None:
    """A prose section heading is legitimate — only anchored entries are mis-levelled."""
    text = CLEAN + "\n## Appendix\n\nsome prose\n"
    assert not any("entries are `###`" in p for p in lint.check_structure(DECISIONS, text))


def test_entry_above_the_first_date_heading_is_caught(lint: ModuleType) -> None:
    text = "# Learnings\n\n### Orphan  {#orphan}\n\nbody\n\n## 2026-07-27\n\n### A  {#a}\n\nb\n"
    problems = lint.check_structure(LEARNINGS, text)
    assert any("above the first date heading" in p for p in problems), problems


def test_file_with_no_date_headings_is_reported(lint: ModuleType) -> None:
    problems = lint.check_structure(LEARNINGS, "# Learnings\n\nprose only\n")
    assert any("no `## YYYY-MM-DD` headings" in p for p in problems), problems


# --- the real fleet journals must stay clean ---------------------------------


def test_committed_journals_pass_the_structural_lint(lint: ModuleType) -> None:
    """Regression sentinel: this repo's own journals were the thing that drifted (#659)."""
    for rel in (LEARNINGS, DECISIONS):
        text = (REPO / rel).read_text(encoding="utf-8")
        assert lint.check_structure(rel, text) == [], rel


# --- diff-scoped check -------------------------------------------------------


def _git(root: Path, *args: str) -> None:
    subprocess.run(["git", *args], cwd=root, check=True, capture_output=True)


@pytest.fixture
def repo(tmp_path: Path) -> Path:
    _git(tmp_path, "init", "-q", "-b", "main")
    _git(tmp_path, "config", "user.email", "t@example.com")
    _git(tmp_path, "config", "user.name", "t")
    _journal(tmp_path, LEARNINGS, CLEAN)
    _git(tmp_path, "add", "-A")
    _git(tmp_path, "commit", "-qm", "base")
    return tmp_path


def test_new_entry_in_the_newest_section_passes(lint: ModuleType, repo: Path) -> None:
    base = subprocess.run(
        ["git", "rev-parse", "HEAD"], cwd=repo, capture_output=True, text=True, check=True
    ).stdout.strip()
    text = CLEAN.replace(
        "### Newest thing  {#newest}",
        "### Fresh entry  {#fresh}\n\nbody\n\n### Newest thing  {#newest}",
    )
    _journal(repo, LEARNINGS, text)
    _git(repo, "commit", "-qam", "add entry on top")
    assert lint.check_new_entries(LEARNINGS, text, base, repo) == []


def test_new_entry_appended_at_the_bottom_is_caught(lint: ModuleType, repo: Path) -> None:
    """The #659 drift itself: a new entry tacked onto the end, under a stale heading."""
    base = subprocess.run(
        ["git", "rev-parse", "HEAD"], cwd=repo, capture_output=True, text=True, check=True
    ).stdout.strip()
    text = CLEAN + "\n### Appended at the end  {#appended}\n\nbody\n"
    _journal(repo, LEARNINGS, text)
    _git(repo, "commit", "-qam", "append at bottom")
    problems = lint.check_new_entries(LEARNINGS, text, base, repo)
    assert any("outside the newest section" in p for p in problems), problems
    assert any("do not append at the end of the file" in p for p in problems), problems


def test_relocating_an_existing_entry_is_not_an_addition(lint: ModuleType, repo: Path) -> None:
    """Re-filing a misplaced entry is the FIX, not a violation.

    A raw diff shows every moved entry as a deletion plus an addition, so a line-based check
    flagged #659's own migration as ~192 misfilings. Identity must survive relocation.
    """
    base = subprocess.run(
        ["git", "rev-parse", "HEAD"], cwd=repo, capture_output=True, text=True, check=True
    ).stdout.strip()
    # Move "Older thing" out of the 07-20 section and into 07-27, changing nothing else.
    text = """# Learnings

## 2026-07-27

### Newest thing  {#newest}

body

### Older thing  {#older}

body

## 2026-07-20
"""
    _journal(repo, LEARNINGS, text)
    _git(repo, "commit", "-qam", "re-file an entry")
    assert lint.check_new_entries(LEARNINGS, text, base, repo) == []


def test_relevelling_an_entry_is_not_an_addition(lint: ModuleType, repo: Path) -> None:
    """`## Title {#slug}` -> `### Title {#slug}` is a repair; the anchor keeps its identity."""
    base_text = CLEAN + "\n## Wrongly levelled  {#wrong}\n\nbody\n"
    _journal(repo, LEARNINGS, base_text)
    _git(repo, "commit", "-qam", "entry at the wrong level")
    base = subprocess.run(
        ["git", "rev-parse", "HEAD"], cwd=repo, capture_output=True, text=True, check=True
    ).stdout.strip()

    fixed = CLEAN.replace(
        "### Newest thing  {#newest}",
        "### Wrongly levelled  {#wrong}\n\nbody\n\n### Newest thing  {#newest}",
    )
    _journal(repo, LEARNINGS, fixed)
    _git(repo, "commit", "-qam", "demote to entry level")
    assert lint.check_new_entries(LEARNINGS, fixed, base, repo) == []


def test_a_genuinely_new_slug_at_the_bottom_is_still_caught(lint: ModuleType, repo: Path) -> None:
    """The move/re-level exemptions must not blunt the check they are carved out of."""
    base = subprocess.run(
        ["git", "rev-parse", "HEAD"], cwd=repo, capture_output=True, text=True, check=True
    ).stdout.strip()
    text = CLEAN + "\n### Brand new  {#brand-new}\n\nbody\n"
    _journal(repo, LEARNINGS, text)
    _git(repo, "commit", "-qam", "new entry at the bottom")
    problems = lint.check_new_entries(LEARNINGS, text, base, repo)
    assert any("outside the newest section" in p for p in problems), problems


def test_untouched_journal_produces_no_diff_findings(lint: ModuleType, repo: Path) -> None:
    base = subprocess.run(
        ["git", "rev-parse", "HEAD"], cwd=repo, capture_output=True, text=True, check=True
    ).stdout.strip()
    assert lint.check_new_entries(LEARNINGS, CLEAN, base, repo) == []


# --- CLI ---------------------------------------------------------------------


def test_cli_exits_zero_on_the_real_repo(lint: ModuleType) -> None:
    assert lint.main(["--root", str(REPO)]) == 0


def test_cli_exits_nonzero_on_a_broken_journal(lint: ModuleType, tmp_path: Path) -> None:
    _journal(tmp_path, LEARNINGS, CLEAN.replace("## 2026-07-20", "## 2026-07-28"))
    assert lint.main([LEARNINGS, "--root", str(tmp_path)]) == 1


def test_missing_journal_is_not_a_violation(lint: ModuleType, tmp_path: Path) -> None:
    """Most plugins carry no journal; absence is not drift."""
    assert lint.main([LEARNINGS, "--root", str(tmp_path)]) == 0
