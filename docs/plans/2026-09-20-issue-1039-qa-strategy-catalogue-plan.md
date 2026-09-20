---
title: /qa as a prescribed strategy catalogue with declared evidence and a computed verdict
type: capability
status: active
date: 2026-09-20
origin: docs/specs/2026-09-19-qa-testing-strategies-spec.md
backend: inline
---

# /qa as a prescribed strategy catalogue with declared evidence and a computed verdict

## Summary

Replace the `/qa` skill's nine-way risk router and its language-model-scored health number with a
catalogue of ten prescribed testing strategies held as data. Code reads a per-repository profile,
computes the required strategy set from file patterns, lets one advisory typed judgment widen that
set and never narrow it, runs each selected strategy's driver to exactly one of `passed`, `failed`
or `blocked`, appends one evidence envelope per strategy to the run record, and computes the
verdict by counting statuses: `pass`, `pass-with-proof-debt`, or `fail`.

One new script, `plugins/saga/scripts/qa_strategies.py`, does the reading, the selecting, the
preflighting, the dispatching, the recording and the counting. Three new data files carry the
catalogue and the two shapes it validates against. The health score and its test are deleted, the
evidence-ledger call leaves the skill, and the skill and its command are rewritten as the
lifecycle's functional-test step rather than an advisory pre-ship gate.

The same script serves the build loop's scenario smoke at the narrower `branch-preview` proof
boundary, through a command-line flag rather than a second runner, so issue 1027's loop is not
edited at all.

## Problem Frame

**The step is about to become authoritative, and it is currently advisory.** `/qa` describes
itself as an advisory router node that "never blocks the router" and "normally runs post-merge"
(`plugins/saga/skills/qa/SKILL.md:25-26`). Issue 1028 put a functional test after the
non-production deployment and made its failure re-enter the build loop. An advisory gate cannot
hold that position.

**It calls a module that the parallel sibling removes — and the specification's reading of where
is already stale.** The specification cites `plugins/saga/skills/qa/SKILL.md:172-181` and
`310-313` as the evidence-custody-ledger calls, verified at commit `2044c363`. At **this card's
base commit `61da4b1c`** those two passages already read the run record instead: the only
surviving references to `evidence_ledger.py` under `plugins/saga/skills/qa/` are
`references/qa-report.md:11`, `:179` and `:193`, confirmed by
`grep -rn "evidence_ledger" plugins/saga/skills/qa/`. The module itself still exists
(`plugins/saga/scripts/evidence_ledger.py`, 27 kilobytes) and issue 1030 deletes it in the same
release, so the three lines in the report reference are a real break and the skill body is not.
The plan uses the file at the base commit, never the specification's earlier reading.

**A check that cannot run reads today as a check that passed.** The skill prescribes a "graceful
no-op" for repositories with no browser surface (`SKILL.md:48-50`). There is no status for "could
not run", so the absence of proof and the presence of proof look the same in the report. The
operator's answer to the requirements document's question six, on 2026-09-19, is that a required
strategy which cannot run stops the run for him, because its causes — environment, credential,
permission — are his approval boundaries and a build loop cannot repair any of them.

**The number at the end has no inputs left.** `plugins/saga/scripts/qa_health_score.py` (123
lines) applies per-finding deductions to counts of language-model-assigned severities. The new
model assigns no severity, so there is nothing to count. The operator's answer to question seven
is that it is removed entirely rather than kept as a non-gating signal.

**The design is not invented here; it is running.** The CAMPPS platform's end-to-end scenario
registry already defines seven driver families with their required evidence, a scenario schema
with eighteen required fields, an evidence-envelope schema, and thirty scenario files; the
`campps-e2e-canary` service implements the matching drivers, a three-status result model with
secret redaction at the driver boundary, and filter-based selection with a cost preflight that can
refuse a run. This card generalises that shape to the repository families CAMPPS does not cover
and calls that executor where it already owns a family.

**The pieces this card needs all exist at its base commit `61da4b1c`, and they were read rather
than assumed.** The run record (`plugins/saga/scripts/run_record.py`, `run_record.v1`) preserves an
unknown top-level key across a read and a write and reports it by name, which is the extension
point the evidence block uses. The release step
(`plugins/saga/scripts/release_step.py:316-389`) already fixes the three scenario states
`passed`, `failed`, `blocked` and refuses a blocked scenario with no cause named. The widen-only
union (`plugins/fleet-core/scripts/fleet_commons/jev_widen.py:152`) already implements a pattern
floor a model may raise and never lower, logs every probability, and degrades to the floor on any
client failure. The build loop (`plugins/saga/scripts/build_loop.py:244-262` and `520-545`) already
runs a list of `{name, command}` scenario-smoke entries through an injected runner, so the shared
component this card owes issue 1027 is a command those entries can name, not an edit to its file.

## Requirements

The specification carries sixteen acceptance criteria and the card carries twelve. Where they
disagree the card wins, and the plan says so — but on a line-by-line reading they do **not**
disagree: the specification's sixteen are a superset. Four of the sixteen have no counterpart on
the card (the CAMPPS delegation, the all-optional profile, the end-to-end run, and the
`health score` string sweep), and every one of the card's twelve appears among the sixteen. The
plan therefore carries all sixteen, and R17 records the one place the card is stricter in wording.

