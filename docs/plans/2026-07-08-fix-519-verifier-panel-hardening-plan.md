---
title: Harden execution_spec refute-N verifier panels - issue #519
type: fix
status: active
date: 2026-07-08
origin: https://github.com/infiquetra/infiquetra-claude-plugins/issues/519
---

# Harden `execution_spec` Refute-N Verifier Panels - Issue #519

## Summary

Refute-N verifier panels can silently degrade to `0/N` reporting verifiers. The current
emitter logs `UNDER-STRENGTH` but still lets the workflow continue when no verifier returns a
schema-valid verdict. Verifiers also run in disposable worktrees that may not contain the unit's
actual output. This fix makes verifier transport structured, makes under-strength panels fail
loudly, and gives verifiers explicit evidence and branch-materialization instructions.

## Requirements

R1. Every verifier `agent()` call must request a schema-valid verdict at generation time.

R2. The verifier schema must require `refuted`, `upheld`, `verifier_identity`, `fallback_depth`,
and `examined_sha`.

R3. Verifier prompts must instruct the verifier to materialize the primary checkout revision
before judging and to report the SHA it actually examined.

R4. Verifier prompts must carry the unit result directly so isolated worktree verifiers can see
the worker's returned evidence even when file output is uncommitted.

R5. A panel with fewer reporting verifiers than its quorum floor must throw a workflow-level
`verifier-under-strength` error.

R6. A malformed verifier object must not count as reporting; it must remain missing.

R7. Refutation behavior must still fail loudly with `verifier-disagreement`.

R8. Saga release surfaces must be updated because emitted workflow behavior changes.

## Key Technical Decisions

**KTD1: Add schema to `_verifier_agent_opts()`.** Verifier call sites are already single-sourced
through `_verifier_agent_opts()`, so the schema belongs there rather than in each panel renderer.

**KTD2: Embed unit result in the verifier prompt at runtime.** The workflow script cannot run
shell commands itself, but it can build a dynamic verifier prompt with `JSON.stringify(result)`.
This gives verifiers the worker's returned evidence without relying on their isolated checkout.

**KTD3: Materialization remains a verifier instruction.** The verifier has Bash and read-only
tools; the generated harness does not. The prompt must tell the verifier to read the primary
checkout SHA with `git -C "$REPO" rev-parse HEAD`, materialize that SHA in its disposable
worktree with `git checkout <sha> -- .`, and include `examined_sha` in the verdict. If enough
evidence is still unavailable, including named untracked output files, the verifier should inspect
the primary checkout read-only and return a refutation describing the visibility gap rather than a
prose "nothing to verify" result.

**KTD4: Under-strength throws before accept-path success.** Below-floor panels are not advisory.
The emitted script should log missing-verifier detail and then throw `verifier-under-strength`.
That preserves the diagnostic while preventing vacuous success.

## Implementation Units

### U1. Verifier schema

Add a verifier schema helper and append it to `_verifier_agent_opts()`:

- `refuted`: array
- `upheld`: array
- `verifier_identity`: string
- `fallback_depth`: permissive value, because existing runtime depth coercion accepts numbers and
  numeric strings
- `examined_sha`: non-empty string by prompt contract

### U2. Verifier evidence prompt

Add a small emitted JavaScript helper that combines the static verifier prompt with the runtime
unit result. Use that helper for every verifier call in `_emit_panel_reconciliation()`. Keep
`input:` populated with an object containing the unit result as a second, runtime-native channel.

### U3. Hard under-strength gate

Replace the log-only under-strength behavior with a throw when `reported.length < floor`. Keep
the existing missing-verifier log and refutation throw, but make below-quorum panels terminal.

### U4. Tests

Update/add emitter tests for:

- verifier schema in all verifier call sites,
- `examined_sha` and materialization instructions in prompts,
- dynamic unit-result prompt helper emission,
- valid-verdict predicate covering `refuted`, `upheld`, and `examined_sha`,
- `verifier-under-strength` throw with the correct quorum floor,
- existing `verifier-disagreement` behavior.

### U5. Release and journal surfaces

Bump saga to `0.75.4`, update marketplace metadata, changelog, and release-surface tests. Update
the engineering journal/queued entry to mark the verifier-panel visibility item shipped.

## Scope Boundaries

Out of scope: changing worker commit behavior, adding filesystem writes from workflow scripts,
changing verifier agent tools, changing majority/unanimous pass-rule semantics when a quorum
reports, or addressing possible RTK/output-shaping content inflation beyond making verifier
evidence explicit and schema-checked.

## Verification

- `uv run pytest tests/test_saga_execution_spec.py tests/test_workflow_emitter.py tests/test_saga_plugin.py::test_infiquetra_lifecycle_metadata_and_marketplace_entry_match -v`
- `uv run ruff check plugins/saga/scripts/execution_spec.py tests/test_saga_execution_spec.py tests/test_workflow_emitter.py tests/test_saga_plugin.py`
- `uv run ruff format --check plugins/saga/scripts/execution_spec.py tests/test_saga_execution_spec.py tests/test_workflow_emitter.py tests/test_saga_plugin.py`
- `uv run mypy plugins/saga/scripts/execution_spec.py`
- `uv run python scripts/sync_marketplace.py --check`
- `uv run python scripts/check_release_surface_parity.py`
- `uv run python tools/release_surface_diff_guard.py --base-ref origin/main`
- `git diff --check`
- emitted workflow `node --check` syntax smoke
