# Doc Review - Codex shared runtime substrate plan

One-line verdict: **READY TO FREEZE** - all P0-P3 findings were fixed; implementation remains gated
on operator approval, exact upstream merges, a fresh isolated Codex worktree, a target-repo plan
refresh, and the port-contract classification gate.

## Review-result contract

- **Target:** `docs/plans/2026-07-15-codex-shared-runtime-substrate-plan.md`
- **Reviewed revision:** local outcome worktree based on
  `a20cc3ce6d740a4891bddba71f7e8f2856620655`
- **Review artifact:**
  `docs/reviews/2026-07-15-codex-shared-runtime-substrate-plan-doc-review.md`
- **Target repository:** `infiquetra/infiquetra-codex-plugins`
- **Planning snapshot:** Codex `739fb34e27f2e045e28cf5d420bbc2fc004115a0`; live `origin/main` matched
  during the read-only grounding pass
- **Classification:** high-risk cross-repository lease, fencing, and settlement proof port
- **Rubrics:** issue cores plus context completeness, issue sizing, prerequisite mapping, and
  readiness security/authority, migration, portability, release, rollback, and dirty-worktree lenses
- **Blocked actions:** no issue/board mutation, worktree creation, agent/validator launch,
  implementation, Git write, install, or profile mutation occurred

## Applied fixes

| ID | Priority | Status | Applied fix |
|---|---|---|---|
| D579S-1 | P1 | fixed | Split the missing Codex lease/settlement substrate from protocol parity and made it a separate DAG node/issue/PR. |
| D579S-2 | P1 | fixed | Replaced runtime-home defaults with one neutral root resolution and a redacted canonical-root digest that both runtimes must match. |
| D579S-3 | P1 | fixed | Preserved Codex `outcome.dispatch.v2`: only protected `ack_kind=launched` proves dispatch; `handed-off` and legacy records cannot be upgraded by shared settlement. |
| D579S-4 | P1 | fixed | Made the mandatory runbook-v3 manifest/classification gate precede every source-derived behavior edit and required exhaustive Codex preservation drift. |
| D579S-5 | P1 | fixed | Added current dirty-primary-worktree detection and required a fresh isolated target worktree from live `origin/main`. |
| D579S-6 | P1 | fixed | Put fence/resource validation at the final side-effect seam and added no-mutation requirements for stale, closing, superseded, wrong-root, corrupt, and unverifiable writers. |
| D579S-7 | P2 | fixed | Classified Claude hooks/Workflow/team teardown as reject/defer rather than importing host-shaped enforcement; constrained this issue to Fleet Core primitives and the Saga adapter. |
| D579S-8 | P2 | fixed | Added a target-repo copy and focused plan/doc-review refresh before manifest binding because coordinator-repo planning bytes cannot satisfy the Codex port contract. |
| D579S-9 | P2 | fixed | Added multiprocess, write-once-effect, crash-window, migration, privacy, root-parity, installed-state, fresh-session, and exact-rollback gates. |
| D579S-10 | P2 | fixed | Removed stale version assumptions; target versions are calculated from the fresh execution base after behavior passes. |
| D579S-11 | P3 | fixed | Added the machine outcome-spec path/node and completed this review-result contract with reviewed revision and artifact path. |

## Readiness summary

| rubric | score | result |
|---|---:|---|
| acceptance clarity | 10/10 | every lease, fence, settlement, acknowledgement, migration, and release claim has executable evidence |
| prerequisite mapping | 10/10 | exact #351/#356/#355 inputs and downstream protocol parity are explicit |
| security/authority | 10/10 | safe neutral root, current fence, final-seam guard, bounded records, and no-mutation rejection are closed |
| portability fidelity | 10/10 | authority class, manifest stages, classification, install, fresh-session, cutover, and rollback follow runbook v3 |
| Codex preservation | 10/10 | dispatch-v2, protected launch receipt, handed-off, and legacy-unverified behavior are named hard invariants |
| issue sizing | 9/10 | large but cohesive shared substrate; protocol, liveness, teardown, doctor, and acceptance stay excluded |

## Evidence verified

- Codex `plugins/saga/scripts/outcome_store.py` derives `dispatched` only from a valid v2 launched
  acknowledgement and retains `handed-off` and `legacy-unverified` states.
- `tests/test_outcome_dispatch_migration.py` pins launched versus handed-off and legacy behavior.
- Codex currently has no lease-broker, resource-guard, or shared dispatch-settlement module matching
  the planned Claude substrate; a protocol-only issue would hide a major prerequisite.
- Codex `AGENTS.md` mandates the v3 port runbook and classification gate before behavior edits.
- The current Codex primary worktree has unrelated modified/untracked state; the plan's isolated
  worktree boundary is necessary.
- The Workflow Structure parses and passes full-review selection with digest
  `1ca06d3b15280fa357d69d8d9e588d90b660a36473ac04af87e4d03b39378aba`.

## Remaining findings by priority

None. P0: 0, P1: 0, P2: 0, P3: 0.

## Residual risk

The upstream modules and exact merge SHAs do not exist yet. The target-repo refresh must compare the
merged source to this plan and may revise module names, row counts, and unit boundaries. It may not
relax the neutral-root, final-fence, native-acknowledgement, or port-gate invariants without a new
operator-approved workflow candidate.
