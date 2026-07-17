---
title: Lease-safe runtime continuity wave 3 - fleet-shared liveness engine
type: feat
status: active
date: 2026-07-15
origin: docs/plans/plugin-fleet-ideation-2026-07-03/survivors/T6.json
deepened: 2026-07-17
---

# Lease-safe runtime continuity wave 3 - fleet-shared liveness engine

## Summary

Implement issue #357 on the merged #351/#356/#355 baseline from PRs #611/#612/#614 plus PR #613's
repair for lease-authorized teardown. The change adds one fleet-core scoring engine, preserves
Outcome R31, and adds a team-execution observation and re-ping protocol. #355 remains a sibling
ownership boundary already serialized into this baseline; #358 alone consumes confirmed liveness
for destructive action.

Destination is merge. Execution uses an operator-approved Verified Workflow. Root owns
implementation, Git, integration, PR, merge, issue closure, and board reconciliation. Agent-lens
roles independently review or validate and authorize no repository mutation.

---

## Problem Frame and Current State

The merged #355 baseline is `a1dc0c2a247fd72e2c5fec723ac1334c511fe7a4` on `origin/main`, with
fleet-core 0.13.0, Saga 0.100.0, and team-execution 2.19.0. The existing #357 branch preserves its
plan/review commit and carries that baseline as the second parent of merge commit
`df70b4ac7359f2eb5aa0e649cff83949656802d6`. `run_ledger.py` provides the lock-consistent
`append_fact_atomic()` path and `kind=dispatch-settlement`. Fleet leases use boot-aware monotonic time
and `DEFAULT_TTL_SECONDS = 300`; lease renewal preserves mutation authorization but is neither a
worker heartbeat nor proof of progress.

`outcome_liveness.py` remains the only production liveness implementation. It derives dispatch and
heartbeat timestamps from the Outcome ledger, applies fixed heartbeat/absolute-timeout budgets,
writes one sticky `stalled` terminal, and cascades through R22. Its heartbeat-first ordering,
max-by-timestamp and dispatch-floor behavior, exact reasons, no-budget opt-out, page-once behavior,
and R22 cascade are regression-critical.

Team-execution still has no shared scoring engine. Its artifact snapshots are whole-worktree,
post-worker review artifacts, so their appearance or epoch change cannot establish per-worker
progress. #357 may reuse the trusted Git-object snapshot mechanism only after capturing a trusted
pre-spawn baseline and restricting comparison to a worker's approved paths. Even then, a changed
declared-path digest proves only scoped activity between observations, not which resident caused it.
It remains `scoped-activity-unattributed` unless a trusted exclusive-provenance receipt binds the
subject, lease/fence, paths, digest interval, and exclusive mutation custody.

The issue's published shared-implementation grep is also stale after #356's fleet-commons decision:
searching only Saga and team-execution would find adapters but omit the canonical fleet-core module.
The implementation must preserve the acceptance intent, amend that check before work, and enforce a
source-aware inventory over fleet-core plus both consumer call sites. A raw “one match” count is not
accepted as proof.

There is no daemon or continuous runtime callback available to either plugin. Outcome polls inside
`advance`; team-execution is a skill-driven coordinator and must poll cooperatively at explicit
protocol boundaries. A plan that only adds a library with no production caller would repeat the
repo's dead-wiring failure pattern.

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
- **Satisfied semantic prerequisites:** #351 and #356 are merged. PR #613's authority-retention rule
  is binding: failed or ambiguous teardown retains broker authority and cannot be treated as
  successful reclamation.
- **Serialized release sibling:** #355 is merged and the branch carries `origin/main` at PR #614 as
  a true merge parent. #355 is not an API prerequisite, and #357 must not import or consume its
  quarantine, close-seal, or orphan-projection code.
- **PR baseline:** merged #355 supplies fleet-core 0.13.0, Saga 0.100.0, and team-execution 2.19.0.
  Target versions are fleet-core 0.14.0, Saga 0.101.0, and team-execution 2.20.0. If merge order or
  any current plugin version changes, recompute versions and rerun document review and workflow
  approval.
- **Downstream unlocks:** #358 consumes liveness decisions for non-skippable teardown; #353 audits
  the completed signal/action wiring after #355/#357/#358; the cross-runtime coordination/acceptance
  children consume the same shared result vocabulary.
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

R3. **Trusted subject and clock identity.** The closed `liveness.subject.v1` key contains exactly
`session_id`, `subplot_id`, `dispatch_id`, `unit_id`, `attempt`, `resident_id`, `agent_id`, `lease_id`,
`resource_sha256`, `broker_epoch`, `fencing_sequence`, and `boot_id`. Its ID is
`"subject:sha256:" + sha256(canonical_json(subject_key))`, where canonical JSON is sorted and compact,
and `resource_sha256` is derived from fleet-core's canonical `resource_ref`, never supplied by the
caller. Each run-fact also carries the operator-facing ISO `at`; Team phi history never crosses a boot
identity. Lease renewal is not a heartbeat, and lease expiry is not confirmed death. Agent prose,
message text, environment values, and untrusted pointer fields cannot choose identity, timestamps,
thresholds, acknowledgments, or results.

