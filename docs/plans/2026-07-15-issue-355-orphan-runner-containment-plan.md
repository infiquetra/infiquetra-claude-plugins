---
title: Lease-safe runtime continuity wave 3 - orphan runner containment
type: feat
status: active
date: 2026-07-15
origin: docs/plans/plugin-fleet-ideation-2026-07-03/survivors/T15.json
deepened: 2026-07-17
---

# Lease-safe runtime continuity wave 3 - orphan runner containment

## Summary

Implement issue #355 on the merged #356/#613 broker by extending `LeaseBroker` with a broker-owned
prepare/commit/abort settlement protocol. The protocol fences agy live apply plus the documented Team
Execution claim and adjudication writers, retains ambiguous authority after any write may have begun,
and emits strict evidence contracts for bounded quarantine and derived orphan projection.

Destination is merge. Execution uses an operator-approved Verified Workflow. Root owns
implementation, Git, integration, PR, merge, issue closure, and board reconciliation. Agent-lens
roles independently review or validate and authorize no repository mutation.

---

## Problem Frame and Current State

The issue is requirements-ready but its proposed resource-lock mechanism predates the merged #356
broker and PR #613 teardown repair. Fleet-core now provides canonical leases, boot-aware TTL,
persistent resource heads, exact release, and `LeaseBroker.agent_settlement`. Its current callback
boundary is not failure-atomic: a callback can mutate durable state and then fail before receipt
publication or exact release. #355 makes the broker own prepare, commit, abort, and terminal authority
retention without introducing another lock, registry, or caller-authored token.

The current bridge boundaries are:

| seam | live function | current behavior |
|---|---|---|
| agy live patch | `agy_delegate.apply_patch_to_live_repo` from `auto-if-clean` (`plugins/agy/scripts/agy_delegate.py`) | applies a derived patch to the live repository outside lease settlement |
| agy durable mirror | `agy_delegate._mirror_to_audit_store` (`plugins/agy/scripts/agy_delegate.py:330`) | overwrites result/receipt mirrors and suppresses write failures |
| Saga registered dispatch | `engine_dispatch.dispatch` and advisory-panel settlement paths | registered Saga facts are already settled and remain so |
| Team Execution claim | documented `record_dispatch_manifest` chaperone writer | live post-dispatch manifest and strict mirror publication is currently unfenced |
| Team Execution adjudication | documented `adjudicate_manifest` chaperone writer | live read-modify-write adjudication and strict mirror publication is currently unfenced |
| ordinary manifest store | `manifest_store` writers outside registered or chaperoned acceptance | noncanonical evidence-only writes that cannot satisfy a gate |
| shared audit mirror | `audit_store.mirror_result`, `mirror_receipt`, and `mirror_manifest` | atomic per-file replacement; armed bridge acceptance must be broker-commit-authorized |

The agy bundle under `.claude/agy/runs/<run_id>` remains local forensic material. External work and
clone verification finish before settlement prepare; only bounded validation and broker-owned commit
callbacks occur under the broker lock. Terminal bundle files still record what happened when live
acceptance is denied, but neither they nor ordinary `manifest_store` output are canonical acceptance.

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
- **Merged prerequisites:** #356 is merged at `811b0470`; its teardown-authority repair #613 is
  merged at `cb6f44ea`. #613's authority-retention rule is binding: failed or ambiguous cleanup keeps
  broker authority and cannot be projected as successful reclamation.
- **Delivery serialization:** #357 owns advanced liveness and #358 owns destructive teardown and
  reclamation. The Wave 3 leaves change shared Saga/fleet-core release surfaces and merge serially
  from refreshed main.
- **Downstream unlocks:** the Claude coordination child of #579 consumes #355 directly; #353 consumes
  #355 plus #351/#357/#358; Codex parity and cross-runtime acceptance follow those contracts.
- **External prerequisites:** PR readiness requires one genuine authorized agy bridge run and its
  matching transcript. The operator's autonomous-execution approval authorizes that run; it needs no
  credential change, deployment, production-data access, or named human specialist.

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

R1. **Reuse the sole #356 authority.** Fleet-core `LeaseBroker` is the only authority, and accepted
writes use `agent_settlement`. No resource-lock directory, second registry, heartbeat registry, or
caller-authored token is introduced.

R2. **Bind agy apply to trusted resource identity.** Agy `auto-if-clean` requires a trusted outer
`--lease-resource-key`; launched `auto-if-clean` is rejected without it. The CLI accepts no other
admission identity. `agy_delegate.main()` calls
`plugins/agy/scripts/agy_lease_admission.py::resolve_direct_agy_admission(repo_root, resource_key,
run_id, providers)` after strict Git-root resolution and before any clone or subprocess. The resolver
imports fleet-core `concurrency_policy.AdmissionLimits` packaged defaults and broker providers,
immediately calls `configure_session_admission`, and returns an immutable typed
`agy.lease-admission.v1` record directly in memory to `run_agy_supervised`; it uses no file,
environment variable, envelope, prompt, bundle, or engine transport. It derives `session_id` from
canonical repository identity plus `run_id`; fixes `owner_id` to `agy-direct:<effective-uid>`;
uses the current PID and provider-derived process start; copies policy digest and session/aggregate
limits from packaged `AdmissionLimits`; sets `mutation=read-write` and the broker-default TTL;
derives canonical `resource_ref` from repository identity plus the bounded key; builds the packaged,
lease-independent `agy.expected-output-template.v1`; and binds its digest as
`expected_output_template_sha256`. The resolver configures admission, acquires the exact lease, then
constructs `expected_output.v1` from that exact template digest plus the acquired `resource_ref`,
`lease_id`, token, and generation. Its `expected_output_sha256` is passed into settlement. The records
have exactly the fields and bounds in the HTD. Missing resolver/record, a stale or fabricated
template, a template/bound-record mismatch, or any caller override fails before subprocess.
Admission lives through the exact lease close and is cleared only when no live lease remains.

R3. **Broker-owned prepare/commit/abort is failure-atomic.** From `leased`, prepare persists
`phase=prepared` and renews authority before any protected write. Commit persists `committing`, invokes
every protected writer under the broker lock, validates a closed `settlement_close.v1`, then atomically
replaces the registry with a `closed` `ResourceFence` carrying that receipt, with the exact lease
removed and eligible admission cleared. That one closed-registry replacement is the commit
linearization point. A caught callback or receipt-validation failure best-effort persists
`phase=ambiguous`; if that write fails, or the process is signaled or dies, the last durable
`prepared` or `committing` state itself retains authority. Context exit before callback aborts and
releases exact authority; after any callback may have started it never releases. Callback output
without a matching closed registry receipt is unaccepted, quarantine-only evidence. Sweep and acquire
retain or block `prepared`, `committing`, and `ambiguous` regardless of TTL.
`LeaseBroker.recover_agent_settlement(...)` is the only recovery API. Only the root coordinator may
call it through the non-child production adapter, with a typed `settlement_recovery_intent.v1` carrying
the exact original `Lease`, token, resource, settlement ID, session and policy, expected retained
phase, original protected-write intent digest, and root recovery-owner identity. Under the broker
lock it requires the current head to match exactly; phase to be `prepared`, `committing`, or
`ambiguous`; original owner death or boot change; the caller's effective UID to own the safe broker
root; original owner ID, session, and policy to match; and no live successor. `prepared` may abort the
exact settlement or restart commit. `committing` and `ambiguous` may only replay idempotent protected
writers whose declared input and output digests match the prepared intent, then use the same
closed-registry CAS linearization; otherwise authority remains retained and the operator is paged.
An identical completed replay returns the existing receipt. Mismatched, stale, live-owner, or
wrong-identity recovery refuses. Recovery never creates a generation or an ordinary successor.

