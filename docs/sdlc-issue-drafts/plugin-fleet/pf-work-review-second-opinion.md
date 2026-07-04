---
title: "enhancement: second-opinion triggers inside /work and reviews"
repo: infiquetra-claude-plugins
type: enhancement
team: campps
project: operations
status: Idea
labels: enhancement, hermes-task, needs-plan
risk: medium
handoff_maturity: requirements-ready
tier: structural
objective: "Stand up the external-engine offload lane"
wave: wave-1
---

# enhancement: second-opinion triggers inside /work and reviews

## Summary

Wires three concrete second-opinion trigger points into the existing `/work` round-N gate
and the `/code-review` (and `/doc-review`) finding pipeline: (1) a flagged review finding can
be sent to an external engine for an advisory second opinion, with Claude logging its own
keep/downgrade/dismiss re-adjudication; (2) `/work`'s round-N loop detects a stuck signal
(repeated failed-test cycles / thrash) and surfaces a one-line offer to get a second opinion,
never auto-dispatching; (3) a reviewer can point out a single finding for an opus-high second
opinion without that opinion gating the verdict. All three are advisory-only dispatches under
the existing chaperone-dispatch model — none of them create a new executor kind, a residency,
or a gate that an external engine can trip.

## Problem Frame

The fleet already has the machinery to author and render external-engine dispatch (`ENGINE_INTENTS`
is produced in `plan/SKILL.md:303-304` and rendered by team-execution's Step A7 worker table,
`team-execution/SKILL.md:229-233` → `references/external-engine-workers.md`), but that producer/
consumer pair is completely absent from `/work`'s interactive flow and from `/code-review`'s
finding-adjudication loop (`docs/plans/2026-07-03-plugin-fleet-grounding-brief.md:24-27`,
correction (c) to intake §9). Concretely:

- `/work`'s round-N PR continuation loop (`plugins/saga/skills/work/SKILL.md:115` Phase 0.4
  round-N detection, `:314` Phase 3 test gates, `:418` Phase 5.3 hard review gate) has no
  stuck-signal detector and no path to an external second opinion when a fix cycle is
  thrashing. The grounding brief records this exact pain as the #2 ranked recurring session
  pattern this quarter: "gate-primitive unreliability... agents fall back to plain-text
  questions" across 6 repos (`docs/plans/2026-07-03-plugin-fleet-grounding-brief.md:122-125`),
  and separately flags "ad hoc tier reasoning every time... operator asking for mid-run
  model-change pauses" (3 repos, `:132-134`) — both point at the same missing lever: no
  in-loop offer to escalate when Claude is stuck, and no standard place to hang it.
- `/code-review`'s Stage-A/Stage-B merge-and-validate pipeline
  (`plugins/saga/skills/code-review/SKILL.md` §Phase 4, cross-reviewer promotion and
  confidence-gate logic, and §5.5 fixer-dispatch offer) has an `advisory` consensus-signal
  concept for in-session votes ("N throwaway in-session votes you act on yourself, nothing
  recorded blocking" — `plugins/saga/skills/code-review/SKILL.md`, Phase 3 review-depth
  section) but no per-finding hook that lets either Claude or a human reviewer route one
  specific finding out to an external engine and fold the answer back in as evidence under
  that finding.
