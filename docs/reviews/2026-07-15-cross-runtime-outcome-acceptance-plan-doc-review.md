# Doc Review - Cross-runtime Outcome acceptance plan

One-line verdict: **READY TO FREEZE** - all P0-P3 findings were fixed; execution remains gated on
exact merged/installed prerequisites, operator approval, and the acceptance workflow candidate.

## Review-result contract

- **Target:** `docs/plans/2026-07-15-cross-runtime-outcome-acceptance-plan.md`
- **Reviewed revision:** local outcome worktree based on
  `a20cc3ce6d740a4891bddba71f7e8f2856620655`
- **Review artifact:**
  `docs/reviews/2026-07-15-cross-runtime-outcome-acceptance-plan-doc-review.md`
- **Repository:** `infiquetra/infiquetra-claude-plugins`
- **Classification:** high-risk multi-runtime acceptance evidence and outcome-close gate
- **Rubrics:** issue cores plus context completeness, issue sizing, prerequisite mapping, and
  readiness concurrency, security/authority, evidence/privacy, release, and QA lenses
- **Hard inputs:** Claude compatibility, Codex substrate, Codex protocol parity, and #353 releases
- **Blocked actions:** no runtime install, external mutation, agent/validator launch, implementation,
  Git write, acceptance run, QA, or closeout occurred

## Applied fixes

| ID | Priority | Status | Applied fix |
|---|---|---|---|
| D579A-1 | P1 | fixed | Replaced false “identical derived node state” across clones with canonical completion/candidate-frontier equivalence and explicit transient unknowns. |
| D579A-2 | P1 | fixed | Required clean exact-SHA checkouts, isolated installed packages, manifest/schema digests, and runtime readback before scenarios. |
| D579A-3 | P1 | fixed | Added two OS processes, deterministic barrier, monotonic overlap receipt, and a write-once fake backend so accidental serialization cannot pass. |
| D579A-4 | P1 | fixed | Asserted shared settlement and Codex's protected launched acknowledgement separately; handoff/handed-off/legacy evidence cannot substitute. |
| D579A-5 | P1 | fixed | Kept protected handoffs inside the same temporary clone and added both directions plus operation/subplot, TTL/skew, copy, cross-clone, forgery, and replay rejection. |
| D579A-6 | P1 | fixed | Added legacy bundle import rejection in both runtimes with complete pre/post mutation snapshots. |
| D579A-7 | P1 | fixed | Made production behavior changes forbidden in the acceptance PR; failures file/reopen the owning defect. |
| D579A-8 | P2 | fixed | Added explicit neutral broker-root selection and cross-runtime redacted-root digest parity. |
| D579A-9 | P2 | fixed | Added teardown twice plus #353 raw-source doctor proof for every lease, worktree, dispatch, delegation, handoff, and wiring position. |
| D579A-10 | P2 | fixed | Closed the evidence schema around exact SHAs/versions/digests/commands, hash-only bounded streams, environment-name allowlist, and privacy denylist. |
| D579A-11 | P2 | fixed | Added a mandatory `saga:qa` gate after code-review/fixes and before #579/outcome closeout. |
| D579A-12 | P3 | fixed | Added the machine outcome-spec path/node and completed this review-result contract with reviewed revision and artifact path. |

## Readiness summary

| rubric | score | result |
|---|---:|---|
| acceptance clarity | 10/10 | every cross-runtime claim has a positive, race, skew, replay, migration, or cleanup selector |
| independence | 10/10 | clean merged inputs, installed readback, and a harness-only PR prevent working-tree self-certification |
| concurrency rigor | 10/10 | process overlap and one write-once effect are measured, not inferred |
| authority/security | 10/10 | same-clone protected handoff and cross-clone read-only boundaries are explicit with no-mutation oracles |
| evidence/privacy | 10/10 | closed schema binds exact revisions while excluding raw/sensitive runtime material |
| closeout mapping | 10/10 | code review, QA, doctor, issue/board, #579, report, and DAG closure are all required |

## Evidence verified

- The Claude compatibility plan deliberately excludes transient state from portable canonical status
  and confines mutating handoff to protected same-clone evidence.
- Codex dispatch state requires a native launched acknowledgement, so shared settlement alone is not
  sufficient acceptance evidence.
- #353 is downstream of settlement, containment, liveness, and teardown and is the independent raw-
  source capstone rather than an acceptance-harness repair mechanism.
- The Workflow Structure parses and passes full-review selection with digest
  `4e50f995b5398188054462b0c36ffb8350e8c9a787ec42764771bc4457829e7a`; required validators are
  concurrency, event-flow, and scenario.

## Remaining findings by priority

None. P0: 0, P1: 0, P2: 0, P3: 0.

## Residual risk

The acceptance commands, exact plugin installation procedure, and #353 invocation must be frozen
from the merged releases. If a prerequisite changes its CLI/schema or cannot provide installed-state
proof, refresh the plan/review and workflow candidate rather than weakening the harness or closing
with a waiver.
