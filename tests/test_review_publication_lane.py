"""Contract checks for the W18 review-artifact publication lane (issue infiquetra/infiquetra-sdlc#99).

The Saga Code Review contract grants a narrow publication lane — in interactive / standalone mode,
write, commit, and push the review document and submit the GitHub pull-request review — while denying
every other write, and retires the blanket commit/push prohibition from all of its carriers. These
tests read the shipped skill, command, and model text directly; they do not use a fixture that merely
repeats the intended behavior.
"""

from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).parent.parent
SKILL = ROOT / "plugins" / "saga" / "skills" / "code-review" / "SKILL.md"
COMMAND = ROOT / "plugins" / "saga" / "commands" / "code-review.md"
MODEL = ROOT / "plugins" / "saga" / "docs" / "model" / "saga-docs-model.yaml"
WORK_SKILL = ROOT / "plugins" / "saga" / "skills" / "work" / "SKILL.md"
WORK_GATES = ROOT / "plugins" / "saga" / "skills" / "work" / "references" / "test-and-gates.md"
VERIFIER_AGENT = ROOT / "plugins" / "saga" / "agents" / "readonly-verifier.md"

# The exact programmatic-mode sentence the /work staleness loop is predicated on. It must stay
# verbatim (plan KTD9 / R10): a reword that softens it re-introduces the /work loop.
PROGRAMMATIC_ZERO_WRITES_A = (
    "Write **ZERO file writes to reviewed code and ZERO ledger writes**;"
)
PROGRAMMATIC_ZERO_WRITES_B = "the caller owns durable persistence and downstream routing."

# Blanket-prohibition carriers retired by this unit; none may survive in any carrier file
# (compared after collapsing whitespace, so line wraps cannot hide a survivor).
RETIRED_BLANKET_TEXTS = (
    "and routes — without mutating code.",
    "It reports and routes — it does **not** fix, commit, push, open PRs, or file issues.",
    "It does **NOT** mutate code, does **NOT** commit, does **NOT** push, does **NOT** open or update a PR",
    "it does not mutate code, commit, push, open PRs, or file issues.",
    "Owns review findings, not fixes, commits, PR creation, or issue filing.",
)


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def _section(text: str, start_heading: str, end_heading: str) -> str:
    start = text.find(start_heading)
    end = text.find(end_heading, start + len(start_heading))
    assert start >= 0, f"missing heading: {start_heading}"
    assert end >= 0, f"missing boundary: {end_heading}"
    return text[start:end]


def _collapse(text: str) -> str:
    return " ".join(text.split())


def _hard_boundary() -> str:
    return _collapse(_section(_read(SKILL), "### 5.7 Hard boundary", "\n---\n"))


def test_hard_boundary_grants_the_interactive_publication_lane() -> None:
    boundary = _hard_boundary()
    assert "Publication lane (interactive / standalone only)" in boundary
    assert "MAY write, commit, and push its own review document" in boundary
    assert "MAY submit the GitHub pull-request review" in boundary


def test_hard_boundary_still_denies_what_the_lane_does_not_grant() -> None:
    boundary = _hard_boundary()
    assert "does **NOT** mutate reviewed source" in boundary
    assert "does **NOT** commit an implementation change" in boundary
    assert "does **NOT** open or update a PR" in boundary
    assert "does **NOT** file SDLC issues" in boundary
    # R74 grants review submission on an existing PR; PR creation stays outside the lane.
    assert "different operation from creating one" in boundary


def test_hard_boundary_states_fix_custody_and_the_evidence_rule() -> None:
    boundary = _hard_boundary()
    # R75: the reviewer hands findings back; it never authors a repair it raised.
    assert "does **NOT** implement the fixes it requests" in boundary
    assert "findings route to the author or to `/work`" in boundary
    assert "owns repair changes and implementation commits" in boundary
    # R75: the artifact commit is evidence only, and names the exact revision reviewed.
    assert "a review-artifact commit is evidence only" in boundary
    assert "full 40-character commit SHA" in boundary
    assert "`reviewed_revision:`" in boundary
    # R10/KTD9: the boundary must state what the /work loop depends on.
    assert "the reviewer commits nothing" in boundary
    assert "`HEAD` does not move" in boundary
    assert "staleness gate depends on exactly this split" in boundary


def test_reviewed_revision_rule_rejects_abbreviated_or_symbolic_values() -> None:
    """Only a full 40-hex SHA identifies the reviewed revision after the branch moves."""

    def validate(reviewed_revision: str) -> None:
        assert re.fullmatch(r"[0-9a-f]{40}", reviewed_revision) is not None, (
            "reviewed_revision must be a full 40-character commit SHA"
        )

    validate("e04f5d60e7e6b32d00608ec0223fc2368e10d77c")  # full SHA passes
    for bad in ("e04f5d6", "HEAD", "main~2", "e04f5d60e7e6b32d00608ec0223fc2368e10d77", ""):
        with_error = None
        try:
            validate(bad)  # abbreviated / symbolic / short / empty must each fail
        except AssertionError as err:
            with_error = err
        assert with_error is not None, f"validate({bad!r}) unexpectedly passed"


