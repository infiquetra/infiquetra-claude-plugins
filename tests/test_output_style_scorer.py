"""Regression tests for the output-style scorer.

The point of these tests is not coverage for its own sake.  A scoring script that reads a
corpus is dangerous in one specific way: when it breaks, it usually breaks by finding
*nothing*, and a metric that reads zero looks like good news rather than like a fault.  That
is exactly what happened on the first run of this scorer -- a non-recursive glob missed every
subagent transcript and reported the unreachable share of output as 0% instead of 57%.

So the tests below are weighted toward the failure modes that are silent:
  * the recursive walk that finds subagent transcripts at all
  * the two independent reach classifiers agreeing
  * each detector firing on a real positive AND staying quiet on a near-miss negative

Run with:  python3 -m pytest tests/test_output_style_scorer.py -q
"""

from __future__ import annotations

import importlib.util
import json
import os
import sys
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest

_SCORER = Path(__file__).resolve().parents[1] / "tools" / "output_style_scorer.py"
_spec = importlib.util.spec_from_file_location("output_style_scorer", _SCORER)
assert _spec and _spec.loader
scorer = importlib.util.module_from_spec(_spec)
sys.modules["output_style_scorer"] = scorer
_spec.loader.exec_module(scorer)


# --------------------------------------------------------------------------------------
# Corpus fixtures
# --------------------------------------------------------------------------------------

NOW = datetime(2026, 8, 7, 12, 0, 0, tzinfo=UTC)


def _stamp(offset_minutes: int = 0) -> str:
    return (NOW + timedelta(minutes=offset_minutes)).isoformat().replace("+00:00", "Z")


def _assistant(text: str, sidechain: bool, session: str, offset: int = 0) -> dict:
    return {
        "type": "assistant",
        "isSidechain": sidechain,
        "sessionId": session,
        "timestamp": _stamp(offset),
        "cwd": "/repo",
        "message": {"content": [{"type": "text", "text": text}]},
    }


def _human(text: str, session: str, source: str = "typed", offset: int = 0) -> dict:
    return {
        "type": "user",
        "isSidechain": False,
        "sessionId": session,
        "timestamp": _stamp(offset),
        "promptSource": source,
        "message": {"content": [{"type": "text", "text": text}]},
    }


def _write(path: Path, records: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(json.dumps(r) for r in records) + "\n")


@pytest.fixture
def corpus_root(tmp_path: Path) -> Path:
    """A miniature transcript tree with the real directory shape.

    Main thread at  projects/<repo>/<uuid>.jsonl
    Subagents at    projects/<repo>/<uuid>/subagents/agent-*.jsonl
    """
    root = tmp_path / "projects"
    _write(
        root / "-repo-alpha" / "sess-1.jsonl",
        [
            _assistant("**Done.** The build is green.\n\nWant me to merge?", False, "sess-1", 0),
            _human("go ahead", "sess-1", offset=1),
            _assistant("Merged.", False, "sess-1", 2),
        ],
    )
    _write(
        root / "-repo-alpha" / "sess-1" / "subagents" / "agent-aworker-abc.jsonl",
        [_assistant("subagent output", True, "sess-1", 1) for _ in range(3)],
    )
    return root


# --------------------------------------------------------------------------------------
# The silent-failure guards
# --------------------------------------------------------------------------------------


def test_walk_is_recursive_and_finds_subagent_transcripts(corpus_root: Path) -> None:
    """The regression that motivated this file: a flat glob reports 0% subagent share."""
    got = scorer.collect(
        [str(corpus_root)], NOW - timedelta(days=1), NOW + timedelta(days=1), set()
    )
    assert got.side_assistant_count == 3, "subagent transcripts were not walked"
    assert got.main_assistant_total == 2


def test_reach_metric_matches_between_the_two_classifiers(corpus_root: Path) -> None:
    got = scorer.collect(
        [str(corpus_root)], NOW - timedelta(days=1), NOW + timedelta(days=1), set()
    )
    reach = next(m for m in scorer.score(got) if m["metric"] == "subagent_reach_share")
    assert reach["cross_check_agrees"] is True
    assert reach["confidence"] == "exact"
    assert reach["numerator"] == 3
    assert reach["denominator"] == 5


def test_disagreeing_classifiers_are_flagged_not_silently_averaged() -> None:
    """If isSidechain ever stops being set, the report must say so rather than read zero."""
    broken = scorer.Corpus(
        main_assistant=["x"],
        main_assistant_total=1,
        side_assistant_count=0,
        side_by_path_count=99,
        main_by_path_count=1,
    )
    reach = next(m for m in scorer.score(broken) if m["metric"] == "subagent_reach_share")
    assert reach["cross_check_agrees"] is False
    assert "SUSPECT" in reach["confidence"]


