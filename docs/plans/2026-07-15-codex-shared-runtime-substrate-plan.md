---
title: Lease-safe runtime continuity - Codex shared runtime substrate
type: feat
status: ready-to-freeze
date: 2026-07-15
updated: 2026-07-19
origin: docs/outcomes/lease-safe-runtime-continuity/issue-sources/codex-shared-runtime-substrate.md
issue: infiquetra/infiquetra-codex-plugins#33
parent: infiquetra/infiquetra-claude-plugins#579
target_repository: infiquetra/infiquetra-codex-plugins
---

# Lease-safe runtime continuity - Codex shared runtime substrate

## Summary

After Claude issues #351, #356, and #355 merge, port their runtime-neutral dispatch-settlement,
lease-broker, resource-head, fence, and guarded-write behavior into `infiquetra-codex-plugins` as one
staged Claude-to-Codex proof port. `fleet-core` owns the shared broker and resource primitives; Saga
owns the Outcome adapter and settlement integration. The port must preserve Codex's existing
`outcome.dispatch.v2` intent/acknowledgement contract: `ack_kind=launched` is the only acknowledgement
that proves dispatch, `handed-off` remains non-launched, and legacy records remain
`legacy-unverified` unless reconciled by the existing migration contract.

This is the prerequisite substrate for the later Codex cross-runtime protocol issue. It deliberately
does not port Claude hooks, Workflow/Team Execution orchestration, liveness/teardown/doctor behavior,
or the Outcome discovery and handoff schemas.

The current Codex `main` worktree contains unrelated user state. Implementation therefore starts
only after approval in a fresh isolated worktree from a freshly fetched `origin/main`; it never
touches the existing dirty paths. The plan is decision-complete now but remains `ready-to-freeze`
until the upstream merge SHAs and the Codex execution base can be recorded in a fresh version-3 port
manifest and its classification gate passes.

## Authority and prerequisites

- **Outcome specification:**
  `docs/outcomes/lease-safe-runtime-continuity/outcome-spec.json`, node `codex-substrate`; its hard
  dependency is `sub-355`, which transitively carries #351 and #356.
- **Maintained authority:** `AUTH-CODEX-ADAPTER`. Merged Claude behavior is lineage and a frozen
  implementation input; after cutover, Codex source and tests are authoritative for the adapter.
- **Shared-policy owner:** Codex `fleet-core` owns the runtime-neutral broker/resource primitives;
  Saga shims and adapters are synchronized consumers, not competing implementations.
- **Hard source inputs:** exact merged commits for Claude #351, #356, and #355, including their
  schemas, tests, release versions, and journal decisions.
- **Hard target input:** fresh Codex `origin/main`, not the currently dirty primary worktree. The
  planning snapshot was `739fb34e27f2e045e28cf5d420bbc2fc004115a0`; execution records the then-current SHA separately.
- **Mandatory procedure:** `docs/portability/claude-to-codex-plugin-port-runbook.md`, version 3.
- **Downstream:** the Codex protocol-parity issue cannot start until this PR is merged, installed in
  isolation, fresh-session proven, and rollback proven.

If source merges alter the planned ownership boundary, dispatch identity, broker root, or resource
guard, refresh this plan and doc-review before behavior edits. Unknown upstream rows, missing refs,
or Codex preservation drift fail closed under the runbook stop rules.

## Current-state invariants to preserve

1. Codex emits `outcome.dispatch.v2` intent plus protected acknowledgement records.
2. Only a valid `ack_kind=launched` acknowledgement yields `state=dispatched`.
3. `ack_kind=handed-off` remains `state=handed-off`; it is not launch proof.
4. Source-only/legacy commits do not become dispatch authority and remain `legacy-unverified` until
   the existing migration path proves them.
5. Protected launch receipts remain in the current Codex protected-state boundary. They are not
   moved into the fleet broker or made portable.
6. Installed caches are proof/readback only, never source and never a shared state root.

## Requirements

