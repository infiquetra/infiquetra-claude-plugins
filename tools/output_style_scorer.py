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

Two later metrics are heuristic in a third way and say so in their own definitions.
`visual_gating_rate` can only see two of the four conditions that make a turn an orientation
turn, so it under-counts that population.  `undigested_relay_rate` infers which turn relayed a
subagent from the order of tool calls rather than observing it.  Both are trend lines.

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
from collections.abc import Iterator
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from typing import Any

# Bump when any DEFINITION below changes; baselines with a different schema are not comparable.
# Adding a NEW metric does not bump it.  An older report simply lacks the new row, and every
# row it does carry was computed by the same definition, so the two remain comparable for the
# metrics they share.  Bumping on an addition would falsely mark the 2026-08-07 baseline as
# incomparable and destroy the only "before" record there is.
METRIC_SCHEMA = 1

# Both Claude Code configurations this operator runs.  Derived from the running user's home
# directory rather than written literally, so the tool works for anyone who checks the
# repository out -- and so no operator's username is baked into tracked source.
DEFAULT_ROOTS = [
    os.path.expanduser("~/.claude/projects"),
    os.path.expanduser("~/.claude-company/projects"),
]

# A user message only counts as a real human turn when it came from the keyboard.  Everything
# else in the `user` slot is tool output, hook injection, or a system-authored continuation.
GENUINE_PROMPT_SOURCES = {"typed", "queued", "suggestion_accepted"}

# Main-thread assistant messages at or above this many characters count as a wall of text.
# 4000 is the empirical cutoff from the 2026-08-07 run (the 40 longest messages of 16,029).
MOUNTAIN_CHARS = 4000

# Tool names that spawn a subagent.  A main-thread turn that calls one of these is followed,
# sooner or later, by the turn that relays what came back.  `Task` is the older name and is
# kept so that transcripts from before the rename still classify.
SPAWN_TOOLS = {"Agent", "Task", "Workflow"}

# A fenced block at or above this many characters, whose first character opens a JSON object
# or array, is a pasted payload rather than a quotation.
PAYLOAD_MIN_CHARS = 800

# This many consecutive quoted lines is a payload pasted behind `>` rather than a quotation.
PAYLOAD_QUOTE_LINES = 8

# --------------------------------------------------------------------------------------
# Detectors
# --------------------------------------------------------------------------------------

# A closing ask: the final non-empty line either asks a question outright, states a
# pre-committed branch, or explicitly hands control back.  Anything else means the turn
# ended on a declarative fact and the reader is left to work out whether it is their move.
#
# The last three alternatives were added on 2026-08-08 (#704) because the house style
# prescribes the pre-committed-branch form this detector was always meant to catch and did
# not: `Your call:`, "unless you say otherwise I will ...", and "your move".  Without them a
# fully style-compliant turn scores as NOT closing with an ask, so the better the style was
# followed the worse this metric would read.
#
# What that costs, measured rather than assumed.  Re-scored over the frozen 2026-07-03 to
# 2026-08-07 window, the extension catches 5 additional turns: 3 from "unless you ..." and 2
# from "your move", both ordinary English that predates the style, and 0 from `Your call:`,
# which no pre-style turn contains.  So turn_closing_ask_rate's pre-style value is 823/14787
# = 5.566% under this definition, against the 818/14787 = 5.532% the 2026-08-07 baseline
# holds under the narrower one; session_closing_ask_rate is unmoved at 11/407.  An "after"
# run must be compared against 5.566%, and docs/measurements/2026-08-08-extended-metrics.md
# carries that corrected figure.  The baseline file itself is untouched and still records
# what the narrower detector saw.  METRIC_SCHEMA stays at 1: the thing being measured -- does
# the turn end by handing the reader a decision -- is unchanged, and the shift is 0.034 of a
# percentage point, disclosed rather than absorbed.
CLOSING_ASK_RE = re.compile(
    r"(\?\s*$)"
    r"|(\b(want|would you like|shall i|should i|do you want|ok to|okay to)\b)"
    r"|(\b(holding|standing by|waiting|blocked) (here |on )?(until|for|on)\b)"
    r"|(\bnothing (is )?needed from you\b)"
    r"|(\bsay (the word|go)\b)"
    r"|(\bif you (say|confirm|approve)\b)"
    r"|((?m:^)\s*your call\s*:)"
    r"|(\bunless you (say|tell me|object|stop me|redirect)\b)"
    r"|(\byour move\b)",
    re.IGNORECASE,
)