- The binding decision register is unambiguous about the ceiling on all three triggers:
  `{#external-engines-never-gatekeepers}` (#283) — "Claude is verifier-of-record for every
  gated decision; codex/agy = generator / advisory-reviewer / non-gated worker only" — and
  `{#external-engine-chaperone-dispatch}` (#318) — "offload→sonnet/medium, second-opinion→
  opus/high, never a second executor kind / residency / git participant"
  (`docs/plans/2026-07-03-plugin-fleet-grounding-brief.md:45-46`). Every trigger this issue
  adds must be advisory, logged, and non-blocking by construction.
- Seed `S-26` (`docs/plans/plugin-fleet-ideation-2026-07-03/survivors/seeds.json`, id `S-26`)
  captured the operator's raw, still-unsettled question — "external-LLM offload-vs-second-
  opinion... at /ideate /brainstorm /plan /work /doc-review /code-review" — as an
  exploration-tier recommendation-doc ask. This issue settles the `/work` and
  `/code-review`/`/doc-review` slice of that per-command posture question in the docs
  themselves (see Acceptance Criteria), rather than deferring it to a separate standalone doc.

### Acceptance criteria
- [ ] A flagged `/code-review` (or `/doc-review`) finding can be dispatched to an external
   engine for a second opinion; Claude's own keep/downgrade/dismiss re-adjudication of that
   finding is recorded against the finding record (not just spoken in-session). Check: a
   fixture review run with one seeded finding, dispatched for a second opinion, produces a
   findings-schema record whose finding carries an `external_opinion` (or equivalent) block
   plus a `claude_adjudication` field with one of `keep`/`downgrade`/`dismiss`. (T1-F3-8)
- [ ] `/work`'s round-N loop detects a repeated-failure / thrash signal (for example: the same
   test file fails N consecutive fix attempts, per a documented threshold) and surfaces a
   single one-line offer to get a second opinion — it does not auto-dispatch. Check: a
   scripted `/work` fixture that trips the repeated-failure signal shows the offer line in
   transcript output and shows no engine call fired unless the operator explicitly accepts
   the offer. (T1-F6-7)
- [ ] A reviewer (human or Claude acting as reviewer) can point out one specific finding for an
   opus-high second opinion, and that request never gates the review's overall verdict —
   the verdict computation proceeds independent of whether the pointed-out opinion has
   returned. Check: a fixture test asserts the returned opinion is stored as advisory
   evidence under the finding (`verified_by_claude` or equivalent flag distinct from the
   route decision) and that the review's `blocked`/verdict fields are computed the same way
   whether or not the point-out was requested. (T1-F5-1)
- [ ] All three triggers are documented in `/work/SKILL.md` and `/code-review/SKILL.md` (or the
   shared `references/external-engine-workers.md`) as advisory-only under the existing
   chaperone-dispatch model: no trigger in this issue creates a new executor kind, git
   residency, or team-execution participant, and none of the three can flip a `blocked`/
   gate status by itself. Check: a doc-lint or manual reviewer can point at the exact
   sentence in each SKILL.md stating the advisory-only, non-gating posture for that trigger.
- [ ] This issue's own text states, for `/work`, `/code-review`, and `/doc-review`, whether the
   external-engine use in each of the three triggers is "offload" (does the work) or
   "second-opinion" (advisory review only) — settling `S-26`'s per-command posture question
   for these three commands specifically (all three triggers here are second-opinion, never
   offload). Check: this document's Grounding References section names the posture per
   trigger; no separate standalone recommendation doc is required to close `S-26` for these
   commands.

### Out-of-scope / non-goals
**In scope:**
- The three trigger points named above, wired into existing `/work` and `/code-review` (and,
  where the same finding pipeline is shared, `/doc-review`) control flow.
- Recording the second-opinion result and Claude's adjudication against the finding /
  work-session record so it survives past the interactive session (not just a transcript
  line).
- Updating `plugins/saga/skills/work/SKILL.md`, `plugins/saga/skills/code-review/SKILL.md`,
  and (if the finding schema needs a field) `plugins/saga/skills/code-review/references/
  findings-schema.md` to describe the trigger, its advisory posture, and its stuck-signal
  threshold (for T1-F6-7).

**Out of scope / non-goals:**
- Building a new external-engine dispatch transport. This issue reuses the existing
  `ENGINE_INTENTS` producer/consumer pair (`plan/SKILL.md:303-304`,
  `team-execution/SKILL.md:229-233`) and the existing chaperone-dispatch tiers; it does not
  invent a new dispatch mechanism.
- Extending second-opinion triggers into `/ideate`, `/brainstorm`, or `/plan` — those remain
  open under seed `S-26` and are not settled by this issue.
- Any change to `/outcome`'s DAG-level dispatch, team-execution's worker-slot model, or the
  `{#external-engines-never-gatekeepers}` binding decision itself. This issue operates
  entirely within that decision's existing ceiling; it does not revisit it.
- A standing/scheduled measurement of second-opinion usefulness or override rate. If that's
  wanted later, it is a follow-up, not part of this issue's definition of done.
- Auto-dispatch of any kind. Every trigger in this issue is operator-confirmed before an
  external engine is called; T1-F6-7 explicitly requires the offer to be declinable.

## Definition of Done

A merged PR (or PRs) that:
- Adds the review-failure second-opinion offer to `/work`'s round-N gate (advisory dispatch
  on a flagged finding's validity, with Claude's keep/downgrade/dismiss re-adjudication
  logged against the finding record).
