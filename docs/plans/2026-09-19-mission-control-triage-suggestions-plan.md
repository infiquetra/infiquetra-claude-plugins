---
title: Mission-control triage suggestions, risk pre-fill, objective and status suggestions, override logging, and auto-labels
type: feat
status: active
date: 2026-09-19
origin: docs/analysis/2026-09-18-typesafe-jev-integration-research.md
backend: inline
---

# Mission-control triage suggestions, risk pre-fill, objective and status suggestions, override logging, and auto-labels

## Summary

This plan adds advisory judgments to two mission-control paths. When an author prepares an issue draft with a new opt-in flag, the draft's machine-readable sidecar gains a suggested issue type with its full probability distribution, a suggested risk tier, and — when candidates are supplied — a suggested Objective and board Status. When an author runs the auto-label command with the same opt-in flag, the command prints the union of the labels the existing regular-expression rules already match and the labels a model judged applicable.

Nothing is applied. Every suggestion is written beside the author's own choice, which always wins; when the two differ the disagreement is recorded in the verdict log as an override. Every call goes through the TypeSafe client that issue 1032 shipped in the fleet-core plugin, and no test in this plan touches the network.

---

## Problem Frame

Two mission-control decisions are made today by a person reading a paragraph or by a regular expression written years ago.

The first is the issue type. An author running `sdlc_manager.py issue prepare` must pass `--type` from the five-value taxonomy in `plugins/mission-control/skills/issues/references/issue-types.md`, with nothing but the decision tree in that document to help. The 2026-09-18 research measured how well a typed judgment agrees with this repository's own labels: 17 of 30 closed issues with generic criteria, and 19 of 30 when the repository's issue-types reference was passed to the model as policy state. Agreement rose to 70 percent on the 23 answers where the model's confidence was at least 0.6. The research's own reading of the misses is that the ceiling is label noise — several of the model's answers are more defensible than the label that was actually applied — which is precisely why this plan shows the whole distribution rather than a single answer, and why nothing is applied automatically.

The second is the content label. `labels_auto_label` at `plugins/mission-control/scripts/sdlc_manager.py:1730-1761` matches title and body text against regular expressions from `labels.json` and posts the matches straight to GitHub. The labels reference calls these rules "legacy fallback rules" at `plugins/mission-control/skills/labels/references/labels-reference.md:156-158`. A pattern such as `security|vulnerability|CVE` cannot recognise a security concern described in different words, and adding more patterns does not fix the class of problem.

Both requirements come from the research: requirement 14, triage suggestions with a type distribution, a risk score, an Objective suggestion and a board Status suggestion with overrides logged; and requirement 15, auto-labels as a yes/no judgment per label with the regular expression kept as a floor. The reconciliation in `docs/analysis/2026-09-19-improve-claude-plugins-objective-plan.md` section 2 carries both forward unchanged.

The foundation already exists. Issue 1032 shipped the client, the verdict log, the override record, the answer cache, the confidence helper and the data rule, merged to this plan's base commit as pull request 1045. This card is a consumer of that foundation and adds no second client.

---

## Requirements

R-IDs are continuous and never renumbered.

### The suggestion path in `issue prepare`

R1. `sdlc_manager.py issue prepare` accepts a new opt-in flag `--suggest`. Without the flag the command makes no model call of any kind and behaves exactly as it does today: the draft markdown is byte-identical, and the sidecar JSON carries no new key. The sidecar's `updated_at` field already differs between two runs of the same command (`sdlc_manager.py:5913`), so it is excluded from that comparison and from the tests that make it.

R2. With `--suggest`, the sidecar JSON gains a top-level `type_suggestion` object carrying the model's chosen issue type, its full probability distribution over all five types in `_ISSUE_TYPES` (`sdlc_manager.py:4444-4450`), its confidence, the confidence floor in force, and the author's chosen type from `--type`. The distribution is the `probabilities` map the choice primitive returns — the shape recorded in `tests/test_typesafe_client.py:47-56` — not something the plan's code derives.

R3. With `--suggest`, the sidecar JSON gains a top-level `risk_suggestion` object carrying a suggested tier, its confidence and the floor. The ordered levels are the repository's own four-tier risk vocabulary read from `_RISK_TIER_VOCABULARY` (`sdlc_manager.py:4027`) — `low`, `medium`, `high`, `very-high` — never a hard-coded three-level list. `UNKNOWN` is not a level: it is the marker for an absent assessment (`sdlc_manager.py:4028`) and is not something to suggest.

R3a. A score answer returns a number, not a level name: the live shape is `{"type": "score", "score": 1.2, "confidence": 0.8}` (`tests/test_typesafe_client.py:56`). The suggestion object therefore carries both the raw score and the level it maps to, where the mapping is the nearest index into the ordered level list. An implementer who expects a tier string from `answer_value` will get a float; this requirement exists so that does not happen.

R4. The risk suggestion never reaches `PreparedIssue.risk` and never changes the compiled body. The issue body remains the only source of a card's risk, which is the standing ruling recorded in the code at `sdlc_manager.py:6023-6028`.

