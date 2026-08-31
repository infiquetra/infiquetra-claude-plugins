"""Handoff maturity — frontmatter-aware inference (KTD7, issue 913 B1)."""

from __future__ import annotations

import contextlib
import importlib.util
import os
import sys
import tempfile
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
    # The decoy file lives inside the declared root (tmp_path/"other"), so by SEC-01
    # resolution it IS a trusted root-subtree path and its own frontmatter wins.
    assert (
        HE.infer_maturity(str(decoy_dir / "2026-08-30-topic-requirements.md"), root=tmp_path)
        == "requirements-ready"
    )
    # The true cwd-decoy case (SEC-01): cwd OUTSIDE the declared root, absolute path under
    # that cwd, same relative subpath — the untrusted absolute must re-anchor to the ROOT's
    # artifact, and the root-relative value ("pending-confirmation") must win with no route.
    # The decoy cwd is created inside a SEPARATE TemporaryDirectory (deleted afterward), so
    # cwd is never a subtree of the declared root — a cwd under tmp_path would be a trusted
    # root-subtree path instead.
    with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as outside_raw:
        outside = Path(outside_raw).resolve() / "cwd-root"
        (outside / "docs" / "brainstorms").mkdir(parents=True)
        (outside / "docs" / "brainstorms" / "2026-08-30-topic-requirements.md").write_text(
            "---\nmaturity: requirements-ready\n---\n\nBody\n", encoding="utf-8"
        )
        monkeypatch.chdir(outside)
        assert (
            HE.infer_maturity(
                str(outside / "docs/brainstorms/2026-08-30-topic-requirements.md"), root=tmp_path
            )
            == "pending-confirmation"
        )
        envelope_outside = HE.build_handoff_envelope(
            str(outside / "docs/brainstorms/2026-08-30-topic-requirements.md"), root=tmp_path
        )
        assert envelope_outside["handoff_maturity"] == "pending-confirmation"
        assert "/issue --prepare" not in envelope_outside["suggested_command"]
    monkeypatch.chdir(tmp_path)
    # Sanity: an absolute path INSIDE the declared root still reads its frontmatter.
    assert HE.infer_maturity(str(target), root=tmp_path) == "pending-confirmation"
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
    # Drift guard: parse_issue vocabulary must EQUAL HANDOFF_MATURITIES, saga-spec prose must
    # carry every value, and mission-control's consumer vocabulary is checked against an
    # explicit exclusion map (API-07) — see the block below for the recorded exclusion.
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
    # Third vocabulary (AM-08/API-07): mission-control's prepared-issue choices tuple,
    # loaded here directly so a future value added to HANDOFF_MATURITIES without adding it
    # here (or recording an exclusion) trips this guard. `pending-confirmation` is the one
    # deliberate exclusion, with its reason recorded in handoff_maturity_exclusions.
    mc_spec = importlib.util.spec_from_file_location(
        "mc_sdlc_check", ROOT / "plugins/mission-control/scripts/sdlc_manager.py"
    )
    assert mc_spec is not None and mc_spec.loader is not None
    mc = importlib.util.module_from_spec(mc_spec)
    sys.modules[mc_spec.name] = mc
    with pytest.MonkeyPatch.context() as mp, open(Path(os.devnull), "w") as devnull:
        mp.setattr(sys, "argv", ["sdlc_manager.py", "--help"])
        with contextlib.redirect_stdout(devnull), contextlib.suppress(SystemExit):
            mc_spec.loader.exec_module(mc)
    mc_values = set(mc._HANDOFF_MATURITY_CHOICES)  # type: ignore[attr-defined]
    handoff_maturity_exclusions: dict[str, str] = {
        "pending-confirmation": (
            "mission-control issue prepare rejects the parked/unroutable maturity with a "
            "runtime error instead of accepting it (safe direction; tracked for its own add) — "
            "see plugins/mission-control/scripts/sdlc_manager.py _HANDOFF_MATURITY_CHOICES"
        )
    }
    for val in handoff_mats - set(handoff_maturity_exclusions):
        assert val in mc_values, (
            f"mission-control handoff vocab missing {val!r}; update the exclusion map or "
            "mission-control's _HANDOFF_MATURITY_CHOICES"
        )
    for excluded, reason in handoff_maturity_exclusions.items():
        assert excluded in handoff_mats, (
            f"exclusion {excluded!r} no longer exists in HANDOFF_MATURITIES: {reason}"
        )


