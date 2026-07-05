"""Tests for scripts/sync_marketplace.py (#429)."""

import importlib.util
import json
import sys
from pathlib import Path

import pytest

_SPEC = importlib.util.spec_from_file_location(
    "sync_marketplace", Path(__file__).parent.parent / "scripts" / "sync_marketplace.py"
)
assert _SPEC is not None and _SPEC.loader is not None
SM = importlib.util.module_from_spec(_SPEC)
sys.modules["sync_marketplace"] = SM
_SPEC.loader.exec_module(SM)


def _write_plugin(plugins_dir: Path, name: str, version: str, keywords: list[str]) -> None:
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
                "keywords": keywords,
            }
        )
    )


def _write_marketplace(path: Path, plugins: list[dict]) -> None:
    path.write_text(
        json.dumps(
            {
                "name": "infiquetra-plugins",
                "owner": {"name": "Infiquetra", "email": "hello@infiquetra.com"},
                "metadata": {"description": "x", "version": "3.0.0", "pluginRoot": "./plugins"},
                "plugins": plugins,
            }
        )
    )


@pytest.fixture
def fixture_tree(tmp_path):
    plugins_dir = tmp_path / "plugins"
    plugins_dir.mkdir()
    marketplace_path = tmp_path / "marketplace.json"
    return plugins_dir, marketplace_path


def test_generates_entry_from_plugin_json(fixture_tree):
    plugins_dir, marketplace_path = fixture_tree
    _write_plugin(plugins_dir, "alpha", "1.0.0", ["a", "b"])
    _write_marketplace(marketplace_path, [])

    marketplace = SM.load_json(marketplace_path)
    entries = SM.build_target_plugins(marketplace, plugins_dir, category_override="tools")

    assert len(entries) == 1
    entry = entries[0]
    assert entry["name"] == "alpha"
    assert entry["version"] == "1.0.0"
    assert entry["description"] == "alpha plugin"
    assert entry["author"] == {"name": "Infiquetra", "email": "hello@infiquetra.com"}
    assert entry["keywords"] == ["a", "b"]


def test_check_reds_on_stale_marketplace(fixture_tree, capsys):
    plugins_dir, marketplace_path = fixture_tree
    _write_plugin(plugins_dir, "alpha", "2.0.0", ["a"])
    _write_marketplace(
        marketplace_path,
        [
            {
                "name": "alpha",
                "source": "./plugins/alpha",
                "version": "1.0.0",
                "description": "alpha plugin",
                "author": {"name": "Infiquetra", "email": "hello@infiquetra.com"},
                "repository": "https://github.com/infiquetra/infiquetra-claude-plugins",
                "license": "MIT",
                "keywords": ["a"],
                "category": "tools",
            }
        ],
    )

    rc = SM.run(
        check=True,
        category_override=None,
        marketplace_path=marketplace_path,
        plugins_dir=plugins_dir,
    )

    assert rc == 1
    assert "alpha" in capsys.readouterr().err


def test_check_green_after_regenerate(fixture_tree):
    plugins_dir, marketplace_path = fixture_tree
    _write_plugin(plugins_dir, "alpha", "2.0.0", ["a"])
    _write_marketplace(
        marketplace_path,
        [
            {
                "name": "alpha",
                "source": "./plugins/alpha",
                "version": "1.0.0",
                "description": "alpha plugin",
                "author": {"name": "Infiquetra", "email": "hello@infiquetra.com"},
                "repository": "https://github.com/infiquetra/infiquetra-claude-plugins",
                "license": "MIT",
                "keywords": ["a"],
                "category": "tools",
            }
        ],
    )

    write_rc = SM.run(
        check=False,
        category_override=None,
        marketplace_path=marketplace_path,
        plugins_dir=plugins_dir,
    )
    check_rc = SM.run(
        check=True,
        category_override=None,
        marketplace_path=marketplace_path,
        plugins_dir=plugins_dir,
    )

    assert write_rc == 0
    assert check_rc == 0


def test_preserves_license_and_category_on_regenerate(fixture_tree):
    plugins_dir, marketplace_path = fixture_tree
    _write_plugin(plugins_dir, "alpha", "1.0.1", ["a"])
    _write_marketplace(
        marketplace_path,
        [
            {
                "name": "alpha",
                "source": "./plugins/alpha",
                "version": "1.0.0",
                "description": "alpha plugin",
                "author": {"name": "Infiquetra", "email": "hello@infiquetra.com"},
                "repository": "https://github.com/infiquetra/infiquetra-claude-plugins",
                "license": "Apache-2.0",
                "keywords": ["a"],
                "category": "infrastructure",
            }
        ],
    )

    marketplace = SM.load_json(marketplace_path)
    entries = SM.build_target_plugins(marketplace, plugins_dir)

    assert entries[0]["license"] == "Apache-2.0"
    assert entries[0]["category"] == "infrastructure"


def test_new_plugin_without_category_flag_fails_loudly(fixture_tree, capsys):
    plugins_dir, marketplace_path = fixture_tree
    _write_plugin(plugins_dir, "alpha", "1.0.0", ["a"])
    _write_marketplace(marketplace_path, [])

    rc = SM.run(
        check=False,
        category_override=None,
        marketplace_path=marketplace_path,
        plugins_dir=plugins_dir,
    )

    assert rc == 1
    assert "category" in capsys.readouterr().err


def test_preserves_existing_entry_order(fixture_tree):
    plugins_dir, marketplace_path = fixture_tree
    _write_plugin(plugins_dir, "zeta", "1.0.0", ["z"])
    _write_plugin(plugins_dir, "alpha", "1.0.1", ["a"])
    _write_plugin(plugins_dir, "mu", "1.0.0", ["m"])
    _write_marketplace(
        marketplace_path,
        [
            {
                "name": "zeta",
                "source": "./plugins/zeta",
                "version": "1.0.0",
                "description": "zeta plugin",
                "author": {"name": "Infiquetra", "email": "hello@infiquetra.com"},
                "repository": "https://github.com/infiquetra/infiquetra-claude-plugins",
                "license": "MIT",
                "keywords": ["z"],
                "category": "tools",
            },
            {
                "name": "alpha",
                "source": "./plugins/alpha",
                "version": "1.0.0",
                "description": "alpha plugin",
                "author": {"name": "Infiquetra", "email": "hello@infiquetra.com"},
                "repository": "https://github.com/infiquetra/infiquetra-claude-plugins",
                "license": "MIT",
                "keywords": ["a"],
                "category": "tools",
            },
            {
                "name": "mu",
                "source": "./plugins/mu",
                "version": "1.0.0",
                "description": "mu plugin",
                "author": {"name": "Infiquetra", "email": "hello@infiquetra.com"},
                "repository": "https://github.com/infiquetra/infiquetra-claude-plugins",
                "license": "MIT",
                "keywords": ["m"],
                "category": "tools",
            },
        ],
    )

    marketplace = SM.load_json(marketplace_path)
    entries = SM.build_target_plugins(marketplace, plugins_dir)

    assert [e["name"] for e in entries] == ["zeta", "alpha", "mu"]
    assert entries[1]["version"] == "1.0.1"
