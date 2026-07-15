---
title: Codex-side cross-runtime Outcome parity and release
repo: infiquetra-codex-plugins
type: capability
team: asgard
project: operations
status: Shaping
labels: capability, hermes-task, needs-plan
risk: high
handoff_maturity: requirements-ready
approval_state: approved
---

# Codex-side cross-runtime Outcome parity and release

### Objective

Deliver the Codex-side parity and release half of the `improve-claude-plugins` lease-safe runtime
continuity outcome against the Claude-authored cross-runtime contract.

### Intent

Adapt the merged Claude cross-runtime Outcome compatibility contract to Codex-native Saga surfaces.
Codex must discover and attach to the same committed Outcome identity, share the git-common-dir
coordination substrate in the same clone, reconstruct canonical status from committed specification
plus GitHub in a different clone, consume the already-merged Codex lease/settlement substrate, and
emit/consume the same repository- and freshness-bound handoff evidence. This is a behavior-parity
port and release, not a byte-copy of Claude host assumptions. It must preserve Codex's native
`outcome.dispatch.v2` intent/acknowledgement contract: only a protected `ack_kind=launched` launch
receipt proves dispatch, while a handoff is not itself a launch.

### Out-of-scope / non-goals

- Redesigning or forking the merged Claude compatibility schema.
- Making `~/.codex`, Codex rollout history, protected workflow evidence, or local launch receipts
  canonical Outcome status.
- Importing another host's git-common-dir cache or protected receipt files.
- Adding a Codex-only lease, idempotency, settlement, completion, or board authority.
- Re-porting the #351/#355/#356 lease, fencing, resource-guard, or settlement substrate owned by the
  prerequisite Codex shared-runtime issue.
- Implementing the final two-runtime acceptance harness owned by the sibling acceptance issue.

### Files expected to change

- `plugins/saga/scripts/outcome.py`
- `plugins/saga/scripts/outcome_spec.py`
- `plugins/saga/scripts/outcome_store.py`
- `plugins/saga/scripts/outcome_dispatcher.py`
- `plugins/saga/scripts/outcome_compat.py` (new or ported, per the Claude contract)
- `plugins/saga/skills/outcome/SKILL.md`
- `plugins/saga/references/outcome-cross-runtime.md` (new or ported)
- `tests/test_outcome_cross_runtime.py` (new)
- `tests/test_outcome_dispatch_migration.py`
- `plugins/saga/.codex-plugin/plugin.json`
- `plugins/saga/CHANGELOG.md`
- `docs/engineering-journal/DECISIONS.md`
- Any Codex repository validation inventory whose digest/version changes with the Saga release.

### Tests to add or update

- Claude-created Outcome discovery from the same clone.
- Codex-created fixture discovery by the Claude-compatible schema.
- Different-clone reconstruction without importing cache state.
- Duplicate-advance rejection through the prerequisite shared lease/idempotency identities while
  retaining Codex `outcome.dispatch.v2` acknowledgement semantics.
- Launch/handoff receipt replay, wrong repository, stale spec revision, and stale issuance.
- Bounded same-clone `advance-one` handoff in both directions; copied, cross-clone, multi-subplot,
  multi-operation, replayed, expired, and future-skewed references are rejected before mutation.
- Legacy `outcome-bundle/1` import rejection; deprecated export/discovery compatibility remains
  read-only and cannot write or replay authoritative state.
- Compatibility and schema version skew HALTs.
- Codex plugin release and repository inventory validation.

### Context library links

_none_

### Inputs inventory

- Parent requirements: infiquetra/infiquetra-claude-plugins#579.
- Outcome specification:
  `docs/outcomes/lease-safe-runtime-continuity/outcome-spec.json`, node `codex-parity`.
- The merged Claude child PR, exact compatibility schema/version, release tag or commit, and journal
  decisions; these are hard inputs, not prose to reinterpret.
- The merged Codex shared-runtime substrate PR, exact source-port manifest, shared broker-root digest,
  settlement identity, resource-guard contract, and preserved dispatch-v2 evidence.
- Codex Saga Outcome modules, dispatch-migration tests, plugin manifest, and repository validation
  inventories in `infiquetra-codex-plugins`.
- The shared #351/#355/#356 settlement, fencing, and lease semantics represented by the Claude
  contract and already ported into the Codex substrate release.
- GitHub completion evidence and repository identity used by both runtimes.

### Failure modes / pre-mortem

- The port copies Claude host/tool assumptions and passes fixtures while failing on Codex-native paths.
- Codex accepts an unknown compatibility field/version or silently drops a load-bearing field.
- Same-clone store resolution diverges because the port uses a runtime home instead of git-common-dir.
- A Codex retry uses a different idempotency key and duplicates a Claude dispatch.
- The port treats `handed-off` as `launched`, bypassing Codex's protected acknowledgement boundary.
- Cross-clone discovery accidentally exposes transient lease, handoff, or launch state instead of
  returning canonical completion/candidate-frontier projection with transient state unknown.
