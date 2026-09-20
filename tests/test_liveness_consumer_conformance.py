"""Source-aware consumer and poll-boundary conformance for issue #357."""

from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).parent.parent
ENGINE = ROOT / "plugins" / "fleet-core" / "scripts" / "fleet_commons" / "liveness_engine.py"
OUTCOME = ROOT / "plugins" / "saga" / "scripts" / "outcome_liveness.py"
EVENTS = ROOT / "plugins" / "saga" / "scripts" / "liveness_events.py"
INVENTORY = ROOT / "plugins" / "saga" / "references" / "liveness-consumer-sites.md"
HOOKS = ROOT / "plugins" / "saga" / "hooks" / "hooks.json"


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def _semver(version: str) -> tuple[int, ...]:
    return tuple(int(part) for part in version.split("."))


def test_fleet_core_has_the_only_liveness_engine_implementation() -> None:
    implementations = [
        path for path in (ROOT / "plugins").rglob("liveness_engine.py") if "tests" not in path.parts
    ]
    assert implementations == [ENGINE]
    assert 'fleet_commons_shim.load("liveness_engine")' in _read(OUTCOME)
    assert 'fleet_commons_shim.load("liveness_engine")' in _read(EVENTS)
    # The third file was the archived plugin's protocol script (issue #1030).


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


def test_no_hook_gates_sendmessage() -> None:
    """No saga hook may gate ``SendMessage`` -- it hard-blocked the agent-teams primitive.

    ``liveness_reping_hook.py`` extracted the recipient from ``tool_input`` keys
    ``recipient``/``target_agent_id``/``target``.  The host tool's actual schema is
    ``{to, message, summary}``, so extraction always failed, the hook raised, and
    ``PreToolUse`` exited 2 -- blocking *every* ``SendMessage`` call rather than only the
    staged-claim ones its own docstring promised to touch (the recipient parse ran before
    the pending-claim lookup, so the "passes silently" path was unreachable).

    This is a regression guard, not a conformance check: re-registering any blocking hook
    on ``SendMessage`` re-breaks agent teams.  A future liveness binding must read ``to``
    and must fail open.
    """
    hooks = json.loads(_read(HOOKS))["hooks"]
    for event, rows in hooks.items():
        for row in rows:
            matcher = row.get("matcher") or ""
            assert "SendMessage" not in matcher, (
                f"{event} registers a hook on SendMessage ({matcher!r}); "
                "a PreToolUse failure there blocks all inter-agent messaging"
            )


def test_detection_has_no_destructive_action_owner() -> None:
    for path in (ENGINE, EVENTS):
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
