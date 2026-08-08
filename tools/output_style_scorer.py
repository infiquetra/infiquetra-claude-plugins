#!/usr/bin/env python3
"""Score Claude Code transcripts for the output-presentation behaviours we are trying to change.

Why this exists
---------------
The output-styles ideation run of 2026-08-07 measured a set of presentation problems from
35 days of real transcripts.  Those measurements were taken with throwaway scripts, and
several of them were produced by hand-labelling messages that a human had already read.
That is fine once.  It is useless as a baseline, because a hand-labelled number cannot be
recomputed later and therefore cannot be compared against.

This script replaces the throwaway work with detectors that will fire on transcripts nobody
has read yet, so the same numbers can be produced again after an output style ships and the
two runs can be compared.

Every metric below carries an explicit DEFINITION string that is emitted with the result.
If a definition changes, old baselines are no longer comparable -- bump METRIC_SCHEMA.

What is and is not mechanical
-----------------------------
Reach, message length, mermaid usage, closing shape and opening shape are counted exactly.
Complaint rates are NOT.  The original 5.6% format / 7.2% clarity figures came from a human
reading 765 messages.  This script computes a keyword-lexicon proxy instead, which will not
reproduce those percentages and is not supposed to.  Compare proxy to proxy across runs; the
hand-labelled figures are recorded in the baseline document as historical context only.

Usage
-----
    python3 tools/output_style_scorer.py --days 35 --out docs/measurements/baseline.json
    python3 tools/output_style_scorer.py --since 2026-07-03 --until 2026-08-07 --markdown

Standard library only, so it runs anywhere without an environment.
"""

from __future__ import annotations

import argparse
import glob
import json
import os
import re
import sys
from collections import Counter
from collections.abc import Iterator
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from typing import Any

# Bump when any DEFINITION below changes; baselines with a different schema are not comparable.
METRIC_SCHEMA = 1

DEFAULT_ROOTS = [
    "/Users/jefcox/.claude/projects",
    "/Users/jefcox/.claude-company/projects",
]

# A user message only counts as a real human turn when it came from the keyboard.  Everything
# else in the `user` slot is tool output, hook injection, or a system-authored continuation.
GENUINE_PROMPT_SOURCES = {"typed", "queued", "suggestion_accepted"}

# Main-thread assistant messages at or above this many characters count as a wall of text.
# 4000 is the empirical cutoff from the 2026-08-07 run (the 40 longest messages of 16,029).
MOUNTAIN_CHARS = 4000

# --------------------------------------------------------------------------------------
# Detectors
# --------------------------------------------------------------------------------------

# A closing ask: the final non-empty line either asks a question outright, states a
# pre-committed branch, or explicitly hands control back.  Anything else means the turn
# ended on a declarative fact and the reader is left to work out whether it is their move.
CLOSING_ASK_RE = re.compile(
    r"(\?\s*$)"
    r"|(\b(want|would you like|shall i|should i|do you want|ok to|okay to)\b)"
    r"|(\b(holding|standing by|waiting|blocked) (here |on )?(until|for|on)\b)"
    r"|(\bnothing (is )?needed from you\b)"
    r"|(\bsay (the word|go)\b)"
    r"|(\bif you (say|confirm|approve)\b)",
    re.IGNORECASE,
)

# A verdict-first opening: the first non-empty line leads with a bolded claim.  Markdown
# headings do not count -- a heading names a section, it does not state a finding.
VERDICT_FIRST_RE = re.compile(r"^\s*\*\*[^*]{4,}?\*\*")

MERMAID_RE = re.compile(r"```\s*mermaid\b", re.IGNORECASE)

# A bare identifier used as a noun: an issue/PR number or a short commit SHA that opens a
# sentence with no preceding common noun naming what it is.  Heuristic by construction --
# it is a trend line, not a verdict on any single message.
BARE_ID_RE = re.compile(
    r"(?:(?<=^)|(?<=[.!?]\s)|(?<=\n))\s*(#\d{1,5}|[0-9a-f]{7,10})\b(?!\s*(?:is a|refers))",
)

# Words that name the presentation itself.  Used only to bound the complaint proxy: a
# message must look like feedback AND mention presentation to count.
FORMAT_LEXICON = re.compile(
    r"\b(mermaid|ascii|diagram|chart|graph|table|picture|render|format|markdown|bullet"
    r"|wall of text|mountain of text|too long|verbose|too much text)\b",
    re.IGNORECASE,
)

CLARITY_LEXICON = re.compile(
    r"\b(unclear|confusing|confused|jargon|acronym|abbreviat|plain english|plain language"
    r"|what do you mean|what does that mean|i don'?t (know|understand|even know) what"
    r"|makes no sense|no idea what|be (clear|specific)|in english)\b",
    re.IGNORECASE,
)

