---
title: Lease-safe runtime continuity wave 3 - orphan runner containment
type: feat
status: active
date: 2026-07-15
origin: docs/plans/plugin-fleet-ideation-2026-07-03/survivors/T15.json
deepened: 2026-07-15
---

# Lease-safe runtime continuity wave 3 - orphan runner containment

## Summary

Implement issue #355 after #356 by applying the fleet lease token to the two verified bridge-evidence
seams: agy delegation and Saga engine dispatch. Superseded writes are rejected without touching live
evidence, expired-unsuperseded writes are preserved in a bounded quarantine, late writes after close
are quarantined and flagged, and a derived orphan projection identifies stalled and artifactless
runs without creating another lease, heartbeat, or mutable status system.

Destination is merge. Execution uses an operator-approved Verified Workflow. Root owns
implementation, Git, integration, PR, merge, issue closure, and board reconciliation. Agent-lens
roles independently review or validate and authorize no repository mutation.

---

## Problem Frame and Current State

The issue is requirements-ready but its proposed mechanism predates #356. Live code now proves that
`plugins/agy/scripts/agy_delegate.py:1930` builds `run-lease.json` only as a terminal run snapshot;
it is not present as a renewable authority while agy runs. Converting that snapshot into a second
lease system would contradict both the issue's non-goal and the outcome's #356 dependency.

#356 instead supplies the canonical fleet-core broker, boot-aware TTL, persistent per-resource fencing
heads, and four derived token dispositions: current, expired, closed/released, and superseded. #355
consumes those dispositions at evidence-acceptance boundaries and records forensic outcomes; it does
not reimplement acquisition, renewal, or generic delegated file-tool fencing.

Five production functions form the current acceptance boundary:

| seam | live function | current behavior |
|---|---|---|
| agy live patch | `agy_delegate.apply_patch_to_live_repo` (`plugins/agy/scripts/agy_delegate.py:1223`) | applies a derived patch to the live repository with no lease check |
| agy durable mirror | `agy_delegate._mirror_to_audit_store` (`plugins/agy/scripts/agy_delegate.py:330`) | overwrites result/receipt mirrors and suppresses write failures |
| Saga claimed manifest | `engine_dispatch.record_dispatch_manifest` (`plugins/saga/scripts/engine_dispatch.py:1435`) | overwrites common-dir and audit-store manifests with no lease check |
| Saga adjudicated manifest | `engine_dispatch.adjudicate_manifest` (`plugins/saga/scripts/engine_dispatch.py:1463`) | overwrites the same logical evidence after read-modify-write with no fence |
| shared audit mirror | `audit_store.mirror_result`, `mirror_receipt`, and `mirror_manifest` (`plugins/fleet-core/scripts/fleet_commons/audit_store.py:194-208`) | atomic per-file replacement, but last writer wins |

The agy bundle under `.claude/agy/runs/<run_id>` remains local forensic material. The external engine
runs in its disposable clone and does not call the Python evidence writer directly. The guarded
acceptance points are therefore live patch application, trusted manifest publication, and durable
mirroring. Terminal bundle files still record what happened even when live acceptance is denied.

`plugins/saga/scripts/outcome_liveness.py:35-142` already derives fixed-budget heartbeat stalls from
the outcome ledger. #355 may adapt that evidence into an orphan projection, but issue #357 owns the
future shared phi-accrual/artifact-progress/idle-ack liveness engine. Issue #358 owns generic process,
resident-teammate, and all-terminal-path teardown. #355 only flags the owner-specific reclaim action.

---

## Traceability and Dependencies

- **Parent outcome/spec:** `docs/outcomes/lease-safe-runtime-continuity/proposal.md` and subplot
  `sub-355` in `docs/outcomes/lease-safe-runtime-continuity/outcome-spec.json`.
- **Source issue:** `infiquetra/infiquetra-claude-plugins#355`; the plan preserves its published
  selector names while replacing its stale `run-lease.json` authority assumption with merged #356.
- **Hard upstream:** #356 must be merged and its exact fleet-core token/resource-head API refreshed
  into this plan before implementation. #350 precedes #356 and is therefore transitive, not another
  direct dependency.
- **Delivery serialization:** #357 and #358 are semantically parallel after #351/#356, but all three
  Wave 3 leaves change shared Saga/fleet-core release surfaces and merge serially from refreshed main.
- **Downstream unlocks:** the Claude coordination child of #579 consumes #355 directly; #353 consumes
  #355 plus #351/#357/#358; Codex parity and cross-runtime acceptance follow those contracts.