def test_intro_and_core_principle_carry_the_same_narrowed_grant() -> None:
    collapsed = _collapse(_read(SKILL))
    intro = _collapse(_section(_read(SKILL), "# Code Review", "## Position in the lifecycle"))
    assert "in interactive / standalone mode it may publish its own review artifact" in intro
    assert (
        "does **not** fix, mutate reviewed source, commit an implementation change, open PRs, or file issues"
        in intro
    )
    core = _collapse(_section(_read(SKILL), "1. **Gate, not fixer.**", "2. **Verify, don't guess.**"))
    assert "in interactive / standalone mode it MAY write, commit, and push the review document" in core
    assert "does **NOT** mutate reviewed source" in core
    assert "does **NOT** implement the fixes it requests" in core
    assert collapsed  # silence the unused capture when assertions above already cover the text


def test_write_step_grants_publishing_with_the_mode_qualifier() -> None:
    publish = _collapse(_section(_read(SKILL), "Publishing the artifact is", "### 5.4 "))
    assert "interactive / standalone only" in publish
    assert "commit and push the review document" in publish
    assert "reviewed_revision:" in publish
    assert "full 40-character commit SHA" in publish
    assert "evidence only, never an implementation commit" in publish


def test_command_file_carries_the_narrowed_grant_not_the_blanket_prohibition() -> None:
    collapsed = _collapse(_read(COMMAND))
    assert "In interactive mode it may publish its own review artifact" in collapsed
    assert "submit the GitHub pull-request review" in collapsed
    assert "the publication lane is interactive-mode only" in collapsed
    assert (
        "it does not mutate reviewed source, commit an implementation change, open PRs, or file issues"
        in collapsed
    )


def test_live_model_ownership_boundary_names_publication() -> None:
    entry = _section(_read(MODEL), "  code-review:", "  qa:")
    boundary = next(
        ln.split("ownership_boundary:", 1)[1].strip()
        for ln in entry.splitlines()
        if ln.strip().startswith("ownership_boundary:")
    )
    assert "review-artifact publication" in boundary
    assert "in interactive mode only" in boundary
    assert "submit the GitHub pull-request review" in boundary
    assert "Does not own fixes, implementation commits" in boundary
    # R75's boundary in the model is untouched by the lane.
    assert "The user wants code changes applied by the reviewer" in entry


def test_no_carrier_still_states_the_blanket_prohibition() -> None:
    for name, text in zip(
        ("SKILL.md", "code-review.md", "saga-docs-model.yaml"),
        (_read(SKILL), _read(COMMAND), _read(MODEL)),
    ):
        collapsed = _collapse(text)
        for blanket in RETIRED_BLANKET_TEXTS:
            needle = _collapse(blanket)
            assert needle not in collapsed, f"{name} still carries the blanket prohibition: {needle!r}"


def test_programmatic_zero_writes_sentence_is_verbatim() -> None:
    """D1 regression: the grant must not leak into the mode /work calls."""
    text = _read(SKILL)
    assert PROGRAMMATIC_ZERO_WRITES_A in text
    assert PROGRAMMATIC_ZERO_WRITES_B in text


def test_every_commit_grant_carries_an_interactive_qualifier() -> None:
    """D1 regression: an unqualified commit/push/pr-review grant anywhere is a loop hazard."""
    text = _read(SKILL)
    grant_markers = (
        "commit and push",
        "commit, and push",
        "submit the GitHub pull-request review",
        "MAY write, commit",
    )
    for para in re.split(r"\n\s*\n", text):
        if not any(marker in para for marker in grant_markers):
            continue
        if "ZERO ledger writes" in para:
            continue  # the programmatic zero-write sentence is a prohibition, not a grant
        assert re.search(r"interactive", para, re.IGNORECASE) is not None, (
            "an unqualified commit/push/pr-review grant is present (D1 hazard):\n" + para
        )


def test_work_staleness_files_carry_their_load_bearing_lines() -> None:
    """D1 integration: the staleness mechanism and REVIEWED_SHA capture survive untouched."""
    work = _read(WORK_SKILL)
    gates = _read(WORK_GATES)
    assert "REVIEWED_SHA=$(git rev-parse HEAD)" in work
    assert "git rev-list <REVIEWED_SHA>..HEAD --count" in work
    assert "git rev-list <REVIEWED_SHA>..HEAD --count" in gates
    assert "`/code-review` in programmatic mode writes no durable artifact" in gates


def test_readonly_verifier_agent_retains_no_mutation_tools() -> None:
    """The refute-N panel agent is not AE31's refusal seat, but its toolset must not widen."""
    frontmatter = _section(_read(VERIFIER_AGENT), "tools:", "\n")
    assert "Edit" not in frontmatter
    assert "Write" not in frontmatter
    for tool in ("Bash", "Read", "Grep", "Glob"):
        assert tool in frontmatter