---
name: work
description: Execute a settled Infiquetra plan to PR-ready, then own the round-N PR continuation loop. Restores and writes the work-thread saga (the primary writer), recommends an execution backend, runs risk-gated tests, calls /code-review programmatically and reads its typed outcome, blocks on repair, incomplete, or stale review state, and coordinates PR-open/review-request/merge under explicit confirmation — without owning deploy. Triggers on "build it", "work this plan", "execute the plan", "resume work on #N", or a plan-ready / resume-ready handoff issue.
---

# Work

`/work` answers **"Build it."** It takes a settled plan — from `/plan`, a `plan-ready` / `resume-ready`
handoff issue, or an approved ad-hoc request — and executes it phase by phase to PR-ready, then **owns
the round-N PR continuation loop** around the resulting PR. It does **not** invent product behavior
(that came from `/brainstorm` and the issue), it does **not** re-run the plan interrogation (`/plan`
settled the HOW), and it does **not** own deploy mutation (`deploy` does). It builds, tests,
gates, records, and coordinates — under explicit confirmation for every outward mutation.

`/work` is the saga's **primary writer**: it `restore`s on resume, mints/advances the work-thread saga
to `lifecycle_phase=work`, writes a tick per phase, and — crucially — **mints the *findable* work-thread
saga** (with `issue_ref` / `plan_path` / branch set) that a standalone `/code-review` appends `review_paths`
to (saga-spec §11). For its own pre-PR gate, `/work` calls `/code-review` programmatically and reads the
returned envelope **directly** — programmatic mode hands persistence to the caller, so `/work` owns the
gate, not a saga round-trip.

## Position in the lifecycle

`/work` is the loop's execution hub — every real build runs through it:

- `/plan` answers: "How should it be built?" (writes the plan + a `lifecycle_phase=plan` saga)
- plan review (`/doc-review`) answers: "Is this plan ready to execute?" — dispatched by `/plan`
  Phase 5.4, not by the operator. (`review` is a declared `lifecycle_phase` in `scripts/saga.py`
  that no code path writes; plan review is a step inside the plan phase, not a recorded phase.)
