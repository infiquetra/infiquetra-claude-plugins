---
date: 2026-06-26
topic: vecu-port-seeds
focus: VECU fork port-gap + principle seeds for the saga/team-execution/mission-control orchestration engine
scope: broad
repo: infiquetra-claude-plugins
maturity: idea-ready
revised: 2026-06-27
---

# Ideation: VECU → Infiquetra Orchestration-Engine Port Seeds

## Reconciliation — operator review (2026-06-27)

After the second-opinion pass, the operator (sole user of these plugins) reviewed the set and made the
calls below. **This section is the authoritative current state.** The original Ranked Survivors,
Did-not-survive, and Second-opinion sections are preserved below as the historical record, annotated
with status flags that point here.

**Killed outright**
- **S-6 (measurement-first ROI gate + HALT) — REMOVED.** Wrong frame for a one-person tool: the
  measurement loop is the operator *using it + `/retro` + adjusting*. It was also being used to *defer*
  S-1 (the highest-value idea), which is backwards. No formal ROI / threshold / HALT ceremony on solo
  tooling — justify ideas by "does it help the one operator," not million-user governance.

**Promoted to build-first**
- **S-1 (worker×model cache scheduling) — un-deferred, now ★ build-first.** The "defer behind S-6"
  sequencing dies with S-6. Keep only the *technical* refinement: cache ≈ 5-min TTL → affinity is
  probabilistic, so design the shed/respawn boundary around that horizon (a sharpening, not a reason to
  wait). Absorbs **R15a context-GC** as a refinement.

**Revived from the cut pile → now live**
- **R1 — autonomous GitHub board work** (status + *good* comments + labels + nonprod-close), gated by
  S-2. Ship-now path: a hardcoded reversible-ops allowlist (PR-merge / deploy stay gated); S-2
  generalizes it into a computed certificate later. "Good comments" = useful progress summaries (what
  changed, why, links), not robotic status pings.
- **R6 — team-spawn guard hook** (warn-first PreToolUse). Standalone.
- **R7 — cc-workflows robustness rubric.** Revived, but scope gets **constrained in brainstorm** (the
  full bundle — cap + quorum-tolerant verify + ADR-gated reviewer + cost rubric — is likely more than
  wanted).
- **R11 — Evidence / Provenance Manifests.** Promoted. The structural answer to parroting; unifies
  S-4 + S-7.
- **R14 — read-only verify/review tool profile** (narrow slice of capability-scoped sandboxing).
  Promoted; would have structurally prevented the verify-agent `git checkout` clobber incident.
- **R15b — typed artifact-pointer passing.** Pulled forward as a separate live item (not parked).

**Folded as refinements (not standalone)**
- **R15a context-GC → S-1.**
- **R12 typed-failure classes + max-ping-pong cap → S-7.** The heavy out-of-band livelock detector is
  dropped, replaced by a simple **max-ping-pong cap** that is **overridable** (when iterate-to-consensus
  is the goal — e.g. differential spec-validation: two independent agents build from the spec and
  divergence means the *spec* is ambiguous, not broken) and, on hit, emits a typed
  `verifier-disagreement` failure that **surfaces the upstream cause** to fix rather than silently
  avoiding the loop ("fix broken code, don't build avoidance machinery").

**Still parked** — R13 mid-flight interrupt (feasibility unknown: can a running cohort be interrupted?),
R2 transcript-mining, R8 CLAUDE.md house-style cleanup, R10 backend-conformance harness.

**Fix / dead** — R3 CI uncollected-test-dir bug (just fix it, outside this ideation) · R4 cost-ledger
(orphaned now S-6 is dead; same over-built accounting the operator rejected) · R9 solo git-ops
(duplicate reject) · S-6 (removed, above).

