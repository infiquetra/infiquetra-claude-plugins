---
title: capability: ship_ceremony.py — one composable, resumable guarded ship primitive replacing the 8-repo manual ritual
repo: infiquetra-claude-plugins
type: capability
team: campps
project: operations
status: Idea
labels: capability, hermes-task, needs-plan
risk: medium
handoff_maturity: requirements-ready
tier: structural
wave: wave-1
objective: Automate the ship ceremony end-to-end
---

# capability: ship_ceremony.py — one composable, resumable guarded ship primitive replacing the 8-repo manual ritual

### Objective
Automate the ship ceremony end-to-end

### Tier
structural

### Wave
wave-1

### Intent

Replace the raw, hand-typed `commit → PR → merge → checkout-main → pull → branch-delete` sequence
that every /work session currently performs with a single composable, resumable, state-tracked
`ship_ceremony.py` primitive — invocable from `/work`, from a git-surface entry point (alias or
hook), and eventually front-loadable to open a draft PR at work start — so shipping a change stops
being an ad hoc ritual re-typed slightly differently in every repo and becomes one guarded state
machine with a saga tick and a reversibility verdict per transition.

### Problem / Motivation

Session-mining synthesis (2026-07-03 grounding brief) ranks "manual ship ceremony" as the
**#1 recurring pain pattern by repo spread**: *"Manual ship ceremony — commit→PR→merge→checkout-main→pull→cleanup
done by raw git/gh in session, even where saga/mission-control installed (8 repos)."*
(`docs/plans/2026-07-03-plugin-fleet-grounding-brief.md:119-121`, feeding theme 7 — "Lifecycle
auto-progression & ship ceremony", `docs/plans/2026-07-03-plugin-fleet-grounding-brief.md:169`).

This is not a hypothetical gap — it is the fleet's own current implementation. `plugins/saga/skills/work/SKILL.md`
section 5.4 ("Reach PR-ready — present continuation routing") has `/work` hand-drive `gh pr create` +
reviewer request (`plugins/saga/skills/work/SKILL.md:445`) and, once approved/clean/fresh, offer
`gh pr merge` explicitly confirmed (`plugins/saga/skills/work/SKILL.md:452`). There is no state
machine, no transition table, no resume-from-state, and no post-merge cleanup step (checkout-main,
pull, branch-delete) anywhere in that flow — each of the 8 repos the grounding brief scanned
re-derives the same raw sequence by hand in every session.

Three absorbed ideation facets converge on this same gap from three angles and are folded into one
issue rather than shipped as three separate primitives, per the plugin-portfolio-groom binding
decision (`{#plugin-portfolio-groom-17-to-7}` — "new plugin ideas carry consolidation burden proof",
cited in `docs/plans/2026-07-03-plugin-fleet-grounding-brief.md:52`):

- **T7-F4-1** (primary) — the core ask: one composable, resumable state machine primitive,
  `plugins/saga/scripts/ship_ceremony.py`, replacing the raw commands with a transition table and a
  per-transition saga tick + reversibility verdict, verified end-to-end against a throwaway branch.
- **H-F3-6** (facet) — the ownership-boundary correction: the ceremony belongs on the git surface
  (terminal — an installable alias/hook pack), not only inside the conversational skill; the 8-repo
  finding is read as an adoption verdict, not just a documentation gap.
- **H-F2-3** (facet) — the removal/timing facet: move ceremony preparation to time zero — mint the
  branch and open the draft PR at `/work` start — so that by the time the operator is ready to ship,
  "ship" is reduced to a flip of an already-open draft PR to ready, rather than a fresh multi-step
  ritual invented at the end.

All three facets are `tier_guess: structural`, `verdict: survive` in the ideation survivor set
(`docs/plans/plugin-fleet-ideation-2026-07-03/survivors/T7.json`, entries for `T7-F4-1`, `H-F3-6`,
`H-F2-3`) and share the same theme (`T7`, "Lifecycle auto-progression & ship ceremony").

### Requirements

R1. `plugins/saga/scripts/ship_ceremony.py` implements a state machine with an explicit transition
    table covering at minimum: commit → open/reuse PR → request review → merge (confirmed) →
    checkout-main → pull → branch-delete. Each transition is resumable — the primitive can be
    invoked mid-ceremony and continue from last-recorded state rather than restarting.

R2. Each transition emits a saga tick (durable state write, consistent with existing saga state
    conventions in `plugins/saga/scripts/lifecycle_state.py` and `outcome_*` tick patterns) and
    records a reversibility verdict — whether that transition can be safely undone if a later step
    fails.

R3. The primitive is invocable from two distinct entry points: (a) `/work`'s existing PR-ready flow
    (`plugins/saga/skills/work/SKILL.md` section 5.4), replacing the current raw `gh pr create`
    (`:445`) / `gh pr merge` (`:452`) calls; and (b) a git-surface entry point — an installable git
    alias or hook pack with matching install/uninstall tooling — so the ceremony can be triggered
    from the terminal without a live Claude Code conversation.

R4. Merge, PR-open, and review-request remain explicitly operator-confirmed at each mutating step —
    the ceremony automates the *sequence and bookkeeping*, not the *authorization*. This preserves
    `/work`'s existing non-goal that it must NOT silently mutate GitHub
    (`plugins/saga/skills/work/SKILL.md:452`-`:460` region, "5.5 /work boundaries").

R5. `work/SKILL.md` no longer contains any raw ceremony git/gh commands (`git checkout`, `git pull`,
    `git branch -d`, ad hoc `gh pr create`/`gh pr merge` invocations) — all such calls are delegated
    to `ship_ceremony.py`.

R6. A front-loaded mode exists that, invoked at `/work` start, mints the working branch, pushes the
    initial scaffold, and opens a draft PR carrying the plan link, so that reaching "ship" later is
    reduced to flipping the existing draft PR to ready rather than opening a new one.

## Definition of Done

`plugins/saga/scripts/ship_ceremony.py` ships as a resumable state machine (commit → PR →
review-request → merge → checkout-main → pull → branch-delete) with a saga tick and reversibility
verdict per transition, invocable from both `/work` and an installable git-surface alias/hook pack,
including the front-loaded draft-PR-at-start mode. `plugins/saga/skills/work/SKILL.md` no longer
contains any raw ceremony git/gh commands, and the full test/format/lint/type gate stays green.

### Acceptance criteria
- [ ] AC1 (T7-F4-1). A full ceremony run drives a throwaway branch end-to-end (commit → PR →
      merge → checkout-main → pull → branch-delete) and asserts a saga tick plus a reversibility
      verdict recorded for every transition in the table.
      Check: `uv run pytest tests/test_ship_ceremony.py -k full_ceremony_throwaway_branch` → passes.
- [ ] AC2 (T7-F4-1). Interrupting the ceremony mid-transition and re-invoking it resumes from the
      last recorded state rather than restarting or duplicating a completed transition (e.g. does
      not re-open a second PR).
      Check: `uv run pytest tests/test_ship_ceremony.py -k resume_from_state` → passes.
- [ ] AC3 (H-F3-6). The ceremony is callable from an installable git alias/hook entry point,
      independent of the `/work` skill, with matching install/uninstall tooling that leaves no
      residue when uninstalled.
      Check: `uv run pytest tests/test_ship_ceremony.py -k git_surface_entry_point` → passes.
- [ ] AC4 (H-F3-6). Triggering the ceremony from the git-surface entry point on a real throwaway
      branch produces the same board-move / cleanup / saga-close effects as triggering it from
      `/work`.
      Check: `uv run pytest tests/test_ship_ceremony.py -k parity_git_surface_vs_work` → passes.
- [ ] AC5 (H-F2-3). A front-loaded mode invoked at `/work` start mints a branch, pushes a scaffold
      commit, and opens a draft PR carrying the plan link; the ceremony's later "ship" transitions
      operate against that existing draft PR (flip-to-ready) rather than opening a new one.
      Check: `uv run pytest tests/test_ship_ceremony.py -k front_loaded_draft_pr` → passes.
- [ ] AC6. `plugins/saga/skills/work/SKILL.md` contains no remaining raw ceremony git/gh commands —
      grep for `git checkout`, `git pull`, `git branch -d`, and inline `gh pr create`/`gh pr merge`
      outside of `ship_ceremony.py`'s own implementation returns no hits in the skill doc.
      Check: `grep -nE "git (checkout|pull|branch -d)|gh pr (create|merge)" plugins/saga/skills/work/SKILL.md` → no output (exit 1 from grep, i.e. no matches).
- [ ] AC7. Full suite, format, lint, types stay green.
      Check: `uv run pytest && uv run ruff format --check . && uv run ruff check . && uv run mypy plugins/ scripts/ tests/ --ignore-missing-imports` → all pass.

### Out-of-scope / non-goals
**In scope**: `plugins/saga/scripts/ship_ceremony.py` (state machine, transition table,
resume-from-state, reversibility verdicts); rewiring `plugins/saga/skills/work/SKILL.md` section 5.4
to invoke it instead of raw git/gh commands; a git alias/hook install/uninstall pack that exposes the
same primitive from the terminal; the front-loaded draft-PR-at-start mode.

**Out of scope / non-goals**:
- Changing who authorizes merge/PR-open/review-request — those remain explicitly operator-confirmed;
  this issue automates sequencing and bookkeeping only, not authorization (preserves `/work`'s
  existing "never silently mutate GitHub" boundary, `plugins/saga/skills/work/SKILL.md` section 5.5).
- `/qa`'s post-merge advisory routing and `lifecycle_phase` advancement — unchanged; `/work`
  continues to not own deploy or issue-filing (`plugins/saga/skills/work/SKILL.md` section 5.5).
- Deploy/canary mutation — owned by the `deploy` plugin, not touched here.
- Any new consensus/review protocol — this is a mechanical sequencing primitive, not a review-gate
  change; the existing P0/P1 + staleness gate ahead of PR-ready is unchanged.
- Backfilling the ceremony into repos other than `infiquetra-claude-plugins` — the 8-repo finding is
  the motivating evidence, not an execution scope; this issue ships the primitive here first.

## Grounding References

- `T7-F4-1` — primary — `docs/plans/plugin-fleet-ideation-2026-07-03/survivors/T7.json`
  (`dod_sketch`: merged `plugins/saga/scripts/ship_ceremony.py` state machine + transition table +
  throwaway-branch test asserting per-transition saga tick + reversibility verdict, `work/SKILL.md`
  no longer emitting raw checkout/pull/branch-delete).
- `H-F3-6` — facet — same file — ownership-boundary axis: ceremony lives on the git surface
  (terminal), not only the conversation; callable from both a slash command and an installable git
  alias/hook pack with install/uninstall tooling; the 8-repo finding read as an adoption verdict.
- `H-F2-3` — facet — same file — removal axis: ceremony moved to time zero (branch + draft PR minted
  at `/work` start) so ship becomes a flip-to-ready rather than a fresh ritual; distinct from
  T7-F4-1 by inverting *when* the ceremony runs, not merging into it as a single transition table.
- Session-mining synthesis, "manual ship ceremony" ranked #1 recurring pain by repo spread (8 repos):
  `docs/plans/2026-07-03-plugin-fleet-grounding-brief.md:119-121`.
- Final theme roster, theme 7 "Lifecycle auto-progression & ship ceremony (8-repo manual ritual;
  stacked-PR gaps)": `docs/plans/2026-07-03-plugin-fleet-grounding-brief.md:169`.
