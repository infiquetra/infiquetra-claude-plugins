# Plugin-Fleet Execution Order (Program Plan of Attack)

- **Date:** 2026-07-04
- **Status:** Adopted 2026-07-04 — Phase 0 executes serially via /plan → /work (see
  Execution mode); /outcome adoption deferred to Phase 1
- **Scope:** Ordering and dependency plan for completing the 12 `improve-claude-plugins`
  Objectives (#332–#343, Operations board) and their 126 sub-issues
- **Companion:** [Gate E issue plan](2026-07-04-plugin-fleet-issue-plan.md) — waves,
  tiers, executor profiles, provenance. This document sequences; that document defines.

## Thesis

Run the program on its own products. Ten of the 126 issues are *program accelerators* —
they multiply the throughput, cost-efficiency, or measurability of the other ~116.
Pull those forward as a bootstrap slice (Phase 0), then execute the objectives in a
dependency-honoring order. Five of the ten are hoisted out of wave-2 objectives; the
Gate E wave assignments are otherwise preserved.

## Phase 0 — Program bootstrap (10 issues, pulled across objectives)

Ordered; edges noted. Everything below multiplies across the remaining ~116 issues.

| # | Issue | Home objective | Why it goes first |
|---|---|---|---|
| 1 | #461 freeze the before picture (baseline pain metrics) | #338 telemetry (wave-2) | Must precede *any* change or every "measured win" claim in the program is unfalsifiable. Cheap (sonnet/low, context-update). |
| 2 | #399 rubber-stamp telemetry (gate decisions vs recommendations) | #338 telemetry (wave-2) | Trivial; value comes from accumulation time. Every gate decision from day one becomes calibration data for the intent-envelope and consensus work. |
| 3 | #463 name the import mechanism (fleet commons decision) | #341 single-source (wave-2) | A decision, not a build (opus/medium exploration). Gates the *form* of every "one shared X" primitive wave-1 builds: #348 retry, #370 tier_vocab, #357 liveness, #411 consensus kernel. Deciding it late means rebuilding wave-1 primitives in wave-2. |
| 4 | #345 ship_ceremony.py | #340 ship ceremony (wave-1) | Every one of the remaining issues ships through it. Payoff is ~120×. |
| 5 | #429 single-source release surfaces (marketplace.json generated, tri-lock parity) | #337 fleet integrity (wave-2) | Every PR in this repo touches plugin.json + marketplace.json + CHANGELOG. With ~120 PRs coming, this is the standing merge-conflict hotspot and per-PR friction tax. Kill it now. |
| 6 | #344 board_progression.py (certificate-gated status writer) | #332 intent envelope (wave-1) | 126 issues × several status moves each, autonomously written instead of hand-moved. Also a consumer contract for /outcome. |
| 7 | #375 /outcome start --from-objective | #332 intent envelope (wave-1) | The program's own steering wheel: each remaining objective becomes a seeded /outcome DAG instead of a hand-built one. Bootstrap irony noted and embraced. |
| 8 | #379 remote gate approval (redis-channel/Discord) | #332 intent envelope (wave-1) | Multi-session, async continuation is the operating mode for this program. Gates answered from anywhere keep runs moving between sessions. |
| 9 | #348 shared 429 retry/backoff primitive | #335 concurrency (wave-1) | Protects every fan-out in the program from rate-limit carnage. Follows #463 so its packaging conforms to the commons decision. |
| 10 | #401 run-fact ledger substrate | #338 telemetry (wave-2) | At least eight wave-1 issues write ledger-shaped data (#349 requeue, #351 spawn-settle, #366/#367 spend, #386 net-savings, #393 reconciliation…). Land the substrate/contract first or wave-2 inherits N incompatible formats to reconcile. Follows #463. |

Internal Phase 0 DAG: #461, #399 immediately and independently; #463 before #348/#401;
#345, #429, #344, #375, #379 mutually independent.

## Objective order (Phases 1–7)

Counts are *remaining* issues after Phase 0 hoists. "Lane" marks objectives safe to run
concurrently (disjoint plugin surfaces) — never more than two objectives in flight.

| Phase | Objective | Remaining | Rationale |
|---|---|---|---|
| 1 | #343 tier+effort lever | 9 | Smallest enabling substrate. 39 team-execution executor profiles carry Effort lines that are **inert** until #363 effort-first-class + #362 dispatch resolver land (known Gate E finding). #370 models.json pricing feeds external-engine economics, spend budgets, and agent-file lint. Nothing else executes at its declared posture until this ships. |
| 2 | #335 concurrency governance | 10 | Protects all subsequent fan-outs: admission governor, lease broker, settlement, orphan fencing. #348 already landed (Phase 0). The teardown/lease machinery (#356) is shared with ship-teardown (#347) — build here, consume there. |
| 3a | #332 intent envelope | 11 | Autonomy posture consumed by every gate; raises autonomous throughput for the rest of the program. #449 envelope-authorized merge goes **last** within the objective — it needs #371 durable gate records, #344 board progression, and #399 telemetry history to be trustworthy. |
| 3b (lane) | #340 ship ceremony remainder | 4 | #346 preflight/undo, #347 teardown reconciliation (consumes #356 leases), #395 positive handoff, #434 stacked-PR guard (moonshot, last). Hardens the Phase 0 primitive while 3a runs — different surfaces (deploy/ceremony vs saga/outcome). |
| 4a | #333 cache economics | 6 | Cost reduction applied to all remaining fan-outs. #438 cross-leaf crew (moonshot) depends on #356 leases (Phase 2) and the /outcome DAG. #467 warm-reuse benchmark proves the claim against the #461 baseline. |
| 4b (lane) | #336 external-engine lane | 20 | Biggest objective. Consumes #370 pricing (Phase 1), #348 circuit breaker, #401 receipt substrate. Order inside: registry schema + bridge + attestation + no-silent-fallback (#452/#387/#388/#390) before economics (#386) and routing (#391); #468 zero-token fire drill is the exit criterion for the whole lane. ext:offload issues elsewhere (#432, #402) prefer this landing first. |
| 5 | #338 telemetry remainder | 7 | Spend observability (#402) now has weeks of wave-1 ledger data to report on. #462 panel economics exploration feeds #412 consensus thresholds in Phase 6. |
| 6a | #341 single-source | 13 | Commons decision (#463) long since made; consensus kernel, vocab collapse, parity registry. **A1 follow-on:** after #415 execution-substrate decoupling ships, run the backend re-triage of the 39 team-execution drafts against the chooser rubric — remaining objectives may flip backends. |
| 6b (lane) | #337 fleet integrity remainder | 14 | #422 agent-file lint needs the effort field (Phase 1). #465 fleet review campaign (ultracode, expensive) runs once the fleet has absorbed wave-1 churn — reviewing surfaces that are about to be rewritten wastes it. |
| 7a | #342 standards enforcement | 7 | Wave-2 tail. Touches infiquetra-context-library as much as this repo; #403 lens catalog coordinates with #418 lens registry from 6a. |
| 7b (lane) | #339 self-improving backlog | 10 | Needs the ledger (mining, session registry) and promote machinery mature. #440 ideate foldback captures this very program's architecture. |
| 8 | #334 capability breadth | 5 | Explicitly "rides on wave-1/2 substrates" per its mission. #469 dark-plugin parity verdict extends the fleet — do it when the fleet's standards are enforceable (post Phase 7a). |

## Cross-objective dependency edges (the ones that bite)

- **#463 → every shared primitive** (#348, #370, #357, #411, #401 packaging): the import
  mechanism decision shapes them all. This is the single biggest rework risk if skipped.
- **#370/#362/#363 → 39 executor profiles, #386, #366, #391, #422**: pricing and effort
  are upstream of offload economics, spend budgets, task routing, and agent-file lint.
- **#401 → #349, #351, #366, #367, #386, #393, #402, #445, #459**: one ledger contract
  under eight-plus writers.
- **#356 (lease broker) → #347 (ship teardown), #438 (cross-leaf crew)**: teardown and
  residency both lease.
- **#371 + #344 + #399 history → #449 (envelope-authorized merge)**: autonomous merge is
  earned, not assumed.
- **#462 (panel economics) → #412 (consensus thresholds)**: measure before setting policy.
- **#415 → A1 backend re-triage** of all not-yet-executed team-execution drafts.
- **#375 → program meta-loop**: every objective after Phase 0 starts as
  `/outcome start --from-objective`.

## Deviations from Gate E wave order

Five hoists, all wave-2 → Phase 0: #461, #399, #401 (telemetry), #463 (single-source),
#429 (fleet integrity). Rationale is in the Phase 0 table; everything else preserves
Gate E waves. No issues are re-scoped, only re-sequenced.

## Execution mode (confirmed by operator 2026-07-04)

Phase 0 executes **serially, one issue per session, via /plan → /work** — no outcome DAG.
Rationale: the Phase 0 frontier is almost always one leaf wide; three of its issues
rebuild /outcome's own machinery (#344, #375, #379), so a coordinator would be running on
gears being replaced under it; and one-issue-per-session makes the session model the
executor model, dissolving the dispatch-seam inheritance problem for this phase.

**/outcome adoption begins at Phase 1**: `/outcome start --from-objective 343`
(tier+effort) is the first real outcome run — a deliberate shakedown of the freshly
shipped #375 seeding, #344 board progression, and #379 remote gates on a mid-size
objective. The switch criterion is "the tooling is genuinely ready", not the calendar —
if Phase 0 shows /outcome needs one more ergonomic piece (e.g. #377 intent-capture),
ship it before switching. From Phase 1 on the original mapping holds: one outcome per
objective, at most two lane-paired objectives in flight, never one 126-leaf DAG.

## Phase 0 checklist

Program-level state lives here, not in a coordinator. Tick each row **in the same PR
that ships it** — the /work closeout owns the tick. Session tier is the Gate E executor
profile (model/effort); the `.json` sidecar carries authoritative backend detail.

| # | Issue | Slug | Session tier | Upstream edges | Shipped |
|---|---|---|---|---|---|
| 1 | #461 | pf-fleet-baseline-metrics | sonnet/low | none — must ship before any other Phase 0 change | [ ] |
| 2 | #399 | pf-gate-divergence-telemetry | sonnet/low | none | [ ] |
| 3 | #463 | pf-fleet-commons-decision | opus/medium | none (blocks items 9–10) | [ ] |
| 4 | #345 | pf-ship-ceremony-primitive | sonnet/high | none | [ ] |
| 5 | #429 | pf-release-surface-single-source | sonnet/high | none | [ ] |
| 6 | #344 | pf-board-progression-shared-writer | sonnet/high | none | [ ] |
| 7 | #375 | pf-outcome-from-objective-ingestion | sonnet/high | none | [ ] |
| 8 | #379 | pf-remote-gate-approval | sonnet/high | none | [ ] |
| 9 | #348 | pf-429-retry-primitive | sonnet/high | #463 merged | [ ] |
| 10 | #401 | pf-run-fact-ledger | sonnet/high | #463 merged | [ ] |

## Shared kickoff contract (every per-issue prompt points here)

A /plan session kicked off with one of the prompts below MUST:

1. **Read the inputs.** This document (checklist, edges, model posture), the GitHub
   issue, and the Gate E draft `docs/sdlc-issue-drafts/plugin-fleet/<slug>.md` plus its
   `.json` sidecar as the requirements source.
2. **Preflight — verify live, don't assume.** The row's upstream edges are *merged*
   (PR merged, not branch-exists); earlier checklist rows are ticked or explicitly
   waived by the operator in this session; the session model matches the row's tier —
   on mismatch, flag it and stop rather than silently proceeding.
3. **Board hygiene at plan start.** Move the issue out of Idea to the board's active
   status via mission-control. Discover the Status vocabulary live — do not hardcode
   option names (that hardcoding habit is literally defect #424 in this program).
4. **Scope guard.** Plan exactly what the draft body specifies — do not absorb
   downstream Phase 0 items. Where the work packages a shared primitive, conform to the
   #463 commons decision once row 3 is shipped.
5. **Put the closeout in the plan** so /work executes it, not the operator: release
   surfaces updated in the same PR (plugin.json, marketplace.json, CHANGELOG,
   drift-guard tests); this issue's checklist row ticked in this document in the same
   PR; board status advanced at ship; engineering-journal capture in the same commit
   when the work yields a durable learning or decision.

## Per-issue kickoff prompts

Start a fresh session at the row's tier, run `/plan`, paste the matching block verbatim.
Each prompt delegates the details to the shared kickoff contract above, so the contract
stays maintained in one place.

**Item 1:**
> Phase 0 item 1 of 10 — issue #461, slug pf-fleet-baseline-metrics. Execute the shared
> kickoff contract in docs/plans/2026-07-04-plugin-fleet-execution-order.md. Expected
> session tier sonnet/low. Upstream edges: none, but this item must ship before any
> other Phase 0 change lands — it freezes the before-picture baseline.

**Item 2:**
> Phase 0 item 2 of 10 — issue #399, slug pf-gate-divergence-telemetry. Execute the
> shared kickoff contract in docs/plans/2026-07-04-plugin-fleet-execution-order.md.
> Expected session tier sonnet/low. Upstream edges: none.

**Item 3:**
> Phase 0 item 3 of 10 — issue #463, slug pf-fleet-commons-decision. Execute the shared
> kickoff contract in docs/plans/2026-07-04-plugin-fleet-execution-order.md. Expected
> session tier opus/medium; profile carries an external second-opinion seat. Upstream
> edges: none. Note: this is an exploration issue whose deliverable is a decision —
> items 9 and 10 block on its outcome, so drive it to a recorded decision, not a build.

**Item 4:**
> Phase 0 item 4 of 10 — issue #345, slug pf-ship-ceremony-primitive. Execute the shared
> kickoff contract in docs/plans/2026-07-04-plugin-fleet-execution-order.md. Expected
> session tier sonnet/high. Upstream edges: none.

**Item 5:**
> Phase 0 item 5 of 10 — issue #429, slug pf-release-surface-single-source. Execute the
> shared kickoff contract in docs/plans/2026-07-04-plugin-fleet-execution-order.md.
> Expected session tier sonnet/high. Upstream edges: none. Note: every subsequent PR in
> this program benefits — favor landing it whole over splitting.

**Item 6:**
> Phase 0 item 6 of 10 — issue #344, slug pf-board-progression-shared-writer. Execute
> the shared kickoff contract in docs/plans/2026-07-04-plugin-fleet-execution-order.md.
> Expected session tier sonnet/high. Upstream edges: none. Note: once this ships, the
> board-hygiene step of the contract can be delegated to board_progression.py — update
> the contract text in the same PR if so.

**Item 7:**
> Phase 0 item 7 of 10 — issue #375, slug pf-outcome-from-objective-ingestion. Execute
> the shared kickoff contract in docs/plans/2026-07-04-plugin-fleet-execution-order.md.
> Expected session tier sonnet/high. Upstream edges: none. Note: this is the feature the
> Phase 1 /outcome switch depends on — acceptance should include a dry-run seed against
> objective #343.

**Item 8:**
> Phase 0 item 8 of 10 — issue #379, slug pf-remote-gate-approval. Execute the shared
> kickoff contract in docs/plans/2026-07-04-plugin-fleet-execution-order.md. Expected
> session tier sonnet/high. Upstream edges: none.

**Item 9:**
> Phase 0 item 9 of 10 — issue #348, slug pf-429-retry-primitive. Execute the shared
> kickoff contract in docs/plans/2026-07-04-plugin-fleet-execution-order.md. Expected
> session tier sonnet/high. Upstream edges: #463 must be merged — the primitive's
> packaging must conform to the recorded commons decision; verify it before planning.

**Item 10:**
> Phase 0 item 10 of 10 — issue #401, slug pf-run-fact-ledger. Execute the shared
> kickoff contract in docs/plans/2026-07-04-plugin-fleet-execution-order.md. Expected
> session tier sonnet/high. Upstream edges: #463 must be merged — the ledger's packaging
> must conform to the recorded commons decision; verify it before planning. Note: at
> least eight wave-1 issues will write to this ledger's contract — treat the record
> schema as the deliverable's load-bearing surface.

## Model posture until the tier resolver exists

There is no machinery today that reads the Gate E executor profiles — `/outcome` has no
model logic (verified 2026-07-04: zero model/effort references in the outcome skill);
that machinery *is* #362/#363, Phase 1. Until then, model selection at dispatch is pure
inheritance mechanics:

| Dispatch seam | Model used today |
|---|---|
| inline leaf | the coordinator session's model |
| fork | the session's model, always — a fork ignores model overrides |
| subagent | session model, unless the Agent call passes `model:` or the agent's `.md` pins one |
| team-execution | safe — all 25 agents pin their own model in frontmatter (7 haiku / 10 opus / 8 sonnet) |
| effort (all seams) | inert — Agent tool has no per-call effort param; only Workflow `agent()` threads it |

Rules for the coordinator session, encoded here so every future session inherits them:

1. **Coordinator runs on Opus.** Coordination is routing and gate judgment — Opus-tier
   per the operator's tiering rule. Fable 5 is 2× Opus per token ($10/$50 vs $5/$25 per
   MTok, cached 2026-06-24) and every `advance` tick re-reads the coordinator's context.
   Reserve Fable for design-heavy sessions, not reconcile ticks.
2. **At `/outcome start`, copy each leaf's executor profile** (model · effort · backend,
   from `docs/sdlc-issue-drafts/plugin-fleet/<slug>.json`) into the leaf's node notes.
   The DAG carries tier intent; this is the manual stand-in for #362 and makes resolver
   adoption trivial when it lands.
3. **Dispatch below-session-tier leaves as subagents with an explicit `model:`** — never
   fork them (forks can't downgrade) and don't run them inline. Phase 0 profiles: nine
   sonnet leaves + one opus leaf (#463). Nothing in Phase 0 calls for Fable.
4. **Treat Effort lines as declared intent, not config,** until #363/#362 land in
   Phase 1 — after which the remaining ~107 issues execute at their declared posture.

## Execution discipline

- Concurrency 3 remains the hard default inside any single run; the two-lane cap above
  is about *objectives*, chosen for disjoint plugin surfaces (merge-conflict control).
- Every PR still updates release surfaces in the same PR (CLAUDE.md rule); #429 makes
  that mechanical instead of manual.
- Moonshots (7 total) sit last within their home objectives; each is individually
  gate-checked, none is load-bearing for a later phase.
- No throughput promise is made here: measured pace comes from #461's baseline plus the
  ledger, and #439 (backlog admission governor, Phase 7b) formalizes pacing once real
  throughput data exists.

## Pre-mortem — most likely failure modes

1. **Skipping Phase 0 item 3 (#463)** and building five differently-packaged shared
   primitives in wave-1 → wave-2 becomes a rework program. Mitigation: #463 is a
   blocking edge, not a suggestion.
2. **Program stall from ship friction**: 120 PRs × manual ceremony + tri-lock conflicts.
   Mitigation: #345 + #429 in Phase 0.
3. **Unfalsifiable wins**: cache/spend/offload objectives all claim measured
   improvement. Mitigation: #461 lands before any other change.
4. **Rate-limit carnage** during team-execution-heavy phases. Mitigation: #348 in
   Phase 0, full governor in Phase 2, before the 20-issue external-engine objective.
5. **Autonomy overreach**: #449 envelope-authorized merge landing before gate records
   and telemetry history exist. Mitigation: explicit last-in-objective ordering.

## Follow-ons wired to this plan

- After #415 ships (Phase 6a): A1 backend re-triage of remaining team-execution drafts.
- After #468 fire drill passes (Phase 4b exit): revisit ext:offload postures on #432,
  #402, #392.
- After Phase 7b: hand pacing authority to #439's governor and retire the manual
  phase gates in this document.
