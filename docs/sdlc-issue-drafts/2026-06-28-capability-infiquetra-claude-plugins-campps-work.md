---
title: "capability: external-engine capability routing — right engine, effort, and protocol per task"
repo: infiquetra-claude-plugins
type: capability
team: campps
project: operations
status: Idea
labels: capability, hermes-task, needs-plan
risk: medium
handoff_maturity: requirements-ready
---

# capability: external-engine capability routing — right engine, effort, and protocol per task

### Objective

Board objective: **improve-claude-plugins**. S-4 of the VECU port-seeds campaign (tier ④, the last
core survivor). Turn saga's hand-run use of external engines (Codex/gpt-5.5, Gemini 3.1 Pro,
Gemini 3.5 Flash) into a reusable, capability-aware routing layer: a registry + resolver that picks
the right engine, effort, and prompting protocol for a task across inline, cc-workflows, and
team-execution — with Claude always the verifier-of-record.

### Intent

Build three layers: (1) a capability **registry** — per engine-variant capability-profile +
prompting-protocol + invocation-recipe, capability-keyed, dated, and editable; (2) a **resolver** that
maps a logical capability (or an explicitly-named engine) to `{engine, effort, protocol}` in both
advisory and autonomous-dispatch modes; (3) **wrapper-subagent dispatch** across all three backends
that forwards a system-assembled literal payload to the engine verbatim. Enforce the trust boundaries
(external engines never hold a gated verdict; gated consensus stays in team-execution), an evidence-only
safety default, fallback provenance, and context-window fitness. Bake in the proven doc-review
external-reviewer panel as a first-class composing role.

### Out-of-scope / non-goals

- The registry file format/home and schema/field names — `/plan` decides (new `delegate-agents` plugin
  vs. saga-shared config vs. standalone data file).
