---
title: Lease-safe runtime continuity - cross-runtime acceptance proof
type: test
status: ready-to-freeze
date: 2026-07-15
origin: docs/outcomes/lease-safe-runtime-continuity/issue-sources/cross-runtime-acceptance.md
issue: infiquetra/infiquetra-claude-plugins#605
parent: infiquetra/infiquetra-claude-plugins#579
---

# Lease-safe runtime continuity - cross-runtime acceptance proof

## Summary

Build and run an independent, revision-pinned acceptance harness against the merged Claude and Codex
Saga releases. The harness uses isolated clean checkouts, installs both plugin packages under test,
and exercises them against one temporary target Git clone plus a second independent clone. It proves
canonical discovery in both directions, protected bounded handoff in both directions, exactly one
dispatch side effect under a real two-process race, native Codex launch acknowledgement, shared
settlement, cross-clone read-only reconstruction, compatibility and legacy-import failure, teardown,
and a clean #353 fleet-doctor result.

The acceptance PR contains harness, fixtures, evidence schema/bundle, interpretation docs, and the
outcome report only. It does not repair either production runtime. A failing behavior creates or
reopens a defect against its owner and leaves the acceptance issue open.

This plan is `ready-to-freeze`: implementation begins only after the exact merged Claude contract,
Codex substrate, Codex protocol-parity, and #353 SHAs/versions/evidence are available and pass their
own gates.

## Hard inputs and authority

- Outcome specification
  `docs/outcomes/lease-safe-runtime-continuity/outcome-spec.json`, node
  `cross-runtime-acceptance`; hard dependencies are `sub-353` and `codex-parity`.
- Exact merged PR SHAs and installed Saga/Fleet Core versions for Claude compatibility, Codex shared
  substrate, and Codex protocol parity.
- Claude compatibility schema and fixture digest plus both Codex port-manifest/cutover digests.
- Runtime-neutral broker-root resolution contract and the redacted canonical-root digest reported by
  both installed runtimes.
- Completed #353 command/report schema and exact merged SHA; transitively merged #351/#355/#357/#358.
- Deterministic GitHub fixtures. No live issue, board, PR, credential, or production-data mutation is
  part of acceptance.
- One acceptance branch/PR in `infiquetra-claude-plugins`; Codex remains read-only input at its exact
  merged revision.

## Acceptance topology

```text
clean Claude checkout @ merged SHA ---- install ----+
                                                   |
clean Codex checkout @ merged SHA ----- install ----+---- temporary target clone A
                                                   |       shared git-common-dir
                                                   |       shared neutral broker root
                                                   |       write-once fake backend
                                                   |
                                                   +---- temporary target clone B
                                                          no common-dir copy
                                                          no broker/handoff/launch copy
                                                          committed spec + GitHub fixture only
```

The protected handoff reference never leaves clone A. Clone B proves canonical completion and
candidate-frontier reconstruction only; transient state is explicitly unknown and mutation is
forbidden.

## Requirements

R1. **Pin source and installed identity before running.** The harness accepts only clean repositories
at exact expected SHAs, verifies plugin manifest versions and relevant schema/port-manifest digests,
installs into isolated homes, and records package/readback identity. Dirty, wrong-SHA, wrong-version,
dual-package, or unproved installed state HALTs before the scenario suite.

R2. **Use contained deterministic fixtures.** Create temporary Git repositories and deterministic
GitHub completion fixtures. Select an explicit safe runtime-neutral fleet root under the test temp
directory and require both runtimes to report the same redacted canonical-root digest. Never read or
copy default-profile caches, credentials, transcripts, rollout history, protected receipts, or live
GitHub state.

R3. **Prove canonical discovery in both directions.** Claude-created and Codex-created committed
Outcome specs are discovered through the other installed runtime. Same-clone reads may overlay local
transient state; cross-clone serialized parity compares only canonical completed nodes, dependency
candidate frontier, unknown evidence, and source digests. Cross-clone `mutation_allowed` is false and
lease/handoff/launch/dispatch state is unknown.

