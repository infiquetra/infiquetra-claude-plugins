---
title: Lease-safe runtime continuity - Claude cross-runtime Outcome contract
type: feat
status: active
date: 2026-07-15
origin: docs/outcomes/lease-safe-runtime-continuity/issue-sources/claude-cross-runtime-coordination.md
issue: infiquetra/infiquetra-claude-plugins#604
parent: infiquetra/infiquetra-claude-plugins#579
---

# Lease-safe runtime continuity - Claude cross-runtime Outcome contract

## Summary

Implement the Claude-side release unit of #579 after #351, #355, and their #356 dependency merge.
Add a runtime-neutral `outcome_compat.py` contract that discovers a committed Outcome by canonical
GitHub repository identity plus Outcome ID, emits a closed compatibility envelope, reconstructs a
portable canonical projection from the committed specification plus GitHub, and validates a
same-clone handoff against protected git-common-dir evidence. Wire `discover`, `attach`, and
`handoff` through the existing `/outcome` CLI without creating another Outcome store, lease,
settlement ledger, or completion authority.

The authority boundary is deliberately asymmetric:

- **Same clone:** Claude and Codex resolve the same git common dir, consume the #356 fleet broker and
  #351 dispatch settlement identity, and may coordinate a mutating `advance` after compatibility and
  handoff validation.
- **Different clone or host:** a runtime reconstructs the same canonical DAG/completion projection
  from a committed spec plus GitHub, but transient dispatch state is unknown and mutation is denied.
  An unsigned or copied handoff never turns a different cache into dispatch authority.

The current `outcome-bundle/1` import copies cache completion and dispatch records into another repo
and writes the bundled spec. That behavior conflicts with #579's authority model. This unit replaces
portable mutation with discovery/validation and makes legacy bundle import fail closed with an
actionable migration receipt; it does not silently preserve a second authority path.

Destination is one Claude-plugin PR and merge. The downstream Codex consumer remains a separately
linked issue and release. Execution uses an operator-approved Verified Workflow. Root owns all
implementation, Git, tests, integration, PR, merge, issue closure, and board reconciliation;
agent-lens roles authorize no repository or external mutation.

---

## Problem Frame and Current State

The committed Outcome spec already defines structure, intent, revision, and decisions. GitHub is the
canonical completion source. The git-common-dir `saga-outcomes/<outcome-id>` tree stores transient
events, dispatch records, and locks, but its current primitives predate the outcome's lease-safe
substrate and have material gaps:

| current behavior | risk | required correction |
|---|---|---|
| `resume()` loads the working-tree spec and the local cache | an uncommitted/stale file or deleted cache changes the apparent story | discovery reads the committed blob; canonical reconstruction reads GitHub directly |
| `outcome_store.acquire_lease()` has best-effort stale reclaim and explicitly excludes cross-host coordination | two runtimes can overlap at stale reclaim | mutating attachment consumes #356's fenced fleet broker; the old lock remains only defense in depth |
| dispatch dedup is a cache-local `commit` record | cache loss or a second clone can make an in-flight leaf look ready | same-clone mutation consumes #351 settlement identity; cross-clone mutation is denied |
| `export_bundle()` serializes cache completion and dispatch records | portable cache data is easy to mistake for authority | discovery envelopes carry committed/GitHub references and digests, never mutable cache facts |
| `import_bundle()` writes a spec and replays cache facts into a different repo | wrong-repository overwrite and competing truth | legacy import HALTs; `attach` validates local canonical sources without copying state |
| `attend()` returns only `/resume <saga-id>` | no repository, revision, compatibility, issuer, freshness, or use binding | a protected local handoff record binds all fields; the printable command is derived after validation |
| no canonical repository identity exists | path aliases, forks, and wrong remotes can attach to the wrong Outcome | normalize and validate the committed repository identity before any store or external mutation |

Canonical reconstruction and transient coordination must not be conflated. A second clone can prove
which leaves are complete and which dependency frontier follows from GitHub. It cannot prove that a
leaf is not currently dispatched from another clone because dispatch state is intentionally not
canonical on GitHub. Its report therefore exposes `transient_state: unknown` and
`mutation_allowed: false`; treating that candidate frontier as dispatchable is a HALT violation.

---

## Traceability and Dependencies

- **Parent objective:** `infiquetra/infiquetra-claude-plugins#579`.
- **Executable child:** `infiquetra/infiquetra-claude-plugins#604`; prepared-source receipt:
  `docs/sdlc-issue-drafts/2026-07-15-claude-side-cross-runtime-outcome-authority-disc-2.md`.
