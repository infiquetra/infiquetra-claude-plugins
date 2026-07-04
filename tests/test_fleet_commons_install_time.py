"""Install-time fleet-commons resolution (issue #463, U5 / AC4).

Rebuilds the *observed* marketplace install layout under ``tmp_path`` — bare per-plugin
per-version file copies under ``<home>/.claude/plugins/cache/<marketplace>/<plugin>/<version>/``
plus an ``installed_plugins.json`` registry (schema ``version: 2``) — and runs mission-control's
executor-profile lint end to end in a subprocess with ``HOME`` pointed at the fake home, cwd
outside the repo, and a scrubbed ``PYTHONPATH``.

The load-bearing assertion is rung *provenance*, not import success: the shim's
``FLEET_COMMONS_DEBUG=1`` stderr line must report rung 3 (``installed-plugins``) — proving the
monorepo ``sys.path`` convenience (rung 2 walk-up) was NOT the path taken, which is the trap
this test exists to close.
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).parent.parent
MARKETPLACE = "infiquetra-plugins"

_VALID_BODY = """\
### Recommended Executor Profile
- **Model:** opus
- **Effort:** medium
- **Backend:** inline
- **Justification (required — profile is above sonnet):** architectural decision.
"""


def _install_plugin(cache: Path, plugin: str, version: str, *, parts: tuple[str, ...]) -> Path:
    """Bare-copy the named subtrees of a repo plugin into the fake cache, as observed live."""
    destination = cache / plugin / version
    for part in parts:
        source = ROOT / "plugins" / plugin / part
        shutil.copytree(source, destination / part)
    return destination


def _build_fake_home(
    tmp_path: Path, *, with_fleet_core: bool = True, decoy_version: str | None = None
) -> tuple[Path, Path]:
    """Fake install root; returns ``(fake_home, mission_control_install)``."""
    fake_home = tmp_path / "home"
    cache = fake_home / ".claude" / "plugins" / "cache" / MARKETPLACE
    cache.mkdir(parents=True)

    mission_control = _install_plugin(
        cache, "mission-control", "2.5.0", parts=(".claude-plugin", "scripts")
    )
    registry: dict[str, list[dict[str, str]]] = {
        f"mission-control@{MARKETPLACE}": [{"installPath": str(mission_control)}]
    }
    if with_fleet_core:
        fleet_core = _install_plugin(
            cache, "fleet-core", "0.1.0", parts=(".claude-plugin", "scripts")
        )
        registry[f"fleet-core@{MARKETPLACE}"] = [{"installPath": str(fleet_core)}]
    if decoy_version is not None:
        decoy = _install_plugin(
            cache, "fleet-core", decoy_version, parts=(".claude-plugin", "scripts")
        )
        manifest = decoy / ".claude-plugin" / "plugin.json"
        manifest.write_text(json.dumps({"name": "fleet-core", "version": decoy_version}))

    (fake_home / ".claude" / "plugins" / "installed_plugins.json").write_text(
        json.dumps({"version": 2, "plugins": registry})
    )
    return fake_home, mission_control


def _run_lint(
    fake_home: Path, mission_control: Path, tmp_path: Path
) -> subprocess.CompletedProcess[str]:
    body_file = tmp_path / "body.md"
    body_file.write_text(_VALID_BODY)
    env = {
        "HOME": str(fake_home),
        "PATH": os.environ.get("PATH", ""),
        "FLEET_COMMONS_DEBUG": "1",
        # Deliberately absent: PYTHONPATH, FLEET_COMMONS_ROOT, CLAUDE_PLUGIN_ROOT — only the
        # installed_plugins.json registry may make resolution succeed.
    }
    return subprocess.run(
        [
            sys.executable,
            str(mission_control / "scripts" / "executor_profile_lint.py"),
            "--body-file",
            str(body_file),
        ],
        capture_output=True,
        text=True,
        env=env,
        cwd=str(tmp_path),  # outside the repo working tree
        timeout=60,
    )


def test_lint_resolves_palette_via_installed_plugins_registry(tmp_path: Path) -> None:
    fake_home, mission_control = _build_fake_home(tmp_path)
    result = _run_lint(fake_home, mission_control, tmp_path)
    assert result.returncode == 0, (result.stdout, result.stderr)
    assert "executor-profile-lint: ok (model=opus effort=medium)" in result.stdout
    assert "fleet-commons: rung=3 (installed-plugins)" in result.stderr
    assert "rung=2" not in result.stderr  # the monorepo walk-up was NOT the path taken


def test_missing_fleet_core_fails_loud_with_actionable_message(tmp_path: Path) -> None:
    fake_home, mission_control = _build_fake_home(tmp_path, with_fleet_core=False)
    result = _run_lint(fake_home, mission_control, tmp_path)
    assert result.returncode != 0
    assert "install the fleet-core plugin" in result.stderr


def test_version_skew_registry_pin_beats_newer_cache_decoy(tmp_path: Path) -> None:
    """Cache holds 0.1.0 and a decoy 0.2.0; the registry pins 0.1.0 — the pin must win."""
    fake_home, mission_control = _build_fake_home(tmp_path, decoy_version="0.2.0")
    result = _run_lint(fake_home, mission_control, tmp_path)
    assert result.returncode == 0, (result.stdout, result.stderr)
    assert "fleet-commons: rung=3 (installed-plugins)" in result.stderr
    provenance = [line for line in result.stderr.splitlines() if line.startswith("fleet-commons:")]
    assert provenance and provenance[0].endswith(f"{os.sep}fleet-core{os.sep}0.1.0")
