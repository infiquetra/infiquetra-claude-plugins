#!/usr/bin/env python3
"""Write-ownership lane lint (issue #431, hardened in #583).

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
that merely *mention* ``gh pr view`` are never mistaken for real calls.

The detector attributes:
1. Command list/tuple literals whose first element is ``"gh"`` (or ``"gh <sub>"`` combined).
2. List concatenation onto ``["gh"]`` (e.g. ``["gh"] + ["issue", "create"]``).
3. List literals passed to known wrapper helpers (e.g. ``_run_gh(["issue", "create", ...])``,
   ``_run_gh_json(...)``, ``_gh(...)``).

Known skips (out of AST scope):
- Dynamically built command lists with no literal subcommand (e.g. ``["gh"] + args`` or
  ``_run_gh(args)``) cannot be statically attributed and are skipped.
- Shell-string invocations (e.g. ``subprocess.run("gh issue create ...", shell=True)``) are
  out of AST list-literal scope and skipped (no live exposure in the repo).

Checks run per detected invocation:

1. **Subcommand lane & verb-aware policing.** If the subcommand is in ``sensitive_subcommands``
   and is not in the invoking plugin's ``allowed_gh_subcommands``:
   - Benign read verbs (``view``, ``list``, ``status``, ``diff``, ``checks``, ``download``,
     ``get``, ``watch``) are permitted across lanes and not flagged.
   - Mutation verbs (``create``, ``edit``, ``delete``, ``close``, ``reopen``, ``merge``, etc.)
     or unverified verbs are flagged as cross-lane violations.
2. **Reserved ``gh api`` endpoint path.** Any ``gh api`` invocation whose endpoint positional
   argument starts with a prefix in ``reserved_api_paths`` (e.g. ``projects/`` → mission-control)
   is a violation unless the invoking plugin is that prefix's declared owner. Flag arguments
   (e.g. ``-f title=projects/...``) are skipped so only the actual endpoint is evaluated.
3. **GraphQL ProjectV2 mutations.** Any ``gh api graphql`` invocation containing ProjectV2
   mutation strings (e.g. ``updateProjectV2ItemFieldValue``, ``addProjectV2ItemById``,
   ``archiveProjectV2Item``) is reserved to the board owner (mission-control) and flagged if
   called from another lane.

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

# Read-only verbs permitted across lanes for sensitive subcommands (#583 R3)
READ_VERBS = frozenset(
    {
        "view",
        "list",
        "status",
        "diff",
        "checks",
        "download",
        "get",
        "watch",
    }
)

# ProjectV2 GraphQL mutation operation names reserved to board owner (#583 R2)
# Ordered longest first so specific mutations match before shorter prefixes (e.g. updateProjectV2)
PROJECT_V2_MUTATIONS: tuple[str, ...] = tuple(
    sorted(
        [
            "updateProjectV2ItemFieldValue",
            "addProjectV2ItemById",
            "archiveProjectV2Item",
            "unarchiveProjectV2Item",
            "deleteProjectV2Item",
            "updateProjectV2ItemPosition",
            "createProjectV2",
            "updateProjectV2",
            "deleteProjectV2",
            "copyProjectV2",
            "createProjectV2Field",
            "updateProjectV2Field",
            "deleteProjectV2Field",
            "createProjectV2StatusUpdate",
            "updateProjectV2StatusUpdate",
            "deleteProjectV2StatusUpdate",
        ],
        key=len,
        reverse=True,
    )
)

# Known wrapper helper names that prepend "gh" to their argument list (#583 R1)
KNOWN_WRAPPER_NAMES = frozenset(
    {
        "_run_gh",
        "_run_gh_json",
        "_gh",
        "run_gh",
        "run_gh_json",
        "_gh_json",
        "gh_cli",
        "_gh_cli",
    }
)


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


def _collect_string_variables(tree: ast.AST) -> dict[str, str]:
    """Collect literal string variable assignments in the AST."""
    var_map: dict[str, str] = {}
    for node in ast.walk(tree):
        if (
            isinstance(node, ast.Assign)
            and isinstance(node.value, ast.Constant)
            and isinstance(node.value.value, str)
        ):
            for target in node.targets:
                if isinstance(target, ast.Name):
                    var_map[target.id] = node.value.value
    return var_map


def _string_token(node: ast.expr, var_map: dict[str, str] | None = None) -> str | None:
    """Best-effort literal string for a list element or argument.

    A plain string constant yields its value; an f-string yields its formatted/joined text
    (resolving simple string variables in var_map when present) or its leading constant prefix.
    """

    if isinstance(node, ast.Constant) and isinstance(node.value, str):
        return node.value
    if isinstance(node, ast.Name) and var_map and node.id in var_map:
        return var_map[node.id]
    if isinstance(node, ast.JoinedStr):
        if var_map:
            parts: list[str] = []
            for v in node.values:
                if isinstance(v, ast.Constant) and isinstance(v.value, str):
                    parts.append(v.value)
                elif (
                    isinstance(v, ast.FormattedValue)
                    and isinstance(v.value, ast.Name)
                    and v.value.id in var_map
                ):
                    parts.append(var_map[v.value.id])
            if parts:
                return "".join(parts)
        if node.values and isinstance(node.values[0], ast.Constant):
            lead = node.values[0].value
            if isinstance(lead, str):
                return lead
    return None


def _is_gh_wrapper_call(node: ast.Call) -> bool:
    """Check if a Call node is invoking a known `gh` CLI wrapper function."""
    if isinstance(node.func, ast.Name):
        name = node.func.id
    elif isinstance(node.func, ast.Attribute):
        name = node.func.attr
    else:
        return False

    if name in KNOWN_WRAPPER_NAMES:
        return True
    return name.startswith(("_run_gh", "run_gh")) or name.endswith(("_gh", "_gh_json"))


def _extract_wrapper_arg_list(node: ast.Call) -> ast.List | ast.Tuple | None:
    """Extract list/tuple argument from a wrapper function call."""
    if node.args and isinstance(node.args[0], (ast.List, ast.Tuple)):
        return node.args[0]
    for kw in node.keywords:
        if kw.arg in ("args", "cmd") and isinstance(kw.value, (ast.List, ast.Tuple)):
            return kw.value
    return None


def find_gh_invocations(source: str) -> list[GhInvocation]:
    """Return every ``gh`` command-list literal in a Python source string.

    Matches:
    - List/tuple literals whose first element is ``"gh"`` (or ``"gh <sub>"`` combined).
    - List concatenation onto ``["gh"]`` (e.g. ``["gh"] + ["issue", "create"]``).
    - Calls to known wrapper helpers passing list literals (e.g. ``_run_gh(["issue", "view"])``).
    """

    try:
        tree = ast.parse(source)
    except SyntaxError:
        return []

    var_map = _collect_string_variables(tree)
    invocations: list[GhInvocation] = []
    for node in ast.walk(tree):
        # Shape 1: Direct list/tuple literal starting with "gh" or "gh <sub>"
        if isinstance(node, (ast.List, ast.Tuple)) and node.elts:
            first = _string_token(node.elts[0], var_map)
            if first is not None and (first == "gh" or first.startswith("gh ")):
                tokens = tuple(
                    t for t in (_string_token(e, var_map) for e in node.elts) if t is not None
                )
                if first == "gh":
                    second = _string_token(node.elts[1], var_map) if len(node.elts) > 1 else None
                    subcommand = second
                else:
                    parts = first.split()
                    subcommand = parts[1] if len(parts) > 1 else None
                invocations.append(GhInvocation(node.lineno, subcommand, tokens))
                continue

        # Shape 2: BinOp addition with ["gh"] (e.g. ["gh"] + ["sub", ...])
        # Note: ["gh"] + args is already captured by Shape 1 on the left list ["gh"] as subcommand=None.
        if (
            isinstance(node, ast.BinOp)
            and isinstance(node.op, ast.Add)
            and isinstance(node.left, (ast.List, ast.Tuple))
            and node.left.elts
        ):
            first = _string_token(node.left.elts[0], var_map)
            if first == "gh":
                if len(node.left.elts) == 1:
                    if isinstance(node.right, (ast.List, ast.Tuple)) and node.right.elts:
                        right_first = _string_token(node.right.elts[0], var_map)
                        if right_first is not None:
                            subcommand = right_first
                            tokens = ("gh",) + tuple(
                                t
                                for t in (_string_token(e, var_map) for e in node.right.elts)
                                if t is not None
                            )
                            invocations.append(GhInvocation(node.lineno, subcommand, tokens))
                else:
                    second = _string_token(node.left.elts[1], var_map)
                    if isinstance(node.right, (ast.List, ast.Tuple)) and node.right.elts:
                        left_tokens = tuple(
                            t
                            for t in (_string_token(e, var_map) for e in node.left.elts)
                            if t is not None
                        )
                        right_tokens = tuple(
                            t
                            for t in (_string_token(e, var_map) for e in node.right.elts)
                            if t is not None
                        )
                        invocations.append(
                            GhInvocation(node.lineno, second, left_tokens + right_tokens)
                        )
                continue

        # Shape 3: Wrapper helper calls: _run_gh(["sub", "verb", ...])
        if isinstance(node, ast.Call) and _is_gh_wrapper_call(node):
            arg_list = _extract_wrapper_arg_list(node)
            if arg_list is not None and arg_list.elts:
                first = _string_token(arg_list.elts[0], var_map)
                if first is not None and first != "gh" and not first.startswith("gh "):
                    subcommand = first
                    arg_tokens = tuple(
                        t
                        for t in (_string_token(e, var_map) for e in arg_list.elts)
                        if t is not None
                    )
                    tokens = ("gh",) + arg_tokens
                    invocations.append(GhInvocation(node.lineno, subcommand, tokens))
                elif first is None:
                    invocations.append(GhInvocation(node.lineno, None, ("gh",)))

    return invocations


def _iter_plugin_py_files(plugin_dir: Path) -> list[Path]:
    """All hand-authored .py files under a plugin dir, excluding tests/generated/cache."""

    files: list[Path] = []
    for path in sorted(plugin_dir.rglob("*.py")):
        if EXCLUDED_DIR_SEGMENTS & set(path.parts):
            continue
        files.append(path)
    return files


def _extract_verb(tokens: tuple[str, ...], subcommand: str) -> str | None:
    """Extract the verb token following the subcommand, skipping flags.

    For example:
    - ("gh", "issue", "view", "123") -> "view"
    - ("gh", "issue", "--repo", "org/repo", "create") -> "create"
    - ("gh", "issue", "create") -> "create"
    - ("gh", "issue") -> None
    """

    sub_idx = -1
    for idx, token in enumerate(tokens):
        if token == subcommand or token.endswith(f" {subcommand}"):
            sub_idx = idx
            break
    if sub_idx == -1:
        return None

    idx = sub_idx + 1
    while idx < len(tokens):
        token = tokens[idx]
        if token.startswith("-"):
            if token in (
                "-R",
                "--repo",
                "-a",
                "--app",
                "--json",
                "-q",
                "--jq",
                "-t",
                "--template",
            ):
                idx += 2
                continue
            idx += 1
            continue
        return token.lower()
    return None


def _api_endpoint(tokens: tuple[str, ...]) -> str | None:
    """Extract the target API endpoint path from a ``gh api`` invocation's tokens.

    Skips flags and their arguments (e.g. ``--method PATCH``, ``-f key=val``) to find
    the positional endpoint argument, preventing false positives on flag values.
    """

    start_idx = 0
    for idx, token in enumerate(tokens):
        if token == "api" or token.endswith(" api"):  # nosec B105
            start_idx = idx + 1
            break

    idx = start_idx
    while idx < len(tokens):
        token = tokens[idx]
        if token.startswith("-"):
            if token in (
                "-X",
                "--method",
                "-F",
                "-f",
                "--field",
                "--raw-field",
                "-H",
                "--header",
                "-q",
                "--jq",
                "-t",
                "--template",
                "--input",
                "-p",
                "--preview",
                "--cache",
            ):
                idx += 2
                continue
            idx += 1
            continue
        return token
    return None


def _find_project_v2_mutation(tokens: tuple[str, ...]) -> str | None:
    """Return the name of a ProjectV2 GraphQL mutation if present in the tokens."""

    for token in tokens:
        for mutation in PROJECT_V2_MUTATIONS:
            if mutation in token:
                return mutation
    return None


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
    board_owner = reserved_api_paths.get("projects/", "mission-control")

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
                verb = _extract_verb(inv.tokens, sub)
                if verb is not None and verb in READ_VERBS:
                    # Benign read verb (e.g. gh issue view) permitted across lanes (#583 R3)
                    pass
                else:
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
                # Check for ProjectV2 GraphQL mutations from non-board-owners (#583 R2)
                mutation = _find_project_v2_mutation(inv.tokens)
                if mutation is not None and plugin != board_owner:
                    violations.append(
                        Violation(
                            file=path,
                            lineno=inv.lineno,
                            plugin=plugin,
                            call=f"gh api graphql ({mutation})",
                            crossed_into=board_owner,
                            reason=f"`{mutation}` GraphQL mutation is reserved to {board_owner}",
                        )
                    )
                    continue

                # Check for reserved REST api endpoint paths (#583 R4)
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

    endpoint = _api_endpoint(tokens)
    if endpoint is None:
        return None
    for prefix, owner in reserved_api_paths.items():
        if endpoint.startswith(prefix) and owner != invoking:
            return prefix, owner
    return None


def run_check(manifest: dict[str, Any], plugins_root: Path) -> list[Violation]:
    """Scan every plugin declared in the manifest and return all violations found.

    Raises ManifestError if any declared plugin directory is missing (#583 R4).
    """

    sensitive = set(manifest["sensitive_subcommands"])
    reserved_api_paths = dict(manifest["reserved_api_paths"])
    lanes = dict(manifest["lanes"])
    violations: list[Violation] = []
    for plugin, lane in lanes.items():
        plugin_dir = plugins_root / plugin
        if not plugin_dir.is_dir():
            raise ManifestError(
                f"declared lane '{plugin}' directory not found under {plugins_root}"
            )
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
        if args.verbose:
            scanned = ", ".join(sorted(manifest["lanes"]))
            print(f"ownership-lanes: scanning declared plugins: {scanned}")
        violations = run_check(manifest, args.plugins_root)
    except ManifestError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2

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
