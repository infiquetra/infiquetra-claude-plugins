---
title: Plugin-Fleet Baseline Metrics — Freeze the Before Picture
type: docs
status: active
date: 2026-07-04
origin: infiquetra/infiquetra-claude-plugins#461 (requirements-ready handoff issue; no /brainstorm doc — the issue's own Source context cites docs/plans/2026-07-03-plugin-fleet-grounding-brief.md and docs/plans/plugin-fleet-ideation-2026-07-03/survivors/T10.json)
---

# Plugin-Fleet Baseline Metrics — Freeze the Before Picture

Phase 0 item 1 of 10 in the `improve-claude-plugins` execution program
(`docs/plans/2026-07-04-plugin-fleet-execution-order.md`). Issue #461,
slug `pf-fleet-baseline-metrics`. This item ships before any other Phase 0 change lands —
it is the pre-state every later wave-1/wave-2 fix will be diffed against.

## Problem frame (carried forward from issue #461)

Eight recurring, independently-corroborated fleet pain patterns currently exist only as
prose claims scattered across `docs/plans/2026-07-03-plugin-fleet-grounding-brief.md` and
the ideation session-mining output. None has a committed number with a re-derivation
recipe, so a future "did wave-1/wave-2 help" retro has nothing authoritative to diff
against. This plan commits one Markdown baseline document that fixes that gap. It is
documentation-only: no code, no plugin behavior change, no new tooling.

## Key Technical Decision

**KTD1 — Re-verify every citation's line number against the grounding brief as it exists
today; do not copy issue #461's cited line numbers verbatim.** Issue #461 cites, e.g.,
`grounding-brief.md:112` for the ship-ceremony metric and `:119` for the rate-limit metric.
Reading the file directly today shows ship-ceremony at line 119 and rate-limit fan-out
kills at line 129 — the brief has been edited since the issue was drafted and every
citation has drifted by 3–10 lines. AC2 requires each metric cite a concrete,
grep-verifiable `file:line`; shipping the issue's stale numbers would fail that
acceptance criterion on the first re-derivation and directly reproduce the "stale claim
asserted as fact" failure mode the same grounding brief calls out (§6 item 2). All eight
citations below were re-read from the file in this planning session — see the per-metric
table.

No other KTDs — this is a transcription task with no architectural ambiguity, matching the
issue's own executor-profile justification (Sonnet/low/inline).

## Scope boundaries

**In scope:** one new file, `docs/plans/2026-07-04-plugin-fleet-baseline-metrics.md`, with
8 metrics (definition, verified evidence citation, executable grep/gh recipe), ending in a
`/retro` re-run checklist line.