# A verdict-first opening: the first non-empty line leads with a bolded claim.  Markdown
# headings do not count -- a heading names a section, it does not state a finding.
VERDICT_FIRST_RE = re.compile(r"^\s*\*\*[^*]{4,}?\*\*")

MERMAID_RE = re.compile(r"```\s*mermaid\b", re.IGNORECASE)

# A visual, for the purpose of gating: a markdown table, a mermaid fence, box-drawing
# characters, or arrow notation of the kind a hand-drawn flow uses.  Prose bullets are not
# visuals and deliberately do not match.  Heuristic by construction, and it errs generously:
# `-->` also occurs inside HTML comments and inside quoted code, so a turn can be credited
# with a visual it did not really draw.  It is a trend line, not a verdict on any one message.
VISUAL_RE = re.compile(
    r"^[ \t]*\|[ \t:|-]*-{3,}[ \t:|-]*\|[ \t]*$"  # markdown table separator row
    r"|```[ \t]*mermaid\b"  # mermaid fence
    r"|[\u2500-\u257f]"  # box-drawing characters (U+2500 to U+257F)
    r"|-->|→|⇒",  # arrow notation
    re.IGNORECASE | re.MULTILINE,
)

# A fenced block whose body opens a JSON object or array.  Restricting to JSON is what keeps
# the legitimate verbatim cases out: a diff hunk, an exact error string and raw command output
# are all correct to reproduce character for character, and none of them starts with { or [.
# Whitespace is tolerated around the language tag, matching what MERMAID_RE and VISUAL_RE
# already do for their own fences: ``` json and ```json are the same fence to a reader, and a
# detector that sees only one of them under-reports by exactly the messages that used a space.
# Widening cannot lose a match (every added element is optional) and gains none on the frozen
# window -- measured 0 additional messages over 2026-07-03..2026-08-07, so no metric moves.
PAYLOAD_FENCE_RE = re.compile(r"```[ \t]*[A-Za-z0-9_+-]*[ \t]*\r?\n(.*?)```", re.DOTALL)
JSON_OPENS_RE = re.compile(r"^\s*[\[{]")
# `"key":` -- used to recognise a dump that was cut off partway and so will not parse.  Five
# is deliberately low: the fallback only ever runs on text that already opens a brace or a
# bracket and already runs past PAYLOAD_MIN_CHARS, and prose meeting both of those still
# almost never carries five quoted key names.  The real 12,347-character offender carries 12.
JSON_KEY_RE = re.compile(r'"[^"\n]{1,60}"\s*:')
JSON_KEYS_FOR_A_DUMP = 5

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
    # Two flag lists kept in lockstep with main_assistant, one entry per prose message.
    # They record the two turn triggers a transcript can actually show: whether this was the
    # session's first prose turn, and whether it was the first prose turn after a subagent
    # was spawned. Both are filled by _order_sessions() after the whole walk, never during
    # it, because a session's records can be spread across files that the glob returns in
    # any order and a flag assigned in scan order would be wrong.
    main_is_session_first: list[bool] = field(default_factory=list)
    main_is_relay: list[bool] = field(default_factory=list)
    # session id -> the turn events that decide those flags, as
    # (timestamp, read order, "prose" | "spawn", index into main_assistant).
    # Sorting by the first two fields puts a session back into real time order; "prose"
    # sorting before "spawn" makes a turn that both relays one subagent and spawns the next
    # count as the relay it is.
    session_events: dict[str, list[tuple[str, int, str, int]]] = field(default_factory=dict)
    records_read: int = 0
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
    # Distinct project directories the corpus spans. Held as a set and reported only as a
    # COUNT: these are absolute paths on the operator's machine and naming them in a
    # committed artifact discloses their home directory and their private repository names.
    project_dirs: set[str] = field(default_factory=set)
    # Assistant records whose `isSidechain` was neither True nor False. Such a record is
    # counted by neither classifier, so a schema change that stopped setting the field would
    # drop every message from both sides of the reach ratio at once and the two classifiers
    # would still agree -- agreeing on zero. This counter is what makes that visible.
    unknown_sidechain: int = 0
    # Records carrying no usable `timestamp`. They parsed fine; they simply cannot be placed
    # inside or outside the window, so they are skipped. Kept separate from lines_unparsed,
    # which means a line that failed to parse as JSON at all.
    records_without_timestamp: int = 0

    @property
    def distinct_project_dirs(self) -> int:
        return len(self.project_dirs)


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


