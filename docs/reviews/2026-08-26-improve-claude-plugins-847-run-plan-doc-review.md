# Document review — issue #847 run-wide implementation plan

The `infiquetra-claude-plugins` run plan is ready to drive issue #847 because every genuine
implementation-readiness defect found in the one broad review has been repaired in the plan.

| field | value |
| --- | --- |
| target path | `docs/plans/2026-08-26-improve-claude-plugins-847-run-plan.md` |
| reviewed revision | plan commit `0be81ccee3bfed304707525dacef7f8087441bf9` (`docs(plans): run-wide implementation plan for orchestration parent #847`), integrated at `7a4e938b8ddaa55557a5407f356a3cc610bc0245`; source grounding remains `origin/main` `3ab04adb0644feecd5a81cade318dc1cce59b6a9` |
| blocked status | **no** — no Priority 0 (P0) or Priority 1 (P1) finding remains after repair |
| applied fixes | fourteen validated findings repaired directly in the plan, including targeted coordinator finding F14 |
| review artifact path | `docs/reviews/2026-08-26-improve-claude-plugins-847-run-plan-doc-review.md` |
| linked issue | [infiquetra/infiquetra-claude-plugins#847](https://github.com/infiquetra/infiquetra-claude-plugins/issues/847) |
| pre-launch audit | [issue #847 operator-decision audit](https://github.com/infiquetra/infiquetra-claude-plugins/issues/847#issuecomment-5419377470) |
| preflight receipt | [issue #847 preflight receipt](https://github.com/infiquetra/infiquetra-claude-plugins/issues/847#issuecomment-5419740532) |
| launch receipt | [issue #847 run launch](https://github.com/infiquetra/infiquetra-claude-plugins/issues/847#issuecomment-5419815095) |
| override rationale | n/a |

## Applied fixes

- Made expansion just-in-time. The coordinator selects only dispatchable rows, then materializes
  the first available recorded pool's exact vendor, model, and effort before calling `expand`.
  Fallback pools replace unavailable capacity; they never raise the four-worker ceiling.
- Preserved the recorded `after` and `serialize` fields while closing the pinned driver's lifecycle
  gap: a Lane O or Lane M successor is not expanded until its predecessor is reviewed, merged,
  green in CI, and cleaned.
- Replaced plugin-directory routing with each child card's exact file list and exact release
  surfaces. The recorded shared journal and marketplace files remain shared collision surfaces;
  no unit acquired a file owned by another lane.
- Corrected the small Mission Control agreement-test unit for issue #830 to one test file, with no
  guidance edit and no release bump.
- Added the exact typed Code Review controller and reviewer-seat expansion, `review-result`
  collection, reviewed-commit freshness check, and repair-cycle rule. Every Work task invokes
  `/saga:work` and suppresses Saga Work's internal review phase because the run owns one separate
  typed controller.
- Rebalanced every lens declaration against the installed Saga roster. Every unit has the four
  required always-on lenses, zero to two justified conditional lenses, one line of reason per
  lens, and no more than six lenses.
- Bounded the help-width repair to the two files named by issue #839 and added the required terminal
  width matrix. A newly discovered out-of-list file now stops the unit for re-planning.
- Removed the Saga workflow-emitter test from issue #840's editable files because the child names it
  only as verification evidence.
- Removed both unattended open questions. The binding launch clarification fixes typed Orchestrate
  review transport; the remaining OpenCode fallback choice stays inside the pinned driver with the
  exact `xhigh` variant.
- Added the exact planning, document-review, worker-pool, and review assignments, and corrected the
  operator-decision audit description to disclose that issue #848 was created after that audit.

## Readiness summary

**READY.** The repaired plan contains nineteen implementation units in the five lanes recorded by
issue #847. It preserves every lane edge, exclusive owner, shared collision exception, worker
route, model, effort, workspace, and merge rule. The JavaScript Object Notation (JSON) implementation
block parses and all nineteen rows carry `name`, `vendor`, `model`, `effort`, `workspace`, `role`,
`paths`, `after`, `serialize`, and exact `task` text. The separate typed review expansion adds one
`review-controller` and at most six live `external-reviewer` seats without changing those rows.

Issue #829's Mission Control test-root repair precedes issue #822. The issue #822 task must read the
merged issue #829 change, use its identical package-root pattern, and cite where the pattern was set
before the coordinator expands that row.

No unit proposes the prohibited general package manager, recovery engine, provenance framework,
documentation generator, replacement launcher, backend abstraction, path-resolution framework, or
replacement rollout capability. The plan names these non-goals globally and repeats the relevant
child-specific boundary in each task.

## Remaining findings by priority

| priority | open findings |
| --- | --- |
| P0 | none |
| P1 | none |
| Priority 2 (P2) | none |
| Priority 3 (P3) | none |

## Issue-phase rubric review

All three core rubrics apply. The three conditional rubrics also apply because this is a nineteen-
unit code-change campaign with a recorded dependency graph and several shared collision surfaces.
Rubric observations are not reclassified as separate findings in the disposition ledger.

| rubric | score | result |
| --- | --- | --- |
| `acceptance_criteria_clarity` | 9/10 | Each unit now states the smallest change, owned files, verification, prohibited expansion, and exact worker task. |
| `devils_advocate_issue` | 9/10 | The repaired plan closes the plausible failure paths: pool substitution, premature lane reuse, stale review results, broad path admission, and scope inflation. |
| `spec_fidelity` | 10/10 | The five lanes, recorded edges, collision exceptions, assignments, and issue #829 → issue #822 content dependency match issue #847. |
| `context_completeness` | 9/10 | The parent, children, preflight, pinned driver, installed launcher behavior, and installed lens roster provide enough context for unattended execution. |
| `issue_sizing` | 10/10 | Nineteen child issues remain nineteen implementation units; no framework or replacement capability was bundled into a child. |
| `prerequisite_mapping` | 10/10 | Launch edges are unchanged, merge-only rules remain coordinator policy, and the issue #829 → issue #822 content edge is explicit. |

## Lens predeclaration audit

The four required always-on lenses are `architecture-maintainability`, `correctness`, `security`,
and `testing`. The table lists only additional conditional lenses. Four-lens entries are deliberate
small-unit selections, not missing assignments; six-lens entries have two distinct conditional
triggers and are not a mechanical default.

| plan unit and child | total | conditional lenses | result |
| --- | ---: | --- | --- |
| U1, issue #842 release guard | 5 | `adversarial` | applicable; release-gate bypasses are the named risk |
| U2, issue #838 journal lint | 5 | `documentation-clarity` | applicable; the repair changes cited prose and anchors |
| U3, issue #846 concurrency tests | 5 | `reliability` | applicable; deterministic behavior under load is the deliverable |
| U4, issue #839 help assertions | 4 | none | proportional; two test files and no product behavior |
| U5, issue #841 launcher preflight | 5 | `reliability` | applicable; fail-before-launch behavior is the deliverable |
| U6, issue #848 model authority | 6 | `documentation-clarity`, `agent-usability` | applicable; the authority contract is consumed through agent-facing documents |
| U7, issue #837 review transport | 5 | `adversarial` | applicable; near-miss review prose must not acquire transport authority |
| U8, issue #845 task spill | 6 | `reliability`, `api-contract` | applicable; data-loss behavior and a persisted marker format change |
| U9, issue #843 parked state | 6 | `reliability`, `adversarial` | applicable; recovery sequencing and hostile remote-state changes |
| U10, issue #844 remote cleanup | 6 | `reliability`, `adversarial` | applicable; destructive readback and wrong-branch attempts |
| U11, issue #828 deferred import | 4 | none | proportional; one import moves without a framework |
| U12, issue #829 test-root pattern | 4 | none | proportional; two test constants establish the pattern |
| U13, issue #822 script-root adoption | 4 | none | proportional; one script adopts issue #829's pattern |
| U14, issue #830 validator agreement | 4 | none | proportional; one test module only |
| U15, issue #818 stale paths | 5 | `documentation-clarity` | applicable; six operator-facing invocations change |
| U16, issue #819 alias clause | 5 | `documentation-clarity` | applicable; the defect is two misleading sentences |
| U17, issue #820 README row | 5 | `documentation-clarity` | applicable; one documented skill row and its guard |
| U18, issue #821 dead subcommand | 5 | `agent-usability` | applicable; an agent-operated command is removed |
| U19, issue #840 backend offers | 6 | `documentation-clarity`, `agent-usability` | applicable; ten agent-facing offer surfaces must agree |

## Assignment audit

Every vendor, model, effort, workspace, and capacity below matches issue #847 and its preflight
receipt. The review mechanism comes from the binding launch clarification: the pinned Orchestrate
controller and reviewer-seat transport, with no substitution.

| responsibility | vendor | model | effort or variant | capacity | workspace |
| --- | --- | --- | --- | ---: | --- |
| planning | `claude` | Fable 5 | `xhigh` | 1 | `847-lane-plan` |
| plan and document review | `codex` | `gpt-5.6-sol` | `max` | 1 | `847-lane-plan` |
| work pool 1 | `agy` | `gemini-3.7-flash-high` | `high` | 4 | per lane |
| work pool 2 | `opencode` | `opencode-go/muse-spark-1.2-contributor` | `xhigh` | 4 replacement slots | per lane |
| work pool 3 | `opencode` | `opencode/muse-spark-1.2-contributor-free` | `xhigh` | on demand, replacement only | per lane |
| Saga Code Review controller | `grok` | `grok-4.6` | `xhigh` | exactly 1 | `847-lane-review` |
| Saga Code Review seats | `grok` | `grok-4.6` | `xhigh` | at most 6 live | `847-lane-review` |

The global implementation ceiling is four active workers. Pool 2 and pool 3 are fallback capacity
for a seat that pool 1 cannot fill; their recorded caps do not add workers. OpenCode receives the
recorded `xhigh` variant through the pinned launcher's in-session `/variants` selection and
readback, not through an invented command-line option.

## Dependency and ownership audit

Each row's paths were compared one-for-one with the child card and issue #847 collision table. The
path count is included to make accidental directory-wide admission visible. `none` means an empty
array in the expand JSON, not an inferred dependency.

| plan unit | lane | path result | `after` | `serialize` |
| --- | --- | --- | --- | --- |
| U1, issue #842 | Guards | exact, 2 paths | none | none |
| U2, issue #838 | Guards | exact, 6 paths | none | none |
| U3, issue #846 | Stability | exact, 2 paths | none | none |
| U4, issue #839 | Stability | exact, 2 paths | none | none |
| U5, issue #841 | Orchestrate | exact, 6 paths | none | none |
| U6, issue #848 | Orchestrate | exact, 8 paths | none | U5 |
| U7, issue #837 | Orchestrate | exact, 5 paths | none | U6 |
| U8, issue #845 | Orchestrate | exact, 7 paths | none | U7 |
| U9, issue #843 | Orchestrate | exact, 7 paths | none | U8 |
| U10, issue #844 | Orchestrate | exact, 6 paths | none | U9 |
| U11, issue #828 | Mission Control | exact, 5 paths | none | none |
| U12, issue #829 | Mission Control | exact, 2 paths | none | U11 |
| U13, issue #822 | Mission Control | exact, 5 paths | U12 | none |
| U14, issue #830 | Mission Control | exact, 1 path | none | U13 |
| U15, issue #818 | Mission Control | exact, 9 paths | none | U14 |
| U16, issue #819 | Mission Control | exact, 4 paths | none | U15 |
| U17, issue #820 | Mission Control | exact, 5 paths | none | U16 |
| U18, issue #821 | Mission Control | exact, 7 paths | none | U17 |
| U19, issue #840 | Saga | exact, 17 paths | none | none |

No implementation unit uses a plugin directory as a routing path. Orchestrate code is exclusive to
Lane O, Mission Control code is exclusive to Lane M, and Saga code is exclusive to Lane A. The
root marketplace registry and routine engineering-journal append are the shared surfaces recorded
by issue #847, not files owned by another lane. Existing journal-citation repair belongs to the
Guards lane; the exact backend decision amendment belongs to the Saga lane.

## Disposition ledger

| Finding | Valid? | Evidence | Repair or rejection rationale | Verification |
| --- | --- | --- | --- | --- |
| F1 (P1) — The original one-shot pool-1 expand block could not apply the recorded fallback route after expansion and incorrectly proposed omitting OpenCode effort. | Yes | Issue #847 decisions D5–D8 fix pool priority and exact effort. The pinned driver persists route fields at `expand`; the pinned launcher selects `unit.effort` through `/variants`. | Replaced one-shot expansion with eligible-row subsets and just-in-time exact pool materialization. Kept `xhigh` for both OpenCode routes and prohibited migration or substitution. | All nineteen rows pass the pinned driver's schema and vendor checks. Simulated pool 2 and pool 3 rows preserve their exact model and `xhigh` effort. |
| F2 (P1) — Plain worker task text would bypass vendor-aware Saga invocation, and Saga Work could launch a duplicate self-review. | Yes | The pinned driver's task normalizer rewrites only tasks beginning `/saga:*` or `$saga:*`. This run has one separate Code Review controller, so Work must not start another review. | Made every task start `/saga:work` and explicitly skip Saga Work Phase 5 self-review, Code Review calls, and override prompts. | Structural check confirms 19 of 19 tasks have the invocation and suppression clauses. |
| F3 (P1) — `serialize` alone releases a Lane O or Lane M successor when its worker is done, before review, merge, CI, and worktree cleanup. | Yes | Pinned-driver eligibility is based on predecessor unit status, while issue #847's collision contract permits only one lane worktree and records merge ordering. | Kept every recorded edge unchanged and delayed successor expansion until the predecessor is reviewed, merged, green, and cleaned. | Exact edge-map check passes; the added gate is coordinator policy and adds no `after` or `serialize` edge. |
| F4 (P1) — Directory-wide plugin paths admitted files outside child ownership and could overlap another unit in the same lane. | Yes | Issue #847 supplies an exact collision table. Original rows used `plugins/orchestrate`, `plugins/mission-control`, or `plugins/saga` directories. | Replaced every broad directory with exact child-card files and exact release surfaces. | Structural scan finds no plugin-directory routing path; all nineteen path lists match the reviewed card mapping. |
| F5 (P1) — Mission Control unit U14 for issue #830 could edit guidance and bump release metadata even though ruling C1 makes it a test-only local agreement guard. | Yes | Issue #830 and issue #847 ruling C1 require a dynamic agreement test, a module docstring, and a loud local-only skip; they prohibit CI coupling and do not authorize a guidance change. | Reduced U14 to `plugins/mission-control/tests/test_card_validator_agreement.py` and explicitly prohibited `flow/SKILL.md` and release-surface edits. | U14 has exactly one path and the run-level release classification excludes it. |
| F6 (P1) — The review assignment lacked an executable dispatch, typed-result custody, and reviewed-commit freshness rule. | Yes | Issue #847 decisions D10–D12 record Grok 4.6, `xhigh`, six sessions, predeclared lenses, and the Saga acceptance policy. The binding launch clarification assigns transport and custody to the pinned Orchestrate controller. | Added the exact controller and reviewer-seat `expand`/`go` templates, `review_result.v1` collection through `review-result`, frozen-commit comparison, and same-lens re-review after repairs. | Controller, seat, workspace, model, effort, cap, result command, and freshness clauses are present and load through the pinned driver. |
| F7 (P2) — Several lens sets did not reflect the installed roster's always-on floor or the unit's named conditional trigger. | Yes | `plugins/saga/references/lens-roster.json` requires four always-on lenses. Issue #847 decision D11 permits only applicable conditionals, one-line reasons, and at most six. | Corrected all sets; added only the warranted adversarial, reliability, API-contract, documentation, or agent-usability lens and restored a missing always-on lens. | Parser check finds nineteen declarations, all four always-on IDs in each, matching stated counts, and a maximum of six. The audit table above records every conditional. |
| F8 (P2) — Stability unit U4 for issue #839 allowed a discovery sweep to add an undeclared file and did not carry the required terminal-width matrix. | Yes | Grounding of direct multiword raw-help assertions found the two child-named tests; other help tests are exit-only, normalized, or single-token. | Kept the two declared test files, added the `COLUMNS` width matrix, and made a new out-of-list hit a stop-and-replan condition. | Both files pass at widths 40, 60, 70, 75, 80, 90, 100, 105, 107, 110, 120, and 200. |
| F9 (P2) — Saga unit U19 for issue #840 listed `tests/test_saga_workflow_emitter.py` as editable even though the child uses it only as verification evidence. | Yes | Issue #840's owned-file list excludes that test while its verification block names it. | Removed it from owned paths and said it is verification-only. | U19's exact 17-path JSON list contains no workflow-emitter test. |
| F10 (P2) — Two open questions would halt an unattended run even though neither required a prompt. | Yes | The binding launch clarification fixes typed Orchestrate review transport; issue #847 records the three worker pools, and the operator required known-set choices to be taken without prompting. | Recorded the required controller, reviewer-seat, and `review-result` transport plus the pinned-driver OpenCode fallback with `xhigh`; removed the question section. | The plan has a `Recorded unattended choices` section, identifies review transport as binding rather than chosen, and has no open-question heading. |
| F11 (P2) — The topology omitted the already-recorded planning and document-review assignments. | Yes | Issue #847's roster records Claude Fable 5 at `xhigh` for planning and Codex `gpt-5.6-sol` at `max` for this document review. | Added both control-phase rows without changing the worker or review pools. | Assignment table matches the issue and preflight receipt field for field. |
| F12 (P2) — Release guidance did not distinguish test-only units from the thirteen behavior or guidance units and left release-path wording open to inference. | Yes | Repository rules require release surfaces for behavior, schema, command, prompt, or guidance changes; issues #829 and #830 are test-only. | Named the thirteen release-bumping units and expanded each plugin's exact three release surfaces. | JSON path audit includes release paths only on the recorded behavior or guidance units. |
| F13 (P3) — The plan described the operator-decision audit as though it covered all current children, but issue #848 was created later. | Yes | The audit comment is dated 2026-08-26T01:34:12Z; issue #848 was created at 2026-08-26T02:10:54Z. | Disclosed the then-eighteen-child scope and made issue #848 plus the updated parent contract U6's direct authority. | The authoritative-input section now states the chronology and U6 remains one of the nineteen validated rows. |
| F14 (P0) — The repaired plan launched and settled reviews outside the required Orchestrate controller, omitted sanctioned reviewer seats, and replaced typed `review-result` custody with a parallel result path. | Yes | The pinned driver defines `review-controller` and `external-reviewer` separately, caps only controllers at one, directs seats through `expand`/`go`, and persists `review_result.v1` through `review-result`. All nineteen Work rows have non-null roles, so issue #837's role-less review-prose classifier cannot reach them. The binding launch clarification prohibits reproducing review lifecycle transitions outside the driver. | Replaced the direct `agents` command and pull-request result recording with one Grok controller, batches of at most six live Grok reviewer seats, and exact-byte `review-result` collection. Preserved every model, effort, lens set, lane, edge, path, pool, and Work role. | The pinned driver's `plan_units()` loads the unchanged nineteen implementation rows plus one controller and six materialized seats: 26 units, exactly one controller, six seats, and zero standalone-review classifications among Work rows. |
| R1 — The plan redesigns Lane O or Lane M dependencies. | No | The final edge map is O1 → O1a → O2 → O3 → O4 → O5 and M1 → M2 → M2a → M3 → M4 → M5 → M6 → M7, exactly as issue #847 records. | Rejected. The coordinator's reviewed-and-merged gate compensates for pinned-driver timing; it does not add an edge. | Exact `after` and `serialize` map comparison passes. |
| R2 — Issue #822 can begin independently of issue #829 or invent its own root pattern. | No | U13 has `after: ["847-m2-829"]`; the dispatch protocol withholds expansion until the merged pattern is read and cited. | Rejected. The content prerequisite and verbatim adoption rule are explicit. | JSON and task-text checks both confirm issue #829 precedes issue #822. |
| R3 — A unit proposes a prohibited general framework or replacement capability. | No | Each child non-goal was checked. The plan's scope boundary bans the package manager, recovery engine, provenance framework, documentation generator, replacement launcher, backend abstraction, and rollout replacement. | Rejected. Narrow state additions in issues #843 and #844 are the child-authorized repairs, not general recovery or provenance systems. | Task scan and unit readback find the prohibited mechanisms only in negative instructions. |
| R4 — Four always-on lenses on a small unit are mechanical overassignment. | No | The installed Saga roster mandates those four on every review; issue #847 decision D11 governs only which conditional lenses earn additional seats. | Rejected. Units U4 and U11–U14 stay at four instead of receiving six mechanically. | Lens parser confirms four on those small units and no unit above six. |
| R5 — The shared journal or marketplace file gives one lane a file owned by another lane. | No | Issue #847 records routine journal appends and the root marketplace registry as shared collision surfaces with merge and re-resolution rules. It separately assigns existing citation repair to G2 and the named backend decision amendment to A1. | Rejected. These are explicit shared exceptions, not cross-lane acquisition of exclusive code. | Exact paths and the single-merge coordinator policy preserve the recorded ownership. |
| R6 — Selecting G1, G2, S1, and S2 for the first four seats adds dependency edges or reassigns lanes. | No | Issue #847 makes G1 and G2 the first merges and places S1/S2 immediately after them; O1, M1, and A1 remain eligible but queued under the four-worker cap. | Rejected. Dispatch priority consumes capacity but does not alter lane ownership or edge fields. | All seven lane heads remain dependency-eligible in JSON; only four are expanded initially. |
| R7 — Review rows must be added to the nineteen-unit expand payload. | Yes | Issue #847 fixes vendor, model, effort, concurrency, lenses, and acceptance but does not choose transport. The pinned driver's `assert_single_review_controller()` caps controllers only; `REVIEWER_SEAT_ROLE`, `assert_no_engine_prefs()`, and `assert_review_transport()` explicitly sanction named `external-reviewer` rows through `expand`/`go`. `is_standalone_review_prompt()` returns false for all nineteen non-null `review-fixer` roles, so issue #837 does not make this payload unloadable. The binding launch clarification requires the driver-owned route. | Accepted. Added exactly one `review-controller`, batched `external-reviewer` seats, and typed `review-result` collection; deleted the parallel direct-session lifecycle. | `plan_units()` loads 26 combined rows: nineteen implementation units, one controller, and six reviewer seats. |

## Decisions taken without asking

No real work question remains.

Review transport is not a decision taken by this review. The binding launch clarification requires
the typed Orchestrate controller, named reviewer seats, `expand`/`go`, and `review-result` route now
specified in the plan.

1. **Global worker ceiling:** four active implementation workers across all pools. This follows the
   explicit four-worker collision limit; fallback pool caps replace unavailable seats rather than
   adding seats.
2. **OpenCode effort:** materialize exact `effort: xhigh` and rely on the pinned launcher's verified
   `/variants` selection. Omitting the field would discard a recorded decision.
3. **Issue #830 scope:** one test file and no release bump. Its child contract and ruling C1 require
   a local agreement guard, not a guidance or packaging change.
4. **Issue #839 discovery:** the two card-owned test files remain the complete editable set. A new
   direct layout-sensitive assertion outside them stops for re-planning instead of silently widening
   ownership.

## Verification

- Parsed the canonical JSON: nineteen distinct rows and every required field present.
- Loaded the rows through the pinned Orchestrate driver: schema, dependency names, Saga invocation,
  and all three recorded vendor routes passed.
- Loaded the nineteen implementation rows plus one typed controller and six materialized reviewer
  seats through `plan_units()`: 26 units, exactly one controller, six seats, and no standalone Work
  review prompt.
- Compared the exact Lane O and Lane M `after` and `serialize` fields to issue #847: passed.
- Checked all task prefixes and external-review suppression clauses: 19 of 19 passed.
- Checked exact non-directory path routing and issue #830's one-test scope: passed.
- Parsed all nineteen lens declarations: stated counts match, the four always-on lenses are present,
  and the maximum is six.
- Ran the issue #839 focused test pair at all twelve required terminal widths: passed.
- Ran `git diff --check`: passed.

## Residual risk

The plan is grounded at `origin/main` `3ab04adb0644feecd5a81cade318dc1cce59b6a9`. Each worker must
fetch and re-anchor before editing, and release versions must be re-resolved at commit and merge.
The pinned launch routes were proved during preflight, but live capacity can still disappear; the
plan stops instead of substituting an unrecorded route. A newly discovered issue #839 file outside
the two declared tests also stops for re-planning. Those are runtime availability and source-drift
risks, not unresolved plan decisions.
