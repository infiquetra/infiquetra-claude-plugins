# Code review — issue 996, cycle 1

The change is accepted. One finding was repaired during the review; five residuals are recorded and none of them blocks.

## Review-result contract

| Field | Value |
|---|---|
| Target | branch `issue/996` |
| Base | commit `2044c363` on `main` (confirmed as the merge base with `origin/main`) |
| Reviewed commit | `8ad1ad2c` (`fix(saga): keep a BaseException from checkout code inside the plan_save_contract envelope`) |
| Note on that identifier | The review ran against the same content as `f11584a1`. That commit was rewritten to `8ad1ad2c` after the review, solely to delete a session-link line from its message; the tree is byte-identical, which `git diff` between the two heads confirms. |
| Mode | programmatic, called by the run driver |
| Outcome | `accepted` |
| Derived overall | 9.4 of 10 |
| Lowest applicable dimension | 8.0 (architecture and maintainability) |
| Acceptance rule | overall at or above 9.0 and every applicable dimension at or above 7.0, per `plugins/saga/references/lens-roster.json` |
| Findings | 6 total: 0 at P0, 0 at P1, 1 at P2 (repaired), 5 at P3 (recorded, accepted) |
| Saga | `issue-996` |
| Linked issue | infiquetra/infiquetra-claude-plugins#996, child of #1005 |
| Artifact | this file |

## How this review was run

The caller approved the recommended lens set (`accept-recommended`) in its launch message, which is a caller-supplied selection and therefore stands in for the operator question the skill would otherwise ask. The caller also forbade spawning subagents, because the session is at its concurrency limit. The lens fan-out was therefore executed in this thread rather than as parallel agents. That changes who ran each lens, not which lenses ran or what they were asked: the four always-on lenses and four approved conditionals below were each applied to the whole difference against the base.

