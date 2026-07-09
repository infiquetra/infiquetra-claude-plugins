"""Tests for the offline engine-registry conformance gate (#455)."""

from __future__ import annotations

import importlib.util
import sys
from copy import deepcopy
from pathlib import Path
from types import ModuleType
from typing import Any

import pytest
import yaml

ROOT = Path(__file__).parent.parent
SCRIPT_DIR = ROOT / "plugins" / "saga" / "scripts"
REGISTRY_PATH = ROOT / "plugins" / "saga" / "references" / "engine-registry.yaml"
SCRIPT = SCRIPT_DIR / "engine_registry_conformance.py"


def _load() -> ModuleType:
    if str(SCRIPT_DIR) not in sys.path:
        sys.path.insert(0, str(SCRIPT_DIR))
    spec = importlib.util.spec_from_file_location("engine_registry_conformance", SCRIPT)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


C = _load()


def _registry_data() -> dict[str, Any]:
    data = yaml.safe_load(REGISTRY_PATH.read_text(encoding="utf-8"))
    assert isinstance(data, dict)
    return data


def _write_registry(tmp_path: Path, data: dict[str, Any]) -> Path:
    path = tmp_path / "engine-registry.yaml"
    path.write_text(yaml.safe_dump(data, sort_keys=False), encoding="utf-8")
    return path


def test_shipped_registry_passes_offline_conformance() -> None:
    registry = C.Registry.load(REGISTRY_PATH)

    report = C.check_registry(registry)

    assert report.ok
    assert report.checked_rows == len(registry.engines)
    assert report.issues == ()


def test_schema_valid_dead_wired_row_fails_dispatch_invocation() -> None:
    data = _registry_data()
    row = data["engines"][-1]
    row["invocation"]["via"] = "missing-provider-bridge"
    registry = C.Registry.from_dict(data)

    report = C.check_registry(registry)

    assert not report.ok
    assert any(
        issue.engine_key == "deepseek/deepseek-chat"
        and issue.check == "dispatch-invocation"
        and "unsupported external engine" in issue.reason
        for issue in report.issues
    )


def test_unknown_receipt_emitter_fails_with_row_key() -> None:
    data = _registry_data()
    data["engines"][-1]["receipt_emitter"] = "missing-emitter"
    registry = C.Registry.from_dict(data)

    report = C.check_registry(registry)

    assert any(
        issue.engine_key == "deepseek/deepseek-chat"
        and issue.check == "receipt-emitter"
        and "missing-emitter" in issue.reason
        for issue in report.issues
    )


def test_advertised_capability_must_appear_in_candidates(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    registry = C.Registry.load(REGISTRY_PATH)
    original = C.Registry.ranked_candidates

    def without_deepseek(self: Any, capability: str, **kwargs: Any) -> tuple[Any, ...]:
        return tuple(
            candidate
            for candidate in original(self, capability, **kwargs)
            if candidate.entry.key != "deepseek/deepseek-chat"
        )

    monkeypatch.setattr(C.Registry, "ranked_candidates", without_deepseek)

    report = C.check_registry(registry)

    assert any(
        issue.engine_key == "deepseek/deepseek-chat" and issue.check == "capability:code-generation"
        for issue in report.issues
    )


def test_checker_does_not_dispatch_or_preflight(monkeypatch: pytest.MonkeyPatch) -> None:
    registry = C.Registry.load(REGISTRY_PATH)

    def forbidden(*_args: Any, **_kwargs: Any) -> None:
        raise AssertionError("conformance must not dispatch or preflight")

    monkeypatch.setattr(C.engine_dispatch, "dispatch", forbidden)
    monkeypatch.setattr(sys.modules["engine_resolver"], "preflight", forbidden)

    assert C.check_registry(registry).ok


def test_cli_passes_live_registry_and_fails_broken_fixture(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    assert C.main(["--registry", str(REGISTRY_PATH)]) == 0
    assert "conformance ok" in capsys.readouterr().out

    broken = deepcopy(_registry_data())
    broken["engines"][-1]["invocation"]["via"] = "missing-provider-bridge"
    path = _write_registry(tmp_path, broken)

    assert C.main(["--registry", str(path)]) == 1
    err = capsys.readouterr().err
    assert "deepseek/deepseek-chat" in err
    assert "dispatch-invocation" in err
