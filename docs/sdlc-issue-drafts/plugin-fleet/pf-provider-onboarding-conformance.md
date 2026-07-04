---
title: "enhancement: provider onboarding — scaffolder, CI conformance gate, and shadow-mode standing"
repo: infiquetra-claude-plugins
type: enhancement
team: campps
project: operations
status: Idea
labels: enhancement, hermes-task, needs-plan
risk: medium
handoff_maturity: requirements-ready
tier: structural
objective: "Stand up the external-engine offload lane"
wave: wave-1
---

# enhancement: provider onboarding — scaffolder, CI conformance gate, and shadow-mode standing

### Objective
Stand up the external-engine offload lane

### Summary
Onboarding a new external-engine provider into `plugins/saga/references/engine-registry.yaml`
today means hand-authoring a row against `plugins/saga/scripts/engine_registry.py`'s validation
rules with no scaffolder, no CI gate dedicated to catching a broken or incomplete row before it
ever reaches dispatch, and no staged-trust path — a newly added row is immediately eligible for
every role, including panel/advisory-reviewer roles, with the same standing as a
benchmark-validated incumbent like `codex/gpt-5.5-high`. Three independently found ideation facets
converge on this same onboarding-cost/onboarding-safety gap: a scaffolder that emits a conformant
row plus a bridge stub, a CI conformance suite that fails the pull request (not a live dispatch)
when a row is wired incompletely, and a probation/trust-tier field that keeps a new row
offload-only until it earns advisory standing. This issue lands all three as one coherent
onboarding path — not three separate patches — because they share the same registry schema, the
same `EngineEntry`/`Registry` model, and the same "problem surfaces before dispatch, not during
it" design goal.

## Definition of Done
A merged PR lands all three coupled facets against `plugins/saga/scripts/engine_registry.py` and
`plugins/saga/references/engine-registry.yaml`: the scaffolder (`tools/add-engine.sh`) emits a
conformant row plus bridge stub for a fixture provider without hand-editing; the named CI
conformance suite (`tests/test_engine_registry_conformance.py`) fails the pull request on a
deliberately dead-wired row and passes on the real registry; and `EngineEntry` carries a
`trust_tier`/`probation` field, defaulting new rows to probation, with resolver logic that refuses
probationary rows for panel/advisory-reviewer roles while permitting offload-only dispatch, plus a
telemetry-fed promotion-threshold check. Release-surface metadata and `docs/adding-a-provider.md`
land in the same PR, and the full test/lint/type gate stays green.

### Problem Frame
Confirmed directly in this repo:

- `plugins/saga/scripts/engine_registry.py:165-180` (`EngineEntry`) has no scaffolding tool that
  emits a new row — every field (`invocation`, `context_window`, `cost_speed_rank`,
  `model_identity`, `last_validated`, `capability_profile`, `prompting_protocol`, `sources`) is
  hand-authored today; `plugins/saga/references/engine-registry.yaml:19-40` (the `codex/gpt-5.5-high`
  row) shows the shape a human must replicate by copy-paste with no generator and no
  `docs/adding-a-provider.md`-style walkthrough anywhere in the repo (confirmed via
  `find . -iname "adding-a-provider*"` and `find . -iname "add-engine*"`, both empty, run
  2026-07-03).