# Negative or corrective register.  Without this, "here is a table" scores as a complaint.
COMPLAINT_REGISTER = re.compile(
    r"(\b(stop|don'?t|do not|never|quit|no more|instead of|rather than|too many|too much"
    r"|not helpful|useless|wrong|why (are|do) you|i (asked|said|told you))\b)"
    r"|(\b(fuck|shit|christ|goddamn)\b)",
    re.IGNORECASE,
)


# --------------------------------------------------------------------------------------
# Corpus walk
# --------------------------------------------------------------------------------------


@dataclass
class Corpus:
    """Every message we care about, already classified, plus the session grouping."""

    # Prose-bearing main-thread messages. Shape metrics score these, because a turn that is
    # only a tool call has no prose to have a verdict or a closing ask.
    main_assistant: list[str] = field(default_factory=list)
    # Every main-thread assistant message including tool-only turns. The reach metric uses
    # this so both sides of the ratio count the same kind of thing.
    main_assistant_total: int = 0
    side_assistant_count: int = 0
    human: list[str] = field(default_factory=list)
    # Independent cross-check on the reach metric: assistant messages counted by where the
    # transcript lives rather than by the isSidechain field. If these two disagree, the
    # schema has changed underneath us and the reach number must not be trusted.
    side_by_path_count: int = 0
    main_by_path_count: int = 0
    # session id -> the text of its final main-thread assistant message
    session_last_main: dict[str, str] = field(default_factory=dict)
    # session id -> timestamp of that final message, so "final" means final in time
    session_last_ts: dict[str, str] = field(default_factory=dict)
    files_scanned: int = 0
    lines_unparsed: int = 0
    cwds: Counter[str] = field(default_factory=Counter)


def _text_of(message: dict[str, Any]) -> str:
    """Pull the human-visible prose out of a message, ignoring tool calls and thinking."""
    content = message.get("content")
    if isinstance(content, str):
        return content
    if not isinstance(content, list):
        return ""
    parts = [
        block.get("text", "")
        for block in content
        if isinstance(block, dict) and block.get("type") == "text"
    ]
    return "\n".join(parts)


def _iter_transcripts(roots: list[str], since: datetime) -> Iterator[str]:
    """Yield transcript paths whose mtime is inside the window.

    The walk must be recursive.  Main-thread sessions sit at `projects/<repo>/<uuid>.jsonl`,
    but subagent transcripts are one level deeper, at
    `projects/<repo>/<uuid>/subagents/agent-*.jsonl`.  A non-recursive glob sees only the
    main thread and reports the subagent share as zero, which reads as good news instead of
    as a broken metric.

    Filtering on mtime first is a cheap pre-filter only; every message is re-checked
    against its own timestamp during parsing, because a long-lived session file can hold
    messages from well before the window.
    """
    for root in roots:
        if not os.path.isdir(root):
            continue
        for path in glob.glob(os.path.join(root, "**", "*.jsonl"), recursive=True):
            try:
                mtime = datetime.fromtimestamp(os.path.getmtime(path), tz=UTC)
            except OSError:
                continue
            if mtime >= since:
                yield path


def collect(roots: list[str], since: datetime, until: datetime, exclude: set[str]) -> Corpus:
    corpus = Corpus()
    for path in _iter_transcripts(roots, since):
        if path in exclude:
            continue
        corpus.files_scanned += 1
        is_subagent_file = f"{os.sep}subagents{os.sep}" in path
        # OSError is caught around the whole read, not just the open: a live session can
        # rotate or delete a transcript mid-walk, which is a fact about the corpus rather
        # than a fault worth failing the run over.
        try:
            with open(path, errors="replace") as handle:
                _scan_lines(handle, corpus, path, is_subagent_file, since, until)
        except OSError:
            continue

    return corpus


