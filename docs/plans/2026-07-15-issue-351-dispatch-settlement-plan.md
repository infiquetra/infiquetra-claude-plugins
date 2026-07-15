---
title: Lease-safe runtime continuity wave 1 - dispatch settlement
type: feat
status: active
date: 2026-07-15
origin: https://github.com/infiquetra/infiquetra-claude-plugins/issues/351
---

# Lease-safe runtime continuity wave 1 - dispatch settlement

## Summary

Implement issue #351 as the second independent leaf of outcome `lease-safe-runtime-continuity`.
Add a single dispatch-settlement contract for outcome, team-execution, and generated-workflow
fan-outs: expected units are recorded before spawn; every committed spawn attempt and terminal
settlement is appended to the canonical hash-chained run-fact ledger; a reconciler classifies missing delivery from
durable evidence; casualty thresholds halt partial gates; and a derive-on-read dead-letter view drives
bounded at-least-once retry. Ship Saga and team-execution release surfaces in the same PR.

Destination is merge. Execution uses an approved Verified Workflow. Root owns implementation, Git,
integration, PR, merge, issue closure, and board reconciliation. Agent-lens roles independently review
or validate and do not mutate the repository.

## Current State and Corrected Assumptions

- `plugins/saga/scripts/run_ledger.py` is already the one canonical, hash-chained, git-common-dir
  run-fact ledger. Its module contract names #351 as a future wave-1 writer and explicitly prohibits
  parallel telemetry ledgers. `append_fact_atomic` can validate a state transition under the same
  exclusive lock used for append.
- `run_ledger`'s existing `kind=reconciliation` means external-engine finding adjudication. Dispatch
  accounting must use a distinct fact kind so those records cannot be confused.
- `plugins/saga/scripts/outcome_dispatcher.py` is the outcome dispatch seam;
  `outcome_worktrees.py` remains the worktree registry/reaper and supplies a read adapter for leak
  projection. It is not replaced or generalized into another store.
- Team-execution workers already write `saga.manifest.v1` at segment/unit exit. Contract-bearing
  manifests carry `output_completeness`; absence is already defined as `missing-output`.
- The issue's `artifact-pointer ACK` assumption is stale. `artifact_pointer.py snapshot` captures a
  Git tree snapshot for reviewer/validator diff transfer after workers complete. It neither identifies
  a worker delivery nor acknowledges one. The existing worker-exit manifest is the correct evidence
  boundary. The acceptance test keeps its published selector
  `no_ack_lands_in_dlq_after_bounded_retries`, but “ACK” means a valid expected worker-exit manifest,
  never an artifact pointer.
- Generated Claude workflow leaves have no filesystem access. Settlement for that lane must be
  driver-materialized from emitted expected-unit metadata and collected structured results, matching
  the existing driver-materialized manifest precedent; emitted agents cannot write the ledger.

## Requirements

- **R1. One schema on one ledger.** Extend `run_fact.v1` with kind `dispatch-settlement`. A dispatch
  appends one `event=manifest` fact before launch and one `event=spawn` fact immediately before each
  unit is committed to the host runtime. Collection appends one terminal `event=settle` fact per
  attempted unit. A crash or failed tool call after spawn is therefore an open position or casualty,
  not an invisible non-event. No sidecar manifest, queue file, status cache, or second ledger.
- **R2. Stable identity and transitions.** A unit attempt is keyed by
  `(dispatch_id, unit_id, attempt)`. The manifest carries `site`, expected unit IDs and deliverable
  contracts, `casualty_threshold_percent`, and `max_attempts`. Spawn carries the stable idempotency
  key. Settle carries classification and evidence digest/reference. A digest-bound
  `event=late-delivery` may follow a non-delivered settle for the same attempt; it never rewrites the
  terminal fact. Under one ledger lock reject duplicate manifests, settle-before-spawn, duplicate
  attempt spawns, duplicate settles/late deliveries, attempt gaps, and idempotency-key drift.
- **R3. Threshold semantics.** `casualty_threshold_percent` is an integer 0..100, default 0 when an
  operator omits it. Compare with integer cross-multiplication and halt only when casualty rate
  strictly exceeds the threshold. Tests use explicit thresholds for permissive partial-progress
  cases. Threshold evaluation occurs per `(dispatch_id, attempt)` cohort after every unit spawned in
  that cohort has a settlement classification; attempt 1's cohort is every manifest unit, while a
  retry cohort contains only units spawned for that attempt.
