---
title: "Dispatch-time tier resolver — one seam mapping (role-class, work-shape, overrides) to {model, effort}"
type: feat
status: active
date: 2026-07-05
origin: docs/sdlc-issue-drafts/plugin-fleet/pf-dispatch-tier-resolver.md
---

# Dispatch-time tier resolver — one seam mapping (role-class, work-shape, overrides) to {model, effort}

## Summary

Build one callable resolver, `fleet_commons/tier_resolver.py`, that maps `(role_kind, work_shape, envelope_ceiling, operator_override)` to a `{model, effort, because, cheaper_fallback}` result, reading its defaults from a machine-readable work-shape→tier registry and its ladder math from the already-shipped `fleet_commons/tier_palette.py`. Migrate team-execution's 25 agent frontmatters from a bare `model:` literal to a registry-resolved `role-tier:`, render `/plan`'s Step-1 tier table from the same registry (drift-guarded), gate expensive tiers (`fable`/`xhigh`) behind an operator confirm flag, and enumerate the fleet's dispatch sites in a routing drift-guard. This is the tier-resolution half of issue #362; effort *honoring* at dispatch is #363's and the vocabulary *source*/ladder ops are #370's.

## Problem Frame

Today a model/effort tier is chosen in N ad-hoc places — 25 hardcoded `model:` literals in team-execution frontmatter, a prose-only heuristic table at `plugins/saga/skills/plan/SKILL.md:298-304`, and per-call literals — with nothing callable that resolves a tier from a role/work-shape. `execution_spec.py` only *validates* tiers against the closed sets; it never *resolves* one. This capability collapses those surfaces into a single resolver every spawn site can funnel through, so a tiering-policy change becomes a registry edit rather than a 25-file sweep, and `fable`/`xhigh` become reachable (behind a gate) outside the `/plan` vocabulary.

## Scope decision (operator-confirmed, 2026-07-05)

This issue stays a **parallel frontier root**; it does not absorb its siblings:

- **Effort *honoring* at team-execution dispatch → #363.** Grounding confirmed team-execution spawns via the **Agent tool**, which has **no per-call effort parameter** (`team-execution/skills/team-execution/SKILL.md:308`, `consensus-protocol.md:26`). #362 *emits* per-teammate effort into the plan/worker tables; #363 (effort-first-class) owns making it honored. Concern filed on #363.
- **Vocabulary source + ladder ops (`escalate`/`downgrade`/`clamp`) + repo-wide bare-literal guard → #370.** #362 builds on `tier_palette.py`'s existing `model_rank`/`effort_rank`; #370 owns the richer ladder + `models.json`. Concern filed on #370.

## Requirements

R1. A callable resolver at `plugins/fleet-core/scripts/fleet_commons/tier_resolver.py` exposes `resolve(work_shape, role_kind=None, envelope_ceiling=None, operator_override=None) -> Resolution`, where `Resolution` carries `model`, `effort`, `because` (a rationale string), `cheaper_fallback` (a `{model, effort}` exactly one rung down the ladder), and `needs_confirm` (bool). `work_shape` is the primary registry key; `role_kind` is an optional coarse refiner (reserved in v1). A `role-tier:` frontmatter value maps to a `work_shape` via a small alias map, then resolves through the registry. `envelope_ceiling` is an optional forward-compat clamp (a caller-supplied upper tier bound): #362 has no live ceiling source, so it is honored when supplied and ignored when `None`, letting the spend-envelope work (#366) wire it later without a signature change. It imports `MODELS`, `EFFORTS`, `model_rank`, `effort_rank` from `tier_palette` via `fleet_commons_shim` — never re-declaring the tuples.

R2. A machine-readable work-shape→tier registry `plugins/fleet-core/scripts/fleet_commons/tier_policy.json` holds one row per work-shape key (mirroring the rows at `plugins/saga/skills/plan/SKILL.md:298-304`), each with `{default_model, default_effort, rationale}`. Because `plan/SKILL.md:301` splits "Mechanical" into `sonnet/medium` and `haiku/low` ("purely mechanical"), the registry represents these as two keys (`mechanical`, `purely-mechanical`) so the resolver returns a single unambiguous tier — this is what lets the role-tier migration preserve the haiku-vs-sonnet distinction. The resolver reads defaults from it; nothing hardcodes the heuristic in code.

