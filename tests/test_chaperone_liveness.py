"""Producer/consumer bridge-run liveness checks (#388)."""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path
from types import ModuleType
from typing import Any

ROOT = Path(__file__).parent.parent
SCRIPTS = ROOT / "plugins" / "saga" / "scripts"


def _load(name: str) -> ModuleType:
    if str(SCRIPTS) not in sys.path:
        sys.path.insert(0, str(SCRIPTS))
    spec = importlib.util.spec_from_file_location(f"{name}_liveness", SCRIPTS / f"{name}.py")
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


BS = _load("bridge_signatures")
D = _load("engine_dispatch")
PM = D.pm
RL = D.run_ledger
MS = D.manifest_store


def _write_engine_fact(ledger: Any, key: str) -> None:
    RL.append_fact(
        ledger,
        RL.build_fact(
            "engine",
            subplot_id="sub-388",
            at="2026-07-09T00:00:00Z",
            bridge_run_key=key,
        ),
    )


def _write_manifest(store: Any, key: str, execution_id: str = "exec-1") -> None:
    MS.write_manifest(
        store,
        execution_id,
        PM.Manifest(
            execution_id=execution_id,
            saga_ref="saga-388",
            attribution=PM.Attribution(
                kind=PM.ProducerKind.EXTERNAL_ENGINE,
                identity="codex/gpt-5.5-xhigh",
            ),
            disposition=PM.Disposition.RAN_AS_REQUESTED,
            created_at="2026-07-09T00:00:00Z",
            bridge_run_key=key,
        ).to_dict(),
    )


def test_matching_launch_and_consumer_keys_pass() -> None:
    assert BS.liveness_errors({"run-1"}, {"run-1"}) == []


def test_launched_unconsumed_fails() -> None:
    assert BS.liveness_errors({"run-1"}, set()) == ["proof-integrity: launched-unconsumed run-1"]


def test_consumed_unlaunched_fails() -> None:
    assert BS.liveness_errors(set(), {"run-1"}) == ["proof-integrity: consumed-unlaunched run-1"]


def test_real_ledger_manifest_liveness_join_passes(tmp_path: Path) -> None:
    ledger = RL.RunLedger(path=tmp_path / "run-facts.jsonl")
    store = MS.Store(root=tmp_path / "manifests").ensure()

    _write_engine_fact(ledger, "run-1")
    _write_manifest(store, "run-1")

    assert D.bridge_liveness_errors(ledger, store) == []


def test_real_ledger_manifest_liveness_join_names_missing_halves(tmp_path: Path) -> None:
    ledger = RL.RunLedger(path=tmp_path / "run-facts.jsonl")
    store = MS.Store(root=tmp_path / "manifests").ensure()

    _write_engine_fact(ledger, "launched-only")
    _write_manifest(store, "consumed-only")

    assert D.bridge_liveness_errors(ledger, store) == [
        "proof-integrity: launched-unconsumed launched-only",
        "proof-integrity: consumed-unlaunched consumed-only",
    ]
