"""Drift guards for sdlc-manager prompts, references, and release metadata."""

from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
PLUGIN_ROOT = ROOT / "plugins" / "sdlc-manager"


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def test_sdlc_manager_metadata_and_marketplace_entry_match() -> None:
    plugin_json = json.loads(_read(PLUGIN_ROOT / ".claude-plugin" / "plugin.json"))
    marketplace = json.loads(_read(ROOT / ".claude-plugin" / "marketplace.json"))
    entry = next(p for p in marketplace["plugins"] if p["name"] == "sdlc-manager")

    assert plugin_json["name"] == "sdlc-manager"
    assert plugin_json["version"] == "1.6.0"
    assert entry["version"] == plugin_json["version"]
    assert entry["source"] == "./plugins/sdlc-manager"
    assert "Jeff Intent" in entry["description"]
    assert "Beads" not in entry["description"]
    assert "beads" not in entry["keywords"]


def test_issue_type_reference_uses_current_template_labels() -> None:
    issue_types = _read(PLUGIN_ROOT / "skills/sdlc-issues/references/issue-types.md")

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
    triage = _read(PLUGIN_ROOT / "commands/sdlc-triage.md")

    assert "Initiative/Objective project field values" in triage
    assert "initiative/objective labels" not in triage
    assert '"capability,hermes-task,needs-plan"' in triage
    assert '"capability,needs-analysis"' not in triage
    assert "Add `needs-analysis` label" not in triage


def test_label_docs_mark_legacy_auto_label_rules_as_fallback() -> None:
    skill = _read(PLUGIN_ROOT / "skills/sdlc-labels/SKILL.md")
    reference = _read(PLUGIN_ROOT / "skills/sdlc-labels/references/labels-reference.md")

    assert "legacy fallback behavior" in skill
    assert "legacy fallback labels" in skill
    assert "legacy fallback labels" in reference
    assert "legacy fallback rules" in reference
    assert "Current capability,\nenhancement, and defect templates apply `needs-plan`" in reference


def test_prepared_issue_guidance_routes_natural_language_creation() -> None:
    skill = _read(PLUGIN_ROOT / "skills/sdlc-issues/SKILL.md")
    command = _read(PLUGIN_ROOT / "commands/sdlc-create.md")
    readme = _read(PLUGIN_ROOT / "README.md")

    for text in (skill, command, readme):
        assert "issue prepare" in text
        assert "issue create-prepared" in text

    assert "Create an Olympus issue from this text" in skill
    assert "Create an Asgard issue from these notes" in skill
    assert "If team or project is ambiguous, ask" in skill
    assert "Never auto-move a prepared issue to `Ready`" in skill
    assert "create an Olympus issue from this text" in command
    assert "prepared-draft path" in command
