---
title: Lease-safe runtime continuity wave 3 - fleet-shared liveness engine
type: feat
status: active
date: 2026-07-15
origin: docs/plans/plugin-fleet-ideation-2026-07-03/survivors/T6.json
deepened: 2026-07-15
---

# Lease-safe runtime continuity wave 3 - fleet-shared liveness engine

## Summary

Implement issue #357 after #351 and #356 by extracting liveness scoring into one pure fleet-core
engine, preserving Saga's existing Outcome R31 adapter, and adding a real team-execution polling
protocol over the canonical run-fact ledger. The engine combines bounded phi-accrual heartbeat
suspicion, trusted path-scoped artifact progress, and append-only idle-notification acknowledgments.
It detects and requests action; #358 retains destructive teardown and #355 retains bridge-write
fencing/quarantine.

Destination is merge. Execution uses an operator-approved Verified Workflow. Root owns
implementation, Git, integration, PR, merge, issue closure, and board reconciliation. Agent-lens
roles independently review or validate and authorize no repository mutation.

---

## Problem Frame and Current State

The issue is requirements-ready but three assumptions have drifted since it was filed:

1. `outcome_liveness.py` is still the only production liveness implementation. It derives dispatch
   and heartbeat timestamps from the Outcome ledger, applies fixed heartbeat/absolute-timeout
   budgets, writes one sticky `stalled` terminal, and cascades through R22. Its max-by-timestamp and
   dispatch-floor behavior are regression-critical.
2. Team-execution is now 2.16.0, not the issue's 2.9.0. It still has no liveness engine, but #351's
   reviewed plan adds canonical dispatch settlement on Saga's hash-chained `run_fact.v1` ledger and
   #356 adds leased residents with a 300-second default TTL and renewal at no later than one third of
   TTL. #357 must consume those contracts, not create another status or retry store.
3. `artifact_pointer.py snapshot` currently runs only after all workers complete and captures the
   whole worktree for review transfer. Pointer presence therefore cannot prove which in-flight worker
   progressed, and #351 explicitly establishes that a pointer is not a delivery ACK. #357 may reuse
   its trusted git-object snapshot mechanism, but progress must be path-scoped, baseline-relative,
   and attribution-safe.

The issue's published shared-implementation grep is also stale after #356's fleet-commons decision:
searching only Saga and team-execution would find adapters but omit the canonical fleet-core module.
The implementation must preserve the acceptance intent, amend that check before work, and enforce a
source-aware inventory over fleet-core plus both consumer call sites. A raw “one match” count is not
accepted as proof.

There is no background daemon or generic runtime callback available to either plugin. Outcome polls
inside `advance`; team-execution is a skill-driven coordinator and must poll at executable protocol
boundaries. A plan that only adds a library with no production caller would repeat the repo's
dead-wiring failure pattern.

The original phi-accrual paper defines suspicion as the negative base-10 logarithm of the probability
that the next heartbeat arrives later than the current delay, using a sampled arrival distribution.
This plan uses that score as a configurable suspicion input, not as unreviewable magic or sole
destructive authority. Source: https://dspace.jaist.ac.jp/dspace/handle/10119/4784

---

## Traceability and Dependencies

- **Parent outcome/spec:** `docs/outcomes/lease-safe-runtime-continuity/proposal.md` and subplot
  `sub-357` in `docs/outcomes/lease-safe-runtime-continuity/outcome-spec.json`.
- **Source issue:** `infiquetra/infiquetra-claude-plugins#357`; source survivors T6-F4-3,
  T6-F5-3, T6-F6-6, and H-F1-3.
- **Hard upstream:** #351 supplies dispatch identity, settlement, retry, and the canonical run-fact
  writer; #356 supplies leased resident identity, boot-aware monotonic renewal, and bounded polling
  cadence. Both must be merged and the plan refreshed before implementation.
- **Serialized baseline:** the outcome currently plans #355 first within Wave 3 because the leaves
  share Saga/fleet-core release files. From that expected base, #357 starts at fleet-core 0.13.0,
  Saga 0.100.0, and team-execution 2.18.0. Refresh exact versions and reapprove if merge order changes.
- **Downstream unlocks:** #358 consumes liveness decisions for non-skippable teardown; #353 audits
  the completed signal/action wiring; the cross-runtime coordination/acceptance children consume the
  same shared result vocabulary.
- **External prerequisites:** none. No daemon, cloud service, deployment, credential change,
  production-data access, or named specialist is required.