- **External prerequisites:** none. No deployment, credential change, production-data access, or
  named human specialist is required for this repository PR.

| published issue acceptance | plan contract | primary executable evidence |
|---|---|---|
| superseded lease write rejected while the current write persists | R3, R4, R7; U1, U3, U4 | `superseded_lease_rejected`, byte-preservation checks, two-process retry race |
| expired lease write is quarantined instead of accepted | R5, R8; U2-U4 | `expired_lease_quarantined`, digest round-trip, at/above-limit rejection |
| stalled or artifactless run is flagged | R10, R11; U5 | `stalled_or_empty_flagged`, explicit output-contract fixture, no-mutation assertion |
| late writer after close remains distinct | R6, R9; U2, U5 | `late_writer_after_close`, terminal-seal mutation and classification proof |
| agy and outcome liveness behavior does not regress | R7; U3, U5, U6 | existing agy bundle/lease suites and R31 outcome-liveness tests |
| repository quality gates pass | R12, R13; U6 | focused selectors, full pytest, Ruff, mypy, Bandit, release parity, diff check |

---

## Requirements

R1. **Reuse the #356 authority.** Every armed agy or Saga bridge run uses #356's fleet-core lease,
resource head, renewal, and token classification. `run-lease.json`, a manifest field, environment
input, or caller-supplied token is never accepted as authority and no second lease/heartbeat registry
is created.

R2. **Stable logical resource identity.** An agy write-capable run requires a bounded stable
`lease_resource_key` supplied as a trusted outer coordinator/CLI parameter; retries use the same key.
The key is validated before dispatch and is never accepted from the delegation envelope, external
engine output, prompt text, environment, or terminal bundle. Read-only/one-shot runs may default to
their unique run ID. Saga uses its authoritative `execution_id` plus `bridge_run_key`. Resource
references include plugin, canonical repository identity, and logical key, not raw prompts or
arbitrary filesystem paths.

R3. **Atomic write fencing.** Extend the broker with a secure resource-scoped guard lock. Grant,
supersede, and guarded evidence commit take the same per-resource lock before the registry lock;
multi-resource operations take resource locks in canonical digest order. The guard reclassifies the
token under the registry lock, releases the registry lock, and holds the resource lock across the
short live mutation. A retry cannot supersede between verification and commit, while unrelated
resources can still acquire or renew.

R4. **Superseded writes are rejected.** A token different from the persistent resource head returns
the typed `ORPHAN_WRITE_BLOCKED` disposition. The live patch, manifest, audit mirror, and current
resource head remain byte-for-byte unchanged. The trusted coordinator emits a write-once forensic
event; external-engine prose cannot select or override this disposition.

R5. **Expired-unsuperseded writes are quarantined.** A token equal to the resource head with a
matching derived-expired lease never lands in the live target. The trusted adapter writes the proposed
payload and a manifest to a mode-0600, content-addressed quarantine under the existing machine-local
delegation audit root, then emits `EXPIRED_LEASE_QUARANTINED`. If quarantine cannot commit, live
evidence remains untouched, the original bundle remains available, and the operation fails loudly as
`QUARANTINE_FAILED`; it never falls through to acceptance.

R6. **Closed late writes stay distinct.** A token equal to the resource head with no live lease is
closed/released. A subsequent write is quarantined with `LATE_WRITE_AFTER_CLOSE`, and the derived
orphan projection classifies it separately from a mid-run stall or expired write. A closed token is
never silently treated as merely unknown.

R7. **Current writes preserve compatibility.** A nonexpired token equal to the resource head commits
through the existing agy patch, manifest-store, and audit-store paths. Existing result schemas,
manifest adjudication, output completeness, bridge receipts, outcome R31 terminals, and successful
non-orphan behavior remain byte/semantics compatible except for additive token/forensic references.

R8. **Quarantine is bounded and tamper-evident.** The quarantine path is derived only from canonical
resource/token/payload digests. The payload limit reuses agy's existing `MAX_OUTPUT_BYTES` semantics:
payloads strictly smaller than 128 MiB are accepted and payloads at or above 128 MiB fail closed and
remain in their source bundle. Payload files are write-once, manifest digests cover bytes and
normalized metadata, a commit marker publishes last, duplicates converge by digest, conflicting
metadata is rejected, and symlink/ownership/mode checks reuse #356 hardening.

R9. **Close seals expose bypassed late mutation.** At authoritative bridge close, the trusted adapter
writes one immutable generation-scoped seal containing the supported artifact contract and bounded
digests. A later scan compares only the newest sealed generation when no later resource head exists;
a valid successor generation makes older seals historical instead of false late-write alarms. A
changed current seal emits a `late-write-after-close` candidate even when the writer bypassed a
guarded API. Missing/corrupt seals required for a terminal generation are evidence errors, not passing
scans; intermediate claimed manifests do not require a seal.

