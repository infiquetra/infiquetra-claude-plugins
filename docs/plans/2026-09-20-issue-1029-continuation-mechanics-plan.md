---
title: Continuation mechanics — skills continue, the record's next step is injected, the prompt suggestion names the command
type: refactor
status: active
date: 2026-09-20
origin: docs/analysis/2026-09-19-improve-claude-plugins-objective-plan.md
backend: inline
---

# Continuation mechanics — skills continue, the record's next step is injected, the prompt suggestion names the command

## Summary

Three small changes to the saga plugin, all of them about what happens at the seam between one
lifecycle step and the next. First, the five lifecycle skills (`/plan`, `/doc-review`, `/work`,
`/code-review`, `/qa`) stop ending with a recommendation and end by doing the next step in the same
turn. Second, a new session-start hook prints the run record's `next_step` when a run is live, and
prints nothing at all when the run's step is done, when the run is closed, or when there is no
record — the suppression that keeps a finished step from being re-announced in a new session.
Third, a new prompt-submission hook names the saga command that matches what the operator just
typed, using local string matching only and making no network call of any kind.

Nothing is removed here. `/loop`, `/resume`, `/handoff` and the handoff and intent envelope
machinery are issue 1030's to remove.

## Problem Frame

Continuation in this plugin is a suggestion, and a suggestion is a step that does not happen on a
busy day.

**The chain is operator-invoked almost everywhere.** `/plan` now runs its own plan review (issue
1026 shipped that), but its last section still *recommends* `/work` rather than running it
(`plugins/saga/skills/plan/SKILL.md:714-722`, and the literal phrase "recommended next" at line
718). `/code-review` ends with a four-way routing list (`code-review/SKILL.md:356-362`), `/qa` ends
by naming `/handoff` or `/retro` (`qa/SKILL.md:340-389`), `/doc-review` ends with an output-shape
description and no continuation at all (`doc-review/SKILL.md:281-297`), and `/work` ends by
"presenting continuation routing" and pausing (`work/SKILL.md:799-836`). The only genuine chaining
today is `/work` calling `/code-review` programmatically (`work/SKILL.md:737-751`) and `/loop`'s
Drive mode, which has to be chosen and which issue 1030 deletes.

**A stale next step can leak into a new session, and it did.** The session that produced this card
opened with a `next_step` left over from an old saga tick. Issue 1023 fixed the authority question
— the run record wins over the envelope log (`plugins/saga/scripts/saga.py:1043-1072`) — and taught
the compaction spore to freeze and re-inject the record (`saga_spore.py:253-289`). What it did not
add is the rule that a finished step should not be announced at all, and there is no session-start
hook that reads the record: `hooks.json` registers the spore reader only for the `compact` source
(`plugins/saga/hooks/hooks.json:14-22`), so a fresh session at `startup` or `resume` gets nothing
from the record and whatever the old envelope happens to say from elsewhere.

**Nothing names the command from what the operator typed.** There is no `UserPromptSubmit` entry in
`hooks.json` at all today.

## Requirements

**R1.** Each of the five lifecycle skills ends by performing the next step in the same turn, not by
recommending it. The phrase "recommended next" appears nowhere under `plugins/saga/skills/`.

**R2.** Continuation never converts an action that is confirmed today into one that happens
silently. `/work`'s pull-request open, review request, and merge stay explicitly confirmed.

**R3.** A session-start hook reads the run record and injects the run's `next_step` when the run is
live — "live" meaning exactly what KTD1 defines: a record exists and its `next_step` is not the
empty string.

**R4.** The same hook injects nothing when the record says the step is done, when the run is
closed, and when no record exists. Under KTD1 the first two are the same observable condition —
an empty `next_step` — and the plan uses no other definition of either. It also injects nothing
outside a git repository and on any error.

**R5.** `next_step` gains no second home. It stays a field of the run record, and the record gains
no new top-level key.

**R6.** A `UserPromptSubmit` hook may name a saga command that matches the operator's text. It
matches locally, makes no network call, sends nothing off the machine, writes no log of the prompt,
and never blocks or rewrites the prompt.

**R7.** The new registrations in `hooks.json` coexist with every entry already there, including
whatever issue 1038's family adds later.

