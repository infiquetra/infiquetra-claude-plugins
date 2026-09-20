"""`team_emitter.py` and `spec_table.py` are gone, and nothing still reaches for them.

Issue 1026 unit U8. The guard is named for what it guards, and it checks the two module names in
**every syntax a caller could use**: a file that exists, an import statement, a
``spec_from_file_location`` by path, and a bare mention in a skill's command line. A removal test
that only checks ``not path.exists()`` passes while a skill still tells an agent to run the script.
"""

from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).parent.parent
SAGA_SCRIPTS = ROOT / "plugins" / "saga" / "scripts"

REMOVED_MODULES = ("team_emitter", "spec_table")
REMOVED_FILES = tuple(SAGA_SCRIPTS / f"{name}.py" for name in REMOVED_MODULES)
REMOVED_TESTS = tuple(ROOT / "tests" / f"test_{name}.py" for name in REMOVED_MODULES)

#: Directories a surviving reference would matter in. Journals and changelogs record history and
#: are expected to name a module that was removed, so they are out of scope by design.
SCANNED_ROOTS = (ROOT / "plugins", ROOT / "tests", ROOT / "scripts", ROOT / "tools")
HISTORY_FILES = ("CHANGELOG.md",)
HISTORY_DIRS = ("engineering-journal", "docs/plans", "docs/reviews")


def test_the_two_modules_no_longer_exist() -> None:
    for path in REMOVED_FILES:
        assert not path.exists(), f"{path.relative_to(ROOT)} came back"


def test_the_tests_that_existed_only_to_test_them_are_gone_too() -> None:
    for path in REMOVED_TESTS:
        assert not path.exists(), (
            f"{path.relative_to(ROOT)} survives its subject; a test of a deleted module either "
            "fails or asserts nothing"
        )


def _actionable_patterns(name: str) -> tuple[re.Pattern[str], ...]:
    """The syntaxes in which naming the module would actually reach for it.

    A mention in prose or a comment -- "issue 1026 removed team_emitter.py" -- names the module
    without reaching for it, and forbidding that would forbid explaining the removal. What is
    forbidden is a form something follows: an import, a load by module name, a path expression in
    code, or a command line in a skill.
    """
    return (
        re.compile(rf"^\s*(?:from|import)\s+{name}\b", re.MULTILINE),  # import statement
        re.compile(rf"spec_from_file_location\(\s*[\"']{name}[\"']"),  # load by module name
        re.compile(rf"/\s*[\"']{name}\.py[\"']"),  # a path expression: dir / "name.py"
        re.compile(rf"(?:python3?|uv run)\s+\S*{name}\.py"),  # a command line
    )


def _offenders(name: str) -> list[str]:
    hits: list[str] = []
    patterns = _actionable_patterns(name)
    for root in SCANNED_ROOTS:
        if not root.exists():
            continue
        for path in root.rglob("*"):
            if not path.is_file() or path.suffix not in {".py", ".md", ".sh", ".json", ".yaml"}:
                continue
            relative = str(path.relative_to(ROOT))
            if path.name in HISTORY_FILES or any(d in relative for d in HISTORY_DIRS):
                continue
            text = path.read_text(encoding="utf-8", errors="ignore")
            for pattern in patterns:
                for match in pattern.finditer(text):
                    line = text[: match.start()].count("\n") + 1
                    hits.append(f"{relative}:{line}")
    return sorted(set(hits))


def test_no_surviving_file_reaches_for_either_module_in_any_syntax() -> None:
    """Every importer named in the plan's inventory is repaired, not left to fail at runtime."""
    for name in REMOVED_MODULES:
        offenders = [
            hit
            for hit in _offenders(name)
            # This file names both modules on purpose: it is the guard.
            if not hit.startswith("tests/test_team_emitter_and_spec_table_removed.py")
        ]
        assert offenders == [], f"{name} is still reached from: {offenders}"


def test_the_scanner_catches_every_actionable_syntax() -> None:
    """Mutation proof for the scanner itself. A scan that has never seen a positive is a scan
    that might be matching nothing at all -- the exact failure this file is written against."""
    for name in REMOVED_MODULES:
        patterns = _actionable_patterns(name)
        for syntax in (
            f"import {name}\n",
            f"from {name} import emit\n",
            f'spec_from_file_location("{name}", path)\n',
            f'SCRIPTS / "{name}.py"\n',
            f"python3 plugins/saga/scripts/{name}.py <spec>\n",
            f"uv run plugins/saga/scripts/{name}.py <spec>\n",
        ):
            assert any(p.search(syntax) for p in patterns), (
                f"the scanner would miss a {name} reference written as {syntax!r}"
            )


def test_the_scanner_does_not_fire_on_a_historical_mention() -> None:
    """The complement: explaining the removal must stay possible, or the changelog entry and
    the comment that says why the tier fell back would both be violations."""
    for name in REMOVED_MODULES:
        patterns = _actionable_patterns(name)
        for prose in (
            f"# Issue 1026 removed ``{name}.py``: the tier falls back to the inline baseline.\n",
            f"Saga no longer ships {name}.py.\n",
        ):
            assert not any(p.search(prose) for p in patterns), (
                f"the scanner fires on a historical mention: {prose!r}"
            )


def test_the_execution_spec_team_tier_falls_to_the_inline_baseline() -> None:
    """`recompile_for_tier` was the one caller of the removed structure emitter. It must emit a
    runnable artifact for the team tier, not raise and not return nothing."""
    source = (SAGA_SCRIPTS / "execution_spec.py").read_text(encoding="utf-8")
    assert "_emit_team_structure" not in source
    assert "Issue 1026 removed ``team_emitter.py``" in source
    assert "return emit_inline_baseline(spec)" in source
