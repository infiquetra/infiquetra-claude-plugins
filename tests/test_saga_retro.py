"""Read-only /retro recipe proposal coverage (#393 U5)."""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path
from types import ModuleType
from typing import Any

ROOT = Path(__file__).parent.parent
SCRIPTS = ROOT / "plugins" / "saga" / "scripts"
RETRO_SKILL = ROOT / "plugins" / "saga" / "skills" / "retro" / "SKILL.md"


def _load(name: str) -> ModuleType:
    if str(SCRIPTS) not in sys.path:
        sys.path.insert(0, str(SCRIPTS))
    spec = importlib.util.spec_from_file_location(name, SCRIPTS / f"{name}.py")
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


RC = _load("reconcile")
RL = RC.run_ledger


def _result(
    reconciliation_id: str,
    execution_id: str,
    *statuses: Any,
) -> Any:
    source_ids = tuple(f"finding-{index}" for index in range(len(statuses)))
    return RC.build_result(
        reconciliation_id=reconciliation_id,
        execution_id=execution_id,
        intent="offload",
        adjudicator_id="claude/opus",
        source_finding_ids=source_ids,
        items=tuple(
            RC.ReconciliationItem(
                source_finding_id=finding_id,
                status=status,
                adjudicator_id="claude/opus",
                rationale=f"Claude adjudicated {finding_id} as {status.value}.",
            )
            for finding_id, status in zip(source_ids, statuses, strict=True)
        ),
    )


def _append(ledger: Any, result: Any, action: str, at: str) -> None:
    RC.append_reconciliation_fact(
        ledger,
        result,
        action=action,
        subplot_id="issue-393",
        at=at,
    )


def test_populated_proposal_deduplicates_identity_and_references_evidence(tmp_path: Path) -> None:
    ledger = RL.RunLedger(tmp_path / "run-facts.jsonl")
    first = _result(
        "recon-1",
        "exec-1",
        RC.ReconciliationStatus.RECONCILED,
        RC.ReconciliationStatus.DROPPED,
    )
    second = _result("recon-2", "exec-2", RC.ReconciliationStatus.OVERRIDDEN)
    _append(ledger, first, "reconcile", "2026-07-09T01:00:00Z")
    _append(ledger, first, "apply", "2026-07-09T01:01:00Z")
    _append(ledger, second, "reconcile", "2026-07-09T01:02:00Z")

    proposal = RC.derive_recipe_update_proposal(ledger)

    assert proposal["status"] == "proposal"
    assert proposal["approval_required"] is True
    assert len(proposal["evidence"]) == 2
    assert proposal["evidence"][0]["actions"] == ["reconcile", "apply"]
    assert len(proposal["evidence"][0]["ledger_fact_hashes"]) == 2
    update = proposal["proposed_updates"][0]
    assert update["recommended_action"] == "review-intent-recipe"
    assert update["reconciliation_count"] == 2
    assert update["evidence_reconciliation_ids"] == ["recon-1", "recon-2"]
    assert update["finding_status_counts"] == {
        "reconciled": 1,
        "dropped": 1,
        "overridden": 1,
    }


def test_empty_ledger_returns_explicit_no_proposal(tmp_path: Path) -> None:
    proposal = RC.derive_recipe_update_proposal(RL.RunLedger(tmp_path / "missing.jsonl"))

    assert proposal == {
        "schema": "recipe_update_proposal.v1",
        "status": "no-proposal",
        "approval_required": False,
        "reason": "no reconciliation facts",
        "proposed_updates": [],
        "evidence": [],
    }


def test_absent_ledger_proposal_creates_no_ledger_or_lock(tmp_path: Path) -> None:
    ledger = RL.RunLedger(tmp_path / "missing" / "run-facts.jsonl")

    assert RC.derive_recipe_update_proposal(ledger)["status"] == "no-proposal"
    assert not ledger.path.parent.exists()
    assert not ledger.path.exists()
    assert not RL._lock_path(ledger).exists()


def test_proposal_read_does_not_mutate_ledger_or_recipe_registry(tmp_path: Path) -> None:
    ledger = RL.RunLedger(tmp_path / "run-facts.jsonl")
    result = _result("recon-1", "exec-1", RC.ReconciliationStatus.DROPPED)
    _append(ledger, result, "reconcile", "2026-07-09T01:00:00Z")
    ledger_before = ledger.path.read_bytes()
    registry_before = tuple(RC.RECIPE_REGISTRY.items())

    RC.derive_recipe_update_proposal(ledger)

    assert ledger.path.read_bytes() == ledger_before
    assert tuple(RC.RECIPE_REGISTRY.items()) == registry_before


def test_retro_documents_approval_gate_and_terminal_read_only_boundary() -> None:
    text = RETRO_SKILL.read_text(encoding="utf-8")

    assert "reconcile.derive_recipe_update_proposal(ledger)" in text
    assert "approval_required" in text
    assert "PROPOSE-DIFF-AND-WAIT" in text
    assert "writes no saga tick" in text
