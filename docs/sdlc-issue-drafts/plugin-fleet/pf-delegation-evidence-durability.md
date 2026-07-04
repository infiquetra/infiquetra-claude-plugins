---
title: "enhancement: delegation evidence survives teardown — durable audit store, write-once draft snapshots, /delegation-audit query"
repo: infiquetra-claude-plugins
type: enhancement
team: campps
project: operations
status: Idea
labels: enhancement, hermes-task, needs-plan
risk: medium
handoff_maturity: requirements-ready
tier: structural
wave: wave-2
objective: "Build the fleet telemetry and ledger substrate"
type: enhancement
---

# enhancement: delegation evidence survives teardown — durable audit store, write-once draft snapshots, /delegation-audit query

### Objective

Build the fleet telemetry and ledger substrate

### Tier

structural

### Wave

wave-2

### Problem / motivation (grounded)

Delegation evidence today lives entirely inside disposable, reclaimable storage, and the
fleet has no query surface that reconciles what a delegation *claimed* against what actually
ran:

- `plugins/agy/scripts/agy_delegate.py:279` (`create_validation_bundle`) and the parallel
  supervised-bundle path write every run's `envelope.json` / `command.json` / `run-lease.json`
  / `result.json` / `projection.md` to
  `bundle_path = repo_root / ".claude" / "agy" / "runs" / <run_id>` — a path inside the
  working repo tree, not a store exempt from worktree teardown. When the delegation runs from
  a disposable saga worktree (the fleet's default isolation posture), the entire bundle
  including the receipt is removed the moment the worktree is reclaimed, so the run's proof-
  of-execution does not outlive the workspace that produced it.
- The chaperone-dispatch model (`plugins/team-execution/skills/team-execution/references/
  worker-manifest.md:80-83`) has the chaperone read an external engine's raw returned
  evidence, adjudicate it, and apply a fixed version to the working tree — but nothing
  persists the engine's *raw pre-fix draft* anywhere. Once the chaperone applies its fix, the
  only artifact that survives is the fixed file; there is no immutable corpus letting anyone
  later measure how much the chaperone actually changed (the "fix-delta"), which blocks any
  future engine-quality measurement work.
- There is no session-wide reconciliation query anywhere in the fleet. `docs/engineering-
  journal/LEARNINGS.md` (§6.1, cross-referenced in `docs/plans/2026-07-03-plugin-fleet-
  grounding-brief.md:101`) records 5+ learnings of silent no-ops in delegation — agy falling
  back to Claude without saying so, dead producer/consumer wiring, test shapes masking dead
  wiring, fake-adapter mismatches — and the grounding brief names this cluster explicitly as
  theme 15 ("delegation integrity"): "any bridge/delegation idea needs a 'did it actually
  run/persist' verification." Today answering that question requires manually opening
  per-run bundles one at a time; nothing aggregates receipts against claims across a session.
- Sibling capability `pf-delegation-receipt-contract` (`docs/sdlc-issue-drafts/plugin-fleet/
  pf-delegation-receipt-contract.md`, theme 15 primary) hardens *what* a receipt must contain
  (`bridge_receipt.v1`) and *when* `Disposition.RAN_AS_REQUESTED` may be claimed. This
  enhancement is the durability and query layer underneath it: even a well-formed receipt is
  worthless as evidence if it is deleted with the worktree, and a fleet of well-formed
  receipts is not auditable without a query surface that flags fallbacks as no-ops.

## Definition of Done

Merged PR that:

1. Adds `--audit-store` (default `~/.claude/delegation-audit`) to `agy_delegate.py`, and
   mirrors the equivalent option into `engine_dispatch.py`'s dispatch-manifest write path, so
   every delegation's receipt and provenance manifest is written to a teardown-exempt durable
   store *in addition to* (not instead of) the existing in-bundle copy. The durable copy must
   be resolvable by `run_id` alone, independent of whether the originating bundle directory
   (or its enclosing worktree) still exists.
2. Adds a write-once `.delegation-drafts/` snapshot step in the chaperone-dispatch path
   (`plugins/team-execution/skills/team-execution/references/worker-manifest.md`'s evidence-
   adjudication step) that captures the external engine's raw, pre-fix returned patch/output
   before the chaperone applies any fix, keyed by run_id, and refuses to overwrite an existing
   snapshot for that run_id (write-once).
3. Adds a `/delegation-audit` skill (or CLI subcommand co-located with the audit-store code)
   that reconciles the durable receipt/manifest store against claimed delegations for a
   session or repo, and flags any delegation whose disposition claims real execution
   (`RAN_AS_REQUESTED`) but whose corresponding receipt shows a Claude-fallback or otherwise
   did not actually run the external engine, naming it a no-op.
4. Ships verified by three integration checks (Acceptance criteria), each exercised against a
   real bundle/worktree lifecycle, not mocked in isolation.

### Acceptance criteria
- [ ] Receipt resolves by `run_id` after the working bundle directory is deleted. *(covers
  T15-F3-8)* Check: `uv run pytest tests/test_agy_delegate_contract.py -k
  audit_store_survives_bundle_deletion` → passes, asserting a receipt written under
  `--audit-store` is still readable by `run_id` after `shutil.rmtree` removes
  `repo_root/.claude/agy/runs/<run_id>`.
- [ ] The write-once draft snapshot for a chaperone-dispatched unit, diffed against the
  chaperone's final applied fix, equals the chaperone's own recorded fix-delta. *(covers
  T15-F4-8)* Check: `uv run pytest tests/test_team_execution_chaperone.py -k
  draft_snapshot_matches_fix_delta` → passes, asserting `.delegation-drafts/<run_id>/raw.diff`
  diffed against the working-tree-applied fix produces the same delta the chaperone itself
  records as its fix.
- [ ] `/delegation-audit` run over a session containing one real delegation and one forced-
  fallback delegation flags exactly the forced-fallback entry as a no-op, and does not flag
  the real delegation. *(covers T15-F1-7)* Check: `uv run pytest
  tests/test_delegation_audit.py -k flags_forced_fallback_only` → passes, asserting the audit
  report's flagged set is exactly `{<forced-fallback run_id>}`.
- [ ] Write-once guard rejects a second snapshot write for the same `run_id`. Check: `uv run
  pytest tests/test_delegation_audit.py -k draft_snapshot_write_once_guard` → passes,
  asserting a second write attempt for an existing `.delegation-drafts/<run_id>/` raises
  rather than silently overwriting.
- [ ] Full suite, lint, and types stay green. Check: `uv run pytest && uv run ruff check . &&
  uv run mypy plugins/ scripts/ tests/ --ignore-missing-imports` → all pass.

### Out-of-scope / non-goals
**In scope:**
- `--audit-store` durable-store option on `agy_delegate.py`'s bundle-creation paths, mirrored
  into `engine_dispatch.py`'s manifest write.
- Write-once `.delegation-drafts/` raw-draft snapshot capture in the chaperone-dispatch
  evidence-adjudication step.
- `/delegation-audit` reconciliation skill/command reading the durable store.
- Tests proving durability across bundle/worktree deletion and correct fallback-flagging.

**Non-goals / explicitly out of scope:**
- Defining or hardening the receipt schema itself (`bridge_receipt.v1`, `AdvisoryEvidence`
  gating, `receipt_emitter` registry key) — that is `pf-delegation-receipt-contract`'s scope;
  this capability consumes whatever receipt shape that capability lands and makes it durable
  and queryable, it does not redefine it.
- Any standing/scheduled audit cadence or dashboard — `/delegation-audit` is an on-demand
  query, not a background job.
- Changing chaperone-dispatch's executor model or granting external engines gating authority
  — per `{#external-engine-chaperone-dispatch}` (#318) and `{#external-engines-never-
  gatekeepers}` (#283), external engines remain offload/second-opinion workers only; this
  capability only makes their evidence durable and auditable, it does not change who decides.
- Backfilling durability onto historical runs already reclaimed before this capability ships.
- Building a new bridge or onboarding a third external engine.

## Grounding References

- Absorbed ideas (`docs/plans/plugin-fleet-ideation-2026-07-03/survivors/T15.json`):
  - `T15-F3-8` (primary) — "Relocate delegation evidence out of disposable-worktree blast
    radius." `dod_sketch`: merged PR adds `--audit-store` (default
    `~/.claude/delegation-audit`) to `agy_delegate.py` mirroring receipt+manifest to a
    teardown-exempt durable store; verified by a test that the receipt resolves by run_id
    after the working bundle dir is deleted. Basis: `plugins/agy/scripts/agy_delegate.py:279`
    (`bundle_path` under `repo_root/.claude/agy/runs/<run_id>`).
  - `T15-F4-8` (facet) — "Auto-archived raw delegate drafts as an immutable experiment-
    measurement corpus." `dod_sketch`: PR adds a pre-chaperone write-once
    `.delegation-drafts/` snapshot, verified by diffing the snapshot against the fixed file
    and confirming it equals the chaperone's own recorded fix-delta. Basis: chaperone
    evidence-adjudication step (`plugins/team-execution/skills/team-execution/references/
    worker-manifest.md:80-83`) reads and fixes engine output with no raw-draft retention today.
  - `T15-F1-7` (facet) — "Unified cross-bridge delegation receipt ledger + /delegation-audit
    reconciliation." `dod_sketch`: merged PR adds a `delegation.receipt.v1` append helper in
    the shared saga lib, emit-calls from agy/`engine_dispatch`/verify-spawn, and a
    `/delegation-audit` skill; verified by an integration test running one real and one
    forced-fallback delegation asserting `/delegation-audit` flags exactly the fallback as a
    no-op. Basis: `docs/engineering-journal/LEARNINGS.md` §6.1 silent-no-ops cluster (5+
    learnings), named as theme 15 in `docs/plans/2026-07-03-plugin-fleet-grounding-
    brief.md:101`.
- Consolidation rationale (issue-map): evidence-durability family — relocate receipts/
  manifests out of disposable-worktree blast radius, snapshot raw delegate drafts write-once
  as a measurement corpus, and a session-wide `/delegation-audit` reconciliation query
  (`T15-F1-7`'s distinct kernel) all read from the same durable store; built as row-kinds and
  readers over one wave-2 fleet-ledger substrate rather than three separate stores, hence
  wave-2 (not wave-1 alongside the receipt-contract capability it depends on).
- Binding decisions this capability builds on and must not violate (grounding brief §2):
  - `{#external-engines-never-gatekeepers}` (#283) — Claude stays verifier-of-record; the
    audit store and `/delegation-audit` surface evidence for Claude's own adjudication, they
    do not grant an external engine or the audit tool gating authority.
  - `{#external-engine-chaperone-dispatch}` (#318) — external engines remain offload/second-
    opinion workers, never a second executor kind or git participant; the write-once draft
    snapshot captures *their* raw output for later measurement, it does not change the
    chaperone's write-capable/apply role.
  - `{#readonly-verifier-fallback-ladder-325}` — any verify/review-class subagent spawn this
    capability's tests or tooling introduce must use `saga:readonly-verifier` +
    `isolation: "worktree"` per `plugins/saga/references/sandbox-spawn-sites.md`, with the
    documented fallback ladder if unavailable.
- Depends on (must land first or be co-sequenced): `pf-delegation-receipt-contract` (theme 15
  primary) — this capability's durable store and `/delegation-audit` reconciliation consume
  whatever receipt/manifest shape (`bridge_receipt.v1`, `AdvisoryEvidence.runner_receipt`)
  that capability lands; if it has not merged first, this capability's tests should target
  the receipt shape live in `engine_dispatch.py`/`provenance_manifest.py` at implementation
  time and be updated once the contract capability lands.

### Recommended executor profile

- **Model:** sonnet
- **Effort:** medium
- **Backend:** inline
- **External LLM:** none
- **Justification:** Bounded plumbing change (new storage path, a write-once snapshot step,
  a reconciliation query) against fully-specified `dod_sketch`es with no open design ambiguity
  requiring opus-tier judgment; the one real design choice (audit-store layout/schema) is
  already pinned by the sibling receipt-contract capability's shape once that lands.

### Release-surface checklist (plugin behavior changes — required)

- [ ] `plugins/agy/.claude-plugin/plugin.json` — version bump + description update reflecting
  the new `--audit-store` option.
- [ ] `plugins/saga/.claude-plugin/plugin.json` — version bump reflecting `engine_dispatch.py`
  durable-store mirroring and any new `/delegation-audit` skill surface.
- [ ] `plugins/team-execution/.claude-plugin/plugin.json` — version bump reflecting the new
  write-once `.delegation-drafts/` snapshot step in chaperone dispatch.
- [ ] `.claude-plugin/marketplace.json` — all three plugin entries' version/description kept
  in sync with the bumps above.
- [ ] `plugins/agy/CHANGELOG.md` — entry documenting `--audit-store` and its default location.
- [ ] `plugins/saga/CHANGELOG.md` — entry documenting durable-store mirroring and the
  `/delegation-audit` skill.
- [ ] `plugins/team-execution/CHANGELOG.md` — entry documenting the write-once draft-snapshot
  step and its write-once guard.
- [ ] Version/metadata drift-guard tests (if present in `tests/`) updated or added to assert
  `plugin.json`/`marketplace.json`/`CHANGELOG.md` tell the same story as the diff.

### Files expected to change

Indicative only — exact set is `/plan`'s to determine.

- `plugins/agy/scripts/agy_delegate.py` — `--audit-store` option, durable-store mirror writes
  on bundle creation.
- `plugins/saga/scripts/engine_dispatch.py` — durable-store mirror write alongside existing
  dispatch-manifest write.
- `plugins/saga/scripts/delegation_audit.py` — new reconciliation module (proposed path).
- `plugins/saga/skills/delegation-audit/SKILL.md` — new `/delegation-audit` skill (proposed
  path).
- `plugins/team-execution/skills/team-execution/references/worker-manifest.md` — documents
  the write-once draft-snapshot step in the evidence-adjudication flow.
- `plugins/team-execution/scripts/` (or equivalent) — write-once `.delegation-drafts/`
  snapshot helper (proposed path; exact module TBD by `/plan`).
- `tests/test_agy_delegate_contract.py` — audit-store-survives-bundle-deletion coverage.
- `tests/test_team_execution_chaperone.py` — draft-snapshot-matches-fix-delta coverage.
- `tests/test_delegation_audit.py` — forced-fallback-flagging and write-once-guard coverage.

### Verification

```bash
uv run pytest tests/test_agy_delegate_contract.py -k audit_store_survives_bundle_deletion -v
uv run pytest tests/test_team_execution_chaperone.py -k draft_snapshot_matches_fix_delta -v
uv run pytest tests/test_delegation_audit.py -v
uv run pytest && uv run ruff check . && uv run mypy plugins/ scripts/ tests/ --ignore-missing-imports
```

Expected: all green; the audit-store test passes only when the receipt is read back after the
originating bundle directory has actually been deleted (not merely unread), and the
`/delegation-audit` test's flagged set is exactly the forced-fallback run_id — not empty, not
both run_ids.

### Handoff maturity

requirements-ready

### Suggested next action

Use `/plan <issue>` to create an implementation plan.

### Source context

- Source: `docs/plans/plugin-fleet-ideation-2026-07-03/survivors/T15.json` (ids: `T15-F3-8`
  (primary), `T15-F4-8`, `T15-F1-7` (facets))
- Source type: ideation issue-map
- Source title: Delegation evidence survives teardown: durable audit store, write-once draft
  snapshots, /delegation-audit query

### Context library links

_none_

### Tests to add or update

- `tests/test_agy_delegate_contract.py`
- `tests/test_delegation_audit.py`
- `tests/test_team_execution_chaperone.py`

### Intent

Delegation evidence today lives entirely inside disposable, reclaimable storage, and the fleet has no query surface that reconciles what a delegation *claimed* against what actually ran:

## Created Issue

- URL: https://github.com/infiquetra/infiquetra-claude-plugins/issues/396
- Number: 396
- Created at: 2026-07-04T08:00:25.134746+00:00

