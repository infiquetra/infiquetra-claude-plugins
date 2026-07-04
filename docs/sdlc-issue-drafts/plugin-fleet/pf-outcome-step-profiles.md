---
title: "capability: declarative lifecycle step-profile registry (input shape -> steps)"
repo: infiquetra-claude-plugins
type: capability
team: campps
project: operations
status: Idea
labels: capability, hermes-task, needs-plan
risk: medium
handoff_maturity: requirements-ready
tier: structural
objective: "Ship run-start intent envelope for lifecycle autonomy"
wave: wave-1
---

# capability: declarative lifecycle step-profile registry (input shape -> steps)

### Intent
Ship a declarative step-profile registry — a data file (JSON) plus a shared pure resolver function —
that maps a leaf's input shape (`kind` + risk flags) to the ordered list of lifecycle steps it must
run, and consume that resolver from both `/work` and `/outcome` dispatch instead of each path assuming
the full lifecycle runs on every leaf. Today `OutcomeSpec.Node` already carries the shape data needed
to make this decision — `kind` (`"code" | "non-code"`, `plugins/saga/scripts/outcome_spec.py:201`,
`NODE_KINDS` at `:56`) and the risk flags `gated` / `risky` / `destructive`
(`plugins/saga/scripts/outcome_spec.py:205-207`, doc'd at `:191-192`) — but nothing reads that data to
select which steps a leaf runs; `/outcome`'s `advance` dispatches ready leaves to their native verbs
uniformly (`plugins/saga/skills/outcome/SKILL.md:27`, "The coordinator routes, it never executes
(R2/R3)"), and `/work` documents its own fixed phase sequence
(`plugins/saga/skills/work/SKILL.md:287-294`, "Phase 2 — Execute phase... one meaningful phase per
`references/execution-strategy.md`") without deriving it from the node's kind or risk flags. The result
is that a low-risk `non-code` leaf and a `destructive`+`gated` `code` leaf run through the same
step list today, with no per-leaf derivation and no shared place to encode "this shape needs
review+qa, that shape needs work only."

This absorbs two convergent ideation survivors from the same theme (`T8`, axis
`step-selection-derivation`) that the ideation issue-map consolidated into one issue
(`consolidation_rationale`: "The data-driven registry (JSON + resolver shared by `/work` and
`/outcome`) is the stronger mechanism; the pure `step_profile(node)` derivation with
HALT-on-missing-capability becomes its resolver semantics."):
- `T8-F4-3` (primary) — "Lifecycle step-profile registry: input shape -> which steps a leaf runs, as
  data not code" (`docs/plans/plugin-fleet-ideation-2026-07-03/survivors/T8.json`, `basis_type: direct`,
  `tier_guess: structural`). Its `dod_sketch`: "Merged PR adding a declarative step-profile registry
  (JSON) + resolver consumed by both `/work` and `/outcome` dispatch; verified by resolver tests mapping
  each input-shape fixture to its ordered step list incl. a prefix-ladder assertion (engages
  `{#tier-vocab-ordering}`)."
- `T8-F1-6` (facet) — "Derive a per-leaf `step_profile` from kind + risk instead of assuming the full
  lifecycle." Its `dod_sketch`: "Merged PR adding a pure `step_profile(node)` fn surfaced in
  attend/graph that HALTs on missing step capability; verified by a table test over
  (kind, risk-flags)->verb-set plus an attend-handoff snapshot."

`T8-F4-3` is the data-driven, shared-registry shape (wins as primary because it is reusable by both
call sites); `T8-F1-6`'s HALT-on-missing-capability semantics and its attend/graph surfacing become
the resolver's runtime behavior, not a separate mechanism.

This also engages the binding decision `{#tier-vocab-ordering}` (Tier tuples are ordered escalation
ladders, not just closed sets — `docs/plans/2026-07-03-plugin-fleet-grounding-brief.md:51`): the
resolver's ordered step list for an escalating risk profile must be a strict prefix-extension of the
step list for the lower risk profile beneath it (e.g. a `gated` leaf's step list is the `risky` leaf's
step list plus additional steps, never a reordering or a disjoint set) — this is what the prefix-ladder
assertion in `T8-F4-3`'s DoD sketch tests.

## Definition of Done
A declarative step-profile registry (JSON) plus a pure `step_profile(node)` resolver exist, are
consumed by both `/work` and `/outcome` dispatch (no duplicated logic), and HALT on any leaf whose
resolved step names a step with no registered capability. The resolved profile is visible in `attend`
output, and the ordered step lists satisfy the `{#tier-vocab-ordering}` prefix-ladder rule across
escalating risk flags. Merged PR with resolver tests as described below.

### Out-of-scope / non-goals
### Out-of-scope / non-goals
- Changing what any individual lifecycle step (`/plan`, `/doc-review`, `/work`, `/code-review`, `/qa`)
  does internally — this issue only decides *which* steps run for a given leaf shape, not their
  contents.
- Changing `OutcomeSpec.Node`'s schema (`kind`, `gated`, `risky`, `destructive`) — the registry consumes
  these fields as they exist today; adding new risk-flag dimensions is a separate issue.
- Retrofitting historical/in-flight outcome runs to the new profile — the resolver applies to newly
  dispatched leaves going forward.
- A UI/CLI flag for the operator to override a derived step profile per-run — the resolver is
  authoritative; an explicit override mechanism is a fast-follow if warranted.
- Team-execution's validator-family dispatch (`plugins/team-execution/...`) — out of scope; this issue
  is scoped to the `/work` and `/outcome` coordinator paths named in both absorbed ideas' DoD sketches.

### Files expected to change
Indicative only — the exact set is `/plan`'s to determine.
- `plugins/saga/scripts/step_profile.py` — new module: the declarative step-profile registry (JSON,
  co-located or inline) plus the pure `step_profile(node)` resolver function.
- `plugins/saga/scripts/outcome_spec.py` — no schema change expected, but the resolver imports/consumes
  `Node.kind`, `Node.gated`, `Node.risky`, `Node.destructive` from here.
- `plugins/saga/skills/outcome/SKILL.md` — `advance`/`attend`/`graph` sections updated to document that
  dispatch consults the step-profile resolver rather than assuming a fixed step list; `attend` surfaces
  the resolved profile to the operator.
- `plugins/saga/skills/work/SKILL.md` — Phase 2 execute-phase section updated to consult the same
  resolver instead of the current fixed phase sequence.
- `tests/test_step_profile.py` — new resolver tests (repo-root collected, per repo convention).

### Tests to add or update
- Table test over `(kind, risk-flags) -> ordered step list`: at minimum covers `("code", no flags)`,
  `("non-code", no flags)`, `("code", risky=True)`, `("code", gated=True)`, `("code", destructive=True)`,
  and a combined-flags case.
- Prefix-ladder assertion: for every pair of profiles where one risk level strictly escalates from
  another, assert the higher profile's step list is the lower profile's step list plus a strict suffix
  (never a reorder, never a removed step) — this is the `{#tier-vocab-ordering}` engagement named in
  `T8-F4-3`.
- HALT-on-missing-capability: a node whose resolved step list names a step with no registered
  executor/capability raises/HALTs rather than silently skipping or degrading (`T8-F1-6` semantics).
- `attend`/`graph` snapshot test: the resolved step profile for a leaf is visible in `attend` output
  (per `T8-F1-6`'s "surfaced in attend/graph").
- Resolver is a pure function: same `(kind, risk-flags)` input always yields the same ordered step
  list, with no hidden state or side effects (unit-testable in isolation from a live outcome run).

## Grounding References

### Context library links
- source_context: docs/plans/2026-07-03-plugin-fleet-grounding-brief.md
- source_context: docs/plans/plugin-fleet-ideation-2026-07-03/survivors/T8.json (T8-F4-3, T8-F1-6)
- source_context: /private/tmp/.../scratchpad/ideation/issue-map/issue-map-final.json (slug
  `pf-outcome-step-profiles`)

### Acceptance criteria
### Acceptance criteria
- [ ] A resolver function maps each of the table-test's input-shape fixtures — `(kind, risk-flags)` —
  to its documented ordered step list. Check: `uv run pytest tests/test_step_profile.py -k table` →
  passes.
- [ ] The prefix-ladder assertion holds across every escalating risk-flag pair in the table (higher
  profile's steps = lower profile's steps + strict suffix, never reordered). Check:
  `uv run pytest tests/test_step_profile.py -k prefix_ladder` → passes.
- [ ] A node whose resolved step names a step with no registered capability HALTs (raises a named,
  typed error) rather than silently skipping it. Check:
  `uv run pytest tests/test_step_profile.py -k halt_missing_capability` → passes.
- [ ] The registry is data (JSON), not inline code branching, and both `/work` and `/outcome` dispatch
  call the same resolver function. Check: `grep -rn "step_profile(" plugins/saga/scripts/*.py` shows
  the resolver imported/called from both the `/work`-path module and the `/outcome`-path module (not
  duplicated logic).
- [ ] The resolved step profile for a leaf is visible in `attend` output. Check:
  `uv run pytest tests/test_outcome_attend.py -k step_profile_snapshot` (or equivalent attend-snapshot
  test named in the plan) → passes.
- [ ] Full suite, format, lint, and types stay green. Check:
  `uv run pytest && uv run ruff format --check . && uv run ruff check . && uv run mypy plugins/ scripts/ tests/ --ignore-missing-imports` →
  all pass.

### Verification
```bash
# Unit tests for the new registry/resolver
uv run pytest tests/test_step_profile.py -v
# Full repo gate (CI parity)
uv run pytest && uv run ruff format --check . && uv run ruff check . && uv run mypy plugins/ scripts/ tests/ --ignore-missing-imports
```
Expected: all green; the prefix-ladder and HALT-on-missing-capability tests pass explicitly.

### Release-surface checklist
This issue changes `/work` and `/outcome` dispatch behavior (which steps run per leaf), so the
following release surfaces must be updated in the same PR:
- [ ] `plugins/saga/.claude-plugin/plugin.json` — version bump for the behavior change.
- [ ] `.claude-plugin/marketplace.json` — saga entry version/description kept in sync if the plugin
  version bumps.
- [ ] `plugins/saga/CHANGELOG.md` — entry describing the new step-profile registry and its effect on
  `/work` and `/outcome` step selection.
- [ ] Any version/metadata drift-guard tests (e.g. a test asserting `plugin.json` version matches
  `marketplace.json` / `CHANGELOG.md`) — run and confirm still green after the bump.

## Executor Profile

### Recommended executor profile
- Model: **sonnet**
- Effort: **medium**
- Backend: **inline**
- External-LLM posture: **none**
- Justification: mechanical, well-scoped registry-plus-resolver work over an existing, already-typed
  schema (`OutcomeSpec.Node`) with a clear table-test contract; no architectural ambiguity or
  adversarial-review need that would justify opus or an external-engine chaperone dispatch.

### Handoff maturity
requirements-ready

### Suggested next action
Use `/plan <issue>` to create an implementation plan.

### Source context
- Source: docs/plans/2026-07-03-plugin-fleet-grounding-brief.md
- Source type: grounding-brief
- Source title: Plugin Fleet Ideation 2026-07-03 — Grounding Brief

### Objective

"Ship run-start intent envelope for lifecycle autonomy"

## Created Issue

- URL: https://github.com/infiquetra/infiquetra-claude-plugins/issues/378
- Number: 378
- Created at: 2026-07-04T07:54:37.717854+00:00

