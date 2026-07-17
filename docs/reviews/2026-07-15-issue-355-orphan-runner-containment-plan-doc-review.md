# Doc review - orphan runner containment plan (#355)

Verdict: **READY AT PRE-IMPLEMENTATION GATES**. The refreshed post-#613 plan has zero unresolved
P0-P3 findings.

## Review contract

- Target: `docs/plans/2026-07-15-issue-355-orphan-runner-containment-plan.md`
- Baseline: `cb6f44ea002a776e9a3cd3eea125c384c90ea65a`
- Reviewed input digest: `35211e260e9e4c826af80d7a2bbdb9687153e0ae89a125d0e2a3d2669c915fd8`
- Logical role: `security-reviewer`
- Role lens digest: `bf5bc1b66c0ee3d06071976b659c522c23057c56de5f6cc010556b2653c86980`
- Verdict: `accept` (overall 10/10; denominator 5)
- Linked issue: `infiquetra/infiquetra-claude-plugins#355`; outcome node `sub-355`
- Override rationale: none

## Finding closure

| ID | Status | Closure |
|---|---|---|
| `d355-saga-manifest-unfenced` | CLOSED | Team claim/adjudication use one execution-stable resource and exact predecessor-receipt CAS settlement. |
| `d355-settlement-not-failure-atomic` | CLOSED | The closed-registry replacement is the sole linearization point; prepared, committing, and ambiguous retain authority on failure. |
| `d355-agy-admission-undefined` | CLOSED | A named in-process resolver derives the closed admission from packaged policy, canonical Git identity, process identity, and the trusted CLI key. |
| `d355-projection-contract-incomplete` | CLOSED | Machine-checkable closed schemas define types, bounds, enums, digest domains, and cross-record bindings. |
| `d355-release-proof-not-executable` | CLOSED | A genuine bridge proof and transcript plus receipt-producing non-dry version and fleet gates are mandatory. |
| `d355-quarantine-unbounded-total` | CLOSED | Quarantine enforces per-item, aggregate-byte, and entry caps under one reservation lock. |
| `d355-canonical-decision-stale` | CLOSED | U7 corrects the existing journal anchor before implementation and conformance rejects stale wording. |
| `d355-quarantine-reservation-recovery` | CLOSED | Durable reservations recover complete staging or remove only dead-owner incomplete staging without touching committed evidence. |
| `d355-schema-broker-types-conflict` | CLOSED | Schemas use the broker's canonical UUID epoch and bounded provider process identity. |
| `d355-expected-output-prelease-cycle` | CLOSED | A lease-independent template is resolved first; the bound expected-output record is created only after acquisition. |
| `d355-release-proof-receipt-unexecutable` | CLOSED | The fixed-argv wrapper writes and verifies separate mode-bound, tamper-evident command receipts. |
| `d355-retained-settlement-recovery-undefined` | CLOSED | Root-only same-generation recovery requires exact retained authority, dead owner, matching policy and digests, and broker-locked CAS. |

## Evidence and gates

- `git diff --check` passed.
- The plan preserves the merged #356/#613 broker as the sole authority and removes the stale second-lock design.
- Fault injection covers callback, receipt, fsync, rename, registry, signal, death, recovery, stale successor, quota, and projection boundaries.
- Team Execution `2.19.0` is included because its documented claim/adjudication protocol changes.
- Implementation must first complete U7, regenerate the exact Verified Workflow candidate and role/profile receipts, and retain genuine delegation-proof command evidence.

Remaining findings: P0 0, P1 0, P2 0, P3 0.

## Residual risk

Quarantined external output remains local forensic evidence and may contain sensitive patch bytes;
strict ownership, no-follow handling, aggregate quotas, and minimum retention limit the exposure.
Retained ambiguous authority can wedge one resource by design; the documented root-only recovery path
prefers a visible stall over an unsafe takeover.