R10. **Orphan candidates are derived on read.** A shared fleet-core projector combines broker
inspection, write-once orphan events, close seals, audit-store artifacts, agy terminal snapshots, and
an adapter over existing outcome heartbeat/terminal evidence. It classifies `stalled`,
`empty-artifacts`, `expired-write-quarantined`, `superseded-write-blocked`, and
`late-write-after-close`; it stores no mutable runner status or queue.

R11. **Flagging does not invent destructive authority.** The thin `reap_orphans.py scan` command emits
deterministic candidate records with the owning reclaimer (`lease-sweep`, `agy-supervisor`,
`outcome`, or `team-execution`). #356 remains the only validated worktree sweep, and #358 later owns
generic process/resident teardown. #355 does not kill PIDs, delete paths, redispatch units, or claim a
candidate was reclaimed.

R12. **Every supported bridge evidence writer is inventoried.** Add a source-aware inventory naming
each acceptance function, resource-key source, acquire/renew seam, guarded commit, quarantine path,
close seal, and reader. A new bridge write or an injected direct overwrite without those fields fails
conformance. Raw logs and bundle-local terminal forensics are explicitly marked non-live evidence,
not silently omitted.

R13. **Release integrity is atomic.** From the expected post-#356 base, bump fleet-core 0.12.0 to
0.13.0, agy 0.4.0 to 0.5.0, and Saga 0.99.0 to 0.100.0. Update all manifests, marketplace rows,
changelogs, drift guards, agy delegation contract, operator recovery guidance, and engineering journal
in the same PR. If the refreshed base differs, update these exact expected increments and rerun
document/workflow approval before implementation.

---

## High-Level Technical Design

The implementation adds evidence disposition around existing writers rather than replacing them:

```text
trusted bridge adapter
        |
        | logical resource + trusted lease handle
        v
resource-scoped guard lock
        |
        +-- current --------> existing live writer --------> close seal
        |
        +-- superseded -----> ORPHAN_WRITE_BLOCKED event --X live target
        |
        +-- expired --------> quarantine manifest/payload --X live target
        |
        +-- closed ---------> quarantine + late event ------X live target

broker + events + seals + artifacts
        |
        v
derived orphan projection --> named owner action only
```

The per-resource lock closes the last check-to-write race for Python-owned evidence commits. It does
not claim to preempt an already-running arbitrary Bash syscall; that limitation remains #356's
documented generic hook boundary. Lock ordering is always sorted resource digest, then registry lock,
and no code may acquire a resource lock while already holding the registry lock.

### Evidence-disposition contract

| token relation | live lease | disposition | live target | forensic result |
|---|---|---|---|---|
| equals head | nonexpired | `accepted` | existing writer commits | close seal/additive token ref |
| equals head | derived expired | `EXPIRED_LEASE_QUARANTINED` | unchanged | content-addressed quarantine + event |
| equals head | absent | `LATE_WRITE_AFTER_CLOSE` | unchanged | quarantine + close-late event |
| differs from head | any | `ORPHAN_WRITE_BLOCKED` | unchanged | metadata-only blocked event |
| unknown/corrupt authority | unknown | `AUTHORITY_INVALID` | unchanged | loud error; no guessed quarantine |

### Machine-local forensic layout

The existing `~/.claude/delegation-audit` root gains additive namespaces:

```text
quarantine/<resource-sha256>/<epoch>-<sequence>/<payload-sha256>/
  payload.bin
  manifest.json
  committed
orphan-events/<resource-sha256>/<event-id>.json
close-seals/<resource-sha256>/<epoch>-<sequence>.json
```

All final files are 0600 beneath a 0700 effective-user-owned, non-symlink root. Event and seal files
are write-once. Quarantine readers require the final commit marker and verify the manifest digest
before returning bytes.

---

## Key Technical Decisions

- **KTD1 - #356 is the lease authority.** `run-lease.json` remains a terminal forensic snapshot with
  an additive token reference. Turning it into a parallel renewable lease would split authority and
  preserve the exact race this issue is meant to close.
- **KTD2 - persistent resource heads determine disposition.** Head plus the live lease set derives
  current, expired, closed, or superseded without a mutable status field. Unknown/corrupt authority
  fails closed rather than being guessed into quarantine.
- **KTD3 - resource locks span the final commit.** A check followed by an unlocked write is still
  racy. A stable digest-named resource lock serializes same-resource grant/supersession with the short
  live commit while leaving other resources independent.
