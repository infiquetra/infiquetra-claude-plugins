---
title: "enhancement: review-round delta packets — typed artifact pointer instead of cold-read"
repo: infiquetra-claude-plugins
type: enhancement
tier: structural
objective: "Make cache economics an engineered, measured win"
wave: wave-1
team: campps
project: operations
status: Idea
labels: enhancement, hermes-task, needs-plan
risk: low
handoff_maturity: requirements-ready
---

# enhancement: review-round delta packets — typed artifact pointer instead of cold-read

### Objective
Make cache economics an engineered, measured win.

## Summary

`team-execution`'s Step B3e re-engagement message already tells reviewers, in prose, to
review only "the specific delta/changes made since last review pass" — but the
`artifact-pointer` block it hands them derefs to `git diff <base-tree> <snapshot-tree>`,
i.e. the full cumulative diff from the run's original base tree to the current epoch's
snapshot tree, not a diff between the previous epoch's snapshot and the current one. On
round N >= 2, every re-engaged reviewer re-reads the whole diff again under a "delta"
label. This issue closes that gap: it derives a real epoch-to-epoch delta artifact and
wires it into the residency path the review loop already uses, so round N >= 2 reviewers
receive a genuinely smaller artifact instead of a full diff dressed as one.

## Problem Frame

- `plugins/team-execution/skills/team-execution/references/consensus-protocol.md:207-221`
  prescribes, in prose, that Step B3e re-engagement messages carry "only delta context,"
  and shows a `## Changes Made (Delta Only)` section — but the accompanying
  `artifact-pointer` example is `{"kind":"diff", ..., "epoch":"<epoch+1>", "deref":"git
  <base-tree> <snapshot-tree>", "base":"<base-tree-oid>"}`. The `base` field never
  changes between epochs; only `snapshot` (the `locator`) advances. Dereferencing that
  pointer always yields base-to-current, not previous-epoch-to-current.
- `plugins/team-execution/skills/team-execution/scripts/artifact_pointer.py`'s `snapshot`
  subcommand (registered at `main()`, `--epoch` argument at line 672) builds exactly one
  pointer shape — base tree vs. the snapshot tree for the given epoch — and has no
  subcommand or code path that diffs two snapshot epochs against each other. There is no
  machinery to produce an actual delta.
- `plugins/team-execution/skills/team-execution/SKILL.md:326-336` (Step B1) says the
  pointer is passed to reviewers/validators "in place of an inlined diff" above a size
  threshold, and that this happens "once per review epoch" — the emitted artifact is
  always a fresh full snapshot, reused unchanged as the "delta" on re-engagement.
- Binding decision `{#worker-cache-scheduling}` (grounding brief `docs/plans/2026-07-03-plugin-fleet-grounding-brief.md:47`)
  settles cache-economics architecture as "derive (segment+agent+tier) saga-side, reside
  team-side" — this issue is a derive-side addition consistent with that decision, not a
  new residency/scheduling primitive.
- This repo's typed-artifact-pointer seam (`{#artifact-pointer-ktds-291}`, PR #291,
  `plugins/team-execution/skills/team-execution/scripts/artifact_pointer.py`) just merged
  and is the natural extension point: this issue adds a second, epoch-scoped pointer kind
  rather than inventing a new transport.
- Root ideation record: `T4-F2-4` (theme T4 "Cache economics & worker reuse", frame F2
  "segment-residency-scheduling"), absorbed as primary into issue-map slug
  `pf-review-delta-packets` — "Stop re-reading the whole diff every review round — hand
  reviewers a derived delta packet via typed artifact pointer."

## Requirements

R1. `artifact_pointer.py` gains a way to produce a pointer whose `deref` command diffs
the **previous** reviewed epoch's snapshot tree against the **current** epoch's snapshot
tree for the same `run-id` (not base-tree vs. current), using the existing
`index.json` epoch-tracking sidecar (`artifact_pointer.py:325-339`) to resolve "previous
epoch reviewed" without the caller having to pass it explicitly.

