"""Credential-free drift guard for the committed board census (#1020).

`board_census.py --check` already compares the committed census against the
LIVE GitHub Projects API -- but it deliberately prints SKIPPED and exits 0
when no `project`-scoped token is available, which is every normal CI run
(DECISIONS `{#board-census-shape-only-live-skip-424}`). That posture is
correct and is not changed here; its consequence is that a drift can sit
unnoticed for months, which is exactly what happened: the committed census
went two board migrations stale between 2026-07-14 and 2026-09-19 while the
live leg reported nothing on every run.

This module closes that gap with an invariant that needs no network and no
credentials, so it gives signal on every CI run: whatever the census records
must agree with the vocabulary `sdlc-schema.json` declares. `sdlc-schema.json`
is the source of truth for board Status vocabulary (DECISIONS
`{#board-vocabulary-schema-is-truth-584}`); the census is a snapshot of the
live boards. When the two disagree, either the snapshot is stale or a board
drifted from the contract, and both are worth failing over.

The live comparison remains available here as an opt-in leg, enabled with
`BOARD_SCHEMA_LIVE=1`, and is skipped otherwise.
"""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path
from typing import Any

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
CONFIG_DIR = REPO_ROOT / "plugins" / "mission-control" / "config"
BOARD_SCHEMA_PATH = CONFIG_DIR / "board-schema.json"
SDLC_SCHEMA_PATH = CONFIG_DIR / "sdlc-schema.json"
PROJECT_MAPPINGS_PATH = CONFIG_DIR / "project-mappings.json"

# Status names the board-stage migration (W13) renamed out of existence. None
# may appear as a Status option on any live board; `sdlc-schema.json`'s own
# stage_flow note says so in as many words.
RETIRED_STATUS_NAMES = frozenset({"Idea", "Ready", "Active", "Done", "Todo", "Committed", "Parked"})


def _load(path: Path) -> dict[str, Any]:
    loaded: dict[str, Any] = json.loads(path.read_text(encoding="utf-8"))
    return loaded


@pytest.fixture(scope="module")
def board_schema() -> dict[str, Any]:
    return _load(BOARD_SCHEMA_PATH)


@pytest.fixture(scope="module")
def stage_flow() -> dict[str, Any]:
    workflows = _load(SDLC_SCHEMA_PATH)["workflows"]
    return dict(workflows["stage_flow"])


@pytest.fixture(scope="module")
def census_keys_by_board_key() -> dict[str, str]:
    """Map each schema board key to the census key that holds it.

    The census is keyed by the project name in `project-mappings.json`;
    `sdlc-schema.json` keys its `boards` block by board key. The two can
    diverge, and they coincide today only because every mapping sets
    `board_key` explicitly -- so cross-walk through `sdlc_manager`'s own
    `_project_board_key` rather than re-implementing its fallback here. A
    reimplementation would miss its `mount-olympus` -> `olympus` special case
    and drift from the function it claims to mirror.
    """
    sys.path.insert(0, str(REPO_ROOT / "plugins" / "mission-control" / "scripts"))
    import sdlc_manager  # noqa: PLC0415

    projects = _load(PROJECT_MAPPINGS_PATH)["projects"]
    return {sdlc_manager._project_board_key(name, proj): name for name, proj in projects.items()}


def _board_fields(
    board_schema: dict[str, Any], census_keys_by_board_key: dict[str, str], board_key: str
) -> dict[str, Any]:
    census_key = census_keys_by_board_key[board_key]
    return dict(board_schema["boards"][census_key]["fields"])


def _option_names(field: dict[str, Any]) -> set[str]:
    return {opt["name"] for opt in field.get("options", [])}


def _active_board_keys() -> list[str]:
    boards = _load(SDLC_SCHEMA_PATH)["boards"]
    return sorted(key for key, board in boards.items() if board.get("status") == "active")


ACTIVE_BOARD_KEYS = _active_board_keys()

# Every guard below is parametrized over ACTIVE_BOARD_KEYS. An empty list would
# collect zero cases and report "passed" -- a drift guard that silently covers
# nothing, which is the same failure class this module exists to catch. Assert
# the list is populated, and pin the count so a board appearing or disappearing
# is a deliberate edit rather than a quiet loss of coverage.
EXPECTED_ACTIVE_BOARD_COUNT = 3


def test_the_guard_actually_covers_the_active_boards() -> None:
    assert ACTIVE_BOARD_KEYS, (
        "no board in sdlc-schema.json is marked active, so every guard in this "
        "module collects zero cases and passes vacuously"
    )
    assert len(ACTIVE_BOARD_KEYS) == EXPECTED_ACTIVE_BOARD_COUNT, (
        f"expected {EXPECTED_ACTIVE_BOARD_COUNT} active boards, found "
        f"{len(ACTIVE_BOARD_KEYS)}: {ACTIVE_BOARD_KEYS}. If a board was added or "
        "retired on purpose, update EXPECTED_ACTIVE_BOARD_COUNT in the same change."
    )


