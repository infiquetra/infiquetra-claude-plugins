---
title: Typed judgments inside ideate, brainstorm, and office-hours
type: feat
status: active
date: 2026-09-19
origin: docs/analysis/2026-09-18-typesafe-jev-integration-research.md
backend: inline
---

# Typed judgments inside ideate, brainstorm, and office-hours

## Summary

Add one saga script, `plugins/saga/scripts/shaping_judgments.py`, that asks TypeSafe's Jev model the small repeated judgments the three shaping commands make by hand today, batched one request per body of text, through the fleet-core client that issue 1032 shipped. Every answer is advisory: it informs a judgment the command already makes, it never becomes a gate, and it never drops anything.

## Problem Frame

The three shaping commands — `/ideate`, `/brainstorm`, `/office-hours` — each make several small judgments per run that today are made by an orchestrating model reading prose. Those judgments are inconsistent between runs (the same candidate list dedupes differently), they scale badly (forty ideation candidates is 780 pairwise comparisons), and they leave no record anyone can score later.

The TypeSafe research (`docs/analysis/2026-09-18-typesafe-jev-integration-research.md`, requirements R9, R12 and R13) identifies exactly which of those judgments are typed-question shaped: a yes/no probability, a pick from a fixed set with its distribution, or a position on an ordered rubric. Issue 1032 already shipped the client, the redaction rule, the retry policy, the verdict log and the cache; nothing here adds a second client or any new network code.

The operator's recorded rule for brainstorm governs the whole card: **add no rigidity without demonstrated value.** That rule, and the rejected "fixed adversarial convergence loop" candidate beside it in the agent-operations change ledger, are why every judgment here is advisory, why none becomes a gate, and why the dialogue and the critique are untouched.

## Requirements

**The module**

- R1. One new file, `plugins/saga/scripts/shaping_judgments.py`, holds every judgment in this card. It loads the fleet-core client through the vendored `plugins/saga/scripts/fleet_commons_shim.py` (the house mechanism, as `plugins/saga/scripts/execution_spec.py:60` does) and contains no HTTP code, no retry code, no redaction code and no second client.
- R2. Question sets are declarative data, in the shape `plugins/fleet-core/scripts/fleet_commons/jev_verbs.py` established: a name, the state it expects, its question map, and its confidence floor. Adding a judgment is a registry entry plus a test, not a code branch. The floor defaults to fleet-core's `0.6` rather than a number invented here, for the reason that file's own docstring gives — every caller reads the same number; the evaluation harness sets the real ones later.
- R2a. The skills call the module as a shell command, the way every other saga script is invoked (`python3 plugins/saga/scripts/shaping_judgments.py <judgment> ...`). There is no Python caller and no import from a skill.
- R3. Every judgment about one body of text is one request. The module's entry point takes a state and a judgment name, builds the whole question map, and calls `typesafe_client.ask` once.
- R4. The entry point takes an injected `ask` callable defaulting to `typesafe_client.ask`, so every test drives a fake and no test touches the network.
- R5. Every result is advisory. The module returns the typed answers, each answer's confidence via `typesafe_client.answer_confidence`, and whether the confidence cleared the judgment's floor. It never returns an instruction, never selects an option on the caller's behalf, and no skill gate is made conditional on it.
- R6. Every judgment fails open, and each judgment's documentation names which side it fails open to. A non-`ok` client status, an absent `TYPESAFE_API_KEY`, or a timeout leaves the calling command behaving exactly as it does today, with a one-line non-blocking note.
- R7. State is document text: the ideation candidate text, the brainstorm or requirements document text, and — for office-hours — the settled frame the skill composes in its Phase 2 (the real problem plus the key assumptions), never the dialogue that produced it. The module never reads or passes a session transcript, because the fleet-core data rule excludes a transcript even after redaction. It never passes a credential. The key is read from the environment by the client alone; it is never printed, logged, or written to any file this card creates.
- R8. Every call the module makes records a verdict through the fleet-core verdict log with a `decision_id` naming the command and the judgment, so the evaluation harness can score it later.

**Ideate (research requirement R12)**