R2. The new delta pointer is a valid instance of the existing `ArtifactPointer` shape
(`kind`, `locator`, `hash`, `epoch`, `deref`, `base` — `artifact_pointer.py:112-134`) so it
dereferences through the same `references/artifact-pointers.md` receiver contract
reviewers and validators already implement; it must not become a third pointer kind
requiring new receiver logic.

R3. Step B3e re-engagement (`consensus-protocol.md:207-221`) is updated to call the new
delta-pointer path instead of re-running `snapshot` and reusing the base-to-current
example. The size-threshold rule already governing pointerization (pointerize at > 4 KB,
or > 1 KB with >= 2 recipients — `SKILL.md:330-331`) applies to the delta artifact's size,
not the cumulative diff's size, so small fixes correctly stay inline even in large runs.

R4. Round 1 (first review, no prior epoch to diff against) is unaffected: Step B1's
existing full-snapshot pointer behavior (`SKILL.md:326-336`) is unchanged for the initial
review pass. Only re-engagement (Step B3e, iteration N >= 2) uses the delta form.

R5. If the previous epoch's snapshot ref is missing or has already been garbage-collected
(TTL reclaim, `artifact_pointer.py` `gc` subcommand), the delta path fails loud and falls
back to the existing full-diff pointer rather than silently emitting an empty or wrong
delta — consistent with halt-not-degrade.

## Key Flows

F1. **Round 1 review (unchanged).** Workers complete Step B1; `snapshot` runs once;
reviewers get the full base-to-current pointer as today. Not touched by this issue.

F2. **Round N >= 2 re-engagement (new).** Fix requests are implemented; Step B3e
re-engages only the reviewers that scored < 9.0 (`consensus-protocol.md:56-58`); instead
of a fresh `snapshot` reused as "delta," the new delta-pointer path diffs the last
epoch this reviewer actually reviewed against the new epoch, and that smaller pointer is
sent. Reviewer dereferences it via the unchanged `artifact-pointers.md` contract and sees
only what changed since their last pass.

F3. **Missing prior-epoch ref (fallback).** Previous epoch's snapshot ref is gone (TTL
`gc` already ran, or a resumed/stale run). Delta computation fails loud; the emitter falls
back to the existing full base-to-current pointer for that reviewer's re-engagement,
logging why the fallback happened.

## Definition of Done

A saga-derived review-delta artifact-pointer is merged and wired into the
`team-execution` review loop's residency path: `artifact_pointer.py` can produce an
epoch-to-epoch delta pointer (R1, R2), Step B3e re-engagement calls it instead of
reusing the base-to-current example (R3), Round 1 behavior is unchanged (R4), and the
missing-prior-epoch fallback is in place (R5) — with round N >= 2 reviewers verified to
receive the delta pointer, not the full diff, and the delta artifact round-trips through
the existing `ArtifactPointer` contract.

### Acceptance criteria
- [ ] AC1 (R1). Given two snapshot epochs for the same `run-id` with different file content,
  a delta command/function produces a pointer whose `deref` diffs epoch N-1's tree against
  epoch N's tree — verified by asserting the produced diff contains only the files changed
  between those two epochs, not files unchanged since the run's original base.
- [ ] AC2 (R2). The delta pointer JSON round-trips through the existing `ArtifactPointer`
  parse/validate path (`artifact_pointer.py:112-134` field set) unchanged — verified by a
  test that constructs a delta pointer and asserts it validates and derefs via the same
  code path a `kind="diff"` base-to-current pointer uses.
- [ ] AC3 (R3). Step B3e's reference example in `consensus-protocol.md` is updated to show the
  delta-producing invocation, not the base-to-current example currently shown at lines
  220-221 — verified by inspection/diff of the reference file plus a doc-lint check that no
  stale `git <base-tree> <snapshot-tree>` example remains in the Step B3e section.
