---
title: Issue 1001 — Saga code review consumes the sdlc roster, runs lens sessions, and computes the verdict
type: feat
status: active
date: 2026-09-19
origin: docs/analysis/2026-09-19-improve-claude-plugins-objective-plan.md
backend: inline
---

# Issue 1001 — Saga code review consumes the sdlc roster, runs lens sessions, and computes the verdict

## Summary

The Saga code-review skill in this repository currently decides for itself what good code means: it
reads a private fourteen-lens policy file, `plugins/saga/references/lens-roster.json`, and scores
against it. The Infiquetra software-development-lifecycle repository (`infiquetra/infiquetra-sdlc`,
called "the lifecycle repository" from here on) now owns that policy, and its architecture decision
record ADR-001 ("the code-review executor boundary") says the plugin is a policy-free executor of a
roster it does not author.

This plan makes that true. Code review will read the lens declaration out of the run record, hand it
to the lifecycle repository's own generator `tools/docs/gen_review_roster.py` to produce a
content-addressed `review_roster.v1`, run one Lens Reviewer per selected lens, compute the verdict in
code from the catalogue's strictness ladder, write a `review_result.v2` into the run record, and
publish the findings as exactly one pull-request comment bound to the reviewed commit — never an
approving review.

## Problem Frame

Three facts, each checked against a current source today rather than recalled.

**The acceptance rule in use is not the organisation's rule.** `plugins/saga/scripts/review_consensus.py`
is 2,787 lines and resolves its thresholds from `ROSTER_PATH` at line 94, which is the plugin's own
`references/lens-roster.json` (1,375 lines). The lifecycle repository's catalogue
(`config/lens-catalogue.json`, 2,882 lines at revision `5efc869f`) holds fifteen lenses, a
three-level strictness ladder, a finding schema and a status vocabulary, and nothing in the plugin
reads any of it.

**The generator can be invoked without vendoring it, and the card's stop condition therefore does not
fire.** This was proved, not assumed. `tools/docs/gen_review_roster.py` imports only `argparse`,
`hashlib`, `json`, `pathlib`, `sys` and `typing`; it resolves its own repository root from
`Path(__file__).resolve().parents[2]` and reads the catalogue, the profile and the ledger relative to
that. Running it from a temporary export of revision `5efc869f` with a hand-built declaration
produced a `review_roster.v1` with hash
`sha256:3a2863068c891cf12f51eb38b216f296a2e988107ed1fb9002cd7817b0700e7a`, selecting eight of the
catalogue's fifteen lenses, plus a `review_roster_validation.v1` report. A subprocess call with the
system Python is enough; no vendored copy, no dependency install, no working-directory requirement.

**No executor is qualified to score anything yet, and that shapes the whole design.** The lifecycle
repository's executor-verification ledger, `config/executor-verifications.json`, has an empty
`entries` array. That is true at the pinned revision `5efc869f` and equally true on that
repository's `origin/main`, which is the same commit — both were read today, not recalled. The
generator refuses a scoring executor with no matching ledger entry, so the probe run above came back
`status: refused` on its `verification_presence` check and exited 1. Until the lifecycle repository
records its first qualification runs (its issue 170's follow-on work, recommendation R24 of the
simplification review), every lens in this repository reports findings and establishes no threshold.
The design must make that the ordinary, honest path rather than a crash.

## Requirements

**R1.** The lens declaration is read from the run record, never invented by the review. The record at
`<primary checkout>/.claude/saga/runs/issue-<N>.json` carries `run_configuration.applicable_lenses`,
written at admission. The review builds an `applicability_declaration.v1` document from it and never
asks the operator to restate it.

**R2.** `review_roster.v1` is produced by invoking the lifecycle repository's generator as a
subprocess. The plugin never reimplements the resolution and never edits the resulting document. Its
content hash is whatever the generator computed, carried through unchanged.

**R3.** The lifecycle checkout is resolved through the staffing component's existing
`fleet_commons.staffing.sdlc_root()`, whose order is an explicit path, then the
`INFIQUETRA_SDLC_PATH` environment variable, then `~/workspace/infiquetra/infiquetra-sdlc`. When it
returns `None`, or when the generator is missing from the resolved checkout, the review **refuses by
name** and writes `review_incomplete`. There is no fallback roster, and the deleted
`lens-roster.json` is never resurrected as one.

**R4.** The exact revision of the lifecycle checkout used for a resolution is recorded in the run
record beside the roster hash, together with whether that checkout's `config/` and `tools/docs/`
directories were clean at the time. A roster resolved from an uncommitted local edit is still a
roster, but a reader must be able to see that it was.

**R5.** One Lens Reviewer runs per selected lens on a verified executor. The choice between a herdr
roster session (through `plugins/agent-launcher/skills/agent-launcher/scripts/roster.py`) and an
in-session subagent is made once per review and recorded in the result's hosting topology; it is
never made per lens and never left implicit.

**R5a.** Each lens dispatch carries exactly five things and nothing else: the issue, the one lens
identifier, the frozen reviewed revision, the roster hash, and the vendor, model, effort and prompt
hash named for that lens in the roster. It carries no other lens's findings, no host's reading of the
diff, and no prior cycle's scores — the catalogue's no-shared-context-contamination invariant. The
rubric itself is not copied into the brief: `plugins/agent-launcher/roles/lens-reviewer.md` already
tells the session how to reach the lifecycle repository and read the catalogue for itself, and the
brief names the lens rather than restating it. Every dispatch states vendor, model and effort
explicitly, because the catalogue's no-hidden-model-inheritance invariant makes an inherited
configuration an unverified one.

**R5b.** Each lens result is written durably the moment it completes, never batched at the end of a
cycle, so a hosting session's death loses only what was in flight and recovery re-dispatches only the
missing lenses.