def _spawns_subagent(message: dict[str, Any]) -> bool:
    """True when this assistant turn called a tool that starts a subagent."""
    content = message.get("content")
    if not isinstance(content, list):
        return False
    return any(
        isinstance(block, dict)
        and block.get("type") == "tool_use"
        and block.get("name") in SPAWN_TOOLS
        for block in content
    )


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

    _order_sessions(corpus)
    return corpus


def _order_sessions(corpus: Corpus) -> None:
    """Put every session back into time order and set the two turn flags from it.

    This runs once, after the walk. Doing it during the walk would tie the answer to the
    order the filesystem happened to hand back a session's transcripts, which is the kind of
    fault that shows up as a metric reading zero rather than as an error.
    """
    count = len(corpus.main_assistant)
    corpus.main_is_session_first = [False] * count
    corpus.main_is_relay = [False] * count
    for events in corpus.session_events.values():
        awaiting_relay = False
        seen_prose = False
        for _stamp, _seq, kind, index in sorted(events):
            if kind == "prose":
                corpus.main_is_relay[index] = awaiting_relay
                corpus.main_is_session_first[index] = not seen_prose
                awaiting_relay = False
                seen_prose = True
            else:
                awaiting_relay = True


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
        when = None
        if isinstance(stamp, str):
            try:
                when = datetime.fromisoformat(stamp.replace("Z", "+00:00"))
            except ValueError:
                when = None
            # A timestamp carrying no offset parses fine and then raises TypeError on
            # comparison against the timezone-aware bounds, aborting the whole walk. Treat a
            # naive stamp as UTC, which is what every Claude Code transcript writes anyway.
            if when is not None and when.tzinfo is None:
                when = when.replace(tzinfo=UTC)
        # One test for "no usable timestamp", covering BOTH an absent/non-string stamp and a
        # string that is not a parseable datetime.  Testing only the absent case let a record
        # stamped "not-a-date" fall through every branch into the corpus -- unfiltered by
        # --since/--until and uncounted here, so nothing reported that it had happened.
        #
        # Keeping such a record would let it into the corpus regardless of the window, and its
        # empty sort key would additionally make it the session's apparent first turn, stealing
        # the orientation flag from the message that really opened the session.  Counted in its
        # own field, NOT in lines_unparsed -- these lines parsed perfectly well, and folding
        # them into an "unparsed" count would report a corpus-integrity problem where there is
        # none.  Over the baseline window this is ~97k records, none of them assistant
        # messages, and unparseable stamps measured 0 of them, so no metric population moves.
        if when is None:
            corpus.records_without_timestamp += 1
            continue
        if not (since <= when <= until):
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
                corpus.unknown_sidechain += 1
                continue
            corpus.main_assistant_total += 1
            corpus.records_read += 1
            seq = corpus.records_read
            # `record.get("message", {})` returns a stored None rather than the default, and
            # _text_of would then raise AttributeError on it, aborting the walk.
            message = record.get("message") or {}
            text = _text_of(message)
            session = record.get("sessionId") or path
            events = corpus.session_events.setdefault(session, [])
            if text.strip():
                corpus.main_assistant.append(text)
                events.append((stamp or "", seq, "prose", len(corpus.main_assistant) - 1))
                if cwd := record.get("cwd"):
                    corpus.project_dirs.add(cwd)
                prev = corpus.session_last_ts.get(session)
                if prev is None or (isinstance(stamp, str) and stamp >= prev):
                    corpus.session_last_main[session] = text
                    corpus.session_last_ts[session] = stamp or ""
            # A tool-call-only turn has no prose and cannot be scored on shape, but it can
            # still be the turn that spawned the subagent, so this runs either way.
            if _spawns_subagent(message):
                events.append((stamp or "", seq, "spawn", -1))

        elif kind == "user":
            if sidechain is not False or "toolUseResult" in record:
                continue
            if record.get("promptSource") not in GENUINE_PROMPT_SOURCES:
                continue
            text = _text_of(record.get("message") or {})
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


