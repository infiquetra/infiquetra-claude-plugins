#!/usr/bin/env python3
"""AST-based test-shape lint — flag a test module that only touches fakes (#458, T11-F2-8).

The repeating failure this gates against (``docs/engineering-journal/LEARNINGS.md``
``{#test-shape-masks-dead-wiring-291}`` and ``{#fake-adapter-hides-real-path-mismatch}``): a test
suite that is 100% green while the thing it claims to prove is false — because the suite never
crosses the boundary (a real adapter, a persisted field) it is supposed to validate. Both incidents
were caught only by manual adversarial review, after merge. This lint is the mechanical, always-on
guard: a test module that **uses a fake but never imports or exercises the real production module**
is flagged.

Detection is purely static (``ast`` — no import, no execution, no network):

* **Fake signal** — the module imports a name/module matching ``(?i)fake``, imports the
  ``fakes_registry``, or defines a local ``class Fake...``.
* **Production signal** — the module crosses into real code: a ``plugins`` import, a ``"plugins"``
  path-segment string literal (the repo's ``spec_from_file_location(name, ROOT/"plugins"/...)``
  importlib-by-path idiom), an importlib loader call (``spec_from_file_location`` /
  ``exec_module`` / ``import_module`` / ``SourceFileLoader``), or an import of a name listed in
  ``--prod-module``.

A module is a **violation** when it shows a fake signal and NO production signal — a fake-only
suite. Given an explicit file, that file is linted regardless of name; given a directory, only
``test_*.py`` files are linted. Strict by default (any violation -> non-zero exit); ``--advisory``
reports violations but always exits 0.
"""

from __future__ import annotations

import argparse
import ast
import re
from dataclasses import dataclass, field
from pathlib import Path

_FAKE_RE = re.compile(r"fake", re.IGNORECASE)
_FAKE_CLASS_RE = re.compile(r"fake", re.IGNORECASE)
_IMPORTLIB_LOADERS = frozenset(
    {"spec_from_file_location", "exec_module", "import_module", "SourceFileLoader"}
)


@dataclass
class ShapeReport:
    """Per-module verdict + the concrete evidence behind it (so a failure is explainable)."""

    path: Path
    has_fake: bool = False
    has_production: bool = False
    fake_evidence: list[str] = field(default_factory=list)
    production_evidence: list[str] = field(default_factory=list)

    @property
    def is_violation(self) -> bool:
        return self.has_fake and not self.has_production


def _module_is_fake(name: str | None) -> bool:
    if not name:
        return False
    if name in ("check_fake_fixtures", "lint_test_shape") or "check_fake_fixtures" in name:
        return False
    return _FAKE_RE.search(name) is not None or "fakes_registry" in name


class _ShapeVisitor(ast.NodeVisitor):
    """Walk a module's AST once, recording fake + production signals with evidence.

    Uses AST-level import and call analysis (#588) so inert strings (docstrings mentioning
    'plugins/', fake-loading import_module/spec_from_file_location calls) do not count as
    production signals.
    """

    def __init__(self, prod_modules: frozenset[str]) -> None:
        self.prod_modules = prod_modules
        self.fake_evidence: list[str] = []
        self.production_evidence: list[str] = []
        self.prod_vars: set[str] = set()

    def _note_fake(self, msg: str) -> None:
        self.fake_evidence.append(msg)

    def _note_prod(self, msg: str) -> None:
        self.production_evidence.append(msg)

    def visit_Import(self, node: ast.Import) -> None:
        for alias in node.names:
            top = alias.name.split(".")[0]
            if alias.name.startswith("plugins") or top in ("plugins", "scripts", "tools"):
                self._note_prod(f"import {alias.name}")
            if top in self.prod_modules or alias.name in self.prod_modules:
                self._note_prod(f"import {alias.name} (declared production module)")
            if _module_is_fake(alias.name):
                self._note_fake(f"import {alias.name}")
        self.generic_visit(node)

    def visit_ImportFrom(self, node: ast.ImportFrom) -> None:
        mod = node.module or ""
        top = mod.split(".")[0]
        if mod.startswith("plugins") or top in ("plugins", "scripts", "tools"):
            self._note_prod(f"from {mod} import ...")
        if top in self.prod_modules or mod in self.prod_modules:
            self._note_prod(f"from {mod} import ... (declared production module)")
        if _module_is_fake(mod):
            self._note_fake(f"from {mod} import ...")
        for alias in node.names:
            if _module_is_fake(alias.name):
                self._note_fake(f"from {mod} import {alias.name}")
            if alias.name in self.prod_modules:
                self._note_prod(f"from {mod} import {alias.name} (declared production module)")
        self.generic_visit(node)

    def visit_ClassDef(self, node: ast.ClassDef) -> None:
        if _FAKE_CLASS_RE.search(node.name):
            self._note_fake(f"class {node.name}")
        self.generic_visit(node)

    def _contains_real_target(self, node: ast.AST) -> bool:
        """Check if an AST subtree constructs or contains a path to plugins, scripts, or tools."""
        for child in ast.walk(node):
            if isinstance(child, ast.Constant) and isinstance(child.value, str):
                val = child.value
                if val in ("plugins", "scripts", "tools") or any(
                    seg in val
                    for seg in ("plugins/", "/plugins", "scripts/", "/scripts", "tools/", "/tools")
                ):
                    return True
            if isinstance(child, ast.Name) and child.id in self.prod_vars:
                return True
        return False

    def visit_Assign(self, node: ast.Assign) -> None:
        if self._contains_real_target(node.value):
            for target in node.targets:
                if isinstance(target, ast.Name):
                    self.prod_vars.add(target.id)
            self._note_prod("path assignment targeting production/scripts")
        self.generic_visit(node)

    def visit_AnnAssign(self, node: ast.AnnAssign) -> None:
        if node.value and self._contains_real_target(node.value):
            if isinstance(node.target, ast.Name):
                self.prod_vars.add(node.target.id)
            self._note_prod("annotated path assignment targeting production/scripts")
        self.generic_visit(node)

    def visit_BinOp(self, node: ast.BinOp) -> None:
        # Path arithmetic like ROOT / "plugins" / "saga" or ROOT / "scripts"
        if isinstance(node.op, ast.Div) and self._contains_real_target(node):
            self._note_prod("path expression targeting production/scripts")
        self.generic_visit(node)

    def visit_Call(self, node: ast.Call) -> None:
        func = node.func
        name = ""
        if isinstance(func, ast.Attribute):
            name = func.attr
        elif isinstance(func, ast.Name):
            name = func.id

        if name == "import_module":
            if node.args:
                first = node.args[0]
                if isinstance(first, ast.Constant) and isinstance(first.value, str):
                    mod_str = first.value
                    if mod_str.startswith("plugins") or mod_str.split(".")[0] in self.prod_modules:
                        self._note_prod(f"import_module({mod_str!r})")
                    elif _module_is_fake(mod_str):
                        self._note_fake(f"import_module({mod_str!r})")
                elif isinstance(first, ast.Name) and first.id in self.prod_vars:
                    self._note_prod(f"import_module({first.id})")
        elif name in ("spec_from_file_location", "SourceFileLoader"):
            if len(node.args) >= 2:
                name_arg = node.args[0]
                loc_arg = node.args[1]
                name_str = (
                    name_arg.value
                    if isinstance(name_arg, ast.Constant) and isinstance(name_arg.value, str)
                    else ""
                )
                loc_str = (
                    loc_arg.value
                    if isinstance(loc_arg, ast.Constant) and isinstance(loc_arg.value, str)
                    else ""
                )

                if _module_is_fake(name_str):
                    self._note_fake(f"importlib loader {name}({name_str!r})")
                if loc_str and _module_is_fake(loc_str):
                    self._note_fake(f"importlib loader {name}(..., {loc_str!r})")

                if self._contains_real_target(loc_arg):
                    if not (_module_is_fake(name_str) or (loc_str and _module_is_fake(loc_str))):
                        self._note_prod(f"importlib loader {name}(...) loading production path")
                elif name_str and (name_str.startswith("plugins") or name_str in self.prod_modules):
                    self._note_prod(f"importlib loader {name}({name_str!r})")
            elif self._contains_real_target(node):
                self._note_prod(f"importlib loader {name}(...) targeting production")
        elif name == "exec_module":
            # exec_module alone is neutral; spec creation provides the signal
            pass

        self.generic_visit(node)


