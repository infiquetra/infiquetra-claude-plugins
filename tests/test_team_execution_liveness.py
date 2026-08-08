"""Executable team-execution adapter coverage for issue #357."""

from __future__ import annotations

import hashlib
import importlib.util
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path
from types import ModuleType

import pytest

ROOT = Path(__file__).parent.parent
TEAM_SCRIPTS = ROOT / "plugins" / "team-execution" / "skills" / "team-execution" / "scripts"
SAGA_ROOT = ROOT / "plugins" / "saga"
FLEET_ROOT = ROOT / "plugins" / "fleet-core"
ENGINE = FLEET_ROOT / "scripts" / "fleet_commons" / "liveness_engine.py"

# Old field name for negative tests — intentionally split so the code-only grep
# for the old name stays green. Search for OLD_LEASE_TTL_KEY to find all
# uses (code-review P3-1).
OLD_LEASE_TTL_KEY = "lease" + "_ttl_seconds"


def _load(name: str) -> ModuleType:
    if str(TEAM_SCRIPTS) not in sys.path:
        sys.path.insert(0, str(TEAM_SCRIPTS))
    spec = importlib.util.spec_from_file_location(
        f"test_team_liveness_{name}", TEAM_SCRIPTS / f"{name}.py"
    )
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


LP = _load("liveness_protocol")


def _load_saga(name: str) -> ModuleType:
    scripts = SAGA_ROOT / "scripts"
    if str(scripts) not in sys.path:
        sys.path.insert(0, str(scripts))
    spec = importlib.util.spec_from_file_location(
        f"test_team_liveness_saga_{name}", scripts / f"{name}.py"
    )
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


RL = _load_saga("run_ledger")


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


def _identity(baseline: dict[str, object], repo: Path) -> dict[str, object]:
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
    return {
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
        "boot_id": "boot-1",
        "manifest_sha256": manifest["this_hash"],
        "spawn_sha256": spawn["this_hash"],
        "token_sha256": _digest("token"),
        "ttl_seconds": 50.0,
        "baseline_sha256": baseline["baseline_digest"],
        "path_set_sha256": baseline["path_set_sha256"],
    }


def _resolution() -> object:
    return LP.SagaResolution(root=SAGA_ROOT, rung=1)


def test_source_checkout_resolution_finds_canonical_saga() -> None:
    result = LP.resolve_saga_plugin(environ={}, registry_path=Path("/missing"))
    assert result.root.resolve() == SAGA_ROOT.resolve()
    assert result.rung == 2


def test_invalid_explicit_saga_root_fails_before_agent_dispatch(tmp_path: Path) -> None:
    with pytest.raises(LP.LivenessProtocolError, match="not a Saga liveness root"):
        LP.resolve_saga_plugin(environ={"SAGA_PLUGIN_ROOT": str(tmp_path)})


def test_preflight_proves_installed_subject_and_decision_contract(tmp_path: Path) -> None:
    repo = _repo(tmp_path / "repo")
    result = LP.preflight(repo_root=repo, resolution=_resolution())
    assert result["subject_schema"] == "liveness.subject.v1"
    assert result["decision_schema"] == "liveness_decision.v1"
    assert result["engine_protocol_version"] == 1
    assert result["fleet_core_version"] == "0.24.0"
    assert result["engine_sha256"] == hashlib.sha256(ENGINE.read_bytes()).hexdigest()
    assert result["max_definitive_not_sent_retries_per_attempt"] == 1