def _is_json_dump(body: str) -> bool:
    """A machine-serialised structure, as opposed to prose that happens to start with a brace.

    Parsing is the first test.  The fallback matters because the real offenders are often
    truncated mid-structure and will never parse: the 12,347-character worst case in the
    2026-08-07 corpus opens `{"findings":[{"content":"[P1] ...` and runs out of room.
    """
    if not JSON_OPENS_RE.match(body):
        return False
    try:
        json.loads(body)
    except (ValueError, RecursionError):
        return len(JSON_KEY_RE.findall(body)) >= JSON_KEYS_FOR_A_DUMP
    return True


def _has_pasted_payload(text: str) -> tuple[bool, int]:
    """Does this message carry a raw payload as its body, and how long is the longest one?

    Three shapes count, and the third is the one that matters most.  A *fenced* block that is
    a JSON dump of at least PAYLOAD_MIN_CHARS is a subagent return pasted whole.  A run of
    PAYLOAD_QUOTE_LINES or more consecutive `>` lines is the same thing behind block-quote
    markers.  And an *unfenced* message that is itself nothing but a JSON dump is the shape
    the worst case in the 2026-08-07 corpus actually took -- 12,347 characters of literal
    unformatted JSON with no fence around it at all.  A fence-only detector reads zero on
    that message, which is why this function checks the bare body too.

    Deliberately NOT counted: diff hunks, exact error strings and raw command output.  Those
    are correct to reproduce character for character, and none of them is a JSON dump.
    """
    longest = 0
    body = text.strip()
    if len(body) >= PAYLOAD_MIN_CHARS and _is_json_dump(body):
        longest = len(body)
    for fenced in PAYLOAD_FENCE_RE.findall(text):
        if len(fenced) >= PAYLOAD_MIN_CHARS and _is_json_dump(fenced):
            longest = max(longest, len(fenced))
    run = 0
    quoted_chars = 0
    for line in text.splitlines():
        if line.lstrip().startswith(">"):
            run += 1
            quoted_chars += len(line)
            if run >= PAYLOAD_QUOTE_LINES:
                longest = max(longest, quoted_chars)
        else:
            run = 0
            quoted_chars = 0
    return longest > 0, longest


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
    # Comparing the two shares alone is not enough. If the schema stopped setting
    # `isSidechain`, EVERY record would fall out of the field-based classifier at once, both
    # shares would read 0.0, and they would "agree" -- on nothing. The two extra conditions
    # are what make the check load-bearing: the field classifier must have seen messages at
    # all, and no record may have carried an unrecognised value for the field.
    agrees = (
        abs(by_path_share - by_field_share) < 1.0
        and all_assistant > 0
        and corpus.unknown_sidechain == 0
    )
    if corpus.unknown_sidechain:
        confidence = f"SUSPECT - {corpus.unknown_sidechain} records with unreadable isSidechain"
    elif not all_assistant:
        confidence = "SUSPECT - the isSidechain classifier counted no messages at all"
    elif not agrees:
        confidence = "SUSPECT - classifiers disagree"
    else:
        confidence = "exact"

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
            confidence=confidence,
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

    metrics.append(_visual_gating_metric(corpus))
    metrics.append(_relay_quality_metric(corpus))

    return metrics