R5. With `--suggest` and one or more Objective candidates supplied on the command line, the sidecar gains an `objective_suggestion` object choosing among the supplied candidates plus an explicit `none` option. With no candidates supplied, the question is not asked and the key records that no candidates were offered. The suggestion never touches the sidecar's existing `project_fields` map, which already records an Objective offline when the handoff source names one (`sdlc_manager.py:4625-4627`); the two sit side by side and the recorded field stays authoritative.

R6. With `--suggest`, the sidecar gains a `status_suggestion` object choosing among the board Status options the vendored schema declares, read offline through `_stage_flow_rules()` (`sdlc_manager.py:376`). The options are the ordered, de-duplicated union of all six stages' lists. They narrow to one stage's list only when a stage is known — and today that never happens from the command line, because `issue prepare` has no `--stage` flag: the `stage` parameter of `issue_prepare` is reachable only from Python, so every command-line prepare passes `None`. The narrowing branch is written against the function parameter, not against a flag that does not exist.

R7. Priority is never suggested. The research measured 3 of 9 agreement and concluded that priority depends on board context the issue text does not carry.

### Acceptance, override and logging

R8. The author's own flags are the decision. `--type`, `--risk`, `--status` and the Objective the card will carry are unchanged by any suggestion; the suggestion is recorded beside them.

R9. When a suggestion differs from the author's corresponding flag, the prepare run appends an override record to the verdict log linking back to the verdict it overrode by hash, through `jev_log.record_override` (`plugins/fleet-core/scripts/fleet_commons/jev_log.py:162-181`). When they agree, only the verdict is recorded.

R10. Every answer taken is appended to the verdict log as a verdict carrying the resolved model version, through `jev_log.record_verdict` (`jev_log.py:122-160`), under a decision identifier namespaced to this consumer so the evaluation harness can score the decisions separately.

R10a. Each verdict carries the author's own value in the record's `label` field. The field is the known-correct value the evaluation harness joins on, and its own docstring says that without it the harness "cannot score accumulated history at all" (`jev_log.py:145-148`). The author's flag is the best available ground truth at prepare time, so passing it is what makes the parent card's acceptance criterion — thirty or more logged verdicts with agreement reported per confidence band — reachable from ordinary use rather than from a separate labelling exercise.

R11. No suggestion this plan adds is ever applied. No model answer changes a draft field, a label set, a board field, or a GitHub object, at any confidence, on any path. The one auto-applying behaviour in scope is the one that already exists — `labels auto-label` without `--suggest` still posts its regular-expression matches to GitHub exactly as it does today — and this plan neither widens nor narrows it.

### The labels union

R12. `sdlc_manager.py labels auto-label` accepts a new opt-in flag `--suggest`. Without it, the command's behaviour is unchanged, including its GitHub write.

R13. With `--suggest`, the command computes and prints the union of the labels the regular-expression rules matched and the labels the model judged applicable at or above the floor, and applies nothing.

R13a. The labels floor is applied to the yes-probability the answer carries, obtained through `typesafe_client.answer_value`, never to `typesafe_client.answer_confidence`. A yes/no answer has no confidence field, so the confidence helper returns the probability's distance from one half doubled (`typesafe_client.py:962-977`): a confident "no" of 0.05 bands at 0.90 and would pass a confidence floor, adding a label the model explicitly rejected. Thresholding the probability is the only correct reading, and a test proves the 0.05 case is excluded.

R14. The union is widen-only: a label the regular-expression rules produced is present in the output for every possible model answer. The model may only add.

R14a. The candidate label set the model is asked about is the fixed set of content labels the labels reference documents — `security`, `performance`, `breaking-change` and `documentation` (`plugins/mission-control/skills/labels/references/labels-reference.md:160-169`) — unioned with any `add_labels` value the configured rules carry. It is not derived from the configured rules alone: `auto_label_rules` is empty in the vendored `sdlc-schema.json`, and `load_config` falls back to an external `labels.json` or a remote fetch that may return nothing, so a rules-only derivation would ask about no labels at all on a machine with no external checkout. The issue-type labels the rules also apply (`capability`, `defect` and their siblings) are excluded from the question set: the issue type is the prepare path's judgment, not the labels path's.

R15. Each label in the printed union names its provenance — rule, model, or both.

### Failure, data and the key

R16. A client failure of any kind — `error`, `timeout` or `malformed` — leaves the draft and the sidecar exactly as they would have been without `--suggest`, except for one `suggestions` block recording the failure status and its note. The command exits with its ordinary status; a failed suggestion is never a blocking readiness gap.

R17. All state sent to the model is built through the client's own `prepare_state`, which redacts and then truncates and is the only path to a transport. No credential, session transcript or customer content is sent, per the data rule in `plugins/fleet-core/references/typesafe.md` section 1.

R18. `TYPESAFE_API_KEY` is read only by the client, from the environment, and is never printed, logged, written to a sidecar or named in an error message raised by this plan's code.

R19. Every question about one draft is batched into a single request, per house rule 5 of the fleet-core reference.

### Tests and release surfaces

R20. Every test drives a fake client through an injected seam. No test in this plan opens a socket, reads `TYPESAFE_API_KEY`, or writes to the real verdict log.