**R1. The catalogue is data, and it lists exactly ten strategies.** Each row carries a strategy
identifier, its situation description, its tool invocation shape, its file-pattern list, its
required evidence fields, its proof boundary (`hermetic`, `branch-preview` or `non-production`),
its mechanical threshold rule, whether a repository may mark it optional, and its cost and
duration estimate. A new strategy is a row plus a driver, never a rewrite of the skill.
(Specification criterion 1; card criterion 1.)

**R2. Selection is computed from the profile, before any judgment is called.** A change whose file
list matches two of the profile's patterns selects those two strategies with no judgment call
made, and the printed selection names the matching pattern for each entry.
(Specification criterion 2.)

**R3. The judgment widens and never narrows, in both directions.** Above the declared act band for
a catalogue strategy the profile's patterns did **not** select, that strategy joins the selection;
below the band for a strategy the patterns **did** select, that strategy is still selected. The band a test reads is the declared value in the catalogue file, never a
literal in the test. (Specification criterion 3; card criterion 2.)

**R4. The judgment's absence is not a failure.** With the client absent, raising, timing out or
returning a non-ok status, selection returns the declared set and the run continues.
(Specification criterion 4; card criterion 3.)

**R5. A missing required environment is `blocked`, never `passed`.** The reason names the variable.
(Specification criterion 5; card criterion 4.)

**R6. The verdict is arithmetic over the envelopes.** `pass` when every required strategy returned
`passed`; `pass-with-proof-debt` when every required strategy returned `passed` and at least one
optional strategy returned `blocked`; `fail` for every other combination. Asserted over the full
status matrix. (Specification criterion 6; card criterion 5.)

**R7. A required `blocked` stops for the operator.** It does not re-enter the build loop.
(Specification criterion 7; card criterion 6.)

**R8. Every envelope validates, and carries no secret.** A driver whose output contains a bearer
token writes an envelope containing no token; redaction happens inside the driver, before the
envelope exists, not at report time. (Specification criterion 8; card criterion 7.)

**R9. An out-of-boundary strategy is recorded as out-of-boundary, not as proof debt.** The three
proof boundaries are a ladder, widest last: `hermetic` ⊂ `branch-preview` ⊂ `non-production`. A run
at boundary B selects every strategy whose declared boundary is B **or narrower**, and records
every strategy whose boundary is wider than B as `out-of-boundary` with that reason. At
`branch-preview` that omits every `non-production` strategy, which is the case the specification
states; the ladder is written down here because the general rule is what the code implements and
what R15's run at `non-production` depends on — without it, a `non-production` run would select
only the widest rung and prove nothing about this repository.
(Specification criterion 9; card criterion 8.)

**R10. An over-ceiling selection refuses wholly.** Zero drivers run; the affordable subset is never
run and never reported as a partial pass. (Specification criterion 10; card criterion 9.)

**R11. The health score is gone, in file and in string.** Neither `plugins/saga/scripts/qa_health_score.py`
nor `tests/test_qa_health_score.py` exists, and no file under `plugins/saga/skills/qa/` or
`plugins/saga/scripts/` contains the string `health score`. The changelog entry that records the
removal names it and is outside the sweep. (Specification criterion 11; card criterion 10.)

**R12. No file under `plugins/saga/skills/qa/` references `evidence_ledger`.**
(Specification criterion 12; card criterion 11.)

**R13. A CAMPPS profile delegates `api-workflow` rather than issuing its own requests.** The driver
invokes the `campps-e2e-canary` entrypoint the profile declares and ingests its envelope, asserted
with a recorded invocation. (Specification criterion 13.)

**R14. A profile that proves nothing is refused.** A profile whose strategies are all optional, and
a repository with no profile at all, each produce a `blocked` run naming the expected profile path,
never a `pass`. (Specification criterion 14.)

**R15. One end-to-end run against this repository's own profile passes.** At the `non-production`
boundary, with at least two strategies reporting `passed`, **one comment published to the issue**
with `gh issue comment` — an issue comment, not a project-board field, so it is outside the rule
that mission-control is the only writer of `Stage` and `Status` — carrying the per-strategy statuses, and the verdict written to the run record. A specification
satisfied only by `blocked` runs has proved nothing. The published comment is part of the
criterion, not a softer "report": the specification's Functional Tester procedure has the step
publish one comment carrying the selection, the per-strategy statuses and the artifact pointers,
and the operator's complaint that started this card is that he cannot tell from a `/qa` report
which checks ran. (Specification criterion 15.)

**R16. The tests and the repository gate pass.** `uv run pytest tests/test_qa_strategies.py` passes
and `scripts/gate.sh` exits zero. (Specification criterion 16; card criterion 12.)

**R17. The card's wording is stricter in one place, and the plan takes the card's.** The card's
tenth criterion is the two `test ! -f` checks alone; the specification's eleventh adds the
`health score` string sweep across two directories. Taking the card as the winner would take the
weaker check, which is not what "the card wins" is for, so the plan carries **both**: the card's
file checks and the specification's string sweep. No other difference between the two lists
changes what gets built.