- **R4. Evidence-derived classification.** Classify each expected unit as:
  `delivered` for a valid expected artifact/manifest with complete required outputs;
  `rate-killed` only for a trusted host/dispatcher `rate_limited` receipt;
  `idle` only for trusted runtime liveness evidence showing a launched but nonterminal idle worker at
  the deadline; `silent-no-op` when spawn is recorded but no recognized delivery or runtime evidence
  exists by the deadline; and `leaked-worktree` in the worktree adapter when an owned live worktree has
  no matching active or terminal attempt. Agent prose claiming success never changes classification.
- **R5. Casualty report and halt.** Produce a deterministic report containing every expected unit,
  classification, attempt, evidence reference, casualty rate, threshold, and `halt_required`. Unknown,
  corrupt, or contradictory evidence halts as an evidence error; it is never guessed into a passing
  class.
- **R6. Derive-on-read DLQ.** The DLQ is the set of latest settled non-delivered attempts whose next
  attempt is below `max_attempts`. It is computed from the verified ledger snapshot, not persisted as
  mutable queue state. A late-delivery fact observed before the next spawn removes that unit from the
  eligible view; a late delivery observed after retry spawn remains evidence of at-least-once delivery
  and does not cancel the in-flight retry. Terminal casualties at the retry cap remain queryable in
  the report but are not automatically dispatched again.
- **R7. At-least-once retry.** The next outcome advance or team-execution fan-out boundary claims each
  eligible DLQ unit by atomically appending its next spawn attempt with the same idempotency key before
  launch. A late first-attempt delivery can therefore coexist with a retry; consumer completeness and
  apply paths must already be idempotent, and settlement reports both attempts instead of pretending
  exactly-once.
- **R8. Read-only leak reconciliation.** `dispatch_settlement.py reconcile --leaks` verifies the
  ledger chain and reports spawn-without-settle positions. With an outcome repo root, it also projects
  stale worktree registry entries as `leaked-worktree` debits without mutating the ledger, registry, or
  filesystem. Reaping remains owned by `outcome_worktrees.py`.
- **R9. Three real fan-out adapters.** Outcome records dispatch and settlement at its production
  dispatcher/harvest boundaries. Team-execution Step B2/B3 records an expected manifest before Agent
  calls, records each spawn immediately before its Agent call, and settles from reviewer/validator
  evidence plus worker manifests. Generated workflows export deterministic expected-unit settlement
  metadata; the root driver records all expected spawns immediately before submitting the workflow
  and settles them from trusted host receipts plus collected structured results. Every adapter uses
  the same core functions and classifications.
- **R10. Compatibility and release integrity.** Do not change concurrency limits, retry HTTP calls,
  worktree reaping, review-cycle bounds, or gate authority. Update Saga and team-execution versions,
  marketplace, both changelogs, drift guards, operator docs, tests, and engineering-journal decisions
  in the same PR.

## Data Contract

Every fact uses `schema=run_fact.v1`, `kind=dispatch-settlement`, the producing `subplot_id`, and an
ISO `at` supplied by the caller. The kind-specific event shapes are closed:

| event | required fields | invariant |
|---|---|---|
| `manifest` | `dispatch_id`, `site`, `units`, `casualty_threshold_percent`, `max_attempts` | one per dispatch; written before any spawn |
| `spawn` | `dispatch_id`, `unit_id`, `attempt`, `idempotency_key` | written immediately before runtime submission |
| `settle` | `dispatch_id`, `unit_id`, `attempt`, `classification`, `reason` | one terminal record per spawned attempt; evidence fields are classification-dependent |
| `late-delivery` | `dispatch_id`, `unit_id`, `attempt`, `evidence_ref`, `evidence_sha256` | only after a non-delivered settle; never rewrites it |