- `Registry.validate()` and `EngineEntry.from_dict` (`plugins/saga/scripts/engine_registry.py:187-227`)
  already raise `RegistryError` on a malformed row, but that check only runs inside
  `tests/test_saga_engine_registry.py` (confirmed via `grep -n "Registry.load\|Registry.validate"
  tests/test_saga_engine_registry.py`) — `.github/workflows/ci.yml:37-43` runs the general pytest
  suite (`uv run python -m pytest -v --cov=plugins ...`), but there is no test asserting that every
  registry row is reachable through the dispatch substrate end-to-end (row → capability resolution
  → preflight entry → every advertised capability resolvable) — a row could pass schema validation
  while still being dead-wired to nothing a caller can actually reach, and that failure class would
  only surface at dispatch time in production, not in CI (grounds `T2-F4-3`; this is the
  cross-registry-loader-and-dispatch lockstep check, distinct from the pure-schema lint already
  covered by the sibling issue `pf-engine-registry-schema`'s `T2-F2-4`).
- `plugins/saga/scripts/engine_registry.py:165-180` (`EngineEntry`) carries no `probation` or
  `trust_tier` field — every row, new or incumbent, resolves identically for every role in
  `plugins/saga/references/engine-registry.yaml`'s `roles:` block (e.g. an adversarial-review panel
  role), so a freshly onboarded provider with zero recorded evidence is immediately eligible to sit
  on a panel/advisory-reviewer role alongside `codex/gpt-5.5-high`, which the file's own header
  comment (`plugins/saga/references/engine-registry.yaml:1-6`) describes as "current benchmark +
  practitioner evidence, tagged per row by source + corroboration strength" — there is no
  structural distinction between a row backed by that evidence and a row with none (grounds
  `T2-F5-4`).

