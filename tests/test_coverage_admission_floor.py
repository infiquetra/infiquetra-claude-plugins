"""Full-suite admission rejects sub-80 coverage without constraining nested scopes."""

import argparse
import re
import shlex
from pathlib import Path

import coverage
import pytest
import yaml
from coverage.results import should_fail_under
from pytest_cov.plugin import validate_fail_under

ROOT = Path(__file__).resolve().parents[1]
CONFIG = ROOT / "pyproject.toml"


def _full_command_thresholds() -> dict[str, float]:
    """Read the actual full-run flags using pytest-cov's installed value validator."""
    workflow = yaml.safe_load((ROOT / ".github/workflows/ci.yml").read_text())
    ci_command = next(
        step["run"]
        for step in workflow["jobs"]["tests"]["steps"]
        if step.get("name") == "Run tests with coverage"
    )
    gate = (ROOT / "scripts/gate.sh").read_text()
    match = re.search(r'^step "Run tests with coverage" \\\n\s*(.+)$', gate, re.MULTILINE)
    assert match is not None, "local full-suite coverage command is missing"
    parser = argparse.ArgumentParser(add_help=False, allow_abbrev=False)
    parser.add_argument("--cov-fail-under", type=validate_fail_under, required=True)
    commands = {"CI": ci_command, "local gate": match.group(1)}
    result: dict[str, float] = {}
    for name, command in commands.items():
        options, _ = parser.parse_known_args(shlex.split(command))
        result[name] = options.cov_fail_under
    return result


@pytest.mark.parametrize(
    ("covered", "valid", "reject"),
    [
        (19980, 25277, True),
        (20221, 25277, True),
        (20222, 25277, False),
        (400, 500, False),
        (399, 500, True),
    ],
)
def test_installed_coverage_rejects_below_floor_before_display_rounding(
    covered: int, valid: int, reject: bool
) -> None:
    config = coverage.Coverage(config_file=str(CONFIG)).config
    for boundary, threshold in _full_command_thresholds().items():
        assert should_fail_under(100 * covered / valid, threshold, config.precision) is reject, (
            boundary
        )


def test_nested_scope_is_not_mistaken_for_full_suite_admission() -> None:
    """The real nested routing regression had three passes at this scoped percentage."""
    config = coverage.Coverage(config_file=str(CONFIG)).config
    scoped_percentage = 100 * 703 / 3986
    assert should_fail_under(scoped_percentage, config.fail_under, config.precision) is False
    for boundary, threshold in _full_command_thresholds().items():
        assert should_fail_under(scoped_percentage, threshold, config.precision) is True, boundary