R20a. The new module carries test coverage at or above the repository's 80 percent minimum. Coverage is measured across `plugins/` by the project's own pytest configuration (`pyproject.toml`, `addopts = "-v --cov=plugins --cov-report=term-missing"`), and both test roots are collected (`testpaths = ["tests", "plugins/*/tests"]`), so tests under `plugins/mission-control/tests/` and under `tests/` both count.

R21. The mission-control plugin version is raised from main's 2.16.0 to 2.17.0 across `plugins/mission-control/.claude-plugin/plugin.json`, `.claude-plugin/marketplace.json` and `plugins/mission-control/CHANGELOG.md`, and the skill documentation for labels and issues describes the new flags.

---

## Key Technical Decisions

**KTD1 — the question set lives in mission-control, not in the fleet-core verb registry.** The fleet-core registry already carries a `triage` verb (`plugins/fleet-core/scripts/fleet_commons/jev_verbs.py:85-102`) asking for an issue type and a risk score, with generic criteria and no policy text. This plan does not extend it. Three reasons. The policy state this card needs — the issue-types reference document, the board Status vocabulary from the vendored schema, and the Objective candidates — is mission-control's own data, and moving it into fleet-core would make the shared library reach into a consumer plugin's configuration. The card names only mission-control files and release surfaces. And every sibling card in this run that touches fleet-core competes for the same version number, which the coordinator has to serialise by hand at merge time; not touching fleet-core removes this card from that contention entirely. *Rejected alternative:* extending the fleet-core verb — cleaner on the "one place for the policy" principle, but it buys a cross-plugin dependency and a version collision to save one module. *Mitigation for the split:* a guard test asserts the mission-control question set and the fleet-core `triage` verb enumerate the same five issue types, so the two cannot drift on the option set. *Revisit when:* a third consumer needs the same repository-policy triage question.

**KTD2 — the author's flag is the decision, and disagreement is the override.** `issue prepare` already requires `--type` and already accepts `--risk` and `--status`. Those flags are the author's choice, made before the model answered. This plan therefore needs no new interaction to capture acceptance or override: the suggestion is written beside the flag, and a difference between them is recorded as an override in the verdict log. This is what makes "nothing auto-applies" structural rather than a promise — there is no code path from an answer to a field. *Rejected alternative:* an interactive prompt offering to accept the suggestion. It would make a scripted prepare interactive, which is the exact failure the prepare-then-approve pipeline was built to avoid.

**KTD3 — the suggestions live in the sidecar, never in the compiled issue body.** The draft markdown's body becomes the created issue's body and is validated by the card validator, which the card puts out of scope. The sidecar is the machine-readable companion that `create-prepared` reads and that no validator parses, so a new key there changes nothing downstream. The operator sees the suggestions in the command's own printed output at prepare time and in the sidecar afterwards. *Rejected alternative:* a block in the draft's front matter. `_parse_draft_frontmatter` (`sdlc_manager.py:5059`) is a naive parser and the front matter is re-rendered on every revision; a structured block there is a drift hazard for no gain.

**KTD4 — suggestions are opt-in, and the flag defaults off.** `--suggest` makes the model call. The twenty existing tests in `plugins/mission-control/tests/test_issue_prepare.py` and every ordinary prepare run stay offline and unchanged, and a machine without `TYPESAFE_API_KEY` is never surprised by a failed call it did not ask for. *Rejected alternative:* on by default with an opt-out. The prepare path runs in automation, in worktrees and on other people's machines; a default that reaches a paid third-party endpoint is the wrong default for a command whose whole design is offline.

**KTD5 — the failure direction is "suggest nothing".** A client failure is recorded and ignored. This is fail-open in the safe direction because a suggestion has no authority: losing it costs an author one hint, while blocking a prepare on a vendor outage would stop the whole intake path. The fleet-core reference's house rule 8 requires each gate to say which side it fails open on; this is that statement.

**KTD6 — the injected seam is a callable named `ask`.** `issue_prepare` and the labels path take an optional `ask` parameter defaulting to `None`, resolved at call time to `fleet_commons_shim.load("typesafe_client").ask`. Tests pass a fake callable and assert on the request it received. This mirrors the injection posture the client itself uses for `urlopen`, `getenv`, `clock` and `sleep` (`typesafe_client.py:830-846`) and keeps the shim out of the import graph of a prepare that never suggests. *Rejected alternative:* monkeypatching the shim in tests. It couples every test to the resolution machinery rather than to the contract under test.

**KTD7 — the floor is 0.6, and a low-confidence answer is shown, not hidden.** The number matches the default on `jev_verbs.Verb.confidence_floor` and the measured 70 percent agreement at or above 0.6 versus 3 of 7 below it. In the prepare path it is a *confidence* floor and it changes no behaviour, because nothing is applied; it is recorded in each suggestion and in each verdict so the evaluation harness has the number that was in force. In the labels path the same number is a *probability* floor, applied to the yes-probability rather than to the banding confidence, and there it does decide whether a model-suggested label is printed. The two readings are deliberately distinct — R13a exists because conflating them would admit a label the model rejected.

**KTD8 — the Objective candidates come from the command line, never from a live lookup.** The Objective field's option list lives on the GitHub project board. `issue prepare` is an offline command by design and this plan does not make it reach the network. Candidates are supplied with a repeatable flag; with none supplied the question is simply not asked and the sidecar says so. *Revisit when:* a later card gives prepare a cached, offline copy of the board's option list.

