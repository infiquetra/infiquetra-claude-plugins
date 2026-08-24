"""Fakes registry + real-contract shadow (#458, T11-F6-8).

The failure this gates against (``docs/engineering-journal/LEARNINGS.md``
``{#fake-adapter-hides-real-path-mismatch}``): a fake (``FakeWT``) stood in for a real adapter
(``WorktreeOps`` / ``git_worktree_ops``), every unit test passed, and only an adversarial
real-substrate run found that the fake's behavior had silently drifted from the real adapter's
public contract. There was no mechanical gate binding a fake to the real class it shadows.

This module is that binding. Each :class:`Binding` pairs a **fake** with the **real class or
protocol** it stands in for, and :func:`verify_registry` (run at import time) fails if any fake's
public contract has drifted out from under its real counterpart — a renamed public method, a
dropped one, or a callable whose arity no longer matches the real contract.

Two contract shapes are supported so the same gate covers both idioms in this repo:

* a **dataclass-of-callables protocol** (``WorktreeOps`` — the worked example), whose contract is its
  fields' ``Callable[[...], ...]`` annotations; and
* a plain **class with public methods**, whose contract is those methods' signatures.
"""

from __future__ import annotations

import ast
import importlib.util
import inspect
import sys
from collections.abc import Callable
from dataclasses import dataclass, fields, is_dataclass
from pathlib import Path
from typing import Any

_SCRIPTS = Path(__file__).resolve().parent.parent / "plugins" / "saga" / "scripts"


def _load(name: str) -> Any:
    """Load a saga script module by path (the repo's importlib-by-path idiom)."""
    if str(_SCRIPTS) not in sys.path:
        sys.path.insert(0, str(_SCRIPTS))
    spec = importlib.util.spec_from_file_location(name, _SCRIPTS / f"{name}.py")
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


class FakeContractDriftError(AssertionError):
    """A registered fake's public contract no longer matches the real class it shadows."""


@dataclass(frozen=True)
class Binding:
    """One fake bound to the real class/protocol it stands in for."""

    name: str
    real: type
    fake_factory: Callable[[], Any]
    note: str = ""

    def build_fake(self) -> Any:
        return self.fake_factory()


# ---------------------------------------------------------------------------
# Contract extraction (works for a dataclass-of-callables OR a method-bearing class)
# ---------------------------------------------------------------------------


def _callable_arity_from_annotation(annotation: Any) -> int | None:
    """Arity declared by a ``Callable[[a, b], r]`` annotation (a str under ``__future__`` or a type).

    Returns the number of positional argument types, or ``None`` when the annotation is not a
    ``Callable[[...], ...]`` with an explicit argument list.
    """
    if isinstance(annotation, str):
        try:
            expr = ast.parse(annotation, mode="eval").body
        except SyntaxError:
            return None
        if not isinstance(expr, ast.Subscript):
            return None
        base = expr.value
        base_name = base.id if isinstance(base, ast.Name) else getattr(base, "attr", "")
        if base_name != "Callable":
            return None
        sl = expr.slice
        if isinstance(sl, ast.Tuple) and sl.elts and isinstance(sl.elts[0], ast.List):
            return len(sl.elts[0].elts)
        return None
    # A real typing.Callable[[...], ...] object exposes its arg types via __args__ (args..., ret).
    args = getattr(annotation, "__args__", None)
    if args is not None and len(args) >= 1:
        return len(args) - 1
    return None


def _signature_arity(fn: Callable[..., Any]) -> int:
    """Positional-parameter count of a callable, excluding an unbound ``self``."""
    params = list(inspect.signature(fn).parameters.values())
    if params and params[0].name == "self" and inspect.isfunction(fn):
        params = params[1:]
    return len(params)


