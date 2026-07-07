"""DoD-named delegation-tripwire tests (#384).

This file is born in U1 with the codex-parity DoD test and is extended by U3-U6 as those
units land (PreToolUse block, Stop-hook audit, dispatch-layer reconciliation, integration
scenarios). U1's slice and U3's PreToolUse-block slice live here.
"""

from __future__ import annotations

import importlib.util
import json
import sys
import time
from pathlib import Path
from types import ModuleType
from typing import Any
from unittest.mock import patch

import pytest

ROOT = Path(__file__).parent.parent
MODULE_PATH = ROOT / "plugins" / "fleet-core" / "scripts" / "fleet_commons" / "delegation_audit.py"
HOOK_PATH = ROOT / "plugins" / "saga" / "hooks" / "delegation_tripwire_hook.py"

sys.path.insert(0, str(ROOT / "plugins" / "fleet-core" / "scripts"))
import fleet_commons_shim  # noqa: E402

_delegation_state = fleet_commons_shim.load("delegation_state")


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
    return _load_module(MODULE_PATH, "delegation_audit_tripwire")


def test_codex_bridge_untested_run_classified_false(
    delegation_audit: ModuleType, tmp_path: Path
) -> None:
    """R5 codex parity: Claude-finished run, no codex launch, bundle codex_launched=false → flagged.

    The transcript shows Claude editing files directly with no codex Bash command; the bundle's
    ``result.json`` reports ``codex_launched: false``. The same engine-parametrized auditor that
    handles agy must classify this as a suspected fallback (not silently accepted as ``real``).
    """
    transcript = tmp_path / "transcript.jsonl"
    transcript.write_text(
        "\n".join(
            [
                json.dumps(
                    {
                        "type": "tool_use",
                        "tool_name": "Read",
                        "arguments": {"file_path": "plugins/codex/scripts/codex_delegate.py"},
                    }
                ),
                json.dumps(
                    {
                        "type": "tool_use",
                        "tool_name": "Edit",
                        "arguments": {
                            "file_path": "plugins/codex/scripts/codex_delegate.py",
                            "old_string": "old",
                            "new_string": "new",
                        },
                    }
                ),
            ]
        )
        + "\n",
        encoding="utf-8",
    )

    run_dir = tmp_path / ".claude" / "codex" / "runs" / "run-untested"
    run_dir.mkdir(parents=True)
    (run_dir / "result.json").write_text(
        json.dumps(
            {"schema": "codex.result.v1", "status": "codex_unavailable", "codex_launched": False}
        ),
        encoding="utf-8",
    )

    classification = delegation_audit.classify(transcript, "codex")
    corroboration = delegation_audit.corroborate("codex", since_ts=None, root=tmp_path)
    verdict = delegation_audit.reconcile(classification, corroboration, self_report="ok")

    assert classification.classification == "fallback_suspected"
    assert classification.claude_file_tool_seen is True
    assert classification.command_seen is False
    assert corroboration.launched is False
    assert verdict == "fallback_suspected"


# ---------------------------------------------------------------------------
# U3 — PreToolUse block (plugins/saga/hooks/delegation_tripwire_hook.py)
# ---------------------------------------------------------------------------


def _load_hook_module() -> Any:
    spec = importlib.util.spec_from_file_location("delegation_tripwire_hook", HOOK_PATH)
    assert spec is not None and spec.loader is not None
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)  # type: ignore[union-attr]
    return mod


@pytest.fixture
def hook() -> Any:
    return _load_hook_module()


def _run_main(hook: Any, payload: dict) -> int:
    with patch.object(sys, "stdin") as mock_stdin:
        mock_stdin.read.return_value = json.dumps(payload)
        with pytest.raises(SystemExit) as exc_info:
            hook.main()
    code = exc_info.value.code
    assert isinstance(code, int)
    return code


def _arm(root: Path, engine: str, session_id: str, *, armed_at: float | None = None) -> None:
    _delegation_state.arm(
        engine,
        session_id,
        "test-dispatcher",
        root=root,
        now=armed_at if armed_at is not None else time.time(),
    )


def _make_evidence(root: Path, bundle_root_rel: str, run_id: str, mtime: float) -> None:
    import os

    run_dir = root / bundle_root_rel / run_id
    run_dir.mkdir(parents=True, exist_ok=True)
    prompt = run_dir / "prompt.txt"
    prompt.write_text("do the thing")
    os.utime(prompt, (mtime, mtime))


