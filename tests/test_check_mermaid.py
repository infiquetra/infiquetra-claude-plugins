"""Tests for scripts/check_mermaid.py (#405).

Fixture tests cover the two acceptance shapes: a valid fence passes, a broken
fence fails naming file and line. The live-tree run is the third acceptance
criterion and is asserted here so `pytest -k mermaid` exercises it. The exit
codes are the whole interface to `scripts/gate.sh` and `.github/workflows/ci.yml`,
so 0, 1 and 3 each have a test of their own.
"""

from __future__ import annotations

import importlib.util
import shutil
import subprocess
import sys
from pathlib import Path
from types import ModuleType

import pytest

REPO = Path(__file__).resolve().parent.parent
SCRIPT = REPO / "scripts" / "check_mermaid.py"
MERMAID_DIR = REPO / "scripts" / "mermaid"

VALID = "flowchart TD\n  A --> B\n"
BROKEN = "flowchart TD\n  A -->\n"


@pytest.fixture(scope="module")
def check() -> ModuleType:
    spec = importlib.util.spec_from_file_location("check_mermaid", SCRIPT)
    assert spec and spec.loader
    mod = importlib.util.module_from_spec(spec)
    sys.modules["check_mermaid"] = mod
    spec.loader.exec_module(mod)
    return mod


@pytest.fixture(scope="module")
def mermaid_ready(check: ModuleType) -> None:
    """Install the pinned mermaid parser once if this checkout has Node."""
    if shutil.which("node") is None or shutil.which("npm") is None:
        pytest.fail("node and npm are required for mermaid fixture tests")
    if not (MERMAID_DIR / "node_modules" / "mermaid").is_dir():
        subprocess.run(["npm", "ci", "--prefix", str(MERMAID_DIR)], check=True)
    check._require_parser()


def test_valid_fence_passes(check: ModuleType, mermaid_ready: None) -> None:
    fences = [check.Fence(path="ok.md", line=1, text=VALID)]
    assert check.parse_fences(fences) == []


def test_broken_fence_fails_naming_file_and_line(check: ModuleType, mermaid_ready: None) -> None:
    fences = [check.Fence(path="docs/broken.md", line=7, text=BROKEN)]
    failures = check.parse_fences(fences)
    assert len(failures) == 1, failures
    rendered = str(failures[0])
    assert rendered.startswith("docs/broken.md:7:")
    assert "mermaid parse failed" in rendered


def test_prose_mention_is_not_a_fence(check: ModuleType) -> None:
    text = (
        "The seed counted `` ```mermaid `` fenced blocks in rendered text: 7 messages.\n"
        "A later sentence names ```mermaid without opening a fence.\n"
    )
    assert check.fences_in_text("notes.md", text) == []


def test_unclosed_fence_names_file_and_line(check: ModuleType, mermaid_ready: None) -> None:
    text = "intro\n```mermaid\nflowchart TD\n  A --> B\n"
    fences = check.fences_in_text("open.md", text)
    assert len(fences) == 1
    assert fences[0].unclosed
    failures = check.parse_fences(fences)
    assert [str(f) for f in failures] == ["open.md:2: unclosed mermaid fence"]


def test_git_grep_enumerates_tracked_fences_only(check: ModuleType, tmp_path: Path) -> None:
    subprocess.run(["git", "init"], cwd=tmp_path, check=True, capture_output=True)
    tracked = tmp_path / "tracked.md"
    tracked.write_text("```mermaid\nflowchart TD\n  A --> B\n```\n", encoding="utf-8")
    untracked = tmp_path / "untracked.md"
    untracked.write_text("```mermaid\nflowchart TD\n  A -->\n```\n", encoding="utf-8")
    mention = tmp_path / "mention.md"
    mention.write_text("see ```mermaid in prose\n", encoding="utf-8")
    subprocess.run(
        ["git", "add", "tracked.md", "mention.md"],
        cwd=tmp_path,
        check=True,
        capture_output=True,
    )
    fences = check.iter_repo_fences(tmp_path)
    assert [(f.path, f.line) for f in fences] == [("tracked.md", 1)]


def test_current_tree_parses(check: ModuleType, mermaid_ready: None) -> None:
    failures = check.check_repo(REPO)
    assert failures == [], [str(f) for f in failures]