- **KTD4 - quarantine is evidence, not a retry queue.** It preserves an expired/closed proposed write
  without making it live. No consumer automatically applies, retries, or deletes quarantined content.
- **KTD5 - superseded beats expired.** When a newer resource head exists, the old writer is rejected
  as superseded even if its TTL also elapsed. Quarantine is reserved for the still-latest token whose
  authorization expired or closed.
- **KTD6 - bundle terminal truth is always retained.** Agy still completes its local result/lease/log
  bundle when live acceptance is blocked. The bundle explains the failure; only the live patch and
  current durable mirror are fenced.
- **KTD7 - close seals catch supported bypasses.** Guarded writers prevent normal late acceptance;
  immutable seals let scans detect a supported artifact tree changed after close without pretending
  to provide a general filesystem monitor.
- **KTD8 - orphan state is projected, not committed.** Write-once facts and immutable seals are
  durable; classifications and owner actions are recomputed on every scan.
- **KTD9 - #357 and #358 retain their layers.** #355 consumes existing heartbeat/lease evidence and
  names reclaim owners. Statistical liveness, notification delivery, generic resource ledgers,
  process eviction, and non-skippable teardown stay in their dedicated issues.

These decisions are recorded under `{#orphan-evidence-fencing-355}` in
`docs/engineering-journal/DECISIONS.md` before implementation starts.

---

## Implementation Units

### U1. Resource-guarded evidence disposition

Provide one race-safe API that classifies and commits a bridge evidence write.

**Goal:** Extend fleet-core's #356 broker with digest-named resource locks and a guard context that
returns a closed disposition object and holds same-resource supersession off until commit ends.

**Requirements:** R1-R4, R7.

**Dependencies:** #356 merged; no prior unit.

**Files:** `plugins/fleet-core/scripts/fleet_commons/lease_broker.py`,
`plugins/fleet-core/scripts/fleet_commons/orphan_evidence.py` (new),
`tests/test_fleet_lease_broker.py`, `tests/test_orphan_fencing.py` (new).

**Approach:** Canonicalize and digest resource references through the broker's existing validator.
Acquire sorted resource locks before the registry lock, reclassify under the registry lock, and expose
only trusted disposition/token/resource values to the callback. Grant and supersede paths take the
same lock order. Never hold the registry lock across I/O outside the small registry update.

**Patterns to follow:** #356's no-follow store rules; `audit_store._write_once` for race-safe immutable
publication; `outcome_store` lock-consistent transition patterns.

**Test scenarios:** Happy path: current token commits exactly once and a concurrent retry blocks until
commit exits. Edge: two resources commit concurrently; multi-resource locks sort identically; a
duplicate current commit is caller-idempotent. Failure: reversed/recursive lock attempts, corrupt
head, missing lease, unsafe lock symlink, and store epoch mismatch fail without invoking the writer.
Integration: real two-process grant-versus-write races prove the old token never commits after the new
head is installed.

**Verification:** No test can produce a state where a superseded token mutates the protected target;
unrelated-resource throughput remains concurrent.

### U2. Write-once quarantine, orphan events, and close seals

Preserve rejected payloads safely and make later classification auditable.

**Goal:** Extend the existing machine-local audit store with bounded quarantine, immutable events,
strict reads, and close seals without changing current receipt/result/manifest paths.

**Requirements:** R4-R6, R8-R10.

**Dependencies:** U1.

**Files:** `plugins/fleet-core/scripts/fleet_commons/audit_store.py`,
`plugins/fleet-core/scripts/fleet_commons/orphan_evidence.py`, `tests/test_audit_store.py`,
`tests/test_orphan_fencing.py`.

**Approach:** Publish payload and digest-bound manifest into a digest-derived directory, then create a
write-once commit marker last. Emit metadata-only events for blocked superseded writes. Write a
contract/digest close seal only after the owning bridge reaches its authoritative terminal evidence
state. A claimed Saga manifest that still expects adjudication is not terminal and is not sealed. New
strict readers distinguish absent, corrupt, partial, and complete forensic artifacts; existing
tolerant audit query behavior remains unchanged outside this feature.

**Patterns to follow:** Audit-store 0600 temp/link/replace primitives and safe-name guards;
`evidence_ledger.py` content-addressed custody semantics; #356 effective-user/no-symlink checks.

