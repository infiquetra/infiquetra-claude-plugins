"""Tests for project-mappings.json resolution order.

The plugin resolves project_mappings via three steps:
  1. External override:  $INFIQUETRA_SDLC_PATH/config/project-mappings.json
  2. Vendored canonical: <plugin>/config/project-mappings.json
  3. Remote `gh api` fallback (reads infiquetra-sdlc raw from GitHub)

These tests pin each branch using `monkeypatch.setattr` on the module's
_VENDORED_PROJECT_MAPPINGS_PATH constant — no renaming the real vendored
file (which would be racy under pytest-xdist + leave orphans on crash).
"""

import json
import sys
from pathlib import Path
from unittest.mock import patch

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))

import sdlc_manager  # noqa: E402


@pytest.fixture
def fake_vendored_path(tmp_path, monkeypatch):
    """Redirect _VENDORED_PROJECT_MAPPINGS_PATH to a tmp dir. Caller controls
    whether the file exists (write to fake_path to make it exist)."""
    fake_path = tmp_path / "vendored-project-mappings.json"
    monkeypatch.setattr(sdlc_manager, "_VENDORED_PROJECT_MAPPINGS_PATH", fake_path)
    return fake_path


def test_external_override_wins_over_vendored(tmp_path, fake_vendored_path) -> None:
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

    # Also write a different vendored — to prove override wins
    fake_vendored_path.write_text(json.dumps({"projects": {"vendored": {"number": 1}}}))

    result = sdlc_manager._resolve_project_mappings(sdlc_path)
    assert result == override_data


def test_vendored_used_when_no_override(tmp_path, fake_vendored_path) -> None:
    """Override missing → fall through to vendored. We control the
    vendored content via the fixture so the test is hermetic."""
    no_override_path = tmp_path / "nonexistent-sdlc"
    fake_vendored_path.write_text(
        json.dumps(
            {
                "organization": "infiquetra",
                "projects": {"vendored-project": {"number": 1}},
            }
        )
    )

    result = sdlc_manager._resolve_project_mappings(no_override_path)
    assert "vendored-project" in result["projects"]


def test_remote_fallback_when_neither_exists(tmp_path, fake_vendored_path) -> None:
    """If both override and vendored are missing, fall back to `gh api`.
    Mock `_gh` to verify the API call + simulate a base64 response."""
    import base64

    fake_payload = json.dumps({"projects": {"remote": {"number": 5}}})
    fake_b64 = base64.b64encode(fake_payload.encode()).decode()

    no_override_path = tmp_path / "nonexistent-sdlc"
    # fake_vendored_path is a tmp path that doesn't exist (we never wrote to it)
    assert not fake_vendored_path.exists()

    with patch.object(sdlc_manager, "_gh", return_value=fake_b64):
        result = sdlc_manager._resolve_project_mappings(no_override_path)
    assert result == {"projects": {"remote": {"number": 5}}}


def test_returns_empty_dict_when_all_three_fail(tmp_path, fake_vendored_path) -> None:
    """If override missing, vendored missing, AND remote `gh api` raises,
    we return {} rather than crashing — caller handles empty config."""
    no_override_path = tmp_path / "nonexistent-sdlc"
    assert not fake_vendored_path.exists()

    with patch.object(
        sdlc_manager,
        "_gh",
        side_effect=sdlc_manager.GhApiError("simulated failure"),
    ):
        result = sdlc_manager._resolve_project_mappings(no_override_path)
    assert result == {}


def test_vendored_project_mappings_has_expected_canonical_state() -> None:
    """The vendored project-mappings.json must declare the canonical
    org-wide state: Olympus is project #1; the repo list matches the
    actual `gh repo list infiquetra` output as of the file's `_provenance`
    date. If this test fails, either the vendored file was edited or the
    org's repo set has drifted — both are events the operator should know
    about. The expected list is captured here verbatim so drift is
    visible in code review.

    NOTE: This test reads the REAL vendored file (not the fixture) — it's
    the canonical-state guard, not a hermetic unit test."""
    vendored = sdlc_manager._VENDORED_PROJECT_MAPPINGS_PATH
    assert vendored.exists(), f"Vendored file missing at {vendored}"
    data = json.loads(vendored.read_text())
    assert data["organization"] == "infiquetra"
    assert "mount-olympus" in data["projects"]
    olympus = data["projects"]["mount-olympus"]
    assert olympus["number"] == 1

    # Exact repo set from `gh repo list infiquetra --json name --jq '.[].name'`
    # captured 2026-05-04. If the org adds/removes a repo, the vendored
    # file needs updating + this test needs updating in the same PR — the
    # symmetry forces the operator to re-verify.
    expected_repos = {
        "campps-blueprint",
        "campps-mvp",
        "github-actions-runners",
        "hermes-extensions",
        "infiquetra-aws-infra",
        "infiquetra-claude-plugins",
        "infiquetra-sdlc",
        "mimir",
        "mimir-blueprint",
    }
    actual_repos = set(olympus["repositories"])
    assert actual_repos == expected_repos, (
        f"Vendored repo list drifted from canonical. "
        f"Missing: {expected_repos - actual_repos}; "
        f"Unexpected: {actual_repos - expected_repos}"
    )
