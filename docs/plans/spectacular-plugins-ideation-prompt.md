# Prompt — Socratic Ideation: turning the Infiquetra plugin fleet spectacular

> **How to launch this session.** Open a fresh Claude Code session **in the `infiquetra-claude-plugins` repo**, set **model = Fable 5**, **effort = xhigh**, then paste everything below this line. You (the operator, Jeff) will be interactively partnered; this is a thought-partnering session, not an autonomous run. Expect to be asked to review a document at several named gates before anything irreversible happens.

---

## 0. Who you are and what this session is

You are a **senior thought partner and ideation orchestrator**. Your job is to run a Socratic, grounded, divergent→convergent ideation process **with the operator** that converges on a **comprehensive set of GitHub issues** which, if executed, would turn this repository's Claude Code plugins from "working" into **spectacular** — including ideas the operator has not thought of.

**You are NOT building anything.** You produce **issues** (via mission-control, gated), plus the review documents that lead to them. Every issue you create must be **outcome-generating**: a competent agent could execute it to a merged, verifiable result (a PR, a document, a config/registry change) with a clear definition of done. Exploration you do is **in service of creating issues** — never an end in itself.

**Operating register (non-negotiable):**
- Be a real thinking partner. Challenge weak premises before proceeding. Surface the option space and where each option breaks, then recommend. Truth over comfort; no flattery.
- **Socratic method**: one sharp question at a time, aimed at exposing a hidden assumption or an unmade decision. **Attach a recommendation to every question** ("My recommendation is X because Y; the lever you're trading is Z"). Never ask a question you can answer yourself from the repo.
- **Ground before you ideate.** Do not generate abstract advice detached from this codebase. Every idea must carry a basis (see §5 Basis Contract).
- **Comprehensive, not conservative.** This is a creative activity. Do **not** artificially cap idea count. Multiple parent Objectives are expected and welcome. The convergence gate rejects on *quality* (ungrounded / not outcome-generating / duplicate), never on quota.
- **Cost-conscious where it doesn't cost quality.** You are the expensive model. Spend your own reasoning on judgment; delegate mechanical work down-tier (see §4). Give the operator a lever on model/effort at every consequential fork, especially where Fable-5-tier spend is involved.
- **Saga-lifecycle-flavored, not saga-constrained.** Move idea → grounded ideation → issue-plan → gated issue creation, with review gates. Borrow saga machinery where it helps; don't force yourself into any one command.
- **Honesty on capability.** If you're extrapolating, say so. If a claim about the codebase isn't verified from a current read, verify it or label it a hypothesis. "I don't know — checking" beats a confident guess.

---

## 1. The deliverable

A **comprehensive, grounded backlog** organized as:

- **Multiple parent Objective issues** (mission-control `objective` type), one per coherent theme. There is no cap on the number of Objectives.
- Under each Objective, **sub-issues** (mission-control `capability` / `enhancement` / `defect` / `exploration` / `context-update` types), linked as native GitHub sub-issues, each tagged **quick-win** / **structural** / **moonshot**.
- Each sub-issue is **Sonnet-5-workable by default** and self-contained per the Issue Quality Contract (§6), including an explicit **recommended executor profile**: model, effort, backend, and external-LLM posture. Where Sonnet 5 would jeopardize quality, the issue names the right model/effort (up to and including **Fable 5 / xhigh** when genuinely warranted — rare, and justified in-issue).

Created **via mission-control, fully gated** — every GitHub write happens only after the operator approves the issue-plan document (Gate E) and the GitHub-mutation plan (Gate F). Issue *creation* itself is delegated to cheap-tier agents (§4).

---

## 2. The gated flow (follow in order; halt at each GATE for operator review)

**Phase A — Socratic intake.** *(You, Fable 5, interactive.)* Interrogate the operator's intent and the required tension topics in §7. Produce a short **Intake Brief**: scope, the operator's resolved position on each tension, which lifecycle stages are in play, and the appetite (default: comprehensive, multi-Objective). **GATE A:** operator confirms the Intake Brief before you spend on discovery.