- Adds the stuck-signal detector (repeated failed-test cycles / thrash) to `/work`'s round-N
  loop, surfacing a one-line second-opinion offer that never auto-dispatches.
- Adds the granular per-finding "point-out" step to `/code-review` (and `/doc-review` where
  the finding pipeline is shared), letting a reviewer dispatch one finding for a
  second-opinion / opus-high advisory opinion that is folded under that finding as evidence,
  without gating the review's verdict on its return.
- Is verified by: a `/work` transcript in which a flagged finding gets an engine second
  opinion and Claude's re-adjudication is recorded before any churn/fix decision; a scripted
  `/work` fixture that trips the repeated-failure signal and shows the offer surfacing
  without auto-dispatching (in attended mode); and a fixture test asserting a point-out
  opinion is stored as advisory evidence with `verified_by_claude` (or equivalent) present,
  and that verdict computation is unaffected by its presence or absence.

## Grounding References

| Absorbed id | Role | Basis | Posture settled here |
|---|---|---|---|
| `T1-F3-8` | primary | Ideation survivor, theme T1 / frame F3 ("Adversarial second-opinion on FINDING /work round-N review-failure boundary"), `docs/plans/plugin-fleet-ideation-2026-07-03/survivors/T1.json` | second-opinion (advisory only; Claude keeps verifier-of-record role per `{#external-engines-never-gatekeepers}`) |
| `T1-F6-7` | facet | Ideation survivor, theme T1 / frame F6 ("Auto-offer a second opinion when /work hits an uncertainty signal"), same file | second-opinion, offer-only, never auto-dispatched |
| `T1-F5-1` | facet | Ideation survivor, theme T1 / frame F5 ("Engine point-out: per-finding second-opinion flag judgment stages"), same file | second-opinion, folded as advisory evidence under the finding, non-gating |
| `S-26` | dedup-merged | Seed, `docs/plans/plugin-fleet-ideation-2026-07-03/survivors/seeds.json` id `S-26`, basis: operator statement "external-LLM offload-vs-second-opinion question at /ideate /brainstorm /plan /work /doc-review /code-review" | this issue settles the `/work`/`/code-review`/`/doc-review` slice of S-26's per-command posture question as second-opinion (see Acceptance Criteria #5); `/ideate`, `/brainstorm`, `/plan` remain open |

