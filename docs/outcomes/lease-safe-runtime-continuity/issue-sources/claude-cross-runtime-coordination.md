### Objective

Deliver the Claude-side authority and compatibility half of the `improve-claude-plugins`
lease-safe runtime continuity outcome without creating a runtime-local source of truth.

### Intent

Ship the Claude Saga contract that lets another conforming runtime discover and attach to an existing
Outcome by repository identity and Outcome ID. The committed Outcome specification and GitHub
completion evidence remain canonical. Same-clone coordination uses the rebuildable git-common-dir
store; cross-clone discovery reconstructs from committed specification plus GitHub. Claude exposes a
versioned compatibility envelope, consumes the shared lease/fencing and dispatch-settlement contracts,
and emits freshness-, operation-, subplot-, and repository-bound handoff references so a Codex
runtime in the same clone cannot duplicate an already reserved or dispatched leaf. A different clone
receives canonical read-only reconstruction only; copied handoff JSON carries no dispatch authority.

### Out-of-scope / non-goals

- Implementing or releasing the Codex-side consumer.
- Making `~/.claude`, `~/.claude-company`, transcripts, caches, or protected launch receipts canonical
  Outcome status.
- Copying git-common-dir coordination caches or mutable receipt stores between clones or hosts.
- Advancing from a different clone or host without a future networked active-dispatch authority.
- Defining another lease, concurrency, settlement, idempotency, or worktree-reaping mechanism beside
  the contracts delivered by #350, #351, #355, and #356.
- Weakening repository identity, receipt freshness, stale-writer fencing, or GitHub completion checks
  to accommodate version skew.

### Files expected to change

- `plugins/saga/scripts/outcome.py`
- `plugins/saga/scripts/outcome_spec.py`
- `plugins/saga/scripts/outcome_store.py`
- `plugins/saga/scripts/outcome_dispatcher.py`
- `plugins/saga/scripts/outcome_compat.py` (new, if the plan confirms a separate module)
- `plugins/saga/skills/outcome/SKILL.md`
- `plugins/saga/references/outcome-cross-runtime.md` (new)
- `tests/test_outcome_cross_runtime_contract.py` (new)
- `plugins/saga/.claude-plugin/plugin.json`
- `plugins/saga/CHANGELOG.md`
- `.claude-plugin/marketplace.json`
- `docs/engineering-journal/DECISIONS.md`

### Tests to add or update

- Runtime-neutral discovery by repository identity and Outcome ID.
- Same-clone git-common-dir attachment without copying runtime-local state.
- Cross-clone reconstruction inputs limited to committed spec plus GitHub evidence.
- Compatibility-envelope version negotiation and fail-closed skew receipts.
- Lease/idempotency binding that rejects a second runtime's duplicate advance.
- Claude-to-Codex handoff receipt identity, freshness, replay, and wrong-repository cases.
- Rejection of legacy bundle import as a portable authority-transfer path.
- Serialization and release-surface drift coverage.

### Context library links

_none_

### Inputs inventory

- Parent requirements: infiquetra/infiquetra-claude-plugins#579.
- Merged shared contracts from #351 (settlement/idempotency), #355 (orphan fencing), and #356 (lease
  authority); the plan must read their final code and decisions rather than assume draft shapes.
- Claude Saga Outcome authority and coordination modules under `plugins/saga/scripts/outcome*.py`.
- Codex Saga's current Outcome schema, protected dispatch acknowledgement, and git-common-dir behavior
  in `infiquetra-codex-plugins` as the downstream compatibility consumer.
- GitHub issues, PRs, and Operations fields as canonical completion/operator evidence.

### Failure modes / pre-mortem

- The compatibility envelope serializes a runtime-local cache path and turns it into accidental
  portable authority.
- A same-clone consumer resolves a different git-common-dir or Outcome ID and creates a second store.
- Handoff evidence omits spec revision, repository identity, or issuance freshness and replays after
  the Outcome changes.