- [ ] AC4 (R4). Round 1 (Step B1) behavior is provably unchanged — verified by an existing or
  updated `tests/test_team_execution_pointers.py` case asserting `snapshot`'s first-call
  output is byte-identical in shape to pre-change behavior.
- [ ] AC5 (R5). When the prior epoch's snapshot ref is absent, the delta path raises/returns a
  typed failure and the caller falls back to full-diff pointer emission — verified by a
  test that removes/never-creates the prior epoch ref and asserts fallback (not a silent
  empty delta) occurs.
- [ ] AC6. A round N>=2 reviewer test double receiving the new pointer, when it dereferences
  the artifact, gets strictly fewer changed files/bytes than the full base-to-current diff
  for the same run when both are computed over the same fixture — verified by comparing
  `deref` output sizes.

### Out-of-scope / non-goals
- No new pointer `kind` (stays `"diff"`); no new receiver-side contract in
  `references/artifact-pointers.md` beyond what already exists for `kind="diff"`.
- No change to Step B1's first-pass full-snapshot behavior, the 9.0/10 consensus
  threshold, the 3-cycle iteration cap, or the re-review scoping rule (only reviewers
  scored < 9.0 are re-engaged) — those stay exactly as `consensus-protocol.md` defines
  them today.
- No change to the `VERIFY_N_CAP`, `/optimize`'s removed concurrency knob, or any other
  fleet-wide concurrency/scheduling primitive — this is a derive-side artifact shape
  change only, per `{#worker-cache-scheduling}`.
- No new residency/scheduling primitive, no second executor kind, no external-engine
  participation — untouched by `{#external-engines-never-gatekeepers}` and
  `{#external-engine-chaperone-dispatch}` (no external engine is involved in review
  delta production or consumption).
- Validators (Step B3, scanner path) are out of scope: this issue only changes what
  reviewers receive on re-engagement, not the validator diff-summary path.

## Grounding References

| Absorbed id | Basis / role | What it contributes |
|---|---|---|
| `T4-F2-4` (primary) | direct; theme T4 "Cache economics & worker reuse", frame F2 "segment-residency-scheduling"; `docs/plans/plugin-fleet-ideation-2026-07-03/survivors/T4.json` | Title, `outcome_shape` ("PR wiring a saga-derived review-delta artifact-pointer into the team-execution review-loop residency path... verified by a test asserting round N>=2 reviewers receive a delta pointer (not full diff) and the delta artifact round-trips"), and `dod_sketch` used verbatim as this issue's Definition of Done. |

Binding decisions this issue builds on / must not contradict:
- `{#worker-cache-scheduling}` — cache-economics architecture already settled
  (derive saga-side, reside team-side, segment boundary = plugin directory); this issue is
  a derive-side addition, not a new architecture. Revisit-when clause (named-teammate
  residency insufficient, or idle-poll justifies a wave queue) is not triggered by this
  change.
