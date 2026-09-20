# Work session — Issue 938: remove Work's in-process second-opinion offer

Issue: infiquetra/infiquetra-claude-plugins#938
Plan: `docs/plans/2026-09-20-issue-938-remove-work-second-opinion-offer-plan.md`
Plan review: `docs/reviews/2026-09-20-issue-938-remove-work-second-opinion-offer-plan-review.md`
Branch: `issue/938`, based on `parent/1018` at `b98e94ea`
Backend: `inline`
Destination: `pr` — the parent pull request for issue 1030 carries the whole integration branch

## The admission step refused, and why that is recorded rather than worked around

`plugins/saga/scripts/admission.py` refused to run for this card, in both dry-run and real mode,
exit code 2, writing nothing:

```text
admission: the card is not ready and admission writes nothing: Missing required H3 sections: ['Risk']
```

Card 938 was filed before the card template gained its `Risk`, `Failure modes / pre-mortem` and
`Stop conditions` sections, and `admission.py` runs the card validator first by design. So there is
no run record for this card. The card does state its risk, in prose inside its Intent section
("its risk is removing one component too many"), but not under a heading the validator can see.

Amending the card body is board authority and belongs to the operator, so it was not done here. No
run record was hand-written either. The admission answers live in the plan under "Admission
answers", each with its source, and the amendment question is carried to the operator. If the
operator adds the section, the coordinator re-runs admission afterwards.

## Choices taken, and where each came from

Every choice below was supplied by the coordinator's stage-two message unless another source is
named; none was invented here.

| Choice | Taken | Source |
|---|---|---|
| Saga | Resumed `issue-938` from this worktree's store; no second saga minted | Coordinator |
| Branch | Stayed on `issue/938` | Coordinator |
| Execution backend | `inline` | Coordinator, matching the plan's `backend:` frontmatter |
| Doc-review gate | Passed, nothing above P3 open; no override used or needed | Coordinator; the review artifact named above |
| Complexity triage | Medium | Coordinator's stage-one message |
| Round-N detection | Fresh build, round 1 — no pull request exists for this card | The skill's documented default; no PR to re-enter |
| Ceremony start | Declined | It opens a draft pull request and this card opens none |
| Code review | None in this stage | Operator decision of 2026-09-19: one review at the parent pull request |
| Gate script | Not run | Coordinator; the inner loop plus the full suite is the proof here |
| Saga version | 0.167.0, bumped from 0.166.0 at `b98e94ea` | Next minor above what the integration branch showed when read |

## What changed

**Removed.** `plugins/saga/scripts/second_opinion.py` (2,076 lines) and
`tests/test_work_second_opinion.py`; the `## Second-opinion triggers` section of
`plugins/saga/skills/work/SKILL.md` and the one sentence in `## Reviewer-session transport` that
pointed forward to it; the `## Repeated-failure second-opinion sidecar` section of
`plugins/saga/skills/work/references/pr-continuation-loop.md`; and
`test_work_second_opinion_trigger_contract_is_operator_confirmed_and_non_gating` from
`tests/test_saga_plugin.py`, which asserted the offer existed and so could not survive it. Both
skill sections were located by heading, not by line number, because sibling card 1029 edits the same
skill file in parallel.

**Kept, with the consumer that needs it and the test that proves that consumer passes.** This is the
card's central safety requirement, so it is enumerated rather than summarised, and
`tests/test_work_second_opinion_removed.py::test_every_retained_component_keeps_its_named_live_consumer`
asserts every row.

