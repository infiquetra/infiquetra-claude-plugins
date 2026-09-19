# Doc review — the mission-control triage-suggestions plan (issue 1035)

## Review result

| Field | Value |
|---|---|
| Target | `docs/plans/2026-09-19-mission-control-triage-suggestions-plan.md` |
| Reviewed revision | working tree on branch `issue/1035`, base commit 866d3670 |
| Linked issue | infiquetra/infiquetra-claude-plugins#1035 |
| Linked parent | infiquetra/infiquetra-claude-plugins#1019 |
| Linked plan saga | `issue-1035`, plan tick recorded 2026-09-19 |
| Classification | plan document — not an idea, issue, or spec artifact, so no rubric-engine phase applies |
| Triggered lens | security and external integration (an API credential, and repository content sent to a third-party vendor) |
| Rounds | 2 |
| Blocked | no |
| Findings after round 2 | 0 at P0, 0 at P1, 0 at P2, 0 at P3 |
| Safe fixes applied | 11 in round 1, 7 in round 2 |

## How this review was run

The plan's author also ran the review, and subagents were unavailable for this turn, so the pass was run twice against the repository rather than against the plan's own prose. Every claim the plan makes about existing code was re-checked by reading the cited file at the cited line, and every requirement was checked for a unit that carries it.

Round 1 checked the plan's factual claims and its requirement mapping. Round 2 re-read the repaired plan looking for contradictions the repairs introduced and for claims that overreach.

No finding was downgraded to make the review pass. Every finding below is closed.

## Round 1 — findings and fixes

| Key | Priority | Finding | Fix |
|---|---|---|---|
| D1 | P1 | Requirement 6 said the board Status options narrow when `--stage` is supplied. `issue prepare` has no `--stage` flag — the subparser at `sdlc_manager.py:7358-7388` defines eleven arguments and none of them is stage, so the `stage` parameter is reachable only from Python and every command-line prepare passes `None`. An implementer would have written a branch against a flag that does not exist. | Requirement 6 now states the union is the normal case, names the absent flag explicitly, and says the narrowing branch is written against the function parameter |
| D2 | P1 | Requirement 3 used three risk levels, low, medium and high. This repository's risk vocabulary is four — `low`, `medium`, `high`, `very-high` at `sdlc_manager.py:4027` — plus an `UNKNOWN` marker that is not a level. A three-level question could never propose the tier the repository reserves for its widest blast radius. | Requirement 3 now reads the levels from `_RISK_TIER_VOCABULARY` rather than hard-coding them, excludes `UNKNOWN`, and a guard test asserts against the constant |
| D3 | P1 | Unit 4 contradicted itself on the candidate label set: it named four documented content labels and then said the set is derived from the configured rules instead. It is also wrong in practice — `auto_label_rules` is empty in the vendored `sdlc-schema.json`, and `load_config` falls back to an external `labels.json` that may not exist, so a rules-only derivation asks about nothing on a machine with no external checkout | New requirement 14a fixes the set as the four documented content labels unioned with any configured rule's labels, excludes the issue-type labels, and a test covers the empty-rules case |
| D4 | P1 | The labels floor was described only as "the floor", which reads as `answer_confidence`. For a yes/no answer that helper returns the probability's distance from one half doubled, so a confident rejection at 0.05 bands at 0.90 and would have added a label the model explicitly said no to | New requirement 13a fixes the threshold to the yes-probability via `answer_value`, states why, and a test asserts the 0.05 case is excluded |
| D5 | P1 | The plan read as though a score answer returns a tier name. It returns a number — `{"type": "score", "score": 1.2, "confidence": 0.8}` in the recorded body at `tests/test_typesafe_client.py:56` | New requirement 3a names the shape, requires the suggestion object to carry both the raw score and the mapped level, and pins the mapping |
| D6 | P2 | Verdict records did not carry the `label` field. Its own docstring says that without it the evaluation harness "cannot score accumulated history at all" — which is exactly what the parent card's acceptance criterion needs | New requirement 10a passes the author's own value as the record's label, making the log self-scoring from ordinary use |
| D7 | P2 | The plan said "the 34 existing prepare tests". The actual count in `test_issue_prepare.py` is 20 | Corrected to twenty, with the file named |
| D8 | P2 | The plan never named the field the choice primitive returns its distribution in | Requirement 2 now names `probabilities` and cites the recorded body |
| D9 | P3 | Four line-range citations were off by one or two lines | All four corrected against the files |
| D10 | P3 | The plan did not mention that `_prepared_project_fields` already records an Objective offline when the handoff source names one, which a reader could mistake for a conflict with the new suggestion | Requirement 5 now says the suggestion sits beside `project_fields` and never touches it |
| D11 | P3 | No coverage expectation was stated for a new module in a repository with an 80 percent minimum | New requirement 20a states it and names the configuration that measures it |

## Round 2 — findings and fixes

| Key | Priority | Finding | Fix |
|---|---|---|---|
| D12 | P1 | The round-1 repair introduced its own error: a test scenario said a score of 1.2 over four levels maps to `high`, calling index 1 "the second level". Index 1 of a zero-based list is `medium`. An implementer copying the scenario would have written a test asserting the wrong answer | Corrected to `medium`, the level list spelled out inline, and the boundary case restated as an exact 1.5 whose rounding the test pins |
| D13 | P1 | Unit 5 pointed at "the Verification section below", which did not exist | A Verification section was added carrying the card's own gate and the repository's inner-loop commands; the unit now points at Open Questions for the runnable command form |
| D14 | P2 | Requirement 11 claimed "nothing is auto-applied anywhere in this plan", which overclaims: `labels auto-label` without the new flag still posts its regular-expression matches to GitHub, as it always has | Requirement 11 now scopes the promise to the suggestions this plan adds and states plainly that the existing apply path is untouched in either direction |
| D15 | P2 | Requirement 1 promised the sidecar would be unchanged "byte for byte", which is impossible: it carries an `updated_at` timestamp that differs between two runs of the same command | Requirement 1 now promises a byte-identical draft markdown and a sidecar with no new key, and excludes the timestamp from the comparison. The markdown claim was checked and holds — the draft body carries no timestamp; only the filename and the sidecar do |
| D16 | P2 | Decision 7 called the number a confidence floor throughout, after requirement 13a made it a probability floor in the labels path | Decision 7 now names both readings and says why they are deliberately distinct |
| D17 | P3 | Decision 9 described `union_labels` as taking "two sets and a number"; its second argument is a mapping from label to answer | Corrected |
| D18 | P3 | Two more citations drifted after the edits | Corrected |

## Readiness summary

**The plan can drive implementation without the implementer inventing a decision.** Six dependency-ordered units, twenty-six requirements each carried by at least one unit, nine decisions each with a rejected alternative and a revisit condition, and a verification command per unit.

**The security lens is satisfied by the foundation, not by this plan's own code.** The credential is read only by the client that issue 1032 shipped, redaction is on the only path to a transport by construction, and the plan adds no HTTP code of its own. Every unit that could touch an artefact carries a key-safety test scenario asserting a sentinel key value appears in no draft, sidecar, log line or printed output.

**Residual risk from limited evidence:** two claims in the plan are measurements from the 2026-09-18 research rather than from this session — the 19-of-30 agreement figure and the 70-percent-at-confidence-0.6 figure. They are cited as the research's measurements, not re-measured here, and nothing in the plan's behaviour depends on either number being exactly right.

## Remaining findings

None. No P0, P1, P2 or P3 finding is open.
