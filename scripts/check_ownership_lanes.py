#!/usr/bin/env python3
"""Write-ownership lane lint (issue #431).

Statically scans each plugin declared in ``marketplace/ownership_lanes.json`` for direct
``gh`` invocations that cross into another plugin's owned write-mutation surface, and exits
non-zero (naming the offending file, line, and out-of-lane call) when it finds one.

Why this exists
---------------
The saga / mission-control / deploy ship-ceremony seam has a real ownership boundary:
mission-control owns the issue + board/project write surface, saga owns the PR ship ceremony,
and deploy only reads deployment/compare state. Until now that boundary was prose-only
(CLAUDE.md Development Workflow step 6 + scattered skill docs). This lint turns the
write-mutation subset of that policy into a machine-checked CI gate: a ``deploy``-lane script
shelling out to ``gh issue`` (mission-control's domain) fails the build instead of slipping
through review.

Detection model
---------------
The scan is AST-based, not a text grep, so docstrings, comments, and error-message strings
that merely *mention* ``gh pr view`` are never mistaken for real calls. For every list/tuple
literal whose first element is the string ``"gh"`` (or ``"gh <sub>"`` combined), the second
token is read as the subcommand. Dynamically built command lists (e.g. ``["gh"] + args``)
have no literal subcommand and are skipped — they cannot be statically attributed to a lane.

Two checks run per detected invocation:

1. **Subcommand lane.** If the subcommand is in ``sensitive_subcommands`` and is not in the
   invoking plugin's ``allowed_gh_subcommands``, that is a cross-lane violation.
2. **Reserved ``gh api`` path.** ``gh api`` is a catch-all every GitHub-touching plugin uses,
   so subcommand-level allow-listing alone is toothless for it. Any ``gh api`` invocation
   whose argument list contains a literal path token starting with a prefix in
   ``reserved_api_paths`` (e.g. ``projects/`` → mission-control) is a violation unless the
   invoking plugin is that prefix's declared owner.

Extending coverage
-------------------
Add a plugin under ``lanes`` with its ``allowed_gh_subcommands`` to bring it into the gate, or
add a prefix under ``reserved_api_paths`` to reserve a ``gh api <path>`` surface to one owner.
No lint-code change is needed for either; this module reads the manifest as its whole contract.
"""

from __future__ import annotations

import argparse
import ast
import json
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_MANIFEST = REPO_ROOT / "marketplace" / "ownership_lanes.json"
DEFAULT_PLUGINS_ROOT = REPO_ROOT / "plugins"

# Directory names (any path segment) excluded from the scan: test suites legitimately embed
# example command lists, and vendored/generated artifacts are not hand-authored plugin code.
EXCLUDED_DIR_SEGMENTS = frozenset({"tests", "generated", "__pycache__"})


class ManifestError(Exception):
    """The ownership-lanes manifest is missing or malformed. Fail loud, never silent-pass."""


@dataclass(frozen=True)
class GhInvocation:
    """A statically detected ``gh`` command-list literal."""

    lineno: int
    subcommand: str | None
    tokens: tuple[str, ...]  # literal string tokens (incl. f-string leading prefixes)


@dataclass(frozen=True)
class Violation:
    """A single out-of-lane call, ready to be printed as a CI failure line."""

    file: Path
    lineno: int
    plugin: str
    call: str
    crossed_into: str
    reason: str

    def render(self, root: Path) -> str:
        try:
            rel: Path | str = self.file.relative_to(root)
        except ValueError:
            rel = self.file
        return (
            f"VIOLATION {rel}:{self.lineno}: {self.plugin}-lane script calls `{self.call}` — "
            f"{self.reason} (owned by: {self.crossed_into})"
        )