| Retained component | Named live consumer | Proving test | Result |
|---|---|---|---|
| `plugins/saga/references/engine-output-trust-boundary.md` | `plugins/team-execution/.../validator-registry.md`, citing it by path | `tests/test_engine_output_trust_boundary.py::test_team_execution_references_point_to_trust_boundary_contract` | pass |
| The same document | `plugins/team-execution/.../validator-criteria.md`, citing it by path | the same test | pass |
| `plugins/saga/scripts/engine_dispatch.py` | `plugins/saga/scripts/engine_resolver.py`, plus nine other Saga scripts | `tests/test_saga_engine_dispatch.py::test_satisfy_gate_requires_ready_reconciliation_before_existing_checks` | pass |
| The same module, as the Orchestrate seats' rule | `plugins/orchestrate/.../orchestrate.py`, which halts rather than falling back to the retired runner | `tests/test_saga_second_opinion.py::test_review_skills_halt_instead_of_naming_a_launch_cli` | pass |
| `plugins/saga/scripts/reconcile.py` | `plugins/saga/scripts/outcome_reconcile.py` | `tests/test_reconcile.py` | pass |
| `plugins/saga/scripts/run_ledger.py` | `plugins/saga/scripts/pulse.py`, plus seventeen other Saga scripts | `tests/test_run_ledger.py` | pass |
| `plugins/saga/scripts/engine_resolver.py` | `plugins/saga/scripts/execution_spec.py` | `tests/test_saga_engine_resolver.py` | pass |
| Document Review's second-opinion prose | The Document Review skill itself; this card is forbidden from resolving it | `tests/test_saga_plugin.py::test_document_review_second_opinion_contract_is_intact` | pass |

**The trust boundary survived intact.** Its document keeps every row, every forbidden sink and every
rule; only the Source cell of the `external_opinion.findings[].content` row changed, because it named
the deleted script. The guard's `PYTHON_CALL_SITES` tuple named two modules and now names the one
that remains. The card's warning was well aimed and the parent card's finding was correct: this
boundary is a document plus a scanning guard, not a shared module, which is exactly why deleting one
scanned site did not break it.

## Tests, and the red observed before the green

`tests/test_work_second_opinion_removed.py` was written and run **before** any removal. Against the
unmodified tree at `4220f3c2` it reported **3 failed, 3 passed**:

- `test_work_offers_no_in_process_second_opinion_by_any_route` — failed, the offer was still there.
- `test_no_feature_private_second_opinion_module_survives` — failed, the module was still on disk.
- `test_the_external_content_trust_boundary_survives_the_removal` — failed, the document still named
  the module.
- `test_every_retained_component_keeps_its_named_live_consumer` — passed, and earned its keep on the
  first run: it caught a proving-test name this driver had guessed wrong
  (`test_satisfy_gate_requires_a_bound_ready_reconciliation`, which does not exist) and named the
  file and the missing function in the failure. Corrected to the real
  `test_satisfy_gate_requires_ready_reconciliation_before_existing_checks`.
- `test_work_keeps_merge_confirmation_typed_outcomes_and_the_programmatic_rule` — passed before and
  after, which is what an anti-regression pin should do.
- `test_readding_the_offer_fails_the_no_offer_check` — the mutation proof; passed, showing the
  predicate is capable of failing. It appends the real offer line to a copy of Work's skill in
  `tmp_path` and calls the same `offer_violations` function the real assertion calls, so the proof
  exercises the enforced rule rather than a restatement of it.

After the removal the same file reports **6 passed**.

`tests/test_saga_second_opinion.py` was rewritten, not deleted. Two of its five tests were about the
deleted module and went with it; three were about contracts that survive and were kept, and its
tombstone test now names all four deleted modules (`engine_session_runner.py`, `engine_offer.py`,
`external_only.py`, `second_opinion.py`).

## The card's own first verification command

The card offers a repository-wide word search as its first check. Run at the merged head it still
returns matches, and that is the correct outcome — the output is quoted and explained in the return
to the coordinator. Three families survive by design: Document Review's prose, which this card is
forbidden to resolve and whose parent is notified instead; the trust-boundary document, whose row
must not be deleted; and `plugins/saga/CHANGELOG.md`, which is release history and is never
rewritten to hide a removed feature.

## Journal

Two `LEARNINGS.md` entries — a trust boundary held as a document plus a scanning guard survives
losing one scanned call site, and the admission questionnaire refuses a card filed before the
template grew its `Risk` section. Two `DECISIONS.md` entries — the external seat's deferred claim
lifecycle is moot and is recorded rather than built, and `engine_recommend.py` is retained as a
named residual because this card does not name it. All four ship in the same commit as the change.

## Follow-ups left behind

- `plugins/saga/scripts/engine_recommend.py` now has only its own test as an importer. Retained,
  because this card does not name it; recorded in `DECISIONS.md` for a card that does.
- Document Review's prose still describes a claim, a runner owner and a pending-collection path
  whose only carrier was the deleted module. Issue 1026 is notified; resolving it is its to schedule.
- Amending card 938 with a `Risk` section so admission can run for it — an operator decision.
