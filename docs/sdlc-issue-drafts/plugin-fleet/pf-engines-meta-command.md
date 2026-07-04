---
title: "enhancement: /engines meta-command + route-explain dry-run for operator-facing engine visibility"
repo: infiquetra-claude-plugins
type: enhancement
team: campps
project: operations
status: Idea
labels: enhancement, hermes-task, needs-plan
risk: low
handoff_maturity: requirements-ready
tier: quick-win
objective: "Stand up the external-engine offload lane"
wave: wave-1
---

# enhancement: /engines meta-command + route-explain dry-run for operator-facing engine visibility

### Objective
Stand up the external-engine offload lane

### Summary
Two small, read-only operator-ergonomics surfaces over the existing saga external-engine capability
registry (`plugins/saga/scripts/engine_registry.py`, seed data at `plugins/saga/references/engine-registry.yaml`):
an `/engines` command that renders the registry as inspectable rows (availability, capability ratings,
staleness, and a new per-repo pin/deprecate overlay), and a `route explain` dry-run subcommand that walks
`Registry.by_capability()`'s existing ranked ladder for a given capability and prints the chosen variant,
the runner-up, and the tie-break reasoning — without invoking any engine. Both are read-only CLI surfaces
over data the registry already holds; neither changes routing behavior, they only make it visible and
occasionally overridable.

### Problem Frame
`Registry.by_capability()` already resolves which engine variant serves a capability today, ranking
candidates by rating descending, then `cost_speed_rank` ascending, then `registry_order`
(`plugins/saga/scripts/engine_registry.py:336-352`). `Registry.stale()` already detects when a row's
`last_validated` predates a known model-revision date (`plugins/saga/scripts/engine_registry.py:378-384`).
None of this is operator-visible today: there is no command or script that prints the registry, no way to
ask "why would this route to codex over agy," and no way to express a per-repo preference short of editing
`engine-registry.yaml` seed data directly. Confirmed absent by direct search of this repo (2026-07-03):
`grep -rn "def explain\|by_capability\|Registry.load" plugins/saga/commands/*.md` returns nothing, and
`ls plugins/saga/commands/` lists 19 existing subcommands (`brainstorm.md`, `work.md`, `outcome.md`, …)
with no `engines.md`. The registry module itself has no `__main__`/CLI entry point
(`plugins/saga/scripts/engine_registry.py`, 385 lines, zero `argparse`/`__main__` hits) — it is import-only,
exercised solely by `tests/test_saga_engine_registry.py`. This is the last mile of the fleet's registry-driven
routing work (grounding brief §1: "registry-driven, `engine_resolver.py`... `engine_registry.py`") — the
lookup and staleness logic exist and are tested, but an operator has no legible way to see what they resolve
to or to steer them per repo.

