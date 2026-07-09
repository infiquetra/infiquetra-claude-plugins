"""Tests for the run-fact ledger substrate (#401): schema, hash-chain custody, derive-on-read views."""

from __future__ import annotations

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


RL = _load("run_ledger")


def _ledger(tmp_path: Path) -> Any:
    return RL.RunLedger(path=tmp_path / "run-facts.jsonl")


def _spend(sub: str, *, tokens: int, cached: int, fresh: int, wall: float = 1.0) -> Any:
    return RL.build_fact(
        "spend",
        subplot_id=sub,
        at="2026-07-05T00:00:00Z",
        tokens=tokens,
        tokens_cached=cached,
        tokens_fresh=fresh,
        wall_seconds=wall,
    )


# --------------------------------------------------------------------------- U1: schema


def test_schema_covers_all_five_kinds(tmp_path: Path) -> None:
    ledger = _ledger(tmp_path)
    RL.append_fact(ledger, _spend("s1", tokens=100, cached=60, fresh=40))
    RL.append_fact(ledger, RL.build_fact("cache", subplot_id="s1", at="t", cached=3, fresh=1))
    RL.append_fact(
        ledger,
        RL.build_fact(
            "engine",
            subplot_id="s1",
            at="t",
            engine="gemini",
            cost=0.02,
            latency_seconds=1.5,
            tokens=200,
        ),
    )
    RL.append_fact(
        ledger,
        RL.build_fact(
            "delegation", subplot_id="s1", at="t", evidence="ptr://run/abc", engine="agy"
        ),
    )
    RL.append_fact(
        ledger,
        RL.build_fact(
            "reconciliation", subplot_id="s1", at="t", reconciliation_id="recon-1"
        ),
    )
    facts = RL.read_facts(ledger)
    assert [f["kind"] for f in facts] == [
        "spend",
        "cache",
        "engine",
        "delegation",
        "reconciliation",
    ]
    assert all(f["schema"] == "run_fact.v1" for f in facts)
    assert facts[2]["engine"] == "gemini" and facts[3]["evidence"] == "ptr://run/abc"


def test_build_fact_rejects_unknown_kind_and_reserved_fields() -> None:
    with pytest.raises(RL.RunLedgerError):
        RL.build_fact("bogus", subplot_id="s1", at="t")
    with pytest.raises(RL.RunLedgerError):
        RL.build_fact("spend", subplot_id="", at="t")  # leaf-produced: subplot_id required
    with pytest.raises(RL.RunLedgerError):
        RL.build_fact("spend", subplot_id="s1", at="t", this_hash="forged")  # reserved chain field


# --------------------------------------------------------------------------- U1: hash chain custody


def test_second_append_chains_onto_the_first(tmp_path: Path) -> None:
    ledger = _ledger(tmp_path)
    first = RL.append_fact(ledger, _spend("s1", tokens=10, cached=5, fresh=5))
    second = RL.append_fact(ledger, _spend("s2", tokens=20, cached=0, fresh=20))
    assert first["prev_hash"] == ""  # genesis
    assert second["prev_hash"] == first["this_hash"]  # chained
    assert RL.verify_chain(ledger).ok


def test_verify_chain_passes_on_untouched_ledger(tmp_path: Path) -> None:
    ledger = _ledger(tmp_path)
    for i in range(4):
        RL.append_fact(ledger, _spend(f"s{i}", tokens=i, cached=0, fresh=i))
    report = RL.verify_chain(ledger)
    assert report.ok and report.break_index is None


def test_in_place_mutation_makes_verify_chain_fail(tmp_path: Path) -> None:
    # Custody: a passed fact cannot be silently altered.
    ledger = _ledger(tmp_path)
    RL.append_fact(ledger, _spend("s0", tokens=10, cached=5, fresh=5))
    RL.append_fact(ledger, _spend("s1", tokens=20, cached=5, fresh=15))
    lines = ledger.path.read_text().splitlines()
    rec0 = json.loads(lines[0])
    rec0["tokens"] = 999999  # tamper with a prior record's field, leave its this_hash intact
    lines[0] = json.dumps(rec0, sort_keys=True, separators=(",", ":"))
    ledger.path.write_text("\n".join(lines) + "\n")
    report = RL.verify_chain(ledger)
    assert not report.ok and report.break_index == 0
    assert "mutated" in report.reason


def test_middle_deletion_makes_verify_chain_fail(tmp_path: Path) -> None:
    # Custody: a fail cannot be buried by deleting a record — the prev_hash link breaks.
    ledger = _ledger(tmp_path)
    for i in range(3):
        RL.append_fact(ledger, _spend(f"s{i}", tokens=i, cached=0, fresh=i))
    lines = ledger.path.read_text().splitlines()
    del lines[1]  # drop the middle record
    ledger.path.write_text("\n".join(lines) + "\n")
    report = RL.verify_chain(ledger)
    assert not report.ok and report.break_index == 1
    assert "link broken" in report.reason


def test_reorder_makes_verify_chain_fail(tmp_path: Path) -> None:
    ledger = _ledger(tmp_path)
    for i in range(3):
        RL.append_fact(ledger, _spend(f"s{i}", tokens=i, cached=0, fresh=i))
    lines = ledger.path.read_text().splitlines()
    lines[1], lines[2] = lines[2], lines[1]  # swap two records
    ledger.path.write_text("\n".join(lines) + "\n")
    assert not RL.verify_chain(ledger).ok


