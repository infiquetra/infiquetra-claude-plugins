"""Tests for exact-variant engine promotion assessment (#455)."""

from __future__ import annotations

import importlib.util
import json
import subprocess
import sys
from pathlib import Path
from types import ModuleType
from typing import Any

import pytest
import yaml

ROOT = Path(__file__).parent.parent
SCRIPT_DIR = ROOT / "plugins" / "saga" / "scripts"
REGISTRY_PATH = ROOT / "plugins" / "saga" / "references" / "engine-registry.yaml"
SCRIPT = SCRIPT_DIR / "engine_promotion.py"
ENGINE_ID = "ollama-cloud"
VARIANT = "gpt-oss-120b"
ENGINE_KEY = f"{ENGINE_ID}/{VARIANT}"


def _load() -> ModuleType:
    if str(SCRIPT_DIR) not in sys.path:
        sys.path.insert(0, str(SCRIPT_DIR))
    spec = importlib.util.spec_from_file_location("engine_promotion", SCRIPT)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


PROMOTION = _load()
RUN_LEDGER = PROMOTION.run_ledger


def _registry(tmp_path: Path, *, trust_tier: str = "probation") -> Path:
    data = yaml.safe_load(REGISTRY_PATH.read_text(encoding="utf-8"))
    for row in data["engines"]:
        if row["engine_id"] == ENGINE_ID and row["variant"] == VARIANT:
            row["trust_tier"] = trust_tier
            break
    path = tmp_path / "engine-registry.yaml"
    path.write_text(yaml.safe_dump(data, sort_keys=False), encoding="utf-8")
    return path


def _ledger(tmp_path: Path) -> Any:
    return RUN_LEDGER.RunLedger(path=tmp_path / "run-facts.jsonl")


def _append(
    ledger: Any,
    number: int,
    *,
    engine: str = ENGINE_ID,
    variant: str = VARIANT,
    status: str = "ok",
    proof: str = "ok",
    run_key: str | None = None,
) -> None:
    fields: dict[str, Any] = {
        "engine": engine,
        "variant": variant,
        "status": status,
        "proof_integrity_status": proof,
    }
    if run_key is not None:
        fields["bridge_run_key"] = run_key
    RUN_LEDGER.append_fact(
        ledger,
        RUN_LEDGER.build_fact(
            "engine",
            subplot_id="sub-455",
            at=f"2026-07-09T00:00:{number:02d}Z",
            **fields,
        ),
    )


def _assess(tmp_path: Path, ledger: Any) -> Any:
    return PROMOTION.assess_promotion(
        ENGINE_KEY,
        registry_path=_registry(tmp_path),
        ledger=ledger,
    )


def test_five_exact_variant_proven_successes_are_eligible(tmp_path: Path) -> None:
    ledger = _ledger(tmp_path)
    for number in range(5):
        _append(ledger, number, run_key=f"run-{number}")

    result = _assess(tmp_path, ledger)

    assert result.eligible
    assert result.matching_runs == 5
    assert result.qualifying_runs == 5
    assert result.inspected_run_keys == tuple(f"run-{number}" for number in range(5))
    assert result.reasons == ()


@pytest.mark.parametrize("count", range(5))
def test_zero_through_four_exact_matches_report_the_deficit(
    tmp_path: Path,
    count: int,
) -> None:
    ledger = _ledger(tmp_path)
    for number in range(count):
        _append(ledger, number, run_key=f"run-{number}")

    result = _assess(tmp_path, ledger)

    assert not result.eligible
    assert result.matching_runs == count
    assert result.reasons[0] == f"need 5 exact-variant engine facts; found {count}"


@pytest.mark.parametrize(
    ("kwargs", "reason"),
    [
        ({"status": "failed", "run_key": "bad-status"}, "status='failed'"),
        ({"proof": "failed", "run_key": "bad-proof"}, "proof_integrity_status='failed'"),
        ({"proof": "unproven", "run_key": "unproven"}, "proof_integrity_status='unproven'"),
        ({"run_key": None}, "bridge_run_key is missing or empty"),
        ({"run_key": "   "}, "bridge_run_key is missing or empty"),
    ],
)
def test_bad_fact_in_latest_window_reports_precise_reason(
    tmp_path: Path,
    kwargs: dict[str, Any],
    reason: str,
) -> None:
    ledger = _ledger(tmp_path)
    for number in range(4):
        _append(ledger, number, run_key=f"run-{number}")
    _append(ledger, 4, **kwargs)

    result = _assess(tmp_path, ledger)

    assert not result.eligible
    assert result.qualifying_runs == 4
    assert any(reason in item for item in result.reasons)


def test_sibling_variant_facts_do_not_count(tmp_path: Path) -> None:
    ledger = _ledger(tmp_path)
    for number in range(5):
        _append(ledger, number, variant="nomic-embed-text", run_key=f"sibling-{number}")
    for number in range(4):
        _append(ledger, number + 5, run_key=f"exact-{number}")

    result = _assess(tmp_path, ledger)

    assert not result.eligible
    assert result.matching_runs == 4
    assert result.inspected_run_keys == tuple(f"exact-{number}" for number in range(4))


