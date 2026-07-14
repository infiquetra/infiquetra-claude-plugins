"""Fleet-commons resolution shim + canonical tier palette (issue #463, U1/U2).

Oracles pinned here:

* palette — content and ordering match the canonical fleet-core contract
  (strongest-first models, weakest-first efforts — ``{#tier-vocab-ordering}``); rank helpers
  raise on unknown values.
* ladder — one test per rung (env override, repo walk-up, installed_plugins.json, cache-sibling
  highest-semver), fail-loud with an actionable message when nothing resolves, malformed
  registry falls through instead of crashing, and an explicit-but-wrong env override raises.
* vendoring — every vendored shim copy is byte-identical to the canonical fleet-core file.
"""

from __future__ import annotations

import importlib.util
import json
import shutil
import sys
from pathlib import Path
from types import ModuleType

import pytest

ROOT = Path(__file__).parent.parent
CANONICAL_SHIM = ROOT / "plugins" / "fleet-core" / "scripts" / "fleet_commons_shim.py"
VENDORED_SHIMS = (
    ROOT / "plugins" / "saga" / "scripts" / "fleet_commons_shim.py",
    ROOT / "plugins" / "mission-control" / "scripts" / "fleet_commons_shim.py",
    ROOT / "plugins" / "unifi" / "skills" / "unifi-network" / "scripts" / "fleet_commons_shim.py",
    ROOT / "plugins" / "unifi" / "skills" / "unifi-protect" / "scripts" / "fleet_commons_shim.py",
    ROOT / "plugins" / "agy" / "scripts" / "fleet_commons_shim.py",
    ROOT / "plugins" / "codex" / "scripts" / "fleet_commons_shim.py",
    # #380: team-execution's Step B1 posture check loads intent_envelope through the shim.
    ROOT
    / "plugins"
    / "team-execution"
    / "skills"
    / "team-execution"
    / "scripts"
    / "fleet_commons_shim.py",
)

_LOAD_COUNTER = 0


