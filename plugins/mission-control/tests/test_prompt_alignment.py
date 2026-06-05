"""Drift guards for mission-control prompts, references, and release metadata."""

from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
PLUGIN_ROOT = ROOT / "plugins" / "mission-control"


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def test_sdlc_manager_metadata_and_marketplace_entry_match() -> None:
    plugin_json = json.loads(_read(PLUGIN_ROOT / ".claude-plugin" / "plugin.json"))
    marketplace = json.loads(_read(ROOT / ".claude-plugin" / "marketplace.json"))
    entry = next(p for p in marketplace["plugins"] if p["name"] == "mission-control")

    assert plugin_json["name"] == "mission-control"
    assert plugin_json["version"] == "2.0.0"
    assert entry["version"] == plugin_json["version"]
    assert entry["source"] == "./plugins/mission-control"
    assert "Jeff Intent" in entry["description"]
    assert "Beads" not in entry["description"]
    assert "beads" not in entry["keywords"]


def test_issue_type_reference_uses_current_template_labels() -> None:
    issue_types = _read(PLUGIN_ROOT / "skills/issues/references/issue-types.md")

    assert "`capability`, `hermes-task`, `needs-plan`" in issue_types
    assert "`enhancement`, `hermes-task`, `needs-plan`" in issue_types
    assert "`defect`, `hermes-task`, `needs-plan`" in issue_types
    assert "`objective`, `hermes-not-actionable`" in issue_types
    assert "`exploration`, `research`, `hermes-not-actionable`" in issue_types
    assert "`context-update`, `documentation`, `hermes-not-actionable`" in issue_types
    assert "`capability`, `needs-analysis` (auto-applied by template)" not in issue_types
    assert "`enhancement`, `needs-analysis` (auto-applied by template)" not in issue_types
    assert "`defect`, `needs-triage` (auto-applied by template)" not in issue_types
    assert "`objective:{short-name}`" not in issue_types
    assert "`initiative:{name}`" not in issue_types


def test_operator_prompt_honors_hermes_actionability_contract() -> None:
    operator = _read(PLUGIN_ROOT / "agents/sdlc-operator.md")

    assert "(capability/enhancement/defect)" in operator
    assert "(objective/exploration/context-update)" in operator
    assert "(capability/enhancement/defect/exploration/context-update)" not in operator
    assert "Step 2: Applied labels (hermes-task, capability, needs-plan)" in operator
    assert "Step 2: Applied labels (hermes-task, capability, needs-analysis)" not in operator
    assert "issue prepare" in operator
    assert "issue create-prepared" in operator
    assert "Asgard `Shaping`, Olympus `Backlog`" in operator


def test_triage_command_uses_project_fields_and_current_actionable_labels() -> None:
    triage = _read(PLUGIN_ROOT / "commands/triage.md")

    assert "Initiative/Objective project field values" in triage
    assert "initiative/objective labels" not in triage
    assert '"capability,hermes-task,needs-plan"' in triage
    assert '"capability,needs-analysis"' not in triage
    assert "Add `needs-analysis` label" not in triage


def test_label_docs_mark_legacy_auto_label_rules_as_fallback() -> None:
    skill = _read(PLUGIN_ROOT / "skills/labels/SKILL.md")
    reference = _read(PLUGIN_ROOT / "skills/labels/references/labels-reference.md")

    assert "legacy fallback behavior" in skill
    assert "legacy fallback labels" in skill
    assert "legacy fallback labels" in reference
    assert "legacy fallback rules" in reference
    assert "Current capability,\nenhancement, and defect templates apply `needs-plan`" in reference


def test_prepared_issue_guidance_routes_natural_language_creation() -> None:
    skill = _read(PLUGIN_ROOT / "skills/issues/SKILL.md")
    create_command = _read(PLUGIN_ROOT / "commands/issue.md")
    readme = _read(PLUGIN_ROOT / "README.md")

    # NOTE: the former /sdlc-create compatibility alias command was removed in the
    # family rename (mission-control commands = issue/board/metrics/triage). Its
    # alias-specific assertions are gone with it; /issue is the single primary command.
    for text in (skill, create_command, readme):
        assert "issue prepare" in text
        assert "issue create-prepared" in text

    assert "name: issue" in create_command
    assert "--prepare" in create_command
    assert "--draft" in create_command
    assert "--from" in create_command
    assert "--maturity" in create_command
    assert "`/issue` is the primary user-facing command" in skill
    assert "/issue [type]" in readme
    assert "Create an Olympus issue from this text" in skill
    assert "Create an Asgard issue from these notes" in skill
    assert "Create an issue from the brainstorm" in skill
    assert "handoff_maturity" in skill
    assert "If team or project is ambiguous, ask" in skill
    assert "Never auto-move a prepared issue to `Ready`" in skill
    assert "from the brainstorm" in create_command
    assert "handoff the plan" in create_command
    assert "/loop <issue>" not in create_command


def test_asgard_olympus_model_uses_explicit_transfer_language() -> None:
    schema = json.loads(_read(PLUGIN_ROOT / "config/sdlc-schema.json"))

    assert schema["schema_version"] == "2026-05-30"
    assert schema["teams"]["asgard"]["status"] == "active"
    assert "Transfer Target" in schema["fields"]["asgard"]
    assert "Promotion Target" not in schema["fields"]["asgard"]
    assert "cross_team_transfer_rule" in schema["team_routing"]
    assert "asgard_to_olympus_rule" not in schema["team_routing"]
    assert "sibling target boards" in schema["team_routing"]["cross_team_transfer_rule"]

    active_surfaces = [
        PLUGIN_ROOT / "config/sdlc-schema.json",
        PLUGIN_ROOT / "scripts/sdlc_manager.py",
        PLUGIN_ROOT / "skills/board/references/kanban-workflow.md",
        PLUGIN_ROOT / "skills/issues/SKILL.md",
        PLUGIN_ROOT / "commands/issue.md",
        PLUGIN_ROOT / "commands/issue.md",
        PLUGIN_ROOT / "agents/sdlc-operator.md",
        PLUGIN_ROOT / "README.md",
    ]
    stale_phrases = [
        "asgard_to_olympus",
        "Promotion Target",
        "Promotion gaps",
        "Olympus promotion gaps",
        "Asgard Seeds Olympus",
        "seed Olympus",
        "promote to Olympus",
    ]

    for path in active_surfaces:
        text = _read(path)
        for phrase in stale_phrases:
            assert phrase not in text, f"{path.relative_to(ROOT)} contains stale phrase {phrase!r}"
