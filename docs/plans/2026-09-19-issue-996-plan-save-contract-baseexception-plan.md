---
title: Keep a BaseException from checkout code inside the plan_save_contract JSON envelope (issue 996)
type: fix
status: active
date: 2026-09-19
backend: inline
---

# Keep a BaseException from checkout code inside the plan_save_contract JSON envelope (issue 996)

Make `plugins/saga/scripts/plan_save_contract.py` honour its own promise — every invocation except `--help` prints one JSON object and exits 0, 1 or 2 — when the repository checkout it loads through `runpy` raises a `BaseException` that is not an `Exception`, such as `SystemExit` or `KeyboardInterrupt`.

## Problem Frame

The tool checks and renders the Saga Plan save-contract documentation for an explicit repository checkout named by `--root`. To do that it executes files out of that checkout in-process through `runpy.run_path`, behind one helper, `module()` at `plan_save_contract.py:78-94`, whose handler on line 88 is `except Exception` — which by Python's exception hierarchy does not cover `SystemExit`, `KeyboardInterrupt` or any other direct `BaseException` subclass. The command-line entry point `main()` at `plan_save_contract.py:439-509` has a second `except Exception` with the same blind spot.

(The card cites `plan_save_contract.py:63` and the loader at `55-69`. Those line numbers are from the reviewed revision `11f8e2ca`; at commit `2044c363`, the base of this branch, the same code sits at the lines given above. The code is unchanged — only its position moved.)

The consequence is the one the tool's docstring rules out: a caller that parses standard output as JSON gets an empty stream and an exit code outside `{0, 1, 2}`.

This is finding `adv09` (severity P2, adversarial lens) carried forward from the issue 926 Saga Code Review, cycle 6, whose outcome was `cycle_cap_best_available`. It is a child of the backlog grouping issue 1005, "Saga Plan save-contract residuals carried from the issue 926 review". Its two siblings in that grouping, issues 997 and 998, are out of scope here.

**Reproduced in this worktree, not taken on the card's word.** Against commit `2044c363` on branch `issue/996`, in a temporary checkout built by the suite's own `tree()` helper:

| Probe inserted into the checkout's `plan_save_proof.py` | Standard output | Exit |
|---|---|---|
| none (baseline) | `{"root": ..., "outcome": "valid", "schema": "plan_save_contract.v3"}` | 0 |
| `sys.exit(7)` at module level | empty | 7 |
| `raise KeyboardInterrupt("probe")` at module level | raw traceback on standard error | 130 |
| `sys.exit(9)` as the first statement of `verify()` | empty | 9 |

The fourth row is new evidence this plan adds to the card. The card's reproduction covers only the two module-level probes, which escape while `module()` loads the file. The third escape happens later: `verify_saved_examples()` (defined at `plan_save_contract.py:425`) loads the proof through `module()` on line 435 and then **calls** `proof.verify(...)` on line 436, outside that helper's `try`. Checkout code that raises a `BaseException` at call time therefore escapes through a second, uncovered seam. Both seams are the same defect in the card's own words — a `BaseException` from `runpy`-loaded checkout code leaving the envelope — so both are in scope.

**The constraint that shapes the fix.** `--help` works today *because* the handler in `main()` is narrow. Argparse raises `SystemExit(0)` from inside `main()`'s `try`; `except Exception` lets it through, so `--help` prints usage and exits 0 (verified: `plan_save_contract.py --help` prints the usage block and exits 0). Widening `main()`'s handler to `BaseException` would convert `--help` into a JSON refusal at exit 2 and break the one invocation the docstring exempts. The repair therefore belongs at the seams where checkout code runs, not at the top-level handler.

## Questions answered from the card

`AskUserQuestion` is unavailable in this session, so every question the installed Saga `/plan` skill would put to the operator was answered from the card, the parent card, the code, or the skill's documented default. Each is recorded here with the answer taken and where the answer came from.