R1. **Freeze an exhaustive port contract before behavior edits.** Record historical plan base,
approved execution base, full Codex preservation drift, exact Claude base/target refs, exact
pathspecs, runbook digest/version, sanitized capability snapshot, expected row counts, and source
reachability. Generate one new JSON manifest under `docs/portability/ports/` and its generated
classification. Classify every source and Codex-drift row; pass `port_contract.py validate --stage
classification` before changing source-derived behavior. First copy this coordinator plan and its
review into the isolated target branch, bind it to `infiquetra/infiquetra-codex-plugins#33`, and
run a mandatory focused plan/doc-review refresh against the frozen refs; bind those target-repo bytes
in the port manifest.

R2. **Use one runtime-neutral fleet-state root.** Resolution order is an explicitly safe absolute
`INFIQUETRA_FLEET_STATE_DIR`, then safe absolute `$XDG_STATE_HOME/infiquetra/fleet-leases`, then
`~/.local/state/infiquetra/fleet-leases`. Reject traversal, symlink escape, non-directory components,
unsafe ownership/permissions, relative environment values, and ambiguous roots. Never default via
`~/.claude`, `~/.codex`, installed cache roots, or `PLUGIN_DATA`. Both runtimes must compare the same
redacted canonical-root digest before admission.

R3. **Port broker and resource-head behavior behind Fleet Core.** Adapt the exact merged lease
schema, monotonic epoch/fencing sequence, concurrency-slot semantics, TTL/renew/reclaim rules,
dead-owner proof, closing fence, persistent resource head, atomic/permission-safe writes, and bounded
corruption handling. No wall-clock-only takeover and no second capacity vocabulary are allowed.

R4. **Port guarded-write semantics without Claude host primitives.** Adapt the #355 resource guard
so every protected write/commit checks current resource identity, owner, epoch/fence, non-closing
state, and successor rules immediately before effect. Claude hooks, hook JSON, TeamCreate,
SendMessage, Workflow, and team teardown are classified `reject` or `defer`, never direct-ported.

R5. **Port shared dispatch settlement and preserve Codex acknowledgement.** Adapt #351 manifest,
spawn-attempt, settlement, casualty, dead-letter, and idempotency identities to Codex Saga. The
adapter binds the shared logical dispatch identity to `outcome.dispatch.v2` intent and protected
acknowledgement. A shared settlement may explain/re-drive an attempt, but cannot manufacture a
Codex launch acknowledgement or reinterpret `handed-off` as launched.

R6. **Make stale writers fail before effect.** Every Outcome dispatch/settlement write presents the
current broker token and fence at the final side-effect seam. Expired, superseded, wrong-root,
wrong-resource, wrong-owner, closing, corrupted, or unverifiable authority HALTs without dispatch,
completion, board, GitHub, spec, receipt, or settlement mutation.

R7. **Prove migration and concurrency at production-shaped boundaries.** Deterministic two-process
tests race acquire, renew, reclaim, guarded commit, settlement recovery, and dispatch. A write-once
fake backend plus exact fact counts prove at most one effect. Existing dispatch-migration tests must
continue to pin launched/handed-off/legacy behavior.

R8. **Release only after full port cutover evidence.** Update `fleet-core` and Saga Codex manifests,
changelogs, portability notes/matrix, generated classification, validation inventory, tests, and
engineering journal in one release unit after behavior passes. Calculate target versions from the
fresh execution base. Pass focused/full checks, repository validation, classification/unit/cutover
gates, clean isolated install, separately authenticated fresh-session readback, and exact rollback.

## Key decisions

- **KTD1 - shared root is runtime-neutral, protected receipts are not.** The broker must be visible to
  both runtimes; Codex launch receipts retain their protected Codex boundary and are correlated by
  identity rather than copied.
- **KTD2 - settlement does not erase native acknowledgement.** Shared run facts are cross-runtime
  idempotency truth; only Codex's protected launched ack satisfies Codex dispatch state.
