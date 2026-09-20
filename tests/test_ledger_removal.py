"""Guards for issue 1028's ledger removal and its three recorded deferrals.

Card 1028 names four ledgers. One is removed here; three are deferred to issue 1030, each because
removing it would mean deleting or rewriting modules this card does not name. Both halves are
guarded, and the deferral half matters as much as the removal: a module removed early takes issue
1030's work with it and leaves a surviving command importing nothing, which is the failure that
card's own importability test exists to catch — after the fact.

The reading is deliberately about IMPORTS, not about the word. ``review_consensus.py`` carries a
field called ``evidence_ledger`` that is a plain mapping of evidence keys to values and has nothing
to do with the module of that name; counting occurrences instead of imports is what made the
module look like it had eight production readers when it has one.
"""

from __future__ import annotations

import ast
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
SCRIPTS = REPO_ROOT / "plugins" / "saga" / "scripts"
REFERENCES = REPO_ROOT / "plugins" / "saga" / "references"
RUN_RECORD_DOC = REFERENCES / "run-record.md"

REMOVED = ("effort_ledger",)
DEFERRED_TO_1030 = ("evidence_ledger", "run_ledger", "dispatch_settlement")

SEARCH_ROOTS = (
    REPO_ROOT / "plugins",
    REPO_ROOT / "tests",
    REPO_ROOT / "scripts",
    REPO_ROOT / "tools",
)


def _python_files() -> list[Path]:
    found: list[Path] = []
    for root in SEARCH_ROOTS:
        if root.is_dir():
            found.extend(sorted(root.rglob("*.py")))
    return found


def _imported_names(path: Path) -> set[str]:
    """Every module name this file imports, by parsing rather than by grepping."""
    try:
        tree = ast.parse(path.read_text(encoding="utf-8"))
    except (OSError, SyntaxError):
        return set()
    names: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            names.update(alias.name.split(".")[0] for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            names.add(node.module.split(".")[0])
    return names


class TestTheRemovedLedger:
    @pytest.mark.parametrize("module", REMOVED)
    def test_the_module_file_is_gone(self, module: str) -> None:
        assert not (SCRIPTS / f"{module}.py").exists()

    def test_its_policy_file_went_with_it(self) -> None:
        assert not (REFERENCES / "effort-policy.yaml").exists()

    @pytest.mark.parametrize("module", REMOVED)
    def test_nothing_imports_it_any_more(self, module: str) -> None:
        importers = [
            str(path.relative_to(REPO_ROOT))
            for path in _python_files()
            if module in _imported_names(path)
        ]
        assert importers == [], f"{module} was removed but is still imported by: {importers}"

    @pytest.mark.parametrize("module", REMOVED)
    def test_no_document_still_tells_a_reader_to_run_it(self, module: str) -> None:
        """A dangling command in a skill is worse than a missing one: an agent will try it."""
        offenders: list[str] = []
        for path in sorted((REPO_ROOT / "plugins").rglob("*.md")):
            if path.name == "CHANGELOG.md":
                continue
            for number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
                if f"{module}.py " in line and "python3" in line:
                    offenders.append(f"{path.relative_to(REPO_ROOT)}:{number}")
        assert offenders == [], f"a document still invokes the removed {module}: {offenders}"


class TestTheDeferredLedgers:
    """Deferred means STILL THERE. A premature removal fails here, not in issue 1030's gate."""

    @pytest.mark.parametrize("module", DEFERRED_TO_1030)
    def test_the_module_is_still_present(self, module: str) -> None:
        assert (SCRIPTS / f"{module}.py").is_file(), (
            f"{module} is deferred to issue 1030; removing it here takes that card's work with it"
        )

    @pytest.mark.parametrize("module", DEFERRED_TO_1030)
    def test_the_deferral_is_recorded_where_the_next_reader_looks(self, module: str) -> None:
        text = RUN_RECORD_DOC.read_text(encoding="utf-8")
        row = next(
            (
                line
                for line in text.splitlines()
                if f"`{module}.py`" in line and line.startswith("|")
            ),
            "",
        )
        assert row, f"the run-record replacement table has no row for {module}"
        assert "deferred to issue 1030" in row, (
            f"the row for {module} does not record the deferral, so the next reader cannot tell a "
            "plan from a fact"
        )

    def test_the_evidence_ledgers_sole_production_importer_is_the_one_named_in_the_deferral(
        self,
    ) -> None:
        """The reason the deferral exists, checked rather than asserted in prose."""
        importers = [
            str(path.relative_to(REPO_ROOT))
            for path in _python_files()
            if "evidence_ledger" in _imported_names(path)
            and not str(path).endswith("evidence_ledger.py")
            and "/tests/" not in str(path)
            and not path.name.startswith("test_")
        ]
        assert importers == ["plugins/saga/scripts/closure_gate.py"]