- **Outcome node:** `claude-cross-runtime` in
  `docs/outcomes/lease-safe-runtime-continuity/outcome-spec.json`.
- **Hard upstream:** #351 supplies canonical dispatch manifest/spawn/settlement identities; #355
  supplies protected evidence rejection and close fencing; #356 supplies broker lease authority and
  monotonic fencing. #355 is already downstream of #356. The branch must refresh the exact merged
  schemas before implementation.
- **Parallel siblings:** #357, #358, and #353 are not semantic prerequisites. Because they can touch
  Saga release surfaces, implementation rebases on current `origin/main` immediately before release
  edits and takes the next available Saga minor version rather than reserving a stale number.
- **Downstream:** the explicit Codex parity issue consumes only the published runtime-neutral schema
  and fixtures. Cross-runtime acceptance starts only after both releases merge.
- **No hidden cross-repo work:** this PR changes no `infiquetra-codex-plugins` file and cannot close
  the Codex parity or acceptance nodes.

| parent/child acceptance | plan contract | primary proof |
|---|---|---|
| discover by repository + Outcome ID | R1-R4; U1-U2 | local/linked-worktree/ref lookup matrix |
| same-clone shared coordination | R5-R7; U3-U4 | two runtime labels, one common dir, one broker/settlement identity |
| different-clone deterministic reconstruction | R4, R8; U2 | two real clones, cache absent, identical canonical projection |
| runtime-local paths not canonical | R2-R3, R6, R8; U1-U4 | serialization denylist and copied-receipt rejection |
| version skew fails before mutation | R3, R9; U1, U4 | pre/post filesystem, Git, board, and GitHub snapshots |
| no duplicate dispatch/completion | R5, R7, R10; U3-U4 | concurrency barrier and exact fact-count assertions |
| independent Claude/Codex release units | R11; U5 | schema fixture + linked issue/release checklist |

---

## Requirements

R1. **One runtime-neutral compatibility module.** Add `outcome_compat.py` with closed parsers and
serializers for `outcome.discovery.v1`, `outcome.canonical-status.v1`,
`outcome.handoff-reference.v1`, and `outcome.compatibility-halt.v1`. The module imports no Claude or
Codex runtime-local history/config package and contains no home-directory defaults. Unknown schemas,
unknown fields in security-bearing subobjects, invalid types, duplicate keys, oversized input, and
unsupported protocol ranges fail closed.

R2. **Repository identity is Git-derived, path-independent, and exact.** Resolve the repository root
and common dir with fixed-argv Git. Resolve `remote.origin.url`, accepting the supported GitHub HTTPS
and SSH forms, stripping only a terminal `.git`, and emitting a normalized
`github.com/<owner>/<repo>` identity. Local paths, symlink spellings, worktree paths, remote URLs with
credentials, foreign hosts, ambiguous remotes, missing origin, and repository-identity mismatch
HALT before store access. The envelope never serializes the repo root or common-dir path.

R3. **Compatibility validation precedes mutation.** Read the committed spec through Git object
commands, not the mutable working-tree file. Bind its exact repo-relative path, Outcome schema,
`spec_revision`, Git commit OID, blob OID, and SHA-256. Require the working-tree copy to match the
committed blob before same-clone mutation. Protocol/schema support and repository/spec bindings are
validated before `Store.ensure`, tolerant/quarantining readers, broker acquisition, run-fact append,
dispatch, board write, GitHub write, or spec save. Every HALT contains the unsupported value, local
supported range, and non-mutating next action without local paths or secrets.

R4. **Discovery is deterministic and ambiguity is fatal.** Locate
`docs/outcomes/<outcome-id>/outcome-spec.json` on the current committed ref or the canonical
`outcome/<outcome-id>` local/remote ref. Validate the embedded Outcome ID. If multiple candidate refs
carry different blobs/revisions, return an ambiguity HALT rather than choosing newest. Same-clone
linked worktrees resolve one identity and one store. A fork or wrong repository cannot attach merely
because it contains a copied path and matching Outcome ID.

R5. **Same-clone mutating authority consumes the merged safety substrate.** Every attached mutating
`advance-one` acquires or receives the successor token for #356's exact merged Outcome-dispatch
resource keyed by canonical repository, Outcome ID, subplot, and dispatch attempt. It presents the
current monotonic fence at the write/dispatch boundary and retains the existing git-common-dir
coordinator and per-subplot locks only as defense in depth. No new coordinator pool or capacity class
is added. It consumes #351's final dispatch identity and settled-record query instead of adding a
handoff-specific dispatch ledger. Expired, superseded, wrong-owner, closing, or unverifiable broker
authority HALTs.

