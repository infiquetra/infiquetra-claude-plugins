---
title: exploration: one-time comprehensive fleet code-review campaign with a risk-tiered scope manifest
repo: infiquetra-claude-plugins
type: exploration
team: campps
project: operations
status: Idea
labels: exploration, hermes-task, needs-plan
risk: medium
handoff_maturity: requirements-ready
objective: Gate fleet integrity (agent files, prompts, release surfaces)
tier: structural
wave: wave-2
---

# exploration: one-time comprehensive fleet code-review campaign with a risk-tiered scope manifest

### Objective
Gate fleet integrity (agent files, prompts, release surfaces)

### Tier
structural

### Wave
wave-2

### Intent
Run a single, one-time comprehensive code-review campaign across all 8 plugins in this repo
(`plugins/agy`, `plugins/deploy`, `plugins/home-lab-ops`, `plugins/mission-control`,
`plugins/redis-channel`, `plugins/saga`, `plugins/team-execution`, `plugins/unifi` —
`docs/plans/2026-07-03-plugin-fleet-grounding-brief.md:10-12`), scoped by a new risk-tiered
review manifest rather than uniform blanket coverage, and executed as concurrency-batched
sub-issues (≤3 files per batch) under sandboxed review spawns.

This issue is the **planning deliverable**: it produces (a) the campaign spec, (b) the
fleet-review manifest, and (c) a tracking Objective that fans out the actual per-batch review
work as its own sub-issues. It does not itself perform the review passes — those are executed
by the sub-issues the tracking Objective creates.

