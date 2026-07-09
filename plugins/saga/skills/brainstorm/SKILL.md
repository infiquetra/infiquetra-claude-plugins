---
name: brainstorm
description: Deep-dive one chosen Infiquetra idea into a right-sized requirements document before planning.
---

# Brainstorm

Brainstorm answers **WHAT to build** for one chosen idea, then writes a right-sized requirements
document. It precedes `/plan`, which answers **HOW to build it**.

Take a single idea — seeded from a `/ideate` survivor handoff, or a topic the operator names directly
— and pressure-test it into a durable requirements doc strong enough that planning never has to invent
product behavior, scope boundaries, or success criteria. This skill does not write implementation
code. It explores, clarifies, and records product decisions.

The engine is **orchestrator-side dialogue**: the steps below run sequentially, in this session, one
question at a time. The only parallel work allowed is the Phase 1 context scan (`Explore` agents).
Resolve product decisions here; defer schemas, endpoints, file layouts, and code-level design to
`/plan` unless the brainstorm is itself about a technical or architectural decision.

Use repo-relative paths in every generated document. Absolute paths break portability across machines
and worktrees.

## Interaction rules

These govern every turn of the dialogue.

1. **One question per turn.** Even when sub-questions feel related, pick the single most useful one
   and ask it. Stacking questions dilutes the answers.
2. **Prefer single-select multiple choice** when choosing one direction, priority, or next step. Use
   `AskUserQuestion` (call `ToolSearch` with `select:AskUserQuestion` first if its schema is not
   loaded). It carries a free-text fallback, so options scaffold without confining.
3. **Use multi-select rarely** — only for compatible sets (goals, constraints, non-goals, success
   criteria that can coexist). If prioritization matters, follow up on which selected item is primary.
4. **Ask open-ended only when the question is genuinely open** — the answer is inherently narrative,
   the question is diagnostic and options would nudge the answer, or you cannot write 3-4 distinct
   plausible options without padding. The rigor probes in Phase 1 are open-ended for exactly this
   reason. Never silently skip the question.
