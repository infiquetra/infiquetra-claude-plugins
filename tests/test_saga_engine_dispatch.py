"""Oracle tests for the Saga external-engine dispatch adapter (U4)."""

from __future__ import annotations

import dataclasses
import importlib.util
import sys
from pathlib import Path
from types import ModuleType
from typing import Any, cast

import pytest

ROOT = Path(__file__).parent.parent
SCRIPT_DIR = ROOT / "plugins" / "saga" / "scripts"
REGISTRY_SCRIPT = SCRIPT_DIR / "engine_registry.py"
RESOLVER_SCRIPT = SCRIPT_DIR / "engine_resolver.py"
DISPATCH_SCRIPT = SCRIPT_DIR / "engine_dispatch.py"


def _load(name: str, path: Path) -> ModuleType:
    if str(SCRIPT_DIR) not in sys.path:
        sys.path.insert(0, str(SCRIPT_DIR))
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


REG = _load("engine_registry", REGISTRY_SCRIPT)
R = _load("engine_resolver", RESOLVER_SCRIPT)
D = _load("engine_dispatch", DISPATCH_SCRIPT)
# Reuse the exact module objects engine_dispatch imported (a re-_load would mint distinct
# enum classes and break `is` identity checks).
MS = D.manifest_store
PM = D.pm
RC = D.reconcile


def _ready_reconciliation(evidence: Any) -> Any:
    return RC.build_result(
        reconciliation_id=f"test-reconciliation-{id(evidence)}",
        execution_id=evidence.execution_id,
        intent=evidence.intent,
        adjudicator_id="claude",
        evidence_digest=evidence.evidence_digest,
        source_finding_ids=evidence.source_finding_ids,
        items=tuple(
            RC.ReconciliationItem(
                source_finding_id=finding_id,
                status=RC.ReconciliationStatus.RECONCILED,
                adjudicator_id="claude",
                rationale="Claude accounted for the advisory finding.",
            )
            for finding_id in evidence.source_finding_ids
        ),
    )


def _resolution(
    *,
    engine_id: str = "codex",
    variant: str = "gpt-5.5-xhigh",
    payload: str = "Run read-only.\n\nReturn a unified diff.",
    halt: str | None = None,
) -> Any:
    return R.Resolution(
        engine_id=engine_id,
        variant=variant,
        effort="high",
        recipe="recipe",
        protocol=["Run read-only."],
        payload=payload,
        write_capable=False,
        fallback=None,
        halt=halt,
    )


def test_codex_invocation_preserves_payload_byte_for_byte_and_read_only() -> None:
    payload = "Run read-only.\n\nReturn the diff exactly.\nTrailing spaces:  "
    resolution = _resolution(payload=payload)

    invocation = D.build_codex_invocation(resolution)

    assert invocation == {
        "via": "codex:delegate",
        "task": payload,
        "sandbox": "read-only",
    }
    assert invocation["task"].encode("utf-8") == payload.encode("utf-8")


def test_agy_envelope_is_no_write_and_forwards_model_verbatim() -> None:
    payload = "Use the no-write envelope.\n\nReturn evidence only."
    model = "  Gemini 3.1 Pro (High)  "
    resolution = _resolution(
        engine_id="agy",
        variant="gemini-3.1-pro-high",
        payload=payload,
    )

    envelope = D.build_agy_envelope(resolution, model=model)

    assert envelope["schema"] == "agy.delegation.v1"
    assert envelope["mode"] == "no-write"
    assert envelope["task"] == payload
    assert envelope["model"] == model


@pytest.mark.parametrize(
    "status",
    ["timeout", "no-output", "error", "malformed", "clone-failed"],
)
def test_dispatch_failure_status_halts_with_downgrade_note_and_no_verdict(
    status: str,
) -> None:
    calls: list[dict[str, Any]] = []

    def runner(invocation: dict[str, Any]) -> dict[str, str]:
        calls.append(invocation)
        return {"status": status, "output": "wrapper failed"}

    evidence = D.dispatch(_resolution(), runner=runner)

    assert len(calls) == 1
    assert evidence.halt is not None
    assert evidence.evidence == ""
    assert evidence.provenance["status"] == status
    assert "note" in evidence.provenance
    assert "Downgraded external engine codex" in evidence.provenance["note"]
    assert status in evidence.provenance["note"]
    assert not hasattr(evidence, "gated_verdict")
    assert "gated_verdict" not in evidence.provenance


def test_dispatch_short_circuits_when_resolution_already_halted() -> None:
    called = False

    def runner(_invocation: dict[str, Any]) -> dict[str, str]:
        nonlocal called
        called = True
        raise AssertionError("runner must not be called for a halted resolution")

    evidence = D.dispatch(_resolution(halt="preflight halted"), runner=runner)

    assert called is False
    assert evidence.halt == "preflight halted"
    assert evidence.evidence == ""
    assert evidence.provenance["status"] == "halted"


def test_satisfy_gate_requires_claude_verification() -> None:
    unverified = D.AdvisoryEvidence(
        engine_id="codex",
        variant="gpt-5.5-xhigh",
        evidence="external finding",
        provenance={"engine": "codex", "variant": "gpt-5.5-xhigh", "status": "ok"},
        execution_id="unverified-execution",
    )

    with pytest.raises(D.DispatchError):
        D.satisfy_gate(unverified, reconciliation=_ready_reconciliation(unverified))

    # #384 U5/R6 (deliberate acceptance change): Claude verification alone is no longer
    # sufficient -- the gate also requires the observer_corroborated mark dispatch stamps.
    verified_uncorroborated = D.AdvisoryEvidence(
        engine_id="codex",
        variant="gpt-5.5-xhigh",
        evidence="Claude verified external finding",
        provenance={"engine": "codex", "variant": "gpt-5.5-xhigh", "status": "ok"},
        execution_id="uncorroborated-execution",
        verified_by_claude=True,
    )
    with pytest.raises(D.DispatchError, match="observer corroboration"):
        D.satisfy_gate(
            verified_uncorroborated,
            reconciliation=_ready_reconciliation(verified_uncorroborated),
        )

    verified = D.AdvisoryEvidence(
        engine_id="codex",
        variant="gpt-5.5-xhigh",
        evidence="Claude verified external finding",
        provenance={
            "engine": "codex",
            "variant": "gpt-5.5-xhigh",
            "status": "ok",
            "observer_corroborated": True,
        },
        execution_id="verified-execution",
        verified_by_claude=True,
    )

    assert D.satisfy_gate(verified, reconciliation=_ready_reconciliation(verified)) is None


def test_satisfy_gate_requires_ready_reconciliation_before_existing_checks() -> None:
    evidence = D.AdvisoryEvidence(
        engine_id="codex",
        variant="gpt-5.5-xhigh",
        evidence="Claude verified external finding",
        provenance={"status": "ok", "observer_corroborated": True},
        execution_id="test-execution",
        verified_by_claude=True,
    )
    with pytest.raises(D.DispatchError, match="typed reconciliation result is required"):
        D.satisfy_gate(evidence)

    incomplete = RC.build_result(
        reconciliation_id="incomplete-reconciliation",
        execution_id="test-execution",
        intent="offload",
        adjudicator_id="claude",
        source_finding_ids=("net-new",),
        items=(),
    )
    with pytest.raises(D.DispatchError, match="net-new"):
        D.satisfy_gate(evidence, reconciliation=incomplete)

    dropped = RC.build_result(
        reconciliation_id="complete-reconciliation",
        execution_id="test-execution",
        intent="offload",
        adjudicator_id="claude",
        evidence_digest=evidence.evidence_digest,
        source_finding_ids=evidence.source_finding_ids,
        items=(
            RC.ReconciliationItem(
                source_finding_id=evidence.source_finding_ids[0],
                status=RC.ReconciliationStatus.DROPPED,
                adjudicator_id="claude",
                rationale="Claude found no source support for the advisory finding.",
            ),
        ),
    )
    assert D.satisfy_gate(evidence, reconciliation=dropped) is None


