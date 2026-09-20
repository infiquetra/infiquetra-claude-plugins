"""What survives the retirement of Saga's in-process second-opinion machinery.

Two removals converge here. Issue #776 deleted the managed-session runner
(`engine_session_runner.py`) with its tests. Issue #938 then deleted
`plugins/saga/scripts/second_opinion.py`, which carried Work's in-process second-opinion offer and
its feature-private dispatch, sidecar, streak and state machinery.

This file no longer loads either of them. It keeps the three contracts that outlived both: the
review skills halt rather than naming a launch command line, the operator-absence gate record
survives, and an advisory reviewer or a panel can never satisfy a gate. The tombstone test below
now names all four deleted files, so none of them can quietly return.
"""

from __future__ import annotations

import importlib.util
import re
import sys
from pathlib import Path
from types import ModuleType

ROOT = Path(__file__).parent.parent
SCRIPTS = ROOT / "plugins" / "saga" / "scripts"
CODE_REVIEW_SKILL = ROOT / "plugins" / "saga" / "skills" / "code-review" / "SKILL.md"
DOC_REVIEW_SKILL = ROOT / "plugins" / "saga" / "skills" / "doc-review" / "SKILL.md"
GATE_RECORD = re.compile(
    r"<!-- gate-record: id=(?P<id>[^\s]+) absence=(?P<absence>[^\s]+) "
    r"transport=(?P<transport>[^\s]+) -->"
)


def _load(name: str, path: Path) -> ModuleType:
    if str(SCRIPTS) not in sys.path:
        sys.path.insert(0, str(SCRIPTS))
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


D = _load("engine_dispatch_for_second_opinion_tombstones", SCRIPTS / "engine_dispatch.py")


def test_the_retired_second_opinion_modules_stay_deleted() -> None:
    """Issue #776's transport and issue #938's in-process offer are both gone from disk.

    A tombstone rather than a behaviour test: each of these four modules was deleted by a card
    that proved it had no live consumer, so the failure this guards against is one of them coming
    back unnoticed alongside unrelated work.
    """
    for name in (
        "engine_session_runner.py",
        "engine_offer.py",
        "external_only.py",
        "second_opinion.py",
    ):
        assert not (SCRIPTS / name).exists(), f"{name} came back; it was deleted deliberately"


def test_review_skills_halt_instead_of_naming_a_launch_cli() -> None:
    for path in (CODE_REVIEW_SKILL, DOC_REVIEW_SKILL):
        text = path.read_text(encoding="utf-8")
        assert "engine_session_runner.py launch" not in text
        assert "HALT" in text
        assert "Orchestrate" in text


def test_operator_absence_gate_record_survives_the_transport_retirement() -> None:
    """Only the engine-offer record was retired; #371's interaction contract stayed.

    The repo-wide lint checks that a marker's vocabulary is legal, not that this
    marker still says HALT, so without this pin a swap to `absence=escalate` lints
    clean.
    """
    code_review = CODE_REVIEW_SKILL.read_text(encoding="utf-8")
    records = {m.group("id"): m.groupdict() for m in GATE_RECORD.finditer(code_review)}
    assert records["code-review-interaction"] == {
        "id": "code-review-interaction",
        "absence": "HALT",
        "transport": "ask-user-question",
    }
    assert "code-review-engine-offer" not in records
    assert "never consent" in code_review


def test_advisory_reviewer_and_panel_remain_non_gating() -> None:
    """An advisory seat cannot satisfy a gate; #776 moved its transport, not its authority."""
    assert frozenset({"advisory-reviewer", "panel"}) == D.NON_GATING_ROLE_KINDS
