### Objective

Port the minimum lease, fencing, and dispatch-settlement substrate required for Codex to participate
in lease-safe cross-runtime Outcomes without depending on Claude host paths or replacing Codex's
stronger native dispatch acknowledgement contract.

### Intent

Create a staged Claude-to-Codex proof port in `infiquetra-codex-plugins` after #351, #355, and #356
merge. Codex fleet-core must consume the same runtime-neutral host-local lease registry, resource
heads, token classifications, and resource guard as Claude. Codex Saga must read and emit the same
dispatch-settlement identities while preserving its existing `outcome.dispatch.v2` intent/ack,
protected launch receipt, `handed-off`, and `legacy-unverified` semantics. This substrate lands and
releases before the separate Codex Outcome compatibility consumer.

### Out-of-scope / non-goals

- Porting Claude Agent/Task hooks, Workflow JavaScript, team-execution teardown, agy, orphan
  quarantine, or fleet-doctor behavior merely because they share source files or commits.
- Replacing or weakening Codex `outcome.dispatch.v2` and protected launch-receipt validation.
- Using `~/.claude`, `~/.codex`, installed caches, plugin `PLUGIN_DATA`, or copied state as the shared
  fleet authority.
- Implementing `outcome.discovery.v1`, protected cross-runtime handoff, or the final two-runtime
  acceptance harness; those remain downstream issues.
- Claiming byte parity or making the Claude repository maintained Codex source after cutover.

### Files expected to change

- `plugins/fleet-core/scripts/fleet_commons/` exact broker, concurrency-policy, and resource-guard
  modules selected by the approved port manifest.
- `plugins/saga/scripts/fleet_commons_shim.py` and every guarded vendored shim only if the shared
  import surface changes.
- `plugins/saga/scripts/run_ledger.py`
- `plugins/saga/scripts/dispatch_settlement.py` (new or adapted)
- `plugins/saga/scripts/outcome.py`
- `plugins/saga/scripts/outcome_store.py`
- `tests/test_fleet_lease_broker.py` or fleet-core equivalent (new)
- `tests/test_dispatch_settlement.py` (new)
- `tests/test_outcome_dispatch_migration.py`
- `docs/portability/ports/<cycle>.json` and rendered classification
- `plugins/{fleet-core,saga}/PORTABILITY.md`
- `plugins/{fleet-core,saga}/.codex-plugin/plugin.json`
- `plugins/{fleet-core,saga}/CHANGELOG.md`
- root marketplace/inventory/version/validation surfaces required by the Codex repo
- `docs/engineering-journal/DECISIONS.md`

### Tests to add or update

- Claude/Codex resolution of the same runtime-neutral fleet state root and redacted root digest.
- Cross-runtime lease registry read, acquire, renew, verify, release, supersession, and four-way token
  classification fixtures.
- Resource-guard serialization and crash-safe protected evidence commit fixtures.
- Shared dispatch manifest/spawn/settle identity and chain validation.
- Codex `outcome.dispatch.v2` launch/handed-off/legacy migration regressions alongside shared
  settlement facts.
- Unknown source schema/version, Claude host path, copied cache, unsafe root, and capability-skew
  rejection.
- Port-contract classification, unit, cutover, isolated install, fresh-session readback, rollback,
  release, and full repository validation.

### Context library links

_none_

### Inputs inventory

- Outcome specification:
  `docs/outcomes/lease-safe-runtime-continuity/outcome-spec.json`, node `codex-substrate`.
- Merged source commits and final schemas from infiquetra/infiquetra-claude-plugins#351, #355, and
  #356.
- The runtime-neutral broker-root decision in the reviewed #356 plan.
- Codex `outcome.dispatch.v2`, protected launch receipts, dispatch migration tests, run-fact ledger,
  fleet-core ownership rules, and source-to-Codex port runbook.
- The latest imported Claude source ref and live Codex `origin/main`, captured into a new closed port
  manifest; historical classifications are evidence only.
- Sanitized current Codex runtime capability snapshot and active session facts.

### Failure modes / pre-mortem

- Codex opens a second broker because its adapter defaults to `PLUGIN_DATA` or a Codex home.
- A direct source copy regresses `outcome.dispatch.v2`, accepts a synthetic leaf ID, or treats
  `handed-off` as launched.
- The port manifest scopes only the desired new files and misses source or Codex drift needed by
  their imports and schemas.