@pytest.mark.parametrize(
    ("intent", "output", "status"),
    [
        ("offload", "patch candidate", RC.ReconciliationStatus.RECONCILED),
        ("second-opinion", "independent finding", RC.ReconciliationStatus.OVERRIDDEN),
        ("divergence", "agreement: both analyses match", RC.ReconciliationStatus.RECONCILED),
        ("divergence", "disagreement: engine disputes Claude", RC.ReconciliationStatus.DROPPED),
    ],
)
def test_dispatch_reconcile_gate_integration_for_every_intent(
    intent: str, output: str, status: Any
) -> None:
    execution_id = f"integration-{intent}-{status.value}"
    dispatched = D.dispatch(
        _resolution(),
        runner=lambda _invocation: {"status": "ok", "output": output},
        execution_id=execution_id,
        intent=intent,
    )
    assert isinstance(dispatched, D.AdvisoryEvidence)
    verified = dataclasses.replace(
        dispatched,
        verified_by_claude=True,
        provenance={**dispatched.provenance, "observer_corroborated": True},
    )
    reconciliation = RC.build_result(
        reconciliation_id=f"recon-{execution_id}",
        execution_id=verified.execution_id,
        intent=verified.intent,
        adjudicator_id="claude",
        evidence_digest=verified.evidence_digest,
        source_finding_ids=verified.source_finding_ids,
        items=(
            RC.ReconciliationItem(
                source_finding_id=verified.source_finding_ids[0],
                status=status,
                adjudicator_id="claude",
                rationale="Claude explicitly adjudicated agreement or disagreement.",
            ),
        ),
    )
    assert D.satisfy_gate(verified, reconciliation=reconciliation) is None


@pytest.mark.parametrize(
    ("mutation", "match"),
    [
        ("execution", "execution_id"),
        ("intent", "intent"),
        ("recipe", "recipe"),
        ("digest", "digest"),
        ("sources", "source findings"),
        ("empty", "empty reconciliation"),
    ],
)
def test_satisfy_gate_rejects_every_reconciliation_binding_mismatch(
    mutation: str, match: str
) -> None:
    evidence = D.AdvisoryEvidence(
        engine_id="codex",
        variant="gpt-5.5-xhigh",
        evidence="bound finding",
        provenance={"status": "ok", "observer_corroborated": True},
        execution_id="bound-execution",
        intent="offload",
        verified_by_claude=True,
    )
    result = _ready_reconciliation(evidence)
    if mutation == "execution":
        result = dataclasses.replace(result, execution_id="wrong-execution")
    elif mutation == "intent":
        result = dataclasses.replace(
            result,
            intent="second-opinion",
            recipe_id=RC.recipe_for_intent("second-opinion").recipe_id,
        )
    elif mutation == "recipe":
        object.__setattr__(result, "recipe_id", "forged-recipe")
    elif mutation == "digest":
        result = dataclasses.replace(result, evidence_digest="0" * 64)
    elif mutation == "sources":
        result = RC.build_result(
            reconciliation_id="wrong-sources",
            execution_id=evidence.execution_id,
            intent=evidence.intent,
            adjudicator_id="claude",
            evidence_digest=evidence.evidence_digest,
            source_finding_ids=("other-source",),
            items=(
                RC.ReconciliationItem(
                    source_finding_id="other-source",
                    status=RC.ReconciliationStatus.RECONCILED,
                    adjudicator_id="claude",
                    rationale="Wrong source for binding test.",
                ),
            ),
        )
    else:
        result = RC.build_result(
            reconciliation_id="empty",
            execution_id=evidence.execution_id,
            intent=evidence.intent,
            adjudicator_id="claude",
            evidence_digest=evidence.evidence_digest,
            source_finding_ids=(),
            items=(),
        )
    with pytest.raises(D.DispatchError, match=match):
        D.satisfy_gate(evidence, reconciliation=result)


def test_satisfy_gate_rejects_exact_replay() -> None:
    evidence = D.AdvisoryEvidence(
        engine_id="codex",
        variant="gpt-5.5-xhigh",
        evidence="one-shot finding",
        provenance={"status": "ok", "observer_corroborated": True},
        execution_id="one-shot-execution",
        verified_by_claude=True,
    )
    result = _ready_reconciliation(evidence)
    assert D.satisfy_gate(evidence, reconciliation=result) is None
    with pytest.raises(D.DispatchError, match="replay"):
        D.satisfy_gate(evidence, reconciliation=result)


def test_satisfy_gate_rejects_advisory_reviewer_evidence_even_when_verified() -> None:
    evidence = D.AdvisoryEvidence(
        engine_id="codex",
        variant="gpt-5.5-xhigh",
        evidence="Claude verified reviewer finding",
        provenance={
            "engine": "codex",
            "variant": "gpt-5.5-xhigh",
            "status": "ok",
            "observer_corroborated": True,
        },
        execution_id="reviewer-execution",
        verified_by_claude=True,
        role_kind="advisory-reviewer",
    )

    with pytest.raises(D.DispatchError, match="advisory-only"):
        D.satisfy_gate(evidence, reconciliation=_ready_reconciliation(evidence))


def test_satisfy_gate_rejects_panel_evidence_even_when_verified() -> None:
    evidence = D.AdvisoryEvidence(
        engine_id="codex",
        variant="gpt-5.5-xhigh",
        evidence="Claude verified panel synthesis",
        provenance={"status": "ok", "observer_corroborated": True},
        execution_id="panel-execution",
        verified_by_claude=True,
        role_kind="panel",
    )

    with pytest.raises(D.DispatchError, match="advisory-only"):
        D.satisfy_gate(evidence, reconciliation=_ready_reconciliation(evidence))


def _economics_resolution(**overrides: object) -> Any:
    values: dict[str, object] = {
        "cost_class": "metered",
        "budget_ceiling_usd": 25.0,
        "estimated_input_cost_usd": 0.004,
    }
    values.update(overrides)
    return dataclasses.replace(_resolution(), **values)


def test_metered_offload_economics_proceed_invokes_runner_and_stamps_provenance() -> None:
    calls: list[dict[str, Any]] = []

    def runner(invocation: dict[str, Any]) -> dict[str, Any]:
        calls.append(invocation)
        return {"status": "ok", "output": "external finding"}

    evidence = D.dispatch(
        _economics_resolution(),
        runner=runner,
        economics={
            "claude_inline_tokens_estimate": 1000,
            "chaperone_tokens_estimate": 200,
        },
    )

    assert len(calls) == 1
    assert evidence.evidence == "external finding"
    assert evidence.provenance["economics"]["status"] == "proceed"
    assert evidence.provenance["economics"]["net_savings"]["net_savings_tokens"] == 800


def test_dispatch_manifest_records_net_savings_economics() -> None:
    evidence = D.dispatch(
        _economics_resolution(),
        runner=_ok_runner,
        economics={
            "claude_inline_tokens_estimate": 1000,
            "chaperone_tokens_estimate": 200,
        },
    )

    manifest = D.build_dispatch_manifest(
        evidence,
        execution_id="exec-economics",
        saga_ref="saga-1",
        created_at="2026-07-09T00:00:00Z",
    )

    assert manifest.economics is not None
    assert manifest.economics.engine_tokens_avoided == 1000
    assert manifest.economics.chaperone_tokens_spent == 200
    assert manifest.economics.net_savings_tokens == 800
    assert manifest.economics.net_savings_status == "positive"
    assert manifest.economics.external_cost_usd == 0.004
    assert PM.Manifest.from_dict(manifest.to_dict()).economics == manifest.economics


def test_dispatch_engine_fact_records_net_savings_economics(tmp_path: Path) -> None:
    ledger = RL.RunLedger(path=tmp_path / "run-facts.jsonl")

    D.dispatch(
        _economics_resolution(),
        runner=_metric_runner(cost=0.004, tokens=200),
        ledger=ledger,
        subplot_id="s1",
        at="2026-07-09T00:00:00Z",
        economics={
            "claude_inline_tokens_estimate": 1000,
            "chaperone_tokens_estimate": 200,
        },
    )

    fact = RL.read_facts(ledger)[0]
    assert fact["engine_tokens_avoided"] == 1000
    assert fact["chaperone_tokens_spent"] == 200
    assert fact["net_savings_tokens"] == 800
    assert fact["net_savings_status"] == "positive"
    assert fact["external_cost_usd"] == 0.004