**R6.** The verdict is computed in code, as a total function of three facts about the cycle, and
emits exactly one of `accepted`, `repairs_requested`, `cycle_cap_best_available`, `review_incomplete`
and nothing else.

**R7.** A lens the catalogue marks `scorable: false` reports findings and establishes no threshold.
Eleven of the catalogue's fifteen lenses are in that state today, because they carry no fixtures.

**R8.** `review_result.v2` is written into the run record's `review_cycles` array, one entry per
cycle, and carries every provenance field the catalogue's `result_provenance_fields` requires.

**R9.** Findings are deduplicated by the catalogue's own fingerprint — path, line and category — and a
duplicate is recorded as `duplicate-of` against the finding it repeats, never deleted and never
counted twice.

**R10.** There is one review history per unit. A request to start a fresh history for a unit that
already has one is refused, because a fresh history would reset the cycle counter and put
incomparable scores side by side.

**R11.** Publication writes exactly one pull-request comment, naming the reviewed revision as a full
forty-character commit identifier, and submits no pull-request review of any kind. A later commit
never inherits an earlier revision's outcome.

**R12.** At the cycle cap — three standard cycles then two escalated — the residual findings are filed
as linked defect issues, their numbers are listed in the result, and the run proceeds with
`cycle_cap_best_available`. There is no fourth standard cycle. The two narrow exceptions that still
block a merge are reproduced data loss or destructive behaviour, and a reproduced security exposure.

**R13.** `plugins/saga/references/lens-roster.json` is deleted, and nothing in the saga plugin reads
it afterwards.

**R14.** `plugins/saga/scripts/evidence_ledger.py` is no longer called by the code-review skill. The
module itself stays, because other callers use it; only this skill's call site goes.

**R15.** The release surfaces move in the same pull request: `plugins/saga/.claude-plugin/plugin.json`,
`.claude-plugin/marketplace.json`, and `plugins/saga/CHANGELOG.md`.

## Admission answers

The repository's own admission step ran before planning:
`uv run python plugins/saga/scripts/admission.py --issue 1001`. It filled twelve of the thirteen
run-configuration parameters and wrote the record to
`/Users/jefcox/workspace/infiquetra/infiquetra-claude-plugins/.claude/saga/runs/issue-1001.json`. The
operator was not available to answer, so each non-defaultable answer was taken from a named source
and is listed here with that source.

| Question | Answer taken | Source |
|---|---|---|
| `risk_tier` | `high`, justified as "it replaces the pre-merge gate; the mitigation is that the acceptance rule is the lifecycle repository's own and the first real review is watched" | Issue 1001's own Risk section, verbatim |
| `approval_scope` | `none` granted in all seven categories: production changes, destructive operations, secrets or credential changes, identity-and-access-management or permission changes, billing or cost-impacting actions, external commitments, major team or process authority changes | The operator's standing list for this run, relayed by the coordinator |
| `destination` | `pr` | The coordinator's instruction, and the `plan_pre_answers.v1` carrier, which the validator applied cleanly |
| `staffing_overrides` | `none` — the staffing component's defaults stand | The coordinator's instruction; this card's own planning tier is opus at high effort by the operator's work-shape policy |
| `lens_declaration` | The four always-on lenses, plus five conditional lenses that apply (reliability, api-contract, adversarial, documentation-clarity, agent-usability) and six that do not, each with a recorded reason | The catalogue's own `applies_when.condition` text for each conditional lens, matched against this card's declared file list |
| `repair_allowances` | three standard cycles, then two escalated | Issue 1001, and the lifecycle repository's `docs/reviewers/repair-planning.md` at revision `5efc869f` |
| `unfinished_testing_response` | `human-involvement` — bring the result to the operator | See the note below; this is the one answer where the coordinator's premise did not hold |
| `change_shape` | `code` | The card's file list is three scripts, a skill, its references, tests and release surfaces |
| `branch_preview` | `false` | Filled from `.saga-profile.json`, not asked |
| `main_consumed_directly` | `false` | Filled from `.saga-profile.json`, not asked |

**Why the five conditional lenses apply.** Reliability, because this change owns lens-execution
recovery — two backoff retries, one substitution, per-lens durable writes, and failure isolation when
a hosting session dies. Api-contract, because it authors command-line contracts for three scripts and
two file-format contracts, `review_roster.v1` and `review_result.v2`, which ADR-001 names as the
cross-repository compatibility contract. Adversarial, because the catalogue's condition names "a
policy or a gate" and this change is the pre-merge gate itself. Documentation-clarity, because the
skill and its four reference documents are rewritten. Agent-usability, because the skill, the Lens
Reviewer prompt and the machine-readable result are all surfaces an agent must operate.

**The one answer with no lifecycle default.** The coordinator's instruction said to take "the
lifecycle's default at the pin" for the response to unfinished functional testing. There is no such
default. `config/run-model.json` at revision `5efc869f` states that `RC-unfinished-testing-response`
is "chosen per run from a closed set of two" — `human-involvement` or
`continued-goal-driven-repair` — and names no default for either. `human-involvement` was taken,
because this repository's profile sets `nonproduction_destination` to `none`: there is no deployed
environment for a functional test to run against, so continued goal-driven repair would have nothing
to drive toward. This is a recorded choice, not a default, and the operator can overturn it.

**The one parameter still unfilled, and why.** `per_lens_score_threshold` remains `unset`. The cause
is a shape mismatch in a sibling card's code, not a missing answer:
`plugins/saga/scripts/admission.py` at line 339 calls
`staffing.lens_catalogue()`, which returns a pair of a dictionary keyed by lens identifier and a
version string, then reads `catalogue.get("lenses")` and `catalogue.get("strictness_ladder")` off the
first element — keys that shape does not have. Both lookups return `None` for every checkout, so the
parameter can never be filled by that path. This belongs to issue 1023, which owns `admission.py`;
this card does not repair it, and this card's own code reads the catalogue directly rather than
through that helper.

