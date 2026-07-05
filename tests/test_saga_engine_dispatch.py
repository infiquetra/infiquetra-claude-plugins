"""Oracle tests for the Saga external-engine dispatch adapter (U4)."""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path
from types import ModuleType
from typing import Any

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
        "via": "codex:codex-rescue",
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
    )

    with pytest.raises(D.DispatchError):
        D.satisfy_gate(unverified)

    verified = D.AdvisoryEvidence(
        engine_id="codex",
        variant="gpt-5.5-xhigh",
        evidence="Claude verified external finding",
        provenance={"engine": "codex", "variant": "gpt-5.5-xhigh", "status": "ok"},
        verified_by_claude=True,
    )

    assert D.satisfy_gate(verified) is None


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


def _ok_runner(_invocation: dict[str, Any]) -> dict[str, str]:
    return {"status": "ok", "output": "external finding"}


def _store(tmp_path: Path) -> Any:
    return MS.Store(root=tmp_path / "saga-manifests" / "saga-1").ensure()


def test_dispatch_emits_manifest_with_attribution(tmp_path: Path) -> None:
    store = _store(tmp_path)
    evidence = D.dispatch(_resolution(), runner=_ok_runner)

    manifest = D.record_dispatch_manifest(
        store,
        evidence,
        execution_id="exec-1",
        saga_ref="saga-1",
        created_at="2026-07-01T00:00:00Z",
        effort="high",
        protocol="codex:codex-rescue",
    )

    assert manifest.attribution.kind is PM.ProducerKind.EXTERNAL_ENGINE
    assert manifest.attribution.identity == "codex/gpt-5.5-xhigh"
    assert manifest.attribution.effort == "high"
    assert manifest.attribution.protocol == "codex:codex-rescue"
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
    evidence = D.dispatch(_resolution(), runner=_ok_runner)
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
        provenance=evidence.provenance,
        verified_by_claude=True,
    )

    # Claimed-`verified` without adjudication cannot satisfy a gate (R11/AE1).
    with pytest.raises(D.DispatchError):
        D.satisfy_gate(verified, manifest)

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
    assert D.satisfy_gate(verified, adjudicated) is None

    # verified_by_claude is still required even with a fully adjudicated manifest.
    with pytest.raises(D.DispatchError):
        D.satisfy_gate(evidence, adjudicated)


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
