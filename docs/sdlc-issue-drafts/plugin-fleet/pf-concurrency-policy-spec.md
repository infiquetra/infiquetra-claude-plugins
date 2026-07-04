---
title: "capability: concurrency policy as a first-class ExecutionSpec block (wave-width cap, resolution ladder, tier/lane weighting, emit-time aggregate guard, spawn-site drift guard)"
repo: infiquetra-claude-plugins
type: capability
tier: structural
objective: "Govern fleet concurrency and reclaim leaked resources"
wave: wave-1
team: campps
project: operations
status: Idea
labels: capability, hermes-task, needs-plan
risk: medium
handoff_maturity: requirements-ready
executor_profile: {model: sonnet, effort: high, backend: inline, external_llm: none}
---

# capability: concurrency policy as a first-class ExecutionSpec block (wave-width cap, resolution ladder, tier/lane weighting, emit-time aggregate guard, spawn-site drift guard)

### Intent
Give the fleet's only orchestration-level concurrency cap — `VERIFY_N_CAP = 7`
(`plugins/saga/scripts/execution_spec.py:114`) — a real policy home instead of leaving it a lone
literal with no schema, no resolution order, and no reach beyond one verify-panel check. Add a
`ConcurrencyPolicy` block to `ExecutionSpec` with a spec-default → env → run-override resolution
ladder; make the layer-wave emitter and the verify-panel chunker both consume it; let read-only
waves and per-lane (engine-registry) overrides modulate it; add an emit-time aggregate in-flight
guard (widest layer × co-running verify panels); and add a spawn-site drift-guard test so a new
fan-out cannot bypass the policy the way today's unbounded `parallel([...])` waves already do.

## Problem / Motivation

- **The only cap in the fleet is a lone literal with no policy home.** `VERIFY_N_CAP = 7`
  (`plugins/saga/scripts/execution_spec.py:114`) bounds one thing — a verify panel's verifier
  count — via `VerifyPanelSpec.validate()` (`execution_spec.py:352-368`). `docs/plans/2026-07-03-
  plugin-fleet-grounding-brief.md` §1 ("Concurrency governance") states this directly: "the only
  orchestration-level cap is `VERIFY_N_CAP = 7` ... team-execution reviewer fan-out, `/outcome`
  leaf dispatch, and engine bridges are unbounded." Nothing bounds a layer's `parallel([...])`
  wave width at all.
- **The fleet has already been burned by exactly this gap.** `VERIFY_N_CAP`'s own docstring
  (`execution_spec.py:111-113`) names its origin: "the bound directly guards the rate-limit
  overcorrection (R3: the 22/23-judges panel that tripped the concurrency cap)." The grounding
  brief's session-mining synthesis (§7, pattern 4, "Rate-limit fan-out kills") independently
  confirms this is recurring, not historical: "'6 of 7 agents failed on rate-limiting'; 'the
  emitter has no concurrency knob... KTD6 was aspiration, not machinery' (3 repos)."
- **`/optimize` deliberately removed a `max_concurrent` knob rather than adopt a shared one.**
  The grounding brief §1 calls this out explicitly: "`/optimize` deliberately removed a
  `max_concurrent` knob (`optimize/SKILL.md:18`) — ideation on theme 13 must engage why." The
  `optimize/SKILL.md:17-19` text confirms the default path "SHEDS `ce-optimize`'s git-worktree-
  per-experiment isolation, its parallel/`max_concurrent` fan-out ... Those re-enter only by an
  explicit operator-choice escalation." A shared, policy-driven cap primitive is what would let a
  future `/optimize` escalation re-adopt bounded concurrency without re-inventing a bespoke knob.
- **The emitter already has a "validate authored values at emit, never invent" pattern to
  extend.** `execution_spec.py:46-53` documents the tier-vocabulary closed-set validation
  contract this issue reuses for the concurrency block: authored values are checked against a
  known-good shape at emit time and fail loudly, rather than being silently coerced.