R6. **Handoff evidence is a protected local reference, never a bearer token.** A handoff record is
stored only in the current git common dir through the post-#355 protected-evidence contract and
binds: repository identity; Outcome ID; committed commit/blob/digest; spec revision; compatibility
version; source runtime; broker-derived issuer/owner identity; broker epoch/fencing sequence; exact
operation (`advance-one` or `attend`); one selected subplot; its dispatch/idempotency identity when
applicable; issued/expiry timestamps; nonce; and state. Issuer authority comes from the live broker
record, never a caller-provided runtime label. Handoffs expire at most 300 seconds after issuance and
a timestamp more than 30 seconds in the future HALTs. The printable `outcome.handoff-reference.v1`
contains an opaque ID and digest but cannot authorize by itself. Acceptance reopens the authoritative
local record, verifies its protected seal and current broker/settlement facts, then uses #355's
resource guard to serialize a protected accept-intent, #356 successor grant/supersession, and
protected accept-commit. The accept-intent binds one receiver and idempotency key: a crash before the
grant resumes only for that receiver; a crash after the grant observes the same current successor and
appends the missing commit. Another receiver cannot steal the intent. If the receiver dies, existing
TTL/dead-owner recovery must close its token before a new handoff; elapsed time alone grants nothing.
Missing, copied, modified, expired, replayed,
wrong-repo, wrong-revision, wrong-operation, wrong-subplot, wrong-issuer, or superseded references
HALT. There is no Outcome-wide, multi-frontier, or `--loop` handoff.

R7. **Single dispatch is proven at the real boundary.** Two same-clone runtime labels attaching and
advancing the same ready leaf race at a deterministic barrier. Exactly one obtains current #356
authority and produces the #351 manifest/spawn/settlement identity and one dispatcher
acknowledgement. The loser returns busy, already-settled, or replay HALT without a second dispatch
intent, backend call, completion event, or board/GitHub write. Crash windows re-drive the merged
#351 settlement state; handoff state does not replace its idempotency.

R8. **Cross-clone reconstruction is canonical and read-only.** A fresh clone with no copied common
dir/cache/handoff reads the committed spec and each GitHub completion contract into
`outcome.canonical-status.v1`. The projection contains completed nodes, dependency-derived candidate
frontier, unknown/unreadable evidence, source digests, and `mutation_allowed: false`; it does not
claim local `ready`, `dispatched`, `running`, lease, or handoff state. Two clones given the same Git
commit and GitHub fixture serialize byte-identically. An unknown GitHub state stays unknown and can
only reduce completion, never fabricate it.

R9. **Version negotiation is narrow and fail closed.** The discovery envelope advertises one
protocol integer plus supported minimum/maximum, exact Outcome schema support, and named required
capabilities. Acceptance computes an intersection before local coordination. A missing required
capability, future schema, downgrade outside the range, or malformed range returns
`outcome.compatibility-halt.v1`; there is no best-effort field dropping or post-mutation downgrade.
The first Codex consumer must use the exact fixtures committed here rather than re-describe them.

R10. **Legacy bundle authority is retired explicitly.** `outcome-bundle/1` export/import is not a
handoff path. The `export` CLI becomes a deprecated alias for `discover`: it writes its warning to
stderr and emits the same `outcome.discovery.v1` JSON bytes, with no completion events, dispatch
ledger, protected evidence, or cache paths. `import` accepts no bundle as authority and must not save
a spec, replay completion events, or replay dispatch records; it exits nonzero with the exact
`discover`/`attach` migration command. The Python `export_bundle`/`import_bundle` compatibility
entrypoints follow those semantics instead of retaining a hidden write path. Tests pin the old
cross-repository write/replay behavior as rejected. There is no escape hatch that copies a cache
between hosts.

R11. **CLI, docs, and release surfaces tell one story.** Add `discover`, `attach`, and `handoff`
operations to the existing Outcome skill/CLI and a runtime-neutral reference document. `discover`
and cross-clone `attach` are read-only; same-clone `attach --advance` requires a valid protected
`advance-one` handoff, dispatches only its selected subplot, and rejects `--loop` or an unscoped
frontier. Update Saga manifest, marketplace, changelog, command/skill coverage, release drift guards,
#579 child links, golden fixtures under `tests/fixtures/outcome-cross-runtime/v1/`, and engineering
journal in the same PR. From the actual merged base, bump Saga exactly once to the next available
minor version.