**R8.** No hook on the chain can block, refuse, or fail a turn. Every one of them exits 0.

**R9.** Tests use temporary stores and temporary records under `tmp_path`. No test writes into the
primary checkout's saga store.

**R10.** The release surfaces move in the same pull request: `plugins/saga/.claude-plugin/plugin.json`,
`.claude-plugin/marketplace.json`, `plugins/saga/CHANGELOG.md`, and the drift guards that read them.

## Key Technical Decisions

**KTD1 — "the step is done" is an empty `next_step`, and nothing else.** The record says a step is
finished by its `next_step` being the empty string; the writer that finishes a step clears it or
replaces it with the following step. The hook suppresses on the empty string and on the absence of
a record, and it infers nothing.

*Rationale.* The record's twelve top-level keys are frozen on purpose —
`plugins/saga/scripts/run_record.py:60-76` says so in as many words ("Fixed here so no later child
of issue 1018 invents one") — so a `closed_at` or `run_state` key is not available to this card.
*Rejected:* inferring doneness from `review_cycles` or `units` (inference over recorded state is
exactly what produced the stale injection this card exists to fix); a new top-level key (frozen);
a sentinel string such as `done` (a sentinel inside a free-text field is a second schema nobody
declared).

**KTD2 — the hook resolves the issue locally, in two steps, and gives up quietly.** It asks
`saga_spore.resolve_active_saga()` for the active saga and takes its `issue-<N>` id; failing that,
it reads the current branch and takes `<N>` from an `issue/<N>` branch name. If neither answers, it
injects nothing.

*Rationale.* Both are local reads already used elsewhere in this plugin, and a session start must
not spend a network call. *Rejected:* asking GitHub whether the issue is closed (a network call on
every session start, and the 1038 measurements put one round trip at roughly 350 milliseconds);
scanning the whole run store for the most recently updated record (that is how a different
worktree's run gets announced in this one).

*The two stores sit differently, and the fallback is not decoration.* The saga envelope store is
per-worktree — the tick written for this card landed under the worktree's own `.claude/saga/` —
while the run record store is resolved from the git **common** directory and is therefore the
primary checkout's for every worktree (`run_record.resolve_store_root`,
`plugins/saga/scripts/run_record.py:175-200`). So in a fresh worktree the first resolution step
usually finds no active saga and the branch name carries the whole answer. The fallback is the
ordinary path in a worktree, not the exceptional one, and its tests are written on that
understanding.

**KTD2a — the resolver is a module of its own, not a function on the record.** It lands in a new
`plugins/saga/scripts/next_step_context.py` rather than in `run_record.py`.

*Rationale.* `saga_spore` imports `saga` (`saga_spore.py:40-42`) and `saga` imports `run_record`
lazily (`saga.py:1066`), so a resolver that lives in `run_record.py` and reaches for
`saga_spore.resolve_active_saga` closes an import cycle: `run_record` → `saga_spore` → `saga` →
`run_record`. The lazy import would keep it from crashing at runtime, which is worse than a crash,
because the layering violation would survive unnoticed. The record module stays a leaf that knows
about storage and nothing about sessions.

**KTD3 — the suggestion hook matches locally and conservatively, and the typed judgment is not
added.** It matches the operator's text against two things only: the saga command names and their
documented aliases, and the step name in the run record's `next_step`. One match suggests; no match
and an ambiguous match are both silence. The command list is read from the hook's own plugin
directory — `${CLAUDE_PLUGIN_ROOT}/commands/` — so the suggestion names commands the installed saga
actually has, and never a command this repository's working tree has but the installed plugin does
not.

*Rationale.* Issue 1038 measured the typed-judgment version at 93 percent on prompts that warrant a
command and 100 percent silence on prompts that do not, and still recommended **defer**, for two
separate reasons: no shape that makes a blocking call reaches the 400 millisecond target, and
whether the operator's live prompt text may be sent to TypeSafe is an open operator decision
(`docs/analysis/2026-09-19-prompt-suggestion-latency.md`, sections 6 and 7). This card therefore
ships the registration and a local matcher, and adds no call.

*Is the feature useful without the typed judgment?* Narrowly, yes, and it should be built narrowly.
A keyword table over a dozen commands will not approach 93 percent recall, and trying to make it do
so produces a noisy hook the operator learns to ignore. What a local matcher can do well is the
high-precision case: the operator names a command, or names the step the record already says is
next. That is worth a line of context, and it is honestly all this hook claims. If the operator
later rules that prompt text may go to TypeSafe, the typed judgment replaces the matcher behind the
same registration.

**KTD4 — `/plan` continues into `/work` only when the run record's `destination` says to.** A
`plan-only` destination stops after the plan review; `pr`, `merge` and `nonprod-deploy` continue.

*Rationale.* The destination is already recorded at admission and is already the field that decides
how far a run goes. Reading it is how continuation stays automatic without becoming unbounded.

**KTD5 — the compaction spore suppresses the same way the session-start hook does.** The run-record
block in `saga_spore.serialize()` (`saga_spore.py:412-424`) prints nothing when the frozen
`next_step` is empty, rather than printing `next_step: ` with nothing after it.

*Rationale.* Two readers of the same field disagreeing about what "done" looks like is how the next
stale-state bug gets written. One rule, two call sites.

**KTD6 — `/qa`'s pass continues into `/retro`, not `/handoff`.** `/handoff` is removed by issue
1030. `/qa` keeps naming the issue-filing route as an option the operator may take, and continues
automatically into the step that will still exist.

## Implementation Units

### U1. The shared next-step read and its suppression rule

**What:** a new module `plugins/saga/scripts/next_step_context.py` holding one function that
answers "what, if anything, should be announced for this repository right now" — resolve the issue
(KTD2), load the record from the primary checkout's store, and return the `next_step` or nothing.
Both hooks and the spore call the same rule. It is a module of its own rather than a function on
`run_record` for the import-cycle reason in KTD2a.

**Why first:** U2, U3 and the spore edit all depend on it, and it is the only place the suppression
rule is written.

**Test scenarios** (`tests/test_next_step_context.py`, new): a live record with a non-empty
`next_step` returns it; a record with an empty `next_step` returns nothing; no record at all
returns nothing; an unreadable or malformed record returns nothing rather than raising; the branch
fallback resolves `issue/1029` to issue 1029 and ignores a branch that is not issue-shaped; and
importing the module leaves `run_record` free of any import of `saga_spore` (the guard that keeps
KTD2a true). Every case uses a `tmp_path` store (R9).

### U2. The session-start hook

**What:** `plugins/saga/hooks/next_step_session_hook.py`, registered on `SessionStart` for
`startup|resume`, printing the standard `hookSpecificOutput` / `additionalContext` shape with the
run's next step and the record's `updated_at`, and printing nothing in every suppressed case. It
follows the existing hooks' contract exactly: read stdin, degrade silently, exit 0 always
(`stale_main_session_hook.py` is the model).

**Also:** the matching suppression in `saga_spore.serialize()` (KTD5).

**Test scenarios** (`tests/test_next_step_session_hook.py`, new): active run prints the step; empty
`next_step` prints nothing; no record prints nothing; a cwd that is not a git repository prints
nothing; malformed stdin prints nothing; every case exits 0. Plus one case in
`tests/test_saga_spore.py` that a frozen record with an empty `next_step` renders no run-record
block, and one in `tests/test_spore_hooks_registration.py` that the new `SessionStart` entry is
registered for `startup|resume` beside the existing stale-default-branch and reclaim entries rather
than replacing any of them (R7).

### U3. The prompt-submission suggestion hook

**What:** `plugins/saga/hooks/prompt_suggestion_hook.py`, registered on `UserPromptSubmit`,
implementing KTD3's local matcher. It emits at most one advisory line, never a block or a rewrite,
and exits 0 on every path.

**Test scenarios** (`tests/test_prompt_suggestion_hook.py`, new): a prompt naming a command
suggests it; a prompt naming the recorded next step suggests that command; an unrelated prompt is
silent; an ambiguous prompt is silent; the hook makes no outbound connection (the test replaces
`socket.socket` with one that fails the test if constructed); the hook writes no file; malformed
stdin is silent; every case exits 0. Plus one case in `tests/test_spore_hooks_registration.py` that
the `UserPromptSubmit` entry is registered and that every pre-existing event and entry in
`hooks.json` survives the addition (R7).

### U4. The five skill endings, and the two shaping skills' wording

**What:** rewrite each ending so it performs the next step.

| Skill | Section to change | Location | Becomes |
|---|---|---|---|
| `/plan` | §5.6 "Route" | `plan/SKILL.md:714-722` | continues into `/work` when the record's `destination` is not `plan-only` (KTD4) |
| `/doc-review` | "Output Shape" | `doc-review/SKILL.md:281-297` | returns its result to `/plan`'s loop when dispatched by it; continues into `/work` **only** when all three hold — the reviewed document classified as a **plan**, the review was invoked standalone rather than by `/plan`, and no `P0` or `P1` remains. A strategy, requirements, or issue document continues into nothing and reports, because `/work` has no plan to execute |
| `/work` | §5.4 "Reach PR-ready and present continuation routing" | `work/SKILL.md:799-836` | continues into `/qa` after a merge, with every confirmed action still confirmed (R2) |
| `/code-review` | §5.4 "Route" | `code-review/SKILL.md:356-362` | each verdict performs its own next step rather than naming it |
| `/qa` | §6.1 and §6.2 | `qa/SKILL.md:340-389` | a pass continues into `/retro` (KTD6); a failure re-enters the loop it already names |

Two shaping skills carry the literal phrase the acceptance criterion greps for —
`brainstorm/SKILL.md:473` and `office-hours/SKILL.md:201` — and they are not lifecycle skills, so
their routing behaviour is unchanged and only the phrasing moves.

**Conflict note.** Issue 938 also edits `plugins/saga/skills/work/SKILL.md`, removing the
external-engine second-opinion offer and `plugins/saga/scripts/second_opinion.py`. This card's edit
to that file is confined to the ending, §5.4 and the §5.5 wording around it; 938's is elsewhere in
the file. Whichever of the two lands second on `parent/1018` resolves the conflict.

**Test scenarios** (`tests/test_skill_continuation_endings.py`, new — a structural test over the
files): the case-insensitive phrase `recommended next` appears in no file under
`plugins/saga/skills/*/SKILL.md` (the same phrase and the same case-insensitivity as the card's
`grep -n -i "recommended next"`); each of the five lifecycle skills' final routing section names
the command it continues into. The guard is written to fail first against the unedited files and
watched failing before the edits land.

### U5. Release surfaces and the journal

**What:** bump `plugins/saga/.claude-plugin/plugin.json` and the saga row in
`.claude-plugin/marketplace.json`, add the `plugins/saga/CHANGELOG.md` entry, and move whatever the
drift guards (`tests/test_release_surface_parity.py`,
`tests/test_release_surface_diff_guard.py`) require. A `LEARNINGS.md` entry for the stale-step
mechanism and a `DECISIONS.md` entry for KTD1 and KTD3 ship in the same commit as the change.

**Version.** The base is saga 0.166.0. Issue 1025 is expected to land 0.167.0 before this card, so
this card takes **0.168.0** and re-checks the number at the merge turn: a sibling that takes the
same number silently is a known trap in this repository, and the fix is to re-bump at merge rather
than to trust the number chosen at planning time.

**Test expectation:** the existing drift guards, unchanged.

## Acceptance criteria, and what proves each one

The card states three criteria. Two are commands; the third is a live observation, and saying so is
part of the plan rather than something for an implementer to discover.

| The card's criterion | Unit | What proves it |
|---|---|---|
| `grep -n -i "recommended next" plugins/saga/skills/*/SKILL.md` prints nothing | U4 | the same grep, plus `tests/test_skill_continuation_endings.py`, which asserts the same phrase with the same case-insensitivity |
| `uv run pytest tests/test_spore_hooks.py -q` passes with the suppression case present | U1, U2 | **see the note below — that path does not exist** |
| Starting a new session in a repository with an active run prints the run's `next_step`, and none for a closed run | U2 | a live check, not a unit test: start a session in this checkout with issue 1029's record live, read the session-start context, then clear the record's `next_step` and start another |

**The card's second command names a file this repository does not have.** There is no
`tests/test_spore_hooks.py`. The spore's tests are `tests/test_compact_spore_session_hook.py`,
`tests/test_precompact_spore_hook.py` and `tests/test_spore_hooks_registration.py`, and an
implementer who runs the card's command verbatim gets a collection error, not a pass — or, worse,
creates an empty file of that name and reports green. **This plan resolves the criterion to**
`uv run pytest tests/test_next_step_session_hook.py tests/test_next_step_context.py tests/test_prompt_suggestion_hook.py tests/test_spore_hooks_registration.py -q`,
which is where the suppression cases actually land. No file named `test_spore_hooks.py` is created
to satisfy the literal text.

**The live check is a step, not an assumption.** U2 is not finished until the two session starts
above have been run and what they printed has been recorded. A unit test over the hook's stdout
proves the hook; it does not prove that Claude Code runs it at `startup` with the registration as
written, and those are different claims.

## Operator questions and gates

<!-- gate-record: id=continuation-preserves-confirmations absence=HALT transport=ask-user-question -->
<!-- gate-record: id=plan-continues-into-work absence=HALT transport=ask-user-question -->

**The one preservation contract.** Continuation must not turn a confirmed action into an automatic
one. `/work`'s pull-request open, review request, and merge each stay behind an explicit operator
confirmation, exactly as they are today. If an implementer finds a continuation that would fire one
of them without a confirmation, that is a stop: ask the operator through AskUserQuestion, and do
not proceed on an assumption.

**The one open question, declared rather than answered.** `/plan` continuing into `/work` in the
same turn for a `pr` destination is new behaviour for this repository, and KTD4 is this plan's
proposed answer rather than a recorded operator ruling. The run record for this card carries
`destination: pr`, which authorizes the run to reach a pull request; it does not by itself say that
one turn may cross from planning into building without a pause. This plan proceeds on KTD4 and
flags it here so the plan reviewer and the operator can overrule it in one word.

## Scope Boundaries

**Out of scope (true non-goals).**

- Any hook that blocks, refuses, or rewrites. Every hook here is advisory.
- Any call to TypeSafe, any network call, and any transmission of the operator's prompt text
  (KTD3).
- A second store for `next_step`, or a new top-level key on the run record (R5, KTD1).
- Removing `/loop`, `/resume`, `/handoff`, or the handoff and intent envelope machinery. Issue 1030
  owns every one of those.
- Changing who wins between the record and the envelope log. Issue 1023 settled that.
- Installing the bumped plugin into either of the two plugin trees under `~/.claude` and
  `~/.claude-company`. This card is one of several under parent issue 1018, and the install and the
  both-trees verification happen once for the parent, not once per card.

**Deferred to follow-up work.**

- The typed-judgment suggester behind the same registration, once the operator rules on whether
  live prompt text may leave the machine (issue 1038, sections 6 and 7).
- A resident local process for the suggestion hook. Issue 1038 measured it as worth 343
  milliseconds and still not enough for a blocking call; nothing here needs it, because nothing
  here blocks.

## Admission answers

<!-- gate-exempt: this section records answers already given; the gate itself is declared under "Operator questions and gates" -->

Recorded by `plugins/saga/scripts/admission.py` at
`/Users/jefcox/workspace/infiquetra/infiquetra-claude-plugins/.claude/saga/runs/issue-1029.json`.
The dry run filled twelve of the thirteen run-configuration parameters and asked eight questions;
the real run recorded all eight and reports thirteen of thirteen filled. AskUserQuestion was
unavailable in this session, so every answer below was taken from a written source and the source
is named.

| Question | Answer | Source |
|---|---|---|
| `risk_tier` | `low` — "hook text and skill endings; nothing here can block a turn" | The card's own Risk section, issue 1029 |
| `approval_scope` | `none` in all seven categories | The operator's standing list for this run: production, destructive actions, credentials, permissions, billing, external commitments, process authority, and plan-review or code-review overrides all stop and ask; nothing else does. Nothing in this card touches any of the seven |
| `destination` | `pr` | The run brief and the `plan_pre_answers.v1` carrier; the pull request is issue 1030's single parent pull request from `parent/1018` |
| `staffing_overrides` | `none` | The run brief; the profile defaults stand |
| `lens_declaration` | the four always-on lenses plus `documentation-clarity`, `agent-usability`, `api-contract`, `privacy` | `config/lens-catalogue.json` at infiquetra-sdlc revision `5efc869f` — see the reasons below |
| `repair_allowances` | 3 standard, 2 escalated | `docs/lifecycle/run-model.md` at `5efc869f`, the settled default |
| `unfinished_testing_response` | bring the result to the operator | The lifecycle names no default here; chosen and justified below |
| `change_shape` | `mixed` | The run brief; this card changes Python hooks and operator-facing instruction text together |

**Why those four conditional lenses, and why not the others.** `documentation-clarity` because five
skill files of operator-facing instructions change. `agent-usability` because the change alters
commands and hooks an agent must discover and operate, which is the catalogue's own condition for
it. `api-contract` because `hooks.json` and the hooks' stdin and stdout shapes are a
configuration and file-format contract that Claude Code consumes. `privacy` because the suggestion
hook reads the operator's live prompt text, and the whole design rests on the claim that none of it
leaves the machine — that claim deserves a reviewer. Not selected, with reasons:
`deployment-infrastructure` (no infrastructure, deployment configuration, migration or rollout
order changes), `reliability` (no failure handling, concurrency, retries or recovery changes; the
hooks fail open), `performance` (local matching, no network call, no latency surface),
`adversarial` (no money, mutation, external integration, policy or gate; the hooks cannot block),
`previous-comments` (no pull request exists for this card yet),
`accessibility-human-usability` (no visual or interactive surface; the operator-facing text is
covered by `documentation-clarity`), `experience` (no product surface).

**Why "bring the result to the operator" for unfinished functional testing.** The lifecycle's two
modes are a closed set and it names no default (`run-model.md` at `5efc869f`, line 163). This card
changes what happens automatically at the seams between steps, which is precisely the kind of
change where a test that cannot finish is evidence the automation is wrong rather than evidence the
code needs another repair round. Continuing to repair toward a prescribed test would mean grinding
against a design question. Bringing it to the operator is the cheaper error.

## Questions answered from the card

The installed `/plan` skill asks these from a known set. None of them is a production, destructive,
credential, permission, billing, external-commitment, or process-authority decision, so none was
escalated.

| Question the skill asks | Answer taken | Where it came from |
|---|---|---|
| Phase 0.2 — is this a handoff issue, and at what maturity? | Plain enhancement card, no `Handoff maturity` section; plan from the card and the objective plan | `gh issue view 1029` |
| Phase 0.3 — resume an existing saga or mint a new one? | Mint. `saga.py scan` returned zero candidates | the scan's own output |
| Phase 0.4 — is a plan document warranted? | Yes. Five units, six key technical decisions, an open operator question | the skill's own rubric |
| Phase 0.5 — scope depth? | Standard. Two hooks, five skill endings, one hook registration, tests, release surfaces | the run brief's complexity triage, "small-to-medium" |
| Phase 0.7 — the pre-answers carrier | Applied: `destination: pr`, `backend: inline`, from caller "improve-claude-plugins run driver" | `plan_pre_answers.py` exited 0 with `stop: null` |
| Phase 5.1 — destination | `pr` — already settled by the carrier, not re-asked | the carrier |
| Phase 5.2 — execution backend | `inline` — already settled by the carrier | the carrier |

## Risk Analysis and Mitigation

**A skill that continues into the wrong step is worse than one that recommends it.** Mitigation:
KTD4 reads the destination from the record rather than deciding in the skill, and R2 keeps every
confirmed action confirmed.

**A continued step can fail, and the turn has to end somewhere sensible.** A skill that continues
into the next step and finds that step failing reports the failure and stops; it does not retry the
chain, and it does not fall back to the step it just finished. The run record's `next_step` is left
naming the step that failed, so the next session's injection says exactly where the run stopped.

**A session-start hook that prints on every session start becomes noise.** Mitigation: the
suppression rule is the point of the card, and the structural tests cover all three silent cases
before the loud one.

**Two drivers edit `work/SKILL.md` in the same parent.** Mitigation: the ending-only edit stated in
U4, and the second lander resolves.
