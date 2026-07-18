"""Host SendMessage binding tests for Saga liveness re-pings (#357)."""

from __future__ import annotations

import hashlib
import importlib.util
import json
import subprocess
import sys
from pathlib import Path
from types import ModuleType

ROOT = Path(__file__).parent.parent
TEAM_SCRIPTS = ROOT / "plugins" / "team-execution" / "skills" / "team-execution" / "scripts"
SAGA_SCRIPTS = ROOT / "plugins" / "saga" / "scripts"
HOOK = ROOT / "plugins" / "saga" / "hooks" / "liveness_reping_hook.py"
HOOKS_JSON = ROOT / "plugins" / "saga" / "hooks" / "hooks.json"


def _load(path: Path, name: str, extra: Path) -> ModuleType:
    if str(extra) not in sys.path:
        sys.path.insert(0, str(extra))
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


LP = _load(TEAM_SCRIPTS / "liveness_protocol.py", "hook_test_liveness_protocol", TEAM_SCRIPTS)
EVENTS = _load(SAGA_SCRIPTS / "liveness_events.py", "hook_test_liveness_events", SAGA_SCRIPTS)
RL = _load(SAGA_SCRIPTS / "run_ledger.py", "hook_test_run_ledger", SAGA_SCRIPTS)
HOOK_MODULE = _load(HOOK, "hook_test_liveness_reping_hook", HOOK.parent)


def _git(repo: Path, *args: str) -> str:
    return subprocess.run(
        ["git", "-C", str(repo), *args],
        capture_output=True,
        text=True,
        check=True,
    ).stdout.strip()


def _repo(path: Path) -> Path:
    path.mkdir()
    _git(path, "init", "-q")
    _git(path, "config", "user.email", "test@example.com")
    _git(path, "config", "user.name", "Test")
    (path / "worker.py").write_text("print('base')\n", encoding="utf-8")
    _git(path, "add", "worker.py")
    _git(path, "commit", "-q", "-m", "initial")
    return path


def _digest(label: str) -> str:
    return hashlib.sha256(label.encode()).hexdigest()


def _setup(repo: Path, *, message: str) -> tuple[dict[str, object], dict[str, object], str]:
    baseline = LP.capture_spawn_baseline(["worker.py"], repo_root=repo, observed_monotonic=0.0)
    ledger = RL.RunLedger.resolve(repo)
    manifest = RL.append_fact_atomic(
        ledger,
        RL.build_fact(
            "dispatch-settlement",
            subplot_id="sub-357",
            at="2026-07-17T00:00:00Z",
            event="manifest",
            dispatch_id="dispatch-1",
            site="team-execution",
            units=[{"unit_id": "unit-1", "idempotency_key": "unit-1-key", "deliverables": []}],
            casualty_threshold_percent=0,
            max_attempts=3,
        ),
    )
    spawn = RL.append_fact_atomic(
        ledger,
        RL.build_fact(
            "dispatch-settlement",
            subplot_id="sub-357",
            at="2026-07-17T00:00:00Z",
            event="spawn",
            dispatch_id="dispatch-1",
            unit_id="unit-1",
            attempt=1,
            idempotency_key="unit-1-key",
        ),
    )
    identity: dict[str, object] = {
        "session_id": "session-1",
        "subplot_id": "sub-357",
        "dispatch_id": "dispatch-1",
        "unit_id": "unit-1",
        "attempt": 1,
        "resident_id": "worker-1",
        "agent_id": "agent-1",
        "lease_id": "lease-1",
        "resource_sha256": _digest("resource"),
        "broker_epoch": "epoch-1",
        "fencing_sequence": 1,
        "boot_id": LP.fleet_commons_shim.load("lease_broker").Providers().boot_id(),
        "manifest_sha256": manifest["this_hash"],
        "spawn_sha256": spawn["this_hash"],
        "token_sha256": _digest("token"),
        "lease_ttl_seconds": 50.0,
        "baseline_sha256": baseline["baseline_digest"],
        "path_set_sha256": baseline["path_set_sha256"],
    }
    resolution = LP.SagaResolution(root=ROOT / "plugins" / "saga", rung=1)
    opened = LP.open_subject(
        repo_root=repo,
        identity=identity,
        event_id="open-1",
        at="2026-07-17T00:00:00Z",
        observed_monotonic=0.0,
        source_ref="manifest-spawn-lease-1",
        resolution=resolution,
    )
    claim = LP.claim_reping(
        repo_root=repo,
        identity=identity,
        event_id="claim-1",
        at="2026-07-17T00:01:00Z",
        now=60.0,
        resolution=resolution,
    )
    assert claim is not None
    request = LP.request_digest("agent-1", message)
    LP.stage_reping_send(
        repo_root=repo,
        identity=identity,
        claim=claim,
        recipient="agent-1",
        request_sha256=request,
        staged_monotonic=60.0,
        response_window_seconds=10.0,
    )
    return identity, claim, opened["subject_id"]


