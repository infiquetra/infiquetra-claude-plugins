# Phase 0 Autonomous Driver — Remainder (#344, #375, #379, #348, #401)

- **Date:** 2026-07-05
- **Status:** Active
- **Authorization:** Jeff, 2026-07-05 — "complete phase 0 without my intervention based on how
  we have completed the rest of phase 0." Opus / xhigh driver. Merge is durably authorized for all
  five named issues (same standing as #477/#478/#480 this session).
- **Backend authority (added 2026-07-05, Jeff AFK):** "You are approved to use the backend you
  recommend." The driver now CHOOSES the cheapest-correct backend per issue with no per-issue ask —
  default inline, escalate only when a specific issue's work-shape warrants it, and state the choice
  in the merge report. (#344 was decided inline by operator before this grant.)
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

- **Backend = driver's cheapest-correct choice** (Jeff granted full backend authority 2026-07-05,
  AFK). Default inline; escalate to team-execution / dynamic-workflows only when the work-shape
  warrants. No per-issue backend ask; state the choice in the merge report.
- **Squash-merge clean, green PRs** without asking (repo auto-merge rule; just-Jeff-and-Claude).
- **Small defects found mid-execution → fix inline, no filing** (e.g. this session's `head_sha`
  refresh + `Fixes #N` autoclose + `--saga-id` resolution). Note them in the PR body / journal.
- **Larger / structural defects → file** a `defect`-typed sub-issue of the owning Objective
  (#332–#343; fallback #337 fleet-integrity if it maps to none), place on the board with that
  Objective, then fix or defer per scope. Convention lives in the execution-order doc's
  "Defects found during execution" section.
- All durable writeback (execution-order tick, journal, work-session).

## Stop and ask — genuine fork ("not in the flow")

- **Novel architectural KTD inside `/plan`** with no obvious default that I *cannot* resolve from
  evidence (a real product-level fork, not a mechanical choice). A KTD resolvable from the code /
  documented principles is resolved and recorded, not paused on. (Backend is no longer a pause
  condition — see backend authority above. #348/#401 remain the likely escalation-*worthy* issues,
  but I choose and proceed.)
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

## #348 — IN PROGRESS (U1+U2 done, U3-U5 remain, 2026-07-05)

Branch `feat/pf-429-retry-primitive-348` (pushed, no PR). **Done + committed + green (160 tests):**
U1 — `plugins/fleet-core/scripts/fleet_commons/retry_backoff.py` (`retry_with_backoff` + `bridge_call`
+ `CircuitBreaker`, fault-injection tested); U2 — both unifi clients adopt `retry_with_backoff` on 429
(existing tests green + retry-count assertions), vendored `fleet_commons_shim` into both unifi client
dirs, registered in the drift-guard `VENDORED_SHIMS`. Plan + doc-review committed on the branch.
**RESUME at U3** (checkpoint taken to avoid delicate emitted-JS surgery under an exhausted context):
- **U3** — `execution_spec.py`: add `_JS_RETRY_HELPER` + wrap each `agent()` in the `parallel([...])`
  wave thunks (`_emit_thunk` 3 forms). **Watch the existing golden tests** that pin the current
  `agent(` emission shape — they will need updating. Compose with the existing `__gate` helper (retry
  the agent() call, then gate the successful result). Tests: `retry_on_429` (structural), golden.
- **U4** — `outcome.py advance()`/dispatch: a 429'd dispatch does NOT advance the leaf to `dispatched`;
  it stays derived `ready` and is re-picked; `retriable-pending` is a result LABEL, not a NODE_STATE
  (KTD4). Test: `retriable_pending`.
- **U5** — release surfaces: bump fleet-core, saga 0.58.0->0.59.0, unifi; regen marketplace; per-plugin
  CHANGELOG; drift-guard version literals; DECISIONS `{#shared-retry-backoff-primitive-348}`;
  execution-order row 9 tick; work-session. NOT agy (KTD2).

## #379 — DEFERRED (operator-gated, 2026-07-05)

**Status: NOT shipped — awaiting Jeff.** Grounding (Explore + direct grep, count 0) verified that
**redis-channel has no sender allowlist/access-policy** — it is deliberately router-agnostic
([[feedback_redis_channel_router_agnostic]]); `Consumer._dispatch` (`redis_consumer.py:159-194`)
delivers every inbound message with zero sender authorization, and `redis_channel_configure`
configures the router endpoint, not an allowlist. This makes **AC4** ("reject approval when not from
an access-policy-approved sender") rest on a false premise. Every resolution collides with a binding
constraint: adding allowlist code violates router-agnosticism; coupling to discord `access.json`
couples the gate to one transport; reframing AC4 to "defer access to the transport + record answerer
provenance" is correct but *contradicts the literal AC* and changes the security model. Because #379
is a remote-**approval** security feature, the pre-mortem (ship a feature that doesn't enforce the
sender-authorization it advertises → injection-driven approval + false sense of security) makes this a
genuine operator fork, not a resolve-from-evidence KTD. **Decision options for Jeff:** (a) reframe AC4
to defer-to-transport + record `answerer`/`transport` provenance (recommended — the only model
consistent with router-agnosticism); (b) build the heavier `gate_request`/`gate_verdict` stream-pair
mirroring the permission relay (`protocol.py:113/130`) AND decide where sender-auth lives; (c)
re-scope #379 to Discord-only with `access.json` as the auth source. Driver proceeded to #348/#401.

## Phase closeout (after #401 merges)

Final execution-order tick, a DECISIONS/LEARNINGS capture for the driver run itself, and a Phase 0
completion report. **Phase 1 (`/outcome start --from-objective 343` shakedown) requires explicit
new authorization — it is NOT auto-started by this driver.**
