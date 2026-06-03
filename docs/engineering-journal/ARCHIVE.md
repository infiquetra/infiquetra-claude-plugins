# Archive — Infiquetra Claude Plugins

> **The graveyard of QUEUED, LEARNINGS, and DECISIONS items.** When something from `QUEUED.md` ships, it moves here as **SHIPPED**. When something is consciously rejected, it moves here as **REJECTED** with the reason + revisit conditions. When a `LEARNINGS.md` or `DECISIONS.md` entry is invalidated by new evidence, the pre-correction version moves here as **SUPERSEDED**.
>
> **Never silently delete.** History is the point — a future Claude (or human) reading "did we ever consider X?" or "why did we change our mind on Y?" gets the answer.
>
> **Append new entries to the top** within each section.

---

## Shipped

### `/work` rebuild — CE `ce-work` execution engine + gstack `ship`/`land-and-deploy` (saga-primary-writer execution loop)  {#work-engine-rebuild-shipped}

**SHIPPED 2026-06-03** (`infiquetra-lifecycle` `0.10.0`, PR #TBD, squash TBD — post-merge follow-up fills them). Was QUEUED P1 `#rebuild-work-engine-merge`.

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

**Consumers.** `/plan` (0.7.0, ARCHIVE [#plan-engine-rebuild-shipped](#plan-engine-rebuild-shipped)), `/code-review` (0.8.0, ARCHIVE [#code-review-engine-rebuild-shipped](#code-review-engine-rebuild-shipped)), and `/work` (0.10.0 primary writer, ARCHIVE [#work-engine-rebuild-shipped](#work-engine-rebuild-shipped)) now implement against this spec; `/resume` + `/loop` remain queued — see QUEUED [#resume-engine-merge-saga](QUEUED.md#resume-engine-merge-saga), [#loop-engine-merge-saga-workflow-offload](QUEUED.md#loop-engine-merge-saga-workflow-offload).

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
