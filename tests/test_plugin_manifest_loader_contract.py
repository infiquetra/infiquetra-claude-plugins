"""Packaged plugin manifests must satisfy the live Claude plugin loader contract (#871).

Orchestrate 2.0.0 through 3.0.6 declared ``dependencies`` as a JSON object.  The loader
requires an array and rejects the whole manifest rather than ignoring the field, so the
plugin did not load at all and ``/orchestrate`` was unavailable.  Nothing in the suite
noticed, because every other check reads the manifest with ``json.load`` -- which is happy
with either shape.

Two legs, deliberately:

* :func:`check_dependencies_shape` is a pure-Python assertion of the shape the loader
  accepts.  It runs everywhere and fails against the 3.0.6 object form.
* :func:`test_every_packaged_manifest_passes_the_live_loader` shells out to the real
  ``claude plugin validate --strict``, so the contract is checked against the loader
  itself rather than against our belief about it.  It skips when the binary is absent.
"""

import json
import shutil
import subprocess
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).parent.parent
PLUGIN_MANIFESTS = sorted(REPO_ROOT.glob("plugins/*/.claude-plugin/plugin.json"))


def check_dependencies_shape(manifest: dict) -> list[str]:
    """Return the reasons ``manifest["dependencies"]`` would be rejected by the loader.

    An empty list means the declaration is acceptable.  Omitting ``dependencies``
    entirely is acceptable; thirteen of this repository's plugins do exactly that.
    """
    if "dependencies" not in manifest:
        return []

    declared = manifest["dependencies"]
    if not isinstance(declared, list):
        return [f"dependencies must be an array, got {type(declared).__name__}"]

    reasons = []
    for index, entry in enumerate(declared):
        if isinstance(entry, str):
            # The loader rejects a version suffix packed into the name string.
            if "@" in entry:
                reasons.append(
                    f"dependencies[{index}]: {entry!r} packs a version into the name; "
                    "use an object with name and version instead"
                )
        elif isinstance(entry, dict):
            if not isinstance(entry.get("name"), str) or not entry["name"]:
                reasons.append(f"dependencies[{index}]: object entry needs a non-empty name")
        else:
            reasons.append(
                f"dependencies[{index}]: entry must be a name string or an object, "
                f"got {type(entry).__name__}"
            )
    return reasons


def test_manifests_were_discovered() -> None:
    """Guard against the glob silently matching nothing and vacuously passing."""
    assert len(PLUGIN_MANIFESTS) >= 10, PLUGIN_MANIFESTS


@pytest.mark.parametrize("manifest_path", PLUGIN_MANIFESTS, ids=lambda p: p.parts[-3])
def test_packaged_manifest_declares_dependencies_the_way_the_loader_expects(
    manifest_path: Path,
) -> None:
    reasons = check_dependencies_shape(json.loads(manifest_path.read_text()))
    assert not reasons, f"{manifest_path.relative_to(REPO_ROOT)}: " + "; ".join(reasons)


def test_the_shape_check_rejects_the_3_0_6_object_form() -> None:
    """Mutation proof: the check above is not vacuous.

    This is the exact declaration that shipped in Orchestrate 2.0.0 through 3.0.6 and
    made the plugin unloadable.
    """
    reasons = check_dependencies_shape({"dependencies": {"agent-launcher": ">=1.0.0"}})
    assert reasons == ["dependencies must be an array, got dict"]


def test_the_shape_check_rejects_a_version_suffixed_name() -> None:
    """The loader rejects ``["agent-launcher@>=1.0.0"]``; so must we."""
    reasons = check_dependencies_shape({"dependencies": ["agent-launcher@>=1.0.0"]})
    assert len(reasons) == 1 and "packs a version into the name" in reasons[0]


def test_the_shape_check_accepts_what_the_loader_accepts() -> None:
    for accepted in (
        [],
        ["agent-launcher"],
        [{"name": "agent-launcher", "version": ">=1.0.0"}],
    ):
        assert check_dependencies_shape({"dependencies": accepted}) == [], accepted


# The agent-launcher release that introduced the behaviour Orchestrate requires: the single
# pane-write door `PaneWriter` that Orchestrate's senders construct, `session_has_started` and
# `agent_row` that `redrive` reads, and a `redeliver()` that accepts an undelivered receipt. Bump
# this only when Orchestrate starts depending on something a newer launcher release introduced --
# not when the launcher ships a patch Orchestrate does not need (terminal review F29).
AGENT_LAUNCHER_FLOOR_RELEASE = "1.4.0"


def _version_tuple(text: str) -> tuple[int, ...]:
    return tuple(int(part) for part in text.split("."))


def test_orchestrate_keeps_its_agent_launcher_floor() -> None:
    """The array rewrite must not quietly drop the version floor issue 841 established, and
    the floor names the release that introduced the required behaviour rather than
    whatever the launcher's current version happens to be: lockstep would force an
    Orchestrate bump for every launcher patch and stop saying which release is required."""
    manifest = json.loads(
        (REPO_ROOT / "plugins/orchestrate/.claude-plugin/plugin.json").read_text()
    )
    declared = manifest["dependencies"]
    assert isinstance(declared, list)
    floors = {entry["name"]: entry.get("version") for entry in declared if isinstance(entry, dict)}
    assert floors.get("agent-launcher") == f">={AGENT_LAUNCHER_FLOOR_RELEASE}", declared


def test_the_declared_floor_is_not_above_the_launcher_this_repository_ships() -> None:
    """The other direction: a floor the packaged launcher cannot satisfy would refuse every
    write command on a fresh install of both plugins from this marketplace."""
    launcher = json.loads(
        (REPO_ROOT / "plugins/agent-launcher/.claude-plugin/plugin.json").read_text()
    )
    assert _version_tuple(AGENT_LAUNCHER_FLOOR_RELEASE) <= _version_tuple(launcher["version"]), (
        f"floor {AGENT_LAUNCHER_FLOOR_RELEASE} is above the shipped launcher {launcher['version']}"
    )


@pytest.mark.skipif(
    shutil.which("claude") is None,
    reason="the claude binary is unavailable, so the live loader contract cannot be checked",
)
@pytest.mark.parametrize("manifest_path", PLUGIN_MANIFESTS, ids=lambda p: p.parts[-3])
def test_every_packaged_manifest_passes_the_live_loader(manifest_path: Path) -> None:
    """Validate against the real loader, not against our belief about it."""
    plugin_dir = manifest_path.parent.parent
    proc = subprocess.run(
        ["claude", "plugin", "validate", "--strict", str(plugin_dir)],
        capture_output=True,
        text=True,
        timeout=120,
    )
    assert proc.returncode == 0, (
        f"claude plugin validate --strict rejected "
        f"{plugin_dir.relative_to(REPO_ROOT)}:\n{proc.stdout}\n{proc.stderr}"
    )
