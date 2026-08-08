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
  --exclude ~/.claude/projects/-Users-jefcox-bin/ab04a9a4-1357-4d06-a5f7-7e4e390246c2.jsonl \
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
| turn_closing_ask_rate | 818 / 14787 = 5.532% | 823 / 14787 = 5.566% | **no — see below** |
| mountain_of_text_rate | 172 / 14787 = 1.163% | 172 / 14787 = 1.163% | yes |
| mermaid_in_terminal_rate | 7 / 14787 = 0.047% | 7 / 14787 = 0.047% | yes |
| bare_identifier_rate | 250 / 14787 = 1.691% | 250 / 14787 = 1.691% | yes |
| format_complaint_proxy | 7 / 842 = 0.831% | 7 / 842 = 0.831% | yes |
| clarity_complaint_proxy | 10 / 842 = 1.188% | 10 / 842 = 1.188% | yes |

Eight of the nine rows are identical field for field, including their definition strings, and every
corpus count matches too: 407 sessions, 96,957 main-thread assistant messages, 14,787 of them
carrying prose, 128,622 subagent messages, 842 genuine human prompts, 0 unparseable lines.

### The ninth row moved on purpose, by 5 turns

`turn_closing_ask_rate` reads 823 here against the baseline's 818. The detector was widened on
2026-08-08 during the code review of this work, because it could not see the closing form the house
style actually prescribes. The style's closing block ends with a line reading `Your call: <branches>`
— a pre-committed decision, which is precisely what this detector's own definition says it counts —
and the old pattern matched none of the three prescribed forms while matching the phrasing the style
names as its counter-example. Left alone, the better the style was followed the worse this metric
would have read, and a successful rollout would have arrived as a regression.

What the widening costs, measured rather than assumed:

| added alternative | additional pre-style turns caught |
| --- | ---: |
| `Your call:` at the start of the closing line | **0** |
| "unless you say / tell me / object / stop me / redirect" | 3 |
| "your move" | 2 |

The style's own literal token appears in **zero** pre-style turns, which is the expected result — it
did not exist before this work. The 5 that moved are ordinary English that happened to appear in the
window. So:

- **The comparison figure for `turn_closing_ask_rate` is 5.566%, not 5.532%.** An "after" run uses
  the widened detector and must be read against the widened pre-style value. Reading it against
  5.532% would credit the style with 5 turns it did not cause.
- **`session_closing_ask_rate` is unmoved** at 11/407 = 2.703%, so its comparison figure is unchanged.
- **The baseline file is untouched** and still records 818 under the narrower detector, which is what
  that detector saw. It is not wrong; it answers a slightly narrower question.
- `METRIC_SCHEMA` stays at 1. The thing being measured — does the turn end by handing the reader a
  decision — is unchanged, and the shift is 0.034 of a percentage point, disclosed here rather than
  absorbed.

**Two numbers differ that are not metrics at all.** Transcripts scanned went from 2,655 to 2,689, and
`records_without_timestamp` appears for the first time at 97,365. The scanner uses file modification
time as a cheap pre-filter before re-checking every message against its own timestamp, so 34 more
files have been touched since the baseline run and now pass that pre-filter; none of them contributed
a message inside the window, which is what the identical corpus counts demonstrate. The timestamp
count is a new field rather than a new fact: records with no usable timestamp were always skipped,
and are now counted separately from `lines_unparsed` so that skipping them cannot be misread as a
corpus-integrity problem. None of them is an assistant message, so no metric population is affected.

### What was removed from both artifacts, and why it is not a regeneration

Both JSON files previously carried a `top_cwds` field listing the ten most-visited project
directories verbatim. This repository is public, and that field wrote the operator's home directory
and the names of nine unrelated private repositories into version control. It has been removed from
both committed artifacts and from the instrument, which now reports `distinct_project_dirs` — a
count — instead. The scanned roots are recorded with `~` in place of the home directory for the same
reason.

Removing that field is **not** a regeneration of the baseline and does not violate the write-once
rule, which exists to stop the pre-style measurement being replaced by a styled one. Nothing was
re-measured: the edit deleted one key. That was verified rather than asserted — the `metrics` array,
the `window`, the `schema`, and every other `corpus` field compare byte-identical before and after,
and `tests/test_output_style_scorer.py::test_the_committed_baseline_file_still_holds_the_pre_style_snapshot`
now pins all nine numerators, denominators, and percentages so that a real regeneration would fail
the suite. Before this it asserted only the file's shape, and a rewrite that replaced every
percentage while preserving the shape passed it — confirmed by mutation during the review.

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
- **One of the three forms the house style permits is invisible here.** The style's permitted catalog
  for terminal output is an indented file tree, a single-line arrow chain, and a Markdown table. The
  detector sees the arrow chain and the table; a two-space indented file tree matches nothing, so a
  turn whose only picture is a tree scores as an orientation turn that drew nothing. This was found
  during the #704 code review, and the arrow chain was changed from `->` to `-->` in the style at the
  same time so that at least two of the three forms are measurable. The tree remains a blind spot,
  and it biases the figure **downward** — the safe direction for a "before" value.
- An explicit operator request for a visual is supposed to override the gate in either direction.
  This measurement does not read the preceding human message, so it cannot honour that override.

### undigested_relay_rate — is a subagent's finding digested, or is its payload pasted?

**Operator decision, 2026-08-08: this is a regression guard, not an improvement target.** At 0 of 498
it has no headroom, and a success criterion that cannot move is not a criterion. It stays in the
scorer, where it does one job well — catching the behaviour if it gets worse — and it is deliberately
absent from the requirements document's Success Criteria table so that a later reader cannot mistake
0.00% for a target already met. The criterion that replaced it there is this metric's companion figure,
`relay_verdict_first_percent`: **11.85%** of relay turns open with the verdict, which has real headroom
and measures the complaint that motivated the work.

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
