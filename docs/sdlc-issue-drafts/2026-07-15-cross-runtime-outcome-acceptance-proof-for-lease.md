---
title: Cross-runtime Outcome acceptance proof for lease-safe continuity
repo: infiquetra-claude-plugins
type: capability
team: asgard
project: operations
status: Shaping
labels: capability, hermes-task, needs-plan
risk: high
handoff_maturity: requirements-ready
approval_state: approved
---

# Cross-runtime Outcome acceptance proof for lease-safe continuity

### Objective

Produce the independent cross-runtime acceptance proof that closes #579 and the
`lease-safe-runtime-continuity` outcome only when released Claude and Codex implementations preserve
one authority and one dispatch.

### Intent

Build and run a revision-pinned acceptance harness against the merged Claude and Codex Saga releases.
The harness exercises same-clone discovery, both handoff directions, different-clone reconstruction,
concurrent advance, runtime-local authority rejection, compatibility skew, and leak/doctor closure.
It records a durable machine-readable evidence bundle containing both repository SHAs and plugin
versions. Same-clone tests share one temporary target repository's git-common-dir and one explicitly
selected runtime-neutral fleet-state root; different-clone tests share neither. This issue verifies
the two implementations; it does not silently repair either one.

### Out-of-scope / non-goals

- Implementing missing Claude or Codex runtime behavior inside the acceptance PR.
- Treating copied local caches, transcripts, rollout history, or launch receipts as test fixtures for
  canonical state.
- Waiving a failed concurrency, freshness, compatibility, settlement, teardown, or fleet-doctor check.
- Claiming exactly-once delivery; the proof is at-most-one dispatch side effect under the shared
  at-least-once/idempotent contract.
- Deploying to production or changing credentials, GitHub authority, or Operations workflow schema.

### Files expected to change

- `tests/test_outcome_cross_runtime.py` (new)
- `tests/fixtures/cross-runtime-outcome/` (new)
- `tools/run_cross_runtime_outcome_acceptance.py` (new)
- `docs/validation/lease-safe-runtime-continuity/cross-runtime-acceptance.json` (generated evidence)
- `docs/validation/lease-safe-runtime-continuity/README.md` (evidence interpretation and rerun steps)
- `docs/outcomes/lease-safe-runtime-continuity/report.md`
- `docs/engineering-journal/LEARNINGS.md` or `DECISIONS.md` only when the run produces a durable
  learning or changes the acceptance contract.

### Tests to add or update

- Claude-to-Codex and Codex-to-Claude discovery of canonical completion and candidate-frontier state;
  cross-clone transient lease/handoff/launch state remains explicitly unknown.
- Same-clone shared coordination and different-clone reconstruction.
- Concurrent two-process advance with a deterministic barrier, proven overlap, one write-once backend
  side effect, one shared settlement identity, and Codex's protected launch acknowledgement chain.
- Runtime-local canonical-state rejection.
- Stale/wrong-repository/forged receipt rejection.
- Compatibility-version skew HALT with no mutation.
- Both bounded same-clone handoff directions plus exact-operation/subplot, replay, copied-reference,
  cross-clone, TTL, future-skew, and forgery rejection.
- Legacy `outcome-bundle/1` import rejection with no state replay or write.
- Teardown plus fleet-doctor proof of zero open worktrees, leases, dispatch positions, or receiptless
  delegations.
- Evidence-bundle schema and exact revision/version binding.

### Context library links

_none_

### Inputs inventory

- Parent requirements and acceptance selectors from infiquetra/infiquetra-claude-plugins#579.
- Outcome specification:
  `docs/outcomes/lease-safe-runtime-continuity/outcome-spec.json`, node
  `cross-runtime-acceptance`.
- Exact merged Claude compatibility, Codex shared-substrate, and Codex protocol-parity PR SHAs, Saga
  versions, compatibility schema digest, port-manifest digests, and runtime-neutral broker-root digest.
- Completed #353 fleet-doctor command/report contract and its prerequisites #351/#355/#357/#358.
- Isolated same-clone and separate-clone Git fixtures plus deterministic GitHub evidence fixtures.
- The two repositories' documented quality commands and release metadata.

### Failure modes / pre-mortem

- The harness imports a local cache/receipt and accidentally proves state sharing the contract forbids.
- Concurrency tests serialize by accident and never race the dispatch boundary.
- A passing result is bound to working-tree code rather than the claimed merged SHAs/versions.
- The test asserts equal transient node state across independent clones instead of comparing only
  canonical completion and candidate-frontier projection, manufacturing false parity.
- Teardown passes while the settlement ledger, lease store, worktree registry, or doctor still reports
  an open position.

### Stop conditions

- HALT if either runtime child is unmerged, version-unpinned, or fails its own full quality gate.
- HALT if the harness cannot prove actual concurrent overlap at the dispatch boundary.
- HALT on any duplicate side effect, authority mismatch, stale/forged receipt acceptance, or
  compatibility degrade.
- HALT if evidence cannot bind exact repository SHAs, plugin versions, commands, and artifact digests.
- HALT and file/reopen an owning-runtime defect rather than fixing production behavior in the
  acceptance PR.

