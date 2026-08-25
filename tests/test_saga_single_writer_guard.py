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

import importlib.util
import re
import sys
from pathlib import Path
from types import ModuleType

ROOT = Path(__file__).resolve().parent.parent
SAGA_ROOT = ROOT / "plugins" / "saga"
SCRIPTS = SAGA_ROOT / "scripts"
SUBMISSION_PATH = (SCRIPTS / "board_progression.py").resolve()


def _load(name: str) -> ModuleType:
    if str(SCRIPTS) not in sys.path:
        sys.path.insert(0, str(SCRIPTS))
    spec = importlib.util.spec_from_file_location(name, SCRIPTS / f"{name}.py")
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


RC = _load("reversibility_certificate")

# The step-1 live receipt as DATA, not as a sentence in a docstring. Every single-select and
# built-in field the three boards carried on 2026-08-25. The tests below read the real
# certificate against this constant, so widening the correction allowlist or recording a newly
# created Stage field both trip the suite instead of passing silently.
LIVE_BOARD_FIELDS = frozenset(
    {
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
)

# Correction field names the certificate allows that the live boards do NOT yet carry. Every
# such name is dead until the field is created; keeping the set explicit is what makes a later
# Stage field a deliberate two-line edit rather than a silent drift.
ALLOWED_NOT_YET_LIVE = frozenset({"Stage"})

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


def scan_saga_direct_writes(root: Path = SAGA_ROOT) -> list[tuple[Path, str]]:
    """Return (path, token) for every in-scope direct Stage/Status write in saga."""
    hits: list[tuple[Path, str]] = []
    for path in _iter_saga_python(root):
        text = path.read_text(encoding="utf-8")
        resolved = path.resolve()
        # Every saga file, submission path included, is forbidden the GraphQL/`gh project`
        # writes and the in-process `flow_set_field(` call. The ONLY exemption the submission
        # path earns is composing the `flow set-field` argv below — which is the whole point
        # of `default_board_writer`. Keeping one offense helper means that exemption lives in
        # exactly one place instead of drifting between two identical-bodied functions.
        tokens = _offenses_in_text(text)
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


def test_correction_allowlist_is_covered_by_the_live_field_receipt() -> None:
    """F3 substitution: every correction field is either live today or recorded as not-live.

    The receipt is only evidence if something reads it. This asserts the REAL
    ``reversibility_certificate.CORRECTION_FIELDS`` against the live field list, so
    widening the allowlist to a field nobody inventoried fails here.
    """
    unaccounted = set(RC.CORRECTION_FIELDS) - LIVE_BOARD_FIELDS - ALLOWED_NOT_YET_LIVE
    assert unaccounted == set(), (
        "correction fields with no entry in the live receipt and no not-yet-live record: "
        + ", ".join(sorted(unaccounted))
    )
    assert "Status" in RC.CORRECTION_FIELDS
    assert "Status" in LIVE_BOARD_FIELDS


def test_stage_is_allowlisted_by_name_and_is_not_a_live_field() -> None:
    """F3 substitution: Stage is a name on the allowlist, not a field on any board.

    Creating a Stage field means adding it to ``LIVE_BOARD_FIELDS`` and dropping it from
    ``ALLOWED_NOT_YET_LIVE``; this test fails until both halves are done, which is exactly
    the deliberate change the receipt is meant to force.
    """
    assert "Stage" in RC.CORRECTION_FIELDS
    assert "Stage" in ALLOWED_NOT_YET_LIVE
    assert "Stage" not in LIVE_BOARD_FIELDS
    assert ALLOWED_NOT_YET_LIVE.isdisjoint(LIVE_BOARD_FIELDS), (
        "a field cannot be both live and recorded as not-yet-live"
    )


def test_correction_allowlist_excludes_the_operator_owned_fields() -> None:
    """Initiative / Objective / Priority stay operator-owned: never a saga correction."""
    for operator_field in ("Objective", "Priority", "Initiative", "Milestone", "Assignees"):
        assert operator_field not in RC.CORRECTION_FIELDS, (
            f"{operator_field} must not be submittable as a saga correction"
        )