This is the primary consolidation target for its ideation theme in
`docs/plans/plugin-fleet-ideation-2026-07-03/survivors/T2.json`: `T2-F1-5` is tagged
`structural`/primary, `T2-F4-3` and `T2-F5-4` are absorbed facets of the same
provider-onboarding-cost axis (theme T2, frames F1/F4/F5). Binding decision
`{#external-engines-never-gatekeepers}` (#283, `docs/engineering-journal/DECISIONS.md:1985`)
constrains all of this: the probation/trust-tier gate governs which *roles* a provider is eligible
for (panel/advisory-reviewer standing), it never makes an external engine a gating decision-maker —
Claude remains verifier-of-record regardless of a row's trust tier.

### Key Decisions
- **One onboarding path, three coupled facets.** The scaffolder, the CI conformance gate, and the
  probation/trust-tier field all operate on the same `engine-registry.yaml` schema and the same
  `EngineEntry`/`Registry` model; shipping them separately risks the scaffolder emitting rows the
  conformance gate doesn't check, or a probation field the scaffolder doesn't default correctly.
- **CI conformance fails the PR, not the dispatch.** Per `T2-F4-3`'s explicit framing, the new
  parametrized test asserts every registry row is reachable through the dispatch substrate (capable
  of resolving through `Registry.by_capability`/`Registry.by_engine`, having a valid `invocation`
  entry, and every advertised `capability_profile` key resolvable) — this is deliberately distinct
  from the sibling `pf-engine-registry-schema` issue's `Registry.validate()`/`Registry.stale()`
  CI wiring (`T2-F2-4`), which is pure schema/staleness lint; this issue's gate cross-checks
  registry↔dispatch↔preflight lockstep against the dead-wiring failure class specifically.
- **Probation is a resolver-visible field, not a documentation convention.** `trust_tier` (or
  `probation: bool`) lives on `EngineEntry` itself so the resolver can refuse a probationary row for
  panel/advisory-reviewer roles mechanically — a comment in `engine-registry.yaml` saying "new,
  unvalidated" would not stop a resolver from selecting it for a panel seat.
- **Promotion out of probation is evidence-gated, not time-gated.** A provider earns advisory
  standing via a recorded promotion-threshold check fed by telemetry (e.g., accumulated offload
  outcomes), not by a fixed calendar window — this matches the "shadow mode earns standing" framing
  in `T2-F5-4`'s title and keeps the promotion path auditable.
- **Scaffolder output must itself pass the conformance gate.** The scaffolder is validated by using
  it: a scaffolded fixture provider is the fixture the conformance suite runs against, so the two
  facets are provably in lockstep rather than independently plausible.

### Actors
- A1. `tools/add-engine.sh` (new) — the scaffolder; prompts for the required `EngineEntry` fields
  and emits a conformant registry row plus a bridge/invocation stub.
- A2. `tests/test_engine_registry_conformance.py` (new) — the CI conformance suite; asserts every
  registry row resolves end-to-end through dispatch and preflight.
- A3. `plugins/saga/scripts/engine_registry.py` — gains the `trust_tier`/`probation` field on
  `EngineEntry` and the resolver-side refusal logic for probationary rows on panel/advisory-reviewer
  roles.
- A4. `plugins/saga/scripts/engine_resolver.py` — the consumer of the new probation field; refuses
  a probationary row for panel/advisory-reviewer role resolution, permits it for offload-only
  dispatch.
- A5. `docs/adding-a-provider.md` (new) — the onboarding walkthrough the scaffolder and conformance
  gate are documented against.
- A6. CI (`.github/workflows/ci.yml`) — the caller of the new conformance suite.

### Requirements
**Scaffolder + registry conformance (T2-F1-5)**
R1. Running the scaffolder for a new provider (e.g. a fixture `deepseek/chat` variant) emits a
registry row in `engine-registry.yaml` and a bridge/invocation stub that together pass
`Registry.validate()` without hand-editing.
R2. Running the scaffolder against a deliberately incomplete input (e.g. missing a required
capability rating or an empty `sources` list) fails with a precise, field-naming error message
before any row is written — it does not emit a broken row silently.
R3. `docs/adding-a-provider.md` documents the scaffolder's inputs/outputs and is kept current with
the scaffolder's actual flag/field set.

**CI conformance gate (T2-F4-3)**
R4. A parametrized CI test asserts, for every row currently in `engine-registry.yaml`, that the row
is reachable via the dispatch substrate: it resolves through `Registry.by_capability` for at least
one declared capability, resolves through `Registry.by_engine`, has a valid `invocation` preflight
entry, and every capability the row advertises in `capability_profile` is a member of the
registry's declared `capabilities` list.
R5. The conformance test fails the pull request (CI) when a fixture row is deliberately partial
(e.g. an advertised capability not present in `by_capability`'s resolvable set) — it never allows a
dead-wired row to reach a live dispatch attempt undetected.
R6. The conformance check is a distinct, named test file/step from the sibling
`pf-engine-registry-schema` issue's schema-lint step — the two are not merged into one test, since
one checks schema shape and the other checks dispatch-reachability lockstep.

**Shadow-mode probation and advisory promotion (T2-F5-4)**
R7. `EngineEntry` carries a `trust_tier` (or `probation: bool`) field; a row scaffolded via R1
defaults to the probationary tier unless explicitly overridden.
R8. Resolver logic refuses a probationary row for panel/advisory-reviewer role resolution, and
still permits the same row for offload-only dispatch.
R9. A recorded, telemetry-fed promotion-threshold check exists that can move a row from
probationary to advisory standing; the check's inputs and threshold are documented, not implicit
in resolver code.

### Key Flows
F1. **New provider scaffolded and validated.** Trigger: an operator runs the scaffolder for a new
provider. The scaffolder emits a row plus bridge stub; `Registry.validate()` passes without manual
edits; the row defaults to probationary standing. Covers R1, R3, R7.
F2. **Scaffolder rejects an incomplete input.** Trigger: the operator supplies incomplete provider
data (e.g. no `sources`). The scaffolder halts before writing, naming the missing field. Covers R2.
F3. **CI catches a dead-wired row.** Trigger: a PR introduces or leaves a row whose advertised
capability isn't resolvable via `by_capability`, or whose `invocation` entry is malformed. The
named conformance test fails and names the offending row and capability; fixing the row makes the
same test pass. Covers R4, R5, R6.
F4. **Probationary row refused for a panel role, permitted for offload.** Trigger: the resolver is
asked to fill a panel/advisory-reviewer role and a candidate row's `trust_tier` is probationary. The
resolver excludes that row from the panel role but still resolves it for an offload-only dispatch
request. Covers R8.
F5. **Promotion out of probation.** Trigger: a probationary row accumulates telemetry meeting the
documented promotion threshold. The promotion-threshold check flags the row as eligible for
advisory standing; the row's `trust_tier` updates accordingly. Covers R9.

### Acceptance Examples
AE1. **Covers R1.** Scaffolding a fixture `deepseek/chat` provider produces a row and bridge stub
that `Registry.load` accepts with zero manual edits.
AE2. **Covers R2.** Scaffolding with a missing capability rating or empty `sources` list fails with
an error naming the specific missing field, and no row is written to `engine-registry.yaml`.
AE3. **Covers R4, R5.** A deliberately partial fixture row (advertised capability absent from the
resolvable set) makes `test_engine_registry_conformance.py` fail, naming the row and the
unreachable capability; reverting the row to complete makes the same test pass.
AE4. **Covers R7, R8.** A newly scaffolded row defaults to `trust_tier: probation`; a resolver test
asserts that row resolves for an offload-only dispatch request but is excluded from resolving a
panel/advisory-reviewer role, while an incumbent row with advisory standing still resolves for
that same panel role.
AE5. **Covers R9.** A test seeds telemetry meeting the documented promotion threshold for a
probationary row and asserts the promotion check flags it eligible; a row below threshold is not
flagged.

### Out-of-scope / non-goals
- This issue builds the scaffolder, the dispatch-reachability conformance gate, and the
  probation/trust-tier field plus its resolver-side enforcement. It does not touch
  `Registry.validate()`'s schema rules or `Registry.stale()`'s staleness gate, capability-vocabulary
  widening, family inheritance, or cost/latency metadata — those are the sibling issue
  `pf-engine-registry-schema` (same wave), which owns pure schema/staleness/vocabulary changes to
  the same two files.
- It does not change `{#external-engines-never-gatekeepers}` (#283) or
  `{#external-engine-chaperone-dispatch}` (#318) — probation/trust-tier gates which *roles* a
  provider is eligible for, it does not grant any external engine gating authority over a Claude
  decision.
- It does not implement a standing/scheduled measurement harness for promotion — the
  promotion-threshold check reads accumulated telemetry on demand at resolution/CI time; it does
  not stand up a new scheduled monitoring service.
- It does not backfill `trust_tier` retroactively onto every existing incumbent row with a
  fabricated evidence trail — incumbent rows keep their current standing; only newly scaffolded
  rows default to probation.
- It does not build a provider-auth preflight or credential-management flow — that is
  `pf-provider-auth-preflight` (sibling issue), which is scoped and shipped separately.

### Dependencies / Assumptions
- Binding: DECISIONS `{#external-engines-never-gatekeepers}` (#283,
  `docs/engineering-journal/DECISIONS.md:1985`) — probation/trust-tier gating governs role
  eligibility, not gating authority.
- Binding: DECISIONS `{#external-engine-chaperone-dispatch}` (#318,
  `docs/engineering-journal/DECISIONS.md:2021`) — dispatch mechanics (offload vs. second-opinion)
  are unchanged; this issue only adds a trust gate in front of role resolution.
- Reuses the existing `EngineEntry`/`Registry` model
  (`plugins/saga/scripts/engine_registry.py:165-260`) and its `from_dict`/`validate` pipeline; this
  issue adds fields and call sites, it does not redesign the dataclass shape wholesale.
- Verified absent today: no scaffolder, no `docs/adding-a-provider.md`, no dispatch-reachability
  conformance test, and no `trust_tier`/`probation` field exist anywhere in this repo (confirmed via
  `find . -iname "add-engine*" -o -iname "adding-a-provider*"` and `grep -n "trust_tier\|probation"
  plugins/saga/scripts/engine_registry.py`, both empty/absent, run 2026-07-03).
- Sibling, same-wave issue `pf-engine-registry-schema` owns `Registry.validate()`/`Registry.stale()`
  CI wiring, capability-vocabulary widening, family inheritance, and cost/latency metadata on the
  same two files — coordinate merge order to avoid conflicting edits to
  `plugins/saga/scripts/engine_registry.py` and `plugins/saga/references/engine-registry.yaml`.
- Grounding references (absorbed ideas, from
  `docs/plans/plugin-fleet-ideation-2026-07-03/survivors/T2.json`):
  - `T2-F1-5` (primary, tier `structural`) — "Provider-onboarding scaffolder + registry
    conformance CI gate." Basis: `dod_sketch` calls for a merged PR (`tools/add-engine.sh` +
    `test_engine_registry_conformance.py` + `adding-a-provider.md`), verified by scaffolding a
    fake `deepseek/chat` row that passes conformance and a deliberately-broken row (missing
    capability, empty sources) that fails with a precise message.
  - `T2-F4-3` (facet, tier `structural`) — "Engine-onboarding conformance test fails CI, not
    dispatch." Basis: `dod_sketch` calls for a parametrized test asserting every row is reachable
    through the dispatch substrate plus a preflight entry plus every advertised capability
    resolvable, plus an `engine-onboarding.md` doc note, verified by the test going red on a
    deliberately-partial fixture row. Explicitly distinct from the schema-lint check
    (`T2-F2-4`, owned by sibling `pf-engine-registry-schema`): this test cross-checks
    registry↔dispatch↔preflight lockstep against the dead-wiring failure class.
  - `T2-F5-4` (facet, tier `structural`, basis type `external`) — "Quarantine-then-immune-tolerance:
    new providers enter offload-only shadow mode and earn advisory standing." Basis: `dod_sketch`
    calls for a merged PR adding a `probation`/`trust_tier` field on `EngineEntry` plus resolver
    logic refusing probationary providers for panel/advisory-reviewer roles plus a telemetry-fed
    promotion-threshold check, verified by resolver tests asserting a probation row resolves for
    offload but halts/is-excluded for a panel role. Explicitly distinct from a scaffolder or a
    conformance test — this is a trust-promotion ladder.
  - Consolidation rationale (`docs/plans/plugin-fleet-ideation-2026-07-03/` issue-map,
    `issue-map-final.json`): all three facets land on the same onboarding path for the same
    registry file and loader — a scaffolder, a dispatch-reachability CI gate, and a staged-trust
    field are the coherent "how a new provider gets in, and how much it's trusted on day one" story
    for the offload lane; shipping them as three unrelated patches risks the scaffolder emitting
    rows the conformance gate doesn't check, or a probation default the scaffolder forgets to set.

### Files expected to change
Indicative only — the exact set is `/plan`'s to determine.
- `tools/add-engine.sh` (new) — the provider-onboarding scaffolder.
- `tests/test_engine_registry_conformance.py` (new) — CI-invoked dispatch-reachability conformance
  suite.
- `docs/adding-a-provider.md` (new) — onboarding walkthrough for the scaffolder.
- `plugins/saga/references/engine-dispatch.md` — routing note documenting the conformance gate and
  the probation/advisory-standing distinction.
- `plugins/saga/scripts/engine_registry.py` — `EngineEntry` gains `trust_tier`/`probation` field.
- `plugins/saga/scripts/engine_resolver.py` — resolver logic refusing probationary rows for
  panel/advisory-reviewer roles.
- `plugins/saga/references/engine-registry.yaml` — existing rows annotated with explicit
  `trust_tier` (incumbents keep current standing; new fixture rows default to probation).
- `.github/workflows/ci.yml` — new named step invoking
  `tests/test_engine_registry_conformance.py`.
- `plugins/saga/.claude-plugin/plugin.json` — version bump.
- `.claude-plugin/marketplace.json` — plugin metadata sync.
- `plugins/saga/CHANGELOG.md` — entry for the scaffolder, conformance gate, and trust-tier field.
- `docs/engineering-journal/DECISIONS.md` — entry recording the probation-default and
  evidence-gated-promotion choices, each with a revisit-when condition.
- `tests/test_saga_engine_registry.py` — extended coverage for the `trust_tier` field and resolver
  refusal behavior.

### Tests to add or update
- Scaffolder happy path: scaffolding a fixture provider emits a row/stub that
  `Registry.load` accepts unedited.
- Scaffolder rejection: an incomplete scaffolder input fails with a field-naming error before any
  row is written.
- Conformance gate: `test_engine_registry_conformance.py` fails on a deliberately partial fixture
  row (unreachable capability, malformed invocation) and passes on the real registry file.
- Probation default: a scaffolded row defaults to `trust_tier: probation`.
- Resolver refusal: a probationary row resolves for offload-only dispatch but is excluded from
  panel/advisory-reviewer role resolution; an advisory-standing row still resolves for that role.
- Promotion threshold: a test seeding telemetry above/below the documented threshold correctly
  flags/does-not-flag a probationary row for promotion.

## Grounding References
- source_context: `docs/plans/plugin-fleet-ideation-2026-07-03/survivors/T2.json` (ids
  `T2-F1-5`, `T2-F4-3`, `T2-F5-4`)
- source_context: `docs/plans/2026-07-03-plugin-fleet-grounding-brief.md` §2 (binding-decision
  register)
- source_context: `docs/sdlc-issue-drafts/plugin-fleet/pf-engine-registry-schema.md` (sibling,
  same-wave issue on the same files — coordinate scope and merge order)

### Acceptance criteria
- [ ] Scaffolding a fixture provider emits a registry row and bridge stub that
  `Registry.validate()` accepts with zero manual edits. Check:
  `uv run pytest tests/test_saga_engine_registry.py -k scaffolder_emits_conformant_row` → passes.
- [ ] Scaffolding with an incomplete input (missing capability rating or empty `sources`) fails
  with a precise, field-naming error and writes no row. Check:
  `uv run pytest tests/test_saga_engine_registry.py -k scaffolder_rejects_incomplete_input` →
  passes.
- [ ] A named CI conformance test asserts every registry row is reachable through the dispatch
  substrate (capability resolution, engine resolution, valid invocation, every advertised
  capability a member of `capabilities`), and fails distinctly on a deliberately partial fixture
  row. Check: `uv run pytest tests/test_engine_registry_conformance.py` → passes on the real
  registry; `uv run pytest tests/test_engine_registry_conformance.py -k dead_wired_row_fails` →
  demonstrates the failure on a fixture.
- [ ] `EngineEntry` carries `trust_tier`/`probation`, defaulting new/scaffolded rows to
  probationary standing. Check:
  `uv run pytest tests/test_saga_engine_registry.py -k trust_tier_default` → passes.
- [ ] Resolver logic refuses a probationary row for panel/advisory-reviewer role resolution while
  still permitting it for offload-only dispatch. Check:
  `uv run pytest tests/test_saga_engine_registry.py -k probation_role_refusal` → passes.
- [ ] A telemetry-fed promotion-threshold check correctly flags/does-not-flag a probationary row
  for advisory promotion. Check:
  `uv run pytest tests/test_saga_engine_registry.py -k promotion_threshold` → passes.
- [ ] `docs/adding-a-provider.md` documents the scaffolder's inputs/outputs and matches its actual
  flag set. Check: `test -f docs/adding-a-provider.md` → exists; manual read confirms it matches
  `tools/add-engine.sh --help` output.
- [ ] `DECISIONS.md` carries an entry for the probation-default and evidence-gated-promotion
  choices, each with a revisit-when condition. Check:
  `grep -n "revisit-when" docs/engineering-journal/DECISIONS.md` → includes new entries for this
  change.
- [ ] Release-surface metadata (plugin version, marketplace entry, CHANGELOG) is updated in the
  same PR. Check: `git diff --name-only` includes `plugins/saga/.claude-plugin/plugin.json`,
  `.claude-plugin/marketplace.json`, and `plugins/saga/CHANGELOG.md`.
- [ ] Full suite, format, lint, and types stay green. Check:
  `uv run pytest && uv run ruff format --check . && uv run ruff check . && uv run mypy plugins/ scripts/ tests/ --ignore-missing-imports`
  → all pass.

### Verification
```bash
# Registry/resolver unit tests, including scaffolder, trust-tier, and promotion coverage
uv run pytest tests/test_saga_engine_registry.py -v

# CI-invoked dispatch-reachability conformance gate
uv run pytest tests/test_engine_registry_conformance.py -v

# Confirm CI wiring is present, not just the test file
grep -n "engine_registry_conformance\|conformance" .github/workflows/ci.yml

# Confirm DECISIONS.md carries the required entries
grep -n "revisit-when" docs/engineering-journal/DECISIONS.md | tail -5

# Full repo gate (CI parity)
uv run pytest && uv run ruff format --check . && uv run ruff check . && uv run mypy plugins/ scripts/ tests/ --ignore-missing-imports
```
Expected: all green; the CI file names a step that runs the conformance suite against the real
`engine-registry.yaml`; a fixture provider scaffolds cleanly and a fixture probationary row is
excluded from panel-role resolution; `DECISIONS.md` contains new entries with revisit-when
conditions for the probation-default and evidence-gated-promotion choices.

### Recommended executor profile
- **Model:** sonnet
- **Effort:** medium
- **Backend:** inline
- **External-LLM posture:** none
- **Justification:** This is a scaffolder-plus-CI-test-plus-schema-field addition against an
  already-implemented, already-tested `EngineEntry`/`Registry` model — the shape of the scaffolder
  output, the conformance assertions, and the probation-field semantics are already specified by
  the absorbed `dod_sketch`es. There is no architectural ambiguity requiring opus-level judgment,
  and this is registry/schema/CI/scaffold work with no case for an external engine to generate or
  review it with an advantage.

### Release-surface checklist
This issue changes plugin behavior (new scaffolder tool, new CI-gated conformance test, and a new
resolver-visible schema field), so the following must land in the same PR:
- [ ] `plugins/saga/.claude-plugin/plugin.json` — version bump.
- [ ] `.claude-plugin/marketplace.json` — plugin metadata sync.
- [ ] `plugins/saga/CHANGELOG.md` — entry describing the scaffolder, the dispatch-reachability
  conformance gate, and the probation/trust-tier field with its promotion path.
- [ ] Drift-guard/conformance test (`tests/test_engine_registry_conformance.py`) wired into
  `.github/workflows/ci.yml` as a named step, so a future dead-wired or wrongly-trusted row fails
  CI instead of surfacing at live dispatch.

### Handoff maturity
requirements-ready

### Suggested next action
Use `/plan <issue>` to create an implementation plan.

### Source context
- Source: `docs/plans/plugin-fleet-ideation-2026-07-03/survivors/T2.json` (ids `T2-F1-5`,
  `T2-F4-3`, `T2-F5-4`)
- Source type: ideation-survivor
- Source title: Provider onboarding: scaffolder, CI conformance gate, and shadow-mode standing

### Context library links

_none_

### Intent

Onboarding a new external-engine provider into `plugins/saga/references/engine-registry.yaml` today means hand-authoring a row against `plugins/saga/scripts/engine_registry.py`'s validation rules with no scaffolder, no CI gate dedicated to catching a broken or incomplete row before it ever reaches dispatch, and no staged-trust path — a newly added row is immediately eligible for every role, including panel/advisory-reviewer roles, with the same standing as a benchmark-validated incumbent like `codex/gpt-5.5-high`. Three independently found ideation facets converge on this same onboarding-cost/onboarding-safety gap: a scaffolder that emits a conformant row plus a bridge stub, a CI conformance suite that fails the pull request (not a live dispatch) when a row is wired incompletely, and a probation/trust-tier field that keeps a new row offload-only until it earns advisory standing. This issue lands all three as one coherent onboarding path — not three separate patches — because they share the same registry schema, the same `EngineEntry`/`Registry` model, and the same "problem surfaces before dispatch, not during it" design goal.

## Created Issue

- URL: https://github.com/infiquetra/infiquetra-claude-plugins/issues/455
- Number: 455
- Created at: 2026-07-04T08:23:29.822979+00:00

