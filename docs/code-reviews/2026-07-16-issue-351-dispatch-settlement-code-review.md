# Code Review — Issue #351 Dispatch Settlement

## Verdict

> **PASS.** All 14 findings were repaired and verified. The final P1 false-green path was closed by
> removing caller-selected artifact outputs and deriving reviewer/validator deliverables only after
> Saga validates a closed payload contract.

| Field | Value |
|---|---|
| Target | `issue/351-dispatch-settlement` against merge base `d198eac4acde5e4aaee7e8712c0d7181e6c59648` |
| Reviewed revision | `3a9f607ab9f3bed7ef689e06865e476912ebc353` |
| Issue | `#351` |
| Plan | `docs/plans/2026-07-15-issue-351-dispatch-settlement-plan.md` |
| Work session | `docs/work-sessions/2026-07-16-issue-351-dispatch-settlement.md` |
| Scope check | CLEAN |
| Blocked | false |

No work-thread saga was discoverable through `saga.py scan`, so the review did not mint or mutate a
saga record.

## Scope Check

Intent: add one canonical, append-only dispatch-settlement contract and real outcome,
team-execution, and generated-workflow adapters, with casualty gating and bounded retry.

Delivered: the diff stays within that intent. It adds the ledger schema, transition engine, outcome
integration, protocol surfaces, release metadata, and tests. The review found incomplete or unsafe
parts of the planned behavior, but no unrelated product scope.

## Plan Completion

| Unit | Status | Evidence |
|---|---|---|
| U1 — schema and atomic transitions | DONE | Closed transitions are lock-consistent; ledger bytes and new directory entries are synchronized before the runtime call. |
| U2 — classification, report, threshold, DLQ | DONE | Persisted closed receipts, attempt-scoped casualty cohorts, bounded retries, and late delivery share one verified path. |
| U3 — outcome adapter | DONE | All terminals settle, completion digests bind canonical events, and runtime requests preserve replay identity. |
| U4 — team-execution adapter | DONE | Packaged Saga resolution and a closed reviewer/validator result adapter are executable and tested. |
| U5 — workflow driver settlement | DONE | Invocation-bound identity, complete commands, safe legacy-name mapping, and behavioral driver tests are present. |
| U6 — CLI, release surfaces, full gate | DONE | JSON and deterministic text views, release parity, marketplace sync, static checks, and the full test gate pass. |

COMPLETION: 6/6 DONE.

## Findings

### CR-351-01 — P1 — Caller-controlled evidence can false-green delivery

- **Location:** `plugins/saga/scripts/dispatch_settlement.py:606`
- **Confidence:** 100
- **Impact:** `trusted: true`, caller-selected outputs, and any syntactically valid digest are
  accepted without loading an artifact, validating its schema, or recomputing its digest. The same
  raw-reference path lets a fabricated late delivery clear a casualty and its DLQ entry.
- **Required fix:** replace the caller-selected trust flag with receipt-specific adapters that load
  the referenced worker manifest, structured result, validator state, or host receipt; verify unit
  and required-output binding; compute the digest internally; and route late delivery through the
  same verified path. Add negative false-green tests.
- **Status:** Resolved; closed artifact kinds validate reviewer/validator payloads and derive outputs internally. Verified by bounded re-review.

### CR-351-02 — P1 — Retry cohort casualties are diluted by the original manifest

- **Location:** `plugins/saga/scripts/dispatch_settlement.py:786`
- **Confidence:** 100
- **Impact:** one failed retry in a ten-unit dispatch is evaluated as 10 percent rather than the
  retry cohort's 100 percent. New fan-out work can proceed even though the configured per-attempt
  threshold is exceeded.
- **Required fix:** derive the live gate from unresolved, attempt-scoped cohorts and add a regression
  where a small retry cohort cannot be diluted by attempt-one successes.
- **Status:** Resolved; attempt-specific cohort regression passes.

### CR-351-03 — P1 — Negative outcome terminals never settle

- **Location:** `plugins/saga/scripts/outcome.py:1748`
- **Confidence:** 100
- **Impact:** `failed`, `rejected`, and `stalled` terminal events are excluded by the success-only
  harvester view. Their spawn remains open forever and can never enter the derived DLQ. Successful
  settlement also hashes a generic marker instead of the canonical completion event.
- **Required fix:** reconcile every terminal event, bind the digest to its durable event content,
  classify negative terminals fail-closed, and cover failed/rejected/stalled-to-DLQ behavior.