class TestDelegationTripwireHookDoD:
    def test_zero_engine_call_write_blocks(
        self, hook: Any, tmp_path: Path, capsys: pytest.CaptureFixture
    ) -> None:
        _arm(tmp_path, "agy", "sess-1")
        payload = {
            "tool_name": "Write",
            "tool_input": {"file_path": "foo.py", "content": "x"},
            "session_id": "sess-1",
            "cwd": str(tmp_path),
        }
        code = _run_main(hook, payload)
        assert code == 2
        err = capsys.readouterr().err
        assert "agy" in err
        assert ".claude/agy/runs" in err
        assert "delegation_state.py" in err

    def test_genuine_agy_run_passes(
        self, hook: Any, tmp_path: Path, capsys: pytest.CaptureFixture
    ) -> None:
        armed_at = time.time()
        _arm(tmp_path, "agy", "sess-2", armed_at=armed_at)
        _make_evidence(tmp_path, ".claude/agy/runs", "run-1", armed_at + 5)
        payload = {
            "tool_name": "Write",
            "tool_input": {"file_path": "foo.py", "content": "x"},
            "session_id": "sess-2",
            "cwd": str(tmp_path),
        }
        code = _run_main(hook, payload)
        assert code == 0
        assert capsys.readouterr().err == ""


class TestDelegationTripwireHookEdgeMatrix:
    def test_unarmed_no_marker_exits_0(self, hook: Any, tmp_path: Path) -> None:
        payload = {
            "tool_name": "Write",
            "tool_input": {"file_path": "foo.py"},
            "session_id": "sess-unarmed",
            "cwd": str(tmp_path),
        }
        assert _run_main(hook, payload) == 0

    def test_stale_ttl_exits_0(self, hook: Any, tmp_path: Path) -> None:
        stale_armed_at = time.time() - _delegation_state.DEFAULT_TTL_SECONDS - 60
        _arm(tmp_path, "agy", "sess-stale", armed_at=stale_armed_at)
        payload = {
            "tool_name": "Write",
            "tool_input": {"file_path": "foo.py"},
            "session_id": "sess-stale",
            "cwd": str(tmp_path),
        }
        assert _run_main(hook, payload) == 0

    def test_evidence_older_than_armed_at_blocked(self, hook: Any, tmp_path: Path) -> None:
        armed_at = time.time()
        _arm(tmp_path, "agy", "sess-old-evidence", armed_at=armed_at)
        _make_evidence(tmp_path, ".claude/agy/runs", "run-old", armed_at - 100)
        payload = {
            "tool_name": "Write",
            "tool_input": {"file_path": "foo.py"},
            "session_id": "sess-old-evidence",
            "cwd": str(tmp_path),
        }
        assert _run_main(hook, payload) == 2

    @pytest.mark.parametrize("tool_name", ["Edit", "MultiEdit", "NotebookEdit"])
    def test_each_matcher_tool_blocked_when_armed_unproven(
        self, hook: Any, tmp_path: Path, tool_name: str
    ) -> None:
        _arm(tmp_path, "agy", f"sess-{tool_name}")
        payload = {
            "tool_name": tool_name,
            "tool_input": {},
            "session_id": f"sess-{tool_name}",
            "cwd": str(tmp_path),
        }
        assert _run_main(hook, payload) == 2

    def test_non_file_tool_exits_0(self, hook: Any, tmp_path: Path) -> None:
        _arm(tmp_path, "agy", "sess-bash")
        payload = {
            "tool_name": "Bash",
            "tool_input": {"command": "ls"},
            "session_id": "sess-bash",
            "cwd": str(tmp_path),
        }
        assert _run_main(hook, payload) == 0

    def test_malformed_stdin_exits_0(self, hook: Any, capsys: pytest.CaptureFixture) -> None:
        with patch.object(sys, "stdin") as mock_stdin:
            mock_stdin.read.return_value = "not json"
            with pytest.raises(SystemExit) as exc_info:
                hook.main()
        assert exc_info.value.code == 0
        assert capsys.readouterr().out == ""

    def test_unreadable_marker_exits_0(self, hook: Any, tmp_path: Path) -> None:
        marker_path = tmp_path / ".claude" / "delegation" / "active.json"
        marker_path.parent.mkdir(parents=True, exist_ok=True)
        marker_path.write_text("{not valid json")
        payload = {
            "tool_name": "Write",
            "tool_input": {"file_path": "foo.py"},
            "session_id": "sess-unreadable",
            "cwd": str(tmp_path),
        }
        assert _run_main(hook, payload) == 0

    def test_missing_bundle_root_still_blocks_when_armed_unproven(
        self, hook: Any, tmp_path: Path
    ) -> None:
        _arm(tmp_path, "agy", "sess-no-bundle")
        payload = {
            "tool_name": "Write",
            "tool_input": {"file_path": "foo.py"},
            "session_id": "sess-no-bundle",
            "cwd": str(tmp_path),
        }
        assert _run_main(hook, payload) == 2

    def test_missing_session_id_exits_0(self, hook: Any, tmp_path: Path) -> None:
        payload = {
            "tool_name": "Write",
            "tool_input": {"file_path": "foo.py"},
            "cwd": str(tmp_path),
        }
        assert _run_main(hook, payload) == 0