| Skill phase | Question | Answer taken | Source of the answer |
|---|---|---|---|
| 0.3 | Resume an existing plan saga, or mint a new one? | Mint a new one. | `python3 plugins/saga/scripts/saga.py scan` returned `{"candidates": [], "count": 0}` — there is nothing to resume. |
| 0.4 | Is a plan document warranted at all? | Yes, warranted. | The work is not atomic: it carries three load-bearing decisions (below), a scope boundary against two sibling cards, and a traceability line back to the issue 926 review. The skill's own instruction is to bias toward writing one. |
| 0.5 | Which scope class — Lightweight, Standard or Deep? | Lightweight. | One helper function, one call site, one test file, and the release bookkeeping. Low ambiguity, no cross-repo or security surface. Three implementation units, which is inside the Lightweight band. |
| 5.1 | Routing destination — plan-only, pr, merge or nonprod-deploy? | `pr`. | Applied at intake from the `plan_pre_answers.v1` carrier supplied by the caller `improve-claude-plugins run driver`; the validator `plan_pre_answers.py` exited 0 with `applied: {backend: inline, destination: pr}` and no stop. |
| 5.1 follow-up | Deploy autonomy, gate or auto? | Not asked, and no value recorded. | The skill asks this only for `nonprod-deploy`. The destination is `pr`. |
| 5.2 | Execution backend — inline, team-execution or dynamic workflows? | `inline`. | Applied from the same carrier. Independently confirmed: `lifecycle_state.py recommend-backend --file-count 8 --release-surface-file-count 3 --phase-count 3` returned `{"recommended": "inline", "rationale": "no escalation signal -> the agent does the work itself"}`. Recommendation and choice agree. |
| 5.2 KTD4 | Is the consensus signal gated or advisory? | Not asked. | No consensus, multi-reviewer or many-attempt signal is present in this work, which is the precondition for the question. |
| 5.2a | Per-unit model and effort tiers; author an ExecutionSpec? | Not entered. | That section is reachable only after an operator explicitly invokes the `cc-workflows-ultracode` backend. The backend here is `inline`. |

No question was skipped silently, and none of the categories reserved for the operator — production, destructive change, credentials, permissions, billing, external commitments, process authority, or a plan-review override — arose.

## Requirements

R1. A `BaseException` raised while `module()` loads a file out of the `--root` checkout through `runpy.run_path` is reported inside the JSON envelope as a refusal: one JSON object on standard output, exit 2, `code` = `engine`, and `file` naming the checkout file that raised. Because every load goes through that one helper, this covers the four call sites in `plan_save_contract.py` — `saga.py` at line 143, the effort rider at lines 215 and 276, and `plan_save_proof.py` at line 435 — and equally the nested load the proof itself makes through the same helper (`api.module(...)` at `plan_save_proof.py:492`).

R2. A `BaseException` raised while the loaded proof's `verify()` runs — that is, at call time rather than load time, at the `proof.verify(...)` call on `plan_save_contract.py:436` — is reported the same way.

R3. A `ContractError` raised by checkout code through `api.fail(...)` keeps its own `code`, `file` and `entry`. In particular a genuine verification failure raised inside `verify()` still reports `code` = `verification`, not `engine`. The new handling must not overwrite a diagnosis that the proof already made.

R4. `plan_save_contract.py --help` still prints the argparse usage block and exits 0, printing no JSON. The top-level handler in `main()` stays narrow.

R5. The unmutated tool is unchanged on every documented path: `validate` exits 0 with `outcome: valid`, `render --check` exits 0 or 1 with `outcome` `clean` or `drift`, and `render --write` exits 0 with `outcome: rendered`.

R6. A regression test drives the real command-line boundary in a subprocess against a temporary checkout, asserting the JSON envelope and the exit code for each of the three escapes reproduced above, and asserting that `--help` is untouched. A test that reverts the repair must go red.

R7. The Saga plugin's release surfaces tell the same story as the diff: `plugins/saga/.claude-plugin/plugin.json`, the `saga` entry in `.claude-plugin/marketplace.json`, and `plugins/saga/CHANGELOG.md` all carry the same new version, strictly greater than the version on `origin/main` at merge time.

R8. The engineering journal carries a dated `LEARNINGS.md` entry recording the mechanism, in the same commit that ships the change.

## Key Technical Decisions

KTD1. **Repair at the two checkout-execution seams, never at the top-level handler.** The conversion from `BaseException` to a refusal envelope goes where checkout code actually runs: inside `module()`, and around the `proof.verify(...)` call in `verify_saved_examples()`. Rejected: widening `main()`'s `except Exception` to `except BaseException`. That single-line change looks like the obvious fix and is wrong — argparse's `SystemExit(0)` for `--help` is raised inside `main()`'s `try`, so the broad handler would print a JSON refusal at exit 2 for `--help` and break R4, the one invocation the tool's docstring exempts. Rejected: special-casing `SystemExit(0)` inside a broad top-level handler, which would make the envelope contract depend on an exit-code value rather than on where the exception came from.

KTD2. **Convert `KeyboardInterrupt` rather than re-raising it, and say so in the code.** An interrupt arriving while checkout code runs becomes a refusal envelope with a named cause, not a traceback at exit 130. This is a deliberate trade: an operator pressing Ctrl-C during the proof run now sees `{"outcome": "invalid", "code": "engine", ...}` and exit 2 instead of a traceback. It is the only option that satisfies the card, because a `KeyboardInterrupt` raised by the checkout's own code — which is exactly the card's second reproduction — is indistinguishable at the seam from one delivered by the terminal. Rejected: re-raising `KeyboardInterrupt` while converting every other `BaseException`, which would leave the card's own reproduction unfixed. The narrow window is the mitigation: the seam covers the load and the proof call, not the whole program.