def test_break_even_economics_halt_does_not_invoke_runner() -> None:
    called = False

    def runner(_invocation: dict[str, Any]) -> dict[str, Any]:
        nonlocal called
        called = True
        raise AssertionError("runner must not be called for break-even halt")

    evidence = D.dispatch(
        _economics_resolution(),
        runner=runner,
        economics={
            "claude_inline_tokens_estimate": 1000,
            "chaperone_tokens_estimate": 1000,
        },
    )

    assert called is False
    assert evidence.halt == "break-even-halt"
    assert evidence.provenance["status"] == "halted"
    assert evidence.provenance["economics"]["status"] == "break-even-halt"


def test_budget_ceiling_economics_halt_reads_prior_provider_spend(tmp_path: Path) -> None:
    ledger = RL.RunLedger(path=tmp_path / "run-facts.jsonl")
    RL.append_fact(
        ledger,
        RL.build_fact(
            "engine",
            subplot_id="prior",
            at="2026-07-05T00:00:00Z",
            engine="codex",
            variant="gpt-5.5-xhigh",
            status="ok",
            cost=5.0,
        ),
    )

    called = False

    def runner(_invocation: dict[str, Any]) -> dict[str, Any]:
        nonlocal called
        called = True
        raise AssertionError("runner must not be called for ceiling halt")

    evidence = D.dispatch(
        _economics_resolution(budget_ceiling_usd=5.2, estimated_input_cost_usd=0.25),
        runner=runner,
        ledger=ledger,
        economics={
            "claude_inline_tokens_estimate": 1000,
            "chaperone_tokens_estimate": 100,
        },
    )

    assert called is False
    assert evidence.halt == "budget-ceiling-halt"
    assert evidence.provenance["economics"]["prior_provider_spend_usd"] == 5.0
    assert evidence.provenance["economics"]["projected_provider_spend_usd"] == 5.25


def test_missing_metered_economics_halt_does_not_invoke_runner() -> None:
    called = False

    def runner(_invocation: dict[str, Any]) -> dict[str, Any]:
        nonlocal called
        called = True
        raise AssertionError("runner must not be called for missing economics")

    evidence = D.dispatch(
        _economics_resolution(estimated_input_cost_usd=None),
        runner=runner,
        economics={"claude_inline_tokens_estimate": 1000},
    )

    assert called is False
    assert evidence.halt == "economics-missing-halt"
    assert evidence.provenance["economics"]["missing_fields"] == [
        "estimated_external_cost_usd",
        "chaperone_tokens_estimate",
    ]


def test_free_class_economics_runs_without_estimates() -> None:
    calls: list[dict[str, Any]] = []

    def runner(invocation: dict[str, Any]) -> dict[str, Any]:
        calls.append(invocation)
        return {"status": "ok", "output": "free output"}

    evidence = D.dispatch(
        _economics_resolution(
            engine_id="ollama-cloud",
            cost_class="free",
            budget_ceiling_usd=None,
            estimated_input_cost_usd=None,
            invocation={
                "via": "engine-bridge-http",
                "base_url": "https://ollama.com/v1",
                "model": "gpt-oss:120b",
                "effort": "default",
                "auth": {"mode": "bearer", "key_env": "OLLAMA_API_KEY"},
            },
        ),
        runner=runner,
        economics={},
    )

    assert len(calls) == 1
    assert evidence.evidence == "free output"
    assert evidence.provenance["economics"]["status"] == "free-class-proceed"


def test_resolution_halt_precedes_economics_and_runner() -> None:
    called = False

    def runner(_invocation: dict[str, Any]) -> dict[str, Any]:
        nonlocal called
        called = True
        raise AssertionError("runner must not be called for resolution halt")

    evidence = D.dispatch(
        _economics_resolution(halt="preflight halted"),
        runner=runner,
        economics={
            "claude_inline_tokens_estimate": 1000,
            "chaperone_tokens_estimate": 1000,
        },
    )

    assert called is False
    assert evidence.halt == "preflight halted"
    assert "economics" not in evidence.provenance


def test_dispatch_returns_advisory_evidence_without_tree_mutation_surface() -> None:
    payload = "Change plugins/saga/scripts/example.py.\n\nReturn the patch as evidence."

    def runner(invocation: dict[str, Any]) -> dict[str, str]:
        assert invocation["sandbox"] == "read-only"
        return {
            "status": "ok",
            "output": "diff --git a/example.py b/example.py\n+proposed evidence only",
        }

    evidence = D.dispatch(_resolution(payload=payload), runner=runner)

    assert isinstance(evidence, D.AdvisoryEvidence)
    assert evidence.evidence.startswith("diff --git")
    assert evidence.halt is None
    assert evidence.provenance == {
        "engine": "codex",
        "variant": "gpt-5.5-xhigh",
        "status": "ok",
    }
    assert not hasattr(evidence, "gated_verdict")


# --- U3: typed manifests (claim_provenance, attribution, disposition) + R11 gate ----------


def _valid_receipt(*, engine_id: str = "codex", variant: str = "gpt-5.5-xhigh") -> dict[str, Any]:
    """A schema-valid ``bridge_receipt.v1`` (cli-shaped) for tests exercising the RAN_AS_REQUESTED
    path (U6/KTD8): receipt-gating means a bare ``ok`` runner result is no longer sufficient."""
    output_attestation = D.fleet_commons_shim.load("output_attestation").emit_attestation(
        artifact="evidence",
        content="external finding",
    )
    return cast(
        "dict[str, Any]",
        D._bridge_receipt.emit_receipt(
            engine_id=engine_id,
            variant=variant,
            transport="cli",
            wall_time_s=0.5,
            bytes_produced=17,
            runner={"pid": 4242, "argv": ["codex", "run"], "exit_code": 0},
            receipt_emitter="codex-bridge",
            run_id="test-run-1",
            external_tokens=42,
            output_attestation=output_attestation,
        ),
    )


def _ok_runner(_invocation: dict[str, Any]) -> dict[str, Any]:
    return {"status": "ok", "output": "external finding", "receipt": _valid_receipt()}


def _store(tmp_path: Path) -> Any:
    return MS.Store(root=tmp_path / "saga-manifests" / "saga-1").ensure()


def test_dispatch_emits_manifest_with_attribution(tmp_path: Path) -> None:
    store = _store(tmp_path)
    evidence = D.dispatch(_resolution(), runner=_ok_runner, execution_id="exec-claims")

    manifest = D.record_dispatch_manifest(
        store,
        evidence,
        execution_id="exec-1",
        saga_ref="saga-1",
        created_at="2026-07-01T00:00:00Z",
        effort="high",
        protocol="codex:delegate",
    )

    assert manifest.attribution.kind is PM.ProducerKind.EXTERNAL_ENGINE
    assert manifest.attribution.identity == "codex/gpt-5.5-xhigh"
    assert manifest.attribution.effort == "high"
    assert manifest.attribution.protocol == "codex:delegate"
    assert manifest.disposition is PM.Disposition.RAN_AS_REQUESTED

    persisted = MS.read_manifest(store, "exec-1")
    assert persisted is not None
    round_tripped = PM.Manifest.from_dict(persisted)
    assert round_tripped.attribution.identity == "codex/gpt-5.5-xhigh"
    assert round_tripped.schema == PM.SCHEMA_VERSION


def test_halted_dispatch_records_disposition_note(tmp_path: Path) -> None:
    store = _store(tmp_path)

    def failing_runner(_invocation: dict[str, Any]) -> dict[str, str]:
        return {"status": "timeout", "output": "wrapper timed out"}

    evidence = D.dispatch(_resolution(), runner=failing_runner)
    manifest = D.record_dispatch_manifest(
        store,
        evidence,
        execution_id="exec-halt",
        saga_ref="saga-1",
        created_at="2026-07-01T00:00:00Z",
    )

    assert manifest.disposition is PM.Disposition.FELL_BACK_TO_CLAUDE
    assert "Downgraded external engine codex" in manifest.disposition_note
    assert "timeout" in manifest.disposition_note

    persisted = MS.read_manifest(store, "exec-halt")
    assert persisted is not None
    assert persisted["disposition"] == "fell-back-to-claude"
    assert "Downgraded external engine codex" in persisted["disposition_note"]


