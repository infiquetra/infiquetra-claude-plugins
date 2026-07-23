---
title: Registry schema forward-compatibility — tolerate-and-preserve unknown fields, doctor/repair verbs
type: fix
status: active
date: 2026-07-23
origin: infiquetra/infiquetra-claude-plugins#617
---

# Registry schema forward-compatibility — tolerate-and-preserve unknown fields, doctor/repair verbs

## Summary

Make the fleet-lease registry reader forward-compatible: unknown **additive** fields from a
schema-newer writer are tolerated on read and preserved byte-faithfully on write, instead of
bricking every older reader with `RegistryCorruptError`. Ship an operator `doctor` (read-only
report) and `repair` (explicit strip-unknown down-migration with backup) verb pair. The fix is
reader-side only and writes **zero new registry fields**, so shipping it cannot itself poison any
pre-#617 reader.

## Problem Frame

The registry (`~/.local/state/infiquetra/fleet-leases/registry.json`) is a shared, machine-wide
mutable file with multiple schema-versioned writers and strict-closed readers: `_closed_mapping`
(`plugins/fleet-core/scripts/fleet_commons/lease_broker.py:363-374`) raises `RegistryCorruptError`
(`:206`) on ANY unknown key anywhere in the document. One newer write bricks every older reader
fleet-wide. This has struck twice:

- **2026-07-17** (session `2c563b9d`): saga 0.99.1's bundled newer fleet-core wrote
  `recovery_capability_sha256`, `settlements`, and per-fence `close_receipt`; the active
  fleet-core 0.12.0 rejected the whole file — `outcome.py` crashed `RegistryCorruptError` and
  lease hooks halted all subagent tool use mid-run. Recovery was manual hand-editing.
