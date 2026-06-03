# Changelog

## 0.9.0 - 2026-06-03

- Rebuild `/founder-review` (alias `/ceo-review`) from a 20-line stub into a real scope/ambition/direction
  review engine — the fourth command rebuild of the engine-merge campaign (after `/office-hours`, `/plan`,
  and `/code-review`). A **port, not a merge**: gstack `plan-ceo-review` is the sole engine source (4
  user-selected scope modes + 18 internalized CEO cognitive patterns + 9 Prime Directives + an adapted
  pre-review system audit), with only CE `product-pulse`'s sharpened no-false-precision posture stolen.
  Fires upstream of execution on a `/plan` artifact, a `STRATEGY.md`, a `/brainstorm` output, or an ad-hoc
  scope question — the third member of the review trio (`/doc-review` = plan-readiness, `/code-review` =
  code quality, **`/founder-review` = is this the right, ambitious-enough thing to build at all?**).
- **Four scope modes, committed for the whole review (no silent drift)** — SCOPE EXPANSION (cathedral) /
  SELECTIVE EXPANSION (hold + cherry-pick) / HOLD SCOPE (bulletproof) / SCOPE REDUCTION (surgeon), selected
  via `AskUserQuestion` with context-defaults (greenfield→Expansion, enhancement→Selective, bugfix/refactor
  →Hold, >15 files→suggest Reduction). Each is distinct; all relevant pre-traction.
- **Review-only boundary** — `/founder-review` challenges scope/ambition/direction + captures a scope
  decision; it never makes code changes, never commits/pushes/opens PRs, never files SDLC issues, and never
  *records* the direction (`/strategy` records; founder-review challenges). On a `STRATEGY.md`, founder-review
  is the *ambition lens* and `/doc-review` the *readiness lens* — complementary, not a collision.
- **CLOSED-LOOP routing (not a hand-wave)** — accepted scope routes to `/plan` to re-plan; the (re-)expanded
  plan artifact is written/updated and handed **back** to `/doc-review` (readiness) + `/code-review` (code)
  **with the concrete path**, so expanding scope re-rigors that scope rather than dropping it. Phase 3
  applies the directives + patterns as scope-level lenses producing **named scope findings**, not vibes.
- **Target-conditional Step-0 ceremonies** — gstack's 0C-bis (implementation alternatives) + 0E (temporal
  interrogation) are plan-specific, so they run on a plan target and are skipped/recast on a
  strategy/brainstorm/scope-question target (0A/0B/0C/0F always run). An **office-hours escape** in 0A
  offers `/office-hours` when the session is vague/unframed, resuming after.
- **NO saga write** — founder-review runs upstream/pre-saga and its output is a scope decision, not a
  readiness/code-review artifact; `saga.py`'s `review_paths` is the wrong home and the guard would skip
  ~always. Cross-session persistence = the `docs/founder-reviews/` scope-decision artifact + the journal ADR.
- Durable artifacts land in their own `docs/founder-reviews/` scope-decision dir (intentionally NOT a
  `/handoff` source and NOT `docs/reviews/`), carrying the Mode + Vision + a Scope-Decisions table
  (ACCEPTED/DEFERRED/SKIPPED) + the founder verdict (ship / sharpen / scrap-and-rethink) + the next-command
  handback. **Operator-choice** offer — all three backends (`inline` | `team-execution` |
  `cc-workflows-ultracode`) cited by path (`references/operator-choice.md`) on a scope-expansion/scrap verdict.
- Two new references: `skills/founder-review/references/{ceo-cognition,review-modes}.md` (the 18 patterns + 9
  directives + sharpened posture; the 4 modes + ceremonies + adapted audit + target-conditional gating).
  Thin `commands/founder-review.md` + `commands/ceo-review.md` (alias) launchers (review-only, no saga
  mention). Self-contained: ports the gstack engine, no gstack vendoring, no runtime dep on CE.

## 0.8.0 - 2026-06-03

- Rebuild `/code-review` from a 20-line stub into a real pre-PR code-quality review engine — the third
  command rebuild of the engine-merge campaign (after `/office-hours` and `/plan`). Merges CE's
  `ce-code-review` findings/validator/judgment-lens spine (the Jeff-preferred backbone) with gstack
  `/review`'s scope-drift detection + plan-completion audit + high-signal checklist categories into a
  self-contained infiquetra engine. Fires at the work→PR boundary (after `/work` produces code, before
  PR/merge) — it is a within-work gate, NOT the saga `review` lifecycle slot (`/doc-review` owns that).
  Six numbered phases: enter + scope → intent + built-vs-planned audit → select lenses (judgment) →
  review fan-out → merge + validate → report + route + saga.