R4. **Superseded writes are metadata-only.** Superseded settlement emits `ORPHAN_WRITE_BLOCKED`; the
live target and current evidence remain unchanged.

R5. **Expired-unsuperseded writes are quarantined.** Expired output is content-addressed into
quarantine and emits `EXPIRED_LEASE_QUARANTINED`. A trusted presented `Lease`, persistent head, and
absence of a canonical closed `ResourceFence` receipt distinguish an expired lease swept from the
registry from an intentional close.

R6. **Closed late writes require receipt proof.** A closed token with a matching canonical generation
receipt in `ResourceFence` produces `LATE_WRITE_AFTER_CLOSE` and quarantine; an audit close seal, when
present, must mirror that receipt. Apparent close without the canonical matching receipt is an
evidence-integrity error, never accepted or silently called late-after-close.

R7. **Current paths preserve compatibility.** Current agy apply and registered Saga dispatch retain
their successful schemas and behavior. Saga's already-settled fact path is extended, not replaced.

R8. **Quarantine is bounded, reserved, and tamper-evident.** Each item is strictly `<128 MiB`;
committed plus staging bytes are capped at 512 MiB and reservations count toward a 256-entry cap.
Minimum retention is 30 days with no acceptance-path eviction. An owner-only no-follow lock guards
usage calculation, reservation, publish, and commit-marker creation; identical duplicates converge,
last-slot races admit one winner, and capacity failure never evicts, falls through, or exceeds a cap.
Staging contains durable `reservation.v1` state. Under the same quota lock, startup, publication, and
operator `quarantine recover` use one recovery algorithm: retain a reservation while its exact
PID/process-start owner is alive on the current boot; when the owner is dead or the boot changed,
atomically finalize the marker if payload and manifest are complete and verify, otherwise remove only
that staging payload/reservation and release its quota. A live reservation's one-hour observation age
only raises an alert and never authorizes reclamation. Recovery never touches committed entries,
bypasses 30-day retention, or evicts evidence.

R9. **The broker receipt is the only canonical close.** `settlement_close.v1` is embedded in the
broker `ResourceFence`; an audit close seal is only a mirror. Sweep retains `prepared`, `committing`,
and `ambiguous` generations regardless of TTL, and acquisition cannot supersede them. Only broker
commit can create a valid receipt and remove authority. `acquire_successor(expected predecessor
token + receipt hash)` uses CAS and succeeds only against the exact closed head.

R10. **Projection inputs and outputs use closed schemas.** Canonical records are compact,
sorted-key ASCII JSON; duplicate keys are rejected before validation, schemas disallow additional
properties, and evidence records carry a self-digest excluded from its own digest. Define
`settlement_close.v1`, `settlement_recovery_intent.v1`, `agy.expected-output-template.v1`,
`expected_output.v1`, `quarantine_manifest.v1`, `orphan_event.v1`, `orphan_candidate.v1`,
`reservation.v1`, and `agy.lease-admission.v1` exactly as specified in the
HTD and deliver `plugins/fleet-core/schemas/orphan-evidence-v1.schema.json` (or an equivalent closed
Python schema registry). Resource, token, lease, run, generation, receipt, and expected-output
bindings must agree wherever present; a mismatch is `EVIDENCE_INTEGRITY_ERROR`. `empty-artifacts`
requires the bound record's exact template to say `required=true` plus an authoritative terminal or
expiry. Missing/malformed required evidence, a stale or fabricated template, or any
template/bound-record mismatch is `EVIDENCE_INTEGRITY_ERROR`, while optional or no-output contracts
produce no candidate.
Projection remains derived on read and stores no mutable status.

R11. **Flagging does not invent destructive authority.** `reap_orphans.py scan` is read-only and only
names `lease-sweep`, `agy-supervisor`, `outcome`, or `team-execution` as owners.

R12. **Fence documented Team Execution writers and inventory every protocol.** Resource identity is
stable by `execution_id`; `attempt_id` never creates a new resource. Claim acquires a CAS successor
from the registered dispatch receipt and commits manifest plus strict mirror. Adjudication acquires a
CAS successor from the claim receipt, rereads current state inside settlement, and commits adjudication
plus mirror. Old predecessors cannot reacquire after retry. The consumer matrix scans Python and
Markdown protocols, rejects documented raw calls without authority, and separately inventories
registered Saga facts, Team Execution writers, unique-run forensics, and noncanonical ordinary stores.

R13. **Release integrity requires executable proof.** Bump fleet-core `0.12.0` to `0.13.0`, agy
`0.4.0` to `0.5.0`, Saga `0.99.1` to `0.100.0`, and Team Execution to `2.19.0` for the protocol
change. Require a genuine `delegation-proof.v1` plus matching transcript. The closed `run` and
`verify` subcommands of `scripts/delegation_proof_receipt.py` are the only release-proof command path.
`run` invokes the fixed internal `check_delegation_proof.py` argv for exactly one mode and atomically
writes a distinct 0600 receipt at
`docs/evidence/issue-355/version-gate-command-receipt.json` or
`docs/evidence/issue-355/fleet-sweep-command-receipt.json`. Each receipt captures mode, exact argv,
cwd, recorded merge-base, base and head SHA, proof and transcript digests, stdout, stderr, exit code,
started/ended UTC, and its self-digest. `verify` recomputes schema and self-digest and requires the
mode, expected argv, base/head, referenced proof/transcript artifacts and digests, and exit zero to
match current release evidence. Missing, swapped, tampered, nonzero, wrong-argv, wrong-base, or
wrong-digest receipts fail. Unit tests, dry runs, or direct unreceipted checks do not satisfy release
proof.

---

## High-Level Technical Design

The broker owns the full settlement state machine and never delegates authority retirement to a
writer callback:

```text
trusted runtime
    |
    +-- acquire canonical LeaseBroker agent lease
    +-- renew during supervised external work
    |
    +-- prepare: leased -> prepared; persist and renew before writes
    |       +-- exit/abort before callback -> release exact lease
    |
    +-- commit: prepared -> committing; persist before callback
            +-- protected writers run under broker lock
            +-- validate closed settlement_close.v1
            +-- one atomic registry replacement attaches receipt,
            |   removes exact lease, clears eligible admission -> closed
            |   (sole commit linearization point)
            +-- caught failure -> best-effort ambiguous
            +-- failed registry write/signal/death -> last durable
                prepared or committing state retains authority
    |
    +-- root-only recovery of retained authority
            +-- recover_agent_settlement with typed original intent
            +-- exact current-head/owner/session/policy/death checks under lock
            +-- prepared -> exact abort or restart commit
            +-- committing/ambiguous -> digest-matched idempotent replay only
            +-- same closed-registry CAS linearization; no new generation

broker + immutable forensics + existing outcome heartbeat
    |
    +-- read-only orphan projection
```

