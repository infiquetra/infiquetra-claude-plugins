"""Two decisions a unit carries that nothing else can recover: how it launches, and whether it lands.

Both exist because the live run for issue 48 lost them. The launcher needed an argument the unit had
no field for, so a whole review phase was started by hand and never entered the run record.
"""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path
from types import ModuleType

import pytest

SCRIPT = (
    Path(__file__).resolve().parents[1]
    / "plugins"
    / "orchestrate"
    / "skills"
    / "orchestrate"
    / "scripts"
    / "orchestrate.py"
)


@pytest.fixture(scope="module")
def orchestrate() -> ModuleType:
    spec = importlib.util.spec_from_file_location("_orchestrate_launch_land", SCRIPT)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


class TestLauncherArgumentsArePassedThrough:
    """The plugin carries what the operator asked for; the launcher decides whether it is valid."""

    def test_extra_arguments_reach_the_command_line(self, orchestrate: ModuleType) -> None:
        unit = orchestrate.Unit(
            name="reviewer",
            vendor="claude",
            task="/saga:code-review the build",
            model="opus",
            launch_args=["--company-account"],
        )
        argv = orchestrate.agent_argv(unit)
        assert "--company-account" in argv

    def test_they_follow_the_vendor_token(self, orchestrate: ModuleType) -> None:
        """The wrapper reads its own flags out of the arguments after the vendor name."""
        unit = orchestrate.Unit(
            name="reviewer", vendor="claude", task="x", launch_args=["--company-account"]
        )
        argv = orchestrate.agent_argv(unit)
        assert argv.index("--company-account") > argv.index("claude")

    def test_nothing_is_added_when_none_are_asked_for(self, orchestrate: ModuleType) -> None:
        unit = orchestrate.Unit(name="reviewer", vendor="claude", task="x")
        plain = orchestrate.agent_argv(unit)
        unit.launch_args = ["--company-account"]
        assert orchestrate.agent_argv(unit) == plain + ["--company-account"]

    def test_an_unknown_argument_is_not_rejected_here(self, orchestrate: ModuleType) -> None:
        """No allow-list: a stale one in this file is the same closed vocabulary one level up."""
        unit = orchestrate.Unit(
            name="reviewer", vendor="qwen", task="x", launch_args=["--not-a-real-flag"]
        )
        assert "--not-a-real-flag" in orchestrate.agent_argv(unit)
