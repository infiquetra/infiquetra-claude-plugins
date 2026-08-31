"""#927 U4: the Orchestrate rung pins — what must not come back, stated independently.

``tests/test_orchestrate_board_writeback.py`` proves the writeback *behaviour*: what a land submits,
what it skips, what it fails loud on. This file pins the *vocabulary* those behaviours carry, and it
does so without the writeback fixtures on purpose — a pin that shares a fixture with the thing it
guards dies the same death the guarded thing does.

Two properties are being held down:

* **``codereview`` maps to Verify nowhere.** Closed ``infiquetra/infiquetra-sdlc`` #89 (W8),
  requirement R69, puts pre-merge continuous integration, tests, code review and merge readiness all
  in the Active stage. Verify begins only after merge plus the applicable non-production deployment
  — or, when nothing deploys, after installed or published artifact verification.
* **No rung is stale.** The previous ladder was a hard-coded second copy of the board's vocabulary,
  and it had drifted so far that not one of its six values was a live ``Status`` option: every board
  write Orchestrate made halted in front of Mission Control's writer, silently. A pin against a
  hard-coded list would repeat that mistake, so these assertions resolve the schema.
"""

from __future__ import annotations

import importlib.util
import json
import re
import sys
from pathlib import Path
from types import ModuleType

ROOT = Path(__file__).resolve().parent.parent
SCRIPT = ROOT / "plugins" / "orchestrate" / "skills" / "orchestrate" / "scripts" / "orchestrate.py"
SCHEMA = ROOT / "plugins" / "mission-control" / "config" / "sdlc-schema.json"

# The prefixes whose boundaries announce, in the order a run crosses them.
LADDER_ORDER = ("plan", "docreview", "work", "fix", "codereview", "landed")


def _orchestrate() -> ModuleType:
    name = "_orchestrate_status_map_contract"
    if name in sys.modules:
        return sys.modules[name]
    spec = importlib.util.spec_from_file_location(name, SCRIPT)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


def _live_rungs() -> set[tuple[str, str]]:
    stage_statuses = json.loads(SCHEMA.read_text(encoding="utf-8"))["workflows"]["stage_flow"][
        "stage_statuses"
    ]
    return {(stage, status) for stage, options in stage_statuses.items() for status in options}


def test_codereview_does_not_map_to_verify() -> None:
    """The pin. Restoring the entry must fail here, whatever else in the module changes."""
    orchestrate = _orchestrate()
    rung = orchestrate.DEFAULT_STATUS_MAP["codereview"]
    assert rung[0] != "Verify", "code review is pre-merge and stays in the Active stage (R69)"
    assert rung == ("Active", "Code review")


def test_no_unit_name_resolves_to_a_verify_stage_before_landing() -> None:
    """Every pre-merge prefix stays out of Verify, not just the one that carried it."""
    orchestrate = _orchestrate()
    for prefix in ("plan", "docreview", "work", "fix", "codereview"):
        stage, _status = orchestrate.mapped_status(f"{prefix}-52-build")
        assert stage != "Verify", f"{prefix!r} submits Verify before the unit has landed"


def test_the_source_carries_no_codereview_to_verify_mapping() -> None:
    """A textual backstop: the entry must not reappear anywhere in the module, map or not."""
    source = SCRIPT.read_text(encoding="utf-8")
    assert not re.search(r'"codereview"\s*:\s*"?Verify', source), (
        "the codereview -> Verify mapping was reintroduced"
    )


def test_the_map_carries_exactly_the_announcing_prefixes() -> None:
    """``codereview`` is remapped, never deleted: deleting the key would silently stop announcing
    at a boundary that announces today, reported as 'no status mapped' rather than as a
    regression."""
    orchestrate = _orchestrate()
    assert set(orchestrate.DEFAULT_STATUS_MAP) == set(LADDER_ORDER)


def test_every_rung_is_a_live_stage_status_pair() -> None:
    orchestrate = _orchestrate()
    live = _live_rungs()
    off = [
        (key, tuple(rung))
        for key, rung in orchestrate.DEFAULT_STATUS_MAP.items()
        if tuple(rung) not in live
    ]
    assert off == [], f"rungs the board does not carry: {off}"


def test_the_rungs_are_stage_monotonic() -> None:
    """No boundary may move a card backwards through the stage flow."""
    stages = list(
        json.loads(SCHEMA.read_text(encoding="utf-8"))["workflows"]["stage_flow"]["stage_statuses"]
    )
    orchestrate = _orchestrate()
    indices = [stages.index(orchestrate.DEFAULT_STATUS_MAP[key][0]) for key in LADDER_ORDER]
    assert indices == sorted(indices), dict(zip(LADDER_ORDER, indices, strict=True))


def test_landed_is_verify_and_never_retro() -> None:
    """``landed`` is the post-merge unit announce, not close-out.

    Retro/Ready to close is the coordinator's row for a child closed with its gate green. Mapping
    ``landed`` there would move Stage past Verify and skip the merge-plus-deploy-or-artifact rule
    this very change is enforcing on Orchestrate."""
    orchestrate = _orchestrate()
    assert orchestrate.DEFAULT_STATUS_MAP["landed"] == ("Verify", "Awaiting verification")


def test_the_hard_coded_ladder_is_gone() -> None:
    """Replaced by the resolved vocabulary, not kept beside it — two copies drift, and this one had."""
    orchestrate = _orchestrate()
    assert not hasattr(orchestrate, "STATUS_LADDER")
    assert orchestrate.live_rungs(), "the schema must resolve from this checkout"
