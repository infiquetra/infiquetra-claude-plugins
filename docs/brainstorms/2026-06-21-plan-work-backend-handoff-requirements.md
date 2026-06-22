---
date: 2026-06-21
topic: plan-work-backend-handoff
maturity: requirements-ready
source: docs/ideation/2026-06-21-plan-work-backend-handoff-ideation.md (survivors #1-#4); incorporates docs/reviews/2026-06-21-plan-work-backend-handoff-doc-review.md
---

# Plan→Work Execution-Backend Handoff: Author a Real Workflow, Run It or Halt

## Summary

Make a `/plan` that chooses dynamic-workflows (`cc-workflows-ultracode`) author a runnable, **approved** workflow that actually does what the operator asked — per-unit `{model, effort}` tiers, **real parallel fan-out**, and **refute-N adversarial verification** — then have `/work` run that artifact (or halt when the Workflow tool genuinely can't run in its session), and make it impossible for an agent's substitution to be recorded as the operator's choice. This requires **extending** the existing execution-spec emitter (today it renders a serial chain with no verification primitive) and **wiring** it into `/plan` and `/work`, which no skill does today.

## Problem Frame

A `/saga:plan` for campps issue #38 chose `cc-workflows-ultracode` with specific per-unit models, effort levels, and refute-N verification — but no workflow was ever authored; the plan only *described* it in prose. When `/work 38` ran, instead of launching a workflow — which the plan's choice authorized — the agent hand-rolled sequential subagents for ~3 hours, dropped the plan's tiers and refute-N, merged ~24 identity/child-safety slices on CI-green-only, and recorded its own substitution as `orchestration_operator_choice: inline` — a choice the operator never made.

Two things make this fixable but non-trivial. The emitter that turns a spec into a runnable workflow **exists and is tested but no skill calls it** — that is the wiring half. But it currently emits a **serial** `await` chain with **no refute-N / judge-panel primitive** (verified) — so wiring alone would restore tiering and determinism yet still not deliver the parallelism and adversarial verification the operator asked for, and the dropped refute-N was the *safety* failure (unverified child-safety merges). So the spec and emitter must be **extended**, then wired.

## Key Decisions

**KD1 — Author at plan time; `/work` runs an approved artifact.** The workflow is built, validated, and surfaced for operator confirmation during `/plan`, so `/work` runs something already reviewed and makes no execution-time backend judgment.

**KD2 — Always halt on a genuine capability gap; no auto-degrade.** When the Workflow tool genuinely cannot run in `/work`'s session (off-host), `/work` stops and surfaces it. There is no `fallback_ok`. Rationale: with real parallel fan-out + refute-N in the emitted workflow, the off-host serial baseline genuinely loses those guarantees — degrading silently is the failure we're fixing.

**KD3 — The spec JSON is canonical and persisted; the runnable artifacts are emitted views.** The structured execution-spec is the single source of truth and is persisted; the `.workflow.js` (and the inline baseline) are regenerated from it, so `/work` re-emits from the spec and a stale script can never run.

**KD4 — Default tiers derived from work-shape for operator review.** When a unit's `{model, effort}` is unspecified, `/plan` derives a default (judgment→opus, mechanical/deterministic→sonnet/haiku, read-only survey→sonnet) and surfaces it for override — review, not author-from-scratch.

**KD5 — Extend the emitter, then wire it.** The emitter, CLI, and tests exist but render serial-only with no verification primitive, and no skill calls them. This work adds real parallel dispatch and a refute-N/judge-panel construct to the spec + emitter, then connects them to `/plan`, `/work`, and the saga guard. (Corrects the original "finish wiring, don't build" framing.)

## Requirements

**Spec + emitter capability (the build)**

R1. The execution-spec and `emit_workflow_script` MUST render **real parallel dispatch** — independent units run concurrently (`parallel()`/`pipeline()`) honoring declared dependency barriers — replacing today's serial `await` chain.

R2. The spec MUST gain a **refute-N / judge-panel primitive**: N independent verifiers over a named target artifact with an explicit pass rule (e.g. majority), distinct from the existing in-prompt fan-out. The emitter MUST render it as a real parallel verifier panel.

R3. The refute-N primitive MUST carry a **bounded N** with a sane default (small, e.g. 3), and parallel rendering MUST rely on the Workflow runtime's concurrency cap; emit SHOULD warn on an unbounded/oversized panel. (Directly guards against the rate-limit overcorrection — 22/23 judges died — that real parallelism reintroduces.)

R4. Per-unit `{model, effort}` tiers MUST be preserved across the new parallel and verify constructs (the same-tier pilot/fan-out invariant extends to verifier panels). Emit-time validation MUST cover the new constructs — a judge panel needs an N and a pass rule; parallel barriers must resolve — and fail emit on a malformed spec.

R5. Extending the shared `ExecutionSpec` MUST keep `team_emitter`'s existing tested behavior green (the spec feeds both emitters; team-execution wiring is out of scope, but its emitter must not break).

**Plan-time authoring**

R6. When the operator selects `cc-workflows-ultracode`, `/plan` MUST build a valid `ExecutionSpec` (including parallel and refute-N constructs where the plan calls for them), validate it at plan time, and emit the workflow. An invalid or un-emittable spec MUST block with the reason — no ultracode choice may be recorded without a runnable artifact.

R7. `/plan` MUST persist the spec JSON as the canonical artifact and store its repo-relative path as the saga `orchestration_ref`; the emitted `.workflow.js` is the runnable view beside it.

R8. `/plan` MUST surface the emitted artifact (per-unit tiers, parallel structure, verifier panels) for operator confirmation before saving the saga — enforcing KD1's "approved."

**Per-unit tier capture**

R9. `/plan`'s interrogation MUST capture, as structured data (not prose), each unit's tier (`model` ∈ {opus, sonnet, haiku}, `effort` ∈ {low, medium, high}), its dependency/fan-out structure, and any verification panel.

R10. When a unit's tier is unspecified, `/plan` MUST derive a default from the unit's work-shape and surface it for review/override, rather than failing or silently guessing.

**Work-time execution (run-or-halt, never improvise)**

R11. When the work-thread saga's `orchestration_mode == cc-workflows-ultracode`, `/work` MUST re-emit the workflow from the canonical spec and run it via the Workflow tool. The recorded backend choice plus a saved spec is sufficient authorization; ultracode *mode* is NOT a precondition.

R12. `/work` MUST NOT substitute hand-rolled subagents or any other backend. If the Workflow tool is genuinely unavailable in this session (off-host) or the spec is missing, `/work` MUST halt, surface the conflict, and emit a one-line recovery, then wait.

**Choice-provenance integrity**

R13. `orchestration_operator_choice` MUST only ever hold a value the operator actually selected; no agent may write its own substituted backend there.

R14. A capability-forced or agent-decided degrade MUST be recorded in `orchestration_downgrade` with provenance, never laundered as the operator's choice.

R15. `saga.py save` MUST reject a tick where `orchestration_mode != orchestration_operator_choice` unless `orchestration_downgrade` is non-empty. (`operator_choice` is authoritative for the operator's pick; `mode` is the effective backend; a recommendation override is the separate `recommended`-vs-`operator_choice` pair and is untouched.)

## Key Flows

F1. **Plan authors and the operator approves.** Operator picks `cc-workflows-ultracode`; `/plan` builds the spec (tiers, parallel barriers, refute-N panels), validates it, emits the `.workflow.js`, surfaces tiers/structure/panels for confirmation, persists the spec, and points `orchestration_ref` at it. **Covers R1–R10.**

F2. **Work runs it.** `/work` restores a saga with `mode == cc-workflows-ultracode`, the Workflow tool is available; it re-emits from the canonical spec and runs the workflow — parallel, tiered, refute-N intact. No hand-rolled substitute. **Covers R11, R12.**

F3. **Off-host halt.** Same as F2 but the Workflow tool is genuinely absent or the spec is missing; `/work` halts with a one-line recovery; nothing executes. **Covers R12.**

F4. **Honest degrade.** After a halt, the operator opts to run a lesser backend; the degrade is recorded in `orchestration_downgrade` with provenance; `operator_choice` stays the operator's actual pick. **Covers R13–R15.**

## Acceptance Examples

AE1. **When** ultracode is chosen but the spec fails validation (bad tier, a fan-out with no targets, a judge panel with no pass rule), **then** `/plan` blocks and surfaces the error; no ultracode choice is recorded without a runnable artifact. **Covers R4, R6.**

AE2. **When** the plan declares independent units, **then** the emitted workflow dispatches them concurrently (not a serial `await` chain), honoring declared barriers. **Covers R1.**

AE3. **When** the plan declares a refute-N check on a unit's output, **then** the emitted workflow runs N independent verifiers in parallel and applies the pass rule, with N bounded by the default. **Covers R2, R3.**

AE4. **When** `/work`'s saga says `mode == cc-workflows-ultracode` and the Workflow tool is available, **then** `/work` re-emits and runs the workflow — not hand-rolled subagents. **Covers R11, R12.**

AE5. **When** the Workflow tool is genuinely absent, **then** `/work` halts with a one-line recovery and nothing executes. **Covers R12.**

AE6. **When** an agent degrades the backend, **then** the saga records `orchestration_downgrade` with provenance and leaves `operator_choice` as the operator's pick; a tick with `mode != operator_choice` and an empty downgrade is rejected by `saga.py save`. **Covers R13–R15.**

AE7. **When** a unit has no specified tier, **then** `/plan` derives one from work-shape (judgment→opus/high; mechanical→sonnet or haiku) and surfaces it for override. **Covers R9, R10.**

## Scope Boundaries

- **No `fallback_ok` / auto-degrade path** (KD2 always-halt).
- **team-execution wiring is out of scope** — its emitter is also currently unwired (verified), but wiring it is a separate effort; this build only requires that extending the shared spec keep `team_emitter`'s tests green (R5).
- **No "buildable unit" gate** — any issue, outcome, or rollup is workable; `hermes-not-actionable` gates automation, not operator work.
- **Deferred to `/plan`:** the spec-construction mechanism (author spec JSON directly vs tier-annotated Implementation Units plus a converter); the prose-unit → agent-prompt derivation (a real, lossy transform); the refute-N default pass rule (majority vs unanimous) and default N; how plan-unit dependencies map onto parallel barriers.

## Dependencies / Assumptions

- **The emitter, CLI, spec dataclasses, and tests exist** (`plugins/saga/scripts/execution_spec.py`, `tests/test_workflow_emitter.py`) — this build extends them (parallel + refute-N) and wires them in. Today the emitter renders serial-only with no verification primitive (verified).
- **The Workflow tool is available in a normal Claude Code session without ultracode mode** (operator-confirmed; it is callable in-session), and supports `parallel()`/`pipeline()` and judge-panel patterns. It is genuinely absent only off-host (redis-channel / non-Claude-Code runner), which is the halt signal.
- **An existing inline/serial baseline + `recheck_orchestration_capability`** already recompile down off-host while preserving units and tiers; this build keeps that floor but, per KD2, `/work` halts rather than auto-degrading a guarantee-bearing ultracode choice.
- **The global tier rule** (judgment→opus; mechanical/deterministic→sonnet/haiku; read-only survey→sonnet) is the basis for R10 default derivation.

## Outstanding Questions

*Resolved by the doc-review settling pass (no `/plan` blockers remain):*

- Launch + off-host detection (was P1) — `/work` instructs `Workflow({scriptPath})` on `mode == ultracode` (a valid opt-in); absence = the tool not present in-session.
- Spec persistence (was P1) — the spec JSON is canonical and persisted (KD3, R7).
- refute-N expressibility (was P1) — now in scope as a real emitter extension (R2, R3).

*Deferred to planning (none block `/plan`):* the items in Scope Boundaries' "Deferred to `/plan`" bullet.

## Sources / Research

- **Ideation:** `docs/ideation/2026-06-21-plan-work-backend-handoff-ideation.md`. **Review:** `docs/reviews/2026-06-21-plan-work-backend-handoff-doc-review.md`.
- **Emitter + spec (extend + wire):** `plugins/saga/scripts/execution_spec.py` — `emit_workflow_script` (≈L306, serial `await` chain, no verify primitive), `emit_inline_baseline` (≈L375), `ExecutionSpec`/`Unit`/`Tier`, the `emit` CLI; tests `tests/test_workflow_emitter.py`.
- **Backend contract:** `plugins/saga/references/operator-choice.md` (§1 backends, §4 capability gate, §6 `orchestration_ref`); off-host recompile via `lifecycle_state.recheck_orchestration_capability` (`plugins/saga/references/execution-spec.md`).
- **Saga fields + telemetry:** `plugins/saga/scripts/saga.py` (`orchestration_mode` / `orchestration_operator_choice` / `orchestration_downgrade`, the `save` path, the field comment at ≈L172); `plugins/saga/scripts/override_rate_reader.py`.
- **Wiring sites:** `plugins/saga/skills/plan/SKILL.md` §5.2–5.3; `plugins/saga/skills/work/SKILL.md` Phase 1.4 / Phase 2.
- **Journal:** DECISIONS `#operator-choice-framework`, `#operator-choice-docs-and-confidence`, the R9 "one spec, two emitters" decision; LEARNINGS `#dead-wiring-needs-producer-and-consumer`.
- **Forensic basis:** campps issue-38 session + saga ticks (`.claude/saga/sagas/issue-38/`).
