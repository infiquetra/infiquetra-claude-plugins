# Doc review — issue 996 plan, 2026-09-19

The plan is ready to drive implementation. Five findings were raised and all five were repaired in place; none remain open, and nothing blocks `/work`.

## Review-result contract

| Field | Value |
|---|---|
| Target | `docs/plans/2026-09-19-issue-996-plan-save-contract-baseexception-plan.md` |
| Classification | plan (path `docs/plans/`, carries `Implementation Units`, `Key Technical Decisions`, `U1`) |
| Reviewed revision | working tree on branch `issue/996`, based on commit `2044c363` |
| Blocked | no |
| Findings | 5 raised, 5 repaired, 0 open (0 P0, 2 P1, 2 P2, 1 P3) |
| Linked issue | infiquetra/infiquetra-claude-plugins#996, child of #1005 |
| Saga | `issue-996`, tick `20260919-163631` |
| Override rationale | not applicable; nothing was overridden |
| Artifact | this file |

No formal SDLC rubric phase applies: the target is a plan, not a blueprint, an architecture decision record, or a GitHub issue, so the idea-phase and issue-phase rubric engines were not run. No external reviewer panel was dispatched; this was not requested and the artifact does not warrant one.

## Applied fixes

Every fix below is evidence-backed against the repository at commit `2044c363`, which is what makes it a safe in-place edit rather than a finding left open.

| Key | Priority | Finding | Repair |
|---|---|---|---|
| D1 | P1 | The plan sent an implementer to `test_plan_renderer_refusals_and_rollback` "in `tests/test_saga_plan_contract_boundaries.py`". That function is not in that file; it is at `tests/test_saga_spec_consumer_row.py:515`. The pattern actually worth copying — a subprocess run against a temporary checkout with the script text restored between probes — is `test_contract_cli_without_pytest` at `tests/test_saga_plan_contract_boundaries.py:248`. | Named the real function and its file and line in both places the plan referred to it, and added a sentence explaining that the required-test inventory in `tests/test_saga_plugin.py` scans both files, which is why the wrong file was easy to infer. |
| D2 | P1 | Key Technical Decision 3 said the shared conversion re-raises `ContractError` untouched at both seams. Read literally at the loader, that changes today's behaviour: `module()` has always rewritten a `ContractError` into its `engine import` message, so the pass-through would alter a path this card is not about and put requirement R5 (documented paths unchanged) at risk. | Added a clarification to KTD3 and to unit U1: at the loader the repair is strictly additive — ordinary exceptions keep today's treatment and only a non-`Exception` `BaseException` is newly converted. The pass-through is required at the `proof.verify` seam only. |
| D3 | P2 | Line numbers were wrong or imprecise. The plan gave `module()` as `78-92` and its handler as line 87 (actual: `78-94`, handler on line 88), `main()` as `437-506` (actual: `439-509`), and `verify_saved_examples()` as "at `435-436`", conflating the function's location with the two lines of interest (it is defined at line 425; the load is line 435 and the call is line 436). | Corrected every number against the file. |
| D4 | P2 | Requirement R1 said the loader fix "covers all four load sites", which reads as exhaustive and is not: the proof makes its own nested load through the same helper at `plan_save_proof.py:492`. | Reworded R1 to say that because every load goes through one helper, the fix covers the four call sites in `plan_save_contract.py` and the proof's nested call as well, each named. |
| D5 | P3 | The card cites `plan_save_contract.py:63` and a loader at `55-69`, which match neither the plan's numbers nor the current file; a reader could conclude the plan had targeted the wrong code. | Added a parenthetical recording that the card's numbers come from the reviewed revision `11f8e2ca` and that the code is unchanged at `2044c363` — only its position moved. |

## Readiness summary

The plan can drive implementation without the agent inventing decisions, because the load-bearing choice is settled with its rejected alternatives and the evidence is first-hand rather than inherited.

**Verification.** The plan does not rest on the card's claims. All three envelope escapes and the `--help` exemption were reproduced in this worktree at `2044c363` against a temporary checkout, and the results are tabulated in the plan's Problem Frame. The reproduction of a `SystemExit` raised at call time inside `verify()` is new evidence the card does not contain, and it widened the repair from one seam to two.

**Assumptions.** The one assumption that would have been dangerous if left unstated is stated: `--help` works today *because* the top-level handler is narrow, so the obvious one-line fix is the wrong fix. That is recorded as KTD1 with its rejected alternatives, and pinned by requirement R4 and a test in unit U2.

**Requirement mapping.** Requirements R1 through R8 each map to a unit: R1–R5 to U1, R3–R6 to U2, R7–R8 to U3. No requirement is unowned and no unit carries work no requirement asked for.

**Open-choice pressure.** The shared conversion's name and exact shape are deliberately left to the implementer; its contract (re-raise `ContractError`, otherwise convert to `code: engine` naming the checkout file) is fixed by R1, R2 and R3, so the open choice is cosmetic rather than behavioural.

**Adversarial reading.** The two ways a literal reading could go wrong were the loader pass-through (D2, repaired) and the missing test reference (D1, repaired). The remaining literal-reading risk is the version number in KTD4, which the plan itself instructs the implementer to re-check against `origin/main` before merge.

## Remaining findings

None. No P0, P1, P2 or P3 finding is open.

## Residual risk from limited evidence

Two, both known and both bounded.

The Saga plugin version `0.159.1` is correct against `origin/main` as of this review, but two sibling cards, issues 997 and 998, run after this one in the same lane and bump the same three files. The repository's own journal records this collision recurring twice before. The plan handles it by instruction rather than by mechanism, because no mechanism exists: the release-surface guard is pull-request-only and cannot run locally.

The behavioural trade in KTD2 — an operator's Ctrl-C during the proof run becomes a JSON refusal at exit 2 rather than a traceback at exit 130 — is a deliberate, reasoned choice rather than a verified-harmless one. It is the only choice that closes the card, since a checkout-raised interrupt and a terminal-delivered one are indistinguishable at the seam, but it is a change an operator could notice.