R4. **Bounded deterministic phi.** Normalize post-dispatch heartbeat timestamps by sorting,
deduplicating, ignoring pre-dispatch samples, and retaining at most the latest 100 positive
inter-arrival intervals. Nonfinite/negative time, `now < dispatch`, or a sample more than the policy's
5-second future-skew tolerance yields `evidence-error`; a sample within tolerance is clamped to `now`
rather than extending liveness into the future. With at least five intervals, compute population
standard deviation with a one-second floor and the exact score:

```text
delay = max(0, now - last_heartbeat)
tail = 0.5 * erfc((delay - mean) / (stddev * sqrt(2)))
phi = min(16, -log10(max(tail, 1e-16)))
```

Default suspicion is `phi >= 8.0`. All constants live in one validated `LivenessPolicy` and can be
explicitly overridden only by a trusted coordinator.

R5. **Exact cold start and Outcome compatibility.** With fewer than five intervals, `phi=null`.
Outcome projects legacy records exactly as today: a fixed heartbeat breach emits the existing reason
and `_record_terminal`; otherwise an absolute timeout breach emits its existing reason and terminal.
Only when neither legacy rule fires may additive phi suspicion or `evidence-error` appear. Adaptive
failure never suppresses a valid R31 terminal, missing dispatch time keeps its current skip behavior,
and `_is_stalled` or a byte-compatible adapter remains the sole Outcome terminal authority. Preserve
heartbeat-first dual-breach ordering, exact reasons, max timestamp, dispatch floor, no-budget opt-out,
malformed-record compatibility, page-once behavior, and R22 cascade. Team-execution uses the current
trusted lease TTL, normally 300 seconds, as a suspicion-only cold-start gap.

R6. **Suspicion precedes team terminal authority.** Phi or a team cold-start breach produces
suspicion only. Team `confirmed-stalled` requires three verified `reping-sent` events whose response
windows expired without a host-bound response or exclusively attributed progress. Claims, failed
sends, ambiguous sends, Git-only activity, and lease expiry never count or confirm death. Outcome has
no armed re-ping/team-confirmation path: it exposes additive suspicion while its unchanged legacy
adapter alone owns R31 terminalization. #357 never kills a process or frees a lease; Team maps a
verified confirmed result to the existing owner action.

R7. **Scoped Git activity is not resident progress by default.** Before each background Agent spawn,
capture a trusted baseline over the resident's approved unit `Files` paths through the existing
temp-index Git-tree mechanism. Derive the canonical digest from sorted `(path, mode, oid)` tuples. A
changed digest emits `scoped-activity-unattributed`; disjoint path declarations still do not prove
authorship, and this signal never updates `last_progress`, closes suspicion, suppresses artifactless,
or authorizes health, delivery, terminalization, or teardown. Upgrade to `artifact-progress` only
when a trusted exclusive-provenance receipt binds subject, lease/fence, paths, baseline/current
digests, observation interval, exclusive mutation custody, and the exact covered generation IDs.
For reachability generations, progress closes only a listed generation whose interval starts at or
after that generation's opened anchor and ends strictly after the later of its opened anchor and
latest matching `reping-sent` accepted time. An interval wholly before or straddling that boundary
closes nothing, and unlisted generations remain open. Artifactless closure retains its separate
cause/anchor rule. Shared worktrees, overlapping scopes, pointer epoch, mtime, chat, and prose are
insufficient. `chatty-artifactless` begins only after an explicit budget, defaulting to the trusted
lease TTL.

R8. **Idle notices acknowledge consumption only.** A trusted host idle signal becomes
`idle-notice`. When the host supplies an event ID, notice identity binds that ID to trusted
session/agent/dispatch identity; otherwise the first writer allocates the next subject-local notice
sequence under the run-ledger lock from normalized host metadata, never message text. The coordinator
appends `idle-ack` only after consuming that exact notice. A duplicate notice/ack converges
idempotently. `idle-ack` never makes a worker healthy, clears suspicion, or satisfies #351 delivery;
only exclusively attributed progress or a host-bound `reping-ack` covering the generation may refute
suspicion.

R9. **Re-ping requires a claimed intent and proven send.** Read-only `poll` returns a candidate and
`claim-reping` atomically appends `reping-intent`; the claim alone starts no timer and consumes no
attempt. A hook-owned `reping-sent` binds the claim, trusted accepted receipt, tool-use ID, recipient,
request digest, and accepted monotonic time; only this event counts and starts a response window.
Policy fixes `max_definitive_not_sent_retries_per_attempt=1`: retry ordinal 0 is the initial send and
ordinal 1 is its sole retry. Each atomic claim key binds subject, generation, liveness attempt, retry
ordinal, and the predecessor definitive-failure receipt (null only at ordinal 0); duplicate claims
converge with one winner and identical replay is idempotent. An accepted receipt at either ordinal
ends retry eligibility and projects one `reping-sent`. A definitive failure at ordinal 0 alone permits
ordinal 1; a definitive failure at ordinal 1 yields nonterminal `reping-delivery-blocked` plus operator
attention, does not count a liveness attempt, and cannot contribute to confirmation. An absent or
ambiguous receipt yields `reping-send-unresolved`/`evidence-error`, with no retry, timer, exhaustion,
or confirmation. `reping-ack` binds the sent event, host response correlation, and covered
generations. No silent loop, sleep, raw message persistence, or mutable queue is allowed.