def test_non_delimited_frontmatter_carrier_fails_closed(tmp_path: Path) -> None:
    """AU-09: a maturity declared OUTSIDE a delimited YAML block must fail closed.

    A bullet-carrier document under docs/brainstorms/ declaring pending-confirmation used to
    fall through to the path rule and return requirements-ready with a live route — the more
    dangerous input got the softer treatment than a mere typo.
    """
    brainstorms = tmp_path / "docs" / "brainstorms"
    brainstorms.mkdir(parents=True)
    target = brainstorms / "2026-08-30-topic-requirements.md"
    target.write_text(
        "# Some doc\n\n- date: 2026-08-30\n- maturity: pending-confirmation\n\nBody\n",
        encoding="utf-8",
    )
    envelope = HE.build_handoff_envelope(
        "docs/brainstorms/2026-08-30-topic-requirements.md", root=tmp_path
    )
    assert envelope["handoff_maturity"].startswith("unknown:")
    assert "/issue --prepare" not in envelope["suggested_command"]
    # A file with NO maturity mention anywhere keeps the legacy path-default behaviour.
    plain = brainstorms / "2026-08-30-plain-requirements.md"
    plain.write_text("# No maturity here\n\nJust prose.\n", encoding="utf-8")
    assert HE.infer_maturity(str(plain)) == "requirements-ready"


def test_bom_prefixed_frontmatter_still_fails_closed(tmp_path: Path) -> None:
    """API-09/CORR-09: a byte-order mark must not make a declared maturity invisible."""
    brainstorms = tmp_path / "docs" / "brainstorms"
    brainstorms.mkdir(parents=True)
    target = brainstorms / "2026-08-30-topic-requirements.md"
    target.write_bytes(b"\xef\xbb\xbf---\nmaturity: pending-confirmation\n---\n\nBody\n")
    envelope = HE.build_handoff_envelope(
        "docs/brainstorms/2026-08-30-topic-requirements.md", root=tmp_path
    )
    assert envelope["handoff_maturity"] == "pending-confirmation"
    assert "/issue --prepare" not in envelope["suggested_command"]


def test_quoted_declared_maturity_resolves(tmp_path: Path) -> None:
    """TEST-09: quote-stripping is load-bearing — a quoted valid value must still route."""
    brainstorms = tmp_path / "docs" / "brainstorms"
    brainstorms.mkdir(parents=True)
    double = brainstorms / "2026-08-30-double-requirements.md"
    double.write_text('---\nmaturity: "pending-confirmation"\n---\n\nBody\n', encoding="utf-8")
    assert HE.infer_maturity(str(double)) == "pending-confirmation"
    single = brainstorms / "2026-08-30-single-requirements.md"
    single.write_text("---\nmaturity: 'pending-confirmation'\n---\n\nBody\n", encoding="utf-8")
    assert HE.infer_maturity(str(single)) == "pending-confirmation"


def test_envelope_schema_version_pinned(tmp_path: Path) -> None:
    """AM-11: envelope schema_version literal carries a drift guard."""
    brainstorms = tmp_path / "docs" / "brainstorms"
    brainstorms.mkdir(parents=True)
    target = brainstorms / "2026-08-30-schema-requirements.md"
    target.write_text("---\nmaturity: requirements-ready\n---\n\nBody\n", encoding="utf-8")
    envelope = HE.build_handoff_envelope(
        "docs/brainstorms/2026-08-30-schema-requirements.md", root=tmp_path
    )
    assert envelope["schema_version"] == "1.1"
    spec_text = (ROOT / "plugins/saga/references/saga-spec.md").read_text(encoding="utf-8")
    assert "1.1" in spec_text
    assert "handoff envelope" in spec_text.lower()


