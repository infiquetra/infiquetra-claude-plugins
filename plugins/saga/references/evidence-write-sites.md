# Evidence Write Sites

This is the containment inventory for accepted and forensic external-runtime output. `LeaseBroker`
is the only acceptance authority. A file existing is never proof that its generation was accepted.

| Producer / transition | Acquire and renew | Protected writer | Canonical close | Refused output | Reader / owner |
|---|---|---|---|---|---|
| Saga registered dispatch | `acquire_agent` for a first generation; `acquire_successor` for a retry; `renew` around runner | `prepare_agent_settlement` then `commit_agent_settlement` appends registered facts | embedded `settlement_close.v1` on the resource head | superseded metadata event; expired or late output quarantine | Saga run-ledger readers / `outcome` |
| Saga advisory panel | one aggregate lease, renewed around members | one broker commit appends reconcile then apply | embedded aggregate close receipt | no panel fact before commit; retained settlement on ambiguous callback | reconciliation readers / `outcome` |
| Team Execution manifest claim | successor CAS from exact registered-dispatch token and receipt | broker commit writes manifest and strict audit mirror | claim close receipt returned by `record_dispatch_manifest` | stale predecessor fails before bytes change | manifest readers / `team-execution` |
| Team Execution adjudication | successor CAS from exact claim token and receipt | broker commit rereads current manifest, writes adjudication and strict mirror | adjudication close receipt returned by `adjudicate_manifest` | stale predecessor or concurrent bytes fail closed | claim gate / `team-execution` |
| Agy direct auto apply | trusted in-process admission; acquire before subprocess; periodic renew | broker commit applies verified patch and armed mirrors | embedded Agy close receipt plus audit seal mirror | superseded metadata only; expired or closed output quarantine | Agy supervisor / `agy-supervisor` |
| Agy run bundle | none beyond the owning canonical path | unique-run terminal forensic files | none; noncanonical | preserved for diagnosis | Agy audit readers / `agy-supervisor` |
| Ordinary `manifest_store` CLI/API | none | atomic evidence-only manifest write | none; noncanonical | not applicable | advisory manifest readers only |
| Quarantine and orphan events | never acquires acceptance authority | reserved, bounded, write-once forensic publication | a close seal only mirrors an existing broker receipt | content-addressed payload or metadata-only event | `reap_orphans.py scan` / named owner |

`attempt_id` is evidence metadata. The Saga and Team Execution resource identity is stable by
`execution_id`; ordinary acquire cannot cross a canonical close. Recovery of prepared, committing,
or ambiguous settlement authority is root-coordinator-only and does not mint a successor.