**The eighth approval boundary.** The coordinator's standing list has eight entries; the run record's
`APPROVAL_CATEGORIES` has seven. The extra one — plan-review and code-review overrides stop and ask
the operator — has no category to sit in, so it is recorded here in prose and honoured as a rule of
this plan: no unit weakens a review threshold or overrides a review verdict without asking.

## Questions answered from the card

The installed `/plan` skill asks from a known set at four points. None was put to the operator; each
was answered from the card, the run record, the lifecycle repository at its pin, or the code.

| Where the skill asks | Answer taken | Where it came from |
|---|---|---|
| §0.7, the pre-answers carrier | `destination: pr`, `backend: inline`, caller "improve-claude-plugins run driver" | `plan_pre_answers.py --invocation-file` exited 0 with a clean apply and no stop |
| §0.4, is a plan document warranted | yes | Three scripts of which two are new, a skill and four references rewritten, a file removed, six children mapped, and release surfaces — nowhere near atomic |
| §0.5, scope class | deep | The same list, plus a cross-repository dependency and a high risk tier |
| §5.1, the destination | `pr`, not re-asked | Applied at intake by the carrier, exactly as §5.1 instructs |
| §5.2, the execution backend | `inline`, recorded against a recommendation of `team-execution` | The carrier applied `inline`; `lifecycle_state.recommend_execution_backend` was still called and returned `team-execution` on the size-and-risk signal. `inline` stands for a second reason worth naming: parent 1018 archives the `team-execution` plugin, so that backend is not a live option in this run |

No question about production, destructive operations, credentials, permissions, billing, external
commitments, or process authority arose, and none would have been answered from a document if it had.

## Key Technical Decisions

**KTD1 — the generator is invoked, never reimplemented, and never vendored.** `review_roster.py`
shells out to `python3 <sdlc-checkout>/tools/docs/gen_review_roster.py --declaration <file>` and
parses the document it prints. The alternative — porting the resolution into the plugin — was
rejected on the evidence of the probe run above: the generator needs no dependency the plugin would
have to carry, so a port would buy nothing and would guarantee the two copies drift. The card's stop
condition is therefore not triggered, and this plan records that finding rather than planning around
it.

**KTD2 — the declaration is built from the run record, because the record has no slot for one.**
`plugins/saga/references/run-record.md` lists twelve top-level keys and thirteen run-configuration
parameters; none of them is an `applicability_declaration.v1`. Parameter 8,
`applicable_lenses`, holds the admission-shaped answer. `review_roster.py` translates that answer,
plus the reviewed revision, the repository, the issue number and the staffing, into the declaration
shape the generator documents. The translation is one function with its own tests, so the two shapes
can be compared rather than conflated.

**KTD3 — a missing lifecycle checkout is a named refusal, not a degraded review.** The staffing
component already treats an absent checkout as a legitimate "documented-policy" answer for a single
lens. That is right for staffing and wrong here: a review that cannot resolve a roster has no policy
to execute at all. `review_roster.py` exits 2 with one line naming `INFIQUETRA_SDLC_PATH` and the
path it tried, and the review writes `review_incomplete`. Acceptance is never invented from absence,
which is the catalogue's own rule.

**KTD4 — the empty ledger is the ordinary path, not an error.** Because
`config/executor-verifications.json` has no entries, the generator's validation report comes back
`refused` on `verification_presence` for every always-on lens. The review treats a refused report as
a run-setup fact: it records the report verbatim, runs every selected lens for findings, and emits
`review_incomplete` rather than a score. The moment the lifecycle repository records its first
qualification, the same code path produces real scores with no change here. Two alternatives were
rejected: inventing a local qualification, which would make the plugin a policy owner again; and
treating a refusal as a crash, which would make every review today fail with a traceback instead of a
result.

**KTD5 — the verdict is the lifecycle repository's four-row table, read in its stated order.** From
`docs/reviewers/verdicts-and-consensus.md` at revision `5efc869f`: an unusable lens result is decided
*before* a low score, because a lens that did not run tells you nothing about the code. So the order
is `review_incomplete` first, then `accepted` when every selected lens is met, then
`repairs_requested` when at least one is not met and the allowance holds, then
`cycle_cap_best_available` when it does not. "Met" is a pair, never one number: the lens's derived
overall at or above the level's minimum *and* every applicable dimension at or above the level's
dimension floor. At `standard`, the level the default profile sets for every lens, that pair is 9.0
and 7.

**KTD6 — the hosting choice is made once per review and recorded.** A roster session is used when the
run record's `roster` array already names panes for this issue, or when the caller asks for one; a
subagent is used otherwise. Recording it is not decoration: the catalogue's six hosting invariants —
no shared-context contamination, no hidden model inheritance, failure isolation, concurrency
ceilings, read-only isolation, attribution — all travel with the logical executor, and a result that
cannot say which topology hosted it is not evidence.

**KTD7 — the review-side external advisory seat goes; the Work-side second-opinion machinery does
not, here.** Issue 1001 rewrites `plugins/saga/skills/code-review/SKILL.md` and
`plugins/saga/scripts/review_consensus.py`, so the "External whole-diff advisory seat" section and
the `ExternalFindingAdjudication` and `ExternalAdvisoryReview` classes at lines 578 and 613 of that
script are inside this card's declared file list and are removed. `plugins/saga/scripts/second_opinion.py`
(2,076 lines) and `plugins/saga/skills/work/SKILL.md` are not in issue 1001's file list; they are
issue 938's. See the child-card map below for the reasoning and the follow-up.

**KTD8 — the lifecycle checkout's revision is recorded with the roster hash.** The generator reads the
*working tree* of whatever checkout `sdlc_root()` resolves, not a pinned revision, so two runs a day
apart can resolve different policy from the same instruction. Recording `git -C <checkout> rev-parse
HEAD` and whether `config/` and `tools/docs/` are clean makes that visible. Pinning the checkout to a
revision was rejected: the lifecycle repository's own decision C1g says the run-frozen roster hash is
the sole pinning point, and a second pin would compete with it.

