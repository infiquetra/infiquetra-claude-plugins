"""Coverage admission must reject raw percentages that display rounding could hide."""

from pathlib import Path

import coverage
import pytest
from coverage.results import should_fail_under

CONFIG = Path(__file__).resolve().parents[1] / "pyproject.toml"


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
    assert should_fail_under(100 * covered / valid, config.fail_under, config.precision) is reject