R12. **Inputs and output are bounded.** Cap an envelope/reference at 256 KiB, Outcome spec blob at
8 MiB, nodes at 10,000, Git stdout at 16 MiB, Git stderr at 64 KiB, and every Git/GitHub call at 20
seconds. Reject symlinks/nonregular envelope files and duplicate JSON keys. Output excludes remote
credentials, filesystem roots, common-dir paths, home paths, raw GitHub response bodies, prompts,
transcripts, tokens, and child output. Capacity or timeout is a HALT, never a partial success.

---

## High-Level Technical Design

```text
                  committed Git object + canonical GitHub completion
                                      |
                           outcome.discovery.v1
                                      |
                  +-------------------+-------------------+
                  |                                       |
       same repository + same common dir          different clone / host
                  |                                       |
       protected handoff reference verified       canonical-status.v1 only
       #356 fenced coordinator acquired            transient state unknown
       #351 settlement identity checked            mutation_allowed=false
                  |
        existing Outcome advance/attend
        exactly one dispatch acknowledgement
```

### Discovery envelope

```text
schema: outcome.discovery.v1
protocol: {version, min_supported, max_supported, required_capabilities[]}
repository: {identity: github.com/owner/repo}
outcome: {id, spec_path, schema_version, spec_revision}
committed: {commit_oid, blob_oid, sha256}
authority:
  structure: committed-spec
  completion: github
  same_clone_coordination: git-common-dir+fleet-broker+dispatch-settlement
  cross_clone_mutation: forbidden
producer: {runtime: claude, saga_version}
```

`producer` is compatibility metadata, not authority. The receiver derives repository and committed
spec facts independently and compares them; it never trusts the envelope's self-description.

### Canonical status projection

```text
schema: outcome.canonical-status.v1
repository_identity / outcome_id / committed digest
completed[]
candidate_frontier[]
unknown[]
node_completion[]: {subplot_id, contract, canonical_state, evidence_digest}
mutation_allowed: false
```

This projection is the portable equivalent status. Same-clone transient overlays remain available
through existing `status`, but are never serialized as canonical cross-clone truth.

### Protected handoff state machine

```text
offer --accept(current repo/spec/fence/scope, unused)--> append acceptance
  |                                                        |
  +--expired/superseded/modified/missing-------------------+--> HALT
accepted --second accept or different receiver/operation----------> replay HALT
```

The handoff references existing dispatch settlement by identity. It does not mint a second
reservation, completion, or retry state machine.

---

## Key Technical Decisions

- **KTD1 - portable status excludes transient dispatch authority.** Spec plus GitHub can reconstruct
  completion and dependency candidates across clones, but cannot prove another clone has no live
  dispatch. Cross-clone attachment is therefore read-only.
- **KTD2 - a handoff reference is not a bearer credential.** Local protected evidence and current
  broker/settlement facts authorize; copied JSON never does.
- **KTD3 - committed blob, not working-tree bytes, anchors discovery.** Same-clone mutation also
  requires the working tree to match, preventing an edited plan from silently changing authority.
- **KTD4 - consume #356/#351/#355, do not wrap them with peers.** Fleet broker owns exclusion/fence,
  settlement owns dispatch idempotency, and protected evidence owns tamper/replay rejection.
- **KTD5 - wrong or ambiguous repository identity HALTs.** Filesystem proximity, matching IDs, and
  newest timestamps are not identity proof.
- **KTD6 - legacy portable import is incompatible by design.** Cache replay across repositories is
  retired, with a migration receipt rather than a hidden compatibility switch.
- **KTD7 - version skew is checked before even benign cache mutation.** This keeps a compatibility
  error provably side-effect free, including quarantine and directory creation.
- **KTD8 - one producer schema, separate consumer release.** Claude commits fixtures and vocabulary;
  Codex ports them in its own issue/PR and may not change the contract silently.

These decisions are recorded under `{#claude-cross-runtime-outcome-contract-579}` in
`docs/engineering-journal/DECISIONS.md` before implementation starts.

---

## Implementation Units

### U1. Repository identity, committed-spec discovery, and closed schemas

**Goal:** Implement strict, bounded, runtime-neutral identity/discovery values and HALT receipts.

**Requirements:** R1-R4, R9, R12.