def test_satisfy_gate_refuses_claimed_only_manifest(tmp_path: Path) -> None:
    store = _store(tmp_path)
    evidence = D.dispatch(_resolution(), runner=_ok_runner, execution_id="exec-claims")
    claims = PM.ClaimProvenance(
        claims=(
            PM.Claim(
                text="all tests pass",
                claimed=PM.ClaimedStatus.VERIFIED,
                source_ref="tests/test_example.py",
            ),
        )
    )
    manifest = D.record_dispatch_manifest(
        store,
        evidence,
        execution_id="exec-claims",
        saga_ref="saga-1",
        created_at="2026-07-01T00:00:00Z",
        claim_provenance=claims,
    )

    verified = D.AdvisoryEvidence(
        engine_id=evidence.engine_id,
        variant=evidence.variant,
        evidence=evidence.evidence,
        # #384 U5/R6 deliberate update: the gate now also requires the observer mark.
        provenance={**evidence.provenance, "observer_corroborated": True},
        execution_id=evidence.execution_id,
        intent=evidence.intent,
        verified_by_claude=True,
    )

    # Claimed-`verified` without adjudication cannot satisfy a gate (R11/AE1).
    with pytest.raises(D.DispatchError):
        D.satisfy_gate(verified, manifest, reconciliation=_ready_reconciliation(verified))

    # After the driving session adjudicates every claim, the gate opens.
    adjudicated = D.adjudicate_manifest(
        store,
        "exec-claims",
        {
            ("all tests pass", "tests/test_example.py"): (
                PM.AdjudicatedStatus.VERIFIED,
                PM.Adjudication(
                    adjudicator="claude",
                    sources_read=("tests/test_example.py",),
                    decision="re-ran suite, all green",
                ),
            )
        },
    )
    assert (
        D.satisfy_gate(verified, adjudicated, reconciliation=_ready_reconciliation(verified))
        is None
    )

    # verified_by_claude is still required even with a fully adjudicated manifest.
    with pytest.raises(D.DispatchError):
        D.satisfy_gate(evidence, adjudicated, reconciliation=_ready_reconciliation(evidence))


def test_adjudicated_refuted_counts_as_parroting(tmp_path: Path) -> None:
    store = _store(tmp_path)
    evidence = D.dispatch(_resolution(), runner=_ok_runner)
    claims = PM.ClaimProvenance(
        claims=(
            PM.Claim(
                text="lint is clean",
                claimed=PM.ClaimedStatus.VERIFIED,
                source_ref="pyproject.toml",
            ),
        )
    )
    D.record_dispatch_manifest(
        store,
        evidence,
        execution_id="exec-parrot",
        saga_ref="saga-1",
        created_at="2026-07-01T00:00:00Z",
        claim_provenance=claims,
    )

    adjudicated = D.adjudicate_manifest(
        store,
        "exec-parrot",
        {
            ("lint is clean", "pyproject.toml"): (
                PM.AdjudicatedStatus.REFUTED,
                PM.Adjudication(adjudicator="claude", decision="ruff reported 3 errors"),
            )
        },
    )

    claim = adjudicated.claim_provenance.claims[0]
    assert claim.adjudicated is PM.AdjudicatedStatus.REFUTED
    assert claim.mismatch_reason is PM.MismatchReason.REFUTED
    assert PM.is_parroting(claim) is True
    assert PM.parroting_count(adjudicated) == 1

    # The parroting signal stays advisory: it is countable, never a gate of its own (R12).
    persisted = MS.read_manifest(store, "exec-parrot")
    assert persisted is not None
    assert "verdict" not in persisted


def test_adjudicate_manifest_keys_same_text_claims_independently(tmp_path: Path) -> None:
    """Two claims sharing text but grounded in different sources adjudicate independently."""
    store = _store(tmp_path)
    evidence = D.dispatch(_resolution(), runner=_ok_runner)
    claims = PM.ClaimProvenance(
        claims=(
            PM.Claim(
                text="module is covered",
                claimed=PM.ClaimedStatus.VERIFIED,
                source_ref="tests/test_a.py",
            ),
            PM.Claim(
                text="module is covered",
                claimed=PM.ClaimedStatus.VERIFIED,
                source_ref="tests/test_b.py",
            ),
        )
    )
    D.record_dispatch_manifest(
        store,
        evidence,
        execution_id="exec-dup-text",
        saga_ref="saga-1",
        created_at="2026-07-01T00:00:00Z",
        claim_provenance=claims,
    )
    adjudicated = D.adjudicate_manifest(
        store,
        "exec-dup-text",
        {
            ("module is covered", "tests/test_a.py"): (
                PM.AdjudicatedStatus.VERIFIED,
                PM.Adjudication(adjudicator="claude", decision="ran test_a, green"),
            ),
            ("module is covered", "tests/test_b.py"): (
                PM.AdjudicatedStatus.REFUTED,
                PM.Adjudication(adjudicator="claude", decision="test_b does not exist"),
            ),
        },
    )
    by_source = {c.source_ref: c for c in adjudicated.claim_provenance.claims}
    assert by_source["tests/test_a.py"].adjudicated is PM.AdjudicatedStatus.VERIFIED
    assert by_source["tests/test_b.py"].adjudicated is PM.AdjudicatedStatus.REFUTED


# --------------------------------------------------------- sandbox write-ceiling lift (U5)
# A sandboxed-mutate unit lifts agy to patch-only (wiring the existing clone); codex halts
# (no write adapter). Default / read-only is byte-identical to before. -k sandboxed_harvest.

ES = _load("execution_spec", SCRIPT_DIR / "execution_spec.py")


def test_agy_sandboxed_mutate_lifts_to_patch_only_with_write_set() -> None:
    sb = ES.Sandbox.from_dict("sandboxed-mutate", "w")
    resolution = _resolution(engine_id="agy", variant="gemini-3.1-pro-high", payload="do it")
    envelope = D.build_agy_envelope(
        resolution, model="opus", sandbox=sb, write_set=["a.py", "b.py"]
    )
    assert envelope["mode"] == "patch-only"
    assert envelope["write_set"] == ["a.py", "b.py"]
    assert envelope["apply_policy"] == "preserve-patch"
    assert envelope["task"].encode("utf-8") == b"do it"  # payload still byte-preserved


def test_agy_read_only_sandbox_keeps_no_write_ceiling() -> None:
    # read-only mutation_policy does NOT lift the ceiling even with a write_set present.
    sb = ES.Sandbox.from_dict("read-only-verify", "w")
    resolution = _resolution(engine_id="agy", variant="v", payload="p")
    envelope = D.build_agy_envelope(resolution, model="opus", sandbox=sb, write_set=["x.py"])
    assert envelope["mode"] == "no-write"
    assert envelope["write_set"] == []


def test_agy_no_sandbox_dispatch_is_byte_identical_to_today() -> None:
    # The whole envelope for a no-sandbox unit is unchanged from the pre-#287 shape.
    resolution = _resolution(engine_id="agy", variant="v", payload="p")
    assert D.build_agy_envelope(resolution, model="opus") == {
        "schema": "agy.delegation.v1",
        "role": "coder",
        "mode": "no-write",
        "task": "p",
        "model": "opus",
        "write_set": [],
        "apply_policy": "preserve-patch",
        "evidence": "summary",
        "verification": {"commands": [], "required": False, "run_scope": "none"},
        "provenance_required": True,
    }


def test_codex_sandboxed_mutate_enforce_halt() -> None:
    sb = ES.Sandbox.from_dict("sandboxed-mutate", "w")
    resolution = _resolution(engine_id="codex", payload="p")
    with pytest.raises(D.DispatchError, match="no write adapter"):
        D.build_codex_invocation(resolution, sandbox=sb)


def test_codex_no_sandbox_still_read_only() -> None:
    resolution = _resolution(engine_id="codex", payload="p")
    assert D.build_codex_invocation(resolution)["sandbox"] == "read-only"


def test_dispatch_codex_sandboxed_mutate_propagates_enforce_halt() -> None:
    sb = ES.Sandbox.from_dict("sandboxed-mutate", "w")
    with pytest.raises(D.DispatchError, match="no write adapter"):
        D.dispatch(_resolution(engine_id="codex"), runner=lambda inv: {"status": "ok"}, sandbox=sb)


