# Phase D Workflow Design — Plugin-Fleet Ideation (Gate C)

- **Date:** 2026-07-03
- **Status:** Awaiting Gate C approval
- **Inputs:** [Intake Brief](2026-07-03-plugin-fleet-ideation-intake-brief.md) ·
  [Grounding Brief](2026-07-03-plugin-fleet-grounding-brief.md)
- **Constraint:** max 3 concurrent agents (all stages chunked ≤3)

## Narrative

One Workflow run, six stages, file-mediated throughout (agents write idea files to the
session scratchpad and return only counts + paths, so no idea corpus ever transits
orchestrator context). Stage D1 is the wide net the operator chose at Gate A: every one of
the 15 approved themes crossed with all six ideation frames — 90 Opus/max agents, each
producing 6–8 grounded ideas distributed across its theme's axes, each idea carrying
exactly one basis (direct / external / reasoned). Stage D2 is the Fable generative edge:
six fleet-wide novelty hunters (one per frame, all themes in scope, blind to the Opus
fleet) plus one codex hunter driven by a Claude chaperone under the chaperone-dispatch
decision. Stage D3 mechanically merges and censuses the pool. Stage D4 is Fable gap
synthesis: two agents read the whole merged pool and generate cross-cutting hybrids and
what the pool implies but nobody wrote. Stage D5 is convergent critique: one Opus/high
critic per theme enforces the basis contract, the outcome-generating test, and the
binding-decision register; kills duplicates; tags survivors quick-win / structural /
moonshot; and reports empty axes. Stage D5b dispatches capped recovery agents only where
an axis came back empty. Stage D6 is the only barrier that needs the full survivor set:
cross-theme dedup and clustering into candidate Objectives. Divergent and convergent
stages never share an agent — a convergent critic never generates, a divergent agent never
filters (per learning `{#ideate-on-imagination-doc-imports-constraints}`).

## Review table (strike or amend any line)

| # | Phase / action | Model | Effort | Agents | Isolation | Rationale |
|---|---|---|---|---|---|---|
| D1 | Wide net: frame×theme divergent generation | opus | max | 90 (15×6) | none — read repo + write own scratchpad file | Your Gate A call: coverage redundancy over consolidation. Lever: `high` instead of `max` cuts est. 30–40% cost/time at modest depth loss. |
| D2a | Fleet-wide novelty hunters (one per frame, blind) | **fable** | **xhigh** | 6 | none | The only generative role Opus can't match: tail novelty on assumption-breaking / analogy / constraint-flipping. Justified per Gate A reshape; fallback opus/max exists but forfeits the hedge the layer exists for. |
| D2b | Codex adversarial-novelty hunter via Claude chaperone | sonnet (chaperone) | medium | 1 | none | Dogfoods the seam per Gate A. Chaperone-dispatch decision honored: codex output is advisory evidence; reconciliation happens at D5/D6 by Claude critics (never-gatekeepers). Chaperone must capture proof-of-invocation; if codex fails, fail LOUD — no silent Claude fallback (`{#agy-delegate-silent-claude-fallback}`). |
| D3 | Mechanical merge + census of idea files | haiku | low | 1 | none | Deterministic file concat + counts. |
| D4 | Gap synthesis: hybrids + missing ideas from merged pool | **fable** | **xhigh** | 2 | none | Post-pool generation only Fable does well; reads all ~700 ideas, writes additions. Barrier justified: needs the full pool. |
| D5 | Convergent critique per theme: basis contract, outcome-generating test, binding-decision check, in-theme dedup, tier tagging, axis-coverage report | opus | high | 17 (15 themes + hunter/codex pool + direct-to-candidate pool) | none | Convergent judgment = Opus per §4 tiering; Fable validation rejected at Gate A (validation can't recover un-generated ideas). |
| D5b | Axis-recovery agents (only for axes D5 reports empty) | opus | max | 0–10 (cap: 2/theme) | none | Spec's recovery rule; data-driven, likely far under cap. |
| D6 | Cross-theme dedup + clustering into candidate Objectives | opus | high | 2 | none | The one true barrier: needs all survivors. Two agents: dedup/merge-map, then Objective clustering proposal. |

**Not in the workflow:** theme briefs and axes (below) are authored here by me (Fable,
inline — this document); Phase E issue drafting is a separate later workflow after Gate E
scoping.

## Estimates (extrapolated, not measured — calibration point: mining ran 72 sonnet/low
agents ≈ 3.2M subagent tokens in ~17 min at concurrency 3)

