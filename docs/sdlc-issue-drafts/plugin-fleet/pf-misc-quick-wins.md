---
title: "enhancement: misc quick wins — resume relevance ranking, scaffold gitignore, headless AWS SSO recommendation"
repo: infiquetra-claude-plugins
type: enhancement
team: campps
project: operations
status: Idea
labels: enhancement, hermes-task, needs-plan
risk: low
handoff_maturity: requirements-ready
tier: quick-win
objective: "Expand saga+deploy capability breadth (misc/quick-wins)"
wave: wave-3
---

# enhancement: misc quick wins — resume relevance ranking, scaffold gitignore, headless AWS SSO recommendation

### Objective

Expand saga+deploy capability breadth (misc/quick-wins).

### Intent

Land three small, independent, low-blast-radius quick wins in one batch: (1) `/resume` Tier 2
ranks candidate sessions by relevance instead of recency alone, (2) `create-plugin.sh`-scaffolded
plugin repos gitignore the saga scratch directory out of the box, and (3) a decision doc records
how background/scheduled automation obtains AWS credentials without an interactive SSO login step.
Each facet ships independently and is independently verifiable; none blocks the others.

## Problem / Motivation

**Facet 1 — resume relevance ranking (absorbed idea `S-6`).** `/resume` Tier 2's candidate-session
discovery is recency-only by design today: `discover_sessions.py` "finds this repo's session
files, **recency-ranks** them, **caps at 5**" with "no keyword or branch ranking (that is queued...)"
(`plugins/saga/skills/resume/references/session-forensics.md:19-37`). The deferral is recorded as
a QUEUED item: `docs/engineering-journal/QUEUED.md:50-57`, `{#resume-session-relevance-ranking}`,
which explicitly cites CE `ce-sessions`' `extract-metadata.py` keyword/branch relevance scoring as
the port target, deferred because "it adds value only when candidate count is high enough that
recency mis-ranks." On a repo with several stale threads, recency-only sort can surface an
unrelated recent session ahead of the actual owning thread, forcing the operator to scroll past
noise — exactly the failure mode the QUEUED item names as the trigger to revisit.

**Facet 2 — scaffold gitignore hygiene (absorbed idea `S-11`).** `tools/create-plugin.sh` scaffolds
`.claude-plugin`, `src`, `tests`, `docs` directories and a `plugin.json` (`tools/create-plugin.sh:73`
onward) but never writes or touches a `.gitignore` for the new plugin directory, and the repo-root
`.gitignore` only ignores the durable `.saga-worktrees/` outcome-orchestrator path — it has no entry
for the saga scratch directory used during per-repo saga runs. The grounding brief's recurring-pain
scan independently surfaces this as a cross-repo pattern: "saga scratch dir not gitignored in
scaffolded repos (4 repos)" (`docs/plans/2026-07-03-plugin-fleet-grounding-brief.md:131`, also
listed at `:184` as a direct-to-candidate seed). A freshly scaffolded plugin repo today risks
accidentally committing scratch-dir contents until an operator notices and patches `.gitignore`
by hand.

**Facet 3 — headless AWS SSO recommendation (absorbed idea `S-16`).** AWS SSO's interactive-login
requirement is flagged as "a structural background-automation constraint"
(`docs/plans/2026-07-03-plugin-fleet-grounding-brief.md:149-150`, echoed in the singleton scan at
section 7) — background or scheduled automation (e.g. a `deploy` plugin cron run, or a saga
`/loop` tick) that needs AWS credentials has no documented path today that avoids a human
completing an interactive SSO browser flow. There is currently no recommendation doc or mechanism
in the repo describing how headless/background runs should obtain AWS credentials; the gap is
recorded only as an unresolved constraint in the grounding brief, not yet actioned.

All three facets were absorbed together into this single quick-win issue by the ideation
consolidation pass (`consolidation_rationale`, issue-map partition) precisely because each is a
narrow, independently shippable increment with no shared code path — batching them avoids issue
sprawl for genuinely small fixes without conflating their acceptance criteria.

## Definition of Done

- `/resume` Tier 2 candidate-session discovery ranks candidates by relevance (keyword/branch
  overlap against the current ask, ported from CE `ce-sessions`' `extract-metadata.py` scoring
  approach per `{#resume-session-relevance-ranking}`), not recency alone, and the ranking is
  fixture-asserted: on a multi-thread fixture with a deliberately-older-but-more-relevant session
  among deliberately-newer-but-irrelevant ones, the correct owning thread ranks first.