- R9. **Pairwise dedupe.** A yes/no question per candidate pair, batched across pairs, producing groups. Grouping never deletes: every candidate identifier that enters appears in exactly one output group, and a group of one is a normal result. The candidate cap is one named module constant with a default of **64**, derived from ideate's own volume ceiling — six frames at roughly eight candidates each (`plugins/saga/skills/ideate/SKILL.md`, Phase 0.4), plus three to five cross-cutting combinations and at most two recovery frames of three to five ideas each. Above the cap the judgment declines and the skill merges as it does today.
- R10. **Axis coverage.** A pick-one question per candidate over the Phase 1.5 axis list, with an explicit "no axis fits" option so a mislabelled candidate is visible rather than forced.
- R11. **Grounding-fit.** A pick-one question over the four Phase 0.2 outcomes (`plugins/saga/skills/ideate/SKILL.md:88`, `:111`, `:120`, `:133`) carrying a confidence floor. A confident answer never suppresses a question the skill would otherwise ask: the "ASK when unsure, never silently auto-route" rule at `:80` is unchanged, and the answer is evidence the skill weighs, not permission to skip the gate. The same holds for R15 below.
- R12. **Tactical scope.** A yes/no question over the focus hint, unioned with the existing keyword list at `plugins/saga/skills/ideate/SKILL.md:163`. The keyword list stays the floor: the judgment may only add tactical-scope detections, never remove one.
- R13. **Critique rubric scores.** An ordered-rubric question per survivor per rubric dimension, over the per-idea dimensions named in `plugins/saga/skills/ideate/references/convergence-and-partnership.md:46-60`: groundedness, basis strength, expected value, novelty, pragmatism, leverage on future work, implementation burden, and overlap with stronger ideas. **Axis spread is excluded** — that same reference states it is "a list-level concern, not per-idea", so scoring it per survivor would answer a question the rubric does not ask. The scores sit beside the critics' prose verdicts; they do not replace a verdict and do not promote or cut anything.
- R14. **Revival check.** A yes/no question asking whether the supplied new evidence addresses the recorded rejection reason, feeding step 1 of the revival state machine (`convergence-and-partnership.md:218`). The state machine's gate 2a is unchanged and still cannot be cleared by a score.

**Brainstorm (research requirement R13)**

- R15. **Scope tier.** A pick-one question over `lightweight`, `standard`, `deep-feature`, `deep-product`, matching Phase 0.4's classification and its Deep sub-mode, with a confidence floor below which the skill asks its existing single disambiguating question.
- R16. **Consequence factors.** One yes/no question per consequence factor, over a single named factor list in the module. Code never aggregates those probabilities into a level, a tier, or a score: brainstorm's "No named tiers are used" rule holds unchanged.
- R17. **Question ordering.** Two ordered-rubric questions per candidate operator question — its consequence and its uncertainty — so code can order them. The skill's rule that a rigor gap found in Phase 1.2 is never filtered out by the consequence test is unchanged; ordering is not filtering.
- R18. **Readiness.** A batch of yes/no questions over a requirements document, one per readiness criterion, run before the Phase 4 `/doc-review` handoff. It is a suggestion shown to the operator; `/doc-review` still decides. The criteria are one named list in the module, each drawn from `plugins/saga/skills/brainstorm/references/requirements-sections.md`: the Summary states what is proposed rather than restating the problem; the Requirements are specific enough to plan without inventing behavior; conditional requirements carry acceptance examples; scope boundaries name what is out; dependencies and load-bearing assumptions are surfaced; no "Resolve before planning" question remains open; and a planner reading cold would not need to ask the operator anything. Seven criteria, seven probabilities.

**Office-hours (the surviving part of research requirement R9)**

- R19. A pick-one question over the Phase 3 routes — `/ideate`, `/brainstorm`, `/plan`, `/strategy`, and "drop it" — asked over the settled frame from Phase 2, whose full probability distribution is shown to the operator. It never routes: the existing `AskUserQuestion` gate still runs, and the distribution is evidence for the pre-selection, not a substitute for the question.

**Release surfaces**

- R20. `plugins/saga/.claude-plugin/plugin.json`, `.claude-plugin/marketplace.json` and `plugins/saga/CHANGELOG.md` all carry the same new saga version, bumped from main's `0.159.3` to `0.160.0`.

## Key Technical Decisions

