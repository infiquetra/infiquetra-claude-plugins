"""Tests for the engineering-journal ordering lint (#659) and anchor lint (#407, #838).

The ordering lint exists because both journals had silently drifted ~10% of their content below
the oldest date heading. The anchor lint exists because a duplicated slug or a dangling
``{#slug}`` / ``](#slug)`` citation corrupts the graph silently. Each class is tested in both
directions — a clean file must pass, and each specific drift shape must be caught by name.

The anchor lint validates both same-file citations (``{#slug}``, ``](#slug)``) and cross-file
Markdown fragment citations (``](FILE.md#anchor)``) across the covered journal set against
explicit heading ``{#slug}`` definitions and GitHub-generated heading anchor slugs (#838).
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


# --- anchor uniqueness and dangling refs (#407) ------------------------------


def test_clean_journal_passes_anchor_check(lint: ModuleType) -> None:
    assert lint.check_anchors([(LEARNINGS, CLEAN)]) == []


def test_duplicate_anchor_names_both_sites(lint: ModuleType) -> None:
    """Cross-file collision: the same heading slug in LEARNINGS and DECISIONS."""
    decisions = "# Decisions\n\n## 2026-07-27\n\n### Copycat  {#newest}\n\nbody\n"
    problems = lint.check_anchors([(LEARNINGS, CLEAN), (DECISIONS, decisions)])
    assert len(problems) == 1, problems
    msg = problems[0]
    assert "duplicate" in msg and "{#newest}" in msg, problems
    assert f"{LEARNINGS}:" in msg and f"{DECISIONS}:" in msg, problems
    newest_line = next(i for i, ln in enumerate(CLEAN.splitlines(), 1) if "{#newest}" in ln)
    copy_line = next(i for i, ln in enumerate(decisions.splitlines(), 1) if "{#newest}" in ln)
    assert f"{LEARNINGS}:{newest_line}" in msg, problems
    assert f"{DECISIONS}:{copy_line}" in msg, problems


def test_same_file_duplicate_anchor_names_both_sites(lint: ModuleType) -> None:
    text = CLEAN.replace("{#older}", "{#newest}")
    problems = lint.check_anchors([(LEARNINGS, text)])
    assert any("duplicate" in p and "{#newest}" in p for p in problems), problems
    lines = [i for i, ln in enumerate(text.splitlines(), 1) if "{#newest}" in ln]
    assert len(lines) == 2, lines
    msg = next(p for p in problems if "duplicate" in p)
    assert f"{LEARNINGS}:{lines[0]}" in msg and f"{LEARNINGS}:{lines[1]}" in msg, problems


def test_dangling_brace_mention_names_the_referencing_line(lint: ModuleType) -> None:
    text = CLEAN + "\nSee `{#ghost}`.\n"
    n = next(i for i, ln in enumerate(text.splitlines(), 1) if "{#ghost}" in ln)
    problems = lint.check_anchors([(LEARNINGS, text)])
    assert any(
        f"{LEARNINGS}:{n}:" in p and "dangling" in p and "{#ghost}" in p for p in problems
    ), problems


def test_dangling_fragment_link_names_the_referencing_line(lint: ModuleType) -> None:
    text = CLEAN + "\nSee [missing](#ghost).\n"
    n = next(i for i, ln in enumerate(text.splitlines(), 1) if "](#ghost)" in ln)
    problems = lint.check_anchors([(LEARNINGS, text)])
    assert any(
        f"{LEARNINGS}:{n}:" in p and "dangling" in p and "{#ghost}" in p for p in problems
    ), problems


def test_defined_slug_satisfies_mention_and_fragment(lint: ModuleType) -> None:
    text = CLEAN + "\nSee `{#newest}` and [newest](#newest).\n"
    assert lint.check_anchors([(LEARNINGS, text)]) == []


def test_cross_file_mention_resolves_against_the_joint_set(lint: ModuleType) -> None:
    decisions = "# Decisions\n\n## 2026-07-27\n\n### A decision  {#decision}\n\nbody\n"
    learnings = CLEAN + "\nSee `{#decision}`.\n"
    assert lint.check_anchors([(LEARNINGS, learnings), (DECISIONS, decisions)]) == []


def test_fenced_template_slug_is_not_a_definition(lint: ModuleType) -> None:
    """The LEARNINGS header shows ``### title {#slug}`` inside a quoted fence; that is not live."""
    text = (
        "# Learnings\n\n"
        "> ```markdown\n"
        "> ### Short descriptive title  {#slug}\n"
        "> ```\n\n"
        "## 2026-07-27\n\n"
        "### Real entry  {#real}\n\n"
        "body\n"
    )
    assert lint.check_anchors([(LEARNINGS, text)]) == []
    # And it must not satisfy a real citation of {#slug} either — that's the placeholder.
    # (PLACEHOLDER_SLUGS already exempts it; this asserts the fence did not define it.)
    colliding = text.replace("{#real}", "{#other}") + "\n### Collision  {#slug}\n\nbody\n"
    problems = lint.check_anchors([(LEARNINGS, colliding)])
    assert not any("duplicate" in p for p in problems), problems


