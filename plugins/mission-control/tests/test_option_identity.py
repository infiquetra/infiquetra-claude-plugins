"""Tests for the identity-preserving single-select option-set helper.

Acceptance selectors (match ``pytest -k`` from the plugins repository root):

  * option_identity — a retained option must carry its existing id, and
    dropping a live option from the submission is refused; both BEFORE the
    mutation leaves the process, because the API overwrites the whole option
    set and either slip clears item values.
  * option_set_complete_list — the submitted list must be the complete
    desired set (the naive one-option write is refused outright).

All GitHub/GraphQL calls are patched at the sdlc_manager-module level — no
network. The destructive mutation constant is `QUERY_UPDATE_FIELD_OPTIONS`;
every error-path assertion is that this constant is NEVER sent.
"""

from __future__ import annotations

import sys
from pathlib import Path
from unittest.mock import patch

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))

import sdlc_manager  # noqa: E402

FIELD_ID = "PVTF_status"


def _opt(opt_id: str, name: str, color: str = "GRAY", description: str | None = None):
    entry = {"id": opt_id, "name": name, "color": color}
    if description is not None:
        entry["description"] = description
    return entry


CURRENT = [
    _opt("OPT_idea", "Idea", "GRAY"),
    _opt("OPT_shaping", "Shaping", "YELLOW"),
    _opt("OPT_ready", "Ready", "GREEN"),
]


def _mutation_calls(mock_graphql):
    return [
        c
        for c in mock_graphql.call_args_list
        if c.args[0] == sdlc_manager.QUERY_UPDATE_FIELD_OPTIONS
    ]


def _identity_error(match):
    return pytest.raises(sdlc_manager.OptionSetIdentityError, match=match)


def test_option_identity_rejects_submission_omitting_a_live_option() -> None:
    """Dropping a live option from the submission is refused before the write."""
    desired = [_opt("OPT_idea", "Idea"), _opt("OPT_shaping", "Shaping", "YELLOW")]
    with (
        patch.object(sdlc_manager, "_graphql") as mock_graphql,
        _identity_error("omits live option"),
    ):
        sdlc_manager.update_field_single_select_options(FIELD_ID, desired, current_options=CURRENT)
    assert _mutation_calls(mock_graphql) == []


def test_option_identity_rejects_retained_option_without_existing_id() -> None:
    """A retained or renamed option submitted without its id is rejected: omitting
    the id mints a new option and clears every item value pointing at the old one."""
    retained_no_id = {"name": "Ready", "color": "GREEN"}
    desired = [
        _opt("OPT_idea", "Idea"),
        _opt("OPT_shaping", "Shaping", "YELLOW"),
        retained_no_id,
    ]
    with (
        patch.object(sdlc_manager, "_graphql") as mock_graphql,
        _identity_error("already exists"),
    ):
        sdlc_manager.update_field_single_select_options(FIELD_ID, desired, current_options=CURRENT)
    assert _mutation_calls(mock_graphql) == []


def test_option_set_complete_list_refuses_one_option_write() -> None:
    """The naive one-option add — the exact shape the removed unsafe reference page
    documented — is refused: it would replace the whole set with one option."""
    desired = [{"name": "new-initiative", "color": "PURPLE"}]
    with (
        patch.object(sdlc_manager, "_graphql") as mock_graphql,
        _identity_error("omits live option"),
    ):
        sdlc_manager.update_field_single_select_options(FIELD_ID, desired, current_options=CURRENT)
    assert _mutation_calls(mock_graphql) == []


def test_option_set_complete_list_refuses_empty_submission() -> None:
    """Empty input is ignored by the API — a silent no-op that must not read as success."""
    with (
        patch.object(sdlc_manager, "_graphql") as mock_graphql,
        _identity_error("empty option list"),
    ):
        sdlc_manager.update_field_single_select_options(FIELD_ID, [], current_options=CURRENT)
    assert _mutation_calls(mock_graphql) == []


def test_option_identity_rejects_unknown_id_not_on_live_field() -> None:
    """Only ids fetched from the live field may be submitted."""
    desired = list(CURRENT) + [_opt("OPT_bogus", "Phantom")]
    with (
        patch.object(sdlc_manager, "_graphql") as mock_graphql,
        _identity_error("does not exist"),
    ):
        sdlc_manager.update_field_single_select_options(FIELD_ID, desired, current_options=CURRENT)
    assert _mutation_calls(mock_graphql) == []