- Agent count: ~119 (+ up to 10 recovery).
- Wall-clock at concurrency 3: **roughly 3.5–5 hours**, dominated by D1 (90 slow max-effort
  generations, ~30 chunks).
- Token order-of-magnitude: **10–20M subagent tokens**, dominated by D1 and D4's
  full-pool reads.

## Idea contract (every D1/D2/D4 idea, enforced by schema)

`{theme, frame, axis, title, idea (3-6 sentences, concrete), basis_type
(direct|external|reasoned), basis (quote+file:line / named prior art / written argument),
outcome_shape (what a merged deliverable looks like), tier_guess
(quick-win|structural|moonshot)}` — written as JSON lines to
`scratchpad/ideation/raw/<stage>__<theme>__<frame>.json`.

Every D1/D2 prompt carries: the two brief files to Read, its frame definition, its theme's
axis list + constraints, the basis contract, and the instruction that binding decisions
constrain (engage revisit-when explicitly or steer clear).

## Frames (fixed six, from process spec)

pain-friction · inversion-removal-automation · assumption-breaking-reframing ·
leverage-compounding · cross-domain-analogy (may WebSearch prior art) ·
constraint-flipping.

## Axes per theme (derived from grounding; each idea tags exactly one)

**T1 External-LLM integration across lifecycle** — surface points (where the offer
appears: /ideate /brainstorm /work /doc-review /code-review, team-execution interactive);
intent semantics (offload vs second-opinion mechanics + reconciliation); chaperone
economics; operator ergonomics of the choice; constraint: never-gatekeepers + chaperone
dispatch.

**T2 Provider/model routing beyond CLI engines** — registry/adapter architecture
(engine_registry extension, bridge contract); provider onboarding cost; task→provider fit
recommendation (capability×rating); auth/config/secrets; cost/latency telemetry.

**T3 Tier-palette currency** — vocabulary propagation (fable/xhigh reachability beyond
saga plan vocab); effort as first-class field (frontmatter, dispatch,
.team-execution.json); escalation-ladder semantics (`{#tier-vocab-ordering}`); palette
drift-proofing (new models without fleet-wide edits); per-teammate/per-unit dispatch
overrides (QUEUED seed).

**T4 Cache economics & worker reuse** — decomposition-posture lever (time-vs-money at run
start, spend-asymmetric approval); segment/residency scheduling (build ON
`{#worker-cache-scheduling}`); cache-aware prompt architecture (stable prefixes, 5-min
TTL); measurement/ledger (the 350–450k recon number); propagation beyond team-execution
(workflows, saga panels, /outcome dispatch).

**T5 Consensus portability** — protocol extraction (shared primitive vs reimplementation);
gated-vs-advisory governance split (must survive porting); threshold configurability
(hardcoded 9.0/7.0/5.0); membership diversity (lenses; external advisory participation —
15/17 prior art); cost scaling (when consensus is worth its tokens).

**T6 Agent-team & gate lifecycle** — teardown/reclamation (Step B8 gap, 15 stale
worktrees, resident shutdown); pause/adjust points (mid-run model/context change);
liveness & delivery guarantees (idle-without-delivering, re-ping protocol); lifecycle
state visibility (what's running/held/leaked). [AskUserQuestion primitive struck per
Gate B.]

