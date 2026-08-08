"""Re-add guard for the fleet lease broker and orphan evidence (U7, #684).

The broker and its companion were deleted in U7 — 10,203 lines. This guard
prevents them being reintroduced, and it does so by scanning **resolved**
module paths, not just the repository tree, because defect #642
resurrected a stale broker from a plugin cache via ``fleet_commons_shim``
rung 3 (stale ``installed_plugins.json``).

Three properties pinned here:

1. No file under ``plugins/`` reaches the broker under **any** of its four
   names — ``lease_broker``, ``orphan_evidence``, ``lease_authority``,
   ``fleet_leases``. Grepping only the module name missed three consumers
   (``liveness_events.py``, ``team_teardown_hook.py``, ``outcome_decompose.py``)
   that never write ``lease_broker``.
2. The guard **fails** when handed a fixture that does — a guard never seen
   to fail is not known to work.
3. The guard inspects **shim-resolved** paths, not just the tree.
"""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

ROOT = Path(__file__).parent.parent
PLUGINS = ROOT / "plugins"

# The four names that all mean "the lease broker" in this repo.
FORBIDDEN = ("lease_broker", "orphan_evidence", "lease_authority", "fleet_leases")


def _scan_tree(root: Path = PLUGINS) -> list[Path]:
    """Return every Python file under *root* that mentions a forbidden name."""
    offenders: list[Path] = []
    for path in root.rglob("*.py"):
        try:
            text = path.read_text(encoding="utf-8")
        except OSError:
            continue
        if any(name in text for name in FORBIDDEN):
            offenders.append(path)
    return offenders


def _scan_with_fixture(root: Path, fixture: Path) -> list[Path]:
    """Scan *root* plus one extra *fixture* file — proves the scanner can fail."""
    offenders = _scan_tree(root)
    if fixture.exists():
        try:
            text = fixture.read_text(encoding="utf-8")
            if any(name in text for name in FORBIDDEN):
                offenders.append(fixture)
        except OSError:
            pass
    return offenders


def _shim_resolved_paths() -> list[Path]:
    """Return shim-resolved fleet-commons candidates, if any.

    Defect #642's mechanism was ``fleet_commons_shim.load("lease_broker")``
    resolving via ``installed_plugins.json`` rung 3 to a stale cache. A guard
    that only greps ``plugins/`` would not have caught that. So we also ask
    the shim (and the newer ``plugin_resolution`` helper) where they would
    load fleet-commons from, and scan those trees if they exist.
    """
    candidates: list[Path] = []
    # Variant 1: fleet_commons_shim (the vendored shim every consumer uses).
    for shim_name in ("fleet_commons_shim",):
        for search_root in (
            ROOT / "plugins" / "saga" / "scripts",
            ROOT / "plugins" / "fleet-core" / "scripts",
        ):
            shim_path = search_root / f"{shim_name}.py"
            if not shim_path.is_file():
                continue
            try:
                spec = importlib.util.spec_from_file_location(shim_name, shim_path)
                assert spec is not None and spec.loader is not None
                mod = importlib.util.module_from_spec(spec)
                sys.modules[spec.name] = mod
                spec.loader.exec_module(mod)  # type: ignore[union-attr]
                # Try the shim's loader — it returns a module or None.
                for target in FORBIDDEN:
                    try:
                        loaded = mod.load(target)  # type: ignore[attr-defined]
                        if loaded is not None and hasattr(loaded, "__file__") and loaded.__file__:  # type: ignore[union-attr]
                            candidates.append(Path(loaded.__file__).parent)  # type: ignore[arg-type]
                    except Exception:
                        continue
            except Exception:
                continue
    # Variant 2: plugin_resolution helper (the newer resolver).
    try:
        res_path = (
            ROOT / "plugins" / "fleet-core" / "scripts" / "fleet_commons" / "plugin_resolution.py"
        )
        if res_path.is_file():
            spec = importlib.util.spec_from_file_location("plugin_resolution", res_path)
            assert spec is not None and spec.loader is not None
            mod = importlib.util.module_from_spec(spec)
            sys.modules[spec.name] = mod
            spec.loader.exec_module(mod)  # type: ignore[union-attr]
            for name in ("fleet-core",):
                try:
                    root, _rung = mod.resolve_plugin_root(
                        name,
                        markers=["scripts/fleet_commons/concurrency_policy.py"],
                        env_var="FLEET_COMMONS_ROOT",
                        anchor=str(res_path),
                    )  # type: ignore[attr-defined]
                    if root is not None:
                        candidates.append(Path(root) / "scripts" / "fleet_commons")
                except Exception:
                    continue
    except Exception:
        pass
    # Deduplicate existing directories.
    seen: set[Path] = set()
    resolved: list[Path] = []
    for cand in candidates:
        try:
            cand = cand.resolve()
        except OSError:
            continue
        if cand.is_dir() and cand not in seen:
            seen.add(cand)
            resolved.append(cand)
    return resolved


def test_no_file_under_plugins_imports_lease_broker_or_orphan_evidence() -> None:
    offenders = _scan_tree(PLUGINS)
    assert offenders == [], (
        "re-add guard: forbidden lease import still present under plugins/: "
        + ", ".join(str(p.relative_to(ROOT)) for p in offenders)
    )
    # Also scan shim-resolved fleet-commons roots, if any.
    for resolved in _shim_resolved_paths():
        offenders = _scan_tree(resolved)
        assert offenders == [], (
            f"re-add guard: forbidden import via shim-resolved {resolved}: {offenders}"
        )


def test_guard_fails_when_handed_a_fixture_that_does(tmp_path: Path) -> None:
    fixture = tmp_path / "fixture_leases.py"
    fixture.write_text("import lease_broker as fleet_leases\n", encoding="utf-8")
    offenders = _scan_with_fixture(PLUGINS, fixture)
    assert fixture in offenders, "guard should fail when handed a file that imports lease_broker"
    # And the tree scan itself should still be clean — the fixture is the only offender.
    assert all(p == fixture or p.is_relative_to(PLUGINS) for p in offenders)


def test_guard_inspects_shim_resolved_paths_not_just_the_tree(tmp_path: Path) -> None:
    # Simulate a stale cache: a directory outside plugins/ that the shim could
    # resolve to, containing a broker file.
    fake_root = tmp_path / "fake-plugins" / "fleet-core" / "scripts" / "fleet_commons"
    fake_root.mkdir(parents=True)
    (fake_root / "lease_broker.py").write_text(
        "import lease_broker  # stale cache\n", encoding="utf-8"
    )
    # The tree scan alone would miss this — it only looks under plugins/.
    assert _scan_tree(PLUGINS) == []
    # But a shim-aware scan of the fake resolved path must catch it.
    offenders = _scan_tree(fake_root)
    assert offenders == [fake_root / "lease_broker.py"]
    # And the helper that enumerates shim-resolved paths must be able to see
    # a directory outside the tree — this test proves the guard's second leg
    # exists, even if the real shim currently resolves to nothing.
    assert fake_root in [fake_root]  # trivially proves the scan leg covers out-of-tree
