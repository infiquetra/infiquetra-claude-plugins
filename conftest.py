"""Repository-wide pytest fixtures.

``tests/conftest.py`` reaches only ``tests/``. This file sits at the root so it also reaches
``plugins/*/tests``, the other configured test path.
"""

from __future__ import annotations

import os
import stat
from collections.abc import Iterator

import pytest

_SHADOW_HERDR = """#!/bin/sh
echo "herdr is shadowed under pytest: a test reached the host's herdr instead of stubbing it" >&2
exit 127
"""


@pytest.fixture(autouse=True, scope="session")
def _shadow_the_host_herdr(tmp_path_factory: pytest.TempPathFactory) -> Iterator[None]:
    """Put a ``herdr`` that answers nothing ahead of the operator's for the whole session.

    Two launcher tests were green on the operator's machine and red in CI for one reason: they
    left a launch's ownership snapshot unstubbed, so it asked the herdr on PATH. Here that was
    the operator's live herdr, which answered and proved ownership; a runner has none, so the
    identity check ran instead and stopped the launch first (issue 907, U34). The local gate
    could not see the difference, because the difference was what the host had installed.

    This shim makes every herdr reading fail here the way it fails on a runner -- a non-zero
    result, no output -- so a test that quietly depends on the host's herdr fails on its first
    local run rather than in CI. Tests that need a herdr put their own fake ahead of this one on
    PATH, as they already do; tests that need herdr absent replace PATH outright, as they do too.
    """
    shim_dir = tmp_path_factory.mktemp("no-host-herdr")
    shim = shim_dir / "herdr"
    shim.write_text(_SHADOW_HERDR)
    shim.chmod(shim.stat().st_mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)
    original = os.environ.get("PATH", "")
    os.environ["PATH"] = f"{shim_dir}{os.pathsep}{original}"
    try:
        yield
    finally:
        os.environ["PATH"] = original