**Files:** `plugins/saga/scripts/outcome_compat.py` (new),
`tests/test_outcome_cross_runtime_contract.py` (new).

**Approach:** Add fixed-argv Git adapters, origin normalization, branch/ref ambiguity detection,
committed blob loading, duplicate-key JSON parsing, exact schema validators, deterministic
serialization, and redacted HALT values. Dependency-inject Git/GitHub/time/nonce in tests. Do not
resolve or create the Outcome store until validation succeeds.

**Test scenarios:** HTTPS/SSH origin equivalence; linked worktree identity; fork/wrong host/credential
URL; absent/ambiguous origin; clean versus dirty spec; local/remote ref agreement/disagreement;
embedded ID mismatch; future/old protocol; unknown capability/field; bool-as-int; duplicate JSON key;
symlink/nonregular/oversize/timeout; stable serialization and no-path denylist.

**Gate:** a malformed or skewed envelope leaves repo/common-dir/broker/audit/GitHub snapshots
unchanged and returns the closed compatibility HALT.

### U2. Canonical GitHub reconstruction and read-only cross-clone attach

**Goal:** Produce byte-equivalent canonical status from committed spec plus GitHub without cache
copying or transient-state claims.

**Requirements:** R3-R4, R8-R9, R12.

**Files:** `plugins/saga/scripts/outcome_compat.py`,
`plugins/saga/scripts/outcome_orchestrator.py`, `plugins/saga/scripts/outcome.py`,
`tests/test_outcome_cross_runtime_contract.py`, focused completion tests.

**Approach:** Reuse the parent-owned completion predicates through a non-materializing read path.
Return completed/candidate/unknown sets and evidence digests; never call `harvest()` or tolerant store
readers in cross-clone mode. Build two real temporary clones/ref layouts with no shared common dir and
inject one GitHub fixture. Compare serialized projections and assert both cache roots remain absent.

**Test scenarios:** Claude-created and Codex-labeled envelopes; all/open/mixed/unknown GitHub states;
code PR and non-code issue contracts; closure-gate evidence; cache absent/corrupt elsewhere; same
commit different filesystem path; fork with copied spec; attempted `--advance` from cross clone.

**Gate:** equivalent Git/GitHub inputs produce identical canonical status, and every cross-clone
mutation attempt HALTs before store/broker/board/GitHub mutation.

### U3. Protected same-clone handoff and broker admission

**Goal:** Bind a one-use handoff to local protected evidence and current #356 authority.

**Requirements:** R5-R6, R9, R12.

**Files:** `plugins/saga/scripts/outcome_compat.py`, `plugins/saga/scripts/outcome_store.py`,
post-#355 protected-evidence module, post-#356 broker module,
`tests/test_outcome_cross_runtime_contract.py`.

**Approach:** Add namespaced immutable offer, accept-intent, and accept-commit records under the
existing protected git-common-dir evidence root. Offer requires a current live #356
Outcome-dispatch resource and records its source token plus committed/spec/dispatch identities, exact
operation, and one subplot with a maximum 300-second TTL. Under #355's resource guard, accept verifies
the caller's derived identity, protected seal, bounded clock, source resource head, #351 settled
state, and absence of another receiver intent; appends/binds the accept-intent; grants the same
logical resource's successor token to the receiver; and appends the commit. Same-receiver retries
resume either crash gap idempotently. The public reference carries only opaque ID, digest, protocol,
operation, and subplot. No absolute path or cache content is exported.

**Test scenarios:** Claude-to-Codex and Codex-to-Claude runtime labels; wrong repo/outcome/revision;
expired/future timestamp; copied to another common dir; byte tamper; forged ID/digest/issuer; wrong
fence; intervening successor; owner closing; already settled; repeated acceptance; concurrent
acceptance; crash before intent, intent-to-grant, and grant-to-commit; same-receiver resume; dead
receiver TTL plus dead-owner recovery; protected evidence corruption.

**Gate:** only one acceptance succeeds, and no invalid reference changes handoff, lease, settlement,
dispatch, board, GitHub, or spec state.

### U4. Lease- and settlement-safe attached advance/attend

**Goal:** Put compatibility, handoff, broker, and settlement checks in front of the existing mutating
Outcome seams and prove exactly one effect.

**Requirements:** R3, R5-R7, R9-R10.

**Files:** `plugins/saga/scripts/outcome.py`, `plugins/saga/scripts/outcome_dispatcher.py`,
post-#351 settlement adapter, post-#356 broker adapter,
`tests/test_outcome_cross_runtime_contract.py`, focused Outcome/store/dispatcher tests.

