# Issue #393 Typed Second-Opinion Reconciliation Work Session

## Scope

Execute U1-U6 from the approved typed second-opinion reconciliation plan on the
operator-confirmed `team-execution` backend. It records implementation, review, validation, and the
authorized #393 PR/CI/merge closeout; outcome coordination and outcome receipt updates remain owned by
the parent coordinator.

## Team Execution Evidence

- Backend: `team-execution`
- Run: `issue-393-typed-second-opinion-reconciliation`
- State: `.claude/team-execution/validators/` (git-ignored)
- Worker schedule: dependency-serial resident workers because the approved units overlap shared Saga
  files; later segments remain blocked until their dependencies commit.
- U1 worker: `worker-reconcile-core`, resolved effort `high`, Agent-path effort rider reconciled with
  no tiering drift.
- U1 manifest: `worker-reconcile-core-U1` in the `issue-393` manifest store, disposition
  `ran-as-requested`.
- U2 worker: `worker-intent-contract`, resolved effort `high`, Agent-path effort rider reconciled with
  no tiering drift.
- U2 manifest: `worker-intent-contract-U2` in the `issue-393` manifest store, disposition
  `ran-as-requested`.
- U3 worker: `worker-manifest-signal`, resolved effort `high`, Agent-path effort rider reconciled
  with no tiering drift.
- U3 manifest: `worker-manifest-signal-U3` in the `issue-393` manifest store, disposition
  `ran-as-requested`.
- U4 worker: `worker-panel-foreman`, resolved effort `high`, Agent-path effort rider reconciled with
  no tiering drift.
- U4 manifest: `worker-panel-foreman-U4` in the `issue-393` manifest store, disposition
  `ran-as-requested`.
- U5 worker: `worker-retro-reader`, resolved effort `high`, Agent-path effort rider reconciled with no
  tiering drift.
- U5 manifest: `worker-retro-reader-U5` in the `issue-393` manifest store, disposition
  `ran-as-requested`.
- U6 worker: `worker-release-closure`, resolved effort `medium`, Agent-path effort rider reconciled
  with no tiering drift.
- U6 manifest: `worker-release-closure-U6` in the `issue-393` manifest store, disposition
  `ran-as-requested`.

## Completed Work

### U1: Typed reconciliation registry and ledger writer

- Added immutable reconciliation recipes, typed results/items, source-finding accounting, canonical
  result hashing, and strict reconciliation-fact read/write validation.
- Extended `run_fact.v1` with the closed `reconciliation` fact kind.
- Added reconciliation completeness as a prerequisite at `engine_dispatch.satisfy_gate()` without
  relaxing the existing Claude verification, observer, disposition, claim, or advisory-role refusals.
- Added happy-path, edge, failure, chain-integrity, and gate-integration tests.

Checks:

- `uv run pytest tests/test_reconcile.py tests/test_run_ledger.py tests/test_saga_engine_dispatch.py -q`
  - 89 passed
- Narrow Ruff over U1 implementation and tests
  - passed
- `uv run mypy plugins/saga/scripts/reconcile.py --follow-imports=skip`
  - passed
- `git diff --check`
  - passed

### U2: Canonical divergence intent and plan-time tier contract

- Added `divergence` to the fleet-core-owned canonical intent vocabulary.
- Added the `opus / high` divergence policy and regenerated the plan skill's tier table from the
  renderer.
- Preserved omitted-intent `offload` behavior, selector XOR validation, plain-Claude serialization,
  and upgrade-only segment intent ordering.
- Added execution-spec, renderer, resolver, team/workflow emitter, and chaperone-economics coverage.

Checks:

- Focused U2 pytest matrix
  - 338 passed
- Narrow Ruff over U2 implementation and tests
  - passed
- `git diff --check`
  - passed

### U3: Rejected-offload disposition and manifest evidence wiring

- Added the `rejected-offload` disposition with a mandatory normalized non-empty note.
- Extended the single manifest-builder precedence while preserving fallback, substitution,
  delegation-integrity, unproven, proof-integrity, and requested-result ordering.
