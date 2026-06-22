---
date: 2026-06-21
saga: task-plan-work-backend-handoff
plan: docs/plans/2026-06-21-plan-work-backend-handoff-plan.md
lifecycle_phase: work
status: PR-ready
backend: cc-workflows-ultracode (dynamic Workflow, hand-authored)
---

# Work session — Plan→Work execution-backend handoff

Built the 6-unit plan that makes a `cc-workflows-ultracode` `/plan` author a runnable, approved
workflow (per-unit tiers + real parallel fan-out + refute-N), have `/work` re-emit-and-run-or-halt
(never improvise), and guard `saga.py` so an AI substitution can't be recorded as the operator's
pick. Closes the campps issue-38 failure class (a workflow chosen but never authored → hand-rolled
serial subagents → dropped tiers + refute-N → false `operator_choice: inline`).

## What was built (by U-ID)

- **U1 + U2** (`execution_spec.py`, `test_workflow_emitter.py`) — `Verify` judge-panel construct
  (`Unit.verify {n, pass_rule}`, bounded `VERIFY_N_CAP=7`) + a pure `dependency_layers()` (Kahn,
  pilot as implicit barrier edge, R3); `emit_workflow_script` rewritten to emit topological-layer
  `parallel([...])` waves sequenced by `await`, with each verify panel rendered as a parallel
  judge-panel of N same-tier verifiers + a pass-rule reconciliation. `emit_inline_baseline` stays
  serial. Per-unit `{model, effort}` preserved on every emitted `agent()`.
- **U3** (`saga.py`, `test_capability_degrade.py`) — save-time `operator_choice` provenance guard:
  rejects a tick that newly asserts `mode != operator_choice` without a fresh, non-blank
  `orchestration_downgrade` note that justifies a genuine **downgrade** (effective mode a lower tier
  than the pick). Save-scoped (render/parse round-trip stays valid).
- **U4** (`plan/SKILL.md` §5.2a/5.3) — `/plan` authors the `ExecutionSpec` (tiers from the work-shape
  heuristic, thin prompts, deps + verify panels), validates (hard block), emits, surfaces for
  approval, persists the **spec JSON** as the canonical `orchestration_ref`.
- **U5** (`work/SKILL.md` Phase 1.5) — `/work` re-emits from the canonical spec and runs
  `Workflow({scriptPath})`, or **HALTS** with a one-line recovery if the Workflow tool is genuinely
  absent / spec missing — explicitly not the off-host recompile-down, not hand-rolled subagents.
- **U6** (`operator-choice.md`, `execution-spec.md`, `DECISIONS.md`, version surfaces) — contract
  docs + a DECISIONS entry mirroring KTD1–KTD7; saga **0.36.0 → 0.37.0** across `plugin.json`,
  `marketplace.json`, `CHANGELOG.md`, and the drift-guard test.

## How it was built (dogfooding)

Built as **two dynamic Workflows** (the backend the plan chose), each with refute-N verification —
the exact practice the failed campps run skipped:

- Workflow A (core): U1 ∥ U3 (parallel, different files) → U2 → refute-N panels over the emitter and
  the guard. Found **2 real defects**: a HIGH guard hole (a carried-forward downgrade note laundered a
  fresh issue-38-shape tick) and a LOW mutation-survivable tier test. Both fixed.
- Dogfooding the guard surfaced a **ship-blocker false positive**: a no-orchestration-args progress
  tick on a non-inline saga was rejected (auto-derive stamped `operator_choice="inline"` from the
  default mode). Fixed at the root (`--orchestration-mode` default `None`; choice only set when this
  tick asserts an orchestration signal).
- Workflow B (wire + docs): U4 ∥ U5 → U6 → doc-accuracy panel (2 low precision fixes).
- Phase 5 holistic review (4 lenses, 0 P0/P1): oracle-honesty **clean**, provenance-integrity
  **confirmed** (no bypass, no false positive). 4 P2/P3 refinements fixed (var collision → SyntaxError
  guard; downgrade direction + whitespace note; refute-N `_refuted` consumer; doc step ordering).

## Checks

Full gate green: **966 pass** (the single failure is the known `.claude/`-leak guard tripping on real
on-disk sagas — green in CI). `ruff format --check` + `ruff check` + `mypy` (`plugins/ scripts/ tests/`)
clean; both plugin validators pass; `marketplace.json` valid; emitted `.workflow.js` passes `node --check`.

## Files modified

`plugins/saga/scripts/execution_spec.py`, `plugins/saga/scripts/saga.py`,
`plugins/saga/skills/plan/SKILL.md`, `plugins/saga/skills/work/SKILL.md`,
`plugins/saga/references/execution-spec.md`, `plugins/saga/references/operator-choice.md`,
`docs/engineering-journal/DECISIONS.md`, `plugins/saga/.claude-plugin/plugin.json`,
`.claude-plugin/marketplace.json`, `plugins/saga/CHANGELOG.md`, `tests/test_workflow_emitter.py`,
`tests/test_capability_degrade.py`, `tests/test_saga_plugin.py` (+ the lifecycle docs trail).

## Next step

Open the PR (destination = merge) and squash-merge on green CI.
