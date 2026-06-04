# Archive — Infiquetra Claude Plugins

> **The graveyard of QUEUED, LEARNINGS, and DECISIONS items.** When something from `QUEUED.md` ships, it moves here as **SHIPPED**. When something is consciously rejected, it moves here as **REJECTED** with the reason + revisit conditions. When a `LEARNINGS.md` or `DECISIONS.md` entry is invalidated by new evidence, the pre-correction version moves here as **SUPERSEDED**.
>
> **Never silently delete.** History is the point — a future Claude (or human) reading "did we ever consider X?" or "why did we change our mind on Y?" gets the answer.
>
> **Append new entries to the top** within each section.

---

## Shipped

### `/retro` rebuild — the meta-improvement engine (3-source merge gstack `retro`+`learn` + CE `ce-compound`, tiered self-edit gate, saga read-only)  {#retro-engine-rebuild-shipped}

**SHIPPED 2026-06-03** (`infiquetra-lifecycle` `0.15.0`, PR #191, squash f6faae2). Was QUEUED P1 `#retro-meta-improvement-engine`.

**Summary.** Tenth **command** rebuild of the engine-merge campaign (after `/office-hours`, `/plan`, `/code-review`, `/founder-review`, `/work`, `/loop`, `/resume`, `/qa`, `/strategy`). Rebuilt `/retro` from a 19-line stub into the lifecycle's **meta-improvement engine** — the pass that captures lifecycle learnings, curates durable journal knowledge, and proposes improvements to the workflow itself (up to and including the lifecycle plugin's own SKILLs). A **real 3-source merge**: gstack `retro` (forensics + the stale-base/wrong-"today" BLOCK guard) + gstack `learn` (the typed/confidence/source curation loop — staleness + contradiction + dedup) + CE `ce-compound` (the compounding "leave the system smarter" frame, agent-consumable findings not a 4500-word essay). Schema, the four interview answers, the folded-in deferred sub-items, and rejected alternatives recorded in DECISIONS [#retro-engine-rebuild](DECISIONS.md#retro-engine-rebuild).

**The four settled answers.** (Q1) **FULL engine in v1** — all 6 net-new passes (interview / transcript review / new-skill-or-plugin / refine-lifecycle-itself / refine-directives / memory-pruning) + a lean metrics snapshot; nothing deferred (the QUEUED brief's MVP-then-v2 split was rejected). (Q2) **Single `/retro` + an optional pass argument** — one engine, selectable passes, not separate sub-commands. (Q3) **Tiered self-edit gate** — pure-additive, append-only journal writes auto-apply; every delete / modify / move of existing durable state is propose-diff-and-wait. (Q4) **Full self-modification blast radius incl. the lifecycle SKILLs** — the gate's reach is the complete surface (journal, `.claude` memory, claude/agent/antigravity directive files, AND `infiquetra-lifecycle`'s own SKILLs); safety comes from the hard gate, not from narrowing reach.

**The design.**
- Rebuilt `/retro` SKILL: the meta-improvement engine — the 6 net-new passes + a lean metrics snapshot, merged from gstack `retro` + `learn` + CE `ce-compound`, behind the tiered self-edit gate.
- **Tiered self-edit gate** — pure-additive journal appends auto-apply; everything else is propose-diff-and-wait; a **global / cross-project** edit (`~/.claude/CLAUDE.md`, auto-memory, the antigravity directive class) carries an **extra cross-project-impact warning**. The in-repo vs global/cross-project directive disambiguation routes each directive edit to the right gate tier.
- **Saga READ-ONLY — the dead-wiring `->retro` advance dropped.** `/retro` reads saga context for evidence but writes **no** saga and advances **no** `lifecycle_phase`; the planned `work`/`qa`→`retro` saga advance was dead wiring (a terminal off-chain reflection pass has no saga-track consumer). So `saga.py` is untouched AND `saga-spec.md` gets **NO §11 change** — the campaign's first command consumer that deliberately writes nothing to the saga.
- **ZERO new Python** — `/retro` is a markdown engine (SKILL + references + command) that reuses existing helpers (read-only `gh` evidence, the journal sink, existing saga readers); adds no `.py`. `saga.py` untouched.
- **Stale-base guard scoped to the windowed mode** — gstack's stale-base/wrong-"today" BLOCK guard (maps onto Jeff's validation discipline) is kept but scoped to the windowed/metrics mode, not every pass.
- **Periphery** — version bumps (plugin `0.15.0`, marketplace entry `0.15.0`, CHANGELOG new `## 0.15.0` block; keywords stay at 10); dispatch-table `/retro` rows stub→shipped (kept ADVISORY + terminal); README `/retro` description stub→shipped. `saga-spec.md` UNCHANGED (no §11 row).

**Folded-in deferred sub-items (so nothing was silently dropped when the QUEUED brief was removed).** The **antigravity directive class** is folded in as one more global / cross-project directive surface under the directive-refinement pass (same cross-project warning). The **output-routing** of surfaced follow-ups (QUEUED entry vs `/handoff` vs ready-to-run ultracode/team-execution plan) is left OPEN for per-case judgment. Both recorded in DECISIONS [#retro-engine-rebuild](DECISIONS.md#retro-engine-rebuild).

**Follow-ups.** Post-merge follow-up fills the PR # + squash SHA into DECISIONS + this entry + LEARNINGS [#self-modifying-engine-needs-a-gate](LEARNINGS.md#self-modifying-engine-needs-a-gate). The output-routing open question may earn a settled default once real retro runs exist. `/optimize`, plus the missing-candidate adds `/investigate` / `/spec`, remain the next likely rebuilds.

**Refs.** DECISIONS [#retro-engine-rebuild](DECISIONS.md#retro-engine-rebuild), [#lifecycle-engine-merge-campaign](DECISIONS.md#lifecycle-engine-merge-campaign). The self-modifying-engine safety lesson — LEARNINGS [#self-modifying-engine-needs-a-gate](LEARNINGS.md#self-modifying-engine-needs-a-gate). Saga read-only / off-chain siblings — DECISIONS [#founder-review-engine-rebuild](DECISIONS.md#founder-review-engine-rebuild), [#strategy-engine-rebuild](DECISIONS.md#strategy-engine-rebuild). Consumed the QUEUED brief `#retro-meta-improvement-engine` (removed; deferred sub-items folded into the DECISIONS entry).

### `/strategy` rebuild — the interview-driven STRATEGY.md engine (faithful single-source CE `ce-strategy` port)  {#strategy-engine-rebuild-shipped}

**SHIPPED 2026-06-03** (`infiquetra-lifecycle` `0.14.0`, PR #189, squash a9d4c90). Was QUEUED P2 `#rebuild-strategy-engine-merge`.

**Summary.** Ninth **command** rebuild of the engine-merge campaign (after `/office-hours`, `/plan`, `/code-review`, `/founder-review`, `/work`, `/loop`, `/resume`, `/qa`). Rebuilt `/strategy` from a 21-line stub into the lifecycle's **interview-driven STRATEGY.md engine** — a **faithful single-source PORT of CE `ce-strategy`** (NOT a merge): gstack has **no** strategy engine (`cso/` is the Chief **SECURITY** Officer, a 14-phase security audit — the pre-audit "gstack cso ≈ Chief Strategy Officer" mapping was a name-match mixup, LEARNINGS [#lifecycle-thin-reskin-systemic](LEARNINGS.md#lifecycle-thin-reskin-systemic)). Position in the lifecycle: the off-chain direction-recording engine — "where are we pointed, and why?" — the records-half complement to `/founder-review`'s challenge-half. Schema, the four interview answers, and rejected alternatives recorded in DECISIONS [#strategy-engine-rebuild](DECISIONS.md#strategy-engine-rebuild).

**The four settled answers.** (Q1) **CE-only source** — gstack has no strategy engine (`cso` = SECURITY, wrong officer); CE `ce-strategy` is the sole engine source, making this a single-source port not a merge. (Q2) **Keep all 8 sections + the Rumelt kernel** — port the whole engine (diagnosis / guiding-policy / coherent-action kernel + the 8-section interview + the locked template), no trimming. (Q3) **Agent-as-customer is persona-only** — personas may name AI-agent actors when the product is agent-consumed, but **tracks stay pure investment areas / domains of work, NOT actors**; the QUEUED brief's blanket "personas/tracks must name AI-agent actors" was half a category error (tracks are domains of work, not actors), caught by reading the real CE `interview.md` semantics + a Jeff challenge (LEARNINGS [#spec-adaptation-is-a-hypothesis](LEARNINGS.md#spec-adaptation-is-a-hypothesis)). (Q4) **Keep the mandatory 2-round pushback per section** — kept verbatim, the mechanism that turns shapeless prose into a real strategy.

**The design.**
- Rebuilt `/strategy` SKILL: the interview-driven STRATEGY.md engine — Rumelt-grounded kernel, Phase-0 file-state routing (new STRATEGY.md vs targeted-section update vs pick-a-section), Phase-1 8-section interview with mandatory 2-round pushback per section, and a locked root-`STRATEGY.md` template (3-5 metrics, 2-4 tracks), rerunnable update-in-place.
- **Artifact home = the repository-root `STRATEGY.md`** (a single locked-template doc).
- **ZERO `saga.py` edits — off-chain / pre-saga** — `/strategy` runs upstream of the work loop and writes no saga, the same off-chain position as `/founder-review`; persistence = the committed `STRATEGY.md` + the journal ADR. `/strategy` records direction, `/founder-review` challenges it.
- **No new Python** — `/strategy` is a markdown engine (SKILL + references + command); `saga.py` untouched. No team-execution / workflows offer (a single durable doc, no parallelism).
- **Periphery** — version bumps (plugin `0.14.0`, marketplace entry `0.14.0`, CHANGELOG new `## 0.14.0` block; keywords stay at 10 — `strategy` was already a keyword); dispatch-table `/strategy` rows stub→shipped (kept ADVISORY); README `/strategy` description stub→shipped.

**Follow-ups.** Wiring STRATEGY.md metrics to live telemetry overlaps the queued `/pulse` / `/optimize` metric loops (QUEUED [#pulse-live-telemetry-component](QUEUED.md#pulse-live-telemetry-component), [#optimize-engine-merge](QUEUED.md#optimize-engine-merge)) — qualitative-only for now. Post-merge follow-up fills the PR # + squash SHA into DECISIONS + this entry. `/retro`, `/optimize` remain the next likely rebuilds.

**Refs.** DECISIONS [#strategy-engine-rebuild](DECISIONS.md#strategy-engine-rebuild), [#lifecycle-engine-merge-campaign](DECISIONS.md#lifecycle-engine-merge-campaign). Off-chain/pre-saga sibling — DECISIONS [#founder-review-engine-rebuild](DECISIONS.md#founder-review-engine-rebuild). Source-mapping correction (gstack `cso` = SECURITY) — LEARNINGS [#lifecycle-thin-reskin-systemic](LEARNINGS.md#lifecycle-thin-reskin-systemic). Spec-adaptation-is-a-hypothesis lesson — LEARNINGS [#spec-adaptation-is-a-hypothesis](LEARNINGS.md#spec-adaptation-is-a-hypothesis).

### `/qa` rebuild — the gate-only acceptance-evidence engine (gstack `/qa`+`/qa-only` merge + ce-debug graft, severity-banded verdict + ported deterministic health score, saga qa-track consumer)  {#qa-engine-rebuild-shipped}

**SHIPPED 2026-06-03** (`infiquetra-lifecycle` `0.13.0`, PR #187, squash fb2c1b3). Was QUEUED P1 `#rebuild-qa-engine-testing-vs-qa-boundary`.

**Summary.** Eighth **command** rebuild of the engine-merge campaign (after `/office-hours`, `/plan`, `/code-review`, `/founder-review`, `/work`, `/loop`, `/resume`). Rebuilt `/qa` from a 19-line stub into the lifecycle's **gate-only acceptance-evidence engine** — the gate downstream of `/work` + `/code-review` answering "does the shipped thing actually work?". A **real two-engine merge** against the **cloned** gstack source (`/qa` + `/qa-only` + `/investigate`) plus a CE `ce-debug` graft (not a phantom — gstack was absent from the install cache, then cloned from GitHub; LEARNINGS [#source-fidelity-cuts-both-ways](LEARNINGS.md#source-fidelity-cuts-both-ways)). Adopts gstack's own report-only `/qa-only` model: tests, gathers evidence, assigns severity, derives a ship verdict, computes a deterministic health score (PORTED from gstack), advances the saga qa-track on pass, and routes — but **never fixes, commits, pushes, opens/merges a PR, deploys, files SDLC issues, or sets readiness labels**. Schema, the four interview answers, and rejected alternatives recorded in DECISIONS [#qa-engine-rebuild](DECISIONS.md#qa-engine-rebuild).

**The four settled answers.** (Q1) **Gate + route, never fix** — the `/qa-only` model; `/work` round-N + the future `/investigate` own all fixing. (Q2) **Severity-banded verdict + a PORTED deterministic health score, reported alongside each other** — RE-OPENED to its final state. Jeff initially said keep; an interim review wrongly claimed "no formula" and briefly slated the score to be dropped; that read was one-hop-short — gstack's score *is* a deterministic weighted-deduction formula at `scripts/resolvers/utility.ts:286-321`, injected as the `{{QA_METHODOLOGY}}` macro (corrected in LEARNINGS [#source-fidelity-cuts-both-ways](LEARNINGS.md#source-fidelity-cuts-both-ways) / the superseded pre-correction in ARCHIVE [#source-fidelity-no-formula-superseded](#source-fidelity-no-formula-superseded)). Once the real formula was located, **Jeff chose to PORT it** — `scripts/qa_health_score.py` ports gstack's deduction values verbatim (critical -25 / high -15 / medium -8 / low -3) with documented infiquetra 9-way ship-risk-class weights (behavior/security 20, data/api 15, deployment/infra 10, config 5, docs 3, trivial 2), re-normalized over the in-scope classes, plus a baseline-from-prior-report delta. The 0-100 number is reported **alongside** the severity-banded verdict (pass/fail per risk class + critical/high/medium/low + a ship verdict `ship` / `ship-with-deferred` / `no-ship` from the tier threshold). **Honest caveat:** the scorer's inputs are LLM-assigned severities, so the score is one signal — the banded verdict is the gate decision. The genuinely rejected alternative was **inventing weights from scratch** (porting gstack's deductions + documenting infiquetra class weights instead). **This adds one new script — `qa_health_score.py` (the scorer) + its oracle test.** (Q3) **Saga qa-track consumer** — `restore`, write `qa_paths`, on PASS advance `lifecycle_phase` `work`→`qa` (the advance `/work` 0.10.0 deferred), on FAIL keep `work`; every flag already exists (`qa`@`LIFECYCLE_PHASES`, `--lifecycle-phase qa`, `--qa-paths`) and `_merge` has no phase-transition validation → **zero `saga.py` edits**. (Q4) **Ship a durable risk-class reference** — the 9-way router + per-class checklists + diff-aware file→class map + severity defs + the P0-P3 cross-walk.

**What shipped.**
- Rebuilt `/qa` SKILL (`skills/qa/SKILL.md`): the gate-only engine — 6 core principles (gate-not-fixer; risk-driven 9-way router with browser-as-one-MCP-class; evidence + falsifiable prediction; severity-banded verdict + ported health score reported alongside; saga qa-track consumer; route-don't-execute) + numbered phases (enter/restore/diff → classify → run checks → findings → verdict + score → report + tick + route) + a hard boundary.
- **NEW scorer** — `scripts/qa_health_score.py`: a deterministic health scorer PORTING gstack's `utility.ts:286-321` deduction values verbatim (critical -25 / high -15 / medium -8 / low -3) with documented infiquetra 9-way ship-risk-class weights, re-normalized over the in-scope classes, baseline-delta; emits per-class scores + the weighted overall + delta as JSON. Honest caveat in its docstring: inputs are LLM-assigned, so the score is one signal, not the gate.
- **2 NEW references** — `references/risk-taxonomy.md` (9-way router + per-class checklists, browser fold, file-pattern→class map, severity defs + P0-P3 cross-walk; carries the runnable `git merge-base`/`git diff` + `saga.py restore` lines) and `references/qa-report.md` (the report shape, browser-decoupled, with the health-score block reported alongside the banded verdict; ship-verdict derivation; tier→blocking-threshold table; carries the runnable `qa_health_score.py --findings-json` + `issue_progress.py --checks-run --evidence-link` + `saga.py save --lifecycle-phase qa --qa-paths` lines).
- Updated `commands/qa.md` (thin launcher) + a `test_qa_engine_merge_contract` contract test (mechanism floors via negation-window for the gate-only negatives, the qa-track advance, merge-state routing, falsifiable-prediction, severity-banded verdict, dispatch-referenced-not-restated) + a `test_qa_health_score` **oracle test** (deduction values, class-weight re-normalization over in-scope classes, baseline-delta, empty-input-is-100).
- **ce-debug falsifiable-prediction graft** — the single distinct ce-debug import: an uncertain-cause failure carries a prediction another path must also fail if the cause is real (a wrong prediction = symptom not cause; a right one gives the routed fixer a head start).
- **Merge-state failure routing** — PASS → `/handoff`//`/retro`; FAIL pre-merge → `/work` (round-N via `/work` Phase 0.4 `pr_refs`), post-merge → `/handoff` (new defect thread). `/investigate` is future-prose only (not on the dispatch-table's routable list). Routing **reads** `loop/references/dispatch-table.md`.
- **Periphery** — version bumps (plugin `0.13.0`, marketplace entry `0.13.0`, CHANGELOG new `## 0.13.0` block; keywords stay at 10); dispatch-table `/qa` row stub→shipped (preserving `test_loop`'s asserted tokens); README `/qa` description; `saga-spec.md §11` gets the new `/qa` AND `/code-review` rows; the `/optimize` `docs/qa/`→`docs/optimize/` one-line collision fix.
- **One new script — `qa_health_score.py` (the ported scorer) + its oracle test; `saga.py` UNTOUCHED; no `agents/` dir.**

**Follow-ups.** `/investigate` (the deep root-cause debugging engine `/qa` routes failures to) remains QUEUED [#investigate-systematic-debugging-engine](QUEUED.md#investigate-systematic-debugging-engine) — the `/qa`↔`/investigate` boundary is now settled on the `/qa` side (gate-only, routes deep failures out). Post-merge follow-up fills the squash SHA into DECISIONS + this entry. `/retro`, `/strategy` remain the next likely rebuilds.

**Refs.** DECISIONS [#qa-engine-rebuild](DECISIONS.md#qa-engine-rebuild), [#lifecycle-engine-merge-campaign](DECISIONS.md#lifecycle-engine-merge-campaign). Consumes the saga foundation as the qa-track consumer (zero edits) — DECISIONS [#saga-schema-foundation](DECISIONS.md#saga-schema-foundation), spec `plugins/infiquetra-lifecycle/references/saga-spec.md` §11. Lands the advance deferred by — DECISIONS [#work-engine-rebuild](DECISIONS.md#work-engine-rebuild). Gate-only + no-`agents/`-dir + the diff mechanic from — DECISIONS [#code-review-engine-rebuild](DECISIONS.md#code-review-engine-rebuild) (`skills/code-review/SKILL.md:164`). No-false-precision posture from — DECISIONS [#founder-review-engine-rebuild](DECISIONS.md#founder-review-engine-rebuild). Source-fidelity lesson — LEARNINGS [#source-fidelity-cuts-both-ways](LEARNINGS.md#source-fidelity-cuts-both-ways), counterpart to LEARNINGS [#brief-source-claim-phantom-artifact](LEARNINGS.md#brief-source-claim-phantom-artifact). Future debugging engine — QUEUED [#investigate-systematic-debugging-engine](QUEUED.md#investigate-systematic-debugging-engine).

### `/resume` rebuild — the lifecycle's heavy forensic reconstruction engine (Tier-1 saga all-ticks + Tier-2 CE `ce-sessions` port)  {#resume-engine-rebuild-shipped}

**SHIPPED 2026-06-03** (`infiquetra-lifecycle` `0.12.0`, PR #185, squash 73975ec). Was QUEUED P1 `#resume-engine-merge-saga`.

**Summary.** Seventh **command** rebuild of the engine-merge campaign (after `/office-hours`, `/plan`, `/code-review`, `/founder-review`, `/work`, `/loop`) and the **unblocked heavy partner** the `/loop` rebuild (0.11.0) explicitly deferred to it — completing the lightweight/heavy resume split (`/loop` = lightweight scan→restore→route + inline cold-reconstruction; `/resume` = heavy forensic dig). Rebuilt `/resume` from a 23-line "read committed docs first" doc into the lifecycle's **heavy forensic reconstruction engine**. Unlike `/loop` (the campaign's native rebuild against a **phantom** brief source), `/resume` is a **real CE `ce-sessions` PORT** — its named upstream was verified to exist and be portable, the positive counterpart to the `/loop` phantom-source lesson (LEARNINGS [#resume-port-source-verified-true](LEARNINGS.md#resume-port-source-verified-true)). Schema, the four interview answers (port CE now staged behind Tier 1 / drop the `[gstack-context]` trailer / any-phase routing via the referenced dispatch-table no-ping-pong / one git-ignored re-entry tick reusing the restored saga_id), the two-tier design, and rejected alternatives recorded in DECISIONS [#resume-engine-rebuild](DECISIONS.md#resume-engine-rebuild).

**Engine — two tiers.** **Tier 1** (saga-anchored deep reconstruction — the common path): a NEW saga **all-ticks reader** (`saga.py read_ticks`) walking the full append-only tick-chain trajectory (the trajectory `/loop`'s latest-tick-only `restore` cannot see) + PR archaeology + conflict reconciliation. **Tier 2** (FALLBACK ONLY — no saga AND no resolvable issue): a slim Claude-only port of CE `ce-sessions` — discover → file-mediated skeleton extract to scratch → generic-agent synthesis, never reading multi-MB session JSONL into context (context-safety by construction).

**What shipped.**
- Rebuilt `/resume` SKILL (`skills/resume/SKILL.md`): the two-tier forensic engine. **Tier 1** = saga-anchored all-ticks deep reconstruction + PR archaeology + conflict reconciliation. **Tier 2** (fallback only, no saga AND no resolvable issue — corrected to same-machine work that never wrote a saga, NOT fresh-clone) = the CE `ce-sessions` port via **generic-agent synthesis** (no `agents/` dir — honoring the shipped `/code-review:164` convention). **Routes to any phase via the SHARED `loop/references/dispatch-table.md`** (referenced, never duplicated — no `/loop` ↔ `/resume` ping-pong). Writes **exactly one** git-ignored re-entry saga tick **reusing the restored `saga_id`** (never-mint discipline). Recency-MVP ranking for Tier-2 candidates.
- **NEW `saga.py read_ticks` all-ticks reader** — walks the full append-only tick-chain trajectory. Placed in `saga.py` (the engine), **NOT** `load_saga_context.py`, because that wrapper is **issue-locked** (`--issue` required) and is the wrong layer for a cold no-issue trajectory read (LEARNINGS [#wrapper-required-arg-wrong-layer](LEARNINGS.md#wrapper-required-arg-wrong-layer)); `load_saga_context.py` stays the shared issue-keyed substrate `/loop` + `/resume` both use.
- **Dropped the `[gstack-context]` WIP-commit trailer** — the saga's append-only tick log already IS the durable trajectory; a parallel trailer would duplicate it.
- **Boundary** — `/resume` reconstructs + restores + routes; it does NOT mint a new saga (reuse-saga_id), own a phase's execution loop, or duplicate the dispatch table.
- Version bumps: plugin `0.12.0`, marketplace entry `0.12.0`; CHANGELOG. keywords stay at 10 (`resume` is not a keyword).

**Follow-ups.** CE's keyword/branch relevance ranking (`extract-metadata.py`) was deferred — recency-MVP is enough until a no-saga Tier-2 forensic returns >5 candidate sessions and recency mis-ranks (QUEUED [#resume-session-relevance-ranking](QUEUED.md#resume-session-relevance-ranking)). Cross-machine (fresh-clone) recovery is out of Tier-2 scope today (same-machine only). Post-merge follow-up fills the squash SHA into DECISIONS + this entry. `/qa`, `/retro`, `/strategy` remain the next likely rebuilds.

**Refs.** DECISIONS [#resume-engine-rebuild](DECISIONS.md#resume-engine-rebuild), [#lifecycle-engine-merge-campaign](DECISIONS.md#lifecycle-engine-merge-campaign). Consumes the saga foundation (adds the all-ticks `read_ticks` reader) — DECISIONS [#saga-schema-foundation](DECISIONS.md#saga-schema-foundation), spec `plugins/infiquetra-lifecycle/references/saga-spec.md`. Heavy partner of the lightweight half — DECISIONS [#loop-engine-rebuild](DECISIONS.md#loop-engine-rebuild) (Q4, the split it deferred). Verification-cuts-both-ways counterpart — LEARNINGS [#brief-source-claim-phantom-artifact](LEARNINGS.md#brief-source-claim-phantom-artifact), [#resume-port-source-verified-true](LEARNINGS.md#resume-port-source-verified-true). Wrapper-wrong-layer learning — LEARNINGS [#wrapper-required-arg-wrong-layer](LEARNINGS.md#wrapper-required-arg-wrong-layer). No-`agents/`-dir convention — DECISIONS [#code-review-engine-rebuild](DECISIONS.md#code-review-engine-rebuild) (`skills/code-review/SKILL.md:164`). Deferred relevance ranking — QUEUED [#resume-session-relevance-ranking](QUEUED.md#resume-session-relevance-ranking).

### `/loop` rebuild — the campaign's one NATIVE router engine (Route/Drive/Resume; no upstream port/merge)  {#loop-engine-rebuild-shipped}

**SHIPPED 2026-06-03** (`infiquetra-lifecycle` `0.11.0`, PR #183, squash 1fca13a). Was QUEUED P1 `#loop-engine-merge-saga-workflow-offload`.

**Summary.** Sixth **command** rebuild of the engine-merge campaign (after `/office-hours`, `/plan`, `/code-review`, `/founder-review`, `/work`) and the campaign's **ONE native rebuild** — unlike every prior rebuild there was **no upstream engine to port or merge**: CE ships no router, the gstack "dispatch table SKILL" the QUEUED brief named is **phantom** (gstack's root SKILL is browser-testing, there is no router dir — verified, LEARNINGS [#brief-source-claim-phantom-artifact](LEARNINGS.md#brief-source-claim-phantom-artifact)), and gstack's context-save/restore is the already-shipped saga plus the queued `/resume`'s engine, not `/loop`'s. So `/loop` was authored fresh against the lifecycle's own saga + operator-choice contracts. Rebuilt from a router stub into a native router engine with three modes: **Route** (classify intent → hand to the right lifecycle command), **Drive** (inline phase walk + per-decision operator-choice offer for `/loop`-owned work), **Resume** (scan → restore → route a durable work-thread + inline cold-reconstruction). Schema, the four interview answers (offload model / routing tick / durable substrate / lightweight-vs-heavy resume split), the no-upstream-port distinction, and rejected alternatives recorded in DECISIONS [#loop-engine-rebuild](DECISIONS.md#loop-engine-rebuild).

**What shipped.**
- Rebuilt `/loop` SKILL (`skills/loop/SKILL.md`): the Route/Drive/Resume native router engine. **Saga-resume wiring** — `scan`s for the matching work-thread saga, `tick`s a routing event, `restore`s state on re-entry, plus inline cold-reconstruction via `load_saga_context.py` when re-entering without a live session. **Per-decision operator-choice offer** for `/loop`-owned work (`inline`/`team-execution`/`cc-workflows-ultracode`). **Offload pointer scoped to `/loop`-owned work only** — `/loop` does NOT instruct a routed command's backend (`/work` writes but never reads `orchestration_mode`, SKILL:174,190). The routing tick carries the existing saga fields plus the offload pointer only for `/loop`-owned offloads — **no schema change**.
- **Additive `saga.py` picker-field extension** — `scan()` / `_saga_summary` now surface the `issue_ref` / `plan_path` / `branch` match keys (plus `destination` + the `orchestration_mode`/`orchestration_ref` pair the picker needs) so a resuming `/loop` (and a standalone `/code-review`) can match the right thread without `restore`-ing every candidate. This is the additive, no-schema-churn fix that **closes Defect 1 (the scan match keys) of `#code-review-saga-scan-touchups`**; **Defect 2 (the `/code-review` Phase-5.4 programmatic-mode append contradiction) is a `/code-review` SKILL change, out of scope here, and REMAINS queued** — see [#code-review-saga-scan-touchups-shipped](#code-review-saga-scan-touchups-shipped).
- **Boundary** — `/loop` classifies + routes + (in Drive) walks phases for work it owns; it does NOT override a routed command's own loop, do heavy forensic reconstruction (`/resume`'s job), or instruct a destination command's backend.
- Durable substrate — volatile `.claude/infiquetra-lifecycle/` for in-flight state + committed artifacts (plans/reviews/work-sessions). No new persistence location.
- Version bumps: plugin `0.11.0`, marketplace entry `0.11.0`; CHANGELOG. keywords stay at 10.

**Follow-ups.** The **heavy forensic** reconstruction half (commit-trailer archaeology + CE forensic session-log reconstruction) was deferred to the then-queued `/resume` rebuild — **since SHIPPED 0.12.0** ([#resume-engine-rebuild-shipped](#resume-engine-rebuild-shipped)); the `/loop` → `/resume` route is opt-in advisory. Post-merge follow-up fills the squash SHA into DECISIONS + this entry.

**Refs.** DECISIONS [#loop-engine-rebuild](DECISIONS.md#loop-engine-rebuild), [#lifecycle-engine-merge-campaign](DECISIONS.md#lifecycle-engine-merge-campaign). Built native on the saga foundation — DECISIONS [#saga-schema-foundation](DECISIONS.md#saga-schema-foundation) — and the operator-choice contract — DECISIONS [#operator-choice-framework](DECISIONS.md#operator-choice-framework). Backend-ownership partner — DECISIONS [#work-engine-rebuild](DECISIONS.md#work-engine-rebuild). Closes Defect 1 of the scan touch-up — [#code-review-saga-scan-touchups-shipped](#code-review-saga-scan-touchups-shipped) (Defect 2 remains QUEUED [#code-review-saga-scan-touchups](QUEUED.md#code-review-saga-scan-touchups)). Phantom-source learning — LEARNINGS [#brief-source-claim-phantom-artifact](LEARNINGS.md#brief-source-claim-phantom-artifact). Heavy-resume partner (since SHIPPED 0.12.0) — ARCHIVE [#resume-engine-rebuild-shipped](#resume-engine-rebuild-shipped).

### `saga.py scan` match-key extension — Defect 1 of the touch-ups (shipped with the `/loop` rebuild; Defect 2 remains queued)  {#code-review-saga-scan-touchups-shipped}

**SHIPPED 2026-06-03** (`infiquetra-lifecycle` `0.11.0`, PR #183, squash 1fca13a). Partially closes QUEUED P2 `#code-review-saga-scan-touchups` — **Defect 1 only**.

**Summary.** The cross-skill scan defect surfaced (not introduced) by the `/work` rebuild's adversarial review had **two** parts. **Defect 1 (scan match keys) — SHIPPED HERE:** `saga.py` `scan()` / `_saga_summary` exposed `saga_id`/`kind`/`id`/`round`/`phase`/`status`/`lifecycle_phase`/`next_step` but **not** the `issue_ref`/`plan_path`/`branch` match keys that `/code-review` Phase 5.1 (and a resuming `/loop`) say they match on — so a standalone matcher had to `restore` every candidate to read them, contradicting the prose. Fixed as a **purely additive** extension to both the `scan()` candidate dict and `_saga_summary` (all three match keys `issue_ref`/`plan_path`/`branch`, plus `destination` + the `orchestration_mode`/`orchestration_ref` pair the `/loop` picker needs), alongside the `/loop` rebuild — the first consumer that needs them. Asserted by `test_scan_exposes_picker_fields`. **Defect 2 (the `/code-review` Phase-5.4 programmatic-mode append contradiction) — NOT shipped here:** that is a `/code-review` SKILL change, out of scope for the `/loop` rebuild (which deliberately touched no other skill), and **REMAINS QUEUED** (re-scoped to Defect 2 only — QUEUED [#code-review-saga-scan-touchups](QUEUED.md#code-review-saga-scan-touchups)).

**Refs.** Shipped with DECISIONS [#loop-engine-rebuild](DECISIONS.md#loop-engine-rebuild) / ARCHIVE [#loop-engine-rebuild-shipped](#loop-engine-rebuild-shipped). Surfaced by DECISIONS [#work-engine-rebuild](DECISIONS.md#work-engine-rebuild) (the forward-coupling residual) and [#code-review-engine-rebuild](DECISIONS.md#code-review-engine-rebuild). Remaining Defect 2 — QUEUED [#code-review-saga-scan-touchups](QUEUED.md#code-review-saga-scan-touchups). Spec `plugins/infiquetra-lifecycle/references/saga-spec.md`.

### `/work` rebuild — CE `ce-work` execution engine + gstack `ship`/`land-and-deploy` (saga-primary-writer execution loop)  {#work-engine-rebuild-shipped}

**SHIPPED 2026-06-03** (`infiquetra-lifecycle` `0.10.0`, PR #181, squash d398055). Was QUEUED P1 `#rebuild-work-engine-merge`.

**Summary.** Fifth **command** rebuild of the engine-merge campaign (after `/office-hours`, `/plan`, `/code-review`, `/founder-review`) and the **execution-loop track** — the most architecturally entangled, landing two deferred foundations at once. Rebuilt `/work` from a 39-line facilitator stub into a real **execution-loop engine that merges CE's `ce-work` execution engine (Jeff-preferred spine) with gstack `ship`/`land-and-deploy`'s autonomy + readiness/staleness gates** — a genuine two-source merge (like `/code-review`), self-contained (no vendoring, no runtime dep). Position in the lifecycle: the loop's execution hub — every real build runs through it. Schema, the four interview answers, the PR-ready-boundary / saga-primary-writer / code-review-identity-handshake / computed-staleness / canary-relocation / qa-resume-advisory decisions, and rejected alternatives recorded in DECISIONS [#work-engine-rebuild](DECISIONS.md#work-engine-rebuild).

**Engine — five numbered phases.** Enter + scan saga + triage + detect round-N → setup + task-list + backend → execute phase-by-phase → record (saga tick + work-session + issue progress) → code-review gate + PR-ready + continuation routing.

**What shipped.**
- Rebuilt `/work` SKILL (`skills/work/SKILL.md`): the five-phase engine. **Saga primary writer** (saga-spec §11) — `scan`/`restore` on re-entry, mint/advance `lifecycle_phase=work` with `--plan-path` set + saved on-branch, a tick per phase (round bump via `--rounds-seen`, never `next_round`); **mints + names the exact saga `/code-review` (append-only/never-mint) appends `review_paths` to**, and passes the saga `kind`+`id` into the programmatic `/code-review` call so the append hits that thread — closing the forward-coupling for both issue AND ad-hoc task work. **PR-ready boundary + round-N PR continuation loop** (`/work` owns re-entry, NOT `/resume`) — a total `gh pr view --json` read + a total transition table (draft/review-required/changes-requested/conflicting/failing-checks/approved-stale/approved-fresh/merged/closed). **Merge is a confirmed git op `/work` owns** (`gh pr merge` under explicit confirmation, never silent); only deploy mutation delegated to `infiquetra-deploy`. **Hard review gate** — block PR-ready on P0/P1 (code-review envelope + saga `review_paths`) OR a computed-stale review; honest recorded override. `requires_hard_test_gate` blocks risky change-kinds. **Boundary** — never silently mutates GitHub, owns no deploy/canary, files no SDLC issues, advances `lifecycle_phase` no further than `work`.
- Three new references: `skills/work/references/{execution-strategy,test-and-gates,pr-continuation-loop}.md` (CE complexity triage + task-list-from-U-IDs + Execution-Strategy table + Parallel Safety Check + the `recommend_execution_backend()` integration; test discovery + scenario-completeness + system-wide check + hard-gate + computed staleness + the gstack autonomy contract + merge-base-before-tests; the total PR-state transition table).
- **NEW code** `recommend_execution_backend()` in `scripts/lifecycle_state.py` (the deferred operator-choice helper — reuses `should_offer_team_execution`, `alternatives` independent of precedence so overlap offers both, `{recommended, rationale, alternatives, omit_ultracode}`) + `main()` refactored into `normalize` + `recommend-backend` subcommands. Closes the 0.5.0 operator-choice deferral.
- **Extended code** `scripts/issue_progress.py` CLI — `parse_args`/`main` now forward the function's full field set (`--work-session-path --commit-sha --checks-run` [pipe] `--blockers --pr-url --review-status --doc-review-artifact --doc-review-blocked --doc-review-findings` [pipe] `--doc-review-override --deploy-status --workflow-url --evidence-link`); the Phase-4 progress comment was previously uninvokable from markdown (dead wiring).
- `commands/work.md` — thin launcher (saga-primary-writer + PR-ready boundary + continuation loop + hard review gate + merge-under-confirmation; no deploy/canary ownership).
- **Surgical flip** `references/operator-choice.md` — the deferred-helper notes (§intro, §6 [stale `/plan`+`/work` writer framing rewritten], §7 `/work` row) updated now that the helper shipped, gated on the SKILL containing the runnable `recommend-backend` CLI line.
- Mechanism-floor contract test (`test_work_engine_merge_contract`) — a runnable `saga.py save --lifecycle-phase work --rounds-seen …`, a `recommend-backend` CLI invocation, the PR `--json` read incl. state/reviewDecision/check-status, a `git rev-list …HEAD` staleness computation, the extended `issue_progress.py` CLI call, the saga-identity handoff into `/code-review`, ≥60-line reference floors — plus helper unit+CLI tests and `issue_progress` CLI tests; version pin → `0.10.0`; existing work/loop/lifecycle_state/issue_progress assertions preserved.
- Work-session artifacts land in the canonical `docs/work-sessions/` (no new dir — `handoff_envelope.py` already classifies it). **Operator-choice** offer — all three backends via the new `recommend_execution_backend()` CLI, pre-selected + alternatives, operator confirms.
- Version bumps: plugin `0.10.0`, marketplace entry `0.10.0`; CHANGELOG. keywords stay at 10 (`work` is not a keyword).

**Follow-ups.** gstack's canary-verify + offer-revert was **read-then-relocated** to `infiquetra-deploy` (a deliberate brief deviation, deploy/canary is deploy's hard boundary) — the capability is QUEUED there, worth-it-when a prod deploy path exists (QUEUED [#infiquetra-deploy-canary-verify-revert](QUEUED.md#infiquetra-deploy-canary-verify-revert)). The `qa` `lifecycle_phase` advance is honestly deferred to the `/qa` rebuild — the saga sits at `work` post-merge; `/qa`/`/resume` routing is advisory. Post-merge follow-up fills the squash SHA into DECISIONS + this entry. `/resume`, `/qa`, `/loop` remain the next likely rebuilds.

**Refs.** DECISIONS [#work-engine-rebuild](DECISIONS.md#work-engine-rebuild), [#lifecycle-engine-merge-campaign](DECISIONS.md#lifecycle-engine-merge-campaign). Lands the deferred operator-choice helper — DECISIONS [#operator-choice-framework](DECISIONS.md#operator-choice-framework). Saga primary-writer — DECISIONS [#saga-schema-foundation](DECISIONS.md#saga-schema-foundation), spec `plugins/infiquetra-lifecycle/references/saga-spec.md` §11. Forward-coupling partner — DECISIONS [#code-review-engine-rebuild](DECISIONS.md#code-review-engine-rebuild). Relocated canary capability — QUEUED [#infiquetra-deploy-canary-verify-revert](QUEUED.md#infiquetra-deploy-canary-verify-revert). Work-session home: `docs/work-sessions/`. Plan `.claude/plans/ok-we-yestereday-we-scalable-fox.md`.

### `/founder-review` rebuild — gstack `plan-ceo-review` port (scope/ambition review lens)  {#founder-review-engine-rebuild-shipped}

**SHIPPED 2026-06-03** (`infiquetra-lifecycle` `0.9.0`, PR #179, squash e4eedf2). Was QUEUED P1 `#founder-review-engine-merge`.

**Summary.** Fourth **command** rebuild of the engine-merge campaign (after `/office-hours`, `/plan`, `/code-review`). Rebuilt `/founder-review` (alias `/ceo-review`) from a 20-line stub into a real **scope/ambition/direction review engine ported from gstack `plan-ceo-review`** — a **PORT, not a merge**: gstack is the sole engine source (4 scope modes + 18 internalized CEO cognitive patterns + 9 Prime Directives + an adapted pre-review system audit), with only CE `ce-product-pulse`'s sharpened no-false-precision posture stolen. Position in the lifecycle: the third member of the review trio (`/doc-review` = plan-readiness, `/code-review` = code quality, **`/founder-review` = is this the right, ambitious-enough thing to build at all?**), firing **upstream of execution** on a `/plan` artifact, a `STRATEGY.md`, a `/brainstorm` output, or an ad-hoc scope question. Schema, the four interview answers, the scope-layer + closed-loop-routing / target-conditional-ceremonies / no-saga-write / scope-decision-dir / sharpened-posture-steal / office-hours-escape / port-not-merge decisions, and rejected alternatives recorded in DECISIONS [#founder-review-engine-rebuild](DECISIONS.md#founder-review-engine-rebuild).

**Engine — numbered phases.** Enter + detect target + adapted system audit → scope challenge + mode selection (Step 0, target-conditional 0C-bis/0E + office-hours escape) → mode-specific scope analysis (4 branches, capped per-expansion opt-in) → founder rigor pass (directives + patterns as scope lenses → named findings + closed-loop handback) → synthesize the scope-decision artifact → route + operator-choice.

**What shipped.**
- Rebuilt `/founder-review` SKILL (`skills/founder-review/SKILL.md`): the scope-layer engine. **Four committed scope modes** (Expansion/Selective/Hold/Reduction, `AskUserQuestion` + context-defaults, no silent drift). **Review-only** — challenges scope/ambition/direction + captures a scope decision; never makes code changes, commits/pushes/PRs, files SDLC issues, or *records* the direction (`/strategy` records). **CLOSED-LOOP routing** — accepted scope → `/plan`; the (re-)expanded plan written/updated + handed back to `/doc-review` + `/code-review` with the concrete path (not a hand-wave); Phase 3 emits named scope findings. **Target-conditional Step-0 ceremonies** (0C-bis/0E run on plan targets, skip/recast on strategy/brainstorm/scope-question; office-hours escape in 0A). **NO saga write** — runs upstream/pre-saga; persistence = the `docs/founder-reviews/` artifact + the journal ADR.
- Two new references: `skills/founder-review/references/{ceo-cognition,review-modes}.md` (18 CEO patterns + 9 Prime Directives + Engineering Preferences + the sharpened no-false-precision posture; the 4 modes + expansion-framing + ceremonies + adapted pre-review audit + target-conditional 0C-bis/0E gating + the scope-decisions artifact format + office-hours escape).
- `commands/founder-review.md` + `commands/ceo-review.md` (alias preserved) — thin launchers (review-only + the boundary, no saga mention).
- Durable artifacts land in their own `docs/founder-reviews/` scope-decision dir (intentionally NOT a `/handoff` source, NOT `docs/reviews/`), carrying the Mode + Vision + a Scope-Decisions table + the founder verdict + the next-command handback. **Operator-choice** offer — all three backends (`inline` | `team-execution` | `cc-workflows-ultracode`) cited at the plugin-root path (`references/operator-choice.md`).
- Mechanism-floor contract test (4 mode names + ≥8/18 CEO patterns + ≥6/9 Prime Directives + commit-no-drift literal + expansion-framing mechanism + the A/B/C opt-in + cap + target-conditional gating + the closed-loop handback token + `docs/founder-reviews/` + boundary negatives + operator-choice citation + NO `saga.py`/`--review-paths` reference + a ≥60-line reference floor — a vibes-y reskin FAILS) + version pin → `0.9.0`; existing founder-review + ceo-review assertions preserved.
- Version bumps: plugin `0.9.0`, marketplace entry `0.9.0`; CHANGELOG. keywords stay at 10 (`founder-review` is not a keyword).

**Follow-ups.** A standalone `/pulse` live-product telemetry component (CE `product-pulse` as the engine source) is QUEUED — worth-it-when Infiquetra has a live product with real telemetry; pre-revenue greenfield has no data yet (QUEUED [#pulse-live-telemetry-component](QUEUED.md#pulse-live-telemetry-component)). Post-merge follow-up fills the squash SHA into DECISIONS + this entry. `/work`→`/loop` (the execution-loop track, where the deferred operator-choice CLI helper lands) and `/qa` remain the next likely rebuilds.

**Refs.** DECISIONS [#founder-review-engine-rebuild](DECISIONS.md#founder-review-engine-rebuild), [#lifecycle-engine-merge-campaign](DECISIONS.md#lifecycle-engine-merge-campaign). Sibling review-lens rebuild: [#code-review-engine-rebuild](DECISIONS.md#code-review-engine-rebuild). Operator-choice contract: `plugins/infiquetra-lifecycle/references/operator-choice.md`. Queued `/pulse`: QUEUED [#pulse-live-telemetry-component](QUEUED.md#pulse-live-telemetry-component). Scope-decision home: `docs/founder-reviews/`. Plan `.claude/plans/ok-we-yestereday-we-scalable-fox.md`.

### `/code-review` rebuild — CE `ce-code-review` spine + gstack `/review` scope/plan audit  {#code-review-engine-rebuild-shipped}

**SHIPPED 2026-06-03** (`infiquetra-lifecycle` `0.8.0`, PR #177, squash 0a9d8cd). Was QUEUED P1 `#rebuild-code-review-engine-merge`.

**Summary.** Third **command** rebuild of the engine-merge campaign (after `/office-hours` and `/plan`). Rebuilt `/code-review` from a 20-line stub into a real **pre-PR code-quality review engine that merges CE's `ce-code-review` findings/validator/judgment-lens spine (Jeff-preferred backbone) with gstack `/review`'s scope-drift detection + plan-completion audit + high-signal checklist categories** — a self-contained infiquetra engine. Position in the lifecycle: a within-work gate at the **work→PR boundary** (after `/work` produces code, before PR/merge) — NOT the saga `LIFECYCLE_PHASES` `review` slot (that's `/doc-review`'s plan→work gate). Schema, the four interview answers, the gate-only / saga-append-only / mode-based-validator / own-dir decisions, and rejected alternatives recorded in DECISIONS [#code-review-engine-rebuild](DECISIONS.md#code-review-engine-rebuild).

**Engine — six numbered phases.** Enter + scope → intent + built-vs-planned audit → select lenses (judgment) → review fan-out → merge + validate → report + route + saga.

**What shipped.**
- Rebuilt `/code-review` SKILL (`skills/code-review/SKILL.md`): the six-phase engine. **Gate-only** — reports + classifies + routes; never mutates code, commits, pushes, opens PRs, or files SDLC issues; the programmatic mode (for `/work`'s future call) is zero-write to reviewed code. **Judgment-based lenses** — 4 always-on (correctness, security, testing, maintainability/conventions) + conditional-by-judgment including a distinct deploy/migration-verification lens + reliability lens; gstack Rails/Swift/Stimulus specialists dropped, its high-signal checklist categories folded into the lens checklists. **Built-vs-planned audit** — informational scope-drift (CLEAN/DRIFT/REQUIREMENTS-MISSING) + the 5-state plan-completion audit (DONE/PARTIAL/NOT-DONE/CHANGED/UNVERIFIABLE) + the 3 verification modes, reading `docs/plans/` + journal. **Mode-based validator** — programmatic validates all Stage-A survivors (capped 15); interactive lets the operator validate. **Saga's first review-track consumer** — append-only to an EXISTING work-thread saga (scan-first, never mint), appending `review_paths` + `orchestration_mode`, preserving `lifecycle_phase`; never `git add` the tick.
- Four new references: `skills/code-review/references/{lens-catalog,findings-schema,validator,built-vs-planned}.md` (lens set + distinct deploy/migration lens; severity/anchored-confidence/autofix_class/owner findings schema; the independent validator template; the scope-drift + 5-state plan-completion audit).
- `commands/code-review.md` — thin launcher reflecting the engine (gate-only + the saga `review_paths` append + no `git add` + the hard boundary).
- Durable artifacts land in their own `docs/code-reviews/` dir (NOT `docs/reviews/` — avoids the `handoff_envelope.py`/`sdlc_manager.py` plan-ready classifier collision), carrying the reviewed SHA + a review-result contract. **Operator-choice** offer — all three backends (`inline` | `team-execution` | `cc-workflows-ultracode`) cited at the plugin-root path (`references/operator-choice.md`).
- Richness-floor contract tests (state/mode/anchor/class/owner counts + min line counts a thin port fails) + version pin → `0.8.0`; all 3 existing code-review test assertions preserved.
- Version bumps: plugin `0.8.0`, marketplace entry `0.8.0`; CHANGELOG.

**Follow-ups.** The safe-autofix *apply* mode is a deliberate future add (gate-only ships first). The forward-coupling is now closed — the `/work` rebuild (SHIPPED 0.10.0) mints/advances + names the work-thread saga code-review appends to AND reads code-review's `review_paths`/blocked-status as a gate input — see [#work-engine-rebuild-shipped](#work-engine-rebuild-shipped). `/founder-review` was the next review-lens rebuild.

**Refs.** DECISIONS [#code-review-engine-rebuild](DECISIONS.md#code-review-engine-rebuild), [#lifecycle-engine-merge-campaign](DECISIONS.md#lifecycle-engine-merge-campaign). Operator-choice contract: `plugins/infiquetra-lifecycle/references/operator-choice.md`. Saga foundation: DECISIONS [#saga-schema-foundation](DECISIONS.md#saga-schema-foundation). Plan `.claude/plans/ok-we-yestereday-we-scalable-fox.md`.

### `/plan` rebuild — CE `ce-plan` artifact engine + gstack `spec` HOW-interrogation  {#plan-engine-rebuild-shipped}

**SHIPPED 2026-06-02** (`infiquetra-lifecycle` `0.7.0`, PR #175, squash a13ba68). Was QUEUED P1 `#rebuild-plan-engine-merge`.

**Summary.** Second **command** rebuild of the engine-merge campaign (after `/office-hours`). Rebuilt `/plan` from a 27-line stub into a real **implementation-plan engine that merges CE's `ce-plan` structured-artifact engine (Jeff-preferred spine) with gstack `spec`'s code-grounded HOW-interrogation front end** — a self-contained infiquetra engine. Position in the lifecycle: `/plan` answers "How should it be built?". Schema, the four interview answers, the review-phase rationale, and rejected alternatives recorded in DECISIONS [#plan-engine-rebuild](DECISIONS.md#plan-engine-rebuild).

**Engine — six numbered phases.** Enter + warranted-gate → ground (HOW) → interrogate (HOW) → synthesize the plan artifact → condensed deepening pass (conditional) → saga + route + operator-choice.

**What shipped.**
- Rebuilt `/plan` SKILL (`skills/plan/SKILL.md`): the six-phase engine. **HOW-only interrogation** (assumes the WHAT settled upstream; open WHAT-ambiguity bounces with a one-way recommendation to run `/brainstorm` first, with a "do not claim `/brainstorm` accepts a handoff" guard). **Warranted-gate** + scope classes. **Condensed deepening** self-review (not CE's full 248-line pass). Routes to `/doc-review` (recommended next) before `/work`. Hard boundary: does NOT implement, does NOT file SDLC issues (`sdlc-manager`), does NOT run the full review gauntlet (`/doc-review`).
- `skills/plan/references/plan-sections.md` — the artifact contract (R-ID / KTD / U-ID + per-unit test scenarios + explicit test-file paths; three-audience; `origin:` / `Implementation Units` / `Key Technical Decisions` / `U1` markers so `/doc-review` recognizes the doc) + the condensed deepening rubric.
- `skills/plan/references/interrogation.md` — the gstack HOW-interrogation register (code-grounded, cite `path:line`).
- `commands/plan.md` — thin launcher (preserves the handoff-maturity note).
- One **plan saga** via the saga CLI (`scripts/saga.py save --lifecycle-phase plan`, runnable, with a "never `git add` the tick" boundary); epic/multi-unit splits hand to `sdlc-manager`.
- **Operator-choice** offer — all three backends (`inline` | `team-execution` | `cc-workflows-ultracode`) cited by path (`references/operator-choice.md`), offered not defaulted.
- Version bumps: plugin `0.7.0`, marketplace entry `0.7.0`; CHANGELOG.

**Seam left queued.** The `/brainstorm` ↔ gstack `spec` WHAT-interrogation ownership seam (where the relentless WHAT-rigor lands — fold into `/brainstorm` vs the standalone `/spec`) is a deliberate downstream decision-point — see QUEUED [#brainstorm-spec-interrogation-seam](QUEUED.md#brainstorm-spec-interrogation-seam).

**Refs.** DECISIONS [#plan-engine-rebuild](DECISIONS.md#plan-engine-rebuild), [#lifecycle-engine-merge-campaign](DECISIONS.md#lifecycle-engine-merge-campaign). Operator-choice contract: `plugins/infiquetra-lifecycle/references/operator-choice.md`. Saga foundation: DECISIONS [#saga-schema-foundation](DECISIONS.md#saga-schema-foundation).

### `/office-hours` rebuild — two-mode gstack diagnostic as the frame-finding front door  {#office-hours-engine-rebuild-shipped}

**SHIPPED 2026-06-02** (`infiquetra-lifecycle` `0.6.0`, PR `#173`, squash `aec888c`). Was QUEUED P1 `#rebuild-office-hours-engine`.

**Summary.** First **command** rebuild of the engine-merge campaign (the two prior ships — saga, operator-choice — were foundations). Rebuilt `/office-hours` from a 23-line facilitative stub into a real **two-mode thought-partner diagnostic faithfully ported from gstack** and adapted to infiquetra: the Think-phase frame-finding front door that `/ideate` routes unframed asks to and `/brainstorm` bounces open thought-partner work back to. Self-contained — ports the gstack engine, no gstack vendoring, no runtime dep on CE. Schema, the four interview answers, adaptations, and rejected alternatives recorded in DECISIONS [#office-hours-engine-rebuild](DECISIONS.md#office-hours-engine-rebuild).

**Two modes.** **Startup mode** — gstack's six market/customer forcing questions, made **stage-aware** with a pre-traction hypothesis-forming register (Infiquetra is pre-revenue greenfield, so questions form hypotheses rather than audit non-existent traction). **Builder mode** — discovery/shaping for infra/workflow/internal-tooling, infiquetra's high-frequency mode, carrying a real depth floor (not a one-liner). Modes switch mid-session.

**What shipped.**
- Rebuilt `/office-hours` SKILL: two-mode engine (Startup [stage-aware] + Builder [depth floor]), anti-sycophancy + pushback re-targeted (hard on vagueness/ungrounded assumptions, not operator judgment; push-twice + escape hatches), **HARD GATE** (never implement/plan/file-SDLC-issue — frame-finding only), route-always + plural clean exits (`/brainstorm`, `/plan`, `/strategy`).
- New artifact dir `docs/office-hours/` for the optional frame note (frontmatter `kind: frame-note`) — kept out of `docs/ideation/` to avoid the `/ideate` resume-scan collision; wired into the `/loop` SKILL + README artifact lists.
- Version bumps: plugin `0.6.0`, marketplace entry `0.6.0`; CHANGELOG.

**Refs.** DECISIONS [#office-hours-engine-rebuild](DECISIONS.md#office-hours-engine-rebuild), [#lifecycle-engine-merge-campaign](DECISIONS.md#lifecycle-engine-merge-campaign). Frame-note home: `docs/office-hours/`.

### Operator-choice framework — execution-backend decision contract (doc-only)  {#operator-choice-framework-shipped}

**SHIPPED 2026-06-02** (`infiquetra-lifecycle` `0.5.0`, PR `#171`, squash `e935bd4`). Was QUEUED P1 `#operator-choice-orchestration-framework`.

**Summary.** Shipped the operator-choice framework as a **doc-only foundation** of the engine-merge campaign: the canonical decision contract for the three execution backends — `inline` | `team-execution` | `cc-workflows-ultracode` — that lifecycle commands cite when they ask the operator which backend to run work through. Lifecycle owns the **choice**, not execution. Schema and rationale (auto-recommend + always-confirm, the `should_offer_team_execution`-plus-consensus / parallel-fan-out triggers, offer-BOTH-on-overlap, the hide-when-Workflow-absent capability gate, `/loop` + `/work` scope) recorded in DECISIONS [#operator-choice-framework](DECISIONS.md#operator-choice-framework).

**Scope — a consumed doc + two offer hooks (deliberate).** This ships the reference doc, the two prose offer hooks, and a `saga-spec` cross-reference fix. The CLI-backed `recommend_execution_backend()` helper is **DEFERRED to the `/work` rebuild**, where it gets a real caller — adding it now would create an uncallable helper that drifts against the doc (the verified state of the existing `should_offer_team_execution`, defined but never called outside its test). The originally-queued sizing was "M / no scripts"; this ship honors that.

**What shipped.**
- `plugins/infiquetra-lifecycle/references/operator-choice.md` — the decision contract (the three backend enum strings, when each is offered, the always-confirm posture, the capability gate, graceful fallback). Complements `references/saga-spec.md` (storage contract).
- Short prose offer hooks in `/loop` and `/work` SKILLs that cite the doc and inline the choices (referencing the brainstorm channel-inline convention — redis-channel sessions cannot call AskUserQuestion — rather than copying it).
- `saga-spec.md` cross-reference fix tying `orchestration_mode` storage to the decision contract.
- Version bumps: plugin `0.5.0`, marketplace entry `0.5.0`; CHANGELOG.

**Consumers.** `/loop` and `/work` carry the offer hooks now; the other command rebuilds cite this doc as they land. The CLI-backed helper `recommend_execution_backend()` **SHIPPED with the `/work` rebuild** (0.10.0) — see [#work-engine-rebuild-shipped](#work-engine-rebuild-shipped), closing the deferral.

**Refs.** DECISIONS [#operator-choice-framework](DECISIONS.md#operator-choice-framework), [#lifecycle-engine-merge-campaign](DECISIONS.md#lifecycle-engine-merge-campaign). Decision contract: `plugins/infiquetra-lifecycle/references/operator-choice.md`.

### Saga foundation — durable, resumable work-state envelope (P0)  {#saga-foundation-shipped}

**SHIPPED 2026-06-02** (`infiquetra-lifecycle` `0.4.0`, PR `#170`). Was QUEUED P0 `#saga-concept-vecu-durable-resumable-work-state`.

**Summary.** Shipped the first foundation of the engine-merge campaign: a unified `saga` durable/resumable work-state primitive — a stable-id `save`/`restore`/`scan` engine writing gstack-style timestamped envelope files, plus the canonical spec the four consumers implement against when they're rebuilt. Schema and rationale (derived `kind-id` identity, append-only envelope log + derived index, three stored state axes + derived maturity, snapshot list semantics, plugin-level `references/` convention) recorded in DECISIONS [#saga-schema-foundation](DECISIONS.md#saga-schema-foundation).

**Scope — an unconsumed primitive (deliberate).** This ships the engine, the three legacy scripts refactored into thin wrappers, and the spec. **No command actually calls `restore`/`scan` after this PR** — consumer wiring is each consumer's own queued item. The new engine is validated by its own unit tests + manual smoke; the wrappers keep every legacy CLI flag and JSON key. The originally-queued sizing was "M / spec-only"; the user chose full-unify-now + characterize-first testing, making it realistically effort L — an accepted, deliberate growth, one PR not a doc.

**What shipped.**
- `plugins/infiquetra-lifecycle/scripts/saga.py` — the engine: derived `kind-id` (`issue-<N>`/`task-<slug>`, sticky), append-only `sagas/<saga_id>/<YYYYMMDD-HHMMSS>.md` envelope log (filename-as-order, never mtime), derived atomic `state.json` index, gstack frontmatter+body envelope, `save`/`restore`/`scan`/`context` ops with `root:Path` + `now`/`runner` injection.
- The three legacy scripts (`scaffold_checkpoint.py`, `find_inflight_work.py`, `load_saga_context.py`) refactored into thin wrappers delegating to `saga.py` (zero CLI-flag/JSON-key removals).
- `plugins/infiquetra-lifecycle/references/saga-spec.md` — the canonical contract (new plugin-level `references/` convention).
- Tests `tests/test_infiquetra_lifecycle_saga.py` (characterize-first → intended-behavior); plugin-version + `saga.py`-existence updates in `tests/test_infiquetra_lifecycle_plugin.py`.
- Version bumps: plugin `0.4.0`, marketplace entry `0.4.0`; CHANGELOG with the behavior-change + upgrade warning (complete in-flight loops before upgrading; legacy `checkpoints/` read as fallback for one version).

**Consumers.** `/plan` (0.7.0, ARCHIVE [#plan-engine-rebuild-shipped](#plan-engine-rebuild-shipped)), `/code-review` (0.8.0, ARCHIVE [#code-review-engine-rebuild-shipped](#code-review-engine-rebuild-shipped)), `/work` (0.10.0 primary writer, ARCHIVE [#work-engine-rebuild-shipped](#work-engine-rebuild-shipped)), `/loop` (0.11.0 router/resume + the additive scan picker-field extension, ARCHIVE [#loop-engine-rebuild-shipped](#loop-engine-rebuild-shipped)), and `/resume` (0.12.0 — adds the all-ticks `read_ticks` reader, ARCHIVE [#resume-engine-rebuild-shipped](#resume-engine-rebuild-shipped)) now implement against this spec.

**Refs.** DECISIONS [#saga-schema-foundation](DECISIONS.md#saga-schema-foundation), [#lifecycle-engine-merge-campaign](DECISIONS.md#lifecycle-engine-merge-campaign). Plan `.claude/plans/ok-we-yestereday-we-scalable-fox.md`.

### Correct Asgard/Olympus model before SDLC handoff work  {#asgard-olympus-model-before-handoff}

**SHIPPED 2026-05-30** (`infiquetra-sdlc` commit `5fe5d91`; plugin sync commit `90956a4`).

**Summary.** Removed the stale assumption that Asgard feeds or promotes work into Mount Olympus
before building the SDLC handoff flow.

**What shipped.**
- Canonical `infiquetra-sdlc` docs and schema now define Asgard and Olympus as sibling target
  boards.
- Cross-team movement is explicit operator transfer, route, clone, or link action only.
- `sdlc-manager` now vendors the corrected schema, renders Asgard transfer notes, and no longer
  warns that every Asgard draft has Olympus readiness gaps.
- Prompt-alignment tests now reject the stale Asgard-to-Olympus promotion language in active
  plugin surfaces.

**Refs.**
- Requirements: [Infiquetra Loop SDLC Handoff](../brainstorms/2026-05-30-infiquetra-loop-sdlc-handoff-requirements.md).
- Plan: [Add SDLC handoff flow](../plans/2026-05-30-002-feat-sdlc-handoff-flow-plan.md).

### Asgard/Olympus issue readiness workflow for `sdlc-manager`  {#asgard-olympus-issue-readiness}

**SHIPPED 2026-05-30** (PR #159, commit `74cd372`).

**Summary.** Added a prepared issue workflow that turns source text into reviewable Asgard or
Mount Olympus drafts, then creates issues only after readiness checks and a confirmed mutation
plan.

**What shipped.**
- `issue prepare` writes markdown drafts and JSON sidecars under `docs/sdlc-issue-drafts/`.
- `issue create-prepared` re-runs readiness, shows a mutation plan, repairs missing
  labels/templates, handles missing project mappings through PR flow, and records created issue
  state back onto drafts.
- Asgard and Mount Olympus readiness profiles with safe starting statuses.
- Natural-language skill/command/operator guidance for Asgard/Olympus issue creation from text.
- Plugin and marketplace metadata bumped to `1.6.0`.
- Unit, mocked mutation, and prompt alignment tests.

**Refs.**
- Ideation doc: [SDLC Manager Asgard/Olympus issue readiness](../ideation/2026-05-30-sdlc-manager-asgard-olympus-issue-readiness.md).
- Requirements: [SDLC Manager Issue Prepare Requirements](../brainstorms/2026-05-30-sdlc-manager-issue-prepare-requirements.md).
- Plan: [Add SDLC issue prepare workflow](../plans/2026-05-30-001-feat-sdlc-issue-prepare-workflow-plan.md).
- Learning: [Prepared issue creation needs an artifact boundary before mutation](LEARNINGS.md#prepared-issue-artifact-boundary).

### Align sdlc-manager prompts with current SDLC schema and release metadata  {#sdlc-manager-prompt-alignment}

**SHIPPED 2026-05-30** (PR #159, commit `74cd372`).

**Summary.** Aligned `sdlc-manager` operator prompts, command docs, issue/label references,
release metadata, and marketplace registration with the current Jeff Intent, Asgard, and Mount
Olympus operating model.

**What shipped.**
- Updated handwritten prompt/reference docs to use current actionable labels:
  `hermes-task`, `needs-plan`, and the type label.
- Kept `needs-analysis` and `needs-triage` documented only as legacy auto-label fallback labels.
- Fixed `sdlc-operator` Hermes-actionability wording and output examples.
- Bumped `sdlc-manager` plugin and marketplace metadata to `1.5.0`.
- Added prompt/reference drift guards for metadata, labels, and actionability claims.

**Refs.**
- Ideation doc: [2026-05-30-sdlc-manager-alignment-pass.md](../ideation/2026-05-30-sdlc-manager-alignment-pass.md).
- Learning: [Prompt docs need their own drift guards](LEARNINGS.md#prompt-docs-need-drift-guards).

### Add Infiquetra loop `/doc-review` command  {#infiquetra-loop-doc-review}

**SHIPPED 2026-05-29** (commit pending).

**Summary.** Added `/doc-review` to `infiquetra-loop` as an implementation-readiness review
surface for plans, requirements documents, formal SDLC artifacts, and strategy/scope documents
that are about to drive implementation.

**What shipped.**
- `/doc-review` command and skill.
- Safe in-place fixes, P-level findings, durable `docs/reviews/` artifact triggers, and a
  review-result contract.
- Formal SDLC routing through `blueprint-reviewer` delegates followed by readiness review.
- `/work` prompt/block guidance and issue-progress rendering fields for doc-review summaries.
- README, changelog, marketplace/plugin metadata, and contract tests.

**Refs.**
- Idea doc: [2026-05-29-infiquetra-loop-doc-review.md](../ideation/2026-05-29-infiquetra-loop-doc-review.md).
- Requirements: [2026-05-29-infiquetra-loop-doc-review-requirements.md](../brainstorms/2026-05-29-infiquetra-loop-doc-review-requirements.md).
- Plan: [2026-05-29-001-feat-infiquetra-doc-review-plan.md](../plans/2026-05-29-001-feat-infiquetra-doc-review-plan.md).
- Plan review: [2026-05-29-infiquetra-doc-review-plan-review.md](../reviews/2026-05-29-infiquetra-doc-review-plan-review.md).

### PR #112 — register `blueprint-reviewer` in marketplace + gitignore `.claude/`  {#pr-112-marketplace-fix}

**SHIPPED 2026-05-01** (commit `4da5705`, squash-merged from `fix/marketplace-register-blueprint-reviewer`).

**Summary.** Two-commit PR that:
1. Added the missing `blueprint-reviewer` entry to `.claude-plugin/marketplace.json` (15 plugins after the change, was 14).
2. Added `.claude/` to `.gitignore` and removed stray files `swap-pane` (0 bytes) and `uv.lock` (242 KB, unused — see DECISIONS).

**Why this matters in the archive.** This is the originating ship for the journal's first three real entries — the LEARNING about marketplace drift, the LEARNING about the `Edit` guard pattern, and the DECISION about repo hygiene. Future readers tracing those entries' "fixed in commit X" / "shipped via Y" links land here.

**Refs.**
- LEARNINGS: [marketplace drift](LEARNINGS.md#marketplace-drift), [marketplace edit guard](LEARNINGS.md#marketplace-edit-guard).
- DECISIONS: [gitignore `.claude/` + no `uv.lock`](DECISIONS.md#gitignore-claude-and-no-uv-lock).

---

## Rejected

### `/ce-doc-review` compatibility alias for `infiquetra-loop`  {#rejected-ce-doc-review-alias}

**REJECTED 2026-05-29.**

**Reason.** During requirements discussion, the user chose not to preserve the CE command name.
The Infiquetra command surface should be `/doc-review`.

**Revisit when.** Multiple users migrate from Compound Engineering and repeatedly fail to find
the Infiquetra command after normal README and marketplace documentation.

---

## Superseded

### "gstack has no scoring formula — its health score is LLM-eyeballed" (pre-correction of `#source-fidelity-cuts-both-ways`)  {#source-fidelity-no-formula-superseded}

**SUPERSEDED 2026-06-03** (same session it shipped) by the inline correction in LEARNINGS [#source-fidelity-cuts-both-ways](LEARNINGS.md#source-fidelity-cuts-both-ways). The pre-correction version made the exact source-fidelity error that very entry warns against.

**Original (pre-correction) claims.**
- Evidence (b): "gstack has **no scoring formula** — its health score is LLM-eyeballed."
- Fix: "after the DA located the score's 'implementation' in `gen-skill-docs.ts` (a generator, not a formula), **dropped the score**."
- Generalizable rule (second clause): "a `.tmpl` that *slots* a value (`{SCORE}/100`) is not an algorithm, and **a value with no formula behind it should be dropped**, not faithfully reproduced as false precision."

**Why superseded.** All three are false-to-source. gstack's QA health score IS a deterministic weighted formula: `scripts/resolvers/utility.ts:286-321` defines a **Health Score Rubric** (per-category deductions Critical -25 / High -15 / Medium -8 / Low -3 at `:302-305`, explicit category weights — Functional 20%, Console/UX/Accessibility 15%, … at `:308-318`, and `score = Σ (category_score × weight)` at `:321`), exported as `generateQAMethodology` (`utility.ts:89`), wired `QA_METHODOLOGY: generateQAMethodology` (`resolvers/index.ts:50`) — i.e. it IS the `{{QA_METHODOLOGY}}` macro `qa/SKILL.md.tmpl:122` injects. The DA read `gen-skill-docs.ts` (the file that *names* the macro) and the bare `{SCORE}/100` template placeholder, then stopped — it did not follow the dispatch the last hop into `resolvers/utility.ts`, the precise "read the implementation, not the scaffold" failure the entry exists to teach.

**The drop decision still stands** — but on the **correct** rationale: the rubric's per-category inputs are LLM-assigned severity counts, so the resulting 0-100 number is **false precision**, not a value with no formula. The corrected entry's rule now says: follow the dispatch the last hop, and drop a value for the *true* reason (LLM-assigned inputs → false precision), never for a convenient-but-unverified one ("no formula exists"). Q2 flip and the zero-new-Python outcome are unaffected.

**Refs.** Corrected inline: LEARNINGS [#source-fidelity-cuts-both-ways](LEARNINGS.md#source-fidelity-cuts-both-ways). The rebuild: DECISIONS [#qa-engine-rebuild](DECISIONS.md#qa-engine-rebuild), ARCHIVE [#qa-engine-rebuild-shipped](#qa-engine-rebuild-shipped).

### No `uv.lock` while uv is not canonical  {#superseded-no-uv-lock-decision}

**SUPERSEDED 2026-05-08** by DECISIONS [uv canonical sync](DECISIONS.md#uv-canonical-sync).

**Original decision.** Add `.claude/` to `.gitignore`. Do not track `uv.lock`. Stray `swap-pane` (0-byte file from a tmux operation) deleted as one-off cleanup.

**Original rejected alternatives.**
- *Track `.claude/settings.local.json`.* Rejected: file holds per-user permission grants for the Claude Code session. Sharing one user's allowed-tool list would either leak local preferences or get blindly overwritten by the next user. The file is named `.local.json` for a reason.
- *Track `.claude/context/sdlc-plan-state.json`.* Rejected: mid-session orchestration state from `sdlc-manager`. Stale immediately after the session ends; would create misleading commits if pushed.
- *Track `uv.lock`.* Rejected: `pyproject.toml` declares `requires = ["hatchling"]` with no `[tool.uv]` section. The repo uses hatchling for building and ad hoc `pip`/`uv` invocations for local dev tooling, so there was no reproducible-build promise being made by checking in a uv lockfile. Tracking it would imply uv was part of the build path.

**Original rationale.** `.claude/` content is per-user / per-session by design (settings.local + context state). `uv.lock` would make a build-tool claim the repo was not making at the time. Both were pure noise in the diff and confused contributors about what was authoritative.

**Why superseded.** The repo now adopts uv as the canonical dependency sync path and CI installs from `uv.lock` with `uv sync --locked --extra dev`.

---