`site` is one of `outcome`, `team-execution`, or `workflow`. Each manifest unit contains one non-empty
`unit_id`, a non-empty stable `idempotency_key`, and a list of expected deliverable identifiers; IDs
are unique within the manifest. `attempt` starts at 1. `max_attempts` is 1..3 and defaults to 3.
`casualty_threshold_percent` is 0..100 and defaults to 0. Evidence references are bounded identifiers,
not raw output. Delivered, rate-killed, and idle settlements require a digest-bound trusted evidence
reference; silent-no-op has no evidence and records the normalized reason. A late delivery also
requires digest-bound artifact evidence. `leaked-worktree` is a read-only report projection, not
fabricated ledger history.

Here, `spawn` means the coordinator durably committed the attempt immediately before submitting it to
the runtime; it does not claim that a process started. This definition is what makes a crash between
the ledger append and host acknowledgment detectable as `silent-no-op` rather than invisible.

## Traceability and Dependencies

- The issue's first casualty-report AC maps to R1/R4/R5; threshold HALT to R3/R5; self-report
  rejection to R4; three-spawn/two-settle and stale-worktree checks to R8; bounded no-ACK retry and
  idempotent re-dispatch to R4/R6/R7; the full quality gate maps to R10.
- The parent context is the approved
  `docs/outcomes/lease-safe-runtime-continuity/outcome-spec.json` revision 3; issue #351's published
  ACs remain the implementation authority. The operator approved the exact Verified Workflow digest
  recorded below; any digest or role/model/effort change reopens the gate.
