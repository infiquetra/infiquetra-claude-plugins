---
title: "Widen-only unions: the parse_issue flags and the journal nudge"
type: feat
status: active
date: 2026-09-19
origin: docs/analysis/2026-09-18-typesafe-jev-integration-research.md
backend: inline
---

# Widen-only unions: the parse_issue flags and the journal nudge

## Summary

Two places in the saga plugin decide something with a hand-written regular expression today, and both decide it too narrowly. This plan adds a model judgment beside each regular expression and takes the union, so the model can only ever add a positive, never remove one.

The two places are the issue-body flags in `plugins/saga/scripts/parse_issue.py` (which feed saga's mandatory test gate) and the engineering-journal nudge in `plugins/saga/hooks/journal_nudge_hook.py` (an advisory line on standard error after a commit).

Every judgment goes through the client that issue 1032 shipped in the fleet-core plugin. This plan writes no HTTP code, no second client, and no new credential handling.

---

## Problem Frame

A regular expression over an issue body is a cheap floor and a poor ceiling. The evidence is this card's own body: issue 1036 is about credentials, production, and destructive operations by name, and `parse_issue.py` reports `has_security: false` for it, because the pattern matches the word `credential` and the body says `credentials`. A flag that feeds a mandatory test gate should not turn on the plural of a word.

The journal nudge has the same shape. It fires only when a commit message starts with `feat` or `fix`, so a `refactor` or `perf` commit that carried a genuinely non-obvious mechanism passes in silence — which is exactly the commit whose learning is worth writing down.

The research document (`docs/analysis/2026-09-18-typesafe-jev-integration-research.md`, requirements R7 and R8) proposed a yes/no model question beside each pattern, with the pattern kept as an unconditional floor. The objective plan (`docs/analysis/2026-09-19-improve-claude-plugins-objective-plan.md`, section 2) carries both forward unchanged; two neighbouring research items that were also in the original list, the orchestrate review-shaped detection and the delegation audit, were dropped with the machinery they targeted and are not in this plan.

---

## Requirements

**R1.** Every judgment in this card is asked through `plugins/fleet-core/scripts/fleet_commons/typesafe_client.py`. No new HTTP code, no second client, no new way of reading the key.

**R2.** The union is widen-only: a flag the regular expression sets stays set whatever the model answers. The model can only turn a `false` into a `true`.

**R3.** The state sent for the journal nudge is the commit's own message and its list of changed file paths. Never a session transcript, never a diff, never customer content. The issue flags send the issue body, which the data rule already permits.

**R4.** `TYPESAFE_API_KEY` is read from the environment by the client alone. This card never prints it, never writes it, and never passes it as an argument.

**R5.** The hook exits 0 in every case — a missing key, a client error, a timeout, a malformed answer, no network at all — and never blocks a commit.

**R6.** Every test uses a fake client through an injected seam and touches no network.

**R7.** The default, no-flag behaviour of `parse_issue.py` stays exactly what it is today: pure regular expressions, no network, no fleet-core import. The model path is opt-in behind `--flags`.

**R8.** Each judgment is logged as a verdict through `jev_log.record_verdict` with the resolved model version and the threshold in force, so the evaluation harness can score it later.

**R9.** Every judgment ships in suggest mode. Nothing in this card takes an action on a model answer by itself, and the seven approval-boundary categories are reported for a human to read, never used to grant or withhold an approval.

---

## Key Technical Decisions

**KTD1 — one shared union primitive in fleet-core, not two copies in saga.**

Both callers need the same four steps: ask a batch of yes/no questions, take the union with a floor, log a verdict per question, and fail open to the floor when anything goes wrong. A new module `plugins/fleet-core/scripts/fleet_commons/jev_widen.py` holds that once. Rejected: writing the union inline in each caller, which would put the fail-open policy in two places and leave the second copy to drift. Revisit when a third caller needs a different failure posture.

**KTD2 — the question sets live in the verb registry, not in the callers.**

`plugins/fleet-core/scripts/fleet_commons/jev_verbs.py` is the declared single home for question text, criteria and confidence floors, and the `jev` command builds a subcommand from every entry automatically. Two verbs are added there: `issue-flags` and `journal-nudge`. The cost is that this card bumps the fleet-core plugin as well as saga. Rejected: keeping the question text inside `parse_issue.py` and the hook, which would make `jev issue-flags` impossible and split the policy.

**KTD3 — the five existing flags keep their names and their meaning; the seven approval-boundary categories are new, advisory, and separate.**

The card names the approval boundaries from the sdlc process document (production changes, destructive operations, secrets or credential changes, identity and permission changes, billing or cost-impacting actions, external commitments, and major team or process authority changes). Those are not the five flags `parse_issue.py` has today. Both are delivered: the five existing flags (`has_security`, `has_api`, `has_infra`, `has_privacy`, `has_refactor`) gain a model judgment each and keep their exact key names, because saga's test gate and four skill documents read them by name; the seven categories arrive under a new `approval_boundaries` key, advisory only, with no pattern floor and no gate reading them. Rejected: replacing the five with the seven, which would narrow a mandatory gate — the one thing this card forbids.

**KTD4 — thresholds are provisional and written down in one place.**

A yes/no answer from this model carries a probability and no confidence field (`docs/engineering-journal/LEARNINGS.md` anchor `{#jev-noul-has-no-confidence-1032}`), so the union compares the probability against a threshold. The issue flags use 0.70 and the journal nudge uses 0.60: a false flag costs an extra test lens, a false nudge costs one line on standard error, so the nudge can afford to be readier. Both numbers are declared as the verbs' `confidence_floor` and recorded in every verdict. They are placeholders until the harness has about thirty real uses per decision, and the plan says so rather than implying they were measured.

**KTD5 — the hook fails silent and fast, with one documented switch.**

The nudge asks the model at most once, with a two-second request timeout and a three-second overall deadline, and only when the pattern did not already nudge. Any outcome other than a clean answer produces no output at all. `INFIQUETRA_TYPESAFE_JOURNAL_NUDGE=off` skips the call entirely, keeping today's behaviour exactly. The side that fails open is the quiet side: a broken or absent model never invents a nudge and never delays a commit beyond three seconds.

**KTD6 — `parse_issue.py` fails open to the regular expressions and still exits 0.**

Four saga skills call this script and read its JSON. A model failure therefore prints the regex result, a `note` naming what failed, and exits 0. The one loud failure is `--issue <N>` when the GitHub command cannot fetch a body: there is no output to print at all, so that exits 1.

---

## High-Level Technical Design

The union primitive is the whole design; everything else is two callers and their command-line surfaces.

`jev_widen.widen()` takes a state, a verb name, a mapping of question keys to their floor values, a threshold and an injected `ask` callable. It asks every question in one request, and for each key returns the floor, the probability, the union, and which side produced the union. When the request is not `ok` it returns the floors unchanged with a `note`, and it logs nothing.

That single injected `ask` seam is what makes requirement R6 mechanical rather than a promise: a test hands `widen()` a function returning a recorded answer map, so no test can reach the network even by accident.

---

## Implementation Units

### U1. The widen-only union primitive in fleet-core

Adds `plugins/fleet-core/scripts/fleet_commons/jev_widen.py` with one public function and one result shape.

**Behaviour:** `widen(state, verb, floors, *, decision_prefix, threshold, ask=None, log=True, timeout=None, max_attempts=None, total_deadline=None)` returns a mapping from question key to `{"regex": bool, "probability": float | None, "union": bool, "source": "regex" | "model" | "none"}` plus a top-level `note` and `resolved_model`. The union is `floor or (probability is not None and probability >= threshold)`. `ask` defaults to `typesafe_client.ask`, and the three transport parameters are passed straight through to it.

**Module loading:** the verdict-log module is loaded exactly the way `typesafe_client._load_log_module()` (`plugins/fleet-core/scripts/fleet_commons/typesafe_client.py:796`) loads it — through `fleet_commons_shim` first, with a direct path load as the fallback — so the primitive works both as an in-repository import and through an installed plugin.

**Failure posture:** any result whose status is not `ok`, any missing answer key, and any non-numeric probability leaves that key's union equal to its floor, records no verdict, and sets `note`.

**Logging:** one `jev_log.record_verdict` call per question, `decision_id` = `<decision_prefix>:<key>`, with the threshold and the resolved model version. Logging failures are swallowed — a full disk must not break a caller.

**Test scenarios** (`tests/test_jev_widen.py`): a floor of `true` with a model probability of 0.01 stays `true` and reports `source: regex`; a floor of `false` with a probability above the threshold becomes `true` and reports `source: model`; a probability exactly at the threshold is included; a client error returns the floors with a `note` and writes no verdict; a missing answer key falls back to its floor; verdicts are written to a temporary directory with the resolved model and threshold present; the fake `ask` is the only call path, asserted by passing a callable that records its arguments.

### U2. Two verbs in the registry

Adds `issue-flags` and `journal-nudge` to `VERBS` in `plugins/fleet-core/scripts/fleet_commons/jev_verbs.py`.

**`issue-flags`** carries twelve yes/no questions over `{"issue": "..."}`: the five existing categories phrased from this repository's actual practice, and the seven approval boundaries phrased from the sdlc process document, with the boundary list passed as policy text. Its `confidence_floor` is 0.70.

**`journal-nudge`** carries one yes/no question over `{"message": "...", "files": [...]}` — whether the commit describes a non-obvious mechanism or a pattern decision worth a journal entry — with this repository's own journal rule as policy text. Its `confidence_floor` is 0.60.

**Test scenarios** (`tests/test_jev_cli.py`): the existing parametrized tests over `verb_names()` cover both new verbs automatically; add explicit assertions that `issue-flags` declares exactly the five flag keys plus the seven boundary keys and that every question is of type `noul`, and that `journal-nudge` declares one question.

### U3. The `--flags` union in `parse_issue.py`

Adds two command-line options and one new function to `plugins/saga/scripts/parse_issue.py`, leaving `extract()` untouched.

**New surface:** `--flags` opts into the model call; `--issue <N>` fetches the body with `gh issue view <N> --json body -q .body`, which infers the repository from the working directory, with an optional `--repo <owner/repo>` to override it; `--body-file` keeps working exactly as it does. With `--flags`, the printed JSON keeps `flags` with the same five keys now holding the union, and adds `flags_detail` (regex, probability, union, source per category) and `approval_boundaries` (the same shape for the seven).

**Imports stay lazy.** `fleet_commons_shim` is imported inside the `--flags` path only, after `sys.path` is pointed at this script's own directory, in the shape `plugins/fleet-core/scripts/jev.py` already uses. Without `--flags` the script has no fleet-core dependency and makes no network call, which is what keeps the four skill call sites deterministic.

**Test scenarios** (`tests/test_parse_issue_flags.py`): the default invocation produces byte-identical JSON to today's for the same body; `--flags` with a fake client widens `has_security` from `false` to `true` on this card's own body (the plural-of-credential case) and never flips a `true` to `false`; a client error prints the regex result with a `note` and exits 0; the seven boundary keys are present, all model-sourced, with `regex: false`; `--issue` and `--body-file` together is a usage error; no test reaches the network, asserted through the injected client seam.

### U4. The widened journal nudge

Adds the model union to `plugins/saga/hooks/journal_nudge_hook.py` without changing any existing silence or nudge condition.

**Where it fires:** only after every existing precondition holds (the tool was Bash, the command was a commit, the journal directory exists, the committed file list is readable, and the commit contains no journal entry) and the `feat`/`fix` pattern did *not* already nudge. When the pattern nudged, the hook prints and returns without asking anything.

**What it sends:** the commit message and the list of changed paths, nothing else.

**Where the message comes from.** The existing `_extract_commit_message` reads the message out of the shell command string and only handles `-m` (`plugins/saga/hooks/journal_nudge_hook.py:71-88`), so a commit written with a here-document or `-F` yields an empty string. The widen path therefore reads the real message with `git show -s --format=%B HEAD` — the same mechanism `_git_show_files` already uses on HEAD at `plugins/saga/hooks/journal_nudge_hook.py:100-120` — and falls back to the parsed string, staying silent when neither yields a message. The `feat`/`fix` floor keeps reading the parsed string exactly as it does today, so nothing narrows.

**What it prints:** the same advisory line, with a short clause naming that the judgment came from the model rather than the commit type, so a reader can tell the two apart.

**Test scenarios** (`tests/test_journal_nudge_hook.py`): every existing test still passes unchanged; a `refactor` commit touching code with no journal entry and a fake client answering above the threshold produces a nudge and exits 0; the same commit with an answer below the threshold is silent and exits 0; a client error, a timeout and an absent key are each silent and exit 0; `INFIQUETRA_TYPESAFE_JOURNAL_NUDGE=off` makes no call at all, asserted by a fake that raises if invoked; a `feat` commit that already nudges makes no model call; the hook still writes no file.

### U5. Documentation, release surfaces, and the journal

Ships the prose and the metadata in the same commit as the code.

**Documents:** a section in `plugins/fleet-core/references/typesafe.md` describing the union primitive, the two verbs, the provisional thresholds, and which side each caller fails open on; a one-line note naming `--flags` as the opt-in path at the four saga call sites that read these flags — `plugins/saga/skills/plan/SKILL.md:75`, `plugins/saga/skills/work/SKILL.md:154`, `plugins/saga/skills/loop/SKILL.md:110` and `plugins/saga/skills/work/references/test-and-gates.md:73`.

**Release surfaces:** `plugins/saga/.claude-plugin/plugin.json`, `plugins/fleet-core/.claude-plugin/plugin.json`, both entries in `.claude-plugin/marketplace.json`, and both `CHANGELOG.md` files. Saga is 0.159.3 on this plan's base commit and fleet-core is 0.26.0; this card bumps the minor of each, and the run coordinator serialises the sibling version bumps at merge time (issue 1037 bumps saga in parallel from the same base).

**Journal:** the decisions above land in `docs/engineering-journal/DECISIONS.md` in the implementation commit, per this repository's rule that a journal entry ships with the change it explains. They are named here so the reviewer can check the two against each other.

**Test scenarios:** the repository's existing metadata drift guards cover the version surfaces; no new test is added for this unit.

---

## Scope Boundaries

**Not in scope.** No regular expression is narrowed, removed or loosened. No gate reads the seven approval-boundary categories. The hook never blocks and never writes a file. No other judgment point from the research document is wired here — the staffing tier suggestion, the conditional-lens proposal, the triage suggestions and the rest belong to their own cards under parent issue 1019.

**Dropped upstream, recorded so nobody re-adds them.** The orchestrate review-shaped detection (research item R16) and the delegation audit (R19) were in the original regex-to-union group and were dropped with the machinery they targeted.

**Deferred to follow-up work.** The thresholds in KTD4 stay provisional until the evaluation harness has roughly thirty real verdicts per decision; the follow-up is a harness run and a journal entry recording whether each decision stays advisory, is promoted, or is removed. Parent issue 1019 owns that measurement.

---

## Risk Analysis and Mitigation

| Risk | Likelihood | Mitigation |
|---|---|---|
| The hook adds latency to every commit | medium | One attempt, a two-second request timeout, a three-second deadline, no call when the pattern already nudged, and a documented off switch |
| The model widens the flags so often that the test gate fires on everything | medium | The threshold is 0.70, every verdict is logged with its threshold, and the harness re-tunes it from real use rather than from a guess |
| The seven advisory categories get mistaken for an approval | low | They are reported under their own key, no code reads them, and R9 plus the reference document say plainly that they grant nothing |
| The fleet-core bump collides with a sibling card | medium | The coordinator serialises version bumps at merge time; this card touches one new file and one registry mapping in fleet-core, which are additive |
| A test reaches the network by accident | low | The injected `ask` seam is the only call path in both callers, and one test per caller asserts the fake was the callee |
| Editing the four saga skill documents trips saga's own prose drift guards | medium | Keep each edit to one line, and run `uv run pytest tests/test_saga_plugin.py -q` before the pull request rather than at review time |

---

## Verification

```bash
uv run pytest tests/test_jev_widen.py tests/test_parse_issue_flags.py tests/test_journal_nudge_hook.py tests/test_jev_cli.py -q
uv run pytest tests/test_saga_plugin.py tests/test_handoff_envelope_maturity.py -q
uv run python plugins/saga/scripts/parse_issue.py --issue 1036 --flags
uv run ruff check .
uv run ruff format --check .
uv run mypy plugins/ scripts/ tests/ --ignore-missing-imports
```

The third command is the only one that reaches the vendor, and it needs `TYPESAFE_API_KEY` in the environment. Without the key it prints the regular-expression result with a `note` and still exits 0, which is itself the fail-open behaviour requirement R5 and decision KTD6 describe.

---

## Questions answered from the card

The operator question tool was unavailable in this session. Each question the plan skill would have asked is answered below from the card, the research document, or the code, with the source named.

| Question | Answer | Source |
|---|---|---|
| Destination for the saga tick | `pr` | The invocation's `plan_pre_answers.v1` carrier, from the run driver; validated and applied at intake |
| Execution backend | `inline` | The same carrier; the work is two small callers and one primitive, with no gated consensus signal |
| Scope class | Standard, five units | Phase 0.5 judgment: two surfaces, one new module, cross-plugin release surfaces, several load-bearing decisions |
| Is a plan document warranted | Yes | The work spans two plugins and hides at least six decisions (threshold, question home, failure posture, category set, latency budget, opt-in surface) |
| Which flag categories gain a judgment | The five existing flags keep their names and gain one each; the seven approval boundaries arrive as a new advisory key | The card names the boundaries and the sdlc document; the code shows the five; KTD3 reconciles them |
| Where the question text lives | The fleet-core verb registry | The registry's own docstring declares it the single home for question policy |
| What the journal nudge may send | The commit message and the changed file list | The card's own constraint, and the data rule in the fleet-core reference |
| Which side each caller fails open on | Quiet: the hook stays silent, `parse_issue.py` returns the regex result | House rule 8 in the fleet-core reference requires the direction to be stated per gate |
| Threshold per decision | 0.70 for the issue flags, 0.60 for the nudge, both provisional | KTD4; no harness measurement exists yet, so the plan labels them rather than implying evidence |
| Test file for the nudge | The existing `tests/test_journal_nudge_hook.py`, not the `tests/test_journal_nudge.py` the card's verification line names | A guard's file name should match the file it guards; the pull request will note the corrected command |
| Resume or mint a saga | Mint; `saga.py scan` returned no candidate | The scan's own output |

No question in the production, destructive, credential, permission, billing, external-commitment or process-authority categories arose. Nothing in this plan deploys, deletes, changes a credential or a permission, spends, commits to anyone outside the repository, or changes decision authority.

---

## Acceptance Criteria Mapping

| Card criterion | Where it is met |
|---|---|
| `parse_issue.py --issue <N> --flags` prints each category with its regex result, the model's probability, and the union | U3, through the `flags_detail` and `approval_boundaries` keys |
| `uv run pytest tests/test_parse_issue_flags.py tests/test_journal_nudge.py -q` passes | U3 and U4; the second path is `tests/test_journal_nudge_hook.py`, per the question table above |
| A flag set by the regular expression stays set whatever the model says | U1's union rule, tested in all three of `tests/test_jev_widen.py`, `tests/test_parse_issue_flags.py` and `tests/test_journal_nudge_hook.py` |
| A flag the model raises is added and logged | U1's verdict logging, tested in `tests/test_jev_widen.py` |
| The hook exits 0 in every case | U4's test scenarios, one per failure mode |
