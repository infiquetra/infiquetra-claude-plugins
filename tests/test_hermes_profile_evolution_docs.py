from __future__ import annotations

import hashlib
import json
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PLUGIN = ROOT / "plugins/hermes-profile-evolution"
DOCS = PLUGIN / "docs"
SCRIPT = PLUGIN / "scripts/profile_request.py"


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def test_documentation_package_is_complete_and_uses_rendered_art() -> None:
    expected = {
        "usage.md",
        "architecture.md",
        "development.md",
        "troubleshooting.md",
        "assets/profile-evolution-claude-code-front-door.svg",
        "assets/profile-evolution-claude-code-front-door.png",
        "assets/renderer-receipt.md",
    }

    assert expected <= {
        path.relative_to(DOCS).as_posix() for path in DOCS.rglob("*") if path.is_file()
    }
    combined = "\n".join(path.read_text() for path in DOCS.rglob("*.md"))
    assert "```mermaid" not in combined
    for tool in ("`Write`", "`Edit`", "`MultiEdit`", "`NotebookEdit`"):
        assert tool in combined
    assert "Bash" in combined and "external editors" in combined
    assert "Team Mimir operator hub" in combined
    assert "Hermes producer" in combined


def test_renderer_receipt_binds_the_committed_source_and_render() -> None:
    assets = DOCS / "assets"
    receipt = (assets / "renderer-receipt.md").read_text()
    assert re.search(r"rsvg-convert version \d+\.\d+\.\d+", receipt)
    for suffix in ("svg", "png"):
        path = assets / f"profile-evolution-claude-code-front-door.{suffix}"
        assert _sha256(path) in receipt


def test_usage_documents_every_released_operator_action() -> None:
    usage = (DOCS / "usage.md").read_text()
    for action in ("suggest", "reply", "resume", "status"):
        assert f'python3 "$PROFILE_ADAPTER" {action}' in usage
    assert "hermes profile-request doctor --target brokkr" in usage
    assert "no public `doctor` action" in usage


def test_cli_help_matches_documented_doctor_boundary() -> None:
    result = subprocess.run(
        [sys.executable, str(SCRIPT), "--help"], capture_output=True, text=True, check=False
    )
    assert result.returncode == 0
    for action in ("suggest", "reply", "resume", "status", "census"):
        assert action in result.stdout
    assert "doctor" not in result.stdout


def test_documentation_release_surfaces_are_version_013() -> None:
    manifest = json.loads((PLUGIN / ".claude-plugin/plugin.json").read_text())
    marketplace = json.loads((ROOT / ".claude-plugin/marketplace.json").read_text())
    entry = next(
        plugin for plugin in marketplace["plugins"] if plugin["name"] == "hermes-profile-evolution"
    )
    assert manifest["version"] == "0.1.3"
    assert entry["version"] == manifest["version"]
    assert (
        f"source version documented here is `{manifest['version']}`"
        in (DOCS / "usage.md").read_text()
    )
    assert (PLUGIN / "CHANGELOG.md").is_file()


def test_architecture_does_not_claim_target_mutation_or_commit_authority() -> None:
    text = (DOCS / "architecture.md").read_text()
    assert "cannot edit or commit target behavior" in text