# ---------------------------------------------------------------------------
# U4 — Stop/SubagentStop audit (plugins/saga/hooks/delegation_stop_audit_hook.py)
# ---------------------------------------------------------------------------

STOP_HOOK_PATH = ROOT / "plugins" / "saga" / "hooks" / "delegation_stop_audit_hook.py"


@pytest.fixture
def stop_hook() -> Any:
    spec = importlib.util.spec_from_file_location("delegation_stop_audit_hook", STOP_HOOK_PATH)
    assert spec is not None and spec.loader is not None
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)  # type: ignore[union-attr]
    return mod


def _write_transcript(path: Path, events: list[dict]) -> None:
    path.write_text("\n".join(json.dumps(e) for e in events) + "\n", encoding="utf-8")


def _fallback_transcript(path: Path) -> None:
    _write_transcript(
        path,
        [
            {"type": "tool_use", "tool_name": "Edit", "input": {"file_path": "foo.py"}},
            {"type": "tool_use", "tool_name": "Bash", "arguments": {"command": "ls -la"}},
        ],
    )


def _real_agy_transcript(path: Path) -> None:
    _write_transcript(
        path,
        [
            {
                "type": "tool_use",
                "tool_name": "Bash",
                "arguments": {"command": "python3 plugins/agy/scripts/agy_delegate.py --task t1"},
            },
        ],
    )


def _agy_bundle(root: Path, run_id: str, *, launched: bool) -> None:
    run_dir = root / ".claude" / "agy" / "runs" / run_id
    run_dir.mkdir(parents=True, exist_ok=True)
    payload: dict[str, Any] = {"status": "ok", "agy_launched": launched}
    if launched:
        payload["receipt"] = {"schema": "agy.receipt.v1"}
    (run_dir / "result.json").write_text(json.dumps(payload), encoding="utf-8")


def _audit_records(root: Path) -> list[Path]:
    audits = root / ".claude" / "delegation" / "audits"
    return sorted(audits.glob("*.json")) if audits.is_dir() else []


class TestDelegationStopAuditHookDoD:
    def test_stop_hook_classifies_fallback_suspected(
        self, stop_hook: Any, tmp_path: Path, capsys: pytest.CaptureFixture
    ) -> None:
        """R3 DoD: armed turn, transcript shows Claude Edit + no engine command -> exit 2 HALT."""
        _arm(tmp_path, "agy", "sess-stop-fallback")
        transcript = tmp_path / "transcript.jsonl"
        _fallback_transcript(transcript)
        payload = {
            "session_id": "sess-stop-fallback",
            "cwd": str(tmp_path),
            "transcript_path": str(transcript),
            "stop_hook_active": False,
        }
        assert _run_main(stop_hook, payload) == 2
        err = capsys.readouterr().err
        assert "HALT" in err
        assert "fallback_suspected" in err
        assert "re-run the delegation" in err

    def test_stop_hook_passes_real_classification(
        self, stop_hook: Any, tmp_path: Path, capsys: pytest.CaptureFixture
    ) -> None:
        """R3 DoD: armed, genuine engine transcript + corroborating bundle -> exit 0, disarmed."""
        _arm(tmp_path, "agy", "sess-stop-real", armed_at=time.time() - 5)
        transcript = tmp_path / "transcript.jsonl"
        _real_agy_transcript(transcript)
        _agy_bundle(tmp_path, "run-real", launched=True)
        payload = {
            "session_id": "sess-stop-real",
            "cwd": str(tmp_path),
            "transcript_path": str(transcript),
            "stop_hook_active": False,
        }
        assert _run_main(stop_hook, payload) == 0
        assert capsys.readouterr().err == ""
        # Disarm-on-pass: the next turn starts unarmed.
        assert _delegation_state.active("sess-stop-real", root=tmp_path) is None


