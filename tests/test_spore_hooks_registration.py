"""U4 registration guard (issue #281): both ends of the spore are wired in hooks.json.

A spore writer with no reader (or vice-versa) is the dead-wiring failure mode KD2 calls out, so this
asserts (a) a PreCompact matcher covering auto+manual -> precompact_spore_hook.py, (b) a SessionStart
entry matched ``compact`` -> compact_spore_session_hook.py, and (c) the existing startup|resume
stale-main entry is unchanged (no regression to the proven path). JSON validity is implied by load."""

from __future__ import annotations

import json
from pathlib import Path
from typing import cast

HOOKS_JSON = Path(__file__).resolve().parent.parent / "plugins" / "saga" / "hooks" / "hooks.json"


def _events() -> dict[str, list[dict]]:
    data = json.loads(HOOKS_JSON.read_text(encoding="utf-8"))
    return cast("dict[str, list[dict]]", data["hooks"])


def _commands_for(entries: list[dict], matcher: str) -> list[str]:
    """All hook commands registered under the entry whose matcher equals ``matcher``."""
    cmds: list[str] = []
    for entry in entries:
        if entry.get("matcher") == matcher:
            cmds.extend(h.get("command", "") for h in entry.get("hooks", []))
    return cmds


def test_precompact_hook_registered_for_auto_and_manual() -> None:
    events = _events()
    assert "PreCompact" in events, "PreCompact event not registered"
    precompact = events["PreCompact"]
    # A single matcher must cover BOTH auto and manual compaction (R6).
    covering = [
        e
        for e in precompact
        if "auto" in (e.get("matcher") or "") and "manual" in (e.get("matcher") or "")
    ]
    assert covering, "no PreCompact matcher covers both auto and manual"
    cmds = [h.get("command", "") for e in covering for h in e.get("hooks", [])]
    assert any("precompact_spore_hook.py" in c for c in cmds)


def test_sessionstart_compact_hook_registered() -> None:
    events = _events()
    cmds = _commands_for(events["SessionStart"], "compact")
    assert any("compact_spore_session_hook.py" in c for c in cmds), (
        "SessionStart(compact) not wired to compact_spore_session_hook.py"
    )


def test_stale_main_startup_resume_entry_unchanged() -> None:
    # KTD1: the new compact hook is a SEPARATE entry; the proven startup|resume path must be intact.
    events = _events()
    cmds = _commands_for(events["SessionStart"], "startup|resume")
    assert any("stale_main_session_hook.py" in c for c in cmds)
    # And the spore hook must NOT have leaked into the stale-main entry.
    assert not any("compact_spore_session_hook.py" in c for c in cmds)


def test_delegation_tripwire_hook_registered_for_file_tools() -> None:
    # U3 (#384, KTD3): PreToolUse matcher covering Write|Edit|MultiEdit|NotebookEdit ->
    # delegation_tripwire_hook.py, as a NEW entry beside validate_json's Edit|Write|MultiEdit one.
    events = _events()
    cmds = _commands_for(events["PreToolUse"], "Write|Edit|MultiEdit|NotebookEdit")
    assert any("delegation_tripwire_hook.py" in c for c in cmds), (
        "PreToolUse(Write|Edit|MultiEdit|NotebookEdit) not wired to delegation_tripwire_hook.py"
    )


def _all_commands(entries: list[dict]) -> list[str]:
    """All hook commands under an event, regardless of matcher (Stop entries have none)."""
    return [h.get("command", "") for e in entries for h in e.get("hooks", [])]


def test_delegation_stop_audit_hook_registered_for_stop() -> None:
    # U4 (#384, R3/KTD8): Stop must run delegation_stop_audit_hook.py (marker-gated).
    events = _events()
    assert "Stop" in events, "Stop event not registered"
    cmds = _all_commands(events["Stop"])
    assert any("delegation_stop_audit_hook.py" in c for c in cmds), (
        "Stop not wired to delegation_stop_audit_hook.py"
    )


def test_delegation_stop_audit_hook_registered_for_subagent_stop() -> None:
    # U4 (#384, KTD8): SubagentStop runs the SAME script — its transcript_path is the
    # subagent's own transcript, the delegation-bearing one for bridge-agent runs.
    events = _events()
    assert "SubagentStop" in events, "SubagentStop event not registered"
    cmds = _all_commands(events["SubagentStop"])
    assert any("delegation_stop_audit_hook.py" in c for c in cmds), (
        "SubagentStop not wired to delegation_stop_audit_hook.py"
    )


def test_validate_json_pretooluse_entry_unchanged() -> None:
    # The pre-existing validate_json entry must be untouched by the new registration.
    events = _events()
    cmds = _commands_for(events["PreToolUse"], "Edit|Write|MultiEdit")
    assert any("validate_json_hook.py" in c for c in cmds)
    assert not any("delegation_tripwire_hook.py" in c for c in cmds)
