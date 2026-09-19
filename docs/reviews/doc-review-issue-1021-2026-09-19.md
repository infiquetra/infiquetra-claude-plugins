# Document Review — one staffing component in fleet-core, issue 1021

**The plan was not ready on its first draft and is ready now.** A first adversarial pass found
thirteen problems, one of which would have taken the saga plugin's plan-save contract down at
runtime. All thirteen were repaired, and a second independent pass confirmed twelve of them,
called one partial on a wording detail, and raised eight further problems — two of medium priority
and six of low. Those were repaired too. No blocking finding remains.

## Review-result contract

| Field | Value |
|---|---|
| Target path | `docs/plans/2026-09-19-issue-1021-staffing-component-plan.md` |
| Reviewed revision | working tree on branch `issue/1021`, based on commit `2044c363` |
| Classification | Plan document — the `docs/plans/` path tie-breaker, and every plan content signal is present (`Implementation Units`, `Key Technical Decisions`, `U1`, file lists, test scenarios, verification) |
| Rubric phase run | `issue` — the document is derived from GitHub issue 1021 |
| Rubrics applied | Core: `acceptance_criteria_clarity`, `devils_advocate_issue`, `spec_fidelity`. Extras, all three judged applicable: `context_completeness`, `issue_sizing`, `prerequisite_mapping` |
| Blocked status | **Not blocking.** No P0 or P1 finding remains after two rounds |
| Review rounds | Two. Round one raised thirteen findings; round two confirmed the repairs and raised eight more, none above P2 |
| Applied fixes | All twenty-one findings repaired in the document; see below |
| Review artifact path | `docs/reviews/doc-review-issue-1021-2026-09-19.md` |
| Linked issue | 1021, a sub-issue of the saga simplification parent 1018 |

## What the rubrics found

The three core issue rubrics produced three repairs, applied before the adversarial pass.

**Acceptance criteria clarity.** The plan carried the card's four acceptance criteria only
implicitly, scattered across requirements and test scenarios. Repaired by adding an
acceptance-criteria trace table mapping each card criterion to its requirement, its unit, and the
scenario that proves it.

**Prerequisite mapping.** The plan named the sibling cards in prose but never said plainly that
nothing blocks this one. Repaired by adding a prerequisites-and-downstream section naming the three
cards that consume the component and the two that follow it.

**Issue sizing.** The plan names about twenty-seven distinct files across two plugins and mixes a data
consolidation with four units of new behavior, which is above the typical single pull request.
Repaired by stating the size, the reason it is not split (the card's central requirement is *one*
data file, so the consolidation and its reader cannot ship in separate releases), and where the
clean cut is if the pull request has to be split anyway.

`spec_fidelity`, `devils_advocate_issue`, and `context_completeness` found nothing to repair: the
plan cites its parent objective document and recommendation R29, inherits the card's non-goals
verbatim, and names repository-relative paths with line numbers throughout.

## Findings and their repairs

All findings are resolved. Priorities are the ones assigned when each was raised.

| # | Priority | Finding | Status |
|---|---|---|---|
| 1 | P0 | Deleting `effort-convention.md` trips a runtime existence gate — `plan_save_contract.py` holds its path in a constant and checks the file exists, so every `load()` would raise | Repaired |
| 2 | P1 | The claim "only four Python modules read the two data files by path" was wrong; four test modules also read them, two of which appeared in no unit's file list | Repaired |
| 3 | P1 | `opencode` is a launcher vendor but not a resolver runtime, and the plan left that contradiction for the implementer to invent a decision about | Repaired |
| 4 | P1 | The card asserts the command prints `opus/high`, and its verification block runs `explain --lens`; the plan specified neither | Repaired |
| 5 | P2 | Two units modified `staffing.py` without depending on the unit that creates it | Repaired |
| 6 | P2 | The generated tier-table marker in the plan skill names the deleted data file in a string literal, guarded by three tests | Repaired |
| 7 | P2 | The onboarding guard asserts four things about the reference document; the plan carried one forward | Repaired |
| 8 | P2 | No unit updated the engineering journal, which this repository requires in the shipping commit | Repaired |
| 9 | P2 | The per-repository tier overlay was called "committed"; it is gitignored and untracked here | Repaired |
| 10 | P2 | Three surviving comments name the deleted reference documents and were covered only by a blanket sentence | Repaired |
| 11 | P3 | `tier_resolver.py:430` was described as the command-line entry point; it is a subcommand handler | Repaired |
| 12 | P3 | `plugins/fleet-core/README.md` was listed for modification with no stated motive | Repaired |
| 13 | P3 | The "61 files and 19 test files" count was unattributed | Repaired |