def _orientation_flags(corpus: Corpus) -> list[bool]:
    """One flag per prose message: is this an orientation turn or a routine one?

    Only two of the style's four orientation triggers leave a mark a transcript can be read
    for -- the first prose turn of a session, and the turn that follows a subagent spawn.  A
    topic change and a return from a long tool run do not, so they are not detected and the
    orientation population is UNDER-counted.  Turns that were really orientation but are not
    detected land in the routine population, where an appropriate visual is scored as a
    misfire.  The metric therefore reads pessimistically, which is the safe direction.
    """
    n = len(corpus.main_assistant)
    first = corpus.main_is_session_first
    relay = corpus.main_is_relay
    return [(i < len(first) and first[i]) or (i < len(relay) and relay[i]) for i in range(n)]


def _visual_gating_metric(corpus: Corpus) -> dict[str, Any]:
    """R32: do visuals appear on orientation turns and stay absent from routine ones?"""
    main = corpus.main_assistant
    orientation = _orientation_flags(corpus)
    has_visual = [bool(VISUAL_RE.search(t)) for t in main]

    orientation_n = sum(orientation)
    routine_n = len(main) - orientation_n
    orientation_with_visual = sum(1 for i in range(len(main)) if orientation[i] and has_visual[i])
    routine_with_visual = sum(1 for i in range(len(main)) if not orientation[i] and has_visual[i])
    correctly_gated = orientation_with_visual + (routine_n - routine_with_visual)

    # The headline is dominated by the routine population, which is roughly fifteen times
    # the orientation population, so most of it is the easy half: a routine turn that drew
    # nothing. This average weights the two halves equally instead, and is the figure to
    # compare across runs -- the headline can sit still while both halves move.
    orientation_right = _rate(orientation_with_visual, orientation_n)
    # `100.0 - _rate(...)` would score an EMPTY routine population as a free 100%, because
    # _rate returns 0.0 on a zero denominator.  Paired with an empty orientation population
    # scoring 0%, an empty corpus would report a plausible-looking balanced 50% -- a number
    # indistinguishable from a real half-right result.  A half with no population has no
    # score, so the average is not computed at all.
    routine_right = 100.0 - _rate(routine_with_visual, routine_n) if routine_n else None
    balanced = (
        round((orientation_right + routine_right) / 2, 3)
        if orientation_n and routine_right is not None
        else None
    )

    return _metric(
        "visual_gating_rate",
        "Main-thread prose messages whose visual matches the turn they are on: an orientation "
        "turn carrying at least one visual, or a routine turn carrying none. Orientation means "
        "the first prose turn of a session or the first prose turn after a subagent was "
        "spawned; every other turn is treated as routine. A visual means a markdown table, a "
        "mermaid fence, box-drawing characters, or arrow notation. HEURISTIC on both axes: two "
        "of the four orientation triggers (a topic change, a return from a long tool run) leave "
        "no transcript signal and are not detected, so orientation is under-counted; and the "
        "visual detector also fires on arrow notation inside quoted code. A trend line, not a "
        "verdict on any single message. The headline percent is diluted by the routine "
        "population being far the larger of the two -- compare balanced_gating_percent across "
        "runs, and read the two component rates below rather than the headline alone.",
        correctly_gated,
        len(main),
        confidence="heuristic",
        balanced_gating_percent=balanced,
        orientation_turns=orientation_n,
        orientation_with_visual=orientation_with_visual,
        orientation_with_visual_percent=_rate(orientation_with_visual, orientation_n),
        routine_turns=routine_n,
        routine_with_visual=routine_with_visual,
        routine_with_visual_percent=_rate(routine_with_visual, routine_n),
        undetected_triggers=["topic change", "return from a long tool run"],
    )