Sweep never reclaims `prepared`, `committing`, or `ambiguous`, regardless of TTL, and acquisition
cannot supersede those phases. Output produced without a matching closed registry receipt is
unaccepted and quarantine-only. Retained-settlement recovery follows the root-only API above; ordinary
retry can proceed only through
`acquire_successor(expected_predecessor_token, expected_receipt_sha256)` against the exact closed
head. The audit close seal mirrors the canonical receipt embedded in `ResourceFence`; it does not
authorize release or successor acquisition.

### Evidence-disposition contract

| token relation | live lease | disposition | live target | forensic result |
|---|---|---|---|---|
| equals head | prepared | `commit-or-recover` | broker invokes protected writers, or proven-dead-owner recovery aborts/restarts exact commit | validated receipt atomically closes and removes exact lease, or exact abort releases it |
| equals head | committing/ambiguous | `retain-or-recover` | no successor write; proven-dead-owner recovery may replay only digest-matched idempotent writers | same CAS close returns one receipt; otherwise retained and operator paged |
| equals head | derived expired | `EXPIRED_LEASE_QUARANTINED` | unchanged | content-addressed quarantine + event |
| equals exact closed receipt | absent | `LATE_WRITE_AFTER_CLOSE` | unchanged | quarantine + close-late event |
| equals head | absent, no matching seal | `EVIDENCE_INTEGRITY_ERROR` | unchanged | loud incomplete-settlement error |
| differs from head | any | `ORPHAN_WRITE_BLOCKED` | unchanged | metadata-only blocked event |
| unknown/corrupt authority | unknown | `AUTHORITY_INVALID` | unchanged | loud error; no guessed quarantine |

### Machine-local forensic layout

The existing `~/.claude/delegation-audit` root gains additive namespaces:

```text
quarantine/<resource-sha256>/<broker-epoch-uuid>:<positive-sequence>/<payload-sha256>/
  payload.bin
  manifest.json
  committed
quarantine-staging/<reservation-id>/
  reservation.json
  payload.bin
  manifest.json
orphan-events/<resource-sha256>/<event-id>.json
close-seals/<resource-sha256>/<broker-epoch-uuid>:<positive-sequence>.json
```

All final files are 0600 beneath a 0700 effective-user-owned, non-symlink root. Event and seal files
are write-once. Quarantine readers require the final commit marker and verify the manifest digest
before returning bytes. An owner-only no-follow lock serializes byte/count reservation, staging,
publication, recovery, and commit-marker creation; committed plus staging occupancy cannot exceed
512 MiB or 256 reserved/committed items, and the acceptance path never evicts the minimum-30-day
evidence. `reservation.v1` advances `reserved -> payload-written -> manifest-written`. Startup,
publication retry, and `quarantine recover` retain a same-boot live exact owner; for a dead owner or
boot change they finalize a verified complete payload/manifest or delete only incomplete/corrupt
staging and release its reservation. One hour is an alert threshold for a live reservation, never a
reclamation deadline.

### Canonical evidence schemas

U2 delivers `plugins/fleet-core/schemas/orphan-evidence-v1.schema.json` or an equivalent closed Python
schema registry. Parsing rejects duplicate JSON keys before validation; every object uses
`additionalProperties: false`. Serialization is compact, sorted-key ASCII JSON. Except where a field
below is explicitly optional, every listed field is required.

Shared scalar rules are machine-checkable: all strings are UTF-8, contain no controls, and are at
most 256 bytes unless narrowed; IDs are 1-128 bytes; SHA-256 values are lowercase hex64; byte sizes
are uint64; counts are uint32; timestamps are RFC3339 UTC with a literal `Z`; `resource_ref` passes
fleet-core `canonical_resource_ref`; `lease_id` is a canonical UUID string; and `token` is exactly
`{"broker_epoch": <canonical lowercase UUID string equal to the current broker epoch>,
"fencing_sequence": <positive integer>}`. `generation` is the ASCII
`<broker-epoch-uuid>:<positive-sequence>` derived from and required to match `token`. Evidence-ref and
artifact-key arrays contain at most 256 unique, lexicographically sorted bounded strings.

Closed enums are: `phase=closed`; `producer=agy|saga|team-execution`;
`reason=expired-lease|late-after-close`;
`classification=expired-write-quarantined|superseded-write-blocked|late-write-after-close|stalled|empty-artifacts|evidence-integrity-error`;
`owner=lease-sweep|agy-supervisor|outcome|team-execution`; and
`trusted_source=agy-admission|saga-output-completeness`; reservation
`state=reserved|payload-written|manifest-written`; and admission `mutation=read-write`. Each `schema`
field is the exact table-row name. `run_id`, `source_id`, `event_id`, `candidate_id`,
`reservation_id`, `owner_id`, `session_id`, `settlement_id`, `recovery_owner_id`, and `boot_id` use
the ID bound. `terminal`,
`authoritative_terminal`, and `required` are booleans; settlement and candidate terminal booleans must
be true. `target_count` is uint32; PID and effective UID are positive integers;
`owner_process_start` and `recovery_owner_process_start` are exact 1-256-byte provider identity
strings, never numeric; TTL and monotonic-nanosecond values are positive integers; and every field
ending `_sha256` is lowercase hex64. `evidence_refs`,
`payload_refs`, and `artifact_keys` use the shared bounded unique/sorted-list rule.

| schema | exact required fields | exact optional fields |
|---|---|---|
| `settlement_close.v1` | `schema`, `resource_ref`, `token`, `lease_id`, `generation`, `phase`, `producer`, `run_id`, `terminal`, `evidence_refs`, `expected_output_sha256`, `receipt_sha256`, `sha256` | none |
| `settlement_recovery_intent.v1` | `schema`, `resource_ref`, `token`, `lease_id`, `generation`, `settlement_id`, `session_id`, `policy_sha256`, `expected_phase`, `protected_write_intent_sha256`, `recovery_owner_id`, `recovery_owner_pid`, `recovery_owner_process_start`, `recovery_owner_boot_id`, `recovery_owner_effective_uid`, `sha256` | none |
| `agy.expected-output-template.v1` | `schema`, `trusted_source`, `source_id`, `required`, `artifact_keys`, `target_count`, `expected_output_template_sha256`, `sha256` | none |
| `expected_output.v1` | `schema`, `expected_output_template_sha256`, `resource_ref`, `token`, `lease_id`, `generation`, `producer`, `run_id`, `expected_output_sha256`, `sha256` | none |
| `quarantine_manifest.v1` | `schema`, `resource_ref`, `token`, `lease_id`, `generation`, `producer`, `run_id`, `reason`, `payload_sha256`, `payload_bytes`, `observed_at`, `expected_output_sha256`, `evidence_refs`, `sha256` | `receipt_sha256` only for a matching closed generation; forbidden for expired lease |
| `orphan_event.v1` | `schema`, `event_id`, `resource_ref`, `token`, `lease_id`, `generation`, `producer`, `run_id`, `classification`, `observed_at`, `expected_output_sha256`, `evidence_refs`, `payload_refs`, `sha256` | `receipt_sha256` only when a matching close exists |
| `orphan_candidate.v1` | `schema`, `candidate_id`, `classification`, `producer`, `run_id`, `resource_ref`, `token`, `lease_id`, `generation`, `authoritative_terminal`, `owner`, `expected_output_sha256`, `evidence_refs`, `sha256` | `receipt_sha256` only when a matching close exists |
| `reservation.v1` | `schema`, `reservation_id`, `payload_sha256`, `payload_bytes`, `owner_pid`, `owner_process_start`, `boot_id`, `created_at`, `created_monotonic_ns`, `state` | `manifest_sha256`, required only for `state=manifest-written` and forbidden otherwise |
| `agy.lease-admission.v1` | `schema`, `session_id`, `owner_id`, `owner_pid`, `owner_process_start`, `policy_sha256`, `session_limit`, `aggregate_limit`, `mutation`, `ttl_seconds`, `resource_ref`, `repository_identity_sha256`, `expected_output_template_sha256` | none |