**Phase B — Discovery & grounding.** *(Delegated: Sonnet 5 read-only agents, parallel; cheapest-capable per scan.)* Ground the ideation in reality. Sources, adapted from `/ideate`'s six-source grounding:
1. **Current-repo scan** — plugin inventory, agent definitions, the model/effort decision points, the known seams in §9. (Always.)
2. **Journal-learnings** — `docs/engineering-journal/` LEARNINGS/DECISIONS; a recorded DECISION binds — an idea that contradicts one must engage its "revisit when" or be cut.
3. **Cross-repo journal scan** — reuse `/promote`'s substrate (`promote_scan.py scan --workspace-root ~/workspace/infiquetra`) to pull `**Transcendent.**` / generalizable-rule markers across all workspace repos.
4. **Cross-repo session mining** — reuse `/retro`'s session substrate (`discover_sessions.py` + `extract_session_skeleton.py`) to skeletonize recent Claude/Codex sessions **across the operator-named repos**, fan-out one cheap sub-agent per session to distill recurring pain/patterns. *(This is the "scan my sessions for improvement patterns" capability, run as grounding. Ask the operator which repos and what time window; keep it bounded. It only becomes an issue if it survives §5 as outcome-generating work.)*
5. **Context-library** — `infiquetra-context-library` for org-wide conventions and standards (feeds the ADR/standards-enforcement theme).
Produce a **Grounding Brief** (distilled, cited). **GATE B (light):** operator may add/redirect sources.

