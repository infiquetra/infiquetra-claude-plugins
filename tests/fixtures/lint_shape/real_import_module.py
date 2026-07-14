"""POSITIVE fixture for ``scripts/lint_test_shape.py`` (#458, T11-F2-8).

This module loads and exercises the REAL production adapter
(``plugins/saga/scripts/outcome_worktrees.py``) via the repo's importlib-by-path idiom, so it
crosses into real code and passes the shape lint (exit 0). It is deliberately NOT named
``test_*.py`` so pytest does not collect it — it exists purely as lint input.
"""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path
from typing import Any

_SCRIPTS = Path(__file__).resolve().parents[3] / "plugins" / "saga" / "scripts"


def _load_outcome_worktrees() -> Any:
    if str(_SCRIPTS) not in sys.path:
        sys.path.insert(0, str(_SCRIPTS))
    spec = importlib.util.spec_from_file_location(
        "outcome_worktrees", _SCRIPTS / "outcome_worktrees.py"
    )
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_real_worktree_name() -> None:
    wt = _load_outcome_worktrees()
    # Exercises the real production function, not a fake's canned answer.
    assert wt.worktree_name("o", "s1") == "saga-outcome-o-s1"