- Projected rejection notes into typed dropped reconciliation items and explicit advisory
  reviewer/validator evidence.
- Preserved the structural rule that rejected, panel, or other advisory evidence cannot satisfy a
  gate.
- Updated the worker-manifest and external-engine chaperone contracts.

Checks:

- Focused U3 pytest matrix
  - 108 passed
- Targeted Ruff format and lint
  - passed
- `git diff --check`
  - passed

### U4: Bounded advisory-jury panel and foreman reconciliation

- Added a separate `AdvisoryPanelRequest` contract and `PANEL_N_CAP = 7`.
- Validated normalized role names, advisory/Claude-foreman role posture, zero membership, cap
  overflow, and all-member availability before the first dispatch.
- Reused `resolve_role()` and `panel_halt()` while preserving the existing single-resolution panel
  role policy.
- Deduplicated identical non-empty member evidence, retained explicit per-member empty evidence, and
  required an exact typed Claude-foreman reconciliation before ledger append.
- Persisted only typed reconcile/apply facts; raw member output remains transient and panel evidence
  remains structurally non-gating.

Checks:

- Focused U4 pytest matrix
  - 249 passed
- Repository Ruff and targeted Ruff rerun
  - passed
- `git diff --check`
  - passed

### U5: Read-only retro proposal view

- Added a chain-verified, reconciliation-schema-validated derive-on-read proposal view.
- Deduplicated reconcile/apply facts by stable reconciliation identity while retaining action and
  ledger-hash evidence.
- Emitted explicit `no-proposal` output for an empty ledger and `approval_required: true` for every
  recipe-review proposal.
- Preserved the torn-tail tolerance and made non-trailing corruption, chain failure, and invalid
  reconciliation records visible failures.
- Documented `/retro`'s terminal, advisory, propose-diff-and-wait boundary.

Checks:

- Focused U5 pytest matrix
  - 25 passed
- Targeted Ruff format and lint
  - passed
- Focused mypy with skipped imports
  - passed
- `git diff --check`
  - passed

### U6: Documentation, decision record, and release closure

- Documented typed reconciliation facts, rejected-offload evidence, three-intent recipes,
  `PANEL_N_CAP`, and read-only retro proposals across the run-fact and Team Execution contracts.
- Recorded the binding intent-to-recipe decision, external-engine authority boundary, approval-only
  learning rule, and fourth-intent revisit condition in the engineering journal.
- Bumped fleet-core to `0.8.4`, Saga to `0.75.17`, and Team Execution to `2.14.3`, with synchronized
  changelogs and marketplace metadata.
- Updated version drift guard tests for the released contracts.

Checks:

- Full focused reconciliation matrix
  - 485 passed
- Release/package matrix
  - 71 passed
- Marketplace sync check
  - passed
- Release-surface parity
  - passed
- `git diff --check`
  - passed

## Team Execution Review Cycle 1

The required panel reviewed the same verified epoch-1 full-diff pointer in two capacity-bounded
waves (three reviewers, then two). Consensus was not reached:

| Reviewer | Score | Verdict |
| --- | ---: | --- |
| Devil's Advocate | 7.1 | needs revision |
| Security | 7.0 | needs revision |
| Architecture | 8.0 | needs revision |
| Testing | 7.1 | needs revision |
| Clarity | 7.1 | needs revision |

### Core remediation

- Bound reconciliation to immutable dispatch execution identity, canonical intent, evidence digest,
  and source-finding identities; rejected replay, mismatch, and empty-result bypasses before existing
  authority checks.
- Preserved rejected results under their canonical intent and closed surplus recipe definitions.
- Replaced raw-result ledger persistence with a bounded structural projection; rationales and engine
  prose remain outside the JSONL record, and ledger/lock files are mode `0600`.
- Added one-lock verified snapshot append semantics and enforced `reconcile` then at most one `apply`.
- Restored all legacy gate suites to their original assertion paths.

Checks:

- Focused core and legacy gate matrix
  - 218 passed
- Direct `reconcile.py` branch coverage
  - 94%