def test_reach_denominator_counts_like_for_like(corpus_root: Path) -> None:
    """Tool-only main-thread turns must count in the reach basis.

    Scoring prose-bearing main-thread messages against *all* subagent messages would
    overstate the unreachable share.
    """
    tool_only = {
        "type": "assistant",
        "isSidechain": False,
        "sessionId": "sess-1",
        "timestamp": _stamp(3),
        "message": {"content": [{"type": "tool_use", "name": "Bash"}]},
    }
    _write(corpus_root / "-repo-alpha" / "sess-2.jsonl", [tool_only])
    got = scorer.collect(
        [str(corpus_root)], NOW - timedelta(days=1), NOW + timedelta(days=1), set()
    )
    assert got.main_assistant_total == 3, "tool-only turn missing from the reach basis"
    assert len(got.main_assistant) == 2, "tool-only turn must not be scored for prose shape"


# --------------------------------------------------------------------------------------
# Message classification
# --------------------------------------------------------------------------------------


def test_tool_results_are_not_counted_as_human_turns(tmp_path: Path) -> None:
    root = tmp_path / "projects"
    tool_result = _human("Bash output here", "s")
    tool_result["toolUseResult"] = {"stdout": "..."}
    hook = _human("injected by a hook", "s")
    hook["promptSource"] = "hook"
    _write(root / "-r" / "s.jsonl", [_human("a real question?", "s"), tool_result, hook])
    got = scorer.collect([str(root)], NOW - timedelta(days=1), NOW + timedelta(days=1), set())
    assert got.human == ["a real question?"]


def test_messages_outside_the_window_are_dropped(tmp_path: Path) -> None:
    root = tmp_path / "projects"
    old = _assistant("ancient", False, "s")
    old["timestamp"] = "2020-01-01T00:00:00Z"
    _write(root / "-r" / "s.jsonl", [old, _assistant("current", False, "s")])
    got = scorer.collect([str(root)], NOW - timedelta(days=1), NOW + timedelta(days=1), set())
    assert got.main_assistant == ["current"]


def test_excluded_paths_are_skipped(corpus_root: Path) -> None:
    target = str(corpus_root / "-repo-alpha" / "sess-1.jsonl")
    got = scorer.collect(
        [str(corpus_root)], NOW - timedelta(days=1), NOW + timedelta(days=1), {target}
    )
    assert got.main_assistant_total == 0
    assert got.side_assistant_count == 3


def test_session_last_message_is_last_in_time_not_last_in_file(tmp_path: Path) -> None:
    root = tmp_path / "projects"
    _write(
        root / "-r" / "s.jsonl",
        [
            _assistant("later, ends with a question?", False, "s", 10),
            _assistant("earlier and declarative.", False, "s", 1),
        ],
    )
    got = scorer.collect([str(root)], NOW - timedelta(days=1), NOW + timedelta(days=1), set())
    assert got.session_last_main["s"] == "later, ends with a question?"


def test_unparseable_lines_are_counted_not_fatal(tmp_path: Path) -> None:
    root = tmp_path / "projects"
    path = root / "-r" / "s.jsonl"
    path.parent.mkdir(parents=True)
    path.write_text("{not json\n" + json.dumps(_assistant("fine", False, "s")) + "\n")
    got = scorer.collect([str(root)], NOW - timedelta(days=1), NOW + timedelta(days=1), set())
    assert got.lines_unparsed == 1
    assert got.main_assistant == ["fine"]


# --------------------------------------------------------------------------------------
# Detectors: each must fire on a positive and stay quiet on a near-miss
# --------------------------------------------------------------------------------------


@pytest.mark.parametrize(
    "line",
    [
        "Want me to run the merge?",
        "Should I open the PR?",
        "Holding here until you weigh in.",
        "Nothing needed from you.",
        "Say the word and I will ship it.",
        "Is that the behaviour you expected?",
    ],
)
def test_closing_ask_fires_on_real_closings(line: str) -> None:
    assert scorer.CLOSING_ASK_RE.search(line)


@pytest.mark.parametrize(
    "line",
    [
        "The build is green.",
        "I merged the branch and pushed it.",
        "Two scope calls remain, and they are yours:",
        "See file.py:42 for the change.",
    ],
)
def test_closing_ask_stays_quiet_on_declaratives(line: str) -> None:
    assert not scorer.CLOSING_ASK_RE.search(line)


