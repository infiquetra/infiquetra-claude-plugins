# Work session — issue 996, the Plan save-contract JSON envelope

Repaired the escape that let a `BaseException` from the repository checkout `plan_save_contract.py` executes leave the tool's JSON envelope, and shipped it as Saga `0.159.1`.

## What shipped

Two seams execute code out of the checkout named by `--root`, and both now keep whatever it raises inside the documented refusal envelope — one JSON object on standard output, exit 2, `code: engine`, and the offending file named.

The first seam is the loader `module()`, which runs a checkout file through `runpy`. Its handler was widened from `except Exception` to `except BaseException`. For ordinary exceptions this is behaviour-identical, because the loader has always rewritten those into its own message; only `SystemExit`, `KeyboardInterrupt` and their siblings are newly caught.

The second seam is the *call* to the loaded proof. `verify_saved_examples` loads `plan_save_proof.py` through the loader and then calls its `verify()` outside the loader's `try`. That call is now wrapped in a new context manager, `checkout_code`, which re-raises a `ContractError` untouched — so a real verification diagnosis from the proof keeps its own `code` and `entry` instead of being relabelled an engine fault — and converts anything else.

The handler in `main()` deliberately stays `except Exception`, and now carries a comment saying why: argparse raises `SystemExit(0)` for `--help` from inside that same `try`, so widening it would turn the one invocation the tool's docstring exempts into a JSON refusal at exit 2.

## The finding the card did not contain

The card, and the review that produced it, named only the loader. Reproducing the defect before planning turned up a third escape the card does not mention: a `SystemExit` raised at call time inside `verify()` gave empty output and exit 9. Guarding the loader alone would have closed the two probes the card lists and left the class open, while looking fixed. Both seams are covered, and both are probed by the new test.

## Questions answered from the coordinator's launch message

`AskUserQuestion` was unavailable, and the coordinator supplied every choice up front. Each is recorded here with the answer applied and its source.

| Decision | Answer applied | Source |
|---|---|---|
| Saga | Resume `issue-996`; advanced to `lifecycle_phase=work`, never minted a second one. | Coordinator's launch message; `saga.py scan` matched the existing saga. |
| Branch | Stayed on `issue/996`. | Coordinator's launch message. |
| Execution backend | `inline`, honoured from the plan's `backend:` frontmatter without an offer, which is what the work skill prescribes when the field is present. | Plan frontmatter, confirmed by the coordinator. |
| Doc-review gate | Passed, no open findings, no override. | `docs/reviews/doc-review-issue-996-2026-09-19.md`. |
| Complexity triage | Small-to-medium: a task list built from the plan's three implementation units, which is the skill's documented default for this size. | Skill default, applied to the plan's unit count. |
| Round detection | Fresh build, not a re-entry: the saga carried no pull-request references. | `saga.py scan` output. |
| Front-loaded draft pull request | Declined. The coordinator directs that the pull request opens after the gate and the code review. | Coordinator's launch message. |
| Board moves | Submitted through the reconcile controller. Planning/Designing, then Planning/Ready for Active, then Active/Implementing — each returned `written` with `field: Stage+Status`, so both halves of each pair landed. | Skill phases 0.6, 5.0 and 1.3b. |
| Code-review mode and lenses | Programmatic mode; lens set `accept-recommended`, treated as a caller-supplied selection rather than an operator question. | Coordinator's launch message. |
| Code-review fan-out | Run in this thread instead of as parallel agents, because subagents were forbidden this turn. Which lenses ran and what they were asked is unchanged. | Coordinator's concurrency instruction. |
| Fixer dispatch | Never auto-run; the one finding worth repairing was repaired by hand. | Coordinator's launch message. |
| Merge | No. The coordinator merges after the required checks pass. | Coordinator's launch message. |

## Where the shipped code qualifies the plan

The plan's third key technical decision opens by saying both seams route through one shared helper. The shipped code qualifies that, exactly as the clarification paragraph directly beneath it anticipated: the loader keeps its own inline handler, because it must go on rewriting a `ContractError` as it always has, while the call seam must let one through. A single helper cannot do both without a flag, and two callers did not justify one. The work skill forbids editing the plan body during execution, so the divergence is recorded here and as finding F6 in the code review rather than by amending the plan.

## What the plan did not foresee

The repository requires every guard in `tests/test_saga_spec_consumer_row.py` and `tests/test_saga_plan_contract_boundaries.py` to carry a behavioural mutation in `tools/canary_registry.json`, enforced by a drift guard in `tests/test_saga_plugin.py` and executed by `tests/test_wiring_canary.py`. Adding the new test without registering a mutation failed that guard. A mutation was registered — narrowing the checkout boundary back to `Exception` — and the canary suite passes, which is what demonstrates the new test has teeth rather than merely existing. The same drift guard also pins the Saga version literal, which the release bump required updating.

## Verification

Reproduced before and after against a temporary checkout built by the test suite's own helper, at base commit `2044c363`: a module-level `sys.exit(7)`, a module-level `raise KeyboardInterrupt`, and a `sys.exit(9)` as the first statement of `verify()` each gave no JSON and an undocumented exit code beforehand, and each gives the documented refusal at exit 2 afterwards. The unmutated checkout still returns `outcome: valid` at exit 0, and `--help` still prints usage at exit 0 with output that does not parse as JSON.

Reverting either half of the repair fails the new test; both mutations were run. The three affected test files pass, 87 tests, and the behavioural canary suite passes, 11 tests.