- **KTD3 - port behavior, not host shape.** Pure schemas/algorithms may direct-port. Paths, hooks,
  skills, docs, manifests, and adapters require Codex adaptation or explicit reject/defer rows.
- **KTD4 - one broker implementation.** Fleet Core owns it; Saga consumes it through the existing
  resolution boundary. No Saga-local broker or home-directory fallback is permitted.
- **KTD5 - staged evidence is part of the feature.** A passing test suite without classification,
  install, fresh-session, cutover, and rollback evidence is not release-ready.

## Implementation units

### U1. Freeze refs, capability truth, and classification

Create the isolated worktree; copy and refresh the plan/review as R1 requires; capture target dirt and
overlap; fetch both repos read-only; freeze the
source base/target and exact pathspec inventory; capture sanitized active-session facts; initialize
the version-3 port manifest; enumerate all source and Codex-drift rows; classify each as
`direct-port`, `codex-adapt`, `preserve`, `defer`, or `reject`; and pass the classification gate.
No production behavior file changes before this gate.

### U2. Fleet Core broker, resource head, and guard

Port/adapt the pure broker records, atomic store, root resolver, token/fence validation, renewal,
closing, reclaim, and resource guard into `plugins/fleet-core/scripts/fleet_commons/`. Add unit,
multiprocess, permission, symlink, unsafe-root, corrupt-record, clock/fence, and shared-root-digest
tests. Synchronize only the required shim surface into Saga and pass the unit manifest gate.

### U3. Saga settlement adapter with dispatch-v2 preservation

Adapt shared dispatch facts and settlement lookup/re-drive into Saga. Thread broker resource/fence and
shared attempt identity through Outcome dispatch immediately before the backend effect. Preserve the
existing intent/ack and protected launch receipt. Add tests for launched, handed-off,
legacy-unverified, crash windows, casualty/dead-letter, already-settled retry, root mismatch, stale
fence, and no-mutation rejection.

### U4. Conformance, migration, and authority-negative tests

Run the same neutral broker and settlement fixtures through Claude and Codex modules without host
paths. Use deterministic process barriers and a write-once backend to prove one effect. Assert no
`~/.claude`, `~/.codex`, `PLUGIN_DATA`, cache, credential, transcript, prompt, or raw child-output
material appears in shared records. Prove old Codex Outcome dispatch migrations still behave exactly
as before.

### U5. Release, installed proof, fresh session, and rollback

Update port manifest rows to verified with existing evidence, generate classification, update
portability/version/release surfaces once, run all gates, install into an isolated Codex home, seed
only documented non-secret migration state, start a fresh session, verify plugin discovery and
shared-root resolution, pass cutover, activate exactly one package identity, and test exact rollback.
Commit sanitized digests/results only.

## Expected target paths

```text
docs/portability/ports/<date>-lease-safe-substrate.json
docs/portability/classifications/<date>-lease-safe-substrate.md
docs/plans/<target-repo-copy-of-this-plan>.md
docs/reviews/<target-repo-doc-review>.md
docs/validation/codex-runtime-capability-snapshot.json
docs/validation/<port-id>/...
plugins/fleet-core/scripts/fleet_commons/<broker-and-resource-modules>.py
plugins/fleet-core/tests/<broker-and-resource-tests>.py
plugins/fleet-core/PORTABILITY.md
plugins/fleet-core/.codex-plugin/plugin.json
plugins/fleet-core/CHANGELOG.md
plugins/saga/scripts/<settlement-and-broker-adapters>.py
plugins/saga/scripts/outcome_dispatcher.py
plugins/saga/scripts/outcome_store.py
plugins/saga/PORTABILITY.md
plugins/saga/.codex-plugin/plugin.json
plugins/saga/CHANGELOG.md
tests/test_outcome_dispatch_migration.py
tests/<lease-settlement-conformance-tests>.py
docs/portability/matrix.md
docs/engineering-journal/DECISIONS.md
```

Exact names and row ownership come from the classified port manifest; this list is a write-set
boundary, not permission to import unrelated source files.

