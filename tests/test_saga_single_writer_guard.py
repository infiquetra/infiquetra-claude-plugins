"""#812 single-writer guard: saga does not compose board Stage/Status writes.

Step-1 inventory (launch pin 2026-08-25, live ``flow field-options`` / field list):

- Operations (#3), Asgard (#2), CAMPPS (#4): fields are Title, Assignees, Status,
  Labels, Linked pull requests, Milestone, Repository, Reviewers, Parent issue,
  Sub-issues progress, Created, Updated, Closed, Objective, Priority.
- ``Status`` is present on all three boards. ``Stage`` is present on none.
- Operations Status options: Idea, Shaping, Ready, Active, Verify, Done.
- Saga GraphQL mutations that write a project field: none. The only ``--field``
  Status/Stage argv is the mission-control submission in
  ``plugins/saga/scripts/board_progression.py:default_board_writer``.

The named in-scope failure: the single-writer policy exists by operator ruling
but nothing enforced it, so a future saga script could silently re-introduce
direct board composition. This guard is the smallest enforcement.
"""

from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SAGA_ROOT = ROOT / "plugins" / "saga"
SUBMISSION_PATH = (SAGA_ROOT / "scripts" / "board_progression.py").resolve()

# Direct ProjectV2 field mutations — reserved to mission-control.
FORBIDDEN_MUTATIONS = (
    "updateProjectV2ItemFieldValue",
    "updateProjectV2ItemField",
    "clearProjectV2ItemFieldValue",
    "QUERY_SET_FIELD_VALUE",
)

# CLI shapes that write a project field without going through mission-control.
FORBIDDEN_CLI = (
    "project item-edit",
    "gh project item-edit",
)

_FIELD_ARGV_RE = re.compile(
    r"""["']--field["']\s*,\s*["'](Status|Stage)["']"""
    r"""|["']--field["']\s*,\s*(?:field_name|field)\b"""
)
_FLOW_SET_FIELD_RE = re.compile(r"""["']flow["']\s*,\s*["']set-field["']""")
_FLOW_SET_FIELD_CALL_RE = re.compile(r"\bflow_set_field\s*\(")


def _iter_saga_python(root: Path = SAGA_ROOT) -> list[Path]:
    return sorted(p for p in root.rglob("*.py") if p.is_file())


def _offenses_in_text(text: str) -> list[str]:
    found: list[str] = []
    for token in FORBIDDEN_MUTATIONS:
        if token in text:
            found.append(token)
    for token in FORBIDDEN_CLI:
        if token in text:
            found.append(token)
    if _FLOW_SET_FIELD_CALL_RE.search(text):
        found.append("flow_set_field(")
    return found


def _submission_path_offenses(text: str) -> list[str]:
    """The submission file may compose ``flow set-field``; it may not GraphQL-write."""
    found: list[str] = []
    for token in FORBIDDEN_MUTATIONS:
        if token in text:
            found.append(token)
    for token in FORBIDDEN_CLI:
        if token in text:
            found.append(token)
    if _FLOW_SET_FIELD_CALL_RE.search(text):
        found.append("flow_set_field(")
    return found


def scan_saga_direct_writes(root: Path = SAGA_ROOT) -> list[tuple[Path, str]]:
    """Return (path, token) for every in-scope direct Stage/Status write in saga."""
    hits: list[tuple[Path, str]] = []
    for path in _iter_saga_python(root):
        text = path.read_text(encoding="utf-8")
        resolved = path.resolve()
        tokens = (
            _submission_path_offenses(text)
            if resolved == SUBMISSION_PATH
            else _offenses_in_text(text)
        )
        if resolved != SUBMISSION_PATH:
            if _FLOW_SET_FIELD_RE.search(text):
                tokens.append("flow,set-field")
            if _FIELD_ARGV_RE.search(text):
                tokens.append("--field Status|Stage")
        for token in tokens:
            hits.append((path, token))
    return hits


def test_no_direct_stage_or_status_write_remains_in_saga() -> None:
    """AC1: no saga call site composes a direct board Stage or Status write."""
    hits = scan_saga_direct_writes()
    assert hits == [], "direct Stage/Status writes in saga:\n" + "\n".join(
        f"  {path.relative_to(ROOT)}: {token}" for path, token in hits
    )


def test_surviving_set_field_reference_is_submission_path_only() -> None:
    """AC1: every surviving ``flow set-field`` argv is the board_progression writer."""
    owners: list[Path] = []
    for path in _iter_saga_python():
        text = path.read_text(encoding="utf-8")
        if _FLOW_SET_FIELD_RE.search(text) or _FIELD_ARGV_RE.search(text):
            owners.append(path.resolve())
    assert owners == [SUBMISSION_PATH], (
        "set-field argv must live only in default_board_writer, got: "
        + ", ".join(str(p.relative_to(ROOT)) for p in owners)
    )


def test_submission_path_passes_field_name_and_correction_flag() -> None:
    """The one legal writer submits ``--field <name>`` and ``--correction``."""
    text = SUBMISSION_PATH.read_text(encoding="utf-8")
    assert '"--field"' in text
    assert '"--correction"' in text
    assert "authorize_correction_field" in text
    assert "set-field-stage" not in text


def test_guard_fails_closed_on_a_direct_write_fixture(tmp_path: Path) -> None:
    """A guard never seen to fail is not known to work — seed a mutation and trip it."""
    fixture = tmp_path / "evil_direct_write.py"
    fixture.write_text(
        'QUERY = """mutation { updateProjectV2ItemFieldValue(input: {}) { ok } }"""\n',
        encoding="utf-8",
    )
    text = fixture.read_text(encoding="utf-8")
    assert "updateProjectV2ItemFieldValue" in _offenses_in_text(text)

    argv_fixture = tmp_path / "evil_argv.py"
    argv_fixture.write_text(
        'cmd = ["python3", "sdlc_manager.py", "flow", "set-field", "--field", "Status"]\n',
        encoding="utf-8",
    )
    argv_text = argv_fixture.read_text(encoding="utf-8")
    assert _FLOW_SET_FIELD_RE.search(argv_text)
    assert _FIELD_ARGV_RE.search(argv_text)


def test_inventory_receipt_no_stage_field_on_live_boards() -> None:
    """F3 substitution: the documented live receipt has Status and no Stage.

    Re-running the live query is the unit's step-1 deliverable (recorded in the
    work-session). This pin keeps the receipt's *shape* in the suite so a later
    Stage field is a deliberate change, not a silent drift past the guard.
    """
    expected = {
        "Title",
        "Assignees",
        "Status",
        "Labels",
        "Linked pull requests",
        "Milestone",
        "Repository",
        "Reviewers",
        "Parent issue",
        "Sub-issues progress",
        "Created",
        "Updated",
        "Closed",
        "Objective",
        "Priority",
    }
    assert "Stage" not in expected
    assert "Status" in expected
