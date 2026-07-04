---
title: "capability: bridge_receipt.v1 — one proof-of-execution contract every external-engine bridge emits, enforced at registration"
repo: infiquetra-claude-plugins
type: capability
team: campps
project: operations
status: Idea
labels: capability, hermes-task, needs-plan
risk: medium
handoff_maturity: requirements-ready
tier: structural
wave: wave-1
objective: Stand up the external-engine offload lane
---

# capability: bridge_receipt.v1 — one proof-of-execution contract every external-engine bridge emits, enforced at registration

### Objective
Stand up the external-engine offload lane

### Tier
structural

### Wave
wave-1

### Problem / motivation (grounded)

The fleet's dispatch path currently accepts an external engine's self-reported `status: "ok"` as
sufficient proof that work actually ran, with no hard evidence requirement behind it:

- `plugins/saga/scripts/engine_dispatch.py:182-187` (`build_dispatch_manifest`) sets
  `disposition = pm.Disposition.RAN_AS_REQUESTED` purely from `evidence.halt is None` — there is no
  field on `AdvisoryEvidence` (`plugins/saga/scripts/engine_dispatch.py:27-36`) carrying a
  process-level fact (pid, argv, exit code, bytes produced, wall time) that the disposition check
  consults. A bridge (or a misbehaving adapter) that fabricates a clean `AdvisoryEvidence` without
  the underlying subprocess ever running reaches `RAN_AS_REQUESTED` today.
- `plugins/saga/scripts/provenance_manifest.py:54-57` defines `Disposition.RAN_AS_REQUESTED` as a
  bare enum value with no accompanying evidence-shape requirement.
- `plugins/saga/scripts/engine_registry.py:33` raises `RegistryError` for any entry missing a field
  named in the registry's current required-fields set — but `receipt_emitter` is not among them
  (`plugins/saga/references/engine-registry.yaml` entries carry no `receipt_emitter` key at all
  today). A provider row can be added to the registry with zero wiring to prove it ever emits
  invocation evidence, and CI does not catch it.
- `plugins/agy/scripts/agy_delegate.py` builds its delegation envelope (`evidence`,
  `provenance_required` fields, `:96-154`) but has no shared receipt schema in common with
  `engine_dispatch.py`'s codex path — each bridge's "did this actually run" story is bespoke,
  not a single enforced contract.
- This is the repo's own recorded dominant failure class: `docs/engineering-journal/LEARNINGS.md`
  documents repeated silent-fallback and dead-wiring incidents in delegation (agy silent
  Claude-fallback, dead-wiring producer+consumer, fake-adapter mismatch — see grounding brief §6.1,
  "Silent no-ops in delegation & dead wiring," 5+ learnings), which is exactly the gap this
  capability closes: today nothing structurally prevents a bridge from claiming success without
  proof.