- `{#artifact-pointer-ktds-291}` — the typed artifact-pointer seam this issue extends
  (PR #291, `plugins/team-execution/skills/team-execution/scripts/artifact_pointer.py`).
- `{#plugin-portfolio-groom-17-to-7}` — no new plugin; this is an in-place change to the
  existing `team-execution` plugin's review loop.

## Recommended Executor Profile

- **Model:** sonnet
- **Effort:** medium
- **Backend:** inline
- **External-LLM posture:** none
- **Justification:** Mechanical extension of an existing, well-specified module
  (`artifact_pointer.py`) plus a reference-doc correction; no architectural judgment call,
  no external-engine involvement, no consensus/gating change. Sonnet at medium effort
  matches the fleet's tiering guidance for scoped, well-bounded code + doc changes; no
  case is made here for opus.

## Release-Surface Checklist

This changes `team-execution` plugin behavior (review-loop artifact shape on
re-engagement), so the following must land in the same PR:
- [ ] `plugins/team-execution/.claude-plugin/plugin.json` — version bump (current:
      `2.9.0`) reflecting the new delta-pointer capability.
- [ ] `.claude-plugin/marketplace.json` — `team-execution` entry version/description kept
      in sync with the plugin.json bump.
- [ ] `plugins/team-execution/CHANGELOG.md` — new entry describing the epoch-delta pointer
      addition and the Step B3e reference-doc correction.
- [ ] Any version/metadata drift-guard test in `tests/` that asserts plugin.json ==
      marketplace.json == CHANGELOG top-entry version stays green after the bump.

### Files expected to change
- `plugins/team-execution/skills/team-execution/scripts/artifact_pointer.py` — add
  epoch-to-epoch delta pointer production, reusing `index.json`'s per-run epoch tracking.
- `plugins/team-execution/skills/team-execution/references/consensus-protocol.md` — replace
  the base-to-current `artifact-pointer` example at Step B3e with the delta-pointer
  invocation.
- `plugins/team-execution/skills/team-execution/references/artifact-pointers.md` — note
  (if needed) that a `kind="diff"` pointer's `deref` may span two snapshot epochs rather
  than base-to-snapshot, with no new receiver-side handling required.
- `plugins/team-execution/.claude-plugin/plugin.json`, `.claude-plugin/marketplace.json`,
  `plugins/team-execution/CHANGELOG.md` — release-surface bump (see checklist above).
- `tests/test_team_execution_pointers.py` — new delta-pointer tests (AC1, AC2, AC4, AC5).
- `tests/test_team_execution_consensus.py` — Step B3e wiring test (AC3, AC6).

### Tests to add or update
- `tests/test_team_execution_pointers.py`: delta pointer diffs epoch N-1 vs. epoch N only
  (AC1); delta pointer round-trips through existing `ArtifactPointer` validate/deref path
  (AC2); Step B1 first-pass snapshot output unchanged (AC4); missing prior-epoch ref
  triggers typed fallback to full-diff, not silent empty delta (AC5).
- `tests/test_team_execution_consensus.py`: Step B3e re-engagement path emits the new
  delta pointer for reviewers scored < 9.0 on round N>=2, and a fixture reviewer sees a
  strictly smaller diff than the full base-to-current pointer over the same run (AC3, AC6).

### Verification
```bash
uv run pytest tests/test_team_execution_pointers.py tests/test_team_execution_consensus.py -v
uv run pytest && uv run ruff check . && uv run mypy plugins/ scripts/ tests/ --ignore-missing-imports
```
Expected: all listed tests pass; full suite, lint, and type-check stay green.

### Handoff maturity
requirements-ready

### Suggested next action
Use `/plan <issue>` to create an implementation plan.

### Source context
- Source: `docs/plans/plugin-fleet-ideation-2026-07-03/survivors/T4.json` (id `T4-F2-4`)
- Source type: ideation survivor (absorbed into issue-map slug `pf-review-delta-packets`)
- Grounding: `docs/plans/2026-07-03-plugin-fleet-grounding-brief.md`

### Intent

`team-execution`'s Step B3e re-engagement message already tells reviewers, in prose, to review only "the specific delta/changes made since last review pass" — but the `artifact-pointer` block it hands them derefs to `git diff <base-tree> <snapshot-tree>`, i.e. the full cumulative diff from the run's original base tree to the current epoch's snapshot tree, not a diff between the previous epoch's snapshot and the current one. On round N >= 2, every re-engaged reviewer re-reads the whole diff again under a "delta" label. This issue closes that gap: it derives a real epoch-to-epoch delta artifact and wires it into the residency path the review loop already uses, so round N >= 2 reviewers receive a genuinely smaller artifact instead of a full diff dressed as one.

### Context library links

_none_

## Created Issue

- URL: https://github.com/infiquetra/infiquetra-claude-plugins/issues/361
- Number: 361
- Created at: 2026-07-04T07:49:51.895704+00:00