- **Read-only waves and per-lane residents are governed identically to read-write waves today**,
  even though the fleet already tracks a `mutation_policy` axis (`execution_spec.py:410-422`,
  `read-only` / `read-write`) that read-only wave-width lifting can reuse instead of inventing a
  new axis, and an engine/lane registry concept (per the fleet's engine-registry pattern) that a
  per-lane `max_concurrent` field can attach to.
- **A drift-guard test already exists as prior art for this exact failure shape.**
  `plugins/saga/references/sandbox-spawn-sites.md` enumerates every fleet spawn site and is
  itself the guard that the CLAUDE.md-mandated sandbox-spawn-site discipline depends on; this
  issue's spawn-site conformance test (facet `T13-F1-7`) mirrors that same enumerate-and-assert
  pattern for concurrency instead of sandboxing.

## Definition of Done

Merged PR(s) delivering:

1. A `ConcurrencyPolicy` dataclass in `plugins/saga/scripts/execution_spec.py` with a resolution
   ladder — spec-authored default → environment override → explicit run-time override — and a
   fleet default cap of 3, validated at emit time using the existing closed-set validation
   pattern (`execution_spec.py:46-53`).
2. `VERIFY_N_CAP` derived from the `ConcurrencyPolicy` block rather than declared as an
   independent literal (facet `T13-F1-2`/`T13-F4-7`: `max_concurrent` promoted to a validated
   `ExecutionSpec` field alongside tier, with an emit-time ceiling check and `to_dict`
   serialization).
3. The layer-wave emitter chunks any authored `parallel([...])` wave to the resolved cap while
   preserving dependency order (facet `T13-F1-1`): a 6-unit layer renders as two 3-wide waves by
   default; a read-only layer may lift to width 4.
4. The verify-panel emitter (`_emit_panel_reconciliation` or equivalent) routes verifier
   fan-out through the same chunking primitive (facet `T13-F3-3`), so an n=7 legal panel never
   emits a single wave wider than the resolved cap.
5. A per-wave read-only lift derived from the existing `mutation_policy` axis (facet `T13-F2-7`):
   an all-read-only layer chunks at width 4; a layer containing any read-write unit chunks at the
   base cap (3).
6. A tier-weighted admission function (facet `T13-F3-8`) in the concurrency governor: a
   tier→weight table so a cheap-tier wave can admit more slots than an expensive-tier wave under
   the same budget, rather than treating concurrency as flat headcount.
7. A per-lane `max_concurrent` override field on the engine-registry (facet `T13-F6-7`), resolved
   as the most specific rung on the resolution ladder (per-lane overrides the tier-weighted
   default, which overrides the env override, which overrides the spec default).
8. An emit-time aggregate in-flight guard (facet `T13-F6-6`): `max_concurrent_agents(spec)`
   computes the widest layer width plus any co-running verify-panel width and warns/fails against
   a fleet-wide aggregate cap at emit time, not at runtime.
9. A spawn-site conformance test (facet `T13-F1-7`) that parses the fleet's spawn-site inventory
   (mirroring `plugins/saga/references/sandbox-spawn-sites.md`'s enumeration discipline) and
   asserts every fan-out site routes through the `ConcurrencyPolicy` primitive; the test goes red
   on an injected unbounded `parallel(...)` fixture.
10. Release-surface updates (see checklist below) reflecting the new policy block as a
    fleet-behavior change.

Verify: per-rung resolution-ladder tests (spec-default, env override, run override, each winning
at its rung); an invalid-override emit failure test; a repo-wide grep confirming no stray cap
literals remain outside the policy block; the spawn-site conformance test red-before/green-after
on an injected unbounded wave.

### Acceptance criteria
- [ ] **AC1 (T13-F1-2, primary).** A `ConcurrencyPolicy` block validates against a resolution ladder
  — spec default → env override → run override — with a default cap of 3. Check: `uv run pytest
  tests/test_concurrency_policy.py -k resolution_ladder` → passes for each rung; an invalid
  override (e.g. non-positive cap) fails `validate()` at emit time —
  `uv run pytest tests/test_concurrency_policy.py -k invalid_override_fails_emit` → passes.
- [ ] **AC2 (T13-F1-1).** Emitted `parallel([...])` layer waves chunk to the resolved cap while
  preserving dependency order. Check: `uv run pytest tests/test_concurrency_policy.py -k
  layer_wave_chunking` → a golden emit test asserts a 6-unit layer renders as two 3-wide waves.
- [ ] **AC3 (T13-F4-7).** `max_concurrent` is a validated `ExecutionSpec` field with an emit-time
  ceiling check and round-trips through `to_dict`/`from_dict`. Check: `uv run pytest
  tests/test_concurrency_policy.py -k max_concurrent_field` → an over-ceiling authored value
  fails emit; a valid value round-trips.
- [ ] **AC4 (T13-F3-3).** Verify-panel verifier fan-out (n up to `VERIFY_N_CAP`) routes through the
  same chunking primitive as layer waves. Check: `uv run pytest tests/test_concurrency_policy.py
  -k panel_chunking` → an n=7 panel emits no single wave wider than the resolved cap.
- [ ] **AC5 (T13-F2-7).** Read-only waves (derived from the existing `mutation_policy` axis) may lift
  the chunk width to 4; any read-write unit in the layer keeps the base cap. Check: `uv run
  pytest tests/test_concurrency_policy.py -k readonly_lift` → an all-read-only layer chunks at
  width 4; a mixed layer chunks at width 3.
- [ ] **AC6 (T13-F3-8).** A tier→weight table drives admission so a cheap-tier wave admits more
  slots than an expensive-tier wave under the same aggregate budget. Check: `uv run pytest
  tests/test_concurrency_policy.py -k tier_weighted_admission` → passes.
- [ ] **AC7 (T13-F6-7).** A per-lane `max_concurrent` field on the engine-registry resolves as the
  most specific rung on the ladder, overriding tier-weighted/env/spec defaults for that lane.
  Check: `uv run pytest tests/test_concurrency_policy.py -k per_lane_override` → passes.
- [ ] **AC8 (T13-F6-6).** An emit-time aggregate in-flight guard (widest layer × co-running verify
  panels) warns/fails against the fleet cap before runtime. Check: `uv run pytest
  tests/test_concurrency_policy.py -k aggregate_guard` → a layer × panel product over the fleet
  cap trips the guard; a within-cap spec emits clean.
- [ ] **AC9 (T13-F1-7).** A spawn-site conformance test enumerates every fleet fan-out site and
  asserts each routes through the `ConcurrencyPolicy` primitive. Check: `uv run pytest
  tests/test_concurrency_conformance.py` → passes on the merged tree; injecting an unbounded
  `parallel(...)` fixture at a new spawn site turns it red (CI parity).
- [ ] **AC10.** `VERIFY_N_CAP` is derived from the `ConcurrencyPolicy` block, not declared as an
  independent literal. Check: `grep -n '^VERIFY_N_CAP = ' plugins/saga/scripts/execution_spec.py`
  → the assignment reads from the policy block/module, not a bare integer literal at module
  scope.

### Out-of-scope / non-goals
**In scope:** the `ConcurrencyPolicy` schema and resolution ladder, layer-wave and verify-panel
chunking consuming it, read-only lift, tier weighting, per-lane override, the emit-time aggregate
guard, and the spawn-site conformance test.

**Non-goals (deferred, explicitly out of scope for this issue):**
- Re-introducing `/optimize`'s removed `max_concurrent` fan-out — this issue builds the shared
  primitive `/optimize` could later opt back into via its documented "explicit operator-choice
  escalation" path (`optimize/SKILL.md:17-19`); re-wiring `/optimize` itself is separate follow-on
  work, not part of this issue.
- Runtime-level rate-limit handling (429 backoff/retry) — the grounding brief §1 notes HTTP-level
  429 handling exists only in unifi and mission-control clients; this issue is an emit-time
  admission-control guard, not a runtime retry primitive. That is a distinct capability.
- team-execution's residency/consensus reviewer-registry mechanics — this issue adds a per-lane
  `max_concurrent` field the registry can carry, but does not redesign reviewer/validator
  dispatch itself.
- Any external-engine worker slot or chaperone-dispatch tier behavior — out of scope per
  `{#external-engine-chaperone-dispatch}` (#318); external-engine workers are not a concurrency
  lane this issue introduces.

## Grounding References

| Absorbed idea | Basis | Role |
|---|---|---|
| `T13-F1-2` | `execution_spec.py:114` (`VERIFY_N_CAP` "a lone literal with no policy home"); grounding brief §1 ("the only orchestration-level cap"); `execution_spec.py:46-53` (validate-at-emit pattern this reuses) | primary |
| `T13-F1-1` | Grounding brief §1 + §7 pattern 4 ("Rate-limit fan-out kills" — "the emitter has no concurrency knob... KTD6 was aspiration, not machinery", 3 repos) | facet |
| `T13-F4-7` | `execution_spec.py:111-114` ("Hard upper bound on a verify panel's verifier count... VERIFY_N_CAP = 7"); theme constraint naming `VERIFY_N_CAP` as "the existing pattern to extend" | facet |
| `T13-F6-6` | Reasoned from the widest-layer / verify-panel co-occurrence risk; grounding brief §1 concurrency-governance gap | facet |
| `T13-F3-3` | `VerifyPanelSpec.validate()` bound (`execution_spec.py:352-368`, KTD3: `1 <= n <= VERIFY_N_CAP`) — extending the bound to actual emitted fan-out width, not just authored n | facet |
| `T13-F2-7` | `mutation_policy` axis (`execution_spec.py:410-422`, read-only enforced by tool-set omission) reused as the read-only wave-lift signal | facet |
| `T13-F3-8` | Reasoned: concurrency is rate cost, not headcount — tier-weighted admission generalizes the flat per-wave cap | facet |
| `T13-F6-7` | Fleet's engine-registry/lane concept — per-lane `max_concurrent` as a registry field, resolved as the most specific ladder rung | facet |
| `T13-F1-7` | `plugins/saga/references/sandbox-spawn-sites.md` enumerate-and-assert discipline, mirrored for concurrency instead of sandboxing | facet |

**Binding decisions this issue builds on / must not contradict:**
- `{#tier-vocab-ordering}` — tier tuples are ordered escalation ladders; the tier-weighted
  admission function (AC6) consumes tier order, it does not redefine it.
- CLAUDE.md sandbox-spawn-sites discipline (`plugins/saga/references/sandbox-spawn-sites.md`) —
  the spawn-site conformance test (AC9) is a sibling guard, not a replacement; it does not relax
  the existing sandbox-spawn requirement for verify/review-class spawns.
- `{#external-engine-chaperone-dispatch}` (#318) — external-engine workers stay chaperone-
  dispatch only; they are not introduced as a concurrency lane by this issue.
- `/outcome` campaign HALT-not-degrade binding — the aggregate in-flight guard (AC8) and the
  invalid-override check (AC1) fail loudly at emit time; they do not silently clamp or degrade.

## Recommended Executor Profile

- **Model:** sonnet
- **Effort:** high
- **Backend:** inline
- **External LLM:** none
- **Justification:** this is a bounded schema-plus-emitter extension over an existing, well-
  documented validation pattern (`execution_spec.py:46-53`) rather than novel design or
  adversarial judgment — sonnet/high matches the fleet's own work-shape heuristic
  (`plugins/saga/skills/plan/SKILL.md`: mechanical, deterministic, scripted transforms over a
  large bounded surface). No external-LLM chaperone dispatch is warranted; this stays inline
  within saga's own script tree.

## Release-Surface Checklist

This issue changes saga's emitted-workflow behavior (new policy block, changed wave-chunking and
verify-panel emission) and adds a new operator-relevant guard, so the following must update in
the same PR:
- [ ] `plugins/saga/.claude-plugin/plugin.json` — version bump reflecting the concurrency-policy
      block and emitter behavior change.
- [ ] `.claude-plugin/marketplace.json` — saga entry version/description kept in sync with the
      plugin.json bump.
- [ ] `plugins/saga/CHANGELOG.md` — entry describing the `ConcurrencyPolicy` block, resolution
      ladder, tier/lane weighting, aggregate guard, and spawn-site drift guard.
- [ ] Drift-guard/version-metadata tests (repo's existing marketplace/plugin-metadata drift
      tests) updated or confirmed still green against the version bump.
- [ ] `plugins/saga/references/sandbox-spawn-sites.md` — cross-referenced (not duplicated) from
      the new spawn-site concurrency-conformance test's docstring, so the two enumeration guards
      stay discoverable as siblings.

## Files Expected to Change

- `plugins/saga/scripts/execution_spec.py` — `ConcurrencyPolicy` dataclass, resolution ladder,
  `VERIFY_N_CAP` derivation, `max_concurrent` field, wave-chunking + panel-chunking emitter
  changes, aggregate in-flight guard.
- `plugins/saga/scripts/concurrency_governor.py` (proposed, new) — tier→weight table, weighted
  admission function, per-lane override resolution.
- `plugins/saga/scripts/team_emitter.py` — verify-panel fan-out routed through the chunking
  primitive (if panel emission lives here rather than `execution_spec.py`).
- `tests/test_concurrency_policy.py` — new resolution-ladder, chunking, read-only-lift,
  tier-weighting, per-lane-override, and aggregate-guard tests.
- `tests/test_concurrency_conformance.py` — new spawn-site conformance/drift-guard test.
- `plugins/saga/.claude-plugin/plugin.json`, `.claude-plugin/marketplace.json`,
  `plugins/saga/CHANGELOG.md` — release-surface updates.

## Tests to Add or Update

- `tests/test_concurrency_policy.py::test_resolution_ladder` — spec-default/env/run-override
  rungs each win at their level.
- `tests/test_concurrency_policy.py::test_invalid_override_fails_emit` — a non-positive/invalid
  cap fails `validate()` loudly.
- `tests/test_concurrency_policy.py::test_layer_wave_chunking` — a 6-unit layer renders two
  3-wide waves preserving dependency order.
- `tests/test_concurrency_policy.py::test_max_concurrent_field` — over-ceiling authoring fails
  emit; valid value round-trips via `to_dict`/`from_dict`.
- `tests/test_concurrency_policy.py::test_panel_chunking` — an n=7 verify panel emits no wave
  wider than the resolved cap.
- `tests/test_concurrency_policy.py::test_readonly_lift` — all-read-only layer chunks at 4; mixed
  layer chunks at 3.
- `tests/test_concurrency_policy.py::test_tier_weighted_admission` — cheap-tier wave admits more
  slots than expensive-tier wave under the same budget.
- `tests/test_concurrency_policy.py::test_per_lane_override` — engine-registry `max_concurrent`
  wins over tier-weighted/env/spec-default rungs for its lane.
- `tests/test_concurrency_policy.py::test_aggregate_guard` — layer × panel product over the
  fleet cap trips the guard; within-cap spec emits clean.
- `tests/test_concurrency_conformance.py::test_all_spawn_sites_route_through_policy` — red on an
  injected unbounded `parallel(...)` fixture at a new spawn site, green on the merged tree.

### Verification
```bash
# New concurrency-policy suite: ladder, chunking, read-only lift, tier weighting, per-lane, aggregate guard
uv run pytest tests/test_concurrency_policy.py -v

# Spawn-site conformance/drift guard
uv run pytest tests/test_concurrency_conformance.py -v

# Existing verify-panel bound regression stays green against the derived VERIFY_N_CAP
uv run pytest tests/test_execution_spec.py -k verify_panel

# Full repo gate (CI parity)
uv run pytest && uv run ruff format --check . && uv run ruff check . && uv run mypy plugins/ scripts/ tests/ --ignore-missing-imports
```
Expected: all green; deliberately reintroducing a stray cap literal or an unbounded `parallel(...)`
spawn site turns the corresponding new test red.

## Handoff Maturity

requirements-ready

## Suggested Next Action

Use `/plan <issue>` to create an implementation plan.

## Source Context

- Source: `docs/plans/plugin-fleet-ideation-2026-07-03/survivors/T13.json` (ids `T13-F1-2`,
  `T13-F1-1`, `T13-F4-7`, `T13-F6-6`, `T13-F3-3`, `T13-F2-7`, `T13-F3-8`, `T13-F6-7`, `T13-F1-7`)
- Source type: ideation survivors + issue-map consolidation
- Source title: Concurrency policy as a first-class ExecutionSpec block: wave-width cap,
  resolution ladder, tier/lane weighting, emit-time aggregate guard, spawn-site drift guard

### Context library links

_none_

### Files expected to change

- `plugins/saga/references/sandbox-spawn-sites.md`
- `plugins/saga/scripts/execution_spec.py`
- `plugins/saga/skills/plan/SKILL.md`
- `plugins/saga/.claude-plugin/plugin.json`
- `.claude-plugin/marketplace.json`
- `plugins/saga/CHANGELOG.md`
- `plugins/saga/scripts/concurrency_governor.py`
- `plugins/saga/scripts/team_emitter.py`

### Tests to add or update

- `tests/test_concurrency_conformance.py`
- `tests/test_concurrency_policy.py`
- `tests/test_execution_spec.py`

### Objective

"Govern fleet concurrency and reclaim leaked resources"

## Created Issue

- URL: https://github.com/infiquetra/infiquetra-claude-plugins/issues/350
- Number: 350
- Created at: 2026-07-04T07:46:26.338983+00:00