- Current implementation this issue replaces: `/work` section 5.4 hand-driving `gh pr create` +
  reviewer request (`plugins/saga/skills/work/SKILL.md:445`) and confirmed `gh pr merge`
  (`plugins/saga/skills/work/SKILL.md:452`), with no state machine or cleanup step present today.
- Binding decision constraining consolidation: `{#plugin-portfolio-groom-17-to-7}` — plugin sprawl is
  an active concern, new-primitive ideas carry consolidation burden proof
  (`docs/plans/2026-07-03-plugin-fleet-grounding-brief.md:52`) — satisfied here by folding three
  absorbed facets (T7-F4-1, H-F3-6, H-F2-3) into one primitive rather than three.
- Binding decision on gated authority: `{#external-engines-never-gatekeepers}` (#283) and
  `{#operator-choice-framework}` — merge/PR-open/review-request in the ceremony remain
  operator-confirmed, consistent with Claude-as-verifier-of-record and doc-only operator-choice
  conventions (`docs/plans/2026-07-03-plugin-fleet-grounding-brief.md:45`, `:49`).

### Recommended Executor Profile

- Model: sonnet
- Effort: high — *target posture: not a live team-execution dispatch knob until `pf-effort-first-class` lands; teammates inherit session tier until then*
- Backend: team-execution
- **External-LLM posture**: none
- **Justification**: Multi-file core primitive touching saga scripts (`ship_ceremony.py`, new module)
  plus skill documentation (`work/SKILL.md` section 5.4 rewrite) plus a new install/uninstall git
  alias/hook pack — cross-cutting enough to be consensus-worthy via team-execution's reviewer
  fan-out, but a well-scoped mechanical state-machine build that does not require opus-tier judgment
  or an external-engine worker slot (no exception to the sonnet default is being claimed).

### Release-Surface Checklist

This issue changes plugin behavior (new script, new skill-invoked flow, removed raw commands from
`work/SKILL.md`) and therefore requires, in the same PR:

- [ ] `plugins/saga/.claude-plugin/plugin.json` — version bump reflecting the new
      `ship_ceremony.py` capability (current: `0.51.0`).
- [ ] `.claude-plugin/marketplace.json` — matching version bump for the `saga` entry
      (current: `0.51.0`, `.claude-plugin/marketplace.json:86`).
- [ ] `plugins/saga/CHANGELOG.md` — new dated entry describing the ship-ceremony primitive, its
      entry points, and the `work/SKILL.md` command removal, following the existing entry format
      (`plugins/saga/CHANGELOG.md:1-20`).
- [ ] Version/metadata drift-guard tests — confirm any existing plugin-metadata consistency test
      (e.g. a marketplace/plugin.json version-match test under `tests/`) is updated or still passes
      against the bumped version.
- [ ] `plugins/saga/skills/work/SKILL.md` — section 5.4 and its reference-file pointers
      (`references/pr-continuation-loop.md`) updated to describe the new ceremony invocation instead
      of raw commands.

### Tests to Add or Update

- `tests/test_ship_ceremony.py` (new) — full-ceremony throwaway-branch pass, resume-from-state,
  git-surface entry-point parity, front-loaded draft-PR mode, reversibility-verdict recording.
- Existing `/work` or saga skill-doc drift-guard tests (if any) — update fixtures/assertions to
  reflect the removed raw git/gh commands in `work/SKILL.md`.

### Verification

```bash
# New primitive's own test suite
uv run pytest tests/test_ship_ceremony.py -v

# Full-repo gate (CI parity)
uv run pytest && uv run ruff format --check . && uv run ruff check . && uv run mypy plugins/ scripts/ tests/ --ignore-missing-imports

# Confirm no raw ceremony commands remain in work/SKILL.md
grep -nE "git (checkout|pull|branch -d)|gh pr (create|merge)" plugins/saga/skills/work/SKILL.md
```

Expected: all green; the final grep returns no matches (exit 1) inside `work/SKILL.md`.

### Handoff maturity
requirements-ready

### Suggested next action
Use `/plan <issue>` to create an implementation plan.

### Source context
- Source: docs/plans/plugin-fleet-ideation-2026-07-03/survivors/T7.json (ids T7-F4-1, H-F3-6, H-F2-3)
- Source type: ideation survivor set (issue-map-final.json entry `pf-ship-ceremony-primitive`)
- Source title: ship_ceremony.py — one composable, resumable guarded ship primitive replacing the 8-repo manual ritual

### Context library links

_none_

### Files expected to change

- `plugins/saga/skills/work/SKILL.md`
- `plugins/saga/scripts/ship_ceremony.py`
- `docs/plans/plugin-fleet-ideation-2026-07-03/survivors/T7.json`
- `plugins/saga/scripts/lifecycle_state.py`
- `work/SKILL.md`
- `plugins/saga/.claude-plugin/plugin.json`
- `.claude-plugin/marketplace.json`
- `plugins/saga/CHANGELOG.md`

### Tests to add or update

- `tests/test_ship_ceremony.py`

## Created Issue

- URL: https://github.com/infiquetra/infiquetra-claude-plugins/issues/345
- Number: 345
- Created at: 2026-07-04T07:44:49.177129+00:00

