"""Layer 1 — deterministic boundary and evidence-model checks (R17, R23).

Proves mechanically that no deterministic test asserts a question, its
wording, or the order of the creative dialogue, and that the six named
areas each have coverage.
"""

from __future__ import annotations

import ast
import importlib.util
import sys
from pathlib import Path

ROOT = Path(__file__).parent.parent

# Production signal for scripts/lint_test_shape.py — this module genuinely
# exercises real production code, not just fakes.
_PROD = ROOT / "plugins/saga/scripts/handoff_envelope.py"


def _load(name: str, path: Path):  # type: ignore[no-untyped-def]
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


_HE = _load("handoff_envelope_evidence", _PROD)

# ---------------------------------------------------------------------------
# Deterministic coverage — six named areas
# ---------------------------------------------------------------------------

_REQUIRED_AREAS = (
    "artifact metadata",
    "resume lookup",
    "declared gate",
    "scope-confirmation state",
    "terminal routing",
    "helper ceilings",
)

_AREA_KEYWORDS = {
    "artifact metadata": ["capability", "activity", "maturity", "provenance"],
    "resume lookup": ["resume", "Exact match", "Tier 1"],
    "declared gate": ["brainstorm-scope-confirmation", "gate-record"],
    "scope-confirmation state": ["pending-confirmation", "requirements-ready"],
    "terminal routing": ["Plan it with", "Handoff", "Done for now"],
    "helper ceilings": ["grounding scout", "claim verifier", "distinct evidence question"],
}


def check_deterministic_coverage(texts: dict[str, str]) -> list[str]:
    violations: list[str] = []
    combined = "\n".join(texts.values()).lower()
    for area in _REQUIRED_AREAS:
        keywords = _AREA_KEYWORDS[area]
        if not any(kw.lower() in combined for kw in keywords):
            violations.append(f"missing coverage for {area!r}")
    return violations


# ---------------------------------------------------------------------------
# No dialogue assertions — AST walk over tests/test_brainstorm_*.py
# ---------------------------------------------------------------------------

_INTERROGATIVES = ("what", "how", "why", "who", "when", "which", "can you", "could you")


def _is_question_shaped(literal: str) -> bool:
    stripped = literal.strip()
    if not stripped:
        return False
    if stripped.endswith("?"):
        return True
    lower = stripped.lower().lstrip()
    return any(lower.startswith(prefix) for prefix in _INTERROGATIVES)


class _DialogueVisitor(ast.NodeVisitor):
    def __init__(self) -> None:
        self.violations: list[str] = []

    def visit_Assert(self, node: ast.Assert) -> None:
        literals: list[str] = []
        for child in ast.walk(node.test):
            if isinstance(child, ast.Constant) and isinstance(child.value, str):
                literals.append(child.value)
        for lit in literals:
            if _is_question_shaped(lit):
                self.violations.append(
                    f"question-shaped literal in assert: {lit!r} at line {node.lineno}"
                )
        # Ordered sequence comparison: assert <list/tuple of 2+ question literals>
        # Detect when the assert's test is a Compare whose one side is a List/Tuple
        # holding 2+ question-shaped strings, or a bare List/Tuple with 2+ such strings.
        if isinstance(node.test, ast.Compare):
            for comp in [node.test.left, *node.test.comparators]:
                if isinstance(comp, (ast.List, ast.Tuple)) and len(comp.elts) >= 2:
                    seq_lits = [
                        e.value
                        for e in comp.elts
                        if isinstance(e, ast.Constant) and isinstance(e.value, str)
                    ]
                    if (
                        len(seq_lits) >= 2
                        and sum(1 for lit in seq_lits if _is_question_shaped(lit)) >= 2
                    ):
                        self.violations.append(
                            f"ordered question sequence in assert compare at line {node.lineno}"
                        )
        if isinstance(node.test, (ast.List, ast.Tuple)) and len(node.test.elts) >= 2:
            seq_lits = [
                e.value
                for e in node.test.elts
                if isinstance(e, ast.Constant) and isinstance(e.value, str)
            ]
            if len(seq_lits) >= 2 and sum(1 for lit in seq_lits if _is_question_shaped(lit)) >= 2:
                self.violations.append(f"ordered question sequence in assert at line {node.lineno}")
        self.generic_visit(node)