def test_only_five_most_recent_exact_matches_decide(tmp_path: Path) -> None:
    ledger = _ledger(tmp_path)
    _append(ledger, 0, status="failed", run_key="old-failure")
    for number in range(1, 6):
        _append(ledger, number, run_key=f"recent-{number}")

    result = _assess(tmp_path, ledger)

    assert result.eligible
    assert result.matching_runs == 6
    assert "old-failure" not in result.inspected_run_keys


def test_duplicate_bridge_run_key_does_not_count_as_a_distinct_run(tmp_path: Path) -> None:
    ledger = _ledger(tmp_path)
    for number in range(5):
        _append(ledger, number, run_key="duplicate" if number >= 3 else f"run-{number}")

    result = _assess(tmp_path, ledger)

    assert not result.eligible
    assert result.qualifying_runs == 4
    assert any("duplicated" in reason for reason in result.reasons)


def test_broken_ledger_chain_fails_closed(tmp_path: Path) -> None:
    ledger = _ledger(tmp_path)
    _append(ledger, 0, run_key="run-0")
    record = json.loads(ledger.path.read_text(encoding="utf-8"))
    record["status"] = "failed"
    ledger.path.write_text(json.dumps(record) + "\n", encoding="utf-8")

    with pytest.raises(PROMOTION.PromotionError, match="chain failed"):
        _assess(tmp_path, ledger)


def test_ledger_change_during_assessment_fails_closed(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    clean_report = RUN_LEDGER.ChainReport(ok=True, break_index=None, reason="ok")
    snapshots = iter(
        [
            RUN_LEDGER.LedgerSnapshot(records=(), report=clean_report),
            RUN_LEDGER.LedgerSnapshot(records=(), report=clean_report),
            RUN_LEDGER.LedgerSnapshot(records=({"kind": "engine"},), report=clean_report),
        ]
    )
    monkeypatch.setattr(RUN_LEDGER, "read_snapshot", lambda _ledger: next(snapshots))

    with pytest.raises(PROMOTION.PromotionError, match="changed during assessment"):
        _assess(tmp_path, _ledger(tmp_path))


def test_advisory_row_reports_promotion_not_applicable(tmp_path: Path) -> None:
    with pytest.raises(PROMOTION.PromotionError, match="not applicable"):
        PROMOTION.assess_promotion(
            ENGINE_KEY,
            registry_path=_registry(tmp_path, trust_tier="advisory"),
            ledger=_ledger(tmp_path),
        )


def test_unknown_or_malformed_engine_key_is_rejected(tmp_path: Path) -> None:
    registry = _registry(tmp_path)
    ledger = _ledger(tmp_path)

    with pytest.raises(PROMOTION.PromotionError, match="exact <engine>/<variant>"):
        PROMOTION.assess_promotion("ollama-cloud", registry_path=registry, ledger=ledger)
    with pytest.raises(PROMOTION.PromotionError, match="unknown engine variant"):
        PROMOTION.assess_promotion("missing/variant", registry_path=registry, ledger=ledger)


def test_cli_json_returns_zero_for_valid_but_ineligible_evidence(tmp_path: Path) -> None:
    ledger = _ledger(tmp_path)
    for number in range(4):
        _append(ledger, number, run_key=f"run-{number}")

    completed = subprocess.run(
        [
            sys.executable,
            str(SCRIPT),
            ENGINE_KEY,
            "--registry",
            str(_registry(tmp_path)),
            "--ledger",
            str(ledger.path),
            "--json",
        ],
        check=False,
        capture_output=True,
        text=True,
    )

    assert completed.returncode == 0
    payload = json.loads(completed.stdout)
    assert payload["eligible"] is False
    assert payload["matching_runs"] == 4


def test_cli_main_renders_both_dispositions_and_fails_cleanly(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    registry = _registry(tmp_path)
    ledger = _ledger(tmp_path)
    for number in range(4):
        _append(ledger, number, run_key=f"run-{number}")
    args = [ENGINE_KEY, "--registry", str(registry), "--ledger", str(ledger.path)]

    assert PROMOTION.main(args) == 0
    output = capsys.readouterr().out
    assert "promotion not eligible" in output
    assert "need 5 exact-variant engine facts; found 4" in output

    _append(ledger, 4, run_key="run-4")
    assert PROMOTION.main(args) == 0
    output = capsys.readouterr().out
    assert "promotion eligible" in output
    assert "reviewed registry PR" in output

    assert PROMOTION.main([*args, "--json"]) == 0
    assert json.loads(capsys.readouterr().out)["eligible"] is True

    malformed = tmp_path / "malformed-registry.yaml"
    malformed.write_text("engines: [", encoding="utf-8")
    assert (
        PROMOTION.main([ENGINE_KEY, "--registry", str(malformed), "--ledger", str(ledger.path)])
        == 1
    )
    assert "engine promotion assessment failed" in capsys.readouterr().err


def test_cli_main_reports_default_ledger_resolution_error(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def unavailable(_cls: type[Any], _repo_root: Path) -> Any:
        raise ValueError("git common dir unavailable")

    monkeypatch.setattr(RUN_LEDGER.RunLedger, "resolve", classmethod(unavailable))

    assert PROMOTION.main([ENGINE_KEY, "--registry", str(_registry(tmp_path))]) == 1
    assert "git common dir unavailable" in capsys.readouterr().err