| published issue acceptance | plan contract | primary executable evidence |
|---|---|---|
| Outcome and team-execution consume one shared engine | R1-R3, R10; U1-U3, U5 | source-aware consumer inventory plus real Outcome/team adapter tests |
| stalled cadence crosses phi threshold; steady cadence does not | R4-R6; U1 | deterministic distribution fixtures and boundary/property cases |
| chatty but artifactless differs from silent stalled | R7; U1, U4, U5 | path-scoped unchanged-digest fixture versus no-heartbeat fixture |
| unacknowledged idle notice re-pings; acknowledged notice does not | R8-R9; U3, U5 | append-only notice/ack/reping transition tests with injected clock |
| Outcome R31 timeout/idempotent-page/R22 cascade stays green | R5, R10; U2 | existing `tests/test_outcome_liveness.py -k stalled` plus integration |
| repository gates pass | R11-R13; U6 | focused suites, full pytest, Ruff, mypy, release parity, diff check |

---

## Requirements

R1. **One pure shared engine.** Add `fleet_commons/liveness_engine.py` as the only implementation of
heartbeat normalization, phi calculation, signal fusion, and decision derivation. It takes immutable
typed observations plus an injected `now`; it performs no file, network, process, notification, or
Git mutation. Saga's Outcome and run-fact adapters load it through the existing fleet-commons shim;
team-execution reaches that exact adapter through the canonical Saga CLI rather than importing or
copying a second parser/engine.

R2. **Existing stores remain authoritative.** Outcome continues to read/write its replay ledger.
Team-execution writes liveness events as a new closed `kind=liveness` family in the #351-expanded
hash-chained `run_fact.v1` ledger. No liveness status file, second ledger, heartbeat registry, mutable
notification queue, or duplicate retry counter is introduced. Views are derived from a verified
lock-consistent snapshot.

R3. **Trusted subject and clock identity.** Every team signal binds `dispatch_id`, `unit_id`, attempt,
leased `resource_ref`, boot identity, and monotonic observation time; its run-fact also carries the
normal operator-facing ISO `at`. Outcome preserves its existing wall-time ledger for compatibility.
Team phi history never crosses a boot identity. Agent prose, message text, environment values, and
untrusted pointer fields cannot choose identity, timestamps, thresholds, acknowledgments, or results.

R4. **Bounded deterministic phi.** Normalize post-dispatch heartbeat timestamps by sorting,
deduplicating, ignoring pre-dispatch samples, and retaining at most the latest 100 positive
inter-arrival intervals. Nonfinite/negative time, `now < dispatch`, or a sample more than the policy's
5-second future-skew tolerance yields `evidence-error`; a sample within tolerance is clamped to `now`
rather than extending liveness into the future. With at least five intervals, compute mean,
population deviation with a 1-second minimum, normal-CDF late-arrival tail probability, and
`phi = -log10(max(tail, 1e-16))`, capped at 16. Default suspicion threshold is 8.0; all constants live
in one `LivenessPolicy`, are validated, and can be explicitly overridden by a trusted coordinator.

R5. **Compatibility fallback and hard timeout.** An Outcome leaf with no heartbeat/timeout budget is
still never terminalized. Absolute `timeout_seconds` remains a hard limit with the exact existing
reason/idempotent-page/cascade behavior. Fewer than five intervals use the existing fixed
`heartbeat_seconds` gap exactly, preserving sparse-history behavior. Statistical history never makes
an unconfigured leaf liveness-killable.

R6. **Phi is suspicion before terminal authority.** When enough samples cross phi 8.0, the engine
emits `heartbeat-suspect`. A coordinator declaring a trusted probe transport may arm one deterministic
re-ping intent; recent trusted artifact progress or a host-correlated response clears the suspicion,
and three exhausted attempts with no progress/ack may produce `confirmed-stalled`. Team-execution's
named resident plus root-owned `SendMessage` path is armed. Current Outcome backends without a trusted
probe/ack transport expose the phi score/suspicion only and retain the existing fixed
`heartbeat_seconds` terminal rule; adaptive scoring must never turn that compatibility path into
“never stalls.” Absolute timeout and sparse fixed-gap behavior remain unchanged. #357 never kills a
process or frees a lease; adapters map a confirmed result to their existing owner action.