## Verification

```bash
python3 scripts/port_contract.py validate --manifest <manifest> --stage classification
python3 scripts/port_contract.py validate --manifest <manifest> --stage unit --unit U2
python3 scripts/port_contract.py validate --manifest <manifest> --stage unit --unit U3
python3 -m pytest plugins/fleet-core/tests -v
python3 -m pytest tests/test_outcome_dispatch_migration.py tests/test_outcome_dispatcher.py tests/test_outcome_store.py -v
python3 -m pytest
python3 scripts/validate_codex_plugins.py
python3 scripts/port_contract.py validate --manifest <manifest> --stage cutover
git diff --check
```

The exact isolated-install, fresh-session, and rollback commands are rendered from the classified
manifest and executed only after root confirms they contain no real-profile credential copy or
external mutation.

## Stop conditions

- Any frozen source/target ref, execution base, pathspec count, runbook digest, or preservation row
  changes after classification.
- The current dirty Codex primary worktree would be modified or any unrelated dirty path overlaps.
- Shared state resolves through a runtime home/cache/`PLUGIN_DATA`, roots diverge, or a path is unsafe.
- Shared settlement can mark Codex dispatched without a protected `ack_kind=launched` acknowledgement.
- `handed-off` becomes launched, or a legacy record becomes verified without the migration contract.
- A stale/closing/superseded writer can reach backend, spec, completion, board, GitHub, receipt, or
  fact mutation.
- A Claude host primitive is direct-ported or an unclassified source/Codex-drift row appears.
- Any classification/unit/cutover, install, fresh-session, rollback, repository, full-test, doc-review,
  or code-review gate fails or retains a P0-P3 finding.

## Workflow Structure

| step_id | depends_on | barrier | role_id | role_kind | independence | vehicle | agent_type | model | effort | isolation | mutation | required_evidence |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| implement | - | - | root | root | n/a | session-root | - | - | - | isolated-worktree | root-only | port-contract,authorized-diff,focused-tests |
| review-devils | implement | review | devils-advocate | agent-lens | separate-context | cc-workflow-agent | saga:readonly-verifier | opus | high | worktree | none | scored-review,findings |
| review-security | implement | review | security | agent-lens | separate-context | cc-workflow-agent | saga:readonly-verifier | opus | high | worktree | none | scored-review,findings |
| review-architecture | implement | review | architecture | agent-lens | separate-context | cc-workflow-agent | saga:readonly-verifier | opus | high | worktree | none | scored-review,findings |
| review-testing | implement | review | testing | agent-lens | separate-context | cc-workflow-agent | saga:readonly-verifier | opus | high | worktree | none | scored-review,test-gaps |
| validate-concurrency | implement | validate | concurrency | agent-lens | separate-context | cc-workflow-agent | saga:readonly-verifier | sonnet | medium | worktree | none | concurrency-matrix,command-results |
| validate-event-flow | implement | validate | event-flow | agent-lens | separate-context | cc-workflow-agent | saga:readonly-verifier | sonnet | medium | worktree | none | event-trace,command-results |
| integrate | review-devils,review-security,review-architecture,review-testing,validate-concurrency,validate-event-flow | - | root | root | n/a | session-root | - | - | - | isolated-worktree | root-only | fixed-findings,classification-unit-cutover,full-gate,install-fresh-session-rollback,git-receipt |

## Workflow Operating Contract

- Runtime: root is the operator's Claude Code session on the cc-workflow backend. Root owns
  implementation, Git, integration, PR creation, merge under the operator's standing outcome
  approval, issue closure, and board reconciliation. The authorized subject is this issue's
  infiquetra-codex-plugins paths (plugins/fleet-core, plugins/saga, docs/portability, tests) plus
  exact Codex release surfaces, executed in a fresh isolated worktree cut from freshly fetched
  origin/main — never the primary checkout. Root records the pre-existing Git baseline before
  `implement`; unrelated worktree paths are excluded.
