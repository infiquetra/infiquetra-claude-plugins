"""Typed external-engine reconciliation and run-fact integration (#393 U1)."""

from __future__ import annotations

import hashlib
import importlib.util
import json
import sys
from pathlib import Path
from types import ModuleType
from typing import Any

import pytest

ROOT = Path(__file__).parent.parent
SCRIPTS = ROOT / "plugins" / "saga" / "scripts"


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


def _ledger(tmp_path: Path) -> Any:
    return RL.RunLedger(tmp_path / "run-facts.jsonl")


def _item(
    finding_id: str,
    status: Any = None,
    rationale: str = "Claude checked the source and accepted the finding.",
) -> Any:
    return RC.ReconciliationItem(
        source_finding_id=finding_id,
        status=status or RC.ReconciliationStatus.RECONCILED,
        adjudicator_id="claude/opus",
        rationale=rationale,
    )


def _result(*, source_ids: tuple[str, ...] = ("finding-1",), items: tuple[Any, ...] | None = None) -> Any:
    return RC.build_result(
        reconciliation_id="recon-exec-1",
        execution_id="exec-1",
        intent="offload",
        adjudicator_id="claude/opus",
        source_finding_ids=source_ids,
        items=items if items is not None else tuple(_item(value) for value in source_ids),
    )


def test_registry_exactly_matches_current_canonical_intents() -> None:
    RC.validate_registry()
    assert tuple(RC.RECIPE_REGISTRY) == tuple(RC._tier_palette.ENGINE_INTENTS)
    assert len({recipe.recipe_id for recipe in RC.RECIPE_REGISTRY.values()}) == len(
        RC.RECIPE_REGISTRY
    )
    with pytest.raises(RC.ReconciliationError, match="unknown reconciliation intent"):
        RC.recipe_for_intent("not-an-intent")


def test_all_findings_accounted_and_empty_findings_are_ready() -> None:
    result = _result(
        source_ids=("accepted", "omitted", "superseded"),
        items=(
            _item("accepted"),
            _item("omitted", RC.ReconciliationStatus.DROPPED, "Not supported by repository source."),
            _item(
                "superseded",
                RC.ReconciliationStatus.OVERRIDDEN,
                "Claude's direct test result supersedes the advisory claim.",
            ),
        ),
    )
    assert result.ready and result.unaccounted_finding_ids == ()
    assert _result(source_ids=(), items=()).ready


def test_missing_finding_is_not_ready_until_explicitly_dropped() -> None:
    incomplete = _result(source_ids=("accepted", "net-new"), items=(_item("accepted"),))
    assert incomplete.unaccounted_finding_ids == ("net-new",)
    with pytest.raises(RC.ReconciliationError, match="net-new"):
        incomplete.require_ready()

    complete = _result(
        source_ids=("accepted", "net-new"),
        items=(
            _item("accepted"),
            _item("net-new", RC.ReconciliationStatus.DROPPED, "Out of scope after Claude review."),
        ),
    )
    assert complete.ready


@pytest.mark.parametrize(
    ("source_ids", "items", "match"),
    [
        (("same", "same"), (), "duplicate source"),
        (("same",), (_item("same"), _item("same")), "duplicate reconciliation item"),
        (("known",), (_item("unknown"),), "unknown findings"),
    ],
)
def test_duplicate_and_unknown_finding_ids_reject(
    source_ids: tuple[str, ...], items: tuple[Any, ...], match: str
) -> None:
    with pytest.raises(RC.ReconciliationError, match=match):
        _result(source_ids=source_ids, items=items)


def test_missing_adjudicator_and_rationale_reject() -> None:
    with pytest.raises(RC.ReconciliationError, match="identify Claude"):
        RC.build_result(
            reconciliation_id="r",
            execution_id="e",
            intent="offload",
            adjudicator_id="engine",
            source_finding_ids=(),
            items=(),
        )
    with pytest.raises(RC.ReconciliationError, match="rationale"):
        _item("finding", rationale="  ")