- **2026-07-22** (#616 work session, LEARNINGS `{#broker-schema-forward-poisoning-616}`): the
  repo broker wrote the new `Lease.isolation` field; the *installed* fleet-core 0.19.0 readers
  hard-rejected every hook-fenced Bash call on the machine ("unknown field(s): isolation") —
  a fleet-wide self-inflicted outage from a not-yet-merged repo diff.

`Registry.from_dict` (`:1255-1360`) already carries **four bespoke hand-rolled migration arms**
accreted one per past field addition (closed_owner_admissions backfill `:1257-1262`,
recovery_capability_sha256 `:1263-1266`, session_admissions + settlements `:1267-1277`,
close_receipt via `_LEGACY_FENCE_KEYS` `:67`). Every schema addition currently requires a bespoke
reader-side arm, and any reader that lacks the arm bricks. The journal's standing rule: no further
broker schema field may ship through governed choreography until this read-tolerance layer lands.

## Requirements

- **R1 — tolerate-and-preserve.** Unknown additive keys in tolerance-scoped mappings (registry
  top level, per-lease, per-fence, per-admission, per-settlement outer record, per-owner-close)
  are tolerated on read (no `RegistryCorruptError`) and preserved byte-faithfully through the
  read → mutate → write round-trip. Preservation must survive `Registry.from_dict` →
  typed-dataclass rebuild → `to_dict` (`:1362-1381`).
- **R2 — known-field validation unchanged.** Every existing value/type/invariant check still
  fails closed: epoch/UUID/timestamp/digest formats, bounded capacities (`:183-194`,
  `:1303-1308`), fencing-sequence monotonicity (`:1333-1334`), settlement live-head binding
  (`:1335-1350`), fence-epoch match (`:1331-1332`).
- **R3 — schema identity gate unchanged.** `schema != "fleet_lease_registry.v1"` (`:29`,
  `:1279-1282`) still fails closed. A future v2 is a deliberate breaking lane; this plan adds no
  minor-version negotiation.
- **R4 — digest-covered commitment records stay closed.** Mappings whose content is verified by
  `_record_sha256` (`:629-631`; settlement-close receipt checks `:703-705`, `:774-778`) keep the
  strict closed vocabulary — unknown keys there still fail closed, because every byte participates
  in the hash commitment. U1 enumerates the digest-covered mappings in code comments and pins the
  carve-out with tests.
- **R5 — zero new written fields.** For an extras-free registry, the serialized output of the new
  broker is byte-identical to today's (same keys, same `sort_keys=True` ordering, `:1654`).
  Shipping #617 cannot brick any pre-#617 reader.
- **R6 — write-path integrity unchanged.** `_write_registry`'s double round-trip validation
  (`:1642`, `:1646`) passes with extras present; temp + `os.replace` + 0600 + dir-fd anchoring
  (`:1649-1667`) byte-unchanged.
- **R7 — doctor verb.** A read-only adapter CLI verb reporting document validity, an
  unknown-field inventory (JSON-path locations + counts), and invariant status; distinct exit
  codes for clean / tolerated-unknowns-present / corrupt. Never mutates.
- **R8 — repair verb.** An explicit adapter CLI verb performing the down-migration the 2026-07-17
  manual recovery did: backup the document, strip tolerated unknown fields, revalidate strictly,
  write atomically (temp + rename, 0600). Refuses documents corrupt beyond unknown-field
  stripping. Never runs implicitly; intended for rollback-to-older-broker scenarios.
- **R9 — incident regression pins.** A simulated schema-newer document (future unknown fields at
  top level, inside a lease, inside a fence) reads clean and round-trips intact; genuinely
  malformed documents (bad values, capacity floods, sequence violations) still fail closed with
  the same errors as today.
- **R10 — live acceptance (operator-gated, post-merge).** On the installed rollout under armed
  hooks: `doctor` on the live registry reports clean; back up the live registry, then inject a
  synthetic future field into it; hooks and a real async Agent spawn still bind and complete (no fleet-wide halt —
  the #616 outage shape, now survived); `repair` strips it back to closed shape with a backup;
  strict re-validation passes. Follows the #615 R9 / #616 + #644 R8 operator-gated pattern.

## Key Technical Decisions

**KTD1 — tolerance line = containers tolerant, commitments closed:** unknown-key tolerance
applies to container mappings (registry top level and per-record maps); digest-covered commitment
records (settlement-close receipts verified by `_record_sha256`) stay strictly closed. Rationale:
container fields are mutable state where additive fields are schema evolution; commitment records
are hash-bound evidence where an unknown byte is indistinguishable from tampering. This preserves
the fail-closed integrity stance exactly where bytes are semantics.

**KTD2 — extras passthrough as a per-dataclass `extras` mapping:** each tolerance-scoped
dataclass (and `Registry` itself) gains an `extras` mapping captured at `from_dict` (the unknown
remainder after known-key validation) and merged last in `to_dict`. Rationale: `to_dict` rebuilds
the document from typed dataclasses, so passthrough must ride the dataclass or it is silently
dropped — which is the round-trip hazard that would corrupt the newer writer's state. Merge-last
plus the existing `sort_keys=True` keeps output deterministic; extras are disjoint from known
keys by construction, so collisions are impossible.

**KTD3 — no version stamp, no migration framework:** the schema string stays
`fleet_lease_registry.v1` and no new field is written. Rationale: any new written field would
itself brick every pre-#617 reader — the exact defect under repair (R5 is the stop condition the
issue names). The four existing bespoke legacy arms remain as-is; future breaking changes ride an
explicit v2 schema string, which fails closed by design. Rejected alternatives: a `schema_minor`
stamp (new field → self-defeating), writer-version stamping with migrate-on-open (machinery with
no consumer while v1 is additive-only), minor-version string lane `v1.x` (changes the `schema`
value, which `:1279` exact-matches — bricks older readers identically).

**KTD4 — repair is an explicit operator down-migration verb, not auto-recovery:** `doctor` /
`repair` land as saga adapter CLI verbs (`plugins/saga/scripts/lease_broker.py`, beside
`inspect` / `sweep`, `:443-474`) delegating to fleet-core broker methods; the `saga:fleet-doctor`
skill stays strictly read-only. Rationale: the adapter CLI is the shipped operational surface;
auto-repairing shared fenced state on read would be a tamper/corruption-masking vector. With
tolerance shipped, repair's remaining job is deliberate rollback support: strip newer fields so
an older broker can read the file — plus a shipped path for the next "corrupt beyond tolerance"
incident triage.

**KTD5 — tolerance is bounded, corruption stays detectable:** the serialized size of all
preserved unknown extras per document is capped (64 KiB); above the cap the read fails closed
with `RegistryCorruptError`. Rationale: tolerance must not erase the corruption line — an
unbounded unknown-blob channel in a 0600 shared-state file invites garbage-flood and smuggling;
the cap keeps the fail-closed posture against non-additive garbage while being far above any
plausible additive-field payload.

## High-Level Technical Design

`_closed_mapping` splits into two callables: the existing strict form (kept verbatim for
commitment records and value validation) and a tolerant form returning
`(known: dict, extras: dict)` — known keys validated exactly as today, unknown keys collected
raw. Tolerance-scoped `from_dict`s switch to the tolerant form and thread `extras` into their
dataclass; `to_dict`s emit known fields then merge extras. `Registry.from_dict`'s four legacy
arms are untouched (they act on known keys only). The extras byte-size cap is enforced at
`Registry.from_dict` after collection (KTD5). `doctor`/`repair` reuse the same machinery:
`doctor` = parse tolerant + report extras inventory; `repair` = parse tolerant, re-serialize
known-only, strict-validate, backup + atomic write.

**Honesty note (deployment reality):** forward-compatibility protects only readers at or above
this version — a pre-#617 reader still bricks on a newer write until upgraded. The bridge for
mixed-version windows remains the documented `FLEET_COMMONS_ROOT` rung-1 pin (LEARNINGS
`{#broker-schema-forward-poisoning-616}`); this plan makes future skews benign, it does not
retroactively fix old readers.

## Implementation Units

### U1. Broker read-tolerance layer (fleet-core)

**Goal:** tolerate-and-preserve unknown additive fields per KTD1/KTD2/KTD5 with zero new written
fields.

**Files:** `plugins/fleet-core/scripts/fleet_commons/lease_broker.py`;
tests in `tests/test_fleet_lease_broker.py`.

**Scope:** tolerant-mapping split; `extras` capture/merge on `Registry`, `Lease`,
`ResourceFence`, `SessionAdmission`, `SettlementRecord` (outer record only), and
`OwnerAdmissionClose`; extras byte cap; digest-covered-mapping audit — enumerate every mapping
verified by `_record_sha256` and pin its closed status in a code comment at the carve-out site.
`FencingToken` follows the audit's verdict (it participates in settlement binding; default
closed unless the audit proves it safe to open).

