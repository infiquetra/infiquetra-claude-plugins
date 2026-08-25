#!/usr/bin/env python3
"""Always-on Mermaid syntax check for tracked Markdown (#405).

Enumerates ```` ```mermaid ```` fences in tracked ``*.md`` files via ``git grep``
(so untracked and ignored files stay out), then validates each fence through
mermaid's own parser running headless in Node (``scripts/mermaid/parse.mjs``).
A syntax error names file and line and fails the check.

Exit codes match ``scripts/gate.sh``: 0 clean, 1 syntax failures, 3 missing
Node/npm/helper (the existing missing-dev-dependency precondition).
"""

from __future__ import annotations

import argparse
import json
import re
import shutil
import subprocess  # nosec B404 — git and node CLIs only, fixed argv, no shell
import sys
from collections.abc import Sequence
from dataclasses import dataclass, field
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
MERMAID_DIR = REPO_ROOT / "scripts" / "mermaid"
HELPER = MERMAID_DIR / "parse.mjs"
NODE_MODULES = MERMAID_DIR / "node_modules" / "mermaid"

# A fence line: optional indent, three-or-more backticks or tildes, then an info
# string. Backticks are excluded from the info string per CommonMark, which is
# also what keeps a prose mention such as ```mermaid``` from opening a fence.
FENCE_LINE = re.compile(r"^(?P<indent>[ \t]*)(?P<marker>`{3,}|~{3,})[ \t]*(?P<info>[^`]*?)[ \t]*$")
# ```mermaid, optionally carrying renderer attributes. Not ```mermaidjs, not
# ```mermaid-foo — those are different languages and must not reach the parser.
MERMAID_INFO = re.compile(r"^mermaid(?:[ \t{].*)?$")

PRECONDITION_EXIT = 3
FAILURE_EXIT = 1


@dataclass(frozen=True)
class Fence:
    path: str
    line: int
    text: str
    unclosed: bool = False


@dataclass(frozen=True)
class Failure:
    path: str
    line: int
    message: str

    def __str__(self) -> str:
        # One line per failure: mermaid's own error text is multi-line, and a
        # newline here would break the file:line: convention editors and CI
        # annotations parse.
        return f"{self.path}:{self.line}: {' '.join(self.message.split())}"


class PreconditionError(RuntimeError):
    """Node, the helper, or mermaid's install is missing — gate exit 3."""


@dataclass
class _OpenFence:
    """A fence being scanned. Tracked for every info string, not just mermaid."""

    indent: str
    char: str
    length: int
    info: str
    start: int
    body: list[str] = field(default_factory=list)

    @property
    def is_mermaid(self) -> bool:
        return bool(MERMAID_INFO.match(self.info))

    def dedented(self) -> str:
        """Body with the opener's own indent removed, per CommonMark."""
        width = len(self.indent)
        return "\n".join(line[width:] if line[:width].isspace() else line for line in self.body)


def fences_in_text(rel: str, text: str) -> list[Fence]:
    """Extract mermaid fences from a Markdown document.

    Every fence is tracked, not only mermaid ones, so a ```mermaid block nested
    inside a wider ````markdown block is body text rather than a fence of its
    own. Closers follow CommonMark: same character, at least as long as the
    opener. Tilde fences, four-or-more-backtick fences, and fences indented
    inside a list item all count — each of them renders on GitHub, so a broken
    diagram written that way must not slip past. An unclosed fence is returned
    with ``unclosed=True`` rather than being sent to the parser.
    """
    fences: list[Fence] = []
    open_fence: _OpenFence | None = None
    for lineno, line in enumerate(text.splitlines(), 1):
        match = FENCE_LINE.match(line)
        if open_fence is None:
            if match:
                marker = match.group("marker")
                open_fence = _OpenFence(
                    indent=match.group("indent"),
                    char=marker[0],
                    length=len(marker),
                    info=match.group("info").strip(),
                    start=lineno,
                )
            continue
        closes = (
            match is not None
            and not match.group("info")
            and match.group("marker")[0] == open_fence.char
            and len(match.group("marker")) >= open_fence.length
        )
        if closes:
            if open_fence.is_mermaid:
                fences.append(Fence(path=rel, line=open_fence.start, text=open_fence.dedented()))
            open_fence = None
            continue
        open_fence.body.append(line)
    if open_fence is not None and open_fence.is_mermaid:
        fences.append(
            Fence(path=rel, line=open_fence.start, text=open_fence.dedented(), unclosed=True)
        )
    return fences


