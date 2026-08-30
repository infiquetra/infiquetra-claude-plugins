"""Cross-plugin resolution shim — cc-workflows finds Saga (review F16).

The ladder was shipped at twenty percent: only the repo-walk-up rung could ever run, and
no test executed it. These tests pop ``sys.modules`` and drive every rung plus the
all-miss failure, so a broken ladder fails a test instead of failing an operator's
installed plugin at run time.
"""

from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path
from types import ModuleType

import pytest

REPO_ROOT = Path(__file__).parent.parent
SHIM_PATH = (
    REPO_ROOT
    / "plugins"
    / "cc-workflows"
    / "skills"
    / "cc-workflows"
    / "scripts"
    / "saga_spec_shim.py"
)
REAL_SAGA_ROOT = REPO_ROOT / "plugins" / "saga"


def _load_shim() -> ModuleType:
    spec = importlib.util.spec_from_file_location("saga_spec_shim_under_test", SHIM_PATH)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules["saga_spec_shim_under_test"] = module
    spec.loader.exec_module(module)
    return module


@pytest.fixture
def shim() -> ModuleType:
    return _load_shim()


def _fake_saga_root(home: Path, name: str) -> Path:
    root = home / name
    scripts = root / "scripts"
    scripts.mkdir(parents=True)
    (scripts / "execution_spec.py").write_text("# fake saga spec module\n", encoding="utf-8")
    return root


@pytest.fixture
def clean_env(shim: ModuleType, monkeypatch: pytest.MonkeyPatch) -> None:
    # Neither override in play unless a test sets it.
    monkeypatch.delenv("SAGA_SPEC_ROOT", raising=False)
    monkeypatch.delenv("CLAUDE_PLUGIN_ROOT", raising=False)
    monkeypatch.delenv("SAGA_SPEC_DEBUG", raising=False)


def test_rung_one_env_override_wins_and_invalid_raises(
    shim: ModuleType, clean_env: None, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    root = _fake_saga_root(tmp_path, "saga-env")
    monkeypatch.setenv("SAGA_SPEC_ROOT", str(root))
    resolved, rung = shim.resolve_root()
    assert resolved == root
    assert rung == 1

    monkeypatch.setenv("SAGA_SPEC_ROOT", str(tmp_path / "not-a-saga-root"))
    with pytest.raises(RuntimeError, match="SAGA_SPEC_ROOT"):
        shim.resolve_root()


def test_rung_two_repo_walk_up_from_the_shipped_shim(shim: ModuleType, clean_env: None) -> None:
    # The real shim file sits under the repo checkout, so the walk-up finds the real
    # saga plugin — no env override, no registry.
    resolved, rung = shim.resolve_root()
    assert resolved == REAL_SAGA_ROOT
    assert rung == 2


def test_rung_three_installed_plugins_registry(
    shim: ModuleType, clean_env: None, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    # Walk-up must miss: pretend the shim lives where no ancestor carries the
    # marketplace marker.
    monkeypatch.setattr(shim, "__file__", str(tmp_path / "nowhere" / "saga_spec_shim.py"))

    home = tmp_path / "home"
    saga_root = _fake_saga_root(tmp_path, "saga-installed")
    registry_dir = home / ".claude" / "plugins"
    registry_dir.mkdir(parents=True)
    (registry_dir / "installed_plugins.json").write_text(
        json.dumps(
            {
                "version": 2,
                "plugins": {
                    "cc-workflows@infiquetra-plugins": [
                        {"installPath": str(tmp_path / "unrelated")}
                    ],
                    "saga@infiquetra-plugins": [{"installPath": str(saga_root)}],
                    # A malformed record must not poison the scan.
                    "saga@broken": [{"no_install_path": True}, "not-a-dict"],
                },
            }
        ),
        encoding="utf-8",
    )
    monkeypatch.setattr(Path, "home", staticmethod(lambda: home))

    resolved, rung = shim.resolve_root()
    assert resolved == saga_root
    assert rung == 3


def test_rung_four_cache_sibling_semver_scan(
    shim: ModuleType, clean_env: None, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(shim, "__file__", str(tmp_path / "nowhere" / "saga_spec_shim.py"))
    # Empty home: the registry rung misses cleanly.
    monkeypatch.setattr(Path, "home", staticmethod(lambda: tmp_path / "empty-home"))

    plugins_cache = tmp_path / "cache" / "plugins"
    for version in ("0.9.0", "1.2.3", "not-a-semver"):
        root = plugins_cache / "saga" / version
        scripts = root / "scripts"
        scripts.mkdir(parents=True)
        if version != "not-a-semver":
            (scripts / "execution_spec.py").write_text("# fake\n", encoding="utf-8")
    monkeypatch.setenv(
        "CLAUDE_PLUGIN_ROOT", str(plugins_cache / "cc-workflows@infiquetra-plugins" / "1.0.0")
    )
    (plugins_cache / "cc-workflows@infiquetra-plugins" / "1.0.0").mkdir(parents=True)

    resolved, rung = shim.resolve_root()
    # The highest semver wins.
    assert resolved == plugins_cache / "saga" / "1.2.3"
    assert rung == 4


def test_all_rungs_miss_fails_loud_with_an_actionable_message(
    shim: ModuleType, clean_env: None, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(shim, "__file__", str(tmp_path / "nowhere" / "saga_spec_shim.py"))
    monkeypatch.setattr(Path, "home", staticmethod(lambda: tmp_path / "empty-home"))

    with pytest.raises(RuntimeError, match="could not resolve a saga plugin root"):
        shim.resolve_root()


def test_load_execution_spec_reuses_the_canonical_module(
    shim: ModuleType, clean_env: None, monkeypatch: pytest.MonkeyPatch
) -> None:
    sentinel = object()
    monkeypatch.setitem(sys.modules, "execution_spec", sentinel)
    assert shim.load_execution_spec() is sentinel


def test_load_execution_spec_loads_the_real_schema_when_no_module_is_cached(
    shim: ModuleType, clean_env: None, monkeypatch: pytest.MonkeyPatch
) -> None:
    # Pop the canonical entry so the shim must resolve and load for real.
    monkeypatch.delitem(sys.modules, "execution_spec", raising=False)
    module = shim.load_execution_spec()
    assert module is sys.modules["execution_spec"]
    # It is Saga's spec schema, not a stub: the seam's own entry point is present.
    assert hasattr(module, "emit_workflow_script")
    assert hasattr(module, "ExecutionSpec")
