# cc-workflows run protocol

The Workflow run protocol, carried with the capability that owns it (#925, U4 — moved from
Saga's `/work` Phase 1.5, which stays the driver-side seam).

## Invocation identity

Mint `WORKFLOW_INVOCATION_ID` **once** for a logical Workflow launch, record it with the
workflow handle in the saga tick, and reuse that exact value only after a crash or explicit
resume. A later launch of the same unchanged spec must mint a new value. Generated agents
receive no filesystem or ledger-write permission; the driving `/work` session is the only
writer. The driver-side pre-submit sequence in `/work` Phase 1.5 (settlement metadata +
manifest + one spawn attempt per unit) is exact-replay idempotent: on resume it replays the
`manifest` command and appends only spawn attempts the ledger report proves are still absent.

## Lease contract — frozen shape, retired admission (#356, #677/U4)

The `workflow_lease_reservation.v1` metadata shape is frozen and still validates closed and
launch-ready, but no batch lease is reserved, attested, renewed, or settled: admission retired
with the lease broker (plan #677, KTD4 — no batch lease exists to renew). The `reserve` /
`attest` / `release` / `renew` commands keep their vocabulary and report the retired,
broker-free outcome; the launch gate survives as a contract-shape check only.

The final `attest` remains the launch gate: any refusal (malformed or not-launch-ready
metadata) means **launch none and HALT**. Since #677/U5 the lease lifecycle hook is deleted
outright: Agent/Task spawns carry no lease admission at all — no reservation, no claim, no
lifecycle records. Generated JavaScript and children receive neither a registry path nor
filesystem access.

## Release and renew

After the Workflow returns, or after the host authoritatively confirms cancellation, close the
protocol with the `release` command. Since #677/U4 no batch lease exists to settle, so it
validates the frozen contract and reports an empty result.

For a long driver-side collection step, the boundary `renew` call stays for protocol
continuity; since #677/U4 there is no batch lease to renew (plan #677 KTD4), and it reports an
empty result.

## Settlement semantics

A Workflow script has no filesystem access, so it cannot write its own receipts — the driving
session is the producer of record. The only accepted delivery receipt is the exact evidence
file schema plus its descriptor (see `/work` Phase 1.5's settlement adapter). Never pass agent
prose or a self-report as evidence: it settles as `silent-no-op`, not success.