**KTD9 — one environment variable names the lifecycle checkout, and it is `INFIQUETRA_SDLC_PATH`.**
Two names for the same thing are live on this branch right now. The staffing component uses
`INFIQUETRA_SDLC_PATH` (`plugins/fleet-core/scripts/fleet_commons/staffing.py:59`), as do
mission-control's README, its card-validator test and its project-mapping override. Sixteen role
prompts under `plugins/agent-launcher/roles/` use `INFIQUETRA_SDLC_ROOT` instead — the lens reviewer's
at line 59, and fifteen siblings at the same position. Setting one does not set the other, so a review
whose controller resolved the checkout one way would dispatch lens sessions that resolve it another
way or not at all. This card adopts `INFIQUETRA_SDLC_PATH`, because it is the one the *code* reads
rather than the one prose describes, and it is already load-bearing for mission-control. Repointing
the sixteen role prompts is issue 1022's file and therefore a follow-up, recorded under Scope
Boundaries; until it lands, U1 accepts `INFIQUETRA_SDLC_ROOT` as a second-priority read and says in
its refusal line which of the two it found, so the mismatch surfaces as a sentence rather than as an
empty resolution.

**KTD10 — the roster is resolved at the checkout's working tree; the lens sessions read the lifecycle
at the pin. Both are recorded.** The role prompts instruct each lens session to read every lifecycle
document with `git -C <checkout> show 5efc869f:<path>`, explicitly refusing the working tree because
"a document at an unknown revision is a guess with a citation on it". The generator cannot do that: it
resolves its inputs from its own location on disk. The two are reconciled by recording both — the
checkout's `HEAD` from KTD8 beside the roster hash, and the pin each lens session read — so a reader
can see whether they agreed. Making the generator read a pin was rejected because it would mean
vendoring or patching the lifecycle repository's own tool, which KTD1 rules out.

**KTD11 — the cycle counter is the length of the run record's `review_cycles` array, filtered by
loop.** The lifecycle repository's rule is one counter per loop, not one per run: the pre-merge code
review loop and the post-merge repair loop each keep their own allowance and their own count, and an
execution retry or a substitution consumes neither. Each `review_result.v2` entry therefore carries a
`loop` field valued `code_review` or `post_merge`, and the allowance check counts entries with a
matching loop rather than the array's length. Without the field the post-merge loop would silently
spend the pre-merge budget, which is exactly the failure the lifecycle repository's decision D5 names.

**KTD12 — a `review_result.v1` entry already in a run record is read, reported, and never rewritten.**
Existing records may hold entries the previous scorer wrote. The run record module's own convention
supplies the rule: an unknown version is reported by name in one line and preserved unchanged. A v1
entry is therefore counted toward neither loop's allowance — its cycle accounting used a different
acceptance rule and is not comparable — and the first v2 cycle in that record starts at one, with the
reason recorded in the result. Silently upgrading a v1 entry was rejected: it would put incomparable
scores in one history, which is exactly what child 946 exists to prevent.

**KTD13 — publication lives in `review_result.py`, not in a fourth script.** Issue 1001 names exactly
three scripts, and adding a fourth would put a file in the tree that the card does not name. The
result writer is the natural home: the comment's body is a rendering of the result it has just
written, and binding the two in one module is what makes it impossible to publish a comment naming a
revision other than the one the result records.

## High-Level Technical Design

Three scripts, each with one job, and a skill that orchestrates them.

```
run record (issue-<N>.json)
  run_configuration.applicable_lenses
            |
            v
  review_roster.py  --- builds applicability_declaration.v1
            |         --- invokes <sdlc>/tools/docs/gen_review_roster.py
            v
  review_roster.v1 + review_roster_validation.v1   (hash, thresholds, per-lens staffing)
            |
            v
  one Lens Reviewer per selected lens   (roster session, or subagent)
            |         --- prompt: plugins/agent-launcher/roles/lens-reviewer.md
            v
  per-lens results + findings (shared finding schema)
            |
            v
  review_consensus.py  --- computes the verdict from the catalogue ladder
            |
            v
  review_result.py  --- writes review_result.v2 into run record review_cycles
            |         --- dedupes by fingerprint, refuses a second history per unit
            v
  one pull-request comment, bound to the reviewed revision
```

The boundary that matters: everything above `review_consensus.py` is *policy the plugin consumes*,
and everything at or below it is *execution the plugin owns*. That is ADR-001's line, drawn through
the code rather than described in prose.

## Implementation Units

**Landing order.** The unit identifiers are stable and are not the order of work. U6 settles the
eleven existing review test files and must land **before** U2's deletions, or the suite reds on
functions that are gone on purpose. Otherwise the order is U1, U6, U2, U3, U4, U5, U7, with U3 after
U2 because the result writer consumes the verdict, and U4 after U3 because publication renders the
result it has just written.

### U1. Resolve the roster by invoking the lifecycle repository's generator

Builds `applicability_declaration.v1` from the run record and hands it to the generator, with a named
refusal when the lifecycle checkout is absent.

**Files:** `plugins/saga/scripts/review_roster.py` (new).

**Covers:** R1, R2, R3, R4, KTD1, KTD2, KTD3, KTD8.

**Interface:** `uv run python plugins/saga/scripts/review_roster.py --declaration <decl.json>` prints
the generator's document. `--issue <N>` builds the declaration from the run record first and prints
both the declaration and the roster. `--sdlc-path` overrides the resolution for a test.

**Behaviour:** exit 0 when the validation report is `ok`, exit 1 when it is `refused` (mirroring the
generator, whose refusal is a run-setup fact the caller must see), exit 2 on a named refusal of this
script's own — no checkout, no generator at the resolved checkout, or a run record with no
`applicable_lenses`.

