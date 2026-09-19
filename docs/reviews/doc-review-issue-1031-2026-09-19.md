# Document review — `/qa` testing-strategies specification (issue 1031)

Readiness verdict: **not blocked**. Four `P1` findings were raised and all four were repaired in place with evidence; no `P0` was found; three `P2`/`P3` findings remain and none of them prevents the specification from driving implementation.

## Review result contract

| Field | Value |
|---|---|
| Target path | `docs/specs/2026-09-19-qa-testing-strategies-spec.md` |
| Reviewed revision | `226ade5f` (the specification as committed), with the repairs below applied in the working tree and committed together with this artifact |
| Blocked status | not blocked |
| Rubric phase | spec — the four always-apply core rubrics, plus two conditional extras that fire |
| Rounds | two (repairs applied after round one; round two found no new `P0` or `P1`) |
| Review artifact | `docs/reviews/doc-review-issue-1031-2026-09-19.md` |
| Linked issue | 1031 (the exploration), 1039 (the implementing capability card), 1018 (the parent) |
| Linked documents | `docs/brainstorms/2026-09-19-qa-testing-strategies-requirements.md` |
| Override rationale | none — no override was used |

## Rubrics applied

Run through the shipped engine at `plugins/saga/scripts/lifecycle_review.py`, phase `spec`.

| Rubric | Class | Applied | Why |
|---|---|---|---|
| `acceptance_testability` | core | yes | always applies |
| `blueprint_fidelity` | core | yes | always applies |
| `devils_advocate_spec` | core | yes | always applies |
| `outcome_clarity` | core | yes | always applies |
| `dependency_mapping` | extra | yes | the specification is multi-criterion and multi-area, and four sibling cards are in flight |
| `scope_unity` | extra | yes | sixteen criteria over ten strategies is exactly the shape the rubric screens |
| `measurement_plan` | extra | no | the change ships no metric or experiment to measure; the outcome condition added under `outcome_clarity` is read from the run record, not from an instrumentation plan |
| `ramp_down_criteria` | extra | no | nothing is ramped or rolled out by cohort |

An honest limitation, recorded rather than hidden: the same session that wrote this specification reviewed it. That is weaker than an independent reviewer, and the findings below should be read with that discount. A cross-family external panel was not dispatched, because the skill makes it opt-in and the operator did not ask for one.

## Applied fixes

All five edits are evidence-backed by the specification itself, the brainstorm it descends from, or this repository's own rules.

| Fix | What changed | Evidence |
|---|---|---|
| F1 | The `Context` section now states the outcome as an observable condition — for every `pass` verdict the count of required strategies equals the count of `passed` envelopes, and a non-zero count of `blocked` envelopes over the first month — rather than as an output ("we will ship a catalogue") | `outcome_clarity`; the condition is read from the run record the specification already defines |
| F2 | The repository-profile paragraph now states that a profile must mark at least one strategy required, and that an all-optional profile or a missing profile is a `blocked` run naming the profile path | `devils_advocate_spec` cheapest-defeat scan; the "no silent skip" principle the specification already carries |
| F3 | The judgment section now states that the act band is declared data in the catalogue file, ships provisional in suggest mode, and is set by the evaluation harness of issue 1032 — the implementer does not invent it. Criterion 3 now reads the band from that declaration rather than from a literal in the test | TypeSafe research house rules 2 and 10: three bands per decision, thresholds from the harness, suggest-first |
| F4 | Criterion 11's string search is scoped to `plugins/saga/skills/qa/` and `plugins/saga/scripts/`, with the changelog entry explicitly outside it | This repository's rule that every behavior change updates `plugins/<plugin>/CHANGELOG.md` — the criterion as written would have failed on the very entry recording the removal |
| F5 | Two criteria added (now 14 and 15): an all-optional or missing profile yields `blocked`; and one end-to-end run against this repository's own profile yields `pass` with at least two strategies `passed`, one published comment, and the verdict in the run record. The file-reference table's count and the critical-path naming in `Related` were corrected with them | `devils_advocate_spec` worst-version test and `dependency_mapping`; both criteria fill in behavior the `Proposed Change` section already requires, rather than inventing new behavior |

## Findings

| ID | Priority | Finding | Status |
|---|---|---|---|
| D1 | P1 | The worst version of this specification that satisfies every criterion is one where every driver returns `blocked` for every repository: the verdict machinery works and nothing is ever proved. No criterion required a single real `pass` | fixed by F5 (criterion 15) |
| D2 | P1 | A repository profile could mark every strategy optional, so a run with zero required strategies would report `pass` having proved nothing — the cheapest possible defeat of the whole design | fixed by F2 and F5 (criterion 14) |
| D3 | P1 | Criterion 3 and the judgment section referred to an "act band" that the document never defined and never said who sets. An implementer would have invented a threshold, which the TypeSafe house rules forbid | fixed by F3 |
| D4 | P1 | Criterion 11 forbade the string "health score" anywhere under `plugins/saga/`, which would have failed against the changelog entry this repository requires for the removal — a criterion that cannot be satisfied alongside the repository's own rule | fixed by F4 |
| D5 | P2 | The outcome was stated as an output (a catalogue gets built) rather than as a condition that tells you whether shipping helped | fixed by F1 |
| D6 | P2 | No criterion covered the success path end to end — the published comment and the run-record write on `pass` were described in `Proposed Change` and asserted nowhere | fixed by F5 (criterion 15) |
| D7 | P3 | The dependency list named three upstream cards and one lateral one but did not say which is on the critical path | fixed by F5 (the `Related` entry for issue 1028) |
| D8 | P3 | The filed capability card 1039's `Inputs inventory` says the specification carries "the fourteen acceptance criteria"; after this review it carries sixteen. The card body is now stale by two | open — left for the coordinator, since the instruction for this turn was to leave card 1039 alone |
| D9 | P3 | The specification defers the `data-check` driver although the simplification review's R30 names data checks among the strategies. The deferral is stated in `Scope Boundaries` with its reason, so this is named drift, not silent drift, which the `blueprint_fidelity` rubric permits | open — accepted as named drift |
| D10 | P3 | Effort is quantified in implementer-sessions with two honest unknowns (Flutter toolchain time, the canary's command-line stability). Sessions are not a calibrated unit in this repository | open — accepted; the rubric asks for a quantified estimate with its measurement method, and both unknowns name theirs |

## Readiness summary

The specification can drive implementation without the implementer inventing decisions. Its current-state section is verified against shipped files with line ranges rather than asserted; its strategy catalogue names a tool per situation and a repository family per strategy; its evidence shape and three-value result type are taken from a schema that thirty real scenarios already exercise; and after the repairs its criteria can no longer be satisfied by a run that proves nothing.

The scope-unity rubric finds one specification, not several: every criterion serves the single outcome of a functional test that reports what it proved, and the named MVP cut is a coherent subset rather than a second specification in disguise. The blueprint-fidelity rubric finds a named source (the brainstorm, and R6, R21, and R30 of the simplification review), aligned decisions, and one named deferral (D9).

## Residual risk from limited evidence

Three things this review could not verify and did not claim. Whether the CAMPPS end-to-end canary is currently green in use — the specification says the implementing card should read its last run before adopting its thresholds, and that remains the right instruction. Whether the canary's command-line interface is stable enough to depend on — named as an unknown in the effort section with its measurement method. And whether the Flutter integration-test toolchain runs cleanly from a cold worktree on this machine — likewise named, not assumed.