def test_dispatch_agy_sandboxed_mutate_passes_patch_only_to_runner() -> None:
    sb = ES.Sandbox.from_dict("sandboxed-mutate", "w")
    seen: dict[str, Any] = {}

    def runner(inv: dict[str, Any]) -> dict[str, Any]:
        seen.update(inv)
        return {"status": "ok", "output": "diff"}

    evidence = D.dispatch(
        _resolution(engine_id="agy", variant="v"),
        runner=runner,
        model="opus",
        sandbox=sb,
        write_set=["a.py"],
    )
    assert seen["mode"] == "patch-only"
    assert seen["write_set"] == ["a.py"]
    assert evidence.evidence == "diff"


def test_manifest_records_declared_sandbox_attribution() -> None:
    evidence = D.AdvisoryEvidence(
        engine_id="agy", variant="v", evidence="out", provenance={"status": "ok"}
    )
    manifest = D.build_dispatch_manifest(
        evidence,
        execution_id="e1",
        saga_ref="s1",
        created_at="2026-07-02",
        sandbox="sandboxed-mutate",
    )
    assert manifest.to_dict()["attribution"]["sandbox"] == "sandboxed-mutate"


def test_manifest_absent_sandbox_emits_no_key_and_round_trips() -> None:
    evidence = D.AdvisoryEvidence(
        engine_id="agy", variant="v", evidence="out", provenance={"status": "ok"}
    )
    manifest = D.build_dispatch_manifest(
        evidence, execution_id="e1", saga_ref="s1", created_at="2026-07-02"
    )
    d = manifest.to_dict()
    assert "sandbox" not in d["attribution"]  # absent-tolerant, no new key
    assert d["schema"] == PM.SCHEMA_VERSION  # no version bump
    assert PM.Manifest.from_dict(d).attribution.sandbox == ""  # round-trips clean


# --------------------------------------------------------------------------- #401 run-fact telemetry

RL = D.run_ledger  # reuse the exact run_ledger module engine_dispatch imported (file-based anyway)


def _metric_runner(**metrics: Any):
    def runner(_invocation: Any) -> dict[str, Any]:
        return {"status": "ok", "output": "the diff", **metrics}

    return runner


def test_advisory_call_writes_one_engine_fact(tmp_path: Path) -> None:
    ledger = RL.RunLedger(path=tmp_path / "run-facts.jsonl")
    ev = D.dispatch(
        _resolution(engine_id="codex"),
        runner=_metric_runner(cost=0.02, latency_seconds=1.5, tokens=200),
        ledger=ledger,
        subplot_id="s1",
        at="2026-07-05T00:00:00Z",
    )
    facts = RL.read_facts(ledger)
    assert len(facts) == 1 and facts[0]["kind"] == "engine"
    assert facts[0]["engine"] == "codex"
    assert facts[0]["cost"] == 0.02 and facts[0]["latency_seconds"] == 1.5
    assert facts[0]["tokens"] == 200.0
    assert ev.evidence == "the diff"  # telemetry did not alter the returned evidence (KTD5)


def test_dispatch_without_ledger_writes_no_fact_and_is_unchanged(tmp_path: Path) -> None:
    # Telemetry is opt-in: no ledger -> no file, evidence byte-identical to before #401.
    ledger_path = tmp_path / "run-facts.jsonl"
    ev = D.dispatch(_resolution(engine_id="codex"), runner=_metric_runner(cost=0.02))
    assert ev.evidence == "the diff"
    assert not ledger_path.exists()


def test_agy_delegation_writes_engine_and_delegation_facts(tmp_path: Path) -> None:
    ledger = RL.RunLedger(path=tmp_path / "run-facts.jsonl")
    D.dispatch(
        _resolution(engine_id="agy", variant="gemini-3.1-pro-high"),
        runner=_metric_runner(cost=0.05, tokens=500),
        model="Gemini 3.1 Pro (High)",
        ledger=ledger,
        subplot_id="s1",
        at="t",
    )
    facts = RL.read_facts(ledger)
    assert [f["kind"] for f in facts] == ["engine", "delegation"]
    assert facts[1]["evidence"].startswith("sha256:")  # a pointer, not inlined bytes
    assert facts[1]["engine"] == "agy"
    assert RL.verify_chain(ledger).ok  # the recorded facts form a valid chain


def test_codex_advisory_writes_no_delegation_fact(tmp_path: Path) -> None:
    ledger = RL.RunLedger(path=tmp_path / "run-facts.jsonl")
    D.dispatch(
        _resolution(engine_id="codex"),
        runner=_metric_runner(),
        ledger=ledger,
        subplot_id="s1",
        at="t",
    )
    assert [f["kind"] for f in RL.read_facts(ledger)] == [
        "engine"
    ]  # not a delegation -> engine only


# ---- U4: resolve_memoization -- RunMemo caches the preflight probe (KTD5, R5) ----


def _memoization_registry_dict() -> dict[str, Any]:
    return {
        "capabilities": list(REG.CAPABILITIES),
        "engines": [
            {
                "engine_id": "codex",
                "variant": "gpt-5.5-xhigh",
                "substrate": "external",
                "egress_policy": "networked",
                "trust_tier": "advisory",
                "default_for_engine": True,
                "invocation": {
                    "via": "codex:delegate",
                    "recipe": "codex exec -s read-only -c model_reasoning_effort=xhigh",
                    "write_capable": False,
                },
                "context_window": 400000,
                "cost_speed_rank": 2,
                "cost_per_token": {"input_usd": 0.000005, "output_usd": 0.000015},
                "cost_class": "metered",
                "budget_ceiling_usd": 25.0,
                "latency_class": "standard",
                "model_identity": "gpt-5.5",
                "last_validated": "2026-07-06",
                "receipt_emitter": "codex-bridge",
                "capability_profile": {
                    "code-generation": {
                        "rating": "STRONG",
                        "note": "structured-output fidelity, multi-file refactor",
                    },
                },
                "prompting_protocol": [
                    "Run read-only when generating against the repo.",
                    "Return a unified diff plus assumptions.",
                ],
                "sources": [
                    {
                        "claim": "top composite reasoning",
                        "url": "https://example.invalid/codex",
                        "date": "2026-06-27",
                        "tag": "OFFICIAL",
                        "corroboration": "STRONG",
                    }
                ],
            }
        ],
        "roles": {},
    }


def _load_memoization_registry(tmp_path: Path) -> Any:
    import yaml

    path = tmp_path / "engine-registry.yaml"
    path.write_text(yaml.safe_dump(_memoization_registry_dict(), sort_keys=False), encoding="utf-8")
    return REG.Registry.load(path)