class TestDelegationStopAuditHookEdgeMatrix:
    def test_loop_guard_stop_hook_active_writes_audit_record_and_exits_0(
        self, stop_hook: Any, tmp_path: Path, capsys: pytest.CaptureFixture
    ) -> None:
        """KTD2 loop guard: stop_hook_active=true + still failing -> audit record + exit 0."""
        _arm(tmp_path, "agy", "sess-stop-loop")
        transcript = tmp_path / "transcript.jsonl"
        _fallback_transcript(transcript)
        payload = {
            "session_id": "sess-stop-loop",
            "cwd": str(tmp_path),
            "transcript_path": str(transcript),
            "stop_hook_active": True,
        }
        assert _run_main(stop_hook, payload) == 0
        err = capsys.readouterr().err
        assert "LOOP GUARD" in err
        records = _audit_records(tmp_path)
        assert records, "loop guard must write an audit record"
        record = json.loads(records[-1].read_text(encoding="utf-8"))
        assert record["loop_guard"] is True
        assert record["verdict"] == "fallback_suspected"
        assert record["session_id"] == "sess-stop-loop"

    def test_divergence_transcript_real_bundle_launch_false_names_delegation_integrity(
        self, stop_hook: Any, tmp_path: Path, capsys: pytest.CaptureFixture
    ) -> None:
        """R4: transcript real but bundle launch=false -> exit 2 naming DELEGATION_INTEGRITY."""
        _arm(tmp_path, "agy", "sess-stop-diverge", armed_at=time.time() - 5)
        transcript = tmp_path / "transcript.jsonl"
        _real_agy_transcript(transcript)
        _agy_bundle(tmp_path, "run-diverge", launched=False)
        payload = {
            "session_id": "sess-stop-diverge",
            "cwd": str(tmp_path),
            "transcript_path": str(transcript),
            "stop_hook_active": False,
        }
        assert _run_main(stop_hook, payload) == 2
        assert "DELEGATION_INTEGRITY" in capsys.readouterr().err

    def test_unarmed_turn_never_opens_transcript(
        self, stop_hook: Any, tmp_path: Path, capsys: pytest.CaptureFixture
    ) -> None:
        """Unarmed -> exit 0 without opening the transcript, proven via a nonexistent path.

        Were the transcript touched while armed, the missing-path branch prints a banner;
        an unarmed turn must produce NO output at all (marker stat first, KTD8).
        """
        payload = {
            "session_id": "sess-stop-unarmed",
            "cwd": str(tmp_path),
            "transcript_path": str(tmp_path / "does-not-exist" / "transcript.jsonl"),
            "stop_hook_active": False,
        }
        assert _run_main(stop_hook, payload) == 0
        captured = capsys.readouterr()
        assert captured.err == ""
        assert captured.out == ""

    def test_missing_transcript_while_armed_banners_and_exits_0(
        self, stop_hook: Any, tmp_path: Path, capsys: pytest.CaptureFixture
    ) -> None:
        """Fail-open: armed but transcript path missing -> banner, exit 0, never crash."""
        _arm(tmp_path, "agy", "sess-stop-no-transcript")
        payload = {
            "session_id": "sess-stop-no-transcript",
            "cwd": str(tmp_path),
            "transcript_path": str(tmp_path / "missing.jsonl"),
            "stop_hook_active": False,
        }
        assert _run_main(stop_hook, payload) == 0
        assert "audit skipped" in capsys.readouterr().err

    def test_malformed_stdin_exits_0(self, stop_hook: Any, capsys: pytest.CaptureFixture) -> None:
        with patch.object(sys, "stdin") as mock_stdin:
            mock_stdin.read.return_value = "not json"
            with pytest.raises(SystemExit) as exc_info:
                stop_hook.main()
        assert exc_info.value.code == 0
        assert capsys.readouterr().err == ""

    def test_pass_writes_audit_record(self, stop_hook: Any, tmp_path: Path) -> None:
        """An audit record is written either way — including the clean pass."""
        _arm(tmp_path, "agy", "sess-stop-record", armed_at=time.time() - 5)
        transcript = tmp_path / "transcript.jsonl"
        _real_agy_transcript(transcript)
        _agy_bundle(tmp_path, "run-record", launched=True)
        payload = {
            "session_id": "sess-stop-record",
            "cwd": str(tmp_path),
            "transcript_path": str(transcript),
            "stop_hook_active": False,
        }
        assert _run_main(stop_hook, payload) == 0
        records = _audit_records(tmp_path)
        assert records
        record = json.loads(records[-1].read_text(encoding="utf-8"))
        assert record["verdict"] == "real"