def test_literal_placeholder_slug_is_not_dangling(lint: ModuleType) -> None:
    text = CLEAN + "\nThe `{#slug}` HTML anchor on the entry title makes it linkable.\n"
    assert lint.check_anchors([(LEARNINGS, text)]) == []


def test_unquoted_fenced_heading_is_not_a_definition(lint: ModuleType) -> None:
    """A ``### Title {#slug}`` inside a fence is an example, not a live definition."""
    text = CLEAN + "\n```markdown\n### Example  {#example-only}\n```\n\nSee `{#example-only}`.\n"
    n = next(i for i, ln in enumerate(text.splitlines(), 1) if "See" in ln)
    problems = lint.check_anchors([(LEARNINGS, text)])
    assert any(
        f"{LEARNINGS}:{n}:" in p and "dangling" in p and "{#example-only}" in p for p in problems
    ), problems
    # Nor does it collide with a real heading of the same slug.
    colliding = CLEAN.replace("{#newest}", "{#example-only}") + (
        "\n```markdown\n### Example  {#example-only}\n```\n"
    )
    assert not any("duplicate" in p for p in lint.check_anchors([(LEARNINGS, colliding)]))


def test_unclosed_fence_is_reported_rather_than_silently_skipping(lint: ModuleType) -> None:
    """A fence never closed hides every later anchor; a silent pass would be the worst answer."""
    text = (
        "# Learnings\n\n## 2026-07-27\n\n### A  {#a}\n\n"
        "```python\nnever closed\n\n### B  {#a}\n\nSee `{#ghost}`.\n"
    )
    problems = lint.check_anchors([(LEARNINGS, text)])
    n = next(i for i, ln in enumerate(text.splitlines(), 1) if ln.startswith("```"))
    assert any(f"{LEARNINGS}:{n}:" in p and "never closed" in p for p in problems), problems


def test_a_balanced_fence_reports_no_unclosed_fence(lint: ModuleType) -> None:
    text = CLEAN + "\n```python\nx = 1\n```\n"
    assert not any("never closed" in p for p in lint.check_anchors([(LEARNINGS, text)]))


def test_cross_file_valid_fragment_explicit_and_generated(lint: ModuleType) -> None:
    decisions = (
        "# Decisions\n\n## 2026-07-27\n\n"
        "### Explicit decision  {#explicit-decision}\n\nbody\n\n"
        "### GitHub Auto Generated Heading\n\nbody\n"
    )
    learnings = (
        CLEAN + "\nSee [explicit](DECISIONS.md#explicit-decision) and "
        "[auto](DECISIONS.md#github-auto-generated-heading).\n"
    )
    assert lint.check_anchors([(LEARNINGS, learnings), (DECISIONS, decisions)]) == []


def test_cross_file_missing_anchor_reports_source_and_destination(lint: ModuleType) -> None:
    decisions = "# Decisions\n\n## 2026-07-27\n\n### Valid  {#valid}\n\nbody\n"
    learnings = CLEAN + "\nSee [broken](DECISIONS.md#missing-slug).\n"
    n = next(i for i, ln in enumerate(learnings.splitlines(), 1) if "See [broken]" in ln)
    problems = lint.check_anchors([(LEARNINGS, learnings), (DECISIONS, decisions)])
    assert problems == [
        f"{LEARNINGS}:{n}: dangling reference to `DECISIONS.md#missing-slug` — "
        f"no heading definition in {DECISIONS}"
    ]


