# Work session — issue 1026, plan continues into plan review

**Branch:** `issue/1026`, from `parent/1018` at `4e951f0e`. **Release:** saga 0.165.0,
cc-workflows 1.0.1, fleet-core 0.28.1. **Destination:** `pr` — this card merges onto the
integration branch and opens no pull request of its own; the parent pull request (issue 1030)
carries one code review for the whole parent.

## What shipped

Nine units, as planned, with one addition the implementation found (see "What the plan got wrong").

| Unit | What | Card |
|---|---|---|
| U1 | The Claude Code Workflow and team-execution prose moved to `plugins/saga/references/workflow-backend.md` (515 lines). `/plan` ends at 728 lines against 772, `/work` at 864 against 1,142, after U2's Phase 5.4 and U4's §1.3 added their own text back. The per-unit tier derivation stayed in `/plan` as §5.2a — see "What the full suite caught" | 808, 1026 |
| U2 | `/plan` Phase 5.4 dispatches the plan review and loops on repair; the Ready-for-Active board move follows it as §5.5 | 1026, 933 |
| U3 | `/doc-review` carries the loop contract, the cycle definition, and reviews a submitted path as given | 933 |
| U4 | `/work` §1.3 keeps refusing, now with a gate-record marker and a named evidence order | 933, 1026 |
| U5 | The rubric command resolves from any working directory and fails loud; `--doc-review-fixes` exists and is forwarded | 932 |
| U6 | The operator-is-the-transport clause, the general prohibition, the repaired cross-reference, the retired panel dispatch | 931 |
| U7 | The never-written `review` phase, the artifact-matching conventions, the default-mode wording, the commit SHA | 934 |
| U8 | `team_emitter.py` and `spec_table.py` removed with their tests and every reference repaired | 1026 |
| U9 | Release surfaces for saga, plus cc-workflows and fleet-core, which the diff guard correctly demanded | 1026 |

## Decisions taken from the coordinator, recorded with their source

Every choice the `/work` skill would have put to an operator was answered up front by the
coordinator's stage-two message, which is the source for each row.

| Question | Answer taken |
|---|---|
| Saga | Resumed `issue-1026` in this worktree's store; no second saga minted |
| Branch | Stayed on `issue/1026` |
| Execution backend | `inline`, as the plan's `backend:` frontmatter records; no other backend offered or entered |
| Doc-review gate | Passed, nothing above P3 open (`docs/reviews/doc-review-issue-1026-2026-09-19.md`); no override needed or permitted |
| Complexity triage | The documented default: fresh build, not a round-N continuation |
| Ship ceremony start | Declined — it opens a draft pull request and this card opens none |
| Code review | None in this stage, by operator decision on 2026-09-19 |
| `execution_spec.py` | Stays on this card; issue 1030 deletes it. The second acceptance criterion is judged at the parent pull request |
| Card 931's `code-review/SKILL.md` line | Taken: the minimal edit that makes the cross-file agreement test pass, and nothing else in that directory |

**Board moves submitted, both landing with `field: Stage+Status`:** `Active` / `Implementing` at
the start of the work (`written`), and earlier in the planning stage `Planning` / `Designing` and
`Planning` / `Ready for Active` (both `written`).

## The acceptance run

The card's fourth criterion asks for a real `/plan issue <N>` run ending in a plan-review pass or a
named `P0`/`P1` without the operator typing `/doc-review`. **The installed saga is 0.159.2 and does
not carry the new Phase 5.4, so it cannot run the new text** — the proof is this branch's own
`plugins/saga/skills/plan/SKILL.md` executed in-thread for issue 1026, with board moves and issue
comments suppressed and every output written to the session scratchpad.

**Hand-off point**, quoted from the file executed:

> **`/plan` does not recommend the review; it runs it.** [...] **Who reviews, decided from the run
> record and not from this session.** Read the run record at
> `<primary checkout>/.claude/saga/runs/issue-<N>.json` and take the first of these that holds:

No operator command appears between the plan document being written and the review starting.

**Branch taken: 3, this session in review-only mode.** Branch 1 did not hold (`roster` is `[]`).
Branch 2 did not hold, and for a reason worth the rollout note: the staffing plan does name
`plan-reviewer` at `claude`/`opus`/`high`, but no installed `roster.py` exists on this host — the
installed agent-launcher is 1.5.2, whose `skills/agent-launcher/scripts/` holds only `composer.py`
and `launcher.py`. The helper ships at 1.7.0 (issue 1024), which is on `parent/1018` and not
installed. **The roster-pane branch becomes reachable only once agent-launcher 1.7.0 is installed
in both plugin trees**, and the release note should say so.

