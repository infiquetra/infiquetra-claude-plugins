"""W18 review-publication-lane contract tests (issue infiquetra/infiquetra-sdlc#99).

These tests read the shipped saga skill / command / model text directly — the same
pattern as ``test_work_review_contract.py``. They do not use a fixture that merely
repeats the intended behaviour.

The lane they pin: the Saga Code Reviewer may, in **interactive / standalone** mode
only, write, commit, and push its own review artifact and submit the GitHub
pull-request review on an existing PR — with no implementation-edit authority over
reviewed source, no PR creation, and no issue filing (R74/R75/R74's mode scope). The
other selector half lives in ``infiquetra-sdlc``'s ``tools/docs/tests/`` (the
repository verdict-vocabulary search), so ``pytest -k review_publication_lane`` is
meaningful in either repository root.

Merged from the two W18 executions (interactive lane branch aab6f1bc + plugin-review-lane
branch 9b2183e1): the authoritative branch's carrier text and D1 paragraph scan, plus the
other worker's ``dispatch_repairs`` hand-back pin, the §5.4 zero-write-skip needle, and
the committed-artifact ``reviewed_revision`` scan.
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
    r"MAY write, commit",
)

# The retired blanket prohibition, in the exact forms the carriers carried before W18.
# Compared after collapsing whitespace so line wraps cannot hide a survivor.
BLANKET_FORMS = (
    "and routes — without mutating code.",
    "It reports and routes — it does **not** fix, commit, push, open PRs, or file issues.",
    "fix, commit, push, open PRs, or file",
    "It does **NOT** mutate code, does **NOT** commit, does **NOT** push, does **NOT** open or update a PR",
    "it does not mutate code, commit, push, open PRs, or file issues.",
    "Owns review findings, not fixes, commits, PR creation, or issue filing.",
)


def _read(path: Path) -> str:
    assert path.exists(), f"missing shipped contract file: {path}"
    return path.read_text(encoding="utf-8")


def _section(text: str, start_heading: str, end_heading: str) -> str:
    start = text.find(start_heading)
    end = text.find(end_heading, start + len(start_heading))
    assert start >= 0, f"missing contract heading: {start_heading}"
    assert end >= 0, f"missing contract boundary: {end_heading}"
    return text[start:end]


def _collapse(text: str) -> str:
    return " ".join(text.split())


def _hard_boundary() -> str:
    return _section(_read(SKILL), "### 5.7 Hard boundary", "\n---\n")


def _sentences(text: str) -> list[str]:
    return re.split(r"(?<=[.!?])\s+", _collapse(text))


def test_hard_boundary_grants_the_publication_lane() -> None:
    boundary = _collapse(_hard_boundary())
    assert "write-artifact publication" not in boundary, "typo guard: the lane is review-artifact"
    assert "Publication lane (interactive / standalone only)" in boundary
    assert "MAY write, commit, and push its own review document" in boundary
    assert "MAY submit the GitHub pull-request review on an existing PR" in boundary
    assert "interactive / standalone" in boundary


def test_hard_boundary_still_denies_source_mutation_pr_creation_and_issue_filing() -> None:
    boundary = _collapse(_hard_boundary())
    assert "does **NOT** mutate reviewed source" in boundary
    assert "does **NOT** commit an implementation change" in boundary
    assert "does **NOT** open or update a PR" in boundary
    assert "does **NOT** file SDLC issues" in boundary
    # R74 grants review submission on an existing PR; PR creation stays outside the lane.
    assert "different operation from creating one" in boundary
    assert "never an implementation commit" in boundary


def test_boundary_states_the_reviewer_hands_findings_back() -> None:
    boundary = _collapse(_hard_boundary())
    assert "does **NOT** implement the fixes it requests" in boundary
    assert "findings route to the author or to `/work`" in boundary
    assert "owns repair changes and implementation commits" in boundary
    # The §5.5 routing section pins the same hand-back to the existing typed-outcome path.
    offer = _collapse(_section(_read(SKILL), "### 5.5 ", "### 5.6 "))
    assert "dispatch_repairs" in offer
    assert "never applies the fix itself" in offer


def test_evidence_rule_requires_a_full_reviewed_revision_sha() -> None:
    boundary = _collapse(_hard_boundary())
    assert "evidence only" in boundary
    assert "full 40-character" in boundary and "`reviewed_revision:`" in boundary
    # An abbreviated SHA or a symbolic ref is not a valid reviewed revision.
    assert "An abbreviated SHA or a symbolic ref like `HEAD`" in _collapse(_read(SKILL))


def test_every_grant_sentence_carries_the_interactive_mode_qualifier() -> None:
    for doc in (_read(SKILL), _read(COMMAND)):
        for sentence in _sentences(doc):
            if not any(re.search(pattern, sentence) for pattern in GRANT_PATTERNS):
                continue
            assert any(word in sentence.lower() for word in QUALIFIER), (
                f"a commit / push / pull-request-review grant appears without an "
                f"interactive / standalone qualifier — the /work programmatic-loop "
                f"regression (D1). Sentence: {sentence!r}"
            )


def test_every_commit_grant_paragraph_carries_an_interactive_qualifier() -> None:
    """Paragraph-level D1 regression (complements the sentence-level scan above)."""
    text = _read(SKILL)
    for para in re.split(r"\n\s*\n", text):
        if not any(
            marker in para
            for marker in ("commit and push", "commit, and push", "MAY write, commit")
        ):
            continue
        if "ZERO ledger writes" in para:
            continue  # the programmatic zero-write sentence is a prohibition, not a grant
        assert re.search(r"interactive", para, re.IGNORECASE) is not None, (
            "an unqualified commit/push grant is present (D1 hazard):\n" + para
        )


def test_programmatic_mode_keeps_its_zero_write_contract_verbatim() -> None:
    # The exact sentences /work's staleness gate depends on. A reword that softens
    # any of them fails here.
    skill = _read(SKILL)
    assert "Write **ZERO file writes to reviewed code and ZERO ledger writes**;" in skill
    assert (
        "In **programmatic / report-only** mode, return the serialized `review_result.v1` "
    ) in skill
    assert "the caller owns durable persistence and downstream routing." in skill
    assert (
        "In **programmatic / report-only** mode, SKIP this step entirely — the caller "
        "owns durable persistence" in _collapse(skill)
    )
    assert (
        "In programmatic mode: review and return `review_result.v1` — the caller owns "
        "persistence and routing; the reviewer commits nothing and `HEAD` does not move."
        in _collapse(_hard_boundary())
    )


def test_work_staleness_files_carry_their_load_bearing_lines() -> None:
    """D1 integration: the staleness mechanism and REVIEWED_SHA capture survive untouched."""
    work = _read(ROOT / "plugins" / "saga" / "skills" / "work" / "SKILL.md")
    gates = _read(
        ROOT / "plugins" / "saga" / "skills" / "work" / "references" / "test-and-gates.md"
    )
    assert "REVIEWED_SHA=$(git rev-parse HEAD)" in work
    assert "git rev-list <REVIEWED_SHA>..HEAD --count" in work
    assert "git rev-list <REVIEWED_SHA>..HEAD --count" in gates
    assert "`/code-review` in programmatic mode writes no durable artifact" in gates


def test_intro_and_core_principle_carry_the_same_narrowed_grant() -> None:
    intro = _collapse(_section(_read(SKILL), "# Code Review", "## Position in the lifecycle"))
    assert "It hands findings back rather than fixing them" in intro
    assert "the author or the Work process owns repair changes and implementation commits" in intro
    assert "in interactive / standalone mode it may publish its own review artifact" in intro
    assert "submit the GitHub pull-request review on an existing PR" in intro
    assert (
        "does **not** mutate reviewed source, commit an implementation change, open PRs, or file issues"
        in intro
    )
    core = _collapse(
        _section(_read(SKILL), "1. **Gate, not fixer.**", "2. **Verify, don't guess.**")
    )
    assert (
        "in interactive / standalone mode it MAY write, commit, and push the review document"
        in core
    )
    assert "MAY submit the GitHub pull-request review on an existing PR" in core
    assert "does **NOT** mutate reviewed source" in core
    assert "does **NOT** commit an implementation change" in core
    assert "with zero durable writes of any kind" in core


def test_write_step_grants_publishing_with_the_mode_qualifier() -> None:
    publish = _collapse(_section(_read(SKILL), "Publishing the artifact is", "### 5.4 "))
    assert "interactive / standalone only" in publish
    assert "commit and push the review document" in publish
    assert "never anything else" in publish
    assert "reviewed_revision:" in publish
    assert "full 40-character commit SHA" in publish
    assert "evidence only, never an implementation commit" in publish
    assert "so Work's captured reviewed SHA stays valid" in publish


def test_command_file_carries_the_narrowed_grant_not_the_blanket_prohibition() -> None:
    collapsed = _collapse(_read(COMMAND))
    assert "In interactive / standalone mode it may publish its own review artifact" in collapsed
    assert "submit the GitHub pull-request review on an existing PR" in collapsed
    assert "evidence only — the artifact names the exact revision reviewed" in collapsed
    assert "the publication lane is interactive-mode only" in collapsed
    assert (
        "it does not mutate reviewed source, commit an implementation change, open PRs, or file issues"
        in collapsed
    )


def test_live_model_ownership_boundary_names_the_lane_and_the_denial() -> None:
    entry = _section(_read(MODEL), "  code-review:", "  qa:")
    boundary = next(
        ln.split("ownership_boundary:", 1)[1].strip()
        for ln in entry.splitlines()
        if ln.strip().startswith("ownership_boundary:")
    )
    assert "review-artifact publication" in boundary
    assert "in interactive mode only" in boundary
    assert "submit the GitHub pull-request review on an existing PR" in boundary
    assert "Does not own fixes, implementation commits" in boundary
    assert "reviewed source" in boundary
    # R75's boundary in the model is untouched by the lane.
    assert "The user wants code changes applied by the reviewer" in entry


def test_no_carrier_site_still_states_the_blanket_prohibition() -> None:
    """A half-updated contract that grants the lane in one place and forbids it in
    another is worse than no change (U2 final scenario): every carrier is checked."""
    for name, text in zip(
        ("SKILL.md", "code-review.md", "saga-docs-model.yaml"),
        (_read(SKILL), _read(COMMAND), _read(MODEL)),
        strict=True,
    ):
        flat = _collapse(text)
        for blanket in BLANKET_FORMS:
            needle = _collapse(blanket)
            assert needle not in flat, (
                f"{name} still states the blanket reviewer-commit prohibition: {needle!r}"
            )


def test_readonly_verifier_agent_still_has_no_mutation_tools() -> None:
    """The refute-N panel agent is not AE31's refusal seat, but its toolset must not widen."""
    agent = _read(VERIFIER_AGENT)
    tools_line = next(line for line in agent.splitlines() if line.startswith("tools:"))
    for tool in ("Edit", "Write"):
        assert not re.search(rf"\b{tool}\b", tools_line), (
            f"readonly-verifier.md granted {tool} — the refute-N panel must stay read-only"
        )
    for tool in ("Bash", "Read", "Grep", "Glob"):
        assert tool in tools_line


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
    # a full 40-character SHA. Earlier artifacts are dated records — rewriting them
    # would corrupt the record the same way strip-every-occurrence would (KTD3's
    # dated-record boundary).
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
