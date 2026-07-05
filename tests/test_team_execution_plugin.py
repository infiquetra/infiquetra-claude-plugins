"""Contract tests for the team-execution plugin package."""

import json
from pathlib import Path

ROOT = Path(__file__).parent.parent
PLUGIN_ROOT = ROOT / "plugins" / "team-execution"

VALIDATOR_AGENTS = {
    "deploy-watcher",
    "security-scanner",
    "iac-cost-scanner",
    "api-compat-scanner",
    "dependency-scanner",
    "smoke-tester",
    "scenario-tester",
    "api-contract-tester",
    "sdk-regression-tester",
    "event-flow-tester",
    "ui-regression-tester",
    "performance-tester",
    "concurrency-tester",
    "github-actions-monitor",
    "runtime-monitor",
}

BASE_REVIEWERS = {
    "devils-advocate-reviewer",
    "security-reviewer",
    "architecture-reviewer",
}

VALIDATOR_REFERENCES = {
    "validator-registry.md",
    "validator-criteria.md",
    "validator-execution-order.md",
    "validator-evidence-state.md",
    "validator-spawn-quirks.md",
}

WORKER_REFERENCES = {
    "external-engine-workers.md",
}


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def _frontmatter_name(path: Path) -> str:
    lines = _read(path).splitlines()
    assert lines[0] == "---"
    for line in lines[1:]:
        if line.startswith("name: "):
            return line.removeprefix("name: ").strip()
    raise AssertionError(f"{path} has no frontmatter name")


def test_team_execution_metadata_is_v2_and_marketplace_matches() -> None:
    plugin_json = json.loads(_read(PLUGIN_ROOT / ".claude-plugin" / "plugin.json"))
    marketplace = json.loads(_read(ROOT / ".claude-plugin" / "marketplace.json"))
    entry = next(p for p in marketplace["plugins"] if p["name"] == "team-execution")

    assert plugin_json["version"] == "2.9.1"  # release-surface CHANGELOG reformat (#429)
    assert entry["version"] == plugin_json["version"]
    assert entry["source"] == "./plugins/team-execution"
    assert "validator" in plugin_json["description"].lower()
    assert "nonprod" in plugin_json["description"].lower()
    assert {"validators", "automation", "nonprod"} <= set(plugin_json["keywords"])


def test_validator_agents_and_base_reviewers_are_packaged() -> None:
    agent_dir = PLUGIN_ROOT / "agents"
    expected_agents = VALIDATOR_AGENTS | BASE_REVIEWERS

    for agent_name in expected_agents:
        path = agent_dir / f"{agent_name}.md"
        assert path.exists(), f"missing agent file: {path}"
        assert _frontmatter_name(path) == agent_name


def test_validator_references_are_packaged_and_linked() -> None:
    references_dir = PLUGIN_ROOT / "skills" / "team-execution" / "references"
    skill_doc = _read(PLUGIN_ROOT / "skills" / "team-execution" / "SKILL.md")
    readme = _read(PLUGIN_ROOT / "README.md")

    for filename in VALIDATOR_REFERENCES:
        path = references_dir / filename
        assert path.exists(), f"missing validator reference: {path}"
        assert filename in skill_doc
        assert filename in readme


def test_worker_references_are_packaged_and_linked() -> None:
    references_dir = PLUGIN_ROOT / "skills" / "team-execution" / "references"
    skill_doc = _read(PLUGIN_ROOT / "skills" / "team-execution" / "SKILL.md")
    readme = _read(PLUGIN_ROOT / "README.md")

    for filename in WORKER_REFERENCES:
        path = references_dir / filename
        assert path.exists(), f"missing worker reference: {path}"
        assert filename in skill_doc
        assert filename in readme


def test_appsec_audit_skill_documents_url_trust_boundaries() -> None:
    skill_path = PLUGIN_ROOT / "skills" / "appsec-audit" / "SKILL.md"
    skill_doc = _read(skill_path).lower()

    assert _frontmatter_name(skill_path) == "appsec-audit"
    for required in ("ssrf", "redirect", "metadata endpoint", "allowlist", "trust boundary"):
        assert required in skill_doc


def test_team_setup_and_tmux_assets_are_removed() -> None:
    # R8 reshape (replaces the old test_team_setup_references_existing_assets, KTD13):
    # team-execution is a native-agent-teams wrapper — /team-setup, the tmux assets, and the
    # validator-pane-behavior reference are gone, and no tmux reference survives outside CHANGELOG.
    for gone in (
        "commands/team-setup.md",
        "docs/example_tmux.conf",
        "docs/agent-overflow.sh",
        "skills/team-execution/references/validator-pane-behavior.md",
    ):
        assert not (PLUGIN_ROOT / gone).exists(), f"R8: {gone} should be deleted"

    for path in PLUGIN_ROOT.rglob("*"):
        if not path.is_file() or path.name == "CHANGELOG.md":
            continue  # an intentional CHANGELOG history note is the one allowed mention
        text = path.read_text(encoding="utf-8", errors="ignore")
        assert "tmux" not in text.lower(), (
            f"R8: tmux reference still in {path.relative_to(PLUGIN_ROOT)}"
        )
        # No dangling reference to the DELETED validator-pane-behavior reference may survive
        # (the deletion's own guard — catches a SKILL.md/README/_REFERENCE_FILES regression).
        assert "validator-pane-behavior" not in text, (
            f"R8: dangling validator-pane-behavior reference in {path.relative_to(PLUGIN_ROOT)}"
        )


def test_skill_documents_validator_state_and_automation_gates() -> None:
    skill_doc = _read(PLUGIN_ROOT / "skills" / "team-execution" / "SKILL.md")

    for required in (
        ".team-execution.json",
        "required_validators",
        "disabled_validators",
        "nonprod_workflows",
        "scenario_hints",
        "smoke_targets",
        ".claude/team-execution/validators/",
        "github.com/infiquetra/*",
        "nonprod",
        "maximum 3 remediation loops",
    ):
        assert required in skill_doc


def test_skill_documents_required_evidence_absence_gate() -> None:
    """U4 (#277 R12/AE8): the evidence-absence completeness gate is documented in the completion
    protocol, including the skipped-by-config exception, mirroring FailureClass 'missing-output'."""
    skill_doc = _read(PLUGIN_ROOT / "skills" / "team-execution" / "SKILL.md")
    order_doc = _read(
        PLUGIN_ROOT / "skills" / "team-execution" / "references" / "validator-execution-order.md"
    )

    # The protocol doc carries the gate (not just a passing mention in SKILL.md).
    assert "Required-Evidence Absence" in order_doc
    assert "missing-output" in order_doc
    assert "evidence record" in order_doc
    assert "required" in order_doc
    # The exception must be explicit and present in BOTH the protocol and the completion step.
    assert "skipped-by-config" in order_doc
    assert "missing-output" in skill_doc
    assert "skipped-by-config" in skill_doc