**One thing to get right:** the card's Verification block reads
`jq -r '.schema, .content_hash'`. The generator emits neither at the top level. Its output is
`{"roster": {...}, "validation": {...}}`, the roster's schema field is `schema` and its hash field is
`hash`, not `content_hash`. The acceptance criterion is satisfied against the real field names, and
the card's example is corrected in the same change rather than a wrapper being invented to match a
typo.

**Test scenarios** (`tests/test_review_roster.py`, new):

- A declaration built from a fixture run record round-trips: the generator's roster hash for that
  declaration equals the hash `review_roster.py` reports, byte for byte, with the generator invoked
  directly as the oracle.
- The four always-on lenses are present in the selection whatever the declaration says, and a
  declaration that sets an always-on lens to `applies: false` produces the generator's own
  applicability failure rather than a silently smaller roster.
- A conditional lens left out with no reason produces the generator's applicability failure.
- `sdlc_root()` returning `None` (via `INFIQUETRA_SDLC_PATH` pointed at a non-directory) exits 2 with
  one line naming the environment variable and the path tried, and no traceback.
- With `INFIQUETRA_SDLC_PATH` unset and `INFIQUETRA_SDLC_ROOT` set to a real checkout, the resolution
  succeeds and the refusal-or-success line names which of the two variables was read (KTD9).
- With both set to different directories, `INFIQUETRA_SDLC_PATH` wins and the other is named in the
  recorded provenance, so a divergence is visible rather than silent.
- A resolved checkout with no `tools/docs/gen_review_roster.py` exits 2, naming the missing file.
- The recorded provenance carries the checkout's `HEAD` and its clean-or-dirty state for `config/`
  and `tools/docs/`.

### U2. Compute the verdict from the catalogue, and give the script a command line

Rewrites the scorer around the lifecycle repository's ladder and acceptance rule, and removes the
private-roster path and the review-side external advisory seat.

**Files:** `plugins/saga/scripts/review_consensus.py` (rewritten), `plugins/saga/references/lens-roster.json`
(deleted).

**Covers:** R6, R7, R13, KTD5, KTD7. Closes child 885 and child 937's threshold half.

**Interface:** `uv run python plugins/saga/scripts/review_consensus.py --result <result.json>` prints
exactly one of `accepted`, `repairs_requested`, `cycle_cap_best_available`, `review_incomplete` and
nothing else. There is no command line today — `review_consensus.py` has no `argparse` import and no
`main` — so this is new surface, not a changed one.

**What goes, by name, and which card names it:** `ROSTER_PATH` (line 94), `always_on_lenses` (2008),
`_conditional_lens_ids` (2030), `_require_roster_conditionals` (2047), `recommend_conditional_lenses`
(2066), `_validate_conditionals` (2099), `_approved_from_choice` (2113), `_launch_set` (2125),
`_question` (2130), `_paused_decision` (2145), `_approved_decision` (2167), `resolve_lens_selection`
(2188), `launch_approved_lenses` (2327), `load_scoring_policy` (2383), and the classes
`ConditionalLensRecommendation` (300), `LensApprovalRecord` (319), `LensSelectionQuestion` (374),
`LensSelectionDecision` (391) — all of them the private-roster and conditional-approval machinery that
issue 1001 replaces by name ("Saga's private fourteen-lens roster … removed"). Plus
`ExternalFindingAdjudication` (578) and `ExternalAdvisoryReview` (613), the review-side external
advisory seat, which issue 1001 also names ("the external-engine second opinion … removed") and which
lives inside a file issue 1001 declares it rewrites. Nothing else is deleted.

**What replaces `load_scoring_policy`.** The old function read thresholds out of the deleted roster
file. Its replacement reads them out of the roster the run already resolved — U1's
`review_roster.v1` carries each selected lens's `threshold` object with its `strictness`,
`derived_overall_minimum` and `applicable_dimension_minimum` already resolved by the generator. The
scorer therefore loads nothing from disk and computes no threshold of its own; it reads the frozen
roster it is handed. That is the executor boundary expressed as a function signature.

**Test scenarios** (`tests/test_review_consensus.py`, rewritten):

- Every selected lens meets its pair (derived overall at least 9.0, every applicable dimension at
  least 7 at `standard`) → `accepted`, including when residual findings remain that leave every
  dimension at or above its floor.
- One lens's derived overall at 8.9 with every dimension at 8 → `repairs_requested`. The derived
  overall alone can fail a lens.
- Every dimension at 9 except one at 6 → `repairs_requested`. The dimension floor alone can fail a
  lens, which is the case a good average would otherwise hide.
- A lens with a missing result, a could-not-execute result, or a result from an executor with no
  ledger entry → `review_incomplete`, and it is decided *before* any low score in the same cycle.
- `-k cap`: the standard and escalated allowances exhausted → `cycle_cap_best_available`, and the
  result lists the residual issue numbers. Child 885's named test.
- A sixth cycle is refused: there is no fourth standard cycle and no third escalated one.
- A result citing a roster hash other than the run's frozen one is refused.
- `test ! -f plugins/saga/references/lens-roster.json`, and no module under `plugins/saga/` imports or
  reads that path.

### U3. Write `review_result.v2`, dedupe by fingerprint, and keep one history per unit

The result writer and the finding ledger.

**Files:** `plugins/saga/scripts/review_result.py` (new).

**Covers:** R8, R9, R10, R12. Closes children 939 and 946, and child 885's residual-filing half.

**Behaviour:** writes one entry per cycle into the run record's `review_cycles` array, carrying every
field the catalogue's `result_provenance_fields` requires — roster hash, catalogue version and hash,
profile path, version and hash, the lens and its strictness level, the reviewed revision, the cycle
number, the executor's vendor, model, effort and prompt hash, the verification reference, the hosting
topology, the checks executed with their resolved versions, and the per-dimension scores with their
applicability. A finding's identity is the catalogue's fingerprint of path, line and category. The
status vocabulary is the catalogue's eight values and no others.