R7. **Artifact progress is real and scoped.** For a contract-bearing team unit with a disjoint trusted
repo-relative output path set, capture a baseline and poll snapshot through the existing temp-index
git-tree mechanism. Derive a canonical digest only from the declared path entries `(path, mode, oid)`.
A new epoch with the same path digest is not progress; another worker's out-of-scope change is not
progress; chat messages are never progress. A unit with no pointer capability, no output contract, or
overlapping ownership falls back to heartbeat-only scoring. Progress is flagged as
`chatty-artifactless` only after an explicit budget, defaulting to its #356 lease TTL (300 seconds).

R8. **Idle notices use append-only acknowledgment.** A trusted host idle signal becomes `idle-notice`.
When the host supplies an event ID, notice identity binds that ID to trusted session/agent/dispatch
identity; otherwise the first writer allocates the next subject-local notice sequence under the
run-ledger lock from normalized host metadata, never message text. The coordinator appends `idle-ack`
only after it consumes that exact notice. A duplicate notice/ack converges idempotently. An ack proves
the notification was consumed, not that outputs were delivered; #351's complete worker manifest
remains the only delivery ACK.

R9. **Unacknowledged notices and probes retry visibly.** At poll time an unacknowledged notice past
its ack window, or a phi/artifactless suspicion, yields a `reping-intent` appended before the trusted
root sends `SendMessage`. Host-correlated response becomes `reping-ack`. Attempts are keyed by notice
or suspicion generation, spaced by the policy window, capped at three, and derived from facts. A
crash after intent stays visible; no silent loop, sleep, or mutable queue is allowed.

R10. **Both production consumers are wired.** Outcome's `production_liveness_processor()` continues
to invoke `outcome_liveness.harvest_liveness`, which adapts the shared engine and retains `_record_terminal`.
Team-execution invokes one Saga-owned liveness event/poll CLI before each worker wave, at #356 renewal
boundaries, on every trusted idle notice/Agent return, and before B2. The CLI returns action intents;
root performs `SendMessage` and records its host receipt. Before implementation, amend the issue's raw
two-directory grep to a source-aware fleet-core/Saga/team-execution conformance check. Conformance
fails a documented poll with no real caller, an omitted canonical engine, or a second implementation
under either consumer.

R11. **Sibling ownership stays intact.** #351 owns dispatch settlement/DLQ/idempotent work retries;
#356 owns leases/renewal/write fencing; #355 owns bridge-write rejection/quarantine/orphan projection;
#358 owns stop/release/process/resident teardown. #357 only observes, scores, acknowledges, re-pings,
and maps confirmed results to existing owner actions.

R12. **Evidence errors fail safe.** Broken run-fact chains, contradictory notice transitions,
unknown schema/policy versions, invalid clocks, corrupt pointers, unsafe paths, missing required
host receipts, and version-skewed fleet-core produce `evidence-error`. They cannot mark a worker
healthy, confirm delivery, terminalize it statistically, or trigger teardown.

R13. **Release integrity is atomic.** From the expected post-#355 base, bump fleet-core 0.13.0 to
0.14.0, Saga 0.100.0 to 0.101.0, and team-execution 2.18.0 to 2.19.0. Update all manifests,
marketplace rows, changelogs, minimum-version/drift guards, operator contracts, tests, and engineering
journal in the same PR. Refresh and reapprove exact increments if the base differs.

---

## High-Level Technical Design

```text
Outcome ledger --------------------+
                                    | normalized immutable observations
team run_fact.v1 liveness events ---+-------------------------------+
                                                                    v
                                                    fleet-core liveness engine
                                                    - fixed fallback
                                                    - phi suspicion
                                                    - path progress
                                                    - notice/ack state
                                                                    |
                                           +------------------------+-------------------+
                                           |                                            |
                                 Outcome adapter                                team poll adapter
                                 sticky R31 only on                            action intents only
                                 confirmed/hard result                         (root sends/records)
                                           |                                            |
                                           v                                            v
                               R22 cascade/page once                       #351 settle / #358 owner
```

### Pure decision contract

The engine returns one closed `liveness_decision.v1` value:

```text
subject_id
classification: healthy | heartbeat-suspect | chatty-artifactless |
                reping-required | confirmed-stalled | evidence-error
phi: number | null
sample_count
last_heartbeat
last_progress
pending_notice_ids[]
reping: {generation, attempt, idempotency_key} | null
reason_code
evidence_refs[]
```