Binding decisions this issue builds inside, not around:
- `{#external-engines-never-gatekeepers}` (#283) — Claude verifier-of-record; external
  engines generator/advisory-reviewer/non-gated worker only.
- `{#external-engine-chaperone-dispatch}` (#318) — offload→sonnet/medium, second-opinion→
  opus/high, never a new executor kind/residency/git participant.
- `{#operator-choice-framework}` — operator-choice is doc-only, CLI-driven `/work`; consistent
  with T1-F6-7's offer-not-auto-dispatch requirement.

Grounding brief cites: `docs/plans/2026-07-03-plugin-fleet-grounding-brief.md:24-27` (theme 2
correction on `ENGINE_INTENTS` producer/consumer gap), `:45-46` (binding-decision register),
`:122-125` and `:132-134` (recurring-pain signals motivating the stuck-signal trigger).

## Recommended Executor Profile

- **Model:** sonnet
- **Effort:** medium
- **Backend:** inline
- **External-LLM posture:** second-opinion (this issue's own subject matter — dispatch is
  advisory-only per `{#external-engine-chaperone-dispatch}`)
- **Justification:** This is a scoped SKILL.md wiring change against an already-understood
  control-flow shape (round-N gate, finding pipeline) with no novel architecture — sonnet at
  medium effort is sufficient. No case for opus: the design decisions (advisory-only,
  non-gating, offer-not-auto-dispatch) are already settled by the binding-decision register
  cited above, so this is mechanical wiring plus doc updates, not open judgment work.

## Release-Surface Checklist

Plugin behavior, prompts, and user-facing guidance change in `saga` (the `/work` and
`/code-review`/`/doc-review` skills). Update in the same PR:
- [ ] `plugins/saga/.claude-plugin/plugin.json` — version bump
- [ ] `.claude-plugin/marketplace.json` — saga entry metadata in sync
- [ ] `plugins/saga/CHANGELOG.md` — entry describing the three new second-opinion triggers
- [ ] Any version/metadata drift-guard tests updated to reflect the bump
- [ ] `plugins/saga/skills/code-review/references/findings-schema.md` updated if a new field
      (`external_opinion`, `claude_adjudication`, or equivalent) is added to the finding shape

## Files Expected to Change

Indicative only; exact set is `/plan`'s to determine.
- `plugins/saga/skills/work/SKILL.md` — round-N gate second-opinion offer, stuck-signal
  detector in Phase 3 / Phase 5.3.
- `plugins/saga/skills/code-review/SKILL.md` — per-finding point-out step in Phase 4
  merge-and-validate.
- `plugins/saga/skills/code-review/references/findings-schema.md` — new field(s) for
  external opinion + Claude adjudication, if needed.
- `plugins/saga/skills/doc-review/SKILL.md` — point-out step, if `/doc-review` shares the
  finding pipeline with `/code-review`.
- `plugins/saga/CHANGELOG.md`, `plugins/saga/.claude-plugin/plugin.json`,
  `.claude-plugin/marketplace.json` — release-surface updates per checklist above.
- `tests/` — new or updated fixture tests for the three triggers.

## Tests to Add or Update

- `/work` round-N fixture: flagged finding dispatched for second opinion → Claude's
  keep/downgrade/dismiss adjudication recorded on the finding record.
- `/work` round-N fixture: scripted repeated-failure signal trips → one-line offer appears,
  no engine call fires without explicit operator acceptance.
- `/code-review` (or `/doc-review`) fixture: point-out on one finding → advisory opinion
  stored with `verified_by_claude`/equivalent flag; overall verdict computation unaffected by
  presence or absence of the point-out.
- Doc-lint or manual check: each SKILL.md states the advisory-only, non-gating posture for
  its trigger.

### Verification
```bash
# Targeted fixture tests for the three triggers (paths indicative; /plan finalizes names)
uv run pytest tests/test_work_second_opinion.py tests/test_code_review_point_out.py -v

# Full repo gate (CI parity)
uv run pytest && uv run ruff check . && uv run mypy plugins/ scripts/ tests/ --ignore-missing-imports
```
Expected: all green; the `/work` and `/code-review` fixtures above pass, demonstrating the
offer/point-out/adjudication behavior without any auto-dispatch or verdict-gating regression.

### Handoff maturity
requirements-ready

### Suggested next action
Use `/plan <issue>` to create an implementation plan.

### Source context
- Source: `docs/plans/plugin-fleet-ideation-2026-07-03/survivors/T1.json` (ids `T1-F3-8`,
  `T1-F6-7`, `T1-F5-1`), `docs/plans/plugin-fleet-ideation-2026-07-03/survivors/seeds.json`
  (id `S-26`), `docs/plans/2026-07-03-plugin-fleet-grounding-brief.md`
- Source type: ideation (Gate B issue-map consolidation)
- Source title: Second-opinion triggers inside /work and reviews: stuck-signal offer,
  round-N finding adjudication, per-finding point-out

### Intent

Wires three concrete second-opinion trigger points into the existing `/work` round-N gate and the `/code-review` (and `/doc-review`) finding pipeline: (1) a flagged review finding can be sent to an external engine for an advisory second opinion, with Claude logging its own keep/downgrade/dismiss re-adjudication; (2) `/work`'s round-N loop detects a stuck signal (repeated failed-test cycles / thrash) and surfaces a one-line offer to get a second opinion, never auto-dispatching; (3) a reviewer can point out a single finding for an opus-high second opinion without that opinion gating the verdict. All three are advisory-only dispatches under the existing chaperone-dispatch model — none of them create a new executor kind, a residency, or a gate that an external engine can trip.

### Context library links

_none_

### Files expected to change

- `references/external-engine-workers.md`
- `plugins/saga/skills/code-review/SKILL.md`
- `docs/plans/plugin-fleet-ideation-2026-07-03/survivors/seeds.json`
- `/work/SKILL.md`
- `/code-review/SKILL.md`
- `plugins/saga/skills/work/SKILL.md`
- `docs/plans/plugin-fleet-ideation-2026-07-03/survivors/T1.json`
- `plugins/saga/.claude-plugin/plugin.json`

### Tests to add or update

- `tests/test_code_review_point_out.py`
- `tests/test_work_second_opinion.py`

### Objective

"Stand up the external-engine offload lane"

## Created Issue

- URL: https://github.com/infiquetra/infiquetra-claude-plugins/issues/394
- Number: 394
- Created at: 2026-07-04T07:59:45.326994+00:00

