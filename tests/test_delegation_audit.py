"""Tests for the fleet-core engine-parametrized delegation auditor (#384, U1/U2)."""

from __future__ import annotations

import importlib.util
import json
import subprocess
import sys
from pathlib import Path
from types import ModuleType

import pytest

ROOT = Path(__file__).parent.parent
MODULE_PATH = ROOT / "plugins" / "fleet-core" / "scripts" / "fleet_commons" / "delegation_audit.py"
STATE_MODULE_PATH = (
    ROOT / "plugins" / "fleet-core" / "scripts" / "fleet_commons" / "delegation_state.py"
)
AUDIT_STORE_MODULE_PATH = (
    ROOT / "plugins" / "fleet-core" / "scripts" / "fleet_commons" / "audit_store.py"
)
AGY_DELEGATE_PATH = ROOT / "plugins" / "agy" / "scripts" / "agy_delegate.py"
FIXTURES = ROOT / "tests" / "fixtures" / "delegation"


def _load_module(path: Path, name: str) -> ModuleType:
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


@pytest.fixture
def delegation_audit() -> ModuleType:
    return _load_module(MODULE_PATH, "delegation_audit")


@pytest.fixture
def agy_delegate() -> ModuleType:
    return _load_module(AGY_DELEGATE_PATH, "agy_delegate")


@pytest.fixture
def delegation_state() -> ModuleType:
    return _load_module(STATE_MODULE_PATH, "delegation_state")


