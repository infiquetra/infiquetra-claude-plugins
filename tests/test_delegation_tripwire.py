"""DoD-named delegation-tripwire tests (#384).

This file is born in U1 with the codex-parity DoD test and is extended by U3-U6 as those
units land (PreToolUse block, Stop-hook audit, dispatch-layer reconciliation, integration
scenarios). Only U1's slice lives here for now.
"""

from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path
from types import ModuleType

import pytest

ROOT = Path(__file__).parent.parent
MODULE_PATH = ROOT / "plugins" / "fleet-core" / "scripts" / "fleet_commons" / "delegation_audit.py"


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