For agy admission, `session_id`, `owner_id`, and `run_id` inputs obey the ID bound; PID is a positive
uint32, process start is the exact bounded provider identity string, TTL is a positive integer, and
policy/repository/expected-output-template digests
are lowercase hex64, limits are positive uint32 values, and `mutation` is exactly `read-write`. The
record exists only in memory from resolver return through exact lease close. Its `session_id` binds
canonical repository identity and `run_id`, while the resulting lease/fence copies its
`resource_ref`, owner, policy, and expected-output-template binding.

Evidence `sha256` is the digest of canonical JSON with only `sha256` omitted. `receipt_sha256` is the
digest of the complete canonical `settlement_close.v1` with `receipt_sha256` and `sha256` omitted.
`expected_output_sha256` is the digest of the complete canonical `expected_output.v1` with
`expected_output_sha256` and `sha256` omitted. Validators require every applicable resource, token,
lease, run, and generation binding to match the broker receipt and expected-output record; mismatch,
missing required linkage, or a receipt referenced by the wrong generation is
`EVIDENCE_INTEGRITY_ERROR`. `expected_output_template_sha256` is the digest of the complete canonical
`agy.expected-output-template.v1` with `expected_output_template_sha256` and `sha256` omitted. The
bound record is valid only against that exact trusted template. Golden round-trip and malformed
fixtures cover every schema using real `FencingToken`, `Lease`, and broker `Providers` values,
including
unknown/missing fields, duplicate keys, bounds, enum violations, digest domains, unsorted/duplicate
lists, noncanonical resource refs, cross-record binding mismatch, and exact recovery-owner identity
comparison.

The `empty-artifacts` classification is legal only when the exact trusted template bound by
`expected_output.v1` says `required=true` and the run has authoritative terminal or expiry evidence.
Saga uses `OutputCompleteness`; agy uses the admission-bound template. Broker receipts, immutable rejection events, and
existing outcome terminals are authoritative; intermediate claims, scan time, mtime, and absent or
malformed evidence are not terminals. Corrupt required evidence yields `EVIDENCE_INTEGRITY_ERROR`;
optional or no-output contracts yield no candidate.

---

## Key Technical Decisions

- **KTD1 - #356/#613 broker is the sole authority.** `LeaseBroker` and its retained-authority cleanup
  contract are authoritative; terminal bundle data remains forensic only.
- **KTD2 - prepare/commit/abort belongs to the broker.** Prepare renews and persists before writes;
  commit persists `committing` before callbacks, and the single atomic closed-registry replacement
  after receipt validation is the only commit linearization point. Pre-callback abort releases exact
  authority. A caught post-callback failure best-effort writes `ambiguous`; failed registry writes,
  signals, and process death leave durable `prepared` or `committing`, which retain authority just as
  `ambiguous` does. Callback output without the closed registry receipt is unaccepted evidence.
- **KTD3 - closed-head CAS is the only successor path.** No digest-named resource lock or ordinary
  acquire can supersede prepared, committing, or ambiguous authority. A successor must name the exact
  predecessor token and canonical receipt hash, preventing stale writers from reacquiring after a retry.
- **KTD4 - quarantine is reserved evidence, not a retry queue.** It preserves an expired/closed
  proposed write without making it live. Durable reservations count against both caps; exact-owner
  recovery finalizes verified complete staging or removes only abandoned incomplete staging. No
  consumer automatically applies, retries, or deletes committed quarantined content.
- **KTD5 - superseded wins at disposition time.** A newer head makes the old writer superseded;
  otherwise a trusted elapsed presented lease can remain expired after registry sweep.
- **KTD6 - agy bundle truth remains additive.** Existing terminal bundle evidence remains available
  and gains `write_disposition`; the status enum is not expanded solely for forensic classification.
- **KTD7 - the embedded broker receipt is canonical; audit seals are mirrors.** Only broker commit may
  create a valid `settlement_close.v1`, attach it to `ResourceFence`, remove the exact lease, and
  close the generation. Audit-store seals support inspection but cannot retire authority.
- **KTD8 - orphan state is projected, not committed.** Write-once facts and immutable seals are
  durable; classifications and owner actions are recomputed on every scan.
- **KTD9 - #357 and #358 retain their layers.** #355 consumes existing heartbeat/lease evidence and
  names reclaim owners. Statistical liveness, notification delivery, generic resource ledgers,
  process eviction, and non-skippable teardown stay in their dedicated issues.

U7 corrects the existing issue #355 decision entry before behavior implementation; no second anchor
is allowed.

---

## Implementation Units

### U7. Correct canonical decision before implementation

Make the durable decision record describe the protocol that implementation will actually enforce.

**Goal:** Replace the stale digest-lock, noncanonical-writer, and under-specified quarantine language in the
single existing `{#orphan-evidence-fencing-355}` decision with broker-owned `prepared`, `committing`,
and `ambiguous` retention; sole closed-registry linearization; exact-receipt CAS successor;
in-memory typed agy admission; closed evidence schemas; and reserved quota/recovery rules.

**Requirements:** R1-R3, R8-R10, R12.

**Dependencies:** Merged #356 at `811b0470` and #613 at `cb6f44ea`; no prior unit. This is the first
implementation step, not a plan-phase journal edit.

**Files:** `docs/engineering-journal/DECISIONS.md`, `tests/test_concurrency_conformance.py`.

**Approach:** Edit the existing anchor in place, preserve its issue and plan linkage, remove the
resource-scoped digest-lock and noncanonical-writer claims, and add a conformance assertion that the
anchor occurs exactly once and names the protocol invariants above.

**Patterns to follow:** The adjacent #356/#613 canonical decision and the existing concurrency
conformance guards for journal-to-runtime contract drift.

**Test scenarios:** A fixture containing the stale digest-lock or noncanonical-writer wording fails;
missing prepare/committing/ambiguous retention, closed linearization, CAS successor, typed admission,
closed schema, or quota reservation/recovery wording fails; a duplicate or missing anchor fails.

**Verification:** The implementation diff shows one in-place decision correction before behavior
files change, and the focused concurrency conformance selector passes.

### U1. Broker-owned settlement protocol and disposition

Make the broker's durable registry transition the only authority that can accept protected output.

