---
title: Lease-safe runtime continuity - Codex cross-runtime Outcome parity
type: feat
status: ready-to-freeze
date: 2026-07-15
deepened: 2026-07-19
origin: docs/outcomes/lease-safe-runtime-continuity/issue-sources/codex-cross-runtime-parity.md
issue: infiquetra/infiquetra-codex-plugins#34
parent: infiquetra/infiquetra-claude-plugins#579
target_repository: infiquetra/infiquetra-codex-plugins
---

# Lease-safe runtime continuity - Codex cross-runtime Outcome parity

## Summary

Port the exact merged Claude `outcome.discovery.v1`, `outcome.canonical-status.v1`,
`outcome.handoff-reference.v1`, and compatibility-HALT contract into Codex-native Saga after both the
Claude compatibility child and Codex shared-runtime substrate merge. The port discovers the same
committed Outcome identity, reconstructs portable canonical completion/candidate-frontier status,
accepts a protected same-clone handoff for one exact `advance-one` or `attend` operation, and retires
legacy `outcome-bundle/1` import authority.

Codex's current dispatch acknowledgement is a preserved invariant, not an upstream difference to
erase. Handoff acceptance creates or resumes the normal Codex `outcome.dispatch.v2` intent; only the
protected `ack_kind=launched` acknowledgement proves dispatch. `handed-off` never counts as launched.
Different-clone discovery is read-only and reports transient lease, handoff, launch, and dispatch
state as unknown.

Like the substrate port, execution uses a new isolated worktree of `infiquetra-codex-plugins`,
driven by the operator's Claude Code session with the cc-workflow ceremony (2026-07-19 operator
decision; the Codex-native auto vehicle was not selected). A fresh runbook-v3 manifest and
classification gate must freeze the exact Claude compatibility SHA, the merged Codex substrate
SHA/manifest digest, Codex preservation drift, and the then-current execution base before behavior
edits. Both prerequisite merges landed 2026-07-19 and are bound under Dependencies below; the plan
is ready to freeze at U1.

## Dependencies and traceability

- **Parent:** `infiquetra/infiquetra-claude-plugins#579`.
- **Outcome specification:**
  `docs/outcomes/lease-safe-runtime-continuity/outcome-spec.json`, node `codex-parity`; hard
  dependencies `claude-cross-runtime` and `codex-substrate`.
- **Claude input (merged):** `infiquetra/infiquetra-claude-plugins` PR #622 closing issue #604,
  merge SHA `97d2fb15dbed7ea210391e3fc293fb0de31dc95e`, Saga 0.103.0. Golden fixtures on `main`
  under `tests/fixtures/outcome-cross-runtime/v1/` (`discovery-envelope.json`,
  `canonical-status.json`, `handoff-reference.json`, `compatibility-halt.json`, plus `invalid/`).
- **Codex input (merged):** `infiquetra/infiquetra-codex-plugins` PR #41 closing issue #33, merge
  SHA `3723a8183e3ea9c372ad9f34fd18f4170c36d26f`, Saga `0.76.0+codex.20260719174556`, Fleet Core
  `0.9.0+codex.20260719174556`. Port manifest
  `docs/portability/ports/2026-07-19-lease-safe-substrate.json`, digest
  `13fe52e36f322357a11fd99104451832e01646f2881ae263b0df990f5bdb140e`. Cross-runtime conformance
  digests pinned at `tests/test_lease_settlement_conformance.py:32-34` (broker registry
  `f60fd482bba4ed5744e4ad590595f9ab92654f66f6371e57350dbc88c75a4b9d`, settlement ledger
  `34804e26ad77eb96eb877d0c5bf3432018c60d739c49f7891aa79e13803a963a`).
- **Procedure:** Codex Claude-to-Codex port runbook v3, `AUTH-CODEX-ADAPTER`.
- **Downstream:** cross-runtime acceptance starts only after this PR merges and its installed/fresh
  proof is bound to the acceptance input set.

## Requirements