## Key Technical Decisions

**KTD1 — the repository's qa profile is an optional `qa` block inside the existing
`.saga-profile.json`, not a new file.** The repository already has one tracked profile at its root
(`plugins/saga/references/repository-profile.md`), and that document already sets the precedent for
extending it: issue 1027's `branch_preview_command` is an optional key that did not change the
`repository_profile.v1` token, on the stated grounds that an optional key leaves every existing
profile valid. A second profile file would give a repository two places to declare facts about
itself and two chances to drift. `plugins/saga/references/qa-profile.schema.json` therefore
describes the shape of the `qa` block rather than of a whole file, and the "expected profile path"
that a blocked run names is `.saga-profile.json` with the missing key named. Rejected: a separate
`.saga-qa-profile.json`, which reads tidier and splits one repository's self-description in two.

**KTD2 — one runner, two boundaries, and no edit to the build loop.** The build loop reads its
scenario smoke as a list of `{name, command}` entries and runs each through an injected runner
(`plugins/saga/scripts/build_loop.py:244-262`). The shared component issue 1027 is owed is
therefore a *command* those entries can name —
`uv run python plugins/saga/scripts/qa_strategies.py run --issue <N> --boundary branch-preview` —
not a function it imports and not a change to its file. The boundary is a flag, the catalogue is
the same catalogue, and the two cards touch no common file. Rejected: importing `qa_strategies`
from `build_loop`, which would couple two cards' merge turns for no behaviour either one needs.

**KTD3 — the widening judgment reuses `jev_widen.widen()`, which costs one new verb in
fleet-core.** The widen-only union already exists, already logs every probability with its
threshold, and already degrades to the floor when the client raises, times out or returns a
non-ok status (`plugins/fleet-core/scripts/fleet_commons/jev_widen.py:152-236`). Reimplementing
that union inside `qa_strategies.py` would put the "may only widen" guarantee in two places, which
is precisely the drift the specification's failure table names as the way a required proof silently
disappears. `widen()` resolves its question set from the verb registry, so a `qa-strategies` verb
is added to `plugins/fleet-core/scripts/fleet_commons/jev_verbs.py` carrying ten yes/no questions
keyed by the ten strategy identifiers. The strategy *descriptions* stay in the catalogue and are
passed as state, so the verb duplicates only the key set — and a guard test asserts the verb's key
set equals the catalogue's strategy identifiers in both directions, so a row added to one and not
the other fails. Cost: fleet-core's release surfaces move in the same pull request. Rejected:
calling `typesafe_client.ask` directly from `qa_strategies.py` with an inline question set, which
avoids the fleet-core bump and duplicates the union.

**KTD4 — `/qa` computes its own verdict and routing, and never lets the release step call a
blocked run a pass.** `release_step.record_functional_test` (`plugins/saga/scripts/release_step.py:316`)
validates that every scenario ends in one of the three states and that a blocked scenario names a
cause — and then computes its status from the `failed` list alone, so a scenario list containing
only `blocked` entries returns `{"status": "passed"}`. That is the silent-skip failure this card
exists to remove, arriving through the back door. `qa_strategies.py` therefore computes the verdict
and the route itself, and calls `record_functional_test` only for a `pass` or a `fail`; a required
`blocked` is written to the run record as an operator stop and never presented as a functional-test
result. The release step's own arithmetic is issue 1028's file and is not edited here; the hazard
is recorded in the engineering journal as a follow-up so the next caller does not meet it fresh.
Rejected: editing `release_step.py`, which widens this card into a sibling's merged work for a
case only this card can produce.

**KTD5 — envelopes are validated at runtime by a hand-written checker driven by the schema file,
and by `jsonschema` in the tests.** `jsonschema` is a development dependency
(`pyproject.toml:37`), not a runtime one, so a runtime import would make the functional-test step
fail on a machine that installed the package without its dev extra. The schema file
(`plugins/saga/references/qa-envelope.schema.json`) is the single source: the runtime checker reads
its `required` list and its declared types from the file, and a test validates the same envelopes
with the real `jsonschema` library, so the hand-written checker cannot quietly diverge from the
schema it claims to enforce. Rejected: adding `jsonschema` to the runtime dependencies, which
changes every consumer's install for one check.

**KTD6 — redaction reuses the TypeSafe client's pattern set as its floor and adds the CAMPPS
patterns.** `typesafe_client.redact_text` (`plugins/fleet-core/scripts/fleet_commons/typesafe_client.py:259`)
already carries secret-word patterns, hash runs and an entropy rule, and is already loaded through
the fleet-core shim by other saga scripts. `qa_strategies.py` calls it at the driver boundary and
adds the bearer-token and authorization-header patterns the CAMPPS driver model names. Rejected:
a fresh pattern set, which starts weaker than one that is already in production use.