**Test scenarios** (`tests/test_review_result.py`, new):

- Two lenses reporting the same path, line and category produce one finding with the agreement
  recorded, and the second is `duplicate-of` the first — not deleted, not counted twice. Child 939's
  named test.
- Similar wording at different locations stays two findings, because similar wording is not evidence
  of the same defect.
- `-k history`: a second review history for a unit that already has one is refused with a named error,
  and the refusal names the existing history's cycle count. Child 946's named test.
- Scores are only compared within the declared lens set: a result whose lens set differs from the
  frozen roster's is refused rather than compared.
- Repair accounting sits beside the score and never inside it: a cycle with three verified fixes and a
  below-floor dimension is still `repairs_requested`.
- A repair whose evidence is insufficient is `unresolved`, never `fixed-verified`.
- At the cap, one linked residual issue is prepared per unresolved finding and the numbers appear in
  the result.

### U4. Publish exactly one comment, bound to the reviewed revision

**Files:** the publication section of `plugins/saga/skills/code-review/SKILL.md`, and the publishing
helper in `plugins/saga/scripts/review_result.py`.

**Covers:** R11, R14. Closes children 935 and 937's carry-over half.

**Behaviour:** one `gh pr comment` naming the reviewed revision as a full forty-character commit
identifier. No `gh pr review`, in any of its forms. Nothing is committed, nothing is pushed, and the
branch does not advance — which is what card 935 reports as broken today, where publishing the review
artifact moved `HEAD` and invalidated the caller's freshness check. The evidence lands in the run
record, not in `docs/code-reviews/` and not through `evidence_ledger.py`.

**Test scenarios** (`tests/test_review_publish.py`, new):

- Publication issues exactly one comment and zero reviews; the recorded `gh` argument vectors are
  asserted, and any argument vector containing `pr review` fails the test. Child 935's named test.
- The comment text contains the full forty-character reviewed commit; an abbreviated identifier or a
  symbolic reference such as `HEAD` fails.
- Publishing twice for the same cycle and revision is refused, not duplicated.
- The reviewed revision in the result and the revision in the comment are the same value, read from
  one source.
- Publication makes no commit and no push: the repository's `HEAD` before and after are identical.