def load_manifest(path: Path) -> dict[str, Any]:
    """Load and structurally validate the ownership-lanes manifest.

    Raises ManifestError on a missing file, invalid JSON, or a missing required key, so a
    corrupted manifest fails the lint loudly instead of letting a cross-lane call through.
    """

    if not path.exists():
        raise ManifestError(f"ownership-lanes manifest not found: {path}")
    try:
        data = json.loads(path.read_text())
    except json.JSONDecodeError as exc:
        raise ManifestError(f"ownership-lanes manifest is not valid JSON ({path}): {exc}") from exc
    if not isinstance(data, dict):
        raise ManifestError(f"ownership-lanes manifest must be a JSON object: {path}")
    for key in ("sensitive_subcommands", "reserved_api_paths", "lanes"):
        if key not in data:
            raise ManifestError(f"ownership-lanes manifest missing required key '{key}': {path}")
    if not isinstance(data["lanes"], dict) or not data["lanes"]:
        raise ManifestError(f"ownership-lanes manifest 'lanes' must be a non-empty object: {path}")
    for plugin, lane in data["lanes"].items():
        if not isinstance(lane, dict) or "allowed_gh_subcommands" not in lane:
            raise ManifestError(
                f"lane '{plugin}' must be an object with 'allowed_gh_subcommands': {path}"
            )
    if not isinstance(data["sensitive_subcommands"], list):
        raise ManifestError(f"'sensitive_subcommands' must be a list: {path}")
    if not isinstance(data["reserved_api_paths"], dict):
        raise ManifestError(f"'reserved_api_paths' must be an object: {path}")
    return data


def _string_token(node: ast.expr) -> str | None:
    """Best-effort literal string for a list element.

    A plain string constant yields its value; an f-string yields its leading constant prefix
    (so ``f"projects/{pid}/items"`` still exposes the ``projects/`` reserved prefix). Anything
    else (a bare name, a call) yields None — it cannot be statically attributed.
    """

    if isinstance(node, ast.Constant) and isinstance(node.value, str):
        return node.value
    if isinstance(node, ast.JoinedStr) and node.values and isinstance(node.values[0], ast.Constant):
        lead = node.values[0].value
        if isinstance(lead, str):
            return lead
    return None


def find_gh_invocations(source: str) -> list[GhInvocation]:
    """Return every ``gh`` command-list literal in a Python source string.

    Matches list/tuple literals whose first element is the string ``"gh"`` (or ``"gh <sub>"``
    combined into one token). Returns the subcommand (None when built dynamically) plus all
    literal string tokens for the reserved-path check.
    """

    try:
        tree = ast.parse(source)
    except SyntaxError:
        return []

    invocations: list[GhInvocation] = []
    for node in ast.walk(tree):
        if not isinstance(node, (ast.List, ast.Tuple)) or not node.elts:
            continue
        first = _string_token(node.elts[0])
        if first is None or (first != "gh" and not first.startswith("gh ")):
            continue

        tokens = tuple(t for t in (_string_token(e) for e in node.elts) if t is not None)
        if first == "gh":
            second = _string_token(node.elts[1]) if len(node.elts) > 1 else None
            subcommand = second
        else:
            parts = first.split()
            subcommand = parts[1] if len(parts) > 1 else None
        invocations.append(GhInvocation(node.lineno, subcommand, tokens))
    return invocations


def _iter_plugin_py_files(plugin_dir: Path) -> list[Path]:
    """All hand-authored .py files under a plugin dir, excluding tests/generated/cache."""

    files: list[Path] = []
    for path in sorted(plugin_dir.rglob("*.py")):
        if EXCLUDED_DIR_SEGMENTS & set(path.parts):
            continue
        files.append(path)
    return files


