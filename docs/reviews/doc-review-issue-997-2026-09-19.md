# Doc review — issue 997 plan, missing PyYAML in the plan_save_contract envelope

**Verdict: ready to drive implementation.** Seven findings, all repaired in place; none blocking,
none remaining at P0 or P1.

## Review-result contract

| Field | Value |
|---|---|
| Target | `docs/plans/2026-09-19-issue-997-plan-save-contract-missing-pyyaml-plan.md` |
| Reviewed revision | working tree, on branch `issue/997` at base commit `9f1bae8a` |
| Blocked | no |
| Rounds | 2 (round 1 found the seven below; round 2 re-read the edited document and found nothing further) |
| Rubric pass | issue phase — three core lenses and three extras |
| Linked issue | infiquetra/infiquetra-claude-plugins#997, parent grouping #1005 |
| Saga | `issue-997`, plan tick written 2026-09-19 |
| Review artifact | this file |
| Override rationale | not applicable; nothing was overridden |

## Rubric pass

Classified as an issue-derived plan document: the path tie-breaker says plan, and the content
carries every plan signal (`Implementation Units`, `Key Technical Decisions`, `U1`). Issue-phase
rubrics were run because the document descends from GitHub issue 997.

| Lens | Applied | Verdict |
|---|---|---|
| `acceptance_criteria_clarity` (core) | yes | Two requirements were not reviewer-testable from the text alone. Both repaired; see D1 and D2. |
| `devils_advocate_issue` (core) | yes | Single purpose, smallest useful slice, implementation choices are decided at plan altitude rather than pre-coded. The one scope expansion beyond the card — the `--help` facet — is explicitly acknowledged in the Problem Frame, which is what this lens asks for. |
| `spec_fidelity` (core) | yes | Descent is named at three levels (card 997, parent grouping 1005, the issue-926 review that produced finding `adv10`). The expansion past the card is acknowledged; the file list exceeding parent 1005's is now explained. See D6. |
| `context_completeness` (extra) | yes, fires | Strong: every file, line number, precedent test and registry entry is named. One gap — the new test had no name while another unit had to repeat it exactly. Repaired; see D5. |
| `issue_sizing` (extra) | yes, fires | Right-sized for one pull request: four units, one plugin, four functional files plus release surfaces and journal. Within the rubric's typical range and matching the shape of sibling pull request 1040. |
| `prerequisite_mapping` (extra) | yes, fires | Upstream (issue 996, merged as pull request 1040) is named and already landed. The downstream sibling 998 is named as out of scope with its version-collision risk called out. No unstated prerequisite found. |

## Findings

All seven were repaired in place as safe fixes; each was supported by the document itself or by
local repository evidence, and none invented an acceptance criterion or resolved a product
decision.

| Key | Priority | Status | Finding |
|---|---|---|---|
| D1 | P1 | fixed | Requirement R2 promised the refusal would carry a "distinct `entry`" but never said what it is, and unit U2's test scenario pointed back at R2 for the value. The guard could not be written from the plan, and KTD2's whole justification — that `entry` and `file` carry the discrimination a caller needs — had nothing concrete behind it. |
| D2 | P2 | fixed | Requirement R4 ("every existing behaviour is byte-identical") named no proving command, leaving a reviewer to invent what "byte-identical" is checked against. |
| D3 | P2 | fixed | The refusal's `file` field had no pinned spelling, so the implementer could emit an absolute path while the guard asserted a repo-relative one. |
| D4 | P3 | fixed | Unit U1's constraint covered the `yaml` name leaving module globals but not `UniqueLoader`, which leaves at the same time and is equally visible to the checkout's proof through `SimpleNamespace(**globals())`. |
| D5 | P3 | fixed | Unit U2's test function had no name while unit U3 requires the canary registry to repeat that name character-for-character. |
| D6 | P3 | fixed | The plan's file list exceeds parent issue 1005's "Files expected to change" with no explanation, which reads as scope creep to a reviewer holding the parent. |
| D7 | P3 | fixed | Two small accuracy defects: the Problem Frame dated the sibling finding as "one week ago" when both cards were filed the same minute on 2026-09-06 and the sibling was repaired today; and the `origin:` frontmatter field carried an issue URL where the plan contract expects a repo-relative path to an upstream document. The issue reference moved into the title, matching the sibling plan. |

## Applied fixes

1. R2 now fixes all four refusal fields as literals: `code: engine`, `entry: python dependency`,
   `file: plugins/saga/scripts/plan_save_contract.py`, and an `error` containing `PyYAML` (D1, D3).
2. R4 now names its proving command, the existing pytest run over the three test files that
   exercise this tool, with no assertion changed (D2).
3. U1's approach repeats the same four literals and cites `plan_save_contract.py:458` as the
   precedent for the repo-relative spelling (D1, D3).
4. U1's constraint now covers `UniqueLoader` alongside `yaml`, with the evidence that the checkout's
   proof reads neither and that `UniqueLoader` has exactly two references in the repository (D4).
5. U2 now names its test function, `test_contract_cli_envelopes_a_missing_pyyaml`, and states that
   U3's registry `guard` string must track it (D5).
6. U2's first test scenario now asserts the literal `entry` and `file` values instead of pointing
   back at U1 (D1, D3).
7. Scope Boundaries gained a paragraph explaining why the file list exceeds parent 1005's, citing
   the repository's `CLAUDE.md` step 6, the canary requirement, the journal rule, and the identical
   file set in sibling pull request 1040 (D6).
8. The sibling-timing sentence was corrected and the `origin:` field was dropped in favour of the
   issue number in the title (D7).

## Residual risk

The plan's reproduction was run with a `PYTHONPATH` stub whose `yaml.py` raises `ImportError`,
while KTD4 specifies that the guard itself must use a virtual environment with PyYAML genuinely
absent. Those are different conditions, and only the first has been observed so far. The plan says
so, and unit U2's "watch it fail first" step is where the second one gets observed — but until that
step runs, nobody has seen the tool behave with PyYAML truly missing rather than present and
raising.
