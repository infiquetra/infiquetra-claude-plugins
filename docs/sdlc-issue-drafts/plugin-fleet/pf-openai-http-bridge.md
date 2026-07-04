---
title: "capability: one OpenAI-compatible HTTP bridge — providers become registry rows, Ollama as first $0 row"
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

# capability: one OpenAI-compatible HTTP bridge — providers become registry rows, Ollama as first $0 row

### Objective

Stand up the external-engine offload lane: today external-engine dispatch (codex, agy) is a
per-engine if-ladder with no shared HTTP substrate and no registry seam for adding a new
OpenAI-compatible provider. This capability replaces the if-ladder with one substrate-keyed
adapter table so any provider that speaks the OpenAI HTTP wire format — starting with Ollama as
the first zero-cost row, and DeepSeek as the first paid API-key row — is a registry row, not a
new code path.

## Problem / Motivation

- **No shared HTTP substrate today.** The fleet's external-engine dispatch is codex- and
  agy-specific: `plugins/agy/scripts/agy_delegate.py` and the codex plugin
  (`~/.claude/plugins/cache/openai-codex`) each own their own launch/result path. There is no
  `engine_dispatch` adapter table and no `engine_bridge_http.py` anywhere in this repo today
  (verified: `grep -rn "engine_dispatch\|engine_bridge_http" plugins/` returns nothing). Adding a
  new HTTP-speaking provider currently means writing a new bespoke integration, not adding a row.
- **`ENGINE_INTENTS` is authored but has nowhere generic to land.** `/plan` authors the
  `ENGINE_INTENTS` producer/consumer pair (`plugins/saga/skills/plan/SKILL.md:303-304`) and
  team-execution renders it into the Step A7 worker table
  (`plugins/team-execution/skills/team-execution/SKILL.md:226-233` →
  `plugins/team-execution/skills/team-execution/references/external-engine-workers.md`), where
  `Engine` is either an explicit `<engine-key>` or a `cap:<capability-key>` selector
  (`SKILL.md:231-233`). That table assumes a resolvable engine registry exists; it does not yet.
- **Operator ask for non-GPT/Gemini engines is an open seed.** The operator's stated ask —
  "a plugin able to act as external engine in workflows/teams for non-GPT/Gemini LLMs (Ollama
  subscription, DeepSeek API), maybe API-key routing, one or several plugins, task-based
  recommendations" (seed `S-27`, `docs/plans/plugin-fleet-ideation-2026-07-03/survivors/seeds.json`)
  — has no registry-driven implementation today.