**T7 Lifecycle auto-progression & ship ceremony** — the ship verb (commit→PR→merge→sync→
cleanup as one guarded command); status/board auto-progression (widen /outcome allowlist →
/work, /loop); evidence-gated closure (immutable evidence, `{#...}` FAIL-overwrite
singleton); ceremony edge cases (stacked PRs, auto-merge, branch protection);
cross-plugin ownership boundary (saga vs mission-control vs deploy).

**T8 /outcome intent capture & Objective ingestion** — intent-dialog design (envelope
autonomy: PR-reviews-required?, merge/deploy gate-or-auto?); Objective ingestion
(parent+sub-issues → DAG seed); unstructured→structured refinement; step-selection
derivation from input shape; mid-flight posture renegotiation.

**T9 Standards/ADR enforcement locus** — injection points (issue creation, plan creation,
review lenses); consumption mechanics (llms.txt index, authority-model priority,
on-demand topic loading); machine- vs judgment-checkable split; drift-guarding the
enforcement itself (mermaid blind spot, board/field schema checks, pagination limits);
conflict surfacing (authority-model stop-and-surface inside plugin flows).

**T10 Cross-repo learning-mining & provenance** — mining substrates (Claude sessions,
219 dark codex sessions, journals); promotion-loop activation (0 promoted ever — find the
friction); provenance discipline (stale-claim verification against live sources);
cadence (scheduled vs on-demand, cost-bounded); feedback loop (mined pattern → issue/spec
pipeline).

**T11 Fleet quality** — agent-prompt audit (~55 agents, rubric); comprehensive
code-review pass mechanism; local-vs-CI parity automation; release-surface drift
automation (CLAUDE.md step 6 → CI guard, `{#marketplace-ci-guard}`); test-shape honesty
(dead-wiring / fake-adapter learnings → test standards).

**T12 Operator-facing model/effort levers** — lever placement (which decision points ask);
recommendation quality ("Fable, worth it, because…" with cheaper fallback);
spend-approval asymmetry (cheap silent, expensive asks); choice persistence (per-repo /
per-run defaults); spend observability (cost shown before/after).

**T13 Rate-limit-aware concurrency governance** — cap-policy architecture (where the knob
lives); enforcement vs aspiration (make claimed caps machinery — KTD6 finding); adaptive
behavior (backoff/queue on 429); scope granularity (per-workflow / per-session /
fleet-wide); reconciling /optimize's deliberately-shed knob.

**T14 Contract/vocabulary propagation & drift guards** — single-source contracts
(fetch-don't-copy for validator mirrors / vendored schemas); rename campaigns as tooling
(lockstep landing automation); drift detection (CI mirror-vs-source guards); version
coupling semantics; blast-radius mapping (which repos consume which contracts).

**T15 Delegation integrity** — proof-of-execution (invocation evidence for every bridge);
silent-fallback elimination (fail-loud contracts); output provenance (engine vs chaperone
attribution); liveness/orphan handling (late-writing orphans, thrashing runners);
evidence durability (immutable artifacts, audit chain).

## Checkpoints & failure posture

- Raw ideas: `scratchpad/ideation/raw/*.json` (one file per agent — nothing lost if the
  run dies; Workflow resume replays completed agents from cache).
- Post-merge pool: `scratchpad/ideation/pool.json`; survivors:
  `scratchpad/ideation/survivors/*.json`; clustering proposal:
  `scratchpad/ideation/objectives-draft.json`.
- Dropped/null agents are counted and logged, never silently absorbed.
- D2b codex failure = loud HALT of that one line (report, continue workflow) — never
  silent substitution.

## What Gate C approval authorizes

Executing exactly this table as one Workflow run (script authored from this design),
including Fable-tier lines D2a and D4 and the ~10–20M-token / ~3.5–5-hour envelope.
Anything outside the table comes back to you first.
