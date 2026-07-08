---
title: Force structured agent output in execution_spec workflows — issue #503
type: fix
status: active
date: 2026-07-08
origin: https://github.com/infiquetra/infiquetra-claude-plugins/issues/503
---

# Force Structured Agent Output In `execution_spec` Workflows — Issue #503

## Summary

`execution_spec.py` currently prompts agents to end with a JSON object and then relies on `__gate`
to parse free text. Completed work can fail if the agent wraps the object in prose, fences, YAML, or
other non-bare text. The workflow harness supports schema-forced structured output, so emitted
`agent()` calls should request the expected shape at generation time instead of treating `__gate` as
the primary parser.

## Requirements

R1. For every unit with `returns`, the emitted `agent()` options must include a JSON Schema derived
from those return keys.

R2. The schema must require every declared return key and allow additional properties.

R3. Schema emission must be single-sourced so singleton calls, parallel thunks, iterate-to-consensus
loops, unattended climb retries, and pilot/fan-out paths cannot drift.

R4. External-engine dispatch unit calls must also carry the schema when they declare `returns`.

R5. Cheap-tier pull-cord behavior must remain valid: a cheap unit may still return
`{"pull_cord": "..."}` instead of the normal return object.

R6. Existing `__gate` validation stays as a backstop for empty output, target counts, pull-cord
collection, and malformed legacy output.

R7. Tests must assert schema emission across the representative call shapes.

R8. Saga release surfaces must be updated because workflow emission behavior changes.

## Key Technical Decisions

**KTD1: Add schema in `_agent_opts()`.** Every unit `agent()` call already consumes `_agent_opts()`;
that is the right single source for schema emission.

**KTD2: Use JSON-compatible schema literals.** `json.dumps` can render the schema object directly
into the JavaScript options object, avoiding hand-built JavaScript object strings.

**KTD3: Pull cord uses `oneOf` only for cheap-tier units.** The existing prompt allows pull cord only
for cheap-tier units with returns. The schema should reflect that contract without weakening normal
return requirements for non-cheap units.

## Implementation Units

### U1. Schema helper

Add a helper that builds the JSON Schema from a unit's `returns`. For normal units, use:

```json
{"type": "object", "properties": {"<key>": {}}, "required": ["<key>"], "additionalProperties": true}
```

For cheap-tier pull-cord units, wrap that schema in `oneOf` with a pull-cord object schema.

### U2. Agent options

Append `schema: <schema>` in `_agent_opts()` whenever `unit.returns` is non-empty, for both normal
and external-engine dispatch options.

### U3. Tests

Add tests that inspect the emitted script for:

- normal return schema,
- external-engine return schema,
- parallel thunk schema,
- iterate-to-consensus schema,
- unattended climb retry schema,
- cheap-tier pull-cord `oneOf`.

### U4. Release surfaces

Bump saga metadata, update changelog, regenerate marketplace metadata, and run release-surface
guards.

## Scope Boundaries

Out of scope: verifier panel under-strength behavior, verifier worktree visibility, changing
`__gate` parsing, changing return key semantics, or migrating existing emitted workflow files.

## Verification

- `uv run pytest tests/test_saga_execution_spec.py tests/test_workflow_emitter.py -k "schema or agent_opts or emit" -v`
- `uv run pytest tests/test_saga_execution_spec.py tests/test_workflow_emitter.py tests/test_saga_plugin.py::test_infiquetra_lifecycle_metadata_and_marketplace_entry_match -v`
- `uv run python -m ruff check plugins/saga/scripts/execution_spec.py tests/test_saga_execution_spec.py tests/test_workflow_emitter.py tests/test_saga_plugin.py`
- `uv run python -m ruff format --check plugins/saga/scripts/execution_spec.py tests/test_saga_execution_spec.py tests/test_workflow_emitter.py tests/test_saga_plugin.py`
- `uv run python -m mypy plugins/saga/scripts/execution_spec.py tests/test_saga_execution_spec.py tests/test_workflow_emitter.py --ignore-missing-imports`
- `python3 scripts/check_release_surface_parity.py`
- `uv run python scripts/sync_marketplace.py --check`
- `python3 tools/release_surface_diff_guard.py --base-ref origin/main`
- `git diff --check`
