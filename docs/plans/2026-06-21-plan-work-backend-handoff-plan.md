---
title: Plan→Work Execution-Backend Handoff — Author a Real Workflow, Run It or Halt
type: feat
status: active
date: 2026-06-21
origin: docs/brainstorms/2026-06-21-plan-work-backend-handoff-requirements.md
---

# Plan→Work Execution-Backend Handoff — Author a Real Workflow, Run It or Halt

## Summary

Extend the existing execution-spec emitter to render **real parallel fan-out** and **refute-N judge-panels** (today it emits a serial `await` chain with no verification primitive), then wire it into `/plan` (author → validate → approve → persist the canonical spec) and `/work` (re-emit from the spec and run, or halt off-host), and guard `saga.py` so an agent's substitution can never be recorded as the operator's choice. This closes the campps issue-38 class of failure: a `cc-workflows-ultracode` plan that authored no runnable workflow, so `/work` hand-rolled sequential subagents, dropped the tiers and refute-N, and recorded `operator_choice: inline` the operator never picked.

## Problem Frame

The emitter (`emit_workflow_script`) exists and is tested but **no skill calls it** (`#dead-wiring-needs-producer-and-consumer`), and it renders **serial-only with no judge primitive** (`plugins/saga/scripts/execution_spec.py:306` — a `for` loop of `const x = await agent(...)`; "fan-out" is one agent handling N targets in its prompt at `:293`). So wiring alone restores tiering and determinism but not the parallelism and adversarial verification the operator asked for — and the dropped refute-N was the *safety* failure (~24 child-safety slices merged CI-green-only). The full requirements, decisions, and the doc-review settlement live in `origin`; this plan is the HOW.

## Requirements

The authoritative requirement list is `origin` R1–R15 (5 groups: spec+emitter capability, plan-time authoring, tier capture, run-or-halt, provenance integrity). Unit mapping for the reviewer's and `/work`'s checklist:

- **R1, R2, R3, R4, R5** (parallel dispatch, refute-N primitive, bounded N, tier preservation + emit-validation, keep team_emitter green) → **U1, U2**
- **R6, R7, R8, R9, R10** (build/validate/block, persist canonical spec + ref, approve, structured tier capture, default derivation) → **U4**
- **R11, R12** (re-emit + run, halt off-host never substitute) → **U5**
- **R13, R14, R15** (operator_choice provenance, downgrade-with-provenance, save-time assert) → **U3**

## Key Technical Decisions

**KTD1 — `/plan` authors the `ExecutionSpec` directly as structured data; no prose-parsing converter.** The spec (per-unit `prompt`, `tier`, `depends_on`, verify panel) is authored during planning and persisted as the canonical JSON (`origin` KD3); the prose plan's Implementation Units are the human-readable mirror. *Rejected:* parsing prose Implementation Units into a spec — brittle and lossy, and it splits canonical authority between two drifting artifacts.

**KTD2 — Per-unit agent prompts are thin pointers, not prose transcriptions.** Each emitted `agent()` prompt is `<unit-id> + one-line goal + "read the plan at <path> as your authoritative spec"`; the emitter already appends fan-out/budget riders. *Rationale:* the emitted script is "control flow only" (`execution_spec.py:323`) — depth comes from the agent reading the plan, so the prose→prompt derivation is near-lossless and the deferred-(b) risk evaporates.

**KTD3 — refute-N defaults: N=3, majority pass-rule, both overridable; emit warns above a cap (7).** A finding survives unless ≥⌈N/2⌉ verifiers refute it. *Rationale:* 3 is the standard small panel (cheap, tie-breaking); majority matches the Workflow tool's documented refute-N; the cap + bound directly guards the 22/23-judges rate-limit overcorrection (`origin` R3). *Rejected:* unanimous (one flaky verifier blocks); unbounded N (the overcorrection).

