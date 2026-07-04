#!/usr/bin/env python3
"""Fleet-commons resolution shim — how a plugin finds fleet-core at run time.

Canonical copy: ``plugins/fleet-core/scripts/fleet_commons_shim.py``. Consumer plugins vendor a
byte-identical copy into their own ``scripts/``; a repo drift-guard test compares every vendored
copy to the canonical file. Keep this file minimal and rarely-changing — it is bootstrap code,
not a home for logic (DECISIONS ``{#fleet-commons-mechanism-463}``).

Resolution ladder (first rung that succeeds wins; provenance is part of the return value):

1. ``FLEET_COMMONS_ROOT`` env override — explicit, so an invalid value raises rather than falls
   through.
2. Repo-checkout walk-up from this file: an ancestor holding both
   ``.claude-plugin/marketplace.json`` and ``plugins/fleet-core/``.
3. ``~/.claude/plugins/installed_plugins.json`` (schema ``version: 2``): any key with prefix
   ``fleet-core@`` → its install records' ``installPath``. Parse/shape trouble is a rung miss,
   never a crash.
4. Cache-sibling scan: ``$CLAUDE_PLUGIN_ROOT/../../fleet-core/<highest semver>/``.
5. Fail loud with an actionable message.

Set ``FLEET_COMMONS_DEBUG=1`` to print ``fleet-commons: rung=<n> (<name>) root=<path>`` to
stderr on every successful resolve (subprocess-observable provenance).
"""

from __future__ import annotations

import importlib.util
import json
import os
import sys
from pathlib import Path
from types import ModuleType

RUNG_NAMES = {1: "env-override", 2: "repo-walk-up", 3: "installed-plugins", 4: "cache-sibling"}

_FAIL_MESSAGE = (
    "fleet-commons: could not resolve a fleet-core root (tried FLEET_COMMONS_ROOT, repo walk-up, "
    "~/.claude/plugins/installed_plugins.json, cache-sibling scan). Fix: install the fleet-core "
    "plugin from the infiquetra-plugins marketplace, or set FLEET_COMMONS_ROOT to a checkout's "
    "plugins/fleet-core directory."
)


def _is_valid_root(root: Path) -> bool:
    return (root / "scripts" / "fleet_commons").is_dir()


def _semver_key(name: str) -> tuple[int, ...] | None:
    try:
        return tuple(int(part) for part in name.split("."))
    except ValueError:
        return None


def _rung_installed_plugins() -> Path | None:
    registry = Path.home() / ".claude" / "plugins" / "installed_plugins.json"
    try:
        plugins = json.loads(registry.read_text(encoding="utf-8"))["plugins"]
        for key, records in plugins.items():
            if not key.startswith("fleet-core@"):
                continue
            for record in records:
                root = Path(record["installPath"])
                if _is_valid_root(root):
                    return root
    except (OSError, ValueError, KeyError, TypeError, AttributeError):
        return None  # undocumented internal registry: any shape surprise is a rung miss
    return None


def _rung_cache_sibling() -> Path | None:
    plugin_root = os.environ.get("CLAUDE_PLUGIN_ROOT")
    if not plugin_root:
        return None
    versions_dir = Path(plugin_root).resolve().parent.parent / "fleet-core"
    if not versions_dir.is_dir():
        return None
    candidates = [
        (key, child)
        for child in versions_dir.iterdir()
        if child.is_dir() and (key := _semver_key(child.name)) is not None
    ]
    for _, root in sorted(candidates, reverse=True):
        if _is_valid_root(root):
            return root
    return None


def resolve_root() -> tuple[Path, int]:
    """Resolve the fleet-core root; returns ``(root, rung)`` or raises RuntimeError."""
    resolved: tuple[Path, int] | None = None
    override = os.environ.get("FLEET_COMMONS_ROOT")
    if override:
        root = Path(override)
        if not _is_valid_root(root):
            raise RuntimeError(
                f"fleet-commons: FLEET_COMMONS_ROOT={override!r} is not a fleet-core root "
                "(expected a directory containing scripts/fleet_commons/)."
            )
        resolved = (root, 1)
    if resolved is None:
        for ancestor in Path(__file__).resolve().parents:
            candidate = ancestor / "plugins" / "fleet-core"
            marketplace = ancestor / ".claude-plugin" / "marketplace.json"
            if marketplace.is_file() and _is_valid_root(candidate):
                resolved = (candidate, 2)
                break
    if resolved is None and (root := _rung_installed_plugins()) is not None:
        resolved = (root, 3)
    if resolved is None and (root := _rung_cache_sibling()) is not None:
        resolved = (root, 4)
    if resolved is None:
        raise RuntimeError(_FAIL_MESSAGE)
    if os.environ.get("FLEET_COMMONS_DEBUG") == "1":
        root, rung = resolved
        print(
            f"fleet-commons: rung={rung} ({RUNG_NAMES[rung]}) root={root}",
            file=sys.stderr,
        )
    return resolved


def resolved_version() -> str:
    """The resolved fleet-core's own version, for diagnostics; 'unknown' when unreadable."""
    root, _ = resolve_root()
    try:
        manifest = json.loads((root / ".claude-plugin" / "plugin.json").read_text(encoding="utf-8"))
        return str(manifest["version"])
    except (OSError, ValueError, KeyError, TypeError):
        return "unknown"


def load(module: str) -> ModuleType:
    """Load ``<root>/scripts/fleet_commons/<module>.py``; repeated loads return the same object."""
    cache_key = f"_fleet_commons_{module}"
    cached = sys.modules.get(cache_key)
    if cached is not None:
        return cached
    root, _ = resolve_root()
    module_path = root / "scripts" / "fleet_commons" / f"{module}.py"
    if not module_path.is_file():
        raise RuntimeError(
            f"fleet-commons: module {module!r} not found at {module_path} "
            f"(fleet-core resolved to {root}, version {resolved_version()})."
        )
    spec = importlib.util.spec_from_file_location(cache_key, module_path)
    if spec is None or spec.loader is None:  # pragma: no cover - importlib internal failure
        raise RuntimeError(f"fleet-commons: importlib could not load {module_path}")
    loaded = importlib.util.module_from_spec(spec)
    sys.modules[cache_key] = loaded
    try:
        spec.loader.exec_module(loaded)
    except BaseException:
        sys.modules.pop(cache_key, None)
        raise
    return loaded