R10. **Both production consumers are wired without changing terminal settlement.** Outcome's
`production_liveness_processor()` continues to invoke `outcome_liveness.harvest_liveness`, which
adapts the shared engine and retains `_record_terminal` plus R5's heartbeat-first compatibility.
Team-execution invokes one Saga-owned liveness event/poll CLI at renewal, host-return, dependency, and
B2 boundaries. The #357 `idle-notice` is nonterminal and remains distinct from #351's terminal
`dispatch.host-receipt.v1 kind=idle`, whose retry/DLQ settlement stays wholly owned by #351. Before
implementation, amend the issue's raw two-directory grep to a source-aware fleet-core/Saga/team-
execution conformance check.

R11. **Sibling ownership stays intact.** #351 owns dispatch settlement/DLQ/idempotent work retries;
#356 owns leases/renewal/write fencing; #355 owns bridge-write rejection/quarantine/orphan projection;
#358 owns stop/release/process/resident teardown. #357 only observes, scores, acknowledges, re-pings,
and maps confirmed results to existing owner actions.

R12. **Evidence errors fail safe without overriding Outcome compatibility.** For Team, a broken
run-fact chain, invalid subject/event, clock or boot mismatch, contradictory transition, missing or
invalid required host receipt, unknown schema/policy version, corrupt pointer, unsafe path, or
version-skewed fleet-core produces nonterminal `evidence-error` before health, progress, suspicion,
or confirmation; only a verified projection can produce `confirmed-stalled`. For Outcome, adaptive
evidence failure cannot suppress a valid legacy heartbeat/absolute terminal, and malformed legacy
records retain their current behavior. Evidence errors never confirm delivery or trigger teardown.

R13. **Release integrity is atomic.** From the merged #355 base, bump fleet-core 0.13.0 to 0.14.0,
Saga 0.100.0 to 0.101.0, and team-execution 2.19.0 to 2.20.0. Update all manifests,
marketplace rows, changelogs, minimum-version/drift guards, operator contracts, tests, and engineering
journal in the same PR. Refresh and reapprove exact increments if the base differs.

R14. **Every spawned worker has one canonical durable liveness subject.** Capture the baseline
immediately before each background Agent spawn. Immediately after the host returns the trusted agent
handle, append `subject-open` under the ledger lock after verifying the exact #351 manifest/spawn
tuple, trusted resident/host agent, current #356 lease/resource/token/boot, and baseline/path-set
digest. An identical replay is idempotent; drift is an error. Every later event carries `subject_id`
plus the exact closed identity fields, and append-lock lookup requires one matching `subject-open` and
valid predecessor. Reject missing, extra, unknown, cross-subject, cross-attempt, and cross-boot fields;
malformed stored history yields `evidence-error`, never implicit health.

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
                                                    - scoped activity/provenance
                                                    - notice/ack state
                                                                    |
                                           +------------------------+-------------------+
                                           |                                            |
                                 Outcome adapter                                team poll adapter
                                 unchanged R31 legacy                          claimed/proven sends
                                 terminal authority                            and action intents
                                           |                                            |
                                           v                                            v
                               R22 cascade/page once                       #351 settle / #358 owner
```

### Pure decision contract

The engine returns one closed `liveness_decision.v1` value:

```text
subject_id
classification: healthy | heartbeat-suspect | chatty-artifactless |
                scoped-activity-unattributed | reping-required |
                reping-send-unresolved | reping-delivery-blocked |
                confirmed-stalled | evidence-error
