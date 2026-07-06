"""Tests for #366 U3: the SpendEnvelope accumulator + spend_envelope field round-trip.

Covers the acceptance criteria
`uv run pytest tests/test_spend_envelope.py -k sub_threshold_silent` and `-k crossing_prompts_once`.
The accumulator is pure: it decides prompt-or-silent for a simulated sequence of spend-increasing
choices; "ask once, at the crossing" means a sequence with a single crossing prompts exactly once.
"""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path
from types import ModuleType

ROOT = Path(__file__).parent.parent
SCRIPT_DIR = ROOT / "plugins" / "saga" / "scripts"
EXECUTION_SPEC_SCRIPT = SCRIPT_DIR / "execution_spec.py"


def _load(name: str, path: Path) -> ModuleType:
    if str(SCRIPT_DIR) not in sys.path:
        sys.path.insert(0, str(SCRIPT_DIR))
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


ES = _load("execution_spec", EXECUTION_SPEC_SCRIPT)


def _one_unit_spec(**overrides: object) -> dict[str, object]:
    spec: dict[str, object] = {
        "name": "envelope-demo",
        "description": "exercise spend_envelope",
        "repo": "/tmp/repo",
        "units": [
            {
                "unit_id": "U1",
                "label": "U1",
                "tier": {"model": "sonnet", "effort": "high"},
                "prompt": "do the thing",
            }
        ],
    }
    spec.update(overrides)
    return spec


def test_sub_threshold_silent() -> None:
    """A sequence of choices that all stay under the envelope yields zero prompts."""
    env = ES.SpendEnvelope(envelope=100)
    prompts = [env.consider(delta) for delta in (10, 20, 30)]
    assert prompts == [False, False, False]
    assert sum(prompts) == 0
    assert env.cumulative == 60
    assert env.remaining == 40


def test_crossing_prompts_once() -> None:
    """A sequence where exactly one choice crosses the envelope prompts exactly once."""
    env = ES.SpendEnvelope(envelope=50)
    prompts = [env.consider(delta) for delta in (20, 20, 20)]
    assert sum(prompts) == 1
    # cumulative walks 0->20 (under), 20->40 (under), 40->60 (crosses on the third choice).
    assert prompts == [False, False, True]
    # once crossed, cumulative is already over the envelope, so later choices never re-prompt.
    assert env.consider(5) is False
    assert env.remaining < 0


def test_exact_hit_is_within_budget_next_crosses() -> None:
    """Landing exactly on the envelope is within budget; the next positive delta crosses."""
    env = ES.SpendEnvelope(envelope=50)
    assert env.consider(50) is False
    assert env.consider(1) is True


def test_spend_envelope_absent_roundtrips() -> None:
    spec = ES.ExecutionSpec.from_dict(_one_unit_spec())
    assert spec.spend_envelope is None
    assert "spend_envelope" not in spec.to_dict()
    assert ES.ExecutionSpec.from_dict(spec.to_dict()).to_dict() == spec.to_dict()


def test_spend_envelope_present_roundtrips_and_validates() -> None:
    spec = ES.ExecutionSpec.from_dict(_one_unit_spec(spend_envelope=40))
    assert spec.spend_envelope == 40
    assert spec.to_dict()["spend_envelope"] == 40
    spec.validate()  # a positive envelope validates


def test_spend_envelope_below_one_rejected() -> None:
    spec = ES.ExecutionSpec.from_dict(_one_unit_spec(spend_envelope=0))
    import pytest

    with pytest.raises(ES.SpecError, match=r"spend_envelope 0 must be >= 1"):
        spec.validate()