- **Status:** Resolved; success and all negative terminals are covered through replay and DLQ paths.

### CR-351-04 — P1 — Outcome runtime requests omit settlement identity

- **Location:** `plugins/saga/scripts/outcome.py:1442`
- **Confidence:** 75
- **Impact:** crash replay reuses the ledger's stable idempotency key internally but does not pass
  that key, dispatch ID, or attempt to the backend. A host that accepted the first submission cannot
  deduplicate the replay.
- **Required fix:** carry settlement identity on `DispatchRequest`, make dispatcher adapters preserve
  it, and test the accepted-launch-before-commit replay window.
- **Status:** Resolved; backend requests preserve dispatch, attempt, and idempotency identity.

### CR-351-05 — P1 — Workflow dispatch identity cannot distinguish a resume from a new run

- **Location:** `plugins/saga/scripts/execution_spec.py:3189`
- **Confidence:** 100
- **Impact:** every unchanged spec receives the same dispatch ID, while the documented launch path
  appends a non-idempotent manifest before every invocation. Crash resume and a genuine later run
  therefore collide.
- **Required fix:** include a durable driver-owned invocation identity, reuse it only for resume,
  make exact manifest replay idempotent, and verify same-instance replay versus new-instance
  separation.
- **Status:** Resolved; invocation identity separates later runs and exact replay is idempotent.

### CR-351-06 — P1 — Team-execution cannot resolve or run the mandatory Saga dependency

- **Location:** `plugins/team-execution/skills/team-execution/SKILL.md:390`
- **Confidence:** 100
- **Impact:** team-execution is packaged independently but now requires a repository-relative Saga
  executable before every reviewer and validator call. A normal installed plugin has no such path.
- **Required fix:** add a packaged resolver/preflight for the installed Saga plugin, fail before any
  Agent call when unavailable, and test source-checkout, installed-registry/cache, and missing
  prerequisite behavior without copying the canonical ledger engine.
- **Status:** Resolved; resolver covers explicit, source, registry, cache, and fail-loud paths.

### CR-351-07 — P1 — Team-execution has no executable result-to-receipt adapter

- **Location:** `plugins/team-execution/skills/team-execution/SKILL.md:394`
- **Confidence:** 100
- **Impact:** reviewer agents return scored text and validators write state files, but the protocol
  requires a contract-bearing manifest and exact trusted receipt that no component creates. Normal
  runs must settle as `silent-no-op` and block their own gates.
- **Required fix:** add a coordinator-owned adapter that validates the real returned result/state,
  materializes the canonical receipt or manifest, and invokes settlement. Add behavioral missing,
  incomplete, self-report, roster-completeness, and artifact-pointer rejection tests.
- **Status:** Resolved; executable adapter validates and materializes closed reviewer/validator receipts.

### CR-351-08 — P1 — Workflow settlement protocol is not executable

- **Location:** `plugins/saga/skills/work/SKILL.md:303`
- **Confidence:** 100
- **Impact:** the launch instructions omit the required `spawn` commands, and the post-run `settle`
  example omits dispatch, unit, attempt, and time arguments. The planned workflow adapter cannot be
  carried out from the documented contract.
- **Required fix:** provide a shell-ready driver command or complete commands that consume metadata,
  record every pre-submit spawn, verify and settle every result, report, and derive retries. Add an
  isolated manifest/spawn/result/missing-result/self-report integration test.
- **Status:** Resolved; shell-ready workflow driver and integration coverage are present.

### CR-351-09 — P2 — Run-fact appends are not synchronized to storage

- **Location:** `plugins/saga/scripts/run_ledger.py:245`
- **Confidence:** 75
- **Impact:** a host crash after runtime submission can lose the pre-call spawn record that the new
  contract calls durable.
- **Required fix:** synchronize the appended file and newly created directory entry before returning;
  add a narrow durability/fault-order regression.
- **Status:** Resolved; append and directory durability ordering is tested.

### CR-351-10 — P2 — Workflow metadata narrows previously valid identifiers

- **Location:** `plugins/saga/scripts/execution_spec.py:3198`
- **Confidence:** 100
- **Impact:** valid return keys with whitespace, duplicates, or long identifiers are passed into the
  stricter settlement identifier contract and can now make workflow emission fail.