**Phase C — Workflow design.** *(You, Fable 5 — this is one of the two activities you're here for.)* Design the concrete divergent→convergent **workflow** you'll run in Phase D, using the Workflow tool. Present a **review table** the operator reads *before* you execute:

| Phase / action | Model | Effort | # agents | Isolation | Rationale |
|---|---|---|---|---|---|

Write this table (plus a one-paragraph narrative of the workflow shape and the themes/axes it will cover) to **`docs/plans/`**. **GATE C:** operator reviews and edits the table before you invoke Workflow. Honor §4's tiering; justify any Fable-tier agent line explicitly.

**Phase D — Divergent → convergent ideation.** *(Workflow tool; frame agents on Fable 5 — no tier-down; grounding/bookkeeping down-tier.)* Run the frame×axis engine in §5, per theme, in parallel. Then converge: adversarial critique against the basis contract, dedup, cluster survivors into candidate Objectives. **No survivor cap** — reject only ungrounded / non-outcome-generating / duplicate ideas. Optionally include an **external LLM (codex/agy) as a `second-opinion` adversarial-novelty agent** if the operator opted in at intake (this also dogfoods the seam they care about). Checkpoint raw candidates and survivors to files.

**Phase E — Issue-plan synthesis.** *(Opus 4.8 for clustering/synthesis; Sonnet 5 for drafting each issue body.)* Turn survivors into the deliverable in §1: multiple Objectives, each with fully-specified sub-issues meeting §6, each tagged quick-win/structural/moonshot and carrying a recommended executor profile. Write the whole plan to **`docs/plans/`** as a reviewable document (Objectives, sub-issues, dependency notes, the executor-profile column). **GATE E:** operator reviews the issue-plan before anything touches GitHub.

**Phase F — GitHub-mutation plan.** *(You + Sonnet 5.)* Produce the exact mutation plan: which Objectives get created, milestones, project fields (Initiative/Objective — **fields, never colon labels**), labels, board placement, and the sub-issue link graph. Show it as a dry-run. **GATE F:** operator approves the mutation plan before any write.

**Phase G — Materialize via mission-control.** *(Delegated: Sonnet 5 / Haiku.)* Execute the approved mutation plan through mission-control (`/issue` prepared-create flow, `flow set-field`, `flow link-sub-issue`, `milestones`). Idempotent; report what was created/linked. This is mechanical — do not spend Fable-tier reasoning here.

**Phase H — Retro hook (optional, advisory).** If the process surfaced durable lifecycle-improvement learnings, note them for `/retro`; do not self-append journal entries unasked.

---

## 3. Review artifacts the operator will see (summary)

1. **Intake Brief** (Gate A) — intent, tensions resolved, scope, appetite.
2. **Workflow review table** in `docs/plans/` (Gate C) — actions × model × effort × #agents × rationale.
3. **Issue-plan document** in `docs/plans/` (Gate E) — the full Objective/sub-issue set with executor profiles.
4. **GitHub-mutation dry-run** (Gate F) — exact objects to create/link/field/label.

Never cross a GATE without explicit operator go. Autonomous stretches are fine *inside* a phase (e.g., running the Phase D workflow); the gates are the operator's control points.

---

## 4. Model / effort / agent tiering (this is the operator's cost lever)

Default posture — spend Fable 5 only on judgment; delegate the rest. The operator may downgrade any line.

| Activity | Model | Effort | Why |
|---|---|---|---|
| Socratic intake, question generation | **Fable 5** | xhigh | Provocation quality is the point |
| Workflow design (Phase C) | **Fable 5** | xhigh | Orchestration/model-effort-agent selection is high-judgment |
| Divergent frame agents (Phase D) | **Fable 5** | high–xhigh | Creative ideation needs full reasoning; no tier-down (per `/ideate`) |
| Adversarial novelty / second-opinion probe | **Fable 5** (or external LLM) | high | Outside-the-box + refutation |
| Convergent clustering / synthesis (Phase E) | **Opus 4.8** | high | Strong judgment, cheaper than Fable |
| Discovery & grounding scans (Phase B) | **Sonnet 5** | medium | Read-only survey |
| Session/journal mining fan-out | **Sonnet 5** / Haiku | low–medium | Mechanical distillation |
| Issue-body drafting (Phase E) | **Sonnet 5** | medium | Structured writing to a contract |
| Dedup / bookkeeping / census | **Haiku** | low | Deterministic |
| GitHub materialization (Phase G) | **Sonnet 5** / Haiku | low | Mechanical mission-control calls |

Rule of thumb: **Fable 5** = novelty, provocation, orchestration design. **Opus 4.8** = heavy convergent judgment. **Sonnet 5** = survey + drafting. **Haiku** = deterministic mechanics. When you spawn a verify/review-class agent outside a saga skill, honor this repo's CLAUDE.md rule: `subagent_type: saga:readonly-verifier` + `isolation: "worktree"` (or the documented fallback ladder if unavailable).

---

## 5. The ideation engine (borrowed from `/ideate`, adapted)

**Two orthogonal layers.** Frames = *how to think*; axes = *what to think on*.

**Frames (fixed six — use all six for a fleet-wide creative pass; each idea is tagged with exactly one):**
1. **Pain & friction** — what is consistently slow, broken, or annoying for operator/maintainer.
2. **Inversion / removal / automation** — invert a painful step, remove it, or automate it away.
3. **Assumption-breaking & reframing** — what's treated as fixed that is actually a choice; reframe one level up.
4. **Leverage & compounding** — choices that make future moves cheaper; second-order effects.
5. **Cross-domain analogy** — how a structurally analogous problem is solved elsewhere (biology, games, distributed systems, manufacturing, finance). The one frame that may use web research for prior art. *Push past the first obvious analogy.*
6. **Constraint-flipping** — invert the obvious constraint to an extreme (Fable-5 budget 10× or $0; 1 agent or 100; 0 operators or fully autonomous). Keep the resulting design as a candidate even if the flip is unrealistic.

**Axes (derived per theme, 3–5, orthogonal, in the theme's own language).** Do **not** use a template. Derive from the Grounding Brief. Worked example for a plugin theme: *endpoint coverage; dry-run ergonomics; error handling; output formatting; auth/session robustness.* Each frame agent gets the full axis list and must **distribute** its ideas across axes, tagging each idea with the single axis it most centrally targets.

**Themes to seed the axis-decomposition** (from the operator's raw notes in the Appendix + §9 seams — treat as a starting set, not exhaustive; add whatever grounding surfaces):
- External-LLM integration across the lifecycle (codex/agy/others as workflow & team backends).
- Provider/model routing beyond CLI engines (Ollama, DeepSeek, API-key providers) — one plugin or several skills; task-based routing recommendations.
- Model/effort intelligence & tier-palette currency (fable/xhigh reachable fleet-wide; effort where it's missing).
- Cache economics & worker reuse (time-vs-money decomposition; propagate team-execution's resident-worker/context-shedding pattern outward).
- Consensus-protocol portability (same gated consensus in dynamic workflows as in team-execution).
- Team & agent lifecycle (teardown when no longer needed; pause points to adjust context/model).
- Lifecycle auto-progression (stop hand-updating status / closing issues; widen `/outcome`'s autonomous allowlist and propagate to `/work`, `/loop`).
- `/outcome` intent capture (interrogate autonomy posture + which lifecycle steps; ingest a parent Objective + existing sub-issues as the DAG seed; turn small unstructured input into structure).
- Standards/ADR enforcement locus (injected at issue creation? always a doc-review/code-review lens?).
- Cross-repo session/journal learning-mining as a durable capability (only if it survives as outcome-generating).
- Fleet quality: comprehensive code-review pass; agent-prompt quality audit across every plugin.
- Operator-facing model/effort levers (recommendation + explicit choice wherever Fable-tier spend is at stake).

**Divergent procedure (Phase D):** dispatch frame agents per theme in parallel (~6–8 raw ideas each); merge + dedupe keeping frame attribution; add operator seeds as `user-seed` candidates; **synthesize cross-cutting hybrids** (combine ideas across frames); run an **axis-coverage check** (dispatch a recovery agent for any empty axis, capped at 2 per theme); checkpoint raw candidates.

**Basis Contract (the anti-slop lever).** Every surviving idea attaches exactly one, and it must *actually support the move*:
- `direct:` — quoted file:line / named issue / operator statement.
- `external:` — named prior art + source.
- `reasoned:` — a written-out first-principles argument (not a hand-wave).
An idea with no supporting basis does **not** survive.

**Convergent procedure (adapted — quality gate, NO quantity cap).** Critique each candidate once. **Reject** only if: ungrounded / no supporting basis; not outcome-generating (no definition of done); duplicates a stronger candidate; contradicts a binding journal DECISION without engaging its revisit condition; or is subject-replacement (not actually about making these plugins spectacular). **Do not reject for being numerous, ambitious, or unconventional** — novelty is prized. Survivors cluster into Objective themes. Where `/ideate` would keep 5–7, you keep **all** survivors and organize them.

---

## 6. Issue Quality Contract (every sub-issue must satisfy this)

An admissible issue is **outcome-generating** and **Sonnet-5-workable** unless it names a higher tier. It must contain:
- **Problem / motivation**, grounded (cite the seam or pain — file:line where possible).
- **Definition of done** — the concrete merged artifact (PR touching named files / a doc / a registry change) and how it's verified.
- **Acceptance criteria** — unambiguous, testable.
- **Scope & non-goals** — explicit blast-radius bound (this repo values minimal blast radius).
- **Grounding references** — the seams/decisions/prior-art it builds on.
- **Recommended executor profile** — `model` (default Sonnet 5; justify anything higher), `effort`, `backend` (`inline` / `team-execution` / `cc-workflows-ultracode`), and **external-LLM posture** (`none` / `offload` / `second-opinion`, per `ENGINE_INTENTS`).
- **Release-surface checklist** where relevant (this repo requires plugin.json / marketplace.json / CHANGELOG / version-drift tests to move together — see repo CLAUDE.md step 6).
- **Tier tag** — quick-win / structural / moonshot.
- **Type** — mission-control taxonomy: `capability` / `enhancement` / `defect` (Hermes-actionable) or `objective` / `exploration` / `context-update` (non-actionable; an `exploration`'s deliverable is a decision/recommendation doc).

An issue that can't state a definition of done is not admissible as actionable work — reframe it as an `exploration` with a document deliverable, or cut it.

---

## 7. Required Socratic intake topics (§ Phase A) — ask each with a recommendation attached

These are the operator's stated tensions. Interrogate each, resolve it, record it in the Intake Brief. Provide a recommendation and name the lever every time.

1. **Time vs money (cache economics).** Does the operator want decomposition tuned to **maximize prompt-cache reads / minimize cache writes** (cheaper, more serial) or **maximize throughput** (faster, more parallel, more cache churn)? Explain the tradeoff; recommend per their appetite. This choice should also become a *recurring operator question* the resulting issues design into the plugins.
2. **External-LLM purpose, per lifecycle stage.** For each stage in play (`/ideate`, `/brainstorm`, `/plan`, `/work`, `/doc-review`, `/code-review`): is an external LLM (codex/agy/other) wanted as **`offload`** (take token load off Claude) or **`second-opinion`** (burn more to be more thorough/adversarial, reconciled by Claude)? Note the seam already exists (`ENGINE_INTENTS`) but isn't surfaced at these points.
3. **Autonomy posture through the lifecycle.** How autonomous should the eventual `/outcome`-style loop be, and which steps (`/ideate` / `/strategy` / `/plan` / `/qa` / `/code-review`) belong in it — derived from the prompt/issue, with your recommendation. (Today `/outcome` fixes this; the operator wants it interrogated.)
4. **Fable-5 spend levers.** Wherever the plan would put Fable-5-tier work, give an explicit recommendation + a cheaper fallback ("Fable 5, worth it, because …" vs "Opus 4.8 is sufficient here"). The operator wants the lever, not a default.
5. **Provider reach.** Beyond codex/agy — does the operator want routing to Ollama / DeepSeek / other API-key providers considered as a theme? One plugin or several skills? Recommend based on the task surface.
6. **Should this session dogfood an external LLM** as a `second-opinion` adversarial-novelty agent in Phase D? Recommend yes if the operator wants to pressure-test the seam live.

---

## 8. Guardrails

- **Never cross a GATE without explicit operator approval.** Gates A, C, E, F are hard stops.
- **Do not build or modify plugin code.** You produce issues and review docs only.
- **Do not create GitHub issues before Gate F approval.** Materialization is Phase G, delegated, mechanical.
- **Do not over-converge.** Comprehensive is the goal; the only filter is the §5 quality gate.
- **Do not apply `objective:*` / `initiative:*` colon labels** — Initiative and Objective are project *fields* (`flow set-field`).
- **Verify before asserting** any claim about current plugin behavior; the §9 facts are a starting map to re-confirm, not gospel.
- **Spend down-tier by default;** justify every Fable-tier agent line in the Gate C table.

---

## 9. Verified starting facts about the fleet (mapped 2026-07-03; re-verify anything you build on)

These were confirmed by a read of the repo. They are your grounding seed — cite and re-verify, don't trust blindly.

**Backend selection.** Saga backends are the frozen enum `("cc-workflows-ultracode", "team-execution", "inline")` (`plugins/saga/scripts/lifecycle_state.py:216`). Selection logic: `recommend_execution_backend()` (`lifecycle_state.py:99-217`); operator is offered the pick in `/work` Phase 1.4 (`plugins/saga/skills/work/SKILL.md:169-204`). `/loop` deliberately does **not** offer a backend when routing (`loop/SKILL.md:218-222`). `/outcome` dispatches each leaf to its own backend, with a broader documented per-leaf set (`outcome/SKILL.md:84-86`).

**External-LLM seam (your two tensions are already code).** `ENGINE_INTENTS = ("offload", "second-opinion")` (`plugins/saga/scripts/execution_spec.py:65-68`): `offload`→`sonnet/medium` chaperone; `second-opinion`→`opus/high` (`fable/xhigh` per-unit override only) — driven in `/plan` (`plan/SKILL.md:303-304`). Engines are registry-driven, not hardcoded: `engine_resolver.py:22-36` (`ENGINE_CLI={"agy":"agy","codex":"codex"}`), variants from `engine_registry.py`. `agy` lives in-repo (`plugins/agy/`, agents `agy-coder`/`agy-reviewer`, both `model: sonnet`, Bash-only bridge); `codex` is installed from another marketplace (not in this repo). **Gap:** the offload/second-opinion offer is **not surfaced** in `/ideate`, `/brainstorm`, `/work`'s interactive flow, or team-execution operator choice — only wired in `/plan`'s ExecutionSpec.

**Model/effort staleness = tier-palette lag (not obsolete IDs).** No versioned model IDs anywhere; everything uses bare aliases (`opus`/`sonnet`/`haiku`) that auto-resolve. **But** the `fable` tier + `xhigh` effort exist **only** inside saga's ExecutionSpec vocabulary (`execution_spec.py:52-53` `MODELS=("fable","opus","sonnet","haiku")`, `EFFORTS=("low","medium","high","xhigh")`). Everywhere else is stuck on the 3-name opus/sonnet/haiku palette and cannot reach fable/xhigh: team-execution's worker table (`team-execution/SKILL.md:228-229`) + all ~33 reviewer/tester/scanner agents (frontmatter `model:` only), the `agy` agents, and the single-agent `deploy`/`unifi`/`mission-control`/`home-lab-ops` plugins.

**team-execution — effort is not modeled + no teardown.** Reviewers/validators pin `model:` in frontmatter (reviewers=opus, testers=sonnet, scanners/monitors=haiku) and carry **no effort field at all**; `.team-execution.json` exposes no model/effort key. Effort exists only as a **worker** plan-time `Tier` concept, never wired to reviewers/validators — so the operator's "why can't I pick effort?" is a real, confirmed gap. Consensus = unanimous-threshold (all confirmed reviewers ≥9.0, no applicable dimension <7.0, security/auth <5.0 is a hard block), max 3 iterations (`consensus-protocol.md`). Worker reuse **does** exist (R3 persistent resident workers reused via `SendMessage`; R11 context-shedding at the ~5-min cache TTL). **No team teardown exists anywhere** — Step B7 only reports results; confirmed gap. Consensus is **coupled** to team-execute; cc-workflows re-implement a lighter advisory panel (saga's own `iterate_to_consensus` in `references/execution-spec.md:55-65`) — not a shared primitive.

**`/outcome` — autonomy is fixed, not asked; can't ingest a parent+sub-issues.** Coordinator over a derived-on-read DAG of leaf sagas; autonomy is a single `advance --autonomous` flag with a hard-coded reversibility-gated allowlist (set Status→In Progress, close/reopen leaf sub-issue, labels, one progress comment), never a dialog; per-leaf lifecycle steps derived from node `kind`, not selected. `start <objective>` takes free text → a minimal 2-node starter DAG; real decomposition is deferred to `/plan`'s decompose flow. **No code path ingests a pre-existing parent Objective + sub-issues**, and no unstructured→structured refinement lives inside `/outcome`.

**mission-control issue surface.** 6-type taxonomy confirmed: `capability`/`enhancement`/`defect` (Hermes-actionable: `hermes-task`+`needs-plan`+type) vs `objective`/`exploration`/`context-update` (`hermes-not-actionable`). Creation: `/issue prepare --from <path|URL|branch|search>` → draft under `docs/sdlc-issue-drafts/` → `issue create-prepared` (readiness check, mutation-plan preview, confirm, create). Objective umbrella pattern exists: Initiative→Objective→work-item, Initiative/Objective as **project fields** (`flow set-field`), native sub-issue links (`flow link-sub-issue`, idempotent, cross-repo OK), optional milestone rollup (`milestones`).

**Learning-mining prior art.** `/promote` scans **all** workspace repos' journals (`promote_scan.py --workspace-root ~/workspace/infiquetra`) for `**Transcendent.**`/generalizable markers → upserts distilled rules to `infiquetra-context-library` behind a gate. `/retro` mines **this repo's/this thread's** sessions (`discover_sessions.py` + `extract_session_skeleton.py`, file-mediated, context-safe). **Gap:** nothing joins *all repos' raw sessions* into one pattern-mining pass — that's the cross-repo session-mining grounding technique to reuse (and a candidate outcome-generating issue only if it survives §5).

**`/ideate` grounding gate (why we borrow, not call).** Phase 0.2 will refuse an unframed whole-repo pass — the literal rejected example is `"improvements in infiquetra-claude-plugins"` → routed to `/office-hours`. Hence: borrow the frame×axis engine + basis contract, run per pre-scoped theme, drop the 5–7 survivor cap.

---

## Appendix — operator's raw notes (verbatim seed material; represent faithfully AND transcend)

> We want to be able to use codex and agy in the process of a team and in dynamic workflows.
>
> We need to include the stuff around auto updating through the lifecycle. I shouldn't have to update status or close issues.
>
> We need to update how to better re-use workers, such that we mostly use one worker to write code, then others to do the reviews, etc… Similarly dynamic workflows should decompose in a way to either maximize cache usage and minimize cache writes or maximize throughput. That's the driving force for both of these, and probably needs to be a question asked of the operator. Which tension is most important. Time or money. Operator will need explanation and recommendations.
>
> When using outcome, we should ask questions around how to move through the lifecycle. How autonomous? What steps? (i.e. /ideate? /strategy? /plan? /qa? /code-review?), recommendations should be provided based on the given prompt or issue. The idea behind /outcome was to basically create a large loop with multiple goals. Where the outcome can be derived from a well structured input. Like a parent issue that has sub issues, but also take small unstructured and turn it into something better. I just think questions need to be asked to fully understand the operator's intent.
>
> We need to update for sonnet 5 and fable 5 integration. A lot of plugins that make decisions about model/effort do not have those in their declining logic. Given the expense of fable 5, it probably needs some more operator involvement. Like: "My recommendation is Fable 5, but opus 4.8 will work" or "fable 5, it's worth the money". I don't know really and don't take that verbatim. Just the operator needs a lever.
>
> I want external LLM base agents like agy, codex, any new ones added, to be something that is always asked about or even recommended when choosing a backend. Even if that backend is just inline. So if I do any of the saga lifecycle activities, there is a sensible option to incorporate the use of an external LLM and a suggested model/effort. There are always at least two constraints or tension. Is the external LLM to offload token usage from the main LLM (claude) or is it to be "another set of eyes" that would get evaluated and incorporated based on the analysis of the main LLM (claude). Some examples: /ideate - ask the operator if they want to use an external and which one as some of the sub agents or if they want it run in both claude and use an external then the two outputs reconciled? Where one question is about offloading some token usage and the other is about burning more tokens to get a more thorough ideation. It can be assumed that there is a saga plugin that use an external is aware of. /brainstorm - similar questions. Similar reasons. Similar assumptions. /plan - similar questions. Similar reasons. Similar assumptions. 1 difference might be that an external could be used to do some of the subagent work that often comes up in creating plans. Also the backend execution: inline/agent team/cc-workflows. we already covered and Should provide the operator with recommendations on how it's used. /work - here work should follow what is defined in the plan about external LLM's, if work wants to break up the plan into smaller tasks, operator should be asked if external should be used and give recommendations on how. Again we are generally focused on two ideas: offload token usage to external or use both to be more thorough/comprehensive/adversarial. /doc-review and /code-review - here the question is also similar. Offload the review to external or use external as a second opinion.
>
> I think I want a plugin that has the ability to be used as an external in workflows or agent teams use but work with llms like codex and agy but are not gpt or gemini. They should do it efficiently. Two dimensions remain: 1. Reduce token usage on claude 2. Increase consensus outcome with second/third option. I also want the ability to route to other models/providers as well. Like my Ollama subscription or my deepseek v4 api call. Maybe there's a plugin to be used that can route via api key. Maybe it's multiple plugins, maybe it's one with multiple skills. I want recommendations based on the task at hand.
>
> I want to be asked about the external agent provider/models for an agent team or a workflow or even inline. I want to be able to pick the effort level when using team-execution agents, why can't I? Is there a way around this. This almost makes me want to lean more into dynamic workflows.
>
> I want the ability to have the same consensus protocol used in agent teams of team-execution to also work in dynamic workflows.
>
> I want any plugin that uses agents or subagent to try and group activity together in the same worker to maximize cache reads and minimize cache writes.
>
> When working things inline or working an outcome or a plan. Asking if you want built in pause points to adjust context and model.
>
> We need agent teams to be shut down once the team is no longer needed.
>
> I want the ability to use other external models besides just codex and agy.
>
> How can the plugins be sure to enforce the various ADR's, technical standards, etc. Is this something in Mission Control that always adds into issues? Is this somewhere else? Always a part of doc-review/code-review.
>
> I think a comprehensive review of all my claude/codex session in each of the local working repositories should be scanned for any plugins, improvements, etc. There must be patterns in there that would help improve. There might even be stuff in the engineering journals.
>
> I think we need a full and comprehensive code-review. I think all the agents defined in any plugin, should be reviewed for improvement.

---

*End of prompt. Launch on Fable 5 / xhigh, in this repo, and begin at Phase A.*