# ---------------------------------------------------------------------------
# U5 — dispatch-layer two-signal acceptance + DELEGATION_INTEGRITY
#      (plugins/saga/scripts/engine_dispatch.py, provenance_manifest.py)
# ---------------------------------------------------------------------------

SAGA_SCRIPTS = ROOT / "plugins" / "saga" / "scripts"
if str(SAGA_SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SAGA_SCRIPTS))

_R = _load_module(SAGA_SCRIPTS / "engine_resolver.py", "engine_resolver_u5")
_D = _load_module(SAGA_SCRIPTS / "engine_dispatch.py", "engine_dispatch_u5")
_PM = _D.pm
_MS = _D.manifest_store


def _resolution(engine_id: str = "agy", variant: str = "gemini-3.1-pro-high") -> Any:
    return _R.Resolution(
        engine_id=engine_id,
        variant=variant,
        effort="high",
        recipe="recipe",
        protocol=["Run."],
        payload="do the delegated thing",
        write_capable=False,
        fallback=None,
        halt=None,
    )


def _valid_agy_receipt() -> dict[str, Any]:
    return dict(
        _D._bridge_receipt.emit_receipt(
            engine_id="agy",
            variant="gemini-3.1-pro-high",
            transport="cli",
            wall_time_s=0.5,
            bytes_produced=17,
            runner={"pid": 4242, "argv": ["agy", "run"], "exit_code": 0},
        )
    )


def _write_bundle(
    root: Path,
    run_id: str,
    *,
    payload: dict[str, Any],
    future_mtime: bool = True,
) -> Path:
    """Write an agy result bundle; ``future_mtime`` lifts it past any armed_at filter."""
    import os

    run_dir = root / ".claude" / "agy" / "runs" / run_id
    run_dir.mkdir(parents=True, exist_ok=True)
    (run_dir / "result.json").write_text(json.dumps(payload), encoding="utf-8")
    if future_mtime:
        future = time.time() + 120
        os.utime(run_dir, (future, future))
    return run_dir


def _ok_runner_with_receipt(_invocation: dict[str, Any]) -> dict[str, Any]:
    return {"status": "ok", "output": "external finding", "receipt": _valid_agy_receipt()}


def _dispatch(tmp_path: Path, *, gated: bool, session_id: str = "", runner: Any = None) -> Any:
    return _D.dispatch(
        _resolution(),
        runner=runner or _ok_runner_with_receipt,
        model="opus",
        gated=gated,
        session_id=session_id,
        workspace_root=tmp_path,
    )


def _manifest_for(tmp_path: Path, evidence: Any, execution_id: str) -> Any:
    store = _MS.Store(root=tmp_path / "manifests" / execution_id).ensure()
    return _D.record_dispatch_manifest(
        store,
        evidence,
        execution_id=execution_id,
        saga_ref="saga-u5",
        created_at="2026-07-07T00:00:00Z",
    )