- **Required fix:** encode or otherwise map workflow result keys into bounded settlement identities
  without changing the original result contract; add compatibility tests.
- **Status:** Resolved; unsafe, long, and duplicate result names retain a safe side mapping.

### CR-351-11 — P2 — Retry claim race lacks a concurrency oracle

- **Location:** `tests/test_dispatch_settlement.py:540`
- **Confidence:** 100
- **Impact:** one-winner retry correctness depends on in-lock append validation, but no concurrent
  claim test proves that guarantee.
- **Required fix:** race two barrier-synchronized claims and assert one attempt-two spawn, one
  rejection, stable idempotency identity, and a valid chain.
- **Status:** Resolved; barrier race proves one winner and a valid chain.

### CR-351-12 — P2 — Unexpected dispatcher crashes lack a settlement regression

- **Location:** `tests/test_outcome_dispatcher.py:294`
- **Confidence:** 100
- **Impact:** the defining crash window is not tested; a future broad exception could accidentally
  settle or erase the open attempt.
- **Required fix:** raise an unexpected dispatcher exception after spawn and assert manifest plus
  spawn remain as one open position.
- **Status:** Resolved; unexpected post-spawn crash leaves exactly one open attempt.

### CR-351-13 — P2 — Human-readable operator views are absent

- **Location:** `plugins/saga/scripts/dispatch_settlement.py:1336`
- **Confidence:** 100
- **Impact:** `report`, `dlq`, and `reconcile --leaks` expose JSON only despite U6 requiring both
  script and terminal-readable output.
- **Required fix:** retain JSON as the default and add deterministic text rendering plus CLI tests.
- **Status:** Resolved; report, DLQ, and reconciliation expose deterministic text output.

### CR-351-14 — P2 — Run-ledger producer documentation contradicts the new writer

- **Location:** `plugins/saga/scripts/run_ledger.py:1`
- **Confidence:** 100
- **Impact:** the public module contract still says the coordinator never writes, while outcome and
  workflow settlement are explicitly coordinator-produced. Future consumers can enforce the wrong
  invariant.
- **Required fix:** document producer-owned facts and the dispatch-settlement exception without
  weakening leaf attribution for ordinary telemetry.
- **Status:** Resolved; producer ownership and the coordinator dispatch exception are documented.

## Suppressed Candidates

- The live-worktree reviewer interpreted `leaked-worktree` as an existing orphaned directory. The
  approved plan's current-state section, KTD7, U3 acceptance selector, and journal decision instead
  define the adapter as a read-only stale registry/on-disk mismatch. The contradictory R4 sentence
  should be corrected during the repair pass, but the implemented KTD7 behavior is not changed.
- A hostile full-filesystem agent can rewrite the whole local ledger and recompute its chain. That is
  explicitly outside `run_ledger`'s tamper-evidence threat model. CR-351-01 remains valid for normal
  coordinator correctness because even an honest caller can currently manufacture trust by mistake;
  the review does not require an impossible privilege boundary against a full-access writer.

## Coverage And Residual Risk

- Pre-review implementation gate: 4,492 passed, 1 skipped; focused 444 passed; validator slices 9
  and 87 passed; Ruff, mypy, release parity/sync/diff guard, and scoped Bandit passed.
- Review lenses: correctness, security, testing, maintainability, reliability, API contract,
  adversarial failure mode, and agent-native usability.
- Findings below confidence 75 were suppressed. No deployment or migration lens applied.
- The review artifact records findings only; the authorized `/work` continuation owns repairs,
  tests, commits, PR, and merge.

## Repair Verification

- A bounded `review_high` follow-up checked only CR-351-01 through CR-351-14: 13 resolved and one
  remaining P1. The P1 demonstrated that the first repair still accepted caller-authored outputs in
  an otherwise valid-looking generic artifact.
- The final repair changed `dispatch.artifact.v1` to the exact shape
  `{schema, kind, unit_id, payload}`, accepts only `reviewer-result` and `validator-state`, validates
  their payload contracts in Saga, and derives `scored-review` or `validator-state` internally.
- The same reviewer rechecked only CR-351-01 and marked it resolved. Its focused verification passed
  62 tests; the coordinator's expanded repair slice passed 516 tests.
- No protected workflow verdict was minted for this bounded follow-up; it verifies the durable code
  review findings rather than replacing the already-passed approved implementation workflow.

## Route

Route to PR publication after the final full quality gate and atomic repair commit.