def test_cross_file_slug_in_other_covered_file_but_missing_in_target_fails(
    lint: ModuleType,
) -> None:
    """A slug defined in one covered file (e.g. ARCHIVE.md) must fail if cited against DECISIONS.md."""
    archive_path = "docs/engineering-journal/ARCHIVE.md"
    archive = "# Archive\n\n### Arch Entry  {#arch-slug}\n\nbody\n"
    decisions = "# Decisions\n\n## 2026-07-27\n\n### Dec Entry  {#dec-slug}\n\nbody\n"
    learnings = CLEAN + "\nSee [wrong file citation](DECISIONS.md#arch-slug).\n"
    n = next(
        i for i, ln in enumerate(learnings.splitlines(), 1) if "See [wrong file citation]" in ln
    )
    problems = lint.check_anchors(
        [(LEARNINGS, learnings), (DECISIONS, decisions), (archive_path, archive)]
    )
    assert problems == [
        f"{LEARNINGS}:{n}: dangling reference to `DECISIONS.md#arch-slug` — "
        f"no heading definition in {DECISIONS}"
    ]


def test_cross_file_destination_outside_covered_set_or_missing(lint: ModuleType) -> None:
    learnings = CLEAN + "\nSee [outside](OTHER_DOC.md#some-anchor).\n"
    n = next(i for i, ln in enumerate(learnings.splitlines(), 1) if "See [outside]" in ln)
    problems = lint.check_anchors([(LEARNINGS, learnings)])
    assert problems == [
        f"{LEARNINGS}:{n}: destination `OTHER_DOC.md` is outside the covered journal set or does not exist"
    ]


def test_cross_file_non_covered_path_with_covered_basename_is_rejected(lint: ModuleType) -> None:
    """Destination resolution is strictly path-based; matching basename in another dir is rejected."""
    learnings = CLEAN + "\nSee [uncovered path](some/other/dir/DECISIONS.md#valid-target).\n"
    n = next(i for i, ln in enumerate(learnings.splitlines(), 1) if "See [uncovered path]" in ln)
    decisions = "# Decisions\n\n## 2026-07-27\n\n### Valid Target  {#valid-target}\n\nbody\n"
    problems = lint.check_anchors([(LEARNINGS, learnings), (DECISIONS, decisions)])
    assert problems == [
        f"{LEARNINGS}:{n}: destination `some/other/dir/DECISIONS.md` is outside the covered journal set or does not exist"
    ]


def test_cross_file_relative_path_navigation(lint: ModuleType) -> None:
    narrative_path = "docs/engineering-journal/narratives/custom-run.md"
    decisions = "# Decisions\n\n## 2026-07-27\n\n### Valid Target  {#valid-target}\n\nbody\n"
    narrative_text = "# Narrative\n\nSee [ref](../DECISIONS.md#valid-target).\n"
    assert lint.check_anchors([(narrative_path, narrative_text), (DECISIONS, decisions)]) == []


def test_cross_file_invalid_relative_path_fails(lint: ModuleType) -> None:
    narrative_path = "docs/engineering-journal/narratives/custom-run.md"
    decisions = "# Decisions\n\n## 2026-07-27\n\n### Valid Target  {#valid-target}\n\nbody\n"
    narrative_text = "# Narrative\n\nSee [broken relative](../../DECISIONS.md#valid-target).\n"
    n = next(
        i for i, ln in enumerate(narrative_text.splitlines(), 1) if "See [broken relative]" in ln
    )
    problems = lint.check_anchors([(narrative_path, narrative_text), (DECISIONS, decisions)])
    assert problems == [
        f"{narrative_path}:{n}: destination `../../DECISIONS.md` is outside the covered journal set or does not exist"
    ]


def test_cross_file_external_links_ignored(lint: ModuleType) -> None:
    learnings = (
        CLEAN + "\nSee [external](https://github.com/org/repo#section) and "
        "[mailto](mailto:alice@example.com#anchor).\n"
    )
    assert lint.check_anchors([(LEARNINGS, learnings)]) == []