**KTD1 — the question sets live in saga, not as new fleet-core verbs.** These eleven judgments quote saga's own prose contracts: ideate's four grounding-fit outcomes, its rubric dimensions, brainstorm's consequence factors, office-hours' route list. Putting them in `jev_verbs.py` would move saga's skill prose into fleet-core and make every wording edit a fleet-core release. The two existing generic verbs, `dedupe` and `readiness`, ask different questions from a different state shape, so reusing them would silently change what is being asked. Everything fleet-wide — the client, redaction, retry, the verdict log, the cache, the data rule — still comes from fleet-core; only the questions are saga's.

**KTD2 — one request per body of text, with the pairwise case bounded.** Independent questions over one state go in one request, per the vendor's guidance and house rule 5 of `plugins/fleet-core/references/typesafe.md`. Pairwise dedupe is the one judgment whose question count grows with the input: it packs pairs into requests sized against the client's 32,000-token state budget and declines above the named candidate cap of R9, returning "not judged" so the skill merges the way it does today. An unbounded fan-out inside an interactive command is the failure this cap prevents.

**KTD3 — a judgment groups; it never removes.** The dedupe output is a grouping over the input identifiers, and the guard test asserts that the set of identifiers coming out equals the set going in. This is what keeps ideate's stated quality mechanism intact: explicit rejection with reasons, never a silent drop by a probability.

**KTD4 — the consequence factors come from one named list, guarded against the existing test.** `tests/test_brainstorm_judgment_contract.py` already pins six factor phrases into the brainstorm skill. The module names the same list once, and a new guard test compares the module's list to that predicate's, so a factor renamed in the skill and not in the module reds rather than drifting.

**KTD5 — advisory means no gate anywhere, and each judgment names its fail-open side.** No skill's existing gate becomes conditional on an answer, no answer is a precondition for a phase, and the operator can ignore any of them without a prompt. Every judgment's documentation states what happens when the call fails, which is always "the command behaves as it does today".

**KTD6 — the office-hours distribution is shown, never acted on.** The choice's probabilities become the evidence line under the routing question; the blocking question, its options, and the hard gate that office-hours never executes are untouched.

**KTD7 — no saga tick.** Issue 1030's release makes these three commands stateless, so nothing here writes saga state. The only record written is the fleet-core verdict log, which lives at `~/.claude/typesafe/` outside the repository.

**KTD8 — the version bumps from main's number and the coordinator serializes.** This plan bumps saga from `0.159.3` (main at commit `866d3670`) to `0.160.0`. Issue 1036 bumps saga in parallel and the integration branch `parent/1018` already carries a `0.160.0`; the coordinator serializes sibling version bumps at merge time, so a re-bump at merge is expected and is not a defect in this branch.

## Implementation Units

### U1. The module, its registry, and its command-line front door

Stand up `shaping_judgments.py` with the declarative registry, the single batched entry point, the injected `ask` seam, the advisory result envelope, and an argparse front door whose subcommands are built from the registry.

**Goal:** one place every judgment in this card is defined, called, and rendered, with nothing skill-specific hard-coded into the call path.

**Files:** `plugins/saga/scripts/shaping_judgments.py` (new).

**Approach:** mirror the shape `plugins/fleet-core/scripts/jev.py` and `jev_verbs.py` established — a frozen dataclass per judgment carrying its name, summary, state help, question map and confidence floor; `judge(state, name, *, ask=...)` building the map and making one call; subcommands generated by iterating the registry so a registered judgment with no subcommand cannot exist. The document-shaped judgments take `--doc <path>` and read the file as the state; the list-shaped ones take `--state` / `--state-file` JSON, matching the existing tool's flags. Output is JSON on standard output; a non-`ok` status prints the advisory note and exits zero, because a failed advisory call is not a failed command.

**The registry — the eleven judgments, their names and their state:**

