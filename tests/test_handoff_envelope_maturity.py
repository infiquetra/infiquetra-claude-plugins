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


def test_out_of_domain_declared_value_falls_through(tmp_path: Path) -> None:
    ideation = tmp_path / "docs" / "ideation"
    ideation.mkdir(parents=True)
    target = ideation / "2026-06-19-plugin-grooming-next-steps.md"
    target.write_text("---\nmaturity: ready-to-execute\n---\n\nBody\n", encoding="utf-8")
    assert HE.infer_maturity(str(target)) == "idea-ready"  # type: ignore[attr-defined]
    # Also via root-relative
    assert (
        HE.infer_maturity("docs/ideation/2026-06-19-plugin-grooming-next-steps.md", root=tmp_path)
        == "idea-ready"
    )  # type: ignore[attr-defined]


def test_inline_comment_stripped(tmp_path: Path) -> None:
    brainstorms = tmp_path / "docs" / "brainstorms"
    brainstorms.mkdir(parents=True)
    target = brainstorms / "2026-08-30-topic-requirements.md"
    target.write_text(
        "---\nmaturity: requirements-ready   # some note\n---\n\nBody\n", encoding="utf-8"
    )
    assert HE.infer_maturity(str(target)) == "requirements-ready"  # type: ignore[attr-defined]


def test_shell_shaped_value_rejected(tmp_path: Path) -> None:
    brainstorms = tmp_path / "docs" / "brainstorms"
    brainstorms.mkdir(parents=True)
    target = brainstorms / "2026-08-30-topic-requirements.md"
    target.write_text("---\nmaturity: ; rm -rf ~\n---\n\nBody\n", encoding="utf-8")
    assert HE.infer_maturity(str(target)) == "requirements-ready"  # type: ignore[attr-defined]


def test_non_utf8_file_does_not_raise(tmp_path: Path) -> None:
    brainstorms = tmp_path / "docs" / "brainstorms"
    brainstorms.mkdir(parents=True)
    target = brainstorms / "2026-08-30-topic-requirements.md"
    target.write_bytes(b"---\nmaturity: requirements-ready\n---\n\nBody \xe9\n")
    # Must not raise UnicodeDecodeError; must fall through to path rule
    assert HE.infer_maturity(str(target)) == "requirements-ready"  # type: ignore[attr-defined]


def test_root_honoured(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    brainstorms = tmp_path / "docs" / "brainstorms"
    brainstorms.mkdir(parents=True)
    target = brainstorms / "2026-08-30-topic-requirements.md"
    _write_file(target, "pending-confirmation")
    # Call from a different working directory — root must be honoured
    other = tmp_path / "other"
    other.mkdir()
    monkeypatch.chdir(other)
    assert (
        HE.infer_maturity("docs/brainstorms/2026-08-30-topic-requirements.md", root=tmp_path)
        == "pending-confirmation"
    )  # type: ignore[attr-defined]
    envelope = HE.build_handoff_envelope(
        "docs/brainstorms/2026-08-30-topic-requirements.md", root=tmp_path
    )  # type: ignore[attr-defined]
    assert envelope["handoff_maturity"] == "pending-confirmation"


def test_non_routable_guard(tmp_path: Path) -> None:
    brainstorms = tmp_path / "docs" / "brainstorms"
    brainstorms.mkdir(parents=True)
    target = brainstorms / "2026-08-30-topic-requirements.md"
    _write_file(target, "pending-confirmation")
    envelope = HE.build_handoff_envelope(
        "docs/brainstorms/2026-08-30-topic-requirements.md", root=tmp_path
    )  # type: ignore[attr-defined]
    assert envelope["handoff_maturity"] == "pending-confirmation"
    assert "/issue --prepare" not in envelope["suggested_command"]  # type: ignore[index]