**Test scenarios** (`tests/test_review_seats.py`, new — child 937's named test):

- Every lens seat's vendor, model and effort come from the staffing plan and are named explicitly in
  the dispatch; an omitted model or effort is refused rather than inherited from the host.
- A result names its reviewed revision and the staffing source that produced its seats.
- A new commit gets a fresh review bound to it: the prior cycle's outcome is not carried onto the new
  revision, and no per-commit reconfirmation is asked of the operator.

### U5. Rewrite the skill and its references around the roster and the verdict

**Files:** `plugins/saga/skills/code-review/SKILL.md` (598 lines),
`references/lens-catalog.md` (132), `references/findings-schema.md` (255),
`references/validator.md` (75), `references/built-vs-planned.md` (95).

**Covers:** R5, R13's prose half, KTD6, and child 939's citation and naming-collision half.

**What changes:** the conditional-lens approval gate goes, because lenses now come from the
declaration fixed at admission; the four references to `plugins/saga/references/lens-roster.json`
(SKILL.md lines 56, 223, 235, 582, and lens-catalog.md lines 4, 13, 118) are repointed at the roster
the run resolved; the "External whole-diff advisory seat" section goes; `review_result.v1` becomes
`review_result.v2` throughout; and the hosting choice of KTD6 is written down as one decision with
one record.

**The naming collision child 939 reports:** `plugins/saga/skills/code-review/references/lens-catalog.md`
and the lifecycle repository's `config/lens-catalogue.json` are two different documents one letter
apart, and the plugin's is a prose guide to a policy file it no longer owns. It is renamed to
`references/lens-execution.md` and rewritten as guidance on *executing* a resolved roster, so the word
"catalogue" belongs to exactly one document in the system.

**The top-finding sentence child 939 asks for**, stated once and in the catalogue's own terms: a
finding never gates on its own. A P1 finding shows up as a dimension score below the floor, and it is
the score that decides; a residual finding that leaves every dimension at or above its floor is
recorded and carried forward and does not fail the lens.

**Test expectation:** the documentation assertions live with U7's conformance checks — no live
reference to the deleted file, no live reference to `review_result.v1`, and every cited lifecycle
document resolving at the recorded revision.

### U6. Settle the eleven existing review test files

Every test file that exercises the machinery U2 and U5 remove has a decided fate before any deletion
lands, so the suite never reds on a function that is gone on purpose.

**Covers:** the completeness half of R13, and the precondition for U2's deletions.

**The inventory, read from `tests/` today** — eleven files carry review machinery, and the card names
only one of them:

| File | What it exercises | Fate |
|---|---|---|
| `tests/test_review_consensus.py` | the scorer | Rewritten to the catalogue ladder; the card names it |
| `tests/test_lens_selection.py` | `resolve_lens_selection`, `launch_approved_lenses`, the conditional-approval record | Deleted with the machinery it tests — every symbol it imports is in U2's removal list |
| `tests/test_review_consensus_cycles.py` | cycle state and the three-cycle limit | Rewritten: the allowance becomes three plus two, per loop, per KTD11 |
| `tests/test_review_consensus_docs.py` | the module's docstrings and worked example | Rewritten against the new public surface |
| `tests/test_review_publication_lane.py` | the publication lane and its consent machinery | Rewritten to U4's one-comment contract; see the naming note below |
| `tests/test_review_second_opinion.py` | the review-side external advisory seat | Deleted with the seat, which issue 1001 names |
| `tests/test_review_loop_end_to_end.py` | the whole loop | Rewritten around the roster and the verdict |
| `tests/test_work_review_contract.py` | Work's contract with the review | Updated where it names `review_result.v1`; Work's own behaviour is not this card's |
| `tests/test_orchestrate_review_loop.py` | Orchestrate's review loop | Updated where it names removed symbols |
| `tests/test_orchestrate_review_transport.py` | reviewer-session transport | Updated where it names removed symbols |
| `tests/test_orchestrate_scoped_review_controllers.py` | scoped review controllers | Updated where it names removed symbols |

`tests/test_adjustment_envelope.py` also imports `review_consensus` at line 41; it is checked and
updated only if it names a removed symbol.

**The naming note.** Child 935 names its test `tests/test_review_publish.py`, and
`tests/test_review_publication_lane.py` already exists for the same subject. Two files one word apart
testing one lane is the same kind of collision child 939 reports between `lens-catalog.md` and the
lifecycle repository's `lens-catalogue.json`. The existing file is rewritten and **renamed** to
`tests/test_review_publish.py`, which satisfies child 935's criterion literally and leaves one file
for one subject.

**Test expectation:** none of its own — this unit's proof is that U2's and U5's suites pass, and that
`uv run pytest tests/ -q -k review` collects no test importing a removed symbol.

### U7. Release surfaces, a full dry run, and the deferred fifth criterion

**Files:** `plugins/saga/.claude-plugin/plugin.json`, `.claude-plugin/marketplace.json`,
`plugins/saga/CHANGELOG.md`, and `plugins/saga/references/run-record.md` where the `review_cycles`
row now names `review_result.v2`.

**Covers:** R15, and the acceptance evidence for the whole card.

**The dry run that stands in for a real review.** Issue 1001's fifth acceptance criterion — "one real
review on a pull request produced one comment, no approving review, and a `review_result.v2` in the
run record" — cannot be proved by this card. Children of parent 1018 open no pull request of their
own; the single pull request for the whole parent is issue 1030's, `parent/1018` onto `main`. The
criterion is therefore **deferred to that pull request**, and this unit records the deferral in the
changelog entry so the next reader does not mistake it for an untested claim.

What this unit proves instead is a full dry run of the review against this branch's own diff, with
the roster sessions replaced by an injected fake executor: the declaration is built from the real run
record, the roster is resolved by the real generator against the real lifecycle checkout, the fake
executor returns fixed per-lens results, the verdict is computed, a `review_result.v2` is written into
a temporary run record, and the publication step is exercised with the `gh` invocation captured rather
than executed. The four scripted criteria in the card — the roster hash, the four verdict words, the
absent `lens-roster.json`, and the three test files passing — are proved outright.

**Test scenarios** (`tests/test_review_dry_run.py`, new):

- The end-to-end dry run above completes and produces a `review_result.v2` whose roster hash equals
  the one the generator printed for the same declaration.
- The captured `gh` argument vector is exactly one `pr comment` and no `pr review`.
- Against today's empty verification ledger the dry run's verdict is `review_incomplete`, with the
  generator's refusal recorded verbatim as the reason — the honest answer under KTD4, asserted so a
  future ledger entry changing it is a visible test change rather than a silent one.

## Operator gates in the rewritten review

The rewritten review has exactly one operator gate, down from three. The conditional-lens approval
gate goes (lenses are fixed at admission) and the publication-consent machinery collapses to one
confirmation.

<!-- gate-record: id=code-review-required-lens-unexecutable absence=HALT transport=ask-user-question -->
**The one gate.** When a *required* lens cannot execute after its whole recovery budget is spent — two
backoff retries on the same verified executor, then one substitution — the Architect decides only
whether that lens applies to this work at all. If it is required, the question stops being technical
and goes to the operator through `AskUserQuestion`, whose choice is between providing another verified
executor and waiting for the current one. On silence: HALT. A timeout, a widget error or a dropped
session is never consent. Dropping or weakening a required lens is forbidden to every role, and no
path through this plan lets a run score a required lens with something that does not meet its floor.

## Scope Boundaries

**Out of scope, and staying out.**

- No change to the lifecycle repository's catalogue, thresholds, or the four always-on lenses. This
  repository consumes them.
- No scoring by the typed-judgment model. Its three jobs here — proposing conditional lenses at
  admission, deduplicating findings across lenses, and flagging a finding whose severity looks out of
  line with its text — are issue 1034 and advisory.
- No approving pull-request review, ever, by any path.
- No local executor qualification. Writing an entry into the lifecycle repository's verification
  ledger from this repository would make the plugin a policy owner again.
- No second pin. The roster hash is the sole pinning point.

**Deferred to follow-up work.**

- **The fifth acceptance criterion**, proved at issue 1030's pull request as described in U7.
- **Issue 938**, the removal of Work's in-process external-engine second-opinion offer and its
  feature-private dispatch, sidecar, streak and state machinery — `plugins/saga/scripts/second_opinion.py`
  and `plugins/saga/skills/work/SKILL.md`. See the child-card map.
- **The `team-execution` plugin's references to the deleted roster.** Ten references across eight
  files (`README.md`, `SKILL.md`, three reviewer agent definitions, and three reference documents)
  read `plugins/saga/references/lens-roster.json`. Issue 1001's file list does not name any
  team-execution file, and this plan deletes nothing the card does not name. Parent 1018 archives that
  plugin, so the references die with it; if archiving lands after this card, a follow-up repoints them
  at the resolved roster. This is flagged to the parent rather than fixed here.
- **`admission.py`'s catalogue shape mismatch**, described under "Admission answers". Issue 1023 owns
  that file.
- **Repointing the sixteen role prompts from `INFIQUETRA_SDLC_ROOT` to `INFIQUETRA_SDLC_PATH`**, per
  KTD9. Every file under `plugins/agent-launcher/roles/` belongs to issue 1022, which issue 1001 does
  not name. U1 reads both variables so the mismatch cannot produce a silent empty resolution, and the
  one-name repair is filed against the parent.

## Child-card map

Six cards are children of issue 1001. Five close when this card's merge lands; one needs its own
follow-up.

| Child | What it asks for | Which unit satisfies it | Closes with this merge? |
|---|---|---|---|
| 885 | At the cycle cap, file residuals and proceed; no fourth cycle | U2 (the `cycle_cap_best_available` verdict) and U3 (filing the residuals) | Yes — its named test `tests/test_review_consensus.py -k cap` is in U2 |
| 935 | One pull-request comment bound to the reviewed revision, evidence in the run record | U4 | Yes — its named test `tests/test_review_publish.py` is in U4 |
| 937 | Tiers from admission, lenses from the declaration, no silent carry-over | U1 (lenses from the declaration), U2 (thresholds from the catalogue), U4 (seats and revision binding) | Yes — its named test `tests/test_review_seats.py` is in U4 |
| 939 | Citations, the naming collision, the top-finding sentence, dedupe by fingerprint | U3 (dedupe) and U5 (citations, the rename, the sentence) | Yes — its named test `tests/test_review_result.py` is in U3 |
| 946 | One review history per unit, lens set frozen, comparable scores | U3 | Yes — its named test `tests/test_review_result.py -k history` is in U3 |
| 938 | Remove Work's legacy in-process external-engine second-opinion offer and its machinery | Partly U2, for the review-side seat only | **No** — needs its own follow-up |

**Why 938 does not close here.** Three reasons, each checkable. Its files are
`plugins/saga/scripts/second_opinion.py` (2,076 lines) and `plugins/saga/skills/work/SKILL.md`, and
neither appears in issue 1001's "Files expected to change" — deleting them under this card would
break the rule that nothing goes unless the card names it. It edits Work's file while other children
of parent 1018 also edit it, so it carries an ordering obligation this card has no way to discharge.
And its acceptance criteria include two things no test in issue 1001's list covers: proving that the
external-content trust boundary survives with all three of its consumers passing (the review panel,
the Orchestrate seats, and the team-execution validator), and notifying the Document Review parent
that its deferred second-opinion prose is now unblocked.

What this card *does* discharge of 938's intent is the review side: the "External whole-diff advisory
seat" section of the code-review skill and the two classes behind it, both inside files issue 1001
declares it rewrites. One fact worth recording for 938's own planner: the external-content trust
boundary is not a shared code module. It is a documented contract,
`plugins/saga/references/engine-output-trust-boundary.md`, enforced by a lint-style test
(`tests/test_engine_output_trust_boundary.py`) that scans two call sites — `engine_dispatch.py` and
`second_opinion.py`. Removing `second_opinion.py` removes one scanned call site; the document,
`engine_dispatch.py`, and the team-execution validator references all survive untouched.

## Risk Analysis and Mitigation

| Risk | How it shows up | Mitigation |
|---|---|---|
| The gate silently weakens | The rewritten review accepts what the old one would have rejected | The verdict is a total function of three facts with a test per row of the lifecycle repository's own table, including the two failure shapes a good average hides |
| The empty ledger reads as a broken review | Every review today returns `review_incomplete` and a reader concludes the code is broken | KTD4 makes it the designed path, U7 asserts it, and the result records the generator's refusal verbatim so the reason is on the page |
| The two rosters drift | The generator's `--check` mode compares the catalogue against the plugin's roster; after U2 the plugin's roster does not exist | ADR-001's transition rule says the check moves to `--strict` when the plugin consumes a generated roster; this card notifies the lifecycle repository that the trigger has fired rather than flipping their flag |
| The lifecycle checkout is dirty or ahead | Two runs resolve different policy from the same instruction | KTD8 records the checkout's `HEAD` and clean state beside the roster hash |
| Deleting the roster breaks a neighbour | `team-execution` reads it in ten places | Named as deferred follow-up above and flagged to parent 1018; nothing is deleted that this card does not name |
| The card's own verification line is wrong | `jq -r '.schema, .content_hash'` prints two nulls and looks like a failure | U1 names the real field path and corrects the card's example in the same change |

## Alternatives Considered

**Vendor the generator into the plugin.** Rejected on measurement: the generator imports only the
standard library and resolves its inputs from its own location, so a subprocess call works today and a
vendored copy would add a second thing to keep in step for no benefit. This is also the card's stated
stop condition, and it is the reason the stop condition does not fire.

**Keep `lens-roster.json` as a fallback when the lifecycle checkout is absent.** Rejected. A fallback
policy is a policy, and ADR-001's whole point is that the plugin owns none. A named refusal tells the
operator what to fix; a fallback hides it and produces a verdict against a rule nobody chose.

**Let the review write its own executor-verification entries so scores work today.** Rejected for the
same reason, more sharply: the ledger is the gate between a model producing a number and that number
being allowed to establish a threshold. Self-qualification removes the gate.

**Score anyway and mark the scores provisional.** Rejected. The catalogue lists "a result from an
executor with no matching entry" among the four things never accepted at any level. A provisional
score is a score that would be read as one.

## Success Metrics

- `uv run python plugins/saga/scripts/review_roster.py --declaration <decl.json>` prints a
  `review_roster.v1` whose hash equals the generator's for the same declaration.
- `uv run python plugins/saga/scripts/review_consensus.py --result <result.json>` prints one of the
  four outcome words and nothing else.
- `test ! -f plugins/saga/references/lens-roster.json`.
- `uv run pytest tests/test_review_roster.py tests/test_review_consensus.py tests/test_review_result.py
  tests/test_review_publish.py tests/test_review_seats.py tests/test_review_dry_run.py -q` passes.
- The full gate is green at the unit's head commit, run in the background per this repository's
  `CLAUDE.md`.
- Deferred to issue 1030's pull request: one real review produced one comment, no approving review,
  and a `review_result.v2` in the run record.