- `tools/create-plugin.sh` (or its generated scaffold output) writes a `.gitignore` entry (or a
  per-plugin `.gitignore` file) covering the saga scratch directory, and a freshly scaffolded repo
  passes `git check-ignore` against that path.
- A decision doc (`docs/engineering-journal/DECISIONS.md` entry, following the repo's existing
  journal convention) records the recommended mechanism for background/scheduled automation to
  obtain AWS credentials without an interactive SSO step (e.g. a headless credential profile,
  cached token refresh, or pre-auth gate), including rejected alternatives and a revisit-when
  condition — or, if a headless mechanism is actually wired up as part of this issue, a background
  run demonstrably authenticates without a human login step.

### Acceptance criteria
- [ ] **AC1 (S-6 — relevance ranking surfaces the right thread).** Given a fixture with at least
      three candidate session skeletons where the most-relevant session (by keyword/branch overlap
      with the ask) is not the most recent, `/resume` Tier 2's ranked candidate list surfaces the
      correct owning thread first. Check: a new fixture-based test (e.g.
      `tests/test_discover_sessions.py -k relevance_ranking`) constructs this scenario and asserts
      the ranked-first candidate is the fixture's designated "correct" one, not the newest one.
- [ ] **AC2 (S-6 — recency-only path preserved as fallback/tie-break).** When no candidate has a
      distinguishing keyword/branch signal (all scores tie), ranking falls back to recency, so the
      existing MVP behavior for the common case (`session-forensics.md:34`: "no signal" → narrow
      window) is not regressed. Check: a fixture with no keyword/branch differentiation asserts
      the ranked order matches today's recency-only order.
- [ ] **AC3 (S-11 — scaffolded repo gitignores scratch dir).** Running
      `./tools/create-plugin.sh <test-plugin-id> "<Test Plugin>"` against a scratch checkout
      produces a repo where the saga scratch path is git-ignored. Check:
      `git check-ignore <scratch-dir-path>` exits `0` (path is ignored) inside the freshly
      scaffolded output.
- [ ] **AC4 (S-11 — existing scaffolds unaffected).** The change to `create-plugin.sh` /
      `.gitignore` templating does not alter the existing generated `plugin.json`, directory
      layout, or any other scaffold output byte-for-byte apart from the new gitignore entry.
      Check: `git diff` against a scaffold run before/after the change shows only gitignore-related
      lines added.
- [ ] **AC5 (S-16 — headless credential path documented or demonstrated).** Either (a) a background
      automation run (e.g. a `deploy` plugin dry-run invoked non-interactively) authenticates to
      AWS without prompting for an interactive SSO login, or (b) `docs/engineering-journal/
      DECISIONS.md` carries a new dated entry naming the chosen mechanism, the rejected
      alternatives considered, and an explicit revisit-when condition. Check: `grep -n
      "aws-sso-headless\|background-automation-aws-creds"
      docs/engineering-journal/DECISIONS.md` finds the new entry (if going the doc route), or the
      background run's transcript/log shows a completed AWS API call with no interactive-login
      prompt (if going the mechanism route).
- [ ] **AC6 (release-surface parity for facets that change plugin behavior).** For facet 1 (resume
      ranking) and facet 2 (scaffold gitignore), since both change existing plugin/tool behavior,
      the corresponding `plugins/saga/.claude-plugin/plugin.json` version bump, `.claude-plugin/
      marketplace.json` entry, and `plugins/saga/CHANGELOG.md` entry are updated in the same PR.
      Check: `git diff --name-only origin/main...HEAD` includes
      `plugins/saga/.claude-plugin/plugin.json`, `.claude-plugin/marketplace.json`, and
      `plugins/saga/CHANGELOG.md` alongside the `discover_sessions.py` / `create-plugin.sh` diffs.

### Out-of-scope / non-goals
**In scope:**
- Porting keyword/branch relevance scoring into `discover_sessions.py`'s Tier 2 candidate ranking,
  scoped to the already-extracted skeletons (never raw session JSONL) per the existing
  context-safety contract (`session-forensics.md:39-49`).
- Adding a scratch-dir `.gitignore` entry to the plugin scaffold template used by
  `tools/create-plugin.sh`.
- Writing (or actioning) the AWS SSO headless-credential recommendation for background automation.