R1. **Freeze and classify the exact port.** Create a new staged manifest covering the exact Claude
compatibility source delta and all current Codex preservation drift. Capture sanitized active-session
capability facts and exhaustive path rows. Pass classification before source-derived behavior edits.
Unrelated substrate rows are `preserve`; no hidden re-port of lease/settlement behavior is allowed.
First copy this coordinator plan and review into the isolated target branch, bind it to
`infiquetra/infiquetra-codex-plugins#34`, and run a focused plan/doc-review refresh against the frozen
Claude/Codex inputs. Bind those exact target-repo planning bytes in the manifest.

R2. **Use exact upstream schemas and fixtures.** Adapt the merged closed parsers/serializers and copy
only neutral fixture bytes classified by the manifest. Unknown protocols, fields in security-bearing
objects, types, duplicate keys, missing capabilities, unsupported Outcome schemas, and size/time
limits HALT before store, broker, fact, GitHub, board, or spec mutation. Codex must not fork the schema
inside this PR.

R3. **Derive repository and committed-spec identity independently.** Resolve the canonical GitHub
repository identity and committed Outcome blob with fixed-argv Git. Compare repo, Outcome ID, path,
commit/blob/digest, revision, protocol, and capability bindings before accessing mutable state. Paths,
fork proximity, copied files, runtime homes, caches, and rollout history are never identity.

R4. **Keep cross-clone projection honest and read-only.** From a second clone, derive only canonical
completion and dependency candidate frontier from committed spec plus GitHub evidence. Serialize
`mutation_allowed:false` and transient state unknown. Do not claim local ready/dispatched/running,
copy common-dir data, or accept a handoff reference from another clone.

R5. **Consume protected same-clone handoffs, not bearer tokens.** Reopen the local protected record by
opaque ID/digest, verify the seal, same canonical repository/common-dir, committed binding, broker
issuer/fence, settlement identity, exact receiver, exact operation, one subplot, nonce/state, maximum
300-second TTL, and maximum 30-second future skew. Use offer -> accept-intent -> substrate successor
fence -> accept-commit. Only the same receiver may resume a crash gap. Copied, cross-clone, broad,
replayed, expired, future-skewed, forged, modified, wrong-repo/revision/operation/subplot/issuer, or
superseded evidence HALTs before mutation.

R6. **Translate `advance-one` through native dispatch-v2.** A successful handoff authorizes one
allowlisted subplot, not a frontier, loop, or Outcome-wide resume. After compatibility and handoff
preflight, consume the substrate broker/guard/settlement contract, create or observe the native Codex
dispatch intent, invoke the backend at most once, and require protected `ack_kind=launched` before
Codex reports dispatched. A handoff acceptance/ack is never substituted for launch acknowledgement.
Substrate consumption here is scoped to handoff acceptance and its single authorized advance; the
repository-wide dispatcher lease seam stays dormant in this PR (KTD6).

R7. **Retire legacy bundle mutation.** Codex `export` becomes the same deprecated read-only discovery
alias defined by Claude. `import` rejects `outcome-bundle/1` before saving a spec or replaying
completion/dispatch/receipt/fact state and returns the precise discover/attach migration command.
No flag restores portable cache authority.

R8. **Prove both runtime orders and all no-mutation failures.** Use the exact Claude golden fixtures,
real same-clone/linked-worktree and separate-clone Git topologies, deterministic process barriers,
write-once backend, and injected GitHub evidence. Prove one shared settlement/effect and native Codex
ack semantics for Claude-first and Codex-first attempts. Snapshot every mutable boundary around
compatibility, cross-clone, forged, replayed, and legacy-import failures.

R9. **Release through the full port cutover.** Update Saga behavior docs, skill, portability notes,
manifest/changelog/inventory, generated classification, tests, and journal after behavior passes.
Calculate the next target version from the fresh base. Pass port classification/unit/cutover,
focused/full tests, repository validation, isolated install, separately authenticated fresh-session
readback, and exact rollback before PR merge.

## Key decisions

- **KTD1 - protocol parity is not transient-state parity.** Cross-clone equality covers canonical
  completion and candidate frontier only; local coordination is intentionally absent.
- **KTD2 - a handoff is scoped authority, not launch evidence.** Codex's protected launched ack stays
  mandatory after acceptance.
