# Code review — issue 1037, the shaping judgments

**Outcome: `accepted`.** One P1 and two P2s were found and repaired in this cycle; nothing blocking remains. The P1 was real and measured, not stylistic: the dedupe judgment was making one request per candidate pair, which at its own documented cap meant 2,016 sequential calls inside a conversational command.

## Review result

| Field | Value |
|---|---|
| Target | branch `issue/1037` |
| Base | `866d3670` (`origin/main`) |
| Reviewed revision | `09265526` — the head after the repairs below |
| Pre-repair revision | `9ca3e767` — where the findings were raised |
| Mode | interactive |
| Cycle | 1 of 3 |
| Backend | inline |
| Outcome | `accepted` |
| Blocking findings remaining | none |
| Plan | `docs/plans/2026-09-19-shaping-judgments-plan.md` |
| Work session | `docs/work-sessions/2026-09-19-issue-1037-shaping-judgments.md` |

## Transport deviation, recorded

The lens fan-out normally spawns one read-only verifier subagent per lens. This run spawns none: the coordinator's instruction for this card forbids subagents, so every lens ran sequentially in the driver's own thread, one at a time. That is a transport change, not a policy change — the lens set, the findings schema, the acceptance rule and the outcome are unchanged, and Code Review still owns the verdict. The cost is that no lens had an independent context window, so cross-lens independence is weaker than a fan-out would give. Recorded here rather than left implicit.

Lens selection was `accept-recommended`, supplied by the caller, which the roster treats as the approval record — no operator question was asked.

## Lenses run

The four always-on lenses, plus seven conditionals whose domain this diff genuinely touches.

| Lens | Why it applied | Result |
|---|---|---|
| architecture-maintainability | always-on | clean; the registry-as-data shape matches `jev_verbs.py`, the shim load matches `execution_spec.py` |
| correctness | always-on | **F1 (P1)**, **F2 (P2)** |
| security | always-on | clean; the key never leaves the client, the module stores no state, the log records hashes not text |
| testing | always-on | **F4 (P2)** |
| privacy | the diff sends document text to a third-party vendor | clean; the state is document text, redaction is on the client's only transport path, the office-hours state is the composed frame rather than dialogue |
| reliability | a network call inside an interactive command | **F3 (P2)** |
| performance | a pairwise fan-out whose size grows with the input | folded into F1 |
| api-contract | a new command-line surface and a result envelope other code reads | clean; subcommands are generated from the registry and a guard binds the two |
| adversarial | the module's entire input is model output | clean; no answer reaches control flow except through an explicit threshold comparison |
| documentation-clarity | five changed files are skill prose | clean |
| agent-usability | the skill prose is read by agents, not people | clean; each addition names the judgment, its phase, what it informs and its fail-open side |
| previous-comments | not applicable — no pull request existed at review time | not run |
| accessibility-human-usability | not applicable — no human interface surface | not run |

## Findings

| # | Priority | Lens | Where | Finding | Status |
|---|---|---|---|---|---|
| F1 | P1 | correctness, performance | `plugins/saga/scripts/shaping_judgments.py`, `dedupe_groups` | One request per candidate pair. Measured: 20 candidates cost 190 requests; at the documented cap of 64 candidates, 2,016 requests, roughly 13 minutes at the research document's measured 330 to 430 ms per call. It also contradicted the plan's own R9 ("batched across pairs"), KTD2, and house rule 5 of the fleet-core reference ("batch every question about one state into one request"). | **fixed** in `09265526` |
| F2 | P2 | correctness | same, the grouping return | A run in which every pair call failed returned `ok: true` with groups that read as judged. Under-grouping caused by an outage is indistinguishable from a real answer, which is the failure the repository's no-lies rule exists to prevent. | **fixed** — the result now carries `pairs_judged` and `pairs_unjudged`, and `ok` is false when nothing was judged |
| F3 | P2 | reliability | same, `judge`'s logging block | A verdict-log write failure propagated out of the call. `jev_log` raises `RuntimeError` on an unwritable log, so an advisory judgment could kill a conversational command because the fleet's measurement directory was broken — the opposite of the fail-open rule the card is built on. | **fixed** — suppressed, catching the wrapping `RuntimeError` as well as `OSError` |
| F4 | P2 | testing | `tests/test_shaping_judgments.py` | No test constrained the request count, so F1 could not have been caught by the suite. | **fixed** — `test_pairs_are_batched_not_one_request_each` and `test_a_batch_carries_each_candidate_once_and_one_question_per_pair` |
| F5 | P3 | correctness | `_is_empty_state` | A dict whose values are all empty (`{"focus": ""}`) is not treated as empty, so `tactical_scope_union("")` spends one request on nothing. Harmless — the keyword floor still answers — and narrowing it risks declining a state that legitimately carries an empty field beside a full one. | open, recorded |
| F6 | P3 | api-contract | the `axis` registry entry | `axis` carries an empty question map because its options come from the run's axis list, so `judge(state, "axis")` without `questions` raises rather than answering. The message says so and the front door builds them, but a caller iterating the registry generically hits it. | open, recorded |

## Built-versus-planned audit

**Scope check: CLEAN.** Nothing was built that the plan did not ask for. One thing was built that the plan described only in prose: the plan said ideate's tactical-scope keyword list "stays the floor", and the implementation made that union real code (`tactical_scope_union`) rather than an instruction in a skill file. That is a strengthening within the stated requirement, not drift, and it is what let F4's sibling guard exist at all.

| Plan item | State | Evidence |
|---|---|---|
| U1 — module, registry, front door | DONE | `shaping_judgments.py`; eleven subcommands generated from the registry, guarded by `test_the_subcommands_and_the_registry_carry_the_same_names` |
| U2 — six ideate judgments | DONE | registry entries plus `dedupe_groups`, `axis_questions`, `tactical_scope_union` |
| U3 — four brainstorm judgments | DONE | registry entries plus `CONSEQUENCE_FACTORS` and `READINESS_CRITERIA` |
| U4 — office-hours routing choice | DONE | the `route` entry; `test_the_routing_answer_carries_every_route` |
| U5 — skill wiring | DONE | three skills and two references; `test_every_judgment_is_named_in_the_skill_that_calls_it` |
| U6 — release surfaces and journal | DONE | saga `0.160.0` across four surfaces; parity, the diff guard and the marketplace validator all green |
| R1 to R20 | DONE | every requirement maps to a unit above; R9's "batched across pairs" was NOT done at first pass and is what F1 repaired |

## Guard quality

Every new guard was watched failing before it was trusted, which is the property that separates a test from a decoration.

The four skill-wiring guards were written before the skills were edited and run: they failed, naming the three skills that did not yet call the module.

Two behavioral mutations were applied to the finished module. Returning only the first member of each dedupe group killed `test_grouping_never_removes_a_candidate` and `test_matched_candidates_share_one_group`. Restoring `axis_spread` to the per-idea rubric killed `test_the_rubric_excludes_axis_spread`.

F1's guard was confirmed by measurement on both sides: the same script reported 190 requests for 20 candidates before the fix and 2 after.

## Residual risk

The eleven judgments' wording has been exercised live for two of them — `readiness` against a real requirements document, and `dedupe` against a three-candidate set whose right answer was known. The other nine have been exercised only through a fake client, so their question wording is unproven against the model even though their plumbing is not. That is the expected state for a card that ships every judgment in suggest mode: the evaluation harness, not this review, is what establishes whether a question asks what it means to, and parent issue 1019 owns that measurement.