**Test scenarios:** Happy path: expired payload quarantines and round-trips with verified digest;
closed payload gets a distinct event; superseded payload stores metadata only. Edge: duplicate same
payload converges, conflicting metadata rejects, zero-byte payload preserves zero bytes, and the
largest payload below 128 MiB succeeds. Failure: payloads at and above 128 MiB, partial directory
without marker, corrupt manifest/digest, symlink substitution, permission drift, disk error, and two
concurrent writers fail closed without a live write. Integration: deleting the disposable bundle does
not remove committed quarantine.

**Verification:** Every forensic reader verifies the commit marker and digest; live audit paths are
unchanged for current writes.

### U3. Fence agy apply and durable mirroring

Make a stale agy retry unable to apply or publish over its successor.

**Goal:** Thread the trusted #356 lease through supervised agy execution, fence live patch application
and durable mirror publication, retain terminal bundle truth, and expose quarantine dispositions.

**Requirements:** R1-R9, R12.

**Dependencies:** U1, U2.

**Files:** `plugins/agy/scripts/agy_delegate.py`,
`plugins/agy/skills/agy-delegate/references/delegation-contract.md`,
`tests/test_agy_delegate_contract.py`, `tests/test_agy_delegate_reliability.py`,
`tests/test_agy_run_lease.py`, `tests/test_orphan_fencing.py`.

**Approach:** Add `--lease-resource-key` to the trusted outer agy coordinator interface, not to
`agy.delegation.v1`; validate it before the delegation envelope is built and never copy it into the
prompt or accept a replacement from engine output. Require it for write-capable retryable calls and
default one-shot/read-only calls to run ID. Keep the acquired handle in coordinator memory and add its
non-authoritative reference to terminal `run-lease.json`. Renew during the existing supervisor loop.
Under the resource guard, current runs call the existing apply/mirror functions; expired or closed
runs quarantine the patch/result/receipt; superseded runs emit the blocked event. Local terminal bundle
files always complete and return a nonpassing disposition when live acceptance did not occur. The
bridge writes its close seal only after the final result/receipt contract is present; a failed durable
mirror remains an evidence error even when the already-applied live patch cannot be rolled back.

**Patterns to follow:** Existing `run_agy_supervised` watchdog and die-clean paths; terminal-bundle
guarantee; `_PASSING_STATUSES` as the single exit mapping; audit store as the machine-local durable
mirror.

**Test scenarios:** Happy path: current auto-if-clean patch applies and mirrors unchanged; read-only
result mirrors under a unique resource. Edge: retry shares a stable outer key; validation-only run
needs no lease; no-output/error records its final evidence contract before sealing. Failure: a key
injected through envelope, environment, prompt, engine output, or bundle cannot change authority;
superseded apply leaves current file and mirror bytes unchanged with `ORPHAN_WRITE_BLOCKED`; expired
patch is not applied and is quarantined; closed late result gets `LATE_WRITE_AFTER_CLOSE`; unavailable
broker/quarantine fails nonzero; a mirror failure leaves an evidence error/missing seal; signal,
timeout, and shutdown-incomplete paths release or expire safely. Integration: a real delayed old
process loses to a retry and cannot change the live repository.

**Verification:** Existing agy bundle tests remain green, and the issue selectors
`superseded_lease_rejected` and `expired_lease_quarantined` pass against the production wrapper seam.

### U4. Fence Saga engine manifests and adjudication

Keep a stale engine/chaperone attempt from overwriting current provenance evidence.

**Goal:** Guard claimed-manifest publication, adjudication read-modify-write, and durable mirrors with
the same token/disposition contract.

**Requirements:** R1-R8, R10, R12.

**Dependencies:** U1, U2.

**Files:** `plugins/saga/scripts/engine_dispatch.py`, `plugins/saga/scripts/manifest_store.py`,
`plugins/saga/scripts/provenance_manifest.py`, `tests/test_saga_engine_dispatch.py`,
`tests/test_manifest_store.py`, `tests/test_orphan_fencing.py`.

**Approach:** Derive the resource from authoritative `execution_id` and `bridge_run_key`; pass a
trusted coordinator lease handle into bridge record/adjudicate functions. Hold the resource guard
across manifest read-modify-write and matching audit mirror. Leave raw `manifest_store.write_manifest`
available for non-bridge driver-materialized completeness, but require guarded callers wherever an
external runner receipt/bridge key arms the path. Expired/closed manifests quarantine; superseded
ones raise typed `DispatchError` after emitting a blocked event. Keep the logical bridge resource
open and renewed from initial claim until terminal adjudication. If a legitimate later adjudicator
takes over, it intentionally acquires the next generation for the same resource and only that current
successor token may update the claimed manifest. Claim publication is intermediate evidence; write the
close seal only after final adjudication or an explicit terminal non-adjudicated outcome.