- The exact logical-capability taxonomy (fixed vocabulary vs. free-form keys) — `/plan`.
- The team-execution external-wrapper context-package contract shape — a `/plan` prerequisite.
- Parallel/fan-out cost and quorum sizing — owned by ideation R7 (fan-out rubric) + S-1 (#275).
- The verified-vs-parroted provenance manifest — owned by ideation R11.
- The read-only sandbox profile itself — owned by ideation R14 (R23 here only *gates* mutation on it).
- No automated measurement / ROI / scoring loop — this is a single-operator dogfood tool.

### Files expected to change

Expected areas (exact set resolved at `/plan`):

- `plugins/saga/` — the registry + resolver + dispatch wiring (home TBD at `/plan`).
- `plugins/saga/references/execution-spec.md` — extend the per-unit `tier` model vocabulary.
- `plugins/saga/scripts/lifecycle_state.py` — resolver seam above `recommend_execution_backend()`.
- `plugins/team-execution/` — the external-wrapper context-package slot (prerequisite contract).
- `tests/test_external_engine_routing.py` — **new**, at repo root (CI-collected).
- Release surfaces: `plugins/saga/.claude-plugin/plugin.json`, `.claude-plugin/marketplace.json`,
  `plugins/saga/CHANGELOG.md`.

### Tests to add or update

Seam + behavior tests, repo-root `tests/` (CI-collected), not `plugins/<plugin>/tests/`:

- resolver maps a capability → `{engine, effort, protocol}`; an explicit engine → its default-variant
  effort+protocol;
- the prompting protocol reaches the engine payload verbatim (not paraphrased by the wrapper);
- a worker-role fallback to Claude emits a provenance note (not silent);
- an explicitly-named unavailable engine halts; an unavailable cross-family second-opinion halts (no
  Claude substitution);
- a context package over the variant's window is not silently truncated;
- an external worker with no sandbox returns evidence, not edits.

### Context library links

- source_context: docs/brainstorms/2026-06-27-external-engine-capability-routing-requirements.md
- doc-review: docs/reviews/2026-06-27-external-engine-capability-routing-readiness.md
- survivor: docs/ideation/2026-06-26-vecu-port-seeds-ideation.md (S-4, lines ~188–211; verdict :377)
- prior art: docs/ideation/2026-05-30-delegate-agent-plugin-ideation.md

### Acceptance criteria

- [ ] `uv run pytest tests/test_external_engine_routing.py` is green (resolver, dispatch, fallback,
  halt, fitness, safety).
- [ ] `test_resolve_capability_returns_engine_effort_protocol` passes — a capability such as
  `cross-family-second-opinion` resolves to a concrete `{engine, effort, protocol}` from the registry.
- [ ] `test_protocol_forwarded_verbatim` passes — the resolved protocol appears unmodified in the
  engine invocation payload.
- [ ] `test_worker_fallback_emits_provenance` and `test_explicit_unavailable_halts` pass — fallback is
  recorded (not silent) and an explicitly-named unavailable engine halts.
- [ ] `uv run ruff check . && uv run ruff format --check . && uv run mypy plugins/ && uv run bandit -r plugins/`
  is clean.

### Verification

```bash
uv run pytest tests/test_external_engine_routing.py -v   # resolver, dispatch, fallback, halt, fitness, safety
uv run pytest                                             # full suite
uv run ruff check . && uv run ruff format --check .
uv run mypy plugins/ && uv run bandit -r plugins/
```

Manual: request a capability (inline or via `/work`) and confirm the resolver dispatches the expected
engine with its protocol applied; confirm an explicitly-named unavailable engine halts rather than
falling back to Claude.

## Summary

Give saga a capability-aware way to use external LLM engines (Codex/gpt-5.5, Gemini 3.1 Pro,
Gemini 3.5 Flash) as gated generators, advisory reviewers, and non-gated workers — selecting the
right engine, effort level, and prompting discipline for a task, across all three execution
backends, with Claude always the verifier-of-record.

## Problem Frame

Saga already reaches for external engines by hand — the doc-review pipeline runs Codex and Gemini as
adversarial reviewers, and at least one campaign synthesized a plan from three independently-generated
drafts (Claude + Codex gpt-5.5 + Gemini Pro) under trust-but-verify discipline. The value is proven.
What is missing is any reusable machinery: every invocation is operator-authored, the choice of which
engine for which task lives in the operator's head, and the hard-won prompting discipline each engine
needs (Gemini's anti-sycophancy framing, Codex's read-only + tools posture) is re-applied from memory
each time or forgotten.

This matters because the engines have genuinely non-overlapping strengths — the strongest
cross-source finding is that a *different model family* is the best practical mitigation for
single-model blind spots and sycophancy. Capturing "which engine, at what effort, prompted how" as
data the engine and operator can both consult turns a manual practice into a capability.

It also matters that the answer drifts. Model rankings shift every few months; this brainstorm's own
starting assumption ("Gemini Pro is the writing engine") was already wrong by the time it was checked.
So the design has to absorb churn rather than freeze a snapshot.

## Key Decisions

**Route on logical capability, not model name.** Work requests target a capability
(`long-context-digest`, `cross-family-second-opinion`, `agentic-coding`, `iac-terminal`) and the
registry resolves it to a concrete engine+effort+protocol. Naming `gemini-pro` directly in a unit rots
the moment rankings shift; naming a capability does not. This also unifies "operator requests an
engine" and "plugin picks an engine" into one resolution path.

**Prompting protocol is executable, not documentation.** Each engine's required invocation discipline
is assembled by the system into the engine's own invocation payload at dispatch. The research is blunt
that *how* you invoke an engine is as load-bearing as *which* one — Gemini's persistent over-eagerness
and sycophancy are mitigated by structural framing and explicit stop conditions, not goodwill.
Dispatching an engine without its protocol is a known failure mode the registry exists to prevent.

**External engines are never gatekeepers.** Claude holds every gated verdict; gated consensus stays in
team-execution. This capability *establishes* that rule as a new binding decision — it is supported by,
but not already decided in, the repo: the parroting finding (`DECISIONS.md:276-290`, where Antigravity
parroted while Claude and Codex independently verified) is the *evidence*, and the gated-vs-advisory
consensus split (`operator-choice.md:81-95`, gated consensus is team-execution only) is the *mechanism*
it rides on. `/plan` should record the decision as a real `DECISIONS.md` entry when the capability lands.

**Build the whole thing; iterate by using it.** This is a single-operator tool. There is no MVP-slice
or proving phase — the feedback loop is the operator using it and adjusting, surfaced through `/retro`,
not an automated measurement or ROI gate.

## Requirements

What must be true of the capability, grouped by concern. IDs are stable and continuous.

**Capability registry**

R1. The system maintains a registry with one entry per external engine *variant*, where a variant is
an engine at a specific effort/thinking level when that level materially changes its behavior (e.g.
gpt-5.5 at `high` vs `xhigh`). The registry also defines a **default variant per engine** (so an
engine-only request resolves an effort) and **named roles/panels that compose multiple variants** — the
reviewer panel is a composing role referencing several engine entries, not a single entry.

R2. Each entry carries three kinds of content: a **capability profile** (strengths/weaknesses keyed to
logical capabilities), a **prompting protocol** (the invocation discipline needed to get good output),
and an **invocation recipe** (the concrete command plus effort/sandbox knobs).

R3. Each entry is stamped with the model identity it describes and the date its capability data was
last validated, so staleness is visible at a glance.

R4. The registry is editable data, not code: changing a ranking, protocol, or recipe is a data edit
that requires no change to resolution logic.

**Capability resolution**

R5. A work request targets a logical capability rather than a model name; the resolver maps the
capability to a concrete `{engine, effort, protocol}` from the registry.

R6. A request may instead name an explicit engine; the resolver then supplies the appropriate
`{effort, protocol}` for that engine, using the task/role context carried with the request — or the
engine's default variant (R1) when no capability or task context is supplied.

R7. Resolution operates in two modes: **advisory** (recommend an engine+effort+protocol for the
operator or caller to act on) and **dispatch** (select and invoke autonomously).

R8. When no external engine is a good fit for a requested capability in a worker or generator role,
resolution falls back to Claude (the always-available default) rather than forcing a poor match. The
fallback is recorded, not silent (R24).

**Dispatch across backends**

R9. External engines are dispatched by wrapping the external call inside an ordinary subagent — no
backend needs native support for a foreign agent type. The wrapper forwards a **system-assembled literal
payload** (resolved protocol + context) to the engine *verbatim*; it does not re-author or paraphrase
the protocol, and it does not hand-assemble shell commands by interpolating arbitrary context — that
class of escaping/drift failure is exactly what the literal payload prevents.

R10. Dispatch is available from all three execution backends: inline (main session), cc-workflows, and
team-execution. (team-execution requires the wrapper contract named in Dependencies.)

R11. At dispatch, the resolved prompting protocol is applied to the **engine's own invocation payload**
(not merely the wrapper Claude's instructions), so the engine's required discipline (adversarial role,
stop conditions, context management) reaches the engine verbatim and is never left to the caller to
remember or to the wrapper to rephrase.

R12. In team-execution, an external engine participates only within the worker/validator context
contract: it receives the curated context package and returns evidence like any other worker. That
context-package slot for an external-engine wrapper does not exist today and is a prerequisite to
define (Dependencies).

**Trust and role boundaries**

R13. Claude is the verifier-of-record for every gated decision; an external engine never holds a gated
verdict that blocks merge/deploy or persists as the gate.

R14. External engines may occupy generator, advisory-reviewer, and non-gated worker roles only.

R15. Gated consensus remains a team-execution capability; an external engine may join a consensus role
only when that consensus is advisory (non-gated).

R16. The doc-review external-reviewer pattern — multiple different-family reviewers whose output Claude
verifies against source — is a first-class, reusable role in the registry, not a one-off. It is modeled
as a composing role (R1) referencing multiple engine variants, each invoked with its own protocol.

R17. When an engine selected for the **cross-family second-opinion** role is unavailable, the system
halts and surfaces it to the operator rather than silently substituting Claude (Claude reviewing
Claude defeats the purpose). For plain worker/generator roles, falling back to Claude is acceptable
(recorded per R24).

**Operator surface**

R18. The operator can request external-engine usage by capability ("use an external engine for this"),
and the system selects the engine+effort+protocol for the task.

R19. The operator can name a specific engine, and the system applies the right effort+protocol for
that engine and task.

R20. The operator can see and override the resolver's choice. Override is a **pre-dispatch / advisory**
control; in autonomous dispatch (non-interactive backends) the resolver acts on the operator's standing
registry configuration — itself the operator's authored choice — and surfaces its selection for
post-hoc correction rather than blocking to wait for an override.

**Durability and maintenance**

R21. Capability data is treated as seed values that drift; the maintenance loop is operator
re-validation prompted by ordinary use and `/retro` — not an automated measurement or scoring system.

R22. When an entry's last-validated date predates a known model revision, the system may surface that
staleness to the operator; it does not auto-update the data.

**Safety, provenance, and fitness**

R23. External engines run **non-mutating / evidence-only by default**; file-mutating work requires the
read-only-sandbox / worktree-ownership profile (ideation R14) to be present. Until that profile exists,
external workers return evidence, not edits.

R24. Any fallback to Claude, or any substitution away from the requested engine, emits a **visible
provenance/downgrade note** (in the result, the saga tick, and the report) — mirroring the existing
`orchestration_downgrade` pattern (`execution-spec.md:136-138`). Degradation is recorded, never silent.

R25. The resolver accounts for the selected variant's **context-window limit** (e.g. Codex-CLI's 400K).
A context package that would exceed the variant's window must not be silently truncated — the resolver
reduces, re-routes, or halts.

R26. An **explicitly operator-named** engine that is unavailable **halts** and surfaces to the operator
— no silent substitution. (Distinct from R8: R8's Claude fallback applies only when the *resolver* chose
the engine for a worker/generator capability, not when the operator named one.)

## Key Flows

F1. **Capability-keyed dispatch.** **Trigger:** a unit or role requests a logical capability.
The resolver looks it up in the registry, returns `{engine, effort, protocol}`, assembles the literal
payload, wraps the call in a subagent that forwards it verbatim, the engine runs, and the result returns
to Claude for verification before it feeds any gate. **Covers R5, R7, R9, R11, R13.**

F2. **Explicit engine request.** **Trigger:** the operator names an engine ("use Codex for this").
The resolver supplies the effort+protocol for that engine and task, dispatches, and returns the
result; if the named engine is unavailable the run halts (R26). **Covers R6, R19, R26.**

F3. **Doc-review reviewer panel.** **Trigger:** a readiness/code review needs adversarial depth.
Multiple different-family engines are dispatched as advisory reviewers, each with its own protocol;
Claude verifies every finding against source before adoption; the gated verdict remains Claude's.
**Covers R14, R15, R16.**

F4. **Unavailable second-opinion engine.** **Trigger:** a cross-family second-opinion is requested but
the selected engine is unavailable. The run halts and tells the operator instead of falling back to
Claude. **Covers R17.**

## Acceptance Examples

AE1. **Covers R17.** When the registry selects Gemini for a cross-family second-opinion and `agy` is
unavailable (not installed, unauthenticated, or rate-limited), the run halts and surfaces it to the
operator — it does not substitute Claude.

AE2. **Covers R8, R24.** When a unit requests `agentic-coding` in a plain worker role and no external
engine is available, the work proceeds on Claude without interrupting the operator — and the result and
saga tick carry a one-line note that the external capability did not run and why.

AE3. **Covers R13, R15.** When an external engine produces a review finding inside a gated context, the
finding is advisory input only; the gated verdict is still issued by Claude / team-execution.

AE4. **Covers R11.** When Gemini 3.5 Flash is dispatched as an autonomous worker, its protocol —
explicit stop conditions and "do not enrich beyond the ask" — is part of the engine payload
automatically, without the caller adding it.

AE5. **Covers R9, R11.** When Gemini is dispatched, its anti-sycophancy protocol is assembled by the
system into the literal payload sent to `agy` verbatim; the wrapper subagent does not paraphrase,
re-order, or summarize it.

AE6. **Covers R26.** When the operator names Codex explicitly and `codex` is unavailable, the run halts
and says so — it does not fall back to Claude or to Gemini.

AE7. **Covers R23.** When an external worker is asked to change files but the read-only-sandbox /
worktree-ownership profile (ideation R14) is not present, it returns the proposed change as evidence
rather than editing the tree.

## Seed Capability Data

The starting registry content, to be loaded as dated seed and re-validated by use. This is current
(2026) evidence from benchmark and practitioner research, tagged by corroboration strength; it is
explicitly *not* a permanent ranking. The architecture does not depend on any cell being eternally
correct — that is what R3/R4/R21 are for.

| Engine (variant) | Strong for | Weak for / caution | Cost·speed |
|---|---|---|---|
| **Codex / gpt-5.5** (`high`→`xhigh`) | top composite reasoning [STRONG]; multi-file refactor, tool-orchestrated debugging, structured-output fidelity [MODERATE]; DevOps / IaC / terminal [MODERATE] | greenfield architecture; pure-chat debugging without tools; creative writing; niche languages [MODERATE]. **Codex-CLI context is 400K, not 1M.** Second-opinion/refuter behavior **unmapped** | most expensive; slowest; `xhigh` ≈ +2–5pp over `high` at 4–5× token cost |
| **Gemini 3.1 Pro** (`High`) | long-context digestion + retrieval [STRONG]; science/abstract reasoning [STRONG]; multimodal; cheap bulk document processing [STRONG]; algorithmic coding [MODERATE] | agentic multi-step execution; ambiguous specs (commits confidently to wrong reading); backend concurrency; run-to-run consistency; **expert long-form writing → route to Claude** [MODERATE] | mid cost; mid speed |
| **Gemini 3.5 Flash** (`High`) | agentic / tool-use (best absolute) [STRONG]; fastest + cheapest [STRONG]; one-shot coding, greenfield scaffolding, structured output [MODERATE] | long-horizon agentic tasks; ignores completion criteria / over-enriches; iterative repair (adds rather than fixes); no image/audio gen [STRONG] | cheapest; fastest |

Prompting-protocol seeds (the R2 third field):

- **Gemini (both):** assign an explicit adversarial/critic role; put behavioral constraints at the top;
  avoid vague blanket negatives ("don't infer" breaks reasoning); terse, command-style prompts ("please"
  is treated as fluff); keep temperature at default; set thinking to `High` for hard tasks; give explicit
  stop conditions to counter over-eagerness.
- **Codex / gpt-5.5:** run read-only when generating against a repo; give it tools to iterate when
  debugging (quality drops in pure-chat mode); manage context actively (it does not self-manage); reserve
  `xhigh` for the hardest tasks given the cost multiplier.

Cross-engine findings that shape routing: a different model family is the best sycophancy mitigation
[STRONG]; no frontier model is meaningfully less sycophantic, so human approval stays regardless
[STRONG]; benchmark deltas under ~2% are noise [STRONG]; Gemini over-eagerness is a recurring family
failure mode [STRONG].

**Seeding requirement:** before this data seeds the registry, each row must carry per-claim source
attribution — source URL, date, OFFICIAL/INDEPENDENT tag, and corroboration strength — not just the
broad `[STRONG]`/`[MODERATE]` tags shown here. The full benchmark and practitioner source lists were
captured in this capability's doc-review research and are recorded in the review artifact under
`docs/reviews/`.

## Scope Boundaries

**In scope:** the registry (profile + protocol + recipe, capability-keyed, dated, editable, with
default-variant and composing-role/panel definitions); the resolver (advisory + dispatch); literal-payload
wrapper-subagent dispatch across inline, cc-workflows, and team-execution; automatic protocol
application; the doc-review reviewer role; external-as-general-worker (evidence-only by default, R23);
the operator request/override surface; fallback provenance (R24); context-window fitness (R25); the
seeded capability data.

**Deferred to `/plan` (the HOW):** the registry's file format and home (a new `delegate-agents` plugin,
saga-shared config, or a standalone data file); schema and field names; how the resolver hooks the
existing per-unit `tier` vocabulary and `recommend_execution_backend()` seam; the exact logical-capability
taxonomy (fixed vocabulary vs free-form); the team-execution external-wrapper context-package contract.