- **KTD3 - substrate is consumed, not reimplemented.** This PR changes the compatibility/Outcome
  adapter only and preserves the broker/settlement port unless a separately reviewed defect is filed.
- **KTD4 - legacy import is incompatible.** Cache/spec replay creates competing authority and is
  removed rather than emulated.
- **KTD5 - upstream fixture drift stops the port.** Codex consumes exact merged bytes/digests; any
  desired schema change returns to the Claude contract issue first.
- **KTD6 - the repository-wide lease seam stays dormant here.** Operator decision 2026-07-19: this
  PR does not rewire `plugins/saga/scripts/outcome.py` (`make_dispatcher` call, line 2048 at the
  substrate merge) to pass `default_lease_authority()`, and the deferred `audit_store`
  ancestor-directory hardening owed by the first live wiring stays deferred with it. Both belong to
  the `cross-runtime-acceptance` leaf. Verifying the seam is still dormant is a review obligation of
  this PR.

## Implementation units

### U1. Fresh port manifest and preservation classification

Create the isolated worktree; copy and refresh the target-repo plan/review; freeze Claude/Codex refs,
pathspecs, source row count, current Codex
drift, active capability snapshot, substrate manifest digest, and runbook digest; generate and review
the manifest/classification; pass the classification gate before behavior edits.

### U2. Compatibility schemas, identity, and discovery

Adapt the closed schemas, bounded deterministic JSON, repository normalization, committed-blob
resolution, ambiguity/wrong-repo rejection, and compatibility negotiation into Codex Saga. Load the
exact neutral Claude fixtures unchanged only where the manifest classifies them portable. Add pure
schema and real-Git topology tests with no-mutation oracles.

### U3. Canonical cross-clone status

Reuse Codex's existing completion predicates through a non-materializing read path. Produce the exact
canonical-status schema with completed/candidate/unknown evidence, stable digests, and
`mutation_allowed:false`. Prove byte-equivalent projection from equivalent Git/GitHub inputs across
different paths without creating/copying local coordination state.

### U4. Protected handoff and one-leaf native advance

Adapt offer/accept validation to the merged Codex substrate guard. Wire `discover`, `handoff`, and
`attach` to Codex's Outcome skill/CLI. Accept only one operation/subplot, bind the successor fence,
then enter a one-subplot dispatch path that retains `outcome.dispatch.v2`. Inject crash windows,
replay, TTL/skew, wrong-root/spec/fence, concurrent receiver, backend failure, and acknowledgement
variants.

### U5. Legacy migration, docs, release, and cutover

Reject legacy import, alias export to discovery, update Codex-native docs/skill and release surfaces,
record journal decisions, finish manifest evidence, run full gates, install in isolation, prove a
fresh session and exact rollback, pass cutover, and merge one atomic issue PR.

## Expected target paths

```text
docs/portability/ports/<date>-outcome-cross-runtime-parity.json
docs/portability/classifications/<date>-outcome-cross-runtime-parity.md
docs/validation/<port-id>/...
plugins/saga/scripts/outcome_compat.py
plugins/saga/scripts/outcome.py
plugins/saga/scripts/outcome_spec.py
plugins/saga/scripts/outcome_store.py
plugins/saga/scripts/outcome_orchestrator.py
plugins/saga/scripts/outcome_dispatcher.py
plugins/saga/skills/outcome/SKILL.md
plugins/saga/references/outcome-cross-runtime.md
tests/fixtures/outcome-cross-runtime/v1/
tests/test_outcome_cross_runtime.py
tests/test_outcome_dispatch_migration.py
tests/test_outcome_cross_runtime_parity_port_contract.py
tests/test_outcome_command.py
plugins/saga/PORTABILITY.md
plugins/saga/.codex-plugin/plugin.json
plugins/saga/CHANGELOG.md
docs/portability/matrix.md
docs/engineering-journal/DECISIONS.md
```

The fresh manifest owns the exact inventory. Fleet Core production behavior is preserve-only here.

## Verification

