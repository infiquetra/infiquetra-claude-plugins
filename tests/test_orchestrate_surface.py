"""The slimmed command surface and the release surfaces that carry it (issue #1025, U8).

These are the card's own runnable acceptance criteria, as tests rather than as a shell transcript,
plus the version guard this repository requires of every plugin change.
"""

from __future__ import annotations

import json
import re

import pytest
from orchestrate_support import ORCHESTRATE_SCRIPT, load_orchestrate

PLUGIN_ROOT = ORCHESTRATE_SCRIPT.parents[3]
REPO_ROOT = PLUGIN_ROOT.parents[1]
MANIFEST = PLUGIN_ROOT / ".claude-plugin" / "plugin.json"
CHANGELOG = PLUGIN_ROOT / "CHANGELOG.md"
MARKETPLACE = REPO_ROOT / ".claude-plugin" / "marketplace.json"

#: Orchestrate's version at this card. Named with its predecessor so a bump is deliberate.
ORCHESTRATE_VERSION = "5.0.0"
# Issue 1001 took 4.6.0 on the integration branch while this card's suite ran; its
# section is folded under 5.0.0 rather than renumbered.
ORCHESTRATE_PREDECESSOR = "4.6.0"

REMOVED_SUBCOMMANDS = ("redrive", "collect", "land")
KEPT_SUBCOMMANDS = ("plan-check", "start", "go", "merge", "clean")


@pytest.fixture(scope="module")
def orch():
    return load_orchestrate("_orchestrate_surface")


@pytest.fixture(scope="module")
def help_text(orch) -> str:
    parser_names: list[str] = []
    import argparse

    original = argparse.ArgumentParser.parse_args

    def capture(self, argv=None, namespace=None):
        for action in self._subparsers._actions if self._subparsers else []:
            if isinstance(action, argparse._SubParsersAction):
                parser_names.extend(action.choices)
        raise SystemExit(0)

    argparse.ArgumentParser.parse_args = capture  # type: ignore[method-assign]
    try:
        with pytest.raises(SystemExit):
            orch.main([])
    finally:
        argparse.ArgumentParser.parse_args = original  # type: ignore[method-assign]
    return "\n".join(parser_names)


class TestTheSubcommandSurface:
    @pytest.mark.parametrize("name", REMOVED_SUBCOMMANDS)
    def test_the_removed_subcommands_are_gone(self, help_text: str, name: str) -> None:
        assert name not in help_text.split()

    @pytest.mark.parametrize("name", KEPT_SUBCOMMANDS)
    def test_the_kept_subcommands_are_present(self, help_text: str, name: str) -> None:
        assert name in help_text.split()

    def test_the_removed_command_functions_are_gone_too(self, orch) -> None:
        """A subcommand hidden from the parser but still callable is not removed."""
        for name in ("cmd_redrive", "cmd_collect", "cmd_land"):
            assert not hasattr(orch, name), name

    def test_merge_replaces_land(self, orch) -> None:
        assert callable(orch.cmd_merge)


class TestTheGrepCriterion:
    def test_the_driver_names_no_reservation_or_writeback_record(self) -> None:
        """The card's second acceptance criterion, as a test.

        Two of the three names never appeared in this file -- checked against base commit
        4e951f0e -- so this asserts the property the criterion is about rather than re-deriving
        the count.
        """
        source = ORCHESTRATE_SCRIPT.read_text(encoding="utf-8")
        pattern = re.compile(r"reserved_landing_paths|launch_reservation|record_writeback_outcome")
        assert pattern.findall(source) == []


class TestTheCompanionFloorWarns:
    def test_a_below_floor_companion_warns_and_the_command_continues(
        self, orch, monkeypatch: pytest.MonkeyPatch, capsys
    ) -> None:
        monkeypatch.setattr(orch, "_AGENT_LAUNCHER_AVAILABLE", True)
        monkeypatch.setattr(
            orch, "_AGENT_LAUNCHER_ERROR", "agent-launcher 1.0.0 is installed; requires >=1.7.0"
        )
        monkeypatch.setattr(orch, "_COMPANION_FAULT_PRINTED", False)
        orch.assert_agent_launcher_available()
        assert "requires >=1.7.0" in capsys.readouterr().err

    def test_a_missing_companion_still_refuses(self, orch, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setattr(orch, "_AGENT_LAUNCHER_AVAILABLE", False)
        monkeypatch.setattr(orch, "_AGENT_LAUNCHER_ERROR", "")
        with pytest.raises(SystemExit) as caught:
            orch.assert_agent_launcher_available()
        assert "agent-launcher plugin not found" in str(caught.value)


class TestReleaseSurfacesMoveTogether:
    def test_the_manifest_carries_this_cards_version(self) -> None:
        assert json.loads(MANIFEST.read_text())["version"] == ORCHESTRATE_VERSION

    def test_the_marketplace_entry_agrees_with_the_manifest(self) -> None:
        entries = json.loads(MARKETPLACE.read_text())["plugins"]
        row = next(entry for entry in entries if entry["name"] == "orchestrate")
        assert row["version"] == ORCHESTRATE_VERSION

    def test_the_changelog_opens_on_this_version_and_names_its_predecessor(self) -> None:
        headings = re.findall(r"^## \[(\d+\.\d+\.\d+)\]", CHANGELOG.read_text(), re.MULTILINE)
        assert headings[0] == ORCHESTRATE_VERSION
        assert headings[1] == ORCHESTRATE_PREDECESSOR

    @pytest.mark.parametrize("name", REMOVED_SUBCOMMANDS)
    def test_the_changelog_names_every_removed_subcommand(self, name: str) -> None:
        latest = CHANGELOG.read_text().split("## [", 2)[1]
        assert f"`{name}`" in latest, f"the 5.0.0 entry must name {name} by name"

    def test_the_changelog_names_the_record_replacement_as_breaking(self) -> None:
        latest = CHANGELOG.read_text().split("## [", 2)[1]
        assert "run record" in latest.lower()
        assert "breaking" in latest.lower()
