"""Second-opinion claim/adjudication after the #776 transport retirement.

The managed-session runner (`engine_session_runner.py`) is deleted with its tests.
This file keeps the claim-store contract that still lives in `second_opinion.py`.
"""

from __future__ import annotations

import ast
import importlib.util
import sys
from pathlib import Path
from types import ModuleType

ROOT = Path(__file__).parent.parent
SCRIPTS = ROOT / "plugins" / "saga" / "scripts"
CODE_REVIEW_SKILL = ROOT / "plugins" / "saga" / "skills" / "code-review" / "SKILL.md"
DOC_REVIEW_SKILL = ROOT / "plugins" / "saga" / "skills" / "doc-review" / "SKILL.md"


def _load(name: str, path: Path) -> ModuleType:
    if str(SCRIPTS) not in sys.path:
        sys.path.insert(0, str(SCRIPTS))
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


SO = _load("second_opinion", SCRIPTS / "second_opinion.py")


def test_dispatch_second_opinion_still_takes_an_injected_runner() -> None:
    tree = ast.parse((SCRIPTS / "second_opinion.py").read_text(encoding="utf-8"))
    found = False
    for node in ast.walk(tree):
        if isinstance(node, ast.FunctionDef) and node.name == "dispatch_second_opinion":
            found = True
            names = [arg.arg for arg in node.args.args]
            names.extend(arg.arg for arg in node.args.kwonlyargs)
            assert "runner" in names
            assert "fallback_runner" not in names
    assert found


def test_second_opinion_module_does_not_import_retired_transport() -> None:
    text = (SCRIPTS / "second_opinion.py").read_text(encoding="utf-8")
    assert "engine_session_runner" not in text
    assert "engine_offer" not in text
    assert "external_only" not in text
    assert not (SCRIPTS / "engine_session_runner.py").exists()
    assert not (SCRIPTS / "engine_offer.py").exists()
    assert not (SCRIPTS / "external_only.py").exists()


def test_review_skills_halt_instead_of_naming_a_launch_cli() -> None:
    for path in (CODE_REVIEW_SKILL, DOC_REVIEW_SKILL):
        text = path.read_text(encoding="utf-8")
        assert "engine_session_runner.py launch" not in text
        assert "HALT" in text
        assert "Orchestrate" in text