@pytest.fixture
def audit_store(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> ModuleType:
    # Never resolve DEFAULT_AUDIT_STORE_ROOT against the real developer home directory (R5/KTD6).
    monkeypatch.setenv("HOME", str(tmp_path / "fake-home"))
    return _load_module(AUDIT_STORE_MODULE_PATH, "audit_store")


# --- classify() happy path -----------------------------------------------------------------


def test_classify_agy_real(delegation_audit: ModuleType) -> None:
    result = delegation_audit.classify(FIXTURES / "real-agy.jsonl", "agy")
    assert result.classification == "real"
    assert result.command_seen is True
    assert result.claude_file_tool_seen is False
    assert result.evidence


def test_classify_codex_real(delegation_audit: ModuleType) -> None:
    result = delegation_audit.classify(FIXTURES / "real-codex.jsonl", "codex")
    assert result.classification == "real"
    assert result.command_seen is True
    assert result.claude_file_tool_seen is False


def test_classify_agy_fallback_suspected(delegation_audit: ModuleType) -> None:
    result = delegation_audit.classify(FIXTURES / "claude-clone-agy.jsonl", "agy")
    assert result.classification == "fallback_suspected"
    assert result.command_seen is False
    assert result.claude_file_tool_seen is True


def test_classify_codex_fallback_suspected(delegation_audit: ModuleType) -> None:
    result = delegation_audit.classify(FIXTURES / "claude-clone-codex.jsonl", "codex")
    assert result.classification == "fallback_suspected"
    assert result.claude_file_tool_seen is True


# --- classify() edge cases -----------------------------------------------------------------


def test_classify_empty_transcript(delegation_audit: ModuleType) -> None:
    result = delegation_audit.classify(FIXTURES / "empty.jsonl", "agy")
    assert result.classification == "fallback_suspected"
    assert result.command_seen is False
    assert result.claude_file_tool_seen is False
    assert result.evidence == []


def test_classify_over_byte_cap_uses_capped_prefix(
    delegation_audit: ModuleType, tmp_path: Path
) -> None:
    big = tmp_path / "big.jsonl"
    line = json.dumps({"tool_name": "Read"}) + "\n"
    # Write well past a tiny cap to prove capped streaming doesn't error.
    with big.open("w", encoding="utf-8") as fh:
        for _ in range(200):
            fh.write(line)
        fh.write(
            json.dumps(
                {
                    "type": "tool_use",
                    "tool_name": "Bash",
                    "arguments": {
                        "command": "python3 plugins/agy/scripts/agy_delegate.py --launch-agy"
                    },
                }
            )
            + "\n"
        )

    # Cap smaller than the file: classification must run to completion without raising, and
    # since the real command only shows up after the cap, it must not be seen.
    tiny_cap = len(line) * 5
    lines = list(delegation_audit._iter_capped_lines(big, byte_cap=tiny_cap))  # noqa: SLF001
    assert lines  # streamed without error
    total_bytes = sum(len(entry.encode("utf-8")) for entry in lines)
    assert total_bytes <= tiny_cap + len(line)


def test_classify_unknown_engine_raises(delegation_audit: ModuleType) -> None:
    with pytest.raises(delegation_audit.UnknownEngineError):
        delegation_audit.classify(FIXTURES / "real-agy.jsonl", "not-a-real-engine")


# --- corroborate() -----------------------------------------------------------------


def test_corroborate_missing_bundle_root_is_unproven(
    delegation_audit: ModuleType, tmp_path: Path
) -> None:
    result = delegation_audit.corroborate("agy", since_ts=None, root=tmp_path)
    assert result.launched is False
    assert result.receipt_present is False
    assert result.problems


def test_corroborate_agy_launched_true_embedded_receipt(
    delegation_audit: ModuleType, tmp_path: Path
) -> None:
    run_dir = tmp_path / ".claude" / "agy" / "runs" / "run-1"
    run_dir.mkdir(parents=True)
    (run_dir / "result.json").write_text(
        json.dumps(
            {"status": "success", "agy_launched": True, "receipt": {"schema": "bridge_receipt.v1"}}
        ),
        encoding="utf-8",
    )
    result = delegation_audit.corroborate("agy", since_ts=None, root=tmp_path)
    assert result.launched is True
    assert result.receipt_present is True
    assert result.statuses == ["success"]


def test_corroborate_codex_launched_false(delegation_audit: ModuleType, tmp_path: Path) -> None:
    run_dir = tmp_path / ".claude" / "codex" / "runs" / "run-1"
    run_dir.mkdir(parents=True)
    (run_dir / "result.json").write_text(
        json.dumps({"status": "codex_unavailable", "codex_launched": False}),
        encoding="utf-8",
    )
    result = delegation_audit.corroborate("codex", since_ts=None, root=tmp_path)
    assert result.launched is False
    assert result.receipt_present is False


def test_corroborate_corrupt_result_json_never_raises(
    delegation_audit: ModuleType, tmp_path: Path
) -> None:
    run_dir = tmp_path / ".claude" / "agy" / "runs" / "run-1"
    run_dir.mkdir(parents=True)
    (run_dir / "result.json").write_text("{not valid json", encoding="utf-8")
    result = delegation_audit.corroborate("agy", since_ts=None, root=tmp_path)
    assert result.launched is False
    assert result.problems


def test_corroborate_missing_result_json_never_raises(
    delegation_audit: ModuleType, tmp_path: Path
) -> None:
    run_dir = tmp_path / ".claude" / "agy" / "runs" / "run-1"
    run_dir.mkdir(parents=True)
    result = delegation_audit.corroborate("agy", since_ts=None, root=tmp_path)
    assert result.launched is False
    assert result.problems


# --- reconcile() -----------------------------------------------------------------


def test_reconcile_real_agrees(delegation_audit: ModuleType) -> None:
    classification = delegation_audit.classify(FIXTURES / "real-agy.jsonl", "agy")
    corroboration = delegation_audit.BundleCorroboration(
        engine="agy", launched=True, receipt_present=True, statuses=["success"]
    )
    assert delegation_audit.reconcile(classification, corroboration, "ok") == "real"


def test_reconcile_fallback_suspected_short_circuits(delegation_audit: ModuleType) -> None:
    classification = delegation_audit.classify(FIXTURES / "claude-clone-agy.jsonl", "agy")
    corroboration = delegation_audit.BundleCorroboration(
        engine="agy", launched=False, receipt_present=False
    )
    assert delegation_audit.reconcile(classification, corroboration, "ok") == "fallback_suspected"


def test_reconcile_divergence_flagged_delegation_integrity(delegation_audit: ModuleType) -> None:
    classification = delegation_audit.classify(FIXTURES / "real-agy.jsonl", "agy")
    corroboration = delegation_audit.BundleCorroboration(
        engine="agy", launched=False, receipt_present=False
    )
    assert delegation_audit.reconcile(classification, corroboration, "ok") == "delegation_integrity"


# --- R7 fixture-parity: every fixture classifies identically via both auditors ---------------


@pytest.mark.parametrize(
    "fixture_name",
    ["real-agy.jsonl", "claude-clone-agy.jsonl", "empty.jsonl"],
)
def test_fixture_parity_with_agy_delegate(
    delegation_audit: ModuleType, agy_delegate: ModuleType, fixture_name: str
) -> None:
    path = FIXTURES / fixture_name
    fleet_result = delegation_audit.classify(path, "agy")
    agy_result = agy_delegate.classify_transcript(path)

    assert fleet_result.classification == agy_result.classification
    assert fleet_result.command_seen == agy_result.agy_command_seen
    assert fleet_result.claude_file_tool_seen == agy_result.claude_file_tool_seen


def test_fixture_parity_original_agy_fixtures(
    delegation_audit: ModuleType, agy_delegate: ModuleType
) -> None:
    original_fixtures = ROOT / "tests" / "fixtures" / "agy" / "transcripts"
    for path in sorted(original_fixtures.glob("*.jsonl")):
        fleet_result = delegation_audit.classify(path, "agy")
        agy_result = agy_delegate.classify_transcript(path)
        assert fleet_result.classification == agy_result.classification, path
        assert fleet_result.command_seen == agy_result.agy_command_seen, path
        assert fleet_result.claude_file_tool_seen == agy_result.claude_file_tool_seen, path


# --- delegation_state: arm/disarm/active liveness channel (#384, U2) ------------------------


def test_arm_status_disarm_round_trip(delegation_state: ModuleType, tmp_path: Path) -> None:
    delegation_state.arm("agy", "session-1", "engine_dispatch", root=tmp_path)
    entry = delegation_state.active("session-1", root=tmp_path)
    assert entry is not None
    assert entry.engine == "agy"
    assert entry.session_id == "session-1"
    assert entry.armed_by == "engine_dispatch"

    removed = delegation_state.disarm("session-1", root=tmp_path)
    assert removed is True
    assert delegation_state.active("session-1", root=tmp_path) is None


def test_stale_entry_invisible_and_reaped(delegation_state: ModuleType, tmp_path: Path) -> None:
    now = 1_000_000.0
    delegation_state.arm("agy", "session-old", "engine_dispatch", root=tmp_path, now=now)

    # Past the TTL: invisible to active().
    later = now + delegation_state.DEFAULT_TTL_SECONDS + 1
    assert delegation_state.active("session-old", root=tmp_path, now=later) is None

    # A subsequent write (arming a different session) reaps the stale entry from the file.
    delegation_state.arm("agy", "session-new", "engine_dispatch", root=tmp_path, now=later)
    marker_path = tmp_path / ".claude" / "delegation" / "active.json"
    payload = json.loads(marker_path.read_text(encoding="utf-8"))
    session_ids = {entry["session_id"] for entry in payload["entries"]}
    assert session_ids == {"session-new"}


def test_two_concurrent_sessions_isolated(delegation_state: ModuleType, tmp_path: Path) -> None:
    delegation_state.arm("agy", "session-a", "engine_dispatch", root=tmp_path)
    delegation_state.arm("codex", "session-b", "engine_dispatch", root=tmp_path)

    entry_a = delegation_state.active("session-a", root=tmp_path)
    entry_b = delegation_state.active("session-b", root=tmp_path)
    assert entry_a is not None and entry_a.engine == "agy"
    assert entry_b is not None and entry_b.engine == "codex"

    delegation_state.disarm("session-a", root=tmp_path)
    assert delegation_state.active("session-a", root=tmp_path) is None
    # Disarming one session must not touch the other's entry.
    assert delegation_state.active("session-b", root=tmp_path) is not None


def test_arm_twice_supersedes_in_place(delegation_state: ModuleType, tmp_path: Path) -> None:
    delegation_state.arm("agy", "session-1", "engine_dispatch", root=tmp_path, now=100.0)
    delegation_state.arm("codex", "session-1", "engine_dispatch_retry", root=tmp_path, now=200.0)

    entry = delegation_state.active("session-1", root=tmp_path, now=200.0)
    assert entry is not None
    assert entry.engine == "codex"
    assert entry.armed_by == "engine_dispatch_retry"
    assert entry.armed_at == 200.0

    marker_path = tmp_path / ".claude" / "delegation" / "active.json"
    payload = json.loads(marker_path.read_text(encoding="utf-8"))
    assert len(payload["entries"]) == 1


def test_corrupt_marker_json_is_unarmed_fail_open(
    delegation_state: ModuleType, tmp_path: Path
) -> None:
    marker_path = tmp_path / ".claude" / "delegation" / "active.json"
    marker_path.parent.mkdir(parents=True)
    marker_path.write_text("{not valid json", encoding="utf-8")

    # Fail-open contract: active() never raises, corrupt file reads as unarmed.
    assert delegation_state.active("session-1", root=tmp_path) is None


def test_missing_marker_file_is_unarmed_fail_open(
    delegation_state: ModuleType, tmp_path: Path
) -> None:
    assert delegation_state.active("session-1", root=tmp_path) is None


def test_cli_arm_status_disarm_round_trip(tmp_path: Path) -> None:
    def run_cli(*args: str) -> dict:
        result = subprocess.run(
            [sys.executable, str(STATE_MODULE_PATH), "--root", str(tmp_path), *args],
            capture_output=True,
            text=True,
            check=True,
        )
        payload = json.loads(result.stdout)
        assert isinstance(payload, dict)
        return payload

    armed = run_cli(
        "arm", "--engine", "agy", "--session-id", "cli-session", "--armed-by", "cli-test"
    )
    assert armed["engine"] == "agy"
    assert armed["session_id"] == "cli-session"

    status = run_cli("status", "--session-id", "cli-session")
    assert status["armed"] is True
    assert status["engine"] == "agy"

    disarmed = run_cli("disarm", "--session-id", "cli-session")
    assert disarmed["removed"] is True

    final_status = run_cli("status", "--session-id", "cli-session")
    assert final_status["armed"] is False


def test_ttl_exact_boundary_still_live(delegation_state: ModuleType, tmp_path: Path) -> None:
    """Pin the strict `>` staleness comparison: age == TTL is still live, age == TTL+1 is not."""
    now = 1_000_000.0
    delegation_state.arm("agy", "session-boundary", "engine_dispatch", root=tmp_path, now=now)

    at_boundary = delegation_state.active(
        "session-boundary", root=tmp_path, now=now + delegation_state.DEFAULT_TTL_SECONDS
    )
    assert at_boundary is not None

    past_boundary = delegation_state.active(
        "session-boundary", root=tmp_path, now=now + delegation_state.DEFAULT_TTL_SECONDS + 1
    )
    assert past_boundary is None


# --- audit_store.write_once_draft() guard (#396, U1) -----------------------------------------


def test_draft_snapshot_write_once_guard(audit_store: ModuleType, tmp_path: Path) -> None:
    """A second write-once draft snapshot for the same run_id is rejected, never overwritten."""
    store = audit_store.Store.for_root(tmp_path / "audit-store")
    first_content = "--- a/foo.py\n+++ b/foo.py\n@@ -1 +1 @@\n-old\n+new\n"

    audit_store.write_once_draft(store, "run-1", first_content)

    with pytest.raises(audit_store.AuditStoreError):
        audit_store.write_once_draft(store, "run-1", "a completely different second attempt")

    # The first snapshot's bytes are unchanged by the rejected second attempt.
    assert audit_store.resolve_draft(store, "run-1") == first_content


# --- delegation_audit.reconcile_store() (#396, U2) -------------------------------------------


def _valid_receipt(run_id: str) -> dict[str, object]:
    return {
        "schema": "bridge_receipt.v1",
        "engine_id": "agy",
        "variant": "flash",
        "transport": "cli",
        "wall_time_s": 1.0,
        "bytes_produced": 10,
        "runner": {"pid": 1, "argv": ["agy"], "exit_code": 0},
        "run_id": run_id,
    }


def test_flags_forced_fallback_only(
    delegation_audit: ModuleType, audit_store: ModuleType, tmp_path: Path
) -> None:
    """Exactly the forced-fallback run is flagged; the genuinely-real run never is."""
    store = audit_store.Store.for_root(tmp_path / "audit-store")

    # A real delegation: claims ran-as-requested AND carries a schema-valid receipt.
    audit_store.mirror_manifest(store, "real-run", {"disposition": "ran-as-requested"})
    audit_store.mirror_receipt(store, "real-run", _valid_receipt("real-run"))

    # A forced fallback: claims ran-as-requested but has no receipt at all (the engine never
    # actually launched — the fleet-wide silent-no-op shape this issue exists to catch).
    audit_store.mirror_manifest(store, "forced-fallback-run", {"disposition": "ran-as-requested"})

    entries = delegation_audit.reconcile_store(store)
    flagged = {entry.run_id for entry in entries if entry.flagged}

    assert flagged == {"forced-fallback-run"}


def test_reconcile_store_degrades_on_corrupt_manifest(
    delegation_audit: ModuleType, audit_store: ModuleType, tmp_path: Path
) -> None:
    """A corrupt manifest.json degrades to 'no claim' rather than raising."""
    store = audit_store.Store.for_root(tmp_path / "audit-store")
    manifest_path = store.manifest_path("corrupt-run")
    manifest_path.parent.mkdir(parents=True, exist_ok=True)
    manifest_path.write_text("{not valid json", encoding="utf-8")

    entries = delegation_audit.reconcile_store(store, run_ids=["corrupt-run"])

    assert len(entries) == 1
    assert entries[0].flagged is False
    assert entries[0].claimed_real is False
