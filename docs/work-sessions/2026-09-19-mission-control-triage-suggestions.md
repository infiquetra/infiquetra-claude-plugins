# Work session — mission-control triage suggestions (issue 1035)

- **Date:** 2026-09-19
- **Issue:** infiquetra/infiquetra-claude-plugins#1035, a child of parent #1019
- **Plan:** `docs/plans/2026-09-19-mission-control-triage-suggestions-plan.md`
- **Doc review:** `docs/reviews/2026-09-19-mission-control-triage-suggestions-plan-doc-review.md` — two rounds, zero open findings, gate passed with no override
- **Branch:** `issue/1035`, based on `main` at commit 866d3670
- **Backend:** `inline`, honoured from the plan's `backend:` frontmatter — no offer was made, per the work skill's "if the plan carries a backend field, honour it and do not offer"
- **Complexity triage:** small-medium; a task list was built from the plan's six Implementation Units

## What was built, by unit

**U1 — the suggestion module.** `plugins/mission-control/scripts/triage_suggest.py`: the batched
question set, the answer shaping, the score-to-level mapping, and the pure `union_labels`
function. It makes no call of its own and reads no file; the caller passes the client's `ask` in.

**U2 — the prepare path.** `issue prepare --suggest` and the repeatable `--objective-option`.
The call happens after every draft field and the readiness verdict are settled and immediately
before the sidecar is serialised, so no answer can reach a field, a gap, or a label.

**U3 — verdict and override logging.** One verdict per answer under
`mission-control/issue-prepare:<question>`, each carrying the resolved model version and the
author's own value as the record's `label`; an override where the author's flag differed.

**U4 — the labels union.** `labels auto-label --suggest` prints the widen-only union with
provenance and applies nothing. Without the flag the command posts exactly as it always has.

**U5 — the card's acceptance test.** `tests/test_mission_control_suggest.py`, at the path the
card names, covering both acceptance criteria and the failure expectation.

**U6 — documentation and release surfaces.** Both skills, the labels reference, the version bump
from main's 2.16.0 to 2.17.0 across the manifest, the marketplace registry, the changelog and the
version-literal guard in `test_prompt_alignment.py`.

## Key decisions

Recorded in `docs/engineering-journal/DECISIONS.md` as `{#1035-triage-questions-live-in-mission-control}`,
`{#1035-flag-is-the-decision-difference-is-the-override}` and `{#1035-suggestion-failure-fails-open}`.
One learning from this session is recorded as `{#1035-score-distribution-keyed-by-index}`.

## The defect the live run found, which no test could

Running the command against a real card body showed the risk line as `risk: 1 0.58, 0 0.25, 2
0.16, 3 0.01`. A score answer's distribution is keyed by the level's **index**, while every other
question's is keyed by its option names — and the recorded fixture this repository already had
carries no score distribution at all, so every test written from it passed. Fixed by
`relabel_score_distribution`, guarded by two tests, and recorded in LEARNINGS. The live line now
reads `risk: medium 0.59, low 0.29, high 0.12, very-high 0.00`.

## Live verification

The card's first acceptance criterion, in its runnable form, was run once against a real card
body taken from the integration branch (`docs/sdlc-issue-drafts/2026-08-27-orchestrate-has-no-non-mutating-plan-validator-s.md`,
whose own front matter records `type: enhancement` and `risk: medium`). It was run from the
session scratchpad so no draft was written into the repository, and **no issue was created**.

| Judgment | Live answer | Against the card's own label |
|---|---|---|
| Issue type | `capability` at 0.80, with `enhancement` second at 0.19 | The label is the model's **second** choice, not its first |
| Risk | `medium` at 0.59 | Matches |
| Board status | `Ready for Planning` at 0.86 | No label to compare; sensible for a requirements-ready card |
| Objective | not asked | No candidates were supplied |

The type miss is the honest result and is the behaviour the card asks for: the distribution is
shown precisely because the single answer is not reliable enough to act on, and `--type defect`
stayed the card's type with the disagreement logged as an override.

## change_kinds

`["behavior"]`

New command-line behaviour on two commands, so the hard test gate applies and is satisfied: every
unit is feature-bearing and carries happy-path, edge-case, failure-path and integration coverage.

## Checks run

pytest | ruff | mypy | release-surface parity | marketplace sync | marketplace validator | release-surface diff guard

## Next step

Open the pull request to `main` after the code review accepts.
