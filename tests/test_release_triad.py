"""Tests for U15: release-triad sync guard (R17).

Asserts that the three version-bearing surfaces for every plugin stay in sync:

  1. ``plugins/<name>/.claude-plugin/plugin.json``  — ``"version"`` field
  2. ``.claude-plugin/marketplace.json``            — ``plugins[].version`` for the plugin
  3. ``plugins/<name>/CHANGELOG.md``               — first ``## <version>`` heading

When all three agree the triad is clean.  When any surface diverges the test
fails with a message that names the drifting surface and its version so the
author knows exactly which file to update.

Design notes
------------
- "Fires only on version-bearing changes" — the guard is a static assertion on
  the current on-disk state.  If all three surfaces agree, the guard passes
  (no false fire on a non-version-bearing edit).  If they disagree, someone
  bumped one surface and forgot the others — that is the failure this guard
  catches (R17).
- CHANGELOG version detection: we extract the first version heading that
  appears in the file.  We support the four heading formats used across this
  repo:
    - ``## [1.2.0] - 2026-06-21``    (home-lab-ops, unifi, team-execution, mission-control)
    - ``## [1.2.0] — 2026-06-21``    (em-dash variant)
    - ``## 0.1.2 - 2026-06-21``      (deploy, saga — bare version, hyphen-dash)
    - ``## 0.1.2 — 2026-06-21``      (bare version, em-dash)
    - ``## [Unreleased]``            (skipped — not a version marker)
  The first match wins; ``[Unreleased]`` headings are ignored.
- Parametrised by plugin name: failures are reported per-plugin, not as a
  single monolithic assertion.
"""

from __future__ import annotations

import json
import pathlib
import re

import pytest

REPO_ROOT = pathlib.Path(__file__).parent.parent
PLUGINS_ROOT = REPO_ROOT / "plugins"
MARKETPLACE_PATH = REPO_ROOT / ".claude-plugin" / "marketplace.json"


# All plugins registered in marketplace.json.  This list is derived from the
# marketplace itself so the test stays in lockstep without a hardcoded list.
def _plugin_names_from_marketplace() -> list[str]:
    data = json.loads(MARKETPLACE_PATH.read_text())
    return [p["name"] for p in data.get("plugins", [])]


ALL_PLUGINS: list[str] = _plugin_names_from_marketplace()

# ---------------------------------------------------------------------------
# Parsers
# ---------------------------------------------------------------------------

_CHANGELOG_VERSION_RE = re.compile(
    r"^##\s+"
    r"(?:\[)?"  # optional opening bracket
    r"(?!Unreleased)"  # skip [Unreleased] headings
    r"(\d+\.\d+\.\d+)"  # capture semver X.Y.Z
    r"(?:\])?"  # optional closing bracket
    r"(?:\s*[-—].*)?$",  # optional date suffix (hyphen or em-dash)
    re.MULTILINE,
)


def _version_from_plugin_json(plugin_name: str) -> str | None:
    """Return the ``version`` field from ``plugins/<name>/.claude-plugin/plugin.json``."""
    path = PLUGINS_ROOT / plugin_name / ".claude-plugin" / "plugin.json"
    if not path.exists():
        return None
    data: dict[str, object] = json.loads(path.read_text())
    v = data.get("version")
    return str(v) if v is not None else None


def _version_from_marketplace(plugin_name: str) -> str | None:
    """Return this plugin's ``version`` from ``.claude-plugin/marketplace.json``."""
    data: dict[str, list[dict[str, str]]] = json.loads(MARKETPLACE_PATH.read_text())
    for entry in data.get("plugins", []):
        if entry.get("name") == plugin_name:
            v = entry.get("version")
            return v if v is not None else None
    return None


def _version_from_changelog(plugin_name: str) -> str | None:
    """Return the first released version heading found in the plugin CHANGELOG.

    ``## [Unreleased]`` headings are skipped.  Returns ``None`` if the file
    does not exist or contains no recognised version heading.
    """
    path = PLUGINS_ROOT / plugin_name / "CHANGELOG.md"
    if not path.exists():
        return None
    text = path.read_text()
    m = _CHANGELOG_VERSION_RE.search(text)
    if m:
        return m.group(1)
    return None


# ---------------------------------------------------------------------------
# Helper: build a human-readable drift report
# ---------------------------------------------------------------------------


def _drift_message(
    plugin: str, plugin_json_ver: str | None, mkt_ver: str | None, cl_ver: str | None
) -> str:
    lines = [f"Release-triad mismatch for plugin '{plugin}':"]
    lines.append(f"  plugin.json                : {plugin_json_ver!r}")
    lines.append(f"  marketplace.json           : {mkt_ver!r}")
    lines.append(f"  CHANGELOG.md (first release): {cl_ver!r}")
    drifters = []
    canonical = plugin_json_ver  # plugin.json is the ground-truth source of truth
    if mkt_ver != canonical:
        drifters.append(f"marketplace.json (has {mkt_ver!r}, expected {canonical!r})")
    if cl_ver != canonical:
        drifters.append(f"CHANGELOG.md (has {cl_ver!r}, expected {canonical!r})")
    if drifters:
        lines.append("  Drifting surface(s): " + "; ".join(drifters))
    lines.append(
        "  Fix: bump all three surfaces to the same version in the same commit (CLAUDE.md §6)."
    )
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("plugin_name", ALL_PLUGINS)
def test_plugin_json_exists(plugin_name: str) -> None:
    """Every registered plugin must have a plugin.json at the canonical path."""
    path = PLUGINS_ROOT / plugin_name / ".claude-plugin" / "plugin.json"
    assert path.exists(), (
        f"plugin.json missing for '{plugin_name}' at {path}. "
        "Create it with a 'version' field matching the marketplace entry."
    )