- Targeted Ruff and scoped mypy
  - passed
- `git diff --check`
  - passed

### Panel remediation

- Centralized panel name, cap, member-count, advisory-verdict, and Claude-foreman policy in the
  lower-level engine registry and removed the resolver's dependency on execution-spec parsing.
- Front-loaded canonical intent and normalized execution metadata validation before any role resolve
  or preflight.
- Added fail-closed `64 KiB` per-member and `256 KiB` cumulative UTF-8 panel output caps.
- Added zero-preflight, no-foreman, no-fact, runtime-halt, exception, and byte-overflow regressions.

Checks:

- Focused panel/spec/registry/resolver/dispatch/reconcile matrix
  - 356 passed
- Repository Ruff
  - passed
- `git diff --check`
  - passed

### Documentation and release-contract remediation

- Replaced stale one-argument gate guidance with the canonical bound reconciliation call and its
  complete readiness, replay, Claude, observer, manifest, role, disposition, proof, liveness, and
  claim refusals.
- Added the normal three-intent chaperone reconciliation sequence and clarified canonical intent
  retention for rejected offloads and transient raw panel output.
- Aligned run-fact, worker-manifest, journal, and existing changelog entries with the bounded
  structural projection, one-call transition semantics, `0600` lock custody, shared lower-level panel
  policy, and UTF-8 byte caps.
- Restored Completed Work chronology to U1 through U6 while preserving the review and remediation
  evidence after the implementation record.

Checks:

- Saga/Team Execution documentation and package matrix
  - 85 passed
- Release guard test matrix
  - 26 passed
- Marketplace sync, release parity, and diff-aware release guard
  - passed
- `git diff --check`
  - passed

## Team Execution Review Cycle 2

Cycle 2 stopped after the first three-reviewer wave found blocking issues. Testing and Clarity were
not run at epoch 2; they are recorded explicitly rather than treated as omitted or passing. Consensus
was not reached or claimed.

| Reviewer | Score | Verdict |
| --- | ---: | --- |
| Devil's Advocate | 8.3 | needs revision |
| Security | 7.8 | needs revision |
| Architecture | 8.4 | needs revision |
| Testing | — | not run - cycle stopped on blocking wave-1 findings |
| Clarity | — | not run - cycle stopped on blocking wave-1 findings |

The blocking findings reopened remediation for typed per-finding evidence, non-mutating torn-tail
reads, rejected-note custody, and exact panel binding.

### Core remediation

- Added immutable ordered `SourceFinding` records with content-derived IDs and digests.
- Required typed runner finding envelopes for `second-opinion` and `divergence`; retained the
  explicitly opaque singleton form only for `offload`.
- Proved a two-finding response cannot pass until both findings are explicitly adjudicated.
- Made ordinary ledger snapshots non-healing and byte-preserving; torn-tail repair now occurs only
  under the locked append path.
- Capped rejected summaries at 1024 UTF-8 bytes, derived all rejection bindings from supplied
  evidence, removed the default intent for evidence-less construction, and protected manifest files
  with mode `0600`.

Checks:

- Focused reconciliation, dispatch, manifest, ledger, retro, and legacy gate matrix
  - 293 passed
- Targeted Ruff and scoped mypy
  - passed
- `git diff --check`
  - passed

### Panel remediation

- Bound foreman results to a canonical digest of the ordered gathered panel evidence.
- Required exact ordered source finding IDs rather than set equality.
- Added shared foreman-result construction plus reordered-ID and wrong-digest no-append regressions.

Checks:

- Focused panel/spec/resolver/dispatch/reconcile matrix
  - 320 passed
- Repository Ruff
  - passed
- `git diff --check`
  - passed

### Documentation alignment

- Aligned Saga and Team Execution contracts with immutable ordered `SourceFinding` envelopes,
  per-content ordinal IDs/digests, exact multi-finding coverage, and the offload-only opaque fallback.
- Documented non-healing ordinary snapshots, append-only repair under lock, evidence-bound 1024-byte
  rejection summaries, and final manifest mode `0600`.
