---
date: 2026-08-08
purpose: Pre-style values for the two metrics added after the baseline was captured
instrument: tools/output_style_scorer.py
schema: 1
window: 2026-07-03 to 2026-08-07
status: measured over the archived window, before any custom output style has shipped
supplements: docs/measurements/2026-08-07-baseline.json
---

# Extended metrics, 2026-08-08 — visual gating and relay quality

## Why this file exists and why it is not the baseline

The output-presentation baseline at `docs/measurements/2026-08-07-baseline.json` carries nine
metrics. Two more were asked for afterwards — one for visual gating and one for relay quality —
and a metric added after a baseline has no "before" value unless something goes and gets one.

The tempting route is to re-run the scorer over its own baseline path so the file carries all
eleven numbers. That route destroys the thing it is trying to complete. The baseline records how
Claude Code behaved **before any custom output style existed**, and that window shut permanently
the moment the first style shipped. Re-running the instrument onto that path would replace the
only surviving record of the unstyled world with a styled measurement still wearing the word
"baseline".

The route taken instead costs nothing, because transcripts are immutable once written and the
ones inside the measured window are all still on disk. The extended scorer was pointed at **the
same window, the same two transcript roots, and the same exclusion**, and written to **a new
output path**. Every number below is therefore a genuine pre-style value, and the baseline file
is untouched — verified with `git diff --exit-code` on that path, which exited 0, and by
comparing its SHA-256 against the committed copy.

## How to reproduce it

```
python3 tools/output_style_scorer.py \
  --since 2026-07-03 --until 2026-08-07 \
  --exclude /Users/jefcox/.claude/projects/-Users-jefcox-bin/ab04a9a4-1357-4d06-a5f7-7e4e390246c2.jsonl \
  --out docs/measurements/2026-08-08-extended-metrics.json --markdown
```

That is the baseline's own reproduce command with one character changed: the `--out` path. The
`--exclude` is the transcript of the ideation session, kept identical so the nine original
metrics are computed over exactly the corpus the baseline saw.

Tests: `python3 -m pytest tests/test_output_style_scorer.py -q` (43 tests; 29 of them predate
this work and still pass unchanged).

## The nine original metrics reproduced exactly

This is the check that makes the two new numbers trustworthy. If adding metrics had disturbed the
corpus walk, the nine existing numbers would have moved, and there would be no way to tell whether
the new numbers were measuring behaviour or measuring a bug.

| metric | baseline | this run | same? |
| --- | ---: | ---: | --- |
| subagent_reach_share | 128622 / 225579 = 57.019% | 128622 / 225579 = 57.019% | yes |
| session_closing_ask_rate | 11 / 407 = 2.703% | 11 / 407 = 2.703% | yes |
| verdict_first_rate | 440 / 14787 = 2.976% | 440 / 14787 = 2.976% | yes |
| turn_closing_ask_rate | 818 / 14787 = 5.532% | 818 / 14787 = 5.532% | yes |
| mountain_of_text_rate | 172 / 14787 = 1.163% | 172 / 14787 = 1.163% | yes |
| mermaid_in_terminal_rate | 7 / 14787 = 0.047% | 7 / 14787 = 0.047% | yes |
| bare_identifier_rate | 250 / 14787 = 1.691% | 250 / 14787 = 1.691% | yes |
| format_complaint_proxy | 7 / 842 = 0.831% | 7 / 842 = 0.831% | yes |
| clarity_complaint_proxy | 10 / 842 = 1.188% | 10 / 842 = 1.188% | yes |

All nine rows are identical field for field, including their definition strings, and every corpus
count matches too: 407 sessions, 96,957 main-thread assistant messages, 14,787 of them carrying
prose, 128,622 subagent messages, 842 genuine human prompts, 0 unparseable lines.

**One number does differ and it is not a metric.** Transcripts scanned went from 2,655 to 2,669.
The scanner uses file modification time as a cheap pre-filter before re-checking every message
against its own timestamp, so fourteen more files have been touched since the baseline run and now
pass that pre-filter. None of them contributed a message inside the window — which is exactly what
the identical corpus counts and identical nine metrics demonstrate.

## The two new metrics

| metric | count | of | percent | confidence |
| --- | ---: | ---: | ---: | --- |
| visual_gating_rate | 12,958 | 14,787 | **87.63%** | heuristic |
| undigested_relay_rate | 0 | 498 | **0.00%** | heuristic |

Both are labelled `heuristic` in the emitted data, in the same way `bare_identifier_rate` already
is, and both say inside their own definition string where the heuristic bites.

### visual_gating_rate — do visuals appear where they are needed and stay away otherwise?

The rule being measured has two halves: an orientation turn should carry a visual, and a routine
turn should not. The headline counts turns that got their half right.