**Test scenarios** (`tests/test_fleet_lease_broker.py`):
unknown top-level key tolerated + preserved through read→write; unknown per-lease / per-fence /
per-admission / per-settlement-outer key preserved; extras survive `_write_registry`'s double
round-trip; extras-free output byte-identical to pre-change serialization (R5 pin); unknown key
inside a settlement-close receipt still fails closed (R4 pin); schema `v2` string still fails
closed (R3 pin); known-field violations (bad epoch, capacity flood, sequence regression,
settlement not binding live head) unchanged errors (R2 pins); extras above the 64 KiB cap fail
closed (KTD5 pin); the four legacy migration arms still fire on their historical shapes.

### U2. doctor / repair operational verbs (fleet-core methods + saga adapter CLI)

**Goal:** shipped operator path replacing the manual 2026-07-17 recovery, per KTD4.

**Depends on:** U1 (reuses the tolerant parse machinery).

**Files:** `plugins/fleet-core/scripts/fleet_commons/lease_broker.py` (broker methods);
`plugins/saga/scripts/lease_broker.py` (CLI verbs beside `inspect`/`sweep` `:443-474`);
tests in `tests/test_fleet_lease_broker.py` (methods) and `tests/test_saga_hooks.py` (CLI seam).

**Scope:** broker `doctor()` returning a structured report (valid | tolerated-unknowns | corrupt,
extras inventory with JSON paths, invariant status) and `repair()` (backup file beside the
registry with a timestamped suffix, strip extras, strict revalidate, atomic 0600 write, refuse
when strict revalidation still fails); adapter verbs `doctor` (exit codes 0 clean / 3
unknowns-present / 4 corrupt) and `repair` (requires an explicit `--strip-unknown` flag; no
default action). Lock/mutation discipline matches existing write paths (single `_locked()` write).

