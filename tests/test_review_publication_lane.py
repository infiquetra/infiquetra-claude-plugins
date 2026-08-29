"""W18 review-publication-lane contract tests (issue infiquetra/infiquetra-sdlc#99).

These tests read the shipped saga skill / command / model text directly — the same
pattern as ``test_work_review_contract.py``. They do not use a fixture that merely
repeats the intended behaviour.

The lane they pin: the Saga Code Reviewer may, in **interactive / standalone** mode
only, write, commit, and push its own review artifact and submit the GitHub
pull-request review on an existing PR — with no implementation-edit authority over
reviewed source, PR creation, or issue filing (R74/R75/R74's mode scope). The other
selector half lives in ``infiquetra-sdlc``'s ``tools/docs/tests/`` (the repository
verdict-vocabulary search), so ``pytest -k review_publication_lane`` is meaningful
in either repository root.
"""

from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).parent.parent
SKILL = ROOT / "plugins" / "saga" / "skills" / "code-review" / "SKILL.md"
COMMAND = ROOT / "plugins" / "saga" / "commands" / "code-review.md"
MODEL = ROOT / "plugins" / "saga" / "docs" / "model" / "saga-docs-model.yaml"
VERIFIER_AGENT = ROOT / "plugins" / "saga" / "agents" / "readonly-verifier.md"
CODE_REVIEWS_DIR = ROOT / "docs" / "code-reviews"

# Grant sentences must carry this qualifier; a grant without it is how the /work loop
# (D1) gets re-introduced by a later edit.
QUALIFIER = ("interactive", "standalone")
GRANT_PATTERNS = (
    r"commit,? and push",
    r"submit the (?:GitHub )?pull-request review",
)

# The retired blanket prohibition, in the exact forms the carriers carried before W18.
BLANKET_FORMS = (
    "fix, commit, push, open PRs, or file",
    "does **NOT** commit, does **NOT** push",
    "it does not\nmutate code, commit, push",
    "Owns review findings, not fixes, commits, PR creation, or issue filing",
)


def _read(path: Path) -> str:
    assert path.exists(), f"missing shipped contract file: {path}"
    return path.read_text(encoding="utf-8")


def _skill() -> str:
    return _read(SKILL)


def _section(text: str, start_heading: str, end_heading: str) -> str:
    start = text.find(start_heading)
    end = text.find(end_heading, start + len(start_heading))
    assert start >= 0, f"missing contract heading: {start_heading}"
    assert end >= 0, f"missing contract boundary: {end_heading}"
    return text[start:end]


def _collapse(text: str) -> str:
    return " ".join(text.split())


def _hard_boundary() -> str:
    return _section(_skill(), "### 5.7 Hard boundary", "\n---\n")


def _sentences(text: str) -> list[str]:
    return re.split(r"(?<=[.!?])\s+", _collapse(text))


def test_hard_boundary_grants_the_publication_lane() -> None:
    boundary = _collapse(_hard_boundary())
    assert "write-artifact publication" not in boundary, "typo guard: the lane is review-artifact"
    assert "review-artifact publication" in boundary
    assert "write, commit, and push the review artifact" in boundary
    assert "submit the GitHub pull-request review" in boundary
    assert "interactive / standalone" in boundary


def test_hard_boundary_still_denies_source_mutation_pr_creation_and_issue_filing() -> None:
    boundary = _collapse(_hard_boundary())
    assert "does **NOT** mutate reviewed source" in boundary
    assert "does **NOT** open or update a PR" in boundary
    assert "does **NOT** file SDLC issues" in boundary
    assert "never an implementation commit" in boundary


def test_boundary_states_the_reviewer_hands_findings_back() -> None:
    boundary = _collapse(_hard_boundary())
    assert "does **NOT** implement the fixes it requests" in boundary
    assert (
        "the author or the Work process owns repair changes and implementation commits" in boundary
    )
    # The §5.5 routing section pins the same hand-back to the existing typed-outcome path.
    offer = _collapse(_section(_skill(), "### 5.5 ", "### 5.6 "))
    assert "dispatch_repairs" in offer
    assert "never authors a fix for a finding it raised" in offer


def test_evidence_rule_requires_a_full_reviewed_revision_sha() -> None:
    boundary = _collapse(_hard_boundary())
    assert "evidence only" in boundary
    assert "names the exact implementation revision reviewed" in boundary
    assert "full 40-character" in boundary and "reviewed_revision" in boundary
    # An abbreviated SHA or a symbolic ref is not a valid reviewed revision.
    assert "An abbreviated SHA or a symbolic ref like `HEAD`" in _collapse(_skill())