- The canonical run-fact ledger prerequisite (#401) is already merged. #351 has no behavioral
  dependency on #350 and must not add throttling. Both edit Saga release surfaces, so #351 starts from
  refreshed `main` after #350 merges; this is a Git/release collision barrier, not a schema dependency.
  Merged #351 unblocks #357, #358, #353, and the Claude-side #579 work in the outcome draft.
- The three adapters are one atomic contract rather than independent features: landing only the core
  or one adapter would leave the issue's falsely-green fan-out failure in production. Units U1-U6
  receive separate commits/checkpoints where useful but close through one issue PR.
- No external service, credential, deployment environment, or named human reviewer is required.

## Key Technical Decisions

- **KTD1 - facts are the manifest.** The `manifest`, `spawn`, and `settle` run facts are the dispatch
  manifest and double-entry record. A second JSON file would violate run-ledger #401's one-format
  decision and create atomicity gaps.
- **KTD2 - a new fact kind, not overloaded reconciliation.** `dispatch-settlement` is distinct from
  external-engine finding reconciliation. Its event vocabulary is closed and validated in a new
  focused module.
- **KTD3 - DLQ is a view.** Eligible retries are derived from the verified append-only stream. This
  preserves derive-on-read truth, makes crash replay deterministic, and removes mutable queue repair.
- **KTD4 - worker manifests are delivery evidence.** A valid `saga.manifest.v1` with expected
  `output_completeness` is the team-execution ACK. Artifact pointers remain diff-transfer snapshots and
  receive no behavioral change.
- **KTD5 - site adapters, shared classifier.** Site code only converts trusted host artifacts into a
  normalized evidence input. Classification, thresholding, transition validation, and DLQ derivation
  stay centralized.
- **KTD6 - conservative default.** An omitted casualty threshold means 0 percent, so any casualty
  halts. Permissive partial operation is an explicit operator choice on that dispatch.
- **KTD7 - stale worktrees are projected, not copied.** A read-only reconcile command may identify a
  registry/on-disk mismatch as an unsettled debit, but it must not append synthetic historical facts
  or reap resources while answering a query.
- **KTD8 - workflow evidence is driver-materialized.** Workflow agents cannot touch the filesystem.
  The generated artifact exports expected-unit metadata; the trusted root driver binds host dispatch
  handles and returned structured results into the ledger.

These decisions are recorded under `{#dispatch-settlement-351}` in
`docs/engineering-journal/DECISIONS.md` before implementation starts.

## Implementation Units

### U1. Dispatch-settlement schema and atomic transitions

Add the fact kind and a focused module containing manifest/unit dataclasses, validation, fact builders,
and lock-consistent transition guards over `run_ledger.append_fact_atomic`. Keep raw agent output and
unbounded rationale out of facts; store identifiers, result digests, trusted receipt type, and bounded
references only.

**Files:** `plugins/saga/scripts/run_ledger.py`,
`plugins/saga/scripts/dispatch_settlement.py` (new), `tests/test_dispatch_settlement.py` (new),
`tests/test_run_ledger.py`.

**Tests:** valid manifest/spawn/settle/late-delivery, duplicate/gapped transition rejection,
idempotency-key drift, broken-chain refusal, 0600 writer-created files, and read paths create no files.

### U2. Classification, report, threshold, and DLQ

Implement normalized evidence adapters, closed classification, complete casualty reports,
cross-multiplied threshold evaluation, verified-snapshot leak diff, derived DLQ, and bounded retry
claiming.

**Files:** `plugins/saga/scripts/dispatch_settlement.py`, `tests/test_dispatch_settlement.py`.

**Tests:** `casualty_report_names_both`, `casualty_rate_halts`,
`settlement_ignores_self_report`, `three_spawn_two_reap_one_open`,
`no_ack_lands_in_dlq_after_bounded_retries`, `dlq_redispatch_is_idempotent`, plus unknown evidence,
late delivery before/after retry claim, retry cap, and threshold boundary.

**Depends on:** U1.

### U3. Outcome dispatch, advance, harvest, and worktree adapter

Inject an explicit ledger/clock seam at the production outcome dispatch boundary. Append the manifest
before launching, append spawn immediately before the dispatcher call, settle from durable completion or
trusted rate-limit/liveness receipts, and consult eligible retries before the normal ready frontier.
Expose worktree registry state through a read-only adapter; do not change reaping.

**Files:** `plugins/saga/scripts/outcome_dispatcher.py`,
`plugins/saga/scripts/outcome.py`, `plugins/saga/scripts/outcome_orchestrator.py`,
`plugins/saga/scripts/outcome_worktrees.py`, `tests/test_outcome_dispatcher.py`,
`tests/test_outcome_orchestrator.py`, `tests/test_dispatch_settlement.py`.

**Tests:** manifest precedes spawn, spawn precedes dispatch, a failed dispatch remains an open or
casualty-classified attempt, completion/rate-limit settle, retry precedes new frontier work, same
idempotency key across attempts, and `stale_worktrees_flagged_as_debit` without read-side mutation.

**Depends on:** U2.

### U4. Team-execution adapter and operator protocol

Add CLI examples and mandatory sequence to Step B2/B3 and consensus/validator references: manifest,
pre-call spawn, collection settlement from validated evidence, threshold gate, and derived retries at
the next fan-out boundary. Adapt existing worker manifests for contract-bearing worker delivery.
Do not modify `artifact_pointer.py` except an optional clarifying cross-reference if tests show docs
remain ambiguous.

**Files:** `plugins/team-execution/skills/team-execution/SKILL.md`,
`plugins/team-execution/skills/team-execution/references/consensus-protocol.md`,
`plugins/team-execution/skills/team-execution/references/validator-evidence-state.md`,
`plugins/team-execution/skills/team-execution/references/worker-manifest.md`,
`tests/test_team_execution_plugin.py`, `tests/test_dispatch_settlement.py`.

**Tests:** protocol snippets invoke the canonical CLI, missing manifest becomes silent-no-op despite
success prose, incomplete required output is not delivered, every configured reviewer/validator is in
the expected manifest, and artifact-pointer presence alone cannot satisfy delivery.

**Depends on:** U2.

### U5. Generated-workflow driver settlement

Emit a deterministic settlement metadata export from `ExecutionSpec` containing dispatch identity,
units, and expected result contracts. Update the workflow launch/collection protocol to materialize
manifest/spawn/settle facts from that metadata, trusted host handles, and structured results. Preserve
workflow agents' no-filesystem boundary.

**Files:** `plugins/saga/scripts/execution_spec.py`,
`plugins/saga/skills/work/SKILL.md` (Phase 1.5 launch and post-run manifest persistence),
`tests/test_saga_execution_spec.py`, `tests/test_dispatch_settlement.py`.

**Tests:** metadata contains every fan-out unit exactly once, a missing returned result settles as a
casualty, self-report cannot replace a structured result, and emitted agents receive no ledger-write
permission.

**Depends on:** U2.

### U6. CLI, release surfaces, and full gate

Expose JSON and human-readable `report`, `dlq`, and `reconcile --leaks` reads plus explicit writer
verbs used by the adapters. From the required post-#350 baseline, bump Saga 0.97.0 to 0.98.0 and
team-execution 2.16.0 to 2.17.0 (new backward-compatible capabilities, matching both plugins' current
minor cadence). Re-read the live baseline immediately before editing; if another merge advanced a
version, use the next minor rather than reusing a released version. Update marketplace, changelogs,
journal, docs, and metadata guards.

**Files:** `plugins/saga/scripts/dispatch_settlement.py`,
`plugins/saga/.claude-plugin/plugin.json`, `plugins/team-execution/.claude-plugin/plugin.json`,
`.claude-plugin/marketplace.json`, both plugin `CHANGELOG.md` files,
`docs/engineering-journal/DECISIONS.md`, `tests/test_saga_plugin.py`, and
`tests/test_team_execution_plugin.py` (both pin current version literals).

**Depends on:** U3, U4, U5.

## Requirement Coverage

| Requirement | Implementation | Primary evidence |
|---|---|---|
| R1, R2 | U1 | schema and atomic transition tests |
| R3 | U2 | threshold boundary and casualty HALT tests |
| R4, R5 | U2, U3-U5 | classifier, report, and adapter evidence tests |
| R6, R7 | U2, U3-U5 | derived DLQ, late-delivery, retry-cap, and idempotency tests |
| R8 | U2, U3, U6 | three-spawn/two-settle and stale-worktree read-only checks |
| R9 | U3, U4, U5 | outcome, team-execution, and workflow adapter suites |
| R10 | U6 | full quality gate and both plugins' release parity |

## Verification

Run in order; any failure blocks integration:

```bash
uv run pytest tests/test_dispatch_settlement.py -v
uv run pytest tests/test_outcome_dispatcher.py tests/test_outcome_orchestrator.py -v
uv run pytest tests/test_saga_execution_spec.py tests/test_team_execution_plugin.py -v
uv run ruff format --check .
uv run ruff check .
uv run mypy plugins/ scripts/ tests/ --ignore-missing-imports
uv run pytest
uv run python scripts/check_release_surface_parity.py
uv run python scripts/sync_marketplace.py --check
uv run python tools/release_surface_diff_guard.py --base-ref origin/main
```

Acceptance selectors from the issue must remain green exactly as published. Also run the CLI against
an isolated fixture ledger and an isolated fixture outcome worktree registry; never use a developer's
live ledger as a mutable test target.

## Failure Modes and Stop Conditions

- A second ledger, manifest file, or mutable queue is introduced: stop and consolidate on
  `run_ledger` before wiring consumers.
- A transition check reads and appends under different locks, or a read command creates/heals files:
  stop; the concurrency and evidence contract is broken.
- Classification depends on agent prose, output text heuristics, wall-clock guessing, or an artifact
  pointer: stop and add a trusted evidence adapter.
- Outcome or workflow wiring cannot prove manifest-before-launch: stop; do not claim coverage from a
  post-hoc report.
- Retry changes consumer state without a stable idempotency key or attempts exactly-once semantics:
  stop and restore at-least-once behavior.
- Worktree reconciliation mutates or reaps during a read: stop and restore projection-only behavior.
- Any P0-P3 document-review or code-review finding remains unresolved, a required validator lacks
  gate-capable evidence, or release metadata drifts: no PR/merge.

## Workflow Structure

| step_id | depends_on | barrier | role_id | role_kind | independence | execution_class | runtime_agent_name | vehicle | mutation | required_evidence | role_lens_sha256 | profile_sha256 | expected_model | expected_effort | validator_required | validator_disabled | deterministic_contract_sha256 |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| implement | - | - | root | root | n/a | - | - | root | root-only | authorized-diff,focused-tests | - | - | - | - | n/a | n/a | - |
| review-devils | implement | review | devils-advocate-reviewer | agent-lens | preferred | review-high | review_high | auto | none | scored-review,findings | 129f6dca0702ffcd4be7f9e5d0939e8e6806788846ba4058044c931883ef0e63 | 42e86e00e054281b0a79e4b3b9b544c04a31eb2fd6b53c0489adc42ea639c9a8 | gpt-5.6-sol | high | n/a | n/a | - |
| review-security | implement | review | security-reviewer | agent-lens | preferred | review-high | review_high | auto | none | scored-review,findings | bf5bc1b66c0ee3d06071976b659c522c23057c56de5f6cc010556b2653c86980 | 42e86e00e054281b0a79e4b3b9b544c04a31eb2fd6b53c0489adc42ea639c9a8 | gpt-5.6-sol | high | n/a | n/a | - |
| review-architecture | implement | review | architecture-reviewer | agent-lens | preferred | review-high | review_high | auto | none | scored-review,findings | e48b37cea0b26bf39cae4d6611b4219e907d52d284ba6b9489b523a4b16c835f | 42e86e00e054281b0a79e4b3b9b544c04a31eb2fd6b53c0489adc42ea639c9a8 | gpt-5.6-sol | high | n/a | n/a | - |
| review-testing | implement | review | testing-reviewer | agent-lens | preferred | review-high | review_high | auto | none | scored-review,test-gaps | a867575e24c86b0573485d1d8bbd81514af3654d544342677b85f4bed0d9af63 | 42e86e00e054281b0a79e4b3b9b544c04a31eb2fd6b53c0489adc42ea639c9a8 | gpt-5.6-sol | high | n/a | n/a | - |
| validate-concurrency | implement | validate | concurrency-tester | agent-lens | preferred | test-medium | test_medium | auto | none | tester-evidence,command-results | d40188645b7876e32ea592dd9799ee2ad7a2e230d82341611708dd492837b3da | 6d69bb4d5e477574ce186a353a3d2fcc7f8ab6b1f014b93aebb05084aecccc1b | gpt-5.6-terra | medium | true | false | - |
| validate-event-flow | implement | validate | event-flow-tester | agent-lens | preferred | test-medium | test_medium | auto | none | tester-evidence,command-results | 2e20ab6935b1e17e363b5e28308a9288107532d0118a6a189f07b0e0eaaff356 | 6d69bb4d5e477574ce186a353a3d2fcc7f8ab6b1f014b93aebb05084aecccc1b | gpt-5.6-terra | medium | true | false | - |
| integrate | review-devils,review-security,review-architecture,review-testing,validate-concurrency,validate-event-flow | - | root | root | n/a | - | - | root | root-only | fixed-findings,full-gate,release-parity,git-receipt | - | - | - | - | n/a | n/a | - |

## Workflow Operating Contract

- The authorized subject is this issue's implementation paths plus exact release surfaces. Root
  records the pre-existing Git baseline before `implement`; unrelated paths are excluded.
- Agent-lens rows authorize `mutation=none` and no external mutation. Current MultiAgent V2 may
  reapply the parent's permission profile, so the named profile is not claimed as an OS-enforced
  read-only sandbox. Root records a baseline, audits the worktree after every attempt, and treats any
  child-created diff as workflow-integrity failure. Root runs commands; both required testers
  independently evaluate the persisted command evidence. The concurrency tester covers
  locking/idempotency/retry races; the event-flow tester covers manifest/event/DLQ transitions. The
  installed registry currently offers no deterministic-validator role, so none is invented.
- `vehicle=auto` requests the pinned named profiles. If the host cannot produce gate-capable
  named-profile attestation, the role runs inline in a fresh bounded context; missing required
  independence or validator evidence blocks rather than being waived.
- Root fixes every P0-P3 finding and creates a fresh follow-up attempt for affected roles. Three
  unsuccessful remediation cycles halt and page the operator. A model/class change requires approval
  of a new workflow candidate.
- Git mutation, PR, merge, issue/board mutation, and completion are root-only. No deployment,
  credential, production-data, force-push, or branch-deletion action is authorized.
- Retain workflow intents, receipts, findings, command evidence, workspace audits, PR URL, merge SHA,
  issue closure, and board reconciliation in protected workflow state plus the issue/PR record.

## Completion Gate

Completion requires all published acceptance selectors plus added transition tests, zero open P0-P3
doc/code review findings, both required validators passing with gate-capable evidence, full verification
green, one atomic issue PR merged, issue #351 closed, its Operations card reconciled, the outcome node
receipt recorded, and the outcome worktree clean except for the next planned wave.