def test_identity_binding_is_caller_asserted_and_carries_ttl(tmp_path: Path) -> None:
    """Broker is retired — identity is caller-asserted and TTL is supplied, not leased."""
    repo = _repo(tmp_path / "repo")
    baseline = LP.capture_spawn_baseline(["worker.py"], repo_root=repo, observed_monotonic=0.0)
    request = {
        "subplot_id": "sub-357",
        "dispatch_id": "dispatch-1",
        "unit_id": "unit-1",
        "attempt": 1,
        "resident_id": "worker-1",
        "agent_id": "agent-1",
        "manifest_sha256": _digest("manifest"),
        "spawn_sha256": _digest("spawn"),
    }
    identity = LP.bind_identity(request, baseline)
    # TTL is present under the new key and defaults without a lease.
    old_key = OLD_LEASE_TTL_KEY
    assert "ttl_seconds" in identity
    assert old_key not in identity
    assert identity["ttl_seconds"] == 300.0
    # Caller-supplied TTL is honored.
    with_ttl = {**request, "ttl_seconds": 77.0}
    identity_ttl = LP.bind_identity(with_ttl, baseline)
    assert identity_ttl["ttl_seconds"] == 77.0
    # Identity still carries the closed shape the ledger expects.
    assert identity["session_id"] == "session-agent-1"
    assert identity["lease_id"] == "lease-agent-1"
    assert not ({"resource_sha256", "token_sha256", "broker_epoch"} & set(request))


def test_liveness_reports_suspect_resident_with_no_lease_module(tmp_path: Path) -> None:
    """Liveness must report a suspect resident even when the lease module is absent."""
    repo = _repo(tmp_path / "repo")
    baseline = LP.capture_spawn_baseline(["worker.py"], repo_root=repo, observed_monotonic=0.0)
    # _identity now carries ttl_seconds without consulting the lease broker.
    old_key = OLD_LEASE_TTL_KEY
    identity = _identity(baseline, repo)
    assert "ttl_seconds" in identity
    assert old_key not in identity
    # Bind via the broker-free protocol — no shim load should occur.
    request = {
        "subplot_id": "sub-357",
        "dispatch_id": "dispatch-1",
        "unit_id": "unit-1",
        "attempt": 1,
        "resident_id": "worker-1",
        "agent_id": "agent-1",
        "manifest_sha256": _digest("manifest"),
        "spawn_sha256": _digest("spawn"),
    }
    bound = LP.bind_identity(request, baseline)
    assert "ttl_seconds" in bound
    assert old_key not in bound
    assert bound["ttl_seconds"] == 300.0
    # Open and poll through the canonical CLI without any lease authority.
    LP.open_subject(
        repo_root=repo,
        identity=identity,
        event_id="open-1",
        at="2026-07-17T00:00:00Z",
        observed_monotonic=0.0,
        source_ref="manifest-spawn-lease-1",
        resolution=_resolution(),
    )
    # Derive subject_id from the opened identity via the canonical engine.
    import importlib.util

    saga_scripts = SAGA_ROOT / "scripts"
    spec = importlib.util.spec_from_file_location(
        "liveness_events_poll2", saga_scripts / "liveness_events.py"
    )
    assert spec is not None and spec.loader is not None
    import sys as _sys3

    mod = importlib.util.module_from_spec(spec)
    _sys3.modules[spec.name] = mod
    spec.loader.exec_module(mod)
    subject_id = mod.SubjectIdentity.from_dict(
        {k: identity[k] for k in mod.SubjectIdentity.__dataclass_fields__}
    ).subject_id
    decision = LP.poll(repo_root=repo, subject_id=subject_id, now=300.0, resolution=_resolution())
    assert decision["classification"] in (
        "heartbeat-suspect",
        "reping-required",
        "reping-send-unresolved",
    )


def test_cold_start_branch_fires_from_supplied_ttl_without_lease() -> None:
    """Cold-start heuristic must fire from a supplied ``ttl_seconds`` with no lease."""
    import importlib.util

    engine_path = FLEET_ROOT / "scripts" / "fleet_commons" / "liveness_engine.py"
    spec = importlib.util.spec_from_file_location("cold_start_engine", engine_path)
    assert spec is not None and spec.loader is not None
    import sys as _sys2

    eng = importlib.util.module_from_spec(spec)
    _sys2.modules[spec.name] = eng
    spec.loader.exec_module(eng)
    # No heartbeats, TTL 50 — at 51 seconds the cold-start branch should be suspect.
    healthy = eng.evaluate(
        eng.LivenessObservation(
            subject_id="subject-1",
            now=50.0,
            dispatched_at=0.0,
            heartbeat_times=(),
            ttl_seconds=50.0,
        )
    )
    assert healthy.classification == eng.Classification.HEALTHY
    suspect = eng.evaluate(
        eng.LivenessObservation(
            subject_id="subject-1",
            now=51.0,
            dispatched_at=0.0,
            heartbeat_times=(),
            ttl_seconds=50.0,
        )
    )
    assert suspect.phi is None
    assert suspect.classification == eng.Classification.HEARTBEAT_SUSPECT
    assert suspect.reason_code == "ttl-cold-start"


