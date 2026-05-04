"""Tests for project-mappings.json resolution order.

The plugin resolves project_mappings via three steps:
  1. External override:  $INFIQUETRA_SDLC_PATH/config/project-mappings.json
  2. Vendored canonical: <plugin>/config/project-mappings.json
  3. Remote `gh api` fallback (reads infiquetra-sdlc raw from GitHub)

These tests pin each branch.
"""

from pathlib import Path
import json
import sys
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))

import sdlc_manager  # noqa: E402


def test_external_override_wins_over_vendored(tmp_path) -> None:
    """If $INFIQUETRA_SDLC_PATH/config/project-mappings.json exists, it
    takes precedence over the vendored copy. This lets a developer test
    against a custom project layout without modifying the plugin."""
    # Set up an override file
    sdlc_path = tmp_path / "infiquetra-sdlc"
    cfg_dir = sdlc_path / "config"
    cfg_dir.mkdir(parents=True)
    override_data = {
        "organization": "infiquetra",
        "projects": {"override-project": {"number": 99, "name": "Override"}},
    }
    (cfg_dir / "project-mappings.json").write_text(json.dumps(override_data))

    # No need to mock anything — _resolve_project_mappings is called
    # with the override path directly
    result = sdlc_manager._resolve_project_mappings(sdlc_path)
    assert result == override_data


def test_vendored_used_when_no_override(tmp_path) -> None:
    """If the override doesn't exist, the vendored copy is used.
    The vendored copy ships in the plugin and is verified to exist
    (`plugins/sdlc-manager/config/project-mappings.json`)."""
    # Point to a non-existent override path so resolution falls through
    no_override_path = tmp_path / "nonexistent-sdlc"
    result = sdlc_manager._resolve_project_mappings(no_override_path)

    # Should have loaded the real vendored file
    assert "projects" in result
    assert "mount-olympus" in result["projects"]
    assert result["projects"]["mount-olympus"]["number"] == 1


def test_remote_fallback_when_neither_exists(tmp_path) -> None:
    """If both override and vendored are missing, fall back to `gh api`.
    We mock _gh to verify the API call is made + simulate a base64
    response from the GitHub Contents API."""
    import base64
    fake_payload = json.dumps({"projects": {"remote": {"number": 5}}})
    fake_b64 = base64.b64encode(fake_payload.encode()).decode()

    no_override_path = tmp_path / "nonexistent-sdlc"

    # Patch the vendored path to also be missing for this test
    fake_vendored = tmp_path / "fake-plugin-config-no-such-file.json"
    with patch.object(
        sdlc_manager, "Path",
        wraps=Path,  # default behavior
    ) as mock_path_cls:
        # Hard to mock Path(__file__) cleanly; instead, just monkeypatch
        # the vendored file probe by ensuring the test never finds it.
        # The simplest approach: construct a controlled environment.
        pass

    # Cleaner approach: temporarily move the vendored file out of the way
    real_vendored = (
        Path(sdlc_manager.__file__).resolve().parent.parent
        / "config" / "project-mappings.json"
    )
    backup = real_vendored.with_suffix(".json.bak-test")
    real_vendored.rename(backup)
    try:
        with patch.object(sdlc_manager, "_gh", return_value=fake_b64):
            result = sdlc_manager._resolve_project_mappings(no_override_path)
        assert result == {"projects": {"remote": {"number": 5}}}
    finally:
        backup.rename(real_vendored)


def test_returns_empty_dict_when_all_three_fail(tmp_path) -> None:
    """If override missing, vendored missing, AND remote `gh api` raises,
    we return {} rather than crashing — caller handles empty config."""
    no_override_path = tmp_path / "nonexistent-sdlc"
    real_vendored = (
        Path(sdlc_manager.__file__).resolve().parent.parent
        / "config" / "project-mappings.json"
    )
    backup = real_vendored.with_suffix(".json.bak-test")
    real_vendored.rename(backup)
    try:
        with patch.object(
            sdlc_manager, "_gh",
            side_effect=sdlc_manager.GhApiError("simulated failure"),
        ):
            result = sdlc_manager._resolve_project_mappings(no_override_path)
        assert result == {}
    finally:
        backup.rename(real_vendored)


def test_vendored_project_mappings_has_expected_canonical_state() -> None:
    """The vendored project-mappings.json must declare the canonical
    org-wide state: Olympus is project #1; project_id captured (best-effort);
    several known repos mapped. If this test fails, either the vendored
    file was edited or the org's project layout changed — both are events
    the operator should know about."""
    vendored = (
        Path(sdlc_manager.__file__).resolve().parent.parent
        / "config" / "project-mappings.json"
    )
    assert vendored.exists(), f"Vendored file missing at {vendored}"
    data = json.loads(vendored.read_text())
    assert data["organization"] == "infiquetra"
    assert "mount-olympus" in data["projects"]
    olympus = data["projects"]["mount-olympus"]
    assert olympus["number"] == 1
    # repo list must include the canonical repos
    repos = set(olympus["repositories"])
    assert {"campps-mvp", "mimir", "infiquetra-sdlc", "infiquetra-claude-plugins"}.issubset(repos)