R4. **Prove protected handoff in both directions.** Claude -> Codex and Codex -> Claude each offer and
accept exactly one operation (`advance-one` or `attend`) and one subplot inside clone A. Test copied
reference, clone B, wrong repository/revision/operation/subplot/receiver/issuer/fence, broad scope,
replay, byte tamper, missing record, expiry beyond 300 seconds, and future skew beyond 30 seconds.
Every rejection precedes any mutable effect.

R5. **Prove actual concurrent overlap and one effect.** Start two OS processes, one per runtime, and
release them through a deterministic barrier immediately before broker admission/dispatch. Record
monotonic enter/release/exit events proving overlap; a test that accidentally serializes fails. Both
processes target one ready leaf and one write-once fake backend. Across both orderings and crash
windows, exactly one backend effect, one shared logical settlement, and no missing dispatch unit may
exist.

R6. **Preserve native Codex acknowledgement.** When Codex is the launcher, its normal
`outcome.dispatch.v2` intent plus protected `ack_kind=launched` chain must exist. A handoff,
`ack_kind=handed-off`, shared settlement alone, or legacy record cannot satisfy this assertion. When
Claude launches, Codex must observe shared settlement without inventing a Codex launched ack.

R7. **Prove compatibility and authority failures are mutation-free.** Unknown protocol/capability or
Outcome schema, wrong repository, stale spec, divergent root digest, malformed/oversized envelope,
and runtime-local authority attempts HALT before spec, common-dir, broker, receipt, settlement,
backend, board, or GitHub mutation. Capture pre/post hashes and effect-spy counts.

R8. **Prove legacy bundle import is dead.** Both installed runtimes reject `outcome-bundle/1` import
before writing a spec or replaying completion, dispatch, receipt, fact, lease, board, or GitHub state.
Deprecated export/discovery output remains read-only and cannot authorize attachment by itself.

R9. **Prove terminal closure.** Run the merged teardown/reclamation path for every scenario fixture,
then invoke #353 against raw sources. Require zero open worktrees, fleet leases/resources, dispatch
positions, receiptless delegations, dead wiring, or unclosed protected handoff/accept records. Re-run
teardown to prove idempotency.

R10. **Emit a closed, privacy-safe evidence bundle.** Record schema version, exact repo SHAs, plugin
versions, compatibility/port-manifest digests, broker-root digest, commands, scenario IDs, verdicts,
timing/overlap summary, fact/effect counts, artifact SHA-256 and sizes, and environment-variable name
allowlist. Store hashes and bounded summaries rather than raw stdout/stderr. Reject absolute paths,
home paths, tokens, prompts, transcripts, child output, credentials, raw GitHub bodies, or secret-
shaped values.

R11. **QA is a mandatory downstream gate.** After implementation, Verified Workflow, code review,
and fixes, run `saga:qa` against the pinned release artifacts and acceptance evidence. #579 and the
outcome close only if QA accepts every criterion with no waiver.

## Key decisions

- **KTD1 - revision-pinned installed behavior, not working-tree claims.** Every verdict is bound to
  exact merged source and installed package identities.
- **KTD2 - concurrency needs a happens-before receipt.** Two processes plus a deterministic barrier
  and write-once backend are mandatory; two sequential CLI calls are not evidence.
- **KTD3 - equivalent cross-clone status excludes transient state.** False equality is worse than an
  explicit unknown.
- **KTD4 - acceptance never fixes production.** Failure routes to the owning Claude or Codex issue.
- **KTD5 - handoff is same-clone protected state.** Only its opaque reference is printable; it is not
  copied to clone B or treated as a bearer credential.
- **KTD6 - one settlement does not replace runtime acknowledgement.** The harness asserts both shared
  idempotency truth and Codex's native launch proof where applicable.

## Implementation units

### U1. Pinning, isolated installation, and evidence schema

Implement strict CLI inputs for both repos/SHAs/versions and output path. Validate cleanliness,
identity, package manifests, schema/port digests, and isolated installation/readback. Define and test
the closed evidence schema, privacy allowlist, atomic output, artifact hashing, and failed-run bundle.

### U2. Git/GitHub topology and canonical discovery matrix

Build clone A and independent clone B from a deterministic origin; install a committed Outcome spec;
inject GitHub evidence; run both runtimes as subprocesses; compare canonical projections in both
creation directions; assert no coordination state appears in clone B and mutation is denied.

