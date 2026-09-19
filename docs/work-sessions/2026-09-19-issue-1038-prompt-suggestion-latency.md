# Work session — issue 1038, prompt-suggestion latency exploration

**Outcome: the exploration is complete and the recommendation is defer.** A resident local process
removes 46% of a cold hook's cost and still cannot beat one API round trip, so no blocking shape meets
the 400 millisecond target; the two shapes that meet it are not usable as built.

| Field | Value |
|---|---|
| Issue | infiquetra/infiquetra-claude-plugins#1038, child of #1019 |
| Branch | `issue/1038`, from `866d3670` |
| Plan | `docs/plans/2026-09-19-issue-1038-prompt-suggestion-latency-plan.md` |
| Doc review | `docs/reviews/2026-09-19-issue-1038-prompt-suggestion-latency-plan-doc-review.md` — passed, nothing open |
| Deliverable | `docs/analysis/2026-09-19-prompt-suggestion-latency.md` |
| Backend | `inline`, from the plan's `backend:` frontmatter; recommender said `team-execution` |
| Destination | `pr` |
| `change_kinds` | `docs`, `behavior` |

## What was built, by unit

**U1 — the synthetic prompt corpus and question set.** Twenty hand-written prompts, fifteen warranting
a saga command and five warranting none, each with the reason recorded.
`docs/analysis/2026-09-19-prompt-suggestion-latency-inputs/corpus.json` and `questions.json`.

**U2 — the harness core.** Shape registry, interleaved runner, subprocess-boundary timing,
nearest-rank percentiles, JSON results. `tools/prompt_suggestion_latency.py`.

**U3 — the cold shapes and the floor.** One request, two requests, and a process that does nothing.

**U4 — the resident process and the warm shapes.** Owner-only Unix domain socket, harness-owned start
and stop, four warm shapes. `tools/prompt_suggestion_daemon.py`.

**U5 — the survival and resolution probes.** Thirty separate hook processes against one resident
instance; the fleet-core resolution rung observed per installed tree.

**U6 — the live run and the deliverable.** Two measurement runs (see below) and the analysis document.

## Key decisions

Recorded in full in `docs/engineering-journal/DECISIONS.md` under
`{#measurement-bars-precede-the-numbers-1038}`: the pass/fail bars were fixed before measuring, shapes
with no blocking call were measured deliberately, the prototype uses an owner-only Unix socket, cached
answers are not billed against the live-call budget, and the data-governance question about sending a
live operator prompt is left to the operator.

## The two runs, and why there are two

The first run timed the warm shapes against the same half-second deadline the hook uses to fail open.
Every two-request trial returned at the deadline, so the recorded latency *was* the deadline, and the
empty answer that came back was scored as a deliberate silence — warm two-request accuracy read 0 of
15 where the identical cold shape read 13 of 15, which is what exposed it. The measurement deadline is
now separate and generous, a timed-out warm trial is recorded as a failure rather than a fast success,
and the warm shapes were re-measured. Cold figures are from the first run and are unaffected: a cold
hook never talks to the resident process.

## Headline measurements

| Shape | p50 ms | p95 ms | trials | right command | stays quiet |
|---|---:|---:|---:|---:|---:|
| floor (process only) | 46.9 | 49.8 | 50 | — | — |
| cold, 1 request | 741.6 | 781.0 | 20 | 14/15 | 5/5 |
| cold, 2 requests | 1044.3 | 1189.9 | 20 | 13/15 | 5/5 |
| warm, 2 requests | 694.5 | 793.4 | 20 | 13/15 | 5/5 |
| warm, 1 request | 398.9 | 428.4 | 20 | 14/15 | 5/5 |
| warm, cache hit | 49.2 | 53.3 | 50 | 14/15 | 5/5 |
| warm, no blocking call | 48.6 | 52.0 | 20 | 1/15 | 4/5 |

Survival: 30 of 30 separate hook processes reached one resident instance. Resolution: both installed
trees resolve fleet-core through `~/.claude/plugins/installed_plugins.json` to version 0.25.3, which
does not carry the TypeSafe client at all.

## Checks run

`ruff check`, `ruff format --check`, `mypy`, `pytest` on the new test file (50 tests), plus a mutation
pass: four guards were each broken deliberately and the covering test confirmed to fail. One of those
mutations found a real weakness — the owner-only directory test was passing via the socket guard
rather than the directory guard — which was repaired by making the two refusals distinguishable.

## Spend and cleanup

About 235 live vendor requests across the smoke run, both measurement runs and two diagnostics, under
the 300 allowed. Token totals are recorded in the deliverable. The resident process is started and
stopped by the harness in a `finally`; `pgrep` confirmed no `prompt_suggestion_daemon` process
remained and no socket directory was left behind.

## Next step

Code review on this branch against `866d3670`, then open the pull request to `main`.
