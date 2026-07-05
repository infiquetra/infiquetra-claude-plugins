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

## #348 — DONE ✅ (SHIPPED 2026-07-05, PR #487)

Merged as squash `54d1361` (PR #487, `Fixes #348` → issue CLOSED/COMPLETED). saga 0.59.0, fleet-core
0.2.0, unifi 1.2.0. All 5 units shipped: U1 fleet-commons `retry_backoff` (retry + `CircuitBreaker` +
`bridge_call`); U2 both unifi clients adopt it (vendored shim, drift-guarded); U3 emitted-wave
`_JS_RETRY_HELPER` wrapping every `parallel([...])` thunk + panel verifier (singletons unwrapped by
design); U4 `/outcome` dispatch classifies a 429 as derived-on-read `retriable-pending`
(`AdvanceResult.retriable`, no committed NODE_STATE, no git/ledger mutation); U5 release surfaces +
DECISIONS `{#shared-retry-backoff-primitive-348}` (KTD1-KTD4) + execution-order row 9 + work-session.
Code-review CLEAN (0 findings, 4 adversarial readonly-verifiers). Two latent U1 lint issues fixed
inline (SIM102, N818). Backend: inline. agy untouched (KTD2). Full gate green (2035 tests).

## #379 — DONE ✅ (SHIPPED 2026-07-05, PR #488)

Merged as squash `cc46675` (PR #488, `Fixes #379` → issue CLOSED/COMPLETED; board Status→Done). saga
0.60.0, redis-channel 0.5.1. All 6 units shipped: U1 `approve_frontier` gains keyword-only
`answerer`/`transport` written into `approvals/r{rev}.json` only when supplied (terminal approval
byte-identical) + `outcome approve --answerer/--transport`; U2/U3 new stdlib-only decoupled
`outcome_gate_transport.py` (transport-agnostic `compose_gate_notice` + fail-closed `parse_gate_answer`
+ redis-only `emit_gate_notice` seam); U4 no-answer parity + disconnected fallback tests; U5 docs
(`operator-choice.md` §5.1 + `redis-channel/PROTOCOL.md`, router-agnostic); U6 release surfaces +
DECISIONS `{#remote-gate-approval-379}` (KTD1-KTD6) + execution-order row 8 + work-session.
Doc-review READY (4 safe fixes applied in-plan; P1 = Discord emit is session-driven). Code-review
CLEAN (0 findings, 4 adversarial readonly-verifiers; 1 fail-closed correctness edge — gate-id-token
verdict pollution — caught + fixed inline `392fd20` + re-verified). Backend inline. Full gate green
(2057 tests). Option A confirmed: sender-auth deferred to the transport (verified upstream-of-session
on both transports), provenance not a new allowlist; redis-channel stays router-agnostic (docs-only).

**Original (last-session) plan-ready note — kept as history.** Plan:
`docs/plans/2026-07-05-remote-gate-approval-379-plan.md` (6 units, KTD1-KTD6). Backend inline
(issue-recommended Sonnet/high; a mechanical two-plugin integration, not novel design). Merge durably
approved (carry like #344/#375/#348).

**GROUNDING CORRECTION (important — my last-session conclusion was WRONG).** Last session I concluded
"AC4 rests on a false premise → genuine operator fork." Re-grounding for the plan (full issue body +
Discord `server.ts` + `access.json`) shows that was an error: the two transports have **different**
access models. **Discord DOES enforce sender access** — `gate()` (`server.ts:236-294`) pre-filters
inbound to `allowFrom`, so the session physically never sees a non-approved sender; **redis-channel**
defers to its router (no in-plugin allowlist — that part was right). So AC4 ("reject non-allowlisted
sender, per `redis-channel-configure` / `discord:access`") is **satisfiable, not false**: option A
(*defer sender-auth to the transport + record provenance*) doesn't contradict AC4 — it **implements**
it. Jeff's option-A choice was correct and is simply "build the issue as specified." There is no real
security fork; the issue itself sizes this as Sonnet/high inline mechanical integration. Both transports
already ship a `request_id`-scoped permission-reply pattern (Discord `PERMISSION_REPLY_RE`
`server.ts:79/833`; redis `permission_request`/`permission_verdict` `protocol.py:113-138`) the
gate-answer mirrors so a channel message can never forge/escalate an approval. Full design in the plan.

**Original (last-session, now-superseded) grounding — kept as history.** Grounding (grep, count 0)
verified **redis-channel has no sender allowlist** — router-agnostic
([[feedback_redis_channel_router_agnostic]]); `Consumer._dispatch` (`redis_consumer.py:159-194`)
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

## #401 — DONE ✅ (SHIPPED 2026-07-05, PR #489)

Merged as squash `4ad193c` (PR #489, `Fixes #401` → issue CLOSED/COMPLETED; board Status→Done). saga
0.61.0. All 7 units shipped: U1/U2 new saga-local stdlib-only `run_ledger.py` (`run_fact.v1` schema,
hash-chained `append_fact`/`verify_chain`, derive-on-read `rollup`/`reuse_ratio`/`last_n_prior`); U3/U4
`engine_dispatch.dispatch(ledger=…)` writes an `engine` fact on any advisory call + a `delegation` fact
for an `agy.delegation.v1` call (telemetry only, no-op without a ledger, byte-identical returns); U5
`lifecycle_state.recommend_execution_backend(ledger=…)` ledger prior (byte-identical with no
ledger/data); U6 `references/run-fact-ledger.md` + DECISIONS `{#run-fact-ledger-401}` (KTD1-KTD7); U7
release surfaces + execution-order row 10. Doc-review READY (5 fixes in-plan; pinned U5 to the real
`recommend_execution_backend` surface + added the tamper-evidence-not-resistance bound). Code-review
CLEAN (0 code findings, 3 adversarial readonly-verifiers all UPHELD; the custody verifier tampered a
real on-disk ledger — mutation/reorder/middle-deletion all caught; one P3 plan-doc reference fixed).
Backend inline. Full gate green (2079 tests). No genuine fork surfaced (KTD1 saga-local resolved from
the manifest_store/outcome_store precedents — the "backend-fork candidate" flag did not fire).

## Phase closeout — PHASE 0 COMPLETE ✅ (2026-07-05)

**All 5 remaining Phase 0 items SHIPPED** — #344 (PR #485), #375 (PR #486), #348 (PR #487, `54d1361`),
#379 (PR #488, `cc46675`), #401 (PR #489, `4ad193c`). Execution-order rows 6–10 all `[x]`. Every item
carried the full contract: `/plan → /doc-review (fix all findings) → /work (inline) → programmatic
/code-review adversarial gate → squash-merge → close → board Done → journal/tick/work-session
writeback`, merge verified via authoritative `gh pr view`.

**Driver-run learnings (durable):**
- **The doc-review gate paid for itself every time.** Each issue's doc-review caught a real
  readiness gap before `/work`: #379's Discord-emit P1 (session-driven vs redis-only), #401's U5
  surface (un-testable prose tier-table → the real `recommend_execution_backend` function) + the
  honest tamper-evidence bound. Grounding file:line anchors against the *current* tree (not the
  issue's authoring-time snapshot) mattered — #348/#379 had shifted `outcome.py` lines.
- **Adversarial code-review that runs real falsification beats a checklist.** The refute-N
  readonly-verifier panels executed the emitted JS (#379) and tampered on-disk ledgers (#401), catching
  a fail-closed correctness edge (#379 gate-id-token pollution) and confirming the #401 custody bound is
  *honestly documented*, not over-claimed.
- **The `Fixes #N` autoclose footgun** (a reference-only commit with a closing keyword) bit #379 once;
  the fix is bare `#N` in reference commits, `Fixes #N` only in the PR body — held for #401.
- **Commit-before-verify** held throughout (a verify agent's `git checkout` can clobber uncommitted work).

**Phase 1 (`/outcome start --from-objective 343` shakedown) requires explicit new authorization — it is
NOT auto-started by this driver.** The engine now has all its Phase 0 primitives (board writer, DAG
seeding, remote gates, shared 429 retry, run-fact ledger) to run its own machinery.
