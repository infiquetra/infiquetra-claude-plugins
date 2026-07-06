"""Tests for U1: `effort:` as a recognized, validated agent-frontmatter field (#363).

Globs every ``plugins/*/agents/*.md`` file and asserts that any ``effort:`` value
present is a member of ``tier_palette.EFFORTS`` and any ``model:`` value present is a
member of ``tier_palette.MODELS`` (R1, R2, R3). A ``tiering_exempt: true`` frontmatter
field opts a file out of the check (KTD6), mirroring the existing
redis-channel-coach exemption used by test_agent_tiering.py.

Reuses ``_parse_frontmatter`` from tests/test_agent_tiering.py rather than
re-implementing YAML-lite frontmatter parsing (KTD6).
"""

from __future__ import annotations

import pathlib
import sys

import pytest

TESTS_ROOT = pathlib.Path(__file__).parent
REPO_ROOT = TESTS_ROOT.parent
PLUGINS_ROOT = REPO_ROOT / "plugins"
FLEET_CORE_SCRIPTS = PLUGINS_ROOT / "fleet-core" / "scripts"

if str(TESTS_ROOT) not in sys.path:
    sys.path.insert(0, str(TESTS_ROOT))
if str(FLEET_CORE_SCRIPTS) not in sys.path:
    sys.path.insert(0, str(FLEET_CORE_SCRIPTS))

from fleet_commons.tier_palette import EFFORTS, MODELS  # noqa: E402
from test_agent_tiering import _parse_frontmatter  # noqa: E402

ALL_AGENT_FILES: list[pathlib.Path] = sorted(PLUGINS_ROOT.glob("*/agents/*.md"))


def _is_exempt(fm: dict[str, str]) -> bool:
    """A file is exempt when it carries a truthy `tiering_exempt` frontmatter value."""
    value = fm.get("tiering_exempt")
    if value is None:
        return False
    return value.strip().lower() not in ("", "false", "no", "0")


def test_agent_glob_finds_files() -> None:
    """Sanity: the glob must actually find agent files, or this test suite is inert."""
    assert ALL_AGENT_FILES, f"no agent files found under {PLUGINS_ROOT}/*/agents/*.md"


@pytest.mark.parametrize(
    "path",
    ALL_AGENT_FILES,
    ids=[str(p.relative_to(PLUGINS_ROOT)) for p in ALL_AGENT_FILES],
)
def test_agent_tier_fields_in_palette(path: pathlib.Path) -> None:
    """Every non-exempt agent's `effort:`/`model:` (if present) must be in-palette.

    An out-of-vocabulary value on either field fails the build (R1/R2). Files with a
    truthy `tiering_exempt` frontmatter field are skipped (R3 escape hatch, KTD6).
    """
    fm = _parse_frontmatter(path)
    if _is_exempt(fm):
        pytest.skip(f"{path.relative_to(PLUGINS_ROOT)} is tiering_exempt")

    if "model" in fm:
        assert fm["model"] in MODELS, (
            f"{path.relative_to(PLUGINS_ROOT)}: model {fm['model']!r} not in palette {MODELS}"
        )
    if "effort" in fm:
        assert fm["effort"] in EFFORTS, (
            f"{path.relative_to(PLUGINS_ROOT)}: effort {fm['effort']!r} not in palette {EFFORTS}"
        )


def test_seeded_bad_effort_fails(tmp_path: pathlib.Path) -> None:
    """A fixture agent with `effort: extreme` must fail the membership check (AC1)."""
    fixture = tmp_path / "bad-effort.md"
    fixture.write_text("---\nname: fixture\nmodel: sonnet\neffort: extreme\n---\nbody\n")
    fm = _parse_frontmatter(fixture)
    assert not _is_exempt(fm)
    assert fm["effort"] not in EFFORTS


def test_seeded_good_effort_passes(tmp_path: pathlib.Path) -> None:
    """The same fixture with `effort: high` must pass the membership check."""
    fixture = tmp_path / "good-effort.md"
    fixture.write_text("---\nname: fixture\nmodel: sonnet\neffort: high\n---\nbody\n")
    fm = _parse_frontmatter(fixture)
    assert not _is_exempt(fm)
    assert fm["effort"] in EFFORTS
    assert fm["model"] in MODELS


def test_seeded_bad_model_fails(tmp_path: pathlib.Path) -> None:
    """A fixture agent with an off-palette `model:` value must fail."""
    fixture = tmp_path / "bad-model.md"
    fixture.write_text("---\nname: fixture\nmodel: opus-ultra\n---\nbody\n")
    fm = _parse_frontmatter(fixture)
    assert not _is_exempt(fm)
    assert fm["model"] not in MODELS


def test_seeded_tiering_exempt_skips_bad_values(tmp_path: pathlib.Path) -> None:
    """`tiering_exempt: true` opts a fixture out even with off-palette values (R3)."""
    fixture = tmp_path / "exempt.md"
    fixture.write_text(
        "---\nname: fixture\nmodel: opus-ultra\neffort: extreme\ntiering_exempt: true\n---\nbody\n"
    )
    fm = _parse_frontmatter(fixture)
    assert _is_exempt(fm)
