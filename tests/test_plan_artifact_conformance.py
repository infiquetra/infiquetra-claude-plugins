"""Plan-artifact conformance — issue #922, unit U1.

One recursive pass over a plans root evaluates the declared frontmatter fields and the
marker triple together (R3), so a document cannot satisfy one contract and silently fail
the other. Classification follows the plan's KTD3: legacy is the absence of ``backend:``,
and nothing else — legacy documents are reported and never fail the run (R4); documents
carrying the field are new-contract and held to the full frontmatter and marker contract.
The check recurses into subdirectories so a document under ``docs/plans/`` that fails the
marker triple is reported instead of being silently accepted by the doc-review path
tie-breaker (R5).

No state store, daemon, registry, or reconciliation pass: the check is a pure function
over a directory tree, serving one operator.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path

import yaml

REPO_ROOT = Path(__file__).resolve().parent.parent
PLANS_ROOT = REPO_ROOT / "docs" / "plans"
PLAN_SKILL_MD = REPO_ROOT / "plugins" / "saga" / "skills" / "plan" / "SKILL.md"

# The marker triple, exactly as declared in plan/SKILL.md ("The body MUST use the exact
# section markers ..."). The definition-pin test asserts the declaration still carries
# these exact tokens, so neither half of the contract can drift silently (R6).
MARKER_IMPLEMENTATION_UNITS = "Implementation Units"
MARKER_KEY_TECHNICAL_DECISIONS = "Key Technical Decisions"
MARKER_U1_PREFIX_LABEL = "the `U1` U-ID prefix"
# The `U1` U-ID prefix: a heading or line beginning with the unit id (`U1.` / `U1:` / `U1 `).
U1_PREFIX_RE = re.compile(r"^#{0,6}\s*U1[.:\s]", re.MULTILINE)

BACKEND_ENUM = ("inline", "team-execution", "cc-workflows-ultracode")
REQUIRED_FIELDS = ("title", "type", "status", "date", "backend")

KIND_LEGACY_NO_BACKEND = "legacy-no-backend"
KIND_MISSING_REQUIRED_FIELD = "missing-required-field"
KIND_BACKEND_NOT_IN_ENUM = "backend-not-in-enum"
KIND_MARKER_MISSING = "marker-missing"

# The nested instance the launch receipt assigned to this unit: a non-plan document under
# docs/plans/ that the check must report rather than let through on the path tie-breaker.
NESTED_VERIFICATION_REPORT = (
    PLANS_ROOT / "plugin-fleet-ideation-2026-07-03" / "gate-g-verification-report.md"
)


@dataclass(frozen=True)
class Finding:
    path: Path
    kind: str
    detail: str
    legacy: bool

    @property
    def failing(self) -> bool:
        # KTD3 / R4: legacy findings are reported, never failing.
        return not self.legacy


def split_frontmatter(text: str) -> tuple[dict[str, object], str]:
    """Return (fields, body) for a YAML-frontmatter document.

    Absent, unterminated, or unparseable frontmatter yields empty fields and the full
    text as body — which classifies the document as legacy (no ``backend:``), never a
    crash in the corpus pass.
    """
    lines = text.splitlines()
    if not lines or lines[0].strip() != "---":
        return {}, text
    for i in range(1, len(lines)):
        if lines[i].strip() == "---":
            try:
                data = yaml.safe_load("\n".join(lines[1:i])) or {}
            except yaml.YAMLError:
                data = {}
            if not isinstance(data, dict):
                data = {}
            return data, "\n".join(lines[i + 1 :])
    return {}, text


def _missing_markers(body: str) -> list[str]:
    missing: list[str] = []
    if MARKER_IMPLEMENTATION_UNITS not in body:
        missing.append(MARKER_IMPLEMENTATION_UNITS)
    if MARKER_KEY_TECHNICAL_DECISIONS not in body:
        missing.append(MARKER_KEY_TECHNICAL_DECISIONS)
    if not U1_PREFIX_RE.search(body):
        missing.append(MARKER_U1_PREFIX_LABEL)
    return missing


def check_document(path: Path) -> list[Finding]:
    """Evaluate the frontmatter contract and the marker triple together for one document."""
    text = path.read_text(encoding="utf-8")
    fields, body = split_frontmatter(text)
    legacy = "backend" not in fields
    findings: list[Finding] = []
    if legacy:
        findings.append(
            Finding(path, KIND_LEGACY_NO_BACKEND, "no `backend:` — legacy document", legacy=True)
        )
    else:
        for name in REQUIRED_FIELDS:
            if fields.get(name) in (None, ""):
                findings.append(
                    Finding(
                        path,
                        KIND_MISSING_REQUIRED_FIELD,
                        f"missing required field `{name}`",
                        legacy=False,
                    )
                )
        value = str(fields.get("backend", "")).strip()
        if value not in BACKEND_ENUM:
            findings.append(
                Finding(
                    path,
                    KIND_BACKEND_NOT_IN_ENUM,
                    f"`backend: {value}` is not one of {' | '.join(BACKEND_ENUM)}",
                    legacy=False,
                )
            )
    for marker in _missing_markers(body):
        findings.append(
            Finding(path, KIND_MARKER_MISSING, f"missing plan marker: {marker}", legacy)
        )
    return findings


def check_plan_corpus(root: Path) -> list[Finding]:
    """One recursive pass over every markdown document under ``root`` (R3, R5)."""
    findings: list[Finding] = []
    for path in sorted(root.rglob("*.md")):
        findings.extend(check_document(path))
    return findings


def corpus_exit(findings: list[Finding]) -> int:
    return 1 if any(f.failing for f in findings) else 0


# --- fixture builders ---------------------------------------------------------------


def _frontmatter(**fields: object) -> str:
    lines = ["---", *[f"{name}: {value}" for name, value in fields.items()], "---"]
    return "\n".join(lines) + "\n"


# Body satisfying all three markers of the triple.
MARKER_BODY = """
# Fixture plan

