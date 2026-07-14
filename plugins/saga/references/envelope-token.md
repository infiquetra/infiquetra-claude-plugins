# Envelope tokens — the revocable merge-authorization credential (#449)

<!-- gate-exempt: this reference documents the token mechanism; it fires no gate -->

The #380 `IntentEnvelope` records run-start posture but **authorizes nothing by itself** (its
own threat model). #449 adds the credential layer: a durable, expiring, immediately-revocable
**envelope token** that turns a committed `ceremony_gates.merge: "auto"` posture into an
actual, narrowly-scoped autonomous-merge authorization — the `AUTONOMOUS_UNDER_ENVELOPE`
write class in `reversibility_certificate.py`. This engages the intake §3 revisit condition
on the never-autonomous merge binding **without flipping the default**: every campaign that
does not explicitly opt in (envelope + posture + token) GATEs exactly as before — and the
previously-unconsumed engine loophole (the merge queue's tokenless R12 auto-merge) is closed
in the same change, so the engine's behavior finally matches the recorded binding.

Engine: `plugins/saga/scripts/envelope_token.py` (store + CLI) +
`reversibility_certificate.authorize_write_under_envelope` (the pure verdict) +
`outcome_merge.make_merge_authorizer` (the queue consumer). Store:
`<outcome-store>/envelope-tokens/` (git-ignored, machine-local, per outcome).

## The enforcement matrix — who may auto-merge

| Committed envelope | `ceremony_gates.merge` | Active token | Merge queue behavior |
| --- | --- | --- | --- |
| none | (effectively `gate`, per the #433 validator stance) | — | `waits-operator` |
| present | `gate` | any | `waits-operator` |
| present | `auto` | none | `waits-operator` (posture is intent, not a credential) |
| present | `auto` | one, valid | **auto-merge**, attributed to the envelope |
| present | `auto` | expired / revoked / era-mismatched | `waits-operator`, precise reason |
| present | `auto` | more than one valid | `waits-operator` (ambiguity never picks) |
| any | any | lane contains a malformed document | `waits-operator` (whole lane fails closed) |

A leaf's own `gated` / `risky` / `destructive` flags still `waits-operator` regardless of any
token. Read-only classification (dirty → conflict, blocked/unknown → defer) runs for every
campaign; only the GitHub **writes** (rebase, squash) are ceremony-gated. Bare `merge` /
`deploy` stay absent from the certificate registry — `authorize_write` GATEs them for every
caller, token or not, and gained no token parameter (#449 R2). Deploy has **no** token scope
in v1 (`scope` is closed to exactly `"merge"`; a `"deploy"` token fails at mint AND at check).

## Token schema (v1, closed, exact keys)

```json
{
  "schema_version": 1,
  "token_id": "emt-3ad47f903901a648",
  "envelope_id": "sha256:<64-hex canonical-envelope fingerprint>",
  "outcome_id": "ship-auth",
  "intent_revision": 0,
  "scope": "merge",
  "issued_at": "2026-07-14T00:00:00+00:00",
  "expires_at": "2026-07-15T00:00:00+00:00",
  "issued_by": "jeff"
}
```

Validation is exact-keys and type-strict; timestamps must be timezone-aware; `expires_at` is
strictly after `issued_at`; at-expiry no longer authorizes (mirrors `authorize_spend`'s
at-ceiling rule). Revocation is a write-once sibling marker
(`<token_id>.revoked.json`) — monotonic, never un-revokable, and an unreadable marker fails
closed **as revoked**.

## Era binding — why fingerprint AND revision

`envelope_id` is the sha256 of the canonical JSON of the schema-validated committed envelope,
and `intent_revision` is bound alongside it. Every check recomputes both from the caller's
current committed spec:

- a #433 `repost` that changes ANY posture content changes the fingerprint → the token stops
  authorizing (tightenings included — mint a fresh token for the new era);
- an A→B→A posture round trip restores the fingerprint but not the revision → still a new
  era, still GATE (the revision is bound because `save_spec`'s documented check-then-write
  residual means a revision number alone can be minted twice — content + revision together
  are strictly narrower than either alone);
- the production merge wiring (`production_merge_processor(repo_root=...)`) reads the
  **on-disk** committed intent per authorization, so a mid-tick repost's tightened posture is
  honored within the same tick. A direct caller that supplies no `intent_reader` falls back
  to the tick's in-memory posture — that residual (one tick, revocation still immediate) is
  documented in `outcome_merge`, not claimed away.

## Validity — re-derived at authorization time, never cached (R3/R4)

`check_token` / `resolve_merge_token` re-read the token file and the revocation marker from
disk on **every** call, and the merge queue invokes its authorizer immediately before every
GitHub write. `envelope_token.py revoke <token-id> --reason ...` therefore stops the very
next rebase/squash — including a later leaf inside the same reconcile tick — with no
cached-authorized state. The precise freshness bound: a revocation landing after a write's
fresh check but *during* that already-in-flight GitHub call cannot recall it (one network
write, an unavoidable check-then-act); every write after it GATEs. `resolve_merge_token` requires EXACTLY one active
matching token: zero, ambiguous (more than one), or a lane containing any document that
cannot be strictly understood all GATE.

## Attribution — the board-sync ledger's `authorizing_envelope_id` (R5)

Every envelope-authorized merge writes two write-once records into the outcome's board-sync
ledger via `board_progression.record_envelope_authorized_merge`, keyed
`merge-under-envelope:{outcome_id}:{subplot_id}:{pr}:{phase}:{token_id}`. The trailing
`token_id` is the era coordinate: an `authorized` record left by an attempt under a dead
envelope era (a capped or gated-later tick) can never satisfy the write-once dedup for a
merge performed under a later era, so both phases of one merge always name the same token:

- **`authorized`** — BEFORE the squash. A merge whose pre-authorization record cannot be
  written durably is **not performed** (audit-first fail-closed).
- **`merged`** — after GitHub confirms the squash.

Both carry `authorizing_envelope_id` + `token_id`, so a revoked or expired envelope can be
proven to have stopped authorizing merges and every historical merge traces to the intent
that permitted it. Non-merge ledger records are untouched — the field is
merge-record-specific. These records deliberately do **not** flow through the `/outcome`
consolidated report's ambiguity tier (its halt-receipt kind filter, #597); they are read
directly from the ledger lane and surfaced per-tick on the merge outcomes.

## Operator CLI

```bash
SCRIPTS=plugins/saga/scripts
# mint against the spec's committed envelope (refuses envelope-less / non-auto postures)
python3 $SCRIPTS/envelope_token.py mint --outcome-id <id> --repo-root . \
  --outcome-spec docs/outcomes/<id>/outcome-spec.json --ttl-hours 24 --issued-by "<who>"
# the immediate stop verb (R4)
python3 $SCRIPTS/envelope_token.py revoke --outcome-id <id> --repo-root . <token-id> --reason "<why>"
# derive validity against the current spec era, fresh
python3 $SCRIPTS/envelope_token.py check --outcome-id <id> --repo-root . \
  --outcome-spec docs/outcomes/<id>/outcome-spec.json
python3 $SCRIPTS/envelope_token.py list --outcome-id <id> --repo-root .
```

The mint verb here is the v1 issuance surface — deliberately a manual operator command, not a
run-start dialog. The interview/dialog issuance flow ("Gate or auto merge?" asked once at
start, minting the token alongside the envelope) is the issuance companion issue under the
same objective, out of #449's scope.

## Honest bounds — what a token does and does not prove

- **Minting is self-attested.** `issued_by` is a label. The trust boundary is the local
  filesystem — the same boundary as gate records, approvals, and every other store artifact
  (`gate-record.md` "Honest bounds", the `outcome_gate_transport` stance). Over the
  self-attested posture record, the token adds: an expiry, an immediate revocation verb,
  binding to one exact envelope content + revision + outcome, and per-merge durable
  attribution. It cannot prove the biological identity of the minter, and it is not a
  defense against a hostile writer with store access.
- **Gate records (#371) are not consulted in v1.** The token is CLI-minted. A future attended
  flow minting from a live gate-record answer must classify with
  `gate_record.is_operator_answerer` — `carried-forward:` / `absence:` provenance never mints
  (the #371 contract, restated in `gate-record.md` consumer item 4).
- **A crash between squash and the `merged` attribution record loses only that record.** The
  `authorized` record and GitHub's own merged-by audit survive; the gap is never backfilled,
  because post-hoc attribution would assert a pre-merge authorization nobody re-verified.
- **The in-memory-posture residual** (direct callers without an `intent_reader`) is bounded
  by one tick and by revocation's per-write freshness — documented above and in the module.
