---
title: "capability: typed second-opinion reconciliation — reconcile.py, intent→recipe map, divergence intent, failure-signal recapture, durable ledger"
repo: infiquetra-claude-plugins
type: capability
team: campps
project: operations
status: Idea
labels: capability, hermes-task, needs-plan
risk: high
handoff_maturity: requirements-ready
tier: structural
wave: wave-1
objective: "Stand up the external-engine offload lane"
---

# capability: typed second-opinion reconciliation — reconcile.py, intent→recipe map, divergence intent, failure-signal recapture, durable ledger

### Objective

Stand up the external-engine offload lane

### Tier

structural

### Wave

wave-1

## Summary

Today the chaperone-dispatch protocol (`plugins/team-execution/skills/team-execution/references/external-engine-workers.md`) lets an external engine (codex/agy) attach a `claim_provenance` verdict alongside its own evidence — but that verdict is untyped prose (`worker-manifest.md:81`: "engine returned prose claims alongside its evidence, e.g. a second-opinion review verdict"), there is exactly one merge behavior regardless of `engine_intent` (`offload` or `second-opinion` — the only two intents that exist today, `external-engine-workers.md:35`), a chaperone-rejected offload silently vanishes instead of counting as signal, the advisory-jury fan-out for hardest calls has no cap-bounded reconciliation shape, and nothing writes a durable record of what got reconciled so `/retro` can learn from it. This capability replaces the freeform prose reconciliation with a typed object, adds a registry mapping each `engine_intent` to an explicit merge protocol, introduces a third intent (`divergence`) where convergence between Claude and the external engine is itself the failure signal, recaptures chaperone-rejected offloads as signal instead of discarding them, bounds the advisory-jury panel fan-out, and writes every reconcile/apply to a durable ledger.

## Problem Frame

Six converging gaps, each independently observed against the shipped chaperone-dispatch contract:

1. **No typed reconciliation object.** `worker-manifest.md:81` documents `claim_provenance` as an optional, producer-`claimed`-only prose field — "chaperone may populate `claim_provenance` [with] engine's claimed layer." There is no schema for what a reconciled-vs-dropped verdict looks like; a net-new finding the external engine raised that Claude silently drops during adjudication (`engine_dispatch.adjudicate_manifest`, referenced in `worker-manifest.md:81`) is currently indistinguishable from a finding that was properly reconciled, because both paths just produce prose.
2. **One merge behavior for two semantically opposite intents.** `external-engine-workers.md:35` documents exactly two `engine_intent` values, `offload` and `second-opinion`, each locking a different chaperone tier at plan time (`plugins/saga/skills/plan/SKILL.md:295-305`, the `{#external-engine-chaperone-dispatch}` KTD2 decision, `docs/engineering-journal/DECISIONS.md:2021`). The tier already forks by intent; the reconciliation/merge protocol at adjudication time does not — there is no registry, just whatever `engine_dispatch.adjudicate_manifest` happens to do today, undocumented as intent-specific behavior.
3. **No third intent for divergence-seeking review.** The two shipped intents (`offload`, `second-opinion`) both implicitly treat agreement as success. A red-team / divergence-seeking use — external engine deliberately probing for daylight between its read and Claude's — has no home; convergence in that mode is a signal that the review wasn't adversarial enough, not a pass.
4. **Chaperone-rejected offload is silently discarded.** The chaperone-dispatch protocol has no disposition for "offload happened, chaperone rejected the result" beyond the existing `fell-back-to-claude` / `substituted-engine` dispositions (`worker-manifest.md:60`), neither of which carries a non-empty rejection note forward as second-opinion signal — the rejection is currently a dead end, not itself an actionable input to the reviewer/validator consensus machinery (`SKILL.md` Step B2/B3, referenced in `external-engine-workers.md`).
5. **Advisory-jury panel fan-out has no cap-bounded reconciliation shape.** The moonshot-tier "hardest calls get an external-engine advisory jury with Claude as foreman" concept has no analog to the existing `VERIFY_N_CAP = 7` hard cap that already bounds adversarial-verifier fan-out (`plugins/saga/scripts/execution_spec.py:114`, `plugins/saga/references/execution-spec.md:53`). Without an equivalent cap and a mandated Claude-adjudication step, an uncapped `role_kind="panel"` fan-out risks the same rate-limit fan-out-kill pattern already logged three separate times against this repo's journal (grounding brief §6, pattern 4: "6 of 7 agents failed on rate-limiting").
6. **No durable ledger, no `/retro` re-validation loop.** Nothing today writes a record of a reconcile/apply event that `/retro` (the terminal, advisory retro phase) can read back to propose registry updates. The intent→recipe registry from gap 2, once it exists, has no mechanism to re-validate itself against real outcomes — it would ship once and never learn.