def test_reconcile_and_apply_append_separate_valid_facts(tmp_path: Path) -> None:
    ledger = _ledger(tmp_path)
    result = _result()
    first = RC.append_reconciliation_fact(
        ledger,
        result,
        action=RC.ReconciliationAction.RECONCILE,
        subplot_id="leaf-1",
        at="2026-07-09T00:00:00Z",
    )
    second = RC.append_reconciliation_fact(
        ledger,
        result,
        action=RC.ReconciliationAction.APPLY,
        subplot_id="leaf-1",
        at="2026-07-09T00:01:00Z",
    )
    facts = RC.read_reconciliation_facts(ledger)
    assert [fact["action"] for fact in facts] == ["reconcile", "apply"]
    assert first["this_hash"] == second["prev_hash"]
    assert all(fact["schema"] == "run_fact.v1" for fact in facts)
    assert RL.verify_chain(ledger).ok


def test_incomplete_and_conflicting_identity_reject_before_append(tmp_path: Path) -> None:
    ledger = _ledger(tmp_path)
    with pytest.raises(RC.ReconciliationError, match="unaccounted"):
        RC.append_reconciliation_fact(
            ledger,
            _result(source_ids=("missing",), items=()),
            action="reconcile",
            subplot_id="leaf",
            at="t",
        )
    assert RL.read_facts(ledger) == []

    original = _result()
    RC.append_reconciliation_fact(ledger, original, action="reconcile", subplot_id="leaf", at="t")
    conflicting = RC.build_result(
        reconciliation_id=original.reconciliation_id,
        execution_id="different-execution",
        intent="offload",
        adjudicator_id="claude/opus",
        source_finding_ids=(),
        items=(),
    )
    with pytest.raises(RC.ReconciliationError, match="already names another result"):
        RC.append_reconciliation_fact(
            ledger, conflicting, action="apply", subplot_id="leaf", at="t2"
        )


def test_reader_rejects_malformed_action_status_recipe_and_hash(tmp_path: Path) -> None:
    result = _result()
    base = {
        "reconciliation_id": result.reconciliation_id,
        "execution_id": result.execution_id,
        "intent": result.intent,
        "recipe_id": result.recipe_id,
        "adjudicator_id": result.adjudicator_id,
        "action": "reconcile",
        "result_hash": RC.canonical_result_hash(result),
        "result": result.to_dict(),
    }
    mutations = (
        {"action": "publish"},
        {"result_hash": "not-a-hash"},
        {"result": {**result.to_dict(), "recipe_id": "wrong-recipe"}},
        {
            "result": {
                **result.to_dict(),
                "items": [{**result.to_dict()["items"][0], "status": "ignored"}],
            }
        },
    )
    for index, mutation in enumerate(mutations):
        ledger = RL.RunLedger(tmp_path / f"bad-{index}.jsonl")
        fields = {**base, **mutation}
        # Preserve a valid outer hash chain so the kind-specific reader reaches schema validation.
        if "result" in mutation and "result_hash" not in mutation:
            fields["result_hash"] = hashlib.sha256(
                json.dumps(fields["result"], sort_keys=True, separators=(",", ":")).encode()
            ).hexdigest()
        RL.append_fact(
            ledger,
            RL.build_fact("reconciliation", subplot_id="leaf", at="t", **fields),
        )
        with pytest.raises(RC.ReconciliationError):
            RC.read_reconciliation_facts(ledger)


def test_reader_refuses_corrupt_chain(tmp_path: Path) -> None:
    ledger = _ledger(tmp_path)
    RC.append_reconciliation_fact(ledger, _result(), action="reconcile", subplot_id="leaf", at="t")
    record = json.loads(ledger.path.read_text())
    record["execution_id"] = "tampered"
    ledger.path.write_text(json.dumps(record) + "\n")
    with pytest.raises(RC.ReconciliationError, match="chain verification failed"):
        RC.read_reconciliation_facts(ledger)