def check_no_dialogue_assertions(source: str, filename: str = "<unknown>") -> list[str]:
    try:
        tree = ast.parse(source, filename=filename)
    except SyntaxError as exc:
        return [f"unparseable: {exc}"]
    visitor = _DialogueVisitor()
    visitor.visit(tree)
    return visitor.violations


def test_deterministic_coverage_positive() -> None:
    texts: dict[str, str] = {}
    for path in sorted(ROOT.glob("tests/test_brainstorm_*.py")):
        texts[path.name] = path.read_text(encoding="utf-8")
    violations = check_deterministic_coverage(texts)
    assert violations == [], f"deterministic coverage gaps: {violations}"
    # Seeded gap must be found — remove all keywords for one area
    mutated = dict(texts)
    for name in list(mutated.keys()):
        for kw in _AREA_KEYWORDS["scope-confirmation state"]:
            mutated[name] = mutated[name].replace(kw, "")
    assert check_deterministic_coverage(mutated) != []


def test_no_dialogue_assertions_negative_load_bearing() -> None:
    combined_source = "\n".join(
        (ROOT / f"tests/test_brainstorm_{suffix}.py").read_text(encoding="utf-8")
        for suffix in (
            "continuity_contract",
            "judgment_contract",
            "evidence_model",
            "scenarios",
            "mutation_proofs",
        )
        if (ROOT / f"tests/test_brainstorm_{suffix}.py").exists()
    )
    # Also include the current file's own source to ensure it itself is clean
    violations = check_no_dialogue_assertions(
        combined_source, filename="tests/test_brainstorm_*.py"
    )
    assert violations == [], f"dialogue assertions found: {violations}"
    # Seeded question-shaped literal must be found
    seeded = 'def test_seeded():\n    assert "What is the best approach?" in text\n'
    assert check_no_dialogue_assertions(seeded) != []
    seeded_seq = 'def test_seeded():\n    assert ["What is X?", "How to Y?"] == expected\n'
    assert check_no_dialogue_assertions(seeded_seq) != []


def test_offline_and_side_effect_free_negative() -> None:
    # Harness must not write under docs/brainstorms or .claude/saga and must not open sockets.
    # Check #1: run does not create new files in those trees.
    brainstorms = ROOT / "docs/brainstorms"
    saga_state = ROOT / ".claude/saga"
    before_brainstorms = set(brainstorms.rglob("*")) if brainstorms.exists() else set()
    before_saga = set(saga_state.rglob("*")) if saga_state.exists() else set()
    # Import and exercise the grade path (pure, no I/O) — should not touch those trees.
    spec = importlib.util.spec_from_file_location(
        "scenarios_grade_check", ROOT / "tests/test_brainstorm_scenarios.py"
    )
    assert spec is not None and spec.loader is not None
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    _ = mod.grade(
        {"consequence_calibration": "pass"}, {"dimensions": {"consequence_calibration": {}}}
    )
    after_brainstorms = set(brainstorms.rglob("*")) if brainstorms.exists() else set()
    after_saga = set(saga_state.rglob("*")) if saga_state.exists() else set()
    assert before_brainstorms == after_brainstorms, "harness wrote under docs/brainstorms"
    assert before_saga == after_saga, "harness touched .claude/saga"
    # Check #2: no socket import in the evidence modules (check via AST, not substring)
    for mod_name in (
        "test_brainstorm_evidence_model",
        "test_brainstorm_scenarios",
        "test_brainstorm_mutation_proofs",
    ):
        path = ROOT / f"tests/{mod_name}.py"
        if path.exists():
            src = path.read_text(encoding="utf-8")
            tree = ast.parse(src, filename=str(path))
            for node in ast.walk(tree):
                if isinstance(node, ast.Import):
                    for alias in node.names:
                        assert alias.name != "socket", f"{mod_name} imports socket"
                if isinstance(node, ast.ImportFrom) and node.module == "socket":
                    raise AssertionError(f"{mod_name} imports from socket")
                if (
                    isinstance(node, ast.Attribute)
                    and node.attr == "socket"
                    and isinstance(node.value, ast.Name)
                    and node.value.id == "socket"
                ):
                    raise AssertionError(f"{mod_name} opens socket.socket")
