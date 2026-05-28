"""Tests for the `flow` subcommand group helpers.

These tests focus on the *logic* of the flow helpers — argument validation,
idempotency handling, error classification — without making real GitHub or
GraphQL calls. The `_gh`, `_graphql`, `_rest_get`, `_rest_post` helpers are
patched at the sdlc_manager-module level.

End-to-end tests (real `gh` calls against a fixture project) are tracked
as a P3 follow-up.
"""

import sys
from pathlib import Path
from unittest.mock import patch

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))

import sdlc_manager  # noqa: E402

# --- flow_link_sub_issue ----------------------------------------------------


def test_link_sub_issue_idempotent_on_already_exists() -> None:
    """A duplicate POST returns HTTP 422 with 'already exists'; we treat
    this as success, not failure (idempotency contract).

    Phase C foundation: the contract is now expressed via the typed
    `ApiAlreadyExists` exception (raised by `_classify_gh_error`), not
    string-matching. See test_typed_exceptions.py for the classifier tests."""
    with (
        patch.object(sdlc_manager, "_rest_get") as mock_get,
        patch.object(sdlc_manager, "_rest_post") as mock_post,
        patch.object(sdlc_manager, "_out") as mock_out,
    ):
        mock_get.side_effect = [
            {"id": 12345},  # child
            {"id": 67890, "title": "parent issue"},  # parent (no pull_request key)
        ]
        mock_post.side_effect = sdlc_manager.ApiAlreadyExists(
            "API call failed: HTTP 422 sub-issue already exists",
            status_code=422,
        )

        sdlc_manager.flow_link_sub_issue("campps-context-library", 1, "campps-mvp", 42, fmt="text")

        # Should NOT have raised; should have called _out with idempotent message
        msgs = [c.args[0] for c in mock_out.call_args_list]
        assert any("Already linked" in m for m in msgs), (
            f"Expected idempotent success message; got: {msgs}"
        )


def test_link_sub_issue_raises_on_real_error() -> None:
    """A non-422 error (auth, server, network) must propagate, not get
    swallowed as 'already exists'."""
    with (
        patch.object(sdlc_manager, "_rest_get") as mock_get,
        patch.object(sdlc_manager, "_rest_post") as mock_post,
    ):
        mock_get.side_effect = [
            {"id": 12345},
            {"id": 67890},
        ]
        mock_post.side_effect = RuntimeError("API call failed: 500 Internal Server Error")

        with pytest.raises(RuntimeError, match="500"):
            sdlc_manager.flow_link_sub_issue("campps-context-library", 1, "campps-mvp", 42, fmt="text")


def test_link_sub_issue_rejects_pr_as_parent() -> None:
    """The sub-issue API requires an issue parent, not a PR. The flow
    helper must detect this before POSTing — error message points at it."""
    with patch.object(sdlc_manager, "_rest_get") as mock_get:
        mock_get.side_effect = [
            {"id": 12345},  # child
            {
                "id": 67890,
                "pull_request": {"url": "..."},
            },  # parent has pull_request key → it's a PR
        ]
        with pytest.raises(RuntimeError, match="parent.*PR.*not an issue|Parent.*is a PR"):
            sdlc_manager.flow_link_sub_issue("campps-mvp", 1, "campps-mvp", 42, fmt="text")


def test_link_sub_issue_rejects_missing_child_db_id() -> None:
    """If the child fetch returns no integer id (corrupt payload, network
    truncation), the helper must raise — never POST with a bad sub_issue_id."""
    with patch.object(sdlc_manager, "_rest_get") as mock_get:
        mock_get.return_value = {"id": None}
        with pytest.raises(RuntimeError, match="no integer 'id'|Cannot link"):
            sdlc_manager.flow_link_sub_issue("r", 1, "r", 2, fmt="text")


# --- flow_verify_label ------------------------------------------------------


def test_verify_label_no_op_when_label_exists() -> None:
    """Probe returns 200 → label exists → no POST, just a 'no-op' message."""
    with (
        patch.object(sdlc_manager, "_gh") as mock_gh,
        patch.object(sdlc_manager, "_rest_post") as mock_post,
        patch.object(sdlc_manager, "_out") as mock_out,
    ):
        mock_gh.return_value = '{"name":"high-priority","color":"D93F0B"}'
        sdlc_manager.flow_verify_label(
            "campps-mvp", "high-priority", "D93F0B", "High priority", fmt="text"
        )
        mock_post.assert_not_called()
        msgs = [c.args[0] for c in mock_out.call_args_list]
        assert any("already exists" in m for m in msgs)


