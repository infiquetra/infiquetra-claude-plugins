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

# The prefixes whose boundaries announce, in the order a run crosses them. `landed` is absent by
# decision, not by omission -- see `test_the_landed_rung_is_retired`.
LADDER_ORDER = ("plan", "docreview", "work", "fix", "codereview")


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


def test_no_rung_reaches_the_verify_stage_by_any_door() -> None:
    """The whole of the W-D2 repair, in one assertion.

    Verify is entered only after merge PLUS the applicable non-production deployment, or after
    installed or published artifact verification when nothing deploys. Orchestrate can check neither
    conjunct: `cmd_land` merges onto the run branch rather than the default branch, and the module
    carries no deployment or artifact-verification signal at all. So NO rung may reach that stage --
    not through `codereview`, which carried it before this change, and not through `landed`, which
    carried it briefly during it. Pinning the stage rather than a key closes both doors and any
    third one a later edit might open.
    """
    orchestrate = _orchestrate()
    offenders = [key for key, rung in orchestrate.DEFAULT_STATUS_MAP.items() if rung[0] == "Verify"]
    assert offenders == [], f"rungs reaching the Verify stage: {offenders}"
    for prefix in orchestrate.DEFAULT_STATUS_MAP:
        stage, _status = orchestrate.mapped_status(f"{prefix}-52-build")
        assert stage != "Verify", f"{prefix!r} submits Verify with neither conjunct checked"


def test_the_landed_rung_is_retired() -> None:
    """`landed` carries no rung, and a `landed-*` unit takes the ordinary unmapped skip.

    Retired rather than gated: a gate on W-D2 would be permanently false here, which is a dead key
    with extra code rather than a safeguard. Retired rather than remapped to `Active`/`Integrating`:
    issue #919's approved board transition contract has no `Integrating` row, so adding one extends
    a contract the operator approved, while retiring only removes a violation. Reversible -- restore
    the key with whatever rung the operator approves.
    """
    orchestrate = _orchestrate()
    assert "landed" not in orchestrate.DEFAULT_STATUS_MAP
    assert orchestrate.mapped_status("landed-52") is None
    assert orchestrate.mapped_status("landed") is None


def test_the_source_carries_no_codereview_to_verify_mapping() -> None:
    """A textual backstop: the entry must not reappear anywhere in the module, map or not.

    The pattern must match the CURRENT shape, not the one the change retired. A rung is now a
    two-element tuple, so a reintroduction reads `"codereview": ("Verify", ...)` -- and a backstop
    that only matched the old bare-string form `"codereview": "Verify"` could never fire again on
    anything a reintroduction would actually look like.
    """
    source = SCRIPT.read_text(encoding="utf-8")
    reintroduced = re.search(
        r'"codereview"\s*:\s*(?:"Verify"|[(\[]\s*"Verify")',
        source,
    )
    assert not reintroduced, "the codereview -> Verify mapping was reintroduced"


def test_the_backstop_fires_on_both_shapes() -> None:
    """Control: prove the pattern above catches a reintroduction in either shape.

    A backstop asserting an absence is green on a tree where it could never match anything, which
    is precisely how the retired-shape version passed while the map had been retyped underneath it.
    """
    pattern = re.compile(r'"codereview"\s*:\s*(?:"Verify"|[(\[]\s*"Verify")')
    assert pattern.search('    "codereview": ("Verify", "Awaiting verification"),')
    assert pattern.search('    "codereview": ["Verify", "Awaiting verification"],')
    assert pattern.search('    "codereview": "Verify",')
    assert not pattern.search('    "codereview": ("Active", "Code review"),')


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


def test_no_rung_reaches_the_retro_stage_either() -> None:
    """`Retro`/`Ready to close` is the coordinator's row for a child closed with its gate green.

    It sits past `Verify` in the stage flow, so a rung reaching it would skip the same rule from the
    other side."""
    orchestrate = _orchestrate()
    offenders = [key for key, rung in orchestrate.DEFAULT_STATUS_MAP.items() if rung[0] == "Retro"]
    assert offenders == [], f"rungs reaching the Retro stage: {offenders}"


def test_the_hard_coded_ladder_is_gone() -> None:
    """Replaced by the resolved vocabulary, not kept beside it — two copies drift, and this one had."""
    orchestrate = _orchestrate()
    assert not hasattr(orchestrate, "STATUS_LADDER")
    assert orchestrate.live_rungs(), "the schema must resolve from this checkout"