class TestTwoSignalAcceptanceDoD:
    def test_reconciliation_flags_divergence(self, tmp_path: Path) -> None:
        """R4 DoD: self-report ok + bundle launch flag false -> DELEGATION_INTEGRITY, not
        accepted."""
        _write_bundle(tmp_path, "run-div", payload={"status": "ok", "agy_launched": False})

        disposition = _dispatch(tmp_path, gated=True, session_id="sess-u5-div")

        assert isinstance(disposition, _D.RequeueDisposition)
        assert disposition.disposition == "requeue"
        assert "delegation-integrity" in disposition.reason

        manifest = _manifest_for(tmp_path, disposition.evidence, "exec-div")
        assert manifest.disposition is _PM.Disposition.DELEGATION_INTEGRITY
        assert "delegation-integrity" in manifest.disposition_note

        # Not accepted: divergent evidence can never satisfy a gate.
        with pytest.raises(_D.DispatchError):
            _D.satisfy_gate(disposition.evidence)

    def test_two_signal_disagreement_requeues(self, tmp_path: Path) -> None:
        """KTD7 DoD: first divergence -> requeue disposition; corroborating retry -> accepted;
        second consecutive divergence -> DispatchError HALT."""
        session = "sess-u5-requeue"
        bundle = _write_bundle(tmp_path, "run-rq", payload={"status": "ok", "agy_launched": False})

        first = _dispatch(tmp_path, gated=True, session_id=session)
        assert isinstance(first, _D.RequeueDisposition)
        assert first.attempt == 1

        # Corroborating retry: the bundle now proves the launch -> accepted, counter reset.
        _write_bundle(tmp_path, "run-rq", payload={"status": "ok", "agy_launched": True})
        retry = _dispatch(tmp_path, gated=True, session_id=session)
        assert isinstance(retry, _D.AdvisoryEvidence)
        assert retry.provenance.get("observer_corroborated") is True

        # Two NEW consecutive divergences: requeue once, then HALT.
        _write_bundle(tmp_path, "run-rq", payload={"status": "ok", "agy_launched": False})
        again = _dispatch(tmp_path, gated=True, session_id=session)
        assert isinstance(again, _D.RequeueDisposition)
        assert again.attempt == 1  # counter was reset by the corroborated acceptance
        with pytest.raises(_D.DispatchError, match="HALT"):
            _dispatch(tmp_path, gated=True, session_id=session)
        assert bundle.is_dir()


class TestTwoSignalAcceptanceMatrix:
    def test_both_signals_agree_ran_as_requested_and_gate_satisfiable(self, tmp_path: Path) -> None:
        _write_bundle(tmp_path, "run-ok", payload={"status": "ok", "agy_launched": True})

        evidence = _dispatch(tmp_path, gated=True, session_id="sess-u5-agree")
        assert isinstance(evidence, _D.AdvisoryEvidence)
        assert evidence.halt is None
        assert evidence.provenance["observer_corroborated"] is True

        manifest = _manifest_for(tmp_path, evidence, "exec-agree")
        assert manifest.disposition is _PM.Disposition.RAN_AS_REQUESTED

        verified = _D.AdvisoryEvidence(
            engine_id=evidence.engine_id,
            variant=evidence.variant,
            evidence=evidence.evidence,
            provenance=evidence.provenance,
            verified_by_claude=True,
            runner_receipt=evidence.runner_receipt,
        )
        assert _D.satisfy_gate(verified) is None

    def test_receipt_valid_but_launch_flag_missing_is_observer_no(self, tmp_path: Path) -> None:
        """Conservative observer: a result.json with NO launch flag at all is observer-no."""
        _write_bundle(tmp_path, "run-noflag", payload={"status": "ok"})

        disposition = _dispatch(tmp_path, gated=True, session_id="sess-u5-noflag")
        assert isinstance(disposition, _D.RequeueDisposition)
        assert "delegation-integrity" in disposition.reason

    def test_advisory_divergence_downgrades_without_requeue(self, tmp_path: Path) -> None:
        """Non-gated divergence keeps the downgrade_note mechanism with the integrity reason
        attached; repeated calls never requeue and never HALT."""
        _write_bundle(tmp_path, "run-adv", payload={"status": "ok", "agy_launched": False})

        for _ in range(3):  # no requeue loop, no HALT escalation
            evidence = _dispatch(tmp_path, gated=False, session_id="sess-u5-advisory")
            assert isinstance(evidence, _D.AdvisoryEvidence)
            assert evidence.halt is not None
            assert "Downgraded external engine agy" in evidence.halt
            assert "delegation-integrity" in evidence.halt

        manifest = _manifest_for(tmp_path, evidence, "exec-advisory")
        assert manifest.disposition is _PM.Disposition.DELEGATION_INTEGRITY

    def test_arming_failure_dispatch_still_runs_and_manifest_names_tripwire_unarmed(
        self, tmp_path: Path
    ) -> None:
        """Fail-open, named: arm() raising must not block dispatch; the manifest records
        tripwire_unarmed."""
        # Force arm() to fail: the marker's parent path exists as a FILE.
        claude_dir = tmp_path / ".claude"
        claude_dir.mkdir()
        (claude_dir / "delegation").write_text("not a directory", encoding="utf-8")
        _write_bundle(tmp_path, "run-unarmed", payload={"status": "ok", "agy_launched": True})

        evidence = _dispatch(tmp_path, gated=True, session_id="sess-u5-unarmed")
        assert isinstance(evidence, _D.AdvisoryEvidence)
        assert evidence.evidence == "external finding"
        assert str(evidence.provenance.get("tripwire", "")).startswith("tripwire_unarmed")

        manifest = _manifest_for(tmp_path, evidence, "exec-unarmed")
        assert manifest.disposition is _PM.Disposition.RAN_AS_REQUESTED
        assert "tripwire_unarmed" in manifest.disposition_note

    def test_dispatch_arms_during_run_and_disarms_in_finally(self, tmp_path: Path) -> None:
        """KTD4: the marker is live while the adapter runs and gone afterwards -- even when
        the runner raises."""
        session = "sess-u5-armed"
        _write_bundle(tmp_path, "run-armed", payload={"status": "ok", "agy_launched": True})

        seen: dict[str, Any] = {}

        def observing_runner(_invocation: dict[str, Any]) -> dict[str, Any]:
            seen["entry"] = _delegation_state.active(session, root=tmp_path)
            return _ok_runner_with_receipt(_invocation)

        _dispatch(tmp_path, gated=True, session_id=session, runner=observing_runner)
        assert seen["entry"] is not None
        assert seen["entry"].engine == "agy"
        assert _delegation_state.active(session, root=tmp_path) is None

        def raising_runner(_invocation: dict[str, Any]) -> dict[str, Any]:
            raise RuntimeError("adapter blew up")

        with pytest.raises(RuntimeError):
            _dispatch(tmp_path, gated=True, session_id=session, runner=raising_runner)
        assert _delegation_state.active(session, root=tmp_path) is None

    def test_single_signal_callers_are_unchanged(self, tmp_path: Path) -> None:
        """Omitting gated/session_id/workspace_root keeps today's advisory behavior
        byte-identical -- no observer mark, no integrity note, no requeue."""
        evidence = _D.dispatch(_resolution(), runner=_ok_runner_with_receipt, model="opus")
        assert isinstance(evidence, _D.AdvisoryEvidence)
        assert evidence.halt is None
        assert evidence.provenance == {
            "engine": "agy",
            "variant": "gemini-3.1-pro-high",
            "status": "ok",
        }

    def test_delegation_integrity_disposition_round_trips(self, tmp_path: Path) -> None:
        _write_bundle(tmp_path, "run-rt", payload={"status": "ok", "agy_launched": False})
        disposition = _dispatch(tmp_path, gated=True, session_id="sess-u5-rt")
        store = _MS.Store(root=tmp_path / "manifests" / "rt").ensure()
        _D.record_dispatch_manifest(
            store,
            disposition.evidence,
            execution_id="exec-rt",
            saga_ref="saga-u5",
            created_at="2026-07-07T00:00:00Z",
        )
        persisted = _MS.read_manifest(store, "exec-rt")
        assert persisted is not None
        assert persisted["disposition"] == "delegation-integrity"
        round_tripped = _PM.Manifest.from_dict(persisted)
        assert round_tripped.disposition is _PM.Disposition.DELEGATION_INTEGRITY