This capability is one of the wave-1 lane items standing up the external-engine offload lane per the ideation objective, and is scoped tightly by the standing binding decision that **external engines are never gatekeepers** (`{#external-engines-never-gatekeepers}`, #283, `docs/engineering-journal/DECISIONS.md:1985`): `engine_dispatch.satisfy_gate()` (`plugins/saga/scripts/engine_dispatch.py:238-258`) already hard-requires `evidence.verified_by_claude == True` before any advisory evidence counts toward a verdict. Typing the reconciliation object does not change who gates — it only removes prose ambiguity about what was adjudicated and how.

## Actors

- A1. **Reconciliation controller (`reconcile.py`, new)** — the new module; consumes a chaperone's raw engine output plus the unit's `engine_intent`, resolves the applicable merge protocol from the intent→recipe registry, produces the typed reconciliation object, and writes the ledger record.
- A2. **Chaperone worker** — existing actor (`external-engine-workers.md`); calls the reconciliation controller instead of hand-rolling prose merge/adjudication logic itself.
- A3. **Claude (verifier-of-record)** — existing actor; remains the sole adjudicator per `{#external-engines-never-gatekeepers}` — the reconciliation object records Claude's adjudication, it does not substitute for it.
- A4. **`/retro`** — existing lifecycle phase; new consumer of the ledger, reading reconcile/apply records to surface gated registry-update proposals.
- A5. **Advisory jury panel (moonshot facet)** — new, cap-bounded fan-out of external engines for hardest-call review, with Claude as foreman adjudicating the panel's reconciled output before anything is recorded.

## Requirements

**Typed reconciliation object (absorbs T1-F2-4, primary)**

- R1. Replace the freeform-prose `claim_provenance` merge path (`worker-manifest.md:81`) with a typed reconciliation object carrying, at minimum, per-item adjudicated flags (`reconciled` / `dropped` / `overridden`) plus the adjudicator's identity and rationale per item.
- R2. A net-new finding the external engine raised that does not appear in the reconciled output must be an explicit, named `dropped` entry — never a silent omission. A dropped net-new finding blocks verification (i.e. the gate cannot pass while an unaccounted-for net-new finding exists in the raw engine output but not in the typed reconciliation object).

**Intent → recipe registry (absorbs T1-F4-3, facet)**

- R3. Add an intent→recipe registry mapping each `engine_intent` value to exactly one documented merge protocol (data, not prose) — analogous in shape to the existing `Unit.engine`/`Unit.capability` fields already load-bearing in `execution_spec.py:241-265`.
- R4. The registry must be referenced from both the reconciliation controller's dispatch path and `external-engine-workers.md` §4 (the context-package / resolution section), so the documented contract and the runtime behavior cannot drift apart.
- R5. Registry parity is enforced by test: every value the `engine_intent` field can validly take resolves to exactly one recipe entry — no intent silently falls through to a default.

**Divergence intent (absorbs T1-F3-2, facet)**

- R6. Add a third `engine_intent` value, `divergence`, to the existing two (`offload`, `second-opinion`) documented at `external-engine-workers.md:35`.
- R7. `divergence` must validate as an accepted value in `execution_spec.py`'s unit validation (alongside the existing `offload`/`second-opinion` validation).
- R8. `divergence` resolves to `opus`/`high` in the plan-time tier table (`plugins/saga/skills/plan/SKILL.md:295-305`, the ordered ladder already used for `second-opinion` per KTD2, `docs/engineering-journal/DECISIONS.md:2021`) — red-team/divergence-seeking review is adversarial verification, not cost-motivated delegation, so it inherits the heavier-tier default already established for `second-opinion` rather than the lighter `offload` default.
- R9. For a `divergence`-intent unit, the reconciliation object's merge protocol (per R3) treats *agreement* between Claude and the external engine as the notable outcome requiring explicit review, not as an automatic pass — inverting the default posture of `offload`/`second-opinion`.

**Failure-signal recapture (absorbs T1-F1-4, facet)**

- R10. Add an explicit disposition for a chaperone-rejected offload, distinct from the existing `fell-back-to-claude` / `substituted-engine` dispositions (`worker-manifest.md:60`).
- R11. A chaperone-rejected offload must emit a non-empty rejection note in the manifest's dispatch record.
- R12. The rejection note is treated as second-opinion signal and surfaced to the existing reviewer/validator consensus machinery (`SKILL.md` Step B2/B3) — never silently discarded from the run's evidence trail.

**Advisory-jury panel cap (absorbs T1-F6-6, facet, moonshot)**

- R13. Wire a `role_kind="panel"` fan-out mode with a hard, overridable cap analogous to `VERIFY_N_CAP` (`plugins/saga/scripts/execution_spec.py:114`) — an `PANEL_N_CAP` (or equivalently named constant) bounding the number of external engines in a single advisory-jury fan-out.
- R14. A fan-out request above the cap hard-blocks (validation failure), mirroring the existing `VERIFY_N_CAP` guard behavior (`execution-spec.md:53`, `:204`) rather than silently truncating.
- R15. Claude adjudication (foreman role) is mandatory before any panel output is recorded — no panel member's raw output reaches the reconciliation ledger unadjudicated, consistent with `{#external-engines-never-gatekeepers}`.

**Durable ledger (absorbs T1-F4-4, facet)**

- R16. Every reconcile/apply event writes a durable ledger record (append-only, consistent with this repo's existing append-only ledger convention, `docs/engineering-journal/DECISIONS.md:960`/`:1097` referenced in the fleet grounding brief).
- R17. `/retro` gains a read hook over the ledger that can emit gated registry-update proposals (i.e. a proposal to change an intent→recipe mapping) — proposals are gated (require explicit approval), never auto-applied, consistent with `/retro`'s existing terminal-advisory-phase posture.

## Key Flows

- F1. **Normal offload reconciliation.** Trigger: chaperone dispatches an `offload`-intent unit, engine returns output. Reconciliation controller resolves the `offload` recipe from the registry, produces a typed reconciliation object (all items `reconciled` or explicitly `dropped`), writes the ledger record. Covers R1, R3, R16.
- F2. **Second-opinion reconciliation with a dropped net-new finding.** Trigger: external engine's second-opinion review raises a finding Claude's adjudication does not carry forward. Reconciliation controller must record it as an explicit `dropped` entry; verification blocks until the drop is accounted for (accepted-with-rationale or reinstated). Covers R1, R2.
- F3. **Divergence-intent review.** Trigger: a `divergence`-intent unit's external engine output agrees with Claude's independent read. Reconciliation controller's `divergence` recipe flags the agreement itself for explicit review rather than auto-passing. Covers R6–R9.
- F4. **Chaperone rejects an offload.** Trigger: chaperone dispatches an offload, engine output fails chaperone-side quality checks. Reconciliation controller emits the new rejected disposition with a non-empty rejection note; note flows into reviewer/validator consensus as signal. Covers R10–R12.
- F5. **Advisory-jury panel fan-out.** Trigger: a hardest-call unit requests `role_kind="panel"` fan-out with N external engines. If N exceeds the cap, validation hard-blocks. Otherwise, all N engines run, Claude-foreman adjudicates the panel's combined output, and only the adjudicated result is recorded. Covers R13–R15.
- F6. **`/retro` mines the ledger.** Trigger: operator runs `/retro`. `/retro` reads accumulated ledger records, surfaces a gated proposal to update an intent→recipe mapping based on observed reconciliation outcomes. Covers R16, R17.

### Out-of-scope / non-goals
- Does not change who gates. `{#external-engines-never-gatekeepers}` (#283) stays fully in force — this capability types and records the reconciliation, it does not let an external engine's output satisfy a gate on its own.
- Does not change the existing chaperone-tier resolution mechanics from `{#external-engine-chaperone-dispatch}` (#318, KTD2) — the plan-time tier table lookup for `offload`/`second-opinion` is unchanged; this capability only adds `divergence` as a third value into that same table.
- Does not introduce a second executor kind or give the external engine write/residency/git participation — the chaperone-worker shape from `{#external-engine-chaperone-dispatch}` KTD1 is unchanged.
- Does not build the standing/scheduled measurement harness the fleet's silent-omission work explicitly rejected (grounding-brief-adjacent decision) — the ledger is append-only evidence for `/retro`'s existing on-demand read, not a new monitoring service.
- Does not retrofit `claim_provenance` typing onto Claude-agent (non-chaperone) workers — those remain lightweight-tier per KTD9 and continue to omit `claim_provenance` entirely.
- Cross-repo: none. This is an internal `saga`/`team-execution` plugin capability with no external-repo surface.

## Dependencies / Assumptions

- Assumes the chaperone-dispatch protocol (`external-engine-workers.md`, #318) and `worker-manifest.md`'s disposition/claim-provenance shape are already merged and load-bearing — verified present today (`plugins/team-execution/skills/team-execution/references/external-engine-workers.md`, `worker-manifest.md:60-81`).
- Assumes `VERIFY_N_CAP = 7` (`plugins/saga/scripts/execution_spec.py:114`) as the existing cap pattern the new `PANEL_N_CAP` is modeled on — verified present at that line.
- Assumes `engine_dispatch.satisfy_gate()`'s `verified_by_claude` hard-require (`plugins/saga/scripts/engine_dispatch.py:238-258`) is unchanged by this capability and continues to be the structural enforcement point for `{#external-engines-never-gatekeepers}`.
- Assumes the two existing `engine_intent` values (`offload`, `second-opinion`) and their KTD2 tier defaults (`plugins/saga/skills/plan/SKILL.md:295-305`) are unchanged except for the new `divergence` addition.

## Success Criteria

- The prose-only `claim_provenance` merge path is fully replaced by the typed reconciliation object for chaperone workers; no code path still produces a freeform-prose-only merge result.
- A dropped net-new finding demonstrably blocks verification in a reproducible test.
- `divergence` is a fully valid third `engine_intent`, exercised end to end (validates, resolves tier, reconciles via its own recipe).
- A chaperone-rejected offload demonstrably surfaces its rejection note into the reviewer/validator consensus evidence trail rather than vanishing.
- An advisory-jury panel fan-out above the cap hard-blocks; at or under the cap, Claude-foreman adjudication is mandatory before any panel output is recorded.
- `/retro` can read a populated ledger and surface at least one gated registry-update proposal in an integration test.
- Doc hands off clean: `/doc-review` can assess readiness without follow-ups; `/plan` can design the mechanism (module boundaries, registry schema, ledger format) without inventing user-facing behavior scope.

## Definition of Done

Merged PR(s) delivering:

1. `plugins/saga/scripts/reconcile.py` (or equivalent module name — exact path is `/plan`'s to determine) implementing the typed reconciliation object, the intent→recipe registry lookup, and ledger writes.
2. `divergence` added as a valid `engine_intent` value in `execution_spec.py` validation, with its tier-table default wired into `plugins/saga/skills/plan/SKILL.md`.
3. A new chaperone-rejected-offload disposition wired into the manifest/dispatch path documented in `worker-manifest.md` and `external-engine-workers.md`.
4. A cap-bounded `role_kind="panel"` fan-out path wired through `engine_resolver.py`/`engine_dispatch.py` with Claude-foreman adjudication mandatory before recording.
5. A `/retro` read hook over the new ledger, emitting gated (not auto-applied) registry-update proposals.
6. Release-surface artifacts updated in the same PR: `plugins/saga/.claude-plugin/plugin.json` and `plugins/team-execution/.claude-plugin/plugin.json` version bumps, `.claude-plugin/marketplace.json`, `plugins/saga/CHANGELOG.md` and `plugins/team-execution/CHANGELOG.md` entries, and drift-guard test updates.
7. A `docs/engineering-journal/DECISIONS.md` entry recording the intent→recipe registry as the new merge-protocol mechanism, with a "revisit when" condition tied to any future fourth `engine_intent` value.

Verification (all commands runnable by a competent agent with no prior context):

```bash
uv run pytest tests/test_reconcile.py -v
uv run pytest tests/test_execution_spec.py -k divergence_intent
uv run pytest tests/test_reconcile.py -k dropped_finding_blocks_verification
uv run pytest tests/test_reconcile.py -k panel_cap
uv run pytest tests/test_reconcile.py -k rejected_offload_signal
uv run pytest tests/test_retro.py -k ledger_proposal
uv run pytest && uv run ruff format --check . && uv run ruff check . && uv run mypy plugins/ scripts/ tests/ --ignore-missing-imports
```

Expected: all green.

### Acceptance criteria
- [ ] Typed reconciliation object with per-item adjudicated flags is produced for every chaperone-dispatched unit; a dropped net-new finding blocks verification (T1-F2-4). Check: `uv run pytest tests/test_reconcile.py -k dropped_finding_blocks_verification` → passes.
- [ ] Each `engine_intent` resolves to exactly one documented merge protocol via the intent→recipe registry, referenced from both `reconcile.py` and `external-engine-workers.md` §4 (T1-F4-3). Check: `uv run pytest tests/test_reconcile.py -k registry_parity` → passes (asserts every valid `engine_intent` value maps to exactly one recipe entry).
- [ ] `divergence` validates as an accepted `engine_intent` value in `execution_spec.py` and resolves to `opus`/`high` in the plan-time tier table, consistent with the existing ordered ladder used for `second-opinion` (T1-F3-2). Check: `uv run pytest tests/test_execution_spec.py -k divergence_intent` → passes.
- [ ] A chaperone-rejected offload emits a non-empty rejection note, recorded as a distinct disposition from `fell-back-to-claude`/`substituted-engine`, and treated as second-opinion signal surfaced to reviewer/validator consensus — never silently discarded (T1-F1-4). Check: `uv run pytest tests/test_reconcile.py -k rejected_offload_signal` → passes.
- [ ] Advisory-jury panel fan-out above `PANEL_N_CAP` hard-blocks at validation; at or under cap, Claude-foreman adjudication is mandatory before any panel output is recorded (T1-F6-6). Check: `uv run pytest tests/test_reconcile.py -k panel_cap` → passes.
- [ ] Every reconcile/apply event writes an append-only ledger record; `/retro` reads the ledger and surfaces a gated registry-update proposal in an integration test (T1-F4-4). Check: `uv run pytest tests/test_retro.py -k ledger_proposal` → passes.
- [ ] `{#external-engines-never-gatekeepers}` remains structurally enforced — no reconciled output satisfies a gate without `evidence.verified_by_claude == True`. Check: `uv run pytest tests/test_engine_dispatch.py -k satisfy_gate` → passes (regression, unchanged behavior).
- [ ] Full repo gate stays green. Check: `uv run pytest && uv run ruff format --check . && uv run ruff check . && uv run mypy plugins/ scripts/ tests/ --ignore-missing-imports` → all pass.
- [ ] Release-surface artifacts updated in the same PR for both affected plugins (`saga`, `team-execution`): `plugin.json` version bumps, `.claude-plugin/marketplace.json`, `CHANGELOG.md` entries, drift-guard tests pass. Check: `uv run pytest tests/ -k "marketplace or plugin_json"` → passes.

### Out-of-scope / non-goals

- Changing who gates: `{#external-engines-never-gatekeepers}` (#283) is unchanged — external engine output still cannot satisfy a gate without Claude verification.
- Changing chaperone-tier resolution mechanics for the existing `offload`/`second-opinion` intents (`{#external-engine-chaperone-dispatch}`, #318, KTD2) — only adding `divergence` as a third value into the same table.
- Introducing a second executor kind, or giving external engines write/residency/git participation (KTD1 unchanged).
- Building a standing/scheduled monitoring service around the ledger — it is append-only evidence for `/retro`'s existing on-demand read.
- Retrofitting `claim_provenance` typing onto lightweight-tier Claude-agent (non-chaperone) workers.
- Any cross-repo change — this is internal to `plugins/saga` and `plugins/team-execution`.

### Files expected to change

Indicative only; exact set is `/plan`'s to determine.

- `plugins/saga/scripts/reconcile.py` — new module: typed reconciliation object, intent→recipe registry, ledger writer.
- `plugins/saga/scripts/execution_spec.py` — add `divergence` to valid `engine_intent` values.
- `plugins/saga/skills/plan/SKILL.md` — add `divergence` row to the tier table (§295-305 region).
- `plugins/team-execution/skills/team-execution/references/external-engine-workers.md` — reference the intent→recipe registry in §4; document the panel fan-out cap.
- `plugins/team-execution/skills/team-execution/references/worker-manifest.md` — add the chaperone-rejected-offload disposition.
- `plugins/saga/scripts/engine_dispatch.py` — panel-mode adjudication wiring (Claude-foreman gate).
- `plugins/saga/scripts/engine_resolver.py` — `role_kind="panel"` fan-out cap constant and validation.
- `plugins/saga/skills/retro/SKILL.md` (or equivalent) — ledger read hook, gated proposal emission.
- `tests/test_reconcile.py` — new test module.
- `tests/test_execution_spec.py` — `divergence` intent validation tests.
- `tests/test_retro.py` — ledger-proposal integration test.
- `docs/engineering-journal/DECISIONS.md` — new entry per Definition of Done item 7.
- `plugins/saga/.claude-plugin/plugin.json`, `plugins/team-execution/.claude-plugin/plugin.json`, `.claude-plugin/marketplace.json`, `plugins/saga/CHANGELOG.md`, `plugins/team-execution/CHANGELOG.md` — release-surface updates.

## Recommended Executor Profile

- **Model:** sonnet
- **Effort:** high — *target posture: not a live team-execution dispatch knob until `pf-effort-first-class` lands; teammates inherit session tier until then*
- **Backend:** team-execution
- **External-LLM posture:** none (this capability builds the reconciliation machinery external engines flow through; it does not itself delegate to an external engine)
- **Justification:** This is mechanical-but-hazardous work — a new typed schema, a registry lookup, and a cap-bounded fan-out path layered onto an already-shipped, well-documented chaperone-dispatch contract (`external-engine-workers.md`, `worker-manifest.md`). Sonnet is the correct tier per the fleet's model/effort tiering guidance (mechanical/deterministic work, not judgment-heavy design). High effort is warranted because the work spans two plugins (`saga`, `team-execution`), touches a gate-adjacent code path (`engine_dispatch.satisfy_gate`) where a regression would silently weaken `{#external-engines-never-gatekeepers}`, and requires careful registry-parity and cap-boundary test coverage. `team-execution` backend is recommended (rather than inline) because the six absorbed facets are independently testable units of work well suited to reviewer-consensus and validator-gated execution, and because a regression in the gate-adjacent `satisfy_gate` path specifically benefits from the read-only-verifier review posture this repo already requires for verify-class spawns.

### Handoff maturity

requirements-ready

### Suggested next action

Use `/plan <issue>` to create an implementation plan.

## Grounding References

- Source: `docs/plans/plugin-fleet-ideation-2026-07-03/survivors/T1.json` (ideation ids `T1-F2-4` primary; `T1-F4-3`, `T1-F3-2`, `T1-F1-4`, `T1-F6-6`, `T1-F4-4` facets)
- Source type: ideation survivor (absorbed, consolidated)
- Source title: Typed second-opinion reconciliation: reconcile.py, intent→recipe map, divergence intent, failure-signal recapture, durable ledger
- Grounding: `docs/plans/2026-07-03-plugin-fleet-grounding-brief.md` (binding-decision register — `{#external-engines-never-gatekeepers}` #283, `{#external-engine-chaperone-dispatch}` #318; §6 recurring-pain theme 4, "External-engine containment = hottest active frontier"); `plugins/team-execution/skills/team-execution/references/external-engine-workers.md`; `plugins/team-execution/skills/team-execution/references/worker-manifest.md`; `docs/engineering-journal/DECISIONS.md:1985` and `:2021`; `plugins/saga/scripts/execution_spec.py:114`

### Intent

Today the chaperone-dispatch protocol (`plugins/team-execution/skills/team-execution/references/external-engine-workers.md`) lets an external engine (codex/agy) attach a `claim_provenance` verdict alongside its own evidence — but that verdict is untyped prose (`worker-manifest.md:81`: "engine returned prose claims alongside its evidence, e.g. a second-opinion review verdict"), there is exactly one merge behavior regardless of `engine_intent` (`offload` or `second-opinion` — the only two intents that exist today, `external-engine-workers.md:35`), a chaperone-rejected offload silently vanishes instead of counting as signal, the advisory-jury fan-out for hardest calls has no cap-bounded reconciliation shape, and nothing writes a durable record of what got reconciled so `/retro` can learn from it. This capability replaces the freeform prose reconciliation with a typed object, adds a registry mapping each `engine_intent` to an explicit merge protocol, introduces a third intent (`divergence`) where convergence between Claude and the external engine is itself the failure signal, recaptures chaperone-rejected offloads as signal instead of discarding them, bounds the advisory-jury panel fan-out, and writes every reconcile/apply to a durable ledger.

### Context library links

_none_

### Tests to add or update

- `tests/test_engine_dispatch.py`
- `tests/test_execution_spec.py`
- `tests/test_reconcile.py`
- `tests/test_retro.py`

### Verification

```bash
uv run pytest && uv run ruff format --check . && uv run ruff check . && uv run mypy plugins/ scripts/ tests/ --ignore-missing-imports
```

### Inputs inventory

- `plugins/team-execution/skills/team-execution/references/external-engine-workers.md`
- `plugins/saga/scripts/reconcile.py`
- `plugins/saga/skills/plan/SKILL.md`
- `plugins/saga/.claude-plugin/plugin.json`
- `plugins/team-execution/.claude-plugin/plugin.json`
- `.claude-plugin/marketplace.json`
- Gate E issue plan: `docs/plans/2026-07-04-plugin-fleet-issue-plan.md`
- Grounding References section of this issue (absorbed-idea bases)

### Failure modes / pre-mortem

- The mechanism ships partially against the Definition of Done — caught by the Acceptance criteria checks below going red.
- Scope creeps past Out-of-scope / non-goals during implementation — caught at PR review against this issue body.
- Release surfaces (plugin.json / marketplace.json / CHANGELOG) drift from the change — caught by the release-surface drift-guard tests.
- `/plan` should deepen this pre-mortem with issue-specific failure modes before implementation.

### Stop conditions

- Any acceptance check cannot go green without widening scope beyond the stated non-goals → HALT, return to operator.
- A load-bearing grounding reference turns out stale against live sources → HALT, re-verify before proceeding.
- Release-surface drift guards fail after version bumps → HALT, reconcile before PR.

## Created Issue

- URL: https://github.com/infiquetra/infiquetra-claude-plugins/issues/393
- Number: 393
- Created at: 2026-07-04T07:59:23.829801+00:00

