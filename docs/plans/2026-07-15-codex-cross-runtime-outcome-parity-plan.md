---
title: Lease-safe runtime continuity - Codex cross-runtime Outcome parity
type: feat
status: ready-to-freeze
date: 2026-07-15
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

Like the substrate port, execution uses a new isolated Codex worktree. A fresh runbook-v3 manifest
and classification gate must freeze the exact Claude compatibility SHA, the merged Codex substrate
SHA/manifest digest, Codex preservation drift, and the then-current execution base before behavior
edits. This plan is `ready-to-freeze` until those inputs exist.

## Dependencies and traceability

- **Parent:** `infiquetra/infiquetra-claude-plugins#579`.
- **Outcome specification:**
  `docs/outcomes/lease-safe-runtime-continuity/outcome-spec.json`, node `codex-parity`; hard
  dependencies `claude-cross-runtime` and `codex-substrate`.
- **Claude input:** exact merged contract, fixtures under
  `tests/fixtures/outcome-cross-runtime/v1/`, release version, journal decisions, and SHA.
- **Codex input:** exact merged substrate SHA, port-manifest digest, neutral broker-root contract,
  settlement identity, resource guard, installed proof, and native dispatch-v2 tests.
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
tests/test_outcome_command.py
plugins/saga/PORTABILITY.md
plugins/saga/.codex-plugin/plugin.json
plugins/saga/CHANGELOG.md
docs/portability/matrix.md
docs/engineering-journal/DECISIONS.md
```

The fresh manifest owns the exact inventory. Fleet Core production behavior is preserve-only here.

## Verification

```bash
python3 scripts/port_contract.py validate --manifest <manifest> --stage classification
python3 scripts/port_contract.py validate --manifest <manifest> --stage unit --unit U2
python3 scripts/port_contract.py validate --manifest <manifest> --stage unit --unit U3
python3 scripts/port_contract.py validate --manifest <manifest> --stage unit --unit U4
python3 -m pytest tests/test_outcome_cross_runtime.py tests/test_outcome_dispatch_migration.py -v
python3 -m pytest tests/test_outcome_store.py tests/test_outcome_command.py tests/test_outcome_completion.py -v
python3 -m pytest
python3 scripts/validate_codex_plugins.py
python3 scripts/port_contract.py validate --manifest <manifest> --stage cutover
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
- A duplicate effect, settlement, launch ack, completion, board write, or GitHub write is possible.
- Any P0-P3 review finding, validator failure, port gate, install/fresh-session/rollback proof,
  repository validation, or full test remains unresolved.

## Workflow Structure

| step_id | depends_on | barrier | role_id | role_kind | independence | execution_class | runtime_agent_name | vehicle | mutation | required_evidence | role_lens_sha256 | profile_sha256 | expected_model | expected_effort | validator_required | validator_disabled | deterministic_contract_sha256 |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| implement | - | - | root | root | n/a | - | - | root | root-only | port-contract,authorized-diff,focused-tests | - | - | - | - | n/a | n/a | - |
| review-devils | implement | review | devils-advocate-reviewer | agent-lens | preferred | review-high | review_high | auto | none | scored-review,findings | 129f6dca0702ffcd4be7f9e5d0939e8e6806788846ba4058044c931883ef0e63 | 42e86e00e054281b0a79e4b3b9b544c04a31eb2fd6b53c0489adc42ea639c9a8 | gpt-5.6-sol | high | n/a | n/a | - |
| review-security | implement | review | security-reviewer | agent-lens | preferred | review-high | review_high | auto | none | scored-review,findings | bf5bc1b66c0ee3d06071976b659c522c23057c56de5f6cc010556b2653c86980 | 42e86e00e054281b0a79e4b3b9b544c04a31eb2fd6b53c0489adc42ea639c9a8 | gpt-5.6-sol | high | n/a | n/a | - |
| review-architecture | implement | review | architecture-reviewer | agent-lens | preferred | review-high | review_high | auto | none | scored-review,findings | e48b37cea0b26bf39cae4d6611b4219e907d52d284ba6b9489b523a4b16c835f | 42e86e00e054281b0a79e4b3b9b544c04a31eb2fd6b53c0489adc42ea639c9a8 | gpt-5.6-sol | high | n/a | n/a | - |
| review-testing | implement | review | testing-reviewer | agent-lens | preferred | review-high | review_high | auto | none | scored-review,test-gaps | a867575e24c86b0573485d1d8bbd81514af3654d544342677b85f4bed0d9af63 | 42e86e00e054281b0a79e4b3b9b544c04a31eb2fd6b53c0489adc42ea639c9a8 | gpt-5.6-sol | high | n/a | n/a | - |
| validate-concurrency | implement | validate | concurrency-tester | agent-lens | preferred | test-medium | test_medium | auto | none | concurrency-matrix,command-results | d40188645b7876e32ea592dd9799ee2ad7a2e230d82341611708dd492837b3da | 6d69bb4d5e477574ce186a353a3d2fcc7f8ab6b1f014b93aebb05084aecccc1b | gpt-5.6-terra | medium | true | false | - |
| validate-event-flow | implement | validate | event-flow-tester | agent-lens | preferred | test-medium | test_medium | auto | none | event-trace,command-results | 2e20ab6935b1e17e363b5e28308a9288107532d0118a6a189f07b0e0eaaff356 | 6d69bb4d5e477574ce186a353a3d2fcc7f8ab6b1f014b93aebb05084aecccc1b | gpt-5.6-terra | medium | true | false | - |
| integrate | review-devils,review-security,review-architecture,review-testing,validate-concurrency,validate-event-flow | - | root | root | n/a | - | - | root | root-only | fixed-findings,classification-unit-cutover,full-gate,install-fresh-session-rollback,git-receipt | - | - | - | - | n/a | n/a | - |

## Workflow operating contract

Root owns all mutations and commands. Reviewers and validators are read-only agent lenses with no
repository or external mutation. Their requested Sol-high and Terra-medium profiles must be confirmed
by runtime receipts; mismatch/absence is rerun in a fresh bounded context. Root fixes every P0-P3
finding and reruns affected gates, stopping after three unsuccessful remediation cycles. No deploy,
credentials, production data, live Outcome advance, real-profile mutation, cache copy, force-push,
or branch deletion is authorized.

## Completion gate

All exact compatibility fixtures and acceptance rows pass; cross-clone behavior is read-only;
handoff is protected, bounded, and one-use; dispatch-v2 launch acknowledgement remains intact; legacy
import is non-mutating; the port gates, isolated install, fresh session, rollback, full tests, and
zero-finding code review pass; one atomic Codex PR merges; the issue/board reconcile; and the exact
merged SHA/version/schema and manifest digests are handed to the acceptance issue.