| | turns | carrying a visual | |
| --- | ---: | ---: | --- |
| Orientation turns | 904 | 250 | **27.66%** — should be high |
| Routine turns | 13,883 | 1,175 | **8.46%** — should be low |

**Read the two component rates, not the headline.** Routine turns outnumber orientation turns
roughly fifteen to one, so 87.63% is mostly the easy half being right: a routine turn that drew
nothing. The headline can sit almost still while both halves move a long way. The instrument
therefore also emits `balanced_gating_percent`, which weights the two halves equally and reads
**59.60%** before the style ships. That is the figure to compare across runs.

The plain finding: when the operator most needs a picture, one appears about a quarter of the
time; when they did not ask for one, one appears about one turn in twelve.

**Where this is heuristic, stated plainly.**

- The style names four conditions that make a turn an orientation turn. Only two of them leave a
  mark a transcript can be read for: the first prose turn of a session, and the first prose turn
  after a subagent was spawned. A topic change and a return from a long tool run leave nothing to
  detect. So the orientation population of 904 is **under-counted**, and real orientation turns
  that went undetected sit in the routine population, where an appropriate visual is scored as a
  misfire. The metric reads pessimistically, which is the safe direction for a "before" value.
- "A visual" means a markdown table, a mermaid fence, box-drawing characters, or arrow notation
  (`-->`, `→`, `⇒`). Arrow notation also occurs inside quoted code and HTML comments, so a turn
  can be credited with a visual it did not really draw. That pushes the other way.
- An explicit operator request for a visual is supposed to override the gate in either direction.
  This measurement does not read the preceding human message, so it cannot honour that override.

### undigested_relay_rate — is a subagent's finding digested, or is its payload pasted?

A relay turn is the first main-thread prose turn after a turn that called `Agent`, `Task`, or
`Workflow`. There were **498** of them in the window. **None** carried a raw payload as its body.

A zero has to be defended rather than reported, because a detector that finds nothing looks like
good news and is usually a fault. Three things establish that this one is real.

1. The detector was checked against the known worst case. The requirements document names a
   12,347-character message of literal unformatted JSON as the worst relay in the corpus. The
   first version of the detector missed it, because that message has **no code fence around it at
   all** — the whole message is the JSON. The detector was extended to catch an unfenced dump, and
   it now fires on that exact message and reports its length as 12,347.
2. That message is nevertheless **not** a relay turn. Its session contains two assistant records
   and never calls a subagent-spawning tool; it is a saga external-action session emitting its own
   structured result. So it is genuinely outside this metric's population, rather than being missed
   by it.
3. Across all 14,787 main-thread prose turns, only **5** carry a pasted payload at all, and the
   instrument reports that count as `payload_turns_anywhere` precisely so a zero headline can be
   read against it. Pasting a raw payload is rare behaviour; it is severe when it happens.

**The relay-quality signal with room to move is the other one in the row.** Requirement R25 of the
requirements document says a relay turn opens with the main thread's own verdict rather than the
subagent's framing. Only **59 of 498 relay turns — 11.85% — open with a verdict**. That is the
number to watch after the style ships. The headline is already at its floor and cannot improve.

**Where this is heuristic, stated plainly.**

- Which turn relayed a subagent is inferred from the order of tool calls, not observed. Sessions
  are re-sorted into real time order before the inference, so the answer does not depend on the
  order the filesystem returned a session's transcript files, but a turn that discusses a subagent
  return several turns later is still not counted.
- A "pasted payload" means a JSON dump of at least 800 characters, fenced or bare, or a run of at
  least eight consecutive quoted lines. Diff hunks, exact error strings and raw command output are
  deliberately excluded: reproducing those character for character is correct, and requirement R24
  says so.
- A relay that paraphrases a payload badly still scores as digested. This metric measures pasting,
  not comprehension.

## What the schema number does and does not mean

`METRIC_SCHEMA` stays at **1**. Its rule is that it bumps when a *definition changes*, and none
did — the two new metrics were appended and the nine existing definition strings are byte-identical.
Bumping it for an addition would have marked the 2026-08-07 baseline as incomparable and thrown
away the only "before" record that exists. An older report simply lacks the two new rows, and every
row it does carry was computed the same way.

## The one thing that must not happen

`docs/measurements/2026-08-07-baseline.json` is write-once. Two guards now exist:

- `tests/test_output_style_scorer.py::test_the_committed_baseline_file_still_holds_the_pre_style_snapshot`
  reads the committed file and asserts it still holds nine metrics, schema 1, the 2026-07-03 to
  2026-08-07 window, and 407 sessions. A run that overwrote it would fail this test.
- `tests/test_output_style_scorer.py::test_the_nine_baseline_metrics_are_unchanged_on_the_same_input`
  asserts the nine come back first, in order, with frozen counts on a fixed synthetic corpus, so
  none can be renamed, reordered, or redefined by a later edit.