**Out of scope (carried from issue #461, unchanged):** fixing any of the 8 underlying pain
points; building telemetry/dashboard tooling; editing `/retro`'s `SKILL.md`; any
`plugin.json`/`marketplace.json`/`CHANGELOG.md` change (none applies — no plugin behavior
changes). `QUEUED.md` has no `G-negative-space-10` entry to mark addressed (verified via
`grep -n "negative-space-10" docs/engineering-journal/QUEUED.md` — zero matches), so that
optional DoD line is a no-op.

## Requirements (from issue #461 AC1–AC10)

- R1. Baseline doc has ≥8 metric subsections (`### `-level headings).
- R2. Every metric cites a concrete `file:line` evidence source.
- R3. Every metric carries a fenced, executable re-measurement recipe.
- R4. Metric set includes: ship-ceremony rate, 429/rate-limit fan-out kill rate, recon
  token cost, promote-ledger firings (zero), silent-no-op/dead-wiring incident count, plus
  three more drawn from the same intent list (gate-primitive unreliability, board/field
  drift, dark codex-mining substrate) to clear the ≥8 floor.
- R5. Two of the eight recipes are independently re-run and their output matches the
  grounding brief's reported numbers.
- R6. Document ends with a `/retro` re-run checklist line.

## Implementation Units

### U1. Draft the baseline metrics document

Write `docs/plans/2026-07-04-plugin-fleet-baseline-metrics.md` with one `### `-headed
subsection per metric. Each subsection: one-line definition, a `**Evidence:**` line citing
the verified `file:line`, and a fenced shell/grep recipe that re-derives or re-confirms the
number.

Verified citation table (re-read directly from
`docs/plans/2026-07-03-plugin-fleet-grounding-brief.md` during planning — supersedes any
line numbers quoted in issue #461):

| # | Metric | Verified citation | Number to freeze |
|---|---|---|---|
| 1 | Manual ship ceremony | `:119` | 8 repos |
| 2 | Gate-primitive unreliability (`AskUserQuestion` auto-proceed) | `:122` | 6 repos |
| 3 | mission-control board/field drift | `:126` | 4 repos |
| 4 | Rate-limit fan-out kills ("429 kill rate") | `:129` | 3 repos |
| 5 | Codex sessions with zero mining substrate | `:115` | 219 sessions |
| 6 | Promote-ledger firings | `:72` | 0 firings |
| 7 | Read-only recon fan-out token cost | `:145` | 350–450k tokens / <20 min |
| 8 | Silent no-ops / dead-wiring incidents | `:101` | 5+ learnings |

Recipe pattern per metric (matches issue #461's own verification example — grep the
committed brief, not a full session-mining re-run, since AC9 asks the re-derived value to
match what the brief already reports):

```bash
grep -n "<distinguishing phrase>" docs/plans/2026-07-03-plugin-fleet-grounding-brief.md
```

Metric 3 additionally gets a repo-local secondary recipe, confirmed live during planning —
the Operations board (`infiquetra` org, project #3) is reachable read-only, so the
pagination-truncation claim ("200 of 375") gets a real cross-check rather than a
conditional one:

```bash
gh api graphql -f query='{ organization(login: "infiquetra") { projectV2(number: 3) { title, items(first: 1) { totalCount } } } }'
```

This confirms the board's current total item count is queryable in one call, which is the
mechanism the "200 of 375" truncation claim is about (a paginator that only fetches the
first page). It does not reproduce the historical 375-item snapshot — it is a liveness
check on the query path, not a re-derivation of the frozen number — so the doc must label it
as such.

Metric 5 has no equivalent zero-effort secondary recipe: the grounding brief's only
artifact identifier near this claim is a *different* mining run's workflow ID
(`wf_7e5d77a2-5c0`, §7), not a path tied to the 219 dark codex sessions. Inventing a path
would violate this plan's own KTD1 discipline (verify before citing), so metric 5 keeps
only the primary grep-the-brief recipe, which already satisfies every acceptance criterion
on its own — matching the issue's own bar.

Test expectation: none — this is the artifact-authoring unit itself; U2 is its
verification.

### U2. Independently re-derive two metrics (AC9)

Re-run two of the eight committed recipes from U1 with no reference back to this plan's
drafting context, and confirm the output matches the number frozen in the doc. Use metric 1
("8 repos", a repo-count claim) and metric 7 ("350–450k tokens", a raw-number claim) — this
pair covers both citation shapes and both already have a recipe copy-pasteable straight from
this plan, so there is no ambiguity for `/work` to resolve at execution time.

Test expectation: run `grep -n "Manual ship ceremony" docs/plans/2026-07-03-plugin-fleet-grounding-brief.md`
and `grep -n "350–450k tokens" docs/plans/2026-07-03-plugin-fleet-grounding-brief.md`;
both must return a line whose content matches the number recorded in the new baseline doc.

### U3. Retro checklist line and journal entry

Add a closing line to the baseline doc instructing future `/retro` runs to re-derive all 8
recipes and diff against the committed numbers before claiming fleet improvement. Add one
`docs/engineering-journal/DECISIONS.md` entry recording KTD1 (re-verify citations at
write-time rather than trusting issue-drafted line numbers) — this is a reusable lesson:
any issue whose evidence citations point at a living document (not a frozen commit) needs
re-verification before the citations are load-bearing again.

Test expectation: `grep -i retro docs/plans/2026-07-04-plugin-fleet-baseline-metrics.md`
returns the checklist line; `DECISIONS.md` has a dated entry for this issue.

## Closeout (per shared kickoff contract)

- Release surfaces: not applicable (issue #461's own checklist confirms no plugin-behavior
  change); no `plugin.json`/`marketplace.json`/`CHANGELOG.md` edits needed.
- Phase 0 checklist: tick row 1 (#461) in
  `docs/plans/2026-07-04-plugin-fleet-execution-order.md` in the same PR that ships this
  doc.
- Board hygiene: move issue #461 from Idea to the next live status via mission-control at
  plan start (discover current Status vocabulary live rather than hardcoding it).
- Engineering journal: `DECISIONS.md` entry per U3, same commit.
