---
title: "enhancement: standing per-plugin review ledger + incremental changed-plugin review"
repo: infiquetra-claude-plugins
type: enhancement
team: campps
project: operations
status: Idea
labels: enhancement, hermes-task, needs-plan
risk: medium
handoff_maturity: requirements-ready
tier: structural
wave: wave-2
objective: "Gate fleet integrity (agent files, prompts, release surfaces)"
---

# enhancement: standing per-plugin review ledger + incremental changed-plugin review

### Objective

Gate fleet integrity (agent files, prompts, release surfaces)

## Summary

Today the 8-plugin fleet (`saga` 0.51.0, `team-execution` 2.9.0, `mission-control` 2.4.0, `agy`
0.1.0, `deploy` 0.1.2, `home-lab-ops` 1.2.0, `redis-channel` 0.5.0, `unifi` 1.1.0 — fleet map
`docs/plans/2026-07-03-plugin-fleet-grounding-brief.md:10-12`) has no standing review
machinery: a comprehensive fleet review is only ever a one-time heroic pass, and no PR-time
signal tells an operator "this plugin drifted N commits past its last real review" or
"only review the plugin segment this PR actually touched." This issue ships the durable
machinery two absorbed ideation facets both converge on: (1) a per-plugin **review ledger**
(last-reviewed SHA + lenses run + open findings) with a CI staleness check, and (2) a
**diff-to-segment incremental reviewer** that maps a PR's merge-base diff onto plugin
directories and invokes `saga:code-review` only on the touched segment(s). Both facets were
absorbed into one PR because they share the same files: the incremental reviewer is what
*writes* the ledger entry after a review runs, and the staleness check is what *reads* it.

## Problem Frame

- **No standing review cadence.** The only review tooling that exists today is the
  work-to-PR-boundary lens, `saga:code-review` (`plugins/saga/commands/code-review.md`,
  `plugins/saga/skills/code-review/SKILL.md`), which is invoked per-PR by `/work` and never
  by anything that looks at fleet-wide staleness. There is no artifact recording *when a
  plugin was last comprehensively reviewed* — a plugin could go arbitrarily long without a
  full-lens pass and nothing would surface it.
- **Segment boundary is already a settled convention, unused here.** The
  `{#worker-cache-scheduling}` decision (`docs/engineering-journal/DECISIONS.md:1950-1970`,
  KTD2 at `:1962`) already establishes "segment boundary = plugin directory" for a different
  subsystem (worker/cache scheduling) because this is a single monorepo and a VECU-style
  repo-change proxy never fires here. This issue reuses that same settled segment boundary
  for review scoping instead of inventing a new one.
- **Fleet-integrity concern is named but has no automation.** Theme 11 in the ideation
  roster — "Fleet quality: comprehensive code review + agent-prompt audit + local-vs-CI
  parity + release-surface drift automation" (`docs/plans/2026-07-03-plugin-fleet-ideation-2026-07-03/../2026-07-03-plugin-fleet-grounding-brief.md:174-175`)
  — names this gap directly; this issue is theme 11's structural build for the review-ledger
  half of that theme.
- **Existing CI has no plugin-scoped review gate.** `.github/workflows/ci.yml` runs a
  fixed set of repo-wide steps (Issue-contract vendored-parity check at `ci.yml:29-35`,
  pytest with coverage at `:37-38`, `validate` job at `:44` onward) — there is no step that
  looks at which plugin directories changed in a PR and reacts differently per plugin.
- **Precedent for this-repo-local guard scripts already exists.** `tools/stale_main_guard.py`
  is the existing pattern for a repo-local, non-blocking (or loud) staleness guard invoked
  from a hook or CI step — the new `check_review_staleness.py` should follow its documented
  shape (docstring-driven, explicit exit-code contract, `This-repo-local` scoping note).