- **Binding constraint this capability must honor:** external engines are never gatekeepers.
  `{#external-engines-never-gatekeepers}` (issue #283) — Claude remains verifier-of-record for
  every gated decision; codex/agy/Ollama/DeepSeek are generator, advisory-reviewer, or non-gated
  worker roles only, structurally enforced. `{#external-engine-chaperone-dispatch}` (issue #318)
  — external engines in teams are chaperone dispatch (offload → sonnet/medium, second-opinion →
  opus/high), never a second executor kind, residency, or git participant. This bridge dispatches
  work to engines; it does not grant them gate authority.
- **Repeated resolution/preflight cost is unmeasured but structurally present.** Every dispatch
  through the current per-engine paths re-probes availability (e.g., `shutil.which`-style checks)
  with no per-run memoization seam, because no shared `resolve`/`resolve_role` path exists yet to
  memoize against.

(Grounding source: `docs/plans/2026-07-03-plugin-fleet-grounding-brief.md` §§1–2, 5;
`docs/plans/plugin-fleet-ideation-2026-07-03/survivors/T2.json` entries `T2-F1-1`, `T2-F1-6`,
`T2-F4-2`, `T2-F6-7`; `docs/plans/plugin-fleet-ideation-2026-07-03/survivors/seeds.json` entry
`S-27`.)

## Definition of Done

A merged PR that:

1. Adds a substrate-keyed `engine_dispatch` adapter table (module path to be fixed by `/plan`,
   e.g. `plugins/team-execution/scripts/engine_dispatch.py`) that replaces the codex/agy
   if-ladder as the single dispatch point for any registry row declaring `transport=http`.
2. Adds a generic `engine_bridge_http.py` (or equivalent) implementing the OpenAI-compatible
   chat/completions wire format, driven entirely by registry row fields (base URL, auth mode,
   model id) — no provider-specific branching inside the bridge itself.
3. Adds Ollama and DeepSeek as the first two registry rows: Ollama keyless
   (`base_url: http://localhost:11434`, no API key required), DeepSeek API-key-routed.
4. Adds a run-scoped resolution/preflight memo threaded through the resolve path, keyed on
   `engine_id` for preflight and `(capability, token_estimate)` for resolution, invalidated at
   run boundary.
5. Ships a dispatch-adapter contract (`dispatch-adapter-contract.md` or equivalent) plus a shared
   `FakeHttpRunner` test double and a contract test suite.

Verified by:

- A dispatch unit test asserting byte-identical `AdvisoryEvidence` is produced whether the call
  goes through the adapter table or a fake HTTP runner (no live network).
- An availability-gated smoke test against `localhost:11434` that records `status: ok` when
  Ollama is reachable and skips (not fails) when it is not.
- A contract test that fails a dead/no-op adapter (one that returns without invoking the runner)
  and passes a conformant one.
- A call-counting fake asserting `shutil.which`/preflight is invoked once per engine across N
  resolves in a single run (a 10-resolve loop against one engine drops from 10 probe calls to 1).
- Full repo gate stays green: `uv run pytest && uv run ruff check . && uv run mypy plugins/ scripts/ tests/ --ignore-missing-imports`.

### Acceptance criteria
- [ ] **AC1 (T2-F1-1 — primary).** A substrate-keyed adapter table dispatches any registry row
      declaring `transport=http` through one generic bridge, with no per-provider branch inside
      the bridge.
      Check: `uv run pytest tests/test_engine_dispatch.py -k transport_http_bridge -v` → passes,
      and asserting the same test body runs unmodified against both an Ollama-shaped row and a
      DeepSeek-shaped row (parametrized).
- [ ] **AC2 (T2-F1-6 — facet).** A fake, non-conformant adapter that returns without invoking the
      HTTP runner is caught by the contract test (red); a conformant adapter passes (green).
      Check: `uv run pytest tests/test_dispatch_adapter_contract.py -v` → the
      `test_dead_adapter_fails` case fails against the no-op fixture and passes against the real
      adapter; `test_conformant_adapter_passes` is green.
- [ ] **AC3 (T2-F4-2 — facet).** The Ollama registry row resolves and dispatches keyless — no
      API key required — as the first $0 offload engine.
      Check: `uv run pytest tests/test_engine_registry.py -k ollama_keyless_resolve -v` → passes;
      when `localhost:11434` is reachable, an additional smoke assertion records
      `status: ok` with no credential supplied.
- [ ] **AC4 (S-27 — dedup-merged, DeepSeek facet).** The DeepSeek registry row resolves and
      dispatches via API-key routing (key read from the documented env var / secret path, never
      hardcoded), and its output is tagged `advisory`/non-gated — it never returns a gate
      verdict.
      Check: `uv run pytest tests/test_engine_registry.py -k deepseek_api_key_routing -v` →
      passes, and asserts the returned envelope's role field is `advisory`, never a gate-decision
      field.
- [ ] **AC5 (T2-F6-7 — facet).** Resolution and preflight are memoized per run: repeated
      dispatches to the same engine within one run invoke the availability probe once, not once
      per call.
      Check: `uv run pytest tests/test_engine_dispatch.py -k resolve_memoization -v` → a
      call-counting fake asserting a 10-resolve loop against one engine invokes the preflight
      probe exactly once (down from 10 without the memo).
- [ ] **AC6 (never-gatekeepers guard, cross-cutting).** No code path in the new bridge or
      adapter table allows an engine-produced result to set or override a gate/verdict field.
      Check: `uv run pytest tests/test_engine_dispatch.py -k never_gatekeeper_guard -v` → passes,
      asserting an engine-tagged `AdvisoryEvidence` result is structurally rejected if it attempts
      to populate a gate-status field.
- [ ] **Full suite, lint, and types stay green.**
      Check: `uv run pytest && uv run ruff check . && uv run mypy plugins/ scripts/ tests/ --ignore-missing-imports` → all pass.

- [ ] Full repo gate passes: `uv run pytest && uv run ruff check .`
### Out-of-scope / non-goals
**In scope:**
- One generic OpenAI-compatible HTTP bridge + substrate-keyed adapter table.
- Ollama (keyless) and DeepSeek (API-key) as the first two registry rows.
- Run-scoped resolution/preflight memoization.
- Dispatch-adapter contract + fake-runner test scaffolding.

**Non-goals (explicitly out of scope for this issue):**
- Task-based engine *recommendation* logic (which engine to pick for which task type) — S-27's
  "task-based recommendations" facet is deferred; this issue only makes engines dispatchable as
  registry rows, it does not add a recommender.
- Any change to gate/verdict authority — external engines remain non-gated per
  `{#external-engines-never-gatekeepers}` (#283); no gate-authority code changes here.
- Any change to team-execution's chaperone-dispatch tiering behavior
  (`{#external-engine-chaperone-dispatch}` #318) — this issue adds the transport, not the
  tiering policy.
- Migrating existing codex/agy dispatch call sites onto the new adapter table — this issue lands
  the adapter table and the two new rows; a follow-up issue migrates codex/agy onto it to avoid
  scope creep on a structural change.
- Additional providers beyond Ollama and DeepSeek (e.g., other OpenAI-compatible endpoints) —
  the registry seam is designed to make future providers a row-add, but adding more rows is
  follow-on work.
- Standing/scheduled cost-latency telemetry beyond the per-run memo — no persistent dashboard or
  cross-run cost ledger in this issue.

## Grounding References

- `docs/plans/2026-07-03-plugin-fleet-grounding-brief.md` §1 (fleet map, model/effort reality),
  §2 (binding-decision register), §5 (pre-existing seeds).
- `docs/plans/plugin-fleet-ideation-2026-07-03/survivors/T2.json`:
  - `T2-F1-1` (primary) — "OpenAI-compatible HTTP bridge + substrate-keyed dispatch adapter
    table."
  - `T2-F1-6` (facet) — "Dispatch-adapter contract + fake-runner no-op guard."
  - `T2-F4-2` (facet) — "Ollama as first $0 offload row."
  - `T2-F6-7` (facet) — "Per-run resolution+preflight memoization."
- `docs/plans/plugin-fleet-ideation-2026-07-03/survivors/seeds.json`:
  - `S-27` (dedup-merged) — basis: operator statement "a plugin able to act as external engine
    in workflows/teams for non-GPT/Gemini LLMs (Ollama subscription, DeepSeek API), maybe
    API-key routing, one or several plugins, task-based recommendations."
- Binding decisions this issue must not violate:
  - `{#external-engines-never-gatekeepers}` (issue #283) — external engines are never
    gate-authority; structurally enforced. Revisit-when: a read-only-sandbox profile ships or
    team-execution gains a formal external-engine worker slot.
  - `{#external-engine-chaperone-dispatch}` (issue #318) — external engines in teams are
    chaperone dispatch only, never a second executor kind or git participant.
- Code seams referenced (verified present/absent as stated):
  - `plugins/saga/skills/plan/SKILL.md:303-304` (`ENGINE_INTENTS` authored in `/plan`).
  - `plugins/team-execution/skills/team-execution/SKILL.md:226-233` and
    `plugins/team-execution/skills/team-execution/references/external-engine-workers.md`
    (rendered worker table with `Engine`/`Intent` columns — the consumer side this bridge feeds).
  - `plugins/saga/scripts/execution_spec.py:52-53` (existing `MODELS`/`EFFORTS` vocabulary —
    unrelated lever, cited only to confirm no existing engine-registry vocabulary exists
    alongside it).
  - Verified absent today: no `engine_dispatch` module, no `engine_bridge_http.py`, no
    `resolve_role`/registry module anywhere under `plugins/` (checked via repo-wide grep) —
    this issue is a genuine "stand up," not a refactor of existing code.

## Recommended Executor Profile

- **Model:** sonnet
- **Effort:** high
- **Backend:** inline
- **External-LLM posture:** none — this issue *builds* the external-engine bridge; it must not
  itself be built by dispatching to an external engine while the never-gatekeepers/chaperone
  constraints are being encoded, to avoid a self-referential trust problem during construction.
- **Justification:** sonnet/high is at or below the sonnet tier; no justification for exceeding
  it is required. This is new-adapter-table-plus-two-registry-rows work with clear test
  contracts (dispatch equivalence, contract red/green, memoization call-count) — mechanical
  enough for sonnet at high effort, not judgment-heavy enough to warrant opus.

## Release-Surface Checklist

This issue changes plugin behavior (new dispatch surface, new registry rows) — update in the
same PR:

- [ ] `plugins/team-execution/.claude-plugin/plugin.json` (or wherever the adapter table lands)
      — version bump and changelog-relevant description update if the dispatch surface is
      user-facing.
- [ ] `.claude-plugin/marketplace.json` — reflect the version bump for the affected plugin.
- [ ] `plugins/team-execution/CHANGELOG.md` (or the owning plugin's CHANGELOG) — entry
      describing the new OpenAI-compatible HTTP bridge and the two new registry rows.
- [ ] Any version/metadata drift-guard tests (e.g., a marketplace-vs-plugin.json parity test) —
      confirmed still green after the bump.
- [ ] `docs/engineering-journal/DECISIONS.md` — entry for the registry-row pattern chosen
      (substrate-keyed adapter table over per-provider branching), with rejected alternatives
      and a revisit-when condition.

## Files Expected to Change

Indicative only — exact set is `/plan`'s to determine:

- `plugins/team-execution/scripts/engine_dispatch.py` (new)
- `plugins/team-execution/scripts/engine_bridge_http.py` (new)
- `plugins/team-execution/skills/team-execution/references/dispatch-adapter-contract.md` (new)
- `plugins/team-execution/skills/team-execution/references/external-engine-workers.md` (updated
  to reference the new registry rows)
- `tests/test_engine_dispatch.py` (new)
- `tests/test_dispatch_adapter_contract.py` (new)
- `tests/test_engine_registry.py` (new)
- `plugins/team-execution/.claude-plugin/plugin.json`
- `.claude-plugin/marketplace.json`
- `plugins/team-execution/CHANGELOG.md`
- `docs/engineering-journal/DECISIONS.md`

### Verification
```bash
# Adapter table dispatch equivalence + memoization
uv run pytest tests/test_engine_dispatch.py -v

# Dispatch-adapter contract (red on dead adapter, green on conformant)
uv run pytest tests/test_dispatch_adapter_contract.py -v

# Registry rows: Ollama keyless, DeepSeek API-key
uv run pytest tests/test_engine_registry.py -v

# Full repo gate (CI parity)
uv run pytest && uv run ruff check . && uv run mypy plugins/ scripts/ tests/ --ignore-missing-imports
```

Expected: all green; `test_engine_dispatch.py -k resolve_memoization` demonstrates the
10-probes-to-1 collapse; `test_engine_registry.py -k ollama_keyless_resolve` demonstrates a
keyless resolve when `localhost:11434` is reachable (skipped, not failed, when it is not).

### Handoff maturity

requirements-ready

### Suggested next action

Use `/plan <issue>` to create an implementation plan.

### Source context

- Source: `docs/plans/plugin-fleet-ideation-2026-07-03/survivors/T2.json` (`T2-F1-1`, `T2-F1-6`,
  `T2-F4-2`, `T2-F6-7`) and `docs/plans/plugin-fleet-ideation-2026-07-03/survivors/seeds.json`
  (`S-27`)
- Source type: ideation survivor set (issue-map)
- Source title: "One OpenAI-compatible HTTP bridge: providers become registry rows, Ollama as
  first $0 row"

### Intent

- **No shared HTTP substrate today.** The fleet's external-engine dispatch is codex- and agy-specific: `plugins/agy/scripts/agy_delegate.py` and the codex plugin (`~/.claude/plugins/cache/openai-codex`) each own their own launch/result path. There is no `engine_dispatch` adapter table and no `engine_bridge_http.py` anywhere in this repo today (verified: `grep -rn "engine_dispatch\|engine_bridge_http" plugins/` returns nothing). Adding a new HTTP-speaking provider currently means writing a new bespoke integration, not adding a row. - **`ENGINE_INTENTS` is authored but has nowhere generic to land.** `/plan` authors the `ENGINE_INTENTS` producer/consumer pair (`plugins/saga/skills/plan/SKILL.md:303-304`) and team-execution renders it into the Step A7 worker table (`plugins/team-execution/skills/team-execution/SKILL.md:226-233` → `plugins/team-execution/skills/team-execution/references/external-engine-workers.md`), where `Engine` is either an explicit `<engine-key>` or a `cap:<capability-key>` selector (`SKILL.md:231-233`). That table assumes a resolvable engine registry exists; it does not yet. - **Operator ask for non-GPT/Gemini engines is an open seed.** The operator's stated ask — "a plugin able to act as external engine in workflows/teams for non-GPT/Gemini LLMs (Ollama subscription, DeepSeek API), maybe API-key routing, one or several plugins, task-based recommendations" (seed `S-27`, `docs/plans/plugin-fleet-ideation-2026-07-03/survivors/seeds.json`) — has no registry-driven implementation today. - **Binding constraint this capability must honor:** external engines are never gatekeepers. `{#external-engines-never-gatekeepers}` (issue #283) — Claude remains verifier-of-record for every gated decision; codex/agy/Ollama/DeepSeek are generator, advisory-reviewer, or non-gated worker roles only, structurally enforced. `{#external-engine-chaperone-dispatch}` (issue #318) — external engines in teams are chaperone dispatch (offload → sonnet/medium, second-opinion → opus/high), never a second executor kind, residency, or git participant. This bridge dispatches work to engines; it does not grant them gate authority. - **Repeated resolution/preflight cost is unmeasured but structurally present.** Every dispatch through the current per-engine paths re-probes availability (e.g., `shutil.which`-style checks) with no per-run memoization seam, because no shared `resolve`/`resolve_role` path exists yet to memoize against.

### Context library links

_none_

### Files expected to change

- `plugins/agy/scripts/agy_delegate.py`
- `plugins/team-execution/skills/team-execution/references/external-engine-workers.md`
- `docs/plans/plugin-fleet-ideation-2026-07-03/survivors/seeds.json`
- `docs/plans/2026-07-03-plugin-fleet-grounding-brief.md`
- `docs/plans/plugin-fleet-ideation-2026-07-03/survivors/T2.json`
- `plugins/team-execution/scripts/engine_dispatch.py`
- `plugins/team-execution/.claude-plugin/plugin.json`
- `.claude-plugin/marketplace.json`

### Tests to add or update

- `tests/test_dispatch_adapter_contract.py`
- `tests/test_engine_dispatch.py`
- `tests/test_engine_registry.py`

## Created Issue

- URL: https://github.com/infiquetra/infiquetra-claude-plugins/issues/387
- Number: 387
- Created at: 2026-07-04T07:57:26.701277+00:00

