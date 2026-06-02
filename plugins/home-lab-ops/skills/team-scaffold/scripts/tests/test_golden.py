"""Golden test: harness_gen of each materialized spec must reproduce the live
team repos' deploy/ files byte-for-byte.

This is the acceptance gate for the gen_harness -> harness_gen promotion. The
fixtures under specs/golden/ are frozen copies of the live infiquetra/team-*
repos (fetched 2026-06-01); all 36 (3 files x 12 teams) matched the migration
generator byte-for-byte at promotion time.
"""
from __future__ import annotations

import pathlib

import pytest

from team_scaffold import harness_gen, spec

ROOT = pathlib.Path(__file__).resolve().parents[1].parent  # skills/team-scaffold
SPECS = ROOT / "specs"
GOLDEN = SPECS / "golden"

SPEC_FILES = sorted(SPECS.glob("team-*.yaml"))
assert len(SPEC_FILES) == 12, f"expected 12 specs, found {len(SPEC_FILES)}"


@pytest.mark.parametrize("spec_path", SPEC_FILES, ids=lambda p: p.stem)
def test_harness_byte_for_byte(spec_path: pathlib.Path) -> None:
    ts = spec.load_spec(spec_path)
    assert ts.validate() == [], f"{ts.repo} spec is invalid"
    rendered = harness_gen.render_harness(ts.as_cfg())
    gold_dir = GOLDEN / ts.repo / "deploy"
    assert gold_dir.is_dir(), f"missing golden fixtures for {ts.repo}"
    for fname, content in rendered.items():
        expected = (gold_dir / fname).read_text()
        assert content == expected, f"{ts.repo}/deploy/{fname} diverged from golden"


def test_requirements_src_pinned_to_namredips() -> None:
    """Byte parity depends on the personal-account remote; guard against a 'fix'."""
    assert "git+https://github.com/namredips/home-lab.git" in harness_gen.REQUIREMENTS