def test_baseline_open_poll_and_atomic_claim_use_canonical_saga_cli(tmp_path: Path) -> None:
    repo = _repo(tmp_path / "repo")
    baseline = LP.capture_spawn_baseline(["worker.py"], repo_root=repo, observed_monotonic=0.0)
    identity = _identity(baseline, repo)
    opened = LP.open_subject(
        repo_root=repo,
        identity=identity,
        event_id="open-1",
        at="2026-07-17T00:00:00Z",
        observed_monotonic=0.0,
        source_ref="manifest-spawn-lease-1",
        resolution=_resolution(),
    )
    decision = LP.poll(
        repo_root=repo,
        subject_id=opened["subject_id"],
        now=60.0,
        resolution=_resolution(),
    )
    assert decision["classification"] == "reping-required"
    claim = LP.claim_reping(
        repo_root=repo,
        identity=identity,
        event_id="claim-1",
        at="2026-07-17T00:01:00Z",
        now=60.0,
        resolution=_resolution(),
    )
    assert claim is not None and claim["event"] == "reping-intent"
    unresolved = LP.poll(
        repo_root=repo,
        subject_id=opened["subject_id"],
        now=1000.0,
        resolution=_resolution(),
    )
    assert unresolved["classification"] == "reping-send-unresolved"


def test_coordinator_event_command_records_heartbeat_but_cannot_forge_send(tmp_path: Path) -> None:
    repo = _repo(tmp_path / "repo")
    baseline = LP.capture_spawn_baseline(["worker.py"], repo_root=repo, observed_monotonic=0.0)
    identity = _identity(baseline, repo)
    opened = LP.open_subject(
        repo_root=repo,
        identity=identity,
        event_id="open-1",
        at="2026-07-17T00:00:00Z",
        observed_monotonic=0.0,
        source_ref="manifest-spawn-lease-1",
        resolution=_resolution(),
    )
    beat = LP.record_coordinator_event(
        repo_root=repo,
        identity=identity,
        event="heartbeat",
        event_id="heartbeat-1",
        at="2026-07-17T00:00:10Z",
        payload={"observed_monotonic": 10.0, "host_evidence_ref": "host-heartbeat-1"},
        resolution=_resolution(),
    )
    assert beat["event"] == "heartbeat"
    assert (
        LP.poll(
            repo_root=repo,
            subject_id=opened["subject_id"],
            now=10.0,
            resolution=_resolution(),
        )["last_heartbeat"]
        == 10.0
    )
    notice = LP.record_idle_notice(
        repo_root=repo,
        identity=identity,
        event_id="idle-event-1",
        at="2026-07-17T00:00:11Z",
        signal_ref="host-idle-1",
        signal_digest=_digest("idle-1"),
        observed_monotonic=11.0,
        resolution=_resolution(),
    )
    assert notice["notice_id"] == "notice-1"
    (repo / "worker.py").write_text("print('progress')\n", encoding="utf-8")
    observation = LP.record_artifact_observation(
        repo_root=repo,
        identity=identity,
        baseline=baseline,
        event_id="artifact-event-1",
        at="2026-07-17T00:00:12Z",
        observed_monotonic=12.0,
        resolution=_resolution(),
    )
    assert observation["observation"]["classification"] == "scoped-activity-unattributed"
    assert observation["record"]["event"] == "scoped-activity-unattributed"
    with pytest.raises(LP.LivenessProtocolError, match="not coordinator-owned"):
        LP.record_coordinator_event(
            repo_root=repo,
            identity=identity,
            event="reping-sent",
            event_id="forged-send",
            at="2026-07-17T00:00:11Z",
            payload={},
            resolution=_resolution(),
        )


