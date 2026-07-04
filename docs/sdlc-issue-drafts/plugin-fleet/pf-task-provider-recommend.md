---
title: "capability: recommend() -- ranked task->provider routing with cheapest-sufficient ladder, prompting protocol, and egress policy"
repo: infiquetra-claude-plugins
type: capability
team: campps
project: operations
status: Idea
labels: capability, hermes-task, needs-plan
risk: medium
handoff_maturity: requirements-ready
tier: structural
objective: "Stand up the external-engine offload lane"
wave: wave-1
---

# capability: recommend() -- ranked task->provider routing with cheapest-sufficient ladder, prompting protocol, and egress policy

## Summary

Add a `recommend()` primitive that, given a task's shape (capability need, sensitivity, budget
posture), returns a ranked list of viable engines/models under a free-first / cheapest-sufficient
policy -- not a single best pick. The recommendation bundles each candidate's per-provider prompting
protocol, and any task carrying sensitive context is constrained to local/no-egress rows only,
never merely to the cheapest row. This is additive to today's `engine_resolver.resolve()`, which
answers "does this specific engine/capability resolve and is it available" for a single selector at
plan-time-preview or dispatch time. `recommend()` answers a different, upstream question: "of all
rows satisfying this task's constraints, what is the ranked, explorable set, and what protocol goes
with each" -- consumed before a selector is even chosen.

## Problem Frame

The fleet's only operator-facing model/effort lever today is saga `/plan`'s per-unit tier table
(`plugins/saga/skills/plan/SKILL.md:293-305`) and its closed `MODELS`/`EFFORTS` vocabularies
(`plugins/saga/scripts/execution_spec.py:52-53`, `fable/opus/sonnet/haiku` x
`low/medium/high/xhigh`). That table assigns exactly one tier per work-shape row -- it is a
work-shape-to-tier lookup, not a ranked ladder of alternatives, and it has no engine/provider
dimension beyond the existing `engine`/`capability` fields on a unit.

`engine_resolver.resolve()` (`plugins/saga/scripts/engine_resolver.py`) already answers engine
availability for one named selector: `mode="advisory"` gives a non-binding plan-time preview
(`plugins/saga/skills/plan/SKILL.md:311-317`, `team-execution/skills/team-execution/references/
external-engine-workers.md` SS2), `mode="dispatch"` gives the run-time binding resolution consumed by
the team-execution chaperone (`team-execution/skills/team-execution/SKILL.md:229-233`). Both modes
take a single `role_kind` + `engine`-or-`capability` selector and return one `Resolution` (with a
Claude-fallback or halt outcome) -- there is no entry point that, given only a task's shape, returns
several ranked candidate rows for a human or calling skill to pick from, nor one that surfaces the
per-provider prompting protocol alongside the ranking, nor one that filters candidates on an egress
axis before ranking on cost.