- Always-on: correctness, security, testing, architecture and maintainability.
- Conditional, approved: adversarial (this change repairs an adversarial-lens finding, so the same lens should judge the repair); application-programming-interface contract (the tool's JSON envelope and exit-code set is a contract other programs read); documentation clarity (the change ships a changelog entry, two journal entries and load-bearing code comments); agent usability (the refusal envelope is consumed by agents, so its wording and its `entry` vocabulary matter).
- Not selected: previous-comments (no pull request exists yet, so there are no review comments to carry), deployment and infrastructure, performance, reliability, privacy, accessibility — none has an applicable dimension in this difference.

## Scope check

**Result: clean.** Intent, from the plan and the commit messages: keep a `BaseException` raised by the checkout that `plan_save_contract.py` executes inside the tool's documented JSON envelope. Delivered: exactly that, at both seams where checkout code runs, plus the tests, the release bookkeeping and the journal entries the repository requires to ship with a behaviour change. No file in the difference is unrelated to that intent.

## Plan-completion audit

Every requirement in the plan is done and confirmable from the difference or from a run.

| Requirement | Verdict | Evidence |
|---|---|---|
| R1 — a `BaseException` while loading checkout code becomes the documented refusal | done | `module()` now catches `BaseException`; probes give exit 2 with `code: engine`. |
| R2 — the same while the loaded `verify()` runs | done | The `proof.verify(...)` call is wrapped in `checkout_code`; the probe gives exit 2 with `entry: engine proof`. |
| R3 — a `ContractError` from the checkout keeps its own diagnosis | done | `checkout_code` re-raises it; the test asserts `code: verification` and the probe's own entry survives. |
| R4 — `--help` still prints usage at exit 0 and no JSON | done | Asserted in the new test, including that the output does not parse as JSON. |
| R5 — documented paths unchanged | done | Unmutated `validate` still returns `outcome: valid` at exit 0; the three affected test files pass, 87 tests. |
| R6 — a regression test at the real command-line boundary, red if the repair is reverted | done | New test drives a subprocess against a temporary checkout; reverting either half of the repair fails it, confirmed by running both mutations. |
| R7 — release surfaces move together | done | Saga plugin manifest, marketplace entry and changelog all read `0.159.1`; the version drift guard in `tests/test_saga_plugin.py` was updated to match. |
| R8 — a dated learnings entry in the same commit | done | `{#996-envelope-needs-baseexception}` ships in commit `f11584a1`. |

Unit U1, U2 and U3 are each done. U2 grew one item the plan did not foresee: the repository requires every guard in these two test files to carry a behavioural mutation in `tools/canary_registry.json`, enforced by `tests/test_saga_plugin.py` and executed by `tests/test_wiring_canary.py`. That entry was added and the canary suite passes, which is what proves the new guard has teeth rather than merely existing.

## Findings

| Key | Priority | Lens | Finding | Status |
|---|---|---|---|---|
| F1 | P2 | architecture and maintainability | `verify_saved_examples` held a variable `tool` naming this script and a new variable `tool_path` naming the checkout's proof — two similar names for different files in one short function, which is how a later edit passes the wrong path. | Repaired in the reviewed commit: renamed to `proof_path`, with a comment saying which file each one is. |
| F2 | P3 | adversarial | One place still reaches into checkout-loaded objects outside a guard: `inspect.signature()` on the checkout's `derive_saga_id` and `inject_effort`. Introspection does not execute a function body, so no `BaseException` can arise from it short of a checkout defining a pathological `__signature__`. | Recorded, not repaired. Guarding introspection would widen the change beyond the card for a fault nobody can currently trigger. |
| F3 | P3 | architecture and maintainability | The shared conversion `checkout_code` has one caller, while `module()` carries a near-identical handler inline, which is the drift the plan's third decision wanted to avoid. | Accepted by design. The two seams genuinely differ: the loader must keep rewriting a `ContractError` as it always has, and the call seam must let one through. Both the code comment and the plan's clarification say so. |
| F4 | P3 | testing | The call seam is probed with a `SystemExit` but not with a `KeyboardInterrupt`; the load seam is probed with both. | Accepted. Both kinds reach the same handler by the same path, and the load-seam probes already prove the handler treats them alike. |
| F5 | P3 | application-programming-interface contract | The changelog names the new `code: engine` behaviour but not the new `entry` value `engine proof`, which is the field that distinguishes the two seams to a machine reader. | Accepted. `entry` has always been free text in this tool ("usage", "filesystem", "load/render"), so adding a value is consistent rather than a contract change. |
| F6 | P3 | documentation clarity | The plan's third decision opens by saying both seams route through one helper, which the shipped code qualifies. The clarification paragraph directly beneath it states the exception, but the opening sentence read alone is now slightly ahead of the code. | Recorded, not repaired. The work skill forbids editing the plan body during execution; this is noted here and in the work-session write-up instead. |

## Scores

| Dimension | Score | Note |
|---|---|---|
| Correctness | 10 | Every claimed behaviour was reproduced before and after, including the unmutated baseline and `--help`. |
| Security | 10 | No new input handling, no shell, no secrets; the message path and its truncation are the existing ones. |
| Testing | 9 | Mutation-proven on both halves and registered in the behavioural canary; the one untested permutation is F4. |
| Architecture and maintainability | 8 | F1 repaired; F3 is a justified, documented divergence that a future reader must still reason about. |
| Adversarial | 9 | The escape class is closed at both execution seams; F2 is a residual that cannot currently be triggered. |
| Application-programming-interface contract | 10 | The envelope shape and the exit-code set are unchanged; `--help` is pinned by a test. |
| Documentation clarity | 9 | Changelog and journal entries are specific and accurate; F6 is a wording lag in the plan, not in the shipped documentation. |
| Agent usability | 10 | Both refusals name the file and give an actionable remedy, and the two seams are distinguishable by `entry`. |

Derived overall 9.4; lowest applicable dimension 8.0. Both acceptance rules are satisfied, so the outcome is `accepted`.

## Residual risk

The deliberate behavioural trade stands: an operator interrupting the tool with Ctrl-C while the checkout's proof runs now receives a JSON refusal at exit 2 instead of a traceback at exit 130. This is recorded as the plan's second decision and in the shipped code comment, and it is the only treatment that closes the reported defect, because an interrupt raised by the checkout is indistinguishable at that point from one delivered by the terminal.

The Saga version `0.159.1` is correct against `origin/main` as of this review. Two sibling cards, issues 997 and 998, touch the same three release files, and the coordinator owns resolving a collision at merge time.