## Implementation Units

### U1. The only unit

Do the thing.

## Key Technical Decisions

**KTD1: Do the thing.** Because it is the thing.
"""

# Body satisfying the frontmatter-adjacent expectations but missing the
# `Key Technical Decisions` marker.
BODY_MISSING_KTD = """
# Fixture plan

## Implementation Units

### U1. The only unit

Do the thing.

## Design notes

No decisions section here.
"""

NEW_CONTRACT_FRONTMATTER = {
    "title": "Fixture plan",
    "type": "feat",
    "status": "active",
    "date": "2026-08-30",
    "backend": "inline",
}


# --- positive: the contract, and the single pass -------------------------------------


def test_new_contract_plan_conforms_with_no_findings(tmp_path: Path) -> None:
    corpus = tmp_path / "plans"
    corpus.mkdir()
    good = corpus / "good-plan.md"
    good.write_text(_frontmatter(**NEW_CONTRACT_FRONTMATTER) + MARKER_BODY, encoding="utf-8")
    # Mutation mate for the required-field rule: same corpus, one required field absent.
    # Deleting the required-field rule from the check would leave this document
    # unreported, so this assertion — not the clean pass above — fails on that mutation.
    incomplete = corpus / "incomplete-plan.md"
    missing_status = {k: v for k, v in NEW_CONTRACT_FRONTMATTER.items() if k != "status"}
    incomplete.write_text(_frontmatter(**missing_status) + MARKER_BODY, encoding="utf-8")

    findings = check_plan_corpus(corpus)

    assert [f for f in findings if f.path == good] == []
    reported = [f for f in findings if f.path == incomplete]
    assert any(f.kind == KIND_MISSING_REQUIRED_FIELD and "`status`" in f.detail for f in reported)
    assert corpus_exit(findings) == 1


def test_single_pass_reports_frontmatter_and_markers_together(tmp_path: Path) -> None:
    corpus = tmp_path / "plans"
    corpus.mkdir()
    doc = corpus / "frontmatter-ok-markers-bad.md"
    doc.write_text(_frontmatter(**NEW_CONTRACT_FRONTMATTER) + BODY_MISSING_KTD, encoding="utf-8")

    # The same call that validates the frontmatter also evaluates the marker half: the
    # document satisfies the frontmatter contract and fails the marker triple, and both
    # verdicts come out of one pass. Deleting the marker half of the check removes the
    # finding this test asserts on.
    findings = check_plan_corpus(corpus)

    assert not any(f.kind == KIND_MISSING_REQUIRED_FIELD for f in findings)
    assert not any(f.kind == KIND_BACKEND_NOT_IN_ENUM for f in findings)
    marker_findings = [f for f in findings if f.path == doc and f.kind == KIND_MARKER_MISSING]
    assert any(MARKER_KEY_TECHNICAL_DECISIONS in f.detail for f in marker_findings)
    assert corpus_exit(findings) == 1


# --- negative: the legacy rule (KTD3) -------------------------------------------------


def test_missing_backend_is_legacy_reported_and_never_fails(tmp_path: Path) -> None:
    corpus = tmp_path / "plans"
    corpus.mkdir()
    legacy_plan = corpus / "legacy-plan.md"
    legacy_fields = {k: v for k, v in NEW_CONTRACT_FRONTMATTER.items() if k != "backend"}
    legacy_plan.write_text(_frontmatter(**legacy_fields) + MARKER_BODY, encoding="utf-8")
    # Whatever else it contains: no frontmatter and no markers at all.
    odd = corpus / "odd.md"
    odd.write_text("# Not much of anything\n\nNo frontmatter, no markers.\n", encoding="utf-8")

    findings = check_plan_corpus(corpus)

    assert findings, "legacy documents are reported, not silently skipped"
    assert all(f.legacy for f in findings)
    assert {f.path for f in findings if f.kind == KIND_LEGACY_NO_BACKEND} == {
        legacy_plan,
        odd,
    }
    assert any(f.path == odd and f.kind == KIND_MARKER_MISSING for f in findings)
    assert corpus_exit(findings) == 0


def test_stripped_backend_field_is_reported_without_failing(tmp_path: Path) -> None:
    # The "new document, missing required field" case. KTD3 makes absence the legacy
    # signal, so this fixture is authored as a new-contract document — carrying every
    # other required field and the new-contract markers the check keys on — and then
    # stripped of `backend:`. That class cannot exist in the real corpus by
    # construction, so the test asserts the report, never corpus membership.
    corpus = tmp_path / "plans"
    corpus.mkdir()
    doc = corpus / "stripped-plan.md"
    authored = _frontmatter(**NEW_CONTRACT_FRONTMATTER) + MARKER_BODY
    stripped = "\n".join(line for line in authored.splitlines() if not line.startswith("backend:"))
    doc.write_text(stripped + "\n", encoding="utf-8")

    findings = check_plan_corpus(corpus)

    assert [f.kind for f in findings] == [KIND_LEGACY_NO_BACKEND]
    assert all(f.legacy and not f.failing for f in findings)
    assert corpus_exit(findings) == 0


# --- negative: recursion under the scanned root ---------------------------------------


def test_check_recurses_into_subdirectories(tmp_path: Path) -> None:
    corpus = tmp_path / "plans"
    nested_dir = corpus / "sub" / "nested"
    nested_dir.mkdir(parents=True)
    nested = nested_dir / "nested-report.md"
    nested.write_text("# Nested report\n\nNo frontmatter, no plan markers.\n", encoding="utf-8")

    # Deleting the recursion (rglob -> glob) removes the nested document from the pass,
    # which is the mutation this test fails on.
    findings = check_plan_corpus(corpus)

    assert any(f.path == nested and f.kind == KIND_MARKER_MISSING for f in findings)
    assert corpus_exit(findings) == 0  # no backend -> legacy -> reported, non-failing


def test_real_corpus_reports_the_nested_verification_report() -> None:
    assert NESTED_VERIFICATION_REPORT.is_file(), (
        "the launch-receipt nested instance must exist at the base"
    )

    findings = check_plan_corpus(PLANS_ROOT)

    reported = [f for f in findings if f.path == NESTED_VERIFICATION_REPORT]
    assert reported, (
        "the nested verification report must be reported, not silently accepted by the "
        "path tie-breaker"
    )
    assert any(f.kind == KIND_MARKER_MISSING for f in reported)


def test_real_corpus_produces_a_report_and_zero_exit() -> None:
    findings = check_plan_corpus(PLANS_ROOT)

    # The assertion is on the exit and on the report being non-empty — never on a count
    # or on a file name (R33).
    assert findings
    assert corpus_exit(findings) == 0


# --- contract pin: the marker triple definition ---------------------------------------


def test_marker_triple_definition_is_pinned_unchanged() -> None:
    # Definition pin (R6), not a classification test: Document Review's recognition
    # prose lives in doc-review/SKILL.md, this unit does not own that file, and no
    # home-grown classifier stands in for it. Pin the tokens as declared in
    # plan/SKILL.md so a later edit cannot silently redefine what makes a document a
    # plan — on either side (the declaration or the check's constants).
    text = PLAN_SKILL_MD.read_text(encoding="utf-8")
    declaration = next(
        (para for para in text.split("\n\n") if "recognize the document as a plan" in para),
        None,
    )
    assert declaration is not None, "plan recognition sentence disappeared from plan/SKILL.md"
    assert "Implementation Units" in declaration
    assert "Key Technical Decisions" in declaration
    assert "`U1` U-ID prefix" in declaration
    assert MARKER_IMPLEMENTATION_UNITS == "Implementation Units"
    assert MARKER_KEY_TECHNICAL_DECISIONS == "Key Technical Decisions"