- **Gate-only boundary** — `/code-review` reports + classifies + routes; it never mutates code, commits,
  pushes, opens PRs, or files SDLC issues (`/work` / `infiquetra-deploy` / `sdlc-manager` own those).
  Adopts CE's full findings schema (`autofix_class` / `owner` / anchored `confidence` / `suggested_fix` /
  `pre_existing` / `evidence`) as agent-consumable routing metadata; fixer dispatch is offered, never
  auto-run. The programmatic mode (for `/work`'s future call) is zero-write to reviewed code.
- **Judgment-based lenses** — read the diff, spawn only lenses with real work, announce the team with a
  one-line justification each. Four always-on lenses (correctness, security, testing,
  maintainability/conventions) plus conditional-by-judgment lenses including a distinct
  deploy/migration-verification lens (DynamoDB/IaC/Ansible checklist) and a reliability lens. gstack's
  Rails/Swift/Stimulus specialists dropped; its high-signal checklist categories (enum-completeness,
  LLM-output-trust-boundary, SQL/shell-injection, race conditions) fold into the lens checklists.
- **Built-vs-planned audit** — scope-drift detection (informational: CLEAN / DRIFT / REQUIREMENTS-MISSING)
  plus the 5-state plan-completion audit (DONE / PARTIAL / NOT-DONE / CHANGED / UNVERIFIABLE) with the
  three verification modes (DIFF / CROSS-REPO / EXTERNAL-STATE) and the honesty rule, reading the
  `docs/plans/` artifact + the journal. The audit always emits findings; the normal P0/P1 findings gate
  is what blocks the PR.
- **Independent validator pass, right-sized by MODE** — programmatic/headless runs a fresh per-finding
  validator over all Stage-A survivors (capped 15, ordered P0→P3, validator-reject/failure → drop);
  interactive mode lets the operator be the per-finding validator. The cost control is the upstream
  suppress-<75 confidence gate + the 15-cap, not a severity carve-out.
- `/code-review` becomes **saga's first review-track consumer** — append-only to an EXISTING work-thread
  saga (found via `saga.py scan`): appends the artifact path to `review_paths` + records the backend in
  `orchestration_mode`, preserving `lifecycle_phase` (it does NOT advance the phase). If no saga exists it
  skips the saga write — never mints, never invents `--kind/--id`. Never `git add` the tick.
- Durable artifacts land in their own `docs/code-reviews/` dir (NOT `docs/reviews/` — avoids the
  handoff/sdlc-manager plan-ready classifier collision), carrying the reviewed SHA + a review-result
  contract. **Operator-choice** offer — all three execution backends (`inline` | `team-execution` |
  `cc-workflows-ultracode`) cited by path (`references/operator-choice.md`) for the fan-out + validator
  pass.
- Four new references: `skills/code-review/references/{lens-catalog,findings-schema,validator,built-vs-planned}.md`.
  Thin `commands/code-review.md` launcher reflecting the engine (gate-only + saga append + the hard
  boundary). Self-contained: ports both source engines, no gstack vendoring, no runtime dep on CE.

## 0.7.0 - 2026-06-02

- Rebuild `/plan` from a 27-line stub into a real implementation-plan engine — the second command
  rebuild of the engine-merge campaign. Merges CE's `ce-plan` structured-artifact engine (the
  Jeff-preferred spine) with gstack `spec`'s code-grounded HOW-interrogation front end into a
  self-contained infiquetra engine. Six numbered phases: enter + warranted-gate → ground (HOW) →
  interrogate (HOW) → synthesize the plan artifact → condensed deepening pass → saga + route +
  operator-choice.
- Artifact contract (CE wholesale): stable **R-IDs** (requirements), **KTDs** (Key Technical
  Decisions), independently-landable **U-IDs** with per-unit enumerated **test scenarios** + explicit
  test-file paths; requirements traceability; "decisions not code"; three-audience design (human +
  agent + `/work` consumer). The plan doc carries `origin:` + `Implementation Units` +
  `Key Technical Decisions` + `U1` markers so `/doc-review` recognizes it.
- **Warranted-gate** + scope classes up front — a `/plan` invocation that doesn't warrant a durable
  plan is named and routed, not force-fit into the artifact.
- **HOW-only interrogation** — `/plan` assumes the WHAT (requirements/scope) settled upstream
  (`/ideate` → `/brainstorm` → `/office-hours`); open WHAT-ambiguity bounces back with a recommendation
  to run `/brainstorm` first (it does NOT claim `/brainstorm` "accepts" a handoff). The interrogation
  register grounds in code (cite `path:line`) before asking.
