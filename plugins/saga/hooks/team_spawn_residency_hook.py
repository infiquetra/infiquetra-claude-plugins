#!/usr/bin/env python3
"""
PreToolUse hook: warn-first team-spawn residency guard.

Fires when the orchestrator spawns a team-execution reviewer or tester
(``Agent`` in this harness, ``Task`` on stock Claude Code) without the
named-persistent-teammate shape S-1 (#275) mandates. Emits a single-line
``additionalContext`` advisory pointing at the fix; never blocks, denies, or
mutates the spawn. Advisory-only: it observes the residency protocol, it
does not enforce it (issue #289).

Properties:
  - SILENT ON PASS: named spawns, non-team-family spawns, and spawns outside
    the trigger set produce no output.
  - NEVER BLOCKING: always exits 0.
  - REGISTRY-DRIVEN: the trigger set is parsed fresh from
    reviewer-registry.md / validator-registry.md on every invocation — no
    materialized manifest to drift (R4).
  - CROSS-LAYOUT-SAFE: resolves the registries' directory across dev-repo,
    versioned-cache-install, and project-root layouts; degrades silently
    when none resolve (D5).

Exit codes:
  0 — always (warn-only; never blocks a spawn).
"""

from __future__ import annotations

import contextlib
import json
import os
import re
import sys
from pathlib import Path

_REVIEWER_REGISTRY = "reviewer-registry.md"
_VALIDATOR_REGISTRY = "validator-registry.md"
_TEAM_EXECUTION_REFERENCES = Path("skills") / "team-execution" / "references"
_INSTALLED_PLUGINS_FILENAME = "installed_plugins.json"

_TEAM_TOOL_NAMES = {"Agent", "Task"}
_INCLUDE_ENV = "TEAM_SPAWN_GUARD_INCLUDE"
_EXCLUDE_ENV = "TEAM_SPAWN_GUARD_EXCLUDE"
_MAX_ANCESTOR_LEVELS = 10

_BACKTICK_TOKEN_RE = re.compile(r"`([a-z0-9-]+)`")
_REVIEWER_TOKEN_RE = re.compile(r"^[a-z0-9-]+-reviewer$")


# ---------------------------------------------------------------------------
# Registry parsing (KTD4, R3, R4)
# ---------------------------------------------------------------------------


def _table_row_tokens(text: str) -> list[str]:
    """Backticked tokens on markdown table rows (lines starting with '|')."""
    tokens: list[str] = []
    for line in text.splitlines():
        if not line.lstrip().startswith("|"):
            continue
        tokens.extend(_BACKTICK_TOKEN_RE.findall(line))
    return tokens


def _reviewer_names(text: str) -> set[str]:
    """Reviewer agent names: backticked `<name>-reviewer` tokens on any table row.

    The whole-token match naturally excludes the "Agent File" column's
    ``agents/<name>-reviewer.md`` values (extra `/` and `.md` break the
    `[a-z0-9-]+` match) and the "Adding a New Reviewer" section's literal
    ``<name>-reviewer`` template (not a table row and not a bare token).
    """
    return {tok for tok in _table_row_tokens(text) if _REVIEWER_TOKEN_RE.match(tok)}


def _tester_names(text: str) -> set[str]:
    """Tester agent names: backticked tokens on table rows within '## Testers' only.

    validator-registry.md also lists scanners/monitors/deploy-watcher/advisory
    roles under sibling sections — section-scoping (not a suffix filter) is
    what excludes them (R3).
    """
    names: set[str] = set()
    in_section = False
    for line in text.splitlines():
        stripped = line.strip()
        if stripped.startswith("## "):
            in_section = stripped == "## Testers"
            continue
        if not in_section or not line.lstrip().startswith("|"):
            continue
        names.update(_BACKTICK_TOKEN_RE.findall(line))
    return names


def load_trigger_set(references_dir: Path) -> frozenset[str]:
    """Parse the reviewer + tester registries into the team-spawn trigger set.

    A missing or unreadable registry file contributes nothing rather than
    raising (R10) — the hook degrades to a smaller (or empty) trigger set,
    never to an error.
    """
    names: set[str] = set()

    with contextlib.suppress(OSError, UnicodeDecodeError):
        names |= _reviewer_names((references_dir / _REVIEWER_REGISTRY).read_text(encoding="utf-8"))

    with contextlib.suppress(OSError, UnicodeDecodeError):
        names |= _tester_names((references_dir / _VALIDATOR_REGISTRY).read_text(encoding="utf-8"))

    return frozenset(names)


# ---------------------------------------------------------------------------
# Registry-directory resolution (KTD3 — four-step chain, first hit wins)
# ---------------------------------------------------------------------------


def _semver_key(path: Path) -> tuple[int, ...]:
    try:
        return tuple(int(part) for part in path.name.split("."))
    except ValueError:
        return (-1,)