def tracked_md_mentioning_mermaid(root: Path) -> list[str]:
    """Tracked ``*.md`` paths that contain the mermaid fence marker.

    ``git grep`` supplies tracked-files-only semantics; extraction below
    discards prose mentions that are not actual fences.
    """
    result = subprocess.run(  # nosec B603 B607 — fixed git argv, no shell
        ["git", "grep", "-l", "-E", "```+mermaid|~~~+mermaid", "--", "*.md"],
        cwd=root,
        capture_output=True,
        text=True,
        check=False,
    )
    if result.returncode not in (0, 1):
        raise PreconditionError(
            f"git grep failed ({result.returncode}): {result.stderr.strip() or result.stdout.strip()}"
        )
    return [line for line in result.stdout.splitlines() if line]


def iter_repo_fences(root: Path) -> list[Fence]:
    fences: list[Fence] = []
    for rel in tracked_md_mentioning_mermaid(root):
        path = root / rel
        if not path.is_file():
            continue
        fences.extend(fences_in_text(rel, path.read_text(encoding="utf-8")))
    return fences


def _require_parser() -> str:
    node = shutil.which("node")
    if node is None:
        raise PreconditionError(
            "node is not on PATH; install Node.js 22+ (CI uses actions/setup-node node-version 22)"
        )
    if not HELPER.is_file():
        raise PreconditionError(f"mermaid helper missing: {HELPER}")
    if not NODE_MODULES.is_dir():
        raise PreconditionError(
            "mermaid parser is not installed; run: npm ci --prefix scripts/mermaid"
        )
    return node


def parse_fences(fences: Sequence[Fence], *, node: str | None = None) -> list[Failure]:
    """Parse fence bodies through mermaid.parse(). Unclosed fences fail locally."""
    failures: list[Failure] = []
    to_parse: list[Fence] = []
    for fence in fences:
        if fence.unclosed:
            failures.append(Failure(fence.path, fence.line, "unclosed mermaid fence"))
        else:
            to_parse.append(fence)
    if not to_parse:
        return failures

    node_bin = node or _require_parser()
    payload = [{"path": f.path, "line": f.line, "text": f.text} for f in to_parse]
    result = subprocess.run(  # nosec B603 — node executable + fixed helper path
        [node_bin, str(HELPER)],
        input=json.dumps(payload),
        capture_output=True,
        text=True,
        check=False,
        cwd=MERMAID_DIR,
    )
    if result.returncode != 0:
        detail = (result.stderr or result.stdout).strip() or f"exit {result.returncode}"
        raise PreconditionError(
            "headless mermaid.parse() is not usable in this environment "
            f"(no mermaid-cli fallback): {detail}"
        )
    try:
        parsed = json.loads(result.stdout or "[]")
    except json.JSONDecodeError as exc:
        raise PreconditionError(
            f"mermaid helper wrote non-JSON stdout: {exc}; stdout={result.stdout!r}"
        ) from exc
    if not isinstance(parsed, list):
        raise PreconditionError("mermaid helper stdout must be a JSON array")
    for item in parsed:
        if not isinstance(item, dict):
            continue
        path = str(item.get("path", ""))
        try:
            line = int(item.get("line", 0))
        except (TypeError, ValueError):
            line = 0
        message = str(item.get("message", "parse failed"))
        failures.append(Failure(path, line, f"mermaid parse failed: {message}"))
    return failures


def check_repo(root: Path = REPO_ROOT) -> list[Failure]:
    return parse_fences(iter_repo_fences(root))


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--root",
        type=Path,
        default=REPO_ROOT,
        help="repository root (default: this checkout)",
    )
    args = parser.parse_args(argv)
    root = args.root.resolve()
    try:
        # Prove the parser is reachable before counting, so an empty population
        # can never report success on a toolchain that would have failed. A
        # green line that verified nothing is the failure mode this check exists
        # to prevent (see scripts/gate.sh's own coverage self-check).
        _require_parser()
        files = tracked_md_mentioning_mermaid(root)
        fences = iter_repo_fences(root)
        if files and not fences:
            raise PreconditionError(
                f"{len(files)} tracked file(s) match the mermaid fence marker but no fence was "
                "extracted — enumeration and extraction disagree, so this run verified nothing"
            )
        failures = parse_fences(fences)
    except PreconditionError as exc:
        print(f"check_mermaid: {exc}", file=sys.stderr)
        return PRECONDITION_EXIT
    if not failures:
        print(f"check_mermaid: {len(fences)} mermaid fence(s) parsed across {len(files)} file(s)")
        return 0
    for failure in failures:
        print(failure, file=sys.stderr)
    print(f"check_mermaid: VIOLATIONS: {len(failures)}", file=sys.stderr)
    return FAILURE_EXIT


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