**Approach:** Add `discover`, `handoff`, and `attach` CLI routing. `attach --advance` first validates
an `advance-one` handoff, then acquires the canonical broker resource, rechecks spec revision/fence
after acquisition, queries #351 settlement, and enters an allowlisted one-subplot form of existing
`advance`. It rejects `--loop`, a changed frontier, or any second ready leaf rather than broadening
the handoff. Thread the dispatch identity/fence to the post-#351 production adapter. Preserve local
coordinator/dispatch locks as secondary containment. `attend` requires an `attend` handoff for the
same subplot and derives the native resume command only after the bindings validate.

**Test scenarios:** two processes/threads released at one barrier; one dispatch call/fact cohort;
stale local lock versus current broker; lease expiry/reclaim and old fence; spec revision changes
before/after acquisition; backend 429/HALT/crash windows; settled retry; handoff replay; second clone;
completion/board writer spies; no child output or credential leakage.

**Gate:** across all interleavings there is at most one dispatch intent/acknowledgement and no stale
writer side effect. Unknown compatibility or authority always precedes mutation.

### U5. Legacy migration, operator contract, release, and downstream fixture

**Goal:** Remove the portable-cache authority path and publish one coherent Claude contract for the
Codex parity issue.

**Requirements:** R10-R12.

**Files:** `plugins/saga/scripts/outcome.py`, `plugins/saga/skills/outcome/SKILL.md`,
`plugins/saga/references/outcome-cross-runtime.md` (new), `tests/test_outcome_command.py`,
`tests/test_saga_plugin.py`, `plugins/saga/.claude-plugin/plugin.json`,
`.claude-plugin/marketplace.json`, `plugins/saga/CHANGELOG.md`, release guards,
`docs/engineering-journal/DECISIONS.md`, #579 child/acceptance links.

**Approach:** Make legacy `export` a warning-plus-byte-identical alias of `discover` and legacy import
non-mutating with a precise `discover`/`attach` migration receipt. Remove portable authority language
from docs. Document canonical versus transient projections, same-clone requirements, cross-clone
read-only behavior, compatibility/HALT fields, and recovery. Commit neutral golden fixtures at
`tests/fixtures/outcome-cross-runtime/v1/` for verbatim Codex consumption. Rebase, calculate the next
available Saga minor version, update every release surface atomically, and run drift guards.

**Test scenarios:** old bundle rejection with zero writes; installed skill/command examples; stale
docs denylist; golden fixture round trip; unknown field/version fixture; marketplace/version/changelog
parity; generated inventories; CLI exit codes and redaction.

**Gate:** the Claude PR is independently releasable, the Codex issue has an exact fixture/schema
input, and no documentation suggests copying a cache, receipt, or runtime-local status.

---

## Files Expected to Change

```text
plugins/saga/scripts/outcome_compat.py                         new
plugins/saga/scripts/outcome.py
plugins/saga/scripts/outcome_orchestrator.py
plugins/saga/scripts/outcome_store.py                         narrow protected handoff seam
plugins/saga/scripts/outcome_dispatcher.py                    exact merged identity/fence wiring
plugins/saga/skills/outcome/SKILL.md
plugins/saga/references/outcome-cross-runtime.md               new
tests/test_outcome_cross_runtime_contract.py                  new
tests/fixtures/outcome-cross-runtime/v1/                      new neutral contract fixtures
tests/test_outcome_command.py
tests/test_outcome_completion.py or test_outcome_orchestrator.py
tests/test_saga_plugin.py
plugins/saga/.claude-plugin/plugin.json
plugins/saga/CHANGELOG.md
.claude-plugin/marketplace.json
release inventory/version drift guards as required by the merged base
docs/engineering-journal/DECISIONS.md
```

The exact post-#351/#355/#356 module names replace the descriptive dependency rows above after the
mandatory refresh. No Codex repository file belongs in this PR.

---

## Test Strategy

1. **Pure schema/identity unit tests:** every field/type/version/repository/path/cap boundary with
   injected Git and duplicate-key JSON input.
2. **Real Git topology tests:** one origin, linked worktrees sharing a common dir, two independent
   clones, divergent refs, dirty spec, fork/wrong remote, and copied handoff.
3. **Canonical reconstruction tests:** parent-owned GitHub completion predicates with deterministic
   fixtures, no store creation, and byte-identical projections across clones.