**Goal:** Extend `LeaseBroker.agent_settlement` with broker-owned prepare, commit, abort, retained
authority, exact-receipt close, successor CAS, and read-only refused-output classification.

**Requirements:** R1, R3-R7, R9.

**Dependencies:** U7; merged #356 at `811b0470` and #613 at `cb6f44ea`.

**Files:** `plugins/fleet-core/scripts/fleet_commons/lease_broker.py`,
`plugins/fleet-core/scripts/fleet_commons/orphan_evidence.py` (new),
`tests/test_fleet_lease_broker.py`, `tests/test_orphan_fencing.py` (new),
`tests/test_fleet_commons_resolution.py`.

**Approach:** Persist `prepared` plus renewed authority before a callback can run and persist
`committing` immediately before it. After protected writers return, validate their closed
`settlement_close.v1` and perform one atomic registry replacement that attaches the receipt to the
`ResourceFence`, removes the exact lease, clears eligible admission, and records `closed`; this is the
sole commit linearization. A pre-callback abort releases exact authority. Once callback execution may
have begun, a caught failure best-effort writes `ambiguous`, while failed fsync/rename/registry write,
signal, or death leaves the last durable `prepared`/`committing` state as retained authority. Sweep
and acquire retain/block all three states. Output without the matching closed registry receipt is
unaccepted and quarantine-only; recovery can inspect it but can close only by rerunning an authorized
CAS commit. `acquire_successor` requires the exact predecessor token and receipt hash.

**Patterns to follow:** Existing `LeaseBroker.agent_settlement`, `classify_token`, atomic registry
replacement, exact release, and #613's fail-closed retained-authority contract.

**Test scenarios:** Prove the closed-registry replacement is the reader-visible linearization point;
readers never accept callback output while the durable state is prepared/committing/ambiguous. Inject
fsync, rename, and registry-write failure before and after callback start, plus signal and process
death. A caught failure persists ambiguous when possible; an unwritable registry truthfully leaves
prepared/committing. Restart/sweep/acquire retains each state. Recovery cannot synthesize close from
callback files and must rerun exact CAS commit. Superseded resolves metadata-only; elapsed still-head
resolves expired; matching closed receipt resolves late; mismatched or corrupt authority is evidence
error. Include a real two-process stale-writer/successor race proving stale CAS failure and byte
preservation.

**Verification:** Only a matching closed `ResourceFence` authorizes accepted output, all retained
states block sweep/acquire, and injected failure/death never creates a false close.

### U2. Write-once quarantine, orphan events, and close seals

Preserve rejected payloads safely and make later classification auditable.

**Goal:** Extend the existing machine-local audit store with machine-validated evidence schemas,
reserved bounded quarantine, deterministic abandoned-staging recovery, immutable events, strict
readers, and write-once generation settlement seals without changing current paths.

**Requirements:** R4-R6, R8-R10.

**Dependencies:** U1.

**Files:** `plugins/fleet-core/scripts/fleet_commons/audit_store.py`,
`plugins/fleet-core/scripts/fleet_commons/orphan_evidence.py`,
`plugins/fleet-core/schemas/orphan-evidence-v1.schema.json` (new, or an equivalent closed Python
schema registry), `tests/fixtures/orphan_evidence/` golden and malformed fixtures,
`tests/test_audit_store.py`, `tests/test_orphan_fencing.py`.

**Approach:** Validate duplicate-key-free input against the HTD's closed schemas and cross-record
bindings. Under the owner-only quota lock, write `reservation.v1`, count its bytes and item toward the
caps, advance it through payload-written and manifest-written, publish to the digest-derived path,
then create the write-once commit marker last. Startup, publication retry, and operator
`quarantine recover` retain current-boot live owners; for dead owners or boot change they finalize a
complete digest-valid payload/manifest or delete only incomplete/corrupt staging and release its
reservation. The one-hour live-reservation age is alert-only. Emit metadata-only superseded events.
Write an audit close seal only as a mirror after the broker's canonical close. Strict readers
distinguish absent, partial, corrupt, and complete; identical publication converges while conflicting
metadata fails.

**Patterns to follow:** Audit-store 0600 temp/link/replace primitives and safe-name guards;
`evidence_ledger.py` content-addressed custody semantics; #356 effective-user/no-symlink checks.

**Test scenarios:** Golden round-trip and malformed fixtures cover every record type, duplicate keys,
unknown/missing fields, all scalar/list bounds, closed enums, digest domains, canonical resource refs,
and mismatched resource/token/lease/run/generation/receipt/expected-output linkage. Expired payload
round-trips with verified digest, closed payload gets a distinct event, and superseded output stores
metadata only. Kill after reservation, payload, manifest, publication, and marker creation, then
restart and prove exact accounting: live owners remain even after one hour; dead/previous-boot
complete staging finalizes; incomplete/corrupt staging alone is removed. Include simultaneous
last-slot contenders, identical convergence, conflicting metadata rejection, cap exhaustion with no
eviction, and proof that recovery never touches committed or under-30-day evidence. Unsafe
permissions, symlinks, digest mismatch, disk failure, and payloads at or above 128 MiB fail without
live acceptance.

**Verification:** Every forensic reader verifies schema, bindings, commit marker, and digest; restart
recovery preserves both caps and retention without time-based live-owner reclamation; live audit paths
are unchanged for current writes.

### U3. Fence agy auto-apply

Make a stale agy retry unable to apply or publish over its successor.

**Goal:** Put direct agy `auto-if-clean`/`apply-if-clean` live mutation and armed mirroring inside the
canonical settlement while retaining terminal bundle truth and unique-run compatibility.

**Requirements:** R1-R9, R12.

**Dependencies:** U1, U2.

**Files:** `plugins/agy/scripts/agy_delegate.py`,
`plugins/agy/scripts/agy_lease_admission.py` (new),
`plugins/agy/skills/agy-delegate/SKILL.md`,
`plugins/agy/skills/agy-delegate/references/delegation-contract.md`,
`plugins/agy/commands/delegate.md`, `plugins/agy/agents/agy-coder.md`, `plugins/agy/README.md`,
`tests/test_agy_delegate_contract.py`, `tests/test_agy_delegate_reliability.py`,
`tests/test_agy_run_lease.py`, `tests/test_agy_apply_policy.py`, `tests/test_orphan_fencing.py`.

**Approach:** Require `--lease-resource-key` only for launched `auto-if-clean`/`apply-if-clean`.
Immediately after strict Git-root resolution and before clone/subprocess,
`agy_delegate.main()` calls
`agy_lease_admission.resolve_direct_agy_admission(repo_root, resource_key, run_id, providers)`.
That producer imports packaged fleet-core `concurrency_policy.AdmissionLimits` and broker providers;
derives session ID from canonical repository identity plus run ID, fixed
`agy-direct:<effective-uid>` owner, current PID/provider process start, packaged policy digest and
limits, `read-write`, broker-default TTL, canonical resource ref, and the packaged direct-apply
expected-output contract; calls `configure_session_admission` immediately; and passes its immutable
typed record directly in memory to `run_agy_supervised`. No file, environment, envelope, prompt,
bundle, or engine field transports admission, and any missing record or override fails before
subprocess. Acquire from that record before external launch, retain its admission through exact lease
close, and clear only after no live lease. Renew during supervision; finish runner and clone
verification before settlement. Broker commit performs live patch and strict audit mirroring under
the lock and creates the canonical receipt; the audit seal is a mirror. Unique-run forensic mirroring
outside canonical acceptance remains best-effort. On refusal, never apply: superseded records
metadata only; expired quarantines the patch/result; closed plus matching receipt quarantines it as
late. Add terminal `write_disposition`. Renewal failure terminates before apply; early clone/runner
failure aborts exact current authority, and failed release remains loud.

