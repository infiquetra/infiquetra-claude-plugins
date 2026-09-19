# Code review — mission-control triage suggestions (issue 1035)

## Review result

| Field | Value |
|---|---|
| Target | branch `issue/1035` against base commit 866d3670 |
| Reviewed revision | the tree committed as `89488284` (the repair commit). Any commit after it touches this artifact only and changes no reviewed code. |
| Linked issue | infiquetra/infiquetra-claude-plugins#1035, child of #1019 |
| Linked plan | `docs/plans/2026-09-19-mission-control-triage-suggestions-plan.md` |
| Linked work session | `docs/work-sessions/2026-09-19-mission-control-triage-suggestions.md` |
| Linked saga | `issue-1035` |
| Mode | interactive (the skill's default) |
| Backend | `inline` |
| Transport | **deviation, recorded:** the lens pass ran in the reviewing thread, one lens at a time, because this driver may spawn no subagents. The roster's `saga:readonly-verifier` / worktree-isolated fan-out was not used. Every finding below is still evidence-cited. |
| Cycles | 2 |
| Outcome | **accepted** |
| Scope check | CLEAN |

## Lens selection

The caller supplied `accept-recommended`, which is the approval record; no operator question was asked.

**Always-on four (auto-run):** architecture-maintainability, correctness, security, testing.

**Conditionals recommended and approved,** each with its reason:

| Lens | Why this diff warrants it |
|---|---|
| `api-contract` | Adds two command-line flags and three optional keys to the prepared-issue sidecar, which `create-prepared` reads |
| `reliability` | Adds an outbound network call with a failure policy, and the change stands or falls on that policy being right |
| `privacy` | Sends issue text to a third-party vendor |
| `adversarial` | The whole change rests on one load-bearing claim — that nothing is applied |
| `documentation-clarity` | Two skills, a reference document and a changelog are operator-facing guidance |
| `agent-usability` | Alters a command and a skill that agents consume, plus a machine-readable sidecar |

**Not selected:** `deployment-infrastructure` (no infrastructure, rollout or migration surface),
`performance` (one opt-in call, no latency-sensitive path), `previous-comments` (no pull request
existed at review time), `accessibility-human-usability` (the printed output is covered by
documentation-clarity).

## Built-versus-planned audit

| Unit | State | Evidence |
|---|---|---|
| U1 suggestion module | DONE | `plugins/mission-control/scripts/triage_suggest.py`; 40 tests |
| U2 prepare path | DONE | `sdlc_manager.py` `_collect_suggestions`, `issue_prepare`; 30 tests |
| U3 verdict and override logging | DONE | `_record_suggestion_verdicts`; verdict, override, failure and unwritable-log tests |
| U4 labels union | DONE | `_suggest_label_union`, `labels_auto_label`; 16 tests |
| U5 the card's acceptance test | DONE | `tests/test_mission_control_suggest.py`, 7 tests |
| U6 documentation and release surfaces | DONE | Both skills, the labels reference, 2.16.0 to 2.17.0 across four surfaces |

**Scope check: CLEAN.** No file outside the plan's named set changed, and every plan requirement
maps to shipped code.

## Cycle 1 findings

| # | Priority | File | Finding | Resolution |
|---|---|---|---|---|
| 1 | **P1** | `sdlc_manager.py` `_suggest_label_union` | The candidate set widened with **every** label the configured rules carry, including issue-TYPE labels — `title_contains_capability` adds `capability` and `needs-analysis`. The model would have been asked "does this warrant the `capability` label?", which is the prepare path's judgment leaking into the labels path, against the module's own docstring and plan R14a. Latent rather than live, because `auto_label_rules` is empty in the vendored schema, so an external `labels.json` was required to trigger it. | Fixed: `_label_widening_exclusions()` excludes the five type names and the routing labels; `candidate_labels` takes `exclude`. Three new tests, including one proving `documentation` survives (it is a content label in its own right even though the taxonomy pairs it with `context-update`) and one proving a rule-matched type label still appears in the union — excluded from the **question**, never from the **floor**. |
| 2 | P2 | `triage_suggest.py` `render_suggestions` | The board-status question offers 25 options and every one printed, putting twenty `0.00` entries on screen for one real answer. Observed in the live run, not in any test. | Fixed: zero-probability options are dropped and counted (`(+20 at 0.00)`). One test. |
| 3 | P2 | `sdlc_manager.py` `_collect_suggestions` | `_issue_types_policy_text()` read the 309-line reference twice per prepare. | Fixed: read once into a local. |
| 4 | P2 | both paths | The documented "client could not be loaded" branch had no test in either path. | Fixed: one test each, driving the shim loader to raise. |
| 5 | P2 | `sdlc_manager.py` dispatch | No test proved the command-line flags reach `issue_prepare`. `--help` shows a flag exists; it does not show `main()` forwards it, so a dispatch arm that dropped `suggest=` would have left every other test green. | Fixed: two tests drive `main()` with a captured `issue_prepare`. |
| 6 | P2 | both skills | Neither told the operator that the issue text leaves the machine for a third-party endpoint. They named the environment variable and stopped there. | Fixed: both skills gain a "Where the text goes" paragraph naming the vendor, the redaction, and the data rule. |
| 7 | P3 | `triage_suggest.py` | A dead `AskCallable` alias with a comment claiming it was re-exported; it was not in `__all__` and had no consumer. | Removed, with its now-unused `Callable` import. |

## Cycle 2

Every cycle-1 finding re-checked against the repaired code and confirmed closed. No new finding at
any priority.

## Independent gates

| Gate | State | Evidence |
|---|---|---|
| Hard test gate (`change_kinds: ["behavior"]`) | PASS | Every feature-bearing unit carries happy-path, edge-case, failure-path and integration coverage |
| Lint (`ruff check`) | PASS | All checks passed |
| Format (`ruff format --check`) | PASS | 546 files already formatted |
| Types (`mypy plugins/ scripts/ tests/`) | PASS | No issues found in 365 source files |
| Release-surface parity | PASS | All plugins in parity |
| Release-surface diff guard | PASS | All changed plugins bumped their release surfaces |
| Marketplace sync and validator | PASS | Matches the plugin fleet; 0 errors |
| Mutation checks | PASS | Six deliberate mutations, each killing exactly its intended guard |

## The security and privacy read, stated plainly

**The key never enters this plugin's code.** `TYPESAFE_API_KEY` appears in `plugins/mission-control/`
only as a variable *name* in help text, prose and one test's `monkeypatch.setenv`. No value is
hard-coded, and the client that issue 1032 shipped is the only thing that reads it. Two tests place
a sentinel key in the environment and assert it appears in no draft, no sidecar, no log line and no
printed output.

**What leaves the machine:** the draft body and this repository's own issue-types reference on the
prepare path; the issue title and body on the labels path. All of it is repository content the data
rule permits, and all of it passes through the client's `prepare_state`, which redacts and then
truncates and is the only path to a transport.

**The load-bearing claim holds structurally.** `triage_suggest.py` contains no assignment to any
draft field and no write of any kind, and `_collect_suggestions` does not mutate the `PreparedIssue`
it is handed — both verified by direct search, not by reading. The suggestion is collected after
readiness is settled, so it cannot reach a field, a gap or a label.

## One finding that belongs to the parent card, not this one

**The parent card's third acceptance criterion is already false on `main` and this card widens the
gap.** Issue #1019 asks that

```
grep -rn "TYPESAFE_API_KEY" plugins/ | grep -v getenv | wc -l
```

print `0`. On base commit 866d3670 it prints **2** — `KEY_ENV = "TYPESAFE_API_KEY"` in the client
and one line of the fleet-core reference, neither containing the word `getenv`. On this branch it
prints **10**, the additions being help text, changelog and skill prose, two test docstrings and one
`monkeypatch.setenv`. Every one is the variable's *name*; none is a key value.

The criterion's intent — "the key is read from the environment only" — is satisfied and is worth
keeping. Its literal form cannot pass and never could. It needs re-expressing before #1019 is
closed, for example by grepping for an assignment of a literal secret rather than for the variable
name. Raised here because this card is what makes the discrepancy obvious; it is not this card's to
fix.

## Outcome

**accepted.** One P1 found and fixed, five P2 and one P3 found and fixed, zero open findings, every
independent gate green. The transport deviation above is the one departure from the roster contract
and is recorded rather than hidden.