def test_verify_label_creates_on_404() -> None:
    """Probe raises ApiNotFound (typed 404) → POST creates the label."""
    with (
        patch.object(sdlc_manager, "_gh") as mock_gh,
        patch.object(sdlc_manager, "_rest_post") as mock_post,
        patch.object(sdlc_manager, "_out"),
    ):
        mock_gh.side_effect = sdlc_manager.ApiNotFound(
            "API call failed: HTTP 404",
            status_code=404,
        )
        sdlc_manager.flow_verify_label(
            "campps-mvp", "high-priority", "D93F0B", "High priority", fmt="text"
        )
        mock_post.assert_called_once()
        body = mock_post.call_args.args[1]
        assert body["name"] == "high-priority"
        assert body["color"] == "D93F0B"  # leading '#' stripped if any
        assert body["description"] == "High priority"


def test_verify_label_strips_leading_hash_from_color() -> None:
    """Operators may pass '#D93F0B' (with leading hash). GitHub API rejects
    it; the helper strips it before POST."""
    with (
        patch.object(sdlc_manager, "_gh") as mock_gh,
        patch.object(sdlc_manager, "_rest_post") as mock_post,
    ):
        mock_gh.side_effect = sdlc_manager.ApiNotFound(
            "API call failed: HTTP 404",
            status_code=404,
        )
        sdlc_manager.flow_verify_label("r", "label", "#ABCDEF", None, fmt="text")
        body = mock_post.call_args.args[1]
        assert body["color"] == "ABCDEF"


def test_verify_label_does_NOT_create_on_non_404_error() -> None:
    """Auth / rate-limit / server errors must propagate — silently treating
    them as 'missing' would mask real problems and create labels under wrong
    auth context. With the typed-exception refactor, ApiAuthError /
    ApiRateLimited / generic GhApiError propagate out of the `except
    ApiNotFound:` block."""
    with (
        patch.object(sdlc_manager, "_gh") as mock_gh,
        patch.object(sdlc_manager, "_rest_post") as mock_post,
    ):
        mock_gh.side_effect = sdlc_manager.ApiAuthError(
            "API call failed: HTTP 401 Bad credentials",
            status_code=401,
        )
        with pytest.raises(sdlc_manager.ApiAuthError):
            sdlc_manager.flow_verify_label("r", "label", None, None, fmt="text")
        mock_post.assert_not_called()


# --- flow_field_options + flow_set_field -----------------------------------


def test_field_options_reads_live_from_graphql() -> None:
    """field-options is a live discovery — never cached. Call must hit
    QUERY_GET_PROJECT_FIELDS."""
    with (
        patch.object(sdlc_manager, "load_config") as mock_load,
        patch.object(sdlc_manager, "_graphql") as mock_gql,
        patch.object(sdlc_manager, "_out") as mock_out,
    ):
        mock_load.return_value = {
            "project_mappings": {
                "projects": {"mount-olympus": {"number": 1, "name": "Olympus"}},
            }
        }
        mock_gql.return_value = {
            "organization": {
                "projectV2": {
                    "id": "PVT_kwx",
                    "fields": {
                        "nodes": [
                            {
                                "id": "FLD_kwabc",
                                "name": "Initiative",
                                "options": [
                                    {"id": "opt1", "name": "olympus-quality"},
                                    {"id": "opt2", "name": "olympus-performance"},
                                ],
                            }
                        ]
                    },
                }
            }
        }
        sdlc_manager.flow_field_options("mount-olympus", "Initiative", fmt="json")
        # Verify it called the GraphQL query (no caching)
        assert mock_gql.called
        # Verify output contains both options with their (live) IDs
        out_payload = mock_out.call_args.args[0]
        names = [o["name"] for o in out_payload]
        assert "olympus-quality" in names
        assert "olympus-performance" in names


def test_set_field_raises_with_helpful_message_on_unknown_option() -> None:
    """If the operator passes an option that doesn't exist on the field,
    the error must list the actual options so they can correct."""
    with (
        patch.object(sdlc_manager, "load_config") as mock_load,
        patch.object(sdlc_manager, "_graphql") as mock_gql,
    ):
        mock_load.return_value = {
            "project_mappings": {
                "projects": {"mount-olympus": {"number": 1, "name": "Olympus"}},
            }
        }
        mock_gql.return_value = {
            "organization": {
                "projectV2": {
                    "id": "PVT_kwx",
                    "fields": {
                        "nodes": [
                            {
                                "id": "FLD_kwabc",
                                "name": "Initiative",
                                "options": [
                                    {"id": "o1", "name": "olympus-quality"},
                                    {"id": "o2", "name": "olympus-performance"},
                                ],
                            }
                        ]
                    },
                }
            }
        }
        with pytest.raises(RuntimeError) as exc:
            sdlc_manager.flow_set_field(
                "mount-olympus",
                "campps-mvp",
                42,
                "Initiative",
                "nonexistent-option",
                fmt="text",
            )
        msg = str(exc.value)
        assert "nonexistent-option" in msg
        # Helpful: includes the actual options + the discovery command hint
        assert "olympus-quality" in msg or "olympus-performance" in msg
        assert "field-options" in msg
