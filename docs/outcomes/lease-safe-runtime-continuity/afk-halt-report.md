# AFK halt report — lease-safe-runtime-continuity, cross-runtime-acceptance leaf

- **Date**: 2026-07-20
- **Halt trigger**: the standing 2026-07-18 merge pre-approval is contingent on **green
  gates**; the acceptance evidence bundle is honestly **red** (`overall: fail`, 12/14) because
  of a **production defect in the pinned Claude runtime** (#628). Fixing it is a new
  production-code unit — outside the recorded AFK authority (halt-never-widen-authority). All
  work inside recorded authority is complete; this report is the halt deliverable.

## What is done (everything except the merge/close)

The cross-runtime-acceptance leaf (#605) executed to the pre-merge boundary on branch
`work/605-cross-runtime-acceptance` (worktree `.claude/worktrees/work-605-acceptance`),
HEAD `c2731c99`:

1. **Harness + evidence shipped on the branch** (KTD4 harness-only: tools/tests/docs, zero
   production or release-surface changes): the revision-pinned dual-runtime harness
   (`tools/run_cross_runtime_outcome_acceptance.py`), 57 hermetic tests, the closed schema +
   live evidence bundle + README + ceremony record under
   `docs/validation/lease-safe-runtime-continuity/`.
2. **Anchored 7-lens ceremony CONVERGED** (round 3; anchor `4b21df73…` byte-verified): 17
   round-1 findings + 2 cycle-2 P3s all remediated and re-adjudicated resolved; three lenses
   independently re-executed the harness and reproduced the 12/14 split; the #628 attribution
   could not be refuted (record: `docs/validation/lease-safe-runtime-continuity/cross-runtime-acceptance-ceremony.md`).
3. **Programmatic code-review gate CLEAN** at `8b13b2a5`: 8 validated findings (4 P2 / 4 P3,
   no P0/P1), all repaired, delta-adjudicated 8/8 resolved with zero new findings (artifact:
   `docs/code-reviews/2026-07-20-issue-605-cross-runtime-acceptance-code-review.md`).
4. **QA gate ship-with-deferred, health 100/100**: a live harness re-run at the pins with the
   post-repair code reproduced the committed bundle **verdict-for-verdict** with identical
   contract/broker digests (ledger artifact:
   `docs/evidence/adhoc-work-605-cross-runtime-acceptance/artifacts/dfe4458c….md`).
5. **Draft PR #629 opened** — deliberately WITHOUT "Closes #605", so nothing auto-closes.
   Progress comments with evidence links posted to #605 throughout.

## The blocker: #628 (filed, open, evidence-backed)

At the pinned runtimes (Claude `794b4da6` / saga 0.105.0, Codex `f3e1af75` / saga
0.78.0+codex.20260720120109), the Claude runtime carries **no `outcome.dispatch.v2`
vocabulary** in its advance dedup or its handoff already-settled guard. A codex-native intent
— even a fully receipt-validated `launched` acknowledgement — does not block Claude from
re-dispatching the same leaf: a cross-runtime **double dispatch** (`settled_chains: 2`), the
exact R5 violation the acceptance exists to catch. `race-codex-first` and `race-simultaneous`
fail; `race-claude-first` is safe (codex is dual-vocabulary-aware). The codex-native chain
itself is proven working by the same scenarios.

Filed as **infiquetra/infiquetra-claude-plugins#628** per the plan's failure rule ("Failures
retain artifacts and file/reopen the owning defect without production edits") and KTD7
(upstream-first discharge). Chain summaries and overlap receipts are in-bundle, so the defect
is auditable from the committed evidence alone.

## Decisions Jeff must make

1. **Authorize the #628 fix unit** (production change to Claude `outcome.py`/`outcome_compat.py`
   advance dedup + settled-guard: teach both to read `outcome.dispatch.v2` intents/acks). This
   is the single blocker for the acceptance going green.
2. **Sequence the re-pin + re-run**: after #628 merges, advance the Claude pin, re-run the
   harness (command in the validation README), commit the green bundle to the acceptance
   branch, mark PR #629 ready, merge, and close #605 → then the outcome close (#579, board
   reconcile, leaf harvests) proceeds under the existing plan.
3. **Or** direct an alternative (e.g., merge the harness red with the documented deferred
   state and close #605 separately after #628) — the current draft-PR shape supports either.

## Exact resume path (mechanical, once #628 ships)

```
1. Merge the #628 fix; note the new origin/main SHA (<NEWPIN>) and bumped saga version.
2. In .claude/worktrees/xr-pin-claude: git fetch && git checkout <NEWPIN>.
3. From .claude/worktrees/work-605-acceptance, re-run the harness per the README "Re-running"
   section with --claude-sha <NEWPIN> and the bumped --claude-saga-version, writing to
   docs/validation/lease-safe-runtime-continuity/cross-runtime-acceptance.json.
4. Expect exit 0, overall: pass 14/14. Update the README "Current verdict" section, commit,
   push, mark PR #629 ready for review, merge, close #605.
5. Resume the outcome flow: leaf harvest (link-pr + evidence at the close SHA under
   leaf-lease-safe-runtime-continuity-cross-runtime-acceptance), #579/board reconcile,
   outcome close + durable writebacks.
```

## Ancillary state worth knowing

- Draft PR: https://github.com/infiquetra/infiquetra-claude-plugins/pull/629 (base `main`,
  +4,546/−0 over 12 all-new files at `c2731c99`).
- Open follow-up defect #627 (filed earlier this frontier) remains open alongside #628.
- The primary checkout carries two local-main commits not yet pushed anywhere relevant to this
  leaf (`dc1d8bef`, `1a7b145a` — earlier session artifacts); untouched by this halt.
- Codex-parity leaf: SHIPPED + HARVESTED (codex PR #42); the KTD8 lease-seam activation landed
  with PA-2; nothing codex-side blocks the resume path.
