---
title: "capability: effort becomes a real, authored, injected, and honored field fleet-wide"
repo: infiquetra-claude-plugins
type: capability
tier: structural
objective: "Make tier+effort a first-class priced resolvable lever"
wave: wave-1
team: campps
project: operations
status: Idea
labels: capability, hermes-task, needs-plan
risk: medium
handoff_maturity: requirements-ready
---

# capability: effort becomes a real, authored, injected, and honored field fleet-wide

### Objective
Make tier+effort a first-class priced resolvable lever

## Summary

`model:` is a real, honored, per-agent frontmatter field across all 8 plugins. `effort:` is not —
it exists in exactly one place (saga's `/plan` unit-tier table and the readonly-verifier per-call
override) and evaporates everywhere else. This capability makes `effort` a first-class field:
authored in agent frontmatter and the team-execution A7 worker table, validated against a shared
vocabulary, injected at spawn time via a prompt-preamble rider (not gated on a harness feature that
doesn't exist yet), reconciled after the fact when a teammate silently ran at the wrong effort, and
lint-guarded in CI so the fleet can't silently regress once it's real.

## Problem Frame

Today the fleet has exactly one operator-facing model/effort lever: saga `/plan`'s per-unit tier
table (`plugins/saga/skills/plan/SKILL.md:295-296`, Step 1 — Derive per-unit tiers), which assigns
a `{model, effort}` pair from a work-shape heuristic and validates it via
`plugins/saga/scripts/execution_spec.py` — where the vocabulary lives as
`MODELS = ("fable", "opus", "sonnet", "haiku")` and `EFFORTS = ("low", "medium", "high", "xhigh")`
(`execution_spec.py:52-53`). That vocabulary is real and enforced by `ExecutionSpec.validate`
(hard-blocks on a malformed spec per the Step 4 gate in `plan/SKILL.md`) — but only for units routed
through the `cc-workflows-ultracode` backend.

Every agent frontmatter across all 8 plugins hardcodes `model:` (confirmed: `grep -rln "^model:"
plugins/*/agents/*.md` returns 33 files; team-execution alone carries 25 agents each declaring
`model: opus|sonnet|haiku`) and zero of them carry an `effort:` field (confirmed: `grep -rln
"^effort:" plugins/*/agents/*.md` returns nothing). The one place effort is dispatched per-call
today is saga's `readonly-verifier` agent (`plugins/saga/agents/readonly-verifier.md:14`): "The
per-call model/effort opts the emitter passes override this file's `model:` default so the panel
runs at the same tier as the unit it verifies." That pattern is real but singular — it is not a
convention any other agent or plugin follows, and nothing generalizes it.

team-execution's Step A7 worker table (`plugins/team-execution/skills/team-execution/SKILL.md:218-233`)
already renders a `Tier` column (e.g. `opus/high`) per worker row today, but it is free text in a
markdown table — nothing parses or validates it, and nothing carries it forward into the actual
`agent()` spawn call, so an authored `high` effort in the plan is never actually injected anywhere.
This is exactly the gap the engineering journal already named and queued: "Plan-dictated per-teammate
effort levels for `/work` + team-execution" (`docs/engineering-journal/QUEUED.md:416`, anchor
`{#team-execution-per-teammate-effort}`), noting effort "only exists inside Workflow script
(`agent(..., {effort})`)," that team-execution spawns subagents by `type` so "all teammates inherit
one session-global effort," and flagging the entry itself as blocked pending the harness shipping an
`effort:` agent-frontmatter field — priority "P3 (→ P2 once Claude Code ships `effort:`
agent-frontmatter field)". This capability does not wait for that harness feature: it builds the
frontmatter convention, validation, and a prompt-preamble injection shim ourselves now, the same way
`BUDGET_RIDER` (`plugins/saga/scripts/execution_spec.py:122`, injected at `:883` and `:1130`) already
proves that a prompt-level rider can carry a directive to a spawned agent without a native harness
knob — this generalizes that exact proven pattern to effort.

Related decisions this work must stay inside: `{#external-engine-chaperone-dispatch}`
(`docs/engineering-journal/DECISIONS.md:2021`) already fixes offload-worker effort at
sonnet/medium and second-opinion-worker effort at opus/high for external-engine workers — this
capability's per-teammate effort cascade must not let a plan or scaffold override those two fixed
rows.

