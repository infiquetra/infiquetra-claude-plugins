# Execution Strategy — how work gets executed

How `/work` sizes a build, turns a plan into a task list, picks an execution strategy, dispatches
subagents safely, commits incrementally, and recommends an execution backend. Adapted from CE
`ce-work`'s execution mechanics; the backend recommendation lands the deferred operator-choice helper.

## Complexity triage (Phase 0.5)

For a fresh build (no `pr_refs` on the saga), size the run before executing:

| Complexity | Signals | Action |
|---|---|---|
| **Trivial** | 1-2 files, no behavioral change (typo, config, rename) | Implement directly — no task list, no execution loop. Still apply Test Discovery if the change touches behavior-bearing code. |
| **Small / Medium** | Clear scope, under ~10 files | Build a task list from the plan's Implementation Units, then execute the loop. |
| **Large** | Cross-cutting, architectural decisions, 10+ files, touches auth/payments/migrations | If it arrived as a bare prompt, recommend `/plan` first to surface edge cases and scope boundaries; honor the operator's choice. If proceeding, build the task list and continue. |

A plan-doc input has already been through `/plan` and `/doc-review`, so it skips the bare-prompt bounce —
the triage here only sizes the execution strategy.

## Task list from U-IDs

Build the task list from the plan's `Implementation Units`. **Preserve each unit's U-ID as a task-subject
prefix** (e.g. "U3: add parser coverage"). This keeps blocker references, deferred-work notes, and the
final summary anchored to the same identifier the plan and the saga use, so traceability survives plan
edits and round bumps.

For each unit, carry:

- the **Goal** and **Approach** (what to build, how the plan framed it),
- the **Files** section (Create / Modify / Test paths — also feeds the Parallel Safety Check),
- the **Execution note** (test-first / characterization-first posture, when present),
- the **Patterns to follow** (specific files/conventions to mirror — read them before implementing),
- the **Verification** field (the primary "done" signal; also the already-shipped check),
- the **Test scenarios** (the starting point for Phase-3 scenario completeness).

Order tasks by dependency. Include test and quality-check tasks. Do not expect the plan to contain
implementation code, micro-step TDD instructions, or exact shell commands — the plan is decisions, not a
script. Do not re-scope plan units into human-time phases; agents execute at agent speed, and
context-window pressure is handled by subagent dispatch below, not by phased sessions.

## Execution-Strategy table

After the task list, pick how to execute from task count and dependency structure:

| Strategy | When to use |
|---|---|
| **Inline** | 1-2 small tasks, or tasks needing operator interaction mid-flight. The default for trivial and small builds. |
| **Serial subagents** | 3+ tasks with dependencies. Each subagent gets a fresh context window focused on one unit — prevents context degradation across many tasks. Requires plan-unit metadata. |
| **Parallel subagents** | 3+ tasks that pass the Parallel Safety Check below. Dispatch independent units simultaneously; run dependent units after their prerequisites complete. Requires plan-unit metadata. |

This strategy choice (inline / serial / parallel **subagent dispatch**) is the *mechanical* "how do I run
the units" decision and is independent of the **backend** choice below (`inline` / `team-execution` /
`cc-workflows-ultracode`), which is the operator-choice contract for *which runtime owns the work*.

## Parallel Safety Check (required before parallel dispatch)

1. Build a **file-to-unit mapping** from every candidate unit's `Files:` section (Create, Modify, Test).
2. Check for **intersection** — any file path appearing in 2+ units is an overlap.
3. **Overlap AND worktree isolation unavailable** → downgrade to serial subagents. Log the reason
   ("Units 2 and 4 share `config/routes.py` — using serial dispatch"). Serial still gives context-window
   isolation without shared-directory write races.
4. **Overlap AND worktree isolation available** → parallel is still safe; the overlap surfaces as a
   predictable merge conflict the orchestrator resolves in the post-batch merge. Log the predicted
   overlap so the post-batch flow knows which merges to expect conflicts on.

Even with no file overlap, parallel subagents sharing the orchestrator's working directory face git index
contention and test interference. Worktree isolation eliminates both; the shared-directory fallback
constraints below mitigate them.

## Subagent dispatch (U-ID preservation)