**Test scenarios:** doctor on clean registry → clean, no mutation (file bytes unchanged); doctor
on extras-carrying registry → inventory lists exact paths, exit 3; doctor on corrupt registry →
exit 4, never raises uncaught; repair strips extras, backup exists with original bytes, result
strict-validates, 0600 preserved; repair on a document corrupt beyond stripping → refused,
registry untouched; repair on clean registry → no-op with explicit "nothing to strip" report;
CLI seam: verbs route through the shim-resolved broker (no direct import bypass).

### U3. Release surfaces + docs

**Goal:** ship the release story in the same PR per repo norms.

**Depends on:** U2.

**Files:** `plugins/fleet-core/.claude-plugin/plugin.json` (bump — minor),
`plugins/saga/.claude-plugin/plugin.json` (bump — adapter CLI changed),
`.claude-plugin/marketplace.json`, both CHANGELOGs, drift-guard pins (`tests/test_saga_plugin.py`,
`tests/test_liveness_events.py`, `tests/test_team_execution_liveness.py` patterns),
`docs/engineering-journal/DECISIONS.md` (`{#registry-forward-compat-617}` mirroring KTD1-KTD5).

**Test expectation:** none beyond the drift-guard pin updates — release-surface unit; gated by
`python3 scripts/check_release_surface_parity.py` and the merge-time sibling-PR version-collision
re-check.

## Scope Boundaries

**Out of scope (true non-goals):**

- Claim-policy change (claim preferring unstamped reservations) — the #644 work-session's D2 note
  called this "#617 claim-policy territory", but it does not match this issue's body (schema
  forward-compat); it needs a fresh defect/enhancement issue. Explicitly adjudicated OUT.
- #646 admission/TTL lifecycle redesign; #645 boot-id cohort split; #647 unfenced edge.
- #642 — the stale `~/.claude/plugins/installed_plugins.json` install registry. A different file
  and mechanism entirely; do not conflate with the fleet-lease registry.
- Harness-side detect-and-refuse of mid-run plugin reload swapping schema writers (issue proposed
  fix 4): harness territory; the operational hazard is documented in LEARNINGS and the DECISIONS
  entry instead.
- Retroactive protection of pre-#617 readers (impossible by construction — see Honesty note).
- `saga:fleet-doctor` skill behavior change (stays read-only; may *mention* the new verbs in a
  doc line only if zero behavior change).

**Deferred to Follow-Up Work:**

- Migration framework / writer-version stamping — revisit when a genuinely breaking v2 schema is
  first needed (KTD3's "revisit when").
- Extending `doctor` output into `saga:fleet-doctor`'s audit report.

## Risk Analysis & Mitigation

- **Silent drop of newer state by an older-but-tolerant writer** — the round-trip hazard KTD2
  exists to kill; pinned by preservation tests in U1 (highest-severity failure mode: data loss
  masquerading as success).
- **Weakened tamper detection** — mitigated by KTD1's commitment carve-out, R2's unchanged value
  validation, and KTD5's size cap; the corruption line moves only for additive unknown keys in
  container maps.
- **Accidental new written field** — R5's byte-identity pin makes this a test failure, not a
  fleet outage.
- **Repair misuse on live state** — repair requires an explicit flag, takes a backup first, and
  refuses anything it cannot strict-validate after stripping; it is documented as a rollback
  tool, not maintenance.
- **Sibling-PR version collision at merge** — re-check open PRs at U3 and at merge time
  (evidence-integrity gotcha; recurred on prior outcomes).

## Acceptance criteria (issue-derived)

1. A schema-newer registry document with additive unknown fields is read without
   `RegistryCorruptError` and round-trips byte-faithfully (R1, R9 — fixes the 2026-07-17 and
   2026-07-22 incident shapes for all future skews).
2. `doctor` and `repair` ship as operator verbs with the R7/R8 contracts — the manual recovery
   has a shipped path.
3. R10 live acceptance passes post-merge under armed installed hooks (operator-gated).
4. Zero new registry fields written; strict behavior preserved for corruption, commitments, and
   schema-identity mismatches (R2-R5).