## Requirements

**Frontmatter (R1–R3)**

R1. Every agent `.md` across all 8 plugins may declare an `effort:` frontmatter field. Where present,
its value MUST be one of `EFFORTS = ("low", "medium", "high", "xhigh")`
(`plugins/saga/scripts/execution_spec.py:53`) — the same vocabulary `/plan` already validates
against, so the fleet has exactly one effort vocabulary, not two.

R2. A lint test (mirroring the existing model-pinning pattern in `tests/test_agent_tiering.py`)
parses every agent `.md`'s frontmatter and asserts: every `effort:` value present is in `EFFORTS`;
every `model:` value present is in `MODELS`. An out-of-vocabulary value on either field fails the
test.

R3. The lint runs in CI (a `scripts/lint_agent_tiers.py` wired into the existing pytest/CI step, per
`T3-F4-6`'s outcome shape) so a hand-authored typo (`effort: extreme`) is caught before merge, not
discovered at spawn time.

**Team-execution A7 worker table (R4–R6)**

R4. The Step A7 worker table's `Tier` column (`plugins/team-execution/skills/team-execution/SKILL.md:218-233`)
is parsed by `team_emitter.py` into a structured `{model, effort}` pair per worker row, not left as
free text. An off-palette effort value in the authored table raises the same validation error as a
frontmatter violation (R1/R2).

R5. Effort resolution is a three-layer cascade, most-specific wins: plan-authored per-unit tier
(`/plan`'s Step 1 table) → team-level default → per-teammate agent-frontmatter default (R1). The
emitted worker table records which layer resolved each teammate's effort (a provenance line, not
just the final value), so a reviewer can see whether a teammate's `high` came from the plan or fell
back to its agent's own default.

R6. External-engine chaperone workers (`{#external-engine-chaperone-dispatch}`,
`docs/engineering-journal/DECISIONS.md:2021`) are excluded from the R5 cascade for effort: an
offload-intent worker is always sonnet/medium and a second-opinion-intent worker is always
opus/high, regardless of what the cascade would otherwise resolve.

**Spawn-time injection (R7–R8)**

R7. A generalized `EFFORT_RIDER` table (structurally mirroring `BUDGET_RIDER`,
`plugins/saga/scripts/execution_spec.py:122`) maps each `EFFORTS` value to a short prompt-preamble
directive string. team-execution's dispatch path prepends the resolved effort's rider text to a
spawned teammate's prompt at `agent()` call time — this is the injection mechanism, since no native
harness `effort` dispatch parameter exists yet for subagent-type spawns (per the QUEUED blocker,
`docs/engineering-journal/QUEUED.md:416`).

R8. This rider mechanism is documented once as the fleet's `effort:` convention (a reference doc,
not duplicated per-plugin) and applied to at least the agy and deploy plugin's agents in addition
to team-execution and saga, so the convention is proven cross-plugin, not saga-only.

**Reconciliation (R9)**

R9. A post-run reconciliation step compares each teammate's plan-authored (or cascade-resolved)
effort against what actually reached the spawn call. A mismatch — the "silently ran at
session-global effort" case named by `T3-F1-4` — emits a named tiering-drift line in the run's
output. A matching run emits nothing.

## Key Flows

F1. **Authoring.** A plan author fills the A7 worker table's `Tier` column; `team_emitter.py`
parses and validates it (R4), applies the R5 cascade for any teammate without an explicit tier, and
excludes chaperone workers from the cascade (R6).
**Covers R4, R5, R6.**

F2. **Spawn.** team-execution dispatches each worker via `agent()`; the resolved effort's
`EFFORT_RIDER` text is prepended to that worker's prompt preamble before the call.
**Covers R7, R8.**

F3. **Reconciliation.** After the run, the resolved-vs-actual effort comparison runs; a mismatch
emits a tiering-drift line, a match emits nothing.
**Covers R9.**

F4. **CI guard.** On every PR, the frontmatter lint (R2/R3) scans `plugins/*/agents/*.md` for
`model:`/`effort:` values outside `MODELS`/`EFFORTS` and fails the build on a violation.
**Covers R1, R2, R3.**

### Acceptance criteria
- [ ] AC1 (R1/R2). A seeded agent frontmatter with `effort: extreme` (out-of-vocabulary) fails
  `tests/test_agent_tier_lint.py`; the same fixture with `effort: high` passes. Check:
  `uv run pytest tests/test_agent_tier_lint.py -v` → the out-of-vocab fixture case fails before the
  fix exists and passes once the lint is wired; the seeded fleet passes.