- Bound the documented panel foreman result to both exact ordered gathered IDs and the canonical
  gathered-evidence digest; updated the existing release/journal surfaces without a version bump.

Checks:

- Saga/Team Execution documentation and package matrix
  - 85 passed
- Release guard test matrix
  - 26 passed
- Marketplace sync, release parity, and diff-aware release guard
  - passed
- `git diff --check`
  - passed

## Team Execution Review Epoch 3

Epoch 3 compared the dereferenced epoch-2 review tree
`b5acc70c61cbc5101f22b5d4f031845451b888c9` through tree
`bc3636852ca75bd5bb058170aee5defb178817ef` (`a3a7da9`). The original resident reviewer handles
were unavailable after the session restore, so the same three role identities and rubrics were
re-engaged; all found actionable blockers. Testing and Clarity were deliberately held rather than
counted as passing once the first wave reopened remediation.

| Reviewer | Score | Verdict |
| --- | ---: | --- |
| Devil's Advocate | 7.8 | needs revision |
| Security | 8.6 | needs revision |
| Architecture | 8.2 | needs revision |
| Testing | — | not run - first-wave blockers |
| Clarity | — | not run - first-wave blockers |

### Epoch-3 remediation

- Retained each typed finding's bounded content only in memory, validated its ID/digest, and capped
  runner envelopes before construction.
- Required review-intent raw output to exactly match the canonical ordered findings envelope, so an
  unlisted net-new finding cannot be hidden in a summary.
- Flattened every typed panel member finding into an individually accountable foreman obligation,
  including repeated content at distinct ordinals.
- Required the original `AdvisoryEvidence` and matching rejected note for rejected-offload projection;
  separated bounded `tripwire_note` operational text from the evidence-bound rejection summary.
- Made absent and torn-tail ledger reads non-mutating: read locks are shared only when already present;
  append remains the sole repair path.

Checks:

- Focused reconciliation, dispatch, manifest, ledger, retro, bridge, and legacy gate matrix
  - 278 passed
- `git diff --check`
  - passed

## Bounded Saga Code Review and Operator-Gated Remediation

Team Execution stopped at its three-remediation-loop cap. The operator then authorized one bounded
inline Saga code review with no Team Execution, external engine, or fixer dispatch and a hard stop on
any surviving P0-P3. That review wrote
`docs/code-reviews/2026-07-09-issue-393-typed-second-opinion-reconciliation-code-review.md` and
validated one P1: dispatch replaced raw review output with declared findings without first requiring
them to match, allowing an undeclared finding to disappear before reconciliation.

After the required operator approval, the focused remediation:

- requires every successful `second-opinion` and `divergence` output to exactly equal the canonical
  ordered declared-findings envelope;
- retains the existing halted-run empty-evidence contract and requires an explicit typed findings
  field even for zero-finding successful reviews;
- replaces the unsafe summary-independence test with mismatch refusal for both review intents; and
- proves a panel mismatch reaches neither its Claude foreman nor the run-fact ledger.

Checks:

- Complete dispatch suite
  - 117 passed
- Focused reconciliation, ledger, dispatch, manifest, retro, bridge, execution-spec, and resolver
  matrix
  - 394 passed
- Atomic-ledger promotion compatibility suite
  - 21 passed after moving the stale race fixture from `read_facts()` to the new `read_snapshot()`
    single source; production behavior was unchanged
- Full repository suite under the locked Python 3.12 environment
  - 3021 passed, 1 skipped, 80% coverage
- Repository Ruff, configured mypy, release-surface parity, changelog lint, and `git diff --check`
  - passed
- Direct engine-dispatch mypy
  - reports only two unchanged `no-any-return` findings at lines 808 and 845
- Bandit
  - the repository-wide unconfigured scan has an existing 650-finding baseline; the changed
    production file adds no flagged pattern and retains one pre-existing low-severity `assert` finding

## Next Step

Run final deterministic repository and release gates, commit the bounded remediation and review
artifact, then use the standing authorization for PR, CI, merge, issue/board closure, and outcome
receipt recording. Pause before issue #394.
