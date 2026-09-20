# Issue 1030 — the removals, the team-execution archive, and the saga 1.0.0 release

Branch `issue/1030`, cut from `parent/1018` at `61da4b1c`. Plan:
`docs/plans/2026-09-20-issue-1030-removals-and-saga-1-0-0-release-plan.md`. Document review:
`docs/reviews/doc-review-issue-1030-2026-09-20.md`.

## The operator's answers, recorded

Both questions the plan left open were answered by the coordinator, relaying decisions the operator
took on 2026-09-19 when he decided the removals and filed the card. They are recorded here because
the plan says an answer to either is what unblocks the work, and a reader needs to see what was
granted rather than infer it.

**The seven approval boundaries.** Production changes: none. Destructive operations: the
in-repository file and directory deletions the card names, on this branch only, reversible through
git history — no branch deletion, no force push, no history rewrite, no data or environment change.
Secrets or credential changes: none. Identity and access or permission changes: none. Billing or
cost-impacting actions: none. External commitments: none. Major team or process authority changes:
exactly one — replacing the sandbox-spawn instruction in `CLAUDE.md` with "review roles run as roster
sessions in their own worktrees" and deleting `plugins/saga/references/sandbox-spawn-sites.md`, as
the card words it, and nothing beyond it.

The admission path was re-run with the completed answers file and now fills **8 of 8** questions and
13 of 13 run-configuration parameters. It did not refuse the second run: an answer already in the
record is never re-asked, so the re-run printed an empty question set and rewrote the record at
`<primary checkout>/.claude/saga/runs/issue-1030.json`.

**cc-workflows.** Take the plan's recommendation: move the three Workflow-emission modules beside
their only importer rather than deleting them, so nothing the card does not name is deleted and the
plugin stays loadable. Whether cc-workflows is later archived is a separate card for the operator.

**That instruction could not be carried out as written, and section "The blocker" below is why.**

## Every other choice, and where it came from

| Choice | Taken | Source |
|---|---|---|
| Saga | resumed `issue-1030`, no second saga minted | coordinator |
| Branch | stayed on `issue/1030` | coordinator |
| Execution backend | `inline`; no other backend offered or entered | coordinator, and the pre-answer carrier the plan stage validated |
| Document-review gate | passed; two P2 and one P3 open by design, no override needed or used | coordinator |
| Code review | none in this stage; deferred to the parent pull request | coordinator |
| Board move | the documented Implementing move, submitted through the reconcile controller | coordinator |
| Complexity triage and round-N detection | the skill's documented defaults | coordinator's standing instruction |
| `/qa` skill, `qa_*` scripts, the QA catalogue, `tests/test_qa_*` | not edited | issue 1039 owns them |
| `release_step.record_functional_test` | not touched | issue 1039 repairs it in its own stage |

## The blocker: the Workflow-emission trio is not separable from the engine family

The instruction assumed `execution_spec.py`, `concurrency_governor.py` and `dispatch_settlement.py`
are three self-contained modules that can move beside the cc-workflows emitter. They are not, and the
measurement is not close.

**Measured three ways at `61da4b1c`:**

1. **The transitive closure.** Moving the three modules with their imports intact drags **44 further
   modules and 24,565 further lines** into cc-workflows, including the entire outcome coordinator.
   The closure is 47 files and 30,061 lines against a seed of 3 files and 5,496 lines.
2. **The direct imports.** `execution_spec.py` imports `engine_calibration`, `engine_overlay`,
   `engine_resolver`, `engine_registry` and `chaperone_economics` at its module head (lines 58 to
   63), with 41 references to them through the file. `dispatch_settlement.py` imports `run_ledger` at
   line 24 and references it **46 times** — the ledger is its substrate, not an optional adapter.
3. **The declared boundary.** The emitter's `SUBSTRATE_SURFACE` — the explicit list of names allowed
   to cross the plugin boundary, added by an earlier review — has 29 entries, and two of them,
   `_load_emission_registry` and `_build_emission_routing_context`, are the engine-routing functions
   themselves. Even the declared surface reaches the engine registry.

**What the emitter actually uses is far smaller**, which is what makes this a real decision rather
than a dead end: one name from `concurrency_governor` (`ordered_chunks`) and three from
`dispatch_settlement` (`UnitSpec`, `safe_contract_identifier`, `settlement_metadata`). Every other
consumer of `dispatch_settlement` is a module this card deletes.

**Why this blocks more than the move.** The card removes the engine family and the ledgers. Whichever
plugin holds `execution_spec.py`, it imports the engine family; whichever holds
`dispatch_settlement.py`, it imports `run_ledger`. So the engine-family and ledger removals — the
bulk of the card's line count — cannot land until the trio is severed from them, wherever the trio
lives. There is no ordering that avoids this.

**The shape of the work, if the operator wants it done.** Sever rather than relocate: keep
`execution_spec.py`'s spec schema and drop its engine-routing arm, which is dead the moment
`/engines` goes; keep the three names the emitter uses from `dispatch_settlement` and drop the
ledger; keep `ordered_chunks`. The cost is not the source edit but the tests: 9,261 lines across
eight test files cover this surface, and `tests/test_workflow_emitter.py` alone is 2,161 lines
exercising the emitter end to end including engine routing. This is a card's worth of work, not a
unit's, and it changes what a Workflow run does — a behaviour decision about a backend, following
from the decision to remove external engines.

**The recommendation** is that this becomes its own card, filed against the same parent, and that
this card's remaining removals land without it.

## What landed

Every removal independent of the trio. See the commit list on the branch.

## Residuals for the merge turn

- The `/qa` skill still names saga's read-only verifier agent at `SKILL.md:201`. Issue 1039 rewrites
  that file and merges first; after its merge, grep the merged `/qa` skill for every removed module
  and agent name and repair any hit there rather than in issue 1039's files.
- `plugins/saga/skills/work/SKILL.md` and `plugins/saga/skills/plan/SKILL.md` still offer
  `team-execution` as an execution backend. That enum value goes with the archive; it is recorded
  here because the backend enum is shared with `references/operator-choice.md` and the cc-workflows
  emitter, so it moves with the archive unit rather than piecemeal.
