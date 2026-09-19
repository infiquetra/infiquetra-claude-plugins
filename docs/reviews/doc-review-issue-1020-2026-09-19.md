# Document Review — Board vocabulary drift plan, issue 1020

**The plan is ready to drive implementation.** Two rounds ran. Round one raised one P1 and four P2
findings; round two, verifying those repairs against source, found two of them incomplete or miscited
and raised five more findings, one of them P2. Every finding was verified against repository source
before being accepted, every one was repaired, and no P0 or P1 remains. The plan's factual claims
about the live GitHub project boards were reproduced independently, twice.

## Review-result contract

| Field | Value |
|---|---|
| Target path | `docs/plans/2026-09-19-1020-board-vocabulary-drift-plan.md` |
| Reviewed revision | Working tree, branch `issue/1020`, base commit `2044c363` |
| Classification | Plan document — `docs/plans/` path tie-breaker, plus the content signals `origin:`, `Implementation Units`, `Key Technical Decisions`, `U1`, file lists, test scenarios and a verification section |
| Rubric phase run | `issue` — the document is issue-derived, planning issue 1020 |
| Rubrics applied | Core: `acceptance_criteria_clarity`, `devils_advocate_issue`, `spec_fidelity`. Extras: `context_completeness`, `issue_sizing`, `prerequisite_mapping` |
| Blocked status | **Not blocked.** Zero P0, zero P1 remaining |
| Rounds run | Two. Round one found the findings; round two verified every repair against source and found five more |
| Applied fixes | Twenty in-place repairs, listed below |
| Review artifact path | `docs/reviews/doc-review-issue-1020-2026-09-19.md` |
| Linked issue | 1020, under the `improve-claude-plugins` objective |
| Override rationale | None needed |

## How the review ran

The readiness-skeptic pass ran inline. An independent adversarial reviewer ran in parallel at
opus/high in its own sandboxed worktree, because the reviewing agent had also authored the plan and
a self-review of one's own document is the weakest possible check. Every finding it returned was
re-verified against repository source before being accepted; none was taken on the reviewer's word.

The rubric engine's `issue`-phase rubrics were applied by judgment, following the precedent in
`docs/reviews/doc-review-issue-918-2026-08-30.md` for an issue-derived plan.

## Findings

| # | Priority | Location | Finding | Status |
|---|---|---|---|---|
| D1 | P1 | U3, test scenarios | The `Stage` assertion demanded exact equality with `stage_flow.stages`. The census sorts options alphabetically (`board_census.py:86-90`), so a correct regenerated file records `Active, Intake, Planning, Retro, Shaping, Verify` against the schema's lifecycle order `Intake, Shaping, Planning, Active, Verify, Retro`. The assertion would go red on a correct census, and the plan's own "observe it fail first" instruction would make that red read as confirmation. | Repaired — compares as sets, with the reason stated |
| D2 | P2 | R4 and U4 | R4 required the retired work-in-progress policy removed from "the two skill documents", but U4 edited only their two pointer lines. Three live instructions to enforce the deleted policy survived, and two more lines named the retired status `Ready` where R3's grep cannot reach. | Repaired — all five lines named, plus `metrics-targets.md:73` |
| D3 | P2 | U4, edit list | The enumerated edit list omitted the "Metrics Boundaries" table (`kanban-workflow.md:158-166`, terminal status `Done`, which exists on no live board) and the "Asgard modes" table (`:40-46`, documenting a `Mode` field the live board no longer carries). | Repaired — both named with an explicit disposition |
| D4 | P2 | R5 | R5 justified deleting all three stale workflow labels as "names a workflow the schema does not define". True of `intent_flow`, false of `campps_initiative`, which the schema does define as `retired_historical`. The CAMPPS deletion is correct but was wrongly justified, and its behavior change was unstated. | Repaired — the two failure modes are now distinguished |
| D5 | P2 | U1, test scenarios | The list of existing tests to update was incomplete: two shape tests break under a name-keyed mapping and were unnamed. | Repaired — both named with their required rewrite |
| D6 | P3 | U3 | The live-leg environment variable name was left to the implementer. | Repaired — fixed as `BOARD_SCHEMA_LIVE=1` in R7 |
| D7 | P3 | U3 | Claimed all four assertions fail before regeneration; the board-presence assertion passes today. | Repaired — narrowed to the second, third and fourth |
| D8 | P3 | U3 | The census-key to schema-board-key crosswalk was unstated, though `_project_board_key` shows the two can diverge. | Repaired — a crosswalk paragraph was added |
| D9 | P3 | U3 | The root `tests/` path was attributed to repository convention, but all 34 mission-control `test_*.py` files sit in the plugin's own directory. | Repaired — attributed to the card |
| D10 | P3 | KTD1, KTD4 | Two citation drifts: a line range off by one at each end, and a quote that blended two differently worded source lines. | Repaired — both quoted verbatim with exact lines |

Two further repairs came from the author's own pass rather than the adversarial reviewer, and are
recorded because one of them corrected a false claim:

| # | Priority | Location | Finding | Status |
|---|---|---|---|---|
| D11 | P1 | Problem frame, R5, U5 | An earlier draft called the stale `project-mappings.json` labels a **live** defect. This was false. `_resolve_project_mappings` (`sdlc_manager.py:305-317`) prefers an external override, and `get_sdlc_path()` falls back to `~/workspace/infiquetra/infiquetra-sdlc`, which exists on this machine and is current — so resolution returns `stage_flow` here. Driving the resolver from the vendored file directly reproduces the real, **latent** behavior. | Repaired — reframed as latent, with the masking mechanism named and a proving command added |
| D12 | P2 | U1 | KTD2's duplicate-name error could collide with the runaway-pagination test, which mocks 30 fields all named `X`. | Repaired — the raise must stay after `paginate_or_raise`; verified that it does, so the guard is unperturbed |

Round two, checking the repairs, turned up three more. Two were found by widening a citation the
round-one repair had introduced, which is the ordinary way a repair pass earns its keep.

| # | Priority | Location | Finding | Status |
|---|---|---|---|---|
| D13 | P2 | R3, U4 | `plugins/mission-control/skills/board/SKILL.md` carries a **duplicate** of the same defect the card is about: the retired `Idea -> Shaping -> Ready -> Active -> Verify -> Done` ladder for Operations and Asgard at lines 37-41, and the same self-admitted staleness sentence at lines 47-48. Fixing only the reference document would leave a second board-facing surface describing a vocabulary no board has. A sweep confirmed these are the only two files carrying the ladder. | Repaired — added to R3 and U4, with the sweep recorded as a completeness check |
| D14 | P3 | U4 | The round-one repair cited `metrics-targets.md:73` for a retired `Ready`. Reading the surrounding lines showed 72-74 is one passage that also says active work is `In Progress` for CAMPPS — a status on no live board — and names "intent-flow boards", the deleted workflow. | Repaired — citation widened to 72-74 with the full defect described |
| D15 | P3 | U3 | The claim that mission-control has 36 test files was wrong; the true count is 34 `test_*.py` files. A wrong count in a document whose whole subject is stale cached facts is worth fixing on principle. | Repaired — corrected to 34 |

A second adversarial pass then checked each repair against source and found that two of them were
themselves incomplete or miscited. This is the pass earning its keep, and it is why the round was run.

| # | Priority | Location | Finding | Status |
|---|---|---|---|---|
| D16 | P2 | R4, U4 | The retired vocabulary reached four more places the repair had not named: `board/SKILL.md:122` ("For Operations and Asgard that means `Done`.") and three cycle-time and terminal-status tables at `metrics/SKILL.md:45-47`, `metrics-targets.md:16-18` and `:48-50`, all giving `Done` or `In Progress` as terminals. Same defect class as the table U4 already named. | Repaired — all four named with the same disposition |
| D17 | P3 | U4 | The "Asgard modes" table was cited at lines 40-46. It is at 43-49; lines 40-41 are the tail of the retired status table and the range stopped before the `Mission` row. The "Metrics Boundaries" citation started one line early on a blank. | Repaired — corrected to 43-49 and 159-166 |
| D18 | P3 | U1 | Both named test line ranges were off (36-61 and 63-97, not 34-59 and 62-95); `:60-61` breaks under a mapping and was undescribed; and the fixture cited at `:231` is `{"boards": {}}` with no `fields` value, so it needs no change, while the real second fixture at `:210` was unnamed. | Repaired — ranges corrected, `:60-61` described, `:231` replaced by `:210` |
| D19 | P3 | U3 | The "prove the guard" paragraph accounted for three failing assertions; the fifth ("`fields` is a mapping") also fails beforehand, since the committed census's `fields` is an array. | Repaired — now four |
| D20 | P3 | KTD4, U3 | Two citation spans: the `sdlc_manager.py:1227` quote spans `:1227-1228`, and `_project_board_key` is `:408-414`. A quotation of `metrics-targets.md:73` used a semicolon where the file has a period. | Repaired — all three corrected |

## What was verified live, not assumed

- `board_census.py --check` against the live boards prints `FAIL board-schema.json has drifted from
  the live board schema.`
- All three boards carry a `Stage` field with the six stages and a `Status` field with exactly the 26
  stage-flow statuses, matching `sdlc-schema.json` version `2026-09-07.5`.
- The field-membership diff U2 predicts — four fields added, eleven removed across the three boards —
  reproduces item for item.
- No live board has a duplicate field name (16 fields on each), so KTD2's hard error cannot fire
  during U2. This closes the one item the adversarial reviewer left unverified.
- The vendored `project-mappings.json`, driven directly, yields a one-entry status order for
  Operations and Asgard and the retired ladder for CAMPPS.

## Residual risk from limited evidence

Every test claim in the plan comes from reading test source, not from executing it. Neither
`scripts/gate.sh` nor `mypy` nor the mission-control suite was run during planning; running them is
the implementer's first-round work, and the plan's verification section names the commands.

U2 depends on a GitHub token carrying the `project` scope. The planning session had one and reached
the live API; a session without one cannot complete that unit, and the plan says to stop rather than
hand-edit the census.