**Patterns to follow:** Existing `run_agy_supervised` watchdog and die-clean paths; terminal-bundle
guarantee; `_PASSING_STATUSES` as the single exit mapping; audit store as the machine-local durable
mirror.

**Test scenarios:** Cover selectors `superseded_lease_rejected`, `expired_lease_quarantined`,
`late_writer_after_close`, `resource_key_required_for_auto_apply`,
`untrusted_resource_key_override_rejected`, `renewal_failure_prevents_apply`,
`current_settlement_applies_and_seals`, and `armed_mirror_failure_is_nonpassing`. Assert the resolver
runs after strict Git-root resolution but before any clone/subprocess; field derivation uses packaged
limits/providers; the typed record has exact fields/types/bounds; only the CLI key is input; every
alternate transport/override and a missing resolver/record fail before launch; admission persists
until exact lease close. Include a real two-process old-writer/retry race proving successor bytes
remain unchanged.

**Verification:** Existing agy bundle tests remain green, and the issue selectors
`superseded_lease_rejected` and `expired_lease_quarantined` pass against the production wrapper seam.

### U4. Fence registered Saga and Team Execution manifest writers

Make every documented accepted manifest transition use the same broker authority as dispatch.

**Goal:** Preserve registered Saga settlement while making Team Execution claim and adjudication
writers canonical broker commits whose stable resource identity is `execution_id` alone.

**Requirements:** R1-R10, R12.

**Dependencies:** U1, U2.

**Files:** `plugins/saga/scripts/engine_dispatch.py`,
`plugins/saga/scripts/manifest_store.py`,
`plugins/team-execution/skills/team-execution/references/worker-manifest.md`,
`plugins/team-execution/skills/team-execution/references/external-engine-workers.md`,
`tests/test_saga_engine_dispatch.py`, `tests/test_manifest_consumer_matrix.py`,
`tests/test_concurrency_conformance.py`, `tests/test_orphan_fencing.py`.

**Approach:** Registered `dispatch` and advisory-panel facts continue through their current lease and
broker settlement. The Team Execution resource key is canonical `execution_id`; `attempt_id` is
receipt/evidence metadata and never changes resource identity. `record_dispatch_manifest` acquires
`acquire_successor` using the registered dispatch's exact close token and receipt hash, then broker
commit writes the manifest plus strict audit mirror and returns the claim close receipt.
`adjudicate_manifest` acquires the successor from that exact claim receipt, rereads the current
manifest after entering settlement, applies adjudication, and broker commit writes adjudication plus
strict mirror. Retries name their expected predecessor; stale predecessors cannot reacquire or alter
bytes. Registered dispatch refusal emits metadata-only blocked evidence or expired/late quarantine
from trusted runner output. Callback output or a mirror without the broker's matching closed registry
receipt is unsealed/noncanonical and cannot satisfy a gate. Ordinary `manifest_store` writes remain
explicitly noncanonical evidence. Extend the consumer matrix across Python and Markdown protocols so
documented raw calls, missing authority/receipt linkage, and gate consumption of unsealed or
noncanonical manifests fail.

**Patterns to follow:** Existing claim/adjudication validation, registered dispatch receipt binding,
`manifest_store` 0600 atomic replacement, Team Execution's documented chaperone call sites, and
HALT-not-degrade engine-dispatch behavior.

**Test scenarios:** Existing registered facts remain settled; superseded dispatch appends no accepted
fact; expired/late output quarantines; and panel reconciliation remains one aggregate settlement.
Claim succeeds only from the exact dispatch receipt and commits manifest plus strict mirror;
adjudication succeeds only from the claim receipt, rereads under settlement, and commits updated bytes
plus mirror. Run two processes with different `attempt_id` values for one `execution_id` and prove
they resolve to the same resource: one exact CAS succeeds, the stale CAS fails, and accepted manifest
and mirror bytes remain unchanged. Python/Markdown fixtures containing documented raw calls or gate
acceptance of an unsealed/noncanonical manifest fail the consumer matrix.

**Verification:** Existing engine-dispatch, reconciliation, claim-provenance, and gate suites remain
green; every documented Team Execution accepted transition has a matching broker close receipt and
rejected/noncanonical output cannot satisfy a gate.

### U5. Derived cross-bridge orphan projection

Turn immutable lease/evidence facts into deterministic reclaim candidates.

**Goal:** Implement a read-only projector and thin Saga CLI that flag aged, empty, quarantined,
blocked, and post-close cases with the correct owner and evidence references.

**Requirements:** R6, R9-R11.

**Dependencies:** U3, U4.

**Files:** `plugins/fleet-core/scripts/fleet_commons/orphan_evidence.py`,
`plugins/saga/scripts/reap_orphans.py` (new), `tests/test_reap_orphans.py` (new),
`tests/test_outcome_liveness.py`. Do not modify `outcome_liveness.py` unless an adapter cannot consume
its current public evidence.

**Approach:** Normalize broker state, agy snapshots/audit mirrors, settled Saga facts, existing
outcome heartbeat/terminal facts, quarantine events, and close seals. Emit `stalled`,
`empty-artifacts`, `expired-write-quarantined`, `superseded-write-blocked`, and
`late-write-after-close`, with evidence errors for malformed, contradictory, partial, or unsealed
terminal state. A successor generation makes an older seal historical. Emit sorted
`orphan_candidate.v1` records with evidence refs and named owner; `scan` never mutates stores or
invokes a reaper.

**Patterns to follow:** `outcome_liveness` max-by-timestamp heartbeat handling and idempotent terminal
semantics; `delegation_audit_query` deterministic audit-store scans; derived-on-read outcome reports.

**Test scenarios:** Cover `stalled_or_empty_flagged`, `late_writer_after_close`, recent renewal not
flagged, intermediate Saga claim not falsely terminal, successor generation making an older seal
historical, byte-deterministic repeated scans, and a mixed 15-run fixture assigning owners correctly.
Assert the scan performs no delete, kill, retry, registry write, or ledger append, and existing R31
liveness tests remain unchanged.

**Verification:** Published issue selectors `stalled_or_empty_flagged` and
`late_writer_after_close` pass while existing R31 stalled-terminal tests remain unchanged.

### U6. Conformance, release, journal, and PR evidence

Prevent future bridge writers from bypassing containment and ship coherent installed metadata.

**Goal:** Inventory every canonical acceptance seam and noncanonical forensic builder, enforce drift,
publish all three plugins coherently, and satisfy the agy delegation-proof gate.

**Requirements:** R7, R11-R13.

**Dependencies:** U3-U5.