**KTD9 — the labels union is a pure function, tested directly.** `union_labels(rule_labels, model_answers, floor)` takes a collection of rule-derived label names, a mapping from label name to the model's answer for it, and a floor, and returns an ordered list of labels with provenance. It makes no call and reads no configuration, so the widen-only property (R14) is provable by test over the full answer space rather than inferred from a command's output.

---

## Implementation Units

Units are dependency-ordered. U-IDs are never renumbered.

### U1. The suggestion module: question set, policy state and answer shaping

The judgment itself, in one module with no input and output of its own beyond data structures.

**Goal:** a module that builds the batched question set for a draft, shapes the client's answers into the sidecar's suggestion objects, and computes the labels union — with no file, network or GitHub access.

**Requirements:** R2, R3, R3a, R5, R6, R7, R13a, R14, R14a, R15, R17, R19, KTD1, KTD7, KTD9.

**Dependencies:** none.

**Files:** `plugins/mission-control/scripts/triage_suggest.py` (new), `plugins/mission-control/tests/test_triage_suggest.py` (new).

**Approach:** Four public functions and no side effects.

`build_questions(issue_text, *, issue_types, risk_levels, status_options, objective_options)` returns one dictionary carrying every question for one draft, batched per house rule 5. The type question is a `choice` over the five issue types, with the criteria written from this repository's actual practice rather than generic definitions — the research's context-update miss is exactly what a generic criterion produces in a repository where prose is behaviour — and with the issue-types reference document passed as the question's `policy`, which is the change that lifted the probe from 17 to 19 of 30. The risk question is a `score` over the four levels the caller passes in, which come from `_RISK_TIER_VOCABULARY` (R3). The status question is a `choice` over the supplied Status options. The Objective question is a `choice` over the supplied candidates plus `none`, and is omitted entirely when no candidates were supplied.

`build_state(issue_text, policy_text)` returns the named-JSON state the questions reference. It carries the draft's own text and the policy document, nothing else; it does not read the environment, a transcript, or any GitHub object. The client's `prepare_state` does the redaction and truncation, so this function never redacts by hand.

`shape_suggestions(answers, *, chosen_type, chosen_risk, chosen_status, chosen_objective, risk_levels, floor)` turns the client's answer map into the four suggestion objects, using `typesafe_client.answer_value` and `typesafe_client.answer_confidence` rather than reading the answer dictionaries directly — the yes/no asymmetry those helpers hide is recorded in LEARNINGS `{#jev-noul-has-no-confidence-1032}`. Each object carries `suggested`, `distribution` (the choice primitive's own `probabilities` map, where the primitive provides one), `confidence`, `floor`, `chosen` and `overridden`. The risk object additionally carries the raw `score` alongside the level it maps to, per R3a.

`union_labels(rule_labels, model_answers, floor)` returns an ordered list of `{"label", "source"}` entries where `source` is `rule`, `model` or `both`. Every label in `rule_labels` appears in the output unconditionally; a model answer contributes only when its yes-probability — `answer_value`, never `answer_confidence` — is at or above the floor (R13a).

**Patterns to follow:** the question-construction helpers `_noul`, `_choice` and `_score` at `plugins/fleet-core/scripts/fleet_commons/jev_verbs.py:43-57` for the wire shape of each primitive; `plugins/fleet-core/references/typesafe.md` section 3 for the house rules; the test-module bootstrap at `plugins/mission-control/tests/test_issue_prepare.py:1-14` for how a mission-control test imports a script module.

**Test scenarios:**

- Happy path: `build_questions` with all five types, the Status union and two Objective candidates returns one dictionary with four questions, the type question's criteria keys equal to `_ISSUE_TYPES`, and the issue-types policy text present in the type question's instructions.
- Edge case: with no Objective candidates, `build_questions` returns three questions and no Objective key.
- Edge case: with no stage supplied, the Status options are the ordered, de-duplicated union of all six stages' lists from `_stage_flow_rules()`; with a stage supplied, they are that stage's list alone.
- Guard: the risk question's levels equal `_RISK_TIER_VOCABULARY` and therefore include `very-high`, and they do not include `UNKNOWN` — the R3 assertion, made against the constant so a vocabulary change fails the test rather than silently narrowing the question.
- Happy path: `shape_suggestions` over a recorded answer map produces a type suggestion whose distribution sums to 1.0 within floating-point tolerance and whose `overridden` is false when the chosen type equals the suggestion.
- Failure path: `shape_suggestions` with a chosen type differing from the suggestion sets `overridden` true and records both values.
- Edge case: a score of 1.2 over the four risk levels `["low", "medium", "high", "very-high"]` maps to `medium` — index 1 of a zero-based list — and the object carries both the raw score and the mapped level (R3a). A score of exactly 1.5 sits between two levels, and the test pins which way the implementation rounds rather than leaving it to chance.
- Edge case: a yes/no answer's confidence is read through `answer_confidence` and is the probability's distance from one half doubled, not a missing `confidence` field read as `None`.
- Widen-only property: `union_labels` over the full cross-product of a two-label rule set and every combination of model answers above and below the floor always contains both rule labels — the property R14 states, proved over the answer space rather than one example.
- Failure path: a label whose yes-probability is 0.05 is excluded, although `answer_confidence` would band it at 0.90 — the R13a trap, asserted directly so the wrong helper cannot be substituted without the test reddening.
- Edge case: a model answer at exactly the floor is included; one just below is excluded.
- Guard: the module's issue-type criteria keys equal the fleet-core `triage` verb's criteria keys, so the split recorded in KTD1 cannot drift on the option set.