def test_every_active_board_is_present_in_the_census(
    board_schema: dict[str, Any], census_keys_by_board_key: dict[str, str]
) -> None:
    """A board the schema calls active but the census never saw is a census
    that silently stopped covering it."""
    for board_key in ACTIVE_BOARD_KEYS:
        assert board_key in census_keys_by_board_key, (
            f"schema board {board_key!r} has no entry in project-mappings.json"
        )
        census_key = census_keys_by_board_key[board_key]
        assert census_key in board_schema["boards"], (
            f"board {board_key!r} (census key {census_key!r}) is missing from board-schema.json"
        )


@pytest.mark.parametrize("board_key", ACTIVE_BOARD_KEYS)
def test_census_fields_are_keyed_by_name(
    board_schema: dict[str, Any], census_keys_by_board_key: dict[str, str], board_key: str
) -> None:
    """`fields` is a mapping, so a consumer can index one field by name (#1020).

    Fails against a census written before that change, whose `fields` is a list.
    """
    fields = _board_fields(board_schema, census_keys_by_board_key, board_key)
    assert isinstance(fields, dict), f"{board_key}: fields must be a mapping, got {type(fields)}"
    for name, field in fields.items():
        assert field.get("name") == name, (
            f"{board_key}: field keyed {name!r} records name {field.get('name')!r}"
        )


@pytest.mark.parametrize("board_key", ACTIVE_BOARD_KEYS)
def test_status_options_match_the_declared_stage_flow_statuses(
    board_schema: dict[str, Any],
    stage_flow: dict[str, Any],
    census_keys_by_board_key: dict[str, str],
    board_key: str,
) -> None:
    """Compare as SETS: the census sorts options by name, the schema lists them
    in lifecycle order, so an ordered comparison is red on a correct file."""
    fields = _board_fields(board_schema, census_keys_by_board_key, board_key)
    assert "Status" in fields, f"{board_key}: census records no Status field"
    assert _option_names(fields["Status"]) == set(stage_flow["statuses"]), (
        f"{board_key}: Status options disagree with sdlc-schema.json stage_flow.statuses"
    )


@pytest.mark.parametrize("board_key", ACTIVE_BOARD_KEYS)
def test_stage_options_match_the_declared_stage_flow_stages(
    board_schema: dict[str, Any],
    stage_flow: dict[str, Any],
    census_keys_by_board_key: dict[str, str],
    board_key: str,
) -> None:
    """Also compared as a set, for the same reason."""
    fields = _board_fields(board_schema, census_keys_by_board_key, board_key)
    assert "Stage" in fields, f"{board_key}: census records no Stage field"
    assert _option_names(fields["Stage"]) == set(stage_flow["stages"]), (
        f"{board_key}: Stage options disagree with sdlc-schema.json stage_flow.stages"
    )


@pytest.mark.parametrize("board_key", ACTIVE_BOARD_KEYS)
def test_no_retired_status_name_survives(
    board_schema: dict[str, Any], census_keys_by_board_key: dict[str, str], board_key: str
) -> None:
    """Exact-name membership, never substring: `Ready for Active`, `Ready for
    Planning` and `Ready to merge` all contain the retired name `Ready`, and
    the Stage field legitimately carries an option called `Active`."""
    fields = _board_fields(board_schema, census_keys_by_board_key, board_key)
    leaked = _option_names(fields["Status"]) & RETIRED_STATUS_NAMES
    assert not leaked, f"{board_key}: retired status name(s) still recorded: {sorted(leaked)}"


@pytest.mark.skipif(
    os.environ.get("BOARD_SCHEMA_LIVE") != "1",
    reason="live board comparison is opt-in; set BOARD_SCHEMA_LIVE=1 (needs a project-scoped token)",
)
def test_committed_census_matches_the_live_boards(board_schema: dict[str, Any]) -> None:
    """The opt-in live leg. `board_census.py --check` is the same comparison
    with a skip-on-no-credential posture; this one is allowed to fail because
    the operator asked for it explicitly."""
    sys.path.insert(0, str(REPO_ROOT / "plugins" / "mission-control" / "scripts"))
    import board_census  # noqa: PLC0415

    fresh = board_census.derive_census(board_census._tracked_projects())
    assert board_schema == fresh, (
        "board-schema.json has drifted from the live boards; "
        "re-run `python3 plugins/mission-control/scripts/board_census.py --write`"
    )