R3. `cheaper_fallback` steps exactly one rung down the ordered ladder per `{#tier-vocab-ordering}`: weaken the model by one `MODELS` rung (`model_rank+1`); if already the weakest model, drop effort by one `EFFORTS` rung (`effort_rank-1`) instead. At the ladder floor (weakest model, lowest effort) the fallback equals the resolved tier (a no-op floor, not an error).

R4. Resolving to an expensive tier (`fable` model or `xhigh` effort) sets `needs_confirm=True` on the `Resolution`; every other tier sets it `False`. The resolver never prompts — it returns the flag and the caller enforces the gate (keeps the resolver a pure function; honors `{#operator-choice-framework}`).

R5. All 25 `team-execution` agent frontmatters (`plugins/team-execution/agents/*.md`) declare a `role-tier:` that resolves through the registry to a `MODELS`/`EFFORTS` member. The existing `model:` field is retained as a last-resort fallback (used only when the registry is unavailable), never the primary source of truth.

R6. `/plan`'s Step-1 tier table renders from `tier_policy.json`, and a drift-guard test fails if the `SKILL.md` prose table and the registry diverge.

R7. `/plan`'s unit tier table and team-execution's A7 worker table carry a per-teammate `effort` value emitted from the resolver (the emission half — honoring is #363). A spawn-site enumeration test lists the fleet's dispatch sites (from the grounding inventory) and asserts each routes its tier decision through the resolver/registry, failing if a new bare palette literal appears at an enumerated site.

R8. Release surfaces updated in the same PR: `plugins/saga` and `plugins/team-execution` `plugin.json` bumps, `.claude-plugin/marketplace.json`, both `CHANGELOG.md`s, and the metadata drift-guard test. `fleet-core`'s surface is bumped if the resolver counts as a fleet-core behavior change.

## Key Technical Decisions

KTD1: **Resolver + registry live in `fleet_commons`, not `saga/scripts`** (operator-decided). The vocabulary it builds on (`tier_palette.py`) is fleet-core, and the resolver is consumed cross-plugin (saga, team-execution, the workflow emitter); `executor_profile_lint.py:89` already proves the `fleet_commons_shim.load(...)` consumption pattern. This overrides the Gate E draft's proposed `plugins/saga/scripts/tier_resolver.py`.

KTD2: **Build on `tier_palette.py`, do not create a competing vocabulary.** `cheaper_fallback`'s ladder math uses the shipped `model_rank`/`effort_rank` (#463), so #362 does not block on #370's `escalate`/`downgrade`/`clamp`. When #370 lands those named ops, the resolver migrates its inline rank math onto them (a later, mechanical swap).

KTD3: **`cheaper_fallback` = weaken model first, then effort.** Cheaper means a weaker model (one `MODELS` rung, since `MODELS` is strongest-first) before a lower effort. This is deterministic and matches operator intuition ("drop to the next cheaper model before giving up reasoning depth"). The floor is a no-op, never an exception.

KTD4: **The expensive-tier gate is a return flag, not a prompt.** `resolve()` sets `needs_confirm` when `model=="fable"` or `effort=="xhigh"`; the caller (`/plan` authoring, a future dispatch site) owns the pause. Rationale: the resolver stays pure/testable and `{#operator-choice-framework}` keeps operator choice doc/CLI-driven, not a runtime-injected prompt per spawn.

KTD5: **`role-tier:` migration keeps `model:` as a fallback (backward-compatible).** Each of the 25 frontmatters gains a `role-tier:`; the pre-existing `model:` is demoted to a documented last-resort value used only if the registry can't be loaded. Nothing breaks if `fleet_commons` is briefly unavailable, and the migration is reviewable one file at a time.

KTD6: **Effort is emitted, not honored (scope fence with #363).** The resolver returns `effort` and the plan/worker tables carry it, but #362 adds no dispatch-time honoring — the Agent tool has no effort knob, and that mechanism is #363's `EFFORT_RIDER`/cascade. The A7 worker-table schema #362 emits into must match what #363 parses; that alignment is called out in the #363 comment.

KTD7: **`role-tier` is a small agent-facing vocabulary mapping to work-shape registry keys, and the team-execution migration is tier-preserving.** The team-execution role suffix maps cleanly to the current model — verified: all 10 `*-reviewer` = opus, all 8 `*-tester` = sonnet, all 7 `*-scanner`/`*-monitor`/`deploy-watcher` = haiku — so three role-tier values preserve every agent's tier: `adversarial-review` → opus/high (reviewers), `contract-test` → sonnet/medium (testers), `mechanical-scan` → haiku/low (scanners/monitors). Each role-tier resolves to its `{model, effort}` through the registry's work-shape rows (`adversarial-review`→`judgment`, `contract-test`→`mechanical`, `mechanical-scan`→`purely-mechanical` — the sonnet-vs-haiku split the heuristic already names at `plan/SKILL.md:301`). `read-only-survey`→sonnet/low and `orchestration`→opus/high are reserved for the fast-follow to other plugins. The migration changes **no agent's effective model** (`model:` is kept as the exact current-model fallback), and a tier-preservation test asserts each migrated agent still resolves to its pre-migration model; any intentional re-tiering is out of scope for #362.

## Implementation Units

### U1. Work-shape → tier registry (`tier_policy.json`)

**Goal:** the machine-readable heuristic the resolver and `/plan` both render from.

**Files:** `plugins/fleet-core/scripts/fleet_commons/tier_policy.json` (new).

**Approach:** one object per work-shape key (`judgment`, `mechanical`, `read-only-survey`, `offload`, `second-opinion`) with `{default_model, default_effort, rationale}`, values drawn verbatim from `plan/SKILL.md:298-304`.

**Test scenarios** (`tests/test_tier_resolver.py`): registry parses as JSON; every `default_model ∈ MODELS` and `default_effort ∈ EFFORTS`; all five SKILL.md rows are present.

### U2. The resolver (`tier_resolver.py`)

**Goal:** `resolve(...) -> Resolution` with `because`, `cheaper_fallback`, `needs_confirm`.

**Files:** `plugins/fleet-core/scripts/fleet_commons/tier_resolver.py` (new); a `resolve` CLI subcommand for `python3 …/tier_resolver.py resolve --role-kind … --work-shape …`.

**Approach:** load `tier_policy.json` (located via `Path(__file__).parent` — a data file beside the module, not shim-loaded); import `MODELS`/`EFFORTS`/`model_rank`/`effort_rank` from `tier_palette` via the shim; map a `role_kind`/role-tier to a `work_shape` via the alias map; apply `operator_override` and `envelope_ceiling` (clamp the resolved tier under the ceiling); compute `cheaper_fallback` per KTD3; set `needs_confirm` per KTD4; build `because` from the registry rationale.

**Depends on:** U1.

**Test scenarios** (`tests/test_tier_resolver.py`): `resolve_shapes` (each work-shape returns its registry tier + rationale); `cheaper_fallback_one_rung` (weaken-model-then-effort, floor no-op); `expensive_tier_confirm_gate` (fable/xhigh → `needs_confirm`, others not); `operator_override` (override wins, still validated); `envelope_ceiling` (resolved tier never exceeds the ceiling).

### U3. Render `/plan` Step-1 table from the registry + drift-guard

**Goal:** the one authored heuristic table is generated from `tier_policy.json`, and drift is caught.

**Files:** `plugins/saga/skills/plan/SKILL.md` (Step-1 table refactored to a registry-sourced block); `tests/test_tier_resolver.py`.

**Depends on:** U1.

**Test scenarios:** `skill_registry_sync` — parse the SKILL.md tier table and assert it equals the registry; a seeded divergence fails the test.

### U4. Migrate team-execution frontmatters to `role-tier:`

**Goal:** 25 agents declare `role-tier:`; `model:` becomes fallback-only.

**Files:** `plugins/team-execution/agents/*.md` (25); `plugins/team-execution/skills/team-execution/references/` A7 doc note.

**Approach:** add `role-tier:` per KTD7 (reviewers→adversarial-review, scanners→mechanical-scan, testers→contract-test); keep each `model:` as the documented fallback. No behavior change until a consumer reads `role-tier` (the resolver does).

**Depends on:** U2.

**Test scenarios** (`tests/test_tier_resolver.py`): `role_tier_resolves_for_all_agents` (every agent's `role-tier` resolves through the registry to a `MODELS`/`EFFORTS` member); `model_fallback_when_registry_absent` (resolution falls back to `model:` when the registry can't load); `tier_preservation` (each of the 25 agents resolves to its pre-migration model — no silent re-tiering).

### U5. Emit per-teammate effort + spawn-site routing drift-guard

**Goal:** effort reaches the plan/worker tables (emission only), and every dispatch site routes through the resolver.

**Files:** `plugins/saga/skills/plan/SKILL.md` (unit tier table emits effort); `plugins/team-execution/skills/team-execution/SKILL.md` (A7 worker table carries the emitted effort, schema aligned with #363); `plugins/saga/references/sandbox-spawn-sites.md` (reference the resolver at each site); `tests/test_tier_resolver.py`.

**Depends on:** U2.

**Test scenarios:** `effort_emitted_into_tables` (a resolved effort appears in the rendered unit/worker table); `spawn_site_enumeration` (the enumerated dispatch sites — team-execution worker dispatch, saga verify-panel, readonly-verifier calls, workflow emitter — each route through the resolver; a new bare palette literal at an enumerated site fails).

### U6. Release surfaces

**Goal:** installed-plugin metadata tells the same story as the diff.

**Files:** `plugins/saga/.claude-plugin/plugin.json`, `plugins/team-execution/.claude-plugin/plugin.json`, `.claude-plugin/marketplace.json`, both `CHANGELOG.md`s, metadata drift-guard test.

**Depends on:** U2–U5.

**Test scenarios:** existing metadata/version drift-guard passes with the bumped versions; `marketplace.json` entries match each `plugin.json`.

## Scope Boundaries

**In scope:** the resolver + registry (fleet_commons); `cheaper_fallback` + expensive-tier confirm flag; `role-tier:` migration for team-execution's 25 agents; rendering `/plan`'s table from the registry; effort *emission*; the spawn-site routing drift-guard; release surfaces.

**Deferred to follow-up (sibling issues, concerns filed):**
- Effort *honoring* at team-execution dispatch → **#363** (Agent tool has no effort knob; `EFFORT_RIDER` shim is #363's).
- Vocabulary source consolidation, `escalate`/`downgrade`/`clamp`, `models.json`, repo-wide bare-literal guard → **#370**.

**True non-goals:** changing the readonly-verifier sandbox contract; inventing new `MODELS`/`EFFORTS` vocabulary; retrofitting non-team-execution plugins' frontmatters (fast-follow); a run-fact-ledger cost-history feature; turning operator-choice into a runtime prompt-per-spawn pattern.

## Verification

Per-unit coverage: `uv run pytest tests/test_tier_resolver.py -v`. Full repo gate before PR: `uv run pytest && uv run ruff format --check . && uv run ruff check . && uv run mypy plugins/ scripts/ tests/ --ignore-missing-imports`. CLI smoke: `python3 plugins/fleet-core/scripts/fleet_commons/tier_resolver.py resolve --work-shape judgment` returns `opus`/`high` with a rationale and a `cheaper_fallback` of `sonnet`/`high`; `--work-shape purely-mechanical` returns `haiku`/`low`. Migration check: `grep -rl '^role-tier:' plugins/team-execution/agents/*.md` reports 25 files.

## Risk Analysis

- **Registry/resolver divergence from `tier_palette`.** Mitigated by importing the tuples/ranking (never copying) and the `role_tier_resolves` + `skill_registry_sync` guards.
- **25-file frontmatter migration blast radius.** Mitigated by KTD5 (keep `model:` as fallback — no behavior change until a consumer reads `role-tier`) and per-file reviewability.
- **Boundary drift with #370 (two ladder implementations).** Mitigated by KTD2 (use `tier_palette` primitives now, migrate onto #370's named ops later) and the filed #370 concern.
- **A7 schema mismatch with #363.** Mitigated by the filed #363 concern requiring schema alignment at both plans.