- [ ] AC2 (R3). CI runs the lint against the real fleet (`plugins/*/agents/*.md`) as a required
  step, not just locally. Check: the CI workflow file includes a step invoking
  `scripts/lint_agent_tiers.py` (or the pytest entry point) and a run of it against current
  `plugins/*/agents/*.md` exits 0.
- [ ] AC3 (R4). A golden A7 worker table with a structured `{model, effort}` per row is parsed into
  validated data by `team_emitter.py`; an off-palette effort value in that table raises. Check:
  `uv run pytest tests/test_team_emitter.py -k worker_effort -v` → both the valid-pair case and the
  off-palette-raises case pass.
- [ ] AC4 (R5). The emitted worker table names which cascade layer resolved each teammate's effort
  (plan / team / agent-default). Check: `uv run pytest tests/test_team_emitter.py -k
  cascade_provenance -v` → a golden-file assertion shows the source layer per teammate.
- [ ] AC5 (R6). A chaperone worker's effort is never overridden by the R5 cascade even when the
  cascade would otherwise resolve differently. Check: `uv run pytest tests/test_team_emitter.py -k
  chaperone_effort_fixed -v` passes for both offload (sonnet/medium) and second-opinion
  (opus/high) intents.
- [ ] AC6 (R7). A teammate authored with `effort: high` receives the `EFFORT_RIDER` text for
  `high` in its dispatch prompt. Check: `uv run pytest tests/test_team_emitter.py -k
  effort_rider_injected -v` — asserts the rider string appears in the constructed spawn prompt/opts.
- [ ] AC7 (R8). The `effort:` convention doc exists once and at least one agy and one deploy plugin
  agent carry a validated `effort:` field consuming it. Check: `grep -rl "^effort:"
  plugins/agy/agents/*.md plugins/deploy/agents/*.md` returns at least one file each; the lint (AC1)
  passes on them.
- [ ] AC8 (R9). A run where a teammate's actual dispatched effort diverges from its
  plan/cascade-resolved effort emits a named tiering-drift line; a matching run emits none. Check:
  `uv run pytest tests/test_team_emitter.py -k tiering_drift -v` — both the mismatch and match cases
  pass.
- [ ] Full suite, format, lint, types stay green. Check: `uv run pytest && uv run ruff format
  --check . && uv run ruff check . && uv run mypy plugins/ scripts/ tests/ --ignore-missing-imports`
  → all pass.

## Definition of Done

- All AC1–AC8 acceptance-criteria checks pass (frontmatter lint, A7 worker-table parsing, cascade
  provenance, chaperone-effort fixing, rider injection, and reconciliation drift detection), and the
  full suite stays green: `uv run pytest && uv run ruff format --check . && uv run ruff check . &&
  uv run mypy plugins/ scripts/ tests/ --ignore-missing-imports`.
- The fleet-wide frontmatter lint (`scripts/lint_agent_tiers.py` or its pytest entry point) runs in
  CI as a required step and exits 0 against the real `plugins/*/agents/*.md` fleet.
- The Release-Surface Checklist below is fully completed in the same PR (plugin.json/marketplace.json
  version bumps, CHANGELOGs, drift-guard tests, and the `QUEUED.md`/`DECISIONS.md` journal updates).

### Out-of-scope / non-goals
- **In scope:** `effort:` frontmatter convention + lint (R1–R3); A7 worker-table parsing/validation
  and the plan→team→agent cascade (R4–R6); the `EFFORT_RIDER` prompt-preamble injection shim
  (R7–R8); post-run reconciliation/drift detection (R9).