- **Condensed deepening pass** — a conditional confidence self-review (not CE's full 248-line
  deepening), kept proportional. The full review gauntlet is NOT dropped — it's the `review` phase
  (`/doc-review` + `/code-review` + `/founder-review`); `/plan` keeps the condensed self-review and
  routes to `/doc-review` (the recommended next step) before `/work`.
- One **plan saga** via the saga CLI (`scripts/saga.py save`, `--lifecycle-phase plan`) — runnable,
  with an explicit "never `git add` the tick" boundary; epic/multi-unit splits hand to `sdlc-manager`.
- **Operator-choice** offer: all three execution backends (`inline` | `team-execution` |
  `cc-workflows-ultracode`) cited by path (`references/operator-choice.md`), offered not defaulted.
- Hard boundary: `/plan` does NOT implement, does NOT file SDLC issues (`sdlc-manager` owns that), and
  does NOT run the full review gauntlet (`/doc-review` owns that). Position: `/plan` answers
  "How should it be built?".

## 0.6.0 - 2026-06-02

- Rebuild `/office-hours` from a 23-line facilitative stub into a real two-mode thought-partner
  diagnostic ported from gstack and adapted to infiquetra — the Think-phase frame-finding front
  door that `/ideate` routes unframed asks to and `/brainstorm` bounces open thought-partner work
  back to. Keeps that handshake.