Precedence is evidence error, hard absolute timeout, compatibility fixed-gap when adaptive transport
is unavailable, sparse fixed-gap fallback, artifact progress, artifactless budget, phi suspicion,
notice acknowledgment, then healthy. An ack or artifact change can refute suspicion but cannot
satisfy output completeness. `confirmed-stalled` names its cause (`absolute-timeout`, `fixed-gap`, or
`reping-exhausted`) so adapters never parse prose.

### Team liveness fact contract

Every team fact uses `schema=run_fact.v1`, `kind=liveness`, #351's `subplot_id`, and a closed event:

| event | required trusted fields | invariant |
|---|---|---|
| `heartbeat` | dispatch/unit/attempt/resource, boot, monotonic time, host evidence ref/digest | host receipt or runtime event, never agent prose |
| `artifact-progress` | subject, pointer ref/digest, declared-path digest, baseline/current digest, monotonic time | only changed scoped digest counts |
| `idle-notice` | host event ID or allocated sequence, subject, normalized signal ref/digest, observed time | one notice identity/digest; no message text |
| `idle-ack` | notice ID, ack ref/digest, observed time | notice must exist; one exact ack |
| `reping-intent` | generation, attempt, idempotency key, reason, observed time | append before SendMessage; attempts 1..3 contiguous |
| `reping-ack` | generation, attempt, host receipt ref/digest, observed time | matching intent must exist |

Transition validation and append occur under the run ledger's one exclusive lock. Reads use one
verified snapshot and create no files. Raw message/prompt/output text is never stored.

### Poll cadence

No daemon is added. Team-execution polls:

1. after #351 manifest creation and before the first Agent spawn;
2. before assigning each unit to a resident;
3. at every #356 renewal boundary (no later than TTL/3, 100 seconds by default);
4. whenever the host returns Agent/SendMessage or emits an idle/terminal signal;
5. before unblocking a dependent segment and before B2 review.

If the coordinator cannot poll while one tool call is in flight, #356 may expire authorization and
block the next mutation; #357 does not pretend it can preempt that call.

---

## Key Technical Decisions

- **KTD1 - fleet-core owns the algorithm; Saga owns coordinator state adapters.** Team-execution
  already depends on Saga's manifest/run-fact substrate, while fleet-core is the installed code bus.
  Moving the Outcome ledger or duplicating parsers would enlarge the issue without improving truth.
- **KTD2 - phi is a score plus capability-gated confirmation, not a kill switch.** Threshold 8 means
  a modeled tail probability of at most 1e-8, but local agent cadence is noisy. An armed trusted
  transport uses bounded host-correlated re-ping/artifact evidence; an unarmed Outcome backend keeps
  the exact fixed-gap terminal and treats phi as advisory.
- **KTD3 - sparse history preserves the old fixed-gap rule.** Five complete intervals are required;
  absolute timeout and no-budget opt-out never change.
- **KTD4 - artifact progress is baseline-relative path content.** Pointer epoch appearance, whole-tree
  change, mtime, and chat activity are insufficient. Overlapping worker scopes disable attribution.
- **KTD5 - idle acknowledgment is consumption evidence only.** It never becomes a worker-output ACK
  and therefore cannot bypass #351 completeness/settlement.
- **KTD6 - facts, not queues.** Notice, ack, and re-ping attempts are append-only facts; pending work
  and attempt counts are projections from a verified snapshot.
- **KTD7 - detection and action remain separate.** #357 may request a re-ping and report the owning
  reclaimer. #358 later makes stop/release/teardown non-skippable.
- **KTD8 - polling is explicit and source-inventoried.** With no daemon, every required boundary must
  name a production caller and fail conformance if it becomes docs-only.

These decisions are recorded under `{#fleet-shared-liveness-357}` in
`docs/engineering-journal/DECISIONS.md` before implementation starts.

---

## Implementation Units

### U1. Pure fleet-core liveness engine

**Goal:** Implement normalized observations, bounded phi math, signal fusion, decision vocabulary,
and evidence errors without I/O.

**Requirements:** R1, R3-R7, R12.

**Dependencies:** #356 merged; no unit dependency.

**Files:** `plugins/fleet-core/scripts/fleet_commons/liveness_engine.py` (new),
`tests/test_liveness_engine.py` (new).

**Approach:** Use frozen dataclasses and closed enums. Validate finite nonnegative times and policy
bounds. Compute a normal-CDF tail with stdlib `math.erf`, clamp it before log, cap output, and return
structured reasons. Keep distribution/sample code separately testable from policy fusion.