### U3. Protected handoff and compatibility-negative matrix

Exercise both handoff directions and every identity/scope/freshness/replay failure. Add compatibility,
root-digest, malformed/oversized, runtime-local authority, and legacy-import tests with pre/post
filesystem and external-writer spies.

### U4. Concurrent dispatch, crash, settlement, and acknowledgement matrix

Add the deterministic process barrier, write-once backend, invocation audit, and crash injection.
Run Claude-first, Codex-first, simultaneous, loser-retry, winner-crash-before/after-effect, lease
expiry/successor, and already-settled cases. Assert one effect/settlement and exact runtime-native
acknowledgement rules.

### U5. Teardown, fleet doctor, durable report, and QA handoff

Run reclamation twice, invoke #353 raw-source correlation, require zero open positions, emit the final
evidence bundle and interpretation README, update the outcome report/journal if warranted, run full
repository checks, code review/fixes, and `saga:qa`. Failures retain artifacts and file/reopen the
owning defect without production edits.

## Expected files

```text
tools/run_cross_runtime_outcome_acceptance.py
tests/test_outcome_cross_runtime.py
tests/fixtures/outcome-cross-runtime-acceptance/
docs/validation/lease-safe-runtime-continuity/cross-runtime-acceptance.schema.json
docs/validation/lease-safe-runtime-continuity/cross-runtime-acceptance.json
docs/validation/lease-safe-runtime-continuity/README.md
docs/outcomes/lease-safe-runtime-continuity/report.md
docs/engineering-journal/LEARNINGS.md or DECISIONS.md only for durable findings
```

No production plugin module or release version belongs in this PR. If the harness requires one, stop
and open/reopen the owning runtime defect.

## Verification

```bash
uv run pytest tests/test_outcome_cross_runtime.py -v
uv run python tools/run_cross_runtime_outcome_acceptance.py \
  --claude-repo <clean-claude-checkout> \
  --claude-sha <merged-sha> \
  --codex-repo <clean-codex-checkout> \
  --codex-sha <merged-sha> \
  --output docs/validation/lease-safe-runtime-continuity/cross-runtime-acceptance.json
uv run pytest
uv run ruff format --check .
uv run ruff check .
uv run mypy plugins/ scripts/ tests/ --ignore-missing-imports
uv run bandit -r plugins/
uv run python scripts/check_release_surface_parity.py
uv run python scripts/sync_marketplace.py --check
git diff --check
```

`saga:qa` separately validates every acceptance selector, artifact binding, rerun command, privacy
boundary, and residual risk after the implementation/code-review loop.

## Stop conditions

- Any prerequisite is unmerged, unpinned, dirty, version/digest-mismatched, uninstalled, or fails its
  own current full gate.
- The harness reads/copies a real runtime cache, protected receipt, transcript, rollout, credential,
  or live external state.
- Process overlap is not proven, the fake backend is not write-once, or a duplicate/missing effect,
  settlement, dispatch unit, completion, board/GitHub write, or acknowledgement appears.
- Cross-clone output claims transient authority, clone B can mutate, or a copied handoff works.
- Any invalid/skew/legacy path mutates state before HALT.
- Teardown/doctor leaves any resource, dispatch, delegation, handoff, or wiring position open.
- Evidence cannot bind exact SHAs/versions/digests/commands or violates the privacy schema.
- A production fix is needed in the acceptance PR, or any P0-P3 review/QA finding remains.

## Workflow Structure