### Acceptance criteria

- [ ] A Claude-created Outcome is discovered and read by the pinned Codex release from the same clone
  without copying runtime-local state. Check: `uv run pytest
  tests/test_outcome_cross_runtime.py -k claude_to_codex_discovery`.
- [ ] A Codex-created Outcome is discovered and read by the pinned Claude release with equivalent
  canonical completion and candidate-frontier state; transient state is unknown outside the creating
  clone. Check: `uv run pytest
  tests/test_outcome_cross_runtime.py -k codex_to_claude_discovery`.
- [ ] Concurrent Claude and Codex advance attempts against one ready leaf yield one dispatch side
  effect in a write-once fake backend, one shared settlement unit, one valid Codex
  `outcome.dispatch.v2` acknowledgement chain when Codex launches, and an audit proving real process
  overlap. Check: `uv run pytest
  tests/test_outcome_cross_runtime.py -k concurrent_advance_single_dispatch`.
- [ ] A second isolated clone reconstructs equivalent status from the committed Outcome spec plus
  GitHub fixtures without importing the first clone's coordination cache. Check: `uv run pytest
  tests/test_outcome_cross_runtime.py -k cross_clone_reconstruction`.
- [ ] Runtime-local paths are rejected as canonical, while local protected launch receipts retain
  their explicit identity/freshness reconciliation boundary. Check: `uv run pytest
  tests/test_outcome_cross_runtime.py -k runtime_local_not_canonical`.
- [ ] Each runtime can offer and accept a protected same-clone handoff for exactly one operation and
  subplot; copied, cross-clone, broad, replayed, forged, older-than-300-second, or more-than-30-second
  future-skewed references fail before mutation. Check: `uv run pytest
  tests/test_outcome_cross_runtime.py -k 'handoff_both_directions or handoff_rejected'`.
- [ ] Both runtimes reject legacy `outcome-bundle/1` imports before any spec, receipt, fact, lease,
  board, or GitHub mutation. Check: `uv run pytest
  tests/test_outcome_cross_runtime.py -k legacy_bundle_import_rejected`.
- [ ] Compatibility or Outcome schema skew HALTs both directions without a board, GitHub, spec, or
  coordination-store mutation. Check: `uv run pytest
  tests/test_outcome_cross_runtime.py -k version_skew_halts`.
- [ ] Final teardown and #353 fleet-doctor inspection report zero open worktrees, leases, dispatch
  positions, receiptless delegations, and dead wiring for the fixture. Check: `uv run pytest
  tests/test_outcome_cross_runtime.py -k teardown_and_doctor_clean`.
- [ ] The durable evidence bundle binds exact Claude/Codex SHAs, Saga versions, test commands, verdicts,
  and artifact digests and validates against its closed schema. Check: `uv run pytest
  tests/test_outcome_cross_runtime.py -k evidence_bundle`.

### Verification

```bash
uv run pytest tests/test_outcome_cross_runtime.py -v
uv run python tools/run_cross_runtime_outcome_acceptance.py \
  --claude-repo . \
  --codex-repo ../infiquetra-codex-plugins \
  --output docs/validation/lease-safe-runtime-continuity/cross-runtime-acceptance.json
uv run pytest
uv run ruff format --check .
uv run ruff check .
uv run mypy plugins/ scripts/ tests/ --ignore-missing-imports
uv run bandit -r plugins/
```

### Notes / conventions

- Native parent: #579 in `infiquetra-claude-plugins`.
- Hard prerequisites: merged Claude compatibility child, merged Codex shared-substrate child, merged
  Codex protocol-parity child, and completed #353 fleet doctor.
  #353 already depends on #351, #355, #357, and #358, so the acceptance issue does not duplicate those
  edges.
- A failing acceptance result reopens or creates a defect against the owning runtime; it never patches
  production behavior in this proof PR or closes #579 with a waiver.
- The protected handoff reference is exercised only inside the shared temporary clone. It is never
  copied into the different-clone fixture. The broker state root is explicitly selected from
  `INFIQUETRA_FLEET_STATE_DIR` (or the documented XDG/default resolution) and both runtimes must report
  the same redacted canonical-root digest before admission.
- Handoff maturity: requirements-ready. Run `saga:plan`, `saga:doc-review`, approved Verified
  Workflow execution, `saga:code-review`, and `saga:qa` before closing.
- The prepared Operations profile requires Status `Shaping` and Objective
  `improve-claude-plugins`. Do not create the issue while Shaping exceeds WIP without either cleared
  capacity or an explicit operator override.

### Handoff maturity
requirements-ready

### Suggested next action
Use `/plan <issue>` to create an implementation plan.

### Source context
- Source: docs/outcomes/lease-safe-runtime-continuity/issue-sources/cross-runtime-acceptance.md
- Source type: local-file
- Source title: cross-runtime-acceptance

### Recommended Tier Band
opus/high

## Created Issue

- URL: https://github.com/infiquetra/infiquetra-claude-plugins/issues/605
- Number: 605
- Created at: 2026-07-15T10:51:01.679814+00:00