- Lens dispatch: the six agent-lens rows execute as `agent()` calls inside one root-authored Claude
  Code Workflow script, each with exactly the agent_type, model, effort, and worktree-isolation
  cells above, routed through a bounded pool so total in-flight subagents never exceed 3. Each call
  embeds its lens charter below plus the diff and evidence scope. Spawn parameters are
  harness-recorded and root records per-lens receipts in the review artifacts; no cryptographic
  attestation is claimed. If the Workflow tool is unavailable, halt and page the operator — never
  silently downgrade to another dispatch path.
- `agent_type=saga:readonly-verifier` is the mandated read-only sandbox profile for review/verify
  spawns (Bash/Read/Grep/Glob in a disposable worktree, per
  `plugins/saga/references/sandbox-spawn-sites.md` in infiquetra-claude-plugins); per-call
  model/effort opts override the profile's default tier. Root audits the isolated worktree after
  every lens attempt and treats any unexplained diff as workflow-integrity failure.
- Lens charters: **devils-advocate** — challenge the port end to end: classification completeness
  (any Claude host primitive surviving as direct-port), runtime-neutral root-resolution divergence
  between the two runtimes, whether any fail-before-effect HALT edge is reachable only after a
  side effect, legacy-record resurrection (`handed-off` relabeled as launch proof), broker
  epoch/fence bypass under crash, retry, and supersession windows, and migration-contract
  false-proof paths; **security** — trust boundaries of the shared state root: path trust
  (symlink/traversal escapes into `~/.claude`, `~/.codex`, or installed caches), protected launch
  receipts staying inside the Codex protected boundary (correlated by identity, never copied),
  forged settlement records and fence spoofing, state-root permission hygiene, and redaction (no
  absolute paths, credentials, or transcripts in reports); **architecture** — consumption of the
  merged #351/#355/#356 contracts without wrapping or redefining their authority, the fleet-core
  (broker/resource primitives) versus saga (settlement adapter, dispatch effect seam) boundary,
  port manifest v3 and runbook version 3 conformance, fleet_commons module and shim coherence, and
  Codex release-surface coherence; **testing** — adequacy of the conformance, migration, and
  authority-negative matrices, deterministic two-process races over the write-once fake backend, a
  zero-mutation oracle for every HALT edge, canonical-root digest comparison coverage, and
  classification/unit/cutover gate evidence; **concurrency** (validator) — independently assess
  the single-effect proof from captured evidence: broker admission versus settlement
  interleavings, epoch supersession races, crash-window resumption, and exact effect/fact counts;
  **event-flow** (validator) — trace dispatch → manifest → spawn attempt → broker token/fence
  check → effect → settlement → acknowledgement end to end across the shared state root and the
  Codex protected boundary, including every HALT edge's proven non-mutation.
- Root fixes every P0-P3 finding and re-runs the affected lenses fresh. Three unsuccessful
  remediation cycles halt and page the operator. Any model, effort, lens, validator, or
  execution-class change requires a newly approved workflow candidate. The approval anchor is the
  SHA-256 of the exact `## Workflow Structure` and `## Workflow Operating Contract` section bytes,
  recorded in the work-session artifact.
- Git mutation, PR creation, merge, issue/board mutation, and completion remain root-only. No
  deployment, credential, production-data, cache-copy, live-Outcome-advance, real-profile-mutation,
  force-push, or branch-deletion action is authorized by this workflow.
- Workflow receipts, findings, command logs, workspace audits, PR URL, merge SHA, issue close, and
  board reconciliation are retained in the repo's review and work-session artifacts and on the
  issue/PR.

---

## Completion gate

The issue completes only when the fresh port manifest passes classification/unit/cutover; all
requirements and negative invariants pass; zero P0-P3 findings remain; the isolated install,
fresh-session readback, and exact rollback pass; one atomic Codex PR merges; the issue closes and its
Operations card is reconciled; and the merged SHA/version/manifest digest are handed to the Codex
protocol-parity issue.
