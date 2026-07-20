---
title: Lease-safe runtime continuity - cross-runtime acceptance proof
type: test
status: ready-to-freeze
date: 2026-07-15
deepened: 2026-07-20
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

**2026-07-20 refresh — bound inputs, pre-acceptance units, and AFK operating mode.** All hard
dependencies are merged and live-verified: `sub-353` (`cf15a09f`), the Codex substrate (#33,
`3723a818`), and the Codex parity port (#34, `d29e75fd`) shipped, leaving this leaf as the sole
remaining node. The operator (Jeff) directed in-session on 2026-07-20: "ok lets refresh the plan
and assume I will be afk for this frontier." This refresh therefore records the delegated authority
for unattended execution: Claude-direct cc-workflow inline ceremony (the vehicle approved for #604,
#33, and #34); the standing 2026-07-18 merge pre-approval ("for the rest of this outcome") covers
every merge in this frontier; doc-review of this refresh with all findings repaired substitutes for
the interactive plan-review touchpoint; and the Workflow Structure anchor is adopted under the same
delegation. Execution pages the operator only by halting on a stop condition and leaving a durable
report — it never widens authority to keep moving. Ceremony anchor:
`4b21df73f98030f97b5f770adddaf33e14048a07af8221005f6d5e3699e1cb0f` over 3754 bytes from the
`## Workflow Structure` heading to the `## Completion gate` heading, exclusive (the span includes
the operating contract).

## Hard inputs and authority

- Outcome specification
  `docs/outcomes/lease-safe-runtime-continuity/outcome-spec.json`, node
  `cross-runtime-acceptance`; hard dependencies are `sub-353` and `codex-parity`.
- Verified baseline pins (live-verified 2026-07-20): Claude `infiquetra-claude-plugins`
  `origin/main` = `cf15a09f` (#353 squash; carries #604 `97d2fb15` and #358 `30bde209`) with saga
  `0.104.0` and fleet-core `0.15.0`; Codex `infiquetra-codex-plugins` `origin/main` = `d29e75fd`
  (#34 squash) with saga `0.77.0+codex.20260720023112` and fleet-core
  `0.9.0+codex.20260719174556`. The PA units below advance both pins; the harness receives the
  exact post-PA merge SHAs and versions on invocation and re-verifies them itself (R1).
- Claude compatibility schema and fixture digest plus both Codex port-manifest/cutover digests.
- Runtime-neutral broker-root resolution contract and the redacted canonical-root digest reported by
  both installed runtimes.
- Completed #353 command/report schema and exact merged SHA; transitively merged #351/#355/#357/#358.
- Deterministic GitHub fixtures. No live issue, board, PR, credential, or production-data mutation is
  part of acceptance.
- One acceptance branch/PR in `infiquetra-claude-plugins`; during acceptance (U1-U5) Codex remains
  read-only input at its exact merged post-PA revision. PA-2 is the one pre-acceptance Codex PR and
  merges before any pin is taken.

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
- **KTD7 - deferred-work discharge is upstream-first and precedes pinning (2026-07-20).** Items
  touching shared or byte-faithful surfaces are fixed in `infiquetra-claude-plugins` first and
  re-ported, never patched codex-only; both PA PRs merge before the harness pins its inputs, so
  acceptance verifies final released behavior. The acceptance PR itself still contains no
  production fix — KTD4 stands.
- **KTD8 - lease-seam activation restores wiring parity (discharges the #34 plan's "KTD6"
  deferral).** Claude's shipped `outcome.py` already passes
  `lease_authority=outcome_dispatcher.default_lease_authority()` at both dispatcher call sites
  (`:2422`/`:2478` at `cf15a09f`); the codex port withheld it by operator decision 2026-07-19.
  PA-2 wires the two codex call sites identically — activation is parity restoration, not new
  design.
- **KTD9 - AFK operating mode (operator directive 2026-07-20).** The directive (verbatim in the
  Summary) delegates this frontier's interactive gates: doc-review of this refresh with all
  findings repaired replaces interactive plan review; the ceremony anchor is adopted under the
  same delegation; merges ride the standing 2026-07-18 pre-approval. Anything outside this
  recorded authority is a HALT with a durable report, never a judgment call.

## Pre-acceptance production units

The #34 code-review and QA gates dispositioned five deferred items; three require production
changes, and the operator's 2026-07-19 seam deferral placed dispatcher lease activation in this
leaf. Both PA units below are discharged and merged before the harness pins its inputs (KTD7).
Right-sizing: each PA unit ships under the programmatic `saga:code-review` gate (four always-on
lenses plus independent validators) and its repo's full local battery — not the six-lens
plan-anchored ceremony, which is reserved for the harness implementation (U1-U5). Rationale: both
are remediation-class changes with narrow, enumerated diffs — the same class as #34's `39a9ed4`
remediation commit, which shipped under the review gate alone. Each unit gets a small tracked
issue (mission-control) so its PR closes it.

### PA-1. Claude upstream hardening (`infiquetra-claude-plugins`)

At the `cf15a09f` sites:

- Stale `export`/`import` `--help` strings still describing the retired bundle flow
  (`plugins/saga/scripts/outcome.py:2281/:2284`): reword to live semantics (`export` is a
  deprecated read-only alias of `discover`; `import` always refuses with migration guidance).
- Unreachable success-print after the unconditional `import_bundle` refusal
  (`outcome.py:2624-2627`): remove the dead success path; the refusal receipt is the only output.
- Protected handoff-store directory created at default umask (`outcome_compat.py` `_write_once`,
  line 1135): create with `0o700` and verify, mirroring the `audit_store` pattern; sealed records
  stay `0o600`.
- `fleet_commons/audit_store.py` ancestor hardening: refuse a symlinked store root and any
  world-writable existing ancestor below the user's home; typed refusal, no silent fallback.

Behavior tests for each; release surfaces in the same PR (saga and fleet-core version rungs,
changelogs, marketplace registry, guard floors per `{#release-event-guard-floor-604}` — floors,
never current-version pins). Full battery, programmatic code review, PR, merge under the standing
approval. The merge SHA becomes the Claude acceptance pin and the new frozen port source.

### PA-2. Codex seam activation and re-port (`infiquetra-codex-plugins`)

- Dispatcher lease activation: wire `lease_authority=outcome_dispatcher.default_lease_authority()`
  at both `make_dispatcher` call sites (`plugins/saga/scripts/outcome.py:2011/:2129` at
  `d29e75fd`), matching Claude's shipped wiring (KTD8); replace
  `test_dispatcher_lease_seam_stays_dormant_ktd6` with an activation pin asserting the authority
  is threaded and a real lease is taken and released on the dispatch path.
- Re-port PA-1: refresh `outcome_compat.py` byte-faithful to the PA-1 merge SHA and re-prove the
  divergence is exactly the `RUNTIME_LABEL` pair; re-port the CLI `--help`/dead-print fixes into
  the grafted arms (`outcome.py:1934/:1937/:2209`); port the `audit_store` ancestor hardening;
  update the port manifest's frozen-source range (preserve `indent=2, sort_keys=True`).
- Release surfaces: saga and fleet-core `+codex` version rungs, changelogs, legacy-token inventory
  rebuild (`build_legacy_workflow_inventory.py --write` after every inventoried-file edit),
  `validate_codex_plugins` green from a worktree-free primary checkout.
- Full battery, programmatic code review, PR, merge. The merge SHA becomes the Codex acceptance
  pin. Codex CLI invocations run with `env -u OPENAI_API_KEY` (the env var is a literal stub).

## Implementation units

U1 begins only after PA-1 and PA-2 are merged and R1 re-verifies the advanced pins.

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
tests/test_cross_runtime_acceptance.py
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

PA units run their own repo's full battery before their PRs (Claude: pytest, ruff check and
format --check, mypy, bandit, release-surface parity, marketplace sync check; Codex:
`PYTHONPATH=. uv run pytest -q -p no:cacheprovider`, ruff check, `validate_codex_plugins` from a
worktree-free primary). The harness suite name is deliberately distinct from the existing
`tests/test_outcome_cross_runtime_contract.py` (#604's contract suite).

```bash
uv run pytest tests/test_cross_runtime_acceptance.py -v
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
- (AFK) A required authority is outside this plan's recorded delegation, an anchor or lens receipt
  cannot be satisfied, or a gate demands operator judgment — HALT, write the durable report, and
  wait; never proceed by widening authority.

## Workflow Structure

Vehicle: Claude-direct cc-workflow inline ceremony — the same form approved for #604 (anchor
`214431cf`), #33 (`bc038d41`), and #34 (`c76ef1ee`). Root (the session) is the only writer; every
reviewer and validator lens is one read-only `agent()` call spawned as `saga:readonly-verifier`
with `isolation: "worktree"`. Reviewer lenses run at opus/high; validator lenses run at
sonnet/medium. Fan-out routes through a bounded pool of 3 (the hard concurrency cap for
above-Haiku agents); if the Workflow tool is unavailable the ceremony HALTS and pages rather than
degrading to inline or unsandboxed review.

| step_id | depends_on | role | tier | charter |
|---|---|---|---|---|
| implement | - | root | - | U1-U5 implementation, fixtures, evidence schema; root-only mutation. |
| review-devils | implement | devils-advocate-reviewer | opus/high | Attack the harness's claim to prove R1-R10: where does a passing bundle overstate what was tested? Hunt accidental serialization masquerading as overlap (KTD2), false cross-clone equality (KTD3), and fixture shortcuts that make negative paths unreachable. |
| review-security | implement | security-reviewer | opus/high | Privacy allowlist and evidence redaction (R10); no default-profile, credential, or transcript reads (R2); handoff-reference containment (KTD5); tamper/replay/skew rejections mutation-free (R4/R7); subprocess env hygiene including the `OPENAI_API_KEY` stub. |
| review-architecture | implement | architecture-reviewer | opus/high | Harness/production boundary (KTD4 — no production repair in the acceptance PR), pin-verification layering (R1), clone A/B topology fidelity, teardown idempotency structure (R9), evidence-schema closure. |
| review-testing | implement | testing-reviewer | opus/high | Scenario-matrix coverage against R3-R9 (both directions, both orderings, crash windows), oracle strength (typed errors and exact counts, never substrings), fixture determinism, negative-path completeness. |
| validate-concurrency | implement | concurrency-tester | sonnet/medium | Execute the two-process barrier matrix; verify monotonic overlap receipts, write-once backend refusal, exactly-one settlement across orderings and crash injections (R5). |
| validate-event-flow | implement | event-flow-tester | sonnet/medium | Trace dispatch -> settlement -> acknowledgement chains; verify Codex-native `outcome.dispatch.v2` plus `ack_kind=launched` when Codex launches and its absence when Claude launches (R6); settlement visibility cross-clone. |
| validate-scenarios | implement | scenario-tester | sonnet/medium | Run the full acceptance matrix end-to-end from the pinned installed profiles; validate the evidence bundle against its schema, artifact digests, and privacy allowlist (R10). |
| integrate | all lenses | root | - | Fix all P0-P3, re-adjudicate with originating lenses to convergence (three-cycle tripwire), full gate, QA routing, evidence-bundle commit. |

## Workflow operating contract

Root is the only writer and owns commands, integration, Git, PR/merge, issue and board
reconciliation, and QA routing. Reviewer and validator lenses are read-only, spawned as
`saga:readonly-verifier` with worktree isolation, and authorize no external mutation; a lens that
cannot run as specified (tool unavailable, receipt mismatch) is rerun fresh or the ceremony HALTS —
never silently downgraded. Root fixes all P0-P3 findings and re-adjudicates each with its
originating lens, stopping after three unsuccessful remediation cycles on the same finding (halt
plus durable report). The workflow authorizes no deploy, credential access, production or live
GitHub data mutation, real-profile mutation, live Outcome advance, force-push, or branch deletion.

## Completion gate

PA-1 and PA-2 are merged with their gates green and their tracked issues closed; every R1-R11
selector passes against exact merged and installed identities; the durable evidence bundle
validates and is privacy-safe; teardown and fleet doctor are clean; code review has zero open
P0-P3 findings; `saga:qa` accepts without waiver; the acceptance PR merges; all four #579 children
close and reconcile on Operations; #579 closes; the outcome report is final; the coordinator DAG
has no pending node or leaked worktree/resource; and the AFK writebacks land (final outcome report,
engineering-journal entries, memory update, and the closing report to the operator).
