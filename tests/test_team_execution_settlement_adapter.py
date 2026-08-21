"""Isolated behavior tests for the independently packaged team settlement adapter."""

from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path
from types import ModuleType
from typing import Any

import pytest

ROOT = Path(__file__).parent.parent
SCRIPT = (
    ROOT
    / "plugins"
    / "team-execution"
    / "skills"
    / "team-execution"
    / "scripts"
    / "dispatch_settlement_adapter.py"
)


def _load() -> ModuleType:
    spec = importlib.util.spec_from_file_location("team_execution_settlement_adapter", SCRIPT)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    try:
        spec.loader.exec_module(module)
    finally:
        sys.modules.pop(spec.name, None)
    return module


ADAPTER = _load()


def _saga_root(root: Path) -> Path:
    saga = root / "plugins" / "saga"
    (saga / "scripts").mkdir(parents=True)
    (saga / "scripts" / "dispatch_settlement.py").write_text("# fixture\n", encoding="utf-8")
    return saga


def test_resolve_saga_plugin_uses_source_checkout_before_registry(tmp_path: Path) -> None:
    checkout = tmp_path / "checkout"
    (checkout / ".claude-plugin").mkdir(parents=True)
    (checkout / ".claude-plugin" / "marketplace.json").write_text("{}", encoding="utf-8")
    saga = _saga_root(checkout)
    script_path = checkout / "plugins" / "team-execution" / "skills" / "scripts" / "adapter.py"

    resolution = ADAPTER.resolve_saga_plugin(
        environ={}, registry_path=tmp_path / "missing.json", script_path=script_path
    )

    assert resolution.root == saga
    assert resolution.rung == 2


def test_resolve_saga_plugin_honors_explicit_override(tmp_path: Path) -> None:
    saga = _saga_root(tmp_path / "override")

    resolution = ADAPTER.resolve_saga_plugin(
        environ={"SAGA_PLUGIN_ROOT": str(saga)},
        registry_path=tmp_path / "missing.json",
        script_path=tmp_path / "no-source" / "adapter.py",
    )

    assert resolution.root == saga
    assert resolution.rung == 1


def test_invalid_explicit_saga_override_fails_without_fallback(tmp_path: Path) -> None:
    with pytest.raises(ADAPTER.SettlementAdapterError, match="SAGA_PLUGIN_ROOT"):
        ADAPTER.resolve_saga_plugin(
            environ={"SAGA_PLUGIN_ROOT": str(tmp_path / "not-saga")},
            registry_path=tmp_path / "missing.json",
            script_path=tmp_path / "no-source" / "adapter.py",
        )


def test_resolve_saga_plugin_reads_installed_registry(tmp_path: Path) -> None:
    saga = _saga_root(tmp_path / "installed")
    registry = tmp_path / "installed_plugins.json"
    registry.write_text(
        json.dumps({"version": 2, "plugins": {"saga@infiquetra": [{"installPath": str(saga)}]}}),
        encoding="utf-8",
    )

    resolution = ADAPTER.resolve_saga_plugin(
        environ={}, registry_path=registry, script_path=tmp_path / "no-source" / "adapter.py"
    )

    assert resolution.root == saga
    assert resolution.rung == 3


def test_resolve_saga_plugin_scans_cache_sibling(tmp_path: Path) -> None:
    plugin_root = tmp_path / "cache" / "marketplace" / "team-execution" / "2.18.0"
    plugin_root.mkdir(parents=True)
    saga = plugin_root.parent.parent / "saga" / "0.99.0"
    (saga / "scripts").mkdir(parents=True)
    (saga / "scripts" / "dispatch_settlement.py").write_text("# fixture\n", encoding="utf-8")

    resolution = ADAPTER.resolve_saga_plugin(
        environ={"CLAUDE_PLUGIN_ROOT": str(plugin_root)},
        registry_path=tmp_path / "missing.json",
        script_path=tmp_path / "no-source" / "adapter.py",
    )

    assert resolution.root == saga
    assert resolution.rung == 4


def test_resolve_saga_plugin_missing_prerequisite_is_actionable(tmp_path: Path) -> None:
    with pytest.raises(
        ADAPTER.SettlementAdapterError, match="before any reviewer or validator Agent call"
    ):
        ADAPTER.resolve_saga_plugin(
            environ={},
            registry_path=tmp_path / "missing.json",
            script_path=tmp_path / "none" / "a.py",
        )


def test_reviewer_artifact_is_materialized_from_complete_structured_result(tmp_path: Path) -> None:
    source = tmp_path / "reviewer.json"
    source.write_text(
        json.dumps(
            {
                "reviewer": "security-reviewer",
                "score": 9.5,
                "dimension_scores": {"auth": 9.5},
                "findings": [],
            }
        ),
        encoding="utf-8",
    )
    receipt = tmp_path / "receipts" / "security-reviewer.json"

    ADAPTER.materialize_artifact(
        kind="reviewer",
        unit_id="security-reviewer",
        source_path=source,
        receipt_path=receipt,
        repo_root=tmp_path,
    )

    assert json.loads(receipt.read_text(encoding="utf-8")) == {
        "schema": "dispatch.artifact.v1",
        "kind": "reviewer-result",
        "unit_id": "security-reviewer",
        "payload": json.loads(source.read_text(encoding="utf-8")),
    }