4. **Concurrency tests:** deterministic barriers around broker admission, handoff acceptance,
   revision recheck, settlement lookup, and dispatch call; exact effect/fact counts after every
   interleaving.
5. **Failure-injection tests:** crash before/after protected acceptance, broker expiry/supersession,
   stale fence, dangling settlement intent, rate limit, corrupt evidence, unknown GitHub, and timeout.
6. **No-mutation and privacy oracles:** snapshot working tree, Git common dir, broker/audit roots, and
   external writer spies before every rejected/skew/cross-clone path; scan output for prohibited path,
   credential, prompt, transcript, and output material.
7. **Regression/release tests:** existing Outcome/store/dispatcher/completion suites, Saga plugin
   inventories, full repository checks, release parity, and diff guard.

The concurrency validator owns the happens-before matrix and exact one-effect proof. The event-flow
validator traces discovery -> compatibility -> protected offer/accept -> broker/fence -> settlement
-> dispatch and every HALT edge. Both use gpt-5.6-terra medium. Four judgment reviewers use
gpt-5.6-sol high because authority, replay, migration, and cross-runtime compatibility failures are
architectural/security risks rather than routine style checks.

---

## Verification

```bash
uv run pytest tests/test_outcome_cross_runtime_contract.py -v
uv run pytest tests/test_outcome_store.py tests/test_outcome_dispatcher.py -v
uv run pytest tests/test_outcome_command.py tests/test_outcome_completion.py -v
uv run pytest tests/test_outcome_orchestrator.py tests/test_saga_plugin.py -v
uv run pytest
uv run ruff format --check .
uv run ruff check .
uv run mypy plugins/ scripts/ tests/ --ignore-missing-imports
uv run bandit -r plugins/
uv run python scripts/check_release_surface_parity.py
uv run python scripts/sync_marketplace.py --check
uv run python tools/release_surface_diff_guard.py --base-ref origin/main
git diff --check
```

Manual acceptance uses two runtime labels in one real clone and a second independent clone. It
captures the discovery envelope, canonical projections, protected handoff ID/digest, broker and
settlement facts, dispatcher call count, no-mutation snapshots, and CLI exits. It uses temporary
repositories and injected GitHub fixtures only; no live Outcome is advanced during the issue PR.

---

## Failure Modes and Stop Conditions

- Any runtime-local directory, transcript, cache, copied receipt, or imported bundle becomes
  canonical structure/completion or portable dispatch authority: stop as a P0 authority violation.
- A cross-clone projection claims `ready`/`dispatched`/`running` or permits mutation without shared
  broker/settlement state: stop; portable output is canonical completion plus candidate frontier only.
- Compatibility/repository/spec validation occurs after store creation, quarantine, broker/fact,
  dispatch, board, GitHub, or spec mutation: stop and restore the preflight boundary.
- Handoff acceptance trusts the public JSON without loading protected local evidence and checking
  current fence/settlement, or can be accepted twice: stop as a P0 replay/forgery defect.
- Two attachment attempts can produce two dispatch intents, acknowledgements, completions, or board
  writes: stop; retain the deterministic interleaving evidence and fix before review.
- The implementation adds a sibling lease, retry queue, completion ledger, active-status store, or
  cross-host cache copier beside #351/#355/#356: stop for scope correction.
- `outcome-bundle/1` still writes a spec or replays cache facts into another repo, or a hidden flag
  restores that behavior: stop; use discovery/reconstruction.
- The Claude PR contains Codex implementation/release edits, or Codex parity is treated as complete
  without its own PR: stop and preserve the cross-repo release boundary.
- Any P0-P3 doc/code-review finding remains, a required validator lacks gate-capable evidence, full
  gates fail, or release metadata drifts: no PR/merge.

---

## Workflow Structure