5. **Open-ended questions must be specific.** Name what counts as an answer ("the most concrete thing
   someone's already done about this — paid, built a workaround, quit a tool"). Avoid "what's your
   take?", "briefly", yes/no traps, and warmth wrappers.

In a channel session (`redis-channel` active), do not call `AskUserQuestion`; inline the choices in
your reply text instead ("Which? A) ... B) ... C) ...").

**Gate-divergence telemetry (optional, issue #399).** When a single-select question offers a
recommended or pre-selected option, record the interaction as `gate_id`
`brainstorm-interrogation-choice` per `plugins/saga/references/gate-divergence-instrumentation.md`
on the next `saga.py save` call. Open-ended questions with no offered default have nothing to
record.

## Engine Offer

Before offering an external-engine lane for brainstorming, run
`python3 plugins/saga/scripts/engine_offer.py offer --stage brainstorm --repo-root . --attended`.
If the helper reports `prompt_required`, this skill owns the `AskUserQuestion` or channel-inline
prompt and then persists the selected preference with `engine_offer.py remember`. The offer is
advisory only; it never dispatches, decides scope, or gates requirements.

## Topic

Take the topic from command arguments, a `/ideate` survivor reference (e.g. `dig deeper on #N` or a
survivor title), or the active artifact. If no topic is supplied, ask: "What would you like to dig
into? Name the feature, problem, or `/ideate` survivor." Do not proceed without one.

## Phase 0 — Resume, assess, route

### 0.1 Resume

If the operator references an existing brainstorm topic, or a recent matching
`docs/brainstorms/*-requirements.md` exists, read it and confirm: "Found an existing requirements doc
for [topic]. Continue from this, or start fresh?" If resuming, summarize current state, continue from
its decisions and open questions, and update that file rather than creating a duplicate.

### 0.2 Seed capture

If the topic arrived from a `/ideate` handoff, ingest the survivor using `/ideate`'s SURVIVOR SCHEMA
(defined in `saga/skills/ideate/references/convergence-and-partnership.md`): its
title, description, `axis` (when the ideation run produced an axis list), basis, rationale, downsides,
confidence (0-100), complexity (Low/Med/High), and status. Treat status (`Unexplored` / `Explored`) as
informational only — it records ideation-side state, not a requirement. Treat the basis and rationale
as starting context, not settled requirements — the brainstorm still pressure-tests them. Any schema
field absent from the handoff is treated as unstated, not invented; never fabricate a basis, axis, or
confidence the survivor did not carry.

**Capture provenance.** Record the ideation doc's repo-relative path (e.g.
`docs/ideation/YYYY-MM-DD-<topic>-ideation.md`) and the survivor reference — its title or its `R#` id —
so Phase 3 can populate the `source` field in the requirements-doc metadata. If the handoff did not
name the ideation doc path, ask for it once; if still unavailable, note provenance as unstated rather
than inventing a path.

If the topic is direct (no `/ideate` handoff), treat the operator's opening as the seed and leave
`source` unset — there is no upstream ideation doc to reference.

### 0.3 Need check

Scan for clear-requirements signals: specific acceptance criteria, a referenced pattern to follow,
exact expected behavior, constrained well-defined scope. If requirements are already clear, keep it
brief — confirm understanding and skip the Phase 1 *dialogue probes*. Still run the Phase 1.1
existing-context scan: its verify-before-claiming rule holds even when no dialogue is needed. Then go
to Phase 2.5 — announce mode (Path A) applies only when the scope is **Lightweight**; a richly
pre-loaded Standard/Deep ask still gets Path B's confirmation gate before Phase 3. Do not force a long
brainstorm onto a tight, well-framed ask.

### 0.4 Scope assessment

Classify the work from the seed plus a light repo scan:

- **Lightweight** — small, well-bounded, low ambiguity.
- **Standard** — a normal feature or bounded refactor with real decisions to make.
- **Deep** — cross-cutting, strategic, or highly ambiguous.

If scope is unclear, ask one targeted question to disambiguate, then proceed.

**Deep sub-mode — feature vs product.** For Deep scope, also classify whether the brainstorm must
establish product shape or inherit it:

- **Deep — feature** (default): the existing product shape anchors the decisions. Primary actors,
  core outcome, positioning, and primary flows are already established in the repo or product. The
  brainstorm extends or refines within that shape.
- **Deep — product**: the brainstorm must establish product shape rather than inherit it. Primary
  actors, core outcome, positioning against adjacent products, or primary end-to-end flows are
  materially unresolved. Existing code lowers the odds of product-tier but does not rule it out — a
  half-built tool with ambiguous shape is still product-tier.

Product-tier triggers the extra Phase 1.2 probes and the extra requirements sections noted in the
section contract. Feature-tier uses Deep behavior unchanged.

## Phase 1 — Understand the idea

### 1.1 Existing-context scan (verify before claiming)

Scan the repo before substantive dialogue. Match depth to scope. This scan may run parallel `Explore`
agents; the dialogue that follows is sequential.

**Lightweight** — search for the topic, check whether something similar already exists, move on.

**Standard and Deep** — two passes:

- *Constraint check* — read project instruction files (`AGENTS.md`, `CLAUDE.md`) for workflow,
  product, or scope constraints. Read root `STRATEGY.md` when present — its target problem, wedge,
  persona, non-goals, and active tracks are direct input to scope, success criteria, and which
  approaches are aligned vs out of scope. If they add nothing, move on.
- *Topic scan* — search relevant terms. Read the most relevant existing artifact (brainstorm, plan,
  spec, prior `/ideate` doc) and skim adjacent examples of similar behavior. Check
  `docs/engineering-journal/LEARNINGS.md` and `DECISIONS.md` for prior findings or decisions that bind
  this idea.

Two rules govern the scan:

1. **Verify before claiming.** When the brainstorm touches checkable infrastructure (tables, routes,
   config, dependencies, model definitions, deploy workflows), read the actual source to confirm what
   exists. Any claim that something is *absent* — a missing table, an endpoint that does not exist, a
   dependency not declared — must be verified against the code first. If you did not verify it, label
   it an unverified assumption. This holds for every brainstorm regardless of topic.
2. **Defer design to planning.** Schemas, migration strategy, endpoint structure, deploy topology
   belong in `/plan` — unless the brainstorm is itself about that technical decision, in which case
   those details are the subject and should be explored.

If nothing obvious appears after a short scan, say so and continue.

### 1.2 Product pressure-test (internal)

Before generating approaches, read the operator's opening and note which rigor gaps actually exist.
This is internal analysis, not a user-facing checklist. Raise only the gaps you found, folded into the
Phase 1.3 dialogue — not fired as a pre-flight gauntlet. A fuzzy opening may earn three or four probes;
a concrete, well-framed one may earn zero.

**Lightweight:**
- Is this solving the real problem?
- Are we duplicating something that already covers this?
- Is there a clearly better framing at near-zero extra cost?

**Standard — scan for these gaps:**
- **Evidence gap.** The opening asserts a want or need but points to nothing anyone has already done
  (time spent, money paid, workarounds built) that would make the want observable.
- **Specificity gap.** The beneficiary is described so abstractly you could not design without silently
  inventing who they are and what changes for them.
- **Counterfactual gap.** The opening does not make visible what people do today when this problem
  arises, nor what changes if nothing ships.
- **Attachment gap.** The opening treats a particular solution shape as the thing being built, rather
  than the value that shape delivers, and has not been examined against smaller forms.

Plus two synthesis questions you weigh in your own reasoning (not gap lenses):
- Is there a nearby framing that creates more value without more carrying cost? What complexity does
  it add?
- Given the current state, goal, and constraints, what is the single highest-leverage move now: the
  request as framed, a reframing, one adjacent addition, a simplification, or doing nothing?

**Deep** — Standard, plus: is this a local patch, or does it move the broader system toward where it
wants to be?

**Deep — product** — Deep, plus:
- **Durability gap.** The value proposition rests on a current state of the world that may shift in
  predictable ways within the horizon the operator cares about.
- What adjacent product could we accidentally build instead, and why is that the wrong one?
- What would have to be true in the world for this to fail?

These force an explicit product thesis and feed the Scope Boundaries and Dependencies/Assumptions
sections of the requirements doc.

### 1.3 Collaborative dialogue

Follow the interaction rules above. Be a thinking partner — bring alternatives, challenge assumptions,
explore what-ifs; do not only extract requirements.

- Ask what the operator is already thinking before offering your own ideas. This surfaces hidden
  context and prevents fixation on your framing.
- Start broad (problem, users, value), then narrow (constraints, exclusions, edge cases).
- **Probe only the gaps Phase 1.2 actually found, open-ended, one probe per gap.** Phase 1 cannot end
  with an un-probed rigor gap that is present. Surface the probes progressively across the
  conversation; interleaving with narrowing moves is fine. Examples, one per gap:
  - *evidence* — "What's the most concrete thing someone's already done about this — paid, built a
    workaround, quit a tool over it?"
  - *specificity* — "Can you name a team or person you've actually watched hit this, or are you
    reasoning from the abstract?"
  - *counterfactual* — "What do people do today when this breaks — who picks up the slack?"
  - *attachment* — "Before we look at approaches: what's the smallest version that still proves the
    bet right, and what's excluded?" Fire this last of the rigor probes when the attachment gap is
    present, regardless of whether a specific shape emerged through narrowing.
  - *durability* — "Under the most plausible near-term shifts, how does this bet hold? Push past
    answers every competitor could also make."
  If a probe reveals genuine uncertainty, record it as an explicit assumption in the doc rather than
  skipping it.
- Clarify the problem frame, validate assumptions, ask about success criteria.
- Make requirements concrete enough that planning will not need to invent behavior.
- Surface dependencies or prerequisites only when they materially affect scope.
- Resolve product decisions here; leave implementation choices for `/plan`.

**Before exiting 1.3 — integration check.** Combine what the operator has said and surface any
non-obvious consequence the dialogue has not probed. If stated-X plus stated-Y plus your-default-Z
produces a downstream effect they are unlikely to have tracked through one-question-at-a-time dialogue,
probe it now, open-ended, one probe per genuine combination effect. Phase 2.5 is a safety net for
residuals, not a punt list for consequences you could ask about here.

**Exit condition:** continue until the idea is clear AND no integration-check question is pending, OR
the operator explicitly wants to proceed.

## Phase 2 — Explore approaches

If multiple plausible directions remain, propose **2-3 concrete approaches** grounded in the scan and
the dialogue. Otherwise state the recommended direction directly.

Use **at least one non-obvious angle** — inversion (what if we did the opposite?), constraint removal
(what if X weren't a limit?), or analogy from how another domain solves this. The first approaches
that come to mind are usually variations on the same axis.

**Present approaches first, then evaluate.** Let the operator see all options before hearing which is
recommended — leading with a recommendation anchors the conversation prematurely.

When useful, include one deliberately higher-upside challenger: the adjacent addition or reframing
that would most increase usefulness, compounding value, or durability without disproportionate
carrying cost. Present it alongside the baseline, not as the default. Omit it when the work is already
over-scoped or the baseline request is clearly the right move.

At product tier, alternatives differ on **what** is built (product shape, actor set, positioning), not
**how** it is built. Implementation-variant alternatives belong at feature tier.

For each approach give:
- Brief description (2-3 sentences).
- Pros and cons.
- Key risks or unknowns.
- When it is best suited.

**Granularity: mechanism / product shape, not architecture.** Name mechanism-level distinctions and
product trade-offs (coupling, complexity surface, migration difficulty). Do NOT name column names,
table names, file paths, class names, or JSON shapes — that is `/plan`'s job. Bringing architecture
forward here forces architectural decisions on intentionally-shallow research, and the Phase 2.5
synthesis then has to filter the leak back out.

After presenting all approaches, state your recommendation and explain why. Prefer simpler solutions
when added complexity creates real carrying cost, but do not reject low-cost, high-value polish just
because it is not strictly necessary. If one approach is clearly best and alternatives are not
meaningful, skip the menu and state it directly. When relevant, call out whether the choice is: reuse
an existing pattern, extend an existing capability, or build something net new.

## Phase 2.5 — Scope-confirmation synthesis

Surface a scoping synthesis before Phase 3 writes the doc — the operator's last chance to correct
scope before the artifact lands. Shape it like what two product collaborators confirm before writing a
spec, not like a comprehensive audit. Each bullet must pass two tests: the **affirmability test** (can
the operator evaluate it without reading code?) and the **detail test** (1-2 lines, conversational,
not documentary). Over-share and over-detail are the failure modes.

Two paths, decided by whether any blocking question fired AND the Phase 0.4 tier:

- **Path A — no blocking question fired AND tier is Lightweight:** announce mode. Emit a 1-3 sentence
  "What we're building" prose summary, then proceed to Phase 3 in the same turn. No confirmation
  question; do not wait for acknowledgment. Lightweight docs are short and post-hoc revision is cheap.
- **Path B — at least one blocking question fired, OR tier is Standard / Deep-feature / Deep-product:**
  full scoping synthesis with a confirmation gate. Surface what we're building, what's in scope,
  what's explicitly out, and the open questions; confirm before writing. Confirmation is
  unconditional even when zero call-outs survive — the operator invested answer-time (or pre-loaded
  substantive scope), so the substance earns a real checkpoint.

The tier guard distinguishes a tight one-liner (Lightweight → Path A) from a richly pre-loaded ask
that needs no dialogue only because everything was pre-stated (Standard/Deep → Path B).

## Phase 3 — Capture the requirements

Write or update a requirements document only when the dialogue produced durable decisions worth
preserving. Skip it when the operator needed only brief alignment and the decisions can flow straight
to `/plan` or a commit message without a brainstorm artifact in between.

When a doc is warranted, compose it from the section contract:

Load `saga/skills/brainstorm/references/requirements-sections.md` and follow it.

When the topic arrived from a `/ideate` handoff, populate the metadata `source` field from the
provenance captured in Phase 0.2 — the ideation doc's repo-relative path plus the survivor reference
(its title or `R#`). Leave `source` unset for a direct topic. This keeps the ideate → brainstorm
provenance link traceable.

Write to `docs/brainstorms/YYYY-MM-DD-<topic>-requirements.md` (today's date; `<topic>` kebab-case).
Use repo-relative paths inside the doc. Confirm completion with the absolute path so the reference is
clickable.

## Phase 4 — Handoff

The brainstorm artifact carries handoff maturity **`requirements-ready`**, which feeds `/handoff` →
`mission-control` and is consumed by `/plan`.

Present next-step options and execute the operator's selection. Hide options that do not apply and
renumber so visible options stay contiguous. While any "Resolve before planning" question remains
open, hide **Plan** and **Build it now**: resolve those blocking questions first (one at a time), or,
if the operator proceeds anyway, convert each remaining item into an explicit decision, assumption, or
"Deferred to planning" question; if they pause, present the handoff as paused, not complete.

Options:

1. **Plan it with `/plan` (recommended)** — move to `/plan` for structured implementation planning.
   Pass the requirements doc path. Shown only when no "Resolve before planning" question remains.
2. **Sharpen with `/spec`** — hand the requirements doc to `/spec` for a relentless WHAT-rigor pass
   (five-Why, scope/MVP/out-of-scope/failure-mode lock, read-code-first grounding) before planning or
   handoff. Pass the requirements doc path. Shown when a requirements doc exists and needs precision
   before it can drive work. (Divergent `/brainstorm` → convergent `/spec`.)
3. **Hand off via `/handoff`** — route the `requirements-ready` artifact to `mission-control` as a
   prepared issue draft for another team or a later session. Shown when a requirements doc exists.
4. **Review with `/doc-review`** — dispatch a readiness review of the requirements doc before
   planning. Shown when a requirements doc exists.
5. **More clarifying questions** — return to Phase 1.3, keep refining scope, edge cases, and
   constraints one question at a time, then return here. Always shown.
6. **Back to `/office-hours`** — when the topic turns out to be more open thought-partner work than a
   concrete requirements ask. Always available.
7. **Done for now** — the requirements doc is saved and resumable later. Always shown.

Use `AskUserQuestion` when 4 or fewer options are visible; render a numbered list ("Pick a number or
describe what you want.") when 5 or more are visible. Never silently skip the question.

When the run ends or hands off, close with the requirements doc's absolute path, the key decisions, and
the recommended next step (`/plan` when ready, or `/office-hours` if it bounced back). When paused with
blocking questions still open, state that planning is blocked by those questions and that the operator
can resume with `/brainstorm`.

## Dropped from the CE original

No HTML rendering or output-mode resolution; no Proof / HITL review loop; no non-software / universal
brainstorming mode; no Slack researcher; no dedicated Visualizations affordance (introduce a diagram
ad hoc via agent agency when it genuinely helps). The artifact is always a single markdown file under
`docs/brainstorms/`. Scratch, when needed, goes under `.claude/saga/`, never `/tmp`.