def test_torn_trailing_line_is_tolerated_not_a_chain_break(tmp_path: Path) -> None:
    ledger = _ledger(tmp_path)
    RL.append_fact(ledger, _spend("s0", tokens=10, cached=5, fresh=5))
    with open(ledger.path, "a", encoding="utf-8") as fh:
        fh.write('{"schema": "run_fact.v1", "kind": "spend"')  # torn, newline-less fragment
    assert len(RL.read_facts(ledger)) == 1  # torn tail dropped
    assert RL.verify_chain(ledger).ok  # not a chain break
    # And a subsequent append heals the tail and chains cleanly.
    RL.append_fact(ledger, _spend("s1", tokens=1, cached=0, fresh=1))
    assert RL.verify_chain(ledger).ok and len(RL.read_facts(ledger)) == 2


def test_empty_and_absent_ledger(tmp_path: Path) -> None:
    ledger = _ledger(tmp_path)
    assert RL.read_facts(ledger) == []
    assert RL.verify_chain(ledger).ok  # vacuously


def test_corrupt_non_trailing_line_raises_not_silently_skipped(tmp_path: Path) -> None:
    # Security-relevant: a mid-file corruption must NOT be silently dropped (that would be a way to
    # bury a fact). Only the trailing torn line is tolerated.
    ledger = _ledger(tmp_path)
    RL.append_fact(ledger, _spend("s0", tokens=1, cached=0, fresh=1))
    RL.append_fact(ledger, _spend("s1", tokens=2, cached=0, fresh=2))
    lines = ledger.path.read_text().splitlines()
    lines[0] = "{not valid json"  # corrupt a NON-trailing line
    ledger.path.write_text("\n".join(lines) + "\n")
    with pytest.raises(RL.RunLedgerError):
        RL.read_facts(ledger)


# --------------------------------------------------------------------------- U2: derive-on-read views


def test_reuse_ratio_over_spend_facts(tmp_path: Path) -> None:
    ledger = _ledger(tmp_path)
    RL.append_fact(ledger, _spend("s0", tokens=100, cached=60, fresh=40))
    RL.append_fact(ledger, _spend("s1", tokens=100, cached=40, fresh=60))
    # total cached 100, total fresh 100 -> 0.5
    assert RL.reuse_ratio(ledger) == 0.5


def test_reuse_ratio_no_data_returns_defined_empty(tmp_path: Path) -> None:
    ledger = _ledger(tmp_path)
    assert RL.reuse_ratio(ledger) is None  # defined empty, not a crash
    # cache-only facts (no spend) also yield None from the spend-based ratio.
    RL.append_fact(ledger, RL.build_fact("cache", subplot_id="s", at="t", cached=1, fresh=0))
    assert RL.reuse_ratio(ledger) is None


def test_last_n_prior_averages_last_n_only(tmp_path: Path) -> None:
    ledger = _ledger(tmp_path)
    for tok in (10, 20, 30, 40):
        RL.append_fact(
            ledger,
            RL.build_fact(
                "engine",
                subplot_id="s",
                at="t",
                engine="x",
                cost=0.0,
                latency_seconds=0.0,
                tokens=tok,
            ),
        )
    assert RL.last_n_prior(ledger, "engine", "tokens", 2) == 35.0  # (30+40)/2
    assert RL.last_n_prior(ledger, "engine", "tokens", 10) == 25.0  # all four (10+20+30+40)/4


def test_last_n_prior_no_data_returns_none(tmp_path: Path) -> None:
    ledger = _ledger(tmp_path)
    assert RL.last_n_prior(ledger, "engine", "tokens", 3) is None
    RL.append_fact(ledger, _spend("s0", tokens=10, cached=5, fresh=5))
    assert RL.last_n_prior(ledger, "engine", "tokens", 3) is None  # no engine facts
    assert RL.last_n_prior(ledger, "spend", "tokens", 0) is None  # empty window


def test_rollup_aggregates_numeric_fields_no_committed_summary(tmp_path: Path) -> None:
    ledger = _ledger(tmp_path)
    RL.append_fact(ledger, _spend("s0", tokens=10, cached=6, fresh=4, wall=2.0))
    RL.append_fact(ledger, _spend("s1", tokens=30, cached=0, fresh=30, wall=4.0))
    roll = RL.rollup(ledger, "spend")
    assert roll["tokens"] == {"sum": 40.0, "avg": 20.0, "count": 2.0}
    assert roll["wall_seconds"]["sum"] == 6.0
    # derive-on-read: nothing is persisted as a summary — the ledger file holds only the 2 facts.
    assert len(ledger.path.read_text().splitlines()) == 2


def test_rollup_includes_engine_net_savings_fields(tmp_path: Path) -> None:
    ledger = _ledger(tmp_path)
    RL.append_fact(
        ledger,
        RL.build_fact(
            "engine",
            subplot_id="s1",
            at="2026-07-09T00:00:00Z",
            engine="codex",
            cost=0.004,
            engine_tokens_avoided=1000,
            chaperone_tokens_spent=200,
            net_savings_tokens=800,
            net_savings_status="positive",
            external_cost_usd=0.004,
        ),
    )

    roll = RL.rollup(ledger, "engine")

    assert roll["engine_tokens_avoided"]["sum"] == 1000.0
    assert roll["chaperone_tokens_spent"]["sum"] == 200.0
    assert roll["net_savings_tokens"]["sum"] == 800.0
    assert roll["external_cost_usd"]["sum"] == 0.004
    assert "net_savings_status" not in roll