def _scan_lines(
    handle: Any, corpus: Corpus, path: str, is_subagent_file: bool, since: datetime, until: datetime
) -> None:
    """Classify every record in one transcript into the corpus."""
    for line in handle:
        line = line.strip()
        if not line:
            continue
        try:
            record = json.loads(line)
        except json.JSONDecodeError:
            corpus.lines_unparsed += 1
            continue
        stamp = record.get("timestamp")
        if isinstance(stamp, str):
            try:
                when = datetime.fromisoformat(stamp.replace("Z", "+00:00"))
            except ValueError:
                when = None
            if when is not None and not (since <= when <= until):
                continue

        kind = record.get("type")
        sidechain = record.get("isSidechain")

        if kind == "assistant":
            if is_subagent_file:
                corpus.side_by_path_count += 1
            else:
                corpus.main_by_path_count += 1
            if sidechain is True:
                corpus.side_assistant_count += 1
                continue
            if sidechain is not False:
                continue
            corpus.main_assistant_total += 1
            text = _text_of(record.get("message", {}))
            if not text.strip():
                # A tool-call-only turn has no prose and cannot be scored on shape.
                continue
            corpus.main_assistant.append(text)
            if cwd := record.get("cwd"):
                corpus.cwds[cwd] += 1
            session = record.get("sessionId") or path
            prev = corpus.session_last_ts.get(session)
            if prev is None or (isinstance(stamp, str) and stamp >= prev):
                corpus.session_last_main[session] = text
                corpus.session_last_ts[session] = stamp or ""

        elif kind == "user":
            if sidechain is not False or "toolUseResult" in record:
                continue
            if record.get("promptSource") not in GENUINE_PROMPT_SOURCES:
                continue
            text = _text_of(record.get("message", {}))
            if text.strip():
                corpus.human.append(text)


# --------------------------------------------------------------------------------------
# Metrics
# --------------------------------------------------------------------------------------


def _rate(numerator: int, denominator: int) -> float:
    return round(100.0 * numerator / denominator, 3) if denominator else 0.0


def _metric(key: str, definition: str, num: int, den: int, **extra: Any) -> dict[str, Any]:
    return {
        "metric": key,
        "definition": definition,
        "numerator": num,
        "denominator": den,
        "percent": _rate(num, den),
        **extra,
    }


def _last_line(text: str) -> str:
    lines = [ln.strip() for ln in text.strip().splitlines() if ln.strip()]
    return lines[-1] if lines else ""


def _first_line(text: str) -> str:
    lines = [ln.strip() for ln in text.strip().splitlines() if ln.strip()]
    return lines[0] if lines else ""


def score(corpus: Corpus) -> list[dict[str, Any]]:
    main = corpus.main_assistant
    main_n = len(main)
    all_assistant = corpus.main_assistant_total + corpus.side_assistant_count
    metrics: list[dict[str, Any]] = []

    # Cross-check the reach metric two ways before trusting it. The isSidechain field is
    # authoritative, but a schema change would silently zero it, so compare against the
    # count derived from transcript location.
    by_path_total = corpus.side_by_path_count + corpus.main_by_path_count
    by_path_share = _rate(corpus.side_by_path_count, by_path_total)
    by_field_share = _rate(corpus.side_assistant_count, all_assistant)
    agrees = abs(by_path_share - by_field_share) < 1.0

    metrics.append(
        _metric(
            "subagent_reach_share",
            "Assistant messages generated inside a subagent (isSidechain=true) as a share of "
            "all assistant messages. This is the fraction of output that no output style can "
            "reach, because styles apply to the main thread only.",
            corpus.side_assistant_count,
            all_assistant,
            main_thread_messages=corpus.main_assistant_total,
            main_thread_messages_with_prose=main_n,
            subagent_messages=corpus.side_assistant_count,
            cross_check_by_path_percent=by_path_share,
            cross_check_agrees=agrees,
            confidence="exact" if agrees else "SUSPECT - classifiers disagree",
        )
    )

    closing = sum(
        1 for t in corpus.session_last_main.values() if CLOSING_ASK_RE.search(_last_line(t))
    )
    metrics.append(
        _metric(
            "session_closing_ask_rate",
            "Sessions whose final main-thread assistant message ends on a line that asks a "
            "question, states a pre-committed branch, or explicitly hands control back, as a "
            "share of all sessions with at least one main-thread assistant message.",
            closing,
            len(corpus.session_last_main),
        )
    )

    verdict = sum(1 for t in main if VERDICT_FIRST_RE.match(_first_line(t)))
    metrics.append(
        _metric(
            "verdict_first_rate",
            "Main-thread assistant messages whose first non-empty line opens with a bolded "
            "claim. Markdown headings do not count.",
            verdict,
            main_n,
        )
    )

    turn_closing = sum(1 for t in main if CLOSING_ASK_RE.search(_last_line(t)))
    metrics.append(
        _metric(
            "turn_closing_ask_rate",
            "Every main-thread assistant message, not just the last of a session, that ends on "
            "a closing ask. Separates 'we never close sessions' from 'we never close turns'.",
            turn_closing,
            main_n,
        )
    )

    mountain = sum(1 for t in main if len(t) >= MOUNTAIN_CHARS)
    metrics.append(
        _metric(
            "mountain_of_text_rate",
            f"Main-thread assistant messages of at least {MOUNTAIN_CHARS} characters of prose, "
            "excluding tool calls and thinking blocks.",
            mountain,
            main_n,
            threshold_chars=MOUNTAIN_CHARS,
        )
    )

    mermaid = sum(1 for t in main if MERMAID_RE.search(t))
    metrics.append(
        _metric(
            "mermaid_in_terminal_rate",
            "Main-thread assistant messages containing a mermaid fence. These render as raw "
            "source in the CLI. Does not count mermaid written into files, which is legitimate.",
            mermaid,
            main_n,
        )
    )

    bare_ids = sum(1 for t in main if BARE_ID_RE.search(t))
    metrics.append(
        _metric(
            "bare_identifier_rate",
            "Main-thread assistant messages where an issue number, PR number, or short commit "
            "SHA opens a sentence with no noun naming what it is. Heuristic: a trend line, not "
            "a verdict on any single message.",
            bare_ids,
            main_n,
            confidence="heuristic",
        )
    )

    human_n = len(corpus.human)
    fmt = sum(1 for t in corpus.human if FORMAT_LEXICON.search(t) and COMPLAINT_REGISTER.search(t))
    metrics.append(
        _metric(
            "format_complaint_proxy",
            "Genuine human messages that name a presentation element AND carry corrective "
            "register. A keyword proxy, NOT the hand-labelled rate. Compare proxy to proxy.",
            fmt,
            human_n,
            confidence="proxy",
        )
    )

    clarity = sum(
        1 for t in corpus.human if CLARITY_LEXICON.search(t) and COMPLAINT_REGISTER.search(t)
    )
    metrics.append(
        _metric(
            "clarity_complaint_proxy",
            "Genuine human messages signalling that something was not understood AND carrying "
            "corrective register. A keyword proxy, NOT the hand-labelled rate.",
            clarity,
            human_n,
            confidence="proxy",
        )
    )

    return metrics