# ---------------------------------------------------------------------------
# U6 -- cross-mechanism integration scenarios (arm -> PreToolUse -> Stop) that
# no single unit's tests prove: the *same* armed session is walked through both
# hooks in sequence, in a scratch repo, exactly as a real turn would.
# ---------------------------------------------------------------------------


class TestChaperoneIntegrationArc:
    def test_full_genuine_arc_pretooluse_passes_then_stop_disarms(
        self, hook: Any, stop_hook: Any, tmp_path: Path, capsys: pytest.CaptureFixture
    ) -> None:
        """Full arc: arm -> fake genuine bundle (prompt.txt + result.json launch=true +
        receipt) -> PreToolUse hook passes (exit 0) -> Stop hook passes and disarms
        (exit 0). No single unit test drives both hooks off one armed session."""
        session_id = "sess-u6-genuine"
        armed_at = time.time() - 5
        _arm(tmp_path, "agy", session_id, armed_at=armed_at)

        # Genuine engine evidence: prompt.txt with mtime >= armed_at (R2), plus a
        # corroborating result.json bundle with the receipt the Stop-hook auditor
        # will reconcile against the transcript.
        run_dir = tmp_path / ".claude" / "agy" / "runs" / "run-u6-genuine"
        run_dir.mkdir(parents=True)
        prompt = run_dir / "prompt.txt"
        prompt.write_text("do delegated thing", encoding="utf-8")
        import os

        os.utime(prompt, (armed_at + 1, armed_at + 1))
        _agy_bundle(tmp_path, "run-u6-genuine", launched=True)

        # PreToolUse: Claude tries to Write mid-turn while armed -- must pass
        # because genuine engine evidence (prompt.txt newer than armed_at) exists.
        pretool_payload = {
            "tool_name": "Write",
            "tool_input": {"file_path": "foo.py", "content": "x"},
            "session_id": session_id,
            "cwd": str(tmp_path),
        }
        assert _run_main(hook, pretool_payload) == 0
        assert capsys.readouterr().err == ""

        # Stop: transcript shows the genuine engine invocation, bundle corroborates
        # launch=true -- verdict is "real", hook passes and disarms the session.
        transcript = tmp_path / "transcript.jsonl"
        _real_agy_transcript(transcript)
        stop_payload = {
            "session_id": session_id,
            "cwd": str(tmp_path),
            "transcript_path": str(transcript),
            "stop_hook_active": False,
        }
        assert _run_main(stop_hook, stop_payload) == 0
        assert capsys.readouterr().err == ""
        assert _delegation_state.active(session_id, root=tmp_path) is None

    def test_full_zero_engine_call_arc_pretooluse_blocks_then_stop_halts(
        self, hook: Any, stop_hook: Any, tmp_path: Path, capsys: pytest.CaptureFixture
    ) -> None:
        """Full arc: arm -> no bundle at all -> PreToolUse blocks (exit 2) ->
        Stop hook, invoked as if the block were bypassed (Claude wrote the file
        anyway, no engine ever ran), still hard-HALTs at turn end (exit 2). Proves
        the two enforcement points are independent, redundant defenses around the
        same armed-unproven state -- not just one hook covering for the other."""
        session_id = "sess-u6-zero-call"
        _arm(tmp_path, "agy", session_id)

        # No bundle evidence anywhere under the engine's bundle root.
        assert not (tmp_path / ".claude" / "agy" / "runs").exists()

        pretool_payload = {
            "tool_name": "Write",
            "tool_input": {"file_path": "foo.py", "content": "x"},
            "session_id": session_id,
            "cwd": str(tmp_path),
        }
        assert _run_main(hook, pretool_payload) == 2
        pretool_err = capsys.readouterr().err
        assert pretool_err != ""

        # Simulate the PreToolUse block being bypassed (e.g. an out-of-band write):
        # the turn still ends with Claude having done the file-tool work itself
        # and no engine command ever invoked -- Stop-hook classification must
        # still catch this independently and HALT.
        transcript = tmp_path / "transcript.jsonl"
        _fallback_transcript(transcript)
        stop_payload = {
            "session_id": session_id,
            "cwd": str(tmp_path),
            "transcript_path": str(transcript),
            "stop_hook_active": False,
        }
        assert _run_main(stop_hook, stop_payload) == 2
        stop_err = capsys.readouterr().err
        assert "HALT" in stop_err
        assert "fallback_suspected" in stop_err