**Current live set: 6 core survivors (S-1–S-5, S-7) + 6 revived/promoted (R1, R6, R7, R11, R14, R15b),
with R15a + R12 folded in.** Recommended order (operator's to set): ① S-1 → ② S-7 + S-5 → ③ S-2 + S-3 →
④ S-4; the cheap revived items (R6 hook, R14 profile) are small and independent. Next step: `/brainstorm`,
S-1 first (operator's pick).

## Grounding Context

**Repo:** Claude Code plugins monorepo (Python 3.12 + markdown), 7 plugins @ marketplace 3.0.0 —
saga 0.38.0 (lifecycle engine; `outcome_*` script family, `execution_spec.py`, `team_emitter.py`),
team-execution 2.2.0 (reviewer/tester/scanner fan-out — **no `scripts/`, no `worker_derivation.py`,
no residency mechanism**), mission-control 2.2.0. Hooks (only `saga/hooks/hooks.json`): SessionStart
stale-main-FF, PreToolUse JSON-validate, PreToolUse Bash pre-push gate, PostToolUse journal-nudge —
**no PreCompact hook anywhere, no team-spawn-shape guard.** Backend contract (`operator-choice.md`):
inline / team-execution / cc-workflows-ultracode; §3.3 says the risk→backend precedence is *cosmetic*
and cc-workflows' real trigger was corrected to adversarial verification, not parallel width
(`LEARNINGS.md:306`). Existing patterns the seeds extend rather than invent: topological-layer
parallelism via Kahn's algorithm in the refute-N emitter (`DECISIONS.md:286`), one-spec-two-emitters +
frozen display-label enum (`:348`), append-only-log-canonical saga schema with rebuildable index
(`:960`), CLI-stays-deterministic / LLM-interpretation-in-skills (`:1097`). Multi-engine precedent with
a known failure mode on record: a plan was synthesized from Claude + Codex + agy/Antigravity, where
"Antigravity parroted an approach without independent verification; Codex's claims were verified
against source" (`DECISIONS.md:260`). The seeds themselves were pre-distilled from the VECU fork
(`coxauto/vecu-claude-plugins`) in a prior session; VECU was not re-read this run.

**Context-libraries:** None consulted — the topic is bound to the current repo's orchestration surface.

**External prior art (cross-domain grounding):** durable-execution engines (Temporal/Restate/Azure
Durable Functions — event-sourcing replay; AWS SnapStart snapshot-restore); serverless cold-start vs
provisioned-concurrency cost economics; wavefront DAG scheduling (Buck/Buck2/Bazel, PERT/Critical-Path,
airline crew-pairing); heterogeneous orchestration (Mixture-of-Experts, xRouter, GNSS RAIM
fault-detection-and-exclusion); verification-in-parallel (MapReduce speculative execution, V-MR
sample re-execution, Thread-Level-Speculation — "risk ∝ conflict-rate & abort-cost, not parallelism");
and unrelated-field analogues (immune memory-cells, Toyota JIT/JIC, Erlang rest-for-one supervision,
tardigrade anhydrobiosis, ASD-STE100 Simplified Technical English, analytical-chemistry spike-recovery,
double-entry/trial-balance accounting, van der Aalst process mining).

## Topic Axes

1. Worker economics & scheduling — spawn-vs-reuse, model/effort tiering, dependency waves, the cost model
2. Context durability — surviving compaction/context-loss, checkpoints, cross-session ledgers
3. Autonomy & HITL boundary — what saga drives autonomously vs operator-gated; the risk→backend routing logic
4. Fan-out verification & robustness — judge/quorum panels, adversarial gates, LLM→script seam validation, multi-engine cooperation, backend-neutral consistency
5. Operator legibility & surface — de-jargoning, the /work status card, CLAUDE.md house-style, transcript pattern-mining

## Ranked Survivors

### 1. Schedule the (worker×model) Cache, Not the Worker

> **★ BUILD-FIRST (operator review 2026-06-27).** Un-deferred — the "defer behind S-6" sequencing died
> with S-6. Absorbs **R15a context-GC** (shrink what each worker carries) as a refinement. Keep the TTL
> realism: cache ≈ 5-min TTL → affinity is probabilistic, design the shed/respawn boundary around it.
> See **Reconciliation** (top).

Make the distinct context cache — not the task or the model tier — the unit you schedule and bill.

Treat cache-reuse as first-order and model choice as second: "group first, then tier the whole group
as one unit." Spawn lazily at dependency-wave readiness so a blocked worker never idle-polls and
re-reads its whole context, and shed a resident at the boundary where its context goes dead. One live
design fork to resolve: crew-pairing (route a leaf-sequence to one resident) vs a warm residency pool.

This is the B8 cost model made the governing rule, and the most converged idea in the run — all six
frames landed on it — extending a pattern that already exists (Kahn-layer parallelism in the refute-N
emitter) rather than inventing one.

team-execution has no `scripts/` and no residency machinery today, making this the highest-burden
survivor; the crew-pairing-vs-pool fork is unresolved and changes the design materially.

| field | value |
|-------|-------|
| basis | `direct:` seeds B8/A2/A9 + DECISIONS.md:286/:348 · `external:` Lambda/SnapStart, Buck/PERT wavefront, airline crew-pairing |
| confidence | 80 |
| complexity | High |
| axis | 1 — worker economics & scheduling |
| status | Unexplored |

### 2. Replace "Risk" Routing With a Computed Reversibility/Idempotency Certificate

Stop routing on "risk" — route on whether work must be recorded, whether its side effect is reversible, and cost.

"Risk" conflates four unrelated things. Replace it with one computed predicate over
{recorded/gating-vs-ephemeral, side-effect-idempotency/abort-cost, cost} that drives both backend
selection and the HITL gate — autonomous only inside a certified envelope (the aviation autoland
framing). Autonomous reversible writes (issue-sync, label/board moves) become the first beneficiary.

This validates the C2 challenge, and it largely holds: the "risky→avoid workflows" lean
(`operator-choice.md:141`) is explicitly cosmetic per §3.3, and the engine already agrees workflows
carry validation (`LEARNINGS.md:306`); the genuine reasons risky work leans to team-execution are
recorded-vs-ephemeral (`:87`), idempotency (`:277`), and cost (`:289`), not "can't validate."

It reframes a shipped contract, so it needs careful migration — the certificate predicate must be
provably equivalent to today's behavior on the non-tie cases before it is trusted.

| field | value |
|-------|-------|
| basis | `direct:` seed C2 + operator-choice.md:140-141/:277/:289 + LEARNINGS.md:306 · `external:` Thread-Level-Speculation, CAT-III autoland certification |
| confidence | 82 |
| complexity | Med |
| axis | 3 — autonomy & HITL boundary |
| status | Unexplored |

### 3. Saga Log Is Canonical Truth; PreCompact Rehydration, Not Salvage

Make compaction the normal save/rehydrate path instead of a loss event to defend against.

Add the missing PreCompact hook so saga writes a minimal "spore" — a prefix-stable spine (open leaf
ids, ready frontier, last gate verdicts, `saga_id`) — and `load_state` prefers it over the harness
auto-summary; `/resume` replays from spore + the append-only log. The spore is a thin index, not a
re-dump of the canonical log.

Converged across all six frames, and the substrate already exists: the saga schema is an append-only
canonical log with a rebuildable index (`DECISIONS.md:960`) — exactly the event-sourcing replay model
Temporal/Restate use. There is no PreCompact hook anywhere today, so long autonomous runs inherit
whatever the harness summarizer happened to keep.

Defining the minimal resumable spine is a real tradeoff — too thin and `/resume` can't rebuild, too
fat and it's expensive to write at every compaction.

| field | value |
|-------|-------|
| basis | `direct:` seed A1 + DECISIONS.md:960 · `external:` Temporal/Restate event-sourcing replay, AWS SnapStart, tardigrade anhydrobiosis |
| confidence | 85 |
| complexity | Med |
| axis | 2 — context durability |
| status | Unexplored |

### 4. Heterogeneous Engines as Gated Generators + Fault-Exclusion

Let Codex and agy into the team — as generators only, never as verifiers-of-record — and exclude the parroting one.

Admit external engines as first-class generators (cheap divergent candidates) under Claude-side
verification, with RAIM-style fault-detection-and-exclusion: over-determine the panel, then detect and
drop the internally-incoherent vote rather than just outvoting it. Combined-arms doctrine — reconcile
at the boundary, don't homogenize.

This validates the C1 seed, grounded in a failure already on record: "Antigravity parroted an approach
without independent verification; Codex's claims were verified against source" (`DECISIONS.md:260`).
The substrate exists (`codex:codex-rescue`, `agy:runner`), so this is a trust-posture design, not a
new integration from scratch.

Highest-uncertainty survivor — agy's reliability is the open risk and FDE across heterogeneous engines
is real work; if verification is weak, a parroted generator silently re-enters under time pressure.

| field | value |
|-------|-------|
| basis | `direct:` seed C1 + DECISIONS.md:260 · `external:` military combined-arms, GNSS RAIM fault-detection-and-exclusion, MapReduce/V-MR sample re-execution |
| confidence | 75 |
| complexity | High |
| axis | 4 — fan-out verification & robustness |
| status | Unexplored |

### 5. Operator Surface as an O(1) Projection — Glyph Card + Controlled Vocabulary

The status card you liked, made deterministic — and the one thing the operator must read to stay in control.

Render the operator surface as a projection of engine state (reuse the one-spec-two-emitters pattern):
a fixed positional glyph card (✅/▶/‖) emitted at every `/work` gate — implementation, reviewer-panel
scores, scanners, test gates, journal counts, CI, pending HITL gates — with a controlled vocabulary
enforced by a lint rather than just a glossary doc. Positional stability means status is read by
location, with no prose re-derivation.

This is the reference image made the norm, verified absent today (`/work` has no fixed card). The deep
argument: operator attention is the one resource that doesn't parallelize, so every other improvement
here (more engines, wider fan-out) degrades governability unless the surface stays constant-size.

Requires ratifying the canonical gate taxonomy + glyph vocabulary once, and splitting agent-facing
markers from operator words — a standard that only sticks if enforced (hence the lint, not a memo).

| field | value |
|-------|-------|
| basis | `direct:` seeds A10+B5+A6 + verified `/work` absence + DECISIONS.md:348 · `external:` ASD-STE100 Simplified Technical English, MVC projection |
| confidence | 80 |
| complexity | Med |
| axis | 5 — operator legibility & surface |
| status | Unexplored |

### 6. Measurement-First ROI Gate With HALT — Over the Porting Itself  ⛔ REMOVED (2026-06-27)

> **⛔ REMOVED — operator review 2026-06-27.** Wrong frame for a one-person tool: the measurement loop is
> the operator using it + `/retro` + adjust. It was also being used to *defer* S-1 (the highest-value
> idea), which is backwards. No ROI / threshold / HALT ceremony on solo tooling. Retained below only as
> historical record; R4 (its folded substrate) is orphaned as a result. See **Reconciliation** (top).

Measure the win before building the machinery, and be willing to not build it — including for this very list.

Instrument the baseline, ship optimization machinery behind a flag, and HALT (don't merge the
complexity) if the measured improvement doesn't clear a pre-committed threshold — as VECU killed full
tiering at 19% < 25%. Point it at this doc's own ambition: the most valuable thing to port from VECU
may be its kill switch, not its features.

Cheapest, highest-discipline survivor, and it directly guards survivors 1/3/4 from becoming
unpaid-for complexity. The journal already carries the instinct (measurement before optimization
machinery, `DECISIONS.md:348`) but no formal HALT verb.

Only as good as the threshold committed to — a soft threshold makes it theater; and it adds a
measurement step before the fun part, exactly when it's tempting to skip.

| field | value |
|-------|-------|
| basis | `direct:` seed B3 + DECISIONS.md:348 · `external:` Toyota jidoka (stop-the-line) |
| confidence | 85 |
| complexity | Low |
| axis | 1 — worker economics & scheduling |
| status | Unexplored |

### 7. Silent-Omission + Seam-Validation Gate, Spike-Calibrated

> **⊕ Absorbs R12 (operator review 2026-06-27):** typed failure classes (budget-exhaustion / malformed /
> tool-denial / stale-context / merge-conflict / verifier-disagreement → different retries) + a simple
> **max-ping-pong cap**, **overridable** when iterate-to-consensus is the goal (e.g. differential
> spec-validation), and on-hit emitting a typed `verifier-disagreement` failure that surfaces the
> upstream cause rather than silently avoiding the loop. The heavy out-of-band livelock detector is
> dropped. Spikes run out-of-band; hostile-input validation covers command inputs + generated patches.

Verify what's missing, not just what's present — and prove the gate still catches by planting known omissions.

A required gate class that diffs a spec's required outputs against produced outputs to catch silent
omissions (the case refute-N misses because there's nothing on the page to refute), treats every
LLM→script seam as hostile input, and measures its own catch-rate by periodically injecting a planted
known omission (analytical-chemistry spike-recovery).

Targets the engine's dominant recorded failure mode: 16/19 StructuredOutput failures were
budget-exhaustion, i.e. silent truncation — an omission a correctness-only gate passes clean
(`LEARNINGS.md:603`). A green gate whose catch-rate is unmeasured is just a hope; the spike makes it a
number.

The spike harness is extra machinery to maintain, and "what should be here" requires a spec complete
enough to diff against — which not every leaf has.

| field | value |
|-------|-------|
| basis | `direct:` seeds B1+B2 + LEARNINGS.md:603/:423 + DECISIONS.md:1097 · `external:` analytical-chemistry spike-recovery, immune missing-self recognition |
| confidence | 78 |
| complexity | Med |
| axis | 4 — fan-out verification & robustness |
| status | Unexplored |

## Did not survive (revivable)

Explicit rejection is the quality mechanism. Most cuts below are deliberate **folds** (absorbed into a
stronger survivor, kept revivable), not dismissals — only R9 is a quality reject, and R3 is a
real-but-tactical bug worth fixing immediately outside this ideation.

| id | title | summary | reason | status |
|----|-------|---------|--------|--------|
| R1 | Autonomous issue-sync + board-as-derived-projection (A3) | saga as sole writer of board state; the GitHub board becomes a projection rebuilt from saga ticks, so drift is structurally impossible | **REVIVED 2026-06-27 → live**: autonomous board status/comments/labels/nonprod-close, gated by S-2; ship via a reversible-ops allowlist, S-2 generalizes later | REVIVED → live |
| R2 | Transcript process-mining → skill candidates (B6) | mine recurring Bash-call clusters from the session corpus and propose them as skills (van der Aalst de-facto-vs-de-jure on the existing journal-nudge hook) | Strong compounding flywheel but overlaps S-5's axis and is lower-urgency than the 7 | rejected |
| R3 | CI false-green guard / uncollected test dirs (B4) | fail CI + block the /work test gate on any test file outside collected roots | Verified-real bug on `main` (pyproject.toml:84 misses `plugins/home-lab-ops/skills/team-scaffold/scripts/tests`); too tactical for a strategic survivor — just fix it | rejected |
| R4 | Cost-ledger + per-message.id dedup as trial-balance (A4) | cross-session ledger that refuses to report a total until by-message == by-leaf (double-entry reconciliation; naive summing inflated cost ~13.7×) | **ORPHANED 2026-06-27** — parent S-6 removed; same over-built accounting rejected for a solo tool. Durable nugget: the dedup correctness fact (~13.7× inflation) | rejected |
| R5 | One-resident-adversary, N-passes refute-N (F2#4) | run refute-N as N adversarial passes by one named resident verifier, not N spawns, sharding only when independence demands it | Cost-optimization of refute-N; folds into S-1 (residency) + S-7 | rejected |
| R6 | Team-spawn guard hook, warn-first PreToolUse (A5) | advisory PreToolUse hook when a team-family subagent_type spawns one-shot without a name | **REVIVED 2026-06-27 → live** as a standalone warn-first hook | REVIVED → live |
| R7 | cc-workflows fan-out cost+robustness rubric (A7) | concurrency cap, quorum-tolerant verify (n//2+1, null verifiers logged not fatal), ADR-gated reviewer, fan-out cost rubric | **REVIVED 2026-06-27 → live**, scope to be constrained in brainstorm (full bundle likely more than wanted) | REVIVED → live |
| R8 | CLAUDE.md house-style standard (A6) | invariant-ratio, MUST-have floor, MUST-NOT list, delete-by-reference to plugin owners, prefix-stability | Folded into S-5 (controlled vocabulary extends to CLAUDE.md); revivable as a corpus-cleanup pass | rejected |
| R9 | Solo git-ops consolidation (A8) | single-invocation commit→PR→merge→worktree-cleanup | Quality reject: low signal, `commit-commands` already covers most of it; duplicates existing capability | rejected |
| R10 | Backend-neutral ExecutionSpec conformance harness (B7) | a harness exercising the same spec against inline/team-execution/cc-workflows, asserting routing + outcome consistency so a new backend can't silently diverge | Folded into S-2 (certificate routing) + S-4 (ExecutionSpec comparability); revivable as a standalone conformance suite | rejected |

No axis ended with zero survivors — axis 1 (S-1; S-6 removed 2026-06-27), axis 2 (S-3), axis 3 (S-2), axis 4 (S-4, S-7),
axis 5 (S-5).

## Co-ideation log

20 seeds entered at Phase 0 (A1–A10, B1–B8) and 2 more mid-run before the frames dispatched (C1, C2).
All were passed INTO the six Phase 2 frame agents to build on / challenge / combine, AND entered the
merged pool, AND faced the identical Phase 3 critique — never rubber-stamped, never silently dropped.

| source | entered | idea / seed | outcome |
|--------|---------|-------------|---------|
| user-seed | Phase 0 | A1 PreCompact saga durability | survived as #3 (reframed by frames 2/3/6: salvage → rehydrate) |
| user-seed | Phase 0 | A2 Cost-first resident worker derivation | survived as #1 (challenged by frame 5's crew-pairing alternative to a pool) |
| user-seed | Phase 0 | A3 Autonomous GitHub-issue sync | cut → R1 (folded into #2; board-as-projection added by frame 1) |
| user-seed | Phase 0 | A4 Cross-session cost ledger + message.id dedup | cut → R4 (folded into #6; trial-balance reframe by frame 5) |
| user-seed | Phase 0 | A5 Team-spawn guard hook | cut → R6 (folded into #1's wave-spawning) |
| user-seed | Phase 0 | A6 CLAUDE.md house-style standard | cut → R8 (folded into #5's controlled vocabulary) |
| user-seed | Phase 0 | A7 cc-workflows fan-out robustness rubric | cut → R7 (split-folded into #1/#4/#7) |
| user-seed | Phase 0 | A8 Solo git-ops consolidation | cut → R9 (quality reject — duplicates existing capability) |
| user-seed | Phase 0 | A9 Dependency-wave worker spawning | survived as #1 (combined with A2/B8; park-don't-poll sharpening by frame 1) |
| user-seed | Phase 0 | A10 Canonical /work gate-status card | survived as #5 (combined with B5; O(1)-surface argument by frame 6) |
| user-seed | Phase 0 | B1 Adversarial silent-omission gate class | survived as #7 (combined with B2; spike-calibration by frame 5) |
| user-seed | Phase 0 | B2 Determinism-boundary input validation | survived as #7 (combined with B1 into one seam gate) |
| user-seed | Phase 0 | B3 Measurement-first ROI gate | survived as #6 (extended by frame 3 to gate the porting itself) |
| user-seed | Phase 0 | B4 CI-uncollected test-dir guard | cut → R3 (real bug, verified live on main — just fix it) |
| user-seed | Phase 0 | B5 Operator de-jargoning pass | survived as #5 (combined with A10) |
| user-seed | Phase 0 | B6 Mine transcripts → skill candidates | cut → R2 (revivable flywheel; process-mining algorithm by frame 5) |
| user-seed | Phase 0 | B7 Backend-neutral ExecutionSpec consistency harness | cut → R10 (folded into #2/#4) |
| user-seed | Phase 0 | B8 Creation-tax vs carry-cost cost model | survived as #1 (the deepest seed — became the governing rule / spine) |
| user-seed | Phase 1 (pre-frame) | C1 Heterogeneous external engines as team members | survived as #4 (frames added gated-generator posture + RAIM fault-exclusion) |
| user-seed | Phase 1 (pre-frame) | C2 Challenge the "workflows are risky" premise | survived as #2 (validated + reframed as the reversibility/idempotency certificate) |
| frame-agent | Phase 2 | "schedule the cache not the worker" / cache-as-unit (frames 2,3) | merged into #1 |
| frame-agent | Phase 2 | crew-pairing route-a-leaf-sequence (frame 5) | merged into #1 as the design fork vs a pool |
| frame-agent | Phase 2 | autoland certificate + idempotency risk-score (frames 3,4,5) | merged into #2 |
| frame-agent | Phase 2 | RAIM fault-detection-and-exclusion panel (frame 5) | merged into #4 |
| frame-agent | Phase 2 | O(1) single-surface argument + ASD-STE100 controlled-vocabulary lint (frames 5,6) | merged into #5 |
| frame-agent | Phase 2 | "port the kill switch, not the features" (frame 3) | merged into #6 |
| frame-agent | Phase 2 | spike-recovery positive-control calibration (frame 5) | merged into #7 |

## Second-opinion pass — Codex + two Gemini engines (2026-06-26)

Ran the 7 survivors past three external engines in fresh, hermetic sessions with an anti-sycophancy
adversarial prompt (see `.claude/saga/ideate/7b3c0de2/critique_prompt.md`): **Codex gpt-5.5 (xhigh)**,
**agy Gemini 3.1 Pro (High)**, **agy Gemini 3.5 Flash (High)**. This is S-4's own contract executed on
S-4's ideation — the engines were **gated generators under Claude-side verification**, not
verifiers-of-record; claims below are verified against source, not adopted wholesale.

**Parroting check (the known agy failure mode): none parroted.** All three disagreed substantively,
picked *different* kills (Codex killed S-1; both Gemini runs killed S-4), and each surfaced distinct
net-new ideas. One claim flagged and NOT adopted: agy-Flash's S-1 "client can't enforce cache affinity
because API load balancers distribute across physical hardware" imports a server-affinity model that
does not map to Anthropic's prefix-keyed prompt cache; the *valid* form is agy-Pro's ~5-minute TTL point
(a worker blocked past the cache TTL loses its cache regardless), which IS adopted.

| survivor | Codex | agy-Pro | agy-Flash | Verified refinement to fold in |
|---|---|---|---|---|
| S-1 cache scheduling | REWORK (kill for now) | REWORK | CUT | ~~Defer behind S-6~~ → **operator overrode 2026-06-27: BUILD-FIRST** (S-6 removed). Kept only the technical refinement: bound to ~5-min cache TTL, treat hits as probabilistic, design shed/respawn around the TTL horizon. |
| S-2 certificate | ADVANCE | ADVANCE | ADVANCE | Reversibility/abort-cost is **not statically computable** in general → the certificate must be **conservative + enumerated** (default-to-gate when unproven), not sold as a proof. |
| S-3 PreCompact spore | ADVANCE | REWORK | REWORK | Spore must rehydrate from **structured durable facts** (leaf ids, gate verdicts, frontier), never a prose CoT summary — else it's just another stale summary. |
| S-4 engines+RAIM | REWORK | CUT | CUT | **Drop the RAIM fault-exclusion / voting half** — heterogeneous LLMs share training data and fail in *correlated* ways, so independence is false (voting amplifies shared errors, excludes correct minorities). **Keep** the gated-generator-under-source-verification core (which this very run validated). |
| S-5 O(1) card | ADVANCE | ADVANCE | REWORK | Glyphs must be **drill-down-traceable** to concrete log state/gate verdict — the card is the top layer, not the only layer, or operators abandon it and tail raw logs. |
| ~~S-6 measurement HALT~~ ⛔ | — | — | — | **REMOVED by operator 2026-06-27** — ROI/HALT ceremony is the wrong frame for a one-person tool (measurement = use it + /retro + adjust). Engines had rated it ADVANCE/ADVANCE/REWORK; operator overrode. |
| S-7 omission gate | ADVANCE | ADVANCE | ADVANCE | **Unanimous strongest.** Spikes must run **out-of-band** (not in the live workspace/context); hostile-input validation must cover **command inputs and generated patches**, not only structured outputs. |

**Sequencing consensus:** build **S-7 first** (unanimous); then **S-2** (2/3) or **S-3** (Codex). **Defer
S-1** (all three). **Cut S-4's RAIM mechanism** (2 cut, 1 rework) while keeping its gated-generator core.

**Operator override (2026-06-27):** S-1 is **build-first**, not deferred — the deferral hung entirely on
S-6, which is removed. S-7 remains a strong, cheap companion. See **Reconciliation** (top).

**Net-new candidate seeds surfaced by the external engines** — operator dispositions applied 2026-06-27 (see status column; details in **Reconciliation**, top):

| id | title | source | summary | status |
|----|-------|--------|---------|--------|
| R11 | Provenance / Evidence Manifests | Codex | every agent output carries a manifest (required inputs, source refs, commands run, files inspected, artifacts produced, unresolved claims) tagged `verified \| inferred \| not-checked` — provenance as a first-class contract; the structural answer to the parroting problem. *Strongest net-new; unifies S-4 + S-7.* | PROMOTED → live |
| R12 | Structural livelock interruption + typed failure classes | agy-Pro + Codex | out-of-band cycle-detector that interrupts cyclic disagreement before budget is torched, plus typed failure handling (budget-exhaustion / malformed / tool-denial / stale-context / merge-conflict / verifier-disagreement → different retries). **Challenges S-7's single-cause framing**: some of the 16/19 budget-exhaustion failures may be livelocks, not over-reading. | FOLDED → S-7 (simple overridable cap; heavy detector dropped) |
| R13 | Mid-flight interrupt + agent hot-swap | agy-Flash | pause parallel sub-agents, inject corrective steering, replace a struggling agent without discarding the cohort's progress — long parallel runs are currently all-or-nothing. | PARKED (feasibility) |
| R14 | Capability-scoped agent sandboxing | Codex | least-privilege per leaf (min tool/path/mutation/network); S-2's reversibility framing does not replace least-privilege for accidental/adversarial actions. | PROMOTED → live (narrow: read-only verify/review profile) |
| R15 | Per-worker context reduction | agy-Pro + agy-Flash | pre-emptive context GC (evict dead-end paths before the next step) + typed artifact-pointer passing (file hashes/AST refs across the team boundary instead of raw text) + semantic log compaction — attacks the (worker×model) cost from the *payload* side, complementary to S-1 and cheaper. | SPLIT: context-GC → S-1 · pointer-passing → live (R15b) |

Noted: agy-Flash's "transactional workspace isolation (worktree-per-worker)" is **partially already
present** — saga/outcome uses worktrees (`outcome_worktrees.py`); the gap is team-execution's parallel
workers, not the engine as a whole.

**Meta-result:** running C1's gated-generator contract on C1's own ideation *worked* (a good prompt
produced substantive, non-parroted critique I verified against source) AND showed precisely why the RAIM
voting half of S-4 is wrong (correlated errors). C1's core is validated; its fault-exclusion add-on is cut.