def analyze_source(source: str, path: Path, prod_modules: frozenset[str]) -> ShapeReport:
    """Static-analyze one module's text into a :class:`ShapeReport` (never imports it)."""
    report = ShapeReport(path=path)
    tree = ast.parse(source, filename=str(path))
    visitor = _ShapeVisitor(prod_modules)
    visitor.visit(tree)
    report.fake_evidence = visitor.fake_evidence
    report.production_evidence = visitor.production_evidence
    report.has_fake = bool(visitor.fake_evidence)
    report.has_production = bool(visitor.production_evidence)
    return report


def analyze_file(path: Path, prod_modules: frozenset[str]) -> ShapeReport:
    return analyze_source(path.read_text(encoding="utf-8"), path, prod_modules)


def _iter_targets(paths: list[Path]) -> list[Path]:
    """Explicit files are always linted; a directory contributes its ``test_*.py`` files only."""
    targets: list[Path] = []
    for p in paths:
        if p.is_dir():
            targets.extend(sorted(p.rglob("test_*.py")))
        else:
            targets.append(p)
    return targets


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("paths", nargs="+", type=Path, help="test files and/or directories to lint")
    parser.add_argument(
        "--prod-module",
        action="append",
        default=[],
        help="extra bare module name that counts as a real production import (repeatable)",
    )
    parser.add_argument(
        "--allowlist",
        type=Path,
        default=None,
        help="file of grandfathered relative paths (one per line, '#' comments) exempt from failing",
    )
    parser.add_argument(
        "--advisory", action="store_true", help="report violations but always exit 0"
    )
    args = parser.parse_args(argv)

    prod_modules = frozenset(args.prod_module)
    allow: set[str] = set()
    if args.allowlist and args.allowlist.exists():
        for line in args.allowlist.read_text(encoding="utf-8").splitlines():
            stripped = line.strip()
            if stripped and not stripped.startswith("#"):
                allow.add(stripped)

    targets = _iter_targets([Path(p) for p in args.paths])
    violations: list[ShapeReport] = []
    for target in targets:
        report = analyze_file(target, prod_modules)
        rel = _relpath(target)
        if report.is_violation and rel not in allow:
            violations.append(report)

    for report in violations:
        print(f"VIOLATION fake-only test module: {_relpath(report.path)}")
        print(f"  fake signal:       {', '.join(report.fake_evidence) or '(none)'}")
        print("  production signal: (none — never imports/exercises the real module)")

    if not violations:
        print(f"lint_test_shape: OK — {len(targets)} module(s) checked, no fake-only suites")
        return 0

    print(f"lint_test_shape: {len(violations)} fake-only test module(s) flagged")
    return 0 if args.advisory else 1


def _relpath(path: Path) -> str:
    try:
        return str(path.resolve().relative_to(Path.cwd().resolve()))
    except ValueError:
        return str(path)


if __name__ == "__main__":
    raise SystemExit(main())