The binding decisions already fix the outer bounds this capability must respect:
`{#external-engines-never-gatekeepers}` (#283) keeps Claude as verifier-of-record for every gated
decision -- `recommend()` is advisory, it never becomes the gate. `{#external-engine-chaperone-
dispatch}` (#318) keeps external engines as chaperone-dispatched offload/second-opinion workers, not
a second executor kind -- `recommend()` ranks within that existing dispatch shape, it does not invent
a new one. `{#tier-vocab-ordering}` establishes that tier tuples are escalation ladders, not closed
sets to pick one row from (`plugins/saga/scripts/execution_spec.py:45-51`, `MODELS`/`EFFORTS`
ordering is load-bearing for `segment_units()`'s upgrade-only merge) -- this issue's ladder
requirement generalizes that same escalation shape from tiers to providers.

## Requirements (grounded to absorbed facets)

Absorbed ideation facets (`docs/plans/plugin-fleet-ideation-2026-07-03/survivors/T2.json`), each
required as an explicit, testable acceptance criterion below:

- **T2-F1-4** (primary, `basis_type: direct`) -- "Policy-driven `recommend()` -- ranked provider
  routing with free-first / cheapest-viable." `recommend()` must return a ranked list, not a
  singleton, under a selectable free-first-then-cheapest-viable policy.
- **T2-F3-6** (facet, `basis_type: direct`) -- "Cheapest-sufficient escalation ladder instead of
  single-best routing." The ranking is explicitly a ladder callers can walk (retry next rung on
  failure/insufficiency), mirroring the existing tier-vocab-ordering escalation shape.
- **T2-F4-4** (facet, `basis_type: direct`) -- "A single `recommend()` primitive handing authors the
  ranked engine AND its prompting protocol." Each ranked row carries its provider-specific prompting
  protocol (the `protocol` shape already produced per-resolution by `engine_resolver.Resolution`,
  `plugins/saga/scripts/engine_resolver.py`), not just an engine identifier.
- **T2-F3-7** (facet, `basis_type: reasoned`) -- "An egress axis -- route sensitive context to
  local-only, not just to cheap." Tasks flagged sensitive must have their candidate set filtered to
  local/no-egress rows *before* cost ranking is applied, not merely deprioritized within it.

## Definition of Done

- A `recommend()` entry point exists (proposed: `plugins/saga/scripts/engine_recommend.py`, or as a
  function added to `engine_resolver.py` if colocation proves simpler at plan time -- `/plan`
  determines the exact module boundary) that:
  1. Accepts a task-shape descriptor (at minimum: `role_kind`, an optional `capability` selector,
     an optional `sensitive: bool` egress flag, and a policy choice among `free-first` /
     `cheapest-viable`).
  2. Reads the existing engine registry (`plugins/saga/references/engine-registry.yaml` via
     `plugins/saga/scripts/engine_registry.py`) as its candidate source -- it does not invent a
     second registry.
  3. Returns an ordered list of candidate rows (not a single `Resolution`), each row carrying at
     minimum an engine/variant identifier, its prompting protocol, and its cost/tier posture.
  4. When `sensitive=True`, filters to local/no-egress candidates before ranking -- a sensitive task
     with no local-only candidate returns an explicit empty/halt result, never a silent fallback to
     a networked provider.
  5. Never gates or auto-dispatches -- `recommend()` is advisory-only (consistent with
     `{#external-engines-never-gatekeepers}`); the caller (a skill, `/plan`, or a human) makes the
     final pick.
- Unit tests cover: ranking order under each policy, ladder-walk behavior (next rung selectable on
  request), protocol presence on every row, and the egress filter (sensitive task with/without a
  local candidate).
- `uv run pytest`, `uv run ruff check .`, and `uv run mypy plugins/ scripts/ tests/
  --ignore-missing-imports` all pass.
- If any consuming skill (`/plan`, team-execution) is wired to call `recommend()` in this issue's
  scope, the corresponding `SKILL.md`/reference doc is updated to describe the new advisory call
  site; if no consumer is wired in v1, this issue ships `recommend()` and its tests only, and a
  follow-up issue tracks wiring it into `/plan`'s tier-table step.

### Acceptance criteria
- [ ] **Covers T2-F1-4.** `recommend()` called with `policy="free-first"` returns free-tier/no-cost
      candidates ranked ahead of paid candidates when a free candidate satisfies the task shape.
      Check: `uv run pytest tests/test_engine_recommend.py -k free_first_ranks_free_candidates_first`
      -> passes.
- [ ] **Covers T2-F1-4.** `recommend()` called with `policy="cheapest-viable"` returns the lowest-cost
      candidate that satisfies the task's stated capability/tier floor ranked first, not merely the
      globally cheapest candidate regardless of fit. Check: `uv run pytest
      tests/test_engine_recommend.py -k cheapest_viable_respects_capability_floor` -> passes.
- [ ] **Covers T2-F3-6.** The returned structure is an ordered list of >= 2 rows when >= 2 candidates
      satisfy the task shape (never collapsed to a single best pick), and a documented "next rung"
      accessor lets a caller request the next candidate after a given one fails. Check: `uv run
      pytest tests/test_engine_recommend.py -k ladder_walk_returns_next_candidate_after_failure` ->
      passes.
- [ ] **Covers T2-F4-4.** Every row in the returned list carries a non-empty prompting protocol
      specific to its engine (reusing `engine_resolver.Resolution.protocol`'s shape), not a shared
      generic protocol string. Check: `uv run pytest tests/test_engine_recommend.py -k
      every_row_carries_engine_specific_protocol` -> passes.
- [ ] **Covers T2-F3-7.** A task with `sensitive=True` and at least one local/no-egress registry
      candidate returns only local/no-egress rows, with any networked candidate excluded from the
      list entirely (not merely ranked last). Check: `uv run pytest tests/test_engine_recommend.py -k
      sensitive_task_filters_to_local_only` -> passes.
- [ ] **Covers T2-F3-7.** A task with `sensitive=True` and zero local/no-egress registry candidates
      returns an explicit empty-result/halt marker rather than falling back to a networked candidate.
      Check: `uv run pytest tests/test_engine_recommend.py -k
      sensitive_task_no_local_candidate_halts` -> passes.
- [ ] **Covers DoD (advisory-only).** `recommend()` never triggers dispatch as a side effect -- calling
      it performs no engine invocation, matching `engine_resolver.resolve(mode="advisory")`'s
      existing non-binding contract. Check: `uv run pytest tests/test_engine_recommend.py -k
      recommend_is_read_only_no_dispatch_side_effect` -> passes.
- [ ] Full suite, format, lint, types stay green. Check: `uv run pytest && uv run ruff format --check
      . && uv run ruff check . && uv run mypy plugins/ scripts/ tests/ --ignore-missing-imports` ->
      all pass.

### Out-of-scope / non-goals
- **Not a new registry.** `recommend()` reads the existing `plugins/saga/references/
  engine-registry.yaml` / `engine_registry.py` schema. Extending the registry schema (e.g. adding a
  cost field if one is missing) is in-scope only to the minimum needed to rank; a full cost-model
  overhaul is out of scope.
- **Not a replacement for `engine_resolver.resolve()`.** `resolve()`'s single-selector
  advisory/dispatch contract is unchanged. `recommend()` is a new, separate upstream entry point;
  this issue does not refactor `resolve()`'s callers.
- **Not wiring into `/plan`'s tier table in this issue** unless the executor judges it trivially
  additive during implementation -- if deferred, file the follow-up explicitly rather than leaving it
  implicit.
- **Not a UI/CLI surface.** This issue delivers the Python entry point and its tests; a
  `mission-control` or `saga` command-level wrapper is a separate issue if wanted.
- **Not changing `{#external-engines-never-gatekeepers}` or `{#external-engine-chaperone-dispatch}`**
  -- `recommend()` operates inside both constraints as advisory-only, chaperone-dispatch-shaped
  tooling; it does not introduce a second executor kind or a gated auto-pick.

## Grounding References

- Issue-map entry: `pf-task-provider-recommend`, objective "Stand up the external-engine offload
  lane", wave-1, tier structural
  (`docs/plans/plugin-fleet-ideation-2026-07-03/../issue-map/issue-map-final.json` — see also the
  session scratchpad copy consulted during drafting).
- Absorbed facets (`docs/plans/plugin-fleet-ideation-2026-07-03/survivors/T2.json`):
  - `T2-F1-4` -- "Policy-driven recommend() -- ranked provider routing with free-first /
    cheapest-viable" (`basis_type: direct`, theme T2, frame F1, axis task-provider-fit).
  - `T2-F3-6` -- "Cheapest-sufficient escalation ladder instead of single-best routing"
    (`basis_type: direct`, theme T2, frame F3, axis task-provider-fit).
  - `T2-F4-4` -- "A single recommend() primitive handing authors the ranked engine AND its prompting
    protocol" (`basis_type: direct`, theme T2, frame F4, axis task-provider-fit).
  - `T2-F3-7` -- "An egress axis -- route sensitive context to local-only, not just to cheap"
    (`basis_type: reasoned`, theme T2, frame F3, axis auth-config-secrets).
- Grounding brief (`docs/plans/2026-07-03-plugin-fleet-grounding-brief.md`):
  - SS1 "Fleet map": the fleet's only operator-facing model/effort lever is saga `/plan`'s tier table
    (`plugins/saga/skills/plan/SKILL.md:296-352`) and closed `MODELS`/`EFFORTS` vocab
    (`plugins/saga/scripts/execution_spec.py:52-53`); `ENGINE_INTENTS` producer/consumer pair
    authored in `/plan` (`plan/SKILL.md:303-304`) rendered in team-execution's worker table
    (`team-execution/SKILL.md:229-233` -> `references/external-engine-workers.md`).
  - SS2 binding-decision register: `{#external-engines-never-gatekeepers}` (#283),
    `{#external-engine-chaperone-dispatch}` (#318), `{#tier-vocab-ordering}`.
  - SS8 final theme roster, item 2: "Provider/model routing beyond CLI engines (one router plugin,
    registry-driven -- intake)" -- this issue is the router-plugin capability for that theme.
- Existing code this builds on (verified in-repo): `plugins/saga/scripts/engine_resolver.py`
  (`resolve()`, `Resolution`, `MODES`, `ROLE_KINDS`, `FALLBACK_ROLE_KINDS`/`HALT_ROLE_KINDS`),
  `plugins/saga/scripts/engine_registry.py` + `plugins/saga/references/engine-registry.yaml`
  (capability/registry schema), `plugins/saga/scripts/execution_spec.py:45-51` (tier-vocab escalation
  ordering precedent).

## Recommended Executor Profile

- **Model:** sonnet
- **Effort:** high — *target posture: not a live team-execution dispatch knob until `pf-effort-first-class` lands; teammates inherit session tier until then*
- **Backend:** team-execution
- **External-LLM posture:** none (this issue does not delegate its own implementation to an external
  engine)
- **Justification:** This is new-module-plus-tests work with a clear existing pattern to extend
  (`engine_resolver.py`'s resolution/registry shapes) rather than novel architectural judgment --
  sonnet/high fits mechanical-but-nontrivial design-within-precedent work. It does not need
  opus-level adversarial judgment because the binding decisions (#283, #318) and the existing
  `Resolution`/registry contracts already constrain the design space; escalate to opus/high only if
  `/plan` surfaces a genuine architectural fork (e.g. whether `recommend()` colocates in
  `engine_resolver.py` or is a new module) that the tier-table step cannot resolve mechanically.

## Release-Surface Checklist

This issue changes plugin behavior (a new capability entry point consumed by `saga`, and potentially
by `team-execution` if wiring is included) -- update in the same PR:

- [ ] `plugins/saga/.claude-plugin/plugin.json` -- version bump + CHANGELOG cross-reference if
      `recommend()` ships as part of `saga`'s scripts surface.
- [ ] `.claude-plugin/marketplace.json` -- version drift check for `saga` (and `team-execution` if
      wired).
- [ ] `plugins/saga/CHANGELOG.md` (and `plugins/team-execution/CHANGELOG.md` if wired) -- entry
      describing the new `recommend()` primitive and its policy/egress contract.
- [ ] Any version/metadata drift-guard tests (e.g. `tests/test_marketplace_versions.py` or
      equivalent, if present) updated to reflect the version bump.
- [ ] `docs/engineering-journal/DECISIONS.md` -- entry for the design choice of colocating vs.
      separating `recommend()` from `resolve()`, with rejected alternatives and a revisit-when
      condition (per this repo's CLAUDE.md auto-maintain rule).

### Files expected to change

Indicative only -- exact set is `/plan`'s to determine.

- `plugins/saga/scripts/engine_recommend.py` (proposed new module) or an addition to
  `plugins/saga/scripts/engine_resolver.py`.
- `plugins/saga/references/engine-registry.yaml` -- only if a cost/egress field is missing and
  minimally required for ranking.
- `tests/test_engine_recommend.py` -- new test file.
- `plugins/saga/CHANGELOG.md`, `plugins/saga/.claude-plugin/plugin.json`,
  `.claude-plugin/marketplace.json` -- release-surface updates.
- `docs/engineering-journal/DECISIONS.md` -- design-decision entry.

### Tests to add or update

- Ranking: free-first policy ranks free/no-cost candidates ahead of paid ones when a free candidate
  satisfies the task shape.
- Ranking: cheapest-viable policy respects a stated capability/tier floor, not just raw cost.
- Ladder: returned structure supports >= 2 candidates and a next-rung accessor.
- Protocol: every returned row carries a non-empty, engine-specific prompting protocol.
- Egress: sensitive task with a local candidate returns local-only rows; sensitive task with no local
  candidate returns an explicit halt/empty result, never a networked fallback.
- Side effect: calling `recommend()` triggers no engine dispatch.

### Verification

```bash
# New recommend() unit tests
uv run pytest tests/test_engine_recommend.py -v
# Full repo gate (CI parity)
uv run pytest && uv run ruff format --check . && uv run ruff check . && uv run mypy plugins/ scripts/ tests/ --ignore-missing-imports
```

Expected: all green.

### Handoff maturity

requirements-ready

### Suggested next action

Use `/plan` on this issue to determine the exact module boundary (new `engine_recommend.py` vs. an
addition to `engine_resolver.py`) and whether `/plan`'s tier-table step is wired to call
`recommend()` in this pass or deferred to a follow-up.

### Source context

- Source: `docs/plans/plugin-fleet-ideation-2026-07-03/survivors/T2.json` (facets `T2-F1-4`,
  `T2-F3-6`, `T2-F4-4`, `T2-F3-7`) via
  `docs/plans/plugin-fleet-ideation-2026-07-03/../issue-map/issue-map-final.json` (slug
  `pf-task-provider-recommend`)
- Source type: ideation-survivor-cluster
- Source title: recommend() -- ranked task->provider routing with cheapest-sufficient ladder,
  prompting protocol, and egress policy

### Intent

Add a `recommend()` primitive that, given a task's shape (capability need, sensitivity, budget posture), returns a ranked list of viable engines/models under a free-first / cheapest-sufficient policy -- not a single best pick. The recommendation bundles each candidate's per-provider prompting protocol, and any task carrying sensitive context is constrained to local/no-egress rows only, never merely to the cheapest row. This is additive to today's `engine_resolver.resolve()`, which answers "does this specific engine/capability resolve and is it available" for a single selector at plan-time-preview or dispatch time. `recommend()` answers a different, upstream question: "of all rows satisfying this task's constraints, what is the ranked, explorable set, and what protocol goes with each" -- consumed before a selector is even chosen.

### Context library links

_none_

### Objective

"Stand up the external-engine offload lane"

## Created Issue

- URL: https://github.com/infiquetra/infiquetra-claude-plugins/issues/391
- Number: 391
- Created at: 2026-07-04T07:58:48.120114+00:00