| step_id | depends_on | barrier | role_id | role_kind | independence | execution_class | runtime_agent_name | vehicle | mutation | required_evidence | role_lens_sha256 | profile_sha256 | expected_model | expected_effort | validator_required | validator_disabled | deterministic_contract_sha256 |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| implement | - | - | root | root | n/a | - | - | root | root-only | pinned-inputs,authorized-diff,focused-tests | - | - | - | - | n/a | n/a | - |
| review-devils | implement | review | devils-advocate-reviewer | agent-lens | preferred | review-high | review_high | auto | none | scored-review,findings | 129f6dca0702ffcd4be7f9e5d0939e8e6806788846ba4058044c931883ef0e63 | 42e86e00e054281b0a79e4b3b9b544c04a31eb2fd6b53c0489adc42ea639c9a8 | gpt-5.6-sol | high | n/a | n/a | - |
| review-security | implement | review | security-reviewer | agent-lens | preferred | review-high | review_high | auto | none | scored-review,findings | bf5bc1b66c0ee3d06071976b659c522c23057c56de5f6cc010556b2653c86980 | 42e86e00e054281b0a79e4b3b9b544c04a31eb2fd6b53c0489adc42ea639c9a8 | gpt-5.6-sol | high | n/a | n/a | - |
| review-architecture | implement | review | architecture-reviewer | agent-lens | preferred | review-high | review_high | auto | none | scored-review,findings | e48b37cea0b26bf39cae4d6611b4219e907d52d284ba6b9489b523a4b16c835f | 42e86e00e054281b0a79e4b3b9b544c04a31eb2fd6b53c0489adc42ea639c9a8 | gpt-5.6-sol | high | n/a | n/a | - |
| review-testing | implement | review | testing-reviewer | agent-lens | preferred | review-high | review_high | auto | none | scored-review,test-gaps | a867575e24c86b0573485d1d8bbd81514af3654d544342677b85f4bed0d9af63 | 42e86e00e054281b0a79e4b3b9b544c04a31eb2fd6b53c0489adc42ea639c9a8 | gpt-5.6-sol | high | n/a | n/a | - |
| validate-concurrency | implement | validate | concurrency-tester | agent-lens | preferred | test-medium | test_medium | auto | none | happens-before-matrix,effect-counts,command-results | d40188645b7876e32ea592dd9799ee2ad7a2e230d82341611708dd492837b3da | 6d69bb4d5e477574ce186a353a3d2fcc7f8ab6b1f014b93aebb05084aecccc1b | gpt-5.6-terra | medium | true | false | - |
| validate-event-flow | implement | validate | event-flow-tester | agent-lens | preferred | test-medium | test_medium | auto | none | event-trace,settlement-ack-chain,command-results | 2e20ab6935b1e17e363b5e28308a9288107532d0118a6a189f07b0e0eaaff356 | 6d69bb4d5e477574ce186a353a3d2fcc7f8ab6b1f014b93aebb05084aecccc1b | gpt-5.6-terra | medium | true | false | - |
| validate-scenarios | implement | validate | scenario-tester | agent-lens | preferred | test-medium | test_medium | auto | none | acceptance-matrix,evidence-schema,command-results | 8167b31e38f328eca0bf4cfc4ad782ee3a85669af7b08be8aa422b8edbc46f68 | 6d69bb4d5e477574ce186a353a3d2fcc7f8ab6b1f014b93aebb05084aecccc1b | gpt-5.6-terra | medium | true | false | - |
| integrate | review-devils,review-security,review-architecture,review-testing,validate-concurrency,validate-event-flow,validate-scenarios | - | root | root | n/a | - | - | root | root-only | fixed-findings,full-gate,qa-verdict,evidence-bundle,git-receipt | - | - | - | - | n/a | n/a | - |

## Workflow operating contract

Root is the only writer and owns commands, integration, Git, PR/merge, issue/board reconciliation,
and QA routing. Reviewers/validators are read-only agent lenses and authorize no external mutation.
The runtime receipt must match each requested Sol-high or Terra-medium profile/lens; missing or
mismatched evidence is rerun fresh. Root fixes all P0-P3 findings and reruns affected roles, stopping
after three unsuccessful remediation cycles. The workflow authorizes no deploy, credential,
production/live GitHub data, real-profile mutation, live Outcome advance, force-push, or branch
deletion.

## Completion gate

Every R1-R11 selector passes against exact merged and installed identities; the durable evidence
bundle validates and is privacy-safe; teardown and fleet doctor are clean; code review has zero open
P0-P3 findings; `saga:qa` accepts without waiver; the acceptance PR merges; all four #579 children
close and reconcile on Operations; #579 closes; the outcome report is final; and the coordinator DAG
has no pending node or leaked worktree/resource.