| Judgment name | Requirement | Command | State it takes |
|---|---|---|---|
| `dedupe` | R9 | `/ideate` | a candidate list as JSON, each entry an identifier and its text |
| `axis` | R10 | `/ideate` | a candidate list plus the Phase 1.5 axis list, as JSON |
| `grounding-fit` | R11 | `/ideate` | the topic and the grounding summary, as JSON |
| `tactical-scope` | R12 | `/ideate` | the focus hint text, as JSON |
| `rubric` | R13 | `/ideate` | a survivor list as JSON |
| `revival` | R14 | `/ideate` | the cut idea, its recorded rejection reason, and the new evidence, as JSON |
| `scope-tier` | R15 | `/brainstorm` | the seed and scan summary, as JSON, or `--doc` |
| `consequence` | R16 | `/brainstorm` | the same state as `scope-tier` |
| `question-order` | R17 | `/brainstorm` | the candidate question list as JSON |
| `readiness` | R18 | `/brainstorm` | `--doc <requirements document>` |
| `route` | R19 | `/office-hours` | the settled frame text, as JSON or `--doc` |

The names are the registry keys, the subcommand names, and the `decision_id` suffixes, so the three cannot drift apart.

**Test scenarios** (`tests/test_shaping_judgments.py`):

- every registered judgment round-trips through a fake `ask` and its answer keys match its declared question map, parameterized over the registry so a new judgment without coverage reds;
- the registry's key set is exactly the eleven names in the table above;
- an empty state — a zero-length candidate list, or an empty document — returns an advisory result with a stated reason and makes no call;
- the front door's subcommand set equals the registry's names, so tool and registry cannot drift;
- `judge` calls the injected `ask` exactly once for a single-document judgment;
- a fake `ask` returning a `timeout` status yields an advisory result with `ok` false and a note, and the process exits zero;
- a state carrying a secret-named key is not what the module sends — the module hands raw state to the client and the client's own redaction is on the only path to a transport, asserted by calling through a fake that captures what `ask` received.

### U2. The six ideate judgments

Register dedupe, axis coverage, grounding-fit, tactical scope, the rubric scores and the revival check, plus the grouping code dedupe needs.

**Goal:** the mechanical judgment work around ideate's critique becomes consistent, without the critique itself changing.

**Files:** `plugins/saga/scripts/shaping_judgments.py`.

**Approach:** five of the six are registry entries only. Dedupe additionally needs pair generation, packing pairs into budget-sized requests, and a grouping step that unions pairs above the threshold into groups — the identifier-preserving grouping of KTD3, with a documented request cap above which it returns "not judged".

**Test scenarios** (`tests/test_shaping_judgments.py`):

- grouping over a fake that answers "same" for one pair returns groups whose combined identifier set equals the input identifier set, and no candidate is absent;
- a candidate no pair matched comes back as its own single-member group;
- a candidate list above the request cap returns "not judged" and makes no call;
- the grounding-fit judgment's criteria name all four Phase 0.2 outcomes;
- the tactical-scope result is a union: a fake answering "no" never clears a keyword-list hit.

### U3. The four brainstorm judgments

Register the scope tier, the consequence-factor nouls, the two question-ordering scores and the readiness batch.

**Goal:** brainstorm's four internal judgments become consistent across sessions with the dialogue untouched.

**Files:** `plugins/saga/scripts/shaping_judgments.py`.

**Approach:** the consequence-factor questions are generated from one named factor list (KTD4). The readiness criteria are likewise one named list, drawn from the hard floor and the material sections of `plugins/saga/skills/brainstorm/references/requirements-sections.md`, one yes/no question each.

**Test scenarios** (`tests/test_shaping_judgments.py`):

- the readiness judgment run against a real requirements document returns one probability per declared criterion, and the key set equals the criterion list;
- the module's consequence-factor list contains every factor `tests/test_brainstorm_judgment_contract.py::check_consequence_factors` pins, so a rename in either place reds;
- nothing in the module aggregates factor probabilities into a level or tier — asserted by the absence of any aggregate field in the result envelope;
- the scope-tier criteria are exactly the four tiers, and a below-floor confidence sets `floor_met` false.

### U4. The office-hours routing choice

Register the routing choice and render its distribution.

**Goal:** the operator sees how the routes compare before answering the routing question, and nothing routes itself.

**Files:** `plugins/saga/scripts/shaping_judgments.py`.

**Approach:** a pick-one question over the five Phase 3 routes whose result carries the full probability map. The renderer emits the distribution as a table; there is no code path from the answer to a command invocation.

**Test scenarios** (`tests/test_shaping_judgments.py`):

- the result carries a probability for every one of the five routes, including the ones not chosen;
- the module exposes no function that returns a command to run from a routing answer, so the answer cannot be executed.