- **Out of scope / non-goals:**
  - A native harness-level `effort:` dispatch parameter for subagent-type spawns. This capability
    is explicitly the pre-harness shim (per `docs/engineering-journal/QUEUED.md:416`'s stated
    blocker); when Claude Code ships a real `effort` dispatch option, migrating the injection
    mechanism off the prompt-preamble rider onto that native option is separate follow-on work.
  - The scaffold-time per-teammate agent-variant generator (`T3-F1-8`, tier_guess: moonshot) that
    would mint physically distinct per-tier agent files at `team-scaffold` time. That is a larger,
    separately-tiered idea (moonshot, not structural) and is not bundled into this capability.
  - Changing the `MODELS`/`EFFORTS` vocabulary itself (e.g. reaching `fable`/`xhigh` outside the
    saga `/plan` path). Per the grounding brief, `fable`/`xhigh` remain unreachable outside saga
    plan vocabulary — this capability propagates the existing four-value `EFFORTS` set, it does not
    expand where the outer two values can be used.
  - Any change to `VERIFY_N_CAP` or the verify-panel N-sizing logic (`execution_spec.py:114`) —
    unrelated axis, no facet here touches panel sizing.
  - Backfilling `effort:` onto every agent in every plugin in one pass. R8 requires proving the
    convention on agy + deploy in addition to saga/team-execution; full fleet-wide backfill across
    home-lab-ops/redis-channel/unifi/mission-control is a follow-on, not a blocking condition of
    this issue.

## Dependencies / Assumptions

- `MODELS`/`EFFORTS` vocabulary already exists and is enforced for the `cc-workflows-ultracode`
  backend path (`plugins/saga/scripts/execution_spec.py:52-53`); this capability reuses it verbatim
  rather than inventing a second vocabulary.
- `BUDGET_RIDER` (`plugins/saga/scripts/execution_spec.py:122`, injected at `:883`/`:1130`) is the
  proven precedent that a prompt-preamble rider can carry a directive into a spawned agent's context
  without a native dispatch parameter — `EFFORT_RIDER` is a structural mirror of this, not a new
  mechanism.
- `plugins/saga/agents/readonly-verifier.md:14` is the one existing per-call effort-override
  precedent in the fleet; this capability generalizes it, it does not replace saga's readonly-verifier
  behavior.
- team-execution's Step A7 (`plugins/team-execution/skills/team-execution/SKILL.md:218-233`) already
  renders a `Tier` column today as free text — the parsing/validation this capability adds is net
  new; the column itself is not.
- `tests/test_agent_tiering.py` already exists and parses agent frontmatter for `model:` pinning
  (`_parse_frontmatter` helper) — the new lint (R2/R3) extends this existing parsing pattern rather
  than inventing a new YAML-frontmatter parser.
- `docs/engineering-journal/QUEUED.md:416` (`{#team-execution-per-teammate-effort}`) is the direct
  operator ask this capability answers ("why can't I pick effort?") and explicitly names the
  blocking condition (no native `effort:` harness field) that this capability's rider-shim works
  around rather than waits on.
- `{#external-engine-chaperone-dispatch}` (`docs/engineering-journal/DECISIONS.md:2021`) fixes
  chaperone-worker effort; R6 is a hard constraint derived from that decision, not a new design
  choice.

## Grounding References

| Absorbed id | Role | Basis (reconstructed) |
|---|---|---|
| `T3-F2-3` | primary | Generalize the readonly-verifier per-call effort pattern (`plugins/saga/agents/readonly-verifier.md:14`) into an `effort:` frontmatter convention + spawn shim, applied to agy+deploy agents. |
| `T3-F4-3` | facet | Declare-and-validate `effort:` in agent frontmatter ahead of any spawn-path consumer; lint asserts every value is in `EFFORTS`, every model in `MODELS`. |
| `T3-F4-6` | facet | Fleet-wide agent-frontmatter tier lint wired into CI (`scripts/lint_agent_tiers.py` + CI step), scanning `plugins/*/agents/*.md`. |
| `T3-F3-3` | facet | Inject effort at spawn now via a prompt-preamble shim (`EFFORT_RIDER`, mirroring `BUDGET_RIDER` at `execution_spec.py:122`) rather than waiting on a native harness dispatch parameter. |
| `T3-F1-3` | facet | Make effort a real, authored, validated field in the team-execution A7 worker table (structured `{model, effort}` per row), not a free-text comment. |
| `T3-F1-4` | facet | Post-run reconciliation: detect and name (tiering-drift line) when a teammate silently ran at session-global effort instead of its authored/resolved effort. |
| `T3-F5-5` | facet | Per-teammate effort as a three-layer cascade (plan → team → per-teammate, most-specific wins) with a resolved-tier provenance trail in the emitted worker table. |
| `T3-F1-8` | facet (descoped) | Scaffold-time per-teammate tier-variant generator — tier_guess `moonshot`; explicitly excluded from this issue's scope (see Scope Boundaries) and left as a separate follow-on candidate. |