def _pre(
    repo: Path, message: str, *, tool_use_id: str = "tool-1", recipient: str = "agent-1"
) -> None:
    HOOK_MODULE.dispatch(
        {
            "hook_event_name": "PreToolUse",
            "tool_name": "SendMessage",
            "tool_use_id": tool_use_id,
            "tool_input": {"recipient": recipient, "message": message},
            "cwd": str(repo),
        }
    )


def _post(
    repo: Path,
    *,
    failure: bool = False,
    definitive: bool = False,
    tool_use_id: str = "tool-1",
) -> None:
    payload: dict[str, object] = {
        "hook_event_name": "PostToolUseFailure" if failure else "PostToolUse",
        "tool_name": "SendMessage",
        "tool_use_id": tool_use_id,
        "observed_monotonic": 60.0,
        "cwd": str(repo),
    }
    if definitive:
        payload["tool_response"] = {"delivery_status": "definitive-not-sent"}
    HOOK_MODULE.dispatch(payload)


def test_accepted_send_records_one_proven_window_without_raw_message(tmp_path: Path) -> None:
    repo = _repo(tmp_path / "repo")
    message = "report progress SECRET-MESSAGE-BODY"
    _, claim, subject_id = _setup(repo, message=message)
    _pre(repo, message)
    _post(repo)
    records = RL.read_facts(RL.RunLedger.resolve(repo))
    sent = [record for record in records if record.get("event") == "reping-sent"]
    assert len(sent) == 1
    assert sent[0]["claim_key"] == claim["claim_key"]
    assert sent[0]["request_digest"] == LP.request_digest("agent-1", message)
    state_root = LP.pending_dir(repo).parent
    persisted = "".join(
        path.read_text(encoding="utf-8", errors="replace") for path in state_root.rglob("*.json")
    )
    assert "SECRET-MESSAGE-BODY" not in persisted
    decision = EVENTS.poll_subject(RL.RunLedger.resolve(repo), subject_id, now=71.0)
    assert decision["reping"]["liveness_attempt"] == 1


def test_definitive_non_send_allows_exact_predecessor_bound_retry(tmp_path: Path) -> None:
    repo = _repo(tmp_path / "repo")
    message = "report progress"
    _, _, subject_id = _setup(repo, message=message)
    _pre(repo, message)
    _post(repo, failure=True, definitive=True)
    records = RL.read_facts(RL.RunLedger.resolve(repo))
    failed = [record for record in records if record.get("event") == "reping-send-failed"]
    assert len(failed) == 1 and failed[0]["definitive_not_sent"] is True
    decision = EVENTS.poll_subject(RL.RunLedger.resolve(repo), subject_id, now=61.0)
    assert decision["reping"]["retry_ordinal"] == 1
    assert decision["reping"]["predecessor_failure_ref"] == failed[0]["event_id"]


def test_ambiguous_failure_records_no_send_fact_and_remains_unresolved(tmp_path: Path) -> None:
    repo = _repo(tmp_path / "repo")
    message = "report progress"
    _, _, subject_id = _setup(repo, message=message)
    _pre(repo, message)
    _post(repo, failure=True, definitive=False)
    records = RL.read_facts(RL.RunLedger.resolve(repo))
    assert not any(
        record.get("event") in {"reping-sent", "reping-send-failed"} for record in records
    )
    decision = EVENTS.poll_subject(RL.RunLedger.resolve(repo), subject_id, now=1000.0)
    assert decision["classification"] == "reping-send-unresolved"
    receipts = list((LP.pending_dir(repo).parent / "receipts").glob("*.json"))
    assert json.loads(receipts[0].read_text())["status"] == "unresolved"


def test_unstaged_or_wrong_recipient_sendmessage_is_ignored(tmp_path: Path) -> None:
    repo = _repo(tmp_path / "repo")
    message = "report progress"
    _setup(repo, message=message)
    _pre(repo, message, recipient="another-agent")
    state_root = LP.pending_dir(repo).parent
    assert not (state_root / "inflight").exists()
    assert len(list((state_root / "pending").glob("*.json"))) == 1


def test_post_replay_after_cleanup_is_silent_and_does_not_duplicate(tmp_path: Path) -> None:
    repo = _repo(tmp_path / "repo")
    message = "report progress"
    _setup(repo, message=message)
    _pre(repo, message)
    _post(repo)
    _post(repo)
    records = RL.read_facts(RL.RunLedger.resolve(repo))
    assert sum(record.get("event") == "reping-sent" for record in records) == 1


def test_hooks_json_wires_pre_post_and_failure_sendmessage_events() -> None:
    hooks = json.loads(HOOKS_JSON.read_text())["hooks"]
    for event in ("PreToolUse", "PostToolUse", "PostToolUseFailure"):
        entries = [entry for entry in hooks[event] if entry.get("matcher") == "SendMessage"]
        assert len(entries) == 1
        commands = [hook["command"] for hook in entries[0]["hooks"]]
        assert any("liveness_reping_hook.py" in command for command in commands)