Use the generic `Explore` / `Task` agents (this plugin has no `agents/` dir — do **not** reference named
`ce-*` agents). For each unit, give the subagent: the full plan path (overall context), the unit's Goal /
Files / Approach / Execution note / Patterns / Test scenarios / Verification, any resolved
deferred-implementation questions, and the instruction to check the unit's test scenarios against all
four applicable categories (happy / edge / error / integration) and supplement gaps. **Preserve the
U-ID** in the dispatch and in everything the subagent reports back.

- **Worktree-isolated:** subagents may stage, commit, and run their unit's tests inside their own worktree
  branch. After the batch, merge those branches in dependency order; on a merge conflict, abort
  (`git merge --abort`) and re-dispatch that unit serially against the merged tree (never hand-resolve
  silently — that discards one unit's intent). Then clean up: unlock, `git worktree remove`, `git branch
  -d`.
- **Shared-directory fallback:** instruct each subagent **not** to `git add`, commit, or run the project
  suite — the orchestrator handles staging/testing/committing after the whole batch completes. Cross-check
  the *actual* files each subagent modified (not just declared `Files:`); a shared-file collision means
  only the last writer survived — commit non-colliding files first, then re-run the colliding units
  serially.

Omit the `mode` parameter when dispatching so the operator's permission settings apply (do not pass
`mode: "auto"`).

## Incremental-commit heuristic

After each logical unit, decide whether to commit:

| Commit when… | Don't commit when… |
|---|---|
| A logical unit is complete (model, service, component) | It's a small part of a larger unit |
| Tests pass + meaningful progress | Tests are failing |
| About to switch contexts (backend → frontend) | Purely scaffolding with no behavior |
| About to attempt a risky/uncertain change | The message would be "WIP" or "partial X" |

**Heuristic:** "Can I write a commit message describing a complete, valuable change? If yes, commit. If
it would be 'WIP', wait." Use the plan's Implementation Units as a starting guide for commit boundaries,
adapting to what you find. Stage only the files for that logical unit (not `git add .`). Use clean
conventional messages with **no attribution footers**.

## Already shipped → verify, don't reimplement

Before implementing a unit, check whether its work is already present and matches the plan's intent —
files exist with the expected capability, or the unit's `Verification` is already satisfied. If so, the
work likely shipped on a prior branch/round/session. **Verify it matches, mark the task complete, and
move on. Do not silently reimplement.** This matters most on round-N re-entry, where earlier rounds
already landed some units.

## Backend recommendation — `recommend_execution_backend()` (Phase 1.4)

`/work` lands the deferred operator-choice helper (operator-choice §7). Compute the cheapest-correct
backend, pre-select it, and surface the alternatives so escalation is one keystroke. Call the CLI:

```bash
python3 plugins/saga/scripts/lifecycle_state.py recommend-backend \
  --file-count <N> --phase-count <N> \
  [--has-security] [--has-infra] [--cross-repo] [--deployment-sensitive] \
  [--needs-consensus] [--broad-fanout] [--no-workflow]
```

It returns JSON: `{recommended, rationale, alternatives, omit_ultracode}`. The recommendation reuses
`should_offer_team_execution`'s thresholds (file_count ≥ 8, phase_count ≥ 4, security, infra, cross-repo,
deployment-sensitive) **or** a needs-consensus signal for `team-execution`; broad-independent-fanout
without elevated risk for `cc-workflows-ultracode`; `inline` otherwise. `alternatives` lists every
reachable backend **independent of which one won precedence**, so an overlap job (consensus AND
fan-out) still offers both — escalation stays one step (operator-choice §3.3).

Surface the recommendation with `AskUserQuestion` (or channel-inline) pre-selecting `recommended`,
listing `alternatives`. **Omit `cc-workflows-ultracode`** from the offer when `omit_ultracode` is true
(pass `--no-workflow` when the Workflow tool is observably absent this session — operator-choice §4). If
the operator picks `cc-workflows-ultracode` but it turns out unavailable, fall back to `team-execution`
or `inline` with a one-line note. Record the operator's pick via the saga's `--orchestration-mode`
(Phase 1.4) — that is the durable home for the choice (operator-choice §6).