**Non-goals (explicitly out of scope for this issue):**
- Any change to Tier 1 (saga-anchored) resume behavior — this issue touches Tier 2 (no-saga
  fallback) candidate discovery only, per the existing Tier 1/Tier 2 boundary
  (`session-forensics.md:3`).
- Standing up a scheduled/repeating relevance-ranking calibration harness — this ships the ranking
  once, fixture-verified; no ongoing measurement loop (matching the grounding brief's rejection of
  standing-ceremony measurement shapes elsewhere, section 4).
- Retrofitting `.gitignore` into already-scaffolded plugin repos in this monorepo — this issue only
  fixes the template so future scaffolds are correct; a separate follow-up would sweep existing
  plugin directories if desired.
- Building new AWS credential infrastructure (a new secrets vault, a new IAM role) beyond what's
  needed to demonstrate or document the headless path — if the decision doc route is taken, no
  code changes are required for this facet at all.
- Any change to `deploy` plugin's tag-promotion policy, canary, or rollback behavior — the AWS SSO
  facet is about how automation *authenticates*, not what it does once authenticated.

## Grounding References

- **Absorbed idea `S-6`** — "Resume session relevance ranking" (`basis`: QUEUED anchor
  `{#resume-session-relevance-ranking}` per `docs/plans/2026-07-03-plugin-fleet-grounding-brief.md`
  section 5; `docs/plans/plugin-fleet-ideation-2026-07-03/survivors/seeds.json`). Full QUEUED entry:
  `docs/engineering-journal/QUEUED.md:50-57` ("Port CE keyword/branch relevance ranking into
  `/resume` Tier 2"), naming CE `ce-sessions`' `extract-metadata.py` as the engine source and the
  ">5 candidate sessions and recency mis-ranks" condition as when it becomes worth building.
- **Absorbed idea `S-11`** — "Gitignore saga scratch dir in scaffolded repos" (`basis`: brief
  section 8 direct-to-candidate "scratch-dir"; section 5 pattern 5, "4 repos: saga scratch dir not
  gitignored" — `docs/plans/2026-07-03-plugin-fleet-grounding-brief.md:131,184`;
  `docs/plans/plugin-fleet-ideation-2026-07-03/survivors/seeds.json`).
- **Absorbed idea `S-16`** — "AWS SSO interactive-login constraint for background automation"
  (`basis`: brief section 8 direct-to-candidate "AWS SSO"; section 7 singleton "AWS SSO
  interactive login as a structural background-automation constraint" —
  `docs/plans/2026-07-03-plugin-fleet-grounding-brief.md:149-150,184`;
  `docs/plans/plugin-fleet-ideation-2026-07-03/survivors/seeds.json`).
- **Existing Tier 2 discovery contract this issue extends:**
  `plugins/saga/skills/resume/references/session-forensics.md:19-37` (recency-only MVP, explicit
  "queued" deferral note), `:39-58` (context-safety contract that any ranking addition must
  preserve — paths and skeletons only, never raw session content).
- **Existing scaffold this issue extends:** `tools/create-plugin.sh:73` onward (directory + manifest
  generation, no `.gitignore` step today).
- **No binding decision in the register (`docs/plans/2026-07-03-plugin-fleet-grounding-brief.md`
  section 2) directly constrains any of these three facets** — all are additive, backward-compatible
  changes to existing tooling, not new architecture.
- **Objective + wave placement:** `objective: "Expand saga+deploy capability breadth
  (misc/quick-wins)"`, `wave: wave-3`, `tier: quick-win` per the issue-map consolidation
  (`issue-map-final.json`, slug `pf-misc-quick-wins`).

## Recommended Executor Profile

- **Model:** sonnet
- **Effort:** low
- **Backend:** inline
- **External-LLM posture:** none
- **Justification:** all three facets are mechanical, bounded changes against existing, already-
  documented contracts (a ranking function over already-extracted skeletons, a template-file
  addition, a decision-doc write-up) with no architectural ambiguity to reason through — sonnet at
  low effort is sufficient and matches the issue's `quick-win` tier. No case for opus or elevated
  effort.

## Release-Surface Checklist

- [ ] `plugins/saga/.claude-plugin/plugin.json` — version bump for the `/resume` Tier 2 ranking
      behavior change (facet 1).
- [ ] `.claude-plugin/marketplace.json` — synced entry for `saga` if its version changes.
- [ ] `plugins/saga/CHANGELOG.md` — dated entry describing the Tier 2 relevance-ranking addition.
- [ ] Drift-guard tests (whatever test asserts plugin.json/marketplace.json/CHANGELOG version
      parity in this repo's CI) pass with the new version.
- [ ] Facet 2 (`tools/create-plugin.sh`) is a repo-root tool, not a versioned plugin — no
      plugin.json/marketplace.json/CHANGELOG entry required for it, but confirm during `/plan`
      whether the scaffold template lives under a plugin's own `plugin.json` version surface (if
      so, apply the same checklist there).
- [ ] Facet 3 (AWS SSO decision doc) makes no plugin behavior change unless the mechanism route is
      chosen and touches `deploy` plugin code — if so, apply the same checklist to
      `plugins/deploy/.claude-plugin/plugin.json`, `.claude-plugin/marketplace.json`, and
      `plugins/deploy/CHANGELOG.md`.

## Files Expected to Change

Indicative only; exact set for `/plan` to determine.

- `plugins/saga/scripts/discover_sessions.py` — add keyword/branch relevance scoring to candidate
  ranking.
- `plugins/saga/skills/resume/references/session-forensics.md` — update the "MVP — recency only"
  section to describe the new ranking behavior.
- `tests/test_discover_sessions.py` — new fixture-based relevance-ranking tests.
- `tools/create-plugin.sh` — add `.gitignore` scaffolding for the saga scratch directory.
- `docs/engineering-journal/DECISIONS.md` — new dated entry for the AWS SSO headless-credential
  recommendation (or `plugins/deploy/` code, if the mechanism route is chosen).
- `plugins/saga/.claude-plugin/plugin.json`, `.claude-plugin/marketplace.json`,
  `plugins/saga/CHANGELOG.md` — release-surface updates for the resume ranking change.

### Verification
```bash
# Facet 1: relevance ranking fixture test
uv run pytest tests/test_discover_sessions.py -k relevance_ranking -v
# Expected: passes; ranked-first candidate matches the fixture's designated correct thread

# Facet 1: recency fallback preserved
uv run pytest tests/test_discover_sessions.py -k recency_fallback -v
# Expected: passes; tied-relevance fixture preserves today's recency order

# Facet 2: scaffolded repo gitignores the scratch path
./tools/create-plugin.sh quick-win-test "Quick Win Test" && \
  git -C plugins/quick-win-test check-ignore <scratch-dir-path>
# Expected: exit 0 (path is ignored)

# Facet 3a (doc route): decision entry present
grep -n "aws-sso-headless\|background-automation-aws-creds" docs/engineering-journal/DECISIONS.md
# Expected: at least one match

# Full repo gate (CI parity)
uv run pytest && uv run ruff format --check . && uv run ruff check . && uv run mypy plugins/ scripts/ tests/ --ignore-missing-imports
```

Expected: all checks pass; each facet's acceptance criterion is independently verifiable without
depending on the other two facets landing first.

### Handoff maturity

requirements-ready

### Suggested next action

Use `/plan <issue>` to create an implementation plan sequencing the three independent facets
(resume ranking, scaffold gitignore, AWS SSO recommendation) as separable units of work within one
plan.

### Source context

- Source: `docs/plans/plugin-fleet-ideation-2026-07-03/survivors/seeds.json` (ideas `S-6`, `S-11`,
  `S-16`)
- Source type: ideation survivor (issue-map)
- Source title: Misc quick wins: resume relevance ranking, scaffold gitignore for saga scratch,
  headless AWS SSO recommendation

### Context library links

_none_

### Files expected to change

- `tools/create-plugin.sh`
- `docs/engineering-journal/DECISIONS.md`
- `plugins/saga/.claude-plugin/plugin.json`
- `plugins/saga/CHANGELOG.md`
- `.claude-plugin/marketplace.json`
- `docs/plans/2026-07-03-plugin-fleet-grounding-brief.md`
- `docs/plans/plugin-fleet-ideation-2026-07-03/survivors/seeds.json`
- `plugins/deploy/.claude-plugin/plugin.json`

### Tests to add or update

- `tests/test_discover_sessions.py`

## Created Issue

- URL: https://github.com/infiquetra/infiquetra-claude-plugins/issues/436
- Number: 436
- Created at: 2026-07-04T08:13:07.481056+00:00

