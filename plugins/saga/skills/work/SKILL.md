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
   with `recommend_execution_backend()`, pre-select it, and always surface the alternatives so
   escalation is one keystroke (operator-choice §2). The recorded value is what the operator picked.
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
recommendation from the work shape, pre-select it, surface the alternatives (overlap offers both),
confirm with the operator, and record what they picked via `--orchestration-mode`.

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
  --rounds-seen "1"
```

`--id` is the only strictly required flag (`--kind` defaults to `issue`); for ad-hoc `task` work pass
`--kind task --id <slug>` and omit `--issue-ref` (then `--plan-path` + the on-branch save are the match
keys). `save` mints unconditionally (correct here — `/work` is the minter), and when Phase 0.3 matched it
appends a tick to the existing directory rather than forking. Never `git add` the tick (saga state is
git-ignored, machine-local). Never set `next_round` — it is derived from `rounds_seen` (saga-spec §6.1).

---

## Phase 2 — Execute phase by phase

Execute **one meaningful phase at a time** per `references/execution-strategy.md`:

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
  --next-step "<the one imperative resume anchor>"
```

List fields are full-snapshot (saga-spec §6) — pass the complete current set each tick, not a delta.

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
verdict, the P-level counts, and `REVIEWED_SHA`) in the Phase-4 work-session writeup; persist the envelope
under `docs/code-reviews/` if you want a durable artifact and reference it from the work-session.

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

1. **Offer to open the PR + request review** (`gh pr create` + reviewer request) — outward-facing,
   **offered/confirmed, never auto-fired**. If the operator declines auto-open, hand them the prepared
   PR body (links the plan, work-sessions, and the code-review artifact) + branch.
2. **Record `pr_refs`** in the saga and set `next_step="await review on PR #N"`; comment the PR status to
   the issue via the extended `issue_progress.py` CLI (`--pr-url`, `--review-status`).
3. **Present continuation routing** and pause. On re-entry, Phase 0.4 reads the live PR state and runs the
   transition table in `references/pr-continuation-loop.md`. When destination ⊇ merge and the PR is
   approved + clean + fresh, **offer `gh pr merge`** (explicitly confirmed) — merge is a git op `/work`
   owns under confirmation. On merge, set `phase_status=complete` and route to `/qa` **advisorily**.

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
