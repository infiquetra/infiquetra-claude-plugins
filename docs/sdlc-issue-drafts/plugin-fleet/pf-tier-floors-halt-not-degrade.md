---
title: "enhancement: tier floors and backend enforceability — halt, never silently degrade or under-tier"
repo: infiquetra-claude-plugins
type: enhancement
team: campps
project: operations
status: Idea
labels: enhancement, hermes-task, needs-plan
risk: medium
handoff_maturity: requirements-ready
tier: structural
wave: wave-1
objective: "Make tier+effort a first-class priced resolvable lever"
---

# enhancement: tier floors and backend enforceability — halt, never silently degrade or under-tier

### Objective
Make tier+effort a first-class priced resolvable lever.

### Tier
structural

### Wave
wave-1

### Intent
Three independent mechanisms currently guarantee the same thing badly: a unit or teammate agent's
declared model/effort tier can be silently overridden downward with no failure signal. This issue
merges all three into one SpecError-flavored change so the ordered tier ladder gets both a ceiling
(existing upgrade-only ordering) and a floor (new), with unenforceable floors failing loud at emit
time rather than degrading silently at runtime:

1. **Backend-enforceability matrix** — a plan-authored `fable/xhigh` unit validates fine against the
   `MODELS`/`EFFORTS` vocabulary (`plugins/saga/scripts/execution_spec.py:52-53`) but when
   `team_emitter` renders it to team-execution markdown, the runtime spawns teammates by `agentType`
   and inherits the session-global tier — the `fable/xhigh` row the worker table shows is cosmetic,
   not enforced. Mirror the existing `SANDBOX_ENFORCEABLE_BY_BACKEND` pattern
   (`plugins/saga/scripts/execution_spec.py:105-109`, "unknown never permissive") with a new
   `TIER_ENFORCEABLE_BY_BACKEND` matrix: a backend that cannot spawn at an arbitrary `{model, effort}`
   (team-execution, today) HALTS at emit time when a unit's declared tier exceeds what it can honor,
   instead of emitting a table it will not obey.
2. **`Unit.min_tier` clamp in `segment_units()`** — `segment_units()` derives a merged segment's tier
   by upgrade-only index arithmetic, `min(MODELS.index(...))` / `max(EFFORTS.index(...))`
   (`plugins/saga/scripts/execution_spec.py:1474-1475`), which lets a cheap unit sharing a segment
   only ever be pulled *up*. There is no way to assert "this unit must never resolve below
   opus/high" as an invariant the merge respects — no floor concept, only ambient upgrade pressure.
   Add an optional `min_tier` field on `Unit` that `segment_units()` clamps the merged tier up to,
   and fail emit if a declared floor is itself off the `MODELS`/`EFFORTS` closed-set vocabulary.
3. **Agent-owned `tier-floor:` frontmatter** — every team-execution agent already pins a static
   `model:` in its frontmatter (verified: all 25 files under `plugins/team-execution/agents/*.md`
   carry `model:`, e.g. `security-reviewer.md:11` → `opus`, `security-scanner.md:8` → `haiku`; zero
   carry an `effort:` field). This is a hardcoded assignment, not an enforced floor: nothing in the
   spawn/spec path prevents a future per-teammate override (the QUEUED
   `{#team-execution-per-teammate-effort}` ask, and the still-open "no dispatch-time override lever"
   gap) from assigning a *lower* tier than the agent's intended minimum, and effort is not settable
   per-teammate at all today. Invert ownership: let a teammate declare its own tier floor in
   frontmatter (`tier-floor: opus/high`), and make any plan-assigned per-teammate tier merely
   escalate above that floor — clamped up, or a loud failure, never a silent downgrade.