- The Codex plugin is changed without updating its release/validation inventory, leaving installed
  behavior stale.

### Stop conditions

- HALT if the Claude contract is not merged, versioned, and digest-pinnable.
- HALT if the Codex shared-runtime substrate is not merged, installed, and bound to an exact port
  manifest and source contract.
- HALT if parity requires changing the upstream schema inside the Codex PR; return to the Claude issue.
- HALT if Codex runtime-local state becomes canonical or copied cross-host state is required.
- HALT if either runtime order can produce duplicate dispatch/completion evidence.
- HALT if version skew degrades instead of returning an actionable, mutation-free compatibility
  receipt.

### Acceptance criteria

- [ ] Codex reads the merged Claude compatibility envelope without translation drift and discovers a
  Claude-created Outcome from the same repository by Outcome ID. Check: `uv run pytest
  tests/test_outcome_cross_runtime.py -k claude_to_codex_discovery`.
- [ ] A Codex-created conforming fixture produces the same derived state when read through the shared
  schema and GitHub evidence contract; cross-clone projections compare canonical completion and
  candidate frontier only, with transient state explicitly unknown. Check: `uv run pytest
  tests/test_outcome_cross_runtime.py -k codex_to_claude_compatible_state`.
- [ ] Same-clone Codex and Claude paths resolve the same git-common-dir store while different clones
  reconstruct without copying that store. Check: `uv run pytest
  tests/test_outcome_cross_runtime.py -k 'same_clone_store or cross_clone_reconstruction'`.
- [ ] A Codex `advance-one` cannot duplicate a Claude-reserved/dispatched leaf, and the inverse
  ordering is also single-dispatch; accepting a handoff creates a normal Codex launch intent and only
  `ack_kind=launched` settles it as dispatched. Check: `uv run pytest
  tests/test_outcome_cross_runtime.py -k concurrent_advance_single_dispatch`.
- [ ] Codex rejects runtime-local status authority plus stale, forged, replayed, wrong-repository, or
  incompatible handoff evidence without mutation. Check: `uv run pytest
  tests/test_outcome_cross_runtime.py -k 'runtime_local_not_canonical or handoff_rejected or version_skew_halts'`.
- [ ] Handoffs authorize one exact operation on one subplot for at most 300 seconds with at most 30
  seconds of future skew; copied, cross-clone, broad, replayed, stale, or forged references and all
  legacy bundle imports fail before mutation. Check: `uv run pytest
  tests/test_outcome_cross_runtime.py -k 'handoff_scope or handoff_rejected or legacy_bundle_import'`.
- [ ] Codex Saga release metadata, changelog, journal, validation inventory, and full quality gates
  ship in one PR after the Claude contract is merged. Check: repository validation and full test suite
  pass.

### Verification

```bash
uv run pytest tests/test_outcome_cross_runtime.py tests/test_outcome_dispatch_migration.py -v
uv run pytest tests/test_outcome_store.py tests/test_outcome_command.py -v
uv run ruff format --check .
uv run ruff check .
uv run mypy plugins/ scripts/ tests/ --ignore-missing-imports
uv run bandit -r plugins/
uv run pytest
uv run python scripts/validate_codex_plugins.py
```

### Notes / conventions

- Native parent: infiquetra/infiquetra-claude-plugins#579 (cross-repo sub-issue link).
- Hard prerequisites: the Claude-side child and Codex shared-runtime substrate child are merged and
  installed. Pin both source contract SHAs/versions plus the substrate port-manifest digest in the
  Codex plan and parity evidence.
- Run the repository's mandatory Claude-to-Codex portability workflow from a clean isolated
  worktree: fresh staged port manifest, exhaustive classification gate before behavior edits,
  unit/cutover gates, isolated install, fresh-session proof, and rollback evidence.
- The repository is not currently mapped to a default project. Add this issue explicitly to
  Operations with Status `Shaping` and Objective `improve-claude-plugins`; do not silently create a
  different board mapping. Do not create it while Shaping exceeds WIP without either cleared capacity
  or an explicit operator override.
- Handoff maturity: requirements-ready. Run `saga:plan`, `saga:doc-review`, approved Verified
  Workflow execution, and `saga:code-review` before merging.

### Handoff maturity
requirements-ready

### Suggested next action
Use `/plan <issue>` to create an implementation plan.

### Source context
- Source: docs/outcomes/lease-safe-runtime-continuity/issue-sources/codex-cross-runtime-parity.md
- Source type: local-file
- Source title: codex-cross-runtime-parity

### Recommended Tier Band
opus/high

## Created Issue

- URL: https://github.com/infiquetra/infiquetra-codex-plugins/issues/34
- Number: 34
- Created at: 2026-07-15T10:50:34.908284+00:00