class TestFleetCoreUnavailableFailOpen:
    """Drive the documented 'missing fleet-core shim/module -> fail open' branch directly."""

    @staticmethod
    def _broken_shim() -> ModuleType:
        stub = ModuleType("fleet_commons_shim")

        def _raise(_module: str) -> Any:
            raise RuntimeError("fleet-core unavailable (simulated)")

        stub.load = _raise  # type: ignore[attr-defined]
        return stub

    def test_tripwire_hook_fails_open_without_fleet_core(
        self, hook: Any, tmp_path: Path
    ) -> None:
        # Armed with no evidence: a working shim would block (exit 2); a broken
        # shim must fail open (exit 0) rather than crash or block.
        session_id = "sess-shim-broken"
        _arm(tmp_path, "agy", session_id)
        payload = {
            "tool_name": "Write",
            "session_id": session_id,
            "cwd": str(tmp_path),
        }
        with patch.dict(sys.modules, {"fleet_commons_shim": self._broken_shim()}):
            assert _run_main(hook, payload) == 0

    def test_stop_hook_fails_open_without_fleet_core(
        self, stop_hook: Any, tmp_path: Path
    ) -> None:
        session_id = "sess-shim-broken-stop"
        _arm(tmp_path, "agy", session_id)
        payload = {
            "session_id": session_id,
            "cwd": str(tmp_path),
            "transcript_path": str(tmp_path / "missing-transcript.jsonl"),
            "stop_hook_active": False,
        }
        with patch.dict(sys.modules, {"fleet_commons_shim": self._broken_shim()}):
            assert _run_main(stop_hook, payload) == 0