### Problem / motivation
The fleet's tier vocabulary is an ordered escalation ladder by design — `MODELS = ("fable", "opus",
"sonnet", "haiku")` / `EFFORTS = ("low", "medium", "high", "xhigh")`
(`plugins/saga/scripts/execution_spec.py:52-53`), and the ordering is explicitly load-bearing per the
comment directly above it (`execution_spec.py:47-51`) and the engineering-journal learning at
`docs/engineering-journal/LEARNINGS.md:164` (`{#tier-vocab-ordering}` — "tier vocabulary tuples are
ordered escalation ladders, not just closed sets"). Today the ladder only has a ceiling
(`segment_units()`'s upgrade-only merge, `execution_spec.py:1474-1475`) and one existing enforceability
matrix for a different axis (`SANDBOX_ENFORCEABLE_BY_BACKEND`, `execution_spec.py:105-109`, halt-not-
degrade for restrictive sandbox values a backend cannot honor). There is no equivalent floor or
enforceability guarantee for tier itself, and three independent gaps compound this:

- **Grounding brief §1** ("Model/effort reality", `docs/plans/2026-07-03-plugin-fleet-grounding-brief.md:13-16`):
  "Every agent frontmatter across all 8 plugins hardcodes `model:` ..., zero `effort:` fields ..., no
  dispatch-time override lever anywhere except saga's readonly-verifier per-call pattern" and
  "`fable`/`xhigh` unreachable outside saga plan vocabulary." Verified directly: `grep` across
  `plugins/team-execution/agents/*.md` confirms all 25 agents pin `model:` and none pin `effort:`.
- team-execution's spawn path inherits the session-global tier rather than honoring a per-unit
  `{model, effort}` (`execution_spec.py:103-104`: "team-execution enforces neither restrictive axis
  ...; its residents run `bypassPermissions` with no per-leaf tool restriction" — the same
  under-enforcement shape, on a different axis, the sandbox matrix already exists to prevent for
  sandbox values).
- `segment_units()` has no floor concept — a security- or design-critical unit sharing a segment with
  a cheap unit can only be pulled up by chance of the merge math, never guaranteed a minimum
  (`execution_spec.py:1470-1477`).

The result is three variations on the same failure mode: a unit or teammate can silently run below
its intended tier, and nothing fails loud when that happens.

## Definition of Done
Merged `TIER_ENFORCEABLE_BY_BACKEND` matrix + `Unit.min_tier` clamp in `segment_units()` +
`tier-floor:` teammate frontmatter honored by the spawn path, all failing loudly rather than
silently degrading. All acceptance criteria below pass and the full repo gate (tests, format,
lint, mypy, bandit) stays green with no regression to the existing `segment_units()` golden tests.

### Out-of-scope / non-goals
### Out-of-scope / non-goals
- Building a general per-teammate effort-override mechanism end-to-end (the QUEUED
  `{#team-execution-per-teammate-effort}` ask) — this issue adds the floor/enforceability primitives
  the override mechanism would need to respect; it does not build the override UI/spawn-path plumbing
  itself.
- Adding `effort:` frontmatter to team-execution agents — out of scope; this issue only prevents
  silent downgrade of whatever tier is assigned (frontmatter-declared floor or plan-declared tier), it
  does not introduce a new effort-authoring surface.
- Changing `SANDBOX_ENFORCEABLE_BY_BACKEND` or any existing sandbox-axis behavior — the new
  `TIER_ENFORCEABLE_BY_BACKEND` matrix is a sibling structure, not a modification of the sandbox one.
- Backfilling `min_tier` or `tier-floor:` onto every existing unit/agent — both are optional fields;
  v1 does not mandate a floor everywhere, only enforces one where declared.
- Any inline-backend change — the inline backend already enforces arbitrary `{model, effort}` per
  call (readonly-verifier pattern) and is unaffected.

### Files expected to change
- `plugins/saga/scripts/execution_spec.py` — add `TIER_ENFORCEABLE_BY_BACKEND` matrix + a
  `tier_unenforceable(backend, tier)` helper (mirroring `SANDBOX_ENFORCEABLE_BY_BACKEND` at
  `execution_spec.py:105-109`); add optional `Unit.min_tier: Tier | None` field with validation
  against `MODELS`/`EFFORTS`; add the clamp-up in `segment_units()` alongside the existing
  upgrade-only merge at `execution_spec.py:1474-1475`.
- `plugins/saga/scripts/team_emitter.py` (or the team-execution emit path, exact module TBD by
  `/plan`) — wire `tier_unenforceable()` into the emit path to raise `SpecError` when a unit's tier
  exceeds what the target backend can honor.
- `plugins/team-execution/agents/*.md` — add an optional `tier-floor:` frontmatter field (documented,
  not backfilled onto every agent) and a doc note in `plugins/team-execution/README.md` or the
  relevant reference describing the new floor semantics.
- `plugins/team-execution/skills/team-execution/references/` — the spawn-path reference doc(s)
  governing how a plan's per-teammate tier assignment is read, updated to describe the floor-clamp
  behavior (exact file TBD by `/plan`, likely alongside `validator-execution-order.md` or the worker
  table reference).
- `tests/test_saga_execution_spec.py` — new cases per acceptance criteria below.
- `tests/test_team_emitter.py` (or equivalent emitter test module) — new case for the
  `TIER_ENFORCEABLE_BY_BACKEND` halt.
- `plugins/saga/CHANGELOG.md`, `plugins/saga/.claude-plugin/plugin.json` — version bump + changelog
  entry (execution_spec schema and emit-path behavior change).
- `plugins/team-execution/CHANGELOG.md`, `plugins/team-execution/.claude-plugin/plugin.json` —
  version bump + changelog entry (new frontmatter field + spawn-path clamp behavior).
- `.claude-plugin/marketplace.json` — version/metadata sync for both plugins per repo CLAUDE.md step 6.

### Tests to add or update
- `tests/test_saga_execution_spec.py::test_min_tier_pulls_cheap_segment_up` — a segment containing a
  unit with `min_tier=opus/high` and another cheaper unit merges to at least `opus/high`.
- `tests/test_saga_execution_spec.py::test_off_palette_min_tier_fails_emit` — a `Unit.min_tier` value
  outside `MODELS`/`EFFORTS` fails validation/emit with a named error.
- `tests/test_saga_execution_spec.py::test_absent_min_tier_round_trips_byte_identical` — a spec with
  no `min_tier` field round-trips through `to_dict`/`from_dict` unchanged (no new key emitted).
- `tests/test_team_emitter.py::test_fable_xhigh_unit_halts_on_non_enforcing_backend` — a `fable/xhigh`
  unit routed to `team-execution` (or another backend absent from `TIER_ENFORCEABLE_BY_BACKEND`) fails
  emit with `SpecError`; the same unit routed to an enforcing backend (e.g.
  `cc-workflows-ultracode`, or `inline`) passes.
- `tests/test_team_emitter.py::test_plan_assigning_below_floor_is_clamped_or_fails` — a plan's
  per-teammate table assigns `haiku` to a teammate whose frontmatter declares `tier-floor: opus/high`;
  assert the effective spawn tier is clamped up to the floor (or the emit fails loud, per the
  mechanism `/plan` selects) rather than silently spawning at `haiku`.
- Existing golden/spec tests (`tests/test_saga_execution_spec.py` current suite) remain green
  unchanged — no regression to the existing upgrade-only segment-merge behavior for specs without a
  `min_tier`/floor declared.

### Verification
```bash
uv run pytest tests/test_saga_execution_spec.py -k "min_tier or floor" -v
uv run pytest tests/test_team_emitter.py -k "tier_enforceable or floor or fable_xhigh" -v
uv run pytest && uv run ruff format --check . && uv run ruff check . && uv run mypy plugins/ scripts/ tests/ --ignore-missing-imports
uv run bandit -r plugins/
```
Expected: all new tests pass; full suite, formatting, linting, mypy, and bandit stay green with no
regressions to the existing `segment_units()` golden tests.

### Context library links
- source_context: docs/plans/2026-07-03-plugin-fleet-grounding-brief.md
- source_context: docs/plans/plugin-fleet-ideation-2026-07-03/survivors/T3.json (ids T3-F2-1, T3-F1-6, T3-F3-8)

### Acceptance criteria
- [ ] A `fable/xhigh` unit routed to a backend absent from `TIER_ENFORCEABLE_BY_BACKEND` (e.g.
  team-execution) fails emit with a named `SpecError`. Check:
  `uv run pytest tests/test_team_emitter.py -k test_fable_xhigh_unit_halts_on_non_enforcing_backend` →
  passes.
- [ ] The same `fable/xhigh` unit routed to a backend present in `TIER_ENFORCEABLE_BY_BACKEND` (e.g.
  `cc-workflows-ultracode` or `inline`) passes emit. Check:
  `uv run pytest tests/test_team_emitter.py -k test_fable_xhigh_unit_halts_on_non_enforcing_backend` →
  the enforcing-backend branch of the same test asserts a clean pass.
- [ ] A declared `Unit.min_tier` pulls a segment containing a cheaper unit up to at least the floor
  tier. Check: `uv run pytest tests/test_saga_execution_spec.py -k test_min_tier_pulls_cheap_segment_up`
  → passes.
- [ ] An off-palette `Unit.min_tier` (not drawn from `MODELS`/`EFFORTS`) fails emit with a named error.
  Check: `uv run pytest tests/test_saga_execution_spec.py -k test_off_palette_min_tier_fails_emit` →
  passes.
- [ ] A spec with no `min_tier` declared round-trips through `to_dict`/`from_dict` byte-identical (no
  new key emitted). Check:
  `uv run pytest tests/test_saga_execution_spec.py -k test_absent_min_tier_round_trips_byte_identical`
  → passes.
- [ ] A plan assigning a per-teammate tier below a teammate's `tier-floor:` frontmatter value is
  clamped up to the floor, or fails loud — never silently spawned below the floor. Check:
  `uv run pytest tests/test_team_emitter.py -k test_plan_assigning_below_floor_is_clamped_or_fails` →
  passes.
- [ ] Existing `segment_units()` golden tests remain unchanged for specs without a floor declared.
  Check: `uv run pytest tests/test_saga_execution_spec.py -v` → full existing suite green, no new
  failures.
- [ ] Full repo gate stays green. Check:
  `uv run pytest && uv run ruff format --check . && uv run ruff check . && uv run mypy plugins/ scripts/ tests/ --ignore-missing-imports && uv run bandit -r plugins/`
  → all pass.
- [ ] Release-surface artifacts updated in the same PR: `plugins/saga/.claude-plugin/plugin.json` and
  `plugins/team-execution/.claude-plugin/plugin.json` version bumps, both plugins' `CHANGELOG.md`
  entries, and `.claude-plugin/marketplace.json` metadata sync all reflect the new fields/behavior.
  Check: manual diff review confirms all four surfaces changed alongside the code diff.

## Recommended Executor Profile
- **Model:** sonnet
- **Effort:** medium
- **Backend:** inline
- **External LLM:** none
- **Justification:** mechanical, well-scoped extension of an existing, already-proven pattern
  (`SANDBOX_ENFORCEABLE_BY_BACKEND` / halt-not-degrade) to a sibling axis (tier), plus one new
  optional dataclass field and its validation/clamp logic. No novel architecture or judgment-heavy
  design work; does not warrant opus.

## Grounding References
- `T3-F2-1` (primary) — backend-enforceability matrix; basis: grounding brief §1 ("fable/xhigh
  unreachable outside saga plan vocabulary") + `execution_spec.py:96-109` (existing
  `SANDBOX_ENFORCEABLE_BY_BACKEND` halt-not-degrade template).
- `T3-F1-6` (facet) — `Unit.min_tier` clamp in `segment_units()`; basis: `execution_spec.py:1473-1475`
  (upgrade-only max merge, no floor) and `{#tier-vocab-ordering}`
  (`docs/engineering-journal/LEARNINGS.md:164`) — the floor must preserve the same ordered-index-
  arithmetic contract that learning protects, not add an unordered override.
- `T3-F3-8` (facet) — agent-owned `tier-floor:` frontmatter; basis: verified via direct grep that all
  25 `plugins/team-execution/agents/*.md` files pin `model:` (e.g. `security-reviewer.md:11`) and none
  pin `effort:`, corroborating grounding brief §1's "hardcodes `model:` ..., zero `effort:` fields ...,
  no dispatch-time override lever" and the still-open QUEUED
  `{#team-execution-per-teammate-effort}` ask this issue's floor primitive must not be violated by.
- Binding decision this builds on: `{#tier-vocab-ordering}` (`docs/engineering-journal/LEARNINGS.md:164`)
  — tier vocabulary ordering is load-bearing; any floor/clamp mechanism must be expressed as index
  arithmetic over the same `MODELS`/`EFFORTS` ordered tuples, not an unordered override.

### Handoff maturity
requirements-ready

### Suggested next action
Use `/plan <issue>` to create an implementation plan.

### Source context
- Source: docs/plans/2026-07-03-plugin-fleet-grounding-brief.md
- Source type: brief
- Source title: Grounding Brief — Plugin-Fleet Ideation (Gate B)

## Created Issue

- URL: https://github.com/infiquetra/infiquetra-claude-plugins/issues/369
- Number: 369
- Created at: 2026-07-04T07:51:58.570599+00:00

