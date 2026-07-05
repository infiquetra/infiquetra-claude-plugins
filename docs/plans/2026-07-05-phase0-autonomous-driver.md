# Phase 0 Autonomous Driver — Remainder (#344, #375, #379, #348, #401)

- **Date:** 2026-07-05
- **Status:** Active
- **Authorization:** Jeff, 2026-07-05 — "complete phase 0 without my intervention based on how
  we have completed the rest of phase 0." Opus / xhigh driver. Merge is durably authorized for all
  five named issues (same standing as #477/#478/#480 this session).
- **Companion:** [execution-order doc](2026-07-04-plugin-fleet-execution-order.md) (sequences),
  [issue plan](2026-07-04-plugin-fleet-issue-plan.md) (defines Gate E). This doc is the *driver
  contract* — it survives compaction so any continuation session resumes the run faithfully.

## Mode

Sequential, single main-loop session (Opus, xhigh). **No parallelism, no `/outcome` DAG** — #344,
#375, #379 rebuild `/outcome`'s own machinery, so a coordinator would run on gears it is replacing.
One issue is carried fully to MERGED before the next begins. The 2-lane schedule was analyzed and
set aside: Jeff chose sequential; it also sidesteps the one same-file overlap (`outcome.py` between
#375 and #348) with zero coordination cost.

## Order (execution-order checklist rows 6–10)

| # | Issue | Slug | Note |
|---|---|---|---|
| 1 | #344 | pf-board-progression-shared-writer | Board writer; **producer** — land before #375 (which soft-consumes its board API). |
| 2 | #375 | pf-outcome-from-objective-ingestion | Seeds the DAG. Shares `outcome.py` with #348 → sequential makes this a non-issue. |
| 3 | #379 | pf-remote-gate-approval | redis-channel transport; most surface-disjoint of the five. |
| 4 | #348 | pf-429-retry-primitive | Cross-plugin (saga + unifi×2 + agy). **BACKEND-FORK CANDIDATE.** |
| 5 | #401 | pf-run-fact-ledger | New substrate, 8+ downstream writers. **BACKEND-FORK CANDIDATE.** |

## Per-issue lifecycle (each iteration)

```
/plan issue N  →  /doc-review the plan  →  fix ALL findings in place  →
/work N (backend = inline)  →  ship-ceremony to MERGED (gh pr view confirms)  →
close issue  →  tick execution-order checklist row [x] IN THE SAME PR  →
engineering-journal + docs/work-sessions writeback in the same commit  →
verify origin/main state  →  report to Jeff  →  next issue
```

## Pre-authorized — proceed silently ("in the flow")

- **Backend = inline** (what every recent Phase 0 issue used).
- **Squash-merge clean, green PRs** without asking (repo auto-merge rule; just-Jeff-and-Claude).
- **Small defects found mid-execution → fix inline, no filing** (e.g. this session's `head_sha`
  refresh + `Fixes #N` autoclose + `--saga-id` resolution). Note them in the PR body / journal.
- **Larger / structural defects → file** a `defect`-typed sub-issue of the owning Objective
  (#332–#343; fallback #337 fleet-integrity if it maps to none), place on the board with that
  Objective, then fix or defer per scope. Convention lives in the execution-order doc's
  "Defects found during execution" section.
- All durable writeback (execution-order tick, journal, work-session).

## Stop and ask — genuine fork ("not in the flow")

- **Backend fork:** an issue where inline is the *wrong* call. Watch **#348** and **#401** (cross-
  plugin / new-substrate blast radius). Ask once, then proceed on the answer.
- **Novel architectural KTD inside `/plan`** with no obvious default (a real design fork, not a
  mechanical choice).
- **CI red that isn't a quick fix**, or a merge that won't go green.
- **Destructive / irreversible op beyond the normal ship ceremony.**

## Guardrails

- **Report after every merge** (diff summary + what shipped). The chain is autonomous, not
  unsupervised — Jeff can halt at any checkpoint. Error-compounding across the producer→consumer
  edges (#344→#375 board API; #375→#348 `outcome.py`) is the main risk; producer-before-consumer
  ordering is already honored above.
- **Verify/review spawns outside a saga skill** use `subagent_type: saga:readonly-verifier` +
  `isolation: "worktree"` (CLAUDE.md; fallback ladder in saga sandbox-spawn-sites reference).
- **Exclude `.serena/project.yml`** from every commit (pre-existing unrelated local mod).
- **Verify merge via `gh pr view`** (authoritative), never local git ancestry. Unlock the macOS
  keychain (`security -v unlock-keychain`) on a 401.
- Release surfaces updated in the same PR every time (#429 single-source makes marketplace.json
  generated — bump plugin.json, regenerate, CHANGELOG grammar `## [X.Y.Z] - YYYY-MM-DD`).

## Phase closeout (after #401 merges)

Final execution-order tick, a DECISIONS/LEARNINGS capture for the driver run itself, and a Phase 0
completion report. **Phase 1 (`/outcome start --from-objective 343` shakedown) requires explicit
new authorization — it is NOT auto-started by this driver.**