**Verification:** `uv run pytest plugins/mission-control/tests/test_triage_suggest.py -q`.

### U2. Wire the suggestions into `issue prepare`

The consumer: one flag, one batched call, four sidecar keys, and a failure that costs nothing.

**Goal:** `issue prepare --suggest` writes the suggestions into the sidecar and leaves every other byte of its output unchanged.

**Requirements:** R1, R2, R3, R3a, R4, R5, R6, R8, R11, R16, R17, R18, R19, KTD2, KTD3, KTD4, KTD5, KTD6, KTD8.

**Dependencies:** U1.

**Files:** `plugins/mission-control/scripts/sdlc_manager.py`, `plugins/mission-control/tests/test_issue_prepare_suggest.py` (new).

**Approach:** Add `--suggest`, a repeatable `--objective-option`, and nothing else, to the prepare subparser at `sdlc_manager.py:7358-7389`. Thread `suggest: bool = False`, `objective_options: Sequence[str] = ()` and `ask: Callable | None = None` through `issue_prepare` (`:5917`) and its dispatch arm (`:7809-7828`).

The call happens after the `PreparedIssue` is built and after readiness has run, immediately before the sidecar is serialised, so a suggestion can never influence a field, a label, a gap or a readiness verdict. The resolution of the client is lazy: `ask` defaults to `None` and is resolved to the shim-loaded client only when `suggest` is true, so a prepare without the flag never imports the shim.

`_sidecar_payload` (`:5885-5914`) gains one optional argument carrying a `suggestions` block, which is omitted entirely when the flag is off. On success the block carries `status: "ok"`, the resolved model version, and the four suggestion objects, with `type_suggestion` and `risk_suggestion` also mirrored as top-level sidecar keys because the card's acceptance criterion names them at the top level. On failure it carries the client's status and note and nothing else; the note comes from `AskResult.note`, which the client composes and which by construction cannot carry the key.

The suggestions are printed in the command's human-readable output as one short block after the readiness lines, and included in the JSON output under the same key.

**Patterns to follow:** the existing lazy-dependency posture in `issue_prepare` where the Saga readiness owner is loaded only when a maturity was supplied (`:5955-5977`); the shim-loading call shape at `plugins/mission-control/scripts/fleet_commons_shim.py:140-168`; the sidecar-assertion style of `test_issue_prepare.py:74-105`.

**Test scenarios:**

- Happy path: a prepare with `--suggest` and a fake `ask` returning a recorded answer map writes a sidecar whose `type_suggestion` carries a five-way distribution and whose `risk_suggestion` carries a tier, and whose draft markdown is byte-identical to the same prepare without the flag.
- Happy path: the fake `ask` receives exactly one call, and its question map carries every question for the draft — the batching requirement, asserted on the request rather than on the answer.
- Failure path: a fake `ask` returning `status: "error"` leaves the draft unchanged and the sidecar carrying only `suggestions.status == "error"` with the note; readiness is unchanged and no blocking gap is added.
- Failure path: the same for `timeout` and for `malformed`.
- Failure path: a fake `ask` that raises an unexpected exception is caught and recorded the same way; a vendor library's exception never escapes the prepare.
- Edge case: without `--suggest`, the fake `ask` is never called, and the sidecar has no `suggestions`, `type_suggestion` or `risk_suggestion` key at all.
- Edge case: a prepare with `--suggest` whose suggested risk is high while the body says low leaves `sidecar["risk"]` at the body's token — the R4 separation, asserted directly.
- Edge case: with no `--objective-option`, the sidecar's `objective_suggestion` records that no candidates were offered and the fake `ask` received no Objective question.
- Key safety: the sidecar JSON, the draft markdown and the captured standard output are searched for a sentinel key value placed in the environment, and it appears in none of them.

**Verification:** `uv run pytest plugins/mission-control/tests/test_issue_prepare_suggest.py plugins/mission-control/tests/test_issue_prepare.py -q`.

### U3. Verdict and override logging for the prepare path

The evidence trail that makes the decision measurable later.

**Goal:** every suggestion taken is logged as a verdict, and every disagreement with the author's flag as an override, in a directory the test controls.

**Requirements:** R9, R10, R10a, R20, KTD2, KTD7.

**Dependencies:** U2.

**Files:** `plugins/mission-control/scripts/sdlc_manager.py`, `plugins/mission-control/scripts/triage_suggest.py`, `plugins/mission-control/tests/test_issue_prepare_suggest.py`.

**Approach:** After a successful call, append one verdict per answer under a decision identifier namespaced `mission-control/issue-prepare:<question>` — `:type`, `:risk`, `:status`, `:objective` — carrying the answer, the confidence from `answer_confidence`, the floor from KTD7, the resolved model version, and the author's own value as the record's `label` (R10a). Where the author's flag differs from the suggestion, append an override carrying the verdict's own hash, the chosen value and a one-line rationale naming the flag that supplied it.