def test_cli_reports_broken_fence(
    check: ModuleType, mermaid_ready: None, tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    subprocess.run(["git", "init"], cwd=tmp_path, check=True, capture_output=True)
    (tmp_path / "bad.md").write_text(
        "# title\n\n```mermaid\nflowchart TD\n  A -->\n```\n", encoding="utf-8"
    )
    subprocess.run(["git", "add", "bad.md"], cwd=tmp_path, check=True, capture_output=True)
    rc = check.main(["--root", str(tmp_path)])
    captured = capsys.readouterr()
    assert rc == 1
    assert "bad.md:3:" in captured.err
    assert "mermaid parse failed" in captured.err


# --- fence forms GitHub renders -------------------------------------------------
# Each of these renders as a diagram on GitHub. A form the scanner does not
# recognise is a broken diagram that ships undetected — the failure #405 exists
# to close — so each one is pinned.


@pytest.mark.parametrize(
    ("label", "text"),
    [
        ("three backticks", "```mermaid\nflowchart TD\n  A --> B\n```\n"),
        ("four backticks", "````mermaid\nflowchart TD\n  A --> B\n````\n"),
        ("tilde fence", "~~~mermaid\nflowchart TD\n  A --> B\n~~~\n"),
        ("indented in a list", "- item\n\n    ```mermaid\n    flowchart TD\n    ```\n"),
        ("renderer attributes", "```mermaid {theme=dark}\nflowchart TD\n  A --> B\n```\n"),
    ],
)
def test_rendered_fence_forms_are_scanned(check: ModuleType, label: str, text: str) -> None:
    fences = check.fences_in_text("t.md", text)
    assert len(fences) == 1, f"{label}: {fences}"
    assert not fences[0].unclosed, label


def test_longer_closing_fence_closes_the_block(check: ModuleType) -> None:
    """CommonMark: a closer may be longer than its opener. It is not unclosed."""
    fences = check.fences_in_text("t.md", "```mermaid\nflowchart TD\n  A --> B\n````\n")
    assert len(fences) == 1
    assert not fences[0].unclosed


def test_nested_example_fence_is_not_scanned(check: ModuleType) -> None:
    """A ```mermaid block shown inside a wider ````markdown block is body text."""
    text = "````markdown\n```mermaid\nBROKEN[[\n```\n````\n"
    assert check.fences_in_text("doc.md", text) == []


def test_other_info_strings_are_not_mermaid(check: ModuleType) -> None:
    assert check.fences_in_text("t.md", "```mermaid-foo\nnot a diagram\n```\n") == []
    assert check.fences_in_text("t.md", "```python\nprint(1)\n```\n") == []


# --- exit-code contract ---------------------------------------------------------


def test_main_exits_zero_on_a_clean_tree(
    check: ModuleType, mermaid_ready: None, tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    subprocess.run(["git", "init"], cwd=tmp_path, check=True, capture_output=True)
    (tmp_path / "ok.md").write_text(f"```mermaid\n{VALID}```\n", encoding="utf-8")
    subprocess.run(["git", "add", "ok.md"], cwd=tmp_path, check=True, capture_output=True)
    assert check.main(["--root", str(tmp_path)]) == 0
    assert "1 mermaid fence(s) parsed" in capsys.readouterr().out


def test_main_exits_three_when_node_is_absent(
    check: ModuleType, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.setattr(check.shutil, "which", lambda _name: None)
    assert check.main([]) == check.PRECONDITION_EXIT
    assert "node is not on PATH" in capsys.readouterr().err


def test_require_parser_reports_a_missing_install(
    check: ModuleType, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.setattr(check, "NODE_MODULES", tmp_path / "absent")
    with pytest.raises(check.PreconditionError, match="npm ci --prefix"):
        check._require_parser()


def test_main_exits_three_when_extraction_finds_nothing(
    check: ModuleType,
    mermaid_ready: None,
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """Files matched but no fence extracted means the run verified nothing."""
    monkeypatch.setattr(check, "tracked_md_mentioning_mermaid", lambda _root: ["ghost.md"])
    assert check.main(["--root", str(tmp_path)]) == check.PRECONDITION_EXIT
    assert "verified nothing" in capsys.readouterr().err


def test_failure_renders_on_one_line(check: ModuleType) -> None:
    """mermaid's error text is multi-line; file:line: output must not be."""
    failure = check.Failure("d.md", 4, "mermaid parse failed: Parse error\n  ...\n  ^")
    assert "\n" not in str(failure)
    assert str(failure).startswith("d.md:4: mermaid parse failed:")
