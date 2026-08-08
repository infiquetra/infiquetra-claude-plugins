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
    assert (
        plugin_json["version"] == "2.10.2"
    )  # house-style presentation contract on sdlc-operator (#704)
    assert entry["version"] == plugin_json["version"]
    assert entry["source"] == "./plugins/mission-control"
    assert "CAMPPS" in plugin_json["description"]
    assert "Mount Olympus" not in plugin_json["description"]
    assert "campps" in plugin_json["keywords"]
    assert "mount-olympus" not in plugin_json["keywords"]
    assert "Operations" in entry["description"]
    assert "Beads" not in entry["description"]
    assert "beads" not in entry["keywords"]


def test_issue_type_reference_uses_current_template_labels() -> None:
    issue_types = _read(PLUGIN_ROOT / "skills/issues/references/issue-types.md")

    assert "`capability`, `hermes-task`, `needs-plan`" in issue_types
    assert "`enhancement`, `hermes-task`, `needs-plan`" in issue_types
    assert "`defect`, `hermes-task`, `needs-plan`" in issue_types
    assert "`objective`, `hermes-not-actionable`" not in issue_types
    assert "`exploration`, `research`, `hermes-not-actionable`" in issue_types
    assert "`context-update`, `documentation`, `hermes-not-actionable`" in issue_types
    assert "`capability`, `needs-analysis` (auto-applied by template)" not in issue_types
    assert "`enhancement`, `needs-analysis` (auto-applied by template)" not in issue_types
    assert "`defect`, `needs-triage` (auto-applied by template)" not in issue_types
    assert "`objective:{short-name}`" not in issue_types
    assert "`initiative:{name}`" not in issue_types


def test_field_first_hierarchy_guidance_is_consistent() -> None:
    issue_skill = _read(PLUGIN_ROOT / "skills/issues/SKILL.md")
    flow_skill = _read(PLUGIN_ROOT / "skills/flow/SKILL.md")
    milestone_skill = _read(PLUGIN_ROOT / "skills/milestones/SKILL.md")
    rollout_hierarchy = _read(PLUGIN_ROOT / "skills/rollout/references/work-hierarchy.md")

    assert "5-type issue" in issue_skill
    assert "Objective is an `Objective` project-field option" in issue_skill
    assert "flow unlink-sub-issue" in flow_skill
    assert "Create the Objective issue" not in milestone_skill
    assert "Capability issue (top-level)" in rollout_hierarchy
    assert "Objective issue + project field option" not in rollout_hierarchy


def test_operator_prompt_honors_hermes_actionability_contract() -> None:
    operator = _read(PLUGIN_ROOT / "agents/sdlc-operator.md")

    assert "(capability/enhancement/defect)" in operator
    assert "(exploration/context-update)" in operator
    assert "(capability/enhancement/defect/exploration/context-update)" not in operator
    assert "Step 2: Applied labels (hermes-task, capability, needs-plan)" in operator
    assert "Step 2: Applied labels (hermes-task, capability, needs-analysis)" not in operator
    assert "issue prepare" in operator
    assert "issue create-prepared" in operator
    assert "Asgard `Shaping`, CAMPPS `Idea`" in operator
    # Olympus is retired; it must not be presented as an active safe-start board.
    assert "Olympus `Backlog`" not in operator
    assert "every new card has a parent by default" not in operator
    assert "flow unlink-sub-issue" in operator


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
    assert "Create a CAMPPS issue from this text" in skill
    assert "Create an Asgard issue from these notes" in skill
    # Olympus is retired; the natural-language router must not steer new work to it.
    assert "Olympus issue from this text" not in skill
    assert "Create an issue from the brainstorm" in skill
    assert "handoff_maturity" in skill
    assert "If team or project is ambiguous, ask" in skill
    assert "Never auto-move a prepared issue to `Ready`" in skill
    assert "from the brainstorm" in create_command
    assert "handoff the plan" in create_command
    assert "/loop <issue>" not in create_command


def test_asgard_campps_model_retires_olympus_as_active_target() -> None:
    schema = json.loads(_read(PLUGIN_ROOT / "config/sdlc-schema.json"))
    roles = schema["work_hierarchy"]["roles"]

    assert schema["schema_version"] == "2026-06-17"
    assert roles["objective"]["project_view_group_by"] == "Objective"
    assert roles["outcome"]["required_by_default"] is False
    assert roles["capability"]["default_parent_role"] is None
    assert roles["capability"]["allowed_parent_roles"] == ["outcome"]
    assert schema["teams"]["asgard"]["status"] == "active"
    assert schema["teams"]["olympus"]["status"] == "retired_historical"
    assert schema["teams"]["olympus"]["board"] is None
    assert "olympus" not in schema["boards"]
    assert schema["boards"]["campps"]["status"] == "active"
    assert "Transfer Target" in schema["fields"]["asgard"]
    assert "Promotion Target" not in schema["fields"]["asgard"]
    assert "cross_team_transfer_rule" in schema["team_routing"]
    assert "asgard_to_olympus_rule" not in schema["team_routing"]
    assert schema["team_routing"]["target_team_values"] == [
        "Asgard",
        "CAMPPS",
        "Jeff",
        "External/Deferred",
    ]
    assert "Asgard and CAMPPS" in schema["team_routing"]["cross_team_transfer_rule"]
    assert (
        "Mount Olympus is retired historical context"
        in schema["team_routing"]["cross_team_transfer_rule"]
    )

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


def test_saga_handoff_routes_without_copying_issue_templates() -> None:
    handoff = _read(ROOT / "plugins/saga/skills/handoff/SKILL.md")
    issue_command = _read(PLUGIN_ROOT / "commands/issue.md")

    assert "Do not copy SDLC issue templates into this skill." in handoff
    assert "/issue --prepare --from <source> --maturity <maturity>" in handoff
    assert "issue prepare" in issue_command
    assert "do not copy\n   SDLC issue template sections into Saga" in issue_command
    assert "### Objective" not in handoff
    assert "### Acceptance criteria" not in handoff
