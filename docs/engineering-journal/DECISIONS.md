# Decisions — Infiquetra Claude Plugins

> **ADR-style records of plugin-pattern / convention / tooling choices.** When you commit a chosen path over alternatives — pick A over B, flip a flag, change a threshold, choose a category, adopt a tool — capture rationale + tradeoff + revisit-when condition + commit hash.
>
> The point is to make **revisit conditions explicit** so a future Claude (or human) reading "why did we pick X?" gets the answer cold, including when it would be right to reconsider.
>
> **Append new entries to the top.** Format:
>
> ```markdown
> ## YYYY-MM-DD
>
> ### Short title (commit hash)  {#slug}
>
> **Decision.** What we picked.
> **Rejected alternatives.** What we considered and didn't pick.
> **Rationale.** Why this won.
> **Revisit when.** Condition that would change the calculus.
> **Refs.** Related LEARNINGS / QUEUED / narratives.
> ```
>
> When new evidence invalidates a decision, **update inline AND move the pre-correction version to `ARCHIVE.md` as SUPERSEDED**.

---

## 2026-06-03

### Rebuild `/loop` as the campaign's one NATIVE router engine — no upstream to port or merge (PR #183, squash 1fca13a)  {#loop-engine-rebuild}

**Decision.** Rebuild `/loop` — the **sixth command rebuild** of the engine-merge campaign (after `/office-hours`, `/plan`, `/code-review`, `/founder-review`, `/work`) — from a router stub into a **self-contained native router engine**. This is the campaign's **ONE native rebuild**: unlike every prior rebuild, there is **no upstream engine to port or merge**. CE ships no router; the gstack "dispatch table SKILL" the QUEUED brief named is **phantom** (verified — gstack's root SKILL is browser-testing, there is no router dir; see LEARNINGS [#brief-source-claim-phantom-artifact](LEARNINGS.md#brief-source-claim-phantom-artifact)); and gstack's context-save/restore is the shipped **saga** plus the queued `/resume`'s engine, **not** `/loop`'s. So `/loop` is authored fresh against the lifecycle's own primitives (saga + operator-choice). Three modes: **Route** (classify intent → hand to the right lifecycle command), **Drive** (inline phase walk with a per-decision operator-choice offer for `/loop`-owned work), **Resume** (scan → restore → route a durable work-thread, with inline cold-reconstruction). The four interview answers settled with Jeff:

- **(Q1) Offload model: inline phase walk + per-decision operator-choice offer; offload pointer scoped to `/loop`-OWNED work only; `/loop` does NOT instruct a routed command's backend.** In Drive mode `/loop` walks the lifecycle phases inline and offers the three execution backends (`inline`/`team-execution`/`cc-workflows-ultracode`) **per decision point** for work it owns. The offload pointer is recorded **only for `/loop`-owned offloads**. When `/loop` *routes* to another command (e.g. `/work`), it does **not** instruct that command's backend — `/work` writes but never reads `orchestration_mode` (verified — SKILL:174,190), so any instruction would have no receiver. Each command owns its own backend decision.
- **(Q2) Routing tick: existing fields + offload pointer only; no schema change.** A routing event ticks the saga carrying the **existing** fields (kind/id/phase/round/status) plus the offload pointer **only for `/loop`-owned offloads**. No new saga schema field — the offload pointer rides existing envelope structure. Avoids foundation churn against the shipped saga spec.
- **(Q3) Durable substrate: volatile `.claude/infiquetra-lifecycle/` + committed artifacts.** `/loop`'s re-entry reads from the volatile session dir `.claude/infiquetra-lifecycle/` for in-flight state plus the committed artifacts (plans, reviews, work-sessions) as the durable substrate. Same split the rest of the lifecycle uses; `/loop` adds no new persistence location.
- **(Q4) Resume split: `/loop` owns lightweight, `/resume` (queued) owns heavy.** `/loop` owns a **lightweight** scan→restore→route plus **inline cold-reconstruction** via `load_saga_context.py` when re-entering without a live session. The **heavy forensic** reconstruction (commit-trailer archaeology, CE forensic reconstruction) belongs to the queued `/resume` rebuild — see QUEUED [#resume-engine-merge-saga](QUEUED.md#resume-engine-merge-saga). The `/resume` route from `/loop` is **opt-in advisory**, not a hard handoff.

**Key design points.**
- **No upstream port/merge — authored native.** This is the load-bearing distinction from every prior rebuild. The QUEUED brief (produced by a budget-exhausted brief workflow — see LEARNINGS [#workflow-structuredoutput-budget](LEARNINGS.md#workflow-structuredoutput-budget)) asserted a "gstack dispatch table SKILL" source that does not exist. Verifying that before building (rather than trusting the brief) is what kept the rebuild from chasing a phantom merge — see LEARNINGS [#brief-source-claim-phantom-artifact](LEARNINGS.md#brief-source-claim-phantom-artifact). `/loop` is built directly on the saga (storage) + operator-choice (decision) contracts.
- **Additive saga picker-field extension — closes Defect 1 of `#code-review-saga-scan-touchups`.** `saga.py` `scan()` / `_saga_summary` gained the `issue_ref` / `plan_path` / `branch` match keys (plus `destination` + the `orchestration_mode`/`orchestration_ref` pair the `/loop` picker needs) so a resuming `/loop` (and a standalone `/code-review`) can match the right thread **without** `restore`-ing every candidate. This is the additive, no-schema-churn fix for **Defect 1** of the cross-skill defect the `/work` rebuild surfaced (scan-dict omitted the match keys) — shipped here with the `/loop` rebuild, asserted by `test_scan_exposes_picker_fields`. **Defect 2 (the `/code-review` Phase-5.4 programmatic-mode append contradiction) is a `/code-review` SKILL change, out of scope for this rebuild — which touched no other skill — and REMAINS queued.**
- **Boundary.** `/loop` classifies + routes + (in Drive) walks phases for work it owns; it does NOT override a routed command's own loop (`/work` keeps owning its execution + PR loop), does NOT do heavy forensic reconstruction (`/resume`), and does NOT instruct a destination command's backend.

**Rejected alternatives.**
- *Full hand-to-Workflow (offload the whole loop to a Claude Code Workflow).* REJECTED — overrides `/work`'s own execution loop; each command owns its backend, `/loop` only offers it per decision for work it owns.
- *Router-only (drop the Drive inline-walk value-add).* REJECTED — Route alone makes `/loop` a thin dispatcher with no value over invoking the command directly; the Drive inline phase walk + per-decision backend offer is the value-add.
- *Fold `/resume` into `/loop`.* REJECTED — scope-creeps the queued `/resume` P1 (heavy forensic reconstruction); `/loop` owns only lightweight scan→restore→route + inline cold-reconstruction.
- *Committed offload pointer (a new committed index file).* REJECTED — duplicates the saga index; the routing tick carries the pointer on existing envelope structure.
- *Extend the saga schema for the offload pointer.* REJECTED — foundation churn against the shipped saga spec for a `/loop`-only field; ride existing fields.
- *Instruct the destination command's backend.* REJECTED — no receiver (`/work` never reads `orchestration_mode`, SKILL:174,190); the instruction would silently no-op.
- *Port a gstack "dispatch table".* REJECTED — it does not exist (phantom brief source; root gstack SKILL is browser-testing, no router dir).
- *Re-port gstack context-save/restore.* REJECTED — that engine is the already-shipped saga + the queued `/resume`'s scope, not `/loop`'s.

**Rationale.** `/loop` is the lifecycle's front door — the command that decides where work goes — and it had only a stub. There was no engine to inherit (CE has no router; the named gstack source is phantom), so it had to be authored native against the lifecycle's own saga + operator-choice contracts. Keeping the Route/Drive/Resume split — and scoping the offload pointer + backend offer to `/loop`-owned work only — keeps `/loop` from overriding the per-command backend ownership the campaign already settled (`/work` reads no `orchestration_mode`). Shipping the additive saga picker-field extension here closes **Defect 1** of the cross-skill scan defect the `/work` rebuild surfaced without a schema change; Defect 2 (a `/code-review` SKILL change) remains queued.

**Revisit when.** The `/resume` rebuild lands the heavy forensic reconstruction (revisit the lightweight/heavy split + the advisory `/resume` route); a routed command starts reading `orchestration_mode` (revisit the "do not instruct destination backend" decision); the offload pointer needs to survive across sessions in a queryable way (revisit the no-new-persistence + ride-existing-fields decision); or a real upstream router engine appears worth porting.

**Refs.** Plugin `0.11.0`. Part of the engine-merge campaign — see [#lifecycle-engine-merge-campaign](#lifecycle-engine-merge-campaign). Built native on the saga foundation — [#saga-schema-foundation](#saga-schema-foundation) — and the operator-choice contract — [#operator-choice-framework](#operator-choice-framework). Backend-ownership partner (writes but never reads `orchestration_mode`) — [#work-engine-rebuild](#work-engine-rebuild). Closes Defect 1 of the scan touch-up — ARCHIVE [#code-review-saga-scan-touchups-shipped](ARCHIVE.md#code-review-saga-scan-touchups-shipped); Defect 2 remains QUEUED [#code-review-saga-scan-touchups](QUEUED.md#code-review-saga-scan-touchups). Heavy-resume partner: QUEUED [#resume-engine-merge-saga](QUEUED.md#resume-engine-merge-saga). Phantom-source learning: LEARNINGS [#brief-source-claim-phantom-artifact](LEARNINGS.md#brief-source-claim-phantom-artifact). Ship record: ARCHIVE [#loop-engine-rebuild-shipped](ARCHIVE.md#loop-engine-rebuild-shipped). Shipped via PR #183 (squash 1fca13a).

### Rebuild `/work` by merging CE `ce-work` execution engine + gstack `ship`/`land-and-deploy` into a saga-primary-writer execution-loop engine (PR #181, squash d398055)  {#work-engine-rebuild}

**Decision.** Rebuild `/work` — the **fifth command rebuild** of the engine-merge campaign (after `/office-hours`, `/plan`, `/code-review`, `/founder-review`) and the **execution-loop track** — from a 39-line facilitator stub into a **self-contained infiquetra execution engine that merges CE's `ce-work` execution engine (Jeff-preferred spine) with gstack `ship`/`land-and-deploy`'s autonomy + readiness/staleness gates**. This is a genuine **two-source merge** (like `/code-review`), not a single-source port (like `/founder-review`). It is the **most architecturally entangled** rebuild of the campaign because it lands two deferred foundations at once: the saga becomes first-class (`/work` is its **primary writer**) and the deferred `recommend_execution_backend()` CLI helper finally gets a real caller. Five numbered phases: enter + scan saga + triage + detect round-N → setup + task-list + backend → execute phase-by-phase → record (saga tick + work-session + issue progress) → code-review gate + PR-ready + continuation routing. The four interview answers settled with Jeff:

- **(Q1) Boundary: PR-ready execution + own the round-N PR continuation loop; merge is a confirmed git op `/work` owns; only deploy is delegated.** `/work` executes the build loop to PR-ready, then **owns the PR→review→merge→qa continuation loop** (Jeff's elaboration: "would want to trigger request for review/approval, pickup and /qa after approval and merge, or handle PR requested changes"). `/work` performs the merge itself when destination ⊇ merge, but **only as an explicitly operator-confirmed `gh pr merge`, never silent** — there is no separate "git/human" skill, merge is a git op `/work` owns under confirmation. Only **deploy mutation** is delegated to `infiquetra-deploy`. gstack's canary-verify + offer-revert are **relocated** to `infiquetra-deploy` (a deliberate brief deviation — read to relocate knowingly, not dropped silently; the capability is queued there). Honors saga-spec §1.1/§10 (deploy is deploy's hard boundary).
- **(Q2) Backend offer: recommend + confirm (land `recommend_execution_backend()`).** The deferred CLI helper gets its first real caller: auto-compute the recommendation from size/risk (reusing `should_offer_team_execution`'s six signals), pre-select it, always surface alternatives so escalation is one keystroke, operator confirms. Exactly operator-choice §2. A library-only helper would be uncallable from markdown — the CLI subcommand resolves the deferral.
- **(Q3) Saga role: first-class round-N state spine (primary writer).** `/work` is saga's **primary writer** (saga-spec §11): `restore`-on-resume (rehydrate round/phase/checks_run/next_step), mint/advance `lifecycle_phase` plan→work, a tick per phase boundary, `issue_ref` adoption, `status=done` at completion. It **mints the *findable* saga a standalone `/code-review` appends to** — it sets `issue_ref`/`plan_path`/branch (the match keys), and for its own pre-PR gate calls `/code-review` programmatically and reads the returned envelope **directly** (programmatic mode hands persistence to the caller). The old `load_saga_context.py`/`find_inflight_work.py` become thin read helpers/fallbacks. Resume is deterministic.
- **(Q4) Review gate: hard + override-with-rationale + computed staleness.** Block PR-ready on unresolved P0/P1 (read `/code-review`'s programmatic envelope **directly**) **OR** a stale review (commits since a `/work`-captured reviewed SHA — `git rev-parse HEAD` at review time, `git rev-list <sha>..HEAD --count`). Allow explicit operator override with a **recorded** rationale (never silent). Matches the current stub + `/loop` intent.

**Key design points.**
- **Saga primary-writer; forward-coupling via findable identity, gate via direct envelope.** `/code-review` (shipped 0.8.0) is append-only/never-mint and, when run **standalone**, matches the work-thread saga on `issue_ref`/`plan_path`/`branch`. `/work`'s job is to mint a **findable** saga: it sets `--issue-ref` (the saga-spec §11 issue_ref-adoption write), `--plan-path` when a plan exists, and saves **on the work branch** — the three match keys. For its **own** in-loop pre-PR gate `/work` does **not** depend on code-review finding or writing the saga: it calls `/code-review` programmatically and reads the **returned envelope directly** (programmatic mode = caller owns persistence — code-review writes nothing in that mode). This was a correction folded after the build's adversarial review caught the original "name the identity into the programmatic call so code-review appends" design as **one-sided**: shipped `/code-review` has no arg to receive a caller-named identity and writes no artifact in programmatic mode, so the gate could not read a saga `review_paths` that was never written. Reading the envelope directly + a self-captured reviewed SHA removes that dependency entirely; the standalone-code-review coupling is preserved by the match keys.
- **Round-N saga ownership.** `/work` owns mint + phase tick + round bump (`--rounds-seen`, never `next_round` — it is derived, saga-spec §6.1) + `issue_ref` adoption; a **standalone** `/code-review` appends `review_paths` + preserves `lifecycle_phase`. The two halves of the round-N saga ownership the journal said to settle, now settled. (Residual: `saga.py scan()` does not surface `issue_ref`/`plan_path`/`branch`, so even standalone code-review must `restore` each candidate to match — a cross-skill defect queued for the `/code-review` touch-up, QUEUED [#code-review-saga-scan-touchups](QUEUED.md#code-review-saga-scan-touchups).)
- **`recommend_execution_backend()` lands in `lifecycle_state.py` + a CLI subcommand.** A pure function next to `should_offer_team_execution` (reused, all 6 kwargs passed, plus a `needs_consensus` branch) with an `ultracode` branch and `inline` default. **`alternatives` is computed independently of the precedence winner** so operator-choice §3.3 "offer BOTH on overlap" survives as a one-keystroke escalation. `main()` refactored from the bare positional into `normalize` + `recommend-backend` subcommands (verified no script/test/CI/hook invoked the positional CLI, so the refactor breaks nothing). A deliberate `or needs_consensus` divergence from §3.1's "PLUS" is documented in the docstring.
- **`issue_progress.py` CLI extension.** The *function* `render_issue_comment()` already accepted `work_session_path`/`commit_sha`/`checks_run`/`blockers`/`pr_url`/`review_status`/`doc_review_*`/`deploy_status`/`workflow_url`/`evidence_link`, but the CLI exposed only 8 of those fields — so `/work`'s Phase-4 comment was uninvokable from markdown (dead wiring). This rebuild extends `parse_args`/`main` to forward the full field set (pipe-separated for the list fields). Same "consumer rebuild extends the CLI" pattern as the helper.
- **Computed staleness from a self-captured SHA (the saga has no `reviewed_sha` field).** `/work` captures `REVIEWED_SHA=$(git rev-parse HEAD)` at the moment it runs `/code-review`, then `git rev-list <REVIEWED_SHA>..HEAD --count > 0` ⇒ stale. No parse of a code-review artifact (programmatic mode writes none) and no stored field. Pinned in `test-and-gates.md`. (Corrected from the original artifact-parse design after the adversarial review flagged that programmatic mode writes no artifact to parse.)
- **qa/resume routing is advisory; the qa-phase-advance is honestly deferred.** `/qa` is still a 19-line stub with zero saga awareness (verified). So on merge `/work` sets `phase_status=complete` + `next_step="run /qa"` and routes to `/qa` **advisorily**, but **leaves `lifecycle_phase=work`** — it does NOT claim "/qa owns/advances the qa slot" as if wired. The saga legitimately sits at `work` post-merge until the `/qa` rebuild lands the `qa` advance (`/handoff` deriving `resume-ready` for that state is correct). Likewise `/resume` routing is advisory — `/work`'s own Phase-0 re-entry is the load-bearing "come back later" mechanism, independent of the `/resume` stub.
- **Boundary.** `/work` builds, gates, records, coordinates the PR loop (merge only under explicit confirmation); it does NOT silently mutate GitHub, own deploy/canary (`infiquetra-deploy`), file SDLC issues (`sdlc-manager`), or advance `lifecycle_phase` past `work`.
- **Three new references + own `docs/work-sessions/` artifact dir.** `references/{execution-strategy,test-and-gates,pr-continuation-loop}.md` — the PR-loop transition table got its own ref so the new surface doesn't crowd the SKILL. Work-session artifacts → the canonical `docs/work-sessions/` (no new dir; `handoff_envelope.py` already classifies it).

**Rejected alternatives.**
- *Own canary-verify + offer-revert inside `/work`.* REJECTED — deploy/canary is `infiquetra-deploy`'s hard boundary (saga-spec §1.1/§10); gstack's canary/revert is read-then-relocated to `infiquetra-deploy` (queued there), recorded as a deliberate brief deviation, not dropped silently.
- *Advisory review gate (CE-style, no teeth).* REJECTED — no teeth lets P0/P1 or stale reviews through to PR; the hard gate + honest recorded override matches the stub + `/loop` intent and Jeff's no-lies rule.
- *Load-context-only saga (not a primary writer).* REJECTED — the round-N spine + the standalone-code-review coupling demand `/work` be the first-class minter/writer (setting the findable `issue_ref`/`plan_path`/branch identity), not a read helper.
- *Library-only `recommend_execution_backend()` helper.* REJECTED — uncallable from markdown skills + would drift against the operator-choice doc (the exact reason the 0.5.0 foundation deferred it); ship it with a runnable CLI subcommand, resolved here.
- *Port all of gstack `ship`/`land-and-deploy`.* REJECTED — drags in gbrain, telemetry, VERSION/CHANGELOG/TODOS/Greptile steps, the section-file split, `~/.gstack` persistence, and template machinery irrelevant to infiquetra; extract the autonomy/readiness/staleness/merge-base mechanics, shed the rest.

**Rationale.** `/work` is the loop's execution hub — every real build runs through it — and it had no engine. CE `ce-work` is the proven execution engine (complexity triage, U-ID task-lists, parallel safety, test discipline); gstack `ship` carries the autonomy + readiness/staleness gates CE lacks. Merging both into an infiquetra-owned engine — rather than depending on either — keeps the plugin self-contained and adapted to a 1-human + agents shop. Making `/work` the saga primary-writer is what turns the saga from an unconsumed primitive (and `/code-review`'s append-only write from a no-op) into a real deterministic round-N spine, and landing `recommend_execution_backend()` here gives the deferred operator-choice helper its first real caller. The PR-ready boundary + round-N continuation loop is what makes "PR-ready" not a dead-end while keeping deploy/canary on the right side of the boundary.

**Revisit when.** The `/qa` rebuild lands the `qa` `lifecycle_phase` advance (revisit the post-merge "sits at work" deferral + the advisory routing); the `/resume` rebuild changes who owns cross-session re-entry; `infiquetra-deploy` ships the relocated canary-verify/offer-revert capability (revisit the deploy handoff shape); code-review emits a greppable `reviewed-sha:` token (revisit the staleness parse regex); or the merge-under-confirmation flow proves awkward on real PRs.

**Refs.** Plugin `0.10.0`. Part of the engine-merge campaign — see [#lifecycle-engine-merge-campaign](#lifecycle-engine-merge-campaign). Lands the deferred operator-choice helper — [#operator-choice-framework](#operator-choice-framework). Saga primary-writer against the spec — [#saga-schema-foundation](#saga-schema-foundation). Forward-coupling partner (append-only/never-mint) — [#code-review-engine-rebuild](#code-review-engine-rebuild). Ship record: ARCHIVE [#work-engine-rebuild-shipped](ARCHIVE.md#work-engine-rebuild-shipped). Relocated canary capability: QUEUED [#infiquetra-deploy-canary-verify-revert](QUEUED.md#infiquetra-deploy-canary-verify-revert). Plan `.claude/plans/ok-we-yestereday-we-scalable-fox.md`. Shipped via PR #181 (squash d398055).

### Port `/founder-review` (alias `/ceo-review`) from gstack `plan-ceo-review` as the scope/ambition review lens (PR #179, squash e4eedf2)  {#founder-review-engine-rebuild}

**Decision.** Rebuild `/founder-review` (alias `/ceo-review`) — the **fourth command rebuild** of the engine-merge campaign (after `/office-hours`, `/plan`, `/code-review`) — from a 20-line stub into a **self-contained infiquetra scope/ambition/direction review engine ported from gstack `plan-ceo-review`** (the 4 scope modes + 18 internalized CEO cognitive patterns + 9 Prime Directives + an adapted pre-review system audit). Unlike `/code-review`'s genuine two-source merge, this is a **PORT, not a merge**: the brief scopes THIS command as **gstack-sole-engine + a single CE posture steal** (the sharpened no-false-precision fragment of `ce-product-pulse`), not a reduced merge. (The brief's "ceo-review" label is loose — the real gstack path is `plan-ceo-review`, verified.) Position in the lifecycle: `/founder-review` is the third member of the review trio — `/doc-review` = plan-readiness, `/code-review` = code quality, **`/founder-review` = is this the right, ambitious-enough thing to build at all?** — firing **upstream of execution** on a `/plan` artifact, a `STRATEGY.md`, a `/brainstorm` output, or an ad-hoc scope question. Its output is a **scope decision** (challenge direction; `/strategy` records it). The four interview answers settled with Jeff:

- **(Q1) product-pulse: steal the posture only (sharpened); QUEUE a standalone `/pulse`.** Lift only the *transplantable* fragment of CE `ce-product-pulse`'s posture — **no false precision** (when founder-review cites a number — effort, file count, scope size — present it and let the operator judge) + **no hardcoded "too big/too small" thresholds**. Do NOT lift the full telemetry "present the numbers, reader judges" posture wholesale — founder-review is qualitative, not a numbers report. A standalone `/pulse` live-telemetry component is QUEUED (worth-it-when a live product has real telemetry; Infiquetra is pre-revenue greenfield with no data yet).
- **(Q2) Scope modes: keep all 4 (the engine's spine).** SCOPE EXPANSION (cathedral) / SELECTIVE EXPANSION (hold + cherry-pick) / HOLD SCOPE (bulletproof) / SCOPE REDUCTION (surgeon) — each distinct, all relevant pre-traction. The operator selects one via `AskUserQuestion` and it is **committed for the whole review — no silent drift**. Context-defaults retained (greenfield→Expansion, enhancement→Selective, bugfix/refactor→Hold, >15 files→suggest Reduction). Trimming re-opens the thin-reskin gap.
- **(Q3) System audit: keep, adapted to infiquetra.** Re-source the pre-review audit to infiquetra inputs — plan artifact + journal + `docs/office-hours/` design notes + `STRATEGY.md` + git context + retrospective + landscape WebSearch (skip gracefully if unavailable); DROP the `~/.gstack`/gbrain/remote-slug/`ceo-plans` machinery. The audit makes the critique grounded (founder-review's analog of code-review's built-vs-planned audit).
- **(Q4) Opt-in flow: per-expansion, capped (+ channel digest).** Keep individual `AskUserQuestion` opt-in per expansion (the "100% in control" guarantee), options A) add / B) defer-to-journal / C) skip, **capped** (gstack's "top 5-6 if >8"). In a redis-channel session `AskUserQuestion` is unavailable → inline + trim aggressively (collapse 0C-bis to a single confirm; present expansions as a digest) so the channel UX stays usable. References `skills/brainstorm/SKILL.md`'s channel-inline convention.

**Key design points.**
- **Scope-layer engine + deep rigor routed in a REAL closed loop.** The engine owns the scope/ambition layer and applies the 9 Prime Directives + 18 CEO patterns as internalized scope-level lenses producing **named scope findings** — it does NOT reproduce gstack's 11 deep-rigor review sections (Architecture, Error-&-Rescue-Map, Security, Data-flow, Code-quality, Test, Performance, Observability, Deployment, Long-Term-Trajectory, Design-&-UX) because infiquetra splits the review lenses (doc/code/founder). Deep rigor is **routed** in a real closed loop: `/doc-review:86` routes *inbound* (suggest founder-review when scope/ambition is prominent); founder-review closes it *outbound* by **writing/updating the (re-)expanded plan artifact and handing it back with the concrete path** (`/doc-review docs/plans/<file>` for readiness; `/code-review` once built). Without the concrete handback, expanding scope then "recommending /doc-review" drops the rigor.
- **founder-review ↔ doc-review boundary stated in the SKILL.** Both can target a `STRATEGY.md`/scope doc; they are complementary lenses — founder-review = *challenge the direction* (ambitious? coherent? worth doing?), doc-review = *check readiness* (can this drive implementation?). The SKILL states this; doc-review already cross-suggests founder-review (`:86`). No doc-review edit (verify-only).
- **Target-conditional Step-0 ceremonies.** gstack's 0C-bis (implementation alternatives) + 0E (HOUR-by-HOUR temporal interrogation) are plan-specific and incoherent on a strategy/scope-question, so they are **conditional on target type** (plan → run both; strategy/brainstorm/scope-question → skip/recast). 0A/0B/0C/0F generalize and always run.
- **No saga write.** founder-review runs upstream/pre-saga and its output is a scope decision, not a readiness/code-review artifact — `saga.py`'s `review_paths` is the wrong home and the "if saga exists" guard would skip ~always. Cross-session persistence = the `docs/founder-reviews/` artifact + the journal ADR. founder-review is NOT a saga review-track consumer.
- **`docs/founder-reviews/` scope-decision dir.** Its own dir (the office-hours/code-review precedent), but the rationale is a scope decision captured for `/plan`/`/strategy` + a journal ADR — deliberately separate from the readiness-review (`docs/reviews/`) and code-review (`docs/code-reviews/`) tracks, and intentionally NOT a `/handoff` artifact source.
- **Office-hours mid-session escape.** Ported as a prose offer in 0A (vague/unframed session → offer `/office-hours`, re-read `docs/office-hours/` notes on return). The gstack `{{INVOKE_SKILL:office-hours}}` inline hack is shed; the detection+offer behavior is kept.

**Rejected alternatives.**
- *Port all 11 deep-rigor sections.* REJECTED — duplicates `/doc-review` + `/code-review`; infiquetra splits the review lenses, so founder-review owns the scope layer and routes deep rigor (closed loop) rather than reproducing the section machinery.
- *Hand-wave the routing ("recommend /doc-review" with no artifact).* REJECTED — the rigor evaporates; gstack bundled all 11 sections precisely to re-rigor expanded scope in-session, so the routing must be a real artifact handback (expanded-plan path → `/doc-review`).
- *Write a saga (append `review_paths`).* REJECTED — dead wiring (the guard skips ~always upstream of the work thread) + wrong field; founder-review is not a saga review-track consumer.
- *Trim the 4 scope modes to 2-3.* REJECTED — re-opens the thin-reskin gap; the 4 modes are the engine's spine, each distinct and pre-traction-relevant.
- *Build `/pulse` now (or fold the analytics artifact in).* REJECTED — premature; Infiquetra is pre-revenue greenfield with no telemetry. Steal the posture, QUEUE the component.
- *Run 0C-bis/0E unconditionally.* REJECTED — they are plan-specific and break on a strategy/scope target; made target-conditional instead.

**Rationale.** gstack `plan-ceo-review` IS the engine for this lens — the 4 committed scope modes + internalized CEO cognition + grounded pre-review audit are the whole point, and there is no CE counterpart engine (CE `product-pulse` is a different artifact — a live-telemetry report). So this is a faithful port + a single posture steal, not a merge. Splitting the review lenses (doc/code/founder) is what lets founder-review own the scope layer and route deep rigor in a closed loop rather than re-implementing 11 sections that already live in its sibling engines. The no-saga-write, scope-decision-dir, and target-conditional ceremonies keep the engine coherent for its actual upstream-of-execution position.

**Revisit when.** A real mid-work-thread founder-review need emerges (revisit no-saga-write); Infiquetra reaches a live product with real telemetry (build the queued `/pulse` and revisit whether founder-review should consume it); the closed-loop handback to `/doc-review`/`/code-review` proves awkward on real expansions; or `/strategy` and founder-review's boundary blurs in practice.

**Refs.** Plugin `0.9.0`. Part of the engine-merge campaign — see [#lifecycle-engine-merge-campaign](#lifecycle-engine-merge-campaign). Sibling review-lens rebuild: [#code-review-engine-rebuild](#code-review-engine-rebuild). Operator-choice contract: [#operator-choice-framework](#operator-choice-framework). Ship record: ARCHIVE [#founder-review-engine-rebuild-shipped](ARCHIVE.md#founder-review-engine-rebuild-shipped). Queued `/pulse` component: QUEUED [#pulse-live-telemetry-component](QUEUED.md#pulse-live-telemetry-component). Plan `.claude/plans/ok-we-yestereday-we-scalable-fox.md`. Shipped via PR #179 (squash e4eedf2).

### Rebuild `/code-review` by merging CE `ce-code-review` spine + gstack `/review` scope/plan audit (PR #177, squash 0a9d8cd)  {#code-review-engine-rebuild}

**Decision.** Rebuild `/code-review` — the third command rebuild of the engine-merge campaign (after `/office-hours` and `/plan`) — from a 20-line stub into a **self-contained infiquetra pre-PR review engine that merges CE's `ce-code-review` findings/validator/judgment-lens spine (the Jeff-preferred backbone) with gstack `/review`'s scope-drift detection + plan-completion audit + high-signal checklist categories**. Six numbered phases: enter + scope → intent + built-vs-planned audit → select lenses (judgment) → review fan-out → merge + validate → report + route + saga. Position in the lifecycle: `/code-review` is a **within-work gate at the work→PR boundary** (after `/work` produces code, before PR/merge) — it is a code-quality review LENS, a sibling of `/doc-review` and `/founder-review`, but NOT the saga `LIFECYCLE_PHASES` `review` slot (that slot is `/doc-review`'s plan→work gate). The four interview answers settled with Jeff:

- **(Q1) Lens model: CE judgment-based lenses, lean infiquetra set — NOT gstack fixed specialists.** The orchestrator reads the diff and spawns only lenses with real work (CE model, matching `/doc-review`'s triggered-lenses pattern). Always-on (4): correctness, security, testing, maintainability/conventions. Conditional-by-judgment: a **distinct deploy/migration-verification lens** (NOT folded away — its own DynamoDB/IaC/Ansible checklist), plus reliability, performance, api-contract, adversarial/red-team, agent-native, previous-comments. Rails/Swift/Stimulus reviewers dropped. gstack's high-signal checklist categories (enum-completeness-reads-OUTSIDE-the-diff, LLM-output-trust-boundary, SQL/shell-injection, race conditions) fold into the correctness/security lens checklists.
- **(Q2) Fix behavior: gate-only; adopt the full schema as routing metadata.** Adopt CE's full findings schema NOW (`autofix_class` / `owner` / anchored `confidence` / `suggested_fix` / `pre_existing` / `evidence`) so findings are agent-consumable — but `/code-review` itself reports + classifies + routes; it never mutates code, commits, pushes, opens PRs, or files SDLC issues. Fixer dispatch (review-fixer agent / `/work` / team-execution) is OFFERED via operator-choice; the safe-autofix *apply* mode is a later add. The programmatic mode (for `/work`'s future call) is **zero-write to reviewed code** — built from CE's `report-only` BEHAVIOR + `headless` ENVELOPE, deliberately NOT CE's mutating `headless` behavior.
- **(Q3) Validator pass: keep, right-sized by MODE (not severity).** Run CE's independent per-finding validator (a fresh agent re-checks each survivor: real in code? introduced by THIS diff? handled elsewhere? → `{validated, reason}`). Right-sizing is **mode-based** (CE's actual mechanism): programmatic/headless → validate all Stage-A survivors (capped 15, ordered P0→P3, failure → drop); interactive → the operator is the per-finding validator (skip the pre-dispatch pass). The cost control is the upstream suppress-<75 confidence gate + the 15-cap, NOT a severity carve-out.
- **(Q4) Fan-out + saga: all three backends + journal audit + saga review-track (append-only, never mint).** Offer `inline` / `team-execution` / `cc-workflows-ultracode` for the lens fan-out + validator pass, cited at the plugin-root path (`../../references/operator-choice.md`). The plan-completion audit reads the `docs/plans/` artifact + the journal (built-vs-planned, faithful to both engines). `/code-review` becomes **saga's first review-track consumer** — append-only to an EXISTING work-thread saga (found via `saga.py scan`): append the artifact path to `review_paths` + record the backend in `orchestration_mode`, preserving `lifecycle_phase` (code-review does NOT advance the phase). If no saga exists → skip the saga write, never mint, never invent `--kind/--id`.

**Key design points.**
- **Gate-only boundary.** code-review reviews + classifies + routes; it does NOT implement fixes, commit/push/PR, or file SDLC issues — the same lifecycle boundary `/plan` enforces. The programmatic mode carries an explicit "ZERO file writes to reviewed code" rule.
- **Saga append-only, never mint.** `saga.py save` mints unconditionally, so the never-mint guard lives in SKILL prose (scan-first; append to the found saga's exact `--kind` + `--id`; preserve `lifecycle_phase`; skip if absent) + a negative smoke test. No `saga.py` changes (fields/flags already exist).
- **Own-dir `docs/code-reviews/`.** Durable artifacts get their own dir (NOT `docs/reviews/`) to avoid the `handoff_envelope.py` / `sdlc_manager.py` "any file in `docs/reviews/` → plan-ready" classifier misclassification — the office-hours-dir precedent.
- **Scope-drift is informational.** gstack scope-drift produces findings but does not itself block; infiquetra keeps it informational — the normal P0/P1 findings gate is what blocks the PR.
- **Lens-as-judgment lean set with a distinct deploy/migration lens.** The lens set is judgment-selected and lean, but the deploy/migration-verification lens and the reliability lens are kept distinct (sub-domains enumerated in `lens-catalog.md`) so no lens ships as a one-liner.

**Rejected alternatives.**
- *gstack fixed-specialist list with scope gates.* REJECTED — re-opens "spawn reviewers that find nothing on this diff"; CE's judgment-based selection matches `/doc-review` and the agent-team philosophy.
- *Safe-autofix-now (apply fixes in this rebuild).* REJECTED — blurs the gate/work boundary; the apply mode is a future add, fixer dispatch is offered not auto-run.
- *Drop the validator (trust first-pass confidence).* REJECTED — re-opens false positives; a review that cries wolf is worse than none (Jeff's no-lies rule).
- *Severity-carved validator (trust anchor for P2/P3).* REJECTED — a no-op after the suppress-<75 gate already removed low-confidence findings, AND falsely attributed to CE (which has no severity-based validator exemption); mode-based right-sizing is CE's actual mechanism.
- *Saga mint-on-absent.* REJECTED — would create phantom sagas with invented `--kind/--id`; append-only never-mint with a negative smoke test instead.
- *`docs/reviews/`-shared artifact dir.* REJECTED — collides with the `handoff_envelope.py` / `sdlc_manager.py` plan-ready classifier predicate; own `docs/code-reviews/` dir instead.
- *Folded operational lens (deploy-verify folded into a generic lens).* REJECTED — loses deploy-verify specificity; the deploy/migration-verification lens stays distinct.

**Rationale.** CE's `ce-code-review` is the strongest findings/validator engine of either source (rich agent-consumable schema, independent per-finding re-verification, judgment-based lens selection); gstack `/review` contributes the scope-drift + plan-completion audit + high-signal checklist army CE lacks. Merging the two — CE's spine + gstack's audit/checklist — gives an infiquetra-owned review engine that is agent-consumable, grounded in the plan + journal, and honest (verify-don't-guess), without inheriting either source's runtime boilerplate or auto-apply behavior. Gate-only keeps it inside the lifecycle's review-not-execute boundary; the saga append-only wiring makes it the first review-track consumer without re-minting the work thread `/work` owns.

**Revisit when.** A real PR run shows the gate-only stance is too passive and the safe-autofix *apply* mode earns its weight (add the apply mode behind operator-choice); the mode-based validator cap (15) proves too tight or too loose on real diffs; the `/work` rebuild lands and wants code-review to mint/advance the saga rather than append-only (revisit the never-mint guard); or the distinct deploy/migration lens proves redundant with a rebuilt `/qa`.

**Refs.** Plugin `0.8.0`. Part of the engine-merge campaign — see [#lifecycle-engine-merge-campaign](#lifecycle-engine-merge-campaign). Builds on the `/plan` rebuild [#plan-engine-rebuild](#plan-engine-rebuild), the operator-choice contract [#operator-choice-framework](#operator-choice-framework), and the saga foundation [#saga-schema-foundation](#saga-schema-foundation). Ship record: ARCHIVE [#code-review-engine-rebuild-shipped](ARCHIVE.md#code-review-engine-rebuild-shipped). `/work` forward-coupling (now closed — `/work` is saga's primary writer): DECISIONS [#work-engine-rebuild](#work-engine-rebuild), ARCHIVE [#work-engine-rebuild-shipped](ARCHIVE.md#work-engine-rebuild-shipped). Shipped via PR #177 (squash 0a9d8cd).

## 2026-06-02

### Rebuild `/plan` by merging CE `ce-plan` artifact engine + gstack `spec` HOW-interrogation (PR #175, squash a13ba68)  {#plan-engine-rebuild}

**Decision.** Rebuild `/plan` — the second command rebuild of the engine-merge campaign — from a 27-line stub into a **self-contained infiquetra plan engine that merges CE's `ce-plan` structured-artifact engine (Jeff-preferred spine) with gstack `spec`'s code-grounded HOW-interrogation front end**. Six numbered phases: enter + warranted-gate → ground (HOW) → interrogate (HOW) → synthesize the plan artifact → condensed deepening pass → saga + route + operator-choice. Position in the lifecycle: `/plan` answers **"How should it be built?"** (the WHAT is assumed settled upstream). The four interview answers settled:

- **(Q1) Adopt CE's full artifact skeleton + right-size it.** Take CE's R-ID/KTD/U-ID + per-unit test-scenario shape wholesale (the canonical plan shape, three-audience: human + agent + `/work` consumer), but right-size the engine to infiquetra rather than porting CE's heaviest machinery verbatim — concretely, a CONDENSED deepening pass rather than CE's full 248-line deepening.
- **(Q2) HOW-only interrogation; assume the WHAT upstream.** `/plan` interrogates *how to build it*, grounding in code (cite `path:line`) before asking. It does NOT re-litigate requirements/scope — that's `/ideate` → `/brainstorm` → `/office-hours` territory. Open WHAT-ambiguity triggers a **one-way bounce**: recommend the operator run `/brainstorm` first (with an explicit guard: do NOT claim `/brainstorm` "accepts" a handoff).
- **(Q3) One plan saga via the CLI; epic split → sdlc-manager.** `/plan` emits a single durable **plan saga** via `scripts/saga.py save --lifecycle-phase plan` (runnable, with a hard "never `git add` the tick" boundary). It does NOT mint per-U-ID sagas; multi-unit/epic splits hand to `sdlc-manager`.
- **(Q4) All three backends via the operator-choice doc.** Offer `inline` | `team-execution` | `cc-workflows-ultracode`, cited by path (`references/operator-choice.md`), offered not defaulted — implements the shipped operator-choice contract.

**Key design points.**
- **Review-phase rationale (the gauntlet is NOT dropped).** The full review gauntlet — `/doc-review` + `/code-review` + `/founder-review` — IS the `review` phase, a separate lifecycle stage. `/plan` keeps a CONDENSED deepening self-review and **routes to `/doc-review` (the recommended next exit) before `/work`**. Folding the gauntlet into `/plan` would break the phase model.
- **Doc-frontmatter vs saga-tick split.** The durable plan doc carries human-facing frontmatter (`title`/`type`/`status`/`date`/`origin`) plus the artifact markers (`Implementation Units` / `Key Technical Decisions` / `U1`) so `/doc-review` recognizes it; the machine work-state (lifecycle phase, destination, ADR/KTD refs, orchestration mode) lives in the saga tick. Two surfaces, deliberately not conflated.
- **One-way `/plan`→`/brainstorm` route.** The bounce is a recommendation only, in one direction; `/plan` never claims a handoff contract on the brainstorm side.

**Rejected alternatives.**
- *Lighter agent-consumable variant (thin reskin of the stub).* REJECTED — the stub is exactly the thin-reskin disease the campaign exists to cure; the artifact skeleton is what makes a plan traceable + agent-consumable.
- *Full gstack interrogation in `/plan`.* REJECTED — gstack `spec`'s five-Why + scope/MVP/failure-mode lock is WHAT-rigor that duplicates `/brainstorm`; `/plan` takes only the HOW-interrogation + code-grounding front end. (Seam between the two left as a queued decision-point — see QUEUED [#brainstorm-spec-interrogation-seam](QUEUED.md#brainstorm-spec-interrogation-seam).)
- *Per-U-ID sagas.* REJECTED — over-reach; one plan saga is the durable record, the U-IDs are slices inside it, and epic splitting belongs to `sdlc-manager`.
- *Defer the saga (plan writes a doc only).* REJECTED — contradicts the saga foundation's §11 consumer contract; `/plan` is a saga consumer and emits one plan saga.
- *Run the full review gauntlet inside `/plan`.* REJECTED — breaks the phase model; the gauntlet is the `review` phase, `/plan` only does a condensed self-review + routes to `/doc-review`.
- *CE's full 248-line deepening pass.* REJECTED — over-heavy for infiquetra; ship a condensed confidence pass instead.

**Rationale.** CE's `ce-plan` is the strongest artifact engine of either source (stable IDs, traceability, per-unit test scenarios, three-audience, already agent-consumable); gstack `spec` contributes the code-grounded interrogation discipline CE lacks at the front. Merging the two — taking CE's skeleton wholesale and grafting gstack's HOW-interrogation — gives an infiquetra-owned plan engine that is traceable, agent-runnable, and grounded, without inheriting either source's runtime boilerplate or duplicating the WHAT-rigor that lives upstream. Right-sizing (condensed deepening, one saga, HOW-only) keeps it proportional to a 1-human + agents shop.

**Revisit when.** A real multi-PR epic shows the one-plan-saga + sdlc-manager epic-split seam is awkward (revisit per-slice saga emission); the `/brainstorm` ↔ `spec` interrogation seam gets resolved and changes where HOW vs WHAT interrogation lives (see QUEUED [#brainstorm-spec-interrogation-seam](QUEUED.md#brainstorm-spec-interrogation-seam)); or the condensed deepening pass proves too thin and CE's fuller confidence pass earns its weight.

**Refs.** Plugin `0.7.0`. Part of the engine-merge campaign — see [#lifecycle-engine-merge-campaign](#lifecycle-engine-merge-campaign). Ship record: ARCHIVE [#plan-engine-rebuild-shipped](ARCHIVE.md#plan-engine-rebuild-shipped). Operator-choice contract: [#operator-choice-framework](#operator-choice-framework). Saga foundation: [#saga-schema-foundation](#saga-schema-foundation). Interrogation seam: QUEUED [#brainstorm-spec-interrogation-seam](QUEUED.md#brainstorm-spec-interrogation-seam).

### Rebuild `/office-hours` as a faithful two-mode gstack port adapted to infiquetra (PR `#173`, squash `aec888c`)  {#office-hours-engine-rebuild}

**Decision.** Rebuild `/office-hours` — the first command rebuild of the engine-merge campaign — as a **faithful two-mode gstack diagnostic port**, adapted to infiquetra and merged with the CE boundary contract (front-door framing + the `/ideate`↔`/brainstorm` handshake). Self-contained: ports the gstack engine, no gstack vendoring, no runtime dep on CE. It is the Think-phase **frame-finding front door** — `/ideate` routes unframed asks here; `/brainstorm` bounces open thought-partner work back. The four interview answers settled:

- **(Q1) KEEP both modes** — Startup mode + Builder mode, not collapsed to one diagnostic. **Jeff override:** Infiquetra is a real startup heading toward paying customers, currently pre-revenue greenfield, so the startup forcing-questions earn their place.
- **(Q2) Route always / frame-note optional** — every session closes by naming a next command; writing a frame note is optional.
- **(Q3) Re-target pushback** — hard on vagueness and ungrounded assumptions, **not** on the operator's judgment; push-twice with escape hatches.
- **(Q4) Frame-finding only + plural exits** — stop the moment you can name the problem and a route; clean exits to `/brainstorm`, `/plan`, `/strategy`. HARD GATE (absolute): never implement, plan, or file an SDLC issue.

**Key adaptations.**
- **Stage-aware startup mode** with a **PRE-TRACTION hypothesis-forming register** — a pre-revenue greenfield operator gets hypothesis-forming questions, not an evidence-audit of customers/traction that don't exist yet.
- **Builder-mode DEPTH FLOOR** — Builder mode is infiquetra's high-frequency mode (infra/workflow/internal-tooling), so it carries real discovery/shaping rigor, not a one-liner.
- **Mid-session mode-switch** — startup↔builder can flip within a session.
- **Frame note in its OWN `docs/office-hours/` dir** (frontmatter `kind: frame-note`), NOT `docs/ideation/` — avoids colliding with the `/ideate` resume-scan (`skills/ideate/SKILL.md:56`).

**Rejected alternatives.**
- *Collapse to one "is the frame settled?" diagnostic.* REJECTED — a review recommended it, **OVERRIDDEN** because Infiquetra is a real startup heading to paying customers; the startup forcing-questions matter.
- *Frame note under `docs/ideation/`.* REJECTED — resume collision with the `/ideate` resume scan (`skills/ideate/SKILL.md:56`); the frame note gets its own `docs/office-hours/` home.
- *Thin builder mode (one-liner).* REJECTED — Builder mode is the high-frequency path and must carry depth.
- *Literal evidence-audit startup questions for a pre-traction operator.* REJECTED — wrong register for pre-revenue greenfield; ported stage-aware to hypothesis-forming instead.

**Rationale.** Faithful gstack port keeps the engine that makes the front door repeatable, shedding gstack's runtime boilerplate per the campaign's port model. The two-mode split survives because infiquetra is genuinely both a startup and a builder shop; the stage-aware + depth-floor adaptations make each mode fit the actual operator rather than a generic YC founder or a throwaway builder check.

**Revisit when.** Infiquetra reaches PMF (revisit the pre-traction register — startup questions can shift back toward evidence-audit); `/investigate` + `/spec` ship (add them as routes).

**Refs.** Plugin `0.6.0`. Part of the engine-merge campaign — see [#lifecycle-engine-merge-campaign](#lifecycle-engine-merge-campaign). Ship record: ARCHIVE [#office-hours-engine-rebuild-shipped](ARCHIVE.md#office-hours-engine-rebuild-shipped). Frame-note home: `docs/office-hours/`.

### Operator-choice framework ships doc-only; CLI helper deferred to `/work` (PR `#171`)  {#operator-choice-framework}

**Decision.** Ship the operator-choice framework as a **DOC-ONLY foundation**: `references/operator-choice.md` — the decision contract for the three execution backends `inline` | `team-execution` | `cc-workflows-ultracode` (these enum strings are the contract; prose labels like "CC workflows"/"ultracode" are not) — plus short prose **offer hooks** in `/loop` and `/work`. Lifecycle owns the **choice**, not execution. No code/helper ships this PR. The four interview answers settled:

- **(a) Who decides** — auto-recommend + **always confirm**. Inline-by-default; escalation is cheap. The agent proposes a backend; the operator confirms.
- **(b) Triggers** — `team-execution` when any `should_offer_team_execution` constant trips (`file_count>=8`, `phase_count>=4`, `has_security`, `has_infra`, `cross_repo`, `deployment_sensitive`) **or** the work needs reviewer consensus; `cc-workflows-ultracode` for broad-independent-parallel-fan-out / exhaustive-sweep work (Claude-Code-only). On **OVERLAP, offer BOTH** — no hard precedence rule.
- **(c) Capability gate** — document all three backends always; **hide** the ultracode option only when the Workflow tool is observably absent; **always graceful-fallback** at execution time.
- **(d) Scope** — `/loop` and `/work` only this PR. The other command rebuilds wire their own offers as they land.

**Rejected alternatives.**
- *Add a library-only `recommend_execution_backend()` helper now.* REJECTED — skills are markdown the agent reads, so a Python helper with no caller would be uncallable and would drift against the doc. This is the verified state of the existing `should_offer_team_execution` (defined in `lifecycle_state.py` but never called outside its own test). The CLI-backed helper is **DEFERRED to the `/work` rebuild**, where it gets a real caller.
- *Silent auto-pick.* REJECTED — violates always-confirm; the operator must see and accept the escalation.
- *Show-but-disable the ultracode option when unavailable.* REJECTED — hide it instead (cleaner; capability is observable).
- *Wire all lifecycle commands now.* REJECTED — scope is `/loop` + `/work`; the rest cite the doc as they rebuild.
- *A hard "risk dominates fan-out" precedence rule on overlap.* REJECTED — cosmetic given always-confirm; offering BOTH lets the operator decide.
- *Copy the brainstorm channel-inline wording verbatim.* REJECTED — reference `skills/brainstorm/SKILL.md`'s canonical channel-inline convention (redis-channel sessions cannot call AskUserQuestion) instead of duplicating it.

**Rationale.** Matches the queue's "no scripts" sizing — one shared reference doc + 2-3 line offer hooks. The doc is the consumed source of truth (the decision contract, complementing `saga-spec.md`'s storage contract). An honest unconsumed-style foundation in the same spirit as the saga ship: settle the contract before consumers calcify it.

**Revisit when.** The `/work` rebuild — wire the CLI-backed execution-backend helper against this doc (or decide the prose offer suffices and no helper is needed).

**Refs.** Plugin `0.5.0`. Part of the engine-merge campaign — see [#lifecycle-engine-merge-campaign](#lifecycle-engine-merge-campaign). Decision contract: `plugins/infiquetra-lifecycle/references/operator-choice.md`; complements storage contract `references/saga-spec.md`. Ship record: ARCHIVE [#operator-choice-framework-shipped](ARCHIVE.md#operator-choice-framework-shipped). Channel-inline convention: `plugins/infiquetra-lifecycle/skills/brainstorm/SKILL.md`. Shipped via PR `#171` (squash `e935bd4`).

### Saga schema: derived `kind-id` identity + append-only envelope log + three-axis state (PR `#170`)  {#saga-schema-foundation}

**Decision.** Define `saga` — the durable, resumable work-state envelope — as the first foundation of the engine-merge campaign, with this schema:

- **Identity: derived `kind-id`** (`issue-<N>` / `task-<slug>`), minted at birth and **sticky**. `round` and `phase` are *fields*, not identity. A task-saga that later gets an issue keeps its id and gains an `issue_ref` (the index cross-references `issue_ref → saga_id` so it stays findable by issue#). Human-legible dirs (`sagas/issue-42/`), deterministic, backward-compatible with the old `{kind}-{id}`.
- **Storage: append-only timestamped envelope log (canonical) + derived `state.json` index (rebuildable).** Each tick is an immutable file `sagas/<saga_id>/<YYYYMMDD-HHMMSS>.md`; ordering is **always by filename string, never mtime** (same-second collision → `-1` suffix). The index is `{last_updated, active_saga_id, sagas:{...}, current_work:{…legacy fields…, saga_id}}`, written atomically (temp+rename); a corrupt index is never fatal because `scan` rebuilds from the log.
- **File format: gstack envelope** — YAML frontmatter (machine fields incl. `extra:` for unknown-key round-trip) + `## Summary` / `## Decisions` (KTDs) / `## Remaining` / `## Notes / Tried` body. Cold-resume reads from frontmatter; matches the shipped CE-artifact house style.
- **Three stored state axes, one derived:** `lifecycle_phase` (CE flow: `ideation|brainstorm|plan|review|work|qa|retro`), `phase_status` (`pending|in_progress|complete`; authoritative, drives `next_phase` = phase+1 if complete else phase), `status` (thread disposition: `active|blocked|paused|handed-off|done|abandoned`; MUST NOT take `pending`/`in_progress`). **`maturity` is derived at `/handoff` time** from `lifecycle_phase` (the existing `infer_maturity` mapping), not stored.
- **List merge: full-snapshot semantics** — a tick's lists replace; absent carries forward; empty clears. Not union.
- **Full unify now:** one `saga.py` engine (`save`/`restore`/`scan`/`context`) with the 3 legacy scripts refactored into thin wrappers.
- **Spec home: plugin-level** `plugins/infiquetra-lifecycle/references/saga-spec.md` (a new convention — no plugin-level `references/` existed before); each consuming SKILL links to it.

**Rejected alternatives.**
- *Minted opaque saga-id (UUID/counter).* Rejected: not human-legible, not deterministic, requires a lookup to resume issue-born work. Derived `kind-id` is self-describing and backward-compatible.
- *Engine-only, migrate the storage format later (PR1 engine+wrappers / PR2 format).* Considered as a de-risk fallback; rejected for this ship in favor of one PR — the user chose "full unify now," and characterize-first tests make the format migration safe in a single change.
- *mtime ordering.* Rejected: mtime is not stable across rsync/backup/snapshot-restore; filename-as-order is deterministic and copy-safe. (Note: the win is for rsync/backup, NOT git worktrees — those don't carry git-ignored state at all.)
- *Union list merge.* Rejected: union-only lists accumulate stale `open_questions`/files and mislead cold resume; gstack ticks are full snapshots, so resume payloads must be able to shrink.
- *Stored `maturity` axis.* Rejected: redundant with `lifecycle_phase`; deriving it at `/handoff` removes a constant axis and the `status`↔`phase_status` ambiguity.
- *Round/phase in the identity.* Rejected: would re-mint a saga id every round, breaking sticky resume; round and phase are mutable fields of a single sticky-id thread.

**Rationale.** Saga is **gstack-dominant** (CE has no saga primitive — single-session assumption — so only its artifact-discipline framing is borrowed): gstack supplies the envelope mechanics (frontmatter+body, filename-as-order, branch-agnostic restore); the payload richness (issue+PR rounds, journal/ADR linkage) is lifecycle's own scripts; CE's contribution is the implied flow recorded in `lifecycle_phase`. Settling the contract semantics (axes, snapshot lists, `current_work`) in the spec **before** consumers calcify them is the whole point of building this foundation first. This ships an **unconsumed primitive** — after this PR no command calls `restore`/`scan`; the 3 legacy CLIs keep working as wrappers and the engine is validated by its own unit tests + manual smoke. Consumer wiring (`/work`, `/resume`, `/loop`, `/plan`) is each consumer's own queued item.

**Revisit when.** A consumer rebuild surfaces a missing/awkward field or enum (extend via `schema_version` + the `extra:` preserve-unknown seam, not a breaking change); append-only growth needs a GC policy (the spec leaves a `max_ticks` seam); or a second identity collision pattern emerges that the derived-id guards don't cover.

**Refs.** Plugin `0.4.0`. Part of the engine-merge campaign — see [#lifecycle-engine-merge-campaign](#lifecycle-engine-merge-campaign). Spec: `plugins/infiquetra-lifecycle/references/saga-spec.md`. Plan `.claude/plans/ok-we-yestereday-we-scalable-fox.md`. ARCHIVE [saga foundation shipped](ARCHIVE.md#saga-foundation-shipped) — consumers remain queued in [QUEUED.md](QUEUED.md).

### Rebuild lifecycle commands by merging gstack + CE engines into self-contained infiquetra engines (commit pending)  {#lifecycle-engine-merge-campaign}

**Decision.** Rebuild each diverged `infiquetra-lifecycle` command — and adopt two missing ones (`/investigate`, `/spec`) — by **merging the best of compound-engineering (CE) and gstack into a new, self-contained infiquetra engine**, worked **1-by-1 via an interview-driven merge**. Port model = the shipped `/ideate` rebuild: extract the engine, adapt to infiquetra (1-human + multi-agent team; `sdlc-manager` owns SDLC issues/boards/readiness; `infiquetra-deploy` owns deploy; the engineering journal; context-libraries), and shed gstack's ~780-line runtime boilerplate **with Jeff's per-item sign-off**. Neither source has priority — Jeff leans CE. Build two foundations first: a first-class `saga` durable/resumable work-state envelope (P0) and a shared inline / team-execution / Claude-Code-workflows operator-choice framework (P1), because the command rebuilds read them. Full per-command queue: [QUEUED.md](QUEUED.md) engine-merge initiative.

**Rejected alternatives.**
- *Adopt one upstream wholesale (just gstack, or just CE).* Rejected — Jeff: "otherwise I would just use one or the other and forget about all this." The value is a merged engine infiquetra owns and evolves, taking bits of both.
- *Vendor gstack / runtime-depend on CE.* Rejected — same standalone-boundary rationale as the `/ideate` ADR ([#ce-ideation-engine-restore](#ce-ideation-engine-restore)); gstack also carries ~780 lines of runtime plumbing (telemetry, gbrain, `~/.gstack`, model overlays) irrelevant to infiquetra.
- *Leave the thin stubs.* Rejected — they bias toward facilitation; the engine is what makes a command repeatable. See LEARNINGS [#lifecycle-thin-reskin-systemic](LEARNINGS.md#lifecycle-thin-reskin-systemic).
- *Auto-shed gstack boilerplate without review.* Rejected — Jeff wants input on what's shed; each rebuild surfaces shed candidates for sign-off.

**Rationale.** CE and gstack each have engine mechanics worth keeping (CE: structured artifacts, causal-chain debugging, persona/findings/validator review; gstack: scope-mode reviews, risk-gated QA, multi-specialist fan-out, save/restore checkpoints). Merging the best of both into an infiquetra-owned engine — rather than depending on either — keeps the plugin self-contained, evolvable, and adapted to a 1-human + agents shop where artifacts must be agent-consumable. Worked 1-by-1 so each merge is a deliberate, interview-settled design, not a bulk port that would re-introduce the stub-disease at engine level.

**Revisit when.** A command's interview shows the merged engine is more than infiquetra needs (ship a lighter version), or CE/gstack ship a materially better engine worth re-syncing, or the parallel-fork maintenance cost exceeds the value of self-containment.

**Refs.** QUEUED engine-merge initiative; LEARNINGS [#lifecycle-thin-reskin-systemic](LEARNINGS.md#lifecycle-thin-reskin-systemic), [#workflow-structuredoutput-budget](LEARNINGS.md#workflow-structuredoutput-budget), [#stub-port-drops-engine](LEARNINGS.md#stub-port-drops-engine); DECISIONS [#ce-ideation-engine-restore](#ce-ideation-engine-restore), [#sdlc-handoff-ownership-boundary](#sdlc-handoff-ownership-boundary).

## 2026-06-01

### Restore the CE ideation engine into `/ideate` + `/brainstorm`, self-contained (commit `30c9099`)  {#ce-ideation-engine-restore}

**Decision.** Rebuild `infiquetra-lifecycle`'s `/ideate` and `/brainstorm` from thin facilitative
stubs into full divergent→convergent engines ported from compound-engineering (CE) and adapted to the
infiquetra world — self-contained, no runtime dependency on CE. `/ideate` generates many candidates
across parallel frame agents, critiques all, and presents only survivors; cut ideas stay revivable.
Two deliberate improvements over CE: (1) a two-way partnership — operator seeds feed *into* the frame
agents and face the same critique; (2) a revival state machine that re-enters the filter with new
evidence (and adjudicates novelty) so revival cannot soft-promote a categorically-cut idea. Added
infiquetra grounding CE never had: context-library reader (`*-context-library` via `gh`), named-repo
reader, grounding-fit gate, read-only `gh` issue-theme clustering. Dropped CE's Proof/HITL,
HTML/output-mode, elsewhere/non-software modes, Slack, and web-research-cache.

**Rejected alternatives.**
- *Delegate to CE at runtime (load `ce-ideate` when present).* Rejected: couples lifecycle to CE
  being installed at a compatible version and drags in CE's ecosystem (Proof, modes, conventions);
  contradicts the plugin's standalone Boundaries.
- *Keep the thin facilitative stubs.* Rejected: "produce a small option set; lead the user through
  choices" biases toward facilitation, which is why ideation felt like the operator supplied all the
  ideas. See LEARNINGS `{#stub-port-drops-engine}`.
- *Issue themes via `sdlc-manager`.* Rejected: `sdlc-manager` has no theme-clustering and issue
  *reads* are not its boundary (it owns mutation). `/ideate` reads issues read-only via `gh` and
  clusters them itself.

**Rationale.** The operator wanted CE's generative engine + survivors back, plus a genuine
partnership where their ideas also enter the pool and rejected ideas are revivable. Self-contained
keeps the plugin's ownership boundaries clean. Forked from CE 3.9.2; authored and adversarially
verified via an ultracode workflow (13 agents; 5 major findings remediated, 0 blocking).

**Revisit when.** CE ships a materially better ideation engine worth re-syncing, or the parallel-fork
maintenance cost exceeds the value of staying self-contained.

**Refs.** Plugin `0.3.0`, marketplace metadata `2.4.0`. LEARNINGS `{#stub-port-drops-engine}`. Plan
`.claude/plans/can-you-review-the-inherited-lantern.md`.

## 2026-05-31

### Rename `infiquetra-loop` → `infiquetra-lifecycle` (commit `0ed70f2`)  {#rename-loop-to-lifecycle}

**Decision.** Rename the plugin to `infiquetra-lifecycle`. "Loop" named only the `/loop` router
command, not the idea-to-ship lifecycle the plugin actually spans (Think → Plan & execute → Hand
off → Review → Improve & route). Renamed the ignored runtime-state dir to
`.claude/infiquetra-lifecycle/` and the handoff-envelope field `loop_owner` → `lifecycle_owner`,
with `sdlc-manager` updated in lockstep (its 4 hardcoded state-path references). Kept the `/loop`
command name unchanged — it's one verb in the lifecycle, not the whole thing. Surfaced the
five-phase command grouping in the plugin description, both READMEs, and the changelog so users see
the categorization.

**Rejected alternatives.**
- *`infiquetra-flow`.* Rejected: still reads too close to "loop" and is vaguer about scope.
- *`infiquetra-sdlc`.* Rejected: collides conceptually with the existing `sdlc-manager` plugin,
  blurring the boundary (lifecycle workflow vs GitHub issue/board ownership).
- *`infiquetra-cadence` / `-forge` / `-workbench`.* Rejected: evocative but less self-describing
  than "lifecycle".
- *Rewrite the old name in dated historical docs (brainstorms, ideation, plans, reviews,
  work-sessions, `ARCHIVE.md`).* Rejected per the journal rule "never silently overwrite history" —
  those artifacts record what the plugin was called at the time.

**Rationale.** The name should describe what the plugin does to a first-time user. "Lifecycle"
matches the description and command taxonomy; "loop" undersold it.

**Revisit when.** The plugin's scope narrows back to pure routing/iteration, or a clearer
single-word name for "full engineering lifecycle" emerges.

**Refs.** Plugin `0.2.0`, `sdlc-manager` `1.6.1`, marketplace metadata `2.3.0`.

### SDLC handoff issue artifacts belong to `sdlc-manager` (commit `2fc317e`)  {#sdlc-handoff-ownership-boundary}

**Decision.** Put handoff issue drafting, source artifact resolution, handoff maturity metadata,
prepared-draft sidecars, mutation plans, labels, board placement, and create-after-confirmation in
`sdlc-manager`. Keep `infiquetra-loop` responsible for lifecycle context and future `/handoff`
routing only.

**Rejected alternatives.**
- *Generate handoff issue bodies inside `infiquetra-loop`.* Rejected: it would duplicate SDLC
  issue semantics and make two plugins responsible for labels, project fields, and readiness.
- *Add a separate handoff artifact format.* Rejected: prepared issue drafts already provide the
  markdown plus JSON sidecar boundary needed for review before mutation.
- *Require recipient teams to have `infiquetra-loop` installed.* Rejected: handoff issues must be
  self-contained for agent teams or humans working only from GitHub.

**Rationale.** This keeps the lifecycle plugin thin at the exit point while centralizing SDLC
mutation rules in the plugin that already owns issue readiness. The prepared draft remains useful
without mutation, and `issue create-prepared` remains the single place where side effects are
rendered and confirmed.

**Revisit when.** Multiple non-SDLC destinations need the same handoff source resolver, or
`infiquetra-loop` grows durable lifecycle state that cannot be represented cleanly in the
prepared issue sidecar.

**Refs.** Plan [Add SDLC handoff flow](../plans/2026-05-30-002-feat-sdlc-handoff-flow-plan.md);
requirements [Infiquetra Loop SDLC Handoff](../brainstorms/2026-05-30-infiquetra-loop-sdlc-handoff-requirements.md).

### Prepared issue workflow uses draft/sidecar boundary plus confirmed mutation (commit `74cd372`)  {#prepared-issue-workflow-boundary}

**Decision.** Add `sdlc-manager issue prepare` and `issue create-prepared` as separate steps.
`issue prepare` writes a markdown draft and JSON sidecar; `issue create-prepared` re-runs
readiness, renders a mutation plan, asks for confirmation, repairs repo prerequisites, handles
mapping PRs, creates the issue, and records the result back onto the draft.

**Rejected alternatives.**
- *Direct source-text to `gh issue create`.* Rejected: bypasses review and makes readiness failures
  visible only after the external issue exists.
- *Put LLM interpretation inside `sdlc_manager.py`.* Rejected: the CLI should stay deterministic;
  skills and agents own rough-source interpretation.
- *Create new issue types for Asgard/Olympus.* Rejected: the six SDLC issue types remain
  canonical; team differences belong in readiness profiles and board/status routing.

**Rationale.** The split gives operators a durable review point before GitHub mutation while still
letting the final create flow perform repo repair and board placement as one visible plan.
Sidecars keep deterministic metadata and lifecycle state out of prose-only markdown, and
re-validation prevents stale edited drafts from bypassing team readiness.

**Revisit when.** Multiple non-agent callers need deterministic text-to-body generation inside the
CLI, or when prepared drafts become common enough to justify a richer review UI or batch create
surface.

**Refs.** LEARNINGS [prepared issue artifact boundary](LEARNINGS.md#prepared-issue-artifact-boundary).

## 2026-05-29

### Split Infiquetra lifecycle orchestration from deployment mutation (commit pending)  {#infiquetra-loop-deploy-boundary}

**Decision.** Add `infiquetra-loop` as the daily lifecycle orchestration plugin and
`infiquetra-deploy` as a separate deployment plugin. `infiquetra-loop` owns office-hours,
strategy, ideation, brainstorm, planning, work execution, code review, optimization, QA, SDLC
issue progress, engineering-journal prompts, retro, and resume. `infiquetra-deploy` owns
tag-promotion deployment, status, release notes, rollback, and hotfix helpers. `team-execution`
remains independent and is offered only when risk, size, or parallelism justify the cost.

**Rejected alternatives.**
- *One merged super-plugin.* Rejected: deployment mutation has a higher blast radius than
  lifecycle coaching and should keep a hard operational boundary.
- *Copy Superpowers, Compound Engineering, gstack, and VECU workflows wholesale.* Rejected:
  the useful pieces need to be adapted to Infiquetra docs, SDLC, and context-library references;
  generic cleanup, GitHub helper, and plugin-management utilities are intentionally out of scope.
- *Version raw loop state as repo artifacts.* Rejected: durable plans and work-session summaries
  belong in repo docs, but raw checkpoint state, API caches, validator JSON, and resume scratch
  are local session data and already covered by the `.claude/` ignore convention.

**Rationale.** The split lets the daily loop replace recurring Superpowers and Compound
Engineering lifecycle use while still enforcing a clear deployment safety boundary. Durable docs
give session-to-session continuity without committing stale runtime state. Keeping `team-execution`
separate preserves its validator and nonprod automation contract without forcing every loop to pay
that token or coordination cost.

**Revisit when.** Deployment policy moves out of tag-promotion, loop usage shows deployment
handoff friction dominates safety value, or `team-execution` becomes cheap enough to run by
default on normal work.

**Refs.** `plugins/infiquetra-loop/`, `plugins/infiquetra-deploy/`,
[team-execution v2 decision](#team-execution-v2-validators).

---

## 2026-05-27

### `team-execution` v2 uses context-selected validators and guarded nonprod automation (commit pending)  {#team-execution-v2-validators}

**Decision.** Evolve `team-execution` from reviewer-only orchestration into a reviewer plus
validator workflow. Validators are a maximum available roster, selected by repository context,
changed files, workflows, contracts, docs, tests, and optional `.team-execution.json`. Automation
is allowed only for `github.com/infiquetra/*`, only after gates pass, and only for nonprod or
publish-nonprod workflows.

**Rejected alternatives.**
- *Spawn every validator on every plan.* Rejected: creates noise, cost, and false blockers for
  validators unrelated to the change.
- *Let validators run before reviewer consensus.* Rejected: reviewer non-consensus means the
  implementation is still unstable; validator findings would be stale or duplicated.
- *Allow generic deployment automation once checks pass.* Rejected: production, staging, branch
  deletion, force-push, and credential changes carry a higher operational risk than this plugin
  should automate.

**Rationale.** Context selection keeps validator evidence proportional to risk while still making
the approved roster available. Gating validators after reviewer consensus creates a stable artifact
to scan and test. Nonprod-only automation gives useful end-to-end validation without turning a
planning plugin into a production deployment system.

**Revisit when.** We have repeated evidence that a validator category is always selected together
with another category and should be merged, or when production deployment safety is owned by a
separate audited release plugin.

**Refs.** LEARNINGS [team setup asset drift](LEARNINGS.md#team-setup-asset-drift).

---

## 2026-05-25

### `redis-channel` plugin: Hermes-agnostic Claude Code channel over Redis Streams (commit pending)  {#redis-bridge-decoupled}

**Decision.** Build the `redis-channel` plugin as a generic Claude Code channel that speaks a documented Redis-streams protocol — no Hermes-specific knowledge in the plugin. The Hermes-side counterpart (`hermes-claude-code-router`) lives in its own public GitHub repo so the protocol is reusable by any future consumer.

**Rejected alternatives.**
- *Embed Hermes/Discord logic directly into the plugin.* Rejected: would reimplement Discord voice-receive that already works (battle-tested) in `hermes-agent`. Verification confirmed the voice-receive code is **not** in `home-lab/asgard_voice_arbiter` (where the initial design assumed it lived) — the arbiter is routing-only; the sink/decode lives in closed-source `hermes-agent.gateway.platforms.discord`. Rebuilding would have been 3–5 days of unknown work.
- *Add the router as a 4th plugin inside `infiquetra/hermes-extensions`.* Considered seriously after `hermes-extensions` was identified as the canonical external-plugin pattern. Rejected per user preference for independent versioning. The router's expected LoC (~1k+) justifies its own home.
- *Use HTTP transport between plugin and router.* Rejected: Redis already runs on Mac mini for `voice_coordinator`; Streams give durable + ordered + consumer-group resume; no port-binding on either side; matches existing Hermes infra patterns.

**Rationale.** Decoupling means: (a) any future consumer (web UI, mobile app, CLI test harness) can drive a Claude Code session by speaking the protocol; (b) the plugin is testable without Hermes infrastructure; (c) protocol changes are version-gated, not implicit. The protocol spec (PROTOCOL.md) and pydantic models (`server/protocol.py`) are copied verbatim into both repos; synchronized PRs enforce drift detection at review time.

**Revisit when.** A second router consumer materializes and surfaces protocol shortcomings, OR the multi-session registry proves unused after 1 month of production data (then collapse to 1:1 lock and merge the router back into a more direct architecture).

**Refs.** [voice-only-permission-approval](#voice-only-permission-approval), [askuserquestion-interception](#askuserquestion-interception), [redis-bridge-verification](LEARNINGS.md#redis-bridge-verification), plan at `/Users/jefcox/.claude/plans/i-would-like-to-distributed-hanrahan.md`.

### Permission approval is voice-only in v1 with destructive echo-confirm (commit pending)  {#voice-only-permission-approval}

**Decision.** Tool-permission relay over the channel accepts only voice approval ("yes <id>" / "no <id>"). Discord button approval (ephemeral DM Allow/Deny) is deferred to v2. Destructive operations (Write/Edit/NotebookEdit + Bash regex matches in `is_destructive`) trigger an echo-confirm safety net: "Approving destructive Bash. Say 'cancel' within 3 seconds."

**Rejected alternatives.**
- *Voice + Discord buttons in parallel (first-wins).* Rejected for v1: adds discord.py interaction handling, ephemeral message lifecycle, race-cancel logic — and the parallel-path UX optimizes for a scenario that doesn't actually exist (you're either hands-free in voice OR at Discord text; rarely both). v2 candidate if usage shows demand.
- *Tool-class allowlist (voice can approve read-only, never destructive).* Rejected by user: they want full hands-free. Mitigated by destructive echo-confirm + audit logging from day 1; revisit if false-positive rate is non-trivial.
- *Always require terminal approval.* Rejected: defeats the hands-free use case.

**Rationale.** Whisper false-positive rate (~1.4% on clean audio, higher in noise) is a real risk for destructive commands. 5-char random IDs (~11.8M space, generated by Claude Code core) make accidental triggering unlikely; 30s window bounds exposure; echo-confirm provides a "did you really mean it" beat. Audit logging from day 1 produces the data needed to tighten or relax this later.

**Revisit when.** Audit logs show ≥1 false-positive destructive approval in a month, OR usage data shows users prefer Discord-button approval to voice approval (would justify the parallel-path build cost). See [Discord button approval](QUEUED.md#discord-button-approval).

**Refs.** [redis-bridge-decoupled](#redis-bridge-decoupled); `is_destructive` classifier at `plugins/redis-channel/server/protocol.py`.

### `AskUserQuestion` interception over agent-file coaching (commit pending)  {#askuserquestion-interception}

**Decision.** When Claude calls `AskUserQuestion` from a `redis-channel` channel session, the CC plugin's MCP server intercepts the tool call and converts the structured question to an inline-choice reply ("Which? A) ..., B) ..., C) ..."). The user's free-text response is parsed against the options and returned as the tool result. Agent-file coaching (in `agents/redis-channel-coach.md`) is provided as a friction-reducing hint but is **not** the enforcement layer.

**Rejected alternatives.**
- *Coach Claude via `agents/redis-channel-coach.md` to avoid AskUserQuestion when source is a channel.* Rejected as primary mechanism: Claude's training pulls it toward AskUserQuestion for clarification; coaching is probabilistic, not deterministic. Verified the channel protocol has no native facility by reading the official Discord channel plugin source + `https://code.claude.com/docs/en/channels-reference`.
- *Wait for the Claude Code channels protocol to add structured-question support.* Rejected: not on the published roadmap; would block v1.
- *Fail the AskUserQuestion call with an error so Claude retries with inline text.* Rejected: poor UX (user sees a tool error, not a question).

**Rationale.** Interception is deterministic. The MCP server sees every tool call before it reaches the user; converting it to a `reply` + parsing the next inbound is a finite-state interaction the server fully controls. Removes a category of "Claude ignored the coach" failures.

**Revisit when.** Claude Code adds a native `notifications/claude/channel/question_request` / `question_verdict` pair to the channel protocol — then replace interception with passthrough. Tracked in `plugins/redis-channel/PROTOCOL.md` "Reserved future expansion."

**Refs.** [redis-bridge-decoupled](#redis-bridge-decoupled); `plugins/redis-channel/PROTOCOL.md` AskUserQuestion section.

---

## 2026-05-08

### Adopt uv as canonical dependency sync (commit pending)  {#uv-canonical-sync}

**Decision.** Use uv as the canonical repository dependency sync tool. Track `uv.lock`, install CI dependencies with `uv sync --locked --extra dev`, and run local and CI checks through `uv run`.

**Rejected alternatives.**
- *Keep using pip in CI.* Rejected: it contradicts the desired repository standard and leaves installs unreproducible.
- *Use `uv pip install` without a lockfile.* Rejected: it is still an ad hoc install path and does not satisfy the existing revisit condition for tracking `uv.lock`.
- *Move all dev dependencies to `[dependency-groups]` now.* Rejected: the existing `dev` extra maps directly from the prior `pip install -e ".[dev]"` workflow, so moving dependency ownership would add churn without improving the conversion.

**Rationale.** The repository already has `pyproject.toml` metadata and had a documented revisit condition to track `uv.lock` once uv became canonical. A checked lockfile plus `uv sync --locked --extra dev` makes CI and local development use the same dependency graph.

**Revisit when.** uv stops being the repository development standard, or the project intentionally changes from extras-based dev dependencies to uv dependency groups.

**Refs.** Supersedes the `uv.lock` portion of [gitignore `.claude/` + no `uv.lock`](#gitignore-claude-and-no-uv-lock); archived pre-correction version in [ARCHIVE](ARCHIVE.md#superseded-no-uv-lock-decision).

---

## 2026-05-01

### Gitignore `.claude/`; `uv.lock` decision superseded (commit `4da5705`)  {#gitignore-claude-and-no-uv-lock}

**Decision.** Add `.claude/` to `.gitignore`. The prior decision not to track `uv.lock` is superseded by [Adopt uv as canonical dependency sync](#uv-canonical-sync).

**Rejected alternatives.**
- *Track `.claude/settings.local.json`.* Rejected: file holds per-user permission grants for the Claude Code session. Sharing one user's allowed-tool list would either leak local preferences or get blindly overwritten by the next user. The file is named `.local.json` for a reason.
- *Track `.claude/context/sdlc-plan-state.json`.* Rejected: mid-session orchestration state from `sdlc-manager`. Stale immediately after the session ends; would create misleading commits if pushed.

**Rationale.** `.claude/` content is per-user / per-session by design (settings.local + context state). The earlier `uv.lock` rationale was correct when the repo used ad hoc pip/uv installs, but no longer applies now that uv is the canonical lock-and-install path.

**Revisit when.** Claude Code introduces a *shared* settings file under `.claude/` that's intended to be checked in. At that point, narrow the gitignore from `.claude/` to specifically `.claude/settings.local.json` and `.claude/context/`.

**Refs.**
- DECISIONS [uv canonical sync](#uv-canonical-sync) — supersedes the lockfile portion of this decision.
- LEARNINGS [marketplace registry drift](LEARNINGS.md#marketplace-drift) — same PR (#112).
- ARCHIVE [PR #112](ARCHIVE.md#pr-112-marketplace-fix) — shipped record.
- ARCHIVE [superseded no-uv-lock decision](ARCHIVE.md#superseded-no-uv-lock-decision) — pre-correction record.

---