**Test scenarios:** Steady 10-second intervals stay below threshold; a 100-second silence after the
same series crosses. Threshold just below/at/above 8, zero variance, duplicate/out-of-order beats,
within/beyond future-skew tolerance, clock rollback, pre-dispatch beats, one to five intervals,
maximum-window truncation, nonfinite values, and a boot change are deterministic. Property cases
assert phi is finite, nonnegative, monotonic in elapsed time for a fixed sample, and invariant to
input order/duplicates.

**Verification:** No I/O at import/evaluate; the original paper's probability meaning and all plan
constants are represented in tests and docs.

### U2. Backward-compatible Outcome adapter

**Goal:** Keep the production `harvest_liveness` API and every R31 side effect while replacing local
threshold calculation with the shared engine.

**Requirements:** R1-R6, R10-R12.

**Dependencies:** U1.

**Files:** `plugins/saga/scripts/outcome_liveness.py`, `plugins/saga/scripts/outcome.py`,
`tests/test_outcome_liveness.py`, `tests/test_outcome_integration.py`.

**Approach:** Load `liveness_engine` through Saga's fleet shim. Continue deriving full dispatch and
heartbeat histories from the Outcome ledger, floor at dispatch, and call existing `_record_terminal`
only for `confirmed-stalled`. Current production backends declare no generic probe transport, so the
adapter returns additive phi suspicion while retaining the fixed heartbeat/timeout terminal decision.
A future/backend-specific injected probe callback may arm adaptive confirmation only with trusted
host receipt evidence. Preserve public functions and exact fixed-timeout reason strings; keep existing
`stalled`/`cascade_paused` keys.

**Test scenarios:** Every current test remains unchanged/green. Add rich steady/stalled histories,
phi suspicion with the compatibility fixed-gap terminal, an injected armed probe adapter with
re-ping confirmation and progress/ack refutation, corrupt engine/skew failure, and real
`production_liveness_processor` integration.

**Verification:** A node with no budget remains immortal; sparse fixed-gap, absolute timeout,
idempotent page, max timestamp, dispatch floor, and R22 cascade are byte/semantic compatible.

### U3. Canonical liveness facts and poll CLI

**Goal:** Extend #351's run-fact ledger with one closed liveness family and expose append/poll verbs
used by team-execution.

**Requirements:** R2-R3, R6, R8-R10, R12.

**Dependencies:** #351 merged; U1.

**Files:** `plugins/saga/scripts/run_ledger.py`, `plugins/saga/scripts/liveness_events.py` (new),
`tests/test_run_ledger.py`, `tests/test_liveness_events.py` (new).

**Approach:** Add `kind=liveness`, typed fact builders, and lock-scoped transition validators.
Provide `heartbeat`, `artifact-progress`, `notice`, `ack`, `reping-intent`, `reping-ack`, and read-only
`poll` commands with JSON output. `poll` verifies the chain once, projects one subject, calls fleet
engine, and returns action intent; it never sends messages or mutates on read.

**Test scenarios:** Valid lifecycle, duplicate idempotency, unknown notice, ack digest mismatch,
intent-before-ack ordering, attempt gap/cap, crash after intent, concurrent same-generation pollers,
broken/torn chain, boot reset, read-side no-create, and bounded IDs/evidence refs.

**Verification:** Two concurrent writers cannot create duplicate attempt numbers; a read never heals
or appends; missing/contradictory evidence returns `evidence-error`.

### U4. Attribution-safe artifact progress

**Goal:** Reuse artifact-pointer snapshot custody while deriving real progress only from declared
worker paths.

**Requirements:** R7, R12.

**Dependencies:** U1, U3.

**Files:** `plugins/team-execution/skills/team-execution/scripts/artifact_pointer.py`,
`plugins/team-execution/skills/team-execution/references/artifact-pointers.md`,
`tests/test_team_execution_pointers.py`, `tests/test_team_execution_liveness.py` (new).

**Approach:** Add a `progress` command that validates disjoint trusted repo-relative path specs,
creates the normal temp-index tree snapshot, enumerates only declared paths with fixed Git argv, and
returns pointer plus canonical baseline/current digest. It does not alter `ArtifactPointer` shape,
review thresholds, dereference, freshness, or delivery meaning.

**Test scenarios:** Own-path change advances; unrelated worker path and same-tree new epoch do not;
untracked own file advances; deletion is progress; overlap, traversal, absolute/symlink-escape,
missing baseline, stale/corrupt pointer, sparse checkout, and Git failure fail safe. Real-git fixture
uses two worker scopes and proves cross-attribution is impossible.