@pytest.mark.parametrize("plugin_name", ALL_PLUGINS)
def test_changelog_exists(plugin_name: str) -> None:
    """Every registered plugin must have a CHANGELOG.md."""
    path = PLUGINS_ROOT / plugin_name / "CHANGELOG.md"
    assert path.exists(), (
        f"CHANGELOG.md missing for '{plugin_name}' at {path}. "
        "Create it with a versioned heading matching plugin.json."
    )


@pytest.mark.parametrize("plugin_name", ALL_PLUGINS)
def test_release_triad_in_sync(plugin_name: str) -> None:
    """plugin.json, marketplace.json, and CHANGELOG.md must all agree on version.

    Fires only when at least one surface disagrees — a clean triad always passes.
    """
    pjson_ver = _version_from_plugin_json(plugin_name)
    mkt_ver = _version_from_marketplace(plugin_name)
    cl_ver = _version_from_changelog(plugin_name)

    assert pjson_ver is not None, f"'{plugin_name}' plugin.json has no 'version' field."
    assert mkt_ver is not None, f"'{plugin_name}' not found in marketplace.json plugins array."
    assert cl_ver is not None, (
        f"'{plugin_name}' CHANGELOG.md has no recognised version heading. "
        "Add a heading like '## [X.Y.Z] - YYYY-MM-DD' or '## X.Y.Z - YYYY-MM-DD'."
    )

    all_agree = pjson_ver == mkt_ver == cl_ver
    assert all_agree, _drift_message(plugin_name, pjson_ver, mkt_ver, cl_ver)


# ---------------------------------------------------------------------------
# Seed-mismatch fixtures: verify the guard actually catches drift
# ---------------------------------------------------------------------------


def test_guard_catches_marketplace_drift(tmp_path: pathlib.Path) -> None:
    """Seeded mismatch: marketplace.json has a wrong version → guard fires."""
    # Build a minimal triad
    plugin_dir = tmp_path / "plugins" / "myplugin" / ".claude-plugin"
    plugin_dir.mkdir(parents=True)
    (plugin_dir / "plugin.json").write_text(json.dumps({"name": "myplugin", "version": "1.0.0"}))

    changelog = tmp_path / "plugins" / "myplugin" / "CHANGELOG.md"
    changelog.write_text("# Changelog\n\n## [1.0.0] - 2026-01-01\n\n- initial release\n")

    mkt_path = tmp_path / ".claude-plugin" / "marketplace.json"
    mkt_path.parent.mkdir(parents=True)
    mkt_path.write_text(
        json.dumps(
            {
                "plugins": [{"name": "myplugin", "version": "0.9.0"}]  # wrong — should be 1.0.0
            }
        )
    )

    # Parse directly using the module's helpers, pointing at tmp_path
    pjson = json.loads((plugin_dir / "plugin.json").read_text()).get("version")
    mkt_data = json.loads(mkt_path.read_text())
    mkt_ver = next((p["version"] for p in mkt_data["plugins"] if p["name"] == "myplugin"), None)
    cl_text = changelog.read_text()
    cl_m = _CHANGELOG_VERSION_RE.search(cl_text)
    cl_ver = cl_m.group(1) if cl_m else None

    assert pjson == "1.0.0"
    assert cl_ver == "1.0.0"
    # The mismatch: mkt_ver should differ
    assert mkt_ver == "0.9.0"
    assert mkt_ver != pjson, "test setup: marketplace version should be wrong"
    # The guard condition that test_release_triad_in_sync would trigger
    all_agree = pjson == mkt_ver == cl_ver
    assert not all_agree, "Seeded mismatch was not detected — guard logic is broken."