def build_report(
    corpus: Corpus,
    metrics: list[dict[str, Any]],
    since: datetime,
    until: datetime,
    roots: list[str],
) -> dict[str, Any]:
    return {
        "schema": METRIC_SCHEMA,
        "window": {"since": since.isoformat(), "until": until.isoformat()},
        "roots": roots,
        "corpus": {
            "files_scanned": corpus.files_scanned,
            "sessions": len(corpus.session_last_main),
            "main_thread_assistant_messages": corpus.main_assistant_total,
            "main_thread_assistant_messages_with_prose": len(corpus.main_assistant),
            "subagent_assistant_messages": corpus.side_assistant_count,
            "genuine_human_messages": len(corpus.human),
            "lines_unparsed": corpus.lines_unparsed,
            "top_cwds": corpus.cwds.most_common(10),
        },
        "metrics": metrics,
    }


def to_markdown(report: dict[str, Any]) -> str:
    window = report["window"]
    corpus = report["corpus"]
    lines = [
        "| metric | count | of | percent | confidence |",
        "| --- | ---: | ---: | ---: | --- |",
    ]
    for m in report["metrics"]:
        lines.append(
            f"| {m['metric']} | {m['numerator']} | {m['denominator']} | "
            f"{m['percent']}% | {m.get('confidence', 'exact')} |"
        )
    return (
        f"Window {window['since'][:10]} to {window['until'][:10]} — "
        f"{corpus['files_scanned']} transcripts, {corpus['sessions']} sessions, "
        f"{corpus['main_thread_assistant_messages']} main-thread assistant messages, "
        f"{corpus['subagent_assistant_messages']} subagent, "
        f"{corpus['genuine_human_messages']} genuine human prompts.\n\n" + "\n".join(lines)
    )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument("--days", type=int, default=35, help="window size when --since is absent")
    parser.add_argument("--since", help="ISO date, inclusive")
    parser.add_argument("--until", help="ISO date, inclusive")
    parser.add_argument("--roots", nargs="*", default=DEFAULT_ROOTS)
    parser.add_argument(
        "--exclude",
        nargs="*",
        default=[],
        help="transcript paths to skip, e.g. the session doing the measuring",
    )
    parser.add_argument("--out", help="write the JSON report here")
    parser.add_argument("--markdown", action="store_true", help="print a markdown table to stdout")
    args = parser.parse_args(argv)

    until = (
        datetime.fromisoformat(args.until).replace(tzinfo=UTC) if args.until else datetime.now(UTC)
    )
    since = (
        datetime.fromisoformat(args.since).replace(tzinfo=UTC)
        if args.since
        else until - timedelta(days=args.days)
    )

    corpus = collect(args.roots, since, until, set(args.exclude))
    report = build_report(corpus, score(corpus), since, until, args.roots)

    if args.out:
        os.makedirs(os.path.dirname(os.path.abspath(args.out)), exist_ok=True)
        with open(args.out, "w") as fh:
            json.dump(report, fh, indent=2)
            fh.write("\n")

    print(to_markdown(report) if args.markdown else json.dumps(report, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
