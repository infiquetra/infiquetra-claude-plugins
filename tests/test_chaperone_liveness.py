"""Producer/consumer bridge-run liveness checks (#388)."""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path
from types import ModuleType

ROOT = Path(__file__).parent.parent
SCRIPT = ROOT / "plugins" / "saga" / "scripts" / "bridge_signatures.py"


def _load() -> ModuleType:
    scripts = SCRIPT.parent
    if str(scripts) not in sys.path:
        sys.path.insert(0, str(scripts))
    spec = importlib.util.spec_from_file_location("bridge_signatures_liveness", SCRIPT)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


BS = _load()


def test_matching_launch_and_consumer_keys_pass() -> None:
    assert BS.liveness_errors({"run-1"}, {"run-1"}) == []


def test_launched_unconsumed_fails() -> None:
    assert BS.liveness_errors({"run-1"}, set()) == ["proof-integrity: launched-unconsumed run-1"]


def test_consumed_unlaunched_fails() -> None:
    assert BS.liveness_errors(set(), {"run-1"}) == ["proof-integrity: consumed-unlaunched run-1"]