| step_id | depends_on | barrier | role_id | role_kind | independence | execution_class | runtime_agent_name | vehicle | mutation | required_evidence | role_lens_sha256 | profile_sha256 | expected_model | expected_effort | validator_required | validator_disabled | deterministic_contract_sha256 |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| implement | - | - | root | root | n/a | - | - | root | root-only | authorized-diff,focused-tests | - | - | - | - | n/a | n/a | - |
| review-devils | implement | review | devils-advocate-reviewer | agent-lens | preferred | review-high | review_high | auto | none | scored-review,findings | 129f6dca0702ffcd4be7f9e5d0939e8e6806788846ba4058044c931883ef0e63 | 42e86e00e054281b0a79e4b3b9b544c04a31eb2fd6b53c0489adc42ea639c9a8 | gpt-5.6-sol | high | n/a | n/a | - |
| review-security | implement | review | security-reviewer | agent-lens | preferred | review-high | review_high | auto | none | scored-review,findings | bf5bc1b66c0ee3d06071976b659c522c23057c56de5f6cc010556b2653c86980 | 42e86e00e054281b0a79e4b3b9b544c04a31eb2fd6b53c0489adc42ea639c9a8 | gpt-5.6-sol | high | n/a | n/a | - |
| review-architecture | implement | review | architecture-reviewer | agent-lens | preferred | review-high | review_high | auto | none | scored-review,findings | e48b37cea0b26bf39cae4d6611b4219e907d52d284ba6b9489b523a4b16c835f | 42e86e00e054281b0a79e4b3b9b544c04a31eb2fd6b53c0489adc42ea639c9a8 | gpt-5.6-sol | high | n/a | n/a | - |
| review-testing | implement | review | testing-reviewer | agent-lens | preferred | review-high | review_high | auto | none | scored-review,test-gaps | a867575e24c86b0573485d1d8bbd81514af3654d544342677b85f4bed0d9af63 | 42e86e00e054281b0a79e4b3b9b544c04a31eb2fd6b53c0489adc42ea639c9a8 | gpt-5.6-sol | high | n/a | n/a | - |
| validate-concurrency | implement | validate | concurrency-tester | agent-lens | preferred | test-medium | test_medium | auto | none | concurrency-matrix,command-results | d40188645b7876e32ea592dd9799ee2ad7a2e230d82341611708dd492837b3da | 6d69bb4d5e477574ce186a353a3d2fcc7f8ab6b1f014b93aebb05084aecccc1b | gpt-5.6-terra | medium | true | false | - |
| validate-event-flow | implement | validate | event-flow-tester | agent-lens | preferred | test-medium | test_medium | auto | none | event-trace,command-results | 2e20ab6935b1e17e363b5e28308a9288107532d0118a6a189f07b0e0eaaff356 | 6d69bb4d5e477574ce186a353a3d2fcc7f8ab6b1f014b93aebb05084aecccc1b | gpt-5.6-terra | medium | true | false | - |
| integrate | review-devils,review-security,review-architecture,review-testing,validate-concurrency,validate-event-flow | - | root | root | n/a | - | - | root | root-only | fixed-findings,full-gate,release-parity,git-receipt | - | - | - | - | n/a | n/a | - |

## Workflow Operating Contract

- The authorized subject is this child issue's Claude repository paths and exact Saga release
  surfaces. Root records the pre-existing Git baseline before `implement`; unrelated paths are
  excluded.
- Agent-lens rows authorize `mutation=none` and no external mutation. Current MultiAgent V2 may
  reapply the parent's permission profile, so the named profile is not claimed as an OS-enforced
  read-only sandbox. Root records a baseline, audits the worktree after every attempt, and treats any
  child-created diff as workflow-integrity failure. Root runs commands; validators assess captured
  evidence and semantics.
- `vehicle=auto` requests the named profiles. The runtime receipt must confirm model, effort,
  role-lens hash, and profile hash before the attempt counts. Mismatch is stopped and rerun in a fresh
  bounded context; missing independence/evidence blocks the gate.
- Root fixes every P0-P3 finding and creates a fresh follow-up attempt for affected roles. Three
  unsuccessful remediation cycles halt and page the operator. Any model, effort, lens, validator, or
  execution-class change requires a newly approved workflow candidate.
- Git mutation, PR creation, merge, issue/board mutation, and completion remain root-only. No deploy,
  credential, production data, cache copy, live Outcome advance, force-push, or branch deletion is
  authorized by this workflow.
- Workflow intents, receipts, findings, command logs, workspace/no-write audits, concurrency traces,
  PR URL, merge SHA, issue close, and board reconciliation are retained in the Verified Workflow
  evidence root and issue/PR.

---

## Completion Gate

Completion requires every acceptance row; explicit same-clone versus cross-clone proof; zero
duplicate effects across deterministic races; legacy portable import retired; zero open P0-P3
doc/code-review findings; both validators passing with gate-capable evidence; full verification
green; one atomic Claude issue PR merged; the child issue closed and Operations card reconciled;
Codex parity unblocked with the exact neutral fixtures; and the outcome worktree clean except for the
next planned leaf. This PR does not claim the parent #579 or cross-runtime outcome complete.
