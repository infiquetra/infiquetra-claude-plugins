"""Tests for the closure-gate wiring into `outcome_orchestrator.harvest()`/`barrier_report()` (#397).

Pins R7 (harvest never writes a `done` completion event until the closure gate is satisfied) and
KTD6 (`harvest()`/`barrier_report()` gain a defaulted `repo_root: Path = Path(".")` so every
pre-existing caller — none of which declares a node's `evidence.required_checks` — is unaffected).
"""

from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path
from types import ModuleType, SimpleNamespace
from typing import Any

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


SPEC = _load("outcome_spec")
STORE = _load("outcome_store")
LEDGER = _load("evidence_ledger")
ORCH = _load("outcome_orchestrator")

SHA = "a" * 40


def _store(tmp_path: Path):
    return STORE.Store(root=tmp_path / "store").ensure()


def _gh(pr_state: dict[str, str] | None = None, head_ref_oid: dict[str, str] | None = None):
    """A fake `gh` runner answering both `pr_state()` and `head_ref_oid()` for the same ref."""
    pr_state = pr_state or {}
    head_ref_oid = head_ref_oid or {}

    def runner(args: list[str], **_kw: Any) -> SimpleNamespace:
        ref = args[3]
        st = pr_state.get(ref, "OPEN")
        body = {
            "state": st,
            "mergedAt": "2026-07-12T00:00:00Z" if st == "MERGED" else None,
            "headRefOid": head_ref_oid.get(ref, ""),
        }
        return SimpleNamespace(returncode=0, stdout=json.dumps(body), stderr="")

    return runner


def _node(sid: str, **kw: Any) -> Any:
    data = {"subplot_id": sid, "title": sid, **kw}
    return SPEC.Node.from_dict(data)


def test_outcome_orchestrator_gate_blocks_harvest(tmp_path: Path) -> None:
    """PR merged (barrier satisfied) but the required check has no evidence -> not harvested."""
    node = _node(
        "sub397",
        kind="code",
        github={"pr": "42"},
        leaf_saga_id="leaf-outcome-sub397",
        evidence={"required_checks": ["qa"]},
    )
    spec = SPEC.OutcomeSpec(outcome_id="oc", objective="test", nodes=[node])
    store = _store(tmp_path)
    runner = _gh(pr_state={"42": "MERGED"}, head_ref_oid={"42": SHA})

    harvested = ORCH.harvest(spec, store=store, github_runner=runner, repo_root=tmp_path)

    assert harvested == []
    assert STORE.completed_subplots(store) == set()


def test_outcome_orchestrator_gate_allows_harvest_when_satisfied(tmp_path: Path) -> None:
    """Same setup, but the required check's evidence is a matching-SHA PASS -> harvested."""
    node = _node(
        "sub397",
        kind="code",
        github={"pr": "42"},
        leaf_saga_id="leaf-outcome-sub397",
        evidence={"required_checks": ["qa"]},
    )
    spec = SPEC.OutcomeSpec(outcome_id="oc", objective="test", nodes=[node])
    store = _store(tmp_path)
    runner = _gh(pr_state={"42": "MERGED"}, head_ref_oid={"42": SHA})
    ledger_store = LEDGER.Store.for_saga("leaf-outcome-sub397", tmp_path)
    LEDGER.write(
        ledger_store,
        check_id="qa",
        reviewed_sha=SHA,
        producer="qa-gate",
        verdict="PASS",
        content="ok",
    )

    harvested = ORCH.harvest(spec, store=store, github_runner=runner, repo_root=tmp_path)

    assert harvested == ["sub397"]
    assert STORE.completed_subplots(store) == {"sub397"}


def test_outcome_orchestrator_harvest_backward_compatible_default_repo_root(tmp_path: Path) -> None:
    """A node with no `required_checks` declared, `harvest()` called with no explicit repo_root."""
    node = _node("design", kind="code", github={"pr": "9"})
    spec = SPEC.OutcomeSpec(outcome_id="oc", objective="test", nodes=[node])
    store = _store(tmp_path)
    runner = _gh(pr_state={"9": "MERGED"})

    harvested = ORCH.harvest(spec, store=store, github_runner=runner)

    assert harvested == ["design"]
    assert STORE.completed_subplots(store) == {"design"}


def test_outcome_orchestrator_barrier_report_surfaces_closure_gate_halt(tmp_path: Path) -> None:
    """`barrier_report()`'s per-node dict names the closure-gate HALT reason."""
    node = _node(
        "sub397",
        kind="code",
        github={"pr": "42"},
        leaf_saga_id="leaf-outcome-sub397",
        evidence={"required_checks": ["qa"]},
    )
    spec = SPEC.OutcomeSpec(outcome_id="oc", objective="test", nodes=[node])
    store = _store(tmp_path)
    runner = _gh(pr_state={"42": "MERGED"}, head_ref_oid={"42": SHA})

    report = ORCH.barrier_report(spec, store=store, github_runner=runner, repo_root=tmp_path)

    assert report["sub397"]["satisfied"] is True  # the GitHub-only barrier IS satisfied
    assert report["sub397"]["closure_gate"]["satisfied"] is False
    assert report["sub397"]["closure_gate"]["halt_reason"] == "missing-evidence:qa"