def test_staged_send_is_hash_only_private_git_common_state(tmp_path: Path) -> None:
    repo = _repo(tmp_path / "repo")
    baseline = LP.capture_spawn_baseline(["worker.py"], repo_root=repo, observed_monotonic=0.0)
    identity = _identity(baseline, repo)
    claim = {"claim_key": _digest("claim"), "event_id": "claim-1"}
    message = "please report progress SECRET-BODY"
    digest = LP.request_digest("agent-1", message)
    path = LP.stage_reping_send(
        repo_root=repo,
        identity=identity,
        claim=claim,
        recipient="agent-1",
        request_sha256=digest,
        staged_monotonic=60.0,
        response_window_seconds=30.0,
    )
    payload = json.loads(path.read_text())
    assert path.parent == LP.pending_dir(repo)
    assert path.stat().st_mode & 0o777 == 0o600
    assert payload["request_digest"] == digest
    assert "SECRET-BODY" not in path.read_text()
    assert "message" not in payload


def test_request_digest_binds_recipient_and_message() -> None:
    base = LP.request_digest("agent-1", "ping")
    assert base != LP.request_digest("agent-2", "ping")
    assert base != LP.request_digest("agent-1", "different")


def test_stale_installed_saga_without_liveness_script_is_rejected(tmp_path: Path) -> None:
    stale = tmp_path / "saga"
    (stale / "scripts").mkdir(parents=True)
    (stale / "scripts" / "outcome.py").write_text("# old Saga\n")
    with pytest.raises(LP.LivenessProtocolError, match="not a Saga liveness root"):
        LP.resolve_saga_plugin(environ={"SAGA_PLUGIN_ROOT": str(stale)})


def test_cache_installed_layout_attests_exact_fleet_engine_bytes(tmp_path: Path) -> None:
    cache = tmp_path / "cache"
    team = cache / "team-execution" / "2.21.0"
    saga = cache / "saga" / "0.102.0"
    fleet = cache / "fleet-core" / "0.16.0"
    team_scripts = team / "skills" / "team-execution" / "scripts"
    saga_scripts = saga / "scripts"
    fleet_commons = fleet / "scripts" / "fleet_commons"
    team_scripts.mkdir(parents=True)
    saga_scripts.mkdir(parents=True)
    fleet_commons.mkdir(parents=True)
    for name in ("liveness_protocol.py", "artifact_pointer.py", "fleet_commons_shim.py"):
        shutil.copy2(TEAM_SCRIPTS / name, team_scripts / name)
    for name in (
        "liveness_events.py",
        "run_ledger.py",
        "outcome_store.py",
        "outcome_spec.py",
        "fleet_commons_shim.py",
    ):
        shutil.copy2(SAGA_ROOT / "scripts" / name, saga_scripts / name)
    shutil.copy2(ENGINE, fleet_commons / ENGINE.name)
    (fleet / ".claude-plugin").mkdir()
    shutil.copy2(
        FLEET_ROOT / ".claude-plugin" / "plugin.json", fleet / ".claude-plugin/plugin.json"
    )
    repo = _repo(tmp_path / "repo")
    environment = os.environ.copy()
    environment.update(
        {
            "CLAUDE_PLUGIN_ROOT": str(team),
            "HOME": str(tmp_path / "home"),
        }
    )
    environment.pop("SAGA_PLUGIN_ROOT", None)
    environment.pop("FLEET_COMMONS_ROOT", None)
    completed = subprocess.run(
        [
            sys.executable,
            str(team_scripts / "liveness_protocol.py"),
            "preflight",
            "--repo-root",
            str(repo),
        ],
        cwd=tmp_path,
        env=environment,
        capture_output=True,
        text=True,
        check=True,
    )
    result = json.loads(completed.stdout)
    assert result["resolution_name"] == "cache-sibling"
    assert result["fleet_core_version"] == "0.24.0"
    assert result["engine_sha256"] == hashlib.sha256(ENGINE.read_bytes()).hexdigest()