**Patterns to follow:** Existing claim/adjudication validation, bridge receipt binding,
`manifest_store` 0600 atomic replacement, and HALT-not-degrade engine-dispatch behavior.

**Test scenarios:** Happy path: one renewed generation claims then adjudicates while retaining the
existing schema and mirror parity. Edge: non-bridge workflow completeness remains unarmed; same-token
adjudication is allowed; a later trusted adjudicator acquires a successor generation for the same
resource; repeat identical mirror converges; an intermediate claimed manifest has no close seal.
Failure: retry supersedes between manifest read and guard acquisition; stale adjudication cannot
revert current claims; expired/closed updates quarantine; missing/mismatched bridge key, lease, or
token fails before any store; no terminal adjudication path can omit its seal. Integration: manifest
and audit mirror remain on the same accepted version under a concurrent retry.

**Verification:** Existing engine dispatch, reconciliation, claim provenance, and gate tests remain
green; stale evidence never satisfies `satisfy_gate`.

### U5. Derived cross-bridge orphan projection

Turn immutable lease/evidence facts into deterministic reclaim candidates.

**Goal:** Implement a read-only projector and thin Saga CLI that flag aged, empty, quarantined,
blocked, and post-close cases with the correct owner and evidence references.

**Requirements:** R6, R9-R11.

**Dependencies:** U3, U4.

**Files:** `plugins/fleet-core/scripts/fleet_commons/orphan_evidence.py`,
`plugins/saga/scripts/reap_orphans.py` (new), `plugins/saga/scripts/outcome_liveness.py`,
`tests/test_reap_orphans.py` (new), `tests/test_outcome_liveness.py`.

**Approach:** Normalize #356 lease renewal/expiry, agy run snapshots, Saga manifest completeness,
existing outcome heartbeat/terminal facts, quarantine events, and close-seal comparisons. Evaluate
empty artifacts only after expiry/close and against an explicit expected-output contract. Compare a
close seal only when its generation remains the newest resource head; an authorized successor makes
older seals historical. Require seals only for terminal bridge states, never for an intermediate
claimed manifest. Emit sorted `orphan_candidate.v1` records with classification,
token/resource/run IDs, evidence refs, and named owner action. `scan` never mutates stores or invokes
a reaper.

**Patterns to follow:** `outcome_liveness` max-by-timestamp heartbeat handling and idempotent terminal
semantics; `delegation_audit_query` deterministic audit-store scans; derived-on-read outcome reports.

**Test scenarios:** Happy path: aged renewal and contract-bearing empty run are flagged; a recent
renewal and valid output are not. Edge: pre-dispatch/out-of-order heartbeat, no output contract,
intermediate unsealed claim, authorized successor after an older seal, deleted local bundle with
durable audit evidence, and repeated scans are deterministic. Failure: corrupt/missing required
terminal seal, changed newest seal, malformed registry, contradictory receipt/manifest, and
uncommitted quarantine surface evidence errors. Integration: `late_writer_after_close` differs from
mid-run `stalled`, and a 15-run mixed fixture assigns every candidate to the right owner without
deleting anything.

**Verification:** Published issue selectors `stalled_or_empty_flagged` and
`late_writer_after_close` pass while existing R31 stalled-terminal tests remain unchanged.

### U6. Conformance, operator contract, and release surfaces

Prevent future bridge writers from bypassing containment and ship coherent installed metadata.

**Goal:** Inventory every supported acceptance seam, add source-aware drift enforcement, document
operator inspection/recovery, and publish fleet-core, agy, and Saga together.

**Requirements:** R7, R11-R13.

**Dependencies:** U3-U5.

**Files:** `plugins/saga/references/evidence-write-sites.md` (new), conformance tests,
`plugins/fleet-core/.claude-plugin/plugin.json`, `plugins/agy/.claude-plugin/plugin.json`,
`plugins/saga/.claude-plugin/plugin.json`, `.claude-plugin/marketplace.json`, three changelogs,
agy delegation contract, `docs/engineering-journal/DECISIONS.md`, and version/parity tests.

**Approach:** Inventory live acceptance and non-live forensic writers separately. The parser scans
production source for bridge result/manifest/apply publication and requires resource identity, guard,
quarantine, seal, and reader ownership. Update versions and release narrative from the refreshed
post-#356 base. Recovery docs allow inspect/export only; no command fabricates a current token or
applies quarantine automatically.

**Patterns to follow:** #350 concurrency and #356 lease lifecycle inventories; release triad/parity
guards; journal decisions in the same behavioral commit.