- **Portfolio-groom precedent for structural-not-enumerative checks.** The
  `{#plugin-portfolio-groom-17-to-7}` decision (`docs/engineering-journal/DECISIONS.md:1031`,
  rationale at the paragraph beginning "Both validators are **structural, not
  enumerative**") sets the bar this issue's new checks must clear: the ledger and staleness
  check must work against whatever plugin directories exist, not a hardcoded plugin list,
  so the fleet can keep changing shape without a drift-guard rewrite.

## Requirements

R1. A per-plugin review ledger file (JSON, one entry per plugin directory under `plugins/`)
records at minimum: plugin name, last-reviewed commit SHA, the lens set that ran, and any
open (unresolved) findings from that pass.

R2. `scripts/check_review_staleness.py` reads the ledger, computes each plugin's commit
distance from its ledger SHA to `HEAD` (or the PR's merge-base), and fails (non-zero exit,
or a named CI annotation) when a plugin's drift exceeds a configurable threshold `N`
commits.

R3. `tools/review-changed-plugins.py` computes the merge-base diff for the current branch,
maps changed file paths to their owning `plugins/<name>/` segment (reusing the
`{#worker-cache-scheduling}` KTD2 segment-boundary convention — one plugin directory = one
segment), and invokes `saga:code-review` scoped to only the touched segment(s) — never the
whole fleet — for a PR that touches a single plugin.

R4. On a successful review invocation, the touched plugin's ledger entry is updated (SHA +
lenses + findings) so R2's staleness check reflects the new baseline.