def test_option_identity_rejects_duplicate_ids_and_names() -> None:
    with (
        patch.object(sdlc_manager, "_graphql") as mock_graphql,
        _identity_error("more than once"),
    ):
        sdlc_manager.update_field_single_select_options(
            FIELD_ID,
            [_opt("OPT_idea", "Idea"), _opt("OPT_idea", "Idea (again)")],
            current_options=CURRENT,
        )
        sdlc_manager.update_field_single_select_options(
            FIELD_ID,
            [_opt("OPT_idea", "Idea"), _opt("OPT_shaping", "IDEA", "YELLOW")],
            current_options=CURRENT,
        )
    assert _mutation_calls(mock_graphql) == []


def test_option_identity_rejects_out_of_enum_colour() -> None:
    desired = [
        _opt("OPT_idea", "Idea", "MAGENTA"),
        _opt("OPT_shaping", "Shaping", "YELLOW"),
        _opt("OPT_ready", "Ready", "GREEN"),
    ]
    with (
        patch.object(sdlc_manager, "_graphql") as mock_graphql,
        _identity_error("allowed enum"),
    ):
        sdlc_manager.update_field_single_select_options(FIELD_ID, desired, current_options=CURRENT)
    assert _mutation_calls(mock_graphql) == []


def test_option_identity_rejects_missing_colour() -> None:
    """A submission must be fully explicit — a colour-less retained option could
    silently drop its colour on the overwrite."""
    partial = [
        {"id": "OPT_idea", "name": "Idea"},
        _opt("OPT_shaping", "Shaping", "YELLOW"),
        _opt("OPT_ready", "Ready", "GREEN"),
    ]
    with (
        patch.object(sdlc_manager, "_graphql") as mock_graphql,
        _identity_error("allowed enum"),
    ):
        sdlc_manager.update_field_single_select_options(FIELD_ID, partial, current_options=CURRENT)
    assert _mutation_calls(mock_graphql) == []


def test_rename_round_trip_preserves_option_ids_and_values() -> None:
    """The migration's core write: same ids, new names, plus a genuinely new option —
    every current id survives in the submitted payload and in the readback, so no
    item value is cleared."""
    desired = [
        _opt("OPT_idea", "Capturing"),
        _opt("OPT_shaping", "Discovering", "YELLOW"),
        _opt("OPT_ready", "Ready for Active", "BLUE"),
        {"name": "Blocked", "color": "RED"},
    ]
    returned = [
        _opt("OPT_idea", "Capturing"),
        _opt("OPT_shaping", "Discovering", "YELLOW"),
        _opt("OPT_ready", "Ready for Active", "BLUE"),
        _opt("OPT_new_1", "Blocked", "RED"),
    ]
    with patch.object(sdlc_manager, "_graphql") as mock_graphql:
        mock_graphql.return_value = {
            "updateProjectV2Field": {"projectV2Field": {"id": FIELD_ID, "options": returned}}
        }
        field = sdlc_manager.update_field_single_select_options(
            FIELD_ID, desired, current_options=CURRENT
        )

    calls = _mutation_calls(mock_graphql)
    assert len(calls) == 1
    submitted_options = calls[0].args[1]["options"]
    submitted_by_id = {o["id"]: o for o in submitted_options if "id" in o}
    desired_by_id = {o["id"]: o for o in desired if "id" in o}
    # Every live option id survives the round trip — identity preserved, no value cleared.
    for cur in CURRENT:
        assert submitted_by_id[cur["id"]]["name"] == desired_by_id[cur["id"]]["name"]
        assert any(o["id"] == cur["id"] for o in field["options"])
    # Only the genuinely new option omitted its id.
    assert len([o for o in submitted_options if "id" not in o]) == 1


def test_rename_is_not_mistaken_for_a_new_option() -> None:
    """Same id + new name is accepted as a rename, not rejected as a collision."""
    desired = [
        _opt("OPT_idea", "Idea", "GRAY"),
        _opt("OPT_shaping", "Shaping", "YELLOW"),
        _opt("OPT_ready", "Ready for Active", "BLUE"),
    ]
    with patch.object(sdlc_manager, "_graphql") as mock_graphql:
        mock_graphql.return_value = {
            "updateProjectV2Field": {"projectV2Field": {"id": FIELD_ID, "options": list(desired)}}
        }
        field = sdlc_manager.update_field_single_select_options(
            FIELD_ID, desired, current_options=CURRENT
        )
    names = {o["name"] for o in field["options"]}
    assert "Ready for Active" in names
    assert len(_mutation_calls(mock_graphql)) == 1