**Verification:** Existing pointer suite remains green and #351 delivery classification still rejects
pointer-only evidence.

### U5. Team-execution production protocol and conformance

**Goal:** Make liveness polling and notice acknowledgment executable at every real resident boundary,
with no second implementation.

**Requirements:** R1-R3, R6-R12.

**Dependencies:** U2-U4.

**Files:** `plugins/team-execution/skills/team-execution/SKILL.md`,
`plugins/team-execution/skills/team-execution/references/liveness-protocol.md` (new),
`plugins/team-execution/skills/team-execution/references/worker-manifest.md`,
`plugins/saga/references/liveness-consumer-sites.md` (new),
`tests/test_team_execution_liveness.py`, conformance tests.

**Approach:** Add exact CLI sequences at B0/B1/B2 boundaries. Root records host evidence, captures
scoped progress, polls, appends re-ping intent, sends one ID-bound message, and records receipt/ack.
The worker cannot self-ack or choose policy. Inventory every Outcome/team consumer, signal writer,
poll boundary, action owner, fallback, and test. Source-aware conformance rejects a new consumer or
idle-notice path without the shared engine and event lifecycle.

**Test scenarios:** Chatty/no-progress, silent/no-heartbeat, artifact-progress despite quiet,
unacked notice re-ping, acked notice no re-ping, duplicate notice, lost SendMessage result, three
unacked probes, manifest-delivered despite idle signal, and zero-output manifest remain distinct.
Protocol tests prove the documented commands resolve to production functions rather than prose.

**Verification:** One source implementation exists in fleet-core; both production consumers and all
poll boundaries are executable and inventoried.

### U6. Release surfaces and full gate

**Goal:** Publish the shared engine and both adapters coherently from the refreshed Wave 3 baseline.

**Requirements:** R10-R13.

**Dependencies:** U2-U5.

**Files:** `plugins/fleet-core/.claude-plugin/plugin.json`,
`plugins/saga/.claude-plugin/plugin.json`, `plugins/team-execution/.claude-plugin/plugin.json`,
`.claude-plugin/marketplace.json`, three changelogs, version/drift tests,
`docs/engineering-journal/DECISIONS.md`, and operator references.

**Approach:** Bump fleet-core 0.14.0, Saga 0.101.0, and team-execution 2.19.0 from the expected base;
update required fleet-core compatibility and release narratives. Run installed-plugin resolution so
both shims prove the same engine bytes/version.

**Test scenarios:** Local and installed layouts resolve the canonical module; an old/missing
fleet-core fails armed liveness with named diagnostic; marketplace/manifests/changelogs agree; an
injected duplicate engine or dead consumer row fails conformance.

**Verification:** Full gate and release parity are green from a clean branch.

---

## Requirement Coverage

| requirement | units | primary proof |
|---|---|---|
| R1-R3 | U1-U3, U5 | single implementation and verified normalized event snapshots |
| R4-R6 | U1-U3 | math/property boundaries, sparse compatibility, bounded confirmation |
| R7 | U1, U4-U5 | real-git two-worker scoped progress and artifactless distinction |
| R8-R9 | U3, U5 | notice/ack/reping transition matrix and crash/concurrency cases |
| R10 | U2, U5 | real Outcome processor and executable team protocol |
| R11-R12 | U2-U5 | sibling-boundary and evidence-error conformance |
| R13 | U6 | installed-resolution and release-surface parity |

---

## Scope Boundaries

### In scope

- Pure fleet-core liveness scoring and decision vocabulary.
- Outcome adapter preserving R31 behavior.
- Team liveness facts/polling, scoped artifact progress, idle ack, and bounded re-ping intent.
- Consumer/writer/poll/action inventory and three-plugin release.

### Non-goals

- Killing agents/processes, stopping residents, releasing leases, deleting worktrees, or Step B8
  teardown; #358 owns these actions.
- Work retry/DLQ/output delivery; #351 owns them.
- Write fencing, quarantine, or bridge orphan classification; #355/#356 own them.
- Background daemon, distributed failure detector, cross-host clock synchronization, notification
  bus, UI/dashboard, generic pub/sub, or backfilling pointers to unsupported worker kinds.
- Changing artifact-pointer schema, review transfer thresholds, worker-manifest ACK semantics,
  validator order, consensus cap, or Outcome R22 terminal cascade.