def test_every_grant_sentence_carries_the_interactive_mode_qualifier() -> None:
    for doc in (_skill(), _read(COMMAND)):
        for sentence in _sentences(doc):
            if not any(re.search(pattern, sentence) for pattern in GRANT_PATTERNS):
                continue
            assert any(word in sentence.lower() for word in QUALIFIER), (
                f"a commit / push / pull-request-review grant appears without an "
                f"interactive / standalone qualifier — the /work programmatic-loop "
                f"regression (D1). Sentence: {sentence!r}"
            )


def test_programmatic_mode_keeps_its_zero_write_contract_verbatim() -> None:
    # The exact sentences /work's staleness gate depends on. A reword that softens
    # either fails here.
    assert (
        "Write **ZERO file writes to reviewed code and ZERO ledger writes**; "
        "the caller owns durable persistence and downstream routing." in _collapse(_skill())
    )
    assert (
        "In **programmatic / report-only** mode, SKIP this step entirely — the caller "
        "owns durable persistence" in _collapse(_skill())
    )
    assert (
        "In programmatic mode: review and return `review_result.v1` — the caller owns "
        "persistence and routing." in _collapse(_hard_boundary())
    )


def test_no_carrier_site_still_states_the_blanket_prohibition() -> None:
    # A half-updated contract that grants the lane in one place and forbids it in
    # another is worse than no change (U2 final scenario): every carrier is checked.
    carriers = [_skill(), _read(COMMAND), _read(MODEL)]
    for carrier in carriers:
        flat = _collapse(carrier)
        for blanket in BLANKET_FORMS:
            assert _collapse(blanket) not in flat, (
                f"carrier still states the blanket reviewer-commit prohibition: {blanket!r}"
            )


def test_live_model_ownership_boundary_names_the_lane_and_the_denial() -> None:
    model = _read(MODEL)
    boundary_lines = [line for line in model.splitlines() if "ownership_boundary:" in line]
    code_review_boundary = next(
        (line for line in boundary_lines if "review artifact" in line), None
    )
    assert code_review_boundary is not None, (
        "commands['code-review'].ownership_boundary no longer states the publication lane"
    )
    assert "interactive mode" in code_review_boundary
    assert "publication of its own review artifact" in code_review_boundary
    assert "submit the GitHub pull-request review" in code_review_boundary
    assert "not fixes, reviewed source, PR creation, or issue filing" in code_review_boundary


def test_readonly_verifier_agent_still_has_no_mutation_tools() -> None:
    # AE31's refusal seat for the refute-N panel is the toolset, and this unit must
    # not widen it. Its `tools:` line must stay free of Edit / Write.
    agent = _read(VERIFIER_AGENT)
    tools_line = next(line for line in agent.splitlines() if line.startswith("tools:"))
    for tool in ("Edit", "Write"):
        assert not re.search(rf"\b{tool}\b", tools_line), (
            f"readonly-verifier.md granted {tool} — the refute-N panel must stay read-only"
        )


_REVIEWED_REVISION_LINE = re.compile(r"^reviewed_revision:\s*(.+)$", re.MULTILINE)
_FULL_SHA = re.compile(r"^[0-9a-f]{40}$")


def _reviewed_revision_violations(text: str) -> list[str]:
    return [
        value.strip()
        for value in _REVIEWED_REVISION_LINE.findall(text)
        if not _FULL_SHA.fullmatch(value.strip())
    ]


def test_reviewed_revision_full_sha_rule_fails_abbreviated_and_symbolic_values() -> None:
    # R4 failure path: an abbreviated SHA or a symbolic ref fails the artifact rule;
    # only a full 40-character SHA identifies the revision after the branch moves.
    bad = "reviewed_revision: b97e0a9\n"
    bad_ref = "reviewed_revision: HEAD\n"
    good = "reviewed_revision: e04f5d60e7e6b32d00608ec0223fc2368e10d77c\n"
    assert _reviewed_revision_violations(bad) == ["b97e0a9"]
    assert _reviewed_revision_violations(bad_ref) == ["HEAD"]
    assert _reviewed_revision_violations(good) == []


def test_new_review_artifacts_record_a_full_commit_sha_as_the_reviewed_revision() -> None:
    # R4, artifact-contract side: any durable review artifact dated on or after this
    # unit's ship date that carries a `reviewed_revision:` frontmatter field must hold
    # a full 40-character SHA. Earlier artifacts are dated records — nine pre-lane
    # artifacts carry abbreviated SHAs, and rewriting them would corrupt the record
    # the same way strip-every-occurrence would (KTD3's dated-record boundary).
    lane_ship_date = "2026-08-28"
    artifacts = sorted(CODE_REVIEWS_DIR.glob("*.md")) if CODE_REVIEWS_DIR.exists() else []
    for artifact in artifacts:
        if artifact.name[:10] < lane_ship_date:
            continue
        violations = _reviewed_revision_violations(_read(artifact))
        assert not violations, (
            f"{artifact.name}: reviewed_revision value(s) {violations} are not full "
            f"40-character commit SHAs"
        )