def test_genuinely_new_option_without_id_is_accepted() -> None:
    new_opt = {"name": "Blocked", "color": "RED"}
    desired = list(CURRENT) + [new_opt]
    returned = list(CURRENT) + [_opt("OPT_new_1", "Blocked", "RED")]
    with patch.object(sdlc_manager, "_graphql") as mock_graphql:
        mock_graphql.return_value = {
            "updateProjectV2Field": {"projectV2Field": {"id": FIELD_ID, "options": returned}}
        }
        field = sdlc_manager.update_field_single_select_options(
            FIELD_ID, desired, current_options=CURRENT
        )
    assert len(field["options"]) == 4


def test_post_write_readback_losing_an_id_is_refused() -> None:
    """The server returned fewer ids than submitted — refuse success, do not assume."""
    desired = list(CURRENT) + [{"name": "Blocked", "color": "RED"}]
    returned = list(CURRENT)  # the new option did not come back
    with (
        patch.object(sdlc_manager, "_graphql") as mock_graphql,
        _identity_error("readback"),
    ):
        mock_graphql.return_value = {
            "updateProjectV2Field": {"projectV2Field": {"id": FIELD_ID, "options": returned}}
        }
        sdlc_manager.update_field_single_select_options(FIELD_ID, desired, current_options=CURRENT)


def test_live_fetch_seam_reads_field_before_validating() -> None:
    """Without explicit current_options the helper reads the live field first and
    still refuses a non-conforming submission before the mutation constant is sent."""

    def side_effect(query, variables=None):
        if query == sdlc_manager.QUERY_GET_SINGLE_SELECT_FIELD:
            return {"node": {"id": FIELD_ID, "name": "Status", "options": CURRENT}}
        raise AssertionError(f"unexpected query: {query[:80]}")

    with (
        patch.object(sdlc_manager, "_graphql", side_effect=side_effect) as mock_graphql,
        _identity_error("omits live option"),
    ):
        sdlc_manager.update_field_single_select_options(
            FIELD_ID, [{"name": "Blocked", "color": "RED"}]
        )
    assert _mutation_calls(mock_graphql) == []
    assert mock_graphql.call_count == 1


def test_fields_set_options_dry_run_writes_nothing(tmp_path) -> None:
    """The CLI verb validates and --dry-run stops before any write."""
    opts_file = tmp_path / "options.json"
    opts_file.write_text(
        '[{"id": "OPT_idea", "name": "Idea", "color": "GRAY"},'
        ' {"id": "OPT_shaping", "name": "Shaping", "color": "YELLOW"},'
        ' {"id": "OPT_ready", "name": "Ready for Active", "color": "BLUE"}]',
        encoding="utf-8",
    )
    project = {"number": 2, "id": "PVT_asgard"}
    field = {
        "id": FIELD_ID,
        "name": "Status",
        "options": [{"id": o["id"], "name": o["name"]} for o in CURRENT],
    }
    with (
        patch.object(
            sdlc_manager,
            "load_config",
            return_value={"project_mappings": {"projects": {"asgard": project}}},
        ),
        patch.object(sdlc_manager, "get_project_config", return_value=project),
        patch.object(sdlc_manager, "get_project_fields", return_value=("PVT_asgard", [field])),
        patch.object(sdlc_manager, "_graphql") as mock_graphql,
    ):
        sdlc_manager.fields_set_options("asgard", "Status", str(opts_file), dry_run=True)
    assert mock_graphql.call_count == 0


def test_unsafe_reference_query_removed_from_mission_control() -> None:
    """Regression for issue #94 M2/M3: the documented one-option mutation — which
    under the API's whole-set overwrite would clear every card value on a
    362-card field — must not survive anywhere in the plugin as guidance."""
    reference = (
        Path(__file__).resolve().parent.parent
        / "skills"
        / "board"
        / "references"
        / "graphql-queries.md"
    )
    text = reference.read_text(encoding="utf-8")
    # Composed at runtime so this test file itself never carries the forbidden
    # token — the acceptance grep over plugins/mission-control/ must return nothing.
    unsafe_constant = "QUERY_" + "CREATE" + "_FIELD_OPTION"
    assert unsafe_constant not in text
    assert "singleSelectOptions: [{ name: $name" not in text
    # The safe entry point is documented in its place.
    assert "QUERY_UPDATE_FIELD_OPTIONS" in text
    assert "update_field_single_select_options" in text