### What the second round added

Round two re-checked every repair against the repository and confirmed twelve outright. It called
the module-count repair partial — the plan said "three production modules" where the truth is two
modules holding three path constants — and that wording is now corrected in both the plan and the
journal entry.

It then raised eight further problems, all repaired:

| # | Priority | Finding | Status |
|---|---|---|---|
| 14 | P2 | A vendor-palette test scenario required an accepted-effort list for every launcher vendor, which would have forced the implementer to invent the `opencode` effort list the opencode decision expressly refuses to invent | Repaired — the effort half is scoped to supported runtimes |
| 15 | P2 | The "no file still links to the deleted documents" check excluded too little: five live files outside the exclusion name them, so the check could never pass without rewriting historical records | Repaired — the check is scoped to plugin scripts, skills, references, and tests |
| 16 | P3 | The decision count said nine; there are eleven, and the journal's reference line stopped at the tenth | Repaired |
| 17 | P3 | The file count said roughly sixteen; the unit file lists name about twenty-seven | Repaired |
| 18 | P3 | The engine-registry consumer count said "more than twenty scripts"; it is thirteen scripts and twenty-two files | Repaired |
| 19 | P3 | The `hermes` exclusion test asserted an absence, which would keep passing after `hermes` was added | Repaired — the forcing function is now a set comparison against the launcher's vendor table |
| 20 | P3 | Two citation errors: a module line number, and calling this repository's own plan skill "installed" when two divergent installed trees exist | Repaired |
| 21 | P3 | The claim that the first unit is a clean cut omitted that it leaves the old reference document describing a deleted file, with the guard test passing *because* the document is stale | Repaired — the cut now carries that body edit |

### The three repairs worth reading

**The runtime gate.** `plugins/saga/scripts/plan_save_contract.py:36` holds
`plugins/fleet-core/references/effort-convention.md` in an `EFFORT_REFERENCE` constant, and `:217`
checks the file exists and fails when it does not. Deleting the document without repointing the
constant would make every `plan_save_contract.load()` raise, and
`tests/test_saga_spec_consumer_row.py:72` copies the same path into its fixture tree, so that whole
suite would die too. The plan now names the constant, the check, and the four files that ride on it,
and adds an error-path scenario that calls `load()` after the deletion.

**The opencode decision, recorded as KTD11.** The launcher's `VENDOR_FLAGS` names seven vendors;
`tier_resolver.SUPPORTED_RUNTIMES` knows six. The plan now gives `opencode` a palette row carrying
`runtime_supported: false`, with the reason in the row — nobody has verified its launch-time model
and effort arguments, and its model identifier must be in `provider/model` form, which no other
vendor requires. `SUPPORTED_RUNTIMES` derives from the rows whose flag is true, so launch behavior
is unchanged, and a test pins the flag so promoting `opencode` later is a deliberate edit.

**The overlay is not committed here.** The card, the review document, and the installed plan skill
all describe `.saga/tier-defaults.json` as tracked. `.gitignore:70` ignores `.saga/` outright, and
there is no overlay file in this worktree at all. The plan's wording is corrected, and the
discrepancy is recorded as an open question rather than resolved: narrowing a repository-wide
ignore rule is a policy change this card has no mandate to make, and the implementer is told not to
edit `.gitignore`.

## Readiness summary

The plan can drive implementation. An unfamiliar agent has repository-relative paths with line
numbers for every claim it needs to act on, eleven decisions with their rejected alternatives, six
dependency-ordered units each carrying its own test scenarios and test-file paths, and a trace from
each of the card's acceptance criteria to the scenario that proves it.

Two things it deliberately does not settle, both recorded rather than guessed: whether the
per-repository tier overlay should be tracked in this repository, and when `opencode` should become
a supported runtime. Neither blocks the work; the first is a repository policy question for the
operator, and the second is answered conservatively by preserving today's behavior.

**The one open question that needs the operator.** The card, the simplification review, and this
repository's own copy of the plan skill all call `.saga/tier-defaults.json` a committed, tracked
file. `.gitignore:70` ignores `.saga/` outright. Whether to narrow that ignore rule is a decision
this card has no mandate to take, so the plan records it and forbids the implementer from editing
`.gitignore`.

## Residual risk from limited evidence

The card's acceptance criteria and the executor-verification ledger were read from the sibling
`infiquetra-sdlc` checkout at `~/workspace/infiquetra/infiquetra-sdlc`, whose freshness against its
own remote was not checked in this session. The ledger's `entries` array is empty and its own note
says that is deliberate, so a stale checkout would change nothing the plan depends on — but a
qualification recorded upstream since the last fetch would not be visible here.
