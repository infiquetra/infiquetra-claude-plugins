"""Emitter substrate surface — the plugin boundary is declared, not accidental (F10a).

The extracted emitter binds names from Saga's ``execution_spec`` across the plugin
boundary; eleven of them are private. These tests pin the declared surface both ways:
every bound name is a member of ``SUBSTRATE_SURFACE``, and every declared name exists on
both sides — so the boundary cannot grow or rot silently in either direction.
"""

from __future__ import annotations

import ast
import importlib.util
import sys
from pathlib import Path
from types import ModuleType

import pytest

REPO_ROOT = Path(__file__).parent.parent
SCRIPTS_DIR = REPO_ROOT / "plugins" / "cc-workflows" / "skills" / "cc-workflows" / "scripts"
EMITTER_PATH = SCRIPTS_DIR / "emitter.py"


def _load_module(name: str, path: Path) -> ModuleType:
    cached = sys.modules.get(name)
    if cached is not None:
        return cached
    if str(path.parent) not in sys.path:
        sys.path.insert(0, str(path.parent))
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


@pytest.fixture
def emitter() -> ModuleType:
    return _load_module("cc_workflows_emitter_surface_test", EMITTER_PATH)


def _bound_target_names() -> set[str]:
    """The names ``_bind_substrate`` assigns — parsed from source, not assumed."""
    tree = ast.parse(EMITTER_PATH.read_text(encoding="utf-8"))
    bind = next(
        n for n in ast.walk(tree) if isinstance(n, ast.FunctionDef) and n.name == "_bind_substrate"
    )
    targets: set[str] = set()
    for node in ast.walk(bind):
        if (
            isinstance(node, ast.Assign)
            and isinstance(node.value, ast.Attribute)
            and isinstance(node.value.value, ast.Name)
            and node.value.value.id == "es"
        ):
            for target in node.targets:
                if isinstance(target, ast.Name):
                    targets.add(target.id)
    targets.discard("_ES")  # the module reference itself, not a substrate name
    return targets


def test_every_bound_name_is_a_declared_surface_member(emitter: ModuleType) -> None:
    declared = set(emitter.SUBSTRATE_SURFACE)
    bound = _bound_target_names()
    assert bound, "the surface parser found no bindings — the pin is broken"
    assert bound <= declared, f"undeclared names cross the plugin boundary: {bound - declared}"
    assert declared <= bound, f"declared surface names are never bound: {declared - bound}"


def test_every_declared_name_exists_on_both_sides(emitter: ModuleType) -> None:
    spec_module = _load_module(
        "execution_spec", REPO_ROOT / "plugins" / "saga" / "scripts" / "execution_spec.py"
    )
    for name in emitter.SUBSTRATE_SURFACE:
        assert hasattr(spec_module, name), f"execution_spec lost the substrate name {name!r}"
        assert getattr(emitter, name) is not None, f"the emitter never bound {name!r}"


def test_bind_substrate_refuses_a_substrate_missing_declared_names(
    emitter: ModuleType,
) -> None:
    class Stub:
        """A substrate with one declared name missing."""

    stub = Stub()
    for name in emitter.SUBSTRATE_SURFACE:
        if name != "VERIFY_N_WARN":
            setattr(stub, name, object())

    with pytest.raises(RuntimeError, match="VERIFY_N_WARN"):
        emitter._bind_substrate(stub)