**Owned by sibling survivors, referenced not built here:** parallel/fan-out cost and quorum sizing →
ideation **R7** (cc-workflows fan-out rubric) + **S-1** (#275, cache scheduling); verified-vs-parroted
audit trail → ideation **R11** (provenance manifests); read-only sandbox profile for external agents →
ideation **R14** (capability-scoped sandboxing). Note R23 makes external-worker mutation *depend on*
the ideation-R14 sandbox: until that ships, external workers stay evidence-only.

## Dependencies / Assumptions

- **External (not in-repo) engine substrate** — the engines are reached through the `codex` CLI
  (`/opt/homebrew/bin/codex`) and the `agy` CLI (`~/.local/bin/agy`), plus separately-installed Claude
  Code plugins (`codex:codex-rescue` agent + `codex:*` skills; `agy:runner` agent + `agy:*` skills) from
  a *different* marketplace. This repo's `.claude-plugin/marketplace.json` registers only the seven
  infiquetra plugins — codex/agy are **not** owned here. The registry sits above this external substrate
  and consumes it; it must **preflight-check availability** (feeds R24/R26) rather than assume it. The
  `delegate-agents` ideation (`docs/ideation/2026-05-30-delegate-agent-plugin-ideation.md`) proposed a
  delegation plugin; whether S-4 consumes the existing CLIs/plugins directly or builds a thin delegation
  layer is a `/plan` decision.
- **Existing routing machinery (verified)** — the per-unit `tier: {model, effort}` vocabulary
  (`execution-spec.md:29`; closed vocab `opus|sonnet|haiku × low|medium|high` at `:97`;
  orchestration-only recompile at `:115-118`) and the `recommend_execution_backend()` work-shape router
  with the `consensus_is_gated` split (`lifecycle_state.py:164-189`). S-4 extends the model vocabulary
  and adds the capability layer above this seam.
- **Supporting evidence (verified), not a standing decision:** the parroting finding
  (`DECISIONS.md:276-290` — Antigravity parroted; Claude and Codex independently verified) is *evidence*
  for, not an existing decision of, the never-gatekeeper rule — this capability establishes that decision
  (see Key Decisions). The gated-vs-advisory consensus split (gated consensus is team-execution only) is
  real and verified (`operator-choice.md:81-95`; `lifecycle_state.py:164-189`).
- **team-execution external-wrapper contract is a prerequisite, not an existing affordance.** Inline and
  cc-workflows dispatch are feasible (wrapper subagents shell out). team-execution's current worker
  contract is `## Team Structure` rows reading plan/reference files; there is no existing context-package
  slot for an external-engine wrapper. Defining that slot/contract is a **prerequisite** for R10/R12
  team-execution dispatch and is `/plan` work.
- **Assumption — capability data is seed and drifts;** no measurement loop (R21).
- **Assumption — GPT-5.5 refuter/second-opinion behavior is unmapped;** its value in the cross-family
  second-opinion role is unproven until the operator exercises it.

## Outstanding Questions

None block planning — "build it all" is settled and the role/trust rules are fixed (this doc establishes
the never-gatekeeper decision; `/plan` records it). The following are deferred to `/plan`:

- Registry home and packaging: new `delegate-agents` plugin vs. saga-shared config vs. standalone data
  file; whether to consume the codex/agy CLIs/plugins directly or via a thin delegation layer.
- Logical-capability taxonomy: a fixed vocabulary vs. free-form keys.
- The team-execution external-engine context-package slot/contract (the R10/R12 prerequisite).
- codex/agy preflight/availability contract (how the system learns an engine is installed / authenticated
  / rate-limited).
- Whether the per-unit `tier.model` vocabulary is literally extended or a parallel `engine` field is added.
- How protocol payload assembly composes with each backend's existing prompt assembly.

## Sources / Research

- **Survivor:** S-4 in `docs/ideation/2026-06-26-vecu-port-seeds-ideation.md` (survivor block lines
  ~188–211; external-panel verdict line 377 — keep the gated-generator-under-source-verification core,
  cut the RAIM voting half).
- **Repo grounding (verified):** `execution-spec.md:29,97,115-118,136-138` (per-unit tier vocabulary,
  orchestration-only recompile, `orchestration_downgrade` provenance pattern); `lifecycle_state.py:164-189`
  (`recommend_execution_backend()` + `consensus_is_gated` split); `DECISIONS.md:276-290` (parroting
  evidence — see Key Decisions for the citation correction); `operator-choice.md:81-95` (gated-vs-advisory
  consensus split); `.claude-plugin/marketplace.json` (the seven infiquetra plugins — codex/agy not among
  them); `docs/ideation/2026-05-30-delegate-agent-plugin-ideation.md` (prior art).
- **Capability research (2026 web, corroboration-tagged):** benchmark and practitioner sweeps across
  coding, reasoning, long-context, writing, agentic tool-use, latency, and cost for the three engines —
  full source lists recorded in `docs/reviews/2026-06-27-external-engine-capability-routing-readiness.md`,
  to be attached per-row at registry seed time. Key correction on record: Gemini Pro is not the
  expert-writing engine — route long-form writing to Claude.

### Handoff maturity
requirements-ready

### Suggested next action
Use `/plan <issue>` to create an implementation plan.

### Source context
- Source: docs/brainstorms/2026-06-27-external-engine-capability-routing-requirements.md
- Source type: brainstorm
- Source title: External-Engine Capability Routing

## Created Issue

- URL: https://github.com/infiquetra/infiquetra-claude-plugins/issues/283
- Number: 283
- Created at: 2026-06-28T04:28:47.789788+00:00

