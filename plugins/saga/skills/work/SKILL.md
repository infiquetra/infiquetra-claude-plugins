---
name: work
description: Execute a settled Infiquetra plan to PR-ready, then own the round-N PR continuation loop. Restores and writes the work-thread saga (the primary writer), recommends an execution backend, runs risk-gated tests, calls /code-review programmatically and reads its envelope, gates hard on P0/P1 and stale reviews, and coordinates PR-open/review-request/merge under explicit confirmation — without owning deploy. Triggers on "build it", "work this plan", "execute the plan", "resume work on #N", or a plan-ready / resume-ready handoff issue.
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
- the `review` phase (`/doc-review`) answers: "Is this plan ready to execute?"
- **`/work` answers: "Build it." — and owns the PR loop to merge** (this engine)
- `/code-review` answers: "Is the built code safe to merge?" (`/work` calls it programmatically for the gate; appends `review_paths` when run standalone against `/work`'s saga)
- `/qa` answers: "Does the shipped thing actually work?" (`/work` routes here advisorily after merge)

`/work` consumes what `/plan` produced (the plan doc + the plan saga) and advances that same saga
through `work`. It calls `/code-review` before opening a PR. After merge it routes to `/qa` advisorily —
it leaves `lifecycle_phase=work` because `/qa` does not yet advance the phase (see Phase 5).

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
4. **Recommend the backend, the operator confirms.** Compute the cheapest-correct execution backend
   with `recommend_execution_backend()`, pre-select it, and always render the offer from the full
   `backends` enumeration — all three, each `{backend, status, note}` — so escalation is one keystroke
   and no backend is silently dropped (operator-choice §2). The recorded value is what the operator
   picked.
5. **Coordinate the PR loop, mutate only under confirmation.** Offer PR-open, review-request, and merge
   — each an explicitly confirmed git/`gh` op, **never silent**. Deploy mutation routes to
   `deploy`; issue comments and board moves route to `mission-control`.
6. **Hard review gate, honest override.** Block PR-ready on unresolved P0/P1 findings or a **stale**
   review (commits since the reviewed SHA). Allow an explicit operator override only with a **recorded**
   rationale — never a silent skip.

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

## Engine Offer

Before offering external-engine help for a work unit, run
`python3 plugins/saga/scripts/engine_offer.py offer --stage work --repo-root . --attended`.
Pass explicit unit shape or fingerprint text when available so mechanical/scaffold work can default to
offload while judgment work stays advisory. If the helper reports `prompt_required`, `/work` owns the
operator prompt and persists the selected preference with `engine_offer.py remember`. The offer never
dispatches by itself, never replaces `/work`'s backend choice, and never satisfies a gate.

## Second-opinion triggers

Issue-specific or plan-specific work may add an advisory second-opinion trigger, but it never changes the
Engine Offer choices into a generic offload path. For a repeated-test-failure trigger, create the Markdown
work-session and its adjacent `saga.work-second-opinion.v1` sidecar together:

```text
docs/work-sessions/YYYY-MM-DD-<topic>.md
docs/work-sessions/YYYY-MM-DD-<topic>-second-opinion.json
```

Use `second_opinion.WorkAttempt`, `load_work_second_opinion_state`,
`record_work_attempt`, and `save_work_second_opinion_state`. Record an attempt only after one applied fix
and its following test run; a rerun must reuse its `attempt_id` and is a no-op. Normalize pytest node IDs to
their repo-relative `.py` file target. Absolute paths, traversal, unparseable targets, malformed sidecars,
and over-cap history are visible fail-closed conditions: do not offer or dispatch.

The detector tracks each target independently. A pass resets every streak; a target missing from a failed run
resets only that target; unrelated extra failures do not reset a persistent target. On the first three-fix
streak, print exactly this one line and persist its offer key before asking:

```text
Second opinion available: {target} failed after 3 fix attempts; dispatch an advisory second opinion?
```

The `none` work preference suppresses only this automatic offer. A remembered `offload` preference is not a
valid trigger route and cannot change it from `second-opinion`. Do not write a permanent preference because
the operator declined one offer. No answer or unattended mode records `unattended`; decline records
`declined`; both proceed through the existing work gates with zero runner calls.

For explicit acceptance, first call `prepare_second_opinion`, then use `accept_work_offer` and atomically
save the sidecar before invoking `dispatch_second_opinion`. The U1 claim store takes its own durable
`requested` reservation immediately before the wrapper; only that owner can call the runner. An unavailable,
halted, timeout, empty, or malformed response calls `record_work_dispatch_outcome` and atomically saves
`unavailable` before the current work verdict and next fix decision proceed unchanged. Never auto-dispatch.

When `/code-review` returns a selected finding with
`external_opinion.state=recommended`, treat it as a typed advisory recommendation, not prose to parse. In
attended mode, ask the same confirmation before acceptance. `/work` owns the full durable completion:
Claude validates every returned typed finding, records `keep`, `downgrade`, or `dismiss`, atomically writes
the enriched consumer artifact, then calls `complete_second_opinion` for the matching `available` and
`apply` transitions. Only Claude-owned final status/severity feeds the existing next-fix and verdict logic.

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
gate (Phase 3).

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

Before executing from a plan, confirm the plan cleared `/doc-review`. Use same-session review output or
the latest matching artifact under `docs/reviews/`. If `/doc-review` reported unresolved P0 or P1
findings, **block execution** unless the operator explicitly overrides and gives a rationale — record the
override rationale (it flows into the Phase-4 issue comment via `--doc-review-override`). Do not treat
chat memory alone as durable evidence after a resume.

### 1.4 Offer the backend, then mint/advance the saga

Offer the execution backend per `references/operator-choice.md` and the **runnable
`recommend_execution_backend()` CLI call** in `references/execution-strategy.md`: compute the
recommendation from the work shape, pre-select it, and render the offer from the full `backends`
enumeration — all three backends, each `{backend, status, note}` (overlap offers both as `alternative`,
and an unavailable ultracode entry is still named with its provenance note, never dropped), confirm with
the operator, and record what they picked via `--orchestration-mode`. Also pass
`--orchestration-recommended <the recommend_execution_backend() output>` so the tick records
recommended-vs-chosen on this decision (R12 override-rate telemetry); `orchestration_operator_choice`
auto-derives from `--orchestration-mode`, so the only added burden is naming the recommendation.

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

### 1.5 cc-workflows-ultracode: re-emit and run, or HALT

When `orchestration_mode == cc-workflows-ultracode`, the recorded backend choice **and** the saved spec
are the opt-in — ultracode mode is not required to launch a Workflow. `/work` does **not** hand-roll
sequential subagents as a substitute (that was the campps issue-38 failure: parallel + refute-N silently
dropped). It either runs the real Workflow tool or halts visibly.

**Re-emit for freshness (KD3).** Read the saga's `orchestration_ref` to locate the canonical spec JSON
the plan authored. Re-emit a fresh `.workflow.js` from it — any intermediate re-plan that changed the
spec is reflected:

```bash
python3 plugins/saga/scripts/execution_spec.py emit <orchestration_ref_spec.json> \
  -o docs/plans/<topic>.workflow.js
```

Then launch it:

```
Workflow({ scriptPath: "docs/plans/<topic>.workflow.js" })
```

The Workflow tool owns execution from this point. `/work` records the returned workflow id as
`orchestration_ref` via a saga tick:

```bash
python3 plugins/saga/scripts/saga.py save \
  --kind <issue|task> --id <...> \
  --orchestration-ref <workflow-id>
```

**HALT conditions.** If **either** of the following holds, `/work` MUST halt — never substitute with
hand-rolled serial subagents or any other inline fallback:

1. The **Workflow tool is genuinely absent** from this session (not found in the available tools).
2. The **spec or orchestration_ref is missing** from the saga (the plan did not author a spec, or the
   saga tick never recorded the ref).

On a HALT, surface the reason and one recovery line, e.g.:

- Workflow tool absent: "HALT — Workflow tool not available in this session. Recovery: resume in a
  Claude Code session where the Workflow tool is present, or ask the operator to switch the backend to
  `team-execution` or `inline`."
- Spec/ref missing: "HALT — saga `orchestration_ref` is empty or the spec file does not exist at
  `<path>`. Recovery: re-run `/plan` to author the spec and record the ref, then resume `/work`."

This is **explicitly not** the off-host recompile-down path (`recheck_orchestration_capability` in
`lifecycle_state.py`), which is reserved for `/loop` and `/resume`. A guarantee-bearing ultracode
choice halts rather than silently losing the parallel fan-out and refute-N verification (KD2/KTD6).

**Provenance guard.** `/work` NEVER writes `operator_choice` to record its own substitution. The
`saga.py` save guard rejects a tick that newly asserts `orchestration_mode != orchestration_operator_choice`
without an `orchestration_downgrade` note justifying that divergence — exactly the issue-38 shape (an AI
swap masquerading as the operator's pick). The guard is precise, not blunt: it is a no-op when no
`operator_choice` is asserted, and it lets an *unchanged* carry-forward of a prior, already-vetted
divergence through (its note was checked when that earlier tick saved). The only legitimate path is:
the operator picks a backend, `/work` records exactly that pick via `--orchestration-mode` (so
`orchestration_operator_choice` derives equal to it — no divergence), and a genuine capability degrade is
recorded as `orchestration_downgrade` WITH the divergence (operator-choice §6).

**Post-run manifest persistence (U4/KTD7).** A Workflow script has no filesystem access, so it cannot
write its own provenance manifest — the *driving session* (this `/work` run) is the producer of record
for `cc-workflows-ultracode` units. Once the Workflow returns, before moving on to Phase 2 wrap-up:

1. Collect the run's per-unit returned results into a JSON object mapping `unit_id -> result` (the same
   shape each unit returned to the Workflow — a dict of the unit's `returns` keys, a fan-out list, or
   `null`/absent for a prose-only leaf).
2. Persist one manifest per spec-declared unit:

   ```bash
   python3 plugins/saga/scripts/manifest_store.py --repo-root . --saga-id <saga-id> \
     record-completeness --spec <orchestration_ref_spec.json> --results <results.json>
   ```

3. A non-zero exit means at least one **contract-bearing** unit (a unit with a non-empty `returns` or an
   enumerated fan-out) tripped `missing-output` (R10) — every manifest is still written (the trip is
   reported, not silently dropped), so treat this like any other Phase 3 completeness finding: investigate
   the named unit before treating the round as PR-ready.
4. Team-execution runs follow the same CLI, called by the worker at exit per `references/*` in
   `team-execution` (U5) — `/work` does not additionally persist those on the worker's behalf.

---

## Phase 2 — Execute phase by phase

**When `orchestration_mode == cc-workflows-ultracode`:** Phase 1.5 already launched the Workflow tool.
The Workflow runtime owns execution; `/work` does not re-enter Phase 2 execution steps for those units.
Resume here only for post-workflow wrap-up (Phase 3 gate, Phase 4 record, Phase 5 PR-ready) once the
Workflow run returns.

Execute **one meaningful phase at a time** per `references/execution-strategy.md` (for `inline` and
`team-execution` modes, and for post-workflow Phase 2 wrap-up):

- **Execution strategy** — inline / serial subagents / parallel subagents, chosen from task count and
  dependency structure, gated by the **Parallel Safety Check** (file-to-unit overlap → worktree
  isolation, or downgrade to serial when isolation is unavailable). Subagent dispatch passes each unit's
  Goal / Files / Approach / Execution note / Patterns / Test scenarios / Verification and **preserves the
  U-ID**.
- **Follow existing patterns** — read the plan's referenced code first; match naming and conventions;
  grep for similar implementations before inventing.
- **Already shipped → verify, don't reimplement.** If a unit's `Verification` is already satisfied by the
  current code (shipped on a prior round/session), confirm it matches, mark it complete, and move on —
  do not silently reimplement.
- **Incremental commits** per logical unit (clean conventional messages, no attribution footers; the
  heuristic and commit-ownership-by-isolation-mode are in `references/execution-strategy.md`).
- **Simplify at phase boundaries** — review recently changed files for consolidation after a cluster of
  units, not after every single one.

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
key decisions, files modified, checks run, and the single next step. This is the canonical, durable home
(`handoff_envelope.py` classifies it resume-ready) — no new directory.

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
A passing test gate is `tests:done:<ref>`, a failure is `tests:failed:<ref>`, still-running is
`tests:in-progress:<ref>`; a non-canonical value (e.g. `pass`/`skip`) parses to *unknown* and the card
renders the Tests cell as not-reached, silently dropping the verdict.

List fields are full-snapshot (saga-spec §6) — pass the complete current set each tick, not a delta.

When a team-execution run stored Layer-2 artifacts (`artifact_pointer.py store`), record their typed
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
  --doc-review-override "<rationale if overridden>"
```

Record durable learnings/decisions in the engineering journal as they surface. `/work` **renders and
hands** the comment to `mission-control`; it does not file or mutate the issue itself.

### 4.4 Autonomous board progression — the shared reconcile controller (post-merge, #344/#450)

After a merge, drive the **allowlisted** post-merge board moves autonomously through the shared
**level-triggered reconcile controller** instead of prompting — the same reversibility contract and
idempotency ledger `/outcome` uses, now with the outside-drift detection `/work` previously lacked
(#450). For each move (Status → Done, then the sub-issue close), run a reconcile tick:

```bash
python3 plugins/saga/scripts/reconcile_controller.py reconcile \
  --op set-field-status --repo <owner/repo> --number <N> --target-state Done
python3 plugins/saga/scripts/reconcile_controller.py reconcile \
  --op sub-issue-close --repo <owner/repo> --number <N>
```

The controller composes the certificate-gated idempotency writer (`board_progression`, #344) with a
**level-triggered drift check**: every tick it re-reads the live board, so a rapid double tick
collapses to one write and an outside edit made while `/work` was at rest is re-detected. The CLI
prints a record JSON:

- `{"status":"written"}` / `{"status":"skipped"}` — the move fired (or was already applied) with
  **no operator prompt**.
- `{"status":"corrected"}` — an outside actor moved the saga-owned **Status** field while `/work` was
  at rest; the controller re-asserted the saga-derived value (reversible board-field drift, R5).
- `{"status":"halt", ...}` with a named `halt_reason` — an **irreversible** outside change (an issue
  reopened/closed under saga, an open/closed drift) that must NOT be silently overwritten. Surface
  the `halt_reason` to the operator and fall back to the operator-prompted `mission-control` path.
- `{"status":"gated"}` — which merge/deploy and any non-allowlisted op **always** return, because the
  allowlist lives in `reversibility_certificate`, not in the controller — fall back to the existing
  operator-prompted `mission-control` path unchanged. A `gated`/`halt` result is the controller
  correctly withholding an op that needs a human, never a failure.

`/work` still does **not** merge or deploy autonomously (permanently gated), and the controller never
widens the autonomously-writable set beyond what `board_progression`/`reversibility_certificate`
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

Read `/code-review`'s structured findings envelope (the programmatic shape — findings grouped by
`autofix_class`, verdict in the header). That envelope is the gate input. Record the review outcome (the
verdict, the P-level counts, and `REVIEWED_SHA`) in the Phase-4 work-session writeup; if you want a
durable artifact, persist the envelope through the evidence ledger (#398) —
`evidence_ledger.py write --check-id code-review --reviewed-sha "$REVIEWED_SHA" --producer work-gate
--verdict <the envelope's verdict> --artifact-file <envelope-text-file>` — rather than a bare file write,
so this programmatic-mode persistence gets the same no-clobber/custody guarantee as `/code-review`'s own
interactive-mode write (SKILL.md §5.3).

### 5.3 Hard review gate (block on P0/P1 or stale)

Block PR-ready when **either** holds (see `references/test-and-gates.md` for the full mechanism):

- **Unresolved P0 or P1 findings** in the code-review envelope, **or**
- a **stale** review — the code moved since `REVIEWED_SHA`. Compute it directly against the SHA `/work`
  captured at review time (no artifact parse):
  ```bash
  git rev-list <REVIEWED_SHA>..HEAD --count
  ```
  A count `> 0` means commits landed since the review → re-run `/code-review` (capturing a fresh
  `REVIEWED_SHA`) before any PR/merge offer.

Allow an explicit operator override only with a **recorded** rationale (it flows into the issue comment
via `--doc-review-override` / the work-session). Never a silent skip.

### 5.4 Reach PR-ready and present continuation routing

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
4. **Present continuation routing** and pause. On re-entry, Phase 0.4 reads the live PR state and runs the
   transition table in `references/pr-continuation-loop.md`. When destination ⊇ merge and the PR is
   approved + clean + fresh, **offer to run the rest of the ceremony** — four separate
   `ship_ceremony.py run` invocations, one transition each (#526): `run --operator-confirmed merge`,
   a bare `run` for `checkout_main`, a bare `run` for `pull`, then
   `run --operator-confirmed branch_delete` — each explicitly confirmed, never silent; merge is a
   git op `/work` owns under confirmation, `ship_ceremony.py` is the mechanism, not a new authority.
   On merge, set `phase_status=complete` and route to `/qa` **advisorily**.
   See `references/pr-continuation-loop.md` under "Merge-watcher and hazards" for safety contracts.
   When the destination includes deploy, route the merged item's ownership transfer through the
   offer step in `plugins/saga/skills/handoff/SKILL.md` ("Deploy edge") — `/work` does not accept
   the handoff itself.

At thread completion set `status=done`.

### 5.5 Hard boundary

`/work` builds, tests, gates, records, and coordinates the PR loop. It does **NOT** silently mutate
GitHub (PR-open, review-request, and merge are each explicitly confirmed; merge is a git op `/work` owns
only under confirmation). It does **NOT** own deploy or canary (`deploy` owns deployment
mutation and production-health revert). It does **NOT** file SDLC issues (`mission-control` owns issue
creation). It does **NOT** advance `lifecycle_phase` past `work` — the `qa` advance is deferred to the
`/qa` rebuild, so the saga legitimately sits at `work` post-merge and `/qa` routing is advisory. Build,
gate, record, coordinate the PR loop under confirmation — then stop.

---

## Reference files

- `references/execution-strategy.md` — CE complexity triage, task-list-from-U-IDs, the Execution-Strategy
  table, the Parallel Safety Check (overlap → worktree / shared-dir fallback / downgrade), subagent
  dispatch (U-ID preservation), the incremental-commit heuristic, already-shipped-verify, and the
  runnable `recommend_execution_backend()` integration. "How work gets executed."
- `references/test-and-gates.md` — test discovery, scenario completeness, the system-wide check,
  `requires_hard_test_gate` rules, merge-base-before-tests, the review-readiness gate (P0/P1 block + the
  computed staleness mechanism), override-with-recorded-rationale, and the gstack autonomy contract
  (stop-for / never-stop-for). "What must pass before PR-ready."
- `references/pr-continuation-loop.md` — the total PR-state transition table (the `gh pr view --json`
  reads, the per-state actions, round-bump via `rounds_seen`, merge-under-confirmation, and the
  qa/resume advisory routing + the qa-deferral). "How the round-N loop runs after PR-ready."
