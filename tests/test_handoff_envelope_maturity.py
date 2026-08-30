"""Handoff maturity — frontmatter-aware inference (KTD7, issue 913 B1)."""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path
from types import ModuleType

import pytest

ROOT = Path(__file__).parent.parent
HANDOFF_PATH = ROOT / "plugins/saga/scripts/handoff_envelope.py"


def _load() -> ModuleType:
    if str(HANDOFF_PATH.parent) not in sys.path:
        sys.path.insert(0, str(HANDOFF_PATH.parent))
    spec = importlib.util.spec_from_file_location("handoff_envelope_maturity", HANDOFF_PATH)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


HE: ModuleType = _load()


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
    assert HE.infer_maturity(str(target)) == "pending-confirmation"


def test_frontmatter_maturity_requirements_ready_wins(tmp_path: Path) -> None:
    # Relocated to a directory whose path rule disagrees (ideation -> idea-ready) so
    # removing the frontmatter reader flips the result.
    ideation = tmp_path / "docs" / "ideation"
    ideation.mkdir(parents=True)
    target = ideation / "2026-08-30-test-topic-requirements.md"
    target.write_text("---\nmaturity: requirements-ready\n---\n\nBody\n", encoding="utf-8")
    assert HE.infer_maturity(str(target)) == "requirements-ready"
    assert (
        HE.infer_maturity("docs/ideation/2026-08-30-test-topic-requirements.md", root=tmp_path)
        == "requirements-ready"
    )


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
    assert HE.infer_maturity(source) == expected


def test_path_inference_preserved_for_brainstorms_file_without_maturity(tmp_path: Path) -> None:
    brainstorms = tmp_path / "docs" / "brainstorms"
    brainstorms.mkdir(parents=True)
    target = brainstorms / "2026-08-30-topic-requirements.md"
    _write_file(target, None)
    # File exists but declares no maturity — path rule applies.
    assert HE.infer_maturity(str(target)) == "requirements-ready"


# ---------------------------------------------------------------------------
# Missing file — no raise, path rule fallback.
# ---------------------------------------------------------------------------


def test_missing_file_falls_back_to_path_rule_and_raises_nothing(tmp_path: Path) -> None:
    missing = tmp_path / "docs" / "brainstorms" / "no-such-file.md"
    # Must not raise; must return path-based value.
    result = HE.infer_maturity(str(missing))
    assert result == "requirements-ready"
    # Non-brainstorms missing path.
    assert HE.infer_maturity("docs/plans/missing.md") == "plan-ready"
    assert HE.infer_maturity("branch:foo") == "resume-ready"


def test_out_of_domain_declared_value_falls_through(tmp_path: Path) -> None:
    ideation = tmp_path / "docs" / "ideation"
    ideation.mkdir(parents=True)
    target = ideation / "2026-06-19-plugin-grooming-next-steps.md"
    target.write_text("---\nmaturity: ready-to-execute\n---\n\nBody\n", encoding="utf-8")
    # Unrecognized non-empty declared maturity now fails closed (API-03), not fall-through
    assert HE.infer_maturity(str(target)) == "unknown:ready-to-execute"
    envelope = HE.build_handoff_envelope(
        "docs/ideation/2026-06-19-plugin-grooming-next-steps.md", root=tmp_path
    )
    assert "/issue --prepare" not in envelope["suggested_command"]


def test_inline_comment_stripped(tmp_path: Path) -> None:
    # Use a value that differs from the path default so broken comment-stripping is detectable:
    # ideation's path rule is idea-ready, but pending-confirmation with trailing comment should win.
    ideation = tmp_path / "docs" / "ideation"
    ideation.mkdir(parents=True)
    target = ideation / "2026-08-30-topic-requirements.md"
    target.write_text(
        "---\nmaturity: pending-confirmation   # some note\n---\n\nBody\n", encoding="utf-8"
    )
    assert HE.infer_maturity(str(target)) == "pending-confirmation"
    assert (
        HE.infer_maturity("docs/ideation/2026-08-30-topic-requirements.md", root=tmp_path)
        == "pending-confirmation"
    )


def test_shell_shaped_value_rejected(tmp_path: Path) -> None:
    brainstorms = tmp_path / "docs" / "brainstorms"
    brainstorms.mkdir(parents=True)
    target = brainstorms / "2026-08-30-topic-requirements.md"
    target.write_text("---\nmaturity: ; rm -rf ~\n---\n\nBody\n", encoding="utf-8")
    assert HE.infer_maturity(str(target)) == "unknown:; rm -rf ~"
    envelope = HE.build_handoff_envelope(
        "docs/brainstorms/2026-08-30-topic-requirements.md", root=tmp_path
    )
    assert "/issue --prepare" not in envelope["suggested_command"]


