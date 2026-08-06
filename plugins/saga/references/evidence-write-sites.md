# Evidence Write Sites

This is the containment inventory for accepted and forensic external-runtime output. Sites already
retired by #677 self-authenticate with `saga.close-receipt.v1` close receipts; the sites still
brokered keep `LeaseBroker` as their acceptance authority until their own retirement unit. A file
existing is never proof that its generation was accepted.

| Producer / transition | Acquire and renew | Protected writer | Canonical close | Refused output | Reader / owner |
|---|---|---|---|---|---|
| Saga registered dispatch | none since #677/U3 — caller-asserted bounded session/execution/attempt identity; a retry chains its predecessor's close receipt by digest | `_dispatch_once` appends registered facts inline | minted `saga.close-receipt.v1` on `provenance["dispatch_close"]` | stale or tampered predecessor receipt refuses before the runner | Saga run-ledger readers / `outcome` |
| Saga advisory panel | none since #677/U3 — `session_id` keys the delegation-integrity tripwire | direct reconcile-then-apply fact appends once the foreman result validates | none; the accepted fencing loss applies | no panel fact before foreman validation | reconciliation readers / `outcome` |
| Team Execution manifest claim | predecessor close receipt from the dispatch's `provenance["dispatch_close"]`, re-validated by digest re-derivation | byte CAS writes manifest and strict audit mirror | claim close receipt returned by `record_dispatch_manifest` | stale/tampered predecessor or store-byte drift fails before bytes change | manifest readers / `team-execution` |
| Team Execution adjudication | predecessor close receipt from the claim, re-validated by digest re-derivation | byte CAS rereads current manifest, writes adjudication and strict mirror | adjudication close receipt returned by `adjudicate_manifest` | stale predecessor or concurrent bytes fail closed | claim gate / `team-execution` |
| Agy direct auto apply | trusted in-process admission; acquire before subprocess; periodic renew | broker commit applies verified patch and armed mirrors | embedded Agy close receipt plus audit seal mirror | superseded metadata only; expired or closed output quarantine | Agy supervisor / `agy-supervisor` |
| Agy run bundle | none beyond the owning canonical path | unique-run terminal forensic files | none; noncanonical | preserved for diagnosis | Agy audit readers / `agy-supervisor` |
| Ordinary `manifest_store` CLI/API | none | atomic evidence-only manifest write | none; noncanonical | not applicable | advisory manifest readers only |
| Quarantine and orphan events | never acquires acceptance authority | reserved, bounded, write-once forensic publication | a close seal only mirrors an existing broker receipt | content-addressed payload or metadata-only event | named owner (the `reap_orphans.py scan` reader was removed in #666) |

`attempt_id` is evidence metadata. The Saga and Team Execution resource identity is stable by
`execution_id` — the attempt label is documentation, so every close receipt for one execution shares
its resource ref, and chain validation is by digest, not by broker fence head. Recovery of prepared,
committing, or ambiguous settlement authority on the still-brokered sites remains
root-coordinator-only and does not mint a successor.