def test_verdict_first_requires_a_bolded_claim_not_a_heading() -> None:
    assert scorer.VERDICT_FIRST_RE.match("**The deploy failed.** Here is why.")
    assert not scorer.VERDICT_FIRST_RE.match("## Summary")
    assert not scorer.VERDICT_FIRST_RE.match("Here is what I found.")
    assert not scorer.VERDICT_FIRST_RE.match("**ok**"), "too short to be a claim"


def test_mermaid_detector_matches_fences_with_and_without_space() -> None:
    assert scorer.MERMAID_RE.search("```mermaid\ngraph TD\n```")
    assert scorer.MERMAID_RE.search("``` mermaid")
    assert not scorer.MERMAID_RE.search("we could use mermaid here")


def test_bare_identifier_fires_on_sentence_initial_ids() -> None:
    assert scorer.BARE_ID_RE.search("#656 is green.")
    assert scorer.BARE_ID_RE.search("The work is done. 458b983 fixed it.")


def test_bare_identifier_stays_quiet_when_the_noun_is_present() -> None:
    assert not scorer.BARE_ID_RE.search("Pull request #656 is green.")
    assert not scorer.BARE_ID_RE.search("The commit 458b983 fixed it.")


def test_complaint_proxy_needs_both_topic_and_corrective_register() -> None:
    """A message that merely mentions a table is not a complaint about tables."""
    praise = "That table is helpful, thanks."
    gripe = "Stop giving me mermaid diagrams in the terminal."
    assert scorer.FORMAT_LEXICON.search(praise) and not scorer.COMPLAINT_REGISTER.search(praise)
    assert scorer.FORMAT_LEXICON.search(gripe) and scorer.COMPLAINT_REGISTER.search(gripe)


# --------------------------------------------------------------------------------------
# Report shape
# --------------------------------------------------------------------------------------


def test_mountain_threshold_is_a_threshold_not_a_display_cap(tmp_path: Path) -> None:
    """The original 0.25% figure came from a `head -40` truncation, not a length cutoff.

    This test exists so that mistake cannot recur silently: every message over the
    threshold must be counted, however many there are.
    """
    root = tmp_path / "projects"
    long_text = "x" * (scorer.MOUNTAIN_CHARS + 1)
    _write(root / "-r" / "s.jsonl", [_assistant(long_text, False, "s", i) for i in range(50)])
    got = scorer.collect([str(root)], NOW - timedelta(days=1), NOW + timedelta(days=1), set())
    metric = next(m for m in scorer.score(got) if m["metric"] == "mountain_of_text_rate")
    assert metric["numerator"] == 50
    assert metric["percent"] == 100.0


def test_every_metric_carries_a_definition(corpus_root: Path) -> None:
    """A baseline is only comparable if the reader can see how each number was computed."""
    got = scorer.collect(
        [str(corpus_root)], NOW - timedelta(days=1), NOW + timedelta(days=1), set()
    )
    for metric in scorer.score(got):
        assert metric["definition"].strip(), f"{metric['metric']} has no definition"
        assert metric["denominator"] >= metric["numerator"]


def test_report_round_trips_through_json(corpus_root: Path) -> None:
    got = scorer.collect(
        [str(corpus_root)], NOW - timedelta(days=1), NOW + timedelta(days=1), set()
    )
    report = scorer.build_report(
        got, scorer.score(got), NOW - timedelta(days=1), NOW, [str(corpus_root)]
    )
    assert json.loads(json.dumps(report))["schema"] == scorer.METRIC_SCHEMA
    assert "| metric |" in scorer.to_markdown(report)


def test_empty_corpus_does_not_divide_by_zero(tmp_path: Path) -> None:
    got = scorer.collect([str(tmp_path / "nope")], NOW - timedelta(days=1), NOW, set())
    for metric in scorer.score(got):
        assert metric["percent"] == 0.0


def test_cli_writes_a_report(tmp_path: Path, corpus_root: Path, capsys) -> None:
    out = tmp_path / "nested" / "baseline.json"
    rc = scorer.main(
        [
            "--roots",
            str(corpus_root),
            "--since",
            "2026-08-01",
            "--until",
            "2026-08-08",
            "--out",
            str(out),
            "--markdown",
        ]
    )
    assert rc == 0
    assert os.path.exists(out)
    assert json.loads(out.read_text())["schema"] == scorer.METRIC_SCHEMA
    assert "subagent_reach_share" in capsys.readouterr().out