KTD3. **One shared conversion, and `ContractError` passes through it untouched.** Both seams route through the same small helper so the two cannot drift apart, and that helper re-raises `ContractError` unchanged before converting anything else. Without the pass-through, a real verification failure raised by `proof.verify` through `api.fail(...)` — which is an ordinary `Exception` — would be relabelled `code: engine` and lose the diagnosis the proof made, silently degrading today's error messages (R3). Rejected: duplicating the handler at both sites, which is how the two seams would drift on the next edit.

**One clarification a literal reading needs.** At the `module()` loader the repair is strictly additive: an ordinary `Exception` keeps today's treatment, including a `ContractError`, which `module()` has always rewritten into its `engine import` message. Only a `BaseException` that is not an `Exception` is newly converted there. The `ContractError` pass-through is required at the `proof.verify` seam, which is the one that can see a verification diagnosis worth preserving. Applying the pass-through to the loader as well would change behaviour on a path this card is not about and would put R5 at risk.

KTD4. **Release as a patch bump of the Saga plugin, and re-check the number at merge time.** The change fixes behaviour and adds no surface, so `0.159.0` becomes `0.159.1`. Two sibling cards, issues 997 and 998, run after this one in the same lane and will each bump the same three files. The repository's own journal records this collision recurring twice against the same branch — `LEARNINGS.md` entry on the `0.150.0` / `0.151.0` sibling collisions — where a sibling merged first and the diff-aware release-surface guard went red on a version that was correct when it was chosen. Before merge, re-read `plugins/saga/.claude-plugin/plugin.json` on `origin/main` and re-bump if a sibling landed first.

## Implementation Units

### U1. Close the two checkout-execution seams

Convert a `BaseException` from checkout code into the documented refusal envelope, at the load seam and at the proof-call seam, without touching the top-level handler.

**Goal:** R1, R2, R3, R4, R5 hold in `plugins/saga/scripts/plan_save_contract.py`.

**Requirements:** R1, R2, R3, R4, R5

**Dependencies:** none

**Files:** `plugins/saga/scripts/plan_save_contract.py`

**Approach:** Add one small conversion used by both seams (KTD3). It re-raises a `ContractError` unchanged, and turns anything else into a `ContractError` carrying the checkout file as `source` and `code` = `engine`, so it flows into the existing `except Exception` in `main()` and out through the existing `report(2, ...)` path — no new exit code, no new output shape. Widen `module()`'s handler on `plan_save_contract.py:88` from `except Exception` to `except BaseException`, keeping its present remedy sentence (`...; restore this checkout and its Python dependencies`) and its present treatment of ordinary exceptions unchanged (KTD3's clarification). Wrap the `proof.verify(...)` call on `plan_save_contract.py:436` in the shared conversion, which re-raises `ContractError` untouched there. Leave `main()`'s handler at `except Exception` (KTD1) and add a short comment there saying why it must stay narrow, so the next reader does not "fix" it into a broad catch and break `--help`. Record the Ctrl-C trade of KTD2 as a comment at the seam.

**Patterns to follow:** the existing `fail()` / `ContractError` / `report()` refusal path in the same file; the `code` vocabulary already in use (`engine`, `verification`, `filesystem`, `syntax`, `usage`).

**Test expectation:** covered by U2; this unit lands with U2 in one commit.

### U2. Regression tests at the real command-line boundary

Pin all three escapes and the `--help` exemption through a subprocess against a temporary checkout, the way the existing boundary suite already does.

**Goal:** R6, and R3's pass-through, are enforced by tests that go red if the repair is reverted.

**Requirements:** R3, R4, R5, R6

**Dependencies:** U1

**Files:** `tests/test_saga_plan_contract_boundaries.py`, `tests/test_saga_plugin.py`

**Approach:** Add one test to `tests/test_saga_plan_contract_boundaries.py` following the shape already used there: build a temporary checkout with the `tree()` helper imported from `tests/test_saga_spec_consumer_row.py`, mutate the checkout's own `plugins/saga/scripts/plan_save_proof.py`, and run the checkout's `plan_save_contract.py` in a subprocess with `--root` pointing at it, restoring the file between probes exactly as `test_contract_cli_without_pytest` (`tests/test_saga_plan_contract_boundaries.py:248`) does with the script text. Four probes: a module-level `sys.exit(7)`; a module-level `raise KeyboardInterrupt(...)`; a `sys.exit(...)` as the first statement of `verify()`; and an unmutated baseline. The first three must each give exit 2 with parseable JSON on standard output whose `code` is `engine` and whose `file` names the proof script; the baseline must give exit 0 with `outcome: valid`. Add a `--help` assertion in the same test — exit 0, usage text, and no JSON — so the KTD1 constraint is pinned next to the change that depends on it. Add a separate assertion that a `ContractError` from the proof keeps `code: verification`, by reusing an existing content mutation that the proof already rejects, so KTD3's pass-through cannot regress. Then add the new test function's name to the required-test inventory in `tests/test_saga_plugin.py` (the list at `tests/test_saga_plugin.py:180-192`), which asserts exactly one definition per named guard, so the regression guard cannot be deleted quietly.