def test_non_utf8_file_does_not_raise(tmp_path: Path) -> None:
    brainstorms = tmp_path / "docs" / "brainstorms"
    brainstorms.mkdir(parents=True)
    target = brainstorms / "2026-08-30-topic-requirements.md"
    target.write_bytes(b"---\nmaturity: requirements-ready\n---\n\nBody \xe9\n")
    # Must not raise UnicodeDecodeError; must fall through to path rule
    assert HE.infer_maturity(str(target)) == "requirements-ready"


def test_root_honoured(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    brainstorms = tmp_path / "docs" / "brainstorms"
    brainstorms.mkdir(parents=True)
    target = brainstorms / "2026-08-30-topic-requirements.md"
    _write_file(target, "pending-confirmation")
    # Plant a decoy at the same relative path under the cwd that declares a different maturity
    # — root must win even when cwd has a colliding file.
    other = tmp_path / "other"
    other.mkdir()
    decoy_dir = other / "docs" / "brainstorms"
    decoy_dir.mkdir(parents=True)
    (decoy_dir / "2026-08-30-topic-requirements.md").write_text(
        "---\nmaturity: requirements-ready\n---\n\nBody\n", encoding="utf-8"
    )
    monkeypatch.chdir(other)
    assert (
        HE.infer_maturity("docs/brainstorms/2026-08-30-topic-requirements.md", root=tmp_path)
        == "pending-confirmation"
    )
    envelope = HE.build_handoff_envelope(
        "docs/brainstorms/2026-08-30-topic-requirements.md", root=tmp_path
    )
    assert envelope["handoff_maturity"] == "pending-confirmation"
    # Also direct check: infer with root vs without
    assert HE.infer_maturity(str(target)) == "pending-confirmation"


def test_non_routable_guard(tmp_path: Path) -> None:
    brainstorms = tmp_path / "docs" / "brainstorms"
    brainstorms.mkdir(parents=True)
    target = brainstorms / "2026-08-30-topic-requirements.md"
    _write_file(target, "pending-confirmation")
    envelope = HE.build_handoff_envelope(
        "docs/brainstorms/2026-08-30-topic-requirements.md", root=tmp_path
    )
    assert envelope["handoff_maturity"] == "pending-confirmation"
    assert "/issue --prepare" not in envelope["suggested_command"]


def test_unrecognized_maturity_fails_closed(tmp_path: Path) -> None:
    brainstorms = tmp_path / "docs" / "brainstorms"
    brainstorms.mkdir(parents=True)
    # Empty maturity
    target = brainstorms / "2026-08-30-topic-requirements.md"
    target.write_text("---\nmaturity: \n---\n\nBody\n", encoding="utf-8")
    envelope = HE.build_handoff_envelope(
        "docs/brainstorms/2026-08-30-topic-requirements.md", root=tmp_path
    )
    assert "/issue --prepare" not in envelope["suggested_command"]
    # Misspelled value
    target.write_text("---\nmaturity: requirments-ready\n---\n\nBody\n", encoding="utf-8")
    envelope = HE.build_handoff_envelope(
        "docs/brainstorms/2026-08-30-topic-requirements.md", root=tmp_path
    )
    assert "/issue --prepare" not in envelope["suggested_command"]
    # Indented nested key should be ignored -> falls through to path rule (requirements-ready) but
    # if same file also has no top-level maturity, it should be ignored
    target.write_text("---\n  maturity: pending-confirmation\n---\n\nBody\n", encoding="utf-8")
    assert (
        HE.infer_maturity("docs/brainstorms/2026-08-30-topic-requirements.md", root=tmp_path)
        == "requirements-ready"
    )


def test_maturity_vocabularies_in_sync() -> None:
    # Drift guard: every code-level maturity vocabulary must be superset of HANDOFF_MATURITIES
    handoff_mats = set(HE.HANDOFF_MATURITIES)  # type: ignore[attr-defined]
    # parse_issue.py vocabulary
    import importlib.util

    spec = importlib.util.spec_from_file_location(
        "parse_issue_check", ROOT / "plugins/saga/scripts/parse_issue.py"
    )
    assert spec is not None and spec.loader is not None
    mod = importlib.util.module_from_spec(spec)
    import sys

    sys.modules[spec.name] = mod  # type: ignore[attr-defined]
    spec.loader.exec_module(mod)
    parse_vals = set(mod.HANDOFF_MATURITY_VALUES)  # type: ignore[attr-defined]
    assert parse_vals == handoff_mats, f"parse_issue vocab {parse_vals} != handoff {handoff_mats}"
    # saga-spec.md HANDOFF_MATURITIES tuple must also match
    spec_text = (ROOT / "plugins/saga/references/saga-spec.md").read_text(encoding="utf-8")
    assert "pending-confirmation" in spec_text
    for val in handoff_mats:
        assert val in spec_text, f"saga-spec missing {val}"