---

## Risks and Mitigations

| risk | impact | mitigation/proof |
|---|---|---|
| noisy cadence false-stalls live work | lost work and bad cascade | min samples, phi 8, artifact/ack refutation, three-stage confirmation, absolute timeout unchanged |
| whole-worktree snapshot credits wrong worker | chatty worker appears productive | disjoint declared path digest; overlap disables progress signal; real two-worker Git test |
| acknowledgment becomes delivery authority | missing outputs pass | ack only proves notice consumption; #351 manifest remains sole delivery ACK |
| manual skill protocol is dead prose | team never polls | exact CLI sequences, production-path tests, consumer-site conformance |
| clock/boot drift corrupts intervals | nonmonotonic or stale phi | #356 boot/monotonic identity for team; validation/reset; existing Outcome compatibility path |
| unbounded events/re-pings | ledger/storage or message storm | 100-sample window, 3 attempts, idempotency keys, derived pending view |
| shared release surfaces collide | bad version/install truth | serialized main refresh and reapproval if expected versions differ |

---

## Verification

Run focused gates after their units, then the full repository gate:

```bash
uv run pytest tests/test_liveness_engine.py -v
uv run pytest tests/test_outcome_liveness.py tests/test_outcome_integration.py -v
uv run pytest tests/test_run_ledger.py tests/test_liveness_events.py -v
uv run pytest tests/test_team_execution_pointers.py tests/test_team_execution_liveness.py -v
uv run pytest
uv run ruff format --check .
uv run ruff check .
uv run mypy plugins/ scripts/ tests/ --ignore-missing-imports
uv run bandit -r plugins/
uv run python scripts/check_release_surface_parity.py
uv run python scripts/sync_marketplace.py --check
uv run python tools/release_surface_diff_guard.py --base-ref origin/main
git diff --check
```

The event-flow validator independently traces heartbeat/progress/notice/ack/re-ping/confirmation and
proves no event grants output or teardown authority. The scenario validator runs steady/stalled,
chatty-artifactless, quiet-progressing, acknowledged/unacknowledged, sparse-history, corrupt-evidence,
and Outcome compatibility scenarios from captured command evidence. Both use gpt-5.6-terra medium;
the four high-judgment reviewers use gpt-5.6-sol high.

Manual evidence includes the policy/math table with computed phi values, one real-git two-worker path
attribution run, one unacked notice producing exactly one next re-ping intent, one ack suppressing it,
and one production Outcome tick preserving page-once/cascade behavior.

---

## Failure Modes and Stop Conditions

- Phi alone writes a sticky terminal or triggers teardown without bounded confirmation: stop; restore
  suspicion-before-action.
- A no-budget Outcome leaf becomes killable, sparse history skips the old fixed fallback, or absolute
  timeout reason/idempotency/cascade changes: stop as a P0/P1 compatibility defect.
- Message text, prompt content, agent-provided timestamps, or raw pointer locator selects policy or
  produces an ack/progress fact: stop at the trust boundary.
- Whole-tree change, mtime, pointer epoch, or another worker's path counts as progress: stop and
  restore scoped baseline-relative digest.
- Idle ack or artifact pointer satisfies #351 delivery/output completeness: stop; contracts merged
  incorrectly.
- Poll reads append/heal, event transitions validate outside the append lock, re-ping attempts exceed
  three/gap, or a broken chain becomes healthy: stop as evidence-integrity defect.
- A second liveness algorithm/store/status cache appears, or team wiring exists only in docs with no
  executable production test: stop and consolidate.
- #357 kills/releases/deletes or duplicates #355/#358 ownership: stop for scope correction.
- Any P0-P3 document/code-review finding remains, a required validator lacks gate-capable evidence,
  full gates fail, or release metadata drifts: no PR/merge.

---

## Workflow Structure