### U5. Wire the three skills and their references

Tell each skill where in its phases to ask, what the answer is for, and what happens when the call fails.

**Goal:** an agent running any of the three commands knows the judgment exists, knows it is advisory, and knows the command behaves as before when it is unavailable.

**Files:** `plugins/saga/skills/ideate/SKILL.md`, `plugins/saga/skills/ideate/references/convergence-and-partnership.md`, `plugins/saga/skills/brainstorm/SKILL.md`, `plugins/saga/skills/brainstorm/references/requirements-sections.md`, `plugins/saga/skills/office-hours/SKILL.md`.

**Approach:** short additions at the phases the judgments serve — ideate Phase 0.2, 0.4, 2 (merge and dedupe, axis coverage), the convergence reference's rubric and revival sections; brainstorm Phase 0.4, 0.5, 1.3 and 4; office-hours Phase 3. Each addition names the judgment, states it is advisory and overridable, and names its fail-open side. No existing gate, question, rule or prohibition is rewritten, and no preset number of rounds or assurance level is introduced.

**Test scenarios** (`tests/test_shaping_judgments.py`):

- every judgment the registry declares for a skill is named in that skill's markdown, so a registered judgment no skill calls, or a skill naming a judgment that does not exist, reds;
- each skill's addition carries the word "advisory" and a stated fail-open behavior;
- `tests/test_brainstorm_judgment_contract.py`, `tests/test_brainstorm_predicate_wiring.py` and `tests/test_saga_doc_formatting.py` still pass unchanged, asserting that the dialogue rules, the helper ceilings, the no-named-tiers rule and the stacked-bold-label formatting contract all survived the edit.

### U6. Release surfaces

Bump saga and record the decisions.

**Goal:** the installed plugin metadata tells the same story as the diff.

**Files:** `plugins/saga/.claude-plugin/plugin.json`, `.claude-plugin/marketplace.json`, `plugins/saga/CHANGELOG.md`, `docs/engineering-journal/DECISIONS.md`.

**Approach:** saga `0.159.3` to `0.160.0` in all three release surfaces, a changelog entry naming the eleven judgments and their advisory posture, and the load-bearing decisions above recorded in `DECISIONS.md` in the same commit as the change.

**Test expectation:** the repository's existing version and release-surface drift guards cover this unit; no new test.

## Verification

The card's two acceptance criteria are the plan's exit test, run verbatim.

```bash
uv run python plugins/saga/scripts/shaping_judgments.py readiness --doc <a requirements document>
uv run pytest tests/test_shaping_judgments.py -q
```

The first must print one probability per readiness criterion — the criterion list of R18 — and it is the one command in this card that makes a live call, so it needs `TYPESAFE_API_KEY` in the environment and is not part of the offline test suite. The second must pass with no network access at all.

Beside those, the whole repository gate must be green before the pull request, per the repository's gate-coverage contract: `GATE_LOG_DIR=/tmp/gate-run bash scripts/gate.sh`, backgrounded, with the result read from `/tmp/gate-run/result.txt`.

## Scope Boundaries

**Out of scope — true non-goals.**

- No preset number of critique rounds and no assurance levels, per the operator's recorded rule and the rejected candidate in the agent-operations change ledger.
- No saga tick written by these three commands; they are stateless after issue 1030's release.
- No judgment becomes a gate, a precondition, or an automatic action in this card. Promotion above a confidence band happens only after the evaluation harness reports agreement, which is the parent card's work.
- No new HTTP code, no second client, no vendor SDK usage beyond what the fleet-core client already resolves.
- The office-hours Startup-versus-Builder mode choice from research requirement R9 is not in this card's objective and is not added here.
- No change to `/loop`, `/handoff`, verify panels, orchestrate review detection, or the delegation audit — all dropped with the machinery they targeted.

**Deferred to follow-up work.**

- Scoring these judgments with `jev eval` once roughly thirty real uses per decision have accumulated, and recording whether each stays advisory, is promoted, or is removed. That measurement belongs to parent issue 1019.
- Any threshold tuning. The floors shipped here are the registry's declared defaults; the harness, not a cookbook, sets the real ones.

## Risk Analysis and Mitigation