The `scripts/port_contract.py validate` CLI is permanently pinned to the 2026-07-11
external-advisory port (its port identifier, frozen refs, row counts, and digests) and cannot pass
for any later port. Per the codex journal decision "2026-07-19: Lease-Safe Substrate Ports
Byte-Faithful, Gates Per-Port" (`docs/engineering-journal/DECISIONS.md`), this port gates through
its own per-port pytest file, which carries the classification, per-unit, and cutover assertions
(manifest digest integrity, row states, evidence recency, `refresh_changes == []`, release
coherence) — the same pattern the substrate port used.

```bash
PYTHONPATH=. uv run pytest tests/test_outcome_cross_runtime_parity_port_contract.py -v
PYTHONPATH=. uv run pytest tests/test_outcome_cross_runtime.py tests/test_outcome_dispatch_migration.py -v
PYTHONPATH=. uv run pytest tests/test_outcome_store.py tests/test_outcome_command.py tests/test_outcome_completion.py -v
PYTHONPATH=. uv run pytest -q
python3 scripts/validate_codex_plugins.py
git diff --check
```

## Stop conditions

- Either merged prerequisite SHA/version/manifest digest is absent, changed, unreachable, or cannot
  be represented by an exhaustive current port contract.
- Any behavior edit precedes the classification gate or touches the dirty primary Codex worktree.
- Codex changes the upstream schema/fixture rather than returning to the Claude issue.
- Cross-clone status claims transient authority or permits mutation; a handoff works outside the
  shared common dir; or a public reference alone authorizes.
- Handoff acceptance marks a leaf launched or bypasses the native dispatch intent/protected launched
  acknowledgement.
- Legacy import writes/replays anything, or an escape hatch retains portable cache authority.
- The repository-wide dispatcher lease seam is activated, or the deferred `audit_store`
  ancestor-directory hardening is pulled into this PR (both belong to `cross-runtime-acceptance`
  per KTD6).
- A duplicate effect, settlement, launch ack, completion, board write, or GitHub write is possible.
- Any P0-P3 review finding, validator failure, port gate, install/fresh-session/rollback proof,
  repository validation, or full test remains unresolved.

## Workflow Structure

| step_id | depends_on | barrier | role_id | role_kind | independence | vehicle | agent_type | model | effort | isolation | mutation | required_evidence |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| implement | - | - | root | root | n/a | session-root | - | - | - | isolated-codex-worktree | root-only | port-contract,authorized-diff,focused-tests |
| review-devils | implement | review | devils-advocate | agent-lens | separate-context | cc-workflow-agent | saga:readonly-verifier | opus | high | worktree | none | scored-review,findings |
| review-security | implement | review | security | agent-lens | separate-context | cc-workflow-agent | saga:readonly-verifier | opus | high | worktree | none | scored-review,findings |
| review-architecture | implement | review | architecture | agent-lens | separate-context | cc-workflow-agent | saga:readonly-verifier | opus | high | worktree | none | scored-review,findings |
| review-testing | implement | review | testing | agent-lens | separate-context | cc-workflow-agent | saga:readonly-verifier | opus | high | worktree | none | scored-review,test-gaps |
| validate-concurrency | implement | validate | concurrency | agent-lens | separate-context | cc-workflow-agent | saga:readonly-verifier | sonnet | medium | worktree | none | concurrency-matrix,command-results |
| validate-event-flow | implement | validate | event-flow | agent-lens | separate-context | cc-workflow-agent | saga:readonly-verifier | sonnet | medium | worktree | none | event-trace,command-results |
| integrate | review-devils,review-security,review-architecture,review-testing,validate-concurrency,validate-event-flow | - | root | root | n/a | session-root | - | - | - | isolated-codex-worktree | root-only | fixed-findings,classification-unit-cutover,full-gate,install-fresh-session-rollback,git-receipt |

## Workflow operating contract

- Runtime: root is the operator's Claude Code session on the cc-workflow backend, working in a
  fresh isolated `git worktree` of `infiquetra-codex-plugins` (the primary Codex checkout stays
  untouched). Root owns implementation, Git, integration, PR creation, merge under the operator's
  standing outcome approval, issue closure, and board reconciliation. The authorized subject is
  this issue's implementation paths plus exact Saga release surfaces; root records the pre-existing
  Git baseline before `implement`, and unrelated worktree paths are excluded.
