"""Source-aware consumer and poll-boundary conformance for issue #357."""

from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).parent.parent
ENGINE = ROOT / "plugins" / "fleet-core" / "scripts" / "fleet_commons" / "liveness_engine.py"
OUTCOME = ROOT / "plugins" / "saga" / "scripts" / "outcome_liveness.py"
EVENTS = ROOT / "plugins" / "saga" / "scripts" / "liveness_events.py"
PROTOCOL = (
    ROOT
    / "plugins"
    / "team-execution"
    / "skills"
    / "team-execution"
    / "scripts"
    / "liveness_protocol.py"
)
SKILL = ROOT / "plugins" / "team-execution" / "skills" / "team-execution" / "SKILL.md"
REFERENCE = (
    ROOT
    / "plugins"
    / "team-execution"
    / "skills"
    / "team-execution"
    / "references"
    / "liveness-protocol.md"
)
INVENTORY = ROOT / "plugins" / "saga" / "references" / "liveness-consumer-sites.md"
HOOKS = ROOT / "plugins" / "saga" / "hooks" / "hooks.json"


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def test_fleet_core_has_the_only_liveness_engine_implementation() -> None:
    implementations = [
        path for path in (ROOT / "plugins").rglob("liveness_engine.py") if "tests" not in path.parts
    ]
    assert implementations == [ENGINE]
    assert 'fleet_commons_shim.load("liveness_engine")' in _read(OUTCOME)
    assert 'fleet_commons_shim.load("liveness_engine")' in _read(EVENTS)
    assert "def evaluate(" not in _read(PROTOCOL)


def test_run_fact_adapter_exposes_every_closed_event() -> None:
    text = _read(EVENTS)
    for event in (
        "subject-open",
        "heartbeat",
        "scoped-activity-unattributed",
        "artifact-progress",
        "idle-notice",
        "idle-ack",
        "reping-intent",
        "reping-sent",
        "reping-send-failed",
        "reping-ack",
    ):
        assert f'"{event}"' in text
    assert '"liveness"' in _read(ROOT / "plugins" / "saga" / "scripts" / "run_ledger.py")


def test_team_skill_has_executable_preflight_event_poll_claim_and_stage_commands() -> None:
    skill = _read(SKILL)
    protocol = _read(PROTOCOL)
    for command in (
        "preflight",
        "baseline",
        "open",
        "record-event",
        "record-idle-notice",
        "record-artifact-observation",
        "poll",
        "claim-reping",
        "stage-send",
    ):
        assert f'"$TEAM_LIVENESS" {command}' in skill
    assert "record-artifact-observation" in skill
    assert "scripts/liveness_events.py" in protocol
    assert "subprocess.run" in protocol


def test_every_required_poll_boundary_is_in_skill_reference_and_inventory() -> None:
    combined = "\n".join((_read(SKILL), _read(REFERENCE), _read(INVENTORY)))
    for boundary in (
        "lease renewal",
        "Agent/SendMessage",
        "dependency",
        "B2",
    ):
        assert boundary in combined
    assert "no always-on daemon" in combined


def test_sendmessage_hook_is_registered_for_pre_post_and_failure() -> None:
    hooks = json.loads(_read(HOOKS))["hooks"]
    for event in ("PreToolUse", "PostToolUse", "PostToolUseFailure"):
        matching = [row for row in hooks[event] if row.get("matcher") == "SendMessage"]
        assert len(matching) == 1
        assert any("liveness_reping_hook.py" in hook["command"] for hook in matching[0]["hooks"])


def test_detection_has_no_destructive_action_owner() -> None:
    for path in (ENGINE, EVENTS, PROTOCOL):
        text = _read(path)
        assert 'subprocess.run(["kill"' not in text
        assert "release_lease(" not in text
        assert "shutil.rmtree" not in text
    inventory = _read(INVENTORY)
    assert "issue #358 reclaimer" in inventory
    assert "#357 never stops/releases/deletes" in inventory


def test_outcome_adapter_preserves_legacy_authority_before_adaptive_scoring() -> None:
    text = _read(OUTCOME)
    reason_index = text.index("reason = _is_stalled")
    record_index = text.index("_record_terminal(store, sid, reason)", reason_index)
    adaptive_index = text.index("adaptive[sid] = _adaptive_decision", record_index)
    assert reason_index < record_index < adaptive_index


def test_atomic_release_versions_match_issue_357_contract() -> None:
    expected = {"fleet-core": "0.14.0", "saga": "0.101.0", "team-execution": "2.20.0"}
    marketplace = json.loads(_read(ROOT / ".claude-plugin" / "marketplace.json"))
    rows = {row["name"]: row for row in marketplace["plugins"]}
    for plugin, version in expected.items():
        manifest = json.loads(_read(ROOT / "plugins" / plugin / ".claude-plugin" / "plugin.json"))
        assert manifest["version"] == version
        assert rows[plugin]["version"] == version
        assert rows[plugin]["description"] == manifest["description"]
        assert f"## [{version}]" in _read(ROOT / "plugins" / plugin / "CHANGELOG.md")
