"""Tests for scripts/check_mermaid.py (#405).

Fixture tests cover the two acceptance shapes: a valid fence passes, a broken
fence fails naming file and line. The live-tree run is the third acceptance
criterion and is asserted here so `pytest -k mermaid` exercises it.
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