# --- the real fleet journals must stay clean ---------------------------------


def test_committed_journals_pass_the_structural_lint(lint: ModuleType) -> None:
    """Regression sentinel: this repo's own journals were the thing that drifted (#659)."""
    for rel in (LEARNINGS, DECISIONS):
        text = (REPO / rel).read_text(encoding="utf-8")
        assert lint.check_structure(rel, text) == [], rel


def test_committed_journals_pass_the_anchor_lint(lint: ModuleType) -> None:
    """Regression sentinel: no duplicate slug, and every citation resolves (#407, #838).

    Validates both same-file citations and cross-file Markdown fragment links
    among the covered journal set.
    """
    files: list[tuple[str, str]] = []
    for rel in (*lint.DEFAULT_JOURNALS, *lint.ANCHOR_EXTRA):
        path = REPO / rel
        if path.is_file():
            files.append((rel, path.read_text(encoding="utf-8")))
    assert lint.check_anchors(files) == []


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


def test_renaming_an_existing_slug_is_not_an_addition(lint: ModuleType, repo: Path) -> None:
    """Disambiguating a duplicate slug on an old heading is not a new filing (#407)."""
    base = subprocess.run(
        ["git", "rev-parse", "HEAD"], cwd=repo, capture_output=True, text=True, check=True
    ).stdout.strip()
    text = CLEAN.replace("{#older}", "{#older-renamed}")
    _journal(repo, LEARNINGS, text)
    _git(repo, "commit", "-qam", "rename an old slug")
    assert lint.check_new_entries(LEARNINGS, text, base, repo) == []


def test_renaming_a_slug_while_the_duplicate_survives_elsewhere_is_not_an_addition(
    lint: ModuleType, repo: Path
) -> None:
    """The real #407 repair shape: one of TWO entries sharing a slug gets renamed.

    The other entry keeps the old slug, so the old slug is still present in the file. An
    exemption keyed to "the base slug vanished from the file" would miss that and read the
    renamed entry as a new filing.
    """
    base_text = CLEAN + "\n### Twin  {#dup}\n\nbody\n"
    _journal(repo, LEARNINGS, base_text.replace("{#older}", "{#dup}"))
    _git(repo, "commit", "-qam", "two entries share a slug")
    base = subprocess.run(
        ["git", "rev-parse", "HEAD"], cwd=repo, capture_output=True, text=True, check=True
    ).stdout.strip()
    text = base_text.replace("### Older thing  {#older}", "### Older thing  {#older-renamed}")
    _journal(repo, LEARNINGS, text)
    _git(repo, "commit", "-qam", "disambiguate the duplicate")
    assert lint.check_new_entries(LEARNINGS, text, base, repo) == []


def test_a_new_bottom_entry_reusing_an_existing_title_is_still_caught(
    lint: ModuleType, repo: Path
) -> None:
    """Title alone must not exempt an entry — only a title whose base slug moved off it.

    Treating the title as an unconditional identity let a brand-new anchored entry be filed
    under a stale date heading unchecked whenever its title matched any existing entry.
    """
    base = subprocess.run(
        ["git", "rev-parse", "HEAD"], cwd=repo, capture_output=True, text=True, check=True
    ).stdout.strip()
    text = CLEAN + "\n### Newest thing  {#second-newest}\n\nbody\n"
    _journal(repo, LEARNINGS, text)
    _git(repo, "commit", "-qam", "reuse a title at the bottom")
    problems = lint.check_new_entries(LEARNINGS, text, base, repo)
    assert any("outside the newest section" in p for p in problems), problems


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


def test_linting_one_journal_still_resolves_slugs_defined_in_the_others(
    lint: ModuleType,
) -> None:
    """The definition set is joint, so naming one file must not manufacture dangles.

    The anchor pass is inherently cross-file: LEARNINGS cites DECISIONS, ARCHIVE, and QUEUED
    slugs constantly. Deriving its file set from the CLI arguments turned every one of those
    honest citations into a dangling reference.
    """
    assert lint.main([LEARNINGS, "--root", str(REPO)]) == 0