def test_carrier_diagnostic_names_delimiters_not_vocabulary(tmp_path: Path) -> None:
    """AM-12: carrier diagnostic must name the missing delimiters, not the vocabulary."""
    brainstorms = tmp_path / "docs" / "brainstorms"
    brainstorms.mkdir(parents=True)
    target = brainstorms / "2026-08-30-carrier-requirements.md"
    # Valid vocabulary value but declared outside delimited block (bullet carrier)
    target.write_text(
        "- maturity: pending-confirmation\n\nBody\n",
        encoding="utf-8",
    )
    assert HE.infer_maturity(str(target)).startswith("unknown:carrier:")
    envelope = HE.build_handoff_envelope(
        "docs/brainstorms/2026-08-30-carrier-requirements.md", root=tmp_path
    )
    assert envelope["handoff_maturity"].startswith("unknown:carrier:")
    assert "/issue --prepare" not in envelope["suggested_command"]
    # Diagnostic must name delimiters, not claim unrecognized value
    assert "delimited" in envelope["suggested_command"].lower()
    assert (
        "carrier" in envelope["suggested_command"].lower()
        or "delimiters" in envelope["suggested_command"].lower()
    )


def test_unterminated_frontmatter_block_fails_closed(tmp_path: Path) -> None:
    """API-13/CORR-15: unterminated block (opening --- without closing ---) must fail closed."""
    brainstorms = tmp_path / "docs" / "brainstorms"
    brainstorms.mkdir(parents=True)
    target = brainstorms / "2026-08-30-unterminated-requirements.md"
    target.write_text(
        "---\nmaturity: pending-confirmation\n\nBody without closing delimiter", encoding="utf-8"
    )
    assert HE.infer_maturity(str(target)).startswith("unknown:unterminated:")
    envelope = HE.build_handoff_envelope(
        "docs/brainstorms/2026-08-30-unterminated-requirements.md", root=tmp_path
    )
    assert "/issue --prepare" not in envelope["suggested_command"]
    # Also test with bullet carrier inside unterminated? No, just ensure no route
    # And test that missing closing delimiter with valid routable value also fails closed
    target2 = brainstorms / "2026-08-30-unterminated2-requirements.md"
    target2.write_text("---\nmaturity: requirements-ready\n\nBody", encoding="utf-8")
    assert HE.infer_maturity(str(target2)).startswith("unknown:unterminated:")
    envelope2 = HE.build_handoff_envelope(
        "docs/brainstorms/2026-08-30-unterminated2-requirements.md", root=tmp_path
    )
    assert "/issue --prepare" not in envelope2["suggested_command"]


def test_sentinel_length_bound(tmp_path: Path) -> None:
    """TEST-14: sentinel truncation bounds unbounded author-controlled text."""
    brainstorms = tmp_path / "docs" / "brainstorms"
    brainstorms.mkdir(parents=True)
    target = brainstorms / "2026-08-30-long-requirements.md"
    long_value = "x" * 300
    target.write_text(f"---\nmaturity: {long_value}\n---\n\nBody\n", encoding="utf-8")
    maturity = HE.infer_maturity(str(target))
    assert maturity.startswith("unknown:")
    # infer returns full raw; envelope truncates to 120 chars after prefix (API-12)
    assert len(maturity) == len("unknown:") + 300
    envelope = HE.build_handoff_envelope(
        "docs/brainstorms/2026-08-30-long-requirements.md", root=tmp_path
    )
    assert len(envelope["handoff_maturity"]) == len("unknown:") + 120  # type: ignore[index]
    assert "/issue --prepare" not in envelope["suggested_command"]


def test_blank_carrier_fails_closed(tmp_path: Path) -> None:
    """TEST-15: blank-value non-delimited carrier must fail closed with bare sentinel."""
    brainstorms = tmp_path / "docs" / "brainstorms"
    brainstorms.mkdir(parents=True)
    target = brainstorms / "2026-08-30-blank-carrier-requirements.md"
    target.write_text("- maturity: \n\nBody\n", encoding="utf-8")
    maturity = HE.infer_maturity(str(target))
    assert maturity == "unknown:carrier:"
    envelope = HE.build_handoff_envelope(
        "docs/brainstorms/2026-08-30-blank-carrier-requirements.md", root=tmp_path
    )
    assert "/issue --prepare" not in envelope["suggested_command"]