def contract_of(obj: Any) -> dict[str, int]:
    """The public {name -> arity} contract of a class, protocol, or instance.

    * A dataclass (class or instance) contributes each field whose value/annotation is a callable.
    * Any other class/instance contributes its public (non-dunder, non-underscore) methods.
    """
    if is_dataclass(obj):
        contract: dict[str, int] = {}
        is_instance = not isinstance(obj, type)
        for f in fields(obj):
            if is_instance:
                value = getattr(obj, f.name)
                if callable(value):
                    contract[f.name] = _signature_arity(value)
            else:
                arity = _callable_arity_from_annotation(f.type)
                if arity is not None:
                    contract[f.name] = arity
        return contract
    # Plain class / instance: public methods.
    contract = {}
    for attr_name, attr in inspect.getmembers(obj, callable):
        if attr_name.startswith("_"):
            continue
        try:
            contract[attr_name] = _signature_arity(attr)
        except (ValueError, TypeError):
            continue
    return contract


def signature_mismatches(real: Any, fake: Any) -> list[str]:
    """Human-readable contract mismatches between a real class/protocol and its fake (empty == OK)."""
    real_c = contract_of(real)
    fake_c = contract_of(fake)
    problems: list[str] = []
    missing = sorted(set(real_c) - set(fake_c))
    extra = sorted(set(fake_c) - set(real_c))
    for name in missing:
        problems.append(
            f"fake is missing real member {name!r} (renamed/dropped on the real class?)"
        )
    for name in extra:
        problems.append(f"fake exposes {name!r} absent from the real contract")
    for name in sorted(set(real_c) & set(fake_c)):
        if real_c[name] != fake_c[name]:
            problems.append(
                f"arity drift on {name!r}: real declares {real_c[name]}, fake has {fake_c[name]}"
            )
    return problems


def verify_binding(binding: Binding) -> None:
    """Raise :class:`FakeContractDriftError` if a binding's fake has drifted from its real contract."""
    problems = signature_mismatches(binding.real, binding.build_fake())
    if problems:
        joined = "\n  - ".join(problems)
        raise FakeContractDriftError(
            f"fake/real contract drift for binding {binding.name!r} ({binding.note}):\n  - {joined}"
        )


def verify_registry() -> None:
    """Verify every registered binding (called at import time — importing this module gates drift)."""
    for binding in REGISTRY:
        verify_binding(binding)


# ---------------------------------------------------------------------------
# Registered bindings — one worked example (the U7 worktree-liveness seam)
# ---------------------------------------------------------------------------

_WT = _load("outcome_worktrees")


class FakeWT:
    """In-memory stand-in for the real git-worktree adapter — a contract-faithful fake.

    Can be seeded from porcelain output (e.g. golden fixture data, #588).
    """

    def __init__(
        self,
        *,
        exists_override: Any = None,
        seed_porcelain: str | None = None,
        root: str = "<ROOT>",
    ) -> None:
        self.paths: set[str] = set()
        self.removed: list[str] = []
        self._exists_override = exists_override
        if seed_porcelain is not None:
            self.load_porcelain(seed_porcelain, root=root)

    def load_porcelain(self, porcelain_text: str, root: str = "<ROOT>") -> None:
        """Consume git worktree porcelain output as fixture data (#588)."""
        for line in porcelain_text.splitlines():
            if line.startswith("worktree "):
                raw_path = line[len("worktree ") :].strip()
                p = raw_path.replace("<ROOT>", root)
                self.paths.add(p)

    def _add(self, path: str, _branch: str) -> bool:
        self.paths.add(path)
        return True

    def _remove(self, path: str) -> bool:
        self.paths.discard(path)
        self.removed.append(path)
        return True

    def _exists(self, path: str) -> bool:
        if self._exists_override is not None:
            return bool(self._exists_override(path))
        return path in self.paths

    def ops(self) -> Any:
        return _WT.WorktreeOps(
            add=self._add,
            remove=self._remove,
            exists=self._exists,
            list_paths=lambda: sorted(self.paths),
        )


def build_fake_worktree_ops() -> Any:
    """Build a ``WorktreeOps`` instance backed by the in-use FakeWT fake."""
    return FakeWT().ops()


REGISTRY: list[Binding] = [
    Binding(
        name="worktree-liveness-oracle",
        real=_WT.WorktreeOps,
        fake_factory=build_fake_worktree_ops,
        note="U7 seam from {#fake-adapter-hides-real-path-mismatch} (in-use FakeWT bound)",
    ),
]


# Import-time gate: importing this module fails loudly if any fake has drifted from its real class.
verify_registry()
