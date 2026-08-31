#!/usr/bin/env python3
"""Saga execution-spec resolution shim — how the cc-workflows plugin finds Saga at run time.

Modeled on ``plugins/fleet-core/scripts/fleet_commons_shim.py`` (DECISIONS
``{#fleet-commons-mechanism-463}``): a resolution ladder, loud failure, bootstrap code only.
The seam is the spec shape (plan KTD, #925 U4): the extracted emitter reads Saga's
``execution_spec.py`` — never a copy of it — so the two sides cannot drift.

Resolution ladder (first rung that succeeds wins):

1. ``SAGA_SPEC_ROOT`` env override — explicit, so an invalid value raises rather than falls
   through.
2. Repo-checkout walk-up from this file: an ancestor holding both
   ``.claude-plugin/marketplace.json`` and ``plugins/saga/scripts/execution_spec.py``.
3. ``~/.claude/plugins/installed_plugins.json`` (schema ``version: 2``): any key with prefix
   ``saga@`` → its install records' ``installPath``. Parse/shape trouble is a rung miss,
   never a crash.
4. Cache-sibling scan: ``$CLAUDE_PLUGIN_ROOT/../../saga/<highest semver>/``.
5. Fail loud with an actionable message.
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
    "cc-workflows: could not resolve a saga plugin root (tried SAGA_SPEC_ROOT, repo walk-up, "
    "~/.claude/plugins/installed_plugins.json, cache-sibling scan). Fix: install the saga "
    "plugin from the infiquetra-plugins marketplace, or set SAGA_SPEC_ROOT to a checkout's "
    "plugins/saga directory."
)


def _is_valid_root(root: Path) -> bool:
    return (root / "scripts" / "execution_spec.py").is_file()


def _semver_key(name: str) -> tuple[int, ...] | None:
    try:
        return tuple(int(part) for part in name.split("."))
    except ValueError:
        return None


def _rung_installed_plugins() -> Path | None:
    registry = Path.home() / ".claude" / "plugins" / "installed_plugins.json"
    try:
        entries = list(json.loads(registry.read_text(encoding="utf-8"))["plugins"].items())
    except (OSError, ValueError, KeyError, TypeError, AttributeError):
        return None  # undocumented internal registry: any shape surprise is a rung miss
    for key, records in entries:
        if not key.startswith("saga@"):
            continue
        try:
            candidates = list(records)
        except TypeError:
            continue
        for record in candidates:
            # Per-record tolerance: one malformed record must not poison the scan.
            try:
                root = Path(record["installPath"])
            except (KeyError, TypeError):
                continue
            if _is_valid_root(root):
                return root
    return None


def _rung_cache_sibling() -> Path | None:
    plugin_root = os.environ.get("CLAUDE_PLUGIN_ROOT")
    if not plugin_root:
        return None
    versions_dir = Path(plugin_root).resolve().parent.parent / "saga"
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
    """Resolve the saga plugin root; returns ``(root, rung)`` or raises RuntimeError."""
    resolved: tuple[Path, int] | None = None
    override = os.environ.get("SAGA_SPEC_ROOT")
    if override:
        root = Path(override)
        if not _is_valid_root(root):
            raise RuntimeError(
                f"cc-workflows: SAGA_SPEC_ROOT={override!r} is not a saga plugin root "
                "(expected a directory containing scripts/execution_spec.py)."
            )
        resolved = (root, 1)
    if resolved is None:
        for ancestor in Path(__file__).resolve().parents:
            candidate = ancestor / "plugins" / "saga"
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
    if os.environ.get("SAGA_SPEC_DEBUG") == "1":
        root, rung = resolved
        print(
            f"cc-workflows: saga-spec rung={rung} ({RUNG_NAMES[rung]}) root={root}", file=sys.stderr
        )
    return resolved


def load_execution_spec() -> ModuleType:
    """Load Saga's ``execution_spec.py`` — the spec schema this emitter emits from.

    Reuses ``sys.modules["execution_spec"]`` when a host process already loaded it (the
    same single-instance convention ``team_emitter.py`` follows), so the spec classes in
    play are always one set; otherwise loads from the resolved saga root and registers
    the module under its bare name.
    """
    cached = sys.modules.get("execution_spec")
    if cached is not None:
        return cached
    root, _ = resolve_root()
    scripts = root / "scripts"
    if str(scripts) not in sys.path:
        sys.path.insert(0, str(scripts))
    module_path = scripts / "execution_spec.py"
    spec = importlib.util.spec_from_file_location("execution_spec", module_path)
    if spec is None or spec.loader is None:  # pragma: no cover - importlib internal failure
        raise RuntimeError(f"cc-workflows: importlib could not load {module_path}")
    loaded = importlib.util.module_from_spec(spec)
    sys.modules["execution_spec"] = loaded
    try:
        spec.loader.exec_module(loaded)
    except BaseException:
        sys.modules.pop("execution_spec", None)
        raise
    return loaded
