"""Tests for the fakes registry + real-contract shadow (#458, T11-F6-8).

Pins the acceptance criterion: renaming a public method on a real adapter class registered in
``tests/fakes_registry.py`` fails that fake's signature-parity test. The current registry passes; a
scratch rename (a mutation binding) demonstrably fails.
"""

from __future__ import annotations

import importlib.util
import sys
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import fakes_registry as fr
import pytest

# The real production adapter this registry shadows lives under plugins/saga/scripts. Loading it here
# (the repo's importlib-by-path idiom) both strengthens the test — it proves the registry binds the
# ACTUAL production class, not a stand-in — and crosses the fake/real boundary this suite validates.
_SCRIPTS = Path(__file__).resolve().parent.parent / "plugins" / "saga" / "scripts"


def _load_real(name: str) -> Any:
    if str(_SCRIPTS) not in sys.path:
        sys.path.insert(0, str(_SCRIPTS))
    spec = importlib.util.spec_from_file_location(name, _SCRIPTS / f"{name}.py")
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


def test_signature_parity_current_registry_holds() -> None:
    """Every registered fake mirrors its real class's public contract (name + arity)."""
    assert fr.REGISTRY, "registry must ship at least one worked-example binding"
    for binding in fr.REGISTRY:
        assert fr.signature_mismatches(binding.real, binding.build_fake()) == [], (
            f"binding {binding.name!r} drifted"
        )
        # verify_binding is the loud gate; it must not raise for a healthy registry.
        fr.verify_binding(binding)


def test_import_time_verification_runs() -> None:
    """Importing the registry runs :func:`verify_registry` — a healthy registry imports cleanly."""
    fr.verify_registry()


def test_signature_parity_detects_rename() -> None:
    """A real class whose public method is renamed out from under its fake fails parity."""

    class RealAdapter:
        def exists(self, path: str) -> bool:  # the real public method
            return True

    class DriftedFake:
        def is_live(self, path: str) -> bool:  # a rename — fake never followed the real contract
            return True

    binding = fr.Binding(
        name="scratch-rename",
        real=RealAdapter,
        fake_factory=DriftedFake,
        note="mutation test",
    )
    problems = fr.signature_mismatches(binding.real, binding.build_fake())
    assert any("exists" in p for p in problems)
    with pytest.raises(fr.FakeContractDriftError):
        fr.verify_binding(binding)


def test_signature_parity_detects_arity_drift() -> None:
    """A fake whose callable arity diverges from the real ``Callable[[...], ...]`` contract fails."""

    @dataclass
    class RealProtocol:
        # Under ``from __future__ import annotations`` this field's contract is the string
        # "Callable[[str, str], bool]" — a declared arity of 2.
        probe: Callable[[str, str], bool]

    class OneArgFake:
        def probe(self, only_one: str) -> bool:  # arity 1 — drift from the real arity 2
            return True

    fake = OneArgFake()
    problems = fr.signature_mismatches(RealProtocol, fake)
    assert any("arity drift" in p and "probe" in p for p in problems)


def test_registry_binds_the_real_production_class() -> None:
    """The registered ``real`` is the ACTUAL production ``WorktreeOps`` from plugins/saga/scripts."""
    real_module = _load_real("outcome_worktrees")
    binding = next(b for b in fr.REGISTRY if b.name == "worktree-liveness-oracle")
    assert binding.real.__name__ == "WorktreeOps"
    # The registered real class mirrors a freshly-loaded production WorktreeOps' public contract.
    assert fr.contract_of(binding.real) == fr.contract_of(real_module.WorktreeOps)


def test_contract_of_handles_dataclass_and_class() -> None:
    """``contract_of`` extracts a contract from both a dataclass protocol and a plain class."""
    wt_binding = next(b for b in fr.REGISTRY if b.name == "worktree-liveness-oracle")
    real_contract = fr.contract_of(wt_binding.real)
    assert real_contract == {"add": 2, "remove": 1, "exists": 1, "list_paths": 0}

    class Plain:
        def run(self, a: int, b: int) -> int:
            return a + b

    assert fr.contract_of(Plain) == {"run": 2}