**Test scenarios:** Happy path: inventory matches all supported writers and installed versions agree.
Edge: raw log/local terminal bundle rows are explicitly non-live; an additive bridge declares its
owner. Failure: injected direct manifest overwrite, unguarded live apply, missing quarantine/close
seal, stale row, release drift, or absent broker version fails. Integration: full package install
loads fleet-core 0.13 from both agy and Saga shims and rejects older required authority.

**Verification:** Conformance, release parity, changelog, plugin loading, and full repository gates
are green from a clean branch.

---

## Requirement Coverage

| requirement | units | primary proof |
|---|---|---|
| R1-R3 | U1, U3, U4 | broker authority and real two-process guarded-commit race |
| R4-R6 | U1-U4 | superseded byte preservation and expired/closed quarantine selectors |
| R7 | U3, U4, U6 | existing agy/Saga regression suites and manifest/result parity |
| R8-R9 | U2, U3, U5 | size/digest/crash tests and post-close seal mutation |
| R10-R11 | U5 | deterministic mixed-run projection with no mutation |
| R12-R13 | U6 | injected bypass failure and release-surface parity |

---

## Scope Boundaries

### In scope

- Agy live patch and durable result/receipt acceptance.
- Saga bridge claimed/adjudicated manifest and audit mirror acceptance.
- Fleet-core guarded disposition, quarantine, immutable events/seals, and read-only projection.
- Existing fixed-budget outcome liveness as one evidence adapter.

### Non-goals

- Another lease, fencing-token, heartbeat, status, or retry queue beside #356/#351.
- Killing arbitrary processes, deleting worktrees, evicting resident teammates, or redispatching work.
- Phi-accrual scoring, artifact-pointer progress policy, or acknowledged idle notifications.
- UI/dashboard surfacing, cross-host/distributed locking, quarantine encryption, retention, or
  automatic application of quarantined content.
- Rewriting agy's existing bundle sequencing or replacing outcome R31 stalled semantics.

### Deferred to follow-up work

- #357 generalizes liveness detection and notification delivery while consuming this projector's
  bridge facts.
- #358 makes teardown non-skippable and executes owner-specific process/resident reclamation.
- The #579 runtime-parity children expose the same disposition and projection contract in Codex.

---

## Risks and Mitigations

| risk | impact | mitigation/proof |
|---|---|---|
| check-to-write race | stale evidence lands after a successful verify | resource lock spans final commit; real process race test |
| lock-order deadlock | admissions/renewals freeze | canonical resource-digest order then registry; inversion tests |
| quarantine leaks sensitive or huge output | local disclosure/disk exhaustion | 0700/0600/no-follow, reject at or above 128 MiB, no prompt/env capture |
| tolerant existing readers hide corruption | false clean orphan scan | new strict forensic readers; existing tolerant queries remain scoped |
| close seal overclaims whole-filesystem coverage | unsupported late writes go unseen | inventory names supported roots; docs state it is not a filesystem monitor |
| #355 absorbs liveness/teardown siblings | oversized or contradictory PR | projection only; #357 detection and #358 reclamation boundaries are explicit |
| release-version base changes before execution | incorrect metadata bump | refresh main and amend/reapprove exact plan/workflow before dispatch |

---

## Verification

Run focused gates after their owning units, then the full repository gate:

```bash
uv run pytest tests/test_fleet_lease_broker.py tests/test_orphan_fencing.py -q
uv run pytest tests/test_audit_store.py tests/test_agy_delegate_contract.py -q
uv run pytest tests/test_saga_engine_dispatch.py tests/test_manifest_store.py -q
uv run pytest tests/test_reap_orphans.py tests/test_outcome_liveness.py -q
uv run pytest
uv run ruff format --check .
uv run ruff check .
uv run mypy plugins/ scripts/ tests/ --ignore-missing-imports
uv run bandit -r plugins/
git diff --check
```

The concurrency validator independently evaluates resource/registry lock order, two-process
supersession races, byte-preservation, duplicate quarantine convergence, and the absence of
check-to-write windows. The event-flow validator traces acquire/renew, current commit, expiry,
quarantine failure, close, late write, supersession, seal scan, orphan classification, and named
reclaim owner. Both fail closed on self-report or missing command evidence.

Manual evidence includes one old agy writer racing a retry against the same live file, one expired
payload recovered from quarantine with matching digest, one post-close artifact mutation surfaced as
late-writer-after-close, and one mixed projection demonstrating no destructive action occurred.

---

## Failure Modes and Stop Conditions

- `run-lease.json`, an environment value, manifest prose, or external-engine output becomes token
  authority: stop and restore #356 as the sole trusted source.