The log directory is injected. `jev_log.record_verdict` and `record_override` both take an optional `directory`, so the tests point it at a temporary path and the real log at `~/.claude/typesafe/` is never touched. Logging failure is swallowed the same way a client failure is: an unwritable log must not fail a prepare.

**Patterns to follow:** the logging loop in the `jev` tool at `plugins/fleet-core/scripts/jev.py:126-136`, which is the reference shape for a consumer writing verdicts; the record fields documented in `plugins/fleet-core/references/typesafe.md` section 2.

**Test scenarios:**

- Happy path: a prepare with `--suggest` against a temporary log directory appends one verdict line per question, each carrying the resolved model version, a state hash rather than the state, and the author's own value in `label`.
- Happy path: a chosen type differing from the suggestion appends exactly one override line whose `verdict_hash` matches the type verdict's `verdict_hash`.
- Edge case: agreement on every question appends verdicts and no override.
- Failure path: a client failure appends nothing at all.
- Failure path: an unwritable log directory does not fail the prepare; the draft and sidecar are still written.
- Key safety: no logged line contains the sentinel key value or the raw state text.

**Verification:** `uv run pytest plugins/mission-control/tests/test_issue_prepare_suggest.py -q`.

### U4. The labels union in `labels auto-label`

The second consumer: the regular expressions stay, and the model may only widen.

**Goal:** `labels auto-label --suggest` prints a provenance-tagged union and applies nothing.

**Requirements:** R12, R13, R13a, R14, R14a, R15, R16, R20, KTD9.

**Dependencies:** U1.

**Files:** `plugins/mission-control/scripts/sdlc_manager.py`, `plugins/mission-control/tests/test_labels_suggest.py` (new).

**Approach:** Add `--suggest` to the auto-label subparser at `sdlc_manager.py:7491` and an optional `suggest` and `ask` to `labels_auto_label` (`:1730-1761`). The existing regular-expression pass is untouched and runs first; its result is the floor. With `--suggest`, the function asks one batched yes/no question per candidate content label — the set R14a fixes — over the issue's title and body, computes `union_labels` and prints the result with provenance. It returns before the `POST` to the labels endpoint; without the flag it posts exactly as it does today.

The issue's title and body still come from the existing `_rest_get`, so this path does reach GitHub as it always has. The model call is the only new outbound request, and the tests fake both.

**Patterns to follow:** the existing regular-expression loop and its `_rest_post` at `sdlc_manager.py:1748-1761`; the fake-transport discipline in `tests/test_typesafe_client.py:62-95`.

**Test scenarios:**

- Happy path: with `--suggest`, a fake issue payload whose text matches one regular-expression rule and a fake `ask` answering yes to two other labels prints a three-label union, each tagged with its provenance.
- Widen-only: a fake `ask` answering no to every label still prints every rule-derived label, tagged `rule` — R14 at the command level, on top of U1's property test.
- Edge case: with no configured rules at all — the vendored `sdlc-schema.json` state, where `auto_label_rules` is empty — the model is still asked about the four documented content labels, so the command is useful on a machine with no external `infiquetra-sdlc` checkout (R14a).
- Edge case: a label both matched by a rule and confirmed by the model is tagged `both` and appears once.
- Failure path: with `--suggest` and a failing fake `ask`, the rule-derived labels are printed with a note naming the client's status, and nothing is applied.
- Edge case: without `--suggest`, the fake `ask` is never called and the REST post happens exactly as it does today — the unchanged-behaviour assertion for R12.
- Edge case: no rules match and the model answers no to everything — the command says nothing matched and posts nothing.

**Verification:** `uv run pytest plugins/mission-control/tests/test_labels_suggest.py -q`.

### U5. The card's named test file and the acceptance command

One file the card names by path, and a runnable form of the command the card names.

**Goal:** `tests/test_mission_control_suggest.py` exists at the repository root and exercises the card's two acceptance criteria end to end against a fake client.

**Requirements:** R1, R2, R3, R20.

**Dependencies:** U2, U4.

**Files:** `tests/test_mission_control_suggest.py` (new).

**Approach:** The card names `tests/test_mission_control_suggest.py` in both acceptance criteria, at the repository root rather than under the plugin's own test directory. That file is written, and it is the card's acceptance test: it drives `issue prepare --suggest` through a fake client into a temporary draft directory and asserts the sidecar carries `type_suggestion` with a distribution and `risk_suggestion`, and it drives the labels union the same way. The per-unit tests under `plugins/mission-control/tests/` remain the detailed suites; this file is the card's own gate and deliberately duplicates their happy paths rather than replacing them.

The card's first acceptance criterion writes the command without `--team` and `--project`, which the parser has required since the prepared-issue pipeline shipped (`sdlc_manager.py:7368-7369`). Those flags stay required — relaxing them would change every prepared draft's team and board routing, which is far outside this card. The runnable form of the criterion is written out in this plan's Open Questions section and is what this unit's test executes.

**Patterns to follow:** the repository-root test convention in `tests/test_typesafe_client.py:21-35`, which loads a module by path rather than by package import.

**Test scenarios:**

