"""Oracle tests for Saga execution-spec external-engine routing (U5)."""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path
from types import ModuleType

import pytest

ROOT = Path(__file__).parent.parent
SCRIPT_DIR = ROOT / "plugins" / "saga" / "scripts"
EXECUTION_SPEC_SCRIPT = SCRIPT_DIR / "execution_spec.py"
LIFECYCLE_STATE_SCRIPT = SCRIPT_DIR / "lifecycle_state.py"


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


ES = _load("execution_spec", EXECUTION_SPEC_SCRIPT)
_load("lifecycle_state", LIFECYCLE_STATE_SCRIPT)


def _spec_dict(**unit_overrides: object) -> dict[str, object]:
    unit: dict[str, object] = {
        "unit_id": "U1",
        "label": "external draft",
        "tier": {"model": "sonnet", "effort": "high"},
        "prompt": "draft a bounded implementation diff",
        "returns": ["diff", "assumptions"],
    }
    unit.update(unit_overrides)
    return {
        "name": "external-engine-demo",
        "description": "exercise external-engine unit selectors",
        "repo": "/tmp/repo",
        "units": [unit],
    }


def test_engine_unit_validates_and_emits_external_engine_marker() -> None:
    spec = ES.ExecutionSpec.from_dict(_spec_dict(engine="codex/gpt-5.5-xhigh"))
    spec.validate()

    script = ES.emit_workflow_script(spec)

    assert "// external-engine dispatch: engine=codex/gpt-5.5-xhigh" in script
    assert 'dispatch: "external-engine"' in script
    assert 'engine: "codex/gpt-5.5-xhigh"' in script


def test_unknown_engine_variant_fails() -> None:
    with pytest.raises(ES.SpecError, match="unknown engine variant"):
        ES.ExecutionSpec.from_dict(_spec_dict(engine="codex/nonexistent"))


def test_unknown_capability_fails() -> None:
    with pytest.raises(ES.SpecError, match="unknown capability"):
        ES.ExecutionSpec.from_dict(_spec_dict(capability="telepathy"))


def test_engine_and_capability_are_mutually_exclusive() -> None:
    with pytest.raises(ES.SpecError, match="mutually exclusive"):
        ES.ExecutionSpec.from_dict(
            _spec_dict(engine="codex/gpt-5.5-xhigh", capability="code-generation")
        )


def test_existing_style_unit_has_no_external_engine_marker() -> None:
    spec = ES.ExecutionSpec.from_dict(_spec_dict())
    spec.validate()

    script = ES.emit_workflow_script(spec)

    assert "external-engine dispatch" not in script
    assert 'model: "sonnet"' in script
    assert 'effort: "high"' in script


def test_advisory_consensus_routes_to_ultracode_backend() -> None:
    from lifecycle_state import recommend_execution_backend

    result = recommend_execution_backend(needs_consensus=True, consensus_is_gated=False)

    assert result["recommended"] == "cc-workflows-ultracode"
