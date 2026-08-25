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
from dataclasses import dataclass
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
MERMAID_DIR = REPO_ROOT / "scripts" / "mermaid"
HELPER = MERMAID_DIR / "parse.mjs"
NODE_MODULES = MERMAID_DIR / "node_modules" / "mermaid"

FENCE_OPEN = r"^ {0,3}```mermaid\b"
FENCE_CLOSE = r"^ {0,3}```\s*$"

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
        return f"{self.path}:{self.line}: {self.message}"


class PreconditionError(RuntimeError):
    """Node, the helper, or mermaid's install is missing — gate exit 3."""


def fences_in_text(rel: str, text: str) -> list[Fence]:
    """Extract mermaid fences from a Markdown document.

    Opening fences may be indented up to three spaces (CommonMark). A prose
    mention of the fence marker is not a fence. An unclosed fence is returned
    with ``unclosed=True`` rather than being sent to the parser.
    """
    open_re = re.compile(FENCE_OPEN)
    close_re = re.compile(FENCE_CLOSE)
    lines = text.splitlines()
    fences: list[Fence] = []
    i = 0
    while i < len(lines):
        if not open_re.match(lines[i]):
            i += 1
            continue
        start_line = i + 1
        i += 1
        body: list[str] = []
        closed = False
        while i < len(lines):
            if close_re.match(lines[i]):
                closed = True
                i += 1
                break
            body.append(lines[i])
            i += 1
        fences.append(Fence(path=rel, line=start_line, text="\n".join(body), unclosed=not closed))
    return fences


def tracked_md_mentioning_mermaid(root: Path) -> list[str]:
    """Tracked ``*.md`` paths that contain the mermaid fence marker.

    ``git grep`` supplies tracked-files-only semantics; extraction below
    discards prose mentions that are not actual fences.
    """
    result = subprocess.run(  # nosec B603 B607 — fixed git argv, no shell
        ["git", "grep", "-l", "-F", "```mermaid", "--", "*.md"],
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
        line = int(item.get("line", 0))
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
        fences = iter_repo_fences(root)
        failures = parse_fences(fences)
    except PreconditionError as exc:
        print(f"check_mermaid: {exc}", file=sys.stderr)
        return PRECONDITION_EXIT
    if not failures:
        print(f"check_mermaid: {len(fences)} mermaid fence(s) parsed")
        return 0
    for failure in failures:
        print(failure, file=sys.stderr)
    print(f"check_mermaid: VIOLATIONS: {len(failures)}", file=sys.stderr)
    return FAILURE_EXIT


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