- Two modes: **Startup mode** — gstack's six market/customer forcing questions, made
  **stage-aware** (a pre-traction / pre-revenue greenfield operator gets a hypothesis-forming
  register, not an evidence-audit of customers that don't exist yet); **Builder mode** —
  discovery/shaping for infra, workflow, and internal-tooling asks, infiquetra's high-frequency
  mode, carrying real depth (not a one-liner). Modes can switch mid-session.
- Anti-sycophancy + pushback re-targeted: hard on vagueness and ungrounded assumptions, not on
  the operator's judgment; push-twice with escape hatches. **HARD GATE** (absolute): never
  implement, plan, or file an SDLC issue — frame-finding only. Stops the moment it can name the
  problem and a route, with plural clean exits (`/brainstorm`, `/plan`, `/strategy`).
- Route always (close by naming a next command); an optional **frame note** lands in its own
  `docs/office-hours/<date>-<topic>-frame.md` (frontmatter `kind: frame-note`) — kept out of
  `docs/ideation/` to avoid colliding with the `/ideate` resume scan.
- Self-contained: ports the gstack engine, sheds its runtime boilerplate (brain-context preflight,
  gbrain sync, learnings-search, telemetry, `~/.gstack` path conventions). No gstack vendoring, no
  runtime dependency on compound-engineering.

## 0.5.0 - 2026-06-02

- Add the operator-choice framework: a new contract document, `references/operator-choice.md`, that
  codifies the 3-way execution-backend choice — `inline` / `team-execution` / `cc-workflows-ultracode`
  (the canonical `ORCHESTRATION_MODES` enum strings). Lifecycle owns the *choice* of backend; it does
  not own execution.
- Add short prose offer hooks to `/loop` and `/work` that surface the operator-choice when work
  warrants a non-inline backend, pointing at the decision contract.
- Fix the `saga-spec.md` `orchestration_mode` cross-ref: it pointed at §7 (the save/restore/scan
  operation contract) instead of the decision contract; it now references
  `references/operator-choice.md`.
- Doc-only foundation. No code or helper is added in this release — the CLI-backed
  orchestration-choice helper is deferred to the `/work` rebuild.

## 0.4.0 - 2026-06-02

- Add a unified saga engine (`scripts/saga.py`): one source of truth for durable, resumable
  work-state with a stable derived identity (`issue-<N>` / `task-<slug>`, sticky for the life of
  the work), save/restore/scan, and gh-context aggregation. Sagas are written as an append-only,
  timestamped envelope log under `.claude/infiquetra-lifecycle/sagas/<saga_id>/<YYYYMMDD-HHMMSS>.md`
  (gstack-style YAML frontmatter + `Summary`/`Decisions`/`Remaining`/`Notes` body), plus a derived,
  rebuildable `state.json` index. Envelopes are immutable; each save appends a new tick.
- The three legacy scripts — `scaffold_checkpoint.py`, `find_inflight_work.py`, and
  `load_saga_context.py` — are now thin wrappers that delegate to `saga.py`. Every CLI flag and JSON
  output key is preserved, so existing callers keep working.
- Behavior changes from this unification:
  - Storage moved from per-phase `checkpoints/` files to per-saga `sagas/<saga_id>/` envelope
    directories.
  - Ordering is now by envelope filename (the timestamped name **is** the canonical order), never by
    filesystem `mtime`. This makes ordering deterministic and robust under rsync/backup/snapshot
    restore.
  - Saves are append-only (a new immutable tick per save) instead of overwriting a single checkpoint.
  - Three stored state axes — `lifecycle_phase` (CE flow position), `phase_status` (phase
    completion, drives the next phase), and `status` (thread disposition) — replace the prior
    ad-hoc fields; `maturity` is derived at `/handoff` time, not stored. Frontmatter lists use
    full-snapshot replace semantics (a tick's lists replace; absent carries forward; empty clears).
- Add a plugin-level contract document, `references/saga-spec.md`, that the lifecycle consumers
  (`/plan`, `/work`, `/resume`, `/loop`) implement against.
- **Upgrade warning:** complete any in-flight `/loop` work before upgrading. Legacy
  `.claude/infiquetra-lifecycle/checkpoints/` state is read as a low-priority `scan` fallback for one
  version only and then dropped — finish or re-save active loops so they migrate into the new
  `sagas/` layout.

## 0.3.0 - 2026-06-01

- Rebuild `/ideate` from a thin facilitative stub into a full divergent→convergent engine ported from
  compound-engineering and adapted to the infiquetra world: parallel frame agents generate many
  grounded candidates, the orchestrator critiques all and presents only the survivors, and cut ideas
  stay first-class and revivable. Adds a two-way thought-partnership — the operator's seed ideas feed
  *into* the frame agents (build on / challenge / combine) and face the identical critique — and a
  revival state machine that re-enters the filter with new evidence, preserving explicit rejection as
  the quality mechanism.
- Add infiquetra-specific grounding to `/ideate`: a grounding-fit gate (proceed / decline /
  recommend `/office-hours` / ask) weighing idea breadth against available grounding; a
  context-library reader (`*-context-library` repos via `gh`, local-clone preferred); a named-repo
  reader for multi-repo asks; read-only `gh` issue-theme clustering on backlog intent; and smart-auto
  web research for the cross-domain-analogy frame. Adaptive frame count (1–6) scales to scope.
- Rebuild `/brainstorm` into a thinking-partner engine that deep-dives one chosen idea (a `/ideate`
  survivor or a named topic) into a right-sized requirements document: scope assessment, a product
  pressure-test, one-question-at-a-time dialogue, 2–3 approaches with a non-obvious angle, and a
  `requirements-ready` artifact under `docs/brainstorms/` for `/plan`.
- Add reference files: `skills/ideate/references/convergence-and-partnership.md`,
  `skills/ideate/references/ideation-artifact.md`, and
  `skills/brainstorm/references/requirements-sections.md`. Self-contained — no runtime dependency on
  compound-engineering.
- Add `/handoff` to route durable lifecycle artifacts to `sdlc-manager` prepared issue drafts, with a
  thin handoff-envelope helper that records source, maturity, target hints, blockers, open questions,
  and the `/create-issue --prepare` routing command without owning SDLC issue bodies. Teach
  `/plan <issue>` and `/work <issue>` to consume handoff maturity and source context from prepared
  SDLC issues.

## 0.2.0 - 2026-05-31

- Rename the plugin from `infiquetra-loop` to `infiquetra-lifecycle`; "loop" named only the `/loop`
  router command, not the whole idea-to-ship lifecycle the plugin covers. The `/loop` command name
  is unchanged.
- Rename the ignored runtime-state directory from `.claude/infiquetra-loop/` to
  `.claude/infiquetra-lifecycle/`; `sdlc-manager` updated in lockstep.
- Rename the handoff-envelope `loop_owner` field to `lifecycle_owner`.
- Document the command set by lifecycle phase: Think, Plan & execute, Hand off, Review, and
  Improve & route.

## 0.1.0 - 2026-05-29

- Add the Infiquetra lifecycle command set from office-hours through resume.
- Add `/doc-review` for plan, requirements, and formal SDLC implementation-readiness review.
- Add durable repository artifact guidance and ignored local runtime-state guidance.
- Add helper scripts for destination selection, issue progress comments, deploy strategy
  detection, team-execution escalation, and engineering-journal triggers.
- Preserve VECU work-loop mechanics source-neutrally: issue parsing, ignored checkpoints,
  inflight resume discovery, saga context loading, sub-issue discovery, and cached deploy
  strategy detection.