Binding decisions this issue must not violate:
- `{#external-engine-chaperone-dispatch}` (`docs/engineering-journal/DECISIONS.md:2021`) — chaperone
  worker effort is fixed by intent, never cascade-resolved (R6).
- `{#tier-vocab-ordering}` (per grounding brief §3) — tier tuples are ordered escalation ladders, not
  arbitrary closed sets; the `EFFORTS` ordering (`low < medium < high < xhigh`) must be preserved
  wherever this capability compares or ranks effort values (e.g. cascade "most-specific wins" is a
  precedence rule, not a magnitude comparison, and must not be conflated with one).
- Direct operator ask: `{#team-execution-per-teammate-effort}`
  (`docs/engineering-journal/QUEUED.md:416`) — this issue is the concrete resolution of that queued
  item; close/update the QUEUED entry in the same PR once this ships.

## Recommended Executor Profile

- **Model:** sonnet
- **Effort:** high — *target posture: not a live team-execution dispatch knob until `pf-effort-first-class` lands; teammates inherit session tier until then*
- **Backend:** team-execution
- **External-LLM posture:** none
- **Justification:** This is schema/convention design (a new frontmatter vocabulary rule, a
  validated cascade, a prompt-injection shim) plus mechanical propagation across existing parsing
  code (`team_emitter.py`, `tests/test_agent_tiering.py`'s frontmatter parser) — bounded,
  deterministic transforms with a clear existing pattern to mirror (`BUDGET_RIDER`), not open-ended
  architectural judgment. Sonnet/high (rather than opus) matches the "mechanical, deterministic,
  scripted transform" tier from `/plan`'s own Step 1 heuristic (`plugins/saga/skills/plan/SKILL.md:295-296`)
  applied to this exact unit shape; high effort (rather than medium) is warranted because the
  three-layer cascade (R5/R6) and chaperone-exclusion interaction are easy to get subtly wrong and
  worth the extra reasoning depth before landing. No external engine is involved; this is
  in-repo Claude work with no offload/second-opinion role to route.

## Release-Surface Checklist

This capability changes agent-facing frontmatter conventions, team-execution's emitted plan
artifact shape, and adds a new CI lint — all plugin-behavior changes requiring the full release
surface update in the same PR:

- [ ] `plugins/saga/.claude-plugin/plugin.json` — version bump if the `effort:` convention doc or
  `EFFORT_RIDER` lands under saga (readonly-verifier generalization, R7/R8).
- [ ] `plugins/team-execution/.claude-plugin/plugin.json` — version bump for the A7 worker-table
  parsing/validation change (R4) and the cascade (R5/R6); current version `2.9.0`.
- [ ] `plugins/agy/.claude-plugin/plugin.json` and `plugins/deploy/.claude-plugin/plugin.json` —
  version bump for the `effort:` field added to at least one agent each (R8).
- [ ] `.claude-plugin/marketplace.json` — update the version string for every plugin bumped above
  (saga is currently listed at `0.51.0`, team-execution at `2.9.0`).
- [ ] `plugins/saga/CHANGELOG.md`, `plugins/team-execution/CHANGELOG.md`,
  `plugins/agy/CHANGELOG.md`, `plugins/deploy/CHANGELOG.md` — an entry each describing the
  `effort:` convention, the A7 cascade, and the new lint.
- [ ] Drift-guard tests: extend `tests/test_agent_tiering.py` (or a new
  `tests/test_agent_tier_lint.py`) so a version/metadata mismatch between a plugin's `plugin.json`
  and `marketplace.json` entry is caught the same way frontmatter drift is caught — do not treat
  the PR as ready until installed-plugin metadata tells the same story as the diff.
- [ ] Update `docs/engineering-journal/QUEUED.md:416` (`{#team-execution-per-teammate-effort}`) to
  reflect that this item has shipped (or move it to `ARCHIVE.md` per the journal's normal
  lifecycle), and add a `DECISIONS.md` entry recording the rider-shim-before-native-harness-field
  choice (rationale + "revisit when Claude Code ships a native `effort:` dispatch parameter").

### Files expected to change (indicative — `/plan` determines the exact set)

- `plugins/saga/agents/readonly-verifier.md` — generalize the per-call effort-override doc comment
  into a pointer at the new fleet-wide convention doc.
- `plugins/saga/references/` (new file) — the `effort:` frontmatter convention + `EFFORT_RIDER`
  documentation.
- `plugins/saga/scripts/execution_spec.py` — add `EFFORT_RIDER` table alongside the existing
  `BUDGET_RIDER` (`:122`).
- `plugins/team-execution/skills/team-execution/SKILL.md` — Step A7 worker-table spec update
  documenting the structured `{model, effort}` column and cascade.
- `plugins/saga/scripts/team_emitter.py` — parse/validate the A7 worker table, implement the
  cascade (R5/R6), inject the `EFFORT_RIDER` at spawn (R7), and emit the reconciliation drift line
  (R9).
- `plugins/agy/agents/*.md`, `plugins/deploy/agents/*.md` — add a validated `effort:` field to at
  least one agent each (R8).
- `scripts/lint_agent_tiers.py` (new) — CI-facing lint entry point (R3).
- `tests/test_agent_tier_lint.py` (new) or extension of `tests/test_agent_tiering.py` — R1/R2
  coverage.
- `tests/test_team_emitter.py` — new cases for R4–R7, R9 (worker_effort, cascade_provenance,
  chaperone_effort_fixed, effort_rider_injected, tiering_drift).
- `docs/engineering-journal/QUEUED.md`, `docs/engineering-journal/DECISIONS.md` — journal updates
  per the Release-Surface Checklist.

### Tests to add or update

- Frontmatter lint: out-of-vocab `effort:`/`model:` value fails; valid values pass; runs against the
  real seeded fleet.
- A7 worker-table parsing: valid `{model, effort}` pair parses; off-palette effort raises.
- Cascade: plan-level tier wins over team-level; team-level wins over agent-default; provenance
  line names the winning layer.
- Chaperone exclusion: offload/second-opinion worker effort is never touched by the cascade.
- Rider injection: `effort: high` on a worker yields the `high` `EFFORT_RIDER` text in its dispatch
  prompt/opts.
- Reconciliation: divergent planned-vs-actual effort emits a named tiering-drift line; matching
  emits none.

### Verification

```bash
# New/updated unit coverage for this capability
uv run pytest tests/test_agent_tier_lint.py tests/test_team_emitter.py -v

# Fleet-wide frontmatter lint (CI parity)
python3 scripts/lint_agent_tiers.py plugins/*/agents/*.md

# Full repo gate
uv run pytest && uv run ruff format --check . && uv run ruff check . && \
  uv run mypy plugins/ scripts/ tests/ --ignore-missing-imports
```
Expected: all green; the lint exits 0 against the real fleet and nonzero against a seeded
out-of-vocabulary fixture.

### Handoff maturity
requirements-ready

### Suggested next action
Use `/plan <issue>` to create an implementation plan.

### Source context
- Source: mission-control ideation issue-map (`ideation/issue-map/issue-map-final.json`, slug
  `pf-effort-first-class`), plugin-fleet ideation 2026-07-03.
- Source type: ideation (multi-facet consolidation)
- Source title: Effort becomes a real, authored, injected, and honored field fleet-wide

### Intent

`model:` is a real, honored, per-agent frontmatter field across all 8 plugins. `effort:` is not — it exists in exactly one place (saga's `/plan` unit-tier table and the readonly-verifier per-call override) and evaporates everywhere else. This capability makes `effort` a first-class field: authored in agent frontmatter and the team-execution A7 worker table, validated against a shared vocabulary, injected at spawn time via a prompt-preamble rider (not gated on a harness feature that doesn't exist yet), reconciled after the fact when a teammate silently ran at the wrong effort, and lint-guarded in CI so the fleet can't silently regress once it's real.

### Context library links

_none_

### Files expected to change

- `plugins/saga/scripts/execution_spec.py`
- `plan/SKILL.md`
- `tests/test_agent_tiering.py`
- `scripts/lint_agent_tiers.py`
- `tests/test_agent_tier_lint.py`
- `plugins/saga/.claude-plugin/plugin.json`
- `plugins/team-execution/.claude-plugin/plugin.json`
- `plugins/agy/.claude-plugin/plugin.json`

## Created Issue

- URL: https://github.com/infiquetra/infiquetra-claude-plugins/issues/363
- Number: 363
- Created at: 2026-07-04T07:50:27.317996+00:00