| step_id | depends_on | barrier | role_id | role_kind | independence | execution_class | runtime_agent_name | vehicle | mutation | required_evidence | role_lens_sha256 | profile_sha256 | expected_model | expected_effort | validator_required | validator_disabled | deterministic_contract_sha256 |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| implement | - | - | root | root | n/a | - | - | root | root-only | authorized-diff,focused-tests | - | - | - | - | n/a | n/a | - |
| review-devils | implement | review | devils-advocate-reviewer | agent-lens | preferred | review-high | review_high | auto | none | scored-review,findings | 129f6dca0702ffcd4be7f9e5d0939e8e6806788846ba4058044c931883ef0e63 | 42e86e00e054281b0a79e4b3b9b544c04a31eb2fd6b53c0489adc42ea639c9a8 | gpt-5.6-sol | high | n/a | n/a | - |
| review-security | implement | review | security-reviewer | agent-lens | preferred | review-high | review_high | auto | none | scored-review,findings | bf5bc1b66c0ee3d06071976b659c522c23057c56de5f6cc010556b2653c86980 | 42e86e00e054281b0a79e4b3b9b544c04a31eb2fd6b53c0489adc42ea639c9a8 | gpt-5.6-sol | high | n/a | n/a | - |
| review-architecture | implement | review | architecture-reviewer | agent-lens | preferred | review-high | review_high | auto | none | scored-review,findings | e48b37cea0b26bf39cae4d6611b4219e907d52d284ba6b9489b523a4b16c835f | 42e86e00e054281b0a79e4b3b9b544c04a31eb2fd6b53c0489adc42ea639c9a8 | gpt-5.6-sol | high | n/a | n/a | - |
| review-testing | implement | review | testing-reviewer | agent-lens | preferred | review-high | review_high | auto | none | scored-review,test-gaps | a867575e24c86b0573485d1d8bbd81514af3654d544342677b85f4bed0d9af63 | 42e86e00e054281b0a79e4b3b9b544c04a31eb2fd6b53c0489adc42ea639c9a8 | gpt-5.6-sol | high | n/a | n/a | - |
| validate-event-flow | implement | validate | event-flow-tester | agent-lens | preferred | test-medium | test_medium | auto | none | event-trace,command-results | 2e20ab6935b1e17e363b5e28308a9288107532d0118a6a189f07b0e0eaaff356 | 6d69bb4d5e477574ce186a353a3d2fcc7f8ab6b1f014b93aebb05084aecccc1b | gpt-5.6-terra | medium | true | false | - |
| validate-scenarios | implement | validate | scenario-tester | agent-lens | preferred | test-medium | test_medium | auto | none | scenario-matrix,command-results | 8167b31e38f328eca0bf4cfc4ad782ee3a85669af7b08be8aa422b8edbc46f68 | 6d69bb4d5e477574ce186a353a3d2fcc7f8ab6b1f014b93aebb05084aecccc1b | gpt-5.6-terra | medium | true | false | - |
| integrate | review-devils,review-security,review-architecture,review-testing,validate-event-flow,validate-scenarios | - | root | root | n/a | - | - | root | root-only | fixed-findings,full-gate,release-parity,git-receipt | - | - | - | - | n/a | n/a | - |

## Workflow Operating Contract

- The authorized subject is this issue's implementation paths plus exact release surfaces. Root
  records the pre-existing Git baseline before `implement`; unrelated worktree paths are excluded.
- Agent-lens rows authorize `mutation=none` and no external mutation. Current MultiAgent V2 may
  reapply the parent's permission profile, so the named profile is not claimed as an OS-enforced
  read-only sandbox. Root records a baseline, audits the worktree after every attempt, and treats any
  child-created diff as workflow-integrity failure. Root runs commands; validators independently
  assess captured evidence and semantics.
- `vehicle=auto` requests the named profiles above. The runtime receipt must confirm model, effort,
  role-lens hash, and profile hash before the attempt counts. A mismatch is stopped and rerun in a
  fresh bounded context with the approved profile; missing independence/evidence blocks the gate.
- Root fixes every P0-P3 finding and creates a fresh follow-up attempt for affected roles. Three
  unsuccessful remediation cycles halt and page the operator. Any model, effort, lens, validator, or
  execution-class change requires a newly approved workflow candidate.
- Git mutation, PR creation, merge, issue/board mutation, and completion remain root-only. No deploy,
  credential, production-data, force-push, or branch-deletion action is authorized.
- Workflow intents, receipts, findings, command logs, workspace audits, PR URL, merge SHA, issue close,
  and board reconciliation are retained in the Verified Workflow evidence root and issue/PR.

---

## Completion Gate

Completion requires every published acceptance outcome plus the added trust/transition/property
proofs, zero open P0-P3 doc/code-review findings, both required validators passing with gate-capable
evidence, full verification green, one atomic issue PR merged, issue #357 closed, its Operations card
reconciled, dependent outcome nodes refreshed, and the outcome worktree clean except for the next
planned wave.