**KTD4 — Dependency → barrier mapping is topological-layer parallelism.** Compute dependency layers (Kahn) from `depends_on`; each layer of ready units renders as one `parallel([...])` block; layers are sequenced by `await`; a pilot gates its fan-out layer. *Rejected:* a flat `pipeline()` (can't express cross-unit barriers cleanly); operator-hand-specified parallel groups (authoring burden).

**KTD5 — The refute-N primitive is a new optional `verify` field on `Unit`, not a new top-level construct.** `verify: {n, pass_rule}` on a unit renders, at emit, a parallel judge-panel of N verifier agents over that unit's output plus the pass-rule reconciliation. *Rationale:* minimal, backward-compatible spec extension — `team_emitter` and existing specs ignore an absent field, keeping `origin` R5 (team tests green) cheap.

**KTD6 — `/work` halts off-host; it does NOT call the resume-path recompile-down.** `recheck_orchestration_capability`'s auto-degrade-to-inline-baseline stays for `/loop`/`/resume`, but a guarantee-bearing `cc-workflows-ultracode` choice in `/work` halts (`origin` KD2) because the off-host serial baseline loses parallel + refute-N. *Rejected:* reuse the recompile-down in `/work` — it silently drops the guarantees the operator chose ultracode for.

**KTD7 — The provenance guard lives at the single `saga.py` `save()` chokepoint.** The auto-derive `operator_choice = (args.orchestration_operator_choice or args.orchestration_mode)` (`saga.py:1074-1075`) stays — absent operator_choice → equals mode, which never conflicts; the guard fires only on an EXPLICIT `mode != operator_choice` pair and `save()` rejects it (non-zero) when `orchestration_downgrade` is empty. The guard MUST live in the `save()` path, NOT the dataclass constructor or `render_envelope` — otherwise the direct render/parse round-trip at `tests/test_saga_saga.py:1259` (operator_choice ≠ default mode, unsaved) would break. *Rationale:* one write path guards every caller without touching pure (de)serialization; `tests/test_capability_degrade.py` is the natural test home.

## Implementation Units

### U1. Extend the spec — parallel layers + a `verify` judge-panel construct

**Goal:** Add dependency-layer computation and an optional `Unit.verify` ({n, pass_rule}) to the spec, with emit-time validation, keeping `from_dict`/`to_dict` and `team_emitter` compatible.

**Approach:** In `plugins/saga/scripts/execution_spec.py`, add a `Verify` dataclass (validated: `1 <= n`, `n <= CAP` with a warn band, `pass_rule ∈ {majority, unanimous}`), wire it onto `Unit` (optional, default none) through `from_dict`/`to_dict`/`validate`. Add a pure `dependency_layers(spec)` helper (Kahn; raises `SpecError` on a cycle or unresolved `depends_on`) that ALSO treats a fan-out unit's `pilot` as an implicit barrier edge, so the pilot always lands in an earlier layer than the fan-out it gates (R3 — without this, layering would put a pilot and its fan-out in the same parallel wave and the gate would be lost). Extend `ExecutionSpec.validate` to cover both. Do not change `team_emitter` behavior — an absent `verify` must round-trip unchanged.

**Files:** Modify `plugins/saga/scripts/execution_spec.py`. Test `tests/test_workflow_emitter.py`, `tests/test_team_emitter.py` (regression).

**Patterns to follow:** mirror the existing `Tier`/`Unit` dataclass + `from_dict`/`validate` style (`execution_spec.py:77-180`); raise `SpecError` with the offending unit id (`:69-74`).

**Verification:** `verify` round-trips and validates; bad N / pass_rule / dependency cycle → `SpecError`; `team_emitter` tests stay green.

**Test scenarios:**
- happy: a spec with two independent units + one dependent unit yields 2 layers; a unit with `verify:{n:3,pass_rule:majority}` validates and round-trips.
- edge: N at the cap boundary; a single-unit layer; a `verify` on a fan-out unit.
- error: `verify` with `n:0` or missing `pass_rule` → `SpecError`; a `depends_on` cycle → `SpecError`; N above the cap → warn (or `SpecError` per KTD3).
- integration: `to_dict`→`from_dict` preserves `verify` and layer structure.

### U2. Render parallel + refute-N in `emit_workflow_script`

**Goal:** Replace the serial `await` chain with topological-layer `parallel([...])` blocks and render a unit's `verify` panel as a parallel judge-panel of N verifiers + the pass-rule reconciliation, preserving per-unit tiers. Leave `emit_inline_baseline` serial.

**Approach:** Rewrite the unit-emission loop (`execution_spec.py:337-356`) to iterate `dependency_layers(spec)` from U1: a layer with >1 ready unit emits `await parallel([() => agent(...), ...])`; a singleton emits `await agent(...)`. For a unit with `verify`, after its `agent()` emit a `parallel([...])` of N verifier `agent()` calls (same-tier per `origin` R4) over the unit's result, then a pass-rule check. Keep the budget rider + R10 reconciliation from `_agent_prompt`. `emit_inline_baseline` is untouched (the off-host floor stays serial).

**Files:** Modify `plugins/saga/scripts/execution_spec.py`. Test `tests/test_workflow_emitter.py`.

**Patterns to follow:** the existing emit string-builder (`emit_workflow_script:319-358`); the Workflow tool's `parallel(thunks)` / judge-panel idiom (refute-N: spawn N skeptics, kill on majority-refute).

**Verification:** independent units emit a `parallel()` block; dependent units sit behind an `await` barrier; a `verify` unit emits N verifier `agent()` calls + the pass rule; every `agent()` carries its `{model, effort}`; the inline baseline is unchanged.

**Test scenarios:**
- happy: 2 independent units → one `parallel()`; a 3rd dependent unit → a second layer after `await`.
- edge: a `verify:{n:3}` unit → 3 verifier `agent()` calls in a `parallel()` + a majority check; a haiku-tier unit still gets the budget rider.
- error: (covered at U1 validate — emit calls `validate()` first, so a malformed spec fails before render).
- integration: a layered spec with a verify panel emits a script whose substrings confirm the structure (a `parallel(` block, N verifier `agent(` calls, the `meta` block, and every unit's `model`/`effort`) — matching the existing substring-assertion convention in `tests/test_workflow_emitter.py`.

**Depends on:** U1.

### U3. `saga.py` provenance guard

**Goal:** `operator_choice` holds only an actual operator pick; a `mode != operator_choice` tick with an empty `orchestration_downgrade` is rejected at save.

**Approach:** In `plugins/saga/scripts/saga.py`, keep the `operator_choice = (args.orchestration_operator_choice or args.orchestration_mode)` auto-derive (`:1074-1075` — it never conflicts), and add a validation in `save()` (NOT the dataclass constructor or `render_envelope`) that raises a non-zero exit when an EXPLICIT `orchestration_mode != orchestration_operator_choice and not orchestration_downgrade`. Keep `orchestration_downgrade` plumbing (already an arg). Document the field semantics inline (`operator_choice` = authoritative pick; `mode` = effective; a recommendation override is the separate `recommended`-vs-`operator_choice` pair).

**Files:** Modify `plugins/saga/scripts/saga.py`. Test `tests/test_capability_degrade.py` (primary) and `tests/test_saga_saga.py`.

**Patterns to follow:** the existing `_build_save_saga` arg-marshalling (`saga.py:1058-1090`) and the save-validation style; `tests/test_capability_degrade.py` conventions.

**Verification:** `mode == operator_choice` saves; `mode != operator_choice` + non-empty downgrade saves; `mode != operator_choice` + empty downgrade → rejected; the R12 override-rate reader still parses both fields.

**Test scenarios:**
- happy: a normal `--orchestration-mode cc-workflows-ultracode` save (operator_choice derives to the same) succeeds.
- edge: an explicit degrade — `mode=inline`, `operator_choice=cc-workflows-ultracode`, non-empty downgrade — succeeds and records provenance.
- error: the issue-38 shape — `mode=cc-workflows-ultracode`, `operator_choice=inline`, empty downgrade → non-zero exit with a clear message.
- integration: `tests/test_override_rate.py` still reads recommended-vs-choice unaffected.
- regression: a `render_envelope`→`parse_envelope` round-trip of a saga with `operator_choice != mode` (unsaved — e.g. `tests/test_saga_saga.py:1259`) stays valid; the guard is `save()`-scoped, not (de)serialization-scoped.

### U4. Wire `/plan` — author, validate, approve, persist the canonical spec

**Goal:** When `cc-workflows-ultracode` is chosen, `/plan` authors the `ExecutionSpec`, validates it, surfaces it for operator confirmation, emits the `.workflow.js`, persists the spec JSON as canonical, and points `orchestration_ref` at it — blocking on an invalid spec.

**Approach:** Edit `plugins/saga/skills/plan/SKILL.md` §5.2–5.3: add the author-spec step (per-unit tier from the R10 work-shape heuristic — judgment→opus, mechanical/deterministic→sonnet/haiku, read-only survey→sonnet — surfaced for override; thin prompts per KTD2; deps + verify panels), the `execution_spec.py validate` + `emit` calls, the operator-confirmation surface (R8), the spec-persist + `--orchestration-ref <spec-path>` save, and the hard block when emit/validate fails. State the tier-derivation heuristic and the default-tier table.

**Files:** Modify `plugins/saga/skills/plan/SKILL.md`. Reference `plugins/saga/references/operator-choice.md`, `plugins/saga/skills/work/references/execution-strategy.md`.

**Patterns to follow:** the existing §5.2 backend offer and §5.3 save block (`plan/SKILL.md:246-315`); the `execution_spec.py emit` CLI.

**Verification:** the SKILL §5.2–5.3 contains the author→validate→approve→persist→ref flow and the block-on-invalid rule; the tier-derivation heuristic + default table are stated.

**Test scenarios:** Test expectation: none — markdown SKILL contract. Verified by presence of the §5.2–5.3 flow + the version-drift guard (U6); the behavior is exercised end-to-end in `/work` (U5) and the emitter tests (U1/U2).

**Depends on:** U1, U2.

### U5. Wire `/work` — re-emit from the spec and run, or halt

**Goal:** When `mode == cc-workflows-ultracode`, `/work` re-emits from the canonical spec and runs the workflow via the Workflow tool; if the tool is genuinely absent or the spec is missing, it halts with a one-line recovery — never substitutes.

**Approach:** Edit `plugins/saga/skills/work/SKILL.md` Phase 1.4 / Phase 2: read `orchestration_ref` (the spec), re-emit the `.workflow.js` (`execution_spec.py emit`, KD3 freshness), and `Workflow({scriptPath})`; the recorded choice + the saved spec is the opt-in (ultracode *mode* not required). On a genuinely-absent Workflow tool or missing spec → HALT + surface + one-line recovery (KD6), explicitly NOT the recompile-down and NOT hand-rolled subagents.

**Files:** Modify `plugins/saga/skills/work/SKILL.md`. Reference `plugins/saga/references/operator-choice.md` §4.

**Patterns to follow:** the existing Phase 1.4 backend handling (`work/SKILL.md:169-203`) and Phase 2 execution (`:206-224`).

**Verification:** the SKILL Phase 1.4/2 contains the re-emit-and-run branch, the halt-not-substitute rule, and the off-host-halt (not recompile-down) decision.

**Test scenarios:** Test expectation: none — markdown SKILL contract. Verified by presence of the run-or-halt branch + the never-substitute rule; the version-drift guard (U6) catches metadata drift.

**Depends on:** U3 (the guard governs the saga writes `/work` makes), U1, U2 (the spec it runs).

### U6. Contract docs, journal, and version surfaces

**Goal:** Update the backend/execution contract docs, record the KTDs in the journal, and bump the saga plugin's release surfaces so installed metadata tells the same story as the diff.

**Approach:** Update `plugins/saga/references/operator-choice.md` (the `/work` halt-not-degrade for a guarantee-bearing ultracode choice; the spec-as-canonical pointer) and `references/execution-spec.md` (the parallel + `verify` constructs, the `/plan` author-and-persist flow). Add a `DECISIONS.md` entry mirroring KTD1–KTD7 with rejected alternatives and a "revisit when." Bump `plugins/saga/.claude-plugin/plugin.json` version, mirror in `.claude-plugin/marketplace.json`, and add a `plugins/saga/CHANGELOG.md` entry. Validate `marketplace.json` with `python3 -m json.tool`.

**Files:** Modify `plugins/saga/references/operator-choice.md`, `plugins/saga/references/execution-spec.md`, `docs/engineering-journal/DECISIONS.md`, `plugins/saga/.claude-plugin/plugin.json`, `.claude-plugin/marketplace.json`, `plugins/saga/CHANGELOG.md`.

**Patterns to follow:** the existing DECISIONS entries (e.g. `#operator-choice-docs-and-confidence`); the marketplace-edit guard (read the array end; include the closing `]` and `version` in the edit; validate JSON).

**Verification:** the contract docs describe the new behavior; the DECISIONS entry exists; plugin.json / marketplace.json / CHANGELOG agree on the new version; the version-drift guard test passes.

**Test scenarios:** Test expectation: covered by the existing plugin-metadata drift-guard tests (version parity across plugin.json / marketplace.json) + `python3 -m json.tool` validation. No new behavior-bearing code.

**Depends on:** U1–U5.

## High-Level Technical Design

The spec stays the single source of truth (`ExecutionSpec`), gaining (a) `dependency_layers()` for topological waves and (b) an optional `Unit.verify` panel. Two emitters consume it: `emit_workflow_script` (now layer-parallel + judge-panels, capable-host) and `emit_inline_baseline` (serial, any-host floor, unchanged). `/plan` authors+validates+persists the spec and emits the `.workflow.js`; `orchestration_ref` → the spec path. `/work` re-emits from the spec (freshness) and runs it, or halts. `saga.py` guards `operator_choice` provenance at the save chokepoint. Data flow: `/plan` interrogation → `ExecutionSpec` (JSON, persisted) → `emit_workflow_script` → `.workflow.js` → `/work` `Workflow({scriptPath})`.

## Risk Analysis & Mitigation

- **Re-parallelizing reintroduces the rate-limit overcorrection.** Mitigation: KTD3 bounded N + emit warning; rely on the Workflow runtime's concurrency cap (min(16, cores-2)).
- **Extending `ExecutionSpec` breaks `team_emitter`.** Mitigation: `verify` is optional + absent-field round-trip; U1/U5 keep `tests/test_team_emitter.py` green (R5).
- **`/work` can't actually launch the Workflow tool from a saga field (harness opt-in).** Mitigation: the run-or-halt design is safe either way — if the launch can't fire, U5's halt surfaces it (never a silent substitute); confirm against real behavior during U5.
- **Plan↔spec drift on round-N.** Mitigation: spec is canonical (KD1/KD3); `/work` re-emits from it; a re-plan rewrites it.

## Alternatives Considered

- **Wire the serial emitter as-is (v1), defer parallel+refute-N.** Rejected by the operator — refute-N was the safety failure; tiering alone doesn't restore it.
- **Parse prose Implementation Units into the spec (a converter).** Rejected (KTD1) — brittle/lossy, splits canonical authority.
- **Reuse the off-host recompile-down in `/work`.** Rejected (KTD6) — it silently drops the chosen guarantees.

## Scope Boundaries

- **team-execution wiring is out of scope** (its emitter is also unwired; a separate effort) — only the regression constraint (R5) applies here.
- **No `fallback_ok` / auto-degrade** in `/work` (KD2/KD6).
- **No buildable-unit gate** — any issue/outcome/rollup is workable.
- **Deferred to implementation (not blockers):** the exact JS string-emission for nested `parallel()`+judge-panels (U2 detail); whether `dependency_layers` lives in `execution_spec.py` or a sibling.

## Requirements traceability

R1,R2,R3,R4,R5 → U1,U2 · R6,R7,R8,R9,R10 → U4 · R11,R12 → U5 · R13,R14,R15 → U3 · contract/journal/version → U6.