def _versioned_cache_dir(plugin_root: Path) -> Path | None:
    """Resolve team-execution's references dir under a versioned-cache install (step 2).

    Only applies when ``plugin_root`` looks like
    ``.../cache/<marketplace>/<plugin>/<version>``. Reads the active
    ``installPath`` from ``installed_plugins.json`` (authoritative); falls
    back to a max-semver glob only when that registry is absent, unreadable,
    or has no ``team-execution@*`` key (last-resort heuristic, D4).
    """
    parents = plugin_root.parents
    if len(parents) < 4 or parents[2].name != "cache":
        return None

    marketplace_dir = parents[1]
    marketplace = marketplace_dir.name
    installed_json = parents[3] / _INSTALLED_PLUGINS_FILENAME

    try:
        data = json.loads(installed_json.read_text(encoding="utf-8"))
        entries = data.get("plugins", {})
        candidates = entries.get(f"team-execution@{marketplace}") or next(
            (v for k, v in entries.items() if k.startswith("team-execution@") and v),
            None,
        )
        if candidates:
            install_path = Path(candidates[0]["installPath"])
            resolved = install_path / _TEAM_EXECUTION_REFERENCES
            if resolved.is_dir():
                return resolved
    except (OSError, ValueError, KeyError, IndexError, TypeError):
        pass

    team_execution_root = marketplace_dir / "team-execution"
    try:
        version_dirs = [p for p in team_execution_root.iterdir() if p.is_dir()]
    except OSError:
        return None
    if not version_dirs:
        return None

    resolved = max(version_dirs, key=_semver_key) / _TEAM_EXECUTION_REFERENCES
    return resolved if resolved.is_dir() else None


def _find_references_dir(cwd: str | None) -> Path | None:
    """Resolve team-execution's references dir across dev-repo / installed / project layouts.

    First hit wins (KTD3): plugin-root sibling (dev repo) -> versioned-cache
    lookup -> CLAUDE_PROJECT_DIR -> bounded ancestor scan from cwd. Returns
    None when nothing resolves (R10/D5) — never raises.
    """
    plugin_root_str = os.environ.get("CLAUDE_PLUGIN_ROOT")
    if plugin_root_str:
        plugin_root = Path(plugin_root_str)

        dev_sibling = plugin_root.parent / "team-execution" / _TEAM_EXECUTION_REFERENCES
        if dev_sibling.is_dir():
            return dev_sibling

        cache_hit = _versioned_cache_dir(plugin_root)
        if cache_hit is not None:
            return cache_hit

    project_dir = os.environ.get("CLAUDE_PROJECT_DIR")
    if project_dir:
        project_candidate = (
            Path(project_dir) / "plugins" / "team-execution" / _TEAM_EXECUTION_REFERENCES
        )
        if project_candidate.is_dir():
            return project_candidate

    current = Path(cwd) if cwd else Path.cwd()
    for _ in range(_MAX_ANCESTOR_LEVELS):
        candidate = current / "plugins" / "team-execution" / _TEAM_EXECUTION_REFERENCES
        if candidate.is_dir():
            return candidate
        parent = current.parent
        if parent == current:
            break
        current = parent

    return None


# ---------------------------------------------------------------------------
# Decision (KTD1, KTD2, KTD5, R2, R5, R7, R8)
# ---------------------------------------------------------------------------


def _normalize_subagent_type(raw: str) -> str:
    """Strip an optional leading '<plugin>:' prefix (live spawns use the prefixed form)."""
    return raw.rsplit(":", 1)[-1]


def _effective_trigger_set(trigger_set: frozenset[str]) -> frozenset[str]:
    names = set(trigger_set)
    include = os.environ.get(_INCLUDE_ENV, "")
    exclude = os.environ.get(_EXCLUDE_ENV, "")
    if include:
        names |= {tok.strip() for tok in include.split(",") if tok.strip()}
    if exclude:
        names -= {tok.strip() for tok in exclude.split(",") if tok.strip()}
    return frozenset(names)


def decide(tool_input: dict, trigger_set: frozenset[str]) -> str | None:
    """Pure predicate: an advisory string on a nameless team-family spawn, else None.

    Warns iff the normalized ``subagent_type`` is in the (env-adjusted)
    trigger set AND ``name`` is missing, empty, or not a string.
    ``run_in_background`` is never consulted (KTD1 — the field no longer
    exists on this harness's Agent tool).
    """
    subagent_type = tool_input.get("subagent_type")
    if not isinstance(subagent_type, str) or not subagent_type:
        return None

    bare_name = _normalize_subagent_type(subagent_type)
    if bare_name not in _effective_trigger_set(trigger_set):
        return None

    name = tool_input.get("name")
    if isinstance(name, str) and name:
        return None

    return (
        f"[team-spawn-residency] '{subagent_type}' spawned without a name — it will re-pay "
        "full context on every consensus/remediation cycle instead of staying resident. "
        "Spawn with `name` so it stays re-addressable via SendMessage (consensus-protocol.md)."
    )


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------


def main() -> None:
    try:
        payload = json.loads(sys.stdin.read())
    except Exception:
        sys.exit(0)

    if not isinstance(payload, dict):
        sys.exit(0)

    if payload.get("tool_name") not in _TEAM_TOOL_NAMES:
        sys.exit(0)

    tool_input = payload.get("tool_input", {})
    if not isinstance(tool_input, dict):
        sys.exit(0)

    references_dir = _find_references_dir(payload.get("cwd"))
    trigger_set = load_trigger_set(references_dir) if references_dir is not None else frozenset()

    advisory = decide(tool_input, trigger_set)
    if advisory is None:
        sys.exit(0)

    print(
        json.dumps(
            {
                "hookSpecificOutput": {
                    "hookEventName": "PreToolUse",
                    "additionalContext": advisory,
                }
            }
        )
    )
    sys.exit(0)


if __name__ == "__main__":
    main()
