"""Tests for scripts/check_release_surface_parity.py (#429)."""

import importlib.util
import json
import sys
from pathlib import Path

_SM_SPEC = importlib.util.spec_from_file_location(
    "sync_marketplace", Path(__file__).parent.parent / "scripts" / "sync_marketplace.py"
)
assert _SM_SPEC is not None and _SM_SPEC.loader is not None
SM = importlib.util.module_from_spec(_SM_SPEC)
sys.modules["sync_marketplace"] = SM
_SM_SPEC.loader.exec_module(SM)

_CHL_SPEC = importlib.util.spec_from_file_location(
    "changelog_heading_lint",
    Path(__file__).parent.parent / "scripts" / "changelog_heading_lint.py",
)
assert _CHL_SPEC is not None and _CHL_SPEC.loader is not None
CHL = importlib.util.module_from_spec(_CHL_SPEC)
sys.modules["changelog_heading_lint"] = CHL
_CHL_SPEC.loader.exec_module(CHL)

_PARITY_SPEC = importlib.util.spec_from_file_location(
    "check_release_surface_parity",
    Path(__file__).parent.parent / "scripts" / "check_release_surface_parity.py",
)
assert _PARITY_SPEC is not None and _PARITY_SPEC.loader is not None
PARITY = importlib.util.module_from_spec(_PARITY_SPEC)
sys.modules["check_release_surface_parity"] = PARITY
_PARITY_SPEC.loader.exec_module(PARITY)


def _write_plugin(plugins_dir: Path, name: str, version: str, changelog_top_version: str) -> None:
    plugin_dir = plugins_dir / name / ".claude-plugin"
    plugin_dir.mkdir(parents=True)
    (plugin_dir / "plugin.json").write_text(
        json.dumps(
            {
                "name": name,
                "version": version,
                "description": f"{name} plugin",
                "author": {"name": "Infiquetra", "email": "hello@infiquetra.com"},
                "repository": "https://github.com/infiquetra/infiquetra-claude-plugins",
                "keywords": [name],
            }
        )
    )
    (plugins_dir / name / "CHANGELOG.md").write_text(
        f"# Changelog\n\n## [{changelog_top_version}] - 2026-07-05\n\n- Entry.\n"
    )


def _write_marketplace(path: Path, entries: list[dict]) -> None:
    path.write_text(
        json.dumps(
            {
                "name": "infiquetra-plugins",
                "owner": {"name": "Infiquetra", "email": "hello@infiquetra.com"},
                "metadata": {"description": "x", "version": "3.0.0", "pluginRoot": "./plugins"},
                "plugins": entries,
            }
        )
    )


def _entry(name: str, version: str) -> dict:
    return {
        "name": name,
        "source": f"./plugins/{name}",
        "version": version,
        "description": f"{name} plugin",
        "author": {"name": "Infiquetra", "email": "hello@infiquetra.com"},
        "repository": "https://github.com/infiquetra/infiquetra-claude-plugins",
        "license": "MIT",
        "keywords": [name],
        "category": "tools",
    }


def test_tri_lock_fails_on_single_plugin_drift(tmp_path):
    plugins_dir = tmp_path / "plugins"
    plugins_dir.mkdir()
    marketplace_path = tmp_path / "marketplace.json"

    _write_plugin(plugins_dir, "alpha", "1.0.0", "1.0.0")
    _write_plugin(plugins_dir, "beta", "2.0.0", "2.0.0")
    _write_plugin(plugins_dir, "gamma", "3.0.0", "9.9.9")  # drifted CHANGELOG
    _write_marketplace(
        marketplace_path,
        [_entry("alpha", "1.0.0"), _entry("beta", "2.0.0"), _entry("gamma", "3.0.0")],
    )

    drifted = PARITY.check_parity(marketplace_path, plugins_dir)

    assert drifted == ["gamma"]


def test_tri_lock_passes_on_agreement(tmp_path):
    plugins_dir = tmp_path / "plugins"
    plugins_dir.mkdir()
    marketplace_path = tmp_path / "marketplace.json"

    _write_plugin(plugins_dir, "alpha", "1.0.0", "1.0.0")
    _write_plugin(plugins_dir, "beta", "2.0.0", "2.0.0")
    _write_marketplace(marketplace_path, [_entry("alpha", "1.0.0"), _entry("beta", "2.0.0")])

    drifted = PARITY.check_parity(marketplace_path, plugins_dir)

    assert drifted == []
