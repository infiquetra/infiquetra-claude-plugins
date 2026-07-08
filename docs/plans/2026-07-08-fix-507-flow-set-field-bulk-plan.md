---
title: Add bulk flow set-field support — issue #507
type: fix
status: active
date: 2026-07-08
origin: https://github.com/infiquetra/infiquetra-claude-plugins/issues/507
---

# Add Bulk Flow Set-Field Support — Issue #507

## Summary

`flow set-field` currently sets one field on one issue per process invocation. Bulk project-field
syncs therefore pay the GraphQL field-discovery and project-item discovery cost once per item,
which exceeded operator execution windows when setting Status and Objective on 19 Operations cards.

This plan adds `--numbers` batch support plus repeated `--field/--option` pairs while preserving the
existing `--number` single-card form. One invocation resolves project fields and current project
items once, then applies the selected options to every requested card while reporting per-card or
per-field failures.

## Requirements

R1. Existing `flow set-field --number N --field F --option O` behavior remains compatible.

R2. New `flow set-field --numbers N1,N2,... --field F --option O` sets the same field/option on
multiple issues in a single process invocation.

R3. Repeated `--field/--option` pairs in the same command must set multiple fields across the same
requested issue set in one process invocation.

R4. A bulk run must perform one project-field discovery query and one project-item fetch for the
invocation, not one discovery pass per issue or per field.

R5. Partial failures must be reported per issue/field and the command must continue processing
remaining updates.

R6. A bulk invocation with any failed item must exit non-zero after reporting the full result set.

R7. The flow skill documentation must show the batch form, repeated pair form, and partial failure
behavior.

R8. Mission-control release surfaces must be updated with the behavior change.

## Key Technical Decisions

**KTD1: Add `--numbers` and repeated field/option pairs.** The issue verification command names
`--numbers`, while the acceptance criteria requires setting two fields across many issues in one CLI
invocation.

**KTD2: Share the mutation engine between single and bulk paths.** Keep `flow_set_field` as the
single-card public helper and add a bulk helper that accepts a list of numbers, reusing the same
option validation and mutation shape.

**KTD3: Report all attempted cards before failing bulk mode.** Single-card mode can keep raising on
failure. Bulk mode should collect `updated` and `failed` entries, emit them, then raise a summary
error if any card failed so shells and agents still see non-zero status.

## Implementation Units

### U1. Extract shared field and item resolution

Add helpers for resolving target fields/options and indexing project items by `(repo, number)`. The
bulk path should perform one project-field discovery query and one `get_project_items` call.

### U2. Add `flow_set_field_bulk`

Implement functions that:

- validate all requested field/option pairs before mutation,
- indexes current project items once,
- iterates requested issue numbers,
- records missing project items as failures,
- catches per-card/per-field GraphQL mutation errors and continues,
- emits a JSON-friendly summary through `_out`,
- raises after output if any field update failed.

### U3. Wire argparse

Change `flow set-field` so `--number` and `--numbers` are mutually exclusive, with one required.
Parse `--numbers` as comma-separated positive integers. Allow repeated `--field` and `--option`
pairs and require matching counts.

### U4. Tests

Add tests that prove:

- the single-card helper still raises a helpful unknown-option message,
- bulk mode uses one field-discovery query and one project-item fetch while issuing N*M mutations,
- bulk mode continues after a mutation failure and reports which number failed,
- the CLI parser routes `--numbers` and repeated field/option pairs to the bulk helper.

### U5. Documentation and release surfaces

Document the batch form and partial failure contract in the flow skill. Bump mission-control
metadata, changelog, marketplace registry, and version drift guard to the next patch version.

## Scope Boundaries

Out of scope: cross-run field/option caching, setting multiple field/option pairs in one command,
or changing `board move`/`labels sync-fields` semantics.

## Verification

- `uv run pytest plugins/mission-control/tests/test_flow_subcommands.py -k "set_field or numbers" -v`
- `uv run pytest plugins/mission-control/tests/test_prompt_alignment.py::test_sdlc_manager_metadata_and_marketplace_entry_match -v`
- `uv run python -m ruff check plugins/mission-control/scripts/sdlc_manager.py plugins/mission-control/tests/test_flow_subcommands.py plugins/mission-control/tests/test_prompt_alignment.py`
- `uv run python -m ruff format --check plugins/mission-control/scripts/sdlc_manager.py plugins/mission-control/tests/test_flow_subcommands.py plugins/mission-control/tests/test_prompt_alignment.py`
- `uv run python -m mypy plugins/mission-control/scripts/sdlc_manager.py plugins/mission-control/tests/test_flow_subcommands.py plugins/mission-control/tests/test_prompt_alignment.py --ignore-missing-imports`
- `python3 scripts/check_release_surface_parity.py`
- `uv run python scripts/sync_marketplace.py --check`
- `python3 tools/release_surface_diff_guard.py --base-ref origin/main`