- Claude defines a new lease/idempotency contract that conflicts with the already-merged outcome
  safety substrate.
- A compatibility-skew error occurs after a board, GitHub, spec, or dispatch mutation.

### Stop conditions

- HALT if implementation requires any runtime-local directory or copied coordination cache to become
  canonical Outcome status.
- HALT if the merged #351/#355/#356 contracts cannot be consumed without changing their authority or
  weakening their failure behavior.
- HALT if a duplicate dispatch/completion side effect is possible under two attachment attempts.
- HALT if unsupported schema/version evidence can mutate before compatibility rejection.
- HALT and return to #579 decomposition if the Claude PR must contain Codex repository changes.

### Acceptance criteria

- [ ] Claude emits a closed, versioned compatibility/discovery envelope derived from the committed
  Outcome specification, and a same-clone conforming consumer can locate the existing Outcome by
  repository identity plus Outcome ID. Check: `uv run pytest
  tests/test_outcome_cross_runtime_contract.py -k discovery_envelope`.
- [ ] Discovery never treats a Claude runtime-local path as canonical status and never requires
  copying the git-common-dir cache to another clone. Check: `uv run pytest
  tests/test_outcome_cross_runtime_contract.py -k runtime_local_not_canonical`.
- [ ] A Claude-side handoff binds outcome ID, repository identity, spec revision, compatibility
  version, exact operation, one subplot, dispatch/idempotency identity, broker-derived issuer, and
  bounded freshness; acceptance reloads protected same-clone evidence, while wrong-repo, stale,
  forged, copied, overbroad, or replayed evidence fails closed. Check: `uv run pytest
  tests/test_outcome_cross_runtime_contract.py -k handoff_receipt`.
- [ ] Two Claude-side attachment/advance attempts against one ready leaf consume the shared lease and
  settlement identities and produce at most one dispatch intent/acknowledgement. Check: `uv run pytest
  tests/test_outcome_cross_runtime_contract.py -k single_dispatch`.
- [ ] An unsupported compatibility or Outcome schema version returns an actionable HALT receipt and
  does not mutate the Outcome, store, board, or GitHub. Check: `uv run pytest
  tests/test_outcome_cross_runtime_contract.py -k version_skew_halts`.
- [ ] Cross-clone reconstruction exposes canonical completion and a candidate frontier with
  `mutation_allowed: false`; legacy `outcome-bundle/1` import cannot write a spec or replay transient
  facts. Check: `uv run pytest tests/test_outcome_cross_runtime_contract.py -k
  'cross_clone or legacy_bundle'`.
- [ ] Saga release metadata, marketplace, changelog, journal, and drift guards describe the shipped
  Claude contract in the same PR. Check: release-surface parity and diff-guard tests pass.

### Verification

```bash
uv run pytest tests/test_outcome_cross_runtime_contract.py -v
uv run pytest tests/test_outcome_store.py tests/test_outcome_dispatcher.py tests/test_outcome_command.py -v
uv run ruff format --check .
uv run ruff check .
uv run mypy plugins/ scripts/ tests/ --ignore-missing-imports
uv run bandit -r plugins/
uv run pytest
uv run python scripts/check_release_surface_parity.py
uv run python scripts/sync_marketplace.py --check
uv run python tools/release_surface_diff_guard.py --base-ref origin/main
```

### Notes / conventions

- Native parent: #579 in `infiquetra-claude-plugins`.
- Outcome prerequisites: #351 and #355 complete; #355 already consumes #356's broker/fencing
  contract. The implementation must reuse those merged contracts rather than carry local substitutes.
- Handoff maturity: requirements-ready. Run `saga:plan`, `saga:doc-review`, approved Verified
  Workflow execution, and `saga:code-review` before merging.
- The prepared Operations profile requires Status `Shaping` and Objective
  `improve-claude-plugins`. Do not create the issue while Shaping exceeds WIP without either cleared
  capacity or an explicit operator override.