**Patterns to follow:** `test_contract_cli_without_pytest` (`tests/test_saga_plan_contract_boundaries.py:248`) and `test_contract_cli_resolves_the_engine_from_the_checkout` (`tests/test_saga_plan_contract_boundaries.py:343`) for the subprocess-against-a-temporary-checkout shape; `tree()`, `cli()` and the `contract_api` fixture in `tests/test_saga_spec_consumer_row.py:37-76`, which the boundaries file already imports. Note that `test_plan_renderer_refusals_and_rollback`, named in the `tests/test_saga_plugin.py` inventory, lives in `tests/test_saga_spec_consumer_row.py:515`, not in the boundaries file — the inventory scans both files, so a new boundaries test is registered in the same tuple.

**Test expectation:** the new test is the deliverable. Mutation check: reverting `except BaseException` in `module()` back to `except Exception` must fail the first two probes, and removing the `verify()` wrapper must fail the third.

### U3. Release surfaces and the engineering journal

Ship the version bump and the durable learning in the same commit as the fix.

**Goal:** R7 and R8 hold; the installed-plugin metadata tells the same story as the diff.

**Requirements:** R7, R8

**Dependencies:** U1, U2

**Files:** `plugins/saga/.claude-plugin/plugin.json`, `.claude-plugin/marketplace.json`, `plugins/saga/CHANGELOG.md`, `docs/engineering-journal/LEARNINGS.md`

**Approach:** Bump the Saga plugin from `0.159.0` to `0.159.1` in `plugins/saga/.claude-plugin/plugin.json` and in the `saga` entry of `.claude-plugin/marketplace.json` (currently `0.159.0` at line 86), and add a matching `## [0.159.1]` entry to `plugins/saga/CHANGELOG.md` naming the envelope fix and issue 996. Immediately before the pull request merges, re-read the version on `origin/main` and re-bump if a sibling card landed first (KTD4). Add a dated `LEARNINGS.md` entry whose generalizable rule is the mechanism: a handler that promises to cover everything a subprocess-style boundary can raise must name `BaseException`, because `except Exception` leaves `SystemExit` and `KeyboardInterrupt` outside the envelope — and the matching narrow handler that makes `--help` work is the reason the repair belongs at the boundary rather than at the top.

**Test expectation:** none -- release bookkeeping and journal prose; the repository's own release-surface parity checks in `scripts/gate.sh` cover the version files.

## Scope Boundaries

**Out of scope — the sibling cards.** Issue 997 (`adv10`, P3: a missing PyYAML crashes outside the envelope and reports drift at exit 1) and issue 998 (`agentusab06`, P3: `plan_save_proof.py --help` exits 0 with no output) are the other two children of the grouping issue 1005. They run after this card in the same lane and each opens its own pull request. Do not fix them here, even though they touch the same two files.

**Out of scope — the top-level handler's other blind spots.** Anything a `BaseException` could reach that is *not* checkout code executed through `runpy` stays as it is. Widening the tool's general failure handling is not this card.

**Out of scope — the contract, the schema and the rendered documentation.** `plan_save_contract.v3`, `plugins/saga/references/plan-save-contract.yaml`, and the generated regions in the Plan skill and the Saga specification are untouched. This card changes failure handling only.

**Deferred to follow-up work.** None identified. If the mutation checks in U2 reveal a further uncovered seam where checkout code executes outside a converting handler, file it against the grouping issue 1005 rather than widening this card.

## Verification

Run from the repository root of this worktree:

```bash
uv run pytest tests/test_saga_plan_contract_boundaries.py tests/test_saga_spec_consumer_row.py tests/test_saga_plugin.py -v
uv run ruff check .
uv run ruff format --check .
uv run mypy plugins/ scripts/ tests/ --ignore-missing-imports
```

A clean run of those four is the inner loop, not the gate. Before pushing, run the whole 24-step gate in the background as `CLAUDE.md` prescribes and read `result.txt` for the verdict:

```bash
GATE_LOG_DIR=/tmp/gate-run bash scripts/gate.sh > /tmp/gate.log 2>&1 &
```