**Files:** `plugins/saga/references/evidence-write-sites.md` (new),
`plugins/fleet-core/README.md`, `docs/engineering-journal/DECISIONS.md`,
`docs/engineering-journal/LEARNINGS.md`, `scripts/delegation_proof_receipt.py` (new),
`tests/test_delegation_proof_receipt.py` (new), the four plugin manifests and changelogs,
`.claude-plugin/marketplace.json`, `tests/test_concurrency_conformance.py`,
`tests/test_agy_plugin.py`, `tests/test_saga_plugin.py`, a genuine
`docs/delegation-proofs/agy/<run>.proof.json`, its matching transcript, and the distinct
`docs/evidence/issue-355/{version-gate,fleet-sweep}-command-receipt.json` artifacts.

**Approach:** Inventory acquire, renew, settlement, rejected-output handling, seal, reader, and owner
for every canonical acceptance seam. Unique bundle files and ordinary manifest-store writes receive
explicit noncanonical rows. Update release surfaces to fleet-core `0.13.0`, agy `0.5.0`, and Saga `0.100.0`;
the agy bump is not PR-ready without genuine proof and transcript evidence.
Run the receipt-producing wrapper from the recorded merge base. Its closed `run` subcommand invokes
the fixed internal `check_delegation_proof.py` argv and writes the mode-specific receipt; `verify`
then validates that receipt against current base, head, proof, and transcript bytes:

```bash
uv run python scripts/delegation_proof_receipt.py run --mode version-gate \
  --base-ref <recorded-merge-base-sha> --proofs-dir docs/delegation-proofs \
  --receipt-out docs/evidence/issue-355/version-gate-command-receipt.json
uv run python scripts/delegation_proof_receipt.py verify \
  --receipt docs/evidence/issue-355/version-gate-command-receipt.json
uv run python scripts/delegation_proof_receipt.py run --mode fleet-sweep \
  --proofs-dir docs/delegation-proofs --transcripts-dir docs/delegation-proofs \
  --receipt-out docs/evidence/issue-355/fleet-sweep-command-receipt.json
uv run python scripts/delegation_proof_receipt.py verify \
  --receipt docs/evidence/issue-355/fleet-sweep-command-receipt.json
```

Both mode-specific receipts bind exact argv, cwd, recorded merge-base SHA, base/head SHA, proof and
transcript digests, stdout, stderr, exit code, UTC bounds, and a self-digest. Both `run` and `verify`
commands must exit 0; unit tests, direct unreceipted checks, dry runs, fabricated proof, or a
transcript mismatch do not satisfy release proof.

**Patterns to follow:** #350 concurrency and #356 lease lifecycle inventories; release triad/parity
guards; journal decisions in the same behavioral commit.

**Test scenarios:** Inventory matches all supported writers and installed versions agree. Unique
bundle and ordinary manifest-store rows remain explicitly noncanonical. Injected documented raw
manifest use, direct manifest overwrite, unguarded live apply, missing rejection/seal/reader
ownership, stale inventory, release drift, absent/fabricated delegation proof, nonzero proof command,
or missing/mismatched command receipt fails.

**Verification:** Conformance, release parity, changelog, plugin loading, both exact non-dry proof
commands and command-receipt validation, and full repository gates are green from a clean branch.

---

## Requirement Coverage

| requirement | units | primary proof |
|---|---|---|
| R1-R3 | U7, U1, U3, U4 | corrected decision, durable-state failure injection, and two-process guarded-commit race |
| R4-R6 | U1-U4 | superseded byte preservation and expired/closed quarantine selectors |
| R7 | U3, U4, U6 | existing agy/Saga regression suites and manifest/result parity |
| R8-R9 | U7, U1-U5 | quota-reservation crash recovery, closed receipt, CAS, and post-close mutation |
| R10-R11 | U2, U5 | closed-schema fixtures and deterministic mixed-run projection with no mutation |
| R12-R13 | U4, U6, U7 | fenced Team Execution transitions, decision conformance, and executable release proof |

## Review Finding Closure Map

| finding | closed by | executable closure |
|---|---|---|
| `d355-saga-manifest-unfenced` | U4 / R12 | claim/adjudication receipt-chain CAS, same-resource two-process race, Python/Markdown consumer gate |
| `d355-settlement-not-failure-atomic` | U1 / R3 | fsync/rename/write/signal/death injection plus reader/recovery linearization tests |
| `d355-agy-admission-undefined` | U3 / R2 | direct resolver timing, exact typed-field derivation, and alternate-transport rejection |
| `d355-projection-contract-incomplete` | U2/U5 / R10 | closed schema registry, golden/malformed fixtures, and cross-record binding failures |
| `d355-release-proof-not-executable` | U6 / R13 and Verification | exact non-dry version-gate/fleet-sweep commands plus retained command receipts |
| `d355-canonical-decision-stale` | U7 | one-anchor diff and concurrency-conformance evidence before implementation |
| `d355-quarantine-reservation-recovery` | U2 / R8 | kill-point restart accounting, last-slot race, no-eviction and retention proof |
| `d355-quarantine-unbounded-total` | R8 / U2 | preserved prior closure: 512 MiB, 256 entries, reservations included |
| `d355-schema-broker-types-conflict` | U2 / R10 | real UUID epoch and provider process-identity round trips through every closed schema |
| `d355-expected-output-prelease-cycle` | U3 / R2 | lease-independent template first, then exact lease-bound expected-output record |
| `d355-release-proof-receipt-unexecutable` | U6 / R13 | receipt wrapper `run` and `verify` with distinct mode-bound artifacts and tamper tests |
| `d355-retained-settlement-recovery-undefined` | U1 / R3 | root-only same-generation recovery API with dead-owner, digest, phase, and CAS checks |

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
- UI/dashboard surfacing, cross-host/distributed locking, quarantine encryption, retention policy
  beyond the required 30-day minimum, or automatic application of quarantined content.
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
| global settlement lock held too long | unrelated broker activity stalls | forbid runner execution, verification commands, and large payload copying inside settlement |
| nested agy/Saga double admission | one run acquires competing authority | Saga-routed agy stays patch-only under Saga's outer lease; only direct `auto-if-clean` acquires the agy apply lease |
| forensic disposition race | rejected-output classification is mistaken for authority | only settlement authorizes acceptance; post-refusal classification is evidence only |
| partial accepted settlement | durable facts appear complete without a terminal receipt | callback output without the matching closed registry receipt is unaccepted/quarantine-only and cannot satisfy a gate |
| quarantine leaks sensitive or huge output | local disclosure/disk exhaustion | 0700/0600/no-follow, reject at or above 128 MiB, no prompt/env capture |
| #613 cleanup ambiguity | unreclaimed authority is reported as reclaimed | retained authority remains unreclaimed and cannot project as success |

---

## Verification

Run focused gates after their owning units, then the full repository gate:

```bash
uv run pytest tests/test_fleet_lease_broker.py tests/test_audit_store.py \
  tests/test_orphan_fencing.py tests/test_fleet_commons_resolution.py -q

uv run pytest tests/test_agy_delegate_contract.py tests/test_agy_delegate_reliability.py \
  tests/test_agy_run_lease.py tests/test_agy_apply_policy.py -q

uv run pytest tests/test_saga_engine_dispatch.py tests/test_manifest_consumer_matrix.py \
  tests/test_reap_orphans.py tests/test_outcome_liveness.py -q

uv run pytest tests/test_concurrency_conformance.py tests/test_agy_plugin.py \
  tests/test_saga_plugin.py tests/test_release_triad.py \
  tests/test_check_delegation_proof.py -q

uv run python scripts/delegation_proof_receipt.py run --mode version-gate \
  --base-ref <recorded-merge-base-sha> --proofs-dir docs/delegation-proofs \
  --receipt-out docs/evidence/issue-355/version-gate-command-receipt.json
uv run python scripts/delegation_proof_receipt.py verify \
  --receipt docs/evidence/issue-355/version-gate-command-receipt.json
uv run python scripts/delegation_proof_receipt.py run --mode fleet-sweep \
  --proofs-dir docs/delegation-proofs --transcripts-dir docs/delegation-proofs \
  --receipt-out docs/evidence/issue-355/fleet-sweep-command-receipt.json
uv run python scripts/delegation_proof_receipt.py verify \
  --receipt docs/evidence/issue-355/fleet-sweep-command-receipt.json

uv run pytest
uv run ruff format --check .
uv run ruff check .
uv run mypy plugins/ scripts/ tests/ --ignore-missing-imports
uv run bandit -r plugins/
git diff --check
```

The concurrency validator independently proves canonical `agent_settlement` behavior, including the
real two-process old-writer/retry race. The event-flow validator traces current, expired, superseded,
closed, incomplete-seal, and successor-generation paths. Both fail closed on self-report or missing
command evidence.

Manual evidence includes one old agy writer racing a retry against the same live file, one expired
payload recovered from quarantine with matching digest, one post-close artifact mutation surfaced as
late-writer-after-close, and one mixed projection demonstrating no destructive action occurred.
PR readiness additionally requires the genuine authorized agy `0.5.0` bridge proof and transcript,
both exact non-dry commands exiting 0, and retained command receipts recording argv, cwd, merge base,
base/head SHA-256, proof/transcript SHA-256, stdout/stderr, and exit code.

---

## Failure Modes and Stop Conditions

- `run-lease.json`, an environment value, manifest prose, or external-engine output becomes token
  authority: stop and restore #356 as the sole trusted source.
- Any accepted live/evidence write occurs outside `agent_settlement`, or runner execution,
  verification commands, or large payload copying occurs while its global lock is held: stop as a P0
  authority or contention defect.
- An expired/closed payload lands live, a superseded payload is quarantined instead of rejected, or a
  quarantine failure falls through to acceptance: stop as a P0 evidence-integrity defect.
- A live target changes in any superseded/expired/closed test, or a current successor changes after
  the stale attempt completes: stop as a P0 clobber defect.
- Quarantine follows caller paths, accepts symlinks/unsafe permissions, omits a digest/commit marker,
  or stores over the size cap: stop as a P0/P1 security and durability defect.
- Projection kills/deletes/retries, stores mutable candidate status, or silently treats corruption as
  empty artifacts: stop and restore derived read-only semantics.
- Failed or ambiguous #613 cleanup is projected as reclaimed despite retained broker authority: stop
  as an evidence-integrity defect.
- The implementation duplicates #357's shared liveness engine or #358's reclamation ledger/teardown:
  stop for scope correction.
- Any P0-P3 document/code-review finding remains, either required validator lacks gate-capable
  evidence, the genuine agy delegation proof is absent, release metadata drifts, or the full gate
  fails: no PR/merge.

---

## Workflow Structure

| step_id | depends_on | barrier | role_id | role_kind | independence | execution_class | runtime_agent_name | vehicle | mutation | required_evidence | role_lens_sha256 | profile_sha256 | expected_model | expected_effort | validator_required | validator_disabled | deterministic_contract_sha256 |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| decision-correction | - | - | root | root | n/a | - | - | root | root-only | canonical-decision-diff,one-anchor-check,concurrency-conformance-results | - | - | - | - | n/a | n/a | - |
| implement | decision-correction | - | root | root | n/a | - | - | root | root-only | authorized-diff,focused-tests | - | - | - | - | n/a | n/a | - |
| review-devils | implement | review | devils-advocate-reviewer | agent-lens | preferred | review-high | review_high | auto | none | scored-review,findings | 129f6dca0702ffcd4be7f9e5d0939e8e6806788846ba4058044c931883ef0e63 | 42e86e00e054281b0a79e4b3b9b544c04a31eb2fd6b53c0489adc42ea639c9a8 | gpt-5.6-sol | high | n/a | n/a | - |
| review-security | implement | review | security-reviewer | agent-lens | preferred | review-high | review_high | auto | none | scored-review,findings | bf5bc1b66c0ee3d06071976b659c522c23057c56de5f6cc010556b2653c86980 | 42e86e00e054281b0a79e4b3b9b544c04a31eb2fd6b53c0489adc42ea639c9a8 | gpt-5.6-sol | high | n/a | n/a | - |
| review-architecture | implement | review | architecture-reviewer | agent-lens | preferred | review-high | review_high | auto | none | scored-review,findings | e48b37cea0b26bf39cae4d6611b4219e907d52d284ba6b9489b523a4b16c835f | 42e86e00e054281b0a79e4b3b9b544c04a31eb2fd6b53c0489adc42ea639c9a8 | gpt-5.6-sol | high | n/a | n/a | - |
| review-testing | implement | review | testing-reviewer | agent-lens | preferred | review-high | review_high | auto | none | scored-review,test-gaps | a867575e24c86b0573485d1d8bbd81514af3654d544342677b85f4bed0d9af63 | 42e86e00e054281b0a79e4b3b9b544c04a31eb2fd6b53c0489adc42ea639c9a8 | gpt-5.6-sol | high | n/a | n/a | - |
| validate-concurrency | implement | validate | concurrency-tester | agent-lens | preferred | test-medium | test_medium | auto | none | tester-evidence,command-results | d40188645b7876e32ea592dd9799ee2ad7a2e230d82341611708dd492837b3da | 6d69bb4d5e477574ce186a353a3d2fcc7f8ab6b1f014b93aebb05084aecccc1b | gpt-5.6-terra | medium | true | false | - |
| validate-event-flow | implement | validate | event-flow-tester | agent-lens | preferred | test-medium | test_medium | auto | none | event-trace,command-results | 2e20ab6935b1e17e363b5e28308a9288107532d0118a6a189f07b0e0eaaff356 | 6d69bb4d5e477574ce186a353a3d2fcc7f8ab6b1f014b93aebb05084aecccc1b | gpt-5.6-terra | medium | true | false | - |
| integrate | review-devils,review-security,review-architecture,review-testing,validate-concurrency,validate-event-flow | - | root | root | n/a | - | - | root | root-only | fixed-findings,full-gate,release-parity,delegation-proof,matching-transcript,version-gate-receipt,fleet-sweep-receipt,git-receipt | - | - | - | - | n/a | n/a | - |

## Workflow Operating Contract

- The authorized subject is this issue's implementation paths plus exact release surfaces. Root
  records the pre-existing Git baseline before `decision-correction`; unrelated worktree paths are
  excluded. `decision-correction` must land the one-anchor diff and passing focused conformance
  evidence before `implement` starts.
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
