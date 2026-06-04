"""Oracle tests for the deterministic /qa health scorer (qa_health_score.py).

Every expected value below is hand-computed FROM the documented formula
(gstack-ported deductions critical -25 / high -15 / medium -8 / low -3, per-class floor 0;
infiquetra ship-risk class weights re-normalized over the in-scope classes), NOT read back
from the implementation. The test asserts these literals so it would catch a scorer that
drifts from the rubric.

Hand derivations:
- {"behavior": {"critical": 1}}                  -> behavior 100-25=75 ; only class -> overall 75
- {"behavior": {"critical": 1}, "api": {"high": 1}}
      behavior 75, api 100-15=85 ; (75*20 + 85*15) / (20+15) = 2775/35 = 79.2857 -> round 79
- {"behavior": {}}                               -> behavior 100 (checked-but-clean) ; overall 100
- {}                                             -> no in-scope class -> vacuously healthy 100
- {"security": {"critical": 4}}                  -> 100-100=0 (floored) ; only class -> overall 0
- {"behavior": {"critical": 1}} + baseline 90    -> overall 75 ; delta 75-90 = -15
"""

from __future__ import annotations

import importlib.util
import json
from pathlib import Path

ROOT = Path(__file__).parent.parent
SCRIPT = ROOT / "plugins" / "infiquetra-lifecycle" / "scripts" / "qa_health_score.py"


def _load():
    spec = importlib.util.spec_from_file_location("qa_health_score", SCRIPT)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_single_class_critical() -> None:
    scorer = _load()
    result = scorer.score_findings({"behavior": {"critical": 1}})
    assert result["per_class"]["behavior"] == 75
    assert result["overall"] == 75
    assert result["in_scope"] == ["behavior"]


def test_two_classes_weighted_renormalized() -> None:
    scorer = _load()
    result = scorer.score_findings({"behavior": {"critical": 1}, "api": {"high": 1}})
    assert result["per_class"]["behavior"] == 75
    assert result["per_class"]["api"] == 85
    # round((75*20 + 85*15) / (20+15)) == round(2775/35) == round(79.2857) == 79
    assert result["overall"] == 79


def test_checked_but_clean_class_scores_100() -> None:
    scorer = _load()
    result = scorer.score_findings({"behavior": {}})
    assert result["per_class"]["behavior"] == 100
    assert result["overall"] == 100
    assert result["in_scope"] == ["behavior"]


def test_empty_input_is_vacuously_healthy() -> None:
    scorer = _load()
    result = scorer.score_findings({})
    assert result["overall"] == 100
    assert result["in_scope"] == []
    assert result["per_class"] == {}


def test_floor_at_zero() -> None:
    scorer = _load()
    result = scorer.score_findings({"security": {"critical": 4}})
    assert result["per_class"]["security"] == 0
    assert result["overall"] == 0


def test_baseline_delta() -> None:
    scorer = _load()
    result = scorer.score_findings({"behavior": {"critical": 1}}, baseline=90)
    assert result["overall"] == 75
    assert result["baseline"] == 90
    assert result["delta"] == -15


def test_cli_inline_json_emits_oracle_json() -> None:
    """End-to-end CLI surface: inline JSON in, the oracle overall/delta out as JSON."""
    import subprocess
    import sys

    proc = subprocess.run(
        [
            sys.executable,
            str(SCRIPT),
            "--findings-json",
            json.dumps({"behavior": {"critical": 1}}),
            "--baseline-score",
            "90",
        ],
        capture_output=True,
        text=True,
        check=True,
    )
    payload = json.loads(proc.stdout)
    assert payload["overall"] == 75
    assert payload["delta"] == -15
    assert payload["per_class"]["behavior"] == 75
