"""Tests for the test-shape lint (#458, T11-F2-8).

Pins the acceptance criterion: a fixture test module that imports/patches only a fake and never
touches the real production module fails ``scripts/lint_test_shape.py``; a fixture module that does
import/exercise the real module passes.
"""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path
from types import ModuleType

import pytest

ROOT = Path(__file__).parent.parent
SCRIPTS = ROOT / "scripts"
FIXTURES = ROOT / "tests" / "fixtures" / "lint_shape"


def _load_lint() -> ModuleType:
    if str(SCRIPTS) not in sys.path:
        sys.path.insert(0, str(SCRIPTS))
    spec = importlib.util.spec_from_file_location("lint_test_shape", SCRIPTS / "lint_test_shape.py")
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules["lint_test_shape"] = module
    spec.loader.exec_module(module)
    return module


@pytest.fixture
def lint() -> ModuleType:
    return _load_lint()


def test_fake_only_fixture_is_flagged(lint: ModuleType) -> None:
    """The negative fixture (fake, no real import) is a violation and exits non-zero."""
    report = lint.analyze_file(FIXTURES / "fake_only_module.py", frozenset())
    assert report.has_fake is True
    assert report.has_production is False
    assert report.is_violation is True
    assert lint.main([str(FIXTURES / "fake_only_module.py")]) == 1


def test_real_import_fixture_passes(lint: ModuleType) -> None:
    """The positive fixture (loads the real module) is not a violation and exits 0."""
    report = lint.analyze_file(FIXTURES / "real_import_module.py", frozenset())
    assert report.has_production is True
    assert report.is_violation is False
    assert lint.main([str(FIXTURES / "real_import_module.py")]) == 0


def test_advisory_mode_never_fails(lint: ModuleType) -> None:
    """--advisory reports a violation but exits 0."""
    assert lint.main([str(FIXTURES / "fake_only_module.py"), "--advisory"]) == 0


def test_prod_module_flag_clears_bare_name_import(lint: ModuleType) -> None:
    """A bare production import (e.g. ``from server import x``) counts once declared via --prod-module."""
    src = "import fakeredis\nfrom server import redis_consumer\n"
    without = lint.analyze_source(src, Path("t.py"), frozenset())
    assert without.is_violation is True  # 'server' unknown -> looks fake-only
    with_flag = lint.analyze_source(src, Path("t.py"), frozenset({"server"}))
    assert with_flag.has_production is True
    assert with_flag.is_violation is False


def test_plugins_import_is_production_signal(lint: ModuleType) -> None:
    """A direct ``from plugins...`` import is recognized as crossing into production."""
    src = "class FakeThing: ...\nfrom plugins.saga.scripts import saga\n"
    report = lint.analyze_source(src, Path("t.py"), frozenset())
    assert report.has_fake is True
    assert report.has_production is True
    assert report.is_violation is False


def test_importlib_by_path_idiom_is_production_signal(lint: ModuleType) -> None:
    """The repo's ``spec_from_file_location(name, ROOT/'plugins'/...)`` idiom counts as production."""
    src = (
        "import importlib.util\n"
        "class FakeX: ...\n"
        "SCRIPTS = 'plugins/saga/scripts'\n"
        "spec = importlib.util.spec_from_file_location('m', SCRIPTS)\n"
    )
    report = lint.analyze_source(src, Path("t.py"), frozenset())
    assert report.has_production is True
    assert report.is_violation is False


def test_directory_scan_only_collects_test_modules(lint: ModuleType, tmp_path: Path) -> None:
    """A directory contributes only ``test_*.py``; the non-test fixtures are skipped in dir mode."""
    (tmp_path / "test_fake_only.py").write_text("class FakeQ: ...\n", encoding="utf-8")
    (tmp_path / "helper_module.py").write_text("class FakeQ: ...\n", encoding="utf-8")
    targets = lint._iter_targets([tmp_path])
    names = {p.name for p in targets}
    assert "test_fake_only.py" in names
    assert "helper_module.py" not in names


def test_inert_docstring_mentioning_plugins_does_not_evade_lint(lint: ModuleType) -> None:
    """An inert docstring mentioning 'plugins/' does not count as a production signal (#588)."""
    src = (
        '"""Test module for fake adapter; see plugins/saga/scripts/outcome.py for context."""\n'
        "class FakeStore:\n"
        "    pass\n"
    )
    report = lint.analyze_source(src, Path("test_inert.py"), frozenset())
    assert report.has_fake is True
    assert report.has_production is False
    assert report.is_violation is True


def test_fake_loader_does_not_evade_lint(lint: ModuleType) -> None:
    """Loading a fake via spec_from_file_location or import_module does not count as production (#588)."""
    src = (
        "import importlib.util\n"
        "class FakeStore: ...\n"
        "spec = importlib.util.spec_from_file_location('fake_mod', 'tests/fixtures/fake_mod.py')\n"
        "mod = importlib.import_module('fake_helper')\n"
    )
    report = lint.analyze_source(src, Path("test_fake_loader.py"), frozenset())
    assert report.has_fake is True
    assert report.has_production is False
    assert report.is_violation is True


def test_whole_suite_is_clean_with_server_prod_module(lint: ModuleType) -> None:
    """The committed suite has no fake-only ``test_*.py`` modules (the CI invariant this gate holds).

    Runs the same invocation as the CI step: ``tests/`` with ``--prod-module server`` (redis-channel
    production is imported as the ``server`` package). A regression — a new fake-only test module —
    would make this fail.
    """
    assert lint.main([str(ROOT / "tests"), "--prod-module", "server"]) == 0