- **`/work` answers: "Build it." — and owns the PR loop to merge** (this engine)
- `/code-review` answers: "Is the built code safe to merge?" (`/work` calls it programmatically for the gate; appends `review_paths` when run standalone against `/work`'s saga)
- `/qa` answers: "Does the shipped thing actually work?" (`/work` routes here advisorily after merge)

`/work` consumes what `/plan` produced (the plan doc + the plan saga) and advances that same saga
through `work`. It calls `/code-review` before opening a PR. After merge it routes to `/qa`
advisorily and leaves `lifecycle_phase=work`, because the advance to `qa` is **`/qa`'s to make and
only on a PASS** — on a FAIL `/qa` keeps the phase at `work` and records the evidence. So the saga
legitimately sits at `work` from merge until `/qa` runs and passes (see Phase 5).

## Core principles

1. **Build, don't re-decide.** `/work` executes a settled plan. It does not invent product behavior,
   re-run the plan interrogation, or renegotiate scope. The plan's Implementation Units define the work;
   honor `Scope Boundaries` and refer back when execution drifts toward adjacent work.
2. **The saga is the spine.** `restore` on resume (rehydrate `round`/`phase`/`checks_run`/`next_step`);
   write a tick per phase boundary; round-N is deterministic. `/work` is the **primary writer** and mints
   the saga with the identity keys (`issue_ref` / `plan_path` / branch) a standalone `/code-review` needs
   to find and append `review_paths` to. Never set `next_round` — it is derived (saga-spec §6.1).
3. **Test as you go, gate hard on risk.** Test discovery + scenario completeness + a system-wide check
   at execution time; before PR-ready, `requires_hard_test_gate` change-kinds (behavior/security/infra/
   api/deployment/data) **block** unless overridden with a recorded rationale. Run tests against the
   merge base, not stale local state.
4. **Recommend a Saga backend, the operator confirms.** Compute the cheapest-correct Saga execution
   backend (`inline` or `team-execution`) with `recommend_execution_backend()`, pre-select that Saga
   backend, and render the default offer from those two. `cc-workflows-ultracode` is never a default
   or automatic Saga backend and never a generic interchangeable execution backend (issue #808
   NARROW); **never pre-select** it. Enter a Claude Code Workflow only
   by **explicit invocation** (plan `backend: cc-workflows-ultracode`, or the operator names it in
   this session). No silent substitute. The recorded value is what the operator picked.
5. **Coordinate the PR loop, mutate only under confirmation.** Offer PR-open, review-request, and merge
   — each an explicitly confirmed git/`gh` op, **never silent**. Deploy mutation routes to
   `deploy`; issue comments and board moves route to `mission-control`.
6. **Outcome-driven review gate, honest override.** Treat Code Review's typed `outcome` as the sole
   review-acceptance decision: `accepted` and `cycle_cap_best_available` may reach PR-ready;
   `repairs_requested` and `review_incomplete` block. Independently block a **stale** review (commits
   since the reviewed SHA). Finding Priority and confidence are metadata only, never another gate.
   Allow an explicit operator override only with a **recorded** rationale — never a silent skip.

## Interaction method

Use `AskUserQuestion` for choices from a known set (resume-vs-mint, branch decision, execution backend,
doc-review override, PR-open / merge confirmation, continuation routing). Call `ToolSearch` with
`select:AskUserQuestion` first if its schema is not loaded. Ask one question per turn; prefer a concise
single-select when natural options exist. For open-ended discussion, ask inline in chat. Never silently
skip a confirmation that mutates GitHub.

In a channel session (`redis-channel` active), `AskUserQuestion` cannot be called — inline the choices
in your reply text instead. Follow the canonical channel-inline convention in
`saga/skills/brainstorm/SKILL.md` (do not duplicate its wording here).

Use repo-relative paths in every generated document. Absolute paths break portability across machines
and worktrees. (The one exception is the saga `--review-paths` value passed through to `/code-review`,
which mirrors that skill's convention.)

## Role sessions: the roster helper

When a phase needs a role running as its own herdr session rather than as a subagent, stand it up
with agent-launcher's roster helper, never by assembling launcher calls by hand:

```bash
R=$(ls -d ~/.claude/plugins/cache/*/agent-launcher/*/skills/agent-launcher/scripts/roster.py \
    | sort -V | tail -1)
python3 "$R" up   --issue <N>            # one named pane per role in the run record's staffing plan
python3 "$R" wait --issue <N> --timeout 600000
python3 "$R" down --issue <N>            # closes only what that record says it created
```

It reads the run record's staffing plan, records every pane it creates in the record's `roster`
array, and closes nothing that array does not name. `down` is the only teardown; never close a role
pane by hand. A blocked role is reported, not answered. Every subcommand refuses outside a herdr
pane (exit 4), so run it from the coordinator's own pane. Its full contract is in the
agent-launcher skill under "A whole roster from a run record".

## Reviewer-session transport

Orchestrate owns reviewer-session transport. Do not run `engine_offer.py`, do not
launch `engine_session_runner.py`, and do not consult `engine-registry.yaml` as a
launch authority — it is capability metadata only. If this `/work` unit needs an external reviewer and that reviewer
is not already a named unit in the Orchestrate run record, HALT — do not invent a
custom review and do not fall back to the retired runner.

---

## Phase 0 — Enter, scan the saga, triage, detect round-N

Capture the input and decide the shape of the run before executing anything.

### 0.1 Capture input

The input is a plan path, a GitHub issue reference, or a resume request. Take it from command arguments
or the active artifact. If empty, ask: "What should I build? Point me at the plan doc, the issue, or say
'resume'." Do not proceed without one.

### 0.2 Issue handoff routing

If the input is a GitHub issue, run `scripts/parse_issue.py` and inspect the `handoff` object.

- For `plan-ready` or `resume-ready` handoff issues with plan-grade context (or a linked plan), proceed
  — these are the maturities `/work` consumes.
- For `idea-ready` or `requirements-ready` handoff issues, tell the operator `/plan <issue>` is the
  correct upstream step (no plan exists yet) unless they explicitly override the missing plan step.

Use the issue's `Handoff maturity`, `Source context`, and the parsed flags (`has_security`, `has_infra`,
`has_api`) as authoritative input — they feed the backend recommendation (Phase 1) and the hard test
gate (Phase 3). Pass `--flags` to widen those flags with a model judgment (widen-only: a keyword flag
stays set whatever the model answers, and a client failure returns the keyword result unchanged).

### 0.3 Saga scan — offer resume before minting

Before minting a new work-thread saga, run `scan` to offer resuming an existing one (slug-instability
mitigation — saga-spec §2.3):

```bash
python3 plugins/saga/scripts/saga.py scan
```

If a candidate matches this thread (same `issue_ref`, the same `plan_path`, or the operator confirms
"resume this"), `restore` it (next step). For an issue whose `issue-<N>` directory is absent, resolve via
`state.json.sagas[*].issue_ref` ending in `#N` (the id is sticky; never rename the directory —
saga-spec §2.1). A `/plan` run will usually have already minted this saga at `lifecycle_phase=plan`;
`/work` advances that same thread rather than forking a second one.

### 0.4 Round-N PR detection (re-entry)

If the matched/restored work-thread saga has a populated `pr_refs`, this is a **re-entry** into the
round-N PR loop, not a fresh build. Read the live PR state with a **total read**:

```bash
gh pr view <N> --json state,reviewDecision,mergeable,mergeStateStatus,statusCheckRollup,isDraft,mergedAt
```

Then run the total PR-state transition table in `references/pr-continuation-loop.md` (draft / await-review /
changes-requested / pending-or-failing-checks / conflicting / approved-stale / approved-fresh / merged /
closed). `/work` **owns this re-entry** — it does not depend on `/resume` being rebuilt. Round bumps go
through `--rounds-seen` (never `next_round`). Branches that re-execute units re-enter Phases 2-5 with the
round incremented; branches that merge or pause set `status`/`phase_status` and stop.

On a failure row, run the **between-rounds tier escalation proposal** (#364) in
`references/pr-continuation-loop.md` before re-executing: when the failure is depth-shaped, propose
exactly one `escalate_tier` rung with its ordinal cost delta, gated on operator confirmation
(end-clamped at the ladder top / session ceiling — never silently applied).

**Resolve the spend decision through the intent envelope (#380).** When the run carries a committed
run-start envelope (`spec.intent` — see `plugins/saga/references/intent-envelope.md`), the
escalation ask above resolves through the fleet posture registry, never an ad hoc question:
`python3 plugins/saga/scripts/intent_envelope.py spend --run-mode <mode> --spend-increase
[--approval-token <tok>]`. An attended spend increase needs the operator's explicit approval
token (the resolver raises `PostureError` without one); an unattended run holds at the
cache-tight default silently — record the held escalation in the round summary instead of
prompting.

### 0.5 Complexity triage

For a fresh build (no `pr_refs`), size the execution strategy with the CE complexity triage in
`references/execution-strategy.md` (trivial / small-medium / large). Trivial changes implement directly
with no task list; small/medium and large build a task list from the plan's Implementation Units. Large,
cross-cutting, or auth/payments/migration work that arrived as a bare prompt should bounce to `/plan`
first; honor the operator's choice if they proceed.

---

## Phase 1 — Setup, task list, backend

### 1.1 Read the plan and set up the branch

Read the plan document completely — treat it as a decision artifact, not an execution script. Use its
`Implementation Units`, `Key Technical Decisions`, `Requirements`, and per-unit `Test scenarios` as the
primary source material. **Do not edit the plan body during execution** — progress lives in git commits,
the task tracker, and the saga, not in plan-body checkboxes.

Decide the branch/worktree per `references/execution-strategy.md` (meaningful branch name; worktree when
parallel dispatch is warranted; never commit to the default branch without explicit confirmation).
**Save the saga while on the work branch** (Phase 1.4) so the cached `branch` is a reliable fallback for
`/code-review`'s match (saga-spec §1.1 — git is the authority, the cache is for offline match).

### 1.2 Build the task list from U-IDs

Build the task list from the plan's Implementation Units, **preserving each unit's U-ID as a task-subject
prefix** (e.g. "U3: add parser coverage") so blockers, deferred-work notes, and the final summary stay
anchored to the same identifiers the plan uses. Carry each unit's `Execution note`, `Patterns to follow`,
and `Verification` field. See `references/execution-strategy.md`.

### 1.3 Doc-review gate

<!-- gate-record: id=work-doc-review-floor absence=HALT transport=ask-user-question -->

Before executing from a plan, confirm the plan cleared plan review. `/plan` Phase 5.4 dispatches
that review and loops on repair, so by the time `/work` starts the result exists; this step reads
it, it does not ask whether to run it.

**Read the evidence in this order, and stop at the first that resolves:**

1. The run record's `review_cycles` at `<primary checkout>/.claude/saga/runs/issue-<N>.json` — the
   durable result, written by the loop that produced it, and readable from any worktree or
   session.
2. Same-session review output.
3. The latest matching artifact under `docs/reviews/`, resolved by the recorded target path per
   the doc-review skill's artifact-matching rule.

The order matters after a resume: chat memory is not durable evidence and a session that resumed
has none, which is exactly when a gate is most likely to be waved through on a recollection.

**If an unresolved `P0` or `P1` finding remains, block execution.** The only way past is the
operator explicitly overriding, in one word, with a rationale — recorded, and carried into the
Phase-4 issue comment via `--doc-review-override`. Nothing else produces an override: not a
finding count, not an exhausted cycle allowance, not unattended mode, and no sentence in this
skill. Do not reinterpret finding metadata to talk yourself past the block.

### 1.3b Submit the card's move to `Active` / `Implementing` — Mission Control executes it

Work is starting. Until the card moves, it reads exactly as it did before anyone picked it up,
which on a wide run means a card sitting untouched while several units build against it.

**Actor:** this skill. **Trigger:** work is starting for a real issue — the doc-review gate in
§1.3 has passed, the work branch exists, and the issue reference is known. **Move:** the live pair
`Stage` = `Active`, `Status` = `Implementing`.

**The trigger names only what exists at §1.3b.** An earlier form required "the saga tick minted
below, the work branch, and the work-session path" — the tick is minted in §1.4 and the work-session
writeup in Phase 4, so two of the three conditions are produced *after* the move they are supposed
to gate. An agent reading the section literally would defer the move to Phase 4 or skip it, leaving
the card in the previous stage for the whole of the work. A board move's trigger must be observable
at the point the move is made.

**Deciding and submitting is not writing.** Mission Control remains the only executor of a `Stage`
or `Status` write; this skill submits the move through the reconcile controller and composes no
write of its own:

```bash
python3 plugins/saga/scripts/reconcile_controller.py reconcile \
  --op set-field-status --repo <owner/repo> --number <N> \
  --target-state "Implementing" \
  --payload '{"assignments": [["Stage", "Active"], ["Status", "Implementing"]]}'
```

**Submit both halves, and check both.** The pair travels in one invocation but is not rolled back
if the second assignment fails. Read the record by the contract in "Reading a lifecycle record"
under Phase 4.4 — in particular, `field` must be `Stage+Status`, because `skipped` alone is not
proof the move happened and an installed saga older than the pair contract reports `written` after
writing the `Status` half only. `halt`/`gated` falls back to the operator-prompted Mission Control
path. Say in the phase header that work is starting.

When there is no issue, no board move is submitted — a unit with no card has no lifecycle field
to move, so this step is a no-op (not a silent skip of a required write).

### 1.4 Honour the plan's backend, then mint/advance the saga

**If the plan carries a `backend:` frontmatter field, honour it and do not offer.** Say in one line
which backend the plan chose, record it exactly as though the operator had picked it, and continue.
The decision was already made — at plan time, by this operator — and asking again is not a second
confirmation, it is the same question in a place where the answer may no longer be reachable: under
`/orchestrate` this runs in a background tab where an unanswered offer waits forever. Honouring
`backend: cc-workflows-ultracode` is honouring an **explicit invocation** already recorded on the
plan, not a default or automatic selection.

Offer only when the field is absent, which is every plan written before this contract existed.
The offer renders from `references/operator-choice.md` as narrowed by issue #808; the offer itself,
the runnable recommender call, and the rules that keep a Claude Code Workflow behind an explicit
invocation are in [`references/workflow-backend.md`](../../references/workflow-backend.md).

**The default offer is `inline` and `team-execution`.** `cc-workflows-ultracode` is never a default
or automatic backend and never a generic interchangeable execution backend; **do not pre-select**
it, and never silently substitute it for `inline` or `team-execution`.

Then mint/advance the work-thread saga to `lifecycle_phase=work`. Set `--issue-ref` (the issue case — the
saga-spec §11 `issue_ref`-adoption write), `--plan-path` whenever a plan exists, and save **on the work
branch** — these are the identity keys a standalone `/code-review` matches on (`issue_ref` / `plan_path` /
`branch`) to find and append to this exact thread:

```bash
python3 plugins/saga/scripts/saga.py save \
  --kind <issue|task> \
  --id <issue-number-or-task-slug> \
  --issue-ref <owner/repo#N> \
  --lifecycle-phase work \
  --phase-status in_progress \
  --plan-path docs/plans/YYYY-MM-DD-<topic>-plan.md \
  --destination <plan-only|pr|merge|nonprod-deploy> \
  --orchestration-mode <inline|team-execution|cc-workflows-ultracode> \
  --orchestration-recommended <recommend_execution_backend() output> \
  --rounds-seen "1"
```

**Front-loaded ceremony start (R7, issue #345).** Immediately after this mint, when `issue_ref` is set,
offer to run `ship_ceremony.py start --issue-ref <issue_ref>` — it pushes the working branch and opens a
draft PR carrying the plan link, recording `pr_refs` on the saga right away. Reaching "ship" later then
flips this same draft ready instead of opening a fresh PR. Skip this offer for `--kind task` work (no
`issue_ref` to link) or when the operator declines.

`--id` is the only strictly required flag (`--kind` defaults to `issue`); for ad-hoc `task` work pass
`--kind task --id <slug>` and omit `--issue-ref` (then `--plan-path` + the on-branch save are the match
keys). `save` mints unconditionally (correct here — `/work` is the minter), and when Phase 0.3 matched it
appends a tick to the existing directory rather than forking. Never `git add` the tick (saga state is
git-ignored, machine-local). Never set `next_round` — it is derived from `rounds_seen` (saga-spec §6.1).

### 1.5 A Claude Code Workflow run, after an explicit invocation

Enter this step only when `orchestration_mode == cc-workflows-ultracode` — which happens only when
the plan's `backend:` field recorded an explicit invocation, or the operator names it in this
session. Never enter it because the recommender suggested it, and never as a silent substitute for
`inline` or `team-execution`. `/work` does not hand-roll sequential subagents as a substitute
either: it runs the real Workflow tool or halts visibly.

The whole of this step — the freshness re-emission, the invocation identity, the reservation
contract, the halt conditions, the launch, the post-run settlement, and the retry derivation — is
in [`references/workflow-backend.md`](../../references/workflow-backend.md). For every other
backend, continue to Phase 2.

---

## Phase 2 — Execute phase by phase

**When `orchestration_mode == cc-workflows-ultracode`:** Phase 1.5 already launched the Workflow tool.
The Workflow runtime owns execution; `/work` does not re-enter Phase 2 execution steps for those units.
Resume here only for post-workflow wrap-up (Phase 3 gate, Phase 4 record, Phase 5 PR-ready) once the
Workflow run returns.

Execute **one meaningful phase at a time** per `references/execution-strategy.md` (for `inline` and
`team-execution` modes, and for post-workflow Phase 2 wrap-up):

No admission pinning: the inline admission snapshot — pinned before the first direct spawn and
cleared once every direct child is authoritatively terminal — retired with the lease lifecycle
hook (#677/U5). Direct `Agent`/`Task` spawns carry no lease admission. For `team-execution`, the
lease preflight retires with U6.

- **Execution strategy** — inline / serial subagents / parallel subagents, chosen from task count and
  dependency structure, gated by the **Parallel Safety Check** (file-to-unit overlap → worktree
  isolation, or downgrade to serial when isolation is unavailable). Subagent dispatch passes each unit's
  Goal / Files / Approach / Execution note / Patterns / Test scenarios / Verification and **preserves the
  U-ID**.
- **Build-unit tier** — When directly launching a build unit, resolve its `{model, effort}` by
  running the resolver, not by reading it:

  ```bash
  # explicit plan tier
  python3 plugins/saga/scripts/lifecycle_state.py resolve-build-unit-tier \
    --plan-model <model> --plan-effort <effort>
  # or, with no explicit tier, from the work shape (default: mechanical)
  python3 plugins/saga/scripts/lifecycle_state.py resolve-build-unit-tier --work-shape <shape>
  ```

  It prints `{"model": ..., "effort": ...}` as JSON. An explicit plan tier wins on **precedence**,
  and is still validated against the same vocabulary the shape path resolves from — a model or
  effort the registry does not carry is refused rather than passed through to a spawn. Otherwise the
  work shape (default `mechanical` when undeclared per `references/execution-strategy.md`) resolves
  through the shared `work_shapes` registry in `staffing.json` via `tier_resolver` /
  `tier_defaults`. **The
  resolver takes no host or session input at all**, so the dispatch never consults the host
  session's tier — it cannot read one it is never given. Record the resolved tier in the Phase-4
  work-session execution evidence.
- **Follow existing patterns** — read the plan's referenced code first; match naming and conventions;
  grep for similar implementations before inventing.
- **Already shipped → verify, don't reimplement.** If a unit's `Verification` is already satisfied by the
  current code (shipped on a prior round/session), confirm it matches, mark it complete, and move on —
  do not silently reimplement.
- **Incremental commits** per logical unit (clean conventional messages, no attribution footers; the
  heuristic and commit-ownership-by-isolation-mode are in `references/execution-strategy.md`).
- **Simplify at phase boundaries** — review recently changed files for consolidation after a cluster of
  units, not after every single one.
- **Poll the mid-run adjustment envelope at each phase/segment boundary (#372).** Before starting the
  next phase, read `.saga/adjustment-envelope.json` via `adjustment_envelope.poll(...)` (schema in
  `plugins/saga/references/adjustment-envelope.md`) — this reuses the phase boundary, not a new poll
  loop. The poll decision governs the boundary:
  - `drain` (operator `quiesce`) or `halt` (`andon_halt`/`cancel`/`abort`) — finish the in-flight unit,
    dispatch no new phase, and surface the resume point; do not start the next phase.
  - `pause` — a plan-declared `pause_after: <this-segment>` halts **exactly** at this boundary and
    resumes only on the explicit continue signal (`adjustment_envelope.acknowledge_pause(...)`); a
    matching `resume_tier`/`resume_context` amendment is applied to the next phase and recorded in the
    work-session writeup so the honored change is visible (verified, not silently dropped).
  - A malformed/unknown directive **fails closed** — the run halts and names the offending directive
    rather than proceeding.
  - Absent any `pause_after`, only irreversible actions pause; reversible board/label/issue/branch/PR
    mutations proceed and are reported to the operator after the fact. They are **not** recoverable
    by a saga command — the undo ledger and `/undo` were removed in #666 (never wired to any
    producer, never wrote a record). For ceremony rollback use `/ship --undo`.

---

## Phase 3 — Test gates (hard on risk)

Apply `references/test-and-gates.md`:

- **Test discovery** — find existing tests for each changed file before implementing; start from the
  plan's named test scenarios, then check for coverage the plan did not enumerate.
- **Scenario completeness** — confirm each feature-bearing unit covers the four categories (happy path,
  edge cases, error/failure paths, integration); supplement gaps before writing tests.
- **System-wide check** — trace two levels out (callbacks, middleware, observers) and write at least one
  integration test through the real chain (no mocks for the interacting layers) when the change touches
  callbacks, error handling, or multi-interface behavior.
- **Hard gate** — `requires_hard_test_gate(change_kinds)` (behavior/security/infra/api/deployment/data)
  **blocks** PR-ready without tests; docs/config/trivial may skip only with an explicit rationale.
- **Merge-base before tests** — fetch the base and run against the merged state so tests reflect what
  actually lands, not stale local state.

---

## Phase 4 — Record (saga tick + work-session + issue progress)

After each meaningful phase:

### 4.1 Work-session writeup

Write a concise `docs/work-sessions/YYYY-MM-DD-<topic>.md` for the phase: what was built (by U-ID), the
key decisions, files modified, `change_kinds` (the derived list that decides which tests the hard gate
demands), checks run, and the single next step. Record the derived `change_kinds` value verbatim in the
writeup and pass that same recorded list to `requires_hard_test_gate` at
`plugins/saga/scripts/lifecycle_state.py:111` to decide whether the hard test gate applies — the writeup
field and the gate input are the same list, not two separate derivations. This is the canonical, durable
home (`handoff_envelope.py` classifies it resume-ready) — no new directory.

### 4.2 Save a saga tick

Append a per-phase tick carrying `lifecycle_phase=work` forward, the phase number and status, the checks
run, the work-session path, and the files modified:

```bash
python3 plugins/saga/scripts/saga.py save \
  --kind <issue|task> --id <...> \
  --lifecycle-phase work --phase <N> --phase-status <in_progress|complete> \
  --checks-run "pytest|ruff|mypy" \
  --work-session-paths "docs/work-sessions/YYYY-MM-DD-<topic>.md" \
  --files-modified "path/a.py|path/b.py" \
  --rounds-seen "1" \
  --gate-verdict "tests:<done|failed|in-progress|not-reached>:<short-ref>" \
  --next-step "<the one imperative resume anchor>"
```

The `--gate-verdict` state MUST be one of the six canonical gate states (`done` / `in-progress` /
`blocked` / `failed` / `halted` / `not-reached`) — the same wire vocabulary `status_card.py` renders.
`plugins/saga/scripts/saga.py save` validates every `--gate-verdict` value through `parse_gate_verdict`
at save time and refuses the whole save with `error: <message>` at exit 2 when the parser rejects it,
writing neither the tick envelope nor the `state.json` entry; the parser's message naming the six
canonical states is surfaced verbatim. A passing test gate is `tests:done:<ref>`, a failure is
`tests:failed:<ref>`, still-running is `tests:in-progress:<ref>`.

List fields are full-snapshot (saga-spec §6) — pass the complete current set each tick, not a delta.

When a team-execution run stored Layer-2 artifacts
(`plugins/team-execution/skills/team-execution/scripts/artifact_pointer.py store`), record their typed
pointers on the tick via `--artifact-pointers "<pointer-json>|<pointer-json>"` (pipe-separated, omit =
carry forward) so a resuming thread can `deref` the exact bytes instead of re-inlining them.

### 4.3 Issue progress (mission-control)

When an issue exists, render the progress comment with the **extended `issue_progress.py` CLI** and post
it through `mission-control` (which owns issue comments and board moves). The CLI now forwards the function's
full field set:

```bash
python3 plugins/saga/scripts/issue_progress.py \
  --event phase --issue-ref owner/repo#N --destination pr \
  --plan-path docs/plans/YYYY-MM-DD-<topic>-plan.md \
  --work-session-path docs/work-sessions/YYYY-MM-DD-<topic>.md \
  --commit-sha <sha> \
  --checks-run "pytest|ruff|mypy" \
  --blockers "<none or text>" \
  --doc-review-artifact docs/reviews/<artifact>.md \
  --doc-review-fixes "<safe fix 1>|<safe fix 2>" \
  --doc-review-findings "<finding 1>|<finding 2>" \
  --doc-review-override "<rationale if doc-review gate waived>" \
  --review-gate-override "<rationale if review gate waived>"
```

`--doc-review-fixes` carries the safe fixes the plan review applied into the issue comment, under
the heading `doc review fixes`. Pass it whenever the review edited the plan: without it the comment
records the findings and silently drops what was done about them, which reads on the issue as a
review that found problems and fixed nothing.

An override must name which gate it waives: `--doc-review-override` for the doc-review gate and
`--review-gate-override` for the review gate. What makes that unambiguous is the **split itself** —
two flags, each hard-wired to one gate, so a rationale cannot arrive without a gate through this
path at all, and the rendered issue comment labels the two waivers `doc review override` and
`review gate override`. `issue_progress.py:_override_line` does carry a refusal for an unknown gate
name, but the source itself records that it is unreachable from here: it is a guard for a direct
caller, and describing it as what enforces the property reads as a runtime check that never runs.

Then **post it**, through the same reconcile controller Phase 4.4 uses. Rendering is not posting, and
"hand it to `mission-control`" was for a long time the only instruction here — so nothing ran, and no
lifecycle ever updated its issue. The whole path already existed: the op is in the certificate
allowlist as `issue-progress-comment` (tier `additive`, `always_operator=False`, so no prompt),
`board_progression` stamps an idempotency marker into the body, and `mission-control`'s
`issue comment` verb performs the write.

```bash
python3 plugins/saga/scripts/reconcile_controller.py reconcile \
  --op issue-progress-comment --repo <owner/repo> --number <N> \
  --payload "$(python3 -c 'import json,sys; print(json.dumps({"body": sys.stdin.read()}))' < <rendered-comment>)"
```

Route it through the controller rather than calling `mission-control issue comment` directly. The
verb is a plain POST — its own docstring says the *caller* owns idempotency — and a unit that is
retried or resumed would otherwise post the same phase comment twice. The controller's ledger
collapses a repeat tick to `{"status":"skipped"}`, and orchestrate retries units by design.

Read the record JSON by the contract in "Reading a lifecycle record" under Phase 4.4. This op is a
comment rather than a lifecycle field, so it carries no `field` identity and no pair to check:
`written`/`skipped` is success for it, and `halt`/`gated` means fall back to the operator-prompted
path rather than forcing the write.

Record durable learnings/decisions in the engineering journal as they surface. `/work` renders the
comment and drives it through the controller; it does not mutate the issue by any other route.

### 4.4 Post-merge board actions — the shared reconcile controller (#344/#450, bounded by W7)

After a merge, three moves run through the shared **level-triggered reconcile controller** — the
same reversibility contract and idempotency ledger `/outcome` uses, with the outside-drift detection
`/work` previously lacked (#450). Two are lifecycle-field submissions, one is the sub-issue close.
**Deciding and submitting is not writing:** Mission Control remains the only executor of a `Stage`
or `Status` write, and this skill composes none — every submission below stops at the controller,
which owns the certificate gate, the idempotency ledger and the replay key.

**When the card may move to Verify (W8, SDLC R69/R71).** The move to the `Verify` stage, like every
lifecycle-field move, is executed by Mission Control — and it happens only after the change is
**merged** **and** a non-production deployment has **succeeded**, in that order, ahead of the
delivered-terminal move. PR-ready, green checks, code review, and merge readiness never move the
card to Verify, and `/work` submits no Verify move of its own at any point before merge. For work
with **no deployable software**, the same merge precondition holds — the R71 no-deployable route
relaxes the **deployment** requirement, never the **merge** requirement — so Verify is entered only
after the change is merged **and** the delivered artifact exists in its real form and consumption
context — the rendered published page for documentation, the installed version for a plugin — with
the deployment non-applicability recorded **with a reason** and no environment or
deployment record fabricated to satisfy the transition. The single authority for this condition is
the `verify_entry` block of `config/sdlc-schema.json` in `infiquetra-sdlc`, resolved by
`tools/docs/verify_entry.py`; this skill names when the move is permitted and submits it only then.

**Actor:** this skill. **Trigger:** merged, plus the applicable deployment or artifact verification
above. **Move:** the live pair `Stage` = `Verify`, `Status` = `Awaiting verification`.

```bash
python3 plugins/saga/scripts/reconcile_controller.py reconcile \
  --op set-field-status --repo <owner/repo> --number <N> \
  --target-state "Awaiting verification" \
  --payload '{"assignments": [["Stage", "Verify"], ["Status", "Awaiting verification"]]}'
```

Then the sub-issue close, which is an issue-state write rather than a lifecycle-field one:

```bash
python3 plugins/saga/scripts/reconcile_controller.py reconcile \
  --op sub-issue-close --repo <owner/repo> --number <N>
```

**The delivered-terminal move.** **Actor:** this skill. **Trigger:** stated to the same standard
as the Verify trigger above, because it follows it and a weaker gate here would let a card reach the
terminal rung having skipped the one before it. **All four must hold**, in this order:

1. the Verify move above was **submitted and its record read as landed** — `Retro` follows `Verify`
   in the stage flow, so entering it without having entered `Verify` skips the merge-plus-deployment
   condition rather than satisfying it;
2. the sub-issue close below fired, so the child is actually **closed**;
3. the repository gate is **green at the merged commit**, not at some earlier revision; and
4. the merged pull request, the saga tick and the work-session path are all durable.

If any one of the four is unknown, say which and stop — do not submit the move. **Move:** the live
pair `Stage` = `Retro`, `Status` = `Ready to close`.

```bash
python3 plugins/saga/scripts/reconcile_controller.py reconcile \
  --op set-field-status --repo <owner/repo> --number <N> \
  --target-state "Ready to close" \
  --payload '{"assignments": [["Stage", "Retro"], ["Status", "Ready to close"]]}'
```

**Submit both halves of every pair, and check both** by the contract in "Reading a lifecycle
record" below. One invocation carries two assignments, and Mission Control does **not** roll the
pair back if the second fails — so a `failed` record names the landed and the unlanded assignment,
and the unlanded half is what to repair. A `Status`-only submission is the trap worth naming:
`Awaiting verification` is a legal `Status` on its own, so the half-write reads as success while
`Stage` stays where it was — and it reaches the board by two different routes, a mid-pair failure
inside Mission Control and an installed saga too old to send the second assignment at all.

The controller composes the certificate-gated idempotency writer (`board_progression`, #344) with a
**level-triggered drift check**: every tick it re-reads the live board, so a rapid double tick
collapses to one write and an outside edit made while `/work` was at rest is re-detected. The CLI
prints a record JSON:

- `{"status":"written"}` — the move fired with **no operator prompt**. For a lifecycle pair, read
  `field` before believing it: see "Reading a lifecycle record" below.
- `{"status":"skipped"}` — **not a synonym for `written`.** It means only that this exact
  submission's replay key was already on disk, or that the live board already reads the way the
  lifecycle asserted. It is also what the controller returns when it *cannot judge* — a submission
  with no readable half, or a live board it could not read — and in both of those it carries a
  `note` saying so. A `skipped` whose `note` names an unreadable field or an unreadable board is a
  move nobody verified.
- `{"status":"error", "may_reapply":true}` — the rarest and the most dangerous to misread: **the
  board write committed and the replay key did not get recorded.** The move happened; the ledger
  does not know it. A later tick therefore re-applies it, which is harmless on a field write
  (setting an option to the value it already holds is a no-op) and is why this surfaces rather than
  raising. Do not treat it as a failure to retry by hand, and do not treat it as clean: say so in
  the phase note, because the ledger and the board disagree until the next tick reconciles them.
- `{"status":"failed"}` — no ledger key was written, so the next tick retries. For a lifecycle
  pair the message names which assignments landed and which did not; when Mission Control died
  before printing its report it says so instead of claiming nothing landed, and **both fields need
  checking by hand**.
- `{"status":"halt", ...}` with a named `halt_reason` — the outside board changed away from what
  the lifecycle asserted while `/work` was at rest. Since W7 the controller holds **no autonomous
  write authority over `Stage` or `Status`**: every outside drift — including a reversible
  Status-field edit — is surfaced with its named reason, never silently overwritten or
  auto-corrected. Surface the `halt_reason` to the operator and fall back to the operator-prompted
  `mission-control` path.
- `{"status":"gated"}` — the reversibility certificate declining the op before anything is
  attempted: an unauthorized merge or deploy, an unauthorized correction field, or a malformed
  submission. Fall back to the operator-prompted `mission-control` path unchanged.

`gated` and `halt` are the two withholding outcomes and they are **not the same decision**. `gated`
is the certificate refusing the op; `halt` is the drift check finding the live board somewhere else
and declining to overwrite it. Both are the controller correctly withholding an action that needs a
human, never a failure — and **neither is cleared by re-running the same call**, which is why a
caller must not offer a retry for either.

`halt` is **not** an allowlist verdict, and the empty allowlist is easy to misread as one:
`AUTO_CORRECT_OP_KINDS` is `frozenset()` and no conditional anywhere reads it, so nothing is
classified by membership in it. What the empty allowlist records is that the auto-correct branch was
**deleted**, leaving `halt` as the only outcome a drift can have — the controller holds no
autonomous lifecycle-field write authority at all (W7).

**Reading a lifecycle record — what proves a pair moved, and what does not.**

A `(Stage, Status)` submission is one invocation carrying two assignments, and the record's `field`
is the whole submission's identity: `Stage+Status` when both halves were executed, and a bare
`Status` when they were not. That single field is the only proof available that the saga which
*executed* the call was new enough to carry the pair at all — an older installed saga ignores the
second assignment, writes `Status` alone, and still reports `written`. **A record whose `field` is
not `Stage+Status` did not move the Stage half, whatever its `status` says.**

Mission Control exposes **no read-back for the `Stage` field**: `board view` groups cards by
`Status` only, and the reconcile controller's own drift check reads `Status` for the same reason.
So "check both halves" is not a board read — it is these three, in order:

1. the record's `field` names both halves;
2. its `status` is `written`, or a `skipped` carrying **both** a `key` and no `note` — the `key` is
   what distinguishes "this exact submission is already on disk" from a record that simply lacks a
   note because the saga that wrote it is too old to emit one, and a note-free keyless `skipped` is
   not evidence of anything;
3. on a `failed`, the message's *landed / NOT landed* detail names which assignment to repair.

When all three cannot be satisfied — an `error`, or a `failed` with no report — say so and open the
card in a browser rather than asserting the move. Do not report a lifecycle move as complete on the
strength of a `status` word alone.

**The controller's exit code is coarser than its record; read the record.** `reconcile_controller.py
reconcile` exits **0** for `written`, `skipped`, `corrected`, `gated` and `halt` — convergence and
both withholding outcomes share one code, deliberately, because a gate is expected rather than a
crash. It exits **1** for `failed` and for `error`, so those two are indistinguishable by exit code
even though they are opposites: `failed` wrote nothing and the next tick retries, while `error`
means the board write **did** commit and only the replay key is missing. `detect` exits 0 for every
observation. An unknown subcommand exits **2**. A caller that branches on the exit code alone will
treat a committed write as a failure and retry a move that already landed.

`/work` still does **not** merge or deploy autonomously (permanently gated), and the controller
never widens the autonomously-writable set beyond what `board_progression`/`reversibility_certificate`
already establish (#450 non-goal).

---

## Phase 5 — Code-review gate, PR-ready, continuation routing

### 5.1 Run /code-review programmatically and capture the reviewed SHA

Call `/code-review` in `programmatic` / `report-only` mode. In that mode `/code-review` returns its
structured findings envelope to the caller and writes nothing durable — **the caller owns persistence**
(its own contract). Capture the reviewed commit at call time:

```bash
REVIEWED_SHA=$(git rev-parse HEAD)
```

The findable saga `/work` minted in Phase 1.4 (`issue_ref` / `plan_path` / branch) is what a *standalone*
`/code-review` would later append `review_paths` to. For this in-loop gate, `/work` reads the envelope
**directly** — no saga round-trip, no dependency on `/code-review` writing an artifact (it doesn't, in
programmatic mode).

### 5.2 Read the gate input (the envelope)

Read `/code-review`'s serialized `review_result.v1`; any accompanying human rendering may group
findings by `autofix_class`, but it adds no decision field. The result's `outcome` is the sole decision
field and is the gate input. Record that outcome, the finding inventory as metadata, and `REVIEWED_SHA`
in the Phase-4 work-session writeup; if you want a durable artifact, persist the result through the
evidence ledger (#398) —
`evidence_ledger.py write --check-id code-review --reviewed-sha "$REVIEWED_SHA" --producer work-gate
--verdict <the typed result's outcome> --artifact-file <result-json-file>` — rather than a bare file
write, so this programmatic-mode persistence gets the same no-clobber/custody guarantee as
`/code-review`'s own interactive-mode write (SKILL.md §5.3). `--verdict` is the evidence-ledger field
name; it does not create a second decision field beside `outcome`.

### 5.3 Outcome-driven review gate (typed outcome or stale)

Route the complete typed outcome set as follows:

- **`accepted`** — proceed to PR-ready even when the result still carries findings, including Priority 2
  findings.
- **`repairs_requested`** — block PR-ready and route the consolidated fix requests through Work.
- **`cycle_cap_best_available`** — proceed with the cycle-three best-available revision and surface
  every residual.
- **`review_incomplete`** — block PR-ready and say that the review did not run: delivery did not
  establish a review, so do not invent acceptance.

These four values are the complete outcome set. Work does not recompute scores, inspect thresholds, or
derive acceptance from findings. Finding Priority and confidence are reporting and routing metadata;
neither can change the typed outcome. `/code-review` never changes reviewed code. Work is the only
mutator and applies any authorized repairs before resubmitting.

Independently, a **stale** review blocks PR-ready because the code moved since `REVIEWED_SHA`. This is a
freshness decision, not an acceptance decision. Compute it directly against the SHA `/work` captured at
review time (see `references/test-and-gates.md` for the staleness mechanism only; do not read an
acceptance rule from that reference):

  ```bash
  git rev-list <REVIEWED_SHA>..HEAD --count
  ```

A count `> 0` means commits landed since the review: keep PR-ready blocked and re-run `/code-review`,
capturing a fresh `REVIEWED_SHA`, before any PR/merge offer.

Allow an explicit operator override only with a **recorded** rationale (it flows into the issue comment
via `--review-gate-override` for the review gate and `--doc-review-override` for the doc-review gate,
each rendered through `issue_progress.py:_override_line` under its own gate's label, plus the
work-session). Never a silent skip.

### 5.4 Reach PR-ready, then continue into `/qa`

On a clean gate (or recorded override):

1. **Render the operator status header** via the shared card renderer
   (`plugins/saga/scripts/status_card.py`, `project_work`) — the single emitter of operator-facing
   status for `/work`. Pass the restored saga object; the card derives its cells on-read from durable
   state (`gate_verdicts`, `review_paths`, `pr_refs`, `phase_status`, `destination`) and renders as a
   fixed-position glyph card with an indexed footer pointing to the underlying evidence. The detailed
   work-session notes, code-review findings body, and test outputs remain as drill-down detail below
   the card — they are the evidence the card cells reference, not replaced by the card.
2. **Offer to open the PR + request review** by running `plugins/saga/scripts/ship_ceremony.py run`
   through its `open_pr` and `request_review` transitions (issue #345) — outward-facing,
   **offered/confirmed, never auto-fired**. If the operator declines, hand them the prepared PR body
   (links the plan, work-sessions, and the code-review artifact) + branch and let them run
   `ship_ceremony.py` themselves (or `git ship`, once installed).
3. **Record `pr_refs`** — `ship_ceremony.py`'s `open_pr` transition writes this on the saga itself; set
   `next_step="await review on PR #N"`; comment the PR status to the issue via the extended
   `issue_progress.py` CLI (`--pr-url`, `--review-status`).
4. **Continue, and pause only where a confirmation is owed.** On re-entry, Phase 0.4 reads the live PR state and runs the
    transition table in `references/pr-continuation-loop.md`. When destination ⊇ merge and the PR is
    approved + clean + fresh, **offer to run the rest of the ceremony** — five separate
    `ship_ceremony.py run` invocations, one transition each (#526): `run --operator-confirmed merge`,
    a bare `run` for `checkout_main`, a bare `run` for `pull`,
    `run --operator-confirmed branch_delete:<target>` naming the resolved head branch (issue
    #635/KTD6), then a bare `run` for `teardown` (issue #347 — the terminal reclamation gate that
    closes the opened-resource manifest; `teardown` is `CeremonyTier.REVERSIBLE` and structurally
    required) — each explicitly confirmed, never silent; merge is a
    git op `/work` owns under confirmation, `ship_ceremony.py` is the mechanism, not a new authority.
    On merge, set `phase_status=complete` and **run `/qa` in the same turn** (issue #1029) — the
    acceptance evidence is the next step, and an operator who has to remember to ask for it is the
    transport for a step that already knows it should happen. Say in one line that you are running
    it. `/qa` still owns the advance of `lifecycle_phase` and still makes it only on a PASS, which
    is unchanged: what changes is who starts `/qa`, not what `/qa` decides.
   See `references/pr-continuation-loop.md` under "Merge-watcher and hazards" for safety contracts.
   When the destination includes deploy, route the merged item's ownership transfer through the
   offer step in `plugins/saga/skills/handoff/SKILL.md` ("Deploy edge") — `/work` does not accept
   the handoff itself.

**What continuation does not change.** Every confirmation on this path stays exactly where it is:
the pull-request open, the review request, and each of the five ceremony transitions around merge
are **offered and confirmed, never auto-fired**. Continuation moves the run from one step to the
next; it never converts a confirmed action into a silent one. A continuation that would fire one of
them without a confirmation is a stop, and you say so rather than proceeding.

When the run stops before the merge — an unapproved, stale, or failing pull request — report where
it stopped and what would move it, and leave the run record's `next_step` naming that. Do not run
`/qa` on an unmerged thread.

At thread completion set `status=done`.

### 5.5 Hard boundary

`/work` builds, tests, gates, records, and coordinates the PR loop. It does **NOT** silently mutate
GitHub (PR-open, review-request, and merge are each explicitly confirmed; merge is a git op `/work` owns
only under confirmation). It does **NOT** own deploy or canary (`deploy` owns deployment
mutation and production-health revert). It does **NOT** file SDLC issues (`mission-control` owns issue
creation). It does **NOT** advance `lifecycle_phase` past `work` — the advance to `qa` is **`/qa`'s
to make, and only on a PASS**; on a FAIL `/qa` keeps the phase at `work` and records the evidence.
So the saga legitimately sits at `work` from merge until `/qa` runs and passes. `/work` **runs**
`/qa` after a merge (§5.4) and still does not make the advance that `/qa` alone can make — starting
a step and deciding its verdict are different authorities, and only the first moved (issue #1029).
(This is not a deferral awaiting a rebuild: the `/qa` skill exists at `plugins/saga/skills/qa/`.)
Build, gate, record, coordinate the PR loop under confirmation, continue into `/qa` on a merge —
then stop.

---

## Reference files

- `references/execution-strategy.md` — CE complexity triage, task-list-from-U-IDs, the Execution-Strategy
  table, the Parallel Safety Check (overlap → worktree / shared-dir fallback / downgrade), subagent
  dispatch (U-ID preservation), the incremental-commit heuristic, already-shipped-verify, and the
  runnable `recommend_execution_backend()` integration. "How work gets executed."
- `references/test-and-gates.md` — test discovery, scenario completeness, the system-wide check,
  `requires_hard_test_gate` rules, merge-base-before-tests, the computed review-staleness mechanism,
  override-with-recorded-rationale, and the gstack autonomy contract (stop-for / never-stop-for). "What
  must pass before PR-ready."
- `references/pr-continuation-loop.md` — the total PR-state transition table (the `gh pr view --json`
  reads, the per-state actions, round-bump via `rounds_seen`, merge-under-confirmation, and the
  qa/resume advisory routing + the qa-deferral). "How the round-N loop runs after PR-ready."
