"""Typed external-engine reconciliation and run-fact integration (#393 U1)."""

from __future__ import annotations

import hashlib
import importlib.util
import json
import os
import stat
import sys
from concurrent.futures import ThreadPoolExecutor
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


def _result(
    *, source_ids: tuple[str, ...] = ("finding-1",), items: tuple[Any, ...] | None = None
) -> Any:
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


def test_registry_builder_rejects_missing_duplicate_and_surplus_definitions() -> None:
    recipe = RC.ReconciliationRecipe("offload", "only", "instruction")
    with pytest.raises(RC.ReconciliationError, match="no reconciliation recipe"):
        RC._build_registry(("offload", "second-opinion"), (recipe,))
    with pytest.raises(RC.ReconciliationError, match="duplicate reconciliation recipe"):
        RC._build_registry(("offload",), (recipe, recipe))
    extra = RC.ReconciliationRecipe("future", "future", "instruction")
    with pytest.raises(RC.ReconciliationError, match="not canonical intents"):
        RC._build_registry(("offload",), (recipe, extra))
    with pytest.raises(RC.ReconciliationError, match="canonical ENGINE_INTENTS contains duplicates"):
        RC._build_registry(("offload", "offload"), (recipe,))


def test_validate_registry_detects_every_public_drift(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(RC, "RECIPE_REGISTRY", {})
    with pytest.raises(RC.ReconciliationError, match="exactly match"):
        RC.validate_registry()
    monkeypatch.setattr(
        RC,
        "RECIPE_REGISTRY",
        {"offload": RC.ReconciliationRecipe("second-opinion", "id", "instruction")},
    )
    with pytest.raises(RC.ReconciliationError, match="keys disagree"):
        RC.validate_registry(("offload",))
    monkeypatch.setattr(
        RC,
        "RECIPE_REGISTRY",
        {
            "offload": RC.ReconciliationRecipe("offload", "same", "one"),
            "second-opinion": RC.ReconciliationRecipe("second-opinion", "same", "two"),
        },
    )
    with pytest.raises(RC.ReconciliationError, match="IDs must be unique"):
        RC.validate_registry(("offload", "second-opinion"))


def test_all_findings_accounted_and_empty_findings_are_ready() -> None:
    result = _result(
        source_ids=("accepted", "omitted", "superseded"),
        items=(
            _item("accepted"),
            _item(
                "omitted", RC.ReconciliationStatus.DROPPED, "Not supported by repository source."
            ),
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


@pytest.mark.parametrize(
    ("factory", "match"),
    [
        (lambda: _item("x" * (RC.MAX_ID_BYTES + 1)), "exceeds"),
        (lambda: _item("finding", rationale="x" * (RC.MAX_RATIONALE_BYTES + 1)), "exceeds"),
        (lambda: _item("finding", rationale="line\nbreak"), "control"),
        (lambda: _item("bad\x00id"), "control"),
    ],
)
def test_item_id_and_rationale_bounds(factory: Any, match: str) -> None:
    with pytest.raises(RC.ReconciliationError, match=match):
        factory()


def test_typed_item_and_result_deserialization_fail_loudly() -> None:
    with pytest.raises(RC.ReconciliationError, match="item fields"):
        RC.ReconciliationItem.from_dict({"status": "reconciled"})
    with pytest.raises(RC.ReconciliationError, match="invalid reconciliation status"):
        RC.ReconciliationItem.from_dict(
            {
                "source_finding_id": "f",
                "status": "accepted",
                "adjudicator_id": "claude",
                "rationale": "reason",
            }
        )
    result = _result()
    with pytest.raises(RC.ReconciliationError, match="result fields"):
        RC.ReconciliationResult.from_dict({})
    payload = result.to_dict()
    with pytest.raises(RC.ReconciliationError, match="must be arrays"):
        RC.ReconciliationResult.from_dict({**payload, "items": "bad"})
    with pytest.raises(RC.ReconciliationError, match="must be an object"):
        RC.ReconciliationResult.from_dict({**payload, "items": ["bad"]})


def test_source_finding_ids_are_content_derived_and_ordered() -> None:
    findings = RC.parse_source_findings([{"content": "same"}, {"content": "same"}])
    assert findings[0].digest == findings[1].digest
    assert findings[0].source_finding_id != findings[1].source_finding_id
    assert findings[0].source_finding_id.startswith("external-finding:0:")
    assert findings[1].source_finding_id.startswith("external-finding:1:")
    with pytest.raises(RC.ReconciliationError, match="encode its kind"):
        RC.SourceFinding("forged", RC.evidence_digest("content"), "content")


def test_result_type_recipe_and_adjudicator_invariants() -> None:
    result = _result()
    with pytest.raises(RC.ReconciliationError, match="does not match intent"):
        RC.ReconciliationResult(
            **{**result.__dict__, "recipe_id": "wrong"}
        )
    with pytest.raises(RC.ReconciliationError, match="immutable tuples"):
        RC.ReconciliationResult(**{**result.__dict__, "source_finding_ids": ["finding-1"]})
    with pytest.raises(RC.ReconciliationError, match="only ReconciliationItem"):
        RC.ReconciliationResult(**{**result.__dict__, "items": ("bad",)})
    with pytest.raises(RC.ReconciliationError, match="must match"):
        RC.ReconciliationResult(
            **{
                **result.__dict__,
                "items": (
                    RC.ReconciliationItem(
                        "finding-1",
                        RC.ReconciliationStatus.RECONCILED,
                        "claude/other",
                        "reason",
                    ),
                ),
            }
        )
    with pytest.raises(RC.ReconciliationError, match="lowercase SHA-256"):
        RC.ReconciliationResult(**{**result.__dict__, "evidence_digest": "bad"})
    with pytest.raises(RC.ReconciliationError, match="status must"):
        RC.ReconciliationItem("finding", "reconciled", "claude", "reason")
    with pytest.raises(RC.ReconciliationError, match="external evidence must"):
        RC.evidence_digest(123)


def test_item_count_and_result_byte_bounds() -> None:
    ids = tuple(f"f-{index}" for index in range(RC.MAX_ITEMS + 1))
    with pytest.raises(RC.ReconciliationError, match="findings"):
        _result(source_ids=ids, items=tuple(_item(value) for value in ids))

    large_ids = tuple(f"large-{index}" for index in range(20))
    with pytest.raises(RC.ReconciliationError, match="result exceeds"):
        _result(
            source_ids=large_ids,
            items=tuple(_item(value, rationale="r" * RC.MAX_RATIONALE_BYTES) for value in large_ids),
        )


def test_rejected_offload_signal_is_typed_visible_and_advisory() -> None:
    result = RC.build_rejected_offload_signal(
        reconciliation_id="recon-rejected-1",
        execution_id="exec-rejected-1",
        intent="offload",
        adjudicator_id="claude/opus",
        rejection_note="  Patch contradicted   repository source.\n",
    )

    assert result.ready
    assert result.intent == "offload"
    assert result.items[0].status is RC.ReconciliationStatus.DROPPED
    assert result.items[0].rationale == "Patch contradicted repository source."

    evidence = RC.reviewer_validator_evidence(result)
    assert evidence["advisory"] is True
    assert evidence["audiences"] == ["reviewer", "validator"]
    assert evidence["result"]["items"][0]["rationale"] == result.items[0].rationale


@pytest.mark.parametrize("intent", ["offload", "second-opinion", "divergence"])
def test_rejected_offload_signal_preserves_canonical_intent(intent: str) -> None:
    result = RC.build_rejected_offload_signal(
        reconciliation_id=f"rejected-{intent}",
        execution_id=f"exec-{intent}",
        intent=intent,
        adjudicator_id="claude",
        rejection_note="Claude rejected the advisory output.",
    )
    assert result.intent == intent
    assert result.recipe_id == RC.recipe_for_intent(intent).recipe_id


@pytest.mark.parametrize("note", ["", "  ", "\n\t", "bad\x00note"])
def test_rejected_offload_signal_requires_note(note: str) -> None:
    with pytest.raises(RC.ReconciliationError, match="rejection note"):
        RC.build_rejected_offload_signal(
            reconciliation_id="recon-rejected-1",
            execution_id="exec-rejected-1",
            intent="offload",
            adjudicator_id="claude",
            rejection_note=note,
        )


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
    assert stat.S_IMODE(os.stat(ledger.path).st_mode) == 0o600


def test_ledger_projection_never_persists_rationale_or_secret_marker(tmp_path: Path) -> None:
    ledger = _ledger(tmp_path)
    marker = "SECRET-MARKER-never-persist"
    result = _result(items=(_item("finding-1", rationale=marker),))
    RC.append_reconciliation_fact(ledger, result, action="reconcile", subplot_id="leaf", at="t")
    raw = ledger.path.read_text(encoding="utf-8")
    assert marker not in raw
    assert "rationale" not in raw
    assert "finding-1" in raw


def test_transition_state_rejects_apply_first_duplicate_and_out_of_order(tmp_path: Path) -> None:
    apply_first = _ledger(tmp_path / "apply-first")
    with pytest.raises(RC.ReconciliationError, match="prior reconcile"):
        RC.append_reconciliation_fact(
            apply_first, _result(), action="apply", subplot_id="leaf", at="t"
        )

    ledger = _ledger(tmp_path / "ordered")
    result = _result()
    RC.append_reconciliation_fact(ledger, result, action="reconcile", subplot_id="leaf", at="t1")
    with pytest.raises(RC.ReconciliationError, match="duplicate"):
        RC.append_reconciliation_fact(
            ledger, result, action="reconcile", subplot_id="leaf", at="t2"
        )
    RC.append_reconciliation_fact(ledger, result, action="apply", subplot_id="leaf", at="t3")
    with pytest.raises(RC.ReconciliationError, match="prior reconcile"):
        RC.append_reconciliation_fact(ledger, result, action="apply", subplot_id="leaf", at="t4")


def test_concurrent_reconciliation_writers_share_atomic_snapshot(tmp_path: Path) -> None:
    ledger = _ledger(tmp_path)

    def write(index: int) -> None:
        result = RC.build_result(
            reconciliation_id=f"recon-{index}",
            execution_id=f"exec-{index}",
            intent="offload",
            adjudicator_id="claude",
            source_finding_ids=(),
            items=(),
        )
        RC.append_reconciliation_fact(
            ledger, result, action="reconcile", subplot_id=f"leaf-{index}", at="t"
        )

    with ThreadPoolExecutor(max_workers=8) as pool:
        list(pool.map(write, range(40)))
    assert len(RC.read_reconciliation_facts(ledger)) == 40
    assert RL.verify_chain(ledger).ok


def test_verify_read_race_observes_only_consistent_snapshots(tmp_path: Path) -> None:
    ledger = _ledger(tmp_path)

    def write(index: int) -> None:
        RL.append_fact(
            ledger,
            RL.build_fact("engine", subplot_id=f"leaf-{index}", at="t", tokens=index),
        )

    with ThreadPoolExecutor(max_workers=5) as pool:
        futures = [pool.submit(write, index) for index in range(30)]
        while not all(future.done() for future in futures):
            assert RL.read_snapshot(ledger).report.ok
        for future in futures:
            future.result()
    snapshot = RL.read_snapshot(ledger)
    assert snapshot.report.ok and len(snapshot.records) == 30


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


@pytest.mark.parametrize(
    ("mutation", "match"),
    [
        ({"schema": "wrong"}, "unsupported schema"),
        ({"at": 1}, "at must be a string"),
        ({"action": 1}, "invalid reconciliation action"),
        ({"action": "publish"}, "invalid reconciliation action"),
        ({"recipe_id": "wrong"}, "recipe disagrees"),
        ({"evidence_digest": "wrong"}, "lowercase SHA-256"),
        ({"source_finding_ids": "wrong"}, "contain arrays"),
        ({"source_finding_ids": ["finding-1", "finding-1"]}, "duplicate source"),
        ({"items": ["wrong"]}, "item projection"),
        ({"items": [{"source_finding_id": "finding-1", "status": "wrong"}]}, "invalid reconciliation status"),
        ({"items": []}, "account for each source"),
        ({"result_hash": "wrong"}, "result_hash"),
    ],
)
def test_projection_validator_covers_malformed_fields(
    tmp_path: Path, mutation: dict[str, Any], match: str
) -> None:
    ledger = _ledger(tmp_path)
    RC.append_reconciliation_fact(ledger, _result(), action="reconcile", subplot_id="leaf", at="t")
    record = RL.read_facts(ledger)[0]
    mutated = {**record, **mutation}
    with pytest.raises(RC.ReconciliationError, match=match):
        RC._validated_reconciliation_facts(
            (mutated,), RL.ChainReport(True, None, "ok")
        )


def test_reader_refuses_corrupt_chain(tmp_path: Path) -> None:
    ledger = _ledger(tmp_path)
    RC.append_reconciliation_fact(ledger, _result(), action="reconcile", subplot_id="leaf", at="t")
    record = json.loads(ledger.path.read_text())
    record["execution_id"] = "tampered"
    ledger.path.write_text(json.dumps(record) + "\n")
    with pytest.raises(RC.ReconciliationError, match="chain verification failed"):
        RC.read_reconciliation_facts(ledger)


def test_retro_reader_refuses_non_trailing_corruption(tmp_path: Path) -> None:
    ledger = _ledger(tmp_path)
    result = _result()
    RC.append_reconciliation_fact(ledger, result, action="reconcile", subplot_id="leaf", at="t1")
    RC.append_reconciliation_fact(ledger, result, action="apply", subplot_id="leaf", at="t2")
    lines = ledger.path.read_text().splitlines()
    ledger.path.write_text("{torn-middle\n" + lines[1] + "\n")

    with pytest.raises(RL.RunLedgerError, match="not the trailing line"):
        RC.derive_recipe_update_proposal(ledger)


def test_retro_reader_tolerates_only_torn_trailing_line(tmp_path: Path) -> None:
    ledger = _ledger(tmp_path)
    RC.append_reconciliation_fact(ledger, _result(), action="reconcile", subplot_id="leaf", at="t")
    ledger.path.write_bytes(ledger.path.read_bytes() + b'{"schema":"run_fact.v1"')
    before = ledger.path.read_bytes()

    proposal = RC.derive_recipe_update_proposal(ledger)

    assert proposal["status"] == "proposal"
    assert proposal["proposed_updates"][0]["reconciliation_count"] == 1
    assert ledger.path.read_bytes() == before


def test_retro_reader_refuses_invalid_reconciliation_fact(tmp_path: Path) -> None:
    ledger = _ledger(tmp_path)
    result = _result()
    RL.append_fact(
        ledger,
        RL.build_fact(
            "reconciliation",
            subplot_id="leaf",
            at="t",
            reconciliation_id=result.reconciliation_id,
            execution_id=result.execution_id,
            intent=result.intent,
            recipe_id=result.recipe_id,
            adjudicator_id=result.adjudicator_id,
            evidence_digest=result.evidence_digest,
            action="reconcile",
            result_hash=RC.canonical_result_hash(result),
            source_finding_ids=list(result.source_finding_ids),
            items=[
                {"source_finding_id": result.source_finding_ids[0], "status": "accepted"}
            ],
        ),
    )

    with pytest.raises(RC.ReconciliationError, match="invalid reconciliation status"):
        RC.derive_recipe_update_proposal(ledger)


def test_panel_evidence_deduplicates_output_and_preserves_empty_member() -> None:
    evidence = RC.gather_panel_evidence(
        (
            ("codex/one", "same advisory finding"),
            ("agy/two", "same advisory finding"),
            ("ollama/three", "  "),
        )
    )

    assert len(evidence) == 2
    duplicate, empty = evidence
    assert duplicate.member_ids == ("codex/one", "agy/two")
    assert duplicate.empty is False
    assert empty.member_ids == ("ollama/three",)
    assert empty.empty is True
    assert empty.source_finding_id.startswith("panel-empty:")


@pytest.mark.parametrize(
    ("kwargs", "match"),
    [
        ({"member_ids": ()}, "at least one"),
        ({"member_ids": ("same", "same")}, "unique"),
        ({"output": 1}, "must be a string"),
        ({"output": "text", "empty": True}, "empty marker"),
    ],
)
def test_panel_evidence_invariants(kwargs: dict[str, Any], match: str) -> None:
    values = {
        "source_finding_id": "panel:f",
        "member_ids": ("member",),
        "output": "text",
        "empty": False,
        **kwargs,
    }
    with pytest.raises(RC.ReconciliationError, match=match):
        RC.PanelMemberEvidence(**values)
    with pytest.raises(RC.ReconciliationError, match="output must be a string"):
        RC.gather_panel_evidence((("member", 1),))


def test_panel_foreman_must_account_for_exact_gathered_evidence() -> None:
    evidence = RC.gather_panel_evidence((("codex/one", "finding"),))
    result = RC.build_result(
        reconciliation_id="panel-reconciliation",
        execution_id="panel-execution",
        intent="second-opinion",
        adjudicator_id="claude/foreman",
        source_finding_ids=(),
        items=(),
    )

    with pytest.raises(RC.ReconciliationError, match="exact ordered"):
        RC.validate_panel_reconciliation(
            result,
            execution_id="panel-execution",
            intent="second-opinion",
            evidence=evidence,
        )


def test_panel_result_helper_binds_ordered_evidence_without_raw_output() -> None:
    evidence = RC.gather_panel_evidence(
        (
            ("codex/one", "duplicate finding"),
            ("agy/two", "duplicate finding"),
            ("ollama/three", ""),
        )
    )
    result = RC.build_panel_reconciliation_result(
        reconciliation_id="panel-reconciliation",
        execution_id="panel-execution",
        intent="second-opinion",
        adjudicator_id="claude/foreman",
        evidence=evidence,
        items=tuple(
            RC.ReconciliationItem(
                item.source_finding_id,
                RC.ReconciliationStatus.RECONCILED,
                "claude/foreman",
                "Claude accounted for this panel evidence.",
            )
            for item in evidence
        ),
    )

    assert result.source_finding_ids == tuple(item.source_finding_id for item in evidence)
    assert RC.validate_panel_reconciliation(
        result,
        execution_id="panel-execution",
        intent="second-opinion",
        evidence=evidence,
    ) is result
    serialized = json.dumps(result.to_dict(), sort_keys=True)
    assert "duplicate finding" not in serialized


def test_panel_foreman_rejects_reordered_ids_and_wrong_binding_digest() -> None:
    evidence = RC.gather_panel_evidence(
        (("codex/one", "finding one"), ("agy/two", "finding two"))
    )
    items = tuple(
        RC.ReconciliationItem(
            item.source_finding_id,
            RC.ReconciliationStatus.RECONCILED,
            "claude",
            "Claude accounted for this panel evidence.",
        )
        for item in evidence
    )
    bound = RC.build_panel_reconciliation_result(
        reconciliation_id="panel-reconciliation",
        execution_id="panel-execution",
        intent="second-opinion",
        adjudicator_id="claude",
        evidence=evidence,
        items=items,
    )
    reordered = RC.build_result(
        reconciliation_id="panel-reordered",
        execution_id="panel-execution",
        intent="second-opinion",
        adjudicator_id="claude",
        evidence_digest=bound.evidence_digest,
        source_finding_ids=tuple(reversed(bound.source_finding_ids)),
        items=tuple(reversed(items)),
    )
    wrong_digest = RC.build_result(
        reconciliation_id="panel-wrong-digest",
        execution_id="panel-execution",
        intent="second-opinion",
        adjudicator_id="claude",
        evidence_digest="0" * 64,
        source_finding_ids=bound.source_finding_ids,
        items=items,
    )

    with pytest.raises(RC.ReconciliationError, match="exact ordered"):
        RC.validate_panel_reconciliation(
            reordered,
            execution_id="panel-execution",
            intent="second-opinion",
            evidence=evidence,
        )
    with pytest.raises(RC.ReconciliationError, match="evidence_digest"):
        RC.validate_panel_reconciliation(
            wrong_digest,
            execution_id="panel-execution",
            intent="second-opinion",
            evidence=evidence,
        )


def test_panel_foreman_rejects_wrong_type_execution_and_intent() -> None:
    evidence = RC.gather_panel_evidence((('member', 'finding'),))
    with pytest.raises(RC.ReconciliationError, match="typed reconciliation"):
        RC.validate_panel_reconciliation(None, execution_id="e", intent="offload", evidence=evidence)
    result = RC.build_result(
        reconciliation_id="panel",
        execution_id="wrong",
        intent="offload",
        adjudicator_id="claude",
        source_finding_ids=tuple(item.source_finding_id for item in evidence),
        items=tuple(
            RC.ReconciliationItem(
                item.source_finding_id,
                RC.ReconciliationStatus.RECONCILED,
                "claude",
                "reason",
            )
            for item in evidence
        ),
    )
    with pytest.raises(RC.ReconciliationError, match="execution_id"):
        RC.validate_panel_reconciliation(result, execution_id="expected", intent="offload", evidence=evidence)
    with pytest.raises(RC.ReconciliationError, match="intent"):
        RC.validate_panel_reconciliation(result, execution_id="wrong", intent="divergence", evidence=evidence)
