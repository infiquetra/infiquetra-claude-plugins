"""Issue #926 (unit P5, issue 918 Wave Two): Plan skill <-> saga-spec drift checks.

Two cheap guards against the documentation drift this unit repairs, both derived
from the documents rather than restated beside them:

* ``test_plan_docs_reject_unhonored_effort_claims`` — no Markdown file under
  ``plugins/saga/`` may claim resolved effort is emitted but not consumed,
  honored, dispatched, or enforced. It matches the *class* of claim (an effort
  token sharing one span with a negation governing an honor-class verb, or the
  standalone ``emission only`` idiom), never one literal sentence.
* ``test_saga_spec_plan_consumer_row_matches_skill`` — the saga-spec ``/plan``
  consumer row lists exactly the fields Plan's Phase 5.3 save blocks write.
  The expected set is derived from the skill's own fenced ``saga.py save``
  blocks (union across variants, minus the ``--kind``/``--id`` identity flags);
  the row is parsed per the convention stated beside it (backticked identifiers
  outside parentheses). No second hardcoded field list lives here.

Mutation proof: restoring the pre-repair effort comment fails the first test,
and adding a flag to a Phase 5.3 save block (or deleting a field from the row)
fails the second. A check that cannot fail is the defect class this repository
has hit before.

Known duplicate outside this scope: a second copy of the stale effort claim
lives at ``plugins/team-execution/skills/team-execution/SKILL.md`` under a
named follow-up issue. The negative check is deliberately scoped to
``plugins/saga/``; widening it to ``plugins/`` belongs to that follow-up.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

ROOT = Path(__file__).parent.parent
PLUGIN_ROOT = ROOT / "plugins" / "saga"
PLAN_SKILL = PLUGIN_ROOT / "skills" / "plan" / "SKILL.md"
SAGA_SPEC = PLUGIN_ROOT / "references" / "saga-spec.md"

# ---------------------------------------------------------------------------
# Negative check: no "effort is emitted but unhonored" claim under plugins/saga/
# ---------------------------------------------------------------------------

_EFFORT_TOKEN = re.compile(r"effort", re.IGNORECASE)
_EMISSION_ONLY = re.compile(r"emission\s+only", re.IGNORECASE)
_NEGATION_GOVERNS_UNHONORED = re.compile(
    r"\b(no|not|never|nothing|none|lacks|awaits|yet)\b"
    r"(?:\W+\w+){0,5}?\W+"
    r"(consum\w*|honor\w*|honour\w*|dispatch\w*|enforc\w*|read\w*)",
    re.IGNORECASE,
)
# A sentence is split into clauses on [,;:] and dashes before matching, so a
# negation governing an honor-class verb must share one *clause* with the
# effort token — mere co-occurrence across a 700-line file, or across the two
# halves of a "do X, not by reading it" instruction, is not a match. HTML
# comment blocks stay whole: the stale claim spans source lines, which is what
# a line-oriented grep misses.
_CLAUSE_SPLIT = re.compile(r"[,;:—–]\s*")


def _claim_spans(text: str) -> list[str]:
    """Every ``<!-- ... -->`` block plus every prose clause, whitespace-folded."""
    spans = re.findall(r"<!--(.*?)-->", text, flags=re.DOTALL)
    prose = re.sub(r"<!--.*?-->", " ", text, flags=re.DOTALL)
    for sentence in re.split(r"(?<=[.!?])\s+", prose):
        spans.extend(_CLAUSE_SPLIT.split(sentence))
    return [" ".join(span.split()) for span in spans if span.strip()]


def _unhonored_effort_match(span: str) -> str | None:
    """Name which claim half a span matches, or ``None`` when it is clean."""
    if not _EFFORT_TOKEN.search(span):
        return None
    if _EMISSION_ONLY.search(span):
        return "emission-only idiom"
    match = _NEGATION_GOVERNS_UNHONORED.search(span)
    if match:
        return f"negation governing honor-class verb: {match.group(0)[:80]!r}"
    return None


def test_plan_docs_reject_unhonored_effort_claims() -> None:
    """No Saga document claims resolved effort is emitted but unhonored.

    Mutation proof: restoring the pre-repair ``EFFORT-EMISSION MARKER`` comment
    fails this test naming that file and span; a reworded relapse ("the effort
    half is surfaced but nothing honors it") fails it too, proving the pattern
    catches the class and not the original wording.
    """
    failures = [
        (str(path.relative_to(ROOT)), _unhonored_effort_match(span), span[:200])
        for path in sorted(PLUGIN_ROOT.rglob("*.md"))
        for span in _claim_spans(path.read_text(encoding="utf-8"))
        if _unhonored_effort_match(span) is not None
    ]
    assert not failures, "Saga docs claim effort is emitted but unhonored:\n" + "\n".join(
        f"{file}: [{why}] {span}" for file, why, span in failures[:5]
    )

    # Rewording proof: a differently worded relapse is still caught.
    assert _unhonored_effort_match("the effort half is surfaced but nothing honors it")
    # Multi-line proof: a claim split across source lines is one span, not two.
    assert _unhonored_effort_match(
        "<!-- effort note: this is emission only:\nno dispatch mechanism honors it -->"
    )
    # False-positive guards: the two legitimate "unconsumed" uses carry no
    # effort token in their span, so the conjunction excludes both.
    assert (
        _unhonored_effort_match(
            "previously-unconsumed engine loophole (the merge queue's tokenless R12 auto-merge)"
        )
        is None
    )
    assert (
        _unhonored_effort_match('errors = [f"proof-integrity: launched-unconsumed {key}"]') is None
    )
    # Self-pass guard: the repaired comment pairs "honoring seam" with "no
    # per-call effort parameter" ~40 words apart across clauses, which the
    # proximity-bound pattern must not match.
    repaired = next(
        span
        for span in _claim_spans(PLAN_SKILL.read_text(encoding="utf-8"))
        if "honoring seam" in span
    )
    assert _unhonored_effort_match(repaired) is None


# ---------------------------------------------------------------------------
# Positive check: the /plan consumer row equals what Phase 5.3 writes
# ---------------------------------------------------------------------------

_IDENTITY_FLAGS = frozenset({"kind", "id"})


def _plan_phase_53() -> str:
    """Return the Phase 5.3 section of plan/SKILL.md (up to Phase 5.4)."""
    text = PLAN_SKILL.read_text(encoding="utf-8")
    start = text.index("### 5.3")
    end = text.index("### 5.4", start)
    return text[start:end]


def _save_blocks(section: str) -> list[str]:
    """Every fenced block in a section that runs ``saga.py save``."""
    blocks = re.findall(r"```[a-z]*\n(.*?)```", section, flags=re.DOTALL)
    save_blocks = [block for block in blocks if "saga.py save" in block]
    assert save_blocks, "Phase 5.3 must contain runnable saga save command block(s)"
    return save_blocks


def _flags_of(block: str) -> set[str]:
    """Flag names in one save block, normalized to stored field names."""
    return {flag.replace("-", "_") for flag in re.findall(r"--([a-z][a-z0-9-]*)", block)}


def _skill_field_set() -> set[str]:
    """Union of Phase 5.3 save-block flags, minus the identity flags."""
    fields = set().union(*(_flags_of(block) for block in _save_blocks(_plan_phase_53())))
    return fields - _IDENTITY_FLAGS


def _plan_row_line(spec_text: str) -> str:
    """The ``| **/plan**`` consumer-table row of a saga-spec text."""
    matches = [line for line in spec_text.splitlines() if line.strip().startswith("| **/plan**")]
    assert len(matches) == 1, f"expected exactly one /plan consumer row, found {len(matches)}"
    return matches[0]


def _row_field_set(spec_text: str | None = None) -> set[str]:
    """Backticked identifiers outside parentheses in the /plan Writes cell."""
    text = SAGA_SPEC.read_text(encoding="utf-8") if spec_text is None else spec_text
    cells = [cell.strip() for cell in _plan_row_line(text).strip().split("|")[1:-1]]
    assert len(cells) >= 3, "the /plan consumer row must have a Writes cell"
    deparen = re.sub(r"\([^)]*\)", " ", cells[2])
    return set(re.findall(r"`([a-z][a-z_]*)", deparen))


def test_saga_spec_plan_consumer_row_matches_skill() -> None:
    """The /plan consumer row names exactly what Phase 5.3's save blocks write.

    Mutation proof: adding a flag to a Phase 5.3 save block without updating
    the row fails this test naming the skill-side orphan, and deleting a field
    from the row without removing its flag fails it naming the row-side orphan.
    The expected set is derived from the skill, never restated here.
    """
    expected = _skill_field_set()
    assert expected, "an empty skill-derived field set must never read as agreement"
    row = _row_field_set()
    assert row, "an empty row field set must never read as agreement"
    assert expected == row, (
        "the /plan consumer row drifted from Phase 5.3: "
        f"in the skill but not the row: {sorted(expected - row)}; "
        f"in the row but not the skill: {sorted(row - expected)}"
    )

    # Union-across-variants proof: --deploy-autonomy and --orchestration-ref
    # each live in only one save block, so an intersection would under-specify.
    per_block = [_flags_of(block) for block in _save_blocks(_plan_phase_53())]
    assert any(
        "deploy_autonomy" in flags and "orchestration_ref" not in flags for flags in per_block
    )
    assert any(
        "orchestration_ref" in flags and "deploy_autonomy" not in flags for flags in per_block
    )

    # Parse-stability proof: parenthesized asides name no stored field.
    raw_row = _plan_row_line(SAGA_SPEC.read_text(encoding="utf-8"))
    assert re.search(r"\([^)]*destination=nonprod-deploy[^)]*\)", raw_row)
    assert "orchestration_operator_choice" in raw_row
    assert "orchestration_operator_choice" not in row

    # Error path: a missing row fails naming the row, never silently or with
    # an IndexError on an empty set.
    rowless = "\n".join(
        line
        for line in SAGA_SPEC.read_text(encoding="utf-8").splitlines()
        if not line.strip().startswith("| **/plan**")
    )
    with pytest.raises(AssertionError, match="exactly one /plan consumer row"):
        _row_field_set(rowless)