- Happy path: the card's first criterion in its runnable form writes a draft whose sidecar carries `type_suggestion` with a five-way distribution and `risk_suggestion`.
- Happy path: the labels union path returns a widened, provenance-tagged list.
- Failure path: a failing fake client leaves the draft unchanged with a note — the card's third named test expectation.
- Key safety: the sentinel key value appears in no artefact the run produced.

**Verification:** `uv run pytest tests/test_mission_control_suggest.py -q`.

### U6. Documentation, release surfaces and the journal

The installed plugin's metadata telling the same story as the diff.

**Goal:** the skills describe the flags, the version is raised from main's number, and the decisions are in the journal.

**Requirements:** R20a, R21.

**Dependencies:** U1 through U5.

**Files:** `plugins/mission-control/skills/labels/SKILL.md`, `plugins/mission-control/skills/labels/references/labels-reference.md`, `plugins/mission-control/skills/issues/SKILL.md`, `plugins/mission-control/.claude-plugin/plugin.json`, `.claude-plugin/marketplace.json`, `plugins/mission-control/CHANGELOG.md`, `docs/engineering-journal/DECISIONS.md`, `docs/engineering-journal/LEARNINGS.md`.

**Approach:** The labels skill gains a short section on `--suggest`, stating plainly that it applies nothing and that the regular expressions remain the floor. The issues skill gains the same for prepare, including the Objective-candidate flag and the fact that the author's `--type` always wins. The labels reference's auto-label table gains a line saying the model may widen the set but never narrow it.

The version goes from main's 2.16.0 to 2.17.0 in the plugin manifest, the marketplace registry and the changelog. The integration branch `parent/1018` already carries a different 2.17.0 and a 2.18.0 from sibling cards in this run; this plan bumps from main's number because this card opens its own pull request against main, and the coordinator serialises the sibling bumps at merge time. The engineering journal records KTD1, KTD2, KTD4 and KTD5 in `DECISIONS.md`, each with its rejected alternative and a revisit condition.

**Test expectation:** the repository's existing release-surface parity tests cover the version agreement between the manifest, the marketplace registry and the changelog; no new test is added for this unit.

**Verification:** `uv run pytest plugins/mission-control/tests/ -q` and the release-surface parity test the repository already runs in continuous integration.

---

## Verification

The card's own gate, and the one an implementer runs last:

```bash
uv run pytest tests/test_mission_control_suggest.py -q
```

The whole surface this plan touches:

```bash
uv run pytest tests/test_mission_control_suggest.py plugins/mission-control/tests/ -q
uv run ruff check .
uv run ruff format --check .
uv run mypy plugins/ scripts/ tests/ --ignore-missing-imports
```

The full pre-merge gate is `scripts/gate.sh`, backgrounded per the repository's own instructions; a clean run of the commands above is a fast inner loop, not a green gate.

---

## Scope Boundaries

**Out of scope, permanently:**

- Auto-applying any suggestion, anywhere, under any confidence. The card states it twice.
- Any change to the card validator.
- Priority suggestions. The research measured 3 of 9 and concluded the text does not carry the needed context.
- A second HTTP client, a vendor SDK import in mission-control, or any network code in this plugin.
- Changes to `plugins/fleet-core/`, including the `triage` verb — see KTD1.
- Relaxing the `--team` or `--project` requirements on `issue prepare`.

**Deferred to follow-up work:**

- A live or cached Objective option list for `issue prepare`, which would let the Objective suggestion work without candidates being supplied by hand (KTD8).
- Wiring the same suggestions into the interactive `issue create` path and the `triage` command, which the research's requirement 14 also names. This card's acceptance criteria name only `issue prepare` and the labels union.
- Reading the accumulated verdict log back through `jev eval` to decide whether any of these decisions graduates past advisory. That is the parent card's own acceptance criterion and needs roughly thirty real uses first.

---

## Risks & Dependencies

| Risk | Likelihood | Effect | Mitigation |
|---|---|---|---|
| A sibling card in this run raises mission-control's version first, colliding at merge | High | A same-version merge lands silently and the installed metadata disagrees with the diff | Bump from main's 2.16.0 and re-check the number at merge time; the coordinator serialises sibling bumps (U6) |
| The issue-types reference is long enough that the truncation ladder abridges it | Medium | The policy the measurement depended on arrives shortened and agreement drops | The client records which truncation stages fired on every result; U2 records that field in the sidecar so a shortened policy is visible rather than silent |
| A suggestion is read as an answer by an author who skims | Medium | An issue type applied on the model's say-so | The distribution and the confidence are shown, not just the chosen value; the author's flag is the only thing that sets a field |
| The vendor endpoint is slow or down during a prepare | Medium | A prepare that would have taken a second takes the client's full deadline | KTD5: the failure is recorded and ignored; the client's own total deadline bounds the wait |
| The labels union's candidate set drifts from `labels.json` | Low | A newly added rule's label is never asked about | U4 derives the candidate set from the configured rules rather than hard-coding it |

**Dependencies:** the TypeSafe client, verdict log, override record and confidence helper shipped by issue 1032 and merged as pull request 1045 into this plan's base commit 866d3670; `TYPESAFE_API_KEY` in the environment at run time, never in a test.

---

## Questions answered from the card