def _relay_quality_metric(corpus: Corpus) -> dict[str, Any]:
    """R33: on a relay turn, is the finding digested or is the payload pasted?"""
    main = corpus.main_assistant
    relay_flags = corpus.main_is_relay
    relays = [main[i] for i in range(len(main)) if i < len(relay_flags) and relay_flags[i]]

    undigested = 0
    longest_payload = 0
    verdict_first = 0
    for text in relays:
        pasted, longest = _has_pasted_payload(text)
        if pasted:
            undigested += 1
        longest_payload = max(longest_payload, longest)
        if VERDICT_FIRST_RE.match(_first_line(text)):
            verdict_first += 1

    # The same payload detector run over every main-thread prose turn, not just the ones
    # classified as relays. A zero headline must be readable against this: it can mean
    # "relays are digested", but it can also mean "the payloads are landing on turns this
    # metric does not classify as relays", and only these two numbers together say which.
    payload_anywhere = 0
    longest_anywhere = 0
    for text in main:
        pasted, longest = _has_pasted_payload(text)
        if pasted:
            payload_anywhere += 1
        longest_anywhere = max(longest_anywhere, longest)

    return _metric(
        "undigested_relay_rate",
        "Relay turns -- the first main-thread prose turn after a subagent was spawned -- that "
        "carry a raw payload as their body rather than a digested finding. A raw payload means "
        "a fenced block of at least "
        f"{PAYLOAD_MIN_CHARS} characters opening a JSON object or array, or a run of at least "
        f"{PAYLOAD_QUOTE_LINES} consecutive quoted lines. Diff hunks, exact error strings and "
        "raw command output are deliberately excluded, because reproducing those verbatim is "
        "correct. HEURISTIC: the relay turn is inferred from tool-call ordering rather than "
        "observed, and a relay that paraphrases a payload badly still scores as digested. "
        "Lower is better. REGRESSION GUARD, NOT A TARGET: this reads 0 of 498 (0.00%) on the "
        "pre-style window, so it has no headroom and cannot serve as a success criterion -- do "
        "not read 0.00% as a target already met. Its job is to catch the behaviour getting "
        "worse. The companion figure relay_verdict_first_percent is the one with headroom and "
        "is the criterion the requirements document carries.",
        undigested,
        len(relays),
        confidence="heuristic",
        relay_turns=len(relays),
        relay_verdict_first=verdict_first,
        relay_verdict_first_percent=_rate(verdict_first, len(relays)),
        longest_relay_payload_chars=longest_payload,
        payload_turns_anywhere=payload_anywhere,
        payload_turns_anywhere_percent=_rate(payload_anywhere, len(main)),
        longest_payload_chars_anywhere=longest_anywhere,
        main_prose_turns=len(main),
        spawn_tools=sorted(SPAWN_TOOLS),
    )


def _tilde(path: str) -> str:
    """Collapse a leading home directory to `~` so committed reports carry no username."""
    home = os.path.expanduser("~")
    return "~" + path[len(home) :] if path.startswith(home) else path


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
        # Written with `~` standing in for the home directory. These reports are committed to a
        # public repository, and an absolute root discloses the operator's username for no
        # analytic gain -- `~/.claude/projects` identifies the corpus just as precisely.
        "roots": [_tilde(r) for r in roots],
        "corpus": {
            "files_scanned": corpus.files_scanned,
            "sessions": len(corpus.session_last_main),
            "main_thread_assistant_messages": corpus.main_assistant_total,
            "main_thread_assistant_messages_with_prose": len(corpus.main_assistant),
            "subagent_assistant_messages": corpus.side_assistant_count,
            "genuine_human_messages": len(corpus.human),
            "lines_unparsed": corpus.lines_unparsed,
            "records_without_timestamp": corpus.records_without_timestamp,
            # How many distinct project directories the corpus spans, as a COUNT and never as
            # a list.  An earlier version emitted the ten most common `cwd` values verbatim,
            # which wrote the operator's home directory and the names of nine private
            # repositories into a committed artifact in a public repository (#704 review).
            # The count carries the diagnostic value -- is this corpus one project or thirty --
            # without disclosing anything about which.
            "distinct_project_dirs": corpus.distinct_project_dirs,
            # Assistant records whose `isSidechain` was neither True nor False.  This must
            # read 0.  Anything else means the transcript schema changed and both sides of
            # the reach ratio silently lost messages -- see subagent_reach_share, whose
            # cross-check consumes this.
            "records_with_unknown_sidechain": corpus.unknown_sidechain,
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
    parser.add_argument("--since", help="ISO date; the window opens at 00:00 UTC on this date")
    parser.add_argument(
        "--until",
        help=(
            "ISO date; the window CLOSES at 00:00 UTC on this date, so that day's own traffic "
            "is outside it. Pass a bare date and the window ends the instant the date begins."
        ),
    )
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
