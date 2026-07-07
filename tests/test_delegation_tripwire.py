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


def test_codex_bridge_untested_run_classified_false(delegation_audit: ModuleType, tmp_path: Path) -> None:
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
        json.dumps({"schema": "codex.result.v1", "status": "codex_unavailable", "codex_launched": False}),
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