**Why now.** The operator has directly asked for a "full comprehensive code-review" beyond
normal diff-scoped review (survivor `S-36`, basis: "operator statement 'full comprehensive
code-review'" — `docs/plans/plugin-fleet-ideation-2026-07-03/survivors/seeds.json`). This repo's
own grounding pass independently surfaced the same gap as theme 11 of the final theme roster —
"Fleet quality: comprehensive code review + agent-prompt audit + local-vs-CI parity +
release-surface drift automation" (`docs/plans/2026-07-03-plugin-fleet-grounding-brief.md:153`,
theme 11 line) — meaning the ask and the independently-observed pain converge on the same gap:
there is no standing or one-time mechanism that reviews the fleet's 106 non-test Python files
(`find plugins -name "*.py"` excluding tests, verified 2026-07-04) and every agent-prompt file
outside the normal per-PR diff-scoped `saga:code-review` pass. `saga:code-review` today only
reads the merge-base diff (see its skill description: "Reads the merge-base diff... without
mutating code") — there is no fleet-wide sweep.

Two prior facets consolidate into this single planning issue rather than shipping as separate
work:

- **`T11-F1-3`** — "One-time comprehensive fleet code-review campaign, concurrency-batched"
  (`docs/plans/plugin-fleet-ideation-2026-07-03/survivors/T11.json`, `dod_sketch`: "Merged
  docs/plans campaign spec + tracking Objective with <=3-file sub-issue batches, each spawning
  saga:readonly-verifier under worktree isolation; verified spec enumerates every *.py path
  cross-checked against find."). This is the keeper facet and absorbs `S-36` per the dedup map
  (`consolidation_rationale` in the issue map: "Keeper T11-F1-3 subsumes seed S-36 per
  dedup-map").
- **`T11-F6-6`** — "Fleet code-review manifest: risk-tiered scope instead of uniform coverage"
  (`docs/plans/plugin-fleet-ideation-2026-07-03/survivors/T11.json`, `dod_sketch`: "Merged
  docs/reviews/fleet-review-manifest (plugin -> {paths, risk_tier, review_lenses}) consumed by
  saga:code-review scope selection + first campaign's triaged findings; verified the review
  reads the manifest and produces a per-plugin scoped pass.").

The campaign spec and the manifest are treated as one planning deliverable because the campaign
cannot be scoped without the manifest that tells it which plugins/paths need which review
lenses at which depth — building them separately would leave the campaign spec unable to name
its own scope. Execution (the actual review passes) fans out as its own sub-issues once this
plan exists.

## Grounding References
- `{#readonly-verifier-fallback-ladder-325}` + `{#verify-agent-git-checkout-clobber}`
  (`docs/plans/2026-07-03-plugin-fleet-grounding-brief.md:50`) — verify-class spawns must use
  the read-only verifier profile plus worktree isolation, with the documented Explore-first
  fallback ladder when `saga:readonly-verifier` is unavailable. This repo's own root CLAUDE.md
  restates the same rule and points to
  `plugins/saga/references/sandbox-spawn-sites.md` for the full spawn-site inventory and the
  fallback ladder.
- `{#external-engines-never-gatekeepers}` (#283) — Claude remains verifier-of-record for every
  gated decision the campaign produces (findings triage, batch pass/fail); any external-engine
  (codex/agy) participation in review batches is advisory-only, never a gate.
- `{#plugin-portfolio-groom-17-to-7}` — plugin sprawl is an active concern; the campaign spec and
  manifest must enumerate the existing 8-plugin fleet map, not invent new plugins.

### Out-of-scope / non-goals
- **This issue does not execute any review batch.** It produces the spec, the manifest, and the
  tracking Objective. The ≤3-file review batches are separate sub-issues spawned by that
  Objective, each independently scoped, reviewed, and merged.
- **No standing/recurring review cadence.** This is explicitly a one-time campaign
  (`T11-F1-3` title: "One-time comprehensive fleet code-review campaign"), not a scheduled or
  cron-driven review loop. A recurring cadence is a distinct future idea, not this issue's scope.
- **No new review tooling or lens beyond what `saga:code-review` already runs.** The manifest
  selects among existing review lenses (architecture, security, simplification, etc.) per
  plugin/path; it does not invent new lens types in this issue.
- **No agent-prompt rewriting.** The campaign audits agent-prompt files as part of its scope
  (per Objective title "Gate fleet integrity (agent files, prompts, release surfaces)") but does
  not itself rewrite any agent prompt — findings route to separate fix sub-issues.
- **No change to `saga:code-review`'s core diff-scoped behavior for ordinary PRs.** The manifest
  is an additional scope-selection input the campaign consumes; it does not replace or gate
  normal per-PR review.

### Files expected to change
Indicative only — the exact set is `/plan`'s to determine.
- `docs/plans/fleet-review-campaign-spec.md` — new campaign spec: enumerates the ≤3-file batch
  plan, the sandboxing requirement per batch (`saga:readonly-verifier` + worktree isolation, or
  the documented fallback ladder), and the tracking-Objective wiring.
- `docs/reviews/fleet-review-manifest.md` (or `.json`) — new manifest: `plugin -> {paths,
  risk_tier, review_lenses}` for all 8 plugins, cross-checked against `find plugins -name
  "*.py"` and every `agents/*.md` file across the fleet.
- `plugins/saga/skills/code-review/SKILL.md` — scope-selection hook so a fleet-review batch can
  consume the manifest instead of only the merge-base diff (exact mechanism left to `/plan`).
- `tests/test_fleet_review_manifest.py` (or equivalent drift-guard test) — asserts the manifest's
  path list matches a live `find` over `plugins/**/*.py` and `plugins/**/agents/*.md`, so the
  manifest cannot silently drift from the fleet.

### Tests to add or update
- Manifest completeness: every plugin under `plugins/` appears in the manifest with a non-empty
  `paths` list; every `*.py` file found by `find plugins -name "*.py"` (excluding test files) is
  covered by some manifest entry.
- Manifest completeness: every `agents/*.md` file across the fleet is covered by some manifest
  entry (Objective explicitly names "agent files" as in scope).
- Batch-size guard: the campaign spec's batching logic never proposes a batch with more than 3
  files.
- Sandbox-guard: every spawn site the campaign spec introduces or references is present in
  `plugins/saga/references/sandbox-spawn-sites.md`'s spawn-site inventory, or uses the documented
  fallback ladder.

## Definition of Done
- Campaign spec exists at `docs/plans/fleet-review-campaign-spec.md` enumerating the ≤3-file
  batch plan, the sandboxing requirement per batch, and the tracking-Objective wiring.
- Fleet-review manifest exists (`plugin -> {paths, risk_tier, review_lenses}`) covering all 8
  plugins, cross-checked against a live `find plugins -name "*.py"`.
- A tracking Objective is created in mission-control to hold the fan-out review-batch
  sub-issues once execution begins.
- This issue does not execute any review batch — only the spec, the manifest, and the
  Objective are produced (execution is out of scope; see Scope & Non-Goals).

### Acceptance criteria
- [ ] Campaign spec exists at `docs/plans/fleet-review-campaign-spec.md` and enumerates every
      `*.py` path in the fleet, cross-checked against a live `find plugins -name "*.py"`. Check:
      `find plugins -name "*.py" -not -path "*/test*" | wc -l` matches the count of paths the
      spec's manifest claims to cover (via the drift-guard test below) → equal.
- [ ] Fleet-review manifest exists (`docs/reviews/fleet-review-manifest.md` or `.json`) with the
      schema `plugin -> {paths, risk_tier, review_lenses}` for all 8 plugins. Check:
      `uv run pytest tests/test_fleet_review_manifest.py -k schema` → passes.
- [ ] The manifest is consumed by scope selection, not just documented — `saga:code-review` (or
      the campaign spec's execution path) reads the manifest and produces a per-plugin scoped
      pass rather than a uniform full-repo pass. Check: `uv run pytest
      tests/test_fleet_review_manifest.py -k scoped_pass` → passes.
- [ ] The campaign spec defines ≤3-file sub-issue batches, each of which spawns
      `saga:readonly-verifier` under worktree isolation (or the documented fallback ladder when
      unavailable). Check: `uv run pytest tests/test_fleet_review_manifest.py -k
      batch_size_and_sandbox` → passes.
- [ ] A tracking Objective (mission-control) is created that will hold the fan-out review-batch
      sub-issues once execution begins; the campaign spec names its identifier. Check: the spec
      file contains a `## Tracking Objective` section naming the Objective issue/URL.
- [ ] The manifest's path coverage does not silently drift from the live fleet — a drift-guard
      test fails if a new plugin or a new top-level `agents/*.md` file is added without a
      corresponding manifest entry. Check: `uv run pytest tests/test_fleet_review_manifest.py -k
      drift_guard` → passes.
- [ ] Full suite, format, lint, and types stay green. Check: `uv run pytest && uv run ruff format
      --check . && uv run ruff check . && uv run mypy plugins/ scripts/ tests/
      --ignore-missing-imports` → all pass.

### Release-surface checklist
This issue is a planning/spec deliverable and, on its own, changes no plugin's runtime behavior,
schema, command, or user-facing guidance — no `plugin.json` version bump, `marketplace.json`
entry, or `CHANGELOG.md` entry is required for *this* issue. If the `/plan` phase decides the
manifest-consumption hook in `plugins/saga/skills/code-review/SKILL.md` constitutes a behavior
change to the `saga` plugin, then the standard release-surface checklist applies to that
follow-on work and must be completed in the same PR as that change:
- [ ] `plugins/saga/.claude-plugin/plugin.json` version bump reflecting the scope-selection
      addition.
- [ ] `.claude-plugin/marketplace.json` entry kept in sync with the bumped version.
- [ ] `plugins/saga/CHANGELOG.md` entry describing the manifest-consumption hook.
- [ ] Any version/metadata drift-guard tests updated to reflect the new version.

### Recommended executor profile
- **Model:** sonnet
- **Effort:** high
- **Backend:** cc-workflows-ultracode
- **External-LLM posture:** none — per `{#external-engines-never-gatekeepers}`, Claude is
  verifier-of-record for the campaign spec and manifest; no external engine participates in this
  planning issue.
- **Justification:** sonnet/high is sufficient — this is a planning/spec-authoring exploration
  (produce a spec, a manifest, and an Objective; enumerate and cross-check file paths), not a
  judgment-heavy architectural call or an adversarial review. It does not warrant opus.

### Verification
```bash
# Manifest schema, coverage, and scoped-pass behavior
uv run pytest tests/test_fleet_review_manifest.py -v

# Confirm the manifest's claimed *.py coverage matches the live fleet
find plugins -name "*.py" -not -path "*/test*" | wc -l

# Full repo gate (CI parity)
uv run pytest && uv run ruff format --check . && uv run ruff check . && uv run mypy plugins/ scripts/ tests/ --ignore-missing-imports
```
Expected: all green; the manifest's path coverage exactly matches the live `find` enumeration
with zero uncovered `*.py` or `agents/*.md` files.

### Handoff maturity
requirements-ready

### Suggested next action
Use `/plan <issue>` to create an implementation plan for the campaign spec and manifest.

### Source context
- Source: docs/plans/plugin-fleet-ideation-2026-07-03/survivors/T11.json (ids `T11-F1-3`,
  `T11-F6-6`), docs/plans/plugin-fleet-ideation-2026-07-03/survivors/seeds.json (id `S-36`)
- Source type: ideation survivor set (thin seeds — reconstructed from `basis`/`dod_sketch` plus
  `docs/plans/2026-07-03-plugin-fleet-grounding-brief.md` sections 5-8)
- Source title: One-time comprehensive fleet code-review campaign with a risk-tiered scope manifest

### Context library links

_none_
