# Cross-runtime Outcome contract (#604) — discovery, canonical status, protected handoff

The runtime-neutral contract that lets another conforming runtime (the Codex Saga consumer,
infiquetra-codex-plugins#34) discover and attach to an existing Outcome by **canonical repository
identity plus Outcome ID**. This document and the golden fixtures at
`tests/fixtures/outcome-cross-runtime/v1/` are the producer vocabulary the Codex port consumes
verbatim (KTD8) — a consumer must not re-describe or loosen them.

## Authority model (the asymmetry)

Two canonical sources, everywhere: the **committed** Outcome spec blob (never the working-tree
file, never any cache) and **GitHub** completion evidence (merged PRs, closed issues).

| context | may read | may mutate |
|---|---|---|
| same clone (same git common dir) | committed spec + GitHub + shared coordination state | one subplot, only under a validated protected handoff + #351 settlement identity (#677/U1 retired the #356 broker successor) |
| different clone / host | committed spec + GitHub | **nothing** — reconstruction is read-only, `mutation_allowed: false`, always |

Runtime-local directories (`~/.claude`, `~/.codex`, caches, transcripts, launch receipts) are
never canonical Outcome status. Copied handoff JSON, copied caches, and legacy
`outcome-bundle/1` files carry **no** authority (KTD2/KTD6).

## Repository identity

`github.com/<owner>/<repo>`, derived from `remote.origin.url` only. Accepted spellings:
`https://github.com/o/r[.git]`, `git@github.com:o/r[.git]`, `ssh://git@github.com/o/r[.git]`.
Only a terminal `.git` is stripped. A credentialed URL, a foreign host, a local-path remote, a
missing origin, or anything else HALTs before any store access (KTD5). Filesystem proximity,
matching IDs, and newest timestamps are never identity proof.

## The four public schemas

All four are **closed**: an unknown field, a duplicate JSON key, a `bool` where an `int`
belongs, an oversized document (256 KiB cap), or an unknown schema string is a HALT, never a
shrug. Serialization is deterministic (`sort_keys`, compact separators) so equal inputs are
byte-equal everywhere.

### `outcome.discovery.v1` — the compatibility envelope

Emitted by `outcome discover <id>` from the committed blob. Fields: `schema`, `protocol`
(`version`/`min_supported`/`max_supported`/`required_capabilities[]`), `repository.identity`,
`outcome` (`id`/`spec_path`/`schema_version`/`spec_revision`), `committed`
(`commit_oid`/`blob_oid`/`sha256`), `authority` (the frozen map: structure=committed-spec,
completion=github, same_clone_coordination=git-common-dir+fleet-broker+dispatch-settlement,
cross_clone_mutation=forbidden), `producer` (`runtime`/`saga_version`). `producer` is
compatibility metadata, not authority — a receiver derives repository and committed facts
independently and compares; it never trusts the envelope's self-description.

### `outcome.canonical-status.v1` — the portable read-only projection

Emitted by `outcome attach <id>`. Fields: `schema`, `repository_identity`, `outcome_id`,
`committed`, `completed[]`, `candidate_frontier[]`, `unknown[]`, `node_completion[]`
(`subplot_id`/`contract`/`canonical_state` ∈ complete|open|unknown/`evidence_digest`),
`mutation_allowed: false`. Conservative evidence rules: an unreadable GitHub state, an
untracked non-code leaf (cache-resident marker), or a child-outcome node is `unknown` and is
excluded from the candidate frontier — unknown can only reduce apparent completion and
candidacy, never fabricate either. Treating the candidate frontier as dispatchable is a HALT
violation on the consumer side: the projection cannot prove another clone has no live dispatch.

### `outcome.handoff-reference.v1` — the printable pointer

Emitted by `outcome handoff <id> <subplot> --operation advance-one|attend`. Fields: `schema`,
`handoff_id` (32-hex), `digest` (the sealed offer record's sha256), `protocol`, `operation`,
`subplot_id`. It is a POINTER, never a bearer token: acceptance reopens the authoritative
protected local record and revalidates every binding; copied JSON authorizes nothing.

### `outcome.compatibility-halt.v1` — the closed failure receipt

Every rejection path returns `schema`, `code`, `unsupported`, `supported`, `next_action`.
Receipts never embed a local path, credential, raw file body, prompt, or transcript. Version
skew, capability gaps, and schema violations are checked **before** even benign cache mutation
(KTD7), so a compatibility error is provably side-effect free.

## Protocol negotiation

The envelope advertises one protocol integer plus a supported min/max range and named required
capabilities (`committed-spec-structure`, `github-completion`, `git-common-dir-coordination`,
`fleet-broker-fencing`, `dispatch-settlement-identity`). Acceptance computes the intersection
before any local coordination; an empty intersection or a missing capability returns the halt
receipt. There is no best-effort field dropping and no post-mutation downgrade.

## The protected handoff lifecycle (same clone only)

Records live under `<git-common-dir>/saga-outcomes/<outcome-id>/handoffs/`, write-once and
sealed (sha256 over the canonical record bytes). Three records per handoff:

1. **Offer** (`outcome.handoff-offer.v1`) — written directly to the store's write-once path.
   Binds: repository identity, outcome id, committed commit/blob/digest, spec revision,
   protocol version, source runtime, issuer owner id, exact operation (`advance-one` or
   `attend`), one subplot, #351 idempotency identity (a non-empty dispatch id is required for
   `advance-one`, so the settled-attempt check is always live; `attend` derives a resume pointer
   and may omit it), issued/expires epochs (TTL ≤ 300 s), nonce. Issuer identity is
   caller-asserted and REQUIRED — an anonymous offer HALTs (#677/U1 retired the broker lease the
   identity was read from; that is an accepted loss of the lease-broker retirement).
2. **Accept-intent** (`outcome.handoff-accept-intent.v1`) — write-once; binds exactly one
   receiver and the idempotency key. A second receiver HALTs; the same receiver resumes any
   crash gap idempotently.
3. **Accept-commit** (`outcome.handoff-accept-commit.v1`) — records the bound receiver and the
   commit epoch. The write-once intent/commit pair IS the acceptance transition (#677/U1 retired
   the broker successor grant and its close-receipt CAS).

Acceptance validates, in order: seal, freshness (expiry; > 30 s future issuance is clock-skew),
repository identity, committed digest + revision, working-tree byte-match (KTD3), operation,
subplot, #351 settled state — every failure a distinct halt code (`handoff-expired`,
`handoff-clock-skew`, `handoff-wrong-repository`, `handoff-wrong-revision`,
`handoff-wrong-operation`, `handoff-wrong-subplot`, `handoff-receiver-conflict`,
`handoff-already-settled`, `handoff-seal-invalid`, `working-tree-divergent`). A receiver that
dies after binding leaves its intent/commit records behind; a different receiver still HALTs on
the bound intent, and the same receiver resumes idempotently.

`attach --advance` re-checks the committed revision and the ready frontier AFTER acceptance and
enters the existing `advance` behind a one-subplot gate — there is no `--loop`, no frontier-wide
handoff, and a moved frontier HALTs (`handoff-frontier-changed`) rather than broadening.
`attach --attend` derives the native resume command only after every binding validates.

## Legacy `outcome-bundle/1` — retired

`export` is a deprecated alias of `discover` (stderr warning, identical envelope bytes; no
completion events, dispatch records, or cache paths). `import` refuses every bundle with the
exact migration commands and writes nothing — no spec save, no event replay, no ledger append.
There is no escape hatch that copies a cache between hosts.

## Recovery guidance

* A halt receipt's `next_action` is always non-mutating and safe to follow verbatim.
* `handoff-receiver-conflict`: the handoff is bound to another receiver (or the offer id
  collided) — request a fresh handoff; never retry with the stale reference.
* An expired offer leaves a sealed offer record behind; the issuing side mints a fresh handoff
  with a new nonce rather than reusing the expired one.
* Cross-clone consumers that need mutation must move to the clone holding the coordination
  state (or wait for a future networked active-dispatch authority — out of scope here).