R5. The staleness check is wired into `.github/workflows/ci.yml` as a named, non-destructive
step (following the existing named-step convention, e.g. `ci.yml:29`'s "Issue-contract
vendored parity" step) so drift is visible in the PR checks list, not just locally.

R6. Both new scripts are structural-not-enumerative in the `{#plugin-portfolio-groom-17-to-7}`
sense: they glob `plugins/*/` rather than hardcoding the 8-plugin list, so adding or
removing a plugin does not require editing these scripts.

### Acceptance criteria
- [ ] AC1 (ledger exists, R1). A per-plugin review ledger file exists, is valid JSON, and
  contains one entry per directory under `plugins/` with `last_reviewed_sha`, `lenses`, and
  `open_findings` keys. Check: `python3 -c "import json; d=json.load(open('<ledger path>')); assert set(d) == {p.name for p in __import__('pathlib').Path('plugins').iterdir() if p.is_dir()}"`.

- [ ] AC2 (staleness check reds on drift, R2 — absorbed facet T11-F3-3). A plugin whose ledger
  SHA is more than `N` commits behind `HEAD` causes `scripts/check_review_staleness.py` to
  exit non-zero and name the stale plugin(s) in its output. Check:
  `uv run pytest tests/test_check_review_staleness.py -k drift_exceeds_threshold` → passes.

- [ ] AC3 (staleness check stays green when current, R2). A plugin whose ledger SHA is within
  the threshold, or matches `HEAD` exactly, does not trip the check. Check:
  `uv run pytest tests/test_check_review_staleness.py -k drift_within_threshold` → passes.

- [ ] AC4 (incremental reviewer scopes to touched segment only, R3 — absorbed facet
  T11-F2-6). A one-plugin PR (diff touching only `plugins/<name>/**`) invokes
  `saga:code-review` against that plugin's segment only — no other plugin's files are
  passed into the review scope. Check:
  `uv run pytest tests/test_review_changed_plugins.py -k single_plugin_touches_only_that_segment` → passes.

- [ ] AC5 (multi-plugin PR reviews each touched segment, not the whole fleet, R3). A PR
  touching two plugin directories triggers exactly two scoped review invocations, not one
  fleet-wide invocation and not a skipped one. Check:
  `uv run pytest tests/test_review_changed_plugins.py -k multi_plugin_two_scoped_invocations` → passes.

- [ ] AC6 (ledger updates after a review runs, R4). After `tools/review-changed-plugins.py`
  completes a review for a touched plugin, that plugin's ledger entry's
  `last_reviewed_sha` advances to the reviewed commit. Check:
  `uv run pytest tests/test_review_changed_plugins.py -k ledger_updated_after_review` → passes.

- [ ] AC7 (CI wiring, R5). `.github/workflows/ci.yml` contains a named step invoking
  `scripts/check_review_staleness.py`. Check:
  `grep -A2 "check_review_staleness" .github/workflows/ci.yml | grep -q "run:"`.

- [ ] AC8 (structural-not-enumerative, R6). Adding a fixture plugin directory under a temp
  `plugins/` tree (not one of the current 8) is picked up by both scripts without any code
  edit. Check: `uv run pytest tests/test_check_review_staleness.py -k discovers_new_plugin_directory` → passes.

- [ ] AC9 (full suite stays green). Check:
  `uv run pytest && uv run ruff format --check . && uv run ruff check . && uv run mypy plugins/ scripts/ tests/ --ignore-missing-imports`
  → all pass.

## Definition of Done

Per-plugin review ledger merged (last-reviewed SHA + lenses + open findings, one entry per
`plugins/*/`) alongside `scripts/check_review_staleness.py` and a CI step that reds when a
plugin drifts more than `N` commits past its ledger SHA. `tools/review-changed-plugins.py`
maps a merge-base diff to plugin segments, invokes `saga:code-review` scoped to only the
touched segment(s), and writes the resulting SHA/lenses/findings back into that plugin's
ledger entry. All of AC1–AC9 pass.

### Out-of-scope / non-goals
In scope:
- The review-ledger data file/format, its staleness checker, and the diff-to-segment
  incremental reviewer script, plus their CI wiring and tests.

Out of scope / non-goals:
- Redefining what `saga:code-review`'s lenses do, or changing its findings schema
  (`plugins/saga/skills/code-review/references/findings-schema.md`) — this issue only adds a
  caller and a ledger-writer around the existing lens engine, it does not modify the lenses.
- A fleet-wide one-time comprehensive review campaign — that was the seed this ledger
  absorbs the durable machinery from; running an initial baseline pass to seed the ledger's
  first entries is a follow-up operational task, not part of this PR's acceptance criteria.
- Agent-prompt audit and local-vs-CI parity automation (the other two facets named under
  theme 11) — tracked separately; this issue is scoped to the review-ledger + incremental
  reviewer pair only.
- Changing the segment-boundary convention itself (plugin directory) — this issue reuses
  the settled `{#worker-cache-scheduling}` KTD2 boundary as-is.
- Any change to `saga:code-review`'s invocation contract from `/work` — that call site is
  unaffected; this issue adds a second, independent caller (the incremental-reviewer
  script), not a replacement for the existing per-PR gate.

## Grounding References

- Absorbed idea `T11-F3-3` — "A comprehensive review is not one heroic pass — segment the
  fleet into a standing review ledger"
  (`docs/plans/plugin-fleet-ideation-2026-07-03/survivors/T11.json`). DoD sketch: merged
  per-plugin review-ledger (last-reviewed SHA + lenses + findings) +
  `scripts/check_review_staleness.py` + CI step; verified the check goes red when a plugin
  drifts N commits past its ledger SHA. Basis: theme 11 ("Fleet quality...") in the final
  theme roster, `docs/plans/2026-07-03-plugin-fleet-grounding-brief.md:174-175`.
- Absorbed idea `T11-F2-6` — "Incremental changed-plugin review: remove the 'when do we
  review the whole fleet' decision"
  (`docs/plans/plugin-fleet-ideation-2026-07-03/survivors/T11.json`). DoD sketch: merged
  `tools/review-changed-plugins.py` mapping a merge-base diff to plugin segments and
  invoking `saga:code-review` per segment into a per-plugin ledger; verified a one-plugin
  PR reviews only that segment. Basis: same theme 11 roster entry; the segment-boundary
  reuse is grounded in `{#worker-cache-scheduling}` KTD2
  (`docs/engineering-journal/DECISIONS.md:1962`).
- Binding decision `{#worker-cache-scheduling}` (`docs/engineering-journal/DECISIONS.md:1950-1970`)
  — segment boundary = plugin directory (KTD2); this issue's incremental reviewer must use
  the same boundary, not invent a new one.
- Binding decision `{#plugin-portfolio-groom-17-to-7}` (`docs/engineering-journal/DECISIONS.md:1031`)
  — structural-not-enumerative validator convention; both new scripts must glob `plugins/*/`
  rather than hardcode plugin names.
- Consolidation rationale (issue-map): "The ledger (last-reviewed SHA, staleness check) and
  the diff-to-segment incremental reviewer are the durable machinery the one-time campaign
  seeds; same files, one PR" — recorded in
  `issue-map-final.json` under slug `pf-review-ledger-incremental`.

## Recommended Executor Profile

- **Model:** sonnet
- **Effort:** medium
- **Backend:** inline
- **External-LLM posture:** none
- **Justification:** Mechanical scaffolding work (a JSON ledger schema, a diff-to-directory
  mapper, a CI step, and pytest coverage) following two well-established this-repo patterns
  (`tools/stale_main_guard.py`'s guard-script shape,
  `plugins/mission-control/config/generated/check_issue_contract_parity.py`'s CI-step
  shape). No architectural ambiguity or adversarial judgment call is required, so this does
  not need an above-sonnet tier; matches the absorbed ideas' own `executor_profile`
  (sonnet/medium/inline/none).

## Release-Surface Checklist

This issue does not change any existing plugin's user-facing behavior, schema, command, or
prompt — it adds new repo-root tooling (`scripts/check_review_staleness.py`,
`tools/review-changed-plugins.py`) and a CI step. No `plugin.json`, `marketplace.json`, or
plugin `CHANGELOG.md` update is required by this issue as scoped. If a future iteration
promotes the incremental reviewer into a `saga` command or skill (e.g. a `/review-fleet`
entry point), that iteration must update at minimum:
- `plugins/saga/.claude-plugin/plugin.json` (version bump)
- `.claude-plugin/marketplace.json` (saga entry version bump)
- `plugins/saga/CHANGELOG.md` (new entry)
- any saga metadata drift-guard tests

## Files Expected to Change

- `scripts/check_review_staleness.py` (new)
- `tools/review-changed-plugins.py` (new)
- `docs/review-ledger.json` or equivalent ledger data file (new — exact path/location left
  to `/plan`)
- `.github/workflows/ci.yml` — new named step invoking the staleness check
- `tests/test_check_review_staleness.py` (new)
- `tests/test_review_changed_plugins.py` (new)

### Verification
```bash
uv run pytest tests/test_check_review_staleness.py tests/test_review_changed_plugins.py -v
uv run pytest && uv run ruff format --check . && uv run ruff check . && uv run mypy plugins/ scripts/ tests/ --ignore-missing-imports
```

Expected: all green; the staleness check trips on a manufactured drifted-ledger fixture and
stays quiet on a current one; the incremental reviewer scopes to exactly the touched
plugin segment(s) in both single- and multi-plugin PR fixtures.

### Handoff maturity

requirements-ready

### Suggested next action

Use `/plan <issue>` to create an implementation plan.

### Source context

- Source: docs/plans/plugin-fleet-ideation-2026-07-03/survivors/T11.json (ids T11-F3-3,
  T11-F2-6) + docs/plans/2026-07-03-plugin-fleet-grounding-brief.md
- Source type: ideation issue-map
- Source title: Standing per-plugin review ledger + incremental changed-plugin review

### Intent

Today the 8-plugin fleet (`saga` 0.51.0, `team-execution` 2.9.0, `mission-control` 2.4.0, `agy` 0.1.0, `deploy` 0.1.2, `home-lab-ops` 1.2.0, `redis-channel` 0.5.0, `unifi` 1.1.0 — fleet map `docs/plans/2026-07-03-plugin-fleet-grounding-brief.md:10-12`) has no standing review machinery: a comprehensive fleet review is only ever a one-time heroic pass, and no PR-time signal tells an operator "this plugin drifted N commits past its last real review" or "only review the plugin segment this PR actually touched." This issue ships the durable machinery two absorbed ideation facets both converge on: (1) a per-plugin **review ledger** (last-reviewed SHA + lenses run + open findings) with a CI staleness check, and (2) a **diff-to-segment incremental reviewer** that maps a PR's merge-base diff onto plugin directories and invokes `saga:code-review` only on the touched segment(s). Both facets were absorbed into one PR because they share the same files: the incremental reviewer is what *writes* the ledger entry after a review runs, and the staleness check is what *reads* it.

### Context library links

_none_

### Files expected to change

- `plugins/saga/commands/code-review.md`
- `plugins/saga/skills/code-review/SKILL.md`
- `.github/workflows/ci.yml`
- `tools/stale_main_guard.py`
- `scripts/check_review_staleness.py`
- `tools/review-changed-plugins.py`
- `plugins/saga/skills/code-review/references/findings-schema.md`
- `docs/plans/plugin-fleet-ideation-2026-07-03/survivors/T11.json`

### Tests to add or update

- `tests/test_check_review_staleness.py`
- `tests/test_review_changed_plugins.py`

## Created Issue

- URL: https://github.com/infiquetra/infiquetra-claude-plugins/issues/430
- Number: 430
- Created at: 2026-07-04T08:11:25.085685+00:00