The interactive question tool was unavailable in this session, so every question the plan skill would have put to the operator was answered from the card, the research documents and the code. Each answer names its source.

| Question | Answer taken | Source |
|---|---|---|
| Routing destination: plan-only, pull request, merge, or nonprod deploy? | Pull request | The structured pre-answer carrier supplied by the run driver, validated at intake by `plan_pre_answers.py` (exit 0, applied `destination: pr`) |
| Execution backend: inline or team execution? | Inline | The same carrier. The recommender was still called and suggested `team-execution` on the size signal; the carrier's `inline` stands and both values are recorded on the saga tick |
| Deploy autonomy: gate or auto? | Not asked | The skill asks it only for a nonprod-deploy destination |
| Gated or advisory consensus? | Not asked | The skill asks it only when a consensus or multi-reviewer signal is present; this card has none |
| Resume an existing plan saga, or mint a new one? | Mint | `saga.py scan` returned zero candidates |
| Is a plan document warranted at all? | Yes | Six units across two commands plus release surfaces, nine load-bearing decisions, and an upstream research document needing traceability — no skip condition holds |
| Scope class: lightweight, standard, or deep? | Standard | Two command paths and one new module, low risk, and a foundation that already exists and is well documented; the card's own risk field says low and its recommended tier band is sonnet/medium |
| Does the judgment extend the fleet-core `triage` verb or live in mission-control? | Mission-control, with a guard test binding the two option sets | The card names only mission-control files; the policy state is mission-control's own; KTD1 records the rejected alternative |
| How is the operator's acceptance or override captured without an interactive prompt? | The author's existing `--type`, `--risk` and `--status` flags are the decision; a difference from the suggestion is the override | KTD2; the flags already exist and prepare is a scripted path |
| Where does the Objective option list come from, given prepare is offline? | A repeatable command-line flag; with no candidates the question is not asked | KTD8; the option list is live board state and prepare makes no network call |
| Where do the board Status candidates come from? | The vendored schema's stage-status lists, read offline through `_stage_flow_rules()` | Verified by running it: six stages, each with its own ordered option list |
| Is the suggestion on by default? | No — `--suggest` is opt-in | KTD4; a default that reaches a paid third-party endpoint is wrong for a command designed to be offline |
| What happens on a client failure? | The draft and sidecar are unchanged but for a note; the prepare succeeds | The card's own test expectation, and KTD5 |
| Is the risk suggestion allowed to seed the card's risk? | No | R4 and the standing ruling in the code at `sdlc_manager.py:6019-6027` that the body is the only source of risk |
| Which mission-control version does this card bump to? | 2.16.0 to 2.17.0, from main's number | Read from `plugins/mission-control/.claude-plugin/plugin.json` on base commit 866d3670; the coordinator serialises the sibling bumps already on the integration branch |
| The card's acceptance command omits the required `--team` and `--project`. Relax them, or record the runnable form? | Record the runnable form; the flags stay required | Relaxing them would change team and board routing for every prepared draft, far outside this card. Raised in Open Questions |
| Is calling a paid third-party endpoint from a new command an external commitment needing sign-off? | No new commitment | The key, the account and the endpoint are already in use by the fleet-core tool merged in pull request 1045; this card adds a caller, not a vendor |

---

## Open Questions

**The card's first acceptance criterion is not runnable as written.** It reads:

```
python3 plugins/mission-control/scripts/sdlc_manager.py issue prepare --repo infiquetra-claude-plugins --type defect --title t --from <file> --suggest
```

`--team` and `--project` have been required on this subparser since the prepared-issue pipeline shipped, so the command as written exits on an argparse error before any suggestion code runs. The plan keeps both flags required and treats the criterion as naming the runnable form below. If the operator intends the flags to become optional, that is a separate card: their values decide the card's team profile and its board, and defaulting them would silently route drafts.

```bash
python3 plugins/mission-control/scripts/sdlc_manager.py issue prepare \
  --repo infiquetra-claude-plugins --type defect --team asgard --project operations \
  --title t --from <file> --suggest
```

**The Objective suggestion is the weakest of the four, and may not earn its place.** With prepare offline, it can only choose among candidates the author already typed out — which means the author has already narrowed the field to a handful before the model sees it. It is planned because requirement 14 names it and because the verdict log will show whether it agrees with what the author picks. If after thirty real uses the agreement is not informative, the honest outcome is to remove it rather than keep an advisory nobody reads.

---

## Sources / Research

- The card: infiquetra/infiquetra-claude-plugins issue 1035, and its parent, issue 1019.
- `docs/analysis/2026-09-18-typesafe-jev-integration-research.md` — section 2 (the issue-type and priority probes), the mission-control rows of section 5 (requirements 14 and 15), and section 8's house rules.
- `docs/analysis/2026-09-19-improve-claude-plugins-objective-plan.md` — section 2, which carries both requirements forward unchanged.
- `plugins/fleet-core/references/typesafe.md` — the data rule, the verdict log record and the ten house rules.
- `plugins/mission-control/skills/issues/references/issue-types.md` — the five-type taxonomy and the decision tree, which becomes the type question's policy state.
- Pull request 1045, merged as commit 866d3670, which is this plan's base and the source of every primitive it consumes.