- Lens dispatch: the six agent-lens rows execute as `agent()` calls inside one root-authored Claude
  Code Workflow script, each with exactly the agent_type, model, effort, and worktree-isolation
  cells above, routed through a bounded pool so total in-flight subagents never exceed 3. Each call
  embeds its lens charter below plus the diff and evidence scope. Spawn parameters are
  harness-recorded and root records per-lens receipts in the review artifacts; no cryptographic
  attestation is claimed. If the Workflow tool is unavailable, halt and page the operator — never
  silently downgrade to another dispatch path.
- `agent_type=saga:readonly-verifier` is the session's mandated read-only sandbox profile for
  review/verify spawns (Bash/Read/Grep/Glob in a disposable worktree, per
  `infiquetra-claude-plugins` `plugins/saga/references/sandbox-spawn-sites.md`); per-call
  model/effort opts override the profile's default tier. Root audits the working tree after every
  lens attempt and treats any unexplained diff as workflow-integrity failure.
- Lens charters: **devils-advocate** — attack the authority chain end to end: whether handoff
  acceptance can ever masquerade as launch evidence, offer -> accept-intent -> successor-fence ->
  accept-commit crash windows, TTL/skew and replay edges, cross-clone or copied-record escape
  hatches, legacy `outcome-bundle/1` resurrection paths, and any HALT edge reachable only after a
  side effect; **security** — trust boundaries of the adapted closed schemas: seal verification and
  forgery, bearer-token creep in handoff references, repository-identity spoofing (fork, copied
  spec, foreign remote), wrong-issuer/fence/receiver/operation rejection exactness, redaction (no
  paths, credentials, transcripts), and clock-skew/freshness enforcement; **architecture** —
  KTD2/KTD3/KTD5/KTD6 conservation: substrate consumed not reimplemented, the `outcome_compat.py`
  module boundary, byte-exact schema/fixture parity with the merged Claude contract, dispatch-v2
  protected launched-ack semantics preserved, the dispatcher lease seam verified still dormant, and
  release-surface coherence; **testing** — both-runtime-order proofs (Claude-first and
  Codex-first), real-Git topology matrices (same clone, linked worktree, separate clone),
  no-mutation snapshots around every HALT, golden-fixture byte round trips, and negative-path
  coverage of every R5 rejection; **concurrency** (validator) — independently assess the
  single-advance proof from captured evidence: handoff double-accept races, successor-fence
  interleavings against broker admission, crash-window resumption by the same receiver only, and
  exact effect/fact counts; **event-flow** (validator) — trace discovery -> compatibility ->
  protected offer/accept -> successor fence -> native dispatch-v2 intent -> protected
  `ack_kind=launched` end to end across store, ledger, and GitHub sites, including every HALT
  edge's proven non-mutation.
- Root fixes every P0-P3 finding and re-runs the affected lenses fresh. Three unsuccessful
  remediation cycles halt and page the operator. Any model, effort, lens, validator, or vehicle
  change requires a newly approved workflow candidate. The approval anchor is the SHA-256 of the
  exact `## Workflow Structure` and `## Workflow operating contract` section bytes, recorded in the
  delta review artifact.
- Git mutation, PR creation, merge, issue/board mutation, and completion remain root-only. No
  deploy, credentials, production data, live Outcome advance, real-profile mutation, cache copy,
  force-push, or branch deletion is authorized.
- Workflow receipts, findings, command logs, workspace audits, PR URL, merge SHA, issue close, and
  board reconciliation are retained in the repo's review and work-session artifacts and on the
  issue/PR.

## Completion gate

All exact compatibility fixtures and acceptance rows pass; cross-clone behavior is read-only;
handoff is protected, bounded, and one-use; dispatch-v2 launch acknowledgement remains intact; the
dispatcher lease seam is proven still dormant (KTD6); legacy import is non-mutating; the port
gates, isolated install, fresh session, rollback, full tests, and zero-finding code review pass;
one atomic Codex PR merges; the issue/board reconcile; and the exact merged SHA/version/schema and
manifest digests are handed to the acceptance issue.
