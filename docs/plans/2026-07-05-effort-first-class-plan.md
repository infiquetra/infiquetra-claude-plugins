---
title: Effort becomes a first-class, validated, pluggably-honored field fleet-wide (#363)
type: feat
status: active
date: 2026-07-05
origin: https://github.com/infiquetra/infiquetra-claude-plugins/issues/363
---

# Effort becomes a first-class, validated, pluggably-honored field fleet-wide (#363)

## Summary

Make `effort` a real first-class **value** across the fleet — authored in agent frontmatter and the
team-execution A7 worker table, validated against the single canonical vocabulary, resolved through a
three-layer cascade, and reconciled after a run. Honor it with the **real** per-call knob on the paths
that already have one (Workflow/ultracode `agent({effort})`, external-engine offload) and a **labeled
proxy** (`EFFORT_RIDER`) only on the native Agent-tool teammate path — both behind one swappable
`inject_effort()` seam so a future native subagent-effort knob is a one-function change.

## Problem Frame

Today `model:` is a real per-agent frontmatter field fleet-wide (25/25 team-execution agents carry it,
plus `role-tier:` from #362); `effort` is not — it exists as emitted metadata in the A7 `Tier` cell
(`team_emitter.py:139`) and as a real parameter on two dispatch paths, but is never honored on the
native Agent-tool teammate spawn that team-execution uses (`SKILL.md:318`; the skill itself flags the
gap at `SKILL.md:239-240`; reasoning effort is session-level per `team-execution/CHANGELOG.md:182`).

The load-bearing fact (verified) is that effort is **already honored for real on 2 of the 3 dispatch
paths** — Workflow/ultracode emits `agent(prompt, {effort})` (`execution_spec.py:982`, `:1020`) and
external-engine offload passes `effort=resolution.effort` (`external-engine-workers.md:155`). It is
faked on exactly one path: the native Agent tool, which has no per-call effort knob. So the work is not
"make effort real" — it is "make effort a first-class value, honored by the real knob where it exists
and proxied honestly where it can't be."

This closes the standing QUEUED item `{#team-execution-per-teammate-effort}` (`QUEUED.md:457`) without
its "re-architect team-execution onto Workflow" cost — which would dissolve team-execution's persistent
named-teammate model and blur the team(gated)/workflow(advisory) governance seam (see KTD1, rejected
alternative B).

## Requirements

R1. Any agent `.md` across all plugins MAY declare an `effort:` frontmatter field. Where present, its
value MUST be one of `tier_palette.EFFORTS = ("low","medium","high","xhigh")` — the single canonical
vocabulary (KTD3), not a re-declared or stale-cited copy.

R2. A glob+membership lint parses every `plugins/*/agents/*.md` frontmatter and asserts: every
`effort:` present is in `EFFORTS` and every `model:` present is in `MODELS`. An out-of-vocabulary value
on either field fails. A `tiering_exempt: true` frontmatter opts a file out (mirroring the existing
redis-channel-coach exemption).

R3. The R2 lint runs in CI as a required step (a `scripts/lint_agent_tiers.py` entry point and/or its
pytest case), so a hand-authored typo (`effort: extreme`) fails the build, not a spawn.

R4. The A7 worker-table `Tier` cell (`team-execution/skills/team-execution/SKILL.md:218-242`) is
validated as a structured `{model, effort}` pair at emit time; an off-palette `effort` half raises the
same validation error as an R1/R2 frontmatter violation. (`team_emitter.py` already composes the cell
from `seg.tier.model`/`.effort` at `:139`; this adds `EFFORTS` validation, not re-parsing of emitter
output.)

R5. Effort resolution is a three-layer cascade, most-specific wins: plan-authored per-unit tier →
team-level default → per-teammate agent-frontmatter default (R1). The **team-level default** is an
optional team-wide effort — there is no such config today (doc-review grep confirmed none), so the
middle layer is structurally present but usually empty, falling through to the agent-frontmatter default
when unset. The cascade is computed by wrapping #362's `tier_resolver.resolve(...)` (this is
`resolve()`'s first non-test consumer). The emitted worker table records a **provenance line** naming
which layer resolved each teammate's effort, not just the value.

R6. External-engine chaperone workers (`{#external-engine-chaperone-dispatch}`, `DECISIONS.md:2579`)
are **excluded** from the R5 cascade: an `offload`-intent worker stays `sonnet/medium` and a
`second-opinion`-intent worker stays `opus/high`. The cascade preserves the intent-driven default
rather than resolving-then-overriding it (KTD5).

R7. A single `inject_effort(prompt, effort, spawn_kind)` seam honors the resolved effort:
- On a **real-knob** path (`spawn_kind ∈ {workflow, external-engine}`) the seam is a pass-through — the
  effort already rides in the `agent()`/engine opts (`execution_spec.py:982`); the seam does not
  double-inject a rider.
- On the **native Agent-tool teammate** path (`spawn_kind = agent`) the seam prepends the
  `EFFORT_RIDER[effort]` directive string to the teammate's prompt preamble — the only available lever
  until the harness ships a native subagent-effort knob.

R8. `EFFORT_RIDER` (a `{effort → directive}` dict) and `inject_effort()` live in `fleet_commons`
(cross-plugin, consumed via `fleet_commons_shim.load`, like `tier_palette`/`tier_resolver`), documented
once as the fleet's effort convention in a single reference doc. At least one `agy` agent and one
`deploy` agent carry a validated `effort:` field, proving the convention is fleet-wide, not saga-only.

R9. A post-run reconciliation compares each teammate's cascade-resolved effort against the effort
recorded for that teammate in the **worker manifest** (`references/worker-manifest.md:48,54` already
records the resolved effort as provenance), and emits a named tiering-drift line on mismatch (nothing on
match). It is **honest per path** (KTD7): on a real-knob path the manifest's effort is the value passed
to `agent()`/the engine; on the Agent-tool path the reconcile can only confirm the `EFFORT_RIDER` text
for the resolved level reached the constructed prompt — the drift line names the path and what was
compared, and never claims to observe harness reasoning spend.

## Key Technical Decisions

KTD1 — **Honoring mechanism = first-class value + pluggable `inject_effort()` seam (Option C).** Honor
the real knob where the path has it (Workflow `agent({effort})`, external-engine offload — already
live); use a labeled `EFFORT_RIDER` proxy only on the native Agent-tool path; both behind one seam so a
future native subagent-effort knob is a one-function swap. *Rejected:* (A) EFFORT_RIDER on every path —
downgrades the two paths that already honor real effort to a prose proxy and hides the real-vs-faked
split; (B) route team-execution onto Workflow — dissolves its persistent named-teammate model (its
reason to exist) and blurs the team(gated)/workflow(advisory) governance seam. Operator-confirmed.

KTD2 — **`EFFORT_RIDER` is a `dict[str, str]` (`{effort → directive}`)**, structurally a prompt-preamble
rider like `BUDGET_RIDER` (`execution_spec.py:132`) but keyed by effort rather than a single cheap-tier
string. Injected via the same `parts.append(...)` + `"\n\n".join(parts)` pattern the two BUDGET_RIDER
sites use (`:1000`, `:1247`).

KTD3 — **Vocabulary source is `tier_palette.EFFORTS`/`MODELS`** (`fleet-core`, canonical since #463).
Never re-declare the tuples; never cite the stale `execution_spec.py:52-53` (they re-export via the
shim at `:59-78`). Resolves the stale-citation flagged in #363's concern comment (point 3).

KTD4 — **The cascade wraps #362's `tier_resolver.resolve()`** — #363 is its first real consumer.
`resolve(role_kind, work_shape, envelope_ceiling, operator_override)` has no "team-default" parameter,
so the cascade is not one call: `resolve()` supplies the **base layer** (agent-frontmatter default, via
the agent's `role-tier` work-shape → registry `default_effort`); the team default and the plan-authored
per-unit tier are applied **above** it, most-specific wins (a plan-unit tier maps to
`operator_override={"effort": …}` when it reaches `resolve()`, or short-circuits the wrap when it is the
winner). The provenance line records which of the three layers supplied the winning value. Aligns the A7
schema with what #362 emits (resolves #363 concern-comment point 2).

KTD5 — **Chaperone exclusion preserves the intent-driven default, it does not override.** The offload
(`sonnet/medium`) and second-opinion (`opus/high`) rows are intent-driven recommendations
(`DECISIONS.md:2593-2597`), so the cascade **skips** chaperone workers entirely rather than resolving
then restoring — keeping the two intents pulling in opposite directions as designed.

KTD6 — **The R2 lint is a new glob+membership shape**, distinct from the existing hardcoded
`PINNED_AGENTS` value-pinning test (`test_agent_tiering.py:48`). It reuses `_parse_frontmatter`
(`test_agent_tiering.py:18`), globs `plugins/*/agents/*.md`, asserts membership in `EFFORTS`/`MODELS`,
and honors a `tiering_exempt` escape hatch.

KTD7 — **Reconcile is honest per path.** "Actual effort" means the effort passed to `agent()`/the engine
on real-knob paths, but only "the rider text reached the prompt" on the Agent-tool path — the seam
cannot observe harness reasoning spend there. The drift line names the path and the compared quantity so
it never overclaims.

## High-Level Technical Design

The `inject_effort()` seam is the load-bearing abstraction. It is the single point every dispatch path
routes its resolved effort through, so the "how is effort honored" decision lives in exactly one place:

```
resolved effort (from R5 cascade / resolve())
        │
        ▼
inject_effort(prompt, effort, spawn_kind)         [fleet_commons]
        │
        ├── spawn_kind = workflow ────────► pass-through
        │      (effort already in agent({effort}) opts @ execution_spec:982)
        │
        ├── spawn_kind = external-engine ─► pass-through
        │      (effort already passed to the engine @ external-engine-workers:155)
        │
        └── spawn_kind = agent ───────────► prompt = EFFORT_RIDER[effort] + "\n\n" + prompt
               (native Agent-tool teammate — the only path with no real knob)
```

When the harness ships a native subagent-effort parameter, the `agent` branch changes from
"prepend rider" to "pass the real knob" — nothing upstream (authoring, lint, cascade, provenance,
reconcile) changes. That is the entire point of KTD1.

## Implementation Units

### U1. Effort vocabulary, frontmatter field, and CI lint

Establish `effort:` as a recognized, validated frontmatter field and guard it in CI.

**Covers:** R1, R2, R3. **Depends on:** none.

Wire `effort:` recognition sourced from `tier_palette.EFFORTS` (KTD3). Build the glob+membership lint as
a **pytest test** (`tests/test_agent_tier_lint.py`) that runs in the **existing** CI pytest step — no new
CI step needed (R3) — with an optional thin `scripts/lint_agent_tiers.py` wrapper for manual/local runs.
It reuses `_parse_frontmatter`, asserts every `effort:`/`model:` value in every `plugins/*/agents/*.md`
is in `EFFORTS`/`MODELS`, and honors `tiering_exempt` (KTD6). **Pre-verified safe:** doc-review confirmed
all 33 existing `model:` values are in-palette and the one model-less agent (redis-channel-coach,
`tiering_exempt`) is correctly skipped, so enabling the fleet-wide lint will not red-CI.

**Test scenarios** (`tests/test_agent_tier_lint.py`): a fixture agent with `effort: extreme` fails; the
same fixture with `effort: high` passes; a `model:`-off-palette fixture fails; a `tiering_exempt: true`
fixture is skipped; the real current fleet passes (no regression).

### U2. `EFFORT_RIDER` + `inject_effort()` seam in fleet_commons

Build the honoring seam and the labeled proxy, cross-plugin, per KTD1/KTD2.

**Covers:** R7, R8 (mechanism half). **Depends on:** U1.

Add `EFFORT_RIDER: dict[str, str]` (one directive per `EFFORTS` value) and
`inject_effort(prompt, effort, spawn_kind)` to `fleet_commons`. The seam pass-throughs `workflow` and
`external-engine` kinds and prepends `EFFORT_RIDER[effort]` for `agent`. Consumed via
`fleet_commons_shim.load("effort_rider")` (or a shared module name); vendor the byte-identical shim per
the #463 pattern.

**Test scenarios** (`tests/test_effort_rider.py`): `EFFORT_RIDER` has a non-empty directive for every
`EFFORTS` value (no missing key); `inject_effort(p, "high", "agent")` returns the rider prepended to
`p`; `inject_effort(p, "high", "workflow")` returns `p` unchanged (pass-through, no double-inject);
`inject_effort(p, "high", "external-engine")` unchanged; an unknown `spawn_kind` raises.

### U3. A7 tier validation, three-layer cascade, chaperone exclusion

Resolve and validate per-teammate effort in the emitter, with provenance.

**Covers:** R4, R5, R6. **Depends on:** U1 (vocab) + `resolve()` (merged in #362); serialized after U2
for the rate-limit cap — no logical dependency on the seam.

In `team_emitter.py`: validate the `Tier` cell's `effort` half against `EFFORTS` (raise on off-palette,
R4); implement the three-layer cascade through `tier_resolver.resolve(...)` (R5, KTD4); record a
provenance line per teammate naming the resolving layer; exclude chaperone (`offload`/`second-opinion`)
workers from the cascade, preserving their intent default (R6, KTD5).

**Test scenarios** (`tests/test_team_emitter.py`): a valid `{model, effort}` row parses; an off-palette
effort raises; `cascade_provenance` golden shows the source layer per teammate; `chaperone_effort_fixed`
holds `sonnet/medium` for offload and `opus/high` for second-opinion even when the cascade would resolve
otherwise.

### U4. Wire the seam into team-execution dispatch + cross-plugin convention

Apply `inject_effort()` at the real spawn site and prove the convention fleet-wide.

**Covers:** R7 (application), R8 (convention doc + cross-plugin agents). **Depends on:** U2, U3.

team-execution's dispatch path calls `inject_effort(prompt, resolved_effort, "agent")` before the
Agent-tool spawn (`SKILL.md:318`). Write the single fleet effort-convention reference doc. Add a
validated `effort:` field to at least one `agy` agent and one `deploy` agent.

**Test scenarios** (`tests/test_team_emitter.py` / `tests/test_effort_rider.py`): a teammate authored
`effort: high` has the `high` rider text in its constructed spawn prompt; `grep -rl "^effort:"
plugins/agy/agents/*.md plugins/deploy/agents/*.md` returns ≥1 each and they pass the U1 lint; the
convention doc exists at its reference path.

### U5. Post-run reconciliation

Detect and name resolved-vs-actual effort drift, honestly per path.

**Covers:** R9. **Depends on:** U4.

Compare each teammate's cascade-resolved effort against the effort recorded for it in the worker manifest
(`references/worker-manifest.md:48,54`); emit a named tiering-drift line on mismatch, nothing on match.
The line names the path and the compared quantity (KTD7).

**Test scenarios** (`tests/test_team_emitter.py`): a mismatch case emits the named drift line; a
matching run emits none; an Agent-tool-path drift line names "rider-text" as the compared quantity (not
"reasoning spend").

### U6. Release surfaces

Ship the installed-plugin metadata and journal in the same PR.

**Covers:** Definition of Done release checklist. **Depends on:** U5.

Bump `saga`, `team-execution`, and `fleet-core` `plugin.json`; mirror `.claude-plugin/marketplace.json`;
add CHANGELOG entries; mark the `QUEUED.md` `{#team-execution-per-teammate-effort}` entry **resolved via
the `inject_effort()` seam** (effort first-class as a value + honored natively on real-knob paths +
proxied on the Agent-tool path), with the native-knob swap noted as the tracked residual follow-up — not
a blanket "shipped" that overclaims real Agent-tool honoring; record KTD1–KTD7 in `DECISIONS.md`; update
the metadata drift-guard test.

**Test scenarios:** the metadata drift-guard test passes with the new versions; `Test expectation: none
-- release-surface bookkeeping, covered by the drift-guard tests above.`

## Scope Boundaries

**Out of scope (true non-goals):**
- **Refactoring `execution_spec.py`'s emit or the external-engine dispatch to route through the seam.**
  Those paths already honor effort natively (`execution_spec.py:982`, `external-engine-workers.md:155`);
  `inject_effort()` is called **only** at the Agent-tool spawn site (U4). Its `workflow`/`external-engine`
  branches are **guarded no-ops** — a safe pass-through so a mistaken call never double-injects a rider,
  proven by AC6 — not new routing wired into the working emit path. `/work` must not touch the emit path.
- Routing team-execution's spawn onto the Workflow engine (KTD1 rejected alternative B) — explicitly not
  this work.
- Changing how the Workflow/ultracode or external-engine paths honor effort — they already pass the real
  knob; the seam only routes to them.
- A native subagent-effort harness parameter — not ours to ship; the seam is designed to adopt it when
  it lands.

**Deferred to Follow-Up Work:**
- Swapping the `agent`-branch of `inject_effort()` from rider to the native knob when the harness ships
  it (the P3→P2 trigger in `QUEUED.md:459`) — a one-function change this plan deliberately sets up.
- Per-model effort-clamp handling (Haiku may clamp top tiers, `QUEUED.md:462`) — surface as a reconcile
  observation if it arises; not a blocker here.

## Acceptance criteria (carried from #363, adjusted for KTD1)

- AC1 (R1/R2): seeded `effort: extreme` fails `tests/test_agent_tier_lint.py`; `effort: high` passes; the seeded fleet passes.
- AC2 (R3): CI runs the lint against the real `plugins/*/agents/*.md` as a required step, exit 0.
- AC3 (R4): the effort value entering the emitter is validated against `EFFORTS` at compose time (an off-palette effort raises) — validated where the tier enters `team_emitter`, not by re-parsing the emitted table.
- AC4 (R5): the emitted table names the resolving cascade layer per teammate.
- AC5 (R6): a chaperone worker's effort is never overridden by the cascade (offload `sonnet/medium`, second-opinion `opus/high`).
- AC6 (R7): a teammate authored `effort: high` receives the `high` `EFFORT_RIDER` text in its Agent-tool spawn prompt; a workflow-path unit does **not** get a double-injected rider.
- AC7 (R8): the convention doc exists once; ≥1 `agy` and ≥1 `deploy` agent carry a validated `effort:` consuming it.
- AC8 (R9): a resolved-vs-actual mismatch emits a named tiering-drift line; a match emits none.
- Full suite green: `uv run pytest && uv run ruff format --check . && uv run ruff check . && uv run mypy plugins/ scripts/ tests/ --ignore-missing-imports`.

## Execution notes

- **Concurrency cap: max 3 concurrent** (hard — Anthropic API rate limit blocks connections above it).
- U1/U3/U4/U5 all touch `tests/test_team_emitter.py` and/or `tests/test_agent_tier_lint.py`; **serialize
  units that share a test file** to avoid concurrent-edit conflicts (the #362 spec ran fully serialized
  for this reason).
- The dependency order (U1 → U2 → {U3} → U4 → U5 → U6) already enforces most serialization; keep it.