- Supersession can occur after classification but before live mutation, or any lock path reverses
  resource-before-registry order: stop as a P0 race/deadlock defect.
- An expired/closed payload lands live, a superseded payload is quarantined instead of rejected, or a
  quarantine failure falls through to acceptance: stop as a P0 evidence-integrity defect.
- A live target changes in any superseded/expired/closed test, or a current successor changes after
  the stale attempt completes: stop as a P0 clobber defect.
- Quarantine follows caller paths, accepts symlinks/unsafe permissions, omits a digest/commit marker,
  or stores over the size cap: stop as a P0/P1 security and durability defect.
- Projection kills/deletes/retries, stores mutable candidate status, or silently treats corruption as
  empty artifacts: stop and restore derived read-only semantics.
- The implementation duplicates #357's shared liveness engine or #358's reclamation ledger/teardown:
  stop for scope correction.
- Any P0-P3 document/code-review finding remains, either required validator lacks gate-capable
  evidence, release metadata drifts, or the full gate fails: no PR/merge.

---

## Workflow Structure

| step_id | depends_on | barrier | role_id | role_kind | independence | execution_class | runtime_agent_name | vehicle | mutation | required_evidence | role_lens_sha256 | profile_sha256 | expected_model | expected_effort | validator_required | validator_disabled | deterministic_contract_sha256 |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| implement | - | - | root | root | n/a | - | - | root | root-only | authorized-diff,focused-tests | - | - | - | - | n/a | n/a | - |
| review-devils | implement | review | devils-advocate-reviewer | agent-lens | preferred | review-high | review_high | auto | none | scored-review,findings | 129f6dca0702ffcd4be7f9e5d0939e8e6806788846ba4058044c931883ef0e63 | 42e86e00e054281b0a79e4b3b9b544c04a31eb2fd6b53c0489adc42ea639c9a8 | gpt-5.6-sol | high | n/a | n/a | - |
| review-security | implement | review | security-reviewer | agent-lens | preferred | review-high | review_high | auto | none | scored-review,findings | bf5bc1b66c0ee3d06071976b659c522c23057c56de5f6cc010556b2653c86980 | 42e86e00e054281b0a79e4b3b9b544c04a31eb2fd6b53c0489adc42ea639c9a8 | gpt-5.6-sol | high | n/a | n/a | - |
| review-architecture | implement | review | architecture-reviewer | agent-lens | preferred | review-high | review_high | auto | none | scored-review,findings | e48b37cea0b26bf39cae4d6611b4219e907d52d284ba6b9489b523a4b16c835f | 42e86e00e054281b0a79e4b3b9b544c04a31eb2fd6b53c0489adc42ea639c9a8 | gpt-5.6-sol | high | n/a | n/a | - |
| review-testing | implement | review | testing-reviewer | agent-lens | preferred | review-high | review_high | auto | none | scored-review,test-gaps | a867575e24c86b0573485d1d8bbd81514af3654d544342677b85f4bed0d9af63 | 42e86e00e054281b0a79e4b3b9b544c04a31eb2fd6b53c0489adc42ea639c9a8 | gpt-5.6-sol | high | n/a | n/a | - |
| validate-concurrency | implement | validate | concurrency-tester | agent-lens | preferred | test-medium | test_medium | auto | none | tester-evidence,command-results | d40188645b7876e32ea592dd9799ee2ad7a2e230d82341611708dd492837b3da | 6d69bb4d5e477574ce186a353a3d2fcc7f8ab6b1f014b93aebb05084aecccc1b | gpt-5.6-terra | medium | true | false | - |
| validate-event-flow | implement | validate | event-flow-tester | agent-lens | preferred | test-medium | test_medium | auto | none | event-trace,command-results | 2e20ab6935b1e17e363b5e28308a9288107532d0118a6a189f07b0e0eaaff356 | 6d69bb4d5e477574ce186a353a3d2fcc7f8ab6b1f014b93aebb05084aecccc1b | gpt-5.6-terra | medium | true | false | - |
| integrate | review-devils,review-security,review-architecture,review-testing,validate-concurrency,validate-event-flow | - | root | root | n/a | - | - | root | root-only | fixed-findings,full-gate,release-parity,git-receipt | - | - | - | - | n/a | n/a | - |

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

Completion requires all issue acceptance criteria, zero open P0-P3 doc/code-review findings, both
required validators passing with gate-capable evidence, the full verification gate green, one atomic
issue PR merged, issue #355 closed, its Operations card reconciled, dependent outcome nodes refreshed,
and the outcome worktree returned to a clean state except for the next planned wave.