| Risk | Why it matters | Mitigation |
|---|---|---|
| Latency inside an interactive command | Live calls measured at 330 to 430 milliseconds; a per-pair fan-out would add minutes to ideate's merge step | One request per state (KTD2), pairs packed into budget-sized requests, a documented request cap above which the judgment declines |
| A judgment quietly becoming load-bearing | The card's whole premise is that these are advisory; a later edit could make one a precondition | Each skill addition names the judgment as advisory with a stated fail-open side, and U5's guard test asserts that wording is present |
| Question wording drifting from the skill prose it quotes | A judgment asking about outcomes the skill no longer has is worse than no judgment | The consequence-factor and readiness lists are single named lists with guard tests bound to the skill's own contract (KTD4, U3) |
| The saga version colliding with the sibling card | Issue 1036 bumps saga in parallel, and `parent/1018` already carries a `0.160.0` | KTD8: bump from main's number, and the coordinator serializes sibling bumps at merge time |

## Questions answered from the card

`AskUserQuestion` is unavailable in this session, so every question the skill would have asked from a known set was answered from the card, the research document, or the code. None of these is a production, destructive, credential, permission, billing, external-commitment, or process-authority decision.

| Question | Answer taken | Where the answer came from |
|---|---|---|
| Destination (plan-only / pr / merge / nonprod-deploy) | `pr` | The invocation's `plan_pre_answers.v1` carrier, validated and applied at intake by `plugins/saga/scripts/plan_pre_answers.py`, caller "improve-claude-plugins run driver" |
| Execution backend | `inline` | The same carrier; `inline` is the only backend a carrier may apply, and the work is one agent's bounded edit to one plugin |
| Is a plan document warranted? | Yes | Phase 0.4's rubric: three skills, a new script, a new test file, release surfaces, and eight decisions worth recording — not atomic on any axis |
| Scope class | Standard | One bounded plugin change with real technical decisions; six units, inside the 3 to 6 range |
| Resume or mint a saga? | Mint | `saga.py scan` returned zero candidates |
| Where do the question sets live — fleet-core verbs or a saga script? | A saga script | The card names `plugins/saga/scripts/shaping_judgments.py` explicitly; KTD1 records the reasoning |
| Which saga version does this bump to? | `0.159.3` to `0.160.0` | Main's number at base commit `866d3670`; KTD8 records the sibling serialization |
| Does the office-hours Startup/Builder mode choice ship here? | No | The card's Objective names only the routing choice; the mode choice is listed as out of scope |
| Which consequence factors does brainstorm ask about? | The six already pinned by the repository's own brainstorm judgment-contract test | `tests/test_brainstorm_judgment_contract.py::check_consequence_factors`, rather than the shorter list in the research document |
| Do these commands write a saga tick? | No | The card's non-goal, because issue 1030's release makes them stateless |

## Sources

- The card: issue 1037, "Ideate, brainstorm, and office-hours judgments"; its parent, issue 1019.
- `docs/analysis/2026-09-18-typesafe-jev-integration-research.md` — requirements R9, R12, R13, and section 6.
- `docs/analysis/2026-09-19-improve-claude-plugins-objective-plan.md` section 2 — what the simplification kept, moved and dropped.
- `docs/operations/saga-brainstorm-change-candidates.md` in the `infiquetra-agent-operations` repository — the operator's recorded brainstorm rule and the rejected fixed-convergence-loop candidate.
- `plugins/fleet-core/references/typesafe.md` — the data rule, the verdict log, and the ten house rules.
- `plugins/fleet-core/scripts/fleet_commons/typesafe_client.py`, `jev_verbs.py`, `plugins/fleet-core/scripts/jev.py`, and `tests/test_typesafe_client.py` — what issue 1032 shipped and the fake-client pattern this card's tests follow.
- `plugins/saga/skills/ideate/SKILL.md`, its `references/convergence-and-partnership.md`, `plugins/saga/skills/brainstorm/SKILL.md`, its `references/requirements-sections.md`, and `plugins/saga/skills/office-hours/SKILL.md` — the phases the judgments attach to.
- `docs/brainstorms/2026-09-19-qa-testing-strategies-requirements.md` on branch `parent/1018` — a real requirements document, used as the readiness judgment's worked sample.