def test_resolve_memoization_ten_resolves_probe_once_with_memo(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """AC5/R5: 10 resolves of the same engine within one RunMemo invoke the
    availability probe exactly once (call-counting `-k resolve_memoization`)."""
    registry = _load_memoization_registry(tmp_path)
    probe_calls: list[str] = []

    def counting_cli_preflight(
        engine_id: str,
        *,
        which: Any,
        config_exists: Any,
        **_kwargs: Any,
    ) -> dict[str, bool | str]:
        probe_calls.append(engine_id)
        return {"available": True, "reason": f"{engine_id} available"}

    monkeypatch.setattr(R, "_cli_preflight", counting_cli_preflight)

    memo = R.RunMemo()
    for _ in range(10):
        resolution = R.resolve(
            {"engine": "codex", "role_kind": "worker"},
            mode="dispatch",
            registry=registry,
            memo=memo,
        )
        assert resolution.halt is None
        assert resolution.engine_id == "codex"

    assert probe_calls == ["codex"]


def test_resolve_memoization_ten_resolves_without_memo_probes_every_time(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """R11: memo is opt-in -- omitting it keeps today's per-resolve probing."""
    registry = _load_memoization_registry(tmp_path)
    probe_calls: list[str] = []

    def counting_cli_preflight(
        engine_id: str,
        *,
        which: Any,
        config_exists: Any,
        **_kwargs: Any,
    ) -> dict[str, bool | str]:
        probe_calls.append(engine_id)
        return {"available": True, "reason": f"{engine_id} available"}

    monkeypatch.setattr(R, "_cli_preflight", counting_cli_preflight)

    for _ in range(10):
        R.resolve(
            {"engine": "codex", "role_kind": "worker"},
            mode="dispatch",
            registry=registry,
            memo=None,
        )

    assert len(probe_calls) == 10


def test_resolve_memoization_does_not_change_capability_reroute(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """R5/KTD5: memoized resolution matches the unmemoized resolution byte-for-byte;
    an argument-differing call does not reroute or change the probe count."""
    registry = _load_memoization_registry(tmp_path)
    monkeypatch.setattr(
        R,
        "_cli_preflight",
        lambda engine_id, **_kwargs: {"available": True, "reason": f"{engine_id} available"},
    )

    memo = R.RunMemo()
    request = {
        "capability": "code-generation",
        "role_kind": "generator",
        "task_context": {"context": "Implement the bounded change."},
    }
    baseline = R.resolve(request, mode="dispatch", registry=registry)

    for context in (
        "Implement the bounded change.",
        "A different caller context string.",
        "Yet another context body entirely.",
    ):
        memoized = R.resolve(
            {**request, "task_context": {"context": context}},
            mode="dispatch",
            registry=registry,
            memo=memo,
        )
        assert memoized.engine_id == baseline.engine_id
        assert memoized.variant == baseline.variant
        assert memoized.halt is None


# --- U6: receipt-gated disposition + never-gatekeeper guard --------------------------------


def test_fabricated_evidence_no_receipt_is_unproven(tmp_path: Path) -> None:
    """R8/KTD8: an ``ok`` runner result with no receipt is `UNPROVEN`, never a silently
    fabricated `RAN_AS_REQUESTED` -- and not the lie of `FELL_BACK_TO_CLAUDE` either."""
    store = _store(tmp_path)

    def no_receipt_runner(_invocation: dict[str, Any]) -> dict[str, str]:
        return {"status": "ok", "output": "external finding"}

    evidence = D.dispatch(_resolution(), runner=no_receipt_runner)
    assert evidence.runner_receipt is None

    manifest = D.record_dispatch_manifest(
        store,
        evidence,
        execution_id="exec-unproven",
        saga_ref="saga-1",
        created_at="2026-07-01T00:00:00Z",
    )

    assert manifest.disposition is PM.Disposition.UNPROVEN
    assert "no receipt present" in manifest.disposition_note

    persisted = MS.read_manifest(store, "exec-unproven")
    assert persisted is not None
    assert persisted["disposition"] == "unproven"


def test_fabricated_evidence_invalid_receipt_is_unproven(tmp_path: Path) -> None:
    """An `ok` runner result with a malformed/incomplete receipt is also `UNPROVEN`, never
    `RAN_AS_REQUESTED` -- the schema, not mere presence of a `receipt` key, gates."""
    store = _store(tmp_path)

    def bad_receipt_runner(_invocation: dict[str, Any]) -> dict[str, Any]:
        return {"status": "ok", "output": "external finding", "receipt": {"schema": "not-v1"}}

    evidence = D.dispatch(_resolution(), runner=bad_receipt_runner)
    manifest = D.record_dispatch_manifest(
        store,
        evidence,
        execution_id="exec-unproven-2",
        saga_ref="saga-1",
        created_at="2026-07-01T00:00:00Z",
    )

    assert manifest.disposition is PM.Disposition.UNPROVEN
    assert manifest.disposition_note


def test_valid_receipt_yields_ran_as_requested(tmp_path: Path) -> None:
    """The positive case: a schema-valid receipt on the evidence is required for, and
    produces, `RAN_AS_REQUESTED`."""
    store = _store(tmp_path)
    evidence = D.dispatch(_resolution(), runner=_ok_runner)
    assert evidence.runner_receipt is not None
    assert D._bridge_receipt.validate_receipt(evidence.runner_receipt) == []

    manifest = D.record_dispatch_manifest(
        store,
        evidence,
        execution_id="exec-proven",
        saga_ref="saga-1",
        created_at="2026-07-01T00:00:00Z",
    )
    assert manifest.disposition is PM.Disposition.RAN_AS_REQUESTED
    assert manifest.disposition_note == ""


def test_halted_dispatch_stays_fell_back_to_claude_regardless_of_receipt(tmp_path: Path) -> None:
    """Halted evidence keeps today's `FELL_BACK_TO_CLAUDE` -- receipt gating only changes the
    `ok` path (U6 scope: halted/failed dispatches are untouched)."""
    store = _store(tmp_path)

    def failing_runner(_invocation: dict[str, Any]) -> dict[str, str]:
        return {"status": "error", "output": "boom"}

    evidence = D.dispatch(_resolution(), runner=failing_runner)
    manifest = D.record_dispatch_manifest(
        store,
        evidence,
        execution_id="exec-halt-receipt",
        saga_ref="saga-1",
        created_at="2026-07-01T00:00:00Z",
    )
    assert manifest.disposition is PM.Disposition.FELL_BACK_TO_CLAUDE


def test_manifest_round_trips_unproven_disposition(tmp_path: Path) -> None:
    store = _store(tmp_path)

    def no_receipt_runner(_invocation: dict[str, Any]) -> dict[str, str]:
        return {"status": "ok", "output": "external finding"}

    evidence = D.dispatch(_resolution(), runner=no_receipt_runner)
    D.record_dispatch_manifest(
        store,
        evidence,
        execution_id="exec-unproven-roundtrip",
        saga_ref="saga-1",
        created_at="2026-07-01T00:00:00Z",
    )
    persisted = MS.read_manifest(store, "exec-unproven-roundtrip")
    assert persisted is not None
    round_tripped = PM.Manifest.from_dict(persisted)
    assert round_tripped.disposition is PM.Disposition.UNPROVEN


def _evidence(
    *,
    engine_id: str = "codex",
    variant: str = "gpt-5.5-xhigh",
    provenance: dict[str, Any] | None = None,
    halt: str | None = None,
    runner_receipt: dict[str, Any] | None = None,
) -> Any:
    prov: dict[str, Any] = {"status": "ok"} if provenance is None else provenance
    return D.AdvisoryEvidence(
        engine_id=engine_id,
        variant=variant,
        evidence="external finding",
        provenance=prov,
        halt=halt,
        runner_receipt=runner_receipt,
    )


def test_rejected_offload_manifest_and_reconciliation_preserve_exact_note() -> None:
    note = "Patch omitted the required failure-path test."
    evidence = D.reject_offload(D.dispatch(_resolution(), runner=_ok_runner), note)
    manifest = D.build_dispatch_manifest(
        evidence,
        execution_id="exec-rejected",
        saga_ref="saga-1",
        created_at="2026-07-09T00:00:00Z",
    )

    assert manifest.disposition is PM.Disposition.REJECTED_OFFLOAD
    assert manifest.disposition_note == note
    assert PM.Manifest.from_dict(manifest.to_dict()) == manifest

    result = D.rejected_offload_reconciliation(
        manifest,
        reconciliation_id="recon-rejected",
        adjudicator_id="claude/opus",
    )
    visible = RC.reviewer_validator_evidence(result)
    assert visible["result"]["items"][0]["rationale"] == note


@pytest.mark.parametrize("note", ["", " ", "\n\t"])
def test_reject_offload_requires_non_empty_note(note: str) -> None:
    with pytest.raises(D.DispatchError, match="non-empty rejection note"):
        D.reject_offload(D.dispatch(_resolution(), runner=_ok_runner), note)


@pytest.mark.parametrize(
    ("evidence", "expected"),
    [
        (
            _evidence(
                provenance={
                    "status": "halted",
                    "rejected_offload_note": "rejected",
                    "note": "fallback",
                },
                halt="fallback",
            ),
            PM.Disposition.FELL_BACK_TO_CLAUDE,
        ),
        (
            _evidence(
                provenance={
                    "status": "ok",
                    "expected_identity": "agy/gemini",
                    "rejected_offload_note": "rejected",
                },
                runner_receipt=_valid_receipt(),
            ),
            PM.Disposition.SUBSTITUTED_ENGINE,
        ),
        (
            _evidence(
                provenance={
                    "status": "ok",
                    "integrity": PM.Disposition.DELEGATION_INTEGRITY.value,
                    "rejected_offload_note": "rejected",
                },
                runner_receipt=_valid_receipt(),
            ),
            PM.Disposition.DELEGATION_INTEGRITY,
        ),
        (
            _evidence(
                provenance={"status": "ok", "rejected_offload_note": "rejected"},
                runner_receipt={**_valid_receipt(), "external_tokens": 0},
            ),
            PM.Disposition.PROOF_INTEGRITY,
        ),
        (
            _evidence(
                provenance={"status": "ok", "rejected_offload_note": "rejected"},
            ),
            PM.Disposition.UNPROVEN,
        ),
        (
            _evidence(
                provenance={"status": "ok", "rejected_offload_note": "rejected"},
                runner_receipt=_valid_receipt(),
            ),
            PM.Disposition.REJECTED_OFFLOAD,
        ),
        (
            _evidence(provenance={"status": "ok"}, runner_receipt=_valid_receipt()),
            PM.Disposition.RAN_AS_REQUESTED,
        ),
    ],
)
def test_rejected_offload_extends_existing_manifest_precedence(
    evidence: Any, expected: Any
) -> None:
    manifest = D.build_dispatch_manifest(
        evidence,
        execution_id="exec-precedence",
        saga_ref="saga-1",
        created_at="2026-07-09T00:00:00Z",
    )
    assert manifest.disposition is expected


def test_rejected_offload_advisory_evidence_cannot_satisfy_gate() -> None:
    evidence = D.reject_offload(
        D.dispatch(_resolution(), runner=_ok_runner, execution_id="exec-rejected-gate"),
        "Rejected after review.",
    )
    verified = dataclasses.replace(
        evidence,
        verified_by_claude=True,
        provenance={**evidence.provenance, "observer_corroborated": True},
    )
    manifest = D.build_dispatch_manifest(
        verified,
        execution_id="exec-rejected-gate",
        saga_ref="saga-1",
        created_at="2026-07-09T00:00:00Z",
    )
    result = D.rejected_offload_reconciliation(
        manifest,
        reconciliation_id="recon-rejected-gate",
        adjudicator_id="claude",
        evidence=verified,
    )

    with pytest.raises(D.DispatchError, match="can never satisfy a gate"):
        D.satisfy_gate(verified, manifest, reconciliation=result)
    with pytest.raises(D.DispatchError, match="can never satisfy a gate"):
        D.satisfy_gate(verified, reconciliation=result)


@pytest.mark.parametrize("gatekeeper_key", ["verdict", "gate_status", "adjudicated"])
def test_never_gatekeeper_guard_rejects_gate_fields(gatekeeper_key: str) -> None:
    """R6/#283 `{#external-engines-never-gatekeepers}`: a runner result carrying any
    gate/verdict-shaped key is structurally rejected -- not merely ignored, not policy-gated
    downstream. This must be impossible to smuggle past `dispatch()`."""

    def gatekeeping_runner(_invocation: dict[str, Any]) -> dict[str, Any]:
        return {"status": "ok", "output": "external finding", gatekeeper_key: "approved"}

    with pytest.raises(D.DispatchError, match="never gatekeepers"):
        D.dispatch(_resolution(), runner=gatekeeping_runner)


def test_never_gatekeeper_guard_allows_clean_result() -> None:
    """Sanity companion to the guard test: a result with none of the gatekeeper keys dispatches
    normally (the guard doesn't over-fire on ordinary evidence)."""
    evidence = D.dispatch(_resolution(), runner=_ok_runner)
    assert evidence.halt is None
    assert evidence.evidence == "external finding"


# --- U2: SUBSTITUTED_ENGINE auto-derivation + gate refusal + note invariant (R2/R3/R4) -----
# selectors: substituted_disposition, fallback_reason


def test_substituted_disposition_when_expected_differs_from_resolved() -> None:
    """Expected 'agy/gemini-3.1-pro-high' but codex/gpt-5.5-xhigh ran -> SUBSTITUTED_ENGINE with
    BOTH identities named in the note (KTD4, R2)."""
    evidence = _evidence(
        provenance={"status": "ok", "expected_identity": "agy/gemini-3.1-pro-high"},
    )
    manifest = D.build_dispatch_manifest(
        evidence, execution_id="e-sub", saga_ref="s1", created_at="2026-07-02"
    )
    assert manifest.disposition is PM.Disposition.SUBSTITUTED_ENGINE
    assert "agy/gemini-3.1-pro-high" in manifest.disposition_note
    assert "codex/gpt-5.5-xhigh" in manifest.disposition_note


def test_substituted_disposition_absent_when_expected_matches_resolved() -> None:
    """expected == resolved -> unchanged path (RAN_AS_REQUESTED with a valid receipt)."""
    receipt = _valid_receipt()
    evidence = _evidence(
        provenance={"status": "ok", "expected_identity": "codex/gpt-5.5-xhigh"},
        runner_receipt=receipt,
    )
    manifest = D.build_dispatch_manifest(
        evidence, execution_id="e-match", saga_ref="s1", created_at="2026-07-02"
    )
    assert manifest.disposition is PM.Disposition.RAN_AS_REQUESTED
    assert manifest.disposition_note == ""


def test_substituted_disposition_none_expected_is_byte_identical() -> None:
    """expected_identity absent -> unchanged derivation (valid receipt -> RAN_AS_REQUESTED,
    empty note); the omitted-vs-explicit-None equivalence is pinned at the dispatch level by
    test_dispatch_expected_identity_none_leaves_provenance_clean."""
    evidence = _evidence(provenance={"status": "ok"}, runner_receipt=_valid_receipt())
    manifest = D.build_dispatch_manifest(
        evidence, execution_id="e-none", saga_ref="s1", created_at="2026-07-02"
    )
    assert manifest.disposition is PM.Disposition.RAN_AS_REQUESTED
    assert manifest.disposition_note == ""


def test_substituted_disposition_halt_and_mismatch_halt_branch_wins() -> None:
    """halt + identity mismatch -> FELL_BACK_TO_CLAUDE wins (KTD4 precedence: halt outranks
    substitution)."""
    evidence = _evidence(
        provenance={"status": "halted", "expected_identity": "agy/gemini", "note": "boom"},
        halt="boom",
    )
    manifest = D.build_dispatch_manifest(
        evidence, execution_id="e-halt", saga_ref="s1", created_at="2026-07-02"
    )
    assert manifest.disposition is PM.Disposition.FELL_BACK_TO_CLAUDE


def test_substituted_disposition_outranks_valid_receipt() -> None:
    """A schema-valid receipt for the WRONG engine must never yield RAN_AS_REQUESTED -- an
    affirmative substitution contradiction outranks mere proof-presence (KTD4)."""
    evidence = _evidence(
        provenance={"status": "ok", "expected_identity": "agy/gemini-3.1-pro-high"},
        runner_receipt=_valid_receipt(),
    )
    manifest = D.build_dispatch_manifest(
        evidence, execution_id="e-sub-receipt", saga_ref="s1", created_at="2026-07-02"
    )
    assert manifest.disposition is PM.Disposition.SUBSTITUTED_ENGINE
    assert manifest.disposition is not PM.Disposition.RAN_AS_REQUESTED


def test_satisfy_gate_refuses_substituted_manifest() -> None:
    """Substituted evidence can never satisfy a gate as-approved (KTD5, R4)."""
    evidence = D.AdvisoryEvidence(
        engine_id="codex",
        variant="gpt-5.5-xhigh",
        evidence="Claude verified external finding",
        provenance={"status": "ok", "observer_corroborated": True},
        execution_id="e-gate",
        verified_by_claude=True,
    )
    substituted = D.build_dispatch_manifest(
        _evidence(provenance={"status": "ok", "expected_identity": "agy/gemini"}),
        execution_id="e-gate",
        saga_ref="s1",
        created_at="2026-07-02",
    )
    assert substituted.disposition is PM.Disposition.SUBSTITUTED_ENGINE
    with pytest.raises(D.DispatchError, match="substitut"):
        D.satisfy_gate(evidence, substituted, reconciliation=_ready_reconciliation(evidence))


def test_fallback_reason_invariant_fills_empty_note_for_non_ran() -> None:
    """R3: every non-RAN_AS_REQUESTED manifest carries a non-empty disposition_note; a degenerate
    empty halt/reason gets a fixed fallback string rather than an empty note."""
    evidence = _evidence(provenance={"status": "halted", "note": "   "}, halt="")
    manifest = D.build_dispatch_manifest(
        evidence, execution_id="e-empty", saga_ref="s1", created_at="2026-07-02"
    )
    assert manifest.disposition is PM.Disposition.FELL_BACK_TO_CLAUDE
    assert manifest.disposition_note.strip() != ""


def test_dispatch_stamps_expected_identity_into_provenance() -> None:
    """dispatch(expected_identity=...) threads the plan-time preview baseline into evidence
    provenance so the builder can derive substitution (KTD3) — chained through to the gate:
    the full real path dispatch -> build_dispatch_manifest -> satisfy_gate refuses the
    substituted run even when the evidence itself is verified and corroborated (#390 review)."""
    evidence = D.dispatch(
        _resolution(),
        runner=_ok_runner,
        expected_identity="agy/gemini-3.1-pro-high",
        execution_id="e-thread",
    )
    assert evidence.provenance["expected_identity"] == "agy/gemini-3.1-pro-high"
    manifest = D.build_dispatch_manifest(
        evidence, execution_id="e-thread", saga_ref="s1", created_at="2026-07-02"
    )
    assert manifest.disposition is PM.Disposition.SUBSTITUTED_ENGINE

    verified = dataclasses.replace(evidence, verified_by_claude=True)
    verified.provenance["observer_corroborated"] = True
    with pytest.raises(D.DispatchError, match="substituted"):
        D.satisfy_gate(verified, manifest, reconciliation=_ready_reconciliation(verified))


def test_dispatch_expected_identity_none_leaves_provenance_clean() -> None:
    """expected_identity=None (explicit or omitted) -> no expected_identity key stamped and
    identical provenance either way — the additive-default preserves today's behavior."""
    evidence = D.dispatch(_resolution(), runner=_ok_runner)
    assert "expected_identity" not in evidence.provenance
    assert "chaperone" not in evidence.provenance
    explicit_none = D.dispatch(_resolution(), runner=_ok_runner, expected_identity=None)
    assert explicit_none.provenance == evidence.provenance


def test_dispatch_stamps_chaperone_provenance_when_supplied() -> None:
    chaperone = {
        "batch_id": "batch-1",
        "review_mode": "ratify-only",
        "sampled_unit_ids": ["U1"],
        "cache_status": "hit",
    }

    evidence = D.dispatch(_resolution(), runner=_ok_runner, chaperone=chaperone)

    assert evidence.provenance["chaperone"] == chaperone
    assert evidence.provenance["chaperone"] is not chaperone


def test_dispatch_halted_resolution_stamps_chaperone_provenance() -> None:
    evidence = D.dispatch(
        _resolution(halt="preflight halted"),
        runner=_ok_runner,
        chaperone={"batch_id": "batch-1", "review_mode": "full-review"},
    )

    assert evidence.halt == "preflight halted"
    assert evidence.provenance["chaperone"] == {
        "batch_id": "batch-1",
        "review_mode": "full-review",
    }


def test_dispatch_copies_resolution_warnings_without_satisfying_gate() -> None:
    resolution = dataclasses.replace(_resolution(), warnings=("stale registry row",))

    evidence = D.dispatch(resolution, runner=_ok_runner, execution_id="warning-execution")

    assert evidence.provenance["warnings"] == ["stale registry row"]
    with pytest.raises(D.DispatchError, match="verified"):
        D.satisfy_gate(evidence, reconciliation=_ready_reconciliation(evidence))


def _panel_resolutions() -> list[Any]:
    return [
        _resolution(variant="panel-one"),
        _resolution(variant="panel-two"),
        _resolution(variant="panel-three"),
    ]


def test_advisory_panel_reconciles_deduplicated_and_empty_output_before_append(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    resolutions = _panel_resolutions()
    monkeypatch.setattr(D.engine_resolver, "resolve_role", lambda *_args, **_kwargs: resolutions)
    outputs = iter(("same advisory finding", "same advisory finding", ""))
    ledger = RC.run_ledger.RunLedger(tmp_path / "panel-facts.jsonl")

    def foreman(evidence: tuple[Any, ...]) -> Any:
        assert len(evidence) == 2
        assert evidence[0].member_ids == ("codex/panel-one", "codex/panel-two")
        assert evidence[1].empty is True
        return RC.build_result(
            reconciliation_id="panel-reconciliation",
            execution_id="panel-execution",
            intent="second-opinion",
            adjudicator_id="claude/foreman",
            source_finding_ids=tuple(item.source_finding_id for item in evidence),
            items=tuple(
                RC.ReconciliationItem(
                    source_finding_id=item.source_finding_id,
                    status=RC.ReconciliationStatus.RECONCILED,
                    adjudicator_id="claude/foreman",
                    rationale=(
                        "Claude explicitly accounted for the empty member response."
                        if item.empty
                        else "Claude verified the duplicate advisory finding once."
                    ),
                )
                for item in evidence
            ),
        )

    result = D.dispatch_advisory_panel(
        D.AdvisoryPanelRequest("cross-family-review-panel"),
        registry=object(),
        runner=lambda _invocation: {"status": "ok", "output": next(outputs)},
        foreman=foreman,
        execution_id="panel-execution",
        intent="second-opinion",
        ledger=ledger,
        subplot_id="issue-393",
        at="2026-07-09T00:00:00Z",
    )

    facts = RC.read_reconciliation_facts(ledger)
    assert [fact["action"] for fact in facts] == ["reconcile", "apply"]
    assert all(evidence.role_kind == "panel" for evidence in result.member_evidence)
    assert result.advisory is True
    assert "same advisory finding" not in ledger.path.read_text(encoding="utf-8")

    verified = dataclasses.replace(
        result.member_evidence[0],
        verified_by_claude=True,
        provenance={**result.member_evidence[0].provenance, "observer_corroborated": True},
    )
    with pytest.raises(D.DispatchError, match="advisory-only"):
        D.satisfy_gate(verified, reconciliation=_ready_reconciliation(verified))


def test_advisory_panel_unavailable_member_blocks_all_dispatch_and_append(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    resolutions = [_resolution(), _resolution(variant="unavailable", halt="not configured")]
    monkeypatch.setattr(D.engine_resolver, "resolve_role", lambda *_args, **_kwargs: resolutions)
    calls = 0

    def runner(_invocation: dict[str, Any]) -> dict[str, str]:
        nonlocal calls
        calls += 1
        return {"status": "ok", "output": "must not run"}

    ledger = RC.run_ledger.RunLedger(tmp_path / "panel-facts.jsonl")
    with pytest.raises(D.DispatchError, match="before dispatch"):
        D.dispatch_advisory_panel(
            D.AdvisoryPanelRequest("cross-family-review-panel"),
            registry=object(),
            runner=runner,
            foreman=lambda _evidence: None,
            execution_id="panel-execution",
            intent="second-opinion",
            ledger=ledger,
            subplot_id="issue-393",
            at="2026-07-09T00:00:00Z",
        )
    assert calls == 0
    assert RC.run_ledger.read_facts(ledger) == []


def test_failed_panel_foreman_writes_no_apply_fact(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        D.engine_resolver,
        "resolve_role",
        lambda *_args, **_kwargs: [_resolution(variant="panel-one")],
    )
    ledger = RC.run_ledger.RunLedger(tmp_path / "panel-facts.jsonl")

    def failed_foreman(evidence: tuple[Any, ...]) -> Any:
        return RC.build_result(
            reconciliation_id="panel-reconciliation",
            execution_id="panel-execution",
            intent="second-opinion",
            adjudicator_id="claude/foreman",
            source_finding_ids=tuple(item.source_finding_id for item in evidence),
            items=(),
        )

    with pytest.raises(D.DispatchError, match="foreman reconciliation failed"):
        D.dispatch_advisory_panel(
            D.AdvisoryPanelRequest("cross-family-review-panel"),
            registry=object(),
            runner=lambda _invocation: {"status": "ok", "output": "finding"},
            foreman=failed_foreman,
            execution_id="panel-execution",
            intent="second-opinion",
            ledger=ledger,
            subplot_id="issue-393",
            at="2026-07-09T00:00:00Z",
        )

    assert [fact["action"] for fact in RC.read_reconciliation_facts(ledger)] == []