@pytest.mark.parametrize(
    "payload",
    [
        {"prose": "Everything passed."},
        {"artifact_pointer": "git:deadbeef"},
        {"reviewer": "security-reviewer", "score": 9, "dimension_scores": {}, "findings": []},
    ],
)
def test_reviewer_success_prose_or_artifact_pointer_cannot_materialize_delivery(
    tmp_path: Path, payload: dict[str, Any]
) -> None:
    source = tmp_path / "reviewer.json"
    source.write_text(json.dumps(payload), encoding="utf-8")

    with pytest.raises(ADAPTER.SettlementAdapterError):
        ADAPTER.materialize_artifact(
            kind="reviewer",
            unit_id="security-reviewer",
            source_path=source,
            receipt_path=tmp_path / "receipt.json",
            repo_root=tmp_path,
        )


def test_reviewer_success_prose_settles_as_silent_no_op(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    saga = _saga_root(tmp_path / "saga")
    capture = tmp_path / "settlement-args.json"
    saga_script = saga / "scripts" / "dispatch_settlement.py"
    saga_script.write_text(
        """import json
import os
import sys
from pathlib import Path

Path(os.environ["SETTLEMENT_CAPTURE"]).write_text(
    json.dumps(sys.argv[1:]), encoding="utf-8"
)
""",
        encoding="utf-8",
    )
    monkeypatch.setenv("SAGA_PLUGIN_ROOT", str(saga))
    monkeypatch.setenv("SETTLEMENT_CAPTURE", str(capture))

    repo = tmp_path / "repo"
    repo.mkdir()
    source = repo / "reviewer.json"
    source.write_text(json.dumps({"prose": "Everything passed."}), encoding="utf-8")

    result = ADAPTER.main(
        [
            "settle",
            "--kind",
            "reviewer",
            "--repo-root",
            str(repo),
            "--subplot-id",
            "team-run",
            "--dispatch-id",
            "review-dispatch",
            "--unit-id",
            "security",
            "--attempt",
            "1",
            "--at",
            "2026-08-20T00:00:00Z",
            "--source-json",
            "reviewer.json",
            "--receipt-path",
            "receipt.json",
        ]
    )

    forwarded = json.loads(capture.read_text(encoding="utf-8"))
    evidence_index = forwarded.index("--evidence-json")
    assert result == 0
    assert forwarded[evidence_index + 1] == "null"
    assert not (repo / "receipt.json").exists()


def test_reviewer_result_with_empty_dimensions_is_still_rejected(tmp_path: Path) -> None:
    source = tmp_path / "reviewer.json"
    source.write_text(
        json.dumps(
            {
                "reviewer": "security",
                "score": 9,
                "dimension_scores": {},
                "findings": [],
            }
        ),
        encoding="utf-8",
    )

    with pytest.raises(
        ADAPTER.IncompleteEvidenceError, match="requires non-empty dimension_scores"
    ):
        ADAPTER.materialize_artifact(
            kind="reviewer",
            unit_id="security",
            source_path=source,
            receipt_path=tmp_path / "receipt.json",
            repo_root=tmp_path,
        )


def test_corrupt_or_contradictory_team_evidence_halts_instead_of_settling_missing(
    tmp_path: Path,
) -> None:
    corrupt = tmp_path / "corrupt.json"
    corrupt.write_text("{not-json", encoding="utf-8")
    with pytest.raises(ADAPTER.SettlementAdapterError) as corrupt_error:
        ADAPTER.materialize_artifact(
            kind="reviewer",
            unit_id="security-reviewer",
            source_path=corrupt,
            receipt_path=tmp_path / "receipt.json",
            repo_root=tmp_path,
        )
    assert not isinstance(corrupt_error.value, ADAPTER.IncompleteEvidenceError)

    contradictory = tmp_path / "contradictory.json"
    contradictory.write_text(
        json.dumps(
            {
                "reviewer": "architecture-reviewer",
                "score": 9.5,
                "dimension_scores": {"design": 9.5},
                "findings": [],
            }
        ),
        encoding="utf-8",
    )
    with pytest.raises(ADAPTER.SettlementAdapterError) as contradictory_error:
        ADAPTER.materialize_artifact(
            kind="reviewer",
            unit_id="security-reviewer",
            source_path=contradictory,
            receipt_path=tmp_path / "receipt.json",
            repo_root=tmp_path,
        )
    assert not isinstance(contradictory_error.value, ADAPTER.IncompleteEvidenceError)


def test_duplicate_team_evidence_keys_are_rejected_as_corrupt(tmp_path: Path) -> None:
    source = tmp_path / "duplicate.json"
    source.write_text(
        '{"reviewer":"security-reviewer","reviewer":"architecture-reviewer"}',
        encoding="utf-8",
    )

    with pytest.raises(ADAPTER.SettlementAdapterError, match="duplicate JSON key") as error:
        ADAPTER.materialize_artifact(
            kind="reviewer",
            unit_id="security-reviewer",
            source_path=source,
            receipt_path=tmp_path / "receipt.json",
            repo_root=tmp_path,
        )

    assert not isinstance(error.value, ADAPTER.IncompleteEvidenceError)


def test_validator_requires_existing_nonempty_evidence_before_materialization(
    tmp_path: Path,
) -> None:
    source = tmp_path / "validator.json"
    source.write_text(
        json.dumps(
            {
                "validator": "security-scanner",
                "required": True,
                "status": "pass",
                "evidence": ["logs/security.txt"],
            }
        ),
        encoding="utf-8",
    )

    with pytest.raises(ADAPTER.SettlementAdapterError, match="does not exist"):
        ADAPTER.materialize_artifact(
            kind="validator",
            unit_id="security-scanner",
            source_path=source,
            receipt_path=tmp_path / "receipt.json",
            repo_root=tmp_path,
        )

    log = tmp_path / "logs" / "security.txt"
    log.parent.mkdir()
    log.write_text("bandit exit=0\n", encoding="utf-8")
    receipt = tmp_path / "receipt.json"
    ADAPTER.materialize_artifact(
        kind="validator",
        unit_id="security-scanner",
        source_path=source,
        receipt_path=receipt,
        repo_root=tmp_path,
    )
    assert json.loads(receipt.read_text(encoding="utf-8"))["kind"] == "validator-state"


def test_manifest_units_preserves_the_complete_configured_roster() -> None:
    units = ADAPTER.manifest_units(
        "reviewer", ["devils-advocate-reviewer", "security-reviewer", "architecture-reviewer"]
    )

    assert [unit["unit_id"] for unit in units] == [
        "devils-advocate-reviewer",
        "security-reviewer",
        "architecture-reviewer",
    ]
    assert all(unit["deliverables"] == ["scored-review"] for unit in units)
    with pytest.raises(ADAPTER.SettlementAdapterError, match="unique"):
        ADAPTER.manifest_units("reviewer", ["security-reviewer", "security-reviewer"])


def test_invoke_saga_uses_only_the_resolved_canonical_cli(tmp_path: Path) -> None:
    saga = _saga_root(tmp_path)
    calls: list[list[str]] = []

    class Completed:
        returncode = 0

    def runner(args: list[str], *, check: bool) -> Completed:
        assert check is False
        calls.append(args)
        return Completed()

    assert ADAPTER.invoke_saga(ADAPTER.SagaResolution(saga, 1), ["report"], runner=runner) == 0
    assert calls == [
        [ADAPTER.sys.executable, str(saga / "scripts" / "dispatch_settlement.py"), "report"]
    ]


def test_settle_arguments_bind_evidence_loading_to_repo_root(tmp_path: Path) -> None:
    args = type(
        "Args",
        (),
        {
            "repo_root": str(tmp_path),
            "subplot_id": "team-run",
            "dispatch_id": "team-dispatch",
            "unit_id": "security-reviewer",
            "attempt": 1,
            "at": "2026-07-16T00:00:00Z",
        },
    )()

    command = ADAPTER._settle_args(args, tmp_path / "receipt.json")

    assert command[:6] == [
        "--repo-root",
        str(tmp_path),
        "--subplot-id",
        "team-run",
        "--evidence-root",
        str(tmp_path),
    ]
    descriptor = json.loads(command[-1])
    assert descriptor == {
        "receipt_type": "artifact",
        "unit_id": "security-reviewer",
        "evidence_path": str(tmp_path / "receipt.json"),
    }


def test_settle_arguments_support_explicit_state_root_outside_repo(tmp_path: Path) -> None:
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    evidence_root = tmp_path / "home-state"
    evidence_root.mkdir()
    args = type(
        "Args",
        (),
        {
            "repo_root": str(repo_root),
            "evidence_root": str(evidence_root),
            "subplot_id": "team-run",
            "dispatch_id": "team-dispatch",
            "unit_id": "security-reviewer",
            "attempt": 1,
            "at": "2026-07-16T00:00:00Z",
        },
    )()

    receipt = evidence_root / "settlement" / "security-reviewer.json"
    command = ADAPTER._settle_args(args, receipt)

    assert command[5] == str(evidence_root)
    assert json.loads(command[-1])["evidence_path"] == str(receipt)
    assert (
        ADAPTER._repo_path(evidence_root, "settlement/security-reviewer.json", label="receipt path")
        == receipt
    )
    with pytest.raises(ADAPTER.SettlementAdapterError, match="inside repo_root"):
        ADAPTER._repo_path(evidence_root, "../escape.json", label="receipt path")
