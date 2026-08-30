"""Handoff maturity — frontmatter-aware inference (KTD7, issue 913 B1)."""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).parent.parent
HANDOFF_PATH = ROOT / "plugins/saga/scripts/handoff_envelope.py"


def _load() -> object:
    if str(HANDOFF_PATH.parent) not in sys.path:
        sys.path.insert(0, str(HANDOFF_PATH.parent))
    spec = importlib.util.spec_from_file_location("handoff_envelope_maturity", HANDOFF_PATH)
    assert spec is not None and spec.loader is not None
    import types

    module: types.ModuleType = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module  # type: ignore[attr-defined]
    spec.loader.exec_module(module)
    return module


HE = _load()  # type: ignore[no-redef]


def _write_file(path: Path, maturity: str | None) -> None:
    if maturity is None:
        path.write_text("# No frontmatter\n\nBody.\n", encoding="utf-8")
        return
    path.write_text(
        f"---\ndate: 2026-08-30\ntopic: test-topic\nmaturity: {maturity}\n---\n\nBody.\n",
        encoding="utf-8",
    )


# ---------------------------------------------------------------------------
# Frontmatter wins — pending-confirmation declared in file.
# ---------------------------------------------------------------------------


def test_frontmatter_maturity_pending_confirmation_wins(tmp_path: Path) -> None:
    brainstorms = tmp_path / "docs" / "brainstorms"
    brainstorms.mkdir(parents=True)
    target = brainstorms / "2026-08-30-test-topic-requirements.md"
    _write_file(target, "pending-confirmation")
    # Absolute path case (tmp_path file).
    assert HE.infer_maturity(str(target)) == "pending-confirmation"  # type: ignore[attr-defined]


def test_frontmatter_maturity_requirements_ready_wins(tmp_path: Path) -> None:
    brainstorms = tmp_path / "docs" / "brainstorms"
    brainstorms.mkdir(parents=True)
    target = brainstorms / "2026-08-30-test-topic-requirements.md"
    _write_file(target, "requirements-ready")
    assert HE.infer_maturity(str(target)) == "requirements-ready"  # type: ignore[attr-defined]


# ---------------------------------------------------------------------------
# Path inference preserved — pre-existing return values unchanged when no
# declared maturity exists (file missing declaration or path not on disk).
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("source", "expected"),
    [
        ("docs/brainstorms/2026-08-30-topic-requirements.md", "requirements-ready"),
        ("docs/ideation/2026-08-30-topic-ideation.md", "idea-ready"),
        ("docs/plans/2026-08-30-topic-plan.md", "plan-ready"),
        ("docs/specs/2026-08-30-topic-spec.md", "requirements-ready"),
        ("docs/work-sessions/2026-08-30-topic-session.md", "resume-ready"),
        ("branch:feature/foo", "resume-ready"),
    ],
)
def test_path_inference_preserved_when_no_declared_maturity(source: str, expected: str) -> None:
    # No file on disk for this source — falls through to path inference.
    assert HE.infer_maturity(source) == expected  # type: ignore[attr-defined]


def test_path_inference_preserved_for_brainstorms_file_without_maturity(tmp_path: Path) -> None:
    brainstorms = tmp_path / "docs" / "brainstorms"
    brainstorms.mkdir(parents=True)
    target = brainstorms / "2026-08-30-topic-requirements.md"
    _write_file(target, None)
    # File exists but declares no maturity — path rule applies.
    assert HE.infer_maturity(str(target)) == "requirements-ready"  # type: ignore[attr-defined]


# ---------------------------------------------------------------------------
# Missing file — no raise, path rule fallback.
# ---------------------------------------------------------------------------


def test_missing_file_falls_back_to_path_rule_and_raises_nothing(tmp_path: Path) -> None:
    missing = tmp_path / "docs" / "brainstorms" / "no-such-file.md"
    # Must not raise; must return path-based value.
    result = HE.infer_maturity(str(missing))  # type: ignore[attr-defined]
    assert result == "requirements-ready"
    # Non-brainstorms missing path.
    assert HE.infer_maturity("docs/plans/missing.md") == "plan-ready"  # type: ignore[attr-defined]
    assert HE.infer_maturity("branch:foo") == "resume-ready"  # type: ignore[attr-defined]