def _load_shim(path: Path) -> ModuleType:
    """Load a shim file under a unique module name so per-test copies never collide."""
    global _LOAD_COUNTER
    _LOAD_COUNTER += 1
    spec = importlib.util.spec_from_file_location(f"_shim_under_test_{_LOAD_COUNTER}", path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _make_fleet_core_root(base: Path, *, version: str = "0.1.0", marker: str = "real") -> Path:
    """Build a minimal valid fleet-core root under ``base`` and return it."""
    root = base
    (root / "scripts" / "fleet_commons").mkdir(parents=True)
    (root / ".claude-plugin").mkdir()
    (root / ".claude-plugin" / "plugin.json").write_text(
        json.dumps({"name": "fleet-core", "version": version})
    )
    (root / "scripts" / "fleet_commons" / "tier_palette.py").write_text(
        f'MARKER = "{marker}"\nMODELS = ("fable", "opus", "sonnet", "haiku")\n'
    )
    return root


@pytest.fixture()
def clean_env(monkeypatch: pytest.MonkeyPatch) -> pytest.MonkeyPatch:
    """Scrub every environment surface the ladder reads, and the load() module cache."""
    for var in ("FLEET_COMMONS_ROOT", "FLEET_COMMONS_DEBUG", "CLAUDE_PLUGIN_ROOT"):
        monkeypatch.delenv(var, raising=False)
    for key in [k for k in sys.modules if k.startswith("_fleet_commons_")]:
        monkeypatch.delitem(sys.modules, key)
    return monkeypatch


@pytest.fixture()
def outside_shim(tmp_path: Path, clean_env: pytest.MonkeyPatch) -> ModuleType:
    """A shim copy living outside any repo checkout, with HOME pointed at an empty tmp home."""
    shim_path = tmp_path / "elsewhere" / "fleet_commons_shim.py"
    shim_path.parent.mkdir(parents=True)
    shutil.copy2(CANONICAL_SHIM, shim_path)
    fake_home = tmp_path / "home"
    fake_home.mkdir()
    clean_env.setenv("HOME", str(fake_home))
    return _load_shim(shim_path)


# --- canonical tier palette -----------------------------------------------------------------


def test_palette_content_and_ordering_match_canonical_contract(
    clean_env: pytest.MonkeyPatch,
) -> None:
    clean_env.setenv("FLEET_COMMONS_ROOT", str(ROOT / "plugins" / "fleet-core"))
    palette = _load_shim(CANONICAL_SHIM).load("tier_palette")
    assert palette.MODELS == ("fable", "opus", "sonnet", "haiku")
    assert palette.EFFORTS == ("low", "medium", "high", "xhigh")
    assert palette.CHEAP_MODELS == ("haiku",)
    assert palette.ENGINE_INTENTS == ("offload", "second-opinion", "divergence")


def test_rank_helpers_encode_the_ordering_contract(clean_env: pytest.MonkeyPatch) -> None:
    clean_env.setenv("FLEET_COMMONS_ROOT", str(ROOT / "plugins" / "fleet-core"))
    palette = _load_shim(CANONICAL_SHIM).load("tier_palette")
    assert palette.model_rank("fable") == 0  # strongest-first
    assert palette.model_rank("haiku") == len(palette.MODELS) - 1
    assert palette.effort_rank("low") == 0  # weakest-first
    assert palette.effort_rank("xhigh") == len(palette.EFFORTS) - 1
    with pytest.raises(ValueError, match="unknown model"):
        palette.model_rank("opus-high")
    with pytest.raises(ValueError, match="unknown effort"):
        palette.effort_rank("med")


# --- rung 1: env override -------------------------------------------------------------------


def test_rung1_env_override_wins(
    outside_shim: ModuleType, tmp_path: Path, clean_env: pytest.MonkeyPatch
) -> None:
    root = _make_fleet_core_root(tmp_path / "override-root")
    clean_env.setenv("FLEET_COMMONS_ROOT", str(root))
    assert outside_shim.resolve_root() == (root, 1)


def test_rung1_invalid_override_raises_instead_of_falling_through(
    outside_shim: ModuleType, tmp_path: Path, clean_env: pytest.MonkeyPatch
) -> None:
    clean_env.setenv("FLEET_COMMONS_ROOT", str(tmp_path / "not-a-root"))
    with pytest.raises(RuntimeError, match="FLEET_COMMONS_ROOT"):
        outside_shim.resolve_root()


# --- rung 2: repo walk-up -------------------------------------------------------------------


def test_rung2_repo_walkup_from_vendored_copy(clean_env: pytest.MonkeyPatch) -> None:
    shim = _load_shim(VENDORED_SHIMS[0])  # saga's vendored copy, inside this checkout
    root, rung = shim.resolve_root()
    assert rung == 2
    assert root == ROOT / "plugins" / "fleet-core"


def test_rung2_walkup_in_synthetic_checkout(tmp_path: Path, clean_env: pytest.MonkeyPatch) -> None:
    repo = tmp_path / "checkout"
    _make_fleet_core_root(repo / "plugins" / "fleet-core")
    (repo / ".claude-plugin").mkdir()
    (repo / ".claude-plugin" / "marketplace.json").write_text("{}")
    consumer_scripts = repo / "plugins" / "consumer" / "scripts"
    consumer_scripts.mkdir(parents=True)
    shutil.copy2(CANONICAL_SHIM, consumer_scripts / "fleet_commons_shim.py")
    clean_env.setenv("HOME", str(tmp_path / "empty-home"))
    shim = _load_shim(consumer_scripts / "fleet_commons_shim.py")
    assert shim.resolve_root() == (repo / "plugins" / "fleet-core", 2)


# --- rung 3: installed_plugins.json ---------------------------------------------------------


def _write_registry(home: Path, entries: dict[str, object]) -> None:
    plugins_dir = home / ".claude" / "plugins"
    plugins_dir.mkdir(parents=True, exist_ok=True)
    (plugins_dir / "installed_plugins.json").write_text(
        json.dumps({"version": 2, "plugins": entries})
    )


def test_rung3_installed_plugins_lookup_is_marketplace_agnostic(
    outside_shim: ModuleType, tmp_path: Path, clean_env: pytest.MonkeyPatch
) -> None:
    root = _make_fleet_core_root(tmp_path / "install" / "fleet-core" / "0.1.0")
    _write_registry(
        tmp_path / "home",
        {"fleet-core@some-renamed-marketplace": [{"installPath": str(root)}]},
    )
    assert outside_shim.resolve_root() == (root, 3)


def test_rung3_malformed_record_does_not_poison_valid_sibling(
    outside_shim: ModuleType, tmp_path: Path, clean_env: pytest.MonkeyPatch
) -> None:
    """Per-record tolerance: a non-dict record must be skipped, not abort the whole scan."""
    root = _make_fleet_core_root(tmp_path / "install" / "fleet-core" / "0.1.0")
    _write_registry(
        tmp_path / "home",
        {
            "fleet-core@mp": [
                "not-a-dict",
                {"scope": "user"},  # well-formed dict missing installPath
                {"installPath": str(root)},
            ]
        },
    )
    assert outside_shim.resolve_root() == (root, 3)


def test_rung3_malformed_registry_falls_through_not_crash(
    outside_shim: ModuleType, tmp_path: Path, clean_env: pytest.MonkeyPatch
) -> None:
    plugins_dir = tmp_path / "home" / ".claude" / "plugins"
    plugins_dir.mkdir(parents=True)
    (plugins_dir / "installed_plugins.json").write_text("{ this is not json")
    cache_root = _make_fleet_core_root(
        tmp_path / "cache" / "mp" / "fleet-core" / "0.1.0", marker="cache"
    )
    consumer = tmp_path / "cache" / "mp" / "consumer" / "1.0.0"
    consumer.mkdir(parents=True)
    clean_env.setenv("CLAUDE_PLUGIN_ROOT", str(consumer))
    assert outside_shim.resolve_root() == (cache_root, 4)


# --- rung 4: cache-sibling scan -------------------------------------------------------------


def test_rung4_cache_sibling_picks_highest_semver(
    outside_shim: ModuleType, tmp_path: Path, clean_env: pytest.MonkeyPatch
) -> None:
    cache = tmp_path / "cache" / "mp"
    _make_fleet_core_root(cache / "fleet-core" / "0.9.0", version="0.9.0")
    newest = _make_fleet_core_root(cache / "fleet-core" / "0.10.0", version="0.10.0")
    (cache / "fleet-core" / "not-a-version").mkdir()  # ignored: unparseable name
    consumer = cache / "consumer" / "1.0.0"
    consumer.mkdir(parents=True)
    clean_env.setenv("CLAUDE_PLUGIN_ROOT", str(consumer))
    assert outside_shim.resolve_root() == (newest, 4)


# --- rung 5: fail loud ----------------------------------------------------------------------


def test_fail_loud_with_actionable_message(outside_shim: ModuleType) -> None:
    with pytest.raises(RuntimeError, match="install the fleet-core plugin"):
        outside_shim.resolve_root()


# --- provenance + load() --------------------------------------------------------------------


def test_debug_env_prints_provenance_line_to_stderr(
    outside_shim: ModuleType,
    tmp_path: Path,
    clean_env: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    root = _make_fleet_core_root(tmp_path / "override-root")
    clean_env.setenv("FLEET_COMMONS_ROOT", str(root))
    clean_env.setenv("FLEET_COMMONS_DEBUG", "1")
    outside_shim.resolve_root()
    assert f"fleet-commons: rung=1 (env-override) root={root}" in capsys.readouterr().err


def test_load_returns_same_module_object_on_repeat(
    outside_shim: ModuleType, tmp_path: Path, clean_env: pytest.MonkeyPatch
) -> None:
    root = _make_fleet_core_root(tmp_path / "override-root", marker="fake")
    clean_env.setenv("FLEET_COMMONS_ROOT", str(root))
    first = outside_shim.load("tier_palette")
    assert first.MARKER == "fake"
    assert outside_shim.load("tier_palette") is first


def test_load_reresolves_when_root_changes_mid_process(
    outside_shim: ModuleType, tmp_path: Path, clean_env: pytest.MonkeyPatch
) -> None:
    """Cache is keyed by (module, root): re-pointing FLEET_COMMONS_ROOT must not serve stale."""
    first_root = _make_fleet_core_root(tmp_path / "root-a", marker="a")
    clean_env.setenv("FLEET_COMMONS_ROOT", str(first_root))
    first = outside_shim.load("tier_palette")
    assert first.MARKER == "a"
    second_root = _make_fleet_core_root(tmp_path / "root-b", marker="b")
    clean_env.setenv("FLEET_COMMONS_ROOT", str(second_root))
    second = outside_shim.load("tier_palette")
    assert second is not first
    assert second.MARKER == "b"


def test_load_missing_module_names_it_and_the_resolved_root(
    outside_shim: ModuleType, tmp_path: Path, clean_env: pytest.MonkeyPatch
) -> None:
    root = _make_fleet_core_root(tmp_path / "override-root")
    clean_env.setenv("FLEET_COMMONS_ROOT", str(root))
    with pytest.raises(RuntimeError, match="'no_such_primitive' not found"):
        outside_shim.load("no_such_primitive")


def test_resolved_version_reads_manifest(
    outside_shim: ModuleType, tmp_path: Path, clean_env: pytest.MonkeyPatch
) -> None:
    root = _make_fleet_core_root(tmp_path / "override-root", version="0.3.7")
    clean_env.setenv("FLEET_COMMONS_ROOT", str(root))
    assert outside_shim.resolved_version() == "0.3.7"


# --- vendoring drift guard ------------------------------------------------------------------


@pytest.mark.parametrize("vendored", VENDORED_SHIMS, ids=lambda p: p.parts[-3])
def test_vendored_shim_is_byte_identical_to_canonical(vendored: Path) -> None:
    assert vendored.read_bytes() == CANONICAL_SHIM.read_bytes(), (
        f"{vendored} has drifted from the canonical shim; "
        "re-copy plugins/fleet-core/scripts/fleet_commons_shim.py"
    )


# --- consumer 1: saga re-export seam (U3) ---------------------------------------------------


def test_saga_execution_spec_reexports_the_shim_loaded_palette_object() -> None:
    """``execution_spec.MODELS is`` the shim-loaded module's — an import, not a copy."""
    saga_scripts = ROOT / "plugins" / "saga" / "scripts"
    if str(saga_scripts) not in sys.path:
        sys.path.insert(0, str(saga_scripts))
    spec = importlib.util.spec_from_file_location(
        "execution_spec", saga_scripts / "execution_spec.py"
    )
    assert spec is not None and spec.loader is not None
    execution_spec = importlib.util.module_from_spec(spec)
    sys.modules["execution_spec"] = execution_spec
    spec.loader.exec_module(execution_spec)

    palette = _load_shim(saga_scripts / "fleet_commons_shim.py").load("tier_palette")
    assert execution_spec.MODELS is palette.MODELS
    assert execution_spec.EFFORTS is palette.EFFORTS
    assert execution_spec._CHEAP_MODELS is palette.CHEAP_MODELS
    assert execution_spec.ENGINE_INTENTS is palette.ENGINE_INTENTS
    # PASS_RULES deliberately stays saga-local (refute-N vocabulary, not tier vocabulary).
    assert execution_spec.PASS_RULES == ("majority", "unanimous")