def test_read_failure_fails_closed(tmp_path: Path) -> None:
    """API-15/CORR-15: read/decode failure must fail closed with distinct sentinel."""
    brainstorms = tmp_path / "docs" / "brainstorms"
    brainstorms.mkdir(parents=True)
    target = brainstorms / "2026-08-30-unreadable-requirements.md"
    # Write bytes that are not valid UTF-8 and contain no recoverable frontmatter
    # (so the retry logic cannot extract a maturity and must return the unreadable sentinel)
    target.write_bytes(b"\xff\xfe\xfd\xfc\xfb")
    maturity = HE.infer_maturity(str(target))
    assert maturity == "unknown:unreadable"
    envelope = HE.build_handoff_envelope(
        "docs/brainstorms/2026-08-30-unreadable-requirements.md", root=tmp_path
    )
    assert "/issue --prepare" not in envelope["suggested_command"]
    assert "unreadable" in envelope["suggested_command"].lower()
    # Valid frontmatter with invalid body byte should still be classified, not unreadable
    valid = brainstorms / "2026-08-30-valid-with-bad-body-requirements.md"
    valid.write_bytes(b"---\nmaturity: pending-confirmation\n---\n\nBody \xe9\n")
    assert HE.infer_maturity(str(valid)) == "pending-confirmation"


def test_reanchored_missing_fallback_to_original(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """CORR-13: re-anchored subpath missing must fallback to original absolute, not path rule."""
    # Root has no docs/brainstorms/b.md, but absolute file outside root declares pending-confirmation
    outside = Path(tempfile.mkdtemp()) / "outside"
    (outside / "docs" / "brainstorms").mkdir(parents=True)
    abs_file = outside / "docs" / "brainstorms" / "2026-08-30-missing-reanchored-requirements.md"
    abs_file.write_text("---\nmaturity: pending-confirmation\n---\n\nBody\n", encoding="utf-8")
    # Ensure root has no such subpath
    assert not (
        tmp_path / "docs" / "brainstorms" / "2026-08-30-missing-reanchored-requirements.md"
    ).exists()
    # Infer with root declared as tmp_path, source is absolute outside root
    maturity = HE.infer_maturity(str(abs_file), root=tmp_path)
    assert maturity == "pending-confirmation"
    envelope = HE.build_handoff_envelope(str(abs_file), root=tmp_path)
    assert envelope["handoff_maturity"] == "pending-confirmation"
    assert "/issue --prepare" not in envelope["suggested_command"]


def test_no_checked_in_artifact_declares_non_vocab_maturity() -> None:
    """CORR-17: repository check — no checked-in artifact declares a non-vocabulary maturity."""
    allowed = set(HE.HANDOFF_MATURITIES)
    source_dirs = [
        ROOT / "docs" / d
        for d in ["ideation", "brainstorms", "specs", "plans", "reviews", "work-sessions"]
    ]
    bad: list[tuple[str, str]] = []
    for base in source_dirs:
        if not base.exists():
            continue
        for path in base.rglob("*.md"):
            try:
                text = path.read_text(encoding="utf-8")
            except (OSError, UnicodeDecodeError):
                continue
            if not text.startswith("---"):
                continue
            end = text.find("\n---", 3)
            if end == -1:
                continue
            frontmatter = text[3:end]
            for line in frontmatter.splitlines():
                if line.startswith("maturity:"):
                    raw = (
                        line.split(":", 1)[1].strip().split("#", 1)[0].strip().strip("\"'").strip()
                    )
                    if raw and raw not in allowed:
                        bad.append((str(path.relative_to(ROOT)), raw))
                    break
    assert not bad, (
        f"checked-in artifacts declare non-vocab maturity outside HANDOFF_MATURITIES: {bad}"
    )