- A resource-guard or settlement fact claims parity while field names, root identity, or
  idempotency-key recipes differ between runtimes.
- Metadata versions before behavior/cutover proof and leaves the installed cache or rollback surface
  stale.

### Stop conditions

- HALT if any source prerequisite is unmerged or its exact commit/schema cannot be pinned.
- HALT if the new port contract does not pass its classification gate before behavior edits.
- HALT if parity requires a Claude host path, copied mutable state, or a Codex-only broker/settlement
  authority.
- HALT and return upstream if the final source contract cannot preserve Codex's stricter protected
  dispatch acknowledgement semantics.
- HALT if a second runtime can exceed capacity, present a stale fence, or generate a different
  settlement identity for the same logical unit.
- HALT on failed isolated install, fresh-session readback, rollback, unit/cutover validation, or full
  repository gates.

### Acceptance criteria

- [ ] Claude and Codex adapters resolve the same safe runtime-neutral fleet root and root-identity
  digest from the same environment; `~/.claude`, `~/.codex`, `PLUGIN_DATA`, unsafe, and divergent
  roots fail before admission. Check: focused fleet-core root-resolution tests.
- [ ] Each runtime reads the other's `fleet_lease_registry.v1`, and acquire/renew/release/
  supersession preserves one broker epoch, monotonic fencing head, capacity result, and current/
  expired/closed/superseded classification. Check: cross-runtime broker conformance fixtures.
- [ ] Codex emits and consumes the merged dispatch-settlement identity and chain, while one real
  launch still requires its protected `outcome.dispatch.v2` acknowledgement; synthetic,
  `handed-off`, and legacy records cannot become dispatched. Check: `uv run pytest
  tests/test_dispatch_settlement.py tests/test_outcome_dispatch_migration.py -v`.
- [ ] The resource guard serializes successor grants and protected evidence commits without stale
  writes; crash-gap retries are idempotent and no Claude-specific quarantine/agy behavior is activated.
  Check: focused guard and negative-surface tests.
- [ ] The new port manifest inventories the full frozen source window and Codex preservation drift,
  passes classification/unit/cutover, and binds the exact source target, Codex execution base,
  capability snapshot, plan, review, evidence, version policy, and release artifacts. Check:
  `python3 scripts/port_contract.py validate` at all required stages.
- [ ] Fleet-core and Saga Codex releases, portability notes, marketplace/inventory, installed proof,
  fresh-session readback, rollback, journal, and full quality gates ship in one independent PR.
  Check: `python3 scripts/validate_codex_plugins.py` and full repository suite.

### Verification

```bash
python3 scripts/port_contract.py verify-source --manifest <manifest> \
  --source-repo ../infiquetra-claude-plugins
python3 scripts/port_contract.py validate --manifest <manifest> --stage classification
uv run pytest tests/test_fleet_lease_broker.py tests/test_dispatch_settlement.py -v
uv run pytest tests/test_outcome_dispatch_migration.py tests/test_outcome_store.py -v
python3 scripts/port_contract.py validate --manifest <manifest> --stage unit --unit <unit>
python3 scripts/validate_codex_plugins.py
uv run ruff format --check .
uv run ruff check .
uv run mypy plugins/ scripts/ tests/ --ignore-missing-imports
uv run bandit -r plugins/
uv run pytest
python3 scripts/port_contract.py validate --manifest <manifest> --stage cutover
```

### Notes / conventions

- Native parent: infiquetra/infiquetra-claude-plugins#579 (cross-repo sub-issue link).
- Hard prerequisites: merged #351, #355, and #356. This issue can run in parallel with the Claude
  cross-runtime compatibility child after those prerequisites settle.
- The port runbook is mandatory. Initialize a fresh manifest from the latest imported Claude source
  through the exact prerequisite target, include exhaustive Codex preservation drift, and stop on
  dirty overlap or execution-base movement.
- Create an isolated Codex issue worktree from fresh `origin/main`; the current main checkout has
  pre-existing unrelated dirt that must remain untouched.
- Handoff maturity: requirements-ready. Run `saga:plan`, `saga:doc-review`, approved Verified
  Workflow execution, and `saga:code-review` before merging.
- Add the issue explicitly to Operations with Status `Shaping` and Objective
  `improve-claude-plugins`; creation remains WIP-gated or requires the operator's explicit override.
