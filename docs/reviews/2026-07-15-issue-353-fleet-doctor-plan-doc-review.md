# Doc Review - Issue #353 independent fleet doctor plan

One-line verdict: **READY** - all P0-P3 findings were fixed in place; the capstone plan can drive
implementation after its upstream contracts merge and the operator approves its exact workflow.

## Review-result contract

- **Target:** `docs/plans/2026-07-15-issue-353-fleet-doctor-plan.md`
- **Reviewed revision:** uncommitted outcome worktree based on `a20cc3ce6d740a4891bddba71f7e8f2856620655`
- **Blocked:** no document-readiness blocker; implementation is dependency- and operator-gated
- **Classification:** issue-derived deep implementation plan
- **Rubrics:** all issue cores plus applicable context, sizing, and prerequisite extras
- **Linked:** `infiquetra/infiquetra-claude-plugins#353`, parent outcome
  `docs/outcomes/lease-safe-runtime-continuity/outcome-spec.json`
- **Review artifact:** this file

## Applied fixes

The review found ten actionable defects or stale assumptions and fixed all ten.

| ID | Priority | Status | Applied fix |
|---|---|---|---|
| D353-1 | P1 | fixed | Rebased the inputs on merged-outcome authority: #351 facts, #356 broker, #355 seals/orphan evidence, #357 liveness, and #358 teardown instead of the issue's pre-substrate paths. |
| D353-2 | P1 | fixed | Preserved the existing `/delegation-audit` surface and made doctor a strict cross-source tripwire rather than a duplicate tolerant single-store query. |
| D353-3 | P1 | fixed | Rejected `outcome_worktrees.read_registry()` and other tolerant/healing readers for runtime audit because malformed input can quarantine/mutate or collapse to empty; specified strict bounded raw readers. |
| D353-4 | P1 | fixed | Required an independent broker/Outcome/audit/bundle observation before classifying a spawn unledgered; a #351 pre-submit fact alone is now phantom/unsettled evidence, not proof of launch. |
| D353-5 | P1 | fixed | Restricted stale-worktree detection to canonical `.saga-worktrees/<outcome>/<subplot>` resources, excluding primary, current-cwd, shared-install, and unrelated developer worktrees. |
| D353-6 | P1 | fixed | Added exit 2 for corrupt, unsafe, changed, capped, unknown, or incomplete evidence so an inability to prove clean cannot return exit 0 or masquerade as a disease finding. |
| D353-7 | P2 | fixed | Removed the proposed production `--fixture` schema; tests create real temporary Git/common-dir/lease/audit roots and invoke production arguments. |
| D353-8 | P2 | fixed | Added explicit `--lease-store`, privacy redaction, owner/mode/symlink/path rules, and fixed Git timeout/stdout/stderr caps. |
| D353-9 | P2 | fixed | Removed runtime canonical-validator imports that would weaken independence; conformance tests compare independent parsing with canonical validators on shared fixtures instead. |
| D353-10 | P2 | fixed | Made capacity limits internally consistent: 8 MiB state JSON/Git stdout, 1 MiB per audit artifact, 64 MiB ledger, 10,000 entries/findings, depth 6, output 16 MiB; overflow is incomplete. |

## Readiness summary

The plan is a right-sized one-PR capstone because it adds one Saga command/skill and no producer
behavior. Its observation independence, strict corruption semantics, two-source correlation, managed
scope, and no-write contract are decision-complete enough for an unfamiliar implementer.

| rubric | score | result |
|---|---:|---|
| acceptance criteria clarity | 10/10 | all eight source rows map to distinct production-shaped scenarios and exit/report evidence |
| devil's advocate | 10/10 | duplicate/repair/scheduler scope is removed; one cross-source auditor remains |
| spec fidelity | 10/10 | the three disease classes and read-only outcome are preserved while stale mechanics are explicitly superseded |
| context completeness | 10/10 | every source, trust boundary, CLI, file family, test, cap, and negative import/action is named |
| issue sizing | 9/10 | five units and one Saga release; strict readers and three joins are cohesive, not separate products |
| prerequisite mapping | 10/10 | all four direct outcome prerequisites, transitive broker, existing audit sibling, and acceptance consumer are explicit |

## Evidence verified

- `outcome_worktrees.read_registry()` uses `_read_json_or_quarantine` and treats malformed registry as
  empty, so it is unsuitable for a zero-mutation strict auditor.
- `run_ledger.read_snapshot()` is non-mutating, but the doctor plan independently verifies the raw
  chain to avoid importing the audited projection.
- #351 defines `manifest`, `spawn`, `settle`, and `late-delivery`; `spawn` is explicitly a durable
  pre-submission position, not a host-launch acknowledgment.
- The #356 broker retains resource heads after lease release, providing an observation independent of
  #351 facts; #358 adds closed-owner and teardown evidence.
- `audit_store.resolve_*` and `delegation_audit.reconcile_store()` deliberately collapse corrupt
  artifacts to no signal, while `/delegation-audit` always exits 0. Doctor's strict exit-2 behavior is
  complementary, not a breaking change.
- Outcome-managed worktrees use `.saga-worktrees`, not the issue's historical `.worktrees` path.
- The Workflow Structure has eight steps and digest
  `4e993a3e3e4a9ce6b953995fdc5d58e74d7be26da2304e95d342d373a7d230b3`. Installed role/profile and
  full-review selection validation pass; no agent or validator was launched.
- Focused current-state regression suite: 95 passed across delegation audit/query, outcome
  worktrees, run ledger, and manifest store. `git diff --check`: clean.

## Remaining findings by priority

None. P0: 0, P1: 0, P2: 0, P3: 0.

## Residual risk

The implementation must refresh against the exact merged schemas; every direct prerequisite is
still planned rather than landed. Cross-file snapshots cannot make independent file-backed stores
transactional, so any source that changes during the scan must keep the result incomplete instead of
being retried or reconciled optimistically.

Runtime independence intentionally duplicates only the bounded schema subset needed for correlation.
The conformance fixtures are therefore release-critical: without them, producer evolution could make
the doctor's independent parser stale and noisy.