**KTD7 — five drivers ship and five strategies are declared without one, each blocked with a named
reason and a revisit condition.** Shipping: `cli-smoke`, `contract-check`, `deploy-boundary`,
`installed-surface`, and `api-workflow` as a delegation to the `campps-e2e-canary` entrypoint the
profile declares. Declared without a driver: `data-check`, `infrastructure-read-back` and
`manual-runbook` (the specification's scope boundary puts all three outside this card), plus
`app-ui` and `hosted-surface`. **The last two are a narrowing beyond the specification's stated
boundary and are declared here rather than hidden:** the specification excludes only `app-ui` at a
simulator or emulator target, and excludes `hosted-surface` nowhere. Neither can be proved from
this repository — there is no Flutter surface, no hosted page and no browser target here — and an
unexercised driver shipped on the strength of its author's reading is worse than a strategy that
says out loud it cannot run. Revisit condition for both: the first repository to take a `qa`
profile that declares them, which is where a real target to prove them against first exists.

**KTD8 — the evidence lives under a new top-level `qa` key in the run record.** The record
preserves an unknown top-level key unchanged across a read and a write and reports it by name
(`plugins/saga/references/run-record.md:65-82`), which is the documented extension point and the
one the orchestrate plugin already uses for its own run-level state. A unit row is the wrong home:
a functional test is a property of the run after the merge, not of one unit's working state. The
key carries the selection with a reason per entry, the envelopes, the preflight result, the verdict
and the route.

**KTD9 — the act band for the widening judgment is a declared number in the catalogue file, and
this card does not set an operating band from a cookbook.** It ships in suggest mode at the
provisional band the catalogue declares, every call logged with its probability and any override,
and the evaluation harness of issue 1032 sets the operating band from recorded real uses. Only the
first judgment ships; the target-variant, scenario-ranking and failure-triage judgments wait for a
recorded harness run, per the operator's answer to question nine.

**KTD10 — the version bumps.** Saga goes to **0.172.0**, the next minor above `0.171.0` on the
integration branch `parent/1018` at this card's base commit `61da4b1c`; fleet-core goes to
**0.30.0**, the next minor above `0.29.0` at the same commit, because KTD3 adds a verb to its
registry. Both numbers are **re-read from `plugin.json` and renumbered above the integration branch
at the merge turn**, not above this branch's base: two cards writing an identical version string
merge silently, with the changelog heading as the only surviving signal — the failure the journal
entry `{#1028-identical-version-strings-merge-silently}` records. Release surfaces moving in the
same pull request: `plugins/saga/.claude-plugin/plugin.json`,
`plugins/fleet-core/.claude-plugin/plugin.json`, `.claude-plugin/marketplace.json`,
`plugins/saga/CHANGELOG.md` and `plugins/fleet-core/CHANGELOG.md`.

## High-Level Technical Design

```
.saga-profile.json  →  qa block: strategies, patterns, environments, scenarios, ceilings
        │
        ▼
qa-catalogue.yaml  ──►  load + validate  ──►  floor selection (file patterns, boundary filter)
                                                      │
                                       jev_widen.widen() ── advisory, union only, may fail
                                                      ▼
                                              preflight (env, secret handles, cost, duration)
                                                      │  over ceiling → refuse whole selection
                                                      ▼
                                        driver dispatch → passed | failed | blocked
                                                      │  redaction inside the driver
                                                      ▼
                                        one envelope each → run record, top-level `qa`
                                                      ▼
                                        verdict (count) → pass | pass-with-proof-debt | fail
                                                      ▼
                          route: close · build loop (with triage) · operator stop
```

Every arrow above is code. The only model call is the one marked advisory, its output is unioned
with the floor and never intersected, and nothing downstream of it reads a model output at all.

## Implementation Units

### U1. The catalogue, the two schemas, and the loader

**Summary:** Turn the specification's table into three data files and one loader that refuses a
malformed one by name.

**Files:** `plugins/saga/references/qa-catalogue.yaml` (new),
`plugins/saga/references/qa-profile.schema.json` (new),
`plugins/saga/references/qa-envelope.schema.json` (new), the loader half of
`plugins/saga/scripts/qa_strategies.py` (new).

**Detail:** Ten rows, each with `id`, `situation`, `tool`, `invocation`, `file_patterns`,
`required_evidence`, `proof_boundary`, `threshold`, `may_be_optional`, `driver` (the driver name or
`null` with a `no_driver_reason` and a `revisit_when`), and `cost_estimate`. One top-level
`judgment` block carrying the provisional act band (KTD9). The profile schema describes the `qa`
block of `.saga-profile.json` (KTD1); the envelope schema names the sixteen required fields of the
evidence envelope.

**Test scenarios** (`tests/test_qa_strategies.py`): the catalogue holds exactly ten strategies and
their identifiers are exactly the ten the specification names; every row carries a non-empty tool
invocation, file-pattern list, required-evidence list, proof boundary and threshold; a catalogue
missing a required column is refused with the column and row named; the declared act band is a
number between zero and one; a profile that validates against the profile schema loads and one
that does not is refused naming the failing field.

### U2. Selection: the floor, the boundary filter, and the widen-only judgment

**Summary:** Compute the required set from the profile's patterns, drop what the boundary cannot
prove, then let one advisory judgment add and never remove.

**Files:** the selection half of `plugins/saga/scripts/qa_strategies.py`;
`plugins/fleet-core/scripts/fleet_commons/jev_verbs.py` (one new `qa-strategies` verb, KTD3).

**Detail:** The floor is computed first, from the profile's file patterns against the change's file
list, and each selected entry records the pattern that selected it. Strategies whose proof boundary
the run's boundary cannot support are removed with the reason `out-of-boundary` and are recorded in
the selection block, never as a result and never as proof debt (R9). Only then is
`jev_widen.widen()` called, with the floor as its floors map and the catalogue's descriptions plus
the change's file list and summary as state; its unions are the final selection. Every probability,
the threshold and the resolved model are recorded.

**Test scenarios** (`tests/test_qa_strategies.py`): two matching patterns select exactly those two strategies with no judgment call
made and the printed selection names each matching pattern; a stubbed client above the band for a
third strategy yields three; the same client below the band for a declared strategy still yields
that strategy (both directions, reading the band from the catalogue file, R3); a client that is
absent, raises, times out, or returns a non-ok status yields the declared set and the run continues
(R4); at boundary `branch-preview` every `non-production` strategy is absent from the selection and
present in the out-of-boundary list (R9); the verb's ten question keys equal the catalogue's ten
strategy identifiers in both directions (the KTD3 guard).

### U3. Preflight: environments, secret handles, cost and duration

**Summary:** Decide before running anything whether the whole selection can run, and refuse the
whole selection rather than the affordable part of it.

**Files:** the preflight half of `plugins/saga/scripts/qa_strategies.py`.

**Detail:** For each selected strategy, check the environment variables and secret handles the
profile declares for it, and sum the catalogue's cost and duration estimates. Over the profile's
ceiling, the run refuses whole: zero drivers, a recorded refusal naming the ceiling and the
estimate, and a `blocked` verdict. A missing environment is not a preflight refusal — it is that
one strategy's `blocked` result at dispatch (R5), because a run that can still prove four of five
things should prove them and say what it could not.

**Test scenarios** (`tests/test_qa_strategies.py`): an estimate over the profile's ceiling runs zero drivers and records the
refusal with both numbers (R10); an estimate under the ceiling runs every selected driver; a
profile with no ceiling declared refuses to run rather than assuming an unlimited one; a missing
secret handle named by the profile refuses the whole selection, because a credential decision is
the operator's.

### U4. The envelope, the redaction, and the drivers

**Summary:** One envelope per strategy, three statuses, secrets removed before the envelope exists,
five drivers that run and five that say why they cannot.

**Files:** the driver half of `plugins/saga/scripts/qa_strategies.py`.

**Detail:** A driver takes the strategy row, the profile's entry for it, the environment identity
from the run record and an injected runner, and returns one envelope. Every driver returns exactly
one of `passed`, `failed`, `blocked`; a driver that fails to start is `blocked`, never an exception
that ends the run. Redaction (KTD6) runs on every captured output before it reaches the envelope.
The five shipping drivers and their thresholds: `cli-smoke` — each declared invocation exits zero
and the reported version matches the deployed version marker; `contract-check` — the drift result
is empty or holds only changes the profile marks permitted; `deploy-boundary` — the marker served
at the edge equals the revision the release step recorded; `installed-surface` — **both** installed
plugin trees resolve the released version and carry the expected commands and skills, which is the
specification's open question answered "both" and the one this repository's six-release history of
one-tree-updated-and-one-not makes load-bearing; `api-workflow` — delegation to the
`campps-e2e-canary` entrypoint the profile declares, ingesting its envelope rather than issuing
requests (R13). The other five return `blocked` with the catalogue row's `no_driver_reason`.

The `installed-surface` driver resolves its two plugin roots through fleet-core's existing
plugin-resolution component, loaded the way `plugins/saga/scripts/admission.py:153-156` already
loads it, rather than hard-coding two home-directory paths. The roots are not the same on every
machine, and a hard-coded path is how a check starts quietly reading the wrong tree — which is the
failure this strategy exists to catch.

**Test scenarios** (`tests/test_qa_strategies.py`): an unset required environment variable yields `blocked` with the variable named
and never `passed` (R5); a driver whose captured output contains a bearer token writes an envelope
with no token (R8); every written envelope validates against the envelope schema with the real
`jsonschema` library (R8, KTD5); a driver that raises yields `blocked` and the run continues; a
strategy with no driver yields `blocked` carrying the catalogue's stated reason; the CAMPPS
delegation records the exact invocation and ingests the returned envelope (R13);
`installed-surface` fails when one of the two trees resolves a different version from the other.

### U5. The verdict, the route, and the run record

**Summary:** Count the statuses, write the block, and route — including the route that does not go
to the build loop.

**Files:** the verdict and recording half of `plugins/saga/scripts/qa_strategies.py`.

**Detail:** The verdict function is pure arithmetic over the envelopes (R6). The route follows from
it: `pass` advances to close; `fail` returns to the build loop; a **required** `blocked` stops for
the operator (R7) and, per KTD4, is never handed to `release_step.record_functional_test`. The `qa`
block is written to the run record under the top-level extension point (KTD8), and proof debt —
every required strategy passed with at least one optional strategy blocked — carries the strategy,
its reason and a revisit condition.

**Test scenarios** (`tests/test_qa_strategies.py`): the verdict over the full status matrix returns `pass`,
`pass-with-proof-debt` and `fail` in the declared combinations (R6); a required `blocked` routes to
the operator stop and not to the build loop (R7); a run with only blocked scenarios never reaches
`record_functional_test` (the KTD4 guard, which fails if the routing is loosened); the `qa` block
round-trips through a save and a load with no other top-level key disturbed; an all-optional
profile and a repository with no `qa` block each produce a `blocked` run naming `.saga-profile.json`
and the missing key, never a `pass` (R14).

### U6. The command line, the boundary flag, and this repository's own profile

**Summary:** Give the Functional Tester one command to run and this repository a profile to prove
the whole thing against.

**Files:** the entry point of `plugins/saga/scripts/qa_strategies.py`; `.saga-profile.json`
(the new `qa` block).

**Detail:** Subcommands `select` (print the selection and its reasons, run nothing), `run` (the
whole procedure), and `verdict` (recompute from what the record already holds). A `--boundary` flag
defaulting to `non-production`, which is what makes this the build loop's smoke runner at
`branch-preview` without editing that loop (KTD2). This repository's `qa` block declares
`cli-smoke` and `installed-surface` as required — the two whose drivers can actually prove
something here — with `contract-check` and `deploy-boundary` optional, its file patterns, its
scenarios, and its cost and duration ceiling.

**Exit codes, declared here so the tests can assert them and the build loop can read them.** The
build loop already fixes the pattern of a small, documented exit-code table
(`plugins/saga/scripts/build_loop.py:120-125`), and this runner follows it: `0` the verdict is
`pass` or `pass-with-proof-debt`; `1` an internal error; `2` a refusal — the preflight refused the
whole selection, or the profile proves nothing, or there is no profile; `3` an unknown record
version; `4` the verdict is `fail`; `5` a required strategy is `blocked` and the run stops for the
operator. The last two are separate codes on purpose, because they route to different places
(R7).

**Test scenarios** (`tests/test_qa_strategies.py`): `select` runs zero drivers and prints one reason per entry; each of the six
exit codes is produced by the condition declared for it, asserted one per case; this repository's
own profile block validates against the profile schema.

**Live check (R15, not a unit test):** one end-to-end `run` at the `non-production` boundary
against this repository's profile produces a `pass` with at least two strategies reporting
`passed`, one comment published to issue 1039 carrying the per-strategy statuses, and the verdict
written to the run record. Its transcript is recorded in the work-session document.

### U7. The skill, the command, the references, the removals and the release surfaces

**Summary:** Rewrite the prose the Functional Tester actually reads, delete the score, and move the
release surfaces in the same pull request.

**Files:** `plugins/saga/skills/qa/SKILL.md` (rewritten),
`plugins/saga/commands/qa.md` (rewritten),
`plugins/saga/skills/qa/references/risk-taxonomy.md` → `qa-catalogue-reference.md` (renamed with
`git mv`, then rewritten), `plugins/saga/skills/qa/references/qa-report.md` →
`qa-evidence-and-verdict.md` (the same), `plugins/saga/scripts/qa_health_score.py` (deleted),
`tests/test_qa_health_score.py` (deleted), **`tests/test_saga_plugin.py`** (the qa-corpus
assertions, see below), `plugins/saga/.claude-plugin/plugin.json`,
`plugins/fleet-core/.claude-plugin/plugin.json`, `.claude-plugin/marketplace.json`,
`plugins/saga/CHANGELOG.md`, `plugins/fleet-core/CHANGELOG.md`,
`docs/engineering-journal/LEARNINGS.md` and `docs/engineering-journal/DECISIONS.md` (entries under
the existing `## 2026-09-20` heading).

**Detail:** The skill becomes the functional-test step: one command, the catalogue, the profile,
the envelope, the three-value verdict, the three routes, and an explicit statement that it never
fixes anything. The nine-way router, the severity assignment, the score, the ledger freeze and the
advisory-router framing all leave. The two reference documents are **renamed and then rewritten**,
rather than created new alongside deleted old ones: the card lists both as "replaced", a rename
keeps their history attached to their successors, and a file called `risk-taxonomy.md` holding a
strategy catalogue would be a name that lies about its contents.

**The one existing test that this rewrite makes red, named here because an implementer following
the plan literally would otherwise meet it at the gate.** `tests/test_saga_plugin.py:1281-1290`
asserts that the qa skill document and the report reference each contain the literal string
`qa_health_score.py`, and counts the score blocks across the corpus. Deleting the script and
rewriting the skill turns those assertions red, and R16's gate can never pass while they stand.
They are rewritten in the same commit to assert the successors instead: that the skill names the
catalogue file and the strategy runner, that the evidence reference names the envelope schema and
the three statuses, and that neither names a score. This is the only file outside the card's list
that the change forces, and it is forced by the card's own removal.

**A downstream consequence, named and deliberately left alone.**
`plugins/saga/scripts/status_card.py:546-600` parses `health_score:` out of the qa artifact's
frontmatter to decide whether the gate ran. After this card `/qa` writes no such frontmatter, so
that parse finds nothing — which its existing guard (`if health_score_raw or tier_raw`) already
handles by omitting the checks section rather than failing. The literal string `health score` with
a space does not appear in that file, so R11's sweep is unaffected. Teaching the status card to
read the new verdict is a follow-up, not this card: the card does not name the file and the
degradation is silent-but-safe rather than wrong.

**Test scenarios** (`tests/test_qa_strategies.py` and `tests/test_saga_plugin.py`): neither deleted file exists and no file under `plugins/saga/skills/qa/` or
`plugins/saga/scripts/` contains the string `health score` (R11, R17); no file under
`plugins/saga/skills/qa/` references `evidence_ledger` (R12); the rewritten qa-corpus assertions in
`tests/test_saga_plugin.py` pass and name the catalogue rather than the score; the saga and
fleet-core versions match across `plugin.json`, `marketplace.json` and the changelog heading (the
repository's existing metadata drift guards).

## Scope Boundaries

**Out of scope — true non-goals:**

- Fixing anything. `/qa` reports, verdicts and routes; every repair belongs to the build loop.
- Any score, rating, or model-assigned severity, in any form.
- Any paid external service — no device farm, no hosted browser grid, no commercial monitor. Local
  toolchains and open-source tools only, by the operator's answer to question five, which is also a
  refusal to name one without him.
- Visual regression, golden-image comparison, performance and load.
- Any production target. The destination is non-production.
- Reimplementing what `campps-e2e-canary` owns.

**Out of scope — owned by the parallel sibling, issue 1030.** That card owns every removal its own
card names: the eleven retired commands and their script families, the ledgers including
`evidence_ledger.py`, the closure and completeness gates, the execution spec, team-execution, and
the retired hooks and agents. This card removes only what its own card names
(`qa_health_score.py` and `tests/test_qa_health_score.py`). Where the rewritten skill stops calling
a module issue 1030 deletes, it simply stops calling it and leaves the deletion there. This card
touches no file in that list.

**Deferred to follow-up work, each with the condition that reopens it:**

- Drivers for `data-check` and `infrastructure-read-back` — each needs an environment or credential
  decision the operator owns. Reopens when he makes it.
- Drivers for `app-ui` and `hosted-surface` — declared without one per KTD7. Reopens with the first
  repository whose profile declares them, which is where a real target exists.
- The target-variant, scenario-ranking and failure-triage judgments — they ship after the
  evaluation harness records agreement for the widening judgment at the chosen band.
- The blocked-scenario arithmetic in `release_step.record_functional_test` (KTD4). Recorded in the
  engineering journal; reopens when a second caller can produce a blocked scenario.
- Teaching `plugins/saga/scripts/status_card.py` to read the new verdict instead of the score's
  frontmatter (U7). Its existing guard already degrades safely to an omitted checks section.
  Reopens when the operator wants the functional-test verdict on the status card.

## Risk Analysis and Mitigation

| Risk | How it would show | Mitigation in this plan |
|---|---|---|
| The judgment narrows the selection | A required proof silently disappears on the change that most needed it | The floor is computed before the client is called and unioned, never intersected; `jev_widen` is reused rather than reimplemented (KTD3); asserted in both directions (U2) |
| A driver returns `passed` on an unreachable environment | The chain reports working software on zero evidence | Three-value result and R5's test; a driver that raises is `blocked`, never an exception |
| A blocked run reads as a pass downstream | The silent skip returns through the release step's arithmetic | KTD4: `/qa` routes itself and never hands a required blocked to that function; guarded by a test that fails if the routing is loosened |
| A secret lands in a durable record | A token in the run record or in an artifact pointer | Redaction inside the driver before the envelope exists, reusing a pattern set already in production use (KTD6). The run record itself lives under the git-ignored `.claude/saga/`, so redaction is defence in depth rather than the only barrier; an envelope's artifact pointers carry paths, never captured values |
| The catalogue and the fleet-core verb drift | The judgment silently stops being asked about a strategy | The key-set equality guard in U2, asserted in both directions |
| Two cards take the same version string | The bump merges silently and the changelog is the only signal | KTD10: renumber above the integration branch at the merge turn, not above this base |
| The runtime grows a development-only dependency | The functional-test step fails on a plain install | KTD5: a runtime checker driven by the schema file, `jsonschema` in the tests only |
| The whole design proves wrong in use | The functional test is worse than the improvised one it replaced | The old skill is replaced in one commit and restorable from history; the run record is written fresh per issue, so there is no migration to unwind |

## Alternatives Considered

**A separate `.saga-qa-profile.json`.** Rejected in KTD1: it splits one repository's
self-description across two files, and the existing profile document already sets the precedent for
an optional key.

**Importing the strategy runner into the build loop.** Rejected in KTD2: a command name achieves
the same sharing and couples no merge turns.

**Calling the TypeSafe client directly instead of adding a fleet-core verb.** Rejected in KTD3: it
avoids one version bump and duplicates the widen-only guarantee, which is the guarantee this design
most depends on.

**Fixing the release step's blocked arithmetic here.** Rejected in KTD4: it reaches into a
sibling's merged work for a case only this card can produce; recorded as a follow-up instead.

**Shipping `app-ui` and `hosted-surface` drivers untested.** Rejected in KTD7: an unexercised
driver is exactly the "graceful no-op" failure this card exists to remove, wearing a new name.

## Questions Answered from the Card

The plan skill asks the operator for these. `AskUserQuestion` is unavailable in this session, so
each was answered from the card, the specification, the requirements document and the code, with
the documented default taken where all four are silent. Nothing in the production, destructive,
credential, permission, billing, external-commitment or process-authority classes was invented.

| Question | Answer taken | Where it came from |
|---|---|---|
| Is a plan document warranted (Phase 0.4)? | Yes | Seven units, ten load-bearing technical decisions and an upstream specification needing traceability; nowhere near the atomic-work skip |
| Scope class (Phase 0.5) | Deep | Cross-cutting, high ambiguity, seven units, and a step every repository's definition of "working software" runs through |
| Destination (Phase 5.1) | `pr` | The caller's `plan_pre_answers.v1` carrier, validated clean by `plan_pre_answers.py`, applied and narrated per the skill's intake rule |
| Execution backend (Phase 5.2) | `inline` | The same carrier; `inline` is the one backend value the carrier may apply without explicit operator invocation |
| Resume or mint a saga (Phase 0.3) | Mint | `saga.py scan` returned zero candidates |
| Risk tier (admission) | `medium` | The card's own Risk section, quoted verbatim into the admission record |
| The seven approval boundaries (admission) | `none` in all seven | The card states the change ships no production access and no new credential, and the specification forbids any paid service; recording `none` refuses scope rather than granting it, and no boundary was granted that the card does not already rule out |
| Staffing overrides (admission) | None | The staffing component's defaults; the card names no role needing a different tier |
| Lens declaration (admission) | The four always-on lenses plus documentation clarity; four conditional lenses left out with a reason each | The card's security flag from `parse_issue.py`, and the rewrite of three documents the Functional Tester reads as its whole instruction set |
| Repair allowances (admission) | The documented default: 3 standard, 2 escalated | The lifecycle repository's decided defaults; the card asks for no change |
| When prescribed testing cannot finish (admission) | Bring the result to the operator | The requirements document's question six, answered by the operator on 2026-09-19 |
| Change shape (admission) | Mixed | Seven units spanning Python, data files and skill prose |
| Verdict vocabulary | `pass` / `pass-with-proof-debt` / `fail` | The operator's answer to question one |
| Who owns the catalogue and the scenarios | Saga owns the strategy families; each repository owns its scenarios in its profile; CAMPPS repositories delegate | The operator's answer to question two |
| Simulator: strategy or target | A target variant of `app-ui` | The operator's answer to question three |
| Does the build loop share this catalogue | Yes, the same command at a narrower boundary | The operator's answer to question four, implemented as KTD2 |
| Budget mechanism | A per-repository ceiling in the profile, with the canary's refusal mechanism | The operator's answer to question ten |
| Which judgments ship | The widening judgment only | The operator's answer to question nine |
| Both installed plugin trees, or one | Both | The specification's open question, recommendation "both", and six recorded releases where one tree updated and the other did not |
| A scenario the plan named that the profile lacks | Block and ask | The specification's open question, recommendation "block", following from the operator's answer to question eight |

## Verification

```bash
uv run python -c "import yaml;d=yaml.safe_load(open('plugins/saga/references/qa-catalogue.yaml'));print(len(d['strategies']))"
uv run pytest tests/test_qa_strategies.py -v
test ! -f plugins/saga/scripts/qa_health_score.py && test ! -f tests/test_qa_health_score.py && echo "score removed"
! grep -rq "evidence_ledger" plugins/saga/skills/qa/ && echo "ledger call removed"
! grep -rqi "health score" plugins/saga/skills/qa/ plugins/saga/scripts/ && echo "string swept"
```

The whole repository gate is the coordinator's to run after this branch merges onto the
integration branch, per this run's rules; it is not run from this worktree.

## Related

- Issue 1039 — this card.
- Issue 1018 — the saga simplification parent; this card never opens its own pull request.
- `docs/specs/2026-09-19-qa-testing-strategies-spec.md` — the specification, sixteen criteria.
- `docs/brainstorms/2026-09-19-qa-testing-strategies-requirements.md` — the operator's ten answers.
- Issue 1023 — the run record; the envelopes' home.
- Issue 1028 — the environment identity and this step's position in the chain.
- Issue 1032 — the TypeSafe client, the `jev` tool and the evaluation harness.
- Issue 1027 — the build loop; a shared runner by command name, not by import (KTD2).
- Issue 1030 — the parallel sibling; it owns every removal this plan does not name.
