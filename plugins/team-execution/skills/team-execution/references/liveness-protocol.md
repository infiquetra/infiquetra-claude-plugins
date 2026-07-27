# Resident liveness protocol

Team execution uses one canonical implementation: fleet-core scores normalized evidence, Saga owns
the `run_fact.v1 kind=liveness` ledger adapter, and this plugin invokes Saga through
`scripts/liveness_protocol.py`. Lease state authorizes mutation but is never heartbeat or death
evidence. #358, not this protocol, owns stop, release, teardown, and deletion.

## Closed subject

Capture `artifact_pointer.py liveness-baseline` immediately before each background Agent spawn. Once
the host returns the trusted handle, call `liveness_protocol.py open` with the closed identity request
and baseline. The adapter resolves the current fleet-core agent lease and derives session, lease,
resource digest, token digest, broker epoch/fence, boot, and TTL; callers never supply those values.
It then appends one idempotent `subject-open` binding:

- subplot and dispatch IDs plus the #351 manifest and spawn digests;
- resident and host agent IDs;
- #356 lease ID, resource/token digests, boot ID, and TTL;
- baseline and canonical path-set digests.

Saga derives `subject_id` as `subject:sha256:<digest>` over exactly session, subplot, dispatch, unit,
attempt, resident, host agent, lease, resource digest, broker epoch/fence, and boot identity. The
manifest/spawn digests, token digest, TTL, baseline, and path-set digest remain closed operational
bindings repeated by every event. Missing, extra, cross-attempt, cross-boot, or drifted fields fail
closed.

Use `liveness_protocol.py record-event` for coordinator-owned `heartbeat`, scoped activity,
exclusive artifact progress, idle ack, and re-ping ack facts. Use `record-idle-notice` for trusted
idle signals: it preserves a host notice ID when present, or allocates the next subject-local
`notice-N` under the run-ledger lock and deduplicates identical normalized host metadata. These
commands refuse
`subject-open`, `reping-intent`, `reping-sent`, and `reping-send-failed`: those remain owned by the
dedicated open, atomic claim, and SendMessage-hook paths. Use
`record-artifact-observation` for the approved-path comparison and append. It invokes
`artifact_pointer.py` itself; exclusive progress is accepted only when the provenance record's
subject, lease, resource/token digests, broker fence, baseline, paths, interval, custody, and named
generations match the canonical liveness identity.

## Poll boundaries

Poll the subject through `liveness_protocol.py poll`:

1. after every #356 lease renewal;
2. whenever Agent or SendMessage returns to the host;
3. after a trusted idle or terminal host signal;
4. before unblocking a dependent segment; and
5. before the B2 reviewer fan-out.

Polling is read-only. A malformed chain or event becomes `evidence-error`; it never implies health or
death. A scoped digest change without exact exclusive provenance becomes
`scoped-activity-unattributed` and closes no generation.

## Re-ping sequence

When poll returns `reping`, call `claim-reping` with that subject and monotonic observation time. Only
the lock-current winner receives a durable `reping-intent`. Before SendMessage, hash the exact
recipient/message tuple, then call `stage-send` with that digest and claim. Never place message text in
the ledger or staged record.

**The send-completion binding has been removed.** Saga previously carried a
`liveness_reping_hook.py` on `SendMessage` Pre/Post/Failure to join the staged claim to the host
tool-use ID. That hook read the recipient from `tool_input` keys `recipient`/`target_agent_id`/
`target`; the host tool's schema is `{to, message, summary}`, so the parse always failed and the
`PreToolUse` leg exited 2 — hard-blocking *every* `SendMessage` call, not just staged ones.

Consequence for this protocol: `stage-send` still records the claim, but nothing binds a send
outcome afterward. A staged claim simply expires unresolved. No `reping-sent`, `reping-send-failed`,
`reping-delivery-blocked`, or `reping-ack` fact is produced. Treat re-ping as best-effort
notification with no delivery evidence.

Any future re-binding must read `to`, and must fail **open** — a liveness observer that can block
the messaging primitive it observes is not an observer.

Three accepted, unacknowledged response windows must expire before Team receives
`terminal_authority=team-reping-confirmed`. Failed, blocked, unresolved, or merely claimed sends do
not contribute.

## Artifact progress

`liveness-observe` compares the baseline and current scoped digest with a temporary Git index. It
emits no durable pointer when unchanged. An exclusive-provenance upgrade must bind the subject,
lease/fence, exact paths and digests, interval, custody ref, and named generations. A reachability
generation closes only when the interval starts at or after its opened anchor and ends strictly after
the later of that anchor and its latest accepted re-ping. Equality, straddling, and unlisted sibling
generations do not close.
