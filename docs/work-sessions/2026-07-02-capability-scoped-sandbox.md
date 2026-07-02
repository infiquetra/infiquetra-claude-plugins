---
title: Work session — Capability-Scoped Agent Sandbox (#287)
date: 2026-07-02
issue: infiquetra/infiquetra-claude-plugins#287
plan: docs/plans/2026-07-02-capability-scoped-sandbox-plan.md
review: docs/reviews/2026-07-02-capability-scoped-sandbox-plan-readiness.md
branch: feat/capability-scoped-sandbox-287
destination: merge
orchestration: inline (U4 + U7 delegated to Sonnet 5 subagents)
status: PR-ready pending code-review gate
---

# Work session — Capability-Scoped Agent Sandbox (#287)

Executed the seven-unit plan inline on the work branch. U1-U3, U5, U6 ran on the main (Opus)
thread; U4 (inventory + skill docs) and U7 (release triad + journal) were delegated to Sonnet 5
subagents per operator directive, then independently verified.

## What shipped

- **U1 — `sandbox` contract.** A two-axis envelope (`mutation_policy` × `workspace_isolation`)
  on `Unit` (`execution_spec.py`) and `Node` (`outcome_spec.py`), with named profile shorthand
  (`read-only-verify`, `sandboxed-mutate`) that expands at parse. Absent ⇒ ambient × read-write;
  `to_dict` emits expanded axes (canonical) and no key when absent (existing specs byte-identical).
- **U2 — read-only verifier + emitter wiring.** New `plugins/saga/agents/readonly-verifier.md`
  (Bash/Read/Grep/Glob, no Edit/Write). All THREE verifier-emitting sites collapsed into one
  `_verifier_agent_opts` helper that emits `agentType: "saga:readonly-verifier"` +
  `isolation: "worktree"` unconditionally. A literal-consistency guard pins the emitted agentType
  to the agent-def `name:` frontmatter.
- **U3 — enforceability matrix + halt.** `SANDBOX_ENFORCEABLE_BY_BACKEND` +
  `unenforceable_sandbox_axis` in `execution_spec.py`. `team_emitter.emit` raises `SpecError` at
  authoring time; `outcome_dispatcher.dispatch` probes the matrix into an axis-naming
  `HaltReceipt`; unlisted backends default to halt.
- **U4 — spawn-site inventory + skills.** `references/sandbox-spawn-sites.md` +
  four SKILL.md edits + `CLAUDE.md` pointer + `tests/test_sandbox_spawn_sites.py`. (Sonnet.)
- **U5 — external write-ceiling lift.** `engine_dispatch.py`: agy `sandboxed-mutate` ⇒
  `mode: "patch-only"` + `write_set`; codex `sandboxed-mutate` ⇒ halt. Declared sandbox recorded
  as optional `attribution.sandbox` (no manifest version bump). Doc updated.
- **U6 — clobber-contained integration test.** `tests/test_sandbox_clobber_contained.py`: a real
  disposable worktree contains a `git checkout` clobber (with a control proving the clobber is
  destructive in the primary tree), plus wiring + no-escalation properties.
- **U7 — release triad + journal.** saga 0.46.0→0.47.0, team-execution 2.6.0→2.7.0, marketplace,
  both CHANGELOGs, drift-guard test updates, DECISIONS + LEARNINGS entries. (Sonnet.)

## Decisions & deviations from the plan (with rationale)

1. **`Sandbox` mirrored, not shared.** `outcome_spec.py` imports only stdlib and raises
   `OutcomeSpecError` (its line-494 comment marks the deliberate independent-houses boundary). A
   shared `Sandbox` class would cross that boundary and leak `SpecError` past `Node.validate`, so
   the envelope is mirrored in each house and a cross-module drift-guard test asserts the two
   vocabularies stay identical.
2. **Matrix placement follows the plan (execution_spec.py).** `team_emitter` reaches it via its
   existing dynamic `execution_spec` load; `outcome_dispatcher` gained one small top-level import.
   The helper duck-types the sandbox so it serves both spec houses.
3. **U3 extended one line into `outcome.py` (beyond the plan's file list).** The dispatcher probe
   is a dead wire unless the `DispatchRequest` producer carries the node's sandbox. Added an
   optional `sandbox` field to `DispatchRequest` and passed `node.sandbox` at the single
   construction site, so the probe fires in production, not only in hand-built tests
   (dead-wiring doctrine — producer + consumer both wired).
4. **Exception-identity fix in `team_emitter`.** Making `emit_team_structure` *raise*
   `SpecError` surfaced a latent bug: it loaded `execution_spec` via `importlib` without
   registering it in `sys.modules`, so `mod.SpecError` was a distinct class from the canonical
   one an upstream `except` catches. Fixed by reusing `sys.modules.get("execution_spec")`.
   Captured in LEARNINGS `{#dynamic-module-reload-breaks-exception-identity}`.
5. **Two drift-guard tests updated (legitimate feature-caused churn).**
   `test_saga_plugin.py`'s "agents/ contains ONLY mechanical-executor" invariant now also allows
   `readonly-verifier` (a structural read-only agent, not a judgment persona). The manifest
   R17 no-orphan-field guard got a `saga-spec.md §13.3` row for the new `attribution.sandbox`.

## Test evidence

Full green gate at U6 (before U7): **1699 passed**, `ruff format --check` clean (181 files),
`ruff check` clean, `mypy plugins/` clean (36 files). Per-unit suites green as each landed
(U1 85, U2 31, U3 386 across affected suites, U5 39, U6 8, U4 2). Final gate re-run after U7 —
see below.

## Files modified

Code: `plugins/saga/scripts/execution_spec.py`, `outcome_spec.py`, `team_emitter.py`,
`outcome_dispatcher.py`, `outcome.py`, `engine_dispatch.py`, `provenance_manifest.py`.
Agent: `plugins/saga/agents/readonly-verifier.md` (new).
Docs/refs: `plugins/saga/references/sandbox-spawn-sites.md` (new), `saga-spec.md`,
four saga SKILL.md files, `external-engine-workers.md`, repo `CLAUDE.md`.
Release: both `plugin.json`, `marketplace.json`, both `CHANGELOG.md`, DECISIONS + LEARNINGS.
Tests: `test_saga_execution_spec.py`, `test_outcome_spec.py`, `test_team_emitter.py`,
`test_outcome_dispatcher.py`, `test_saga_engine_dispatch.py`, `test_sandbox_clobber_contained.py`
(new), `test_sandbox_spawn_sites.py` (new), `test_saga_plugin.py`,
`test_team_execution_plugin.py`, `saga-spec.md` consumer-matrix.

## Code review

Independent adversarial review (fresh Opus reviewer, working-tree diff, ran the suites +
CI-equivalent mypy/ruff). **Verdict: mergeable as-is, no P0/P1.** It traced every wiring claim
producer→consumer and confirmed the top-risk failure mode (silent sandbox drop / dead wiring)
does not occur on any structurally-wireable path — including the `outcome.py:769` →
`outcome_dispatcher.dispatch:127` producer→consumer for the node sandbox, and all three verifier
emitter sites routing through `_verifier_agent_opts`.

Three P3 findings, dispositioned:
- **Fixed** — `outcome_dispatcher.team_execution_artifact` still did a redundant fresh
  `exec_module` of `execution_spec` (the same dual-class identity fragility U3 fixed); collapsed
  to the module-level `import execution_spec`.
- **Fixed** — renamed `test_..._write_set_never_exceeds_declared_files` →
  `test_agy_write_set_is_passed_through_verbatim_not_expanded`; the builder passes `write_set`
  through verbatim, and clamping to the unit's declared files is the caller's contract (the
  chaperone passes `unit.files`), not builder-enforced. Test name now matches what it proves.
- **Accepted (no change)** — the engine leg's R4 halt/lift is prose-wired via
  `external-engine-workers.md` (which the diff updates), because `engine_dispatch` has no Python
  production caller. This is the pre-existing invocation model for that module and matches KTD4
  ("the external face is a dispatch-builder change"); the verifier and outcome-dispatcher legs
  are structurally enforced.

Post-fix gate: **1699 passed**, `ruff format --check` + `ruff check` clean, `mypy plugins/` clean.

## Next step

Offer commit (feature branch) + PR-open under explicit operator confirmation. Destination is
merge, also under confirmation. `/qa` acceptance carries the live-harness registry-drift smoke
(agent resolves, toolset lacks Edit/Write, cwd is a worktree) that pytest cannot exercise.