def test_guard_catches_changelog_drift(tmp_path: pathlib.Path) -> None:
    """Seeded mismatch: CHANGELOG.md has a stale version → guard fires."""
    plugin_dir = tmp_path / "plugins" / "myplugin" / ".claude-plugin"
    plugin_dir.mkdir(parents=True)
    (plugin_dir / "plugin.json").write_text(json.dumps({"name": "myplugin", "version": "2.0.0"}))

    changelog = tmp_path / "plugins" / "myplugin" / "CHANGELOG.md"
    changelog.write_text("# Changelog\n\n## [1.9.0] - 2025-12-01\n\n- old release\n")  # stale

    mkt_path = tmp_path / ".claude-plugin" / "marketplace.json"
    mkt_path.parent.mkdir(parents=True)
    mkt_path.write_text(json.dumps({"plugins": [{"name": "myplugin", "version": "2.0.0"}]}))

    pjson = json.loads((plugin_dir / "plugin.json").read_text()).get("version")
    mkt_data = json.loads(mkt_path.read_text())
    mkt_ver = next((p["version"] for p in mkt_data["plugins"] if p["name"] == "myplugin"), None)
    cl_text = changelog.read_text()
    cl_m = _CHANGELOG_VERSION_RE.search(cl_text)
    cl_ver = cl_m.group(1) if cl_m else None

    assert pjson == "2.0.0"
    assert mkt_ver == "2.0.0"
    assert cl_ver == "1.9.0"  # stale
    all_agree = pjson == mkt_ver == cl_ver
    assert not all_agree, "Seeded changelog mismatch was not detected — guard logic is broken."


def test_guard_passes_on_synced_triad(tmp_path: pathlib.Path) -> None:
    """All three surfaces agree → guard does not fire."""
    plugin_dir = tmp_path / "plugins" / "myplugin" / ".claude-plugin"
    plugin_dir.mkdir(parents=True)
    (plugin_dir / "plugin.json").write_text(json.dumps({"name": "myplugin", "version": "3.1.0"}))

    changelog = tmp_path / "plugins" / "myplugin" / "CHANGELOG.md"
    changelog.write_text("# Changelog\n\n## [3.1.0] - 2026-06-21\n\n- synced release\n")

    mkt_path = tmp_path / ".claude-plugin" / "marketplace.json"
    mkt_path.parent.mkdir(parents=True)
    mkt_path.write_text(json.dumps({"plugins": [{"name": "myplugin", "version": "3.1.0"}]}))

    pjson = json.loads((plugin_dir / "plugin.json").read_text()).get("version")
    mkt_data = json.loads(mkt_path.read_text())
    mkt_ver = next((p["version"] for p in mkt_data["plugins"] if p["name"] == "myplugin"), None)
    cl_text = changelog.read_text()
    cl_m = _CHANGELOG_VERSION_RE.search(cl_text)
    cl_ver = cl_m.group(1) if cl_m else None

    assert pjson == "3.1.0"
    assert mkt_ver == "3.1.0"
    assert cl_ver == "3.1.0"
    all_agree = pjson == mkt_ver == cl_ver
    assert all_agree, (
        f"Synced triad was incorrectly flagged as drifting: "
        f"plugin.json={pjson!r}, marketplace={mkt_ver!r}, CHANGELOG={cl_ver!r}"
    )


def test_changelog_version_regex_bare_format() -> None:
    """Regex matches the bare-version format used by saga and deploy CHANGELOGs."""
    text = "# Changelog\n\n## 0.30.0 - 2026-06-21\n\n- some entry\n"
    m = _CHANGELOG_VERSION_RE.search(text)
    assert m is not None, "Regex did not match bare-version CHANGELOG heading."
    assert m.group(1) == "0.30.0"


def test_changelog_version_regex_bracketed_format() -> None:
    """Regex matches the bracketed format used by home-lab-ops, unifi, etc."""
    text = "# Changelog\n\n## [1.2.0] - 2026-06-21\n\n### Changed\n"
    m = _CHANGELOG_VERSION_RE.search(text)
    assert m is not None, "Regex did not match bracketed CHANGELOG heading."
    assert m.group(1) == "1.2.0"


def test_changelog_version_regex_skips_unreleased() -> None:
    """Regex skips [Unreleased] and finds the first actual version below it."""
    text = (
        "# Changelog\n\n"
        "## [Unreleased]\n\n"
        "### Added — some future thing\n\n"
        "## [0.5.0] - 2026-06-01\n\n"
        "- shipped\n"
    )
    m = _CHANGELOG_VERSION_RE.search(text)
    assert m is not None, "Regex did not find a version after [Unreleased]."
    assert m.group(1) == "0.5.0"


def test_changelog_version_regex_em_dash_format() -> None:
    """Regex matches em-dash date separator (used in mission-control CHANGELOG)."""
    text = "# Changelog\n\n## [2.2.0] — 2026-06-21\n\n### Changed\n"
    m = _CHANGELOG_VERSION_RE.search(text)
    assert m is not None, "Regex did not match em-dash CHANGELOG heading."
    assert m.group(1) == "2.2.0"


def test_drift_message_names_drifting_surface() -> None:
    """_drift_message names the specific surface(s) that are out of sync."""
    msg = _drift_message("saga", "0.30.0", "0.29.0", "0.30.0")
    assert "marketplace.json" in msg
    assert "0.29.0" in msg
    assert "Drifting surface" in msg
    # CHANGELOG agrees — should not be flagged
    assert "CHANGELOG" not in msg.split("Drifting")[1]


def test_drift_message_both_surfaces_named() -> None:
    """When two surfaces drift, both are named in the drift message."""
    msg = _drift_message("deploy", "0.1.2", "0.1.0", "0.1.1")
    assert "marketplace.json" in msg
    assert "CHANGELOG.md" in msg