- Binding decision `{#external-engines-never-gatekeepers}` (#283, grounding brief §2) already
  establishes that Claude is verifier-of-record and external engines are advisory/generator-only —
  this capability is the mechanical enforcement of that decision at the evidence layer: an engine's
  self-report cannot promote itself to `RAN_AS_REQUESTED` without a hard receipt Claude's own
  dispatch code inspects.

## Definition of Done

Merged PR that:

1. Adds `bridge_receipt.py` (schema + emit helper) defining `bridge_receipt.v1`: a required,
   versioned invocation-evidence record (at minimum: `pid`, `argv`, `exit_code`, `bytes_produced`,
   `wall_time_s`, `engine_id`, `variant`) and wires it into both `engine_dispatch.py`'s codex path
   and `agy_delegate.py`'s agy path, so both of the fleet's live bridges emit the same shape.
2. Adds a `runner_receipt` field (or equivalent structured evidence container) to
   `AdvisoryEvidence` and threads it through `build_dispatch_manifest` so that
   `Disposition.RAN_AS_REQUESTED` cannot be assigned unless a conforming `bridge_receipt.v1` record
   is present; fabricated/absent-evidence dispatch results are forced to
   `Disposition.FELL_BACK_TO_CLAUDE` (or an explicit new failure disposition) instead.
3. Adds a required `receipt_emitter` key to the engine-registry entry schema
   (`engine_registry.py`'s field-validation path used by `RegistryError`), validated both at
   registry load time and by a CI test, so a provider row lacking wiring to a receipt emitter fails
   before it can be dispatched to.
4. Adds `test_bridge_receipt_drift.py` (or equivalent), enumerating every registered bridge and
   asserting each one calls the shared emit path — red when a bridge is added or edited without the
   emit call, mirroring the existing marketplace-drift-guard pattern
   (`docs/plans/2026-07-03-plugin-fleet-grounding-brief.md` §4).
5. Is verified by: the drift test passing/failing correctly (see Acceptance criteria), plus one
   live codex-bridge run and one live agy-bridge run each producing a conforming
   `bridge_receipt.v1` record inspectable in the resulting manifest.

### Acceptance criteria
- [ ] Every bridge currently registered in `plugins/saga/references/engine-registry.yaml` (codex,
      agy) emits a conforming `bridge_receipt.v1` record on dispatch; a bridge lacking the emit
      call trips the drift test red. Check: `uv run pytest tests/test_bridge_receipt_drift.py -k
      all_bridges_emit` → passes on current bridges, fails when a test double bridge omits the
      emit call. *(covers T15-F2-1, primary)*
- [ ] `AdvisoryEvidence` with `halt is None` but no `runner_receipt` (or a `runner_receipt` failing
      schema validation) cannot produce `Disposition.RAN_AS_REQUESTED` from
      `build_dispatch_manifest` — it resolves to `FELL_BACK_TO_CLAUDE` (or an explicit
      unverifiable-evidence disposition) instead. Check: `uv run pytest
      tests/test_saga_engine_dispatch.py -k fabricated_evidence_no_receipt` → passes, asserting
      the disposition is never `RAN_AS_REQUESTED` for receipt-less evidence. *(covers T15-F1-1)*
- [ ] A registry entry omitting `receipt_emitter` fails registry validation (`RegistryError`) at
      load and fails a CI-collected test. Check: `uv run pytest tests/test_saga_engine_registry.py
      -k missing_receipt_emitter` → passes, asserting `RegistryError` is raised for a dummy
      provider row without `receipt_emitter`. *(covers T15-F2-2)*
- [ ] Live proof-of-execution: one codex-bridge dispatch and one agy-bridge dispatch each produce
      a `bridge_receipt.v1` record with all required fields populated (non-placeholder `pid`,
      `argv`, `exit_code`). Check: manual/integration run recorded in the PR description with the
      two emitted receipts pasted or referenced by manifest ID.
- [ ] Full suite, lint, and types stay green. Check: `uv run pytest && uv run ruff check . && uv
      run mypy plugins/ scripts/ tests/ --ignore-missing-imports` → all pass.

### Out-of-scope / non-goals
**In scope:**
- `bridge_receipt.py` schema + emit helper, shared by both live bridges (codex, agy).
- `AdvisoryEvidence` / `build_dispatch_manifest` gating change in `engine_dispatch.py` and
  `provenance_manifest.py`'s `Disposition` handling.
- `receipt_emitter` required-key addition to the engine-registry schema and its CI-enforced
  validation.
- Bridge-enumeration drift test.

**Non-goals / explicitly out of scope:**
- Building a new bridge or onboarding a third external engine — this wires the two bridges that
  exist today (codex, agy).
- Changing who is verifier-of-record — Claude remains the sole gate per
  `{#external-engines-never-gatekeepers}` (#283); this capability only hardens the evidence an
  engine must supply before its claim is even eligible for consideration, it does not let an
  engine self-certify past Claude's adjudication.
- Redesigning `team-execution`'s chaperone-dispatch model — per
  `{#external-engine-chaperone-dispatch}` (#318), external engines stay offload/second-opinion
  workers, never a second executor kind; this issue does not touch team roster or residency.
- A standing telemetry/measurement loop over receipt catch-rate — this ships the enforced contract
  and its drift guard, not an ongoing monitoring dashboard.
- Retrofitting historical manifests emitted before this change — no backfill of past
  `RAN_AS_REQUESTED` dispositions.

## Grounding References

- Absorbed ideas (full bases in
  `docs/plans/plugin-fleet-ideation-2026-07-03/survivors/T15.json`):
  - `T15-F2-1` (primary) — "Unified bridge_receipt.v1 invocation-evidence contract across all
    delegation bridges." `dod_sketch`: merged PR adds `bridge_receipt.py` (schema+emit) wired into
    `engine_dispatch` + `agy_delegate`, plus `test_bridge_receipt_drift.py` enumerating registered
    bridges; verified by drift test red when a bridge lacks the emit call and a live codex+agy run
    each producing a conforming receipt.
  - `T15-F1-1` (facet) — "runner_receipt: hard subprocess proof before RAN_AS_REQUESTED."
    `dod_sketch`: merged PR adds `runner_receipt` (pid/argv/exit/bytes/wall) to `AdvisoryEvidence` +
    downgrade guard in `build_dispatch_manifest`; verified by
    `test_engine_dispatch_receipt.py` asserting fabricated-evidence-no-receipt cannot reach
    `RAN_AS_REQUESTED`.
  - `T15-F2-2` (facet) — "Provider-registry receipt guard: no bridge enters the router without
    proof-of-execution wiring." `dod_sketch`: merged PR adds a required `receipt_emitter` key to
    the `engine_registry` entry schema validated at load + CI guard; verified by a test that a
    dummy provider without a receipt-emitter turns the guard red. Marketplace-drift-guard pattern
    applied to registration.
  - Consolidation rationale (issue-map): `T15-F2-1` is the dedup keeper for eight receipt-contract
    variants; the `runner_receipt` hard-proof fields (pid/argv/exit/bytes/wall) and the
    registry-side `receipt_emitter` registration guard are the two halves — emission and
    enforcement — of the same contract PR.
- Recurring-pain theme this closes: grounding brief §6.1, "Silent no-ops in delegation & dead
  wiring" (5+ journal learnings) — this is theme 15 (delegation integrity), the newest theme
  candidate named directly from that pain.
- Binding decisions this capability builds on and must not violate (grounding brief §2):
  - `{#external-engines-never-gatekeepers}` (#283) — Claude stays verifier-of-record; this
    capability hardens the evidence bar an engine must clear before Claude even considers its
    claim, it does not grant engines gating authority.
  - `{#external-engine-chaperone-dispatch}` (#318) — external engines remain
    offload/second-opinion workers only; no change to executor kind or team residency here.
- Current-state code citations verified during grounding (2026-07-03):
  - `plugins/saga/scripts/engine_dispatch.py:27-36` (`AdvisoryEvidence` dataclass, no receipt
    field today).
  - `plugins/saga/scripts/engine_dispatch.py:163-187` (`build_dispatch_manifest`, disposition
    derived from `halt is None` only).
  - `plugins/saga/scripts/provenance_manifest.py:54-57` (`Disposition.RAN_AS_REQUESTED` enum,
    no evidence-shape requirement attached).
  - `plugins/saga/scripts/engine_registry.py:33` (`RegistryError` on missing required field —
    `receipt_emitter` absent from that set today).
  - `plugins/saga/references/engine-registry.yaml` (live registry entries, no `receipt_emitter`
    key present).
  - `plugins/agy/scripts/agy_delegate.py:96-154` (agy envelope's own bespoke evidence fields, not
    unified with the codex path).

### Recommended executor profile

- **Model:** sonnet
- **Effort:** high
- **Backend:** inline
- **External-LLM posture:** none
- **Justification:** not applicable above sonnet — this is a bounded, mechanically-scoped
  contract-and-guard change (one schema module, one gating edit, one registry-required-field
  addition, one drift test) against code paths and shapes already fully specified in the absorbed
  ideas' `dod_sketch`es; no open design ambiguity requiring opus-tier judgment.

### Release-surface checklist (plugin behavior changes — required)

- [ ] `plugins/saga/.claude-plugin/plugin.json` — version bump + description update reflecting the
      new `bridge_receipt.v1` contract and the `AdvisoryEvidence`/registry schema changes.
- [ ] `plugins/agy/.claude-plugin/plugin.json` — version bump reflecting `agy_delegate.py`'s
      adoption of the shared receipt emitter.
- [ ] `.claude-plugin/marketplace.json` — both plugin entries' version/description kept in sync
      with the bumps above.
- [ ] `plugins/saga/CHANGELOG.md` — entry documenting `bridge_receipt.v1`, the
      `RAN_AS_REQUESTED` gating change, and the `receipt_emitter` required-registry-key addition
      (note any backward-compatibility/migration stance for existing registry entries).
- [ ] `plugins/agy/CHANGELOG.md` — entry documenting agy's adoption of the shared receipt
      contract.
- [ ] Version/metadata drift-guard tests (if present in `tests/`) updated or added to assert
      `plugin.json`/`marketplace.json`/`CHANGELOG.md` tell the same story as the diff.

### Files expected to change

Indicative only — exact set is `/plan`'s to determine.

- `plugins/saga/scripts/bridge_receipt.py` — new schema + emit module (proposed path).
- `plugins/saga/scripts/engine_dispatch.py` — `AdvisoryEvidence` gains `runner_receipt`;
  `build_dispatch_manifest` gates `RAN_AS_REQUESTED` on it.
- `plugins/saga/scripts/provenance_manifest.py` — disposition handling for
  unverifiable/receipt-less evidence.
- `plugins/saga/scripts/engine_registry.py` — `receipt_emitter` added to required-field
  validation.
- `plugins/saga/references/engine-registry.yaml` — existing entries updated with
  `receipt_emitter` values.
- `plugins/agy/scripts/agy_delegate.py` — wired to emit `bridge_receipt.v1` via the shared module.
- `tests/test_bridge_receipt_drift.py` — new drift/enumeration test (proposed path).
- `tests/test_saga_engine_dispatch.py` — fabricated-evidence-no-receipt case.
- `tests/test_saga_engine_registry.py` — missing-`receipt_emitter` case.

### Tests to add or update

- Drift test: every registered bridge (codex, agy) emits a conforming `bridge_receipt.v1` record;
  a bridge lacking the emit call fails the test.
- Dispatch test: `AdvisoryEvidence` without a valid `runner_receipt` cannot resolve to
  `Disposition.RAN_AS_REQUESTED`.
- Registry test: an entry missing `receipt_emitter` raises `RegistryError` at load and fails CI.
- Integration/manual: one live codex dispatch and one live agy dispatch each produce an inspectable
  conforming receipt.

### Verification

```bash
uv run pytest tests/test_bridge_receipt_drift.py -v
uv run pytest tests/test_saga_engine_dispatch.py -k receipt -v
uv run pytest tests/test_saga_engine_registry.py -k receipt_emitter -v
uv run pytest && uv run ruff format --check . && uv run ruff check . && uv run mypy plugins/ scripts/ tests/ --ignore-missing-imports
```

Expected: all green; the drift test fails only when a bridge is deliberately edited to skip the
emit call (verify by temporarily commenting out the emit call in one bridge and confirming red,
per the exemplar's self-test convention).

### Handoff maturity
requirements-ready

### Suggested next action
Use `/plan <issue>` to create an implementation plan.

### Source context
- Source: docs/plans/plugin-fleet-ideation-2026-07-03/survivors/T15.json (ids: T15-F2-1 (primary),
  T15-F1-1, T15-F2-2 (facets))
- Source type: ideation issue-map
- Source title: bridge_receipt.v1: one proof-of-execution contract every bridge emits, enforced at
  registration

### Context library links

_none_

### Intent

The fleet's dispatch path currently accepts an external engine's self-reported `status: "ok"` as sufficient proof that work actually ran, with no hard evidence requirement behind it:

## Created Issue

- URL: https://github.com/infiquetra/infiquetra-claude-plugins/issues/383
- Number: 383
- Created at: 2026-07-04T07:56:09.867734+00:00