phi: number | null
sample_count
last_heartbeat
last_progress
pending_notice_ids[]
reping: {generation_id, cause, liveness_attempt, retry_ordinal, claim_key} | null
terminal_authority: none | team-reping-confirmed
reason_code
evidence_refs[]
```

Outcome terminalization stays outside this decision vocabulary: its adapter first projects the exact
legacy records and applies fixed heartbeat, then absolute timeout, through `_is_stalled` and
`_record_terminal`. Only when neither legacy rule fires does the engine contribute additive
suspicion/evidence error; adaptive failure never suppresses a valid R31 terminal. Team evaluates a
verified projection before health, progress, suspicion, or confirmation. Cold start and phi are
suspicion only; `scoped-activity-unattributed` and `idle-ack` close no suspicion. Team
`confirmed-stalled` requires three proven sends and expiration of the third response window.

### Team liveness fact contract

Every team fact uses `schema=run_fact.v1`, `kind=liveness`, #351's `subplot_id`, and a closed event:

| event | required trusted fields | invariant |
|---|---|---|
| `subject-open` | exact `liveness.subject.v1` key; current lease/token/boot; manifest/spawn tuple; path-set and baseline digest | atomically verifies trusted sources; identical replay is idempotent, drift is error |
| `heartbeat` | exact subject fields, monotonic time, host evidence ref/digest | host receipt or runtime event, never agent prose |
| `scoped-activity-unattributed` | exact subject fields, baseline/current scoped digest, interval | records Git activity only; closes no suspicion and updates no progress |
| `artifact-progress` | exact subject fields, scoped digests, interval, exclusive-provenance receipt, covered generation IDs | progress only when receipt proves exclusive subject mutation custody; reachability closure is interval- and name-bound |
| `idle-notice` | exact subject fields, host event ID or allocated sequence, normalized signal ref/digest, observed time | one notice identity/digest; no message text |
| `idle-ack` | exact subject fields, notice ID, ack ref/digest, observed time | notice must exist; closes delivery only |
| `reping-intent` | exact subject fields, generation ID/cause/anchor, liveness attempt, retry ordinal, predecessor failure receipt, claim key | atomic claim only; no count or timer; ordinal 0 initial and ordinal 1 sole retry |
| `reping-sent` | matching claim, trusted receipt, tool-use ID, recipient, request digest, accepted monotonic time | only accepted send counts and starts response window |
| `reping-send-failed` | matching claim and trusted definitive-not-sent receipt | ordinal 0 permits ordinal 1; ordinal 1 becomes nonterminal delivery-blocked/operator attention; neither counts |
| `reping-ack` | matching sent event, response/correlation ref, covered generation IDs | host-bound response closes only named generations |

Transition validation and append occur under the run ledger's one exclusive lock. Every event repeats
the exact closed identity fields; lookup requires exactly one matching `subject-open`, correct
subplot/clock/predecessor, and rejects missing, extra, unknown, cross-subject, cross-attempt, or
cross-boot data. Reads use one verified snapshot and create no files. Raw message/prompt/output text
is never stored.

A generation is cause-specific and stable:
`generation_id = sha256(canonical_json({subject_id, cause, anchor_ref}))`. Heartbeat-absent anchors to
`subject-open`; heartbeat-gap/phi anchors to the latest accepted heartbeat or `subject-open` when
none; artifactless anchors to the latest exclusively attributed progress or `subject-open`; and
idle-unacknowledged anchors to the exact notice. Signal families do not rotate each other. A heartbeat
closes prior absent/gap/phi generations. Exclusive progress retains the existing artifactless closure
rule, but closes a reachability generation only when its trusted receipt lists that generation, its
interval starts at or after the generation's opened anchor, and its interval ends strictly after
`max(generation_opened_anchor, latest_matching_reping_sent_accepted_time)`. Before-boundary and
straddling intervals close no reachability generation, and a receipt closes only the generations it
names. A host-bound response closes explicitly covered generations; idle ack closes delivery only;
unattributed activity closes nothing. Recurrence requires the cause anchor to change, and every intent
names one generation and cause with attempts counted per generation.

### Poll cadence

No daemon is added. Team-execution polls:

1. capture the approved-path baseline immediately before every background Agent spawn;
2. append `subject-open` immediately after the host returns the trusted agent handle;
3. poll at every #356 renewal boundary, whenever the host returns Agent/SendMessage or emits a
   trusted idle/terminal signal, before unblocking a dependent segment, and before B2 review;
4. atomically claim a returned re-ping candidate before `SendMessage`;
5. bind the pre-call tool-use ID, recipient, claim, and request digest in the hook, then record a
   host-owned accepted or definitive-not-sent receipt after the call; and
6. record only a host-bound correlated response as `reping-ack`.

If the coordinator cannot poll while one tool call is in flight, #356 may expire authorization and
block the next mutation; #357 does not pretend it can preempt that call.

---

## Key Technical Decisions

- **KTD1 - fleet-core owns the algorithm; Saga owns coordinator state adapters.** Team-execution
  already depends on Saga's manifest/run-fact substrate, while fleet-core is the installed code bus.
  Moving the Outcome ledger or duplicating parsers would enlarge the issue without improving truth.
- **KTD2 - Outcome legacy authority and Team adaptive authority are separate.** Threshold 8 means a
  modeled tail probability of at most 1e-8, but phi never owns Outcome terminalization. Outcome first
  applies its exact fixed heartbeat then absolute-timeout rules; only Team can reach
  `terminal_authority=team-reping-confirmed` after three verified send windows.
- **KTD3 - sparse/adaptive failure preserves the old Outcome rule.** Five complete intervals are
  required for phi. Missing/corrupt adaptive inputs never suppress a valid legacy R31 terminal;
  malformed records, missing dispatch, absolute timeout, and no-budget behavior remain unchanged.
- **KTD4 - Git digest proves scoped activity, not authorship.** Pointer epoch, whole-tree change,
  mtime, chat, disjoint path declarations, and scoped digest change are insufficient for progress.
  Only a trusted exclusive-provenance receipt upgrades activity to resident progress.
- **KTD5 - idle acknowledgment is consumption evidence only.** It never becomes a worker-output ACK
  and therefore cannot bypass #351 completeness/settlement.
- **KTD6 - facts, not queues.** Notice, ack, cause-specific generations, claims, proven sends,
  definitive failures, and responses are append-only facts; pending work and attempt counts are
  projections from a verified snapshot.
- **KTD7 - detection and action remain separate.** #357 may request a re-ping and report the owning
  reclaimer. #358 later makes stop/release/teardown non-skippable.
- **KTD8 - polling is explicit and source-inventoried.** With no daemon, every required boundary must
  name a production caller and fail conformance if it becomes docs-only.
- **KTD9 - lease and liveness remain distinct.** Lease state controls mutation authority; it is
  neither heartbeat evidence nor proof of death.
- **KTD10 - idle consumption and worker reachability remain distinct.** `idle-ack` closes notification
  delivery only; a generation-bound `reping-ack` or exclusively attributed progress may close worker
  suspicion.
- **KTD11 - re-ping is claimed, sent, then proven.** Only the atomic claim winner may call
  `SendMessage`; only a hook-bound trusted accepted receipt counts or starts a timer. Definitive
  non-send permits exactly one same-attempt retry (`max_definitive_not_sent_retries_per_attempt=1`),
  with ordinal- and predecessor-bound claims. A second definitive failure becomes nonterminal
  delivery-blocked/operator attention, while absent/ambiguous receipt fails closed without retry or
  exhaustion.

These decisions are recorded under `{#fleet-shared-liveness-357}` in
`docs/engineering-journal/DECISIONS.md` before implementation starts.

---

## Implementation Units

### U1. Pure fleet-core liveness engine

**Goal:** Implement normalized observations, bounded phi math, signal fusion, decision vocabulary,
and evidence errors without I/O.

**Requirements:** R1, R3-R7, R12, R14.

**Dependencies:** #356 merged; no unit dependency.

**Files:** `plugins/fleet-core/scripts/fleet_commons/liveness_engine.py` (new),
`tests/test_liveness_engine.py` (new).

**Approach:** Use frozen dataclasses and closed enums. Validate finite nonnegative times and policy
bounds. Compute `delay = max(0, now - last_heartbeat)`,
`tail = 0.5 * erfc((delay - mean) / (stddev * sqrt(2)))`, and
`phi = min(16, -log10(max(tail, 1e-16)))` over the latest 100 sorted, deduplicated positive
post-dispatch intervals, with population standard deviation floored at one second. Zero through four
intervals return `phi=null`; team cold start uses the trusted current lease TTL as suspicion only.
Lease renewal/expiry is never converted to heartbeat/death evidence. The closed result vocabulary
includes unattributed scoped activity and unresolved sends, while terminal authority is `none` or
`team-reping-confirmed`; Outcome legacy terminals remain outside the engine result.

**Test scenarios:** Steady 10-second intervals stay below threshold; a 100-second silence after the
same series crosses. Zero through four intervals return `phi=null`; team TTL cold-start breach is
suspicion only. Threshold just below/at/above 8, zero variance, duplicate/out-of-order beats,
within/beyond future-skew tolerance, clock rollback, pre-dispatch beats, maximum-window truncation,
nonfinite values, renewal without heartbeat, expiry without confirmation, unattributed Git change,
and a boot change are deterministic. Stable zero-heartbeat and artifactless generations remain fixed
until their cause-specific anchors change; unrelated signal families do not rotate them. Property
cases assert phi is finite, nonnegative, monotonic in elapsed time for a fixed sample, and invariant
to input order/duplicates.

**Verification:** No I/O at import/evaluate; the original paper's probability meaning and all plan
constants are represented in tests and docs.

### U2. Backward-compatible Outcome adapter

**Goal:** Keep the production `harvest_liveness` API and every R31 side effect while replacing local
threshold calculation with the shared engine.

**Requirements:** R1-R6, R10-R12.

**Dependencies:** U1.

**Files:** `plugins/saga/scripts/outcome_liveness.py`, `plugins/saga/scripts/outcome.py`,
`tests/test_outcome_liveness.py`, `tests/test_outcome_integration.py`.

**Approach:** Load `liveness_engine` through Saga's fleet shim, but keep `_is_stalled` or a
byte-compatible adapter as the sole terminal authority. Project legacy records exactly as today:
fixed heartbeat breach first, otherwise absolute timeout, with existing reason and
`_record_terminal`. Only after neither fires may additive phi suspicion/evidence error be returned.
Outcome has no armed re-ping transport or Team-style `confirmed-stalled`. Preserve public functions,
malformed-record behavior, and existing `stalled`/`cascade_paused` keys.

**Test scenarios:** Every current test remains unchanged/green. Add rich steady/stalled histories,
phi suspicion without adaptive terminalization, corrupt engine/skew input alongside a valid legacy
terminal, malformed legacy input, and real `production_liveness_processor` integration. Add an
explicit regression where heartbeat and absolute timeout are both breached and heartbeat retains
precedence and exact reason text.

**Verification:** A node with no budget remains immortal; missing dispatch still skips; sparse fixed
gap, malformed input, absolute timeout, idempotent page, max timestamp, dispatch floor, and R22
cascade are byte/semantic compatible. Adaptive failure cannot suppress a valid R31 terminal.

### U3. Canonical liveness facts and poll CLI

**Goal:** Extend #351's run-fact ledger with one closed liveness family and expose append/poll verbs
used by team-execution.

**Requirements:** R2-R3, R6, R8-R10, R12, R14.

**Dependencies:** #351 merged; U1.

**Files:** `plugins/saga/scripts/run_ledger.py`, `plugins/saga/scripts/liveness_events.py` (new),
`tests/test_run_ledger.py`, `tests/test_liveness_events.py` (new).

**Approach:** Add `kind=liveness`, the exact closed `liveness.subject.v1` key/ID derivation, typed fact
builders, and lock-scoped subject/predecessor validators. Provide `subject-open`, `heartbeat`,
`scoped-activity-unattributed`, `artifact-progress`, `notice`, `ack`, `claim-reping`, `reping-sent`,
`reping-send-failed`, `reping-ack`, and read-only `poll` commands. Cause-specific generations use the
specified subject/cause/anchor digest and close only through their allowed signals. `poll` verifies
the chain once and returns a candidate without mutation. `claim-reping` creates an intent only;
separate trusted send/failure receipts determine counting, timer start, retry, and recovery. Freeze
the policy at `max_definitive_not_sent_retries_per_attempt=1`; derive ordinal-0 and ordinal-1 claim
keys from subject, generation, liveness attempt, retry ordinal, and predecessor failure receipt under
the append lock. Accepted send, exhausted definitive failure, and unresolved send are mutually
exclusive projections, and replay never creates a second fact or eligibility path.

**Test scenarios:** Full happy transition from subject-open through heartbeat/phi generation and three
intent/sent/expired windows confirms. Verify exact canonical ID, subject-open source checks,
idempotent replay/drift, stable absent/artifactless generations, family independence, idle ack only
closing notice delivery, and exclusive progress closing only allowed generations. Every event rejects
missing/extra/unknown/cross-subject/cross-attempt/cross-boot fields and wrong receipt identity. Claim
without send starts no timer. A definitive ordinal-0 failure exposes exactly ordinal 1 for the same
liveness attempt and requires the exact predecessor failure receipt; competing ordinal-1 claims have
one winner and identical replay is idempotent. Acceptance at ordinal 0 or 1 creates exactly one sent
window and ends retry eligibility. A definitive ordinal-1 failure yields nonterminal
`reping-delivery-blocked` with operator attention, zero liveness-attempt count, and no confirmation
authority. An unresolved ordinal 0 or 1 never retries, counts, or starts a window. Team corruption
precedes any health decision, and confirmation occurs only after the third proven-send window expires.

**Verification:** Two concurrent writers cannot create duplicate attempts; a read never heals or
appends; missing/contradictory evidence returns nonterminal `evidence-error`; only `reping-sent`
increments the per-generation count or starts a window.

### U4. Attribution-safe artifact progress

**Goal:** Reuse artifact-pointer snapshot custody to detect scoped activity while requiring exclusive
provenance before attributing resident progress.

**Requirements:** R7, R12.

**Dependencies:** U1, U3.

**Files:** `plugins/team-execution/skills/team-execution/scripts/artifact_pointer.py`,
`plugins/team-execution/skills/team-execution/references/artifact-pointers.md`,
`tests/test_team_execution_pointers.py`, `tests/test_team_execution_liveness.py` (new).

**Approach:** Capture the baseline before spawn. Add an observation command that validates trusted
repo-relative path specs, creates a temporary index tree, enumerates only declared paths with fixed
Git argv, and compares canonical baseline/current digests. A change defaults to
`scoped-activity-unattributed`, even for disjoint scopes, and closes no suspicion. Upgrade to
`artifact-progress` only with a trusted receipt binding subject, lease/fence, paths, both digests,
interval, and exclusive mutation custody. Unchanged polling creates no durable pointer ref; use
existing bounded snapshot-ref garbage collection without changing `ArtifactPointer` or delivery
meaning. Require the receipt to list covered generation IDs. Apply the opened-anchor/latest-matching-
accepted-send interval test independently to each listed reachability generation; do not infer
coverage from subject, cause, or time alone. Keep artifactless closure on its existing rule.

**Test scenarios:** Own-path change without provenance is unattributed and updates no progress;
disjoint declarations do not upgrade authorship; trusted exclusive provenance upgrades the exact
interval. Unrelated paths and same-digest epochs do not advance, and unchanged polling leaves no
durable ref. Untracked/deleted own files are scoped activity only absent provenance. Overlap,
traversal, absolute/symlink escape, missing baseline, stale/corrupt pointer, sparse checkout, and Git
failure fail safe. A real-Git two-worker fixture proves unattributed activity closes no generation.
For reachability closure, test a wholly-before interval, an interval straddling the opened anchor or
latest accepted-send time, and an interval ending exactly at the boundary all close nothing. An
interval starting at or after the opened anchor and ending strictly after the latest boundary closes
the listed generation only; an otherwise eligible unlisted sibling remains open. Missing covered
generation IDs fail closed, while artifactless closure retains its independent existing behavior.

**Verification:** Existing pointer suite remains green; Git digest alone never changes
`last_progress`, health, suspicion, artifactless, delivery, terminal, or teardown authority.

### U5. Team-execution production protocol and conformance

**Goal:** Make liveness polling and notice acknowledgment executable at every real resident boundary,
with no second implementation.

**Requirements:** R1-R3, R6-R12, R14.

**Dependencies:** U2-U4.

**Files:** `plugins/team-execution/skills/team-execution/scripts/liveness_protocol.py` (new),
`plugins/team-execution/skills/team-execution/SKILL.md`,
`plugins/team-execution/skills/team-execution/references/liveness-protocol.md` (new),
`plugins/team-execution/skills/team-execution/references/worker-manifest.md`,
`plugins/saga/hooks/liveness_reping_hook.py` (new),
`plugins/saga/hooks/hooks.json`,
`plugins/saga/references/liveness-consumer-sites.md` (new),
`tests/test_team_execution_liveness.py` (new),
`tests/test_liveness_reping_hook.py` (new),
`tests/test_liveness_consumer_conformance.py` (new).

**Approach:** Model the packaged adapter's Saga resolution and preflight on
`dispatch_settlement_adapter.py`. Document and implement the sequence baseline -> Agent spawn ->
`subject-open` -> poll at renewal/host-return/dependency/B2 boundaries -> atomic claim -> hook-bound
`SendMessage` -> accepted/definitive-not-sent host receipt -> correlated `reping-ack`. The hook binds
the pre-call tool-use ID, recipient, claim, and request digest, and creates a host-owned completion or
failure receipt after the call without persisting raw message text. Recovery treats accepted receipt
as sent, ordinal-0 definitive non-send as the sole same-attempt retry, ordinal-1 definitive non-send as
nonterminal delivery-blocked/operator attention, and absent/ambiguous receipt as unresolved with no
retry/timer/exhaustion. Inventory every consumer, writer, poll boundary, action owner, fallback, and
test; reject dead wiring, missing subjects, or direct unclaimed/unproven sends.

**Test scenarios:** Chatty/no-progress, silent/no-heartbeat, unattributed scoped activity,
exclusive-provenance progress, unacked/acked/duplicate notice, claim without send, accepted send,
definitive ordinal-0 failure followed by the sole retry, ordinal-1 delivery-blocked/operator attention,
ambiguous crash no-retry, wrong receipt identity, one concurrent initial-claim winner, and one
concurrent retry-claim winner. Acceptance on either ordinal ends retry eligibility and replay is
idempotent. Three accepted, unacknowledged sends confirm only after the third response window;
failed, blocked, and unresolved sends never contribute. `idle-ack` does not clear suspicion; #351
terminal idle remains distinct from #357 notice; protocol/hook tests prove commands and host receipts
resolve to production functions.

**Verification:** One source implementation exists in fleet-core; both consumers and all poll/send
boundaries are executable and inventoried. The issue's acceptance check is amended to cover
fleet-core, both adapters, cause-specific generations, subject validation, send-proof hooks, and the
unattributed/provenance distinction.

### U6. Release surfaces and full gate

**Goal:** Publish the shared engine and both adapters coherently from the refreshed Wave 3 baseline.

**Requirements:** R10-R13.

**Dependencies:** U2-U5.

**Files:** `plugins/fleet-core/.claude-plugin/plugin.json`,
`plugins/saga/.claude-plugin/plugin.json`, `plugins/team-execution/.claude-plugin/plugin.json`,
`.claude-plugin/marketplace.json`, three plugin changelogs,
`tests/test_saga_plugin.py`, `tests/test_team_execution_plugin.py`, version/drift tests,
`docs/engineering-journal/DECISIONS.md`, and operator references.

**Approach:** Confirm the branch retains merged #355 as a parent and the expected fleet-core 0.13.0,
Saga 0.100.0, and team-execution 2.19.0 base. Bump to fleet-core 0.14.0, Saga 0.101.0, and
team-execution 2.20.0; update required fleet-core compatibility and release narratives. Run
installed-plugin resolution so both shims prove the same engine bytes/version.

**Test scenarios:** Local and installed layouts resolve the canonical module; an old/missing
fleet-core fails armed liveness with named diagnostic; marketplace/manifests/changelogs agree; an
injected duplicate engine or dead consumer row fails conformance.

**Verification:** Full gate and release parity are green from a clean branch.

---

## Requirement Coverage

| requirement | units | primary proof |
|---|---|---|
| R1-R3 | U1-U3, U5 | single implementation and verified normalized event snapshots |
| R4-R6 | U1-U3 | math/property boundaries, unchanged Outcome authority, proven-send confirmation |
| R7 | U1, U4-U5 | Git activity remains unattributed absent exclusive provenance |
| R8-R9 | U3, U5 | stable generations plus claim/send/failure/ack crash and concurrency matrix |
| R10 | U2, U5 | real legacy-authoritative Outcome processor and executable Team protocol |
| R11-R12 | U2-U5 | sibling-boundary and evidence-error conformance |
| R13 | U6 | installed-resolution and release-surface parity |
| R14 | U1, U3-U5 | pre-spawn baseline, idempotent subject-open, and missing-subject rejection |

---

## Scope Boundaries

### In scope

- Pure fleet-core liveness scoring and decision vocabulary.
- Outcome adapter preserving R31 behavior.
- Team liveness facts/polling, scoped activity observation, provenance-qualified progress, idle ack,
  and bounded re-ping intent.
- Host hook receipts proving accepted/definitively-unsent re-pings and fail-closed recovery.
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
| noisy cadence false-stalls live work | lost work and bad cascade | min samples, phi 8, cause-stable generations, three proven-send windows; Outcome legacy authority unchanged |
| scoped Git change credits wrong worker | chatty worker appears productive | digest is unattributed by default; only exclusive-provenance receipt upgrades; real two-worker Git test |
| acknowledgment becomes delivery authority | missing outputs pass | ack only proves notice consumption; #351 manifest remains sole delivery ACK |
| lease state is mistaken for liveness | authorized but dead worker appears healthy, or expired lease appears dead | conformance proves renewal emits no heartbeat/progress and expiry alone never confirms |
| duplicate or unproven re-ping send | message storm, premature timeout, ambiguous attempts | ordinal/predecessor-bound atomic claim; one definitive retry; accepted ends eligibility; blocked/unresolved sends do not retry/count/time |
| subject identity aliases or drifts | cross-attempt evidence corrupts health | exact canonical subject key/ID; atomic source validation; closed fields on every event |
| unrelated signal rotates suspicion | retries reset or exhaust incorrectly | cause/anchor generation IDs; cause-specific closure and recurrence tests |
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

The event-flow validator independently traces subject-open, heartbeat/activity/provenance,
notice/ack, cause-specific generations, atomic re-ping claim, accepted/failed/unresolved send,
response, and confirmation and proves no event grants output or teardown authority.
The scenario validator covers `phi=null` for zero through four intervals, exact threshold and
monotonicity, TTL cold-start suspicion, valid Outcome terminal despite corrupt phi, heartbeat-first
dual breach, malformed legacy compatibility, renewal/expiry separation, exact subject validation,
stable/family-independent generations, same-digest epoch, unattributed/provenance activity,
idle-ack non-refutation, claim/no-send/failure/ambiguous recovery, concurrent claim winner, wrong
receipt rejection, ordinal-0 sole-retry eligibility, ordinal-1 delivery-blocked/operator attention,
accepted-send retry cutoff, unresolved no-retry, retry replay/concurrent-winner idempotency,
before/straddling/equal-boundary reachability non-closure, strict-after named-generation closure,
unlisted-sibling non-closure, unchanged artifactless closure, third-proven-window confirmation,
terminal/nonterminal idle separation, and Team corruption-before-health.
Both use gpt-5.6-terra medium; the four high-judgment reviewers use gpt-5.6-sol high.

Manual evidence includes the policy/math table with computed phi values, one real-Git two-worker run
showing unattributed activity, one trusted exclusive-provenance upgrade, one unacked notice producing
exactly one claimed and receipt-proven re-ping, one ack closing only notice delivery, and one
production Outcome tick preserving legacy terminal/page-once/cascade behavior despite adaptive error.

The prior document review and Verified Workflow approval predate merged #355's release metadata. This
baseline refresh must update the existing `{#fleet-shared-liveness-357}` journal anchor, rerun
`/doc-review` to zero P0-P3 findings, and regenerate and validate the exact workflow candidate,
digest, and role/lens/profile receipts. Any workflow semantic or digest change requires operator
reapproval. Before PR creation, confirm the merged-#355 ancestry and run focused/full pytest, Ruff,
mypy, Bandit, release parity, marketplace sync, diff guard, event-flow/scenario validators, and code
review. Close #357 and reconcile board/outcome state only after merged-SHA and updated `origin/main`
proof.

### Round 2 closure mapping

| closure ID | plan resolution | primary proof |
|---|---|---|
| `issue-357.r31-terminal-authority` | R5-R6/R12, KTD2-KTD3, U2 keep legacy Outcome precedence and forbid adaptive suppression | valid terminal with corrupt phi; dual-breach/malformed regressions |
| `issue-357.reping-send-proof` | R9, KTD11, U3/U5 add intent/sent/failed receipts, hook binding, and fail-closed recovery | claim/no-send/failure/ambiguous/concurrent/wrong-receipt tests |
| `issue-357.suspicion-generations` | cause/anchor stable IDs and cause-specific closure are defined in HTD, KTD6, U1/U3 | stable absent/artifactless and family-independence transition tests |
| `issue-357.subject-identity-schema` | R3/R14 and U3 define canonical closed identity and lock-scoped source/event validation | canonical ID, replay/drift, missing/extra/cross identity tests |
| `issue-357.progress-attribution` | R7, KTD4, U1/U4/U5 distinguish unattributed Git activity from proven progress | real-Git no-close test plus exclusive-provenance upgrade |
| `issue-357.reping-definitive-failure-retry-contract` | R9, KTD11, U3/U5 freeze one ordinal- and predecessor-bound definitive-not-sent retry, then nonterminal delivery-blocked attention | ordinal 0/1 eligibility, accepted cutoff, exhausted failure, unresolved, replay, and concurrent-winner tests |
| `issue-357.progress-reachability-closure` | R7, HTD generation transitions, U3/U4 bind named reachability closure to a strictly post-anchor/post-send exclusive-provenance interval | before, straddling, equal-boundary, strict-after, named-only, and artifactless-regression tests |

---

## Failure Modes and Stop Conditions

- Phi or adaptive failure suppresses/changes a valid legacy Outcome terminal, or Outcome gains Team
  re-ping confirmation: stop; restore `_is_stalled`/byte-compatible terminal authority.
- A no-budget Outcome leaf becomes killable, sparse history skips the old fixed fallback, or absolute
  timeout reason/idempotency/cascade changes: stop as a P0/P1 compatibility defect.
- Message text, prompt content, agent-provided timestamps, or raw pointer locator selects policy or
  produces an ack/progress fact: stop at the trust boundary.
- Whole-tree/scoped change, disjoint path declaration, mtime, pointer epoch, or another worker's path
  counts as progress without trusted exclusive provenance: stop and emit unattributed activity.
- Idle ack or artifact pointer satisfies #351 delivery/output completeness: stop; contracts merged
  incorrectly.
- Poll reads append/heal, subject/event transitions validate outside the append lock, identity fields
  are open or drift, causes rotate one another's generations, or a broken chain becomes healthy: stop
  as evidence-integrity defect.
- A claim starts a timer/count, an unproven or ambiguous send is retried, a definitive non-send
  consumes an attempt, more than one definitive retry is eligible, a claim omits its ordinal or
  predecessor receipt, accepted delivery remains retryable, an exhausted failure is terminal, or
  fewer than three proven send windows confirm: stop as re-ping integrity defect.
- Exclusive progress closes an unlisted reachability generation, closes from an interval before or
  straddling its opened/latest-send boundary, treats equality as sufficient, or changes the separate
  artifactless closure rule: stop as provenance-ordering defect.
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
