# Doc review — Issue 938 removal plan

Target: `docs/plans/2026-09-20-issue-938-remove-work-second-opinion-offer-plan.md`
Reviewed revision: working tree on branch `issue/938`, base commit `b98e94ea`
Classification: plan (path `docs/plans/`, carries `Implementation Units`, `Key Technical Decisions`, a `U1` prefix)
Blocked: no
Linked issue: infiquetra/infiquetra-claude-plugins#938
Review artifact: this file

## Readiness summary

The plan can drive implementation without the implementing agent inventing a missing decision. Six
safe fixes were applied in place; no `P0` and no `P1` finding remains open.

The formal SDLC rubric engine was not run: this is a plan artifact, which the skill's own
classification routes to the readiness-skeptic pass rather than to the idea-phase or issue-phase
rubrics. No external reviewer panel was dispatched — that path is opt-in and was not requested.

## Applied fixes

| # | Priority | Finding | Fix |
|---|---|---|---|
| D1 | P1 | The consumer count in KTD1 did not add up: it claimed eleven of thirteen exported names had zero outside references, then named three that had some — fourteen names for a set of thirteen. An implementer checking the arithmetic would lose confidence in the whole no-consumer proof, which is the safety argument for the entire card. | Corrected to ten with zero references, and each of the three that appear is now traced to the specific site this card removes. Corrected in both KTD1 and the removed-component table. |
| D2 | P1 | U1 located both sections to delete by line number on the base commit. Sibling card 1029 edits one of those two files, so the offsets would be stale by the time the unit runs, and an agent cutting lines 113 through 160 after a sibling landed would cut the wrong text. | Both sections are now located by their headings and by the heading each one ends before. The base-commit line numbers are kept as orientation with an explicit warning that the offsets, not the headings, are the unstable part. |
| D3 | P1 | The card's own first verification command is a repository-wide word search that will still return matches after the removal — from Document Review's prose, from the trust-boundary document, and from the changelog. An agent reading a non-empty result as a failed removal would either declare the card unfinished or delete one of the two things the card most explicitly forbids deleting. | The Verification section now states that a non-empty result is the correct outcome, names the three surviving families and why each survives, and points at the scoped negative suite as the real proof. |
| D4 | P2 | KTD6 said the retained-component test "runs each proving test's file as a real dependency assertion" — an open choice that reads like running pytest inside pytest. | Settled: three explicit assertions per row (component file exists, consumer file exists and still carries the citing reference, proving test file exists and still defines the named test), and an explicit statement that it does not invoke pytest recursively. |
| D5 | P2 | U5 left the work-session note unnamed, so the observed-red evidence for the mutation proof had no recorded home. | Named the path and said what the note must carry: the command, the failure output, and the commit it ran against. |
| D6 | P2 | The plan landed this card's change without noticing that it makes one cross-reference stale: the code-review findings schema tells its reader that removing Work's offer "is issue 938, not this card", which stops being true the moment this card lands. | Added the one-line past-tense correction to U5, with the reason it belongs in this card rather than a later sweep. |

## Remaining findings

None at `P0` or `P1`.

| # | Priority | Finding | Status |
|---|---|---|---|
| D7 | P3 | The plan defers its key-technical-decision journal entries to the work stage rather than writing them at planning time as the plan skill's Phase 3 describes. | Accepted, and now stated as KTD9 with its reason: this repository's rule that an entry ships in the commit that ships the change is the narrower rule, and parallel sibling cards writing the same journal files make an early entry one that has to be rewritten at the merge turn. |

## Residual risk from limited evidence

One claim in the plan cannot be proven until the work stage runs: that deleting
`plugins/saga/scripts/second_opinion.py` leaves the repository's full test suite green. The
no-consumer evidence is a static reference count across four directory trees, which is strong but is
not the same as a passing suite. The plan's own verification sequence ends with a full `pytest tests/`
run, and the card's merge onto the integration branch is gated on it, so the gap closes at the point
where it can actually be closed.
