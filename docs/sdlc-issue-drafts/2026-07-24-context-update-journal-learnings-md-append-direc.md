---
title: context-update(journal): LEARNINGS.md append direction contradicts its own stated convention
repo: infiquetra-claude-plugins
type: context-update
team: asgard
project: operations
status: Shaping
labels: context-update, documentation, hermes-not-actionable
risk: low
mode: docs
handoff_maturity: requirements-ready
---

# context-update(journal): LEARNINGS.md append direction contradicts its own stated convention

## Summary

`docs/engineering-journal/LEARNINGS.md` states one append convention in its header and practices
the opposite in its most recent ~400 lines. A reader who trusts the header reads the wrong end of
the file and misses the newest material entirely.

## Evidence

Measured on `origin/main` at `474fd3cc`:

| Fact | Value |
|---|---|
| Total lines | 4205 |
| Dated `## YYYY-MM-DD` headings | 44 |
| Last dated heading | `## 2026-05-01`, line 3805 |
| `###` entries appended *after* that heading | 16 (~400 lines, ~10 % of the file) |

The header (lines 5-6) says:

> **Append new entries to the top.** Most-recent first.

And the dated sections do descend correctly — `## 2026-07-22` at line 28, `## 2026-07-21` at 85,
`## 2026-07-20` at 144, down to `## 2026-05-01` at 3805. That part works.

The problem is everything *after* line 3805. Sixteen entries live there with no date heading of
their own, and several are unambiguously recent: `{#async-spawn-posttooluse-race-616-r8}` and
`{#harvest-leaf-saga-id-backfill-617}` both document work done 2026-07-23, and
`{#prepared-sidecar-objective-inert-637}` is from the same week. They sit under a heading that says
2026-05-01.

Reproduce:

```
git show origin/main:docs/engineering-journal/LEARNINGS.md > /tmp/L.md
grep -nE '^## [0-9]{4}' /tmp/L.md | tail -1        # -> 3805:## 2026-05-01
grep -nE '^### ' /tmp/L.md | awk -F: '$1>3805' | wc -l   # -> 16
```

## Why it matters

Two failure modes, both silent:

1. **Newest-first is false.** Someone following the header reads the top, finds `## 2026-07-22`,
   and reasonably concludes that is the latest entry. Everything from 07-23 and 07-24 is 3800 lines
   further down.
2. **Date lookup is wrong.** "What did we learn in May?" returns July entries. The dated-heading
   index is the file's only navigation aid and it silently mis-sorts ~10 % of the content.

Neither is loud. Nothing errors, nothing fails CI, and both readings look correct from the inside.

## What was deliberately not done

The #620 entry `{#sys-modules-stale-patch-620}` landed in PR #656 appended at the **tail**, beside
its campaign siblings — following the practiced convention rather than the stated one, because that
is where a reader currently finds recent material. Restructuring 400 lines inside a merge-pending
docs PR was out of scope. That decision is recorded in commit `be7765f7` and is reversible.

## Fix shapes (not prescriptive)

1. **Ratify the practice.** Change the header to say append-at-bottom, drop or mark-historical the
   dated-heading index. Cheapest, zero risk, loses chronological navigation.
2. **Restore the stated convention.** Re-file the 16 orphaned entries under correct dated headings
   at the top. Mechanical but non-trivial: each entry's true date comes from the commit that added
   it (`git log -S '{#anchor}' -- docs/engineering-journal/LEARNINGS.md`), and every `{#slug}`
   anchor must survive because other entries and `DECISIONS.md` cross-reference them.
3. **Make it checkable.** Whichever convention wins, add a lint that fails when an entry lands
   outside the declared order. Without it the drift recurs — it accumulated 16 entries deep with
   nobody noticing. #407 (`check_journal.py`) is the natural home.

Recommend 2 + 3 if the chronological index is worth keeping, otherwise 1 + 3. Either without 3
means re-filing this issue in a few months.

### Files expected to change

- `docs/engineering-journal/LEARNINGS.md` — header convention and/or entry placement.
- `scripts/check_journal.py` (new, only under fix shape 3) plus its test under `tests/`.
- `docs/engineering-journal/DECISIONS.md` — a decision entry recording which convention won.

### Tests to add or update

- Only under fix shape 3: a test for the journal lint that fails on an out-of-order entry and
  passes on the repaired file.
- No test changes for the docs-only shapes.

### Context library links

- Shared practice: https://github.com/infiquetra/infiquetra-sdlc/blob/main/docs/process/engineering-journal.md

### Acceptance criteria

- [ ] `LEARNINGS.md`'s stated convention and its actual entry order agree — verify with
      `grep -nE '^## [0-9]{4}' docs/engineering-journal/LEARNINGS.md | tail -1` and confirm no
      `###` entry sits below it that postdates it.
- [ ] Every existing `{#slug}` anchor still resolves: no cross-reference in `LEARNINGS.md`,
      `DECISIONS.md`, `QUEUED.md`, or `narratives/` points at a missing anchor.
- [ ] A `DECISIONS.md` entry records which convention won and why.

### Verification

```
grep -nE '^## [0-9]{4}' docs/engineering-journal/LEARNINGS.md | tail -1
grep -oE '\{#[a-z0-9-]+\}' docs/engineering-journal/*.md | sort -u | wc -l
uv run pytest -q tests/ -k journal
```

### Objective

`improve-claude-plugins` (Operations board). Journal hygiene surfaced while placing the #620
learning during PR #656; not a leaf of the governed-execution-integrity DAG.

### Intent

The engineering journal's stated navigation contract is true, so a reader can find the newest
learning without knowing which end of the file the last author happened to use.

### Target repo / surface

`infiquetra-claude-plugins` — `docs/engineering-journal/LEARNINGS.md`, and `scripts/` only if the
lint shape is chosen.

### Mode

docs

### Constraints

Anchor stability is the hard constraint — `{#slug}` targets are cross-referenced from other journal
files and from issue bodies, so no re-file may change or drop one. Entry *text* must not be edited
while moving; this is a placement fix, not a rewrite. Docs-only shapes take no plugin version bump.

### Risk

low — documentation only, fully reversible, no runtime path. The only real hazard is breaking
anchors during a bulk move, which the acceptance criteria check directly.

### Transfer notes

Do the archaeology before the move: `git log -S '{#anchor}'` gives each orphaned entry's true date,
and several of the 16 may genuinely belong to 2026-05-01 — do not assume all of them are misfiled.
The drift is at least three months deep, so expect some entries whose commit date and content date
disagree. Related open idea: #407 (`check_journal.py` — schema-validate engineering journals).

### Out-of-scope / non-goals

Rewriting or pruning entry content (that is `/retro`'s promote/supersede/prune pass); the other
journal files (`DECISIONS.md`, `QUEUED.md`, `ARCHIVE.md`, `narratives/`) unless they carry the same
drift; building the full `check_journal.py` capability from #407, which is broader than this fix.

### Handoff maturity
requirements-ready

### Suggested next action
Use `/plan <issue>` to create an implementation plan.

### Source context

- Source: `docs/engineering-journal/LEARNINGS.md` at `origin/main` `474fd3cc`
- Source type: repo-measurement
- Noticed while placing the #620 learning during PR #656.

### Recommended Tier Band
sonnet/low

## Created Issue

- URL: https://github.com/infiquetra/infiquetra-claude-plugins/issues/659
- Number: 659
- Created at: 2026-07-24T23:41:21.183518+00:00