**Verdict: pass, cycle 1 of an allowance of 3**, bound to revision `0711c076`. Three findings, all
`P2`/`P3`, all against the plan's inventories rather than its decisions, and all already discharged
by the implementation. No operator override was asked for or given, and the allowance was not
exhausted.

## What the plan got wrong, and how the tests caught it

Three inventory failures, each surfaced by a guard rather than at runtime:

1. **`spec_table.py` had four callers, not one.** The plan named `work/SKILL.md:400`. The
   four-syntax scan found `plugins/cc-workflows/skills/cc-workflows/SKILL.md:88`,
   `plugins/saga/commands/tier.md:50` and `plugins/saga/skills/outcome/SKILL.md:165`, each a
   command line telling an agent to run the script. All three now describe building the approval
   table from the spec.
2. **`team_emitter.py` was named in six more places**, all stale prose describing a module that
   would no longer exist. All repaired.
3. **The silent rubric degradation went one layer deeper than card 932 described.**
   `lifecycle_review.py`'s `rubrics list-cores` and `list-extras` exited 0 printing nothing when
   the rubric library was absent, so a reviewer read "no rubrics apply" for a broken install. The
   `read` subcommand had always failed loud, which is why it survived. Both listings now raise.

A fourth was found by the targeted run: `tests/test_saga_plugin.py` asserted the *path string*
`../code-review/references/findings-schema.md`, which is exactly the defect card 931 names. Removing
the dangling reference reddened it, and it is replaced by a guard that resolves the target and reads
it.

## What the full suite caught that the targeted runs could not

Two more guards named the moved section from files I had not thought to run, and both are the same
shape: a test that pins content in `plan/SKILL.md` while living somewhere unrelated.

1. **`tests/test_operator_choice_drift.py`** pins that `/plan`'s offer surface names both §3.2
   purposes and frames the team-versus-Workflow fork on governance. The offer moved, so the guard
   followed it to `references/workflow-backend.md` — the contract is the purposes and the framing,
   not the file.
2. **`tests/test_saga_spec_consumer_row.py`** failed because the `GENERATED EFFORT HONORING NOTE`
   marker pair moved out of the file its renderer targets. `plan_save_contract.py` renders that note
   *and* the §5.3 save examples against one `SKILL` constant, so the note could not move without
   teaching that generator a second target document.

That second one changed the design, not just a constant: **the per-unit tier derivation came back
to `/plan` as §5.2a**, no longer gated on the Workflow backend, taking both generated regions with
it. It reads better there anyway — the effort note covers the `agent`, `external-engine` and
`workflow` spawn kinds alike, so it was never Workflow-only in substance. Only the spend guards,
the authoring steps and the spec naming stayed in the reference file, and the tier-table drift
guard and its renderer docstring were reverted to name `plan/SKILL.md` again.

**The rule this earns:** after moving a section that contains a generated region or a marker pair,
run the full suite before believing the move is finished. A targeted run over the files you edited
cannot see a guard that names the file you edited from somewhere else.

## Proof

**Twenty-one guards, each watched failing on its own mutation and passing when restored.** The
mutation reverts the change the guard was written for — not a cosmetic edit near it — and the
harness restores the file and re-runs before reporting. Two guards were rewritten after surviving
their first mutation: the evidence-order case now parses the numbered list rather than searching for
three substrings, and the explicit-invocation case is scoped to the section where the backend is
actually chosen.

**Inner loop at the merged head:** `ruff check` clean, `ruff format --check` clean (565 files),
`mypy plugins/ scripts/ tests/` clean (378 source files), `check_release_surface_parity` in parity,
`sync_marketplace --check` matching, the marketplace validator passing with 0 errors,
`lint_journal_order --base-ref origin/parent/1018` with 0 violations, `changelog_heading_lint`
canonical, `plan_artifact_conformance` exit 0, `lint_gate_absence_contract` (as CI runs it) 0
violations, and `release_surface_diff_guard --base-ref origin/parent/1018` reporting all changed
plugins bumped.

**The card's runnable criteria:** `grep -c -i "workflow backend" plugins/saga/skills/plan/SKILL.md`
prints `0` and `plugins/saga/references/workflow-backend.md` exists. Worth saying plainly: that grep
printed `0` on the base too, so the criterion as worded passes vacuously — the real guard asserts the
*section* is gone (`test_no_workflow_backend_section_survives_in_the_plan_skill`), which the mutation
proof confirms fails when the section returns.

## Gate-absence baseline

The ratchet in `plugins/saga/scripts/gate_absence_baseline.json` shrank `plan/SKILL.md` from 6
uncovered sites to 5 and added `references/workflow-backend.md` at 1. The site moved with its
section; it was not forgiven.
