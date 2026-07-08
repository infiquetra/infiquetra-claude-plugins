---
title: Fix cross-repo objective ingestion provenance and subplot IDs — issues #512/#513
type: fix
status: active
date: 2026-07-08
origin:
  - https://github.com/infiquetra/infiquetra-claude-plugins/issues/512
  - https://github.com/infiquetra/infiquetra-claude-plugins/issues/513
---

# Fix Cross-Repo Objective Ingestion Provenance And Subplot IDs — Issues #512/#513

## Summary

`/outcome start --from-objective` currently treats sub-issue numbers as globally unique and stamps
every ingested node with the parent Objective's repository. Cross-repo Objectives can therefore fail
with duplicate `subplot_id` values, and even when they start successfully, board-sync/reconcile/
harvest target the wrong GitHub repository for child issues.

## Requirements

R1. `discover_subissues` must fetch each sub-issue's own `repository.nameWithOwner`.

R2. `discover_subissues` must also fetch tracked issue repositories so edge inference can distinguish
same-number issues across repositories.

R3. Normalized sub-issues must surface the child repository without breaking same-repo fixtures.

R4. `nodes_from_objective` must stamp each node's `github.repo` and `github.issue` with the child
repo, falling back to the parent repo only when older normalized data has no child repo.

R5. Subplot IDs must remain `sub-<number>` when the number is unique in the ingested set, and become
repo-qualified when the same number appears in multiple repositories.

R6. Edge inference must use the exact same subplot ID scheme as node assembly.

R7. Ambiguous legacy `blocked_by` references that name only a duplicated number must be dropped
fail-loudly rather than guessed.

R8. Tests must cover cross-repo duplicate issue numbers, cross-repo provenance, same-repo unchanged
IDs, and edge inference under the new ID scheme.

R9. Saga release surfaces must be updated because `/outcome` ingestion behavior changes.

## Key Technical Decisions

**KTD1: Qualify IDs only on number collision.** Existing same-repo outcomes and tests keep the
familiar `sub-95` shape when issue numbers are unique. Cross-repo duplicates get deterministic
repo-qualified IDs such as `sub-infiquetra-campps-tenant-setup-95`.

**KTD2: Centralize ID generation in `outcome_edges`.** The edge mapper already owns relationship
normalization. Adding a shared `subplot_ids_for_subissues` helper lets `nodes_from_objective` and
`edges_from_relationships` consume one ID mapping.

**KTD3: Normalize tracked issues as typed references.** New GraphQL data becomes
`{"repo": "owner/repo", "number": N}` so cross-repo relationships are precise. The edge mapper will
still accept legacy integer references for same-repo fixtures.

## Implementation Units

### U1. Discovery normalization

Add `repository { nameWithOwner }` to sub-issue and tracked-issue selections. Normalize child repo
onto each sub-issue and normalize `blocked_by` entries as typed repo/number references when repo data
is present.

### U2. Shared subplot ID mapping

Add helpers in `outcome_edges.py` to derive stable subplot IDs for normalized sub-issues, qualifying
only same-number collisions by repository slug.

### U3. Edge inference

Update `edges_from_relationships` to resolve typed blocked-by references by repo+number, preserve
legacy integer handling for unambiguous same-repo cases, and report ambiguous/dangling/self/cycle
drops using the resolved subplot IDs.

### U4. Node assembly

Update `nodes_from_objective` to use the shared subplot ID map and stamp each node with its child
repository.

### U5. Tests and live verification

Add fixture-driven tests for:

- normalized child repo and tracked issue repo,
- cross-repo duplicate issue numbers ingesting with unique IDs,
- child-repo provenance stamps,
- same-repo unique numbers retaining `sub-<N>`,
- edge inference resolving typed cross-repo relationships.

Run the live Objective ingestion smoke from the issues if credentials and network allow.

### U6. Release surfaces

Bump saga metadata, update changelog, regenerate marketplace metadata, and run release-surface
guards.

## Scope Boundaries

Out of scope: migrating already-started outcome specs, changing graph-edit verbs, changing dispatch
or board-sync behavior beyond consuming corrected `github` stamps, and deleting or rewriting
existing outcome artifacts.

## Verification

- `uv run pytest tests/test_outcome_from_objective.py -v`
- `uv run python -m ruff check plugins/saga/scripts/discover_subissues.py plugins/saga/scripts/outcome_edges.py plugins/saga/scripts/outcome.py tests/test_outcome_from_objective.py tests/test_saga_plugin.py`
- `uv run python -m ruff format --check plugins/saga/scripts/discover_subissues.py plugins/saga/scripts/outcome_edges.py plugins/saga/scripts/outcome.py tests/test_outcome_from_objective.py tests/test_saga_plugin.py`
- `uv run python -m mypy plugins/saga/scripts/discover_subissues.py plugins/saga/scripts/outcome_edges.py plugins/saga/scripts/outcome.py tests/test_outcome_from_objective.py --ignore-missing-imports`
- `python3 scripts/check_release_surface_parity.py`
- `uv run python scripts/sync_marketplace.py --check`
- `python3 tools/release_surface_diff_guard.py --base-ref origin/main`
- `python3 plugins/saga/scripts/outcome.py start collision-check --from-objective infiquetra/campps-context-library#69 --repo-root /tmp/outcome-repro-512-513`
- `python3 plugins/saga/scripts/outcome.py graph collision-check --repo-root /tmp/outcome-repro-512-513`
- `git diff --check`