def scan_plugin(
    plugin: str,
    plugin_dir: Path,
    lane: dict[str, Any],
    *,
    sensitive: set[str],
    reserved_api_paths: dict[str, str],
    lanes: dict[str, Any],
) -> list[Violation]:
    """Scan one plugin directory and return its cross-lane violations."""

    allowed = set(lane.get("allowed_gh_subcommands", []))
    violations: list[Violation] = []
    for path in _iter_plugin_py_files(plugin_dir):
        try:
            source = path.read_text()
        except OSError:
            continue
        for inv in find_gh_invocations(source):
            sub = inv.subcommand
            if sub is None:
                continue  # dynamically built command; not statically attributable
            if sub in sensitive and sub not in allowed:
                owner = _owner_of_subcommand(sub, plugin, lanes)
                violations.append(
                    Violation(
                        file=path,
                        lineno=inv.lineno,
                        plugin=plugin,
                        call=f"gh {sub}",
                        crossed_into=owner,
                        reason=f"`{sub}` is not in {plugin}'s ownership lane",
                    )
                )
                continue
            if sub == "api":
                crossed = _reserved_path_crossed(inv.tokens, plugin, reserved_api_paths)
                if crossed is not None:
                    prefix, owner = crossed
                    violations.append(
                        Violation(
                            file=path,
                            lineno=inv.lineno,
                            plugin=plugin,
                            call=f"gh api {prefix}...",
                            crossed_into=owner,
                            reason=f"`gh api {prefix}` is reserved to {owner}",
                        )
                    )
    return violations


def _owner_of_subcommand(sub: str, invoking: str, lanes: dict[str, Any]) -> str:
    """Name the plugin(s) that declare this subcommand in their lane, for the message."""

    owners = sorted(
        name
        for name, lane in lanes.items()
        if name != invoking and sub in lane.get("allowed_gh_subcommands", [])
    )
    return ", ".join(owners) if owners else "another plugin lane"


def _reserved_path_crossed(
    tokens: tuple[str, ...], invoking: str, reserved_api_paths: dict[str, str]
) -> tuple[str, str] | None:
    """Return (prefix, owner) if a ``gh api`` invocation reaches a reserved path it can't own."""

    for token in tokens:
        for prefix, owner in reserved_api_paths.items():
            if token.startswith(prefix) and owner != invoking:
                return prefix, owner
    return None


def run_check(manifest: dict[str, Any], plugins_root: Path) -> list[Violation]:
    """Scan every plugin declared in the manifest and return all violations found."""

    sensitive = set(manifest["sensitive_subcommands"])
    reserved_api_paths = dict(manifest["reserved_api_paths"])
    lanes = dict(manifest["lanes"])
    violations: list[Violation] = []
    for plugin, lane in lanes.items():
        plugin_dir = plugins_root / plugin
        if not plugin_dir.is_dir():
            continue
        violations.extend(
            scan_plugin(
                plugin,
                plugin_dir,
                lane,
                sensitive=sensitive,
                reserved_api_paths=reserved_api_paths,
                lanes=lanes,
            )
        )
    return violations


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0] if __doc__ else None)
    parser.add_argument(
        "--manifest",
        type=Path,
        default=DEFAULT_MANIFEST,
        help="Path to ownership_lanes.json (default: marketplace/ownership_lanes.json).",
    )
    parser.add_argument(
        "--plugins-root",
        type=Path,
        default=DEFAULT_PLUGINS_ROOT,
        help="Root directory containing per-plugin subdirectories (default: plugins/).",
    )
    parser.add_argument(
        "--verbose",
        action="store_true",
        help="Print the plugins scanned and a clean-pass line when no violations are found.",
    )
    args = parser.parse_args(argv)

    try:
        manifest = load_manifest(args.manifest)
    except ManifestError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2

    if args.verbose:
        scanned = ", ".join(sorted(manifest["lanes"]))
        print(f"ownership-lanes: scanning declared plugins: {scanned}")

    violations = run_check(manifest, args.plugins_root)
    if violations:
        for violation in violations:
            print(violation.render(args.plugins_root), file=sys.stderr)
        print(
            f"\n{len(violations)} ownership-lane violation(s) found. "
            f"A plugin script crossed into another plugin's owned mutation surface. "
            f"Move the call behind its owning plugin, or update {args.manifest.name} if the "
            f"lane boundary genuinely changed.",
            file=sys.stderr,
        )
        return 1

    if args.verbose:
        print("ownership-lanes: OK — no cross-lane mutations found.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