### Key Decisions
- **Read-only, never a second gate.** Both surfaces only render existing registry state and dry-run the
  existing `by_capability()` ranking; neither dispatches an engine nor blocks a lifecycle stage. This keeps
  the work inside DECISIONS `{#external-engines-never-gatekeepers}` (#283) — Claude remains verifier-of-record
  everywhere; `/engines` and `route explain` are visibility tools, not decision points.
  Follows the existing precedent that CLI stays deterministic and skills own interpretation
  (`docs/engineering-journal/DECISIONS.md:1097`).
- **Pin/deprecate is a per-repo overlay, not a registry mutation.** Pinning or deprecating an engine variant
  writes to a small per-repo overlay file (e.g. `.saga/engine-overlay.json`), never to the shipped
  `engine-registry.yaml` seed data. `by_capability()`'s resolution order is: overlay pin (if set) → existing
  rating/cost_speed_rank/registry_order ladder; a deprecated variant is excluded from candidates entirely
  (falls back to the next-ranked candidate, or a typed halt if no candidate remains).
  This mirrors the existing halt-not-degrade posture from the `/outcome` campaign (grounding brief §2).
- **`route explain` is a pure dry-run of the existing ladder, not a new ranking.** It calls the same
  `by_capability()` candidate list and tie-break key already in the registry
  (`plugins/saga/scripts/engine_registry.py:336-352`) and prints the ordered candidates plus which key broke
  each tie; it does not introduce a second ranking algorithm.
- **One CLI, one PR.** `/engines` (list/pin/deprecate) and `route explain` are two subcommands of the same
  small CLI surface over the same registry, per the consolidation rationale that split them would double the
  registry-loading boilerplate for no behavioral gain.

### Actors
- A1. `/engines` command (new saga command + CLI entry point) — renders registry rows, applies/reads the
  per-repo pin/deprecate overlay.
- A2. `route explain` subcommand (same CLI surface) — dry-runs `Registry.by_capability()` for a given
  capability and prints the ranked ladder and reasoning.
- A3. `.saga/engine-overlay.json` — new per-repo overlay file recording pinned/deprecated engine variants.
- A4. Operator — reads `/engines` output to see registry health and per-repo state; runs `route explain
  <capability>` to audit what a stage would resolve to before it runs.

### Requirements
**`/engines` listing**
R1. `/engines` lists every engine variant row from the loaded registry with: `engine_id/variant` key,
declared capabilities and ratings, `cost_speed_rank`, and a staleness flag computed via the registry's
existing `Registry.stale()` (`plugins/saga/scripts/engine_registry.py:378-384`).
R2. `/engines` shows the current repo's pin/deprecate overlay state per row (pinned, deprecated, or neither),
read from `.saga/engine-overlay.json` if present.

**Per-repo pin/deprecate**
R3. `/engines pin <capability> <engine_id>/<variant>` writes an overlay entry that forces
`by_capability(capability)` to resolve to that variant for the current repo, provided the variant declares
that capability; pinning a variant that does not declare the requested capability is rejected with a typed
error, not silently accepted.
R4. `/engines deprecate <engine_id>/<variant>` writes an overlay entry that excludes that variant from all
future `by_capability()` candidate lists for the current repo; if excluding it leaves zero candidates for a
capability, resolution halts with a typed error naming the capability and the fact that all candidates are
deprecated, rather than silently falling through to an unranked variant.
R5. Overlay entries are additive and inspectable — `/engines` (R2) always shows the effective overlay state,
so a pin or deprecate from a prior session is never invisible.

**`route explain` dry-run**
R6. `route explain <capability>` calls the registry's existing `by_capability()` resolution and prints the
full ordered candidate list (not just the winner), each candidate's rating for the requested capability, its
`cost_speed_rank`, and which key (rating, then cost_speed_rank, then registry_order) decided each pairwise
tie in the ordering.
R7. `route explain` is read-only: it never invokes an engine, never writes to the overlay, and produces
identical output across repeated runs given unchanged registry/overlay state.
R8. When the requested capability has no declared candidates, `route explain` reports the same typed halt
`by_capability()` already raises (`RegistryError`) rather than crashing or printing an empty ranking.

### Key Flows
F1. **Operator inspects the fleet.** Trigger: operator runs `/engines`. Command loads the registry (seed
YAML + repo overlay), renders every row with capability ratings, cost rank, staleness flag, and pin/deprecate
state. Covers R1, R2.
F2. **Operator pins a variant for this repo.** Trigger: operator runs `/engines pin second-opinion codex/gpt-5.5-high`.
Command validates the variant declares `second-opinion`, writes the overlay entry, and a subsequent
`by_capability("second-opinion")` call in this repo returns the pinned variant. Covers R3, R5.
F3. **Operator deprecates a stale variant.** Trigger: operator runs `/engines deprecate agy/some-variant`
after `/engines` flagged it stale. Command writes the overlay entry; a subsequent `by_capability()` call for
any capability that variant used to serve excludes it from candidates, falling back to the next-ranked
variant or halting typed if none remain. Covers R4, R5.
F4. **Operator audits a route before running a stage.** Trigger: operator runs
`route explain adversarial-review`. Command dry-runs `by_capability("adversarial-review")`, printing the
ranked candidate list and the deciding tie-break key, without invoking anything. Covers R6, R7, R8.

### Acceptance Examples
AE1. **Covers R1.** `/engines` output includes a row for every variant declared in
`plugins/saga/references/engine-registry.yaml`, each annotated with its declared capabilities/ratings,
`cost_speed_rank`, and a stale/current flag from `Registry.stale()`.
AE2. **Covers R2, R5.** After `/engines pin code-generation codex/gpt-5.5-high`, running `/engines` again
shows that row marked pinned for `code-generation` in the current repo.
AE3. **Covers R3.** `/engines pin debug codex/gpt-5.5-high` where that variant's `capability_profile` does
not declare `debug` is rejected with a typed error naming the missing capability; no overlay entry is
written.
AE4. **Covers R4.** `/engines deprecate` on every variant that serves a given capability, followed by
`by_capability(capability)` (or `route explain <capability>`), produces a typed halt naming the capability
and stating all candidates are deprecated — not a silent fallback to an excluded variant.
AE5. **Covers R6.** `route explain second-opinion` prints the ranked candidate list in the same order
`by_capability("second-opinion")` would resolve, and names `cost_speed_rank` as the deciding key when two
candidates tie on rating.
AE6. **Covers R7.** Two consecutive `route explain <capability>` runs against unchanged registry/overlay
state produce byte-identical output; neither run writes to `.saga/engine-overlay.json` or invokes an engine
CLI.
AE7. **Covers R8.** `route explain <unknown-capability>` reports the same `RegistryError` message
`by_capability()` raises for an unknown or undeclared capability, rather than an unhandled traceback.

### Out-of-scope / non-goals
- This issue ships two read-only/overlay-only CLI surfaces over the existing registry. It does not change
  `Registry.by_capability()`'s ranking algorithm — `route explain` dry-runs the existing rating →
  cost_speed_rank → registry_order tie-break chain, it does not introduce a second ranking.
- It does not mutate the shipped `engine-registry.yaml` seed data — pin/deprecate state lives in a separate
  per-repo overlay file only.
- It does not add a new dispatch path or change chaperone-dispatch behavior
  (`{#external-engine-chaperone-dispatch}` #318) — no engine is invoked by either surface.
- It does not implement automated staleness remediation (re-benchmarking, auto-updating `last_validated`) —
  `/engines` only surfaces the existing `Registry.stale()` flag; refreshing seed data stays a manual
  `/retro`-driven process per the registry's own header comment.
- It does not touch `team-execution`'s worker dispatch or `execution_spec.py`'s `ENGINE_INTENTS` producer —
  this is a saga-side registry visibility layer only.

### Dependencies / Assumptions
- Binding: DECISIONS `{#external-engines-never-gatekeepers}` (#283) — both surfaces stay read-only/advisory,
  never gating.
- Binding: DECISIONS `{#external-engine-chaperone-dispatch}` (#318) — no new dispatch path is introduced.
- Reuses existing, tested registry primitives: `Registry.by_capability()`
  (`plugins/saga/scripts/engine_registry.py:336-352`) and `Registry.stale()`
  (`plugins/saga/scripts/engine_registry.py:378-384`), both already covered by
  `tests/test_saga_engine_registry.py` (219 lines, 8 existing test functions).
- Verified absent today: no `/engines` or `route`/`explain` command exists in `plugins/saga/commands/`
  (19 existing `.md` files enumerated, none named `engines.md`); `engine_registry.py` has no CLI entry point
  (`grep -n "__main__\|argparse" plugins/saga/scripts/engine_registry.py` returns nothing) — this is
  greenfield CLI/command work over an existing, already-tested module, not a refactor.
- Grounding references (absorbed ideas, from `docs/plans/plugin-fleet-ideation-2026-07-03/survivors/`):
  - `T1-F4-8` (primary, tier `structural`) — "`/engines` meta-command: one legible surface to inspect, pin,
    and deprecate engines." Basis: `dod_sketch` calls for a merged PR adding an `/engines` saga subcommand
    (no new plugin) that renders the registry, flags stale rows, and writes a per-repo pin/deprecate overlay
    honored by the resolver; verified by a test that a pinned variant wins resolution and a deprecated engine
    is skipped.
  - `T2-F6-8` (facet, tier `quick-win`) — "`route explain` — a read-only recommendation dry-run over
    capability × rating × cost." Basis: `dod_sketch` calls for a merged PR (`Registry.explain_capability()`
    returning chosen/runner-up/tie-break-chain/halt, plus a thin `explain` CLI), verified by tests asserting a
    tie names `cost_speed_rank` as the deciding key and a WEAK-only capability reports the Claude fallback and
    reason without invoking any engine; distinct from the ranking logic itself because it makes the
    autonomous route auditable, not the ranking.
  - Consolidation rationale (`docs/plans/plugin-fleet-ideation-2026-07-03/issue-map/issue-map-final.json`):
    both facets are read-only operator ergonomics surfaces over the same registry — one small CLI PR rather
    than two, since both require the same registry-loading boilerplate.

### Files expected to change
Indicative only — the exact set is `/plan`'s to determine.
- `plugins/saga/commands/engines.md` — new saga command definition (`/engines`, `/engines pin`,
  `/engines deprecate`, `route explain`).
- `plugins/saga/scripts/engine_registry.py` — add `explain_capability()` (chosen/runner-up/tie-break-chain/
  halt) and overlay-aware resolution (pin/deprecate lookup before the existing ladder).
- `plugins/saga/scripts/engine_overlay.py` (or embedded in `engine_registry.py`) — new per-repo overlay
  read/write module and `.saga/engine-overlay.schema.json`.
- `plugins/saga/.claude-plugin/plugin.json` — version bump.
- `.claude-plugin/marketplace.json` — plugin metadata sync.
- `plugins/saga/CHANGELOG.md` — entry describing the new `/engines` command and `route explain` subcommand.
- `tests/test_saga_engine_registry.py` — extend with pin/deprecate/explain coverage, or a new
  `tests/test_engine_overlay.py`.

### Tests to add or update
- `/engines` listing: every registry row appears with capabilities/ratings, cost rank, and staleness flag.
- Pin: pinning a variant that declares the requested capability wins resolution; pinning a variant that does
  not declare it is rejected with a typed error and no overlay write.
- Deprecate: a deprecated variant is excluded from candidates; deprecating all candidates for a capability
  produces a typed halt, not a silent fallback.
- `route explain`: output matches `by_capability()`'s resolution order; a rating tie names `cost_speed_rank`
  as the deciding key; an unknown capability reports the same `RegistryError` `by_capability()` raises;
  repeated runs against unchanged state are byte-identical and make no engine calls or overlay writes.

## Grounding References
- source_context: `docs/plans/plugin-fleet-ideation-2026-07-03/survivors/T1.json` (id `T1-F4-8`)
- source_context: `docs/plans/plugin-fleet-ideation-2026-07-03/survivors/T2.json` (id `T2-F6-8`)
- source_context: `docs/plans/2026-07-03-plugin-fleet-grounding-brief.md` §1 (fleet map, registry-driven
  routing), §2 (binding-decision register)

## Definition of Done
A merged PR adds an `/engines` command (registry listing plus per-repo pin/deprecate) and a `route explain`
subcommand that dry-runs `by_capability()`'s existing ranked ladder and prints why. Both surfaces are
read-only or overlay-only — no ranking algorithm change, no new dispatch path. Verified by CLI tests over a
fixture registry (pin wins resolution, deprecate excludes and halts, `route explain` matches resolution order
and is idempotent), with release-surface metadata (plugin version, marketplace entry, CHANGELOG) updated in
the same PR.

### Acceptance criteria
- [ ] `/engines` lists every registry row with declared capabilities/ratings, `cost_speed_rank`, and a
  staleness flag from `Registry.stale()`. Check: `uv run pytest tests/test_saga_engine_registry.py -k engines_list` → passes.
- [ ] `/engines` shows the current repo's pin/deprecate overlay state per row. Check:
  `uv run pytest tests/test_saga_engine_registry.py -k engines_overlay_state` → passes.
- [ ] Pinning a variant that declares the requested capability makes `by_capability()` resolve to it for the
  current repo. Check: `uv run pytest tests/test_saga_engine_registry.py -k pin_wins_resolution` → passes.
- [ ] Pinning a variant that does not declare the requested capability is rejected with a typed error and no
  overlay write occurs. Check: `uv run pytest tests/test_saga_engine_registry.py -k pin_rejects_undeclared_capability` → passes.
- [ ] Deprecating a variant excludes it from future `by_capability()` candidate lists; deprecating all
  candidates for a capability halts typed rather than falling back silently. Check:
  `uv run pytest tests/test_saga_engine_registry.py -k deprecate_excludes_and_halts` → passes.
- [ ] `route explain <capability>` prints the ranked candidate list in `by_capability()`'s resolution order
  and names `cost_speed_rank` as the deciding key on a rating tie. Check:
  `uv run pytest tests/test_saga_engine_registry.py -k route_explain_tie_break` → passes.
- [ ] `route explain` never invokes an engine or writes the overlay, and is idempotent across repeated runs.
  Check: `uv run pytest tests/test_saga_engine_registry.py -k route_explain_read_only` → passes.
- [ ] `route explain <unknown-capability>` reports the same `RegistryError` `by_capability()` raises. Check:
  `uv run pytest tests/test_saga_engine_registry.py -k route_explain_unknown_capability` → passes.
- [ ] Release-surface metadata (plugin version, marketplace entry, CHANGELOG) is updated in the same PR.
  Check: `git diff --name-only` includes `plugins/saga/.claude-plugin/plugin.json`,
  `.claude-plugin/marketplace.json`, and `plugins/saga/CHANGELOG.md`.
- [ ] Full suite, format, lint, and types stay green. Check:
  `uv run pytest && uv run ruff format --check . && uv run ruff check . && uv run mypy plugins/ scripts/ tests/ --ignore-missing-imports`
  → all pass.

### Verification
```bash
# Unit tests for the new /engines and route explain surfaces
uv run pytest tests/test_saga_engine_registry.py -k "engines or pin or deprecate or route_explain" -v
# Confirm existing registry behavior (by_capability, stale) is unchanged
uv run pytest tests/test_saga_engine_registry.py -v
# Full repo gate (CI parity)
uv run pytest && uv run ruff format --check . && uv run ruff check . && uv run mypy plugins/ scripts/ tests/ --ignore-missing-imports
```
Expected: all green; `/engines` renders the full registry with overlay state; `route explain` output for a
known tie names `cost_speed_rank` as the deciding key; existing `by_capability`/`stale` tests remain
unaffected.

### Recommended executor profile
- **Model:** sonnet
- **Effort:** low
- **Backend:** inline
- **External-LLM posture:** none
- **Justification:** Both surfaces are thin, read-only (or overlay-only) CLI wrappers over an already-built
  and already-tested registry module (`Registry.by_capability()`, `Registry.stale()`) — there is no ranking
  algorithm to design, no architectural ambiguity, and no gated-decision risk to reason about. Sonnet/low is
  sufficient; there is no case for opus or an external engine, since the work is presentation and a thin
  overlay, not judgment.

### Release-surface checklist
This issue changes plugin behavior (new `/engines` command, new `route explain` subcommand, new overlay
schema), so the following must land in the same PR:
- [ ] `plugins/saga/.claude-plugin/plugin.json` — version bump.
- [ ] `.claude-plugin/marketplace.json` — plugin metadata sync.
- [ ] `plugins/saga/CHANGELOG.md` — entry describing the new `/engines` command and `route explain`
  subcommand.
- [ ] Drift-guard/coverage test enumerating both new subcommands, so a future registry change that breaks
  `/engines` or `route explain` fails CI instead of silently drifting.

### Handoff maturity
requirements-ready

### Suggested next action
Use `/plan <issue>` to create an implementation plan.

### Source context
- Source: `docs/plans/plugin-fleet-ideation-2026-07-03/survivors/T1.json` (id `T1-F4-8`); `T2.json` (id
  `T2-F6-8`)
- Source type: ideation-survivor
- Source title: /engines meta-command + route-explain dry-run for operator-facing engine visibility

### Context library links

_none_

### Intent

Two small, read-only operator-ergonomics surfaces over the existing saga external-engine capability registry (`plugins/saga/scripts/engine_registry.py`, seed data at `plugins/saga/references/engine-registry.yaml`): an `/engines` command that renders the registry as inspectable rows (availability, capability ratings, staleness, and a new per-repo pin/deprecate overlay), and a `route explain` dry-run subcommand that walks `Registry.by_capability()`'s existing ranked ladder for a given capability and prints the chosen variant, the runner-up, and the tie-break reasoning — without invoking any engine. Both are read-only CLI surfaces over data the registry already holds; neither changes routing behavior, they only make it visible and occasionally overridable.

## Created Issue

- URL: https://github.com/infiquetra/infiquetra-claude-plugins/issues/453
- Number: 453
- Created at: 2026-07-04T08:22:36.253798+00:00

